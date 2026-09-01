import argparse
import logging
import math
import signal
import sys
import threading
import time

import yaml
from systemd.journal import JournalHandler
from wb_common.mqtt_client import MQTTClient
from yaml.loader import SafeLoader

from .device_messenger import MqttMessenger
from .metrics_dict import METRICS

logger = logging.getLogger(__name__)
logger.addHandler(JournalHandler())
logger.setLevel(logging.INFO)

EXIT_FAILURE = 1
EXIT_INVALID_ARGUMENT = 2
EXIT_CONFIG_ERROR = 6
EXIT_STOPPED = 7

MQTT_AUTH_ERROR_CODES = (4, 5)
MQTT_CLEANUP_TIMEOUT_S = 2.0


class MetricClient:
    def __init__(self, broker_url, device_name, metrics_list):
        self._mqtt_client = MQTTClient("wb-mqtt-metrics", broker_url)
        self._mqtt_client.on_connect = self._on_connect
        self._mqtt_client.on_disconnect = self._on_disconnect
        self._mqtt_client.will_set(f"/devices/{device_name}/meta/error", "r", retain=True)

        self._messenger = MqttMessenger(client=self._mqtt_client, device_name=device_name)
        self._metrics = [METRICS[metric](self._messenger) for metric in metrics_list]
        self._stop_event = threading.Event()
        self._connected = threading.Event()
        self._exit_code = EXIT_FAILURE

    def _on_connect(self, _, __, ___, rc):
        code = getattr(rc, "value", rc)
        if code != 0:
            logger.error("MQTT connection failed, rc=%s", code)
            if not self._stop_event.is_set():
                self._exit_code = EXIT_INVALID_ARGUMENT if code in MQTT_AUTH_ERROR_CODES else EXIT_FAILURE
                self._stop_event.set()
            return

        self._connected.set()
        try:
            self._messenger.create_device()
            for metric in self._metrics:
                metric.create()
                metric.send()
        except Exception:  # pylint: disable=broad-except
            logger.exception("Failed to publish metrics after MQTT connection")
            self._exit_code = EXIT_FAILURE
            self._stop_event.set()

    def _on_disconnect(self, _, __, rc):
        self._connected.clear()
        if rc != 0:
            logger.error("Unexpected disconnection.")

    def _signal(self, *_):
        logger.info("Asynchronous interrupt, stopping")
        if not self._stop_event.is_set():
            self._exit_code = EXIT_STOPPED
        self._stop_event.set()

    def run(self, period):
        signal.signal(signal.SIGINT, self._signal)
        signal.signal(signal.SIGTERM, self._signal)
        self._mqtt_client.start()

        while not self._stop_event.wait(period):
            if not self._connected.is_set():
                continue
            logger.debug("Sending metrics")
            for metric in self._metrics:
                metric.send()

        return self._exit_code

    @staticmethod
    def _wait_for_cleanup(publications):
        deadline = time.monotonic() + MQTT_CLEANUP_TIMEOUT_S
        unconfirmed = 0
        for _, publication in publications:
            try:
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    publication.wait_for_publish(timeout=remaining)
                if remaining <= 0 or not publication.is_published():
                    unconfirmed += 1
            except (RuntimeError, ValueError):
                unconfirmed += 1
        if unconfirmed:
            logger.error(
                "Failed to clear %d of %d retained MQTT topics within %.1f seconds",
                unconfirmed,
                len(publications),
                MQTT_CLEANUP_TIMEOUT_S,
            )

    def stop(self, remove_device=False):
        try:
            if remove_device:
                if not self._connected.is_set():
                    logger.error("Unable to remove virtual device: MQTT broker is unavailable")
                else:
                    logger.info("Removing virtual device")
                    self._wait_for_cleanup(self._messenger.remove_device())
        finally:
            logger.info("Stopping MQTT client")
            self._mqtt_client.stop()


def load_config(config_path):
    with open(config_path, encoding="utf-8") as config_file:
        data = yaml.load(config_file, Loader=SafeLoader)
    broker_url = data["mqtt"]["broker"]
    period = data["mqtt"]["period"]
    device_name = data["mqtt"]["device-name"]
    metrics_list = data["metrics"]["list"]
    if metrics_list is None:
        metrics_list = []
    if not isinstance(broker_url, str) or not broker_url.strip():
        raise TypeError("mqtt.broker must be a non-empty string")
    if (
        isinstance(period, bool)
        or not isinstance(period, (int, float))
        or not math.isfinite(period)
        or period <= 0
    ):
        raise TypeError("mqtt.period must be a positive finite number")
    if (
        not isinstance(device_name, str)
        or not device_name.strip()
        or any(char in device_name for char in "/+#")
    ):
        raise TypeError("mqtt.device-name must be a valid MQTT device id")
    if not isinstance(metrics_list, list) or not all(isinstance(metric, str) for metric in metrics_list):
        raise TypeError("metrics.list must be a list of strings")
    if len(set(metrics_list)) != len(metrics_list):
        raise TypeError("metrics.list must not contain duplicates")
    unknown_metrics = set(metrics_list) - METRICS.keys()
    if unknown_metrics:
        raise TypeError(f"unknown metrics: {', '.join(sorted(unknown_metrics))}")
    return broker_url, period, device_name, metrics_list


def main(argv=None):
    if argv is None:
        argv = sys.argv

    parser = argparse.ArgumentParser(
        description="The tool to send metrics", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-c", "--config", type=str, default="/etc/wb-mqtt-metrics.conf", help="get data from config"
    )

    args = parser.parse_args(argv[1:])

    try:
        broker_url, period, device_name, metrics_list = load_config(args.config)
    except (OSError, yaml.YAMLError, KeyError, TypeError, OverflowError) as error:
        logger.error("Failed to read config %s: %s", args.config, error)
        return EXIT_CONFIG_ERROR

    if not metrics_list:
        logger.info("No metrics enabled, nothing to do")
        return EXIT_STOPPED

    client = None
    exit_code = EXIT_FAILURE
    try:
        client = MetricClient(broker_url, device_name, metrics_list)
        exit_code = client.run(period)
    except Exception:  # pylint: disable=broad-except
        logger.exception("wb-mqtt-metrics failed")
    finally:
        if client is not None:
            try:
                client.stop(remove_device=exit_code == EXIT_STOPPED)
            except Exception:  # pylint: disable=broad-except
                logger.exception("Failed to stop wb-mqtt-metrics cleanly")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

import argparse
import logging
import signal
import sys
import threading
from urllib.parse import urlparse

import yaml
from systemd.journal import JournalHandler
from wb_common.mqtt_client import MQTTClient
from yaml.loader import SafeLoader

from .device_messenger import MqttMessenger
from .metrics_dict import METRICS

logger = logging.getLogger(__name__)
logger.addHandler(JournalHandler())
logger.setLevel(logging.INFO)

# Exit codes from the WB service guideline; 2 and 6 are RestartPreventExitStatus in the unit.
EXIT_SUCCESS = 0
EXIT_INVALIDARGUMENT = 2
EXIT_NOTCONFIGURED = 6
EXIT_NOTRUNNING = 7
# CONNACK codes for a rejected login: bad user name or password, not authorized
MQTT_AUTH_ERRORS = (4, 5)
# broker URL forms wb-common's MQTTClient.start() accepts: unix:///path, or host:port under these schemes
BROKER_URL_HOST_SCHEMES = ("tcp", "mqtt-tcp", "ws")


class MetricClient:
    def __init__(self, broker_url, device_name, metrics_list):
        self._mqtt_client = MQTTClient("wb-mqtt-metrics", broker_url)
        self._mqtt_client.on_connect = self._on_connect
        self._mqtt_client.on_disconnect = self._on_disconnect

        self._messenger = MqttMessenger(client=self._mqtt_client, device_name=device_name)
        self._metrics = [METRICS[metric](self._messenger) for metric in metrics_list]
        self._stop_event = threading.Event()
        self._exit_code = EXIT_SUCCESS

    def _on_connect(self, _, __, ___, rc):
        if rc != 0:
            logger.error("MQTT connection failed with rc %s", rc)
            if rc in MQTT_AUTH_ERRORS:
                # a rejected login is a configuration problem, paho would retry it forever: exit with 2
                self._exit_code = EXIT_INVALIDARGUMENT
                self._stop_event.set()
            return

        # WB service guideline: republish the meta and the last values in the connect handler. A
        # reconnect usually follows a broker restart, and the republish is cheap and idempotent, so
        # the first connection and every reconnect are treated the same
        self._messenger.create_device()
        for metric in self._metrics:
            metric.create()
            metric.send()

    def _on_disconnect(self, _, __, rc):
        if rc != 0:
            logger.error("Unexpected disconnection.")

    def _signal(self, *_):
        logger.info("Asynchronous interrupt, stopping")
        self._stop_event.set()

    def run(self, period):
        """
        Send the metrics every period until a signal or a rejected MQTT login; returns the exit code.
        """
        signal.signal(signal.SIGINT, self._signal)
        signal.signal(signal.SIGTERM, self._signal)
        self._mqtt_client.start(retry_first_connection=True)

        while not self._stop_event.is_set():
            # without a broker the values would only pile up in paho's queue; on_connect sends fresh ones
            if self._mqtt_client.is_connected():
                logger.debug("Sending metrics")
                for metric in self._metrics:
                    metric.send()
            # wait() returns as soon as _signal() sets the event. time.sleep() would not:
            # it is resumed after the handler returns (PEP 475), delaying shutdown by up
            # to a full period, long enough for systemd to SIGKILL before cleanup runs.
            self._stop_event.wait(period)
        return self._exit_code

    def stop(self):
        if self._mqtt_client.is_connected():
            logger.info("Removing virtual device")
            self._messenger.remove_device()
        else:
            logger.error("MQTT broker is not connected, retained topics cannot be removed")
        logger.info("Stopping mqtt client")
        self._mqtt_client.stop()


def check_broker_url(url):
    """
    Return url if wb-common's MQTTClient.start() can use it, otherwise raise ValueError.

    The message never carries the URL: it may hold a password and ends up in the journal.
    """
    parsed = urlparse(str(url))  # YAML may hand over a number instead of a string
    if parsed.scheme == "unix" and parsed.path:
        return url
    if parsed.scheme in BROKER_URL_HOST_SCHEMES and parsed.port:  # .port raises on a non-numeric port
        return url
    raise ValueError("broker URL must be unix:///path or tcp://host:port (also mqtt-tcp://, ws://)")


def read_config(path):
    """
    Return (broker_url, period, device_name, metrics_list); raises on a missing or invalid file.
    """
    with open(path, encoding="utf-8") as f:
        data = yaml.load(f, Loader=SafeLoader)
    metrics_list = data["metrics"]["list"] or []
    unknown = [name for name in metrics_list if name not in METRICS]
    if unknown:
        raise ValueError(f"unknown metrics {unknown}, known metrics: {sorted(METRICS)}")
    period = data["mqtt"]["period"]
    if not isinstance(period, (int, float)) or period <= 0:
        raise ValueError(f"period must be a positive number, not {period!r}")
    return check_broker_url(data["mqtt"]["broker"]), period, data["mqtt"]["device-name"], metrics_list


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
        broker_url, period, device_name, metrics_list = read_config(args.config)
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
        logger.error("Cannot read config %s: %s", args.config, exc)
        return EXIT_NOTCONFIGURED
    if not metrics_list:
        logger.info("No metrics configured, nothing to do")
        return EXIT_NOTRUNNING

    client = MetricClient(broker_url, device_name, metrics_list)

    try:
        return client.run(period)
    finally:
        client.stop()


if __name__ == "__main__":
    sys.exit(main())

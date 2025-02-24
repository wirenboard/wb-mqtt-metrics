import argparse
import logging
import signal
import sys
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


class MetricClient:
    def __init__(self, broker_url, device_name, metrics_list):
        self._mqtt_client = MQTTClient("wb-mqtt-metrics", broker_url)
        self._mqtt_client.on_connect = self._on_connect
        self._mqtt_client.on_disconnect = self._on_disconnect

        self._messenger = MqttMessenger(client=self._mqtt_client, device_name=device_name)
        self._metrics = [METRICS[metric](self._messenger) for metric in metrics_list]
        self._stopped = False

    def _on_connect(self, _, __, ___, rc):
        if rc == 0:
            self._messenger.create_device()
            for metric in self._metrics:
                metric.create()
                metric.send()

    def _on_disconnect(self, _, __, rc):
        if rc != 0:
            logger.error("Unexpected disconnection.")

    def _signal(self, *_):
        logger.debug("Asynchronous interrupt, stopping")
        self._stopped = True

    def run(self, period):
        self._mqtt_client.start()

        signal.signal(signal.SIGINT, self._signal)
        signal.signal(signal.SIGTERM, self._signal)

        while not self._stopped:
            logger.debug("Sending metrics")
            for metric in self._metrics:
                metric.send()
            time.sleep(period)

    def stop(self):
        logger.info("Removing virtual device")
        self._messenger.remove_device()
        logger.info("Stopping mqtt client")
        self._mqtt_client.stop()


def main(argv=None):
    if argv is None:
        argv = sys.argv

    parser = argparse.ArgumentParser(description="The tool to send metrics")

    parser.add_argument(
        "-c", "--config", type=str, default="/etc/wb-mqtt-metrics.conf", help="get data from config"
    )

    args = parser.parse_args(argv[1:])

    with open(args.config, encoding="utf-8") as f:
        data = yaml.load(f, Loader=SafeLoader)
        broker_url = data["mqtt"]["broker"]
        period = data["mqtt"]["period"]
        device_name = data["mqtt"]["device-name"]

        metrics_list = data["metrics"]["list"]

    client = MetricClient(broker_url, device_name, metrics_list)

    try:
        client.run(period)
    finally:
        client.stop()


if __name__ == "__main__":
    sys.exit(main())

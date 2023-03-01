import argparse
import logging
import sys
import time

import yaml
from systemd.journal import JournalHandler
from wb_common.mqtt_client import MQTTClient
from yaml.loader import SafeLoader

from .device_messenger import DeviceMessenger
from .metrics_dict import METRICS

logger = logging.getLogger(__name__)
logger.addHandler(JournalHandler())
logger.setLevel(logging.INFO)


def connect_mqtt(broker_url) -> MQTTClient:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT Broker %s!", broker_url)
        else:
            logger.error("Failed to connect, return code %d\n", rc)

    def on_disconnect(client, userdata, rc):
        if rc != 0:
            logger.error("Unexpected disconnection.")

    client = MQTTClient("wb-mqtt-metrics", broker_url)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect()

    return client


def main(argv=None):
    if argv is None:
        argv = sys.argv

    parser = argparse.ArgumentParser(description="The tool to send metrics")

    parser.add_argument("-c", "--config", action="store", help="get data from config")

    args = parser.parse_args(argv[1:])

    with open(args.config, encoding="utf-8") as f:
        data = yaml.load(f, Loader=SafeLoader)
        broker_url = data["mqtt"]["broker"]
        period = data["mqtt"]["period"]
        device_name = data["mqtt"]["device-name"]

        metrics_list = data["metrics"]["list"]

    client = connect_mqtt(broker_url)
    messenger = DeviceMessenger(client=client, device_name=device_name)

    metrics = []
    for metric in metrics_list:
        metrics.append(METRICS[metric](messenger))

    try:
        while True:
            for metric in metrics:
                metric.send(messenger)
            time.sleep(period)
    finally:
        client.disconnect()


if __name__ == "__main__":
    sys.exit(main())

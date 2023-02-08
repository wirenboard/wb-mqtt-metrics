import argparse
import random
import sys
import time

import yaml
from paho.mqtt import client as mqtt_client
from yaml.loader import SafeLoader

from .device_messenger import DeviceMessenger
from .metrics_dict import METRICS


def connect_mqtt(broker, port) -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    def on_disconnect(client, userdata, rc):
        if rc != 0:
            print("Unexpected disconnection.")

    client_id = random.randint(0, 255)
    client = mqtt_client.Client('python-mqtt-wb-{0}'.format(client_id))
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect(broker, port)

    return client


def main(argv=None):
    if argv is None:
        argv = sys.argv

    parser = argparse.ArgumentParser(description="The tool to send metrics")

    parser.add_argument("-c", "--config", action="store", help="get data from config")

    args = parser.parse_args(argv[1:])

    with open(args.config, encoding="utf-8") as f:
        data = yaml.load(f, Loader=SafeLoader)
        broker = data['mqtt']['broker']
        port = data['mqtt']['port']
        period = data['mqtt']['period']
        device_name = data['mqtt']['device-name']

        metrics_list = data["metrics"]["list"]

    client = connect_mqtt(broker, port)
    messenger = DeviceMessenger(client=client, device_name=device_name)

    metrics = []
    for metric in metrics_list:
        metrics.append(METRICS[metric](messenger))

    try:
        client.loop_start()

        while True:
            for metric in metrics:
                metric.send(messenger)
            time.sleep(period)
    finally:
        client.loop_stop()


if __name__ == "__main__":
    sys.exit(main())

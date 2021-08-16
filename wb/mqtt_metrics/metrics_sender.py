import random
import time
from threading import Thread
from .metrics_dict import METRICS
from .device_messenger import DeviceMessenger
import sys
import yaml
from yaml.loader import SafeLoader
import argparse

from paho.mqtt import client as mqtt_client

metrics = []


def connect_mqtt(broker, port) -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    client_id = random.randint(0, 255)
    client = mqtt_client.Client('python-mqtt-wb-{0}'.format(client_id))
    client.on_connect = on_connect
    client.connect(broker, port)
    return client


def create_device(metrics_list, d):
    for metric in metrics_list:
        metrics.append(METRICS[metric](d))


def thread2_loop(period, device_messenger: DeviceMessenger):
    while True:
        for metric in metrics:
            metric.send(device_messenger)
        time.sleep(period)


def main(argv=sys.argv):
    parser = argparse.ArgumentParser(description='The tool to send metrics')

    parser.add_argument('-c', '--config', action='store', help='get data from config')

    args = parser.parse_args(argv[1:])

    with open(args.config) as f:
        data = yaml.load(f, Loader=SafeLoader)
        broker = data['mqtt']['broker']
        port = data['mqtt']['port']
        period = data['mqtt']['period']
        device_name = data['mqtt']['device-name']

        metrics_list = data['metrics']['list']

    client = connect_mqtt(broker, port)
    d = DeviceMessenger(client=client, device_name=device_name)

    create_device(metrics_list, d)
    thread = Thread(target=thread2_loop, args=(period, d,))
    thread.start()
    client.loop_forever()


if __name__ == '__main__':
    sys.exit(main())

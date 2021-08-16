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


def connect_mqtt(broker, port, device_name) -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
            create_device(client, device_name)
        else:
            print("Failed to connect, return code %d\n", rc)

    client_id = random.randint(0, 255)
    client = mqtt_client.Client('python-mqtt-wb-{0}'.format(client_id))
    client.on_connect = on_connect
    client.connect(broker, port)
    return client


def create_device(client: mqtt_client, device_name):
    d = DeviceMessenger(client=client, device_name=device_name)

    for metric in METRICS:
        metrics.append(metric(d))


def thread2_loop(period):
    while True:
        for metric in metrics:
            metric.send()
        time.sleep(period)


def main(argv=sys.argv):
    parser = argparse.ArgumentParser(description='The tool to send metrics')

    parser.add_argument('-c', '--config', action='store', help='get data from config')

    args = parser.parse_args(argv[1:])

    with open(args.config) as f:
        data = yaml.load(f, Loader=SafeLoader)
        broker = data['broker']
        port = data['port']
        period = data['period']
        device_name = data['device-name']

    client = connect_mqtt(broker, port, device_name)
    thread = Thread(target=thread2_loop, args=(period, ))
    thread.start()
    client.loop_forever()


if __name__ == '__main__':
    sys.exit(main())

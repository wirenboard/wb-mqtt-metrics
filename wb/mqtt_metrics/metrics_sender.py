import time
from threading import Thread
from wb.mqtt_metrics.metrics_dict import METRICS
from wb.mqtt_metrics.device_messenger import DeviceMessenger
import sys

from paho.mqtt import client as mqtt_client

# BROKER = '192.168.42.1'
BROKER = '192.168.43.173'
PORT = 1883
DEVICE_NAME = 'metrics'
metrics = []


def connect_mqtt() -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
            create_device(client)
        else:
            print("Failed to connect, return code %d\n", rc)

    client = mqtt_client.Client('python-mqtt-wb-255')
    client.on_connect = on_connect
    client.connect(BROKER, PORT)
    return client


def create_device(client: mqtt_client):
    d = DeviceMessenger(client=client, device_name=DEVICE_NAME)

    for metric in METRICS:
        metrics.append(metric(d))


def thread2_loop():
    while True:
        for metric in metrics:
            metric.send()
        time.sleep(10)


def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        print("Received `{0}` from `{1}` topic".format(msg.payload.decode(), msg.topic))

        if msg.topic == '/devices/{0}/meta/name'.format(DEVICE_NAME):
            thread = Thread(target=thread2_loop, args=())
            thread.start()

    client.subscribe('/devices/{0}/#'.format(DEVICE_NAME))
    client.on_message = on_message


def main():
    client = connect_mqtt()
    subscribe(client)
    client.loop_forever()


if __name__ == '__main__':
    sys.exit(main())

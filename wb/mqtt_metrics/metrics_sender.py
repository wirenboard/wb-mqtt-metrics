import argparse
import random
import sys
import time
import urllib.parse
from threading import Thread

import paho_socket
import yaml
from paho.mqtt import client as mqtt_client
from yaml.loader import SafeLoader

from .device_messenger import DeviceMessenger
from .metrics_dict import METRICS

metrics = []


def connect_mqtt(broker, port, device_name, metrics_list, period) -> mqtt_client:
    thread_info = {"thread": None, "must_work": False}

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
            d = DeviceMessenger(client=client, device_name=device_name)
            create_device(metrics_list, d)

            thread_info["must_work"] = True
            thread_info["thread"] = Thread(
                target=thread2_loop,
                args=(
                    period,
                    d,
                    thread_info,
                ),
            )
            thread_info["thread"].start()
        else:
            print("Failed to connect, return code %d\n", rc)

    def on_disconnect(client, userdata, rc):
        if rc != 0:
            print("Unexpected disconnection.")
        thread_info["must_work"] = False
        thread_info["thread"].join()

    client_id = "python-mqtt-wb-{0}".format(random.randint(0, 255))
    url = urllib.parse.urlparse(broker)
    if url.scheme == "unix":
        client = paho_socket.Client(client_id)
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.sock_connect(url.path)
    else:
        client = mqtt_client.Client(client_id)
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.connect(broker, port)

    return client


def create_device(metrics_list, d):
    for metric in metrics_list:
        metrics.append(METRICS[metric](d))


def thread2_loop(period, device_messenger: DeviceMessenger, thread_info):
    while thread_info["must_work"]:
        for metric in metrics:
            metric.send(device_messenger)
        time.sleep(period)


def main(argv=sys.argv):
    parser = argparse.ArgumentParser(description="The tool to send metrics")

    parser.add_argument("-c", "--config", action="store", help="get data from config")

    args = parser.parse_args(argv[1:])

    with open(args.config) as f:
        data = yaml.load(f, Loader=SafeLoader)
        broker = data["mqtt"]["broker"]
        try:
            port = data["mqtt"]["port"]
        except KeyError:
            port = 0
        period = data["mqtt"]["period"]
        device_name = data["mqtt"]["device-name"]

        metrics_list = data["metrics"]["list"]

    client = connect_mqtt(broker, port, device_name, metrics_list, period)
    client.loop_forever()


if __name__ == "__main__":
    sys.exit(main())

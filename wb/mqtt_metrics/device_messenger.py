import json

from wb_common.mqtt_client import MQTTClient


class DeviceMessenger:
    def __init__(self, client: MQTTClient, device_name: str):
        self.client = client
        self.device_name = device_name

        meta = {"driver": "wb-mqtt-metrics", "title": {"en": "Metrics", "ru": "Метрики"}}
        client.publish(f"/devices/{self.device_name}/meta", json.dumps(meta), retain=True, qos=1)
        client.publish(f"/devices/{self.device_name}/meta/driver", meta["driver"], retain=True, qos=1)
        client.publish(f"/devices/{self.device_name}/meta/name", meta["title"]["en"], retain=True, qos=1)
        client.publish(f"/devices/{self.device_name}/meta/error", None, retain=True, qos=1)

    def publish(self, topic, value):
        self.client.publish(topic, value, retain=True, qos=1)

    # pylint: disable=too-many-arguments
    def create(self, metric_name, ctrl_type, units="", ctrl_min=0, ctrl_max=None):
        self.publish(f"/devices/{self.device_name}/controls/{metric_name}/meta/type", ctrl_type)

        if ctrl_type == "value":
            self.publish(f"/devices/{self.device_name}/controls/{metric_name}/meta/units", units)

        if ctrl_type in {"value", "range"}:
            if ctrl_max:
                self.publish(f"/devices/{self.device_name}/controls/{metric_name}/meta/max", ctrl_max)
            self.publish(f"/devices/{self.device_name}/controls/{metric_name}/meta/min", ctrl_min)

    def send(self, metric_name, value):
        self.publish(f"/devices/{self.device_name}/controls/{metric_name}", value)

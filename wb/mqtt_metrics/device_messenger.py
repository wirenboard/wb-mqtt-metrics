import json

from wb_common.mqtt_client import MQTTClient


class MqttMessenger:
    def __init__(self, client: MQTTClient, device_name: str):
        self.client = client
        self.device_name = device_name

    def create_device(self):
        meta = {"driver": "wb-mqtt-metrics", "title": {"en": "Metrics", "ru": "Метрики"}}
        self.client.publish(f"/devices/{self.device_name}/meta", json.dumps(meta), retain=True, qos=1)
        self.client.publish(f"/devices/{self.device_name}/meta/driver", meta["driver"], retain=True, qos=1)
        self.client.publish(f"/devices/{self.device_name}/meta/name", meta["title"]["en"], retain=True, qos=1)
        self.client.publish(f"/devices/{self.device_name}/meta/error", None, retain=True, qos=1)

    def _publish(self, topic, value):
        self.client.publish(topic, value, retain=True, qos=1)

    # pylint: disable=too-many-arguments
    def create_control(self, metric_name, ctrl_type, units="", ctrl_min=0, ctrl_max=None):
        meta = {"type": ctrl_type, "readonly": True}
        self._publish(f"/devices/{self.device_name}/controls/{metric_name}/meta/type", ctrl_type)
        self._publish(f"/devices/{self.device_name}/controls/{metric_name}/meta/readonly", "1")

        if ctrl_type == "value" and units:
            self._publish(f"/devices/{self.device_name}/controls/{metric_name}/meta/units", units)
            meta["units"] = units

        if ctrl_type in {"value", "range"}:
            if ctrl_max:
                self._publish(f"/devices/{self.device_name}/controls/{metric_name}/meta/max", ctrl_max)
                meta["max"] = ctrl_max
            self._publish(f"/devices/{self.device_name}/controls/{metric_name}/meta/min", ctrl_min)
            meta["min"] = ctrl_min

        self._publish(f"/devices/{self.device_name}/controls/{metric_name}/meta", json.dumps(meta))

    def send_value(self, metric_name, value):
        self._publish(f"/devices/{self.device_name}/controls/{metric_name}", value)

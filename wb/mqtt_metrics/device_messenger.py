from wb_common.mqtt_client import MQTTClient


class DeviceMessenger:
    def __init__(self, client: MQTTClient, device_name: str):
        self.client = client
        self.device_name = device_name

        client.publish(
            "/devices/{0}/meta/name".format(self.device_name), self.device_name, retain=True, qos=1
        )
        client.publish("/devices/{0}/meta/error".format(self.device_name), None, retain=True, qos=1)

    def publish(self, topic, value):
        self.client.publish(topic, value, retain=True, qos=1)

    def create(self, metric_name, ctrl_type, units="", ctrl_min=0, ctrl_max=None):
        self.publish("/devices/{0}/controls/{1}/meta/type".format(self.device_name, metric_name), ctrl_type)

        if ctrl_type == "value":
            self.publish("/devices/{0}/controls/{1}/meta/units".format(self.device_name, metric_name), units)

        if ctrl_type in {"value", "range"}:
            if ctrl_max:
                self.publish(
                    "/devices/{0}/controls/{1}/meta/max".format(self.device_name, metric_name), ctrl_max
                )
            self.publish("/devices/{0}/controls/{1}/meta/min".format(self.device_name, metric_name), ctrl_min)

    def send(self, metric_name, value):
        self.publish("/devices/{0}/controls/{1}".format(self.device_name, metric_name), value)

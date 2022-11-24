from paho.mqtt import client as mqtt_client


class DeviceMessenger:
    def __init__(self, client: mqtt_client, device_name):
        self.client = client
        self.device_name = device_name

        client.publish(
            "/devices/{0}/meta/name".format(self.device_name), self.device_name, retain=True, qos=1
        )
        client.publish("/devices/{0}/meta/error".format(self.device_name), None, retain=True, qos=1)

    def publish(self, topic, value):
        self.client.publish(topic, value, retain=True, qos=1)

    def create(self, metric_name, type, units="", min=0, max=None):
        self.publish("/devices/{0}/controls/{1}/meta/type".format(self.device_name, metric_name), type)

        if type == "value":
            self.publish("/devices/{0}/controls/{1}/meta/units".format(self.device_name, metric_name), units)

        if type == "value" or type == "range":
            if max:
                self.publish("/devices/{0}/controls/{1}/meta/max".format(self.device_name, metric_name), max)
            self.publish("/devices/{0}/controls/{1}/meta/min".format(self.device_name, metric_name), min)

    def send(self, metric_name, value):
        self.publish("/devices/{0}/controls/{1}".format(self.device_name, metric_name), value)

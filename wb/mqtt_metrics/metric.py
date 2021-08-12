from abc import ABCMeta, abstractmethod
from wb.mqtt_metrics.device_messenger import DeviceMessenger


class Metric(metaclass=ABCMeta):

    def __init__(self, device_messenger: DeviceMessenger):
        self.device_messenger = device_messenger
        self.create()

    @abstractmethod
    def send(self):
        pass

    @abstractmethod
    def create(self):
        pass

from abc import ABCMeta, abstractmethod
from .device_messenger import DeviceMessenger


class Metric(metaclass=ABCMeta):

    def __init__(self, device_messenger: DeviceMessenger):
        self.create(device_messenger)

    @abstractmethod
    def send(self, device_messenger: DeviceMessenger):
        pass

    @abstractmethod
    def create(self, device_messenger: DeviceMessenger):
        pass

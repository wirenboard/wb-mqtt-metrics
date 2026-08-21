import os
import shutil
from abc import ABCMeta, abstractmethod

from .device_messenger import MqttMessenger

MIB = 1024 * 1024
KIB_PER_MIB = 1024

MEMINFO_PATH = "/proc/meminfo"
MOUNTINFO_PATH = "/proc/self/mountinfo"
SYS_DEV_BLOCK_PATH = "/sys/dev/block"


def read_meminfo():
    meminfo = {}
    with open(MEMINFO_PATH, encoding="utf-8") as meminfo_file:
        for line in meminfo_file:
            name, _, rest = line.partition(":")
            meminfo[name] = int(rest.split()[0])
    return meminfo


def get_ram_data():
    meminfo = read_meminfo()

    ram_total = meminfo["MemTotal"] // KIB_PER_MIB
    ram_available = meminfo["MemAvailable"] // KIB_PER_MIB
    swap_total = meminfo["SwapTotal"] // KIB_PER_MIB
    swap_free = meminfo["SwapFree"] // KIB_PER_MIB

    return {
        "ram_total": ram_total,
        "ram_used": ram_total - ram_available,
        "ram_available": ram_available,
        "swap_total": swap_total,
        "swap_used": swap_total - swap_free,
    }


def get_load_averages():
    return [round(x, 2) for x in os.getloadavg()]


def get_df(path):
    usage = shutil.disk_usage(path)
    return [usage.used // MIB, usage.total // MIB]


def get_dev_root_link():
    devno = None
    with open(MOUNTINFO_PATH, encoding="utf-8") as mountinfo_file:
        for line in mountinfo_file:
            fields = line.split()
            if len(fields) > 4 and fields[4] == "/":
                devno = fields[2]

    if devno is None:
        return "unknown"

    try:
        return "/dev/" + os.path.basename(os.readlink(os.path.join(SYS_DEV_BLOCK_PATH, devno)))
    except OSError:
        return "unknown"


class Metric(metaclass=ABCMeta):
    def __init__(self, messenger: MqttMessenger):
        self._messenger = messenger

    @abstractmethod
    def send(self):
        pass

    @abstractmethod
    def create(self):
        pass


class LoadAverage(Metric):
    CONTROL_DEFINITIONS = {
        "load_average_1min": {
            "title": {"en": "Load average (1 min)", "ru": "Средняя нагрузка (1 мин)"},
            "type": "value",
            "units": "tasks",
        },
        "load_average_5min": {
            "title": {"en": "Load average (5 min)", "ru": "Средняя нагрузка (5 мин)"},
            "type": "value",
            "units": "tasks",
        },
        "load_average_15min": {
            "title": {"en": "Load average (15 min)", "ru": "Средняя нагрузка (15 мин)"},
            "type": "value",
            "units": "tasks",
        },
    }

    def create(self):
        for metric_name, meta in self.CONTROL_DEFINITIONS.items():
            self._messenger.create_control(metric_name, meta)

    def send(self):
        load_averages = get_load_averages()
        for metric_name, value in zip(self.CONTROL_DEFINITIONS, load_averages):
            self._messenger.send_value(metric_name, value)


class FreeRam(Metric):
    CONTROL_DEFINITIONS = {
        "ram_available": {
            "title": {"en": "RAM available", "ru": "Доступная оперативная память"},
            "type": "value",
            "units": "MiB",
        },
        "ram_used": {
            "title": {"en": "RAM used", "ru": "Используемая оперативная память"},
            "type": "value",
            "units": "MiB",
        },
        "ram_total": {
            "title": {"en": "RAM total", "ru": "Всего оперативной памяти"},
            "type": "value",
            "units": "MiB",
        },
        "swap_total": {
            "title": {"en": "Swap total", "ru": "Всего swap памяти"},
            "type": "value",
            "units": "MiB",
        },
        "swap_used": {
            "title": {"en": "Swap used", "ru": "Используется swap"},
            "type": "value",
            "units": "MiB",
        },
    }

    def create(self):
        for metric_name, meta in self.CONTROL_DEFINITIONS.items():
            self._messenger.create_control(metric_name, meta)

        ram_data = get_ram_data()
        self._messenger.send_value("ram_total", ram_data["ram_total"])
        self._messenger.send_value("swap_total", ram_data["swap_total"])

    def send(self):
        ram_data = get_ram_data()
        self._messenger.send_value("ram_available", ram_data["ram_available"])
        self._messenger.send_value("ram_used", ram_data["ram_used"])
        self._messenger.send_value("swap_used", ram_data["swap_used"])


class DevRoot(Metric):
    CONTROL_DEFINITIONS = {
        "dev_root_used_space": {
            "title": {"en": "Used space in dev root", "ru": "Используемое место в корневом разделе"},
            "type": "value",
            "units": "MiB",
        },
        "dev_root_total_space": {
            "title": {"en": "Total space of dev root", "ru": "Общий размер корневого раздела"},
            "type": "value",
            "units": "MiB",
        },
        "dev_root_linked_on": {
            "title": {"en": "Dev root linked on", "ru": "Корневой раздел смонтирован на"},
            "type": "text",
        },
    }

    def create(self):
        for metric_name, meta in self.CONTROL_DEFINITIONS.items():
            self._messenger.create_control(metric_name, meta)

        df_dev_root = get_df("/")
        self._messenger.send_value("dev_root_linked_on", get_dev_root_link())
        self._messenger.send_value("dev_root_total_space", df_dev_root[1])

    def send(self):
        self._messenger.send_value("dev_root_used_space", get_df("/")[0])


class Data(Metric):
    CONTROL_DEFINITIONS = {
        "data_used_space": {
            "title": {"en": "Data used space", "ru": "Используемое место в разделе данных"},
            "type": "value",
            "units": "MiB",
        },
        "data_total_space": {
            "title": {"en": "Data total space", "ru": "Общий размер раздела данных"},
            "type": "value",
            "units": "MiB",
        },
    }

    def create(self):
        for metric_name, meta in self.CONTROL_DEFINITIONS.items():
            self._messenger.create_control(metric_name, meta)
        self._messenger.send_value("data_total_space", get_df("/mnt/data")[1])

    def send(self):
        self._messenger.send_value("data_used_space", get_df("/mnt/data")[0])

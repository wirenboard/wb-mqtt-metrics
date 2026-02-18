import shutil
import subprocess
from abc import ABCMeta, abstractmethod

from .device_messenger import MqttMessenger

FREE_PATH = shutil.which("free")
UPTIME_PATH = shutil.which("uptime")
DF_PATH = shutil.which("df")
MOUNT_PATH = shutil.which("mount")


def get_ram_data():
    with subprocess.Popen([FREE_PATH, "-m"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as proc:
        cmd_res = proc.stdout.readlines()

    keyword = "Mem:"
    memory_data = cmd_res[1].decode()
    memory_data = [int(x) for x in memory_data[memory_data.find(keyword) + len(keyword) :].split()]
    output = {"ram_total": memory_data[0], "ram_used": memory_data[1], "ram_available": memory_data[5]}

    keyword = "Swap:"
    memory_data = cmd_res[2].decode()
    memory_data = [int(x) for x in memory_data[memory_data.find(keyword) + len(keyword) :].split()]
    output["swap_total"] = memory_data[0]
    output["swap_used"] = memory_data[1]

    return output


def get_load_averages():
    with subprocess.Popen([UPTIME_PATH], stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as proc:
        cmd_res = proc.stdout.readlines()[0].decode()

    keyword = "load average: "
    load_averages = cmd_res[cmd_res.find(keyword) + len(keyword) :].split()
    load_averages[0] = load_averages[0][:-1]
    load_averages[1] = load_averages[1][:-1]
    return [float(x.replace(",", ".")) for x in load_averages]


def get_df(path):
    with subprocess.Popen([DF_PATH, "-m", path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as proc:
        cmd_res = proc.stdout.readlines()[1].decode()

    df_def_root_data = cmd_res.split()
    used = df_def_root_data[2]
    total = df_def_root_data[1]
    return [used, total]


def get_dev_root_link():
    with subprocess.Popen([MOUNT_PATH], stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as proc:
        for line in proc.stdout.readlines():
            line_str = line.decode()
            if " on / " in line_str:
                return line_str.split()[0]

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

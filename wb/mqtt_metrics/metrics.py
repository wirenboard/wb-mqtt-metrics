import os
import shutil
from abc import ABCMeta, abstractmethod

from .device_messenger import MqttMessenger

MIB = 1024 * 1024
KIB_PER_MIB = 1024

MEMINFO_PATH = "/proc/meminfo"
MOUNTINFO_PATH = "/proc/self/mountinfo"
SYS_DEV_BLOCK_PATH = "/sys/dev/block"

DATA_MOUNTPOINT = "/mnt/data"

SDCARD_DEVICE = "/dev/mmcblk1p1"
SDCARD_MOUNTPOINT = "/mnt/sdcard"


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


def find_mount(mountpoint):
    found = None
    with open(MOUNTINFO_PATH, encoding="utf-8") as mountinfo_file:
        for line in mountinfo_file:
            fields = line.split()
            if len(fields) > 4 and fields[4] == mountpoint:
                separator = fields.index("-", 6)
                found = (fields[2], fields[separator + 1])
    return found


def get_block_device(devno):
    if devno is None:
        return "unknown"

    try:
        return "/dev/" + os.path.basename(os.readlink(os.path.join(SYS_DEV_BLOCK_PATH, devno)))
    except OSError:
        return "unknown"


def get_dev_root_link():
    mount = find_mount("/")
    return get_block_device(mount[0] if mount else None)


def is_separate_filesystem(path):
    try:
        return os.stat(path).st_dev != os.stat("/").st_dev
    except OSError:
        return False


def is_sdcard_inserted():
    return os.path.exists(SDCARD_DEVICE)


def get_sdcard_devno():
    mount = find_mount(SDCARD_MOUNTPOINT)
    if mount is None or mount[1] == "autofs":
        return None
    return mount[0]


def get_sdcard_data(devno):
    stat = os.statvfs(SDCARD_MOUNTPOINT)
    return {
        "sdcard_used_space": (stat.f_blocks - stat.f_bfree) * stat.f_frsize // MIB,
        "sdcard_total_space": stat.f_blocks * stat.f_frsize // MIB,
        "sdcard_linked_on": get_block_device(devno),
        "sdcard_readonly": 1 if stat.f_flag & os.ST_RDONLY else 0,
    }


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

    def __init__(self, messenger: MqttMessenger):
        super().__init__(messenger)
        self._enabled = False

    def create(self):
        self._enabled = is_separate_filesystem(DATA_MOUNTPOINT)
        if not self._enabled:
            return

        for metric_name, meta in self.CONTROL_DEFINITIONS.items():
            self._messenger.create_control(metric_name, meta)
        self._messenger.send_value("data_total_space", get_df(DATA_MOUNTPOINT)[1])

    def send(self):
        if self._enabled:
            self._messenger.send_value("data_used_space", get_df(DATA_MOUNTPOINT)[0])


class SdCard(Metric):
    CONTROL_DEFINITIONS = {
        "sdcard_used_space": {
            "title": {"en": "SD card used space", "ru": "Используемое место на SD-карте"},
            "type": "value",
            "units": "MiB",
        },
        "sdcard_total_space": {
            "title": {"en": "SD card total space", "ru": "Общий размер SD-карты"},
            "type": "value",
            "units": "MiB",
        },
        "sdcard_linked_on": {
            "title": {"en": "SD card linked on", "ru": "Устройство SD-карты"},
            "type": "text",
        },
        "sdcard_readonly": {
            "title": {"en": "SD card read-only", "ru": "SD-карта только для чтения"},
            "type": "switch",
        },
    }

    def __init__(self, messenger: MqttMessenger):
        super().__init__(messenger)
        self._controls_created = False

    def create(self):
        if self._controls_created:
            self._create_controls()

    def send(self):
        data = self._read()
        if data is None:
            if self._controls_created:
                for metric_name in self.CONTROL_DEFINITIONS:
                    self._messenger.remove_control(metric_name)
                self._controls_created = False
            return

        if not self._controls_created:
            self._create_controls()
        for metric_name, value in data.items():
            self._messenger.send_value(metric_name, value)

    def _create_controls(self):
        for metric_name, meta in self.CONTROL_DEFINITIONS.items():
            self._messenger.create_control(metric_name, meta)
        self._controls_created = True

    def _read(self):
        devno = get_sdcard_devno() if is_sdcard_inserted() else None
        if devno is None:
            return None

        try:
            return get_sdcard_data(devno)
        except OSError:
            return None

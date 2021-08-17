import subprocess
from .metric import Metric


def get_ram_data():
    p = subprocess.Popen('free -m', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    cmd_res = p.stdout.readlines()[1].decode()
    keyword = "Mem:"
    memory_data = cmd_res[cmd_res.find(keyword) + len(keyword):].split()
    return [int(x) for x in memory_data]


def get_load_averages():
    p = subprocess.Popen('uptime', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    cmd_res = p.stdout.readlines()[0].decode()
    keyword = "load average: "
    load_averages = cmd_res[cmd_res.find(keyword) + len(keyword):].split()
    load_averages[0] = load_averages[0][:-1]
    load_averages[1] = load_averages[1][:-1]
    return [float(x.replace(',', '.')) for x in load_averages]


def get_df_dev_root():
    p = subprocess.Popen('df | grep /dev/root', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    cmd_res = p.stdout.readlines()[0].decode()
    df_def_root_data = cmd_res.split()
    mounted_on = df_def_root_data[5]
    used = df_def_root_data[2]
    total = df_def_root_data[1]
    return [mounted_on, used, total]


def get_df_dev_mmcblk0p6():
    p = subprocess.Popen('df | grep /dev/mmcblk0p6', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    cmd_res = p.stdout.readlines()[0].decode()
    df_dev_mmcblk0p6_data = cmd_res.split()
    used = df_dev_mmcblk0p6_data[2]
    total = df_dev_mmcblk0p6_data[1]
    return [used, total]


class LoadAverage(Metric):
    def create(self, device_messenger):
        device_messenger.create('load_average_1min', 'value', 'tasks')
        device_messenger.create('load_average_5min', 'value', 'tasks')
        device_messenger.create('load_average_15min', 'value', 'tasks')

    def send(self, device_messenger):
        load_averages = get_load_averages()
        device_messenger.send('load_average_1min', load_averages[0])
        device_messenger.send('load_average_5min', load_averages[1])
        device_messenger.send('load_average_15min', load_averages[2])


class FreeRam(Metric):
    def create(self, device_messenger):
        device_messenger.create('free_ram', 'value', 'MB')
        device_messenger.create('total_ram', 'value', 'MB')
        device_messenger.send('total_ram', get_ram_data()[0])

    def send(self, device_messenger):
        device_messenger.send('free_ram', get_ram_data()[2])


class DevRoot(Metric):
    def create(self, device_messenger):
        device_messenger.create('dev_root_used_space', 'value', 'KB')
        device_messenger.create('dev_root_total_space', 'value', 'KB')
        device_messenger.create('dev_root_mounted_on', 'text')
        device_messenger.send('dev_root_mounted_on', get_df_dev_root()[0])
        device_messenger.send('dev_root_total_space', get_df_dev_root()[2])

    def send(self, device_messenger):
        device_messenger.send('dev_root_used_space', get_df_dev_root()[1])


class DevMmcblk0p6(Metric):
    def create(self, device_messenger):
        device_messenger.create('dev_mmcblk0p6_used_space', 'value', 'KB')
        device_messenger.create('dev_mmcblk0p6_total_space', 'value', 'KB')
        device_messenger.send('dev_mmcblk0p6_total_space', get_df_dev_mmcblk0p6()[1])

    def send(self, device_messenger):
        device_messenger.send('dev_mmcblk0p6_used_space', get_df_dev_mmcblk0p6()[0])


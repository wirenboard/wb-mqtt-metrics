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


def get_df(cluster):
    p = subprocess.Popen('df -m | grep {0}'.format(cluster), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    cmd_res = p.stdout.readlines()[0].decode()
    df_def_root_data = cmd_res.split()
    used = df_def_root_data[2]
    total = df_def_root_data[1]
    return [used, total]


def get_dev_root_link():
    p = subprocess.Popen("mount|grep ' / '|cut -d' ' -f 1", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.stdout.readlines()[0].decode()


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
        device_messenger.create('ram_free', 'value', 'MiB')
        device_messenger.create('ram_total', 'value', 'MiB')
        device_messenger.send('ram_total', get_ram_data()[0])

    def send(self, device_messenger):
        device_messenger.send('ram_free', get_ram_data()[2])


class DevRoot(Metric):
    def create(self, device_messenger):
        device_messenger.create('dev_root_used_space', 'value', 'MiB')
        device_messenger.create('dev_root_total_space', 'value', 'MiB')
        device_messenger.create('dev_root_mounted_on', 'text')
        df_dev_root = get_df('/dev/root')
        device_messenger.send('dev_root_mounted_on', get_dev_root_link())
        device_messenger.send('dev_root_total_space', df_dev_root[1])

    def send(self, device_messenger):
        device_messenger.send('dev_root_used_space', get_df('/dev/root')[0])


class Data(Metric):
    def create(self, device_messenger):
        device_messenger.create('data_used_space', 'value', 'MiB')
        device_messenger.create('data_total_space', 'value', 'MiB')
        device_messenger.send('data_total_space', get_df('/dev/mmcblk0p6')[1])

    def send(self, device_messenger):
        device_messenger.send('data_used_space', get_df('/dev/mmcblk0p6')[0])


import subprocess
from wb.mqtt_metrics.metric import Metric


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


class LoadAverage(Metric):
    def create(self):
        self.device_messenger.create('load_average_1min', 'value', 'tasks')
        self.device_messenger.create('load_average_5min', 'value', 'tasks')
        self.device_messenger.create('load_average_15min', 'value', 'tasks')

    def send(self):
        self.device_messenger.send('load_average_1min', get_load_averages()[0])
        self.device_messenger.send('load_average_5min', get_load_averages()[1])
        self.device_messenger.send('load_average_15min', get_load_averages()[2])


class FreeRam(Metric):
    def create(self):
        self.device_messenger.create('free_ram', 'value', 'MB')
        self.device_messenger.create('total_ram', 'value', 'MB')
        self.device_messenger.send('total_ram', get_ram_data()[0])

    def send(self):
        self.device_messenger.send('free_ram', get_ram_data()[2])


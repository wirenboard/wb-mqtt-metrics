import subprocess

from .metric import Metric


def get_ram_data():
    p = subprocess.Popen("free -m", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    cmd_res = p.stdout.readlines()

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
    p = subprocess.Popen("uptime", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    cmd_res = p.stdout.readlines()[0].decode()
    keyword = "load average: "
    load_averages = cmd_res[cmd_res.find(keyword) + len(keyword) :].split()
    load_averages[0] = load_averages[0][:-1]
    load_averages[1] = load_averages[1][:-1]
    return [float(x.replace(",", ".")) for x in load_averages]


def get_df(cluster):
    p = subprocess.Popen(
        "df -m | grep {0}".format(cluster), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    cmd_res = p.stdout.readlines()[0].decode()
    df_def_root_data = cmd_res.split()
    used = df_def_root_data[2]
    total = df_def_root_data[1]
    return [used, total]


def get_dev_root_link():
    p = subprocess.Popen(
        "mount|grep ' / '|cut -d' ' -f 1", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    return p.stdout.readlines()[0].decode()


class LoadAverage(Metric):
    def create(self, device_messenger):
        device_messenger.create("load_average_1min", "value", "tasks")
        device_messenger.create("load_average_5min", "value", "tasks")
        device_messenger.create("load_average_15min", "value", "tasks")

    def send(self, device_messenger):
        load_averages = get_load_averages()
        device_messenger.send("load_average_1min", load_averages[0])
        device_messenger.send("load_average_5min", load_averages[1])
        device_messenger.send("load_average_15min", load_averages[2])


class FreeRam(Metric):
    def create(self, device_messenger):
        device_messenger.create("ram_available", "value", "MiB")
        device_messenger.create("ram_used", "value", "MiB")
        device_messenger.create("ram_total", "value", "MiB")
        device_messenger.create("swap_total", "value", "MiB")
        device_messenger.create("swap_used", "value", "MiB")
        ram_data = get_ram_data()
        device_messenger.send("ram_total", ram_data["ram_total"])
        device_messenger.send("swap_total", ram_data["swap_total"])

    def send(self, device_messenger):
        ram_data = get_ram_data()
        device_messenger.send("ram_available", ram_data["ram_available"])
        device_messenger.send("ram_used", ram_data["ram_used"])
        device_messenger.send("swap_used", ram_data["swap_used"])


class DevRoot(Metric):
    def create(self, device_messenger):
        device_messenger.create("dev_root_used_space", "value", "MiB")
        device_messenger.create("dev_root_total_space", "value", "MiB")
        device_messenger.create("dev_root_linked_on", "text")
        df_dev_root = get_df("/dev/root")
        device_messenger.send("dev_root_linked_on", get_dev_root_link())
        device_messenger.send("dev_root_total_space", df_dev_root[1])

    def send(self, device_messenger):
        device_messenger.send("dev_root_used_space", get_df("/dev/root")[0])


class Data(Metric):
    def create(self, device_messenger):
        device_messenger.create("data_used_space", "value", "MiB")
        device_messenger.create("data_total_space", "value", "MiB")
        device_messenger.send("data_total_space", get_df("/dev/mmcblk0p6")[1])

    def send(self, device_messenger):
        device_messenger.send("data_used_space", get_df("/dev/mmcblk0p6")[0])

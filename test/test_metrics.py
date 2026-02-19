import logging
import sys
import types

# Ensure runtime dependencies exist so the modules under test can be imported in this environment.
if "wb_common" not in sys.modules:
    wb_common = types.ModuleType("wb_common")
    mqtt_client = types.ModuleType("wb_common.mqtt_client")

    class StubMQTTClient:
        pass

    mqtt_client.MQTTClient = StubMQTTClient
    wb_common.mqtt_client = mqtt_client
    sys.modules["wb_common"] = wb_common
    sys.modules["wb_common.mqtt_client"] = mqtt_client

if "yaml" not in sys.modules:
    yaml_mod = types.ModuleType("yaml")
    loader_mod = types.ModuleType("yaml.loader")
    loader_mod.SafeLoader = object
    yaml_mod.load = lambda stream, Loader=None: {}
    yaml_mod.loader = loader_mod
    sys.modules["yaml"] = yaml_mod
    sys.modules["yaml.loader"] = loader_mod

if "systemd" not in sys.modules:
    systemd = types.ModuleType("systemd")
    journal = types.ModuleType("systemd.journal")

    class DummyJournalHandler(logging.Handler):
        def emit(self, record):
            return None

    journal.JournalHandler = DummyJournalHandler
    systemd.journal = journal
    sys.modules["systemd"] = systemd
    sys.modules["systemd.journal"] = journal

from wb.mqtt_metrics.metrics import Data, DevRoot, FreeRam, LoadAverage
from wb.mqtt_metrics.metrics_sender import MetricClient


def test_load_average_create_and_send(mocker):
    load_values = [0.1, 0.2, 0.3]
    mocker.patch("wb.mqtt_metrics.metrics.get_load_averages", return_value=load_values)
    messenger = mocker.MagicMock()
    metric = LoadAverage(messenger)

    metric.create()
    expected_create = [mocker.call(name, meta) for name, meta in LoadAverage.CONTROL_DEFINITIONS.items()]
    assert messenger.create_control.call_args_list == expected_create

    metric.send()
    expected_send = [
        mocker.call(name, value) for name, value in zip(LoadAverage.CONTROL_DEFINITIONS, load_values)
    ]
    assert messenger.send_value.call_args_list == expected_send


def test_free_ram_create_and_send(mocker):
    ram_data = {
        "ram_total": 100,
        "ram_used": 50,
        "ram_available": 40,
        "swap_total": 20,
        "swap_used": 10,
    }
    mocker.patch("wb.mqtt_metrics.metrics.get_ram_data", return_value=ram_data)
    messenger = mocker.MagicMock()
    metric = FreeRam(messenger)

    metric.create()
    assert messenger.create_control.call_count == len(FreeRam.CONTROL_DEFINITIONS)
    assert messenger.send_value.call_args_list == [
        mocker.call("ram_total", ram_data["ram_total"]),
        mocker.call("swap_total", ram_data["swap_total"]),
    ]

    messenger.send_value.reset_mock()
    metric.send()
    assert messenger.send_value.call_args_list == [
        mocker.call("ram_available", ram_data["ram_available"]),
        mocker.call("ram_used", ram_data["ram_used"]),
        mocker.call("swap_used", ram_data["swap_used"]),
    ]


def test_dev_root_create_and_send(mocker):
    df_map = {"/": ["11", "22"]}
    mocker.patch("wb.mqtt_metrics.metrics.get_df", side_effect=lambda path: df_map[path])
    mocker.patch("wb.mqtt_metrics.metrics.get_dev_root_link", return_value="/dev/root")
    messenger = mocker.MagicMock()
    metric = DevRoot(messenger)

    metric.create()
    assert messenger.create_control.call_count == len(DevRoot.CONTROL_DEFINITIONS)
    assert messenger.send_value.call_args_list == [
        mocker.call("dev_root_linked_on", "/dev/root"),
        mocker.call("dev_root_total_space", df_map["/"][1]),
    ]

    messenger.send_value.reset_mock()
    metric.send()
    assert messenger.send_value.call_args_list == [
        mocker.call("dev_root_used_space", df_map["/"][0]),
    ]


def test_data_metric_create_and_send(mocker):
    df_values = {"/mnt/data": ["5", "9"]}
    mocker.patch("wb.mqtt_metrics.metrics.get_df", side_effect=lambda path: df_values[path])
    messenger = mocker.MagicMock()
    metric = Data(messenger)

    metric.create()
    assert messenger.send_value.call_args_list == [
        mocker.call("data_total_space", df_values["/mnt/data"][1]),
    ]

    messenger.send_value.reset_mock()
    metric.send()
    assert messenger.send_value.call_args_list == [
        mocker.call("data_used_space", df_values["/mnt/data"][0]),
    ]


def test_metric_client_run_and_stop(monkeypatch):
    class DummyMetric:
        def __init__(self, messenger):
            self.messenger = messenger
            self.create_called = False
            self.send_count = 0

        def create(self):
            self.create_called = True

        def send(self):
            self.send_count += 1

    class StubMessenger:
        def __init__(self, client, device_name):
            self.device_name = device_name
            self.create_device_called = False
            self.remove_device_called = False

        def create_device(self):
            self.create_device_called = True

        def remove_device(self):
            self.remove_device_called = True

        def create_control(self, *_):
            return None

        def send_value(self, *_):
            return None

    class StubMQTTClient:
        def __init__(self, *_):
            self.start_called = False
            self.stop_called = False
            self.on_connect = None
            self.on_disconnect = None

        def start(self):
            self.start_called = True
            if self.on_connect:
                self.on_connect(None, None, None, 0)

        def stop(self):
            self.stop_called = True
            if self.on_disconnect:
                self.on_disconnect(None, None, 0)

    monkeypatch.setattr("wb.mqtt_metrics.metrics_sender.MQTTClient", StubMQTTClient)
    monkeypatch.setattr("wb.mqtt_metrics.metrics_sender.MqttMessenger", StubMessenger)
    monkeypatch.setattr(
        "wb.mqtt_metrics.metrics_sender.METRICS",
        {"Dummy": DummyMetric},
    )

    client = MetricClient("broker", "device", ["Dummy"])
    sleep_marker = {"client": client}

    def fake_sleep(_period):
        sleep_marker["client"]._stopped = True

    monkeypatch.setattr("wb.mqtt_metrics.metrics_sender.time.sleep", fake_sleep)

    client.run(period=0)
    client.stop()

    assert client._metrics[0].create_called
    assert client._metrics[0].send_count >= 2
    assert client._mqtt_client.start_called
    assert client._mqtt_client.stop_called
    assert client._messenger.remove_device_called

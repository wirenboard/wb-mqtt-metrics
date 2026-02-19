import json
import logging

from wb.mqtt_metrics.metrics import Data, DevRoot, FreeRam, LoadAverage
from wb.mqtt_metrics.metrics_sender import MetricClient

TEST_DEVICE_NAME = "device"
TEST_BROKER_URL = "test"
TEST_METRICS_LIST = ["LoadAverage", "FreeRam", "DevRoot", "Data"]

logger = logging.getLogger()


def _control_meta_value(ctrl_meta):
    ctrl_type = ctrl_meta["type"]
    payload = {"type": ctrl_type, "readonly": True}

    title = ctrl_meta.get("title")
    if title:
        payload["title"] = title

    units = ctrl_meta.get("units")
    if ctrl_type == "value" and units:
        payload["units"] = units

    if ctrl_type in {"value", "range"}:
        ctrl_max = ctrl_meta.get("max")
        if ctrl_max is not None:
            payload["max"] = ctrl_max
        payload["min"] = ctrl_meta.get("min", 0)

    return json.dumps(payload)

START_PUBLICATIONS = [
    (
        "/devices/device/meta",
        '{"driver": "wb-mqtt-metrics", "title": {"en": "Metrics", "ru": "\\u041c\\u0435\\u0442\\u0440\\u0438\\u043a\\u0438"}}',  # pylint: disable=line-too-long
    ),
    ("/devices/device/meta/driver", "wb-mqtt-metrics"),
    ("/devices/device/meta/name", "Metrics"),
    ("/devices/device/meta/error", None),
    ("/devices/device/controls/load_average_1min/meta/type", "value"),
    ("/devices/device/controls/load_average_1min/meta/readonly", "1"),
    ("/devices/device/controls/load_average_1min/meta/units", "tasks"),
    ("/devices/device/controls/load_average_1min/meta/min", 0),
    (
        "/devices/device/controls/load_average_1min/meta",
        _control_meta_value(LoadAverage.CONTROL_DEFINITIONS["load_average_1min"]),
    ),
    ("/devices/device/controls/load_average_5min/meta/type", "value"),
    ("/devices/device/controls/load_average_5min/meta/readonly", "1"),
    ("/devices/device/controls/load_average_5min/meta/units", "tasks"),
    ("/devices/device/controls/load_average_5min/meta/min", 0),
    (
        "/devices/device/controls/load_average_5min/meta",
        _control_meta_value(LoadAverage.CONTROL_DEFINITIONS["load_average_5min"]),
    ),
    ("/devices/device/controls/load_average_15min/meta/type", "value"),
    ("/devices/device/controls/load_average_15min/meta/readonly", "1"),
    ("/devices/device/controls/load_average_15min/meta/units", "tasks"),
    ("/devices/device/controls/load_average_15min/meta/min", 0),
    (
        "/devices/device/controls/load_average_15min/meta",
        _control_meta_value(LoadAverage.CONTROL_DEFINITIONS["load_average_15min"]),
    ),
    ("/devices/device/controls/load_average_1min", "t"),
    ("/devices/device/controls/load_average_5min", "e"),
    ("/devices/device/controls/load_average_15min", "s"),
    ("/devices/device/controls/ram_available/meta/type", "value"),
    ("/devices/device/controls/ram_available/meta/readonly", "1"),
    ("/devices/device/controls/ram_available/meta/units", "MiB"),
    ("/devices/device/controls/ram_available/meta/min", 0),
    (
        "/devices/device/controls/ram_available/meta",
        _control_meta_value(FreeRam.CONTROL_DEFINITIONS["ram_available"]),
    ),
    ("/devices/device/controls/ram_used/meta/type", "value"),
    ("/devices/device/controls/ram_used/meta/readonly", "1"),
    ("/devices/device/controls/ram_used/meta/units", "MiB"),
    ("/devices/device/controls/ram_used/meta/min", 0),
    (
        "/devices/device/controls/ram_used/meta",
        _control_meta_value(FreeRam.CONTROL_DEFINITIONS["ram_used"]),
    ),
    ("/devices/device/controls/ram_total/meta/type", "value"),
    ("/devices/device/controls/ram_total/meta/readonly", "1"),
    ("/devices/device/controls/ram_total/meta/units", "MiB"),
    ("/devices/device/controls/ram_total/meta/min", 0),
    (
        "/devices/device/controls/ram_total/meta",
        _control_meta_value(FreeRam.CONTROL_DEFINITIONS["ram_total"]),
    ),
    ("/devices/device/controls/swap_total/meta/type", "value"),
    ("/devices/device/controls/swap_total/meta/readonly", "1"),
    ("/devices/device/controls/swap_total/meta/units", "MiB"),
    ("/devices/device/controls/swap_total/meta/min", 0),
    (
        "/devices/device/controls/swap_total/meta",
        _control_meta_value(FreeRam.CONTROL_DEFINITIONS["swap_total"]),
    ),
    ("/devices/device/controls/swap_used/meta/type", "value"),
    ("/devices/device/controls/swap_used/meta/readonly", "1"),
    ("/devices/device/controls/swap_used/meta/units", "MiB"),
    ("/devices/device/controls/swap_used/meta/min", 0),
    (
        "/devices/device/controls/swap_used/meta",
        _control_meta_value(FreeRam.CONTROL_DEFINITIONS["swap_used"]),
    ),
    ("/devices/device/controls/ram_total", "test"),
    ("/devices/device/controls/swap_total", "test"),
    ("/devices/device/controls/ram_available", "test"),
    ("/devices/device/controls/ram_used", "test"),
    ("/devices/device/controls/swap_used", "test"),
    ("/devices/device/controls/dev_root_used_space/meta/type", "value"),
    ("/devices/device/controls/dev_root_used_space/meta/readonly", "1"),
    ("/devices/device/controls/dev_root_used_space/meta/units", "MiB"),
    ("/devices/device/controls/dev_root_used_space/meta/min", 0),
    (
        "/devices/device/controls/dev_root_used_space/meta",
        _control_meta_value(DevRoot.CONTROL_DEFINITIONS["dev_root_used_space"]),
    ),
    ("/devices/device/controls/dev_root_total_space/meta/type", "value"),
    ("/devices/device/controls/dev_root_total_space/meta/readonly", "1"),
    ("/devices/device/controls/dev_root_total_space/meta/units", "MiB"),
    ("/devices/device/controls/dev_root_total_space/meta/min", 0),
    (
        "/devices/device/controls/dev_root_total_space/meta",
        _control_meta_value(DevRoot.CONTROL_DEFINITIONS["dev_root_total_space"]),
    ),
    ("/devices/device/controls/dev_root_linked_on/meta/type", "text"),
    ("/devices/device/controls/dev_root_linked_on/meta/readonly", "1"),
    (
        "/devices/device/controls/dev_root_linked_on/meta",
        _control_meta_value(DevRoot.CONTROL_DEFINITIONS["dev_root_linked_on"]),
    ),
    ("/devices/device/controls/dev_root_linked_on", "test"),
    ("/devices/device/controls/dev_root_total_space", "e"),
    ("/devices/device/controls/dev_root_used_space", "t"),
    ("/devices/device/controls/data_used_space/meta/type", "value"),
    ("/devices/device/controls/data_used_space/meta/readonly", "1"),
    ("/devices/device/controls/data_used_space/meta/units", "MiB"),
    ("/devices/device/controls/data_used_space/meta/min", 0),
    (
        "/devices/device/controls/data_used_space/meta",
        _control_meta_value(Data.CONTROL_DEFINITIONS["data_used_space"]),
    ),
    ("/devices/device/controls/data_total_space/meta/type", "value"),
    ("/devices/device/controls/data_total_space/meta/readonly", "1"),
    ("/devices/device/controls/data_total_space/meta/units", "MiB"),
    ("/devices/device/controls/data_total_space/meta/min", 0),
    (
        "/devices/device/controls/data_total_space/meta",
        _control_meta_value(Data.CONTROL_DEFINITIONS["data_total_space"]),
    ),
    ("/devices/device/controls/data_total_space", "e"),
    ("/devices/device/controls/data_used_space", "t"),
]


def test_mosquitto_restart(mocker):
    publications = []

    def publish(self, topic, value, retain, qos):  # pylint: disable=unused-argument
        publications.append((topic, value))

    mocker.patch("wb_common.mqtt_client.MQTTClient.publish", new=publish)
    mocker.patch("wb_common.mqtt_client.MQTTClient")
    client = MetricClient(TEST_BROKER_URL, TEST_DEVICE_NAME, TEST_METRICS_LIST)
    mocker.patch("wb.mqtt_metrics.metrics.get_dev_root_link", return_value="test")
    mocker.patch("wb.mqtt_metrics.metrics.get_df", return_value="test")
    mocker.patch("wb.mqtt_metrics.metrics.get_load_averages", return_value="test")
    mocker.patch(
        "wb.mqtt_metrics.metrics.get_ram_data",
        return_value={
            "ram_total": "test",
            "swap_total": "test",
            "ram_available": "test",
            "ram_used": "test",
            "swap_used": "test",
        },
    )
    client._mqtt_client._on_connect(None, None, None, 0)  # pylint: disable=protected-access
    assert publications == START_PUBLICATIONS

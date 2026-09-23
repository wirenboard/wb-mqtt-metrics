import logging

import pytest
import yaml

from wb.mqtt_metrics.metrics_sender import EXIT_NOTCONFIGURED, EXIT_NOTRUNNING, main

VALID_CONFIG = {
    "mqtt": {"broker": "unix:///tmp/mosquitto.sock", "period": 5, "device-name": "metrics"},
    "metrics": {"list": ["LoadAverage", "FreeRam"]},
}


def write_config(tmp_path, content):
    path = tmp_path / "wb-mqtt-metrics.conf"
    if content is not None:
        path.write_text(content if isinstance(content, str) else yaml.safe_dump(content), encoding="utf-8")
    return str(path)


@pytest.mark.parametrize(
    "content",
    [
        None,
        "mqtt: [broken",
        "",
        {"mqtt": {"broker": "unix:///tmp/mosquitto.sock"}},
        {**VALID_CONFIG, "metrics": {"list": ["LoadAverage", "NoSuchMetric"]}},
    ],
    ids=["missing-file", "broken-yaml", "empty-file", "missing-keys", "unknown-metric"],
)
def test_invalid_config_exits_not_configured(tmp_path, content):
    assert main(["wb-metrics", "-c", write_config(tmp_path, content)]) == EXIT_NOTCONFIGURED


@pytest.mark.parametrize("metrics_list", [[], None], ids=["empty-list", "no-list"])
def test_nothing_to_do_exits_not_running(tmp_path, metrics_list):
    config = {**VALID_CONFIG, "metrics": {"list": metrics_list}}

    assert main(["wb-metrics", "-c", write_config(tmp_path, config)]) == EXIT_NOTRUNNING


@pytest.mark.parametrize(
    "mqtt",
    [
        {"broker": "tcp://user:secret@localhost"},
        {"broker": "foo://x"},
        {"broker": 1883},
        {"period": "fast"},
        {"period": 0},
    ],
    ids=[
        "broker-without-port",
        "unknown-broker-scheme",
        "broker-not-a-string",
        "non-numeric-period",
        "zero-period",
    ],
)
def test_unusable_mqtt_settings_exit_not_configured_before_any_client(tmp_path, mocker, caplog, mqtt):
    metric_client = mocker.patch("wb.mqtt_metrics.metrics_sender.MetricClient")
    config = {**VALID_CONFIG, "mqtt": {**VALID_CONFIG["mqtt"], **mqtt}}

    with caplog.at_level(logging.ERROR, logger="wb.mqtt_metrics.metrics_sender"):
        assert main(["wb-metrics", "-c", write_config(tmp_path, config)]) == EXIT_NOTCONFIGURED

    metric_client.assert_not_called()
    assert "Cannot read config" in caplog.text
    assert "secret" not in caplog.text, "the broker URL, password included, leaked into the journal"


def test_exit_code_comes_from_run_and_client_is_stopped(tmp_path, mocker):
    client = mocker.patch("wb.mqtt_metrics.metrics_sender.MetricClient").return_value
    client.run.return_value = 2

    assert main(["wb-metrics", "-c", write_config(tmp_path, VALID_CONFIG)]) == 2

    client.run.assert_called_once_with(5)
    client.stop.assert_called_once()

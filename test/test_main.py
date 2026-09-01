import json
import logging
from pathlib import Path

import pytest

from wb.mqtt_metrics import metrics_sender

# Lifecycle tests intentionally exercise callback methods and state owned by the service.
# pylint: disable=protected-access


def write_config(tmp_path, contents):
    config = tmp_path / "metrics.conf"
    config.write_text(contents, encoding="utf-8")
    return str(config)


def valid_config(metrics=None):
    return {
        "mqtt": {
            "broker": "unix:///run/mosquitto.sock",
            "period": 5,
            "device-name": "metrics",
        },
        "metrics": {"list": ["LoadAverage"] if metrics is None else metrics},
    }


def test_missing_config_returns_6(tmp_path):
    assert metrics_sender.main(["wb-metrics", "-c", str(tmp_path / "missing")]) == 6


def test_malformed_config_returns_6(tmp_path):
    config = write_config(tmp_path, "mqtt: [")
    assert metrics_sender.main(["wb-metrics", "-c", config]) == 6


def test_unknown_metric_returns_6(tmp_path):
    config = write_config(tmp_path, json.dumps(valid_config(["Unknown"])))
    assert metrics_sender.main(["wb-metrics", "-c", config]) == 6


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("mqtt", "broker", ""),
        ("mqtt", "period", 0),
        ("mqtt", "period", float("nan")),
        ("mqtt", "device-name", "bad/device"),
        ("metrics", "list", "LoadAverage"),
        ("metrics", "list", ["LoadAverage", "LoadAverage"]),
    ],
)
def test_invalid_config_value_returns_6(tmp_path, section, key, value):
    data = valid_config()
    data[section][key] = value
    config = write_config(tmp_path, yaml_dump(data))

    assert metrics_sender.main(["wb-metrics", "-c", config]) == 6


def yaml_dump(data):
    # JSON covers every case but .nan, which is intentionally accepted by the
    # backwards-compatible YAML parser and must be rejected by validation.
    return json.dumps(data).replace("NaN", ".nan")


def test_empty_metrics_returns_7_without_connecting(tmp_path, mocker):
    config = write_config(tmp_path, json.dumps(valid_config([])))
    metric_client = mocker.patch.object(metrics_sender, "MetricClient")

    assert metrics_sender.main(["wb-metrics", "-c", config]) == 7
    metric_client.assert_not_called()


def test_stopped_client_removes_device(tmp_path, mocker):
    config = write_config(tmp_path, json.dumps(valid_config()))
    client = mocker.patch.object(metrics_sender, "MetricClient").return_value
    client.run.return_value = metrics_sender.EXIT_STOPPED

    assert metrics_sender.main(["wb-metrics", "-c", config]) == metrics_sender.EXIT_STOPPED
    client.stop.assert_called_once_with(remove_device=True)


def test_runtime_failure_returns_1_and_still_stops_client(tmp_path, mocker):
    config = write_config(tmp_path, json.dumps(valid_config()))
    client = mocker.patch.object(metrics_sender, "MetricClient").return_value
    client.run.side_effect = RuntimeError("metric failed")

    assert metrics_sender.main(["wb-metrics", "-c", config]) == metrics_sender.EXIT_FAILURE
    client.stop.assert_called_once_with(remove_device=False)


def test_default_config_is_json():
    config_path = next(
        parent / "wb-mqtt-metrics.conf"
        for parent in Path(__file__).resolve().parents
        if (parent / "wb-mqtt-metrics.conf").exists()
    )

    expected = valid_config(["LoadAverage", "FreeRam", "DevRoot", "Data"])
    expected["mqtt"]["broker"] = "unix:///var/run/mosquitto/mosquitto.sock"

    with config_path.open(encoding="utf-8") as config_file:
        assert json.load(config_file) == expected


def test_authentication_failure_returns_2(mocker):
    mocker.patch.object(metrics_sender.signal, "signal")
    client = metrics_sender.MetricClient("tcp://user:bad@localhost:1883", "metrics", [])
    mocker.patch.object(client._mqtt_client, "start")
    mocker.patch.object(client._mqtt_client, "stop")

    client._on_connect(None, None, None, 5)

    assert client.run(1) == metrics_sender.EXIT_INVALID_ARGUMENT


def test_other_connack_failure_returns_1(mocker):
    mocker.patch.object(metrics_sender.signal, "signal")
    client = metrics_sender.MetricClient("tcp://localhost:1883", "metrics", [])
    mocker.patch.object(client._mqtt_client, "start")

    client._on_connect(None, None, None, 3)

    assert client.run(1) == metrics_sender.EXIT_FAILURE


def test_publish_failure_after_connect_returns_1(mocker):
    client = metrics_sender.MetricClient("tcp://localhost:1883", "metrics", [])
    mocker.patch.object(client._messenger, "create_device", side_effect=RuntimeError("publish"))

    client._on_connect(None, None, None, 0)

    assert client._stop_event.is_set()
    assert client._exit_code == metrics_sender.EXIT_FAILURE


def test_cleanup_waits_for_all_retained_publications(mocker):
    client = metrics_sender.MetricClient("tcp://localhost:1883", "metrics", [])
    mqtt_stop = mocker.patch.object(client._mqtt_client, "stop")
    publications = [mocker.MagicMock(), mocker.MagicMock()]
    for publication in publications:
        publication.is_published.return_value = True
    mocker.patch.object(
        client._messenger,
        "remove_device",
        return_value=[("topic/1", publications[0]), ("topic/2", publications[1])],
    )
    client._connected.set()

    client.stop(remove_device=True)

    for publication in publications:
        publication.wait_for_publish.assert_called_once()
    mqtt_stop.assert_called_once_with()


def test_cleanup_without_broker_is_logged_and_client_still_stops(mocker, caplog):
    client = metrics_sender.MetricClient("tcp://localhost:1883", "metrics", [])
    mqtt_stop = mocker.patch.object(client._mqtt_client, "stop")
    remove_device = mocker.patch.object(client._messenger, "remove_device")
    caplog.set_level(logging.ERROR)

    client.stop(remove_device=True)

    assert "MQTT broker is unavailable" in caplog.text
    remove_device.assert_not_called()
    mqtt_stop.assert_called_once_with()


def test_unconfirmed_cleanup_is_logged(mocker, caplog):
    publication = mocker.MagicMock()
    publication.wait_for_publish.side_effect = RuntimeError("disconnected")
    caplog.set_level(logging.ERROR)

    metrics_sender.MetricClient._wait_for_cleanup([("topic", publication)])

    assert "Failed to clear 1 of 1 retained MQTT topics" in caplog.text

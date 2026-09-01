from wb.mqtt_metrics.device_messenger import MqttMessenger


def test_topics_cleanup(mocker):
    messenger = MqttMessenger(mocker.MagicMock(), "test_device")
    messenger.create_device()
    meta = {"type": "value", "units": "V", "min": 0, "max": 100}
    messenger.create_control("test_metric", meta)
    assert messenger.cleanup_topics == [
        "/devices/test_device/meta",
        "/devices/test_device/meta/driver",
        "/devices/test_device/meta/name",
        "/devices/test_device/meta/error",
        "/devices/test_device/controls/test_metric/meta/type",
        "/devices/test_device/controls/test_metric/meta/readonly",
        "/devices/test_device/controls/test_metric/meta/units",
        "/devices/test_device/controls/test_metric/meta/max",
        "/devices/test_device/controls/test_metric/meta/min",
        "/devices/test_device/controls/test_metric/meta",
        "/devices/test_device/controls/test_metric",
    ]
    messenger.client.publish = mocker.MagicMock()
    publications = messenger.remove_device()
    for topic in messenger.cleanup_topics:
        messenger.client.publish.assert_any_call(topic, None, retain=True, qos=1)
    assert messenger.client.publish.call_count == len(messenger.cleanup_topics)
    assert [topic for topic, _ in publications] == messenger.cleanup_topics


def test_topics_cleanup_after_reconnect(mocker):
    messenger = MqttMessenger(mocker.MagicMock(), "test_device")
    meta = {"type": "value", "units": "V", "min": 0, "max": 100}

    def connect():
        # MetricClient._on_connect re-runs creation on every successful connect,
        # not only on the first one
        messenger.create_device()
        messenger.create_control("test_metric", meta)

    connect()
    after_first_connect = list(messenger.cleanup_topics)

    for _ in range(2):
        connect()

    assert messenger.cleanup_topics == after_first_connect

    messenger.client.publish = mocker.MagicMock()
    messenger.remove_device()
    published = [call.args[0] for call in messenger.client.publish.call_args_list]
    assert published == messenger.cleanup_topics

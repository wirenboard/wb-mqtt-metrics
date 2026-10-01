import logging
import signal
import time

import pytest

from wb.mqtt_metrics.metrics_sender import (
    EXIT_INVALIDARGUMENT,
    EXIT_SUCCESS,
    MetricClient,
)

TEST_DEVICE_NAME = "device"
TEST_BROKER_URL = "test"

# large enough that a resumed time.sleep() is unmistakable in the timing
TEST_PERIOD = 10
MAX_SHUTDOWN_SECONDS = 3


class SignallingMetric:
    """
    Calls the recorded SIGTERM handler from inside the loop body, once, the way a real delivery would.
    """

    def __init__(self, handlers):
        self.handlers = handlers
        self.sends = 0

    def create(self):
        pass

    def send(self):
        self.sends += 1
        if self.sends == 1:
            # run() registers the handlers before the first send, so a KeyError here is a regression
            self.handlers[signal.SIGTERM](signal.SIGTERM, None)


@pytest.fixture(autouse=True, name="signal_handlers")
def record_signal_handlers(mocker):
    """
    Record the handlers run() registers as {signum: handler}, so none lands in the test process.
    """
    handlers = {}
    mocker.patch("wb.mqtt_metrics.metrics_sender.signal.signal", side_effect=handlers.__setitem__)
    return handlers


# pylint: disable=protected-access
@pytest.fixture(name="client")
def make_client(mocker):
    """
    A MetricClient whose MQTT client never touches the network and reports itself connected.
    """
    mocker.patch("wb_common.mqtt_client.MQTTClient.publish")
    client = MetricClient(TEST_BROKER_URL, TEST_DEVICE_NAME, [])
    for method in ("start", "stop"):
        mocker.patch.object(client._mqtt_client, method)
    mocker.patch.object(client._mqtt_client, "is_connected", return_value=True)
    return client


def test_run_returns_promptly_on_sigterm(client, signal_handlers):
    metric = SignallingMetric(signal_handlers)
    client._metrics = [metric]

    started = time.monotonic()
    assert client.run(TEST_PERIOD) == EXIT_SUCCESS
    elapsed = time.monotonic() - started

    assert elapsed < MAX_SHUTDOWN_SECONDS, (
        f"run() took {elapsed:.1f}s to return with period={TEST_PERIOD}; "
        "the wait is not being cut short by the signal"
    )
    assert metric.sends == 1, "the loop ran another cycle after the signal"


def test_rejected_login_stops_with_2(client, signal_handlers):
    client._mqtt_client.start.side_effect = lambda **_: client._on_connect(None, None, None, 5)
    metric = SignallingMetric(signal_handlers)
    client._metrics = [metric]

    assert client.run(TEST_PERIOD) == EXIT_INVALIDARGUMENT

    client._mqtt_client.start.assert_called_once_with(retry_first_connection=True)
    assert metric.sends == 0, "metrics were sent although the broker rejected the login"


def test_metrics_are_not_sent_while_disconnected(client, signal_handlers):
    client._mqtt_client.is_connected.return_value = False
    metric = SignallingMetric(signal_handlers)
    client._metrics = [metric]
    client._stop_event.set()  # one pass of the loop is enough

    client.run(TEST_PERIOD)

    assert metric.sends == 0


@pytest.mark.parametrize("connected", [True, False])
def test_stop_removes_topics_only_when_connected(client, mocker, caplog, connected):
    client._mqtt_client.is_connected.return_value = connected
    remove_device = mocker.patch.object(client._messenger, "remove_device")

    with caplog.at_level(logging.ERROR, logger="wb.mqtt_metrics.metrics_sender"):
        client.stop()

    assert remove_device.called is connected
    assert ("retained topics cannot be removed" in caplog.text) is not connected
    client._mqtt_client.stop.assert_called_once()

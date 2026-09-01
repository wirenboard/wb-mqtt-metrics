import os
import signal
import time

from wb.mqtt_metrics.metrics_sender import MetricClient

TEST_DEVICE_NAME = "device"
TEST_BROKER_URL = "test"

# large enough that a resumed time.sleep() is unmistakable in the timing
TEST_PERIOD = 10
MAX_SHUTDOWN_SECONDS = 3


class SignallingMetric:
    """Raises SIGTERM from inside the loop body, once."""

    def __init__(self):
        self.sends = 0

    def create(self):
        pass

    def send(self):
        self.sends += 1
        if self.sends == 1:
            # run() installs the handlers before the first send, so this cannot race
            os.kill(os.getpid(), signal.SIGTERM)


# pylint: disable=protected-access
def test_run_returns_promptly_on_sigterm(mocker):
    original_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    mocker.patch("wb_common.mqtt_client.MQTTClient.publish")
    client = MetricClient(TEST_BROKER_URL, TEST_DEVICE_NAME, [])

    metric = SignallingMetric()
    client._metrics = [metric]
    mocker.patch.object(
        client._mqtt_client,
        "start",
        side_effect=lambda: client._on_connect(None, None, None, 0),
    )

    try:
        started = time.monotonic()
        exit_code = client.run(TEST_PERIOD)
        elapsed = time.monotonic() - started
    finally:
        # never leave the test process with wb-mqtt-metrics' handlers installed
        for sig, handler in original_handlers.items():
            signal.signal(sig, handler)

    assert elapsed < MAX_SHUTDOWN_SECONDS, (
        f"run() took {elapsed:.1f}s to return with period={TEST_PERIOD}; "
        "the wait is not being cut short by the signal"
    )
    assert metric.sends == 1, "the loop ran another cycle after the signal"
    assert exit_code == 7

import os

import pytest

from wb.mqtt_metrics import metrics

# HugePages_Total has no "kB" suffix on purpose: the parser must not choke on it
MEMINFO_SAMPLE = """\
MemTotal:        1020400 kB
MemFree:          123456 kB
MemAvailable:     654321 kB
Buffers:           20000 kB
Cached:           500000 kB
SwapCached:            0 kB
SReclaimable:      40000 kB
SwapTotal:        262140 kB
SwapFree:         262140 kB
HugePages_Total:       0
Hugepagesize:       2048 kB
"""


def test_read_meminfo(tmp_path, mocker):
    meminfo_file = tmp_path / "meminfo"
    meminfo_file.write_text(MEMINFO_SAMPLE, encoding="utf-8")
    mocker.patch.object(metrics, "MEMINFO_PATH", str(meminfo_file))

    meminfo = metrics.read_meminfo()

    assert meminfo["MemTotal"] == 1020400
    assert meminfo["MemAvailable"] == 654321
    assert meminfo["HugePages_Total"] == 0


def test_get_ram_data(tmp_path, mocker):
    meminfo_file = tmp_path / "meminfo"
    meminfo_file.write_text(MEMINFO_SAMPLE, encoding="utf-8")
    mocker.patch.object(metrics, "MEMINFO_PATH", str(meminfo_file))

    ram_data = metrics.get_ram_data()

    assert ram_data == {
        "ram_total": 996,
        "ram_used": 358,
        "ram_available": 638,
        "swap_total": 255,
        "swap_used": 0,
    }


def test_ram_controls_reconcile(tmp_path, mocker):
    meminfo_file = tmp_path / "meminfo"
    meminfo_file.write_text(MEMINFO_SAMPLE, encoding="utf-8")
    mocker.patch.object(metrics, "MEMINFO_PATH", str(meminfo_file))

    ram_data = metrics.get_ram_data()

    # an operator reading the three RAM controls side by side must see them add up
    assert ram_data["ram_used"] + ram_data["ram_available"] == ram_data["ram_total"]


# As seen on a WB controller: the root line's source is "/dev/root", not the real
# device -- only the major:minor in field 2 identifies it.
MOUNTINFO_SAMPLE = """\
25 30 0:23 / /sys rw,nosuid,nodev,noexec,relatime shared:7 - sysfs sysfs rw
26 30 0:24 / /proc rw,nosuid,nodev,noexec,relatime shared:14 - proc proc rw
30 1 179:2 / / rw,noatime,discard,errors=remount-ro shared:1 - ext4 /dev/root rw,stripe=1024
31 30 0:19 / /run rw,nosuid,nodev,noexec,relatime shared:5 - tmpfs tmpfs rw,size=51200k
36 30 179:6 / /mnt/data rw,relatime shared:29 - ext4 /dev/mmcblk0p6 rw
"""

ROOT_DEVNO = "179:2"
ROOT_DEV_SYSFS_TARGET = "../../devices/platform/soc/soc:aips-bus@2100000/mmc/mmcblk0/mmcblk0p2"


def _patch_root_lookup(tmp_path, mocker, mountinfo, devno=ROOT_DEVNO):
    mountinfo_file = tmp_path / "mountinfo"
    mountinfo_file.write_text(mountinfo, encoding="utf-8")
    mocker.patch.object(metrics, "MOUNTINFO_PATH", str(mountinfo_file))

    sys_dev_block = tmp_path / "block"
    sys_dev_block.mkdir()
    if devno:
        # a dangling symlink is fine: only the target's basename is read
        (sys_dev_block / devno).symlink_to(ROOT_DEV_SYSFS_TARGET)
    mocker.patch.object(metrics, "SYS_DEV_BLOCK_PATH", str(sys_dev_block))


def test_get_dev_root_link_resolves_devno_through_sysfs(tmp_path, mocker):
    # the metric must report /dev/mmcblk0p2, never the "/dev/root" mountinfo names
    _patch_root_lookup(tmp_path, mocker, MOUNTINFO_SAMPLE)
    assert metrics.get_dev_root_link() == "/dev/mmcblk0p2"


def test_get_dev_root_link_ignores_shadowed_root(tmp_path, mocker):
    shadowed = "29 1 0:2 / / rw - rootfs rootfs rw\n" + MOUNTINFO_SAMPLE
    _patch_root_lookup(tmp_path, mocker, shadowed)
    assert metrics.get_dev_root_link() == "/dev/mmcblk0p2"


def test_get_dev_root_link_no_root_entry(tmp_path, mocker):
    _patch_root_lookup(tmp_path, mocker, "26 30 0:24 / /proc rw shared:14 - proc proc rw\n")
    assert metrics.get_dev_root_link() == "unknown"


def test_get_dev_root_link_does_not_match_nested_mountpoint(tmp_path, mocker):
    _patch_root_lookup(tmp_path, mocker, "36 30 179:6 / /mnt/data rw shared:29 - ext4 /dev/mmcblk0p6 rw\n")
    assert metrics.get_dev_root_link() == "unknown"


SDCARD_AUTOFS_LINE = "40 30 0:42 / /mnt/sdcard rw,relatime shared:31 - autofs systemd-1 rw,fd=50,pgrp=1\n"
SDCARD_VFAT_LINE = "91 40 179:25 / /mnt/sdcard rw,relatime shared:47 - vfat /dev/mmcblk1p1 rw,fmask=0022\n"
SDCARD_DEVNO = "179:25"


def _patch_mountinfo(tmp_path, mocker, mountinfo):
    mountinfo_file = tmp_path / "mountinfo"
    mountinfo_file.write_text(mountinfo, encoding="utf-8")
    mocker.patch.object(metrics, "MOUNTINFO_PATH", str(mountinfo_file))


def test_find_mount_reads_fstype_after_variable_optional_fields(tmp_path, mocker):
    # no optional field at all on the first line, two on the second
    _patch_mountinfo(
        tmp_path,
        mocker,
        "30 1 179:2 / / rw - ext4 /dev/root rw\n36 30 179:6 / /mnt/data rw shared:29 master:3 - ext4 x rw\n",
    )
    assert metrics.find_mount("/") == ("179:2", "ext4")
    assert metrics.find_mount("/mnt/data") == ("179:6", "ext4")
    assert metrics.find_mount("/mnt/sdcard") is None


def test_get_sdcard_devno_ignores_bare_automount_point(tmp_path, mocker):
    _patch_mountinfo(tmp_path, mocker, MOUNTINFO_SAMPLE + SDCARD_AUTOFS_LINE)
    assert metrics.get_sdcard_devno() is None


def test_get_sdcard_devno_finds_card_over_automount_point(tmp_path, mocker):
    _patch_mountinfo(tmp_path, mocker, MOUNTINFO_SAMPLE + SDCARD_AUTOFS_LINE + SDCARD_VFAT_LINE)
    assert metrics.get_sdcard_devno() == SDCARD_DEVNO


@pytest.mark.parametrize("f_flag, readonly", [(0, 0), (os.ST_RDONLY | os.ST_NOSUID, 1)], ids=["rw", "ro"])
def test_get_sdcard_data(tmp_path, mocker, f_flag, readonly):
    sys_dev_block = tmp_path / "block"
    sys_dev_block.mkdir()
    (sys_dev_block / SDCARD_DEVNO).symlink_to("../../devices/platform/soc/mmc/mmcblk1/mmcblk1p1")
    mocker.patch.object(metrics, "SYS_DEV_BLOCK_PATH", str(sys_dev_block))
    stat = mocker.Mock(f_frsize=4096, f_blocks=3 * 256 * 1024, f_bfree=2 * 256 * 1024 + 255, f_flag=f_flag)
    statvfs = mocker.patch("os.statvfs", return_value=stat)

    assert metrics.get_sdcard_data(SDCARD_DEVNO) == {
        "sdcard_used_space": 1023,  # rounded down, as get_df() does
        "sdcard_total_space": 3072,
        "sdcard_linked_on": "/dev/mmcblk1p1",
        "sdcard_readonly": readonly,
    }
    statvfs.assert_called_once_with("/mnt/sdcard")


SDCARD_DATA = {
    "sdcard_used_space": 1023,
    "sdcard_total_space": 30436,
    "sdcard_linked_on": "/dev/mmcblk1p1",
    "sdcard_readonly": 0,
}


class FakeSdCard:  # pylint: disable=too-few-public-methods
    """
    The state of the card slot and the mount, driven by the test, behind the helpers SdCard calls.
    """

    def __init__(self, mocker):
        self.inserted = False
        self.mounted = False
        mocker.patch.object(metrics, "is_sdcard_inserted", side_effect=lambda: self.inserted)
        mocker.patch.object(
            metrics, "get_sdcard_devno", side_effect=lambda: SDCARD_DEVNO if self.mounted else None
        )
        self.get_data = mocker.patch.object(metrics, "get_sdcard_data", return_value=SDCARD_DATA)


def _sdcard_metric(mocker):
    messenger = mocker.Mock()
    metric = metrics.SdCard(messenger)
    metric.create()
    messenger.reset_mock()
    return metric, messenger


def _created(messenger):
    return [call.args[0] for call in messenger.create_control.call_args_list]


def _removed(messenger):
    return [call.args[0] for call in messenger.remove_control.call_args_list]


SDCARD_CONTROLS = list(metrics.SdCard.CONTROL_DEFINITIONS)


@pytest.mark.parametrize("inserted", [False, True], ids=["no-card", "card-not-mounted"])
def test_sdcard_not_mounted_creates_nothing_and_is_not_touched(mocker, inserted):
    card = FakeSdCard(mocker)
    card.inserted = inserted
    metric, messenger = _sdcard_metric(mocker)

    for _ in range(2):
        metric.send()

    assert not messenger.method_calls
    # statvfs() on the automount point would mount the card
    card.get_data.assert_not_called()


def test_sdcard_mounted_is_reported(mocker):
    card = FakeSdCard(mocker)
    card.inserted = card.mounted = True
    metric, messenger = _sdcard_metric(mocker)

    metric.send()

    assert _created(messenger) == SDCARD_CONTROLS
    assert [call.args for call in messenger.send_value.call_args_list] == list(SDCARD_DATA.items())

    messenger.reset_mock()
    metric.send()
    messenger.create_control.assert_not_called()
    assert messenger.send_value.call_count == len(SDCARD_DATA)


@pytest.mark.parametrize(
    "inserted, mounted",
    [(True, False), (False, True), (False, False)],
    ids=["unmounted", "pulled-out", "gone"],
)
def test_sdcard_controls_removed_when_card_goes_and_back_when_it_returns(mocker, inserted, mounted):
    card = FakeSdCard(mocker)
    card.inserted = card.mounted = True
    metric, messenger = _sdcard_metric(mocker)
    metric.send()

    # "pulled-out": still listed in mountinfo after the device is gone
    card.inserted, card.mounted = inserted, mounted
    messenger.reset_mock()
    metric.send()
    assert _removed(messenger) == SDCARD_CONTROLS
    messenger.send_value.assert_not_called()

    messenger.reset_mock()
    metric.send()
    messenger.remove_control.assert_not_called()  # removed once, not every period

    card.inserted = card.mounted = True
    messenger.reset_mock()
    metric.send()
    assert _created(messenger) == SDCARD_CONTROLS
    assert messenger.send_value.call_count == len(SDCARD_DATA)


def test_sdcard_read_failure_removes_controls(mocker):
    card = FakeSdCard(mocker)
    card.inserted = card.mounted = True
    metric, messenger = _sdcard_metric(mocker)
    metric.send()

    card.get_data.side_effect = OSError(5, "Input/output error")
    messenger.reset_mock()
    metric.send()

    assert _removed(messenger) == SDCARD_CONTROLS
    messenger.send_value.assert_not_called()


def test_sdcard_reconnect_republishes_meta_only_while_mounted(mocker):
    card = FakeSdCard(mocker)
    metric, messenger = _sdcard_metric(mocker)
    metric.send()

    metric.create()
    assert not messenger.method_calls

    card.inserted = card.mounted = True
    metric.send()
    messenger.reset_mock()
    # the broker may have lost the retained meta
    metric.create()
    assert _created(messenger) == SDCARD_CONTROLS


def test_is_sdcard_inserted(tmp_path, mocker):
    device = tmp_path / "mmcblk1p1"
    mocker.patch.object(metrics, "SDCARD_DEVICE", str(device))
    assert not metrics.is_sdcard_inserted()
    device.touch()
    assert metrics.is_sdcard_inserted()


ROOT_DEV = 0xB302  # 179:2
DATA_PARTITION_DEV = 0xB306  # 179:6


def _patch_stat_dev(mocker, devs):
    """
    Make os.stat() return st_dev from devs by path, and raise FileNotFoundError for the other paths.
    """

    def stat(path):
        if path not in devs:
            raise FileNotFoundError(2, "No such file or directory", path)
        return mocker.Mock(st_dev=devs[path])

    mocker.patch("os.stat", side_effect=stat)


@pytest.mark.parametrize(
    "devs, separate",
    [
        ({"/": ROOT_DEV, "/mnt/data": DATA_PARTITION_DEV}, True),
        # a plain folder and a bind mount of a root filesystem folder look the same: the root's st_dev
        ({"/": ROOT_DEV, "/mnt/data": ROOT_DEV}, False),
        ({"/": ROOT_DEV}, False),
    ],
    ids=["partition", "folder", "missing"],
)
def test_is_separate_filesystem(mocker, devs, separate):
    _patch_stat_dev(mocker, devs)
    assert metrics.is_separate_filesystem("/mnt/data") is separate


DATA_DF = [4321, 9876]
DATA_CONTROLS = list(metrics.Data.CONTROL_DEFINITIONS)


class FakeDataLayout:  # pylint: disable=too-few-public-methods
    """
    Whether /mnt/data is a partition of its own, behind the helpers Data calls.
    """

    def __init__(self, mocker, separate):
        mocker.patch.object(metrics, "is_separate_filesystem", return_value=separate)
        self.get_df = mocker.patch.object(metrics, "get_df", return_value=DATA_DF)


def test_data_partition_is_reported(mocker):
    layout = FakeDataLayout(mocker, separate=True)
    messenger = mocker.Mock()
    metric = metrics.Data(messenger)

    metric.create()
    metric.send()

    assert _created(messenger) == DATA_CONTROLS
    assert [call.args for call in messenger.send_value.call_args_list] == [
        ("data_total_space", DATA_DF[1]),
        ("data_used_space", DATA_DF[0]),
    ]
    assert {call.args for call in layout.get_df.call_args_list} == {("/mnt/data",)}


def test_data_folder_on_root_creates_nothing(mocker):
    layout = FakeDataLayout(mocker, separate=False)
    messenger = mocker.Mock()
    metric = metrics.Data(messenger)

    for _ in range(2):
        metric.create()
        metric.send()

    assert not messenger.method_calls
    # it would be the root filesystem's numbers, not the data's
    layout.get_df.assert_not_called()

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

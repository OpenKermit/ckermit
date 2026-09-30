"""Tests for file modification dates.

Tests of dates after 2038 skip when time_t is 32 bits. The others
use dates that every time_t width can hold, up to the last second a
signed 32-bit time_t can represent, and run everywhere.
"""
import calendar
import os
import time

import pytest

from conftest import make_loopback_dirs
from test_largefile import _parse_sizeofs


def _skip_unless_64_bit_time_t(run_wermit):
    """Skip unless the binary under test has a 64-bit time_t.

    A 32-bit time_t, as on 32-bit FreeBSD, cannot hold dates after
    2038.
    """
    result = run_wermit("show features")
    if _parse_sizeofs(result.stdout)["time_t"] < 8:
        pytest.skip("time_t is 32 bits; dates after 2038 unsupported")


# The last second a signed 32-bit time_t can represent.
LAST_32_BIT_SECOND = 2**31 - 1


def _set_mtime(path, when):
    """Set path's mtime to the local time tuple when and return it."""
    stamp = time.mktime(when + (0, 0, -1))
    os.utime(path, (stamp, stamp))
    return int(stamp)


@pytest.mark.parametrize("when", [
    (1965, 6, 15, 12, 0, 0),
    (1999, 6, 15, 12, 0, 0),
    (2037, 12, 31, 23, 59, 59),
    (2150, 6, 15, 12, 0, 0),
])
def test_fdate_reports_file_date(tmp_path, run_wermit, when):
    r"""Verify \fdate() reports a file's date, including before 1970
    and after 2106."""
    if when[0] > 2037:
        _skip_unless_64_bit_time_t(run_wermit)
    path = tmp_path / "f.txt"
    path.write_text("hello world")
    _set_mtime(path, when)
    expected = "%04d%02d%02d %02d:%02d:%02d" % when

    result = run_wermit(f"echo D=[\\fdate({path})]")
    assert f"D=[{expected}]" in result.stdout, result.stdout


def test_send_preserves_date_after_2106(tmp_path, run_wermit,
                                        wermit_loopback):
    """Verify SEND gives the received file a date after 2106."""
    _skip_unless_64_bit_time_t(run_wermit)
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    src = client_dir / "new.txt"
    src.write_text("hello world")
    stamp = _set_mtime(src, (2150, 6, 15, 12, 0, 0))

    result = wermit_loopback(server_dir, "", f"send {src}")

    received = server_dir / "new.txt"
    assert received.exists(), result.stdout
    assert int(received.stat().st_mtime) == stamp, (
        f"received mtime {time.ctime(received.stat().st_mtime)}, "
        f"expected {time.ctime(stamp)}"
    )


def test_cvtdate_gmt_after_2106(run_wermit, monkeypatch):
    r"""Verify \fcvtdate() converts a GMT date after 2106 to local time."""
    _skip_unless_64_bit_time_t(run_wermit)
    monkeypatch.setenv("TZ", "EST5")
    result = run_wermit(r"echo D=[\fcvtdate(21500615 12:00:00 GMT)]")
    assert "D=[21500615 07:00:00]" in result.stdout, result.stdout


def test_fdate_last_32_bit_second(tmp_path, run_wermit, monkeypatch):
    r"""Verify \fdate() reports the last second of a 32-bit time_t."""
    monkeypatch.setenv("TZ", "UTC")
    path = tmp_path / "f.txt"
    path.write_text("hello world")
    os.utime(path, (LAST_32_BIT_SECOND, LAST_32_BIT_SECOND))

    result = run_wermit(f"echo D=[\\fdate({path})]")
    assert "D=[20380119 03:14:07]" in result.stdout, result.stdout


@pytest.mark.parametrize("tz,stamp", [
    ("UTC", LAST_32_BIT_SECOND),
    ("EST5", LAST_32_BIT_SECOND),
    # June, so the receiver applies its daylight saving adjustment.
    ("EST5EDT", calendar.timegm((2037, 6, 15, 16, 0, 0))),
])
def test_send_preserves_date_before_2038(tmp_path, wermit_loopback,
                                         monkeypatch, tz, stamp):
    """Verify SEND gives the received file a date up to the last
    second of a 32-bit time_t."""
    monkeypatch.setenv("TZ", tz)
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    src = client_dir / "new.txt"
    src.write_text("hello world")
    os.utime(src, (stamp, stamp))

    result = wermit_loopback(server_dir, "", f"send {src}")

    received = server_dir / "new.txt"
    assert received.exists(), result.stdout
    assert int(received.stat().st_mtime) == stamp, (
        f"received mtime {int(received.stat().st_mtime)}, "
        f"expected {stamp}"
    )


def test_send_date_before_1970_keeps_receipt_time(tmp_path,
                                                   wermit_loopback,
                                                   monkeypatch):
    """Verify a received date before 1970 leaves the file with the
    time it was received.

    zstrdt() rejects dates before 1970. A munged date
    would land far from the time of the transfer.
    """
    monkeypatch.setenv("TZ", "UTC")
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    src = client_dir / "new.txt"
    src.write_text("hello world")
    stamp = calendar.timegm((1965, 6, 15, 12, 0, 0))
    os.utime(src, (stamp, stamp))

    start = int(time.time())
    result = wermit_loopback(server_dir, "", f"send {src}")
    end = int(time.time())

    received = server_dir / "new.txt"
    assert received.exists(), result.stdout
    mtime = int(received.stat().st_mtime)
    assert start - 1 <= mtime <= end + 1, (
        f"received mtime {mtime}, expected between {start} and {end}"
    )


@pytest.mark.parametrize("tz,gmt,local", [
    ("EST5", "20370615 12:00:00", "20370615 07:00:00"),
    ("UTC", "20380119 03:14:07", "20380119 03:14:07"),
    ("EST5", "20380119 03:14:07", "20380118 22:14:07"),
])
def test_cvtdate_gmt_before_2038(run_wermit, monkeypatch, tz, gmt,
                                 local):
    r"""Verify \fcvtdate() converts a GMT date up to the last second
    of a 32-bit time_t to local time."""
    monkeypatch.setenv("TZ", tz)
    result = run_wermit(f"echo D=[\\fcvtdate({gmt} GMT)]")
    assert f"D=[{local}]" in result.stdout, result.stdout


@pytest.mark.parametrize("switches,expected", [
    ("/after:20000101", {"c"}),
    ("/before:19700101", {"a"}),
    ("/after:19650101 /before:20000101", {"a", "b"}),
    ("/after:{20380119 03:14:06}", {"c"}),
    ("/before:{20380119 03:14:07}", {"a", "b"}),
])
def test_directory_date_switches(tmp_path, run_wermit, monkeypatch,
                                 switches, expected):
    """Verify DIRECTORY /AFTER: and /BEFORE: select by file date
    before 1970 and up to the last second of a 32-bit time_t."""
    monkeypatch.setenv("TZ", "UTC")
    stamps = {
        "a": calendar.timegm((1965, 6, 15, 12, 0, 0)),
        "b": calendar.timegm((1999, 6, 15, 12, 0, 0)),
        "c": LAST_32_BIT_SECOND,
    }
    for name, stamp in stamps.items():
        path = tmp_path / name
        path.write_text("x")
        os.utime(path, (stamp, stamp))

    # A comma directly after a date would be parsed as part of it.
    result = run_wermit(f"cd {tmp_path} , directory {switches} , exit")
    listed = {line.split()[-1] for line in result.stdout.splitlines()
              if line.startswith("-")}
    assert listed == expected, result.stdout

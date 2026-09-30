"""Tests for file modification dates outside 1970-2106."""
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


def _set_mtime(path, when):
    """Set path's mtime to the local time tuple when and return it."""
    stamp = time.mktime(when + (0, 0, -1))
    os.utime(path, (stamp, stamp))
    return int(stamp)


@pytest.mark.parametrize("when", [
    (1965, 6, 15, 12, 0, 0),
    (1999, 6, 15, 12, 0, 0),
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

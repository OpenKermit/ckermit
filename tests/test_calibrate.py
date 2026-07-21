"""Tests for SEND /CALIBRATE and GET /CALIBRATE.

These tests exist to catch a regression in either path, not to measure
performance.
"""

import logging
import pytest
from conftest import assert_ok, make_loopback_dirs, pattern_bytes

logger = logging.getLogger(__name__)


@pytest.mark.parametrize("kbytes", [1, 5])
def test_calibrate_send_generates_data(tmp_path, wermit_loopback, kbytes):
    """SEND /CALIBRATE:n sends n Kbytes of generated data in place of
    a real file. The server has no /CALIBRATE of its own, so it
    writes the incoming data normally, under the fixed name
    CALIBRATION; verify it arrives with exactly n*1024 bytes."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    result = wermit_loopback(
        server_dir, "",
        f"cd {client_dir}, set delay 0, send /calibrate:{kbytes}")
    assert_ok(result)

    dest_file = server_dir / "CALIBRATION"
    assert dest_file.exists()
    assert dest_file.stat().st_size == kbytes * 1024


def test_calibrate_send_default_size(tmp_path, wermit_loopback):
    """SEND /CALIBRATE: with no number after the colon defaults to
    1024 Kbytes. (The colon itself is mandatory; /CALIBRATE with no
    colon at all is a syntax error, since the switch is declared
    CM_ARG.)"""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    result = wermit_loopback(
        server_dir, "",
        f"cd {client_dir}, set delay 0, send /calibrate:", timeout=30)
    assert_ok(result)

    dest_file = server_dir / "CALIBRATION"
    assert dest_file.exists()
    assert dest_file.stat().st_size == 1024 * 1024


def test_calibrate_get_discards_data(tmp_path, wermit_loopback):
    """GET /CALIBRATE on the receiving side discards the incoming data
    instead of writing it to disk. The server sends a real file;
    verify the transfer completes but no local copy is created."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    file_name = "calib_source.dat"
    (server_dir / file_name).write_bytes(pattern_bytes(4096))

    result = wermit_loopback(
        server_dir, "",
        f"cd {client_dir}, set delay 0, get /calibrate {file_name}")
    assert_ok(result)

    assert not (client_dir / file_name).exists()

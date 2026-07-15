import os
import shutil

import pytest

from conftest import (pattern_bytes, DEBUG_LOOPBACK as DEBUG_ZMODEM,
                      ZMODEM_QUIET_PROTOCOL_CLAUSE)

ZMODEM_BLOCK_SIZE = 1024

MB = 1024 * 1024

pytestmark = pytest.mark.skipif(
    shutil.which("sz") is None or shutil.which("rz") is None,
    reason="lrzsz (sz/rz) commands not available",
)

# Extra seconds added to every timeout in TCP mode, on top of what PTY
# mode needs for the same transfer, to leave headroom for TCP
# connection setup/teardown beyond the pty case's process fork/exec.
TCP_TIMEOUT_MARGIN = 15


def run_zmodem_receive(zmodem_remote, tmp_path, content, timeout=45):
    """
    Runs kermit as a Zmodem receiver (kermit's stdin connected to a
    pty hosting sz), which reads content from a source file and
    writes it to dest_dir/test_z_receive.txt. Asserts the transfer
    succeeded, the received file is byte-identical, and its mtime was
    preserved to the second.
    """
    # Setup source directory and file
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    src_file = src_dir / "test_z_receive.txt"
    src_file.write_bytes(content)

    # Set modification time with sub-second precision
    target_mtime = 1700000000.5678
    os.utime(src_file, (target_mtime, target_mtime))

    # Setup dest directory where wermit will run and receive the file
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    # Receive command: wermit connects to a remote hosting sz -- either
    # directly via a pseudoterminal, or over raw TCP, depending on
    # zmodem_remote's mode.
    cmd_str = (f"{ZMODEM_QUIET_PROTOCOL_CLAUSE}, "
              "set terminal autodownload on, set host {HOST}, connect, "
              "close, exit")

    if zmodem_remote.mode == "tcp":
        timeout += TCP_TIMEOUT_MARGIN
    debug_log = tmp_path / "wermit_debug.log" if DEBUG_ZMODEM else None
    returncode, stdout = zmodem_remote(
        ["sz", str(src_file)], cmd_str, dest_dir, timeout=timeout,
        debug_log=debug_log)

    assert returncode == 0, f"Zmodem receive failed: returncode={returncode}, stdout={stdout}"

    received_file = dest_dir / "test_z_receive.txt"
    assert received_file.exists(
    ), f"Received file not found in {dest_dir}. stdout={stdout}"
    assert received_file.read_bytes() == content

    # Verify modification time is preserved to the second
    dest_mtime = received_file.stat().st_mtime
    assert abs(dest_mtime - target_mtime) <= 1.0


def run_zmodem_send(zmodem_remote, tmp_path, content, timeout=45):
    """
    Runs wermit as a Zmodem sender (wermit's stdin connected to a pty
    hosting rz), which sends a source file's content and rz writes it
    to dest_dir/test_z_send.txt. Asserts the transfer succeeded, the
    received file is byte-identical, and its mtime was preserved to
    the second.
    """
    # Setup source file to send
    src_file = tmp_path / "test_z_send.txt"
    src_file.write_bytes(content)

    # Set modification time with sub-second precision
    target_mtime = 1700000000.5678
    os.utime(src_file, (target_mtime, target_mtime))

    # Setup dest directory where rz will run and write the file
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    # Send command: wermit sets protocol to zmodem, hosts rz -- either
    # directly via a pseudoterminal, or over raw TCP, depending on
    # zmodem_remote's mode -- and sends the file.
    cmd_str = (f"{ZMODEM_QUIET_PROTOCOL_CLAUSE}, "
              f"set host {{HOST}}, send {src_file}, close, exit")

    if zmodem_remote.mode == "tcp":
        timeout += TCP_TIMEOUT_MARGIN
    debug_log = tmp_path / "wermit_debug.log" if DEBUG_ZMODEM else None
    returncode, stdout = zmodem_remote(
        ["rz"], cmd_str, dest_dir, timeout=timeout, debug_log=debug_log)

    assert returncode == 0, f"Zmodem send failed: returncode={returncode}, stdout={stdout}"

    received_file = dest_dir / "test_z_send.txt"
    assert received_file.exists(
    ), f"Sent file not found in {dest_dir}. stdout={stdout}"
    assert received_file.read_bytes() == content

    # Verify modification time is preserved to the second
    dest_mtime = received_file.stat().st_mtime
    assert abs(dest_mtime - target_mtime) <= 1.0


def test_zmodem_receive(zmodem_remote, tmp_path):
    content = b"Zmodem receive payload content test." * 50
    run_zmodem_receive(zmodem_remote, tmp_path, content)


def test_zmodem_send(zmodem_remote, tmp_path):
    content = b"Zmodem send payload content test." * 50
    run_zmodem_send(zmodem_remote, tmp_path, content)


ZMODEM_SIZES = [
    pytest.param(ZMODEM_BLOCK_SIZE - 1, id="blksize-1"),
    pytest.param(ZMODEM_BLOCK_SIZE, id="blksize"),
    pytest.param(ZMODEM_BLOCK_SIZE + 1, id="blksize+1"),
    pytest.param(2 * ZMODEM_BLOCK_SIZE - 1, id="2xblksize-1"),
    pytest.param(2 * ZMODEM_BLOCK_SIZE, id="2xblksize"),
    pytest.param(2 * ZMODEM_BLOCK_SIZE + 1, id="2xblksize+1"),
]


@pytest.mark.parametrize("size", ZMODEM_SIZES)
def test_zmodem_receive_sizes(zmodem_remote, tmp_path, size):
    """
    Zmodem receive at and around exact multiples of
    ZMODEM_BLOCK_SIZE, to exercise sub-packet count/boundary
    arithmetic.
    """
    run_zmodem_receive(zmodem_remote, tmp_path, pattern_bytes(size))


@pytest.mark.parametrize("size", ZMODEM_SIZES)
def test_zmodem_send_sizes(zmodem_remote, tmp_path, size):
    """
    Zmodem send at and around exact multiples of ZMODEM_BLOCK_SIZE,
    to exercise sub-packet count/boundary arithmetic.
    """
    run_zmodem_send(zmodem_remote, tmp_path, pattern_bytes(size))


def test_zmodem_receive_large(zmodem_remote, tmp_path):
    """Zmodem receive of a file well beyond a single sub-packet."""
    run_zmodem_receive(
        zmodem_remote, tmp_path, pattern_bytes(20 * MB), timeout=90)


def test_zmodem_send_large(zmodem_remote, tmp_path):
    """Zmodem send of a file well beyond a single sub-packet."""
    run_zmodem_send(
        zmodem_remote, tmp_path, pattern_bytes(20 * MB), timeout=90)

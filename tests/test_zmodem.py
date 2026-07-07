import os
import pty
import select
import shutil
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("sz") is None or shutil.which("rz") is None,
    reason="lrzsz (sz/rz) commands not available",
)

# Here we test the Zmodem transfers.

# run_wermit_pty is used to run kermit with its stdin, stdout, and stderr connected
# to a real pseudoterminal slave.
#
# This is because, by default, when kermit sets up a host connection over a
# pseudoterminal, it runs ckutio.c:ttptycmd().
# If kermit's own stdin is not a TTY (e.g., standard input is redirected from
# /dev/null or pipes), the original implementation of tcgetattr(0, &term) and
# ioctl(0, TIOCGWINSZ, &twin) would fail, printing "tcgetattr: Inappropriate ioctl
# for device" and aborting.
#
# Using pty.openpty() ensures that tests execute in a clean, simulated terminal
# environment matching normal shell usage.


def run_wermit_pty(wermit_path, cmd_str, cwd, timeout=45):
    master, slave = pty.openpty()

    cmd = [
        wermit_path, "-H", "-Y", "-C",
        f"set command more-prompting off, {cmd_str}"
    ]

    proc = subprocess.Popen(
        cmd,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        cwd=str(cwd),
        close_fds=True
    )

    os.close(slave)

    output = []
    start_time = time.time()

    # Read output using select for timeout handling
    while proc.poll() is None:
        if time.time() - start_time > timeout:
            proc.terminate()
            os.close(master)
            raise subprocess.TimeoutExpired(cmd, timeout)

        r, _, _ = select.select([master], [], [], 0.1)
        if master in r:
            try:
                data = os.read(master, 4096)
                if not data:
                    break
                output.append(data)
            except OSError:
                break

    # Read any remaining output after process exits
    while True:
        r, _, _ = select.select([master], [], [], 0.05)
        if master in r:
            try:
                data = os.read(master, 4096)
                if not data:
                    break
                output.append(data)
            except OSError:
                break
        else:
            break

    os.close(master)
    proc.wait()

    return proc.returncode, b"".join(output).decode('utf-8', errors='replace')


def test_zmodem_receive(wermit_path, tmp_path):
    # Setup source directory and file
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    src_file = src_dir / "test_z_receive.txt"
    content = b"Zmodem receive payload content test." * 50
    src_file.write_bytes(content)

    # Set modification time with sub-second precision
    target_mtime = 1700000000.5678
    os.utime(src_file, (target_mtime, target_mtime))

    # Setup dest directory where wermit will run and receive the file
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    # Receive command: wermit connects to pseudoterminal running sz
    cmd_str = f"set terminal autodownload on, set host /network-type:pseudoterminal sz {src_file}, connect, close, exit"

    returncode, stdout = run_wermit_pty(wermit_path, cmd_str, dest_dir)

    assert returncode == 0, f"Zmodem receive failed: returncode={returncode}, stdout={stdout}"

    received_file = dest_dir / "test_z_receive.txt"
    assert received_file.exists(
    ), f"Received file not found in {dest_dir}. stdout={stdout}"
    assert received_file.read_bytes() == content

    # Verify modification time is preserved to the second
    dest_mtime = received_file.stat().st_mtime
    assert abs(dest_mtime - target_mtime) <= 1.0


def test_zmodem_send(wermit_path, tmp_path):
    # Setup source file to send
    src_file = tmp_path / "test_z_send.txt"
    content = b"Zmodem send payload content test." * 50
    src_file.write_bytes(content)

    # Set modification time with sub-second precision
    target_mtime = 1700000000.5678
    os.utime(src_file, (target_mtime, target_mtime))

    # Setup dest directory where rz will run and write the file
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    # Send command: wermit sets protocol to zmodem, hosts rz over
    # pseudoterminal, and sends file
    cmd_str = f"set protocol zmodem, set host /network-type:pseudoterminal rz, send {src_file}, close, exit"

    returncode, stdout = run_wermit_pty(wermit_path, cmd_str, dest_dir)

    assert returncode == 0, f"Zmodem send failed: returncode={returncode}, stdout={stdout}"

    received_file = dest_dir / "test_z_send.txt"
    assert received_file.exists(
    ), f"Sent file not found in {dest_dir}. stdout={stdout}"
    assert received_file.read_bytes() == content

    # Verify modification time is preserved to the second
    dest_mtime = received_file.stat().st_mtime
    assert abs(dest_mtime - target_mtime) <= 1.0

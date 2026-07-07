import logging
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

logger = logging.getLogger(__name__)

# Use the same variable as tests/conftest.py's wermit_loopback.
# When set, wermit's internal "log debug" trace is captured to a file and
# dumped into the pytest failure report, and a timeout also dumps whatever
# pty output was captured before it fired plus a snapshot of any wermit,
# sz, or rz processes still running.
DEBUG_ZMODEM = bool(os.environ.get("KERMIT_TEST_DEBUG_LOOPBACK"))


def _log_debug_file(label, path):
    path = Path(path)
    if not path.exists():
        return
    try:
        logger.info(
            "%s: wermit debug log:\n%s",
            label, path.read_text(errors="replace"))
    except OSError as e:
        logger.warning(
            "%s: failed to read debug log %s: %s", label, path, e)


def _log_process_snapshot(label):
    """Logs any wermit/sz/rz processes still alive, so a timeout tells us
    whether the hang is in wermit itself or in the child it exec'd."""
    try:
        ps = subprocess.run(
            ["ps", "-ef"], capture_output=True, text=True, timeout=5)
        relevant = "\n".join(
            line for line in ps.stdout.splitlines()
            if line.startswith("UID")
            or any(name in line for name in ("wermit", " sz", " rz"))
        )
        logger.info("%s: relevant process snapshot:\n%s", label, relevant)
    except Exception as e:
        logger.warning(
            "%s: failed to capture process snapshot: %s", label, e)


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


def run_wermit_pty(wermit_path, cmd_str, cwd, timeout=45, debug_log=None):
    master, slave = pty.openpty()

    debug_prefix = f"log debug {debug_log}, " if debug_log else ""
    cmd = [
        wermit_path, "-H", "-Y", "-C",
        f"{debug_prefix}set command more-prompting off, {cmd_str}"
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
            captured = b"".join(output).decode('utf-8', errors='replace')
            logger.error(
                "run_wermit_pty: wermit (pid %d) timed out after %ds. "
                "pty output captured before timeout:\n%s",
                proc.pid, timeout, captured)
            _log_process_snapshot("run_wermit_pty")
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
            os.close(master)
            if debug_log:
                _log_debug_file("run_wermit_pty", debug_log)
            raise subprocess.TimeoutExpired(
                cmd, timeout, output=captured.encode())

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

    if debug_log:
        _log_debug_file("run_wermit_pty", debug_log)

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

    debug_log = tmp_path / "wermit_debug.log" if DEBUG_ZMODEM else None
    returncode, stdout = run_wermit_pty(
        wermit_path, cmd_str, dest_dir, debug_log=debug_log)

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

    debug_log = tmp_path / "wermit_debug.log" if DEBUG_ZMODEM else None
    returncode, stdout = run_wermit_pty(
        wermit_path, cmd_str, dest_dir, debug_log=debug_log)

    assert returncode == 0, f"Zmodem send failed: returncode={returncode}, stdout={stdout}"

    received_file = dest_dir / "test_z_send.txt"
    assert received_file.exists(
    ), f"Sent file not found in {dest_dir}. stdout={stdout}"
    assert received_file.read_bytes() == content

    # Verify modification time is preserved to the second
    dest_mtime = received_file.stat().st_mtime
    assert abs(dest_mtime - target_mtime) <= 1.0

"""Tests for DIAL with a scripted modem on a pseudoterminal."""
import os
import pty
import select
import subprocess
import time
import tty

import pytest

from conftest import scaled


def _skip_unless_lockdir_writable(wermit_path):
    """Skip unless this user can create wermit's UUCP lock file.

    SET LINE fails when wermit cannot create its lock file.  DIAL then
    has no line.
    """
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-C", r"echo [\v(lockdir)], exit"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=scaled(10))
    start = result.stdout.find("[")
    lockdir = result.stdout[start + 1:result.stdout.find("]", start)]
    if lockdir and not os.access(lockdir, os.W_OK):
        pytest.skip(f"lock directory {lockdir} is not writable")


def _dial(wermit_path, dial_command, number, expect):
    """DIAL number through a scripted Hayes modem.

    The modem answers OK to each command.  wermit is stopped once the
    modem has received expect, or after 20 seconds.  Return the bytes
    the modem received.
    """
    master, slave = pty.openpty()
    tty.setraw(master)
    name = os.ttyname(slave)
    got = b""
    buf = b""
    proc = subprocess.Popen(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         f"set line {name}, set carrier-watch off, set modem type hayes, "
         f"set modem dial-command {dial_command}, set dial retries 1, "
         f"set dial timeout 5, set hints off, "
         f"dial {number}, exit"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    try:
        end = time.time() + 20
        while (time.time() < end and proc.poll() is None
               and expect not in got):
            ready, _, _ = select.select([master], [], [], 0.2)
            if master not in ready:
                continue
            try:
                data = os.read(master, 1024)
            except OSError:
                break
            got += data
            buf += data
            while b"\r" in buf:
                line, buf = buf.split(b"\r", 1)
                if line.strip():
                    os.write(master, b"\r\nOK\r\n")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        os.close(master)
        os.close(slave)
    return got


@pytest.mark.slow
def test_dial_command_percent_percent(wermit_path):
    """Verify %% in SET MODEM DIAL-COMMAND sends one %.

    The first %s is the number.  Other bytes go as they are.
    """
    _skip_unless_lockdir_writable(wermit_path)
    got = _dial(wermit_path, "ATD%%%s", "5551234", b"ATD%5551234")
    assert b"ATD%5551234" in got, got


@pytest.mark.slow
def test_dial_command_plain(wermit_path):
    """Verify a DIAL-COMMAND without %% sends the number for %s."""
    _skip_unless_lockdir_writable(wermit_path)
    got = _dial(wermit_path, "ATDT%s", "5551234", b"ATDT5551234")
    assert b"ATDT5551234" in got, got

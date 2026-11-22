"""Tests for DIAL with a scripted modem on a pseudoterminal."""
import os
import select
import subprocess
import time
import tty

import pytest

from conftest import open_pty_line, scaled, skip_unless_line_lockable


def _dial(wermit_path, dial_command, number, expect):
    """DIAL number through a scripted Hayes modem.

    The modem answers OK to each command.  wermit is stopped once the
    modem has received expect, or after 20 seconds.  Return the bytes
    the modem received.
    """
    master, slave, name = open_pty_line()
    tty.setraw(master)
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
        running = proc.poll() is None
        if running:
            # SIGTERM lets wermit remove its lock file for the line.
            proc.terminate()
        # On exit, wermit hangs up the modem and waits for a reply.
        # Closing the master ends that wait at once.
        os.close(master)
        if running:
            try:
                proc.wait(timeout=scaled(5))
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        os.close(slave)
    return got


@pytest.mark.slow
def test_dial_command_percent_percent(wermit_path):
    """Verify %% in SET MODEM DIAL-COMMAND sends one %.

    The first %s is the number.  Other bytes go as they are.
    """
    skip_unless_line_lockable(wermit_path)
    got = _dial(wermit_path, "ATD%%%s", "5551234", b"ATD%5551234")
    assert b"ATD%5551234" in got, got


@pytest.mark.slow
def test_dial_command_plain(wermit_path):
    """Verify a DIAL-COMMAND without %% sends the number for %s."""
    skip_unless_line_lockable(wermit_path)
    got = _dial(wermit_path, "ATDT%s", "5551234", b"ATDT5551234")
    assert b"ATDT5551234" in got, got

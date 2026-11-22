"""Tests for DIAL with a scripted modem on a pseudoterminal."""
import os
import re
import select
import subprocess
import sys
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
        if proc.poll() is None:
            # SIGTERM lets wermit remove its lock file for the line.
            proc.terminate()
            _answer_hangup(master, proc, scaled(5))
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        # wermit holds the lock file for the line until it exits.  On
        # the BSDs, openpty() can return the line to another test once
        # the master is closed.
        os.close(master)
        os.close(slave)
    return got


def _answer_hangup(master, proc, timeout):
    """Answer OK to the hangup that wermit sends on exit.

    wermit sends "+++" and then a hangup command, and waits for a reply
    to each.  Return when proc exits or after timeout seconds.
    """
    buf = b""
    end = time.monotonic() + timeout
    while proc.poll() is None and time.monotonic() < end:
        ready, _, _ = select.select([master], [], [], 0.1)
        if master not in ready:
            continue
        try:
            buf += os.read(master, 1024)
        except OSError:
            break
        # Each "+++" and each nonblank line ending in CR gets an OK.
        parts = re.split(rb"(\+\+\+|\r)", buf)
        buf = parts[-1]
        for text, sep in zip(parts[0:-1:2], parts[1::2]):
            if sep == b"+++" or text.strip():
                os.write(master, b"\r\nOK\r\n")
    try:
        proc.wait(timeout=max(end - time.monotonic(), 0))
    except subprocess.TimeoutExpired:
        pass


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


@pytest.mark.slow
def test_dial_closes_master_after_exit(wermit_path, monkeypatch):
    """Verify _dial() closes the pty master only after wermit exits.

    wermit holds the lock file for the line until it exits.  On the
    BSDs, openpty() can return the same line to another test once the
    master is closed.  That test then finds the line locked.
    """
    skip_unless_line_lockable(wermit_path)
    seen = {}
    real_open = open_pty_line
    real_close = os.close

    def record_open():
        master, slave, name = real_open()
        seen["master"] = master
        return master, slave, name

    class RecordPopen(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            seen["proc"] = self

    def record_close(fd):
        if fd == seen.get("master"):
            seen["running"] = seen["proc"].poll() is None
        real_close(fd)

    monkeypatch.setattr(sys.modules[__name__], "open_pty_line",
                        record_open)
    monkeypatch.setattr(subprocess, "Popen", RecordPopen)
    monkeypatch.setattr(os, "close", record_close)
    got = _dial(wermit_path, "ATDT%s", "5551234", b"ATDT5551234")
    monkeypatch.undo()
    assert b"ATDT5551234" in got, got
    assert seen["running"] is False

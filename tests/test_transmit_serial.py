"""Tests for TRANSMIT on a pseudoterminal serial line (ckuus4.c)."""
import os
import select
import subprocess
import termios
import threading
import time

import pytest

from conftest import (expected_timeout, kermit_wait, open_pty_line,
                      scaled, skip_unless_line_lockable)


def _reply_after_transmit(master, reply, done):
    """Write reply to master once TRANSMIT's byte arrives.

    The reply goes out 0.5 seconds after the transmitted byte.  The
    wermit script pauses before INPUT, so the reply arrives between
    TRANSMIT and INPUT.
    """
    while not done.is_set():
        ready, _, _ = select.select([master], [], [], 0.1)
        if master not in ready:
            continue
        try:
            data = os.read(master, 4096)
        except OSError:
            return
        if b"x" in data:
            time.sleep(expected_timeout(0.5))
            os.write(master, reply)
            break
    while not done.is_set():
        ready, _, _ = select.select([master], [], [], 0.1)
        if master in ready:
            try:
                if not os.read(master, 4096):
                    return
            except OSError:
                return


@pytest.mark.parametrize("mode", ["binary", "text"])
def test_input_after_transmit_keeps_raw_line(wermit_path, tmp_path, mode):
    """Verify input after TRANSMIT arrives without line processing.

    The line starts with ICANON and ICRNL set.  The other end sends
    "ok" and CR after TRANSMIT and before INPUT.  INPUT must see the
    CR instead of an LF.
    """
    skip_unless_line_lockable(wermit_path)
    (tmp_path / "f.txt").write_text("x")
    master, slave, name = open_pty_line()
    attrs = termios.tcgetattr(slave)
    attrs[0] |= termios.ICRNL
    attrs[3] |= termios.ICANON
    termios.tcsetattr(slave, termios.TCSANOW, attrs)
    done = threading.Event()
    reader = threading.Thread(
        target=_reply_after_transmit, args=(master, b"ok\r", done),
        daemon=True)
    reader.start()
    pause = max(2, round(expected_timeout(2)))
    cmds = (f"set line {name}, set carrier-watch off, set speed 9600, "
            "set flow none, set transmit echo off, "
            f"transmit /{mode} /nowait f.txt, pause {pause}, "
            rf"input {kermit_wait()} ok\13, "
            r"echo STATUS=\v(status), exit")
    try:
        result = subprocess.run(
            [wermit_path, "-H", "-Y", "-Q", "-C", cmds],
            cwd=tmp_path, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=scaled(30))
    finally:
        done.set()
        reader.join(timeout=5)
        os.close(slave)
        os.close(master)
    assert "STATUS=0" in result.stdout, result.stdout + result.stderr

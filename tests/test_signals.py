"""
Tests for SIGHUP and SIGWINCH handling (ckutio.c).

sighup() and winchh() set flags.  chksigs() acts on them between
commands, between packets and in the CONNECT loop.  sighup() exits at
once while Kermit waits in a marked system call.
"""
import fcntl
import os
import pty
import select
import signal
import socket
import struct
import subprocess
import termios
import threading
import time

import pytest

from test_ssl import _tls_send_after

from conftest import scaled


def _start(wermit_path, cmds, stdin=subprocess.DEVNULL):
    """Start wermit running cmds and return the Popen object."""
    return subprocess.Popen(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         "set command more-prompting off, " + cmds],
        stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True)


def _hup_and_wait(proc, delay, limit=5):
    """Send SIGHUP after delay seconds and return the seconds to exit.

    Fails if the process does not exit within limit seconds.
    """
    time.sleep(delay)
    assert proc.poll() is None, proc.stdout.read()
    start = time.monotonic()
    proc.send_signal(signal.SIGHUP)
    try:
        proc.wait(timeout=scaled(limit))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        pytest.fail(f"no exit within {limit} s of SIGHUP")
    return time.monotonic() - start


def test_sighup_during_busy_script(wermit_path):
    """Verify SIGHUP ends a script that runs without reading input."""
    proc = _start(wermit_path,
                  "for \\%i 1 100000000 1 { .x := \\v(time) }")
    _hup_and_wait(proc, 0.5)
    assert proc.returncode == 1, proc.returncode


def test_sighup_during_pause(wermit_path):
    """Verify SIGHUP ends PAUSE at once."""
    proc = _start(wermit_path, "pause 60")
    _hup_and_wait(proc, 0.5)
    assert proc.returncode == 1, proc.returncode


def test_sighup_at_prompt(wermit_path):
    """Verify SIGHUP ends Kermit waiting for a command on stdin."""
    r, w = os.pipe()
    try:
        proc = subprocess.Popen(
            [wermit_path, "-H", "-Y", "-Q"], stdin=r,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True)
        _hup_and_wait(proc, 0.5)
    finally:
        os.close(r)
        os.close(w)
    assert proc.returncode == 1, proc.returncode


def test_sighup_during_tcp_input(wermit_path):
    """Verify SIGHUP ends INPUT waiting on an idle TCP connection."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    conns = []
    threading.Thread(target=lambda: conns.append(srv.accept()),
                     daemon=True).start()
    try:
        port = srv.getsockname()[1]
        proc = _start(wermit_path,
                      f"set host 127.0.0.1 {port} /raw-socket, "
                      "input 60 NEVER")
        _hup_and_wait(proc, 1)
    finally:
        srv.close()
    assert proc.returncode == 1, proc.returncode


@pytest.mark.parametrize("protocol", ["ssl-raw", "tls-raw"])
def test_sighup_during_tls_input(wermit_path, ssl_pki, protocol):
    """Verify SIGHUP ends INPUT waiting on an idle TLS connection.

    The TLS read blocks inside SSL_read().  SIGHUP interrupts it, and
    the next read acts on the signal.
    """
    port, thread, srv = _tls_send_after(ssl_pki, 30, b"LATE\r\n")
    try:
        proc = _start(wermit_path,
                      f"set authentication ssl verify-file "
                      f"{ssl_pki['ca_crt']}, "
                      f"set host localhost {port} /{protocol}, "
                      "input 60 NEVER")
        _hup_and_wait(proc, 2)
    finally:
        srv.close()
    assert proc.returncode == 1, proc.returncode


def _read_until(master, marker, timeout):
    """Read from master until marker appears, and return the text."""
    out = b""
    end = time.monotonic() + timeout
    while marker not in out and time.monotonic() < end:
        r, _, _ = select.select([master], [], [], 0.2)
        if r:
            try:
                data = os.read(master, 4096)
            except OSError:
                break
            if not data:
                break
            out += data
    return out.decode(errors="replace")


def _set_winsize(fd, rows, cols):
    """Set the window size of the terminal fd."""
    fcntl.ioctl(fd, termios.TIOCSWINSZ,
                struct.pack("HHHH", rows, cols, 0, 0))


def test_sigwinch_updates_size_after_command(wermit_path):
    """Verify a window-size change during PAUSE shows in \\v(rows)."""
    master, slave = pty.openpty()
    _set_winsize(slave, 24, 80)
    try:
        proc = subprocess.Popen(
            [wermit_path, "-H", "-Y", "-Q", "-C",
             "echo READY, pause 2, "
             "echo SIZE=[\\v(rows)x\\v(cols)], exit 0"],
            stdin=slave, stdout=slave, stderr=slave,
            start_new_session=True)
        os.close(slave)
        slave = -1
        assert "READY" in _read_until(master, b"READY", 10)
        _set_winsize(master, 40, 100)
        proc.send_signal(signal.SIGWINCH)
        out = _read_until(master, b"SIZE=[", 10)
        out += _read_until(master, b"]", 2)
        proc.wait(timeout=scaled(10))
    finally:
        if slave >= 0:
            os.close(slave)
        os.close(master)
    assert "SIZE=[40x100]" in out, out

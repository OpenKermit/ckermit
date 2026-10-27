"""Tests for external protocols run over a SET HOST /PTY connection.

ttptycmd() runs the protocol command in a pty and relays data
between it and the connection.  The result of SEND comes from the
protocol command's exit status.
"""
import os
import select
import signal
import subprocess
import time

import pytest

from conftest import start_wermit_pty


def _send_with(run_wermit, tmp_path, connection, protocol_cmd, after=""):
    """SEND f.txt over a /PTY connection with protocol_cmd.

    after holds Kermit commands to run after SEND, before exit.
    """
    (tmp_path / "f.txt").write_text("hello\n")
    clause = " ".join(f'"{protocol_cmd}"' for _ in range(4))
    return run_wermit(
        f"cd {tmp_path}, set exit warning off, "
        f'set protocol zmodem "" "" {clause}, '
        f"set host /pty {connection}, "
        "send f.txt, echo STATUS=\\v(status)"
        + (f", {after}" if after else ""), timeout=30)


@pytest.mark.parametrize("protocol_cmd,status", [
    ("sh -c 'exit 0'", 0),
    ("sh -c 'exit 1'", 1),
])
def test_external_protocol_exit_status(run_wermit, tmp_path,
                                       protocol_cmd, status):
    """Verify SEND reports the protocol command's exit status."""
    result = _send_with(run_wermit, tmp_path, "sh -c 'sleep 10'",
                        protocol_cmd)
    assert f"STATUS={status}" in result.stdout, result.stdout


def test_external_protocol_connection_lost(run_wermit, tmp_path):
    """Verify SEND fails when the connection ends during the transfer.

    The connection's child exits after one second.  The protocol
    command would exit 0 after 20 seconds but is cut off when the
    grace period after the connection ends runs out.  The status must
    come from the protocol child, not from another child.
    """
    result = _send_with(run_wermit, tmp_path, "sh -c 'sleep 1'",
                        "sleep 20")
    assert "STATUS=1" in result.stdout, result.stdout


def test_external_protocol_output_before_exit(run_wermit, tmp_path):
    """Verify the protocol command's last output reaches the connection.

    The command writes a line and exits at once.  The connection's
    child copies what it receives to got.txt.  Kermit waits up to 5
    seconds for the 12 bytes to arrive there before it exits.  Exit
    closes the connection, and the BSDs then discard what cat has not
    read.
    """
    got = tmp_path / "got.txt"
    wait = ("for \\%i 1 50 1 "
            "{ if not < \\fsize(got.txt) 12 break, msleep 100 }")
    result = _send_with(run_wermit, tmp_path,
                        f"sh -c 'cat > {got}'",
                        "echo LAST-OUTPUT", after=wait)
    assert "STATUS=0" in result.stdout, result.stdout
    assert "LAST-OUTPUT" in got.read_text(), result.stdout


def test_external_protocol_background_child(run_wermit, tmp_path):
    """Verify SEND ends when a background process holds the pty open.

    The protocol command exits at once and leaves a background sleep
    that holds the pty slave.  Its stderr goes to /dev/null so that
    run_wermit() does not wait for it.  The pty does not reach end of file, so
    SEND ends after the drain bound instead.
    """
    got = tmp_path / "got.txt"
    start = time.monotonic()
    result = _send_with(run_wermit, tmp_path,
                        f"sh -c 'cat > {got}'",
                        "sh -c 'sleep 20 2>/dev/null & echo BG-OUTPUT'")
    elapsed = time.monotonic() - start
    assert "STATUS=0" in result.stdout, result.stdout
    assert elapsed < 15, f"SEND took {elapsed:.1f} seconds"


def _ignore_sigchld():
    """Start a new session with SIGCHLD ignored, as some launchers do."""
    os.setsid()
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)


def test_external_protocol_exit_after_other_child(wermit_path, tmp_path):
    """Verify SEND sees the protocol exit after another child's exit.

    wermit starts with SIGCHLD ignored.  OPEN !READ starts a sleep that
    exits during the transfer, so its SIGCHLD comes first.  The
    protocol command exits later with status 0 and leaves a background
    sleep that holds the pty slave.  SEND must report the status and
    end within the drain bound, not when the background sleep exits.
    """
    (tmp_path / "f.txt").write_text("hello\n")
    proto = "sh -c 'sleep 20 2>/dev/null & sleep 4'"
    clause = " ".join(f'"{proto}"' for _ in range(4))
    got = tmp_path / "got.txt"
    cmd = (f"set command more-prompting off, cd {tmp_path}, "
           "set exit warning off, "
           f'set protocol zmodem "" "" {clause}, '
           f"set host /pty sh -c 'cat > {got}', "
           "open !read sleep 1.5, "
           "send f.txt, echo STATUS=\\v(status), exit")
    start = time.monotonic()
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-C", cmd],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=40,
        preexec_fn=_ignore_sigchld)
    elapsed = time.monotonic() - start
    assert "STATUS=0" in result.stdout, result.stdout
    assert elapsed < 15, f"SEND took {elapsed:.1f} seconds"


def _read_until(fd, marker, timeout):
    """Read from fd until marker appears or timeout runs out."""
    out = b""
    end = time.monotonic() + timeout
    while time.monotonic() < end and marker not in out:
        r, _, _ = select.select([fd], [], [], 0.1)
        if not r:
            continue
        try:
            data = os.read(fd, 4096)
        except OSError:
            break
        if not data:
            break
        out += data
    return out


def _sigchld_disposition(pid):
    """Return "caught", "ignored" or "default" for SIGCHLD in pid."""
    bit = 1 << (signal.SIGCHLD - 1)
    masks = {}
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            key, _, value = line.partition(":")
            if key in ("SigCgt", "SigIgn"):
                masks[key] = int(value.split()[0], 16)
    if masks["SigCgt"] & bit:
        return "caught"
    if masks["SigIgn"] & bit:
        return "ignored"
    return "default"


def _have_signal_masks():
    """Return whether /proc/PID/status lists SigCgt and SigIgn."""
    try:
        with open("/proc/self/status") as f:
            text = f.read()
    except OSError:
        return False
    return "SigCgt:" in text and "SigIgn:" in text


def test_external_protocol_interrupted(wermit_path, tmp_path):
    """Verify Ctrl-C during an external protocol cleans up.

    The protocol command records its PID and sleeps.  SIGINT ends the
    transfer.  The protocol program must be stopped and reaped, and
    SIGCHLD must be back at its default disposition, neither caught
    nor ignored.  The disposition check needs SigCgt and SigIgn in
    /proc/PID/status, so it runs on Linux only.
    """
    (tmp_path / "f.txt").write_text("hello\n")
    pidfile = tmp_path / "proto.pid"
    proto = "sh -c 'echo $$ > proto.pid; exec sleep 30'"
    clause = " ".join(f'"{proto}"' for _ in range(4))
    cmd = ("set exit warning off, "
           f'set protocol zmodem "" "" {clause}, '
           "set host /pty sh -c 'cat > /dev/null', "
           "send f.txt")
    proc, fd = start_wermit_pty(wermit_path, cmd, tmp_path)
    try:
        end = time.monotonic() + 10
        while not pidfile.exists() and time.monotonic() < end:
            _read_until(fd, b"\0", 0.1)
        proto_pid = int(pidfile.read_text())
        _read_until(fd, b"\0", 1.5)
        proc.send_signal(signal.SIGINT)
        out = _read_until(fd, b"C-Kermit>", 10)
        assert b"C-Kermit>" in out, out
        try:
            os.kill(proto_pid, 0)
            running = True
        except ProcessLookupError:
            running = False
        assert not running, "protocol program still running"
        if _have_signal_masks():
            assert _sigchld_disposition(proc.pid) == "default"
        os.write(fd, b"exit\r")
        end = time.monotonic() + 5
        while proc.poll() is None and time.monotonic() < end:
            _read_until(fd, b"\0", 0.2)
    finally:
        # Close the master before waiting.  An exiting process can
        # block while its terminal output drains.
        if proc.poll() is None:
            proc.kill()
        os.close(fd)
        proc.wait(timeout=10)

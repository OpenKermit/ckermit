"""Tests for stopping pseudoterminal far ends after a test."""
import os
import signal
import subprocess
import sys
import time

import conftest
from conftest import stop_far_end

# A session leader that ignores SIGHUP and keeps a child in its process
# group.  It writes "LEADER CHILD" pids to the file named by argv[1].
HUNG_FAR_END = """
import os, signal, subprocess, sys, time
signal.signal(signal.SIGHUP, signal.SIG_IGN)
child = subprocess.Popen(["sleep", "600"])
with open(sys.argv[1] + ".tmp", "w") as f:
    f.write(f"{os.getpid()} {child.pid}\\n")
os.rename(sys.argv[1] + ".tmp", sys.argv[1])
time.sleep(600)
"""


def _gone(pid, limit=10):
    """Return True if pid stops existing within limit seconds.

    A pid that another user's process reuses counts as gone.
    """
    end = time.monotonic() + limit
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return True
        time.sleep(0.05)
    return False


def test_stop_far_end_kills_hung_process_group(tmp_path, monkeypatch):
    """Verify stop_far_end() kills a far end that ignores SIGHUP.

    The far end leads a process group with a second process in it.
    stop_far_end() kills the whole group after the wait.
    """
    monkeypatch.setattr(conftest, "expected_timeout", lambda s: 0.2)
    pids = tmp_path / "pids"
    proc = subprocess.Popen([sys.executable, "-c", HUNG_FAR_END, str(pids)],
                            start_new_session=True)
    try:
        end = time.monotonic() + 10
        while not pids.exists() and time.monotonic() < end:
            time.sleep(0.05)
        leader, child = (int(x) for x in pids.read_text().split())
        pid_file = tmp_path / "far.pid"
        pid_file.write_text(f"{leader}\n")
        assert stop_far_end(pid_file)
        assert proc.wait(timeout=10) == -signal.SIGKILL
        assert _gone(child), f"child {child} still running"
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()


def test_stop_far_end_without_pid_file(tmp_path):
    """Verify stop_far_end() returns at once when the file is missing.

    When pid_file does not exist, stop_far_end() returns False without
    waiting.
    """
    start = time.monotonic()
    assert not stop_far_end(tmp_path / "missing.pid")
    assert time.monotonic() - start < 1


def test_stop_far_end_pid_of_other_user(tmp_path, monkeypatch):
    """Verify stop_far_end() returns False for another user's pid.

    os.kill(pid, 0) raises PermissionError when another user's process
    has the pid.  The far end has exited, so nothing is killed.
    """
    def kill(pid, sig):
        raise PermissionError(1, "Operation not permitted")

    pid_file = tmp_path / "far.pid"
    pid_file.write_text("12345\n")
    with monkeypatch.context() as m:
        m.setattr(conftest.os, "kill", kill)
        assert stop_far_end(pid_file) is False


def test_gone_pid_of_other_user(monkeypatch):
    """Verify _gone() counts another user's pid as gone."""
    def kill(pid, sig):
        raise PermissionError(1, "Operation not permitted")

    with monkeypatch.context() as m:
        m.setattr(os, "kill", kill)
        assert _gone(12345, 0.1)


def test_pid_wrapper_keeps_pid(tmp_path, pid_wrapper):
    """Verify pidwrap records the pid that the command then runs as."""
    pid_file = tmp_path / "w.pid"
    out = subprocess.run([str(pid_wrapper), str(pid_file), "sh", "-c",
                          "echo $$"], capture_output=True, text=True,
                         timeout=10)
    assert out.stdout.strip() == pid_file.read_text().strip()


def test_pseudoterminal_far_end_is_stopped(tmp_path, wermit_loopback):
    """Verify the pseudoterminal far end is gone when the client returns.

    wermit_loopback records the far end pid in server_server.pid.
    """
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    result = wermit_loopback(server_dir, client_commands="remote pwd")
    assert result.returncode == 0, result.stdout
    pid = int((tmp_path / "server_server.pid").read_text())
    assert _gone(pid, 0.1), f"far end {pid} still running"

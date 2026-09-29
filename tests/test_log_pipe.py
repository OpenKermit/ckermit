"""Tests for piped log command execution across child processes.

Verifies that piped log descriptors do not leak to child processes
or block EXIT when a child process outlives Kermit.
"""
import os
import signal
import time

import pytest

from conftest import assert_ok

CHILD_SECONDS = 8


@pytest.mark.parametrize("log_type", [
    "debug", "packets", "session", "transactions",
])
def test_piped_log_does_not_block_exit_on_pty_child(
        run_wermit, tmp_path, log_type):
    """Verify EXIT does not wait for a SET HOST PTY child that outlives it."""
    log_file = tmp_path / "log.out"
    pid_file = tmp_path / "child.pid"

    # The child ignores SIGHUP to outlive the connection.
    child = (f"/bin/sh -c 'echo $$ > {pid_file}; "
             f"trap \"\" HUP; exec sleep {CHILD_SECONDS}'")
    cmd = (f"log {log_type} {{|cat > {log_file}}}, "
           f"set host /network-type:pseudoterminal {child}, "
           "pause 1, exit")

    start = time.monotonic()
    try:
        result = run_wermit(cmd, timeout=CHILD_SECONDS + 10)
        elapsed = time.monotonic() - start
    finally:
        try:
            os.kill(int(pid_file.read_text()), signal.SIGKILL)
        except (OSError, ValueError):
            pass

    assert_ok(result)
    assert elapsed < CHILD_SECONDS - 3, (
        f"EXIT blocked for {elapsed:.1f}s\n"
        f"stdout: {result.stdout}")
    assert log_file.exists(), f"{log_type} log command never ran"


def test_switch_from_piped_debug_log_to_file(run_wermit, tmp_path):
    """Verify LOG DEBUG can replace a piped debug log with a file."""
    pipe_out = tmp_path / "pipe.out"
    file_log = tmp_path / "debug.log"
    cmd = (r"for \%i 1 50 1 { "
           f"log debug {{|cat > {pipe_out}}}, log debug {file_log} }}, "
           "echo SWITCH-DONE, exit")

    result = run_wermit(cmd, timeout=60)

    assert_ok(result)
    assert "SWITCH-DONE" in result.stdout, result.stdout
    assert file_log.stat().st_size > 0, "file debug log is empty"

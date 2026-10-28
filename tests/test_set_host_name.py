"""Tests for the length limit on a SET HOST name or command.

cx_net() keeps the host name or PTY command in ttname[].  The buffer
holds TTNAMLEN (512) bytes.  A longer name fails SET HOST.
"""
import pytest

TTNAMLEN = 512


@pytest.mark.parametrize("length,status", [(TTNAMLEN - 1, "0"),
                                           (TTNAMLEN, "1")])
def test_set_host_pty_command_length(run_wermit, length, status):
    """Verify a PTY command that does not fit in ttname[] fails."""
    command = "echo " + "x" * (length - len("echo "))
    assert len(command) == length
    result = run_wermit(
        f"set host /network-type:pseudoterminal {command}, "
        "echo STATUS=\\v(status), close, exit", timeout=30)
    assert f"STATUS={status}" in result.stdout, \
        result.stdout + result.stderr

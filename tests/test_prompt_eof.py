"""
Tests for prompts that read from standard input at end of file.

Each prompt must end, and the command must fail or proceed, when no
answer can be read.  stdin is /dev/null.
"""
import subprocess

import pytest

from test_ftp_crafted import _serve_ftp


def _run(wermit_path, cmds, timeout=20):
    """Run cmds with stdin at end of file and return CompletedProcess."""
    return subprocess.run(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         "set command more-prompting off, " + cmds + ", exit 0"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=timeout, start_new_session=True)


def test_getok_at_end_of_input(wermit_path):
    """Verify GETOK fails when no answer can be read."""
    result = _run(wermit_path, "getok {Proceed? }, echo S=\\v(status)")
    assert "S=1" in result.stdout, result.stdout


@pytest.mark.parametrize("replies", [
    {"PASS": b"530 no\r\n"},
    {"PASS": b"332 account please\r\n", "ACCT": b"530 no\r\n"},
], ids=["password", "account"])
def test_ftp_login_prompt_at_end_of_input(wermit_path, replies):
    """Verify the FTP login fails when the password or account prompt ends.

    The empty answer is sent to the server, and the server refuses it.
    """
    port, thread, srv = _serve_ftp(b"220 hi\r\n", replies)
    try:
        result = _run(wermit_path,
                      f"ftp open 127.0.0.1 {port} /user:u, "
                      "echo S=\\v(status), ftp close")
    finally:
        srv.close()
        thread.join(timeout=5)
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "login failed" in out.lower(), out
    assert "S=" in result.stdout, out

"""
Tests for the transfer summary after an external protocol (proto(),
ckcpro.w).
"""
import shutil

import pytest


def test_zmodem_send_does_not_report_no_files(run_wermit, tmp_path):
    """Verify a successful Zmodem SEND does not say no files were sent.

    External protocols do not count files, so the count cannot show
    whether files were transferred.
    """
    if not (shutil.which("sz") and shutil.which("rz")):
        pytest.skip("lrzsz not installed")
    (tmp_path / "f.txt").write_text("hello\n")
    recv = tmp_path / "r"
    recv.mkdir()
    result = run_wermit(
        f"cd {tmp_path}, "
        f"set host /pty sh -c 'cd {recv} && exec rz', "
        "send /protocol:zmodem f.txt, echo S=\\v(status), close",
        timeout=60)
    assert (recv / "f.txt").read_text() == "hello\n"
    assert "S=0" in result.stdout, result.stdout
    assert "No files were transferred" not in result.stdout, result.stdout

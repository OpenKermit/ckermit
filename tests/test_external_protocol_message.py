"""
Tests for the transfer summary after an external protocol (proto(),
ckcpro.w).
"""
import shutil

import pytest


@pytest.mark.zmodem
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
    # rz leaves IEXTEN set.  With IEXTEN, a BSD tty discards ^V input in
    # non-canonical mode.  NetBSD and OpenBSD also discard ^O.  sz does
    # not escape those bytes, so a CRC byte of 0x0f or 0x16 makes rz
    # answer ZNAK until the timeout.  The CRC covers the file mtime.
    # stty -iexten passes every byte.
    result = run_wermit(
        f"cd {tmp_path}, "
        f"set host /pty sh -c 'cd {recv} && stty -iexten && exec rz', "
        "send /protocol:zmodem f.txt, echo S=\\v(status), close",
        timeout=60)
    assert (recv / "f.txt").read_text() == "hello\n"
    assert "S=0" in result.stdout, result.stdout
    assert "No files were transferred" not in result.stdout, result.stdout

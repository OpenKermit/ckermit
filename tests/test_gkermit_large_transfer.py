"""Large binary transfer to G-Kermit in receive mode (gkermit -i -r).

I noticed that with the certain settings in use below, it provoked a hang.  This
has been addressed with the proper disabling of IXON in ckupty.c now.  This test
verifies the issue remains fixed.

Skips automatically if the gkermit binary is absent.
"""
import pytest

from conftest import pattern_bytes
from test_transfer import JUMBO_PACKET_LEN

# Settings profile under which this report's hang was reproduced
# manually, applied as a command prefix before SET HOST.
HANG_REPRO_SETTINGS = (
    "set reliable on, set clearchannel on, "
    f"set receive packet-length {JUMBO_PACKET_LEN}, "
    f"set send packet-length {JUMBO_PACKET_LEN}, "
    "set window 32, set control unprefix all, "
    "set transfer slow-start off, set streaming on, "
    "set file type binary, set transfer mode manual, "
)

MB = 1024 * 1024

# The issue triggered after just a few packets, so it's not necessary to do
# 20MB here.
LARGE_FILE_SIZE = 1 * MB


@pytest.mark.parametrize("trial", range(5))
def test_send_large_file_to_gkermit_receive(tmp_path, foreign_kermit_pty,
                                             gkermit_path, trial):
    """SEND a large binary file from wermit to 'gkermit -i -r'.

    Repeated (trial) rather than run once, since the hang this
    reproduces is timing-sensitive and does not fire on every attempt.
    A hang shows up as a subprocess.TimeoutExpired from
    foreign_kermit_pty's underlying run_wermit_pty, which logs the pty
    output captured before the timeout plus a process snapshot to help
    tell whether wermit or gkermit is the one still stuck.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    src = src_dir / "large_binary.dat"
    content = pattern_bytes(LARGE_FILE_SIZE)
    src.write_bytes(content)

    cmd_str = (
        "set command more-prompting off, "
        f"{HANG_REPRO_SETTINGS}set delay 0, set host {{HOST}}, "
        f"send {{{src}}}, close, exit"
    )
    returncode, stdout = foreign_kermit_pty(
        [gkermit_path, "-i", "-r"], cmd_str, dest_dir, timeout=90)
    assert returncode == 0, stdout

    dest = dest_dir / "large_binary.dat"
    assert dest.exists(), stdout
    assert dest.read_bytes() == content

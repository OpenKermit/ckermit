"""Compatibility tests against E-Kermit software (./eksw).

E-Kermit is a minimal send/receive implementation driven over a
pseudoterminal via foreign_kermit_pty. Tests skip automatically if the
eksw binary is absent.

Behavioral properties of E-Kermit 0.94:
- Inbound filenames are uppercased and extra dots replaced with
  underscores. Outbound filenames are sent unchanged.
- Overwrites existing destination files unconditionally.
- Supports block check types 1, 3, and 5. Block check type 2 is known
  to stall.
- Supports window sizes 1 through 3.
- readpkt() in eksw's unixio.c treats a raw 0x0A (LF) byte as an alternate
  packet terminator in addition to the negotiated one.  The comments say
  it has something to do with HyperTerminal.

  This means it cannot correctly receive any packet whose data contains an
  unprefixed 0x0A, e.g. under SET CONTROL UNPREFIX ALL.
"""
import subprocess

import pytest

from conftest import pattern_bytes
from test_transfer import KERMIT_PACKET_LEN

RECEIVE_CONFIRM_OFF = "set receive confirm off, "


def _eksw_receive_name(name):
    """Return filename as transformed by eksw -r.

    Uppercase the string and replace non-final dots with underscores.
    """
    if "." not in name:
        return name.upper()
    base, ext = name.rsplit(".", 1)
    return f"{base.replace('.', '_').upper()}.{ext.upper()}"


def _eksw_transfer(tmp_path, foreign_kermit_pty, eksw_path, direction,
                   file_name, file_content, is_text=False,
                   eksw_flags=(), wermit_extra="", timeout=15):
    """Run transfer between wermit and eksw.

    Return the destination directory Path.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    src = src_dir / file_name

    if is_text:
        src.write_text(file_content)
    else:
        src.write_bytes(file_content)

    if direction == "send":
        peer_argv = [eksw_path, *eksw_flags, "-r"]
        cmd_str = (
            "set command more-prompting off, "
            f"{wermit_extra}set delay 0, set host {{HOST}}, "
            f"send {{{src}}}, close, exit"
        )
    else:
        eksw_cmd = " ".join(
            [eksw_path, *eksw_flags, "-s", file_name])
        peer_argv = ["sh", "-c", f"cd {src_dir} && exec {eksw_cmd}"]
        cmd_str = (
            "set command more-prompting off, "
            f"{RECEIVE_CONFIRM_OFF}{wermit_extra}set delay 0, "
            "set host {HOST}, receive, close, exit"
        )

    returncode, stdout = foreign_kermit_pty(
        peer_argv, cmd_str, dest_dir, timeout=timeout)
    assert returncode == 0, stdout

    dest_name = _eksw_receive_name(file_name) if direction == "send" \
        else file_name
    dest = dest_dir / dest_name
    assert dest.exists(), stdout
    if is_text:
        assert dest.read_text() == file_content
    else:
        assert dest.read_bytes() == file_content
    return dest_dir


@pytest.mark.parametrize("direction", ["send", "get"])
@pytest.mark.parametrize("size", [
    pytest.param(0, id="0B"),
    pytest.param(1024, id="1024B"),
    pytest.param(KERMIT_PACKET_LEN - 1, id="pktlen-1"),
    pytest.param(KERMIT_PACKET_LEN, id="pktlen"),
    pytest.param(KERMIT_PACKET_LEN + 1, id="pktlen+1"),
])
def test_transfer_binary(tmp_path, foreign_kermit_pty, eksw_path,
                         direction, size):
    """Binary transfer in both directions across packet boundaries."""
    _eksw_transfer(
        tmp_path, foreign_kermit_pty, eksw_path, direction,
        "binary_file.dat", pattern_bytes(size))


def test_transfer_text_crlf(tmp_path, foreign_kermit_pty, eksw_path):
    """Text transfer with -T flag for CRLF line ending conversion."""
    content = "Line 1: Hello.\nLine 2: Compat test.\nLine 3.\n"
    dest_dir = _eksw_transfer(
        tmp_path, foreign_kermit_pty, eksw_path, "send",
        "text_file.txt", content, is_text=True,
        eksw_flags=["-T"], wermit_extra="set file type text, ")
    assert (dest_dir / "TEXT_FILE.TXT").read_bytes() == content.encode()


def test_filenames_uppercased_and_dots_squashed(
        tmp_path, foreign_kermit_pty, eksw_path):
    """Verify inbound filename uppercasing and dot substitution."""
    dest_dir = _eksw_transfer(
        tmp_path, foreign_kermit_pty, eksw_path, "send",
        "Mixed.Case.tar.gz", b"filename conversion check")
    assert not (dest_dir / "Mixed.Case.tar.gz").exists()
    assert (dest_dir / "MIXED_CASE_TAR.GZ").read_bytes() == \
        b"filename conversion check"


def test_collision_always_overwrites(tmp_path, foreign_kermit_pty,
                                     eksw_path):
    """Verify file collision overwrites destination file in place."""
    dest_dir = tmp_path / "collision_dir"
    dest_dir.mkdir()
    src_dir = tmp_path / "collision_src"
    src_dir.mkdir()
    src = src_dir / "dup.txt"

    for content in (b"version 1", b"version 2, different length"):
        src.write_bytes(content)
        returncode, stdout = foreign_kermit_pty(
            [eksw_path, "-r"],
            "set command more-prompting off, set delay 0, "
            f"set host {{HOST}}, send {src}, close, exit",
            dest_dir, timeout=15)
        assert returncode == 0, stdout

    assert (dest_dir / "DUP.TXT").read_bytes() == \
        b"version 2, different length"
    assert not (dest_dir / "DUP.TXT.~1~").exists()


@pytest.mark.parametrize("block_check", [1, 3, 5])
def test_block_check_types(tmp_path, foreign_kermit_pty, eksw_path,
                           block_check):
    _eksw_transfer(
        tmp_path, foreign_kermit_pty, eksw_path, "send",
        f"bc{block_check}.dat", pattern_bytes(2000),
        eksw_flags=["-b", str(block_check)],
        wermit_extra=f"set block-check {block_check}, ")


@pytest.mark.xfail(
    strict=True, raises=subprocess.TimeoutExpired,
    reason="SET BLOCK-CHECK 2 against eksw -b 2 stalls during transfer.")
def test_block_check_type_2(tmp_path, foreign_kermit_pty, eksw_path):
    """Verify block-check type 2 timeout behavior."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    src = src_dir / "bc2.dat"
    content = pattern_bytes(2000)
    src.write_bytes(content)

    returncode, stdout = foreign_kermit_pty(
        [eksw_path, "-b", "2", "-r"],
        "set command more-prompting off, set block-check 2, "
        f"set delay 0, set host {{HOST}}, send {src}, "
        "close, exit",
        dest_dir, timeout=8)
    assert returncode == 0, stdout
    assert (dest_dir / _eksw_receive_name("bc2.dat")).read_bytes() \
        == content


@pytest.mark.parametrize("window_size", [2, 3])
def test_sliding_window(tmp_path, foreign_kermit_pty, eksw_path,
                        window_size):
    """Sliding window transfer using supported window sizes 2 and 3."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    src = src_dir / "win.dat"
    content = pattern_bytes(50 * KERMIT_PACKET_LEN)
    src.write_bytes(content)

    returncode, stdout = foreign_kermit_pty(
        [eksw_path, "-w", str(window_size), "-r"],
        f"set command more-prompting off, set window-size {window_size}, "
        f"set delay 0, set host {{HOST}}, send {src}, close, exit",
        dest_dir, timeout=20)
    assert returncode == 0, stdout
    assert (dest_dir / _eksw_receive_name("win.dat")).read_bytes() \
        == content


def test_error_injection_recovery(tmp_path, foreign_kermit_pty, eksw_path):
    """Transfer recovery with simulated packet error rate."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    src = src_dir / "err.dat"
    content = pattern_bytes(50 * KERMIT_PACKET_LEN)
    src.write_bytes(content)

    returncode, stdout = foreign_kermit_pty(
        [eksw_path, "-E", "1", "-r"],
        "set command more-prompting off, set delay 0, "
        f"set host {{HOST}}, send {src}, close, exit",
        dest_dir, timeout=30)
    assert returncode == 0, stdout
    assert (dest_dir / _eksw_receive_name("err.dat")).read_bytes() \
        == content


@pytest.mark.parametrize("mode_flag", ["-R", "-L"])
def test_remote_local_mode_flags_are_no_ops(
        tmp_path, foreign_kermit_pty, eksw_path, mode_flag):
    """Transfer with remote and local mode flags."""
    _eksw_transfer(
        tmp_path, foreign_kermit_pty, eksw_path, "send",
        "rl.txt", b"remote/local mode flag check",
        eksw_flags=[mode_flag])


@pytest.mark.xfail(
    reason="E-Kermit readpkt() (eksw unixio.c) treats any raw 0x0A byte as "
           "an alternate packet terminator, so it cannot receive "
           "unprefixed binary data containing one; not fixable from "
           "the C-Kermit side. See this module's docstring.",
    strict=True)
def test_unprefixed_lf_hangs(tmp_path, foreign_kermit_pty, eksw_path):
    """SEND with SET CONTROL UNPREFIX ALL, to data containing 0x0A.

    pattern_bytes() output contains every byte value 0-255, including 0x0A, once
    per 256-byte block. Under SET CONTROL UNPREFIX ALL, C-Kermit sends that byte
    raw. eksw's readpkt() then reads it as if it were the end of the packet,
    desyncing the exchange. Run under a short timeout since the known failure
    is a hang.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    src = src_dir / "lf.dat"
    content = pattern_bytes(4 * KERMIT_PACKET_LEN)
    src.write_bytes(content)

    returncode, stdout = foreign_kermit_pty(
        [eksw_path, "-B", "-r"],
        "set command more-prompting off, set control unprefix all, "
        f"set delay 0, set host {{HOST}}, send {{{src}}}, close, exit",
        dest_dir, timeout=5)
    assert returncode == 0, stdout
    assert (dest_dir / _eksw_receive_name("lf.dat")).read_bytes() \
        == content

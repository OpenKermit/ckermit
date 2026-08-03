"""Compatibility tests against G-Kermit (./gkermit).

G-Kermit is a minimal send/receive Kermit implementation driven over a
pseudoterminal via foreign_kermit_pty. Tests skip automatically if the
gkermit binary is absent.

Behavioral properties of G-Kermit 2.01 on Linux:
- Peer-initiated sends ('gkermit -s') require 'receive' on wermit.
- Preserves filename casing and dot structure without conversion.
"""
from pathlib import Path

import pytest

from conftest import pattern_bytes
from test_transfer import KERMIT_PACKET_LEN

RECEIVE_CONFIRM_OFF = "set receive confirm off, "


def _gkermit_transfer(tmp_path, foreign_kermit_pty, gkermit_path, direction,
                      file_name, file_content, is_text=False,
                      gkermit_flags=(), wermit_extra="", timeout=15):
    """Run transfer between wermit and gkermit.

    Return destination directory Path.
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
        peer_argv = [gkermit_path, *gkermit_flags, "-r"]
        cmd_str = (
            "set command more-prompting off, "
            f"{wermit_extra}set delay 0, set host {{HOST}}, "
            f"send {{{src}}}, close, exit"
        )
    else:
        peer_argv = [gkermit_path, *gkermit_flags, "-s", str(src)]
        cmd_str = (
            "set command more-prompting off, "
            f"{RECEIVE_CONFIRM_OFF}{wermit_extra}set delay 0, "
            "set host {HOST}, receive, close, exit"
        )

    returncode, stdout = foreign_kermit_pty(
        peer_argv, cmd_str, dest_dir, timeout=timeout)
    assert returncode == 0, stdout

    dest = dest_dir / file_name
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
def test_transfer_binary(tmp_path, foreign_kermit_pty, gkermit_path,
                         direction, size):
    _gkermit_transfer(
        tmp_path, foreign_kermit_pty, gkermit_path, direction,
        "binary_file.dat", pattern_bytes(size))


def test_transfer_text_crlf(tmp_path, foreign_kermit_pty, gkermit_path):
    """Text transfer with -T flag for CRLF line ending conversion."""
    content = "Line 1: Hello.\nLine 2: Compat test.\nLine 3.\n"
    dest_dir = _gkermit_transfer(
        tmp_path, foreign_kermit_pty, gkermit_path, "send",
        "text_file.txt", content, is_text=True,
        gkermit_flags=["-T"], wermit_extra="set file type text, ")
    assert (dest_dir / "text_file.txt").read_bytes() == content.encode()


@pytest.mark.parametrize("file_name", [
    pytest.param("Mixed.Case.tar.gz", id="mixed-case-multidot"),
    pytest.param("ALLCAPS.TXT", id="all-caps"),
    pytest.param("lowercase.txt", id="lowercase"),
])
@pytest.mark.parametrize("direction", ["send", "get"])
def test_filenames_preserved(tmp_path, foreign_kermit_pty, gkermit_path,
                             direction, file_name):
    """Verify filename preservation in both transfer directions."""
    _gkermit_transfer(
        tmp_path, foreign_kermit_pty, gkermit_path, direction,
        file_name, b"filename preservation check")


def test_send_name_with_space(tmp_path, foreign_kermit_pty, gkermit_path):
    """Send path containing spaces to gkermit -r."""
    _gkermit_transfer(
        tmp_path, foreign_kermit_pty, gkermit_path, "send",
        "name with space.txt", b"space in filename, send direction")


def test_get_name_with_space(tmp_path, foreign_kermit_pty, gkermit_path):
    """Receive path containing spaces from gkermit -s."""
    _gkermit_transfer(
        tmp_path, foreign_kermit_pty, gkermit_path, "get",
        "name with space.txt", b"space in filename, get direction")


def test_collision_default_backup_suffix(tmp_path, foreign_kermit_pty,
                                         gkermit_path):
    """Verify default backup file naming (~1~) on collision."""
    dest_dir = tmp_path / "collision_dir"
    dest_dir.mkdir()
    src_dir = tmp_path / "collision_src"
    src_dir.mkdir()
    src = src_dir / "dup.txt"

    src.write_bytes(b"version 1")
    returncode, stdout = foreign_kermit_pty(
        [gkermit_path, "-r"],
        "set command more-prompting off, set delay 0, "
        f"set host {{HOST}}, send {src}, close, exit",
        dest_dir, timeout=15)
    assert returncode == 0, stdout

    src.write_bytes(b"version 2, different length")
    returncode, stdout = foreign_kermit_pty(
        [gkermit_path, "-r"],
        "set command more-prompting off, set delay 0, "
        f"set host {{HOST}}, send {src}, close, exit",
        dest_dir, timeout=15)
    assert returncode == 0, stdout

    assert (dest_dir / "dup.txt").read_bytes() == \
        b"version 2, different length"
    assert (dest_dir / "dup.txt.~1~").read_bytes() == b"version 1"


def test_collision_writeover_flag(tmp_path, foreign_kermit_pty, gkermit_path):
    """Verify -w flag causes file collision overwrite in place."""
    dest_dir = tmp_path / "collision_dir"
    dest_dir.mkdir()
    src_dir = tmp_path / "collision_src"
    src_dir.mkdir()
    src = src_dir / "dup.txt"

    for content in (b"version 1", b"version 2, different length"):
        src.write_bytes(content)
        returncode, stdout = foreign_kermit_pty(
            [gkermit_path, "-w", "-r"],
            "set command more-prompting off, set delay 0, "
            f"set host {{HOST}}, send {src}, close, exit",
            dest_dir, timeout=15)
        assert returncode == 0, stdout

    assert (dest_dir / "dup.txt").read_bytes() == \
        b"version 2, different length"
    assert not (dest_dir / "dup.txt.~1~").exists()


@pytest.mark.parametrize("packet_len", [96, 200, 1000])
def test_packet_length_negotiation(tmp_path, foreign_kermit_pty,
                                   gkermit_path, packet_len):
    """Verify transfer with negotiated packet length parameters."""
    content = pattern_bytes(20 * packet_len)
    _gkermit_transfer(
        tmp_path, foreign_kermit_pty, gkermit_path, "send",
        "multi_packet.dat", content,
        gkermit_flags=["-e", str(packet_len)],
        wermit_extra=(
            f"set send packet-length {packet_len}, "
            f"set receive packet-length {packet_len}, "
        ))

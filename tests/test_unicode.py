"""
This file contains tests for the Unicode conversion routines in Kermit.

How Kermit decides when to perform character set translation:

1. File Type (Text vs. Binary):
   Character translation is only performed on files transferred in text
   mode. If the effective file type is binary, no translation is performed.
   See comments in test_line_endings.py for more on this.

2. Transfer Translation Setting:
   Character set translation must be enabled. This is controlled by the
   SET TRANSFER TRANSLATION command. By default, it is ON. If set to OFF,
   translation is bypassed.

3. Character Set Configurations:
   Kermit defines the local file encoding via SET FILE CHARACTER-SET
   (defaulting to ASCII) and the wire/network encoding via SET TRANSFER
   CHARACTER-SET.
   - If the transfer character set is set to transparent, or if
     translation is disabled, no translation takes place.
   - If both the file character set and the transfer character set are
     identical (and neither is Unicode), translation is bypassed.
   - If either the file character set or the transfer character set is
     a Unicode encoding (e.g. 'utf8' or 'ucs2'), Kermit routes the file
     through Unicode translation routines. Even if they are identical
     (e.g., ucs2 to ucs2), Unicode translation is performed to handle
     byte-order marks (BOM) and byte swapping.

4. System Compatibility (wearealike check):
   Unlike End-of-Line (EOL) translation, which is bypassed if the sender
   and receiver run on compatible operating systems (where wearealike is
   set to 1), character set translation is NOT bypassed when systems are
   alike, as long as the character sets differ or one of them is Unicode.
"""

import pytest
from conftest import assert_ok


def cs_setup(fcs, transfer_cs):
    return [
        "set delay 0",
        "set file type text",
        "set transfer translation on",
        "set send character-set manual",
        "set file scan off",
        f"set file character-set {fcs}",
        f"set transfer character-set {transfer_cs}",
    ]


def run_translation_test(tmp_path, wermit_loopback, direction,
                         sender_fcs, receiver_fcs,
                         transfer_cs,
                         sender_setup_extra, receiver_setup_extra,
                         file_name, file_content, expected_content):
    """
    Helper to run a loopback transfer with specific character set settings.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    src_file = src_dir / file_name
    src_file.write_bytes(file_content)

    # Base setup commands for sender and receiver
    receiver_cmds = cs_setup(receiver_fcs, transfer_cs)
    if receiver_setup_extra:
        receiver_cmds.extend(
            [c.strip() for c in receiver_setup_extra.split(",")]
        )

    sender_cmds = cs_setup(sender_fcs, transfer_cs)
    if sender_setup_extra:
        sender_cmds.extend(
            [c.strip() for c in sender_setup_extra.split(",")]
        )

    if direction == "send":
        sender_cmds.append(f"send {src_file}")
        result = wermit_loopback(dest_dir, "\n".join(receiver_cmds),
                                 ", ".join(sender_cmds))
    elif direction == "get":
        receiver_cmds.extend([
            f"cd {dest_dir}",
            f"get {file_name}"
        ])
        result = wermit_loopback(src_dir, "\n".join(sender_cmds),
                                 ", ".join(receiver_cmds))
    else:
        raise ValueError(f"Unknown direction: {direction}")

    assert_ok(result)

    dest_file = dest_dir / file_name
    assert dest_file.exists()
    dest_content = dest_file.read_bytes()
    assert dest_content == expected_content, (
        f"Expected {expected_content!r}, got {dest_content!r}\n"
        f"Client stdout: {result.stdout}"
    )


# 1. Test UTF-8 to/from Latin-1 (aka latin1 or ISO-8859-1)

@pytest.mark.parametrize("direction", ["send", "get"])
def test_utf8_to_latin1(tmp_path, wermit_loopback, direction):
    # Input content: "El niño y el café." in UTF-8
    run_translation_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_fcs="utf8",
        receiver_fcs="latin1-iso",
        transfer_cs="utf8",
        sender_setup_extra="",
        receiver_setup_extra="",
        file_name="test.txt",
        file_content=b"El ni\xc3\xb1o y el caf\xc3\xa9.",
        expected_content=b"El ni\xf1o y el caf\xe9."
    )


@pytest.mark.parametrize("direction", ["send", "get"])
def test_latin1_to_utf8(tmp_path, wermit_loopback, direction):
    # Input content: "El niño y el café." in Latin-1
    run_translation_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_fcs="latin1-iso",
        receiver_fcs="utf8",
        transfer_cs="utf8",
        sender_setup_extra="",
        receiver_setup_extra="",
        file_name="test.txt",
        file_content=b"El ni\xf1o y el caf\xe9.",
        expected_content=b"El ni\xc3\xb1o y el caf\xc3\xa9."
    )


# 2. Test UTF-8 to/from UTF-16 (UCS-2) - Big Endian (No BOM)

@pytest.mark.parametrize("direction", ["send", "get"])
def test_utf8_to_ucs2_be_nobom(tmp_path, wermit_loopback, direction):
    expected = (
        b"\x00E\x00l\x00 \x00n\x00i\x00\xf1\x00o\x00 \x00y"
        b"\x00 \x00e\x00l\x00 \x00c\x00a\x00f\x00\xe9\x00."
    )
    run_translation_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_fcs="utf8",
        receiver_fcs="ucs2",
        transfer_cs="utf8",
        sender_setup_extra="",
        receiver_setup_extra=(
            "set file ucs byte-order big-endian, "
            "set file ucs bom off"
        ),
        file_name="test.txt",
        file_content=b"El ni\xc3\xb1o y el caf\xc3\xa9.",
        expected_content=expected
    )


# 3. Test UTF-8 to/from UTF-16 (UCS-2) - Little Endian (No BOM)
@pytest.mark.parametrize("direction", ["send", "get"])
def test_utf8_to_ucs2_le_nobom(tmp_path, wermit_loopback, direction):
    expected = (
        b"E\x00l\x00 \x00n\x00i\x00\xf1\x00o\x00 \x00y\x00 \x00"
        b"e\x00l\x00 \x00c\x00a\x00f\x00\xe9\x00.\x00"
    )
    run_translation_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_fcs="utf8",
        receiver_fcs="ucs2",
        transfer_cs="utf8",
        sender_setup_extra="",
        receiver_setup_extra=(
            "set file ucs byte-order little-endian, "
            "set file ucs bom off"
        ),
        file_name="test.txt",
        file_content=b"El ni\xc3\xb1o y el caf\xc3\xa9.",
        expected_content=expected
    )


# 4. Test UTF-8 to/from UTF-16 (UCS-2) - Big Endian (With BOM)
@pytest.mark.parametrize("direction", ["send", "get"])
def test_utf8_to_ucs2_be_bom(tmp_path, wermit_loopback, direction):
    expected = (
        b"\xfe\xff\x00E\x00l\x00 \x00n\x00i\x00\xf1\x00o\x00 \x00y"
        b"\x00 \x00e\x00l\x00 \x00c\x00a\x00f\x00\xe9\x00."
    )
    run_translation_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_fcs="utf8",
        receiver_fcs="ucs2",
        transfer_cs="utf8",
        sender_setup_extra="",
        receiver_setup_extra=(
            "set file ucs byte-order big-endian, "
            "set file ucs bom on"
        ),
        file_name="test.txt",
        file_content=b"El ni\xc3\xb1o y el caf\xc3\xa9.",
        expected_content=expected
    )


# 5. Test UTF-16 (UCS-2) to UTF-8 - Big Endian (No BOM)
@pytest.mark.parametrize("direction", ["send", "get"])
def test_ucs2_be_nobom_to_utf8(tmp_path, wermit_loopback, direction):
    content = (
        b"\x00E\x00l\x00 \x00n\x00i\x00\xf1\x00o\x00 \x00y"
        b"\x00 \x00e\x00l\x00 \x00c\x00a\x00f\x00\xe9\x00."
    )
    run_translation_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_fcs="ucs2",
        receiver_fcs="utf8",
        transfer_cs="utf8",
        sender_setup_extra=(
            "set file ucs byte-order big-endian, "
            "set file ucs bom off"
        ),
        receiver_setup_extra="",
        file_name="test.txt",
        file_content=content,
        expected_content=b"El ni\xc3\xb1o y el caf\xc3\xa9."
    )


# 6. Test UTF-16 (UCS-2) to UTF-8 - Little Endian (No BOM)
@pytest.mark.parametrize("direction", ["send", "get"])
def test_ucs2_le_nobom_to_utf8(tmp_path, wermit_loopback, direction):
    content = (
        b"E\x00l\x00 \x00n\x00i\x00\xf1\x00o\x00 \x00y\x00 \x00"
        b"e\x00l\x00 \x00c\x00a\x00f\x00\xe9\x00.\x00"
    )
    run_translation_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_fcs="ucs2",
        receiver_fcs="utf8",
        transfer_cs="utf8",
        sender_setup_extra=(
            "set file ucs byte-order little-endian, "
            "set file ucs bom off"
        ),
        receiver_setup_extra="",
        file_name="test.txt",
        file_content=content,
        expected_content=b"El ni\xc3\xb1o y el caf\xc3\xa9."
    )


# 7. Test UTF-16 (UCS-2) to UTF-8 - Big Endian (Autodetect via BOM)
@pytest.mark.parametrize("direction", ["send", "get"])
def test_ucs2_be_bom_to_utf8(tmp_path, wermit_loopback, direction):
    content = (
        b"\xfe\xff\x00E\x00l\x00 \x00n\x00i\x00\xf1\x00o\x00 \x00y"
        b"\x00 \x00e\x00l\x00 \x00c\x00a\x00f\x00\xe9\x00."
    )
    run_translation_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_fcs="ucs2",
        receiver_fcs="utf8",
        transfer_cs="utf8",
        sender_setup_extra="",
        receiver_setup_extra="",
        file_name="test.txt",
        file_content=content,
        expected_content=b"El ni\xc3\xb1o y el caf\xc3\xa9."
    )


# 8. Test UTF-16 (UCS-2) to UTF-8 - Little Endian (Autodetect via BOM)
@pytest.mark.parametrize("direction", ["send", "get"])
def test_ucs2_le_bom_to_utf8(tmp_path, wermit_loopback, direction):
    content = (
        b"\xff\xfeE\x00l\x00 \x00n\x00i\x00\xf1\x00o\x00 \x00y\x00 \x00"
        b"e\x00l\x00 \x00c\x00a\x00f\x00\xe9\x00.\x00"
    )
    run_translation_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_fcs="ucs2",
        receiver_fcs="utf8",
        transfer_cs="utf8",
        sender_setup_extra="",
        receiver_setup_extra="",
        file_name="test.txt",
        file_content=content,
        expected_content=b"El ni\xc3\xb1o y el caf\xc3\xa9."
    )


# 9. Test UTF-8 to UTF-8 via UCS-2 Wire Transfer
@pytest.mark.parametrize("direction", ["send", "get"])
def test_utf8_to_utf8_via_ucs2_transfer(tmp_path, wermit_loopback, direction):
    run_translation_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_fcs="utf8",
        receiver_fcs="utf8",
        transfer_cs="ucs2",
        sender_setup_extra="",
        receiver_setup_extra="",
        file_name="test.txt",
        file_content=b"El ni\xc3\xb1o y el caf\xc3\xa9.",
        expected_content=b"El ni\xc3\xb1o y el caf\xc3\xa9."
    )


# 10. Test Latin-1 to Latin-1 via UTF-8 Wire Transfer
@pytest.mark.parametrize("direction", ["send", "get"])
def test_latin1_to_latin1_via_utf8_transfer(
    tmp_path, wermit_loopback, direction
):
    run_translation_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_fcs="latin1-iso",
        receiver_fcs="latin1-iso",
        transfer_cs="utf8",
        sender_setup_extra="",
        receiver_setup_extra="",
        file_name="test.txt",
        file_content=b"El ni\xf1o y el caf\xe9.",
        expected_content=b"El ni\xf1o y el caf\xe9."
    )


# 11. Test consecutive transfers with different byte orders to verify that
# fileorder is correctly reset per-file in a single session.
# This verifies the bugfix in 93ffe02415fbcc82c56133cc91d4585a4e8a8055.
def test_unicode_consecutive_transfers(tmp_path, wermit_loopback):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    # File 1: UCS-2 LE no-BOM ("LE")
    file1 = src_dir / "file1.txt"
    file1.write_bytes(b"L\x00E\x00")

    # File 2: UCS-2 BE no-BOM ("BE")
    file2 = src_dir / "file2.txt"
    file2.write_bytes(b"\x00B\x00E")

    receiver_cmds = cs_setup("utf8", "utf8")
    sender_cmds = cs_setup("ucs2", "utf8") + ["set file ucs bom off"]

    # Send LE first, then BE.
    cmds = sender_cmds + [
        "set file ucs byte-order little-endian",
        f"send {file1}",
        "set file ucs byte-order big-endian",
        f"send {file2}",
    ]

    result = wermit_loopback(dest_dir, "\n".join(
        receiver_cmds), ", ".join(cmds))
    assert_ok(result)

    dest1 = dest_dir / "file1.txt"
    dest2 = dest_dir / "file2.txt"
    assert dest1.exists()
    assert dest2.exists()

    assert dest1.read_bytes() == b"LE"
    assert dest2.read_bytes() == b"BE"


# 12. Test translating characters that cannot be represented in the
# destination encoding.
@pytest.mark.parametrize("direction", ["send", "get"])
def test_utf8_to_ascii_unrepresented(tmp_path, wermit_loopback, direction):
    # Accented characters 'ñ' and 'é' cannot be represented in ASCII.
    # They should be replaced by the default unknown symbol '?' (ASCII 63).
    run_translation_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_fcs="utf8",
        receiver_fcs="ascii",
        transfer_cs="utf8",
        sender_setup_extra="",
        receiver_setup_extra="",
        file_name="test.txt",
        file_content=b"El ni\xc3\xb1o y el caf\xc3\xa9.",
        expected_content=b"El ni?o y el caf?."
    )

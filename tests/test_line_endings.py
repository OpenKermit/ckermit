"""
The tests in this file test the line ending conversions performed by
Kermit.

Line ending translation is determined by the interaction of four settings:

1. SET FILE SYSTEM-ID: e.g. U1 (UNIX), UN (Windows), D7 (VMS).  This
identifies the type of operating system that Kermit is running on.

2. SET FILE TRANSFER MODE: manual or automatic.  This setting controls whether
Kermit detects file type automatically, or stricly uses the configured
SET FILE TYPE.

3. SET FILE TYPE: text, binary.  The default file type, strictly used
only if SET FILE TRANSFER MODE is manual.

4. SET FILE END-OF-LINE: lf, crlf, cr.  Specifies the EOL format of the local
system.

How Kermit decides whether to translate line endings:

1. Determine Effective File Type:
   - In manual mode, it uses the configured SET FILE TYPE (text or binary).
   - In automatic mode, it detects type from filename extension
     (e.g. .txt -> text) or content analysis using scanfile().
   - If the effective type is binary, no EOL translation is performed.

2. Check System Compatibility (wearealike check):
   - At connection startup, the sender and receiver exchange their System IDs.
   - If the IDs match or represent compatible OS families (e.g. UNIX to UNIX,
     or Windows to MS-DOS), Kermit determines they are alike (wearealike = 1).
   - If wearealike is 1, EOL translation is completely bypassed (even for text
     files)
     to preserve byte structure and optimize performance.
   - If wearealike is 0 (systems are not compatible), EOL translation is
     performed.

3. EOL Translation Execution:
   - The sender reads line endings using its configured SET FILE END-OF-LINE
     (or system default) and converts them to the network canonical EOL (CRLF).
   - The receiver translates incoming CRLFs to its local SET FILE END-OF-LINE
     (or system default).

Why these tests require SET FILE SYSTEM-ID:

In a loopback test setup, both Kermit processes run on the same Linux host,
meaning both default to reporting the same system ID (U1). Since their system
IDs match, Kermit marks them alike (wearealike = 1) and skips EOL translation
entirely.  To test cross-platform EOL translation, the tests use 'set file
system-id' to simulate dissimilar systems (e.g. UNIX U1 sending to Windows
UN), forcing wearealike to 0 and triggering EOL translation.
"""

import pytest
from pathlib import Path
from conftest import assert_ok, make_loopback_dirs, resolve_transfer_paths

_SETUP_TEXT_AUTO = (
    "set transfer mode automatic, set file type text, "
    "set transfer translation on, set transfer character-set latin1"
)
_SETUP_BINARY_AUTO = (
    "set transfer mode automatic, set file type binary, "
    "set transfer translation on, set transfer character-set latin1"
)
_SETUP_AUTO = "set transfer mode automatic"


def _resolve_sysid(sysid, eol):
    if sysid is None:
        return "U1" if eol == "lf" else "UN"
    return sysid


def run_ending_test(tmp_path, wermit_loopback, direction,
                    sender_eol, receiver_eol,
                    sender_setup_extra, receiver_setup_extra,
                    file_name, file_content, expected_content,
                    sender_sysid=None, receiver_sysid=None):
    """
    Helper to run a loopback transfer with specific EOL settings and extra
    commands.
    """
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    src_file, dest_file = resolve_transfer_paths(
        client_dir, server_dir, direction, file_name)

    src_file.write_bytes(file_content)

    # Determine simulated platform system ID.
    sender_sysid = _resolve_sysid(sender_sysid, sender_eol)
    receiver_sysid = _resolve_sysid(receiver_sysid, receiver_eol)

    sender_sysid_cmd = f"set file system-id {sender_sysid}"
    receiver_sysid_cmd = f"set file system-id {receiver_sysid}"

    sender_eol_cmd = f"set file end-of-line {sender_eol}"
    receiver_eol_cmd = f"set file end-of-line {receiver_eol}"

    # Combine receiver setups
    receiver_cmds = [
        "set delay 0",
        receiver_sysid_cmd,
        receiver_eol_cmd,
    ]
    if receiver_setup_extra:
        receiver_cmds.append(receiver_setup_extra)

    # Combine sender/client setups
    client_cmds = [
        "set delay 0",
        sender_sysid_cmd,
        sender_eol_cmd,
    ]
    if sender_setup_extra:
        client_cmds.append(sender_setup_extra)

    if direction == "send":
        # Server is receiver, client is sender.
        client_cmds.append(f"send {src_file}")
        result = wermit_loopback(server_dir, "\n".join(receiver_cmds),
                                 ", ".join(client_cmds))
    elif direction == "get":
        # Server is sender, client is receiver.
        client_cmds_rcv = receiver_cmds + \
            [f"cd {client_dir}", f"get {file_name}"]
        result = wermit_loopback(server_dir, "\n".join(client_cmds),
                                 ", ".join(client_cmds_rcv))
    else:
        raise ValueError(f"Unknown direction: {direction}")

    assert_ok(result)

    assert dest_file.exists()
    assert dest_file.read_bytes() == expected_content, (
        f"Client stdout: {result.stdout}"
    )

# 1. Test that by default (manual transfer mode, binary file type), line
# endings are NOT changed.
#
# This covers the fix to the default transfer mode in commit
# cdd2e257e8720e2d42a7a41ad504c76a95ef5ade.


@pytest.mark.parametrize("direction", ["send", "get"])
def test_default_no_conversion_lf_to_crlf(
        tmp_path, wermit_loopback, direction):
    # Linux (LF) to Windows (CRLF), but with defaults (manual, binary)
    run_ending_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_eol="lf",
        receiver_eol="crlf",
        sender_setup_extra="",
        receiver_setup_extra="",
        file_name="file.txt",
        file_content=b"Line 1\nLine 2\n",
        expected_content=b"Line 1\nLine 2\n"
    )


@pytest.mark.parametrize("direction", ["send", "get"])
def test_default_no_conversion_crlf_to_lf(
        tmp_path, wermit_loopback, direction):
    # Windows (CRLF) to Linux (LF), but with defaults (manual, binary)
    # Also relevant to cdd2e257e8720e2d42a7a41ad504c76a95ef5ade.
    run_ending_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_eol="crlf",
        receiver_eol="lf",
        sender_setup_extra="",
        receiver_setup_extra="",
        file_name="file.txt",
        file_content=b"Line 1\r\nLine 2\r\n",
        expected_content=b"Line 1\r\nLine 2\r\n"
    )

# 2. Test explicit text mode (set file type text) with automatic transfer
# mode (set transfer mode automatic)


@pytest.mark.parametrize("direction", ["send", "get"])
def test_explicit_text_auto_conversion_lf_to_crlf(
        tmp_path, wermit_loopback, direction):
    # Linux (LF) to Windows (CRLF)
    setup = _SETUP_TEXT_AUTO
    run_ending_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_eol="lf",
        receiver_eol="crlf",
        sender_setup_extra=setup,
        receiver_setup_extra=setup,
        file_name="file.txt",
        file_content=b"Line 1\nLine 2\n",
        expected_content=b"Line 1\r\nLine 2\r\n"
    )


@pytest.mark.parametrize("direction", ["send", "get"])
def test_explicit_text_auto_conversion_crlf_to_lf(
        tmp_path, wermit_loopback, direction):
    # Windows (CRLF) to Linux (LF)
    setup = _SETUP_TEXT_AUTO
    run_ending_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_eol="crlf",
        receiver_eol="lf",
        sender_setup_extra=setup,
        receiver_setup_extra=setup,
        file_name="file.txt",
        file_content=b"Line 1\r\nLine 2\r\n",
        expected_content=b"Line 1\nLine 2\n"
    )

# 3. Test automatic detection of .txt file (default binary type, but auto
# transfer mode enables text mode for .txt)


@pytest.mark.parametrize("direction", ["send", "get"])
def test_auto_detect_txt_conversion_lf_to_crlf(
        tmp_path, wermit_loopback, direction):
    # Linux (LF) to Windows (CRLF) with .txt extension
    setup = _SETUP_BINARY_AUTO
    run_ending_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_eol="lf",
        receiver_eol="crlf",
        sender_setup_extra=setup,
        receiver_setup_extra=setup,
        file_name="file.txt",
        file_content=b"Line 1\nLine 2\n",
        expected_content=b"Line 1\r\nLine 2\r\n"
    )


@pytest.mark.parametrize("direction", ["send", "get"])
def test_auto_detect_txt_conversion_crlf_to_lf(
        tmp_path, wermit_loopback, direction):
    # Windows (CRLF) to Linux (LF) with .txt extension
    setup = _SETUP_BINARY_AUTO
    run_ending_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_eol="crlf",
        receiver_eol="lf",
        sender_setup_extra=setup,
        receiver_setup_extra=setup,
        file_name="file.txt",
        file_content=b"Line 1\r\nLine 2\r\n",
        expected_content=b"Line 1\nLine 2\n"
    )


@pytest.mark.parametrize("direction", ["send", "get"])
def test_auto_detect_dat_no_conversion(tmp_path, wermit_loopback, direction):
    # Linux (LF) to Windows (CRLF) with .dat extension and default/binary type
    # We include binary bytes (null and 0xff) to ensure scanfile classifies it
    # as binary.
    setup = _SETUP_BINARY_AUTO
    run_ending_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_eol="lf",
        receiver_eol="crlf",
        sender_setup_extra=setup,
        receiver_setup_extra=setup,
        file_name="file.dat",
        file_content=b"Line 1\nLine 2\n\0\xff",
        expected_content=b"Line 1\nLine 2\n\0\xff"
    )


@pytest.mark.parametrize("direction", ["send", "get"])
def test_scanfile_small_file_ucs2_be_bug(tmp_path, wermit_loopback, direction):
    """
    Regression test for the scanfile() small file UCS-2 detection bug,
    which was fixed in dfd875f3e7651def1a63aa528f3647d0d10aae9f.

    Prior to the fix, a file under 20 bytes containing 8-bit data
    and a zero byte at an even position would be misidentified as
    UCS-2 Big Endian and therefore text.

    The fix forces a minimum x of 2, preventing false UCS-2 detection.
    """
    setup = _SETUP_BINARY_AUTO

    # Null byte in even position (triggers BE check before fix)
    # Length of "Short binary!\n" is 14, so \0 is at index 14 (even position)
    run_ending_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_eol="lf",
        receiver_eol="crlf",
        sender_setup_extra=setup,
        receiver_setup_extra=setup,
        file_name="small_be.dat",
        file_content=b"Short binary!\n\0\xff",
        expected_content=b"Short binary!\n\0\xff"
    )


@pytest.mark.parametrize("direction", ["send", "get"])
def test_scanfile_small_file_ucs2_le_bug(tmp_path, wermit_loopback, direction):
    """
    Similar to test_scanfile_small_file_ucs2_be_bug, but this tests for
    correct behavior with a zero byte in an odd position.
    """
    setup = _SETUP_BINARY_AUTO

    # Null byte in odd position (triggers LE check before fix)
    # Length of "Short binary\n" is 13, so \0 is at index 13 (odd position)
    run_ending_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_eol="lf",
        receiver_eol="crlf",
        sender_setup_extra=setup,
        receiver_setup_extra=setup,
        file_name="small_le.dat",
        file_content=b"Short binary\n\0\xff",
        expected_content=b"Short binary\n\0\xff"
    )


@pytest.mark.parametrize("direction", ["send", "get"])
def test_wearealike_eol_bypass_lf_to_crlf(
        tmp_path, wermit_loopback, direction):
    """
    Test EOL translation bypass when systems are alike (wearealike=1)
    even if the client and server have conflicting local EOL configurations.
    Here, UNIX (U1) to UNIX (U1), sender EOL lf, receiver EOL crlf.
    """
    setup = _SETUP_AUTO
    run_ending_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_eol="lf",
        receiver_eol="crlf",
        sender_setup_extra=setup,
        receiver_setup_extra=setup,
        file_name="file.txt",
        file_content=b"Line 1\nLine 2\n",
        expected_content=b"Line 1\nLine 2\n",
        sender_sysid="U1",
        receiver_sysid="U1"
    )


@pytest.mark.parametrize("direction", ["send", "get"])
def test_wearealike_eol_bypass_crlf_to_lf(
        tmp_path, wermit_loopback, direction):
    """
    Test EOL translation bypass when systems are alike (wearealike=1)
    even if the client and server have conflicting local EOL configurations.
    Here, UNIX (U1) to UNIX (U1), sender EOL crlf, receiver EOL lf.
    """
    setup = _SETUP_AUTO
    run_ending_test(
        tmp_path=tmp_path,
        wermit_loopback=wermit_loopback,
        direction=direction,
        sender_eol="crlf",
        receiver_eol="lf",
        sender_setup_extra=setup,
        receiver_setup_extra=setup,
        file_name="file.txt",
        file_content=b"Line 1\r\nLine 2\r\n",
        expected_content=b"Line 1\r\nLine 2\r\n",
        sender_sysid="U1",
        receiver_sysid="U1"
    )

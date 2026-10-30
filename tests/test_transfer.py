"""Kermit file transfer tests.

Tests of the transfer engine run over a pty.  Tests that apply
ALL_TRANSPORTS also run over raw-socket, telnet and ssl.
"""
import os
import re
import signal
import threading
import pytest
from pathlib import Path
import logging
from conftest import (CLEAR_UNPREFIX_MODES, assert_ok, make_loopback_dirs,
                      pattern_bytes, resolve_transfer_paths, scaled)

logger = logging.getLogger(__name__)


ALL_TRANSPORTS = pytest.mark.parametrize(
    "loopback_transport", ["pseudoterminal", "raw-socket", "telnet", "ssl"],
    indirect=True)


# Default long packet length C-Kermit negotiates with itself over this
# suite's pty loopback (wermit_loopback), with no explicit SET
# SEND/RECEIVE PACKET-LENGTH. Confirmed with STATISTICS /VERBOSE after
# a loopback SEND: "packet length : 3997 (send), 4000 (receive)".
KERMIT_PACKET_LEN = 4000

# Packet length requested by SET RECEIVE/SEND PACKET-LENGTH 9024 (the
# platform max according to MAXSP/MAXRP in ckcker.h).  Confirmed by
# STATISTICS /VERBOSE and packet counts that this is actually reached
# end to end in both directions (e.g. a 3MB SEND drops from 878
# packets at the KERMIT_PACKET_LEN default to 383 packets, "packet
# length: 9021 (send), 9024 (receive)")
JUMBO_PACKET_LEN = 9024

MB = 1024 * 1024


def run_transfer_helper(tmp_path, wermit_loopback, direction,
                        file_type, file_name, file_content, is_text=False,
                        timeout=10, protocol_cmds=""):
    """
    Execute loopback file transfer tests in both SEND and GET directions.

    This helper function sets up a temporary workspace directory tree
    containing "client" and "server" subdirectories, writes the specified
    content to the source file, and executes a file transfer between two
    kermit instances.

    Parameters:

    tmp_path (pathlib.Path):
        Pytest fixture providing a temporary directory for the test.
    wermit_loopback (callable):
        A fixture that runs a client against a fresh loopback server
        for one command sequence and returns a CompletedProcess.
    direction (str):
        The transfer direction. Valid settings:
            - "send": The client sends the file to the server.
            - "get": The client gets the file from the server.
    file_type (str):
        The C-Kermit file transfer type. Valid settings:
            - "binary": Transfers raw bytes without modifications.
            - "text": Transfers text, allowing record format conversion.
    file_name (str):
        The name of the file to create and transfer (e.g., "test.dat").
    file_content (bytes or str):
        The content to write to the source file before transferring.
    is_text (bool, optional):
        If True, writes the file and reads it as text (using unicode
        strings). If False (default), writes and reads raw bytes.
    timeout (int, optional):
        Seconds to allow the client process to run before it is
        considered hung.  Defaults to 10.
    protocol_cmds (str, optional):
        Extra comma-separated SET commands (e.g. SET RELIABLE ON,
        SET STREAMING ON) applied to both the server and the client
        before the transfer.
    """
    logger.info("run_transfer_helper: Starting transfer. "
                "Direction: %s, type: %s, file: %s",
                direction, file_type, file_name)

    client_dir, server_dir = make_loopback_dirs(tmp_path)
    src_file, dest_file = resolve_transfer_paths(
        client_dir, server_dir, direction, file_name)

    if is_text:
        src_file.write_text(file_content)
    else:
        src_file.write_bytes(file_content)

    file_size = len(file_content)
    logger.info("run_transfer_helper: Dirs and source file created. "
                "File size: %d bytes.", file_size)

    if direction == "send":
        client_cmd = f"set file type {file_type}, set delay 0, send {src_file}"
    else:
        client_cmd = (f"set file type {file_type}, set delay 0, "
                      f"cd {client_dir}, get {file_name}")
    server_setup_cmds = f"set file type {file_type}, set delay 0"
    if protocol_cmds:
        server_setup_cmds = f"{protocol_cmds}, {server_setup_cmds}"
        client_cmd = f"{protocol_cmds}, {client_cmd}"
    logger.info("run_transfer_helper: Running loopback transfer in %s",
                server_dir)
    result = wermit_loopback(server_dir, server_setup_cmds,
                             client_cmd, timeout=timeout)

    logger.info("run_transfer_helper: Client exit code: %d", result.returncode)
    logger.debug("run_transfer_helper: Client stdout: %s", result.stdout)
    logger.debug("run_transfer_helper: Client stderr: %s", result.stderr)
    assert_ok(result)

    # Verify exact contents on the destination side
    logger.info("run_transfer_helper: Verifying destination file %s",
                dest_file)
    assert dest_file.exists()
    if is_text:
        content = dest_file.read_text()
    else:
        content = dest_file.read_bytes()
    assert content == file_content


def run_transfers_in_one_session(tmp_path, wermit_loopback, direction,
                                 contents, protocol_cmds="", timeout=None):
    """Transfer several binary files in one loopback session.

    contents maps each file name to its bytes.  Each file is a separate
    SEND or GET transaction.  The assertion names every file that did
    not arrive intact.  protocol_cmds is a comma-separated list of SET
    commands that both ends run first.  The timeout defaults to 10 s
    per file.
    """
    if timeout is None:
        timeout = 10 * len(contents)
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    for name, content in contents.items():
        src_file, _ = resolve_transfer_paths(
            client_dir, server_dir, direction, name)
        src_file.write_bytes(content)
    prefix = f"{protocol_cmds}, " if protocol_cmds else ""
    transfers = ", ".join(f"{direction} {name}" for name in contents)
    result = wermit_loopback(
        server_dir,
        f"{prefix}set file type binary",
        f"{prefix}set file type binary, cd {client_dir}, {transfers}",
        timeout=timeout)
    bad = []
    for name, content in contents.items():
        _, dest_file = resolve_transfer_paths(
            client_dir, server_dir, direction, name)
        if not dest_file.exists() or dest_file.read_bytes() != content:
            bad.append(name)
    assert not bad, (bad, result.stdout[-2000:])
    assert_ok(result)


@ALL_TRANSPORTS
@CLEAR_UNPREFIX_MODES
@pytest.mark.parametrize("direction", ["send", "get"])
def test_kermit_transfer_binary(tmp_path, wermit_loopback, direction):
    """
    Test binary file transfer in both SEND and GET directions, for a
    range of file sizes: 1K, sizes around KERMIT_PACKET_LEN, and twice
    KERMIT_PACKET_LEN.  The packet boundary code is the same for each
    packet after the first.  One session transfers every size.
    Verifies that files are byte-identical.
    """
    sizes = [1024, KERMIT_PACKET_LEN - 1, KERMIT_PACKET_LEN,
             KERMIT_PACKET_LEN + 1, 2 * KERMIT_PACKET_LEN]
    run_transfers_in_one_session(
        tmp_path, wermit_loopback, direction,
        {f"binary_{size}.dat": pattern_bytes(size) for size in sizes})


@ALL_TRANSPORTS
@CLEAR_UNPREFIX_MODES
@pytest.mark.parametrize("direction", ["send", "get"])
def test_kermit_transfer_large(tmp_path, wermit_loopback, direction,
                               loopback_transport):
    """
    Test binary file transfer of a file well beyond a single packet
    or window, in both SEND and GET directions.

    A window is at most 32 packets of 9024 bytes.  1 MB spans several
    windows.  A GET over pty moves 5 MB.  In a GET the far end writes
    the data on the slave side of the pty.  On NetBSD, data written on
    the master side moves at 230 KB/s on a 599 MHz Alpha.
    """
    size = 5 * MB if (loopback_transport == "pseudoterminal"
                      and direction == "get") else MB
    logger.info(
        "test_kermit_transfer_large: Starting test (direction=%s, size=%d)",
        direction, size)
    run_transfer_helper(
        tmp_path,
        wermit_loopback,
        direction,
        file_type="binary",
        file_name="large_file.dat",
        file_content=pattern_bytes(size),
        is_text=False,
        timeout=60
    )
    logger.info(
        "test_kermit_transfer_large: Test passed (direction=%s, size=%d)",
        direction, size)


def _run_nul_replay_transfer(tmp_path, wermit_loopback):
    """Runs the unprefixed-NUL-replay transfer once and asserts the
    destination file is byte-identical to the source. Shared by
    test_kermit_transfer_unprefixed_nul_replay (which sweeps several
    attempts on one transport to catch the race) and
    test_kermit_transfer_unprefixed_nul_replay_transport_smoke (which
    runs once per other transport).

    The strlen() bug fixed in b58e0336 reproduces on NetBSD x86 in
    about half of 512 KB transfers.  A 2 MB transfer reproduces at the
    same rate, and 128 KB does not reproduce it.  It does not
    reproduce on Linux."""
    content = pattern_bytes(512 * 1024)
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    src_file = client_dir / "nul_replay.dat"
    src_file.write_bytes(content)

    result = wermit_loopback(
        server_dir,
        server_setup_cmds=(
            "set control unprefix all, set file type binary, set delay 0"
        ),
        client_commands=(
            "set control unprefix all, set file type binary, "
            f"set delay 0, send {src_file}"
        ),
        timeout=30,
        # Enable server debug logging to slow server execution.
        server_debug_log=True,
    )
    assert_ok(result)

    dest_file = server_dir / "nul_replay.dat"
    assert dest_file.exists()
    assert dest_file.read_bytes() == content


@CLEAR_UNPREFIX_MODES
@pytest.mark.parametrize("loopback_transport", ["pseudoterminal"],
                         indirect=True)
@pytest.mark.parametrize("attempt", range(5))
@pytest.mark.slow
def test_kermit_transfer_unprefixed_nul_replay(tmp_path, wermit_loopback,
                                               attempt, loopback_transport):
    """Binary transfer with embedded NUL bytes under out-of-order replay.

    Forces SET CONTROL UNPREFIX ALL on the server with server debug logging
    enabled to test packet replay processing when the server lags the client.
    """
    _run_nul_replay_transfer(tmp_path, wermit_loopback)


@CLEAR_UNPREFIX_MODES
@pytest.mark.parametrize("loopback_transport",
                         ["raw-socket", "telnet", "ssl"], indirect=True)
@pytest.mark.slow
def test_kermit_transfer_unprefixed_nul_replay_transport_smoke(
        tmp_path, wermit_loopback, loopback_transport):
    """
    To save time, just one attempt per transport rather than 5.
    The race itself does not depend on transport choice.
    """
    _run_nul_replay_transfer(tmp_path, wermit_loopback)


@pytest.mark.parametrize("direction", ["send", "get"])
@pytest.mark.parametrize("loopback_transport",
                         ["telnet", "ssl", "ssl-telnet", "tls-telnet"],
                         indirect=True)
def test_kermit_transfer_with_telnet_wait(tmp_path, wermit_loopback,
                                          loopback_transport, direction):
    """Binary transfer with the default Telnet negotiation wait.

    The other tests in this module turn the wait off.  This one keeps
    tn_wait() in the session setup.  /SSL-TELNET and /TLS-TELNET
    negotiate Telnet inside TLS.  The file holds every byte value.
    """
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    content = bytes(range(256)) * 64
    src_dir, dest_dir = ((client_dir, server_dir) if direction == "send"
                         else (server_dir, client_dir))
    (src_dir / "all.bin").write_bytes(content)
    result = wermit_loopback(
        server_dir,
        server_setup_cmds="set file type binary",
        client_commands=(f"cd {client_dir}, set file type binary, "
                         f"{direction} all.bin"),
        telnet_wait=True)
    assert_ok(result)
    assert (dest_dir / "all.bin").read_bytes() == content


def protocol_option_cmds(reliable, streaming, slow_start, jumbo):
    """Build the comma-separated SET command string for one
    combination of the reliable/streaming/slow-start/jumbo-packet
    options, for use as run_transfer_helper's protocol_cmds."""
    cmds = [
        f"set reliable {'on' if reliable else 'off'}",
        f"set streaming {'on' if streaming else 'off'}",
        f"set transfer slow-start {'on' if slow_start else 'off'}",
    ]
    if jumbo:
        cmds.append(f"set receive packet-length {JUMBO_PACKET_LEN}")
        cmds.append(f"set send packet-length {JUMBO_PACKET_LEN}")
    return ", ".join(cmds)


@CLEAR_UNPREFIX_MODES
@pytest.mark.parametrize("direction", ["send", "get"])
@pytest.mark.parametrize("jumbo", [False, True], ids=["stdpkt", "jumbopkt"])
@pytest.mark.parametrize("slow_start", [False, True],
                        ids=["faststart", "slowstart"])
@pytest.mark.parametrize("streaming", [False, True],
                        ids=["nostream", "stream"])
@pytest.mark.parametrize("reliable", [False, True],
                        ids=["unreliable", "reliable"])
def test_kermit_transfer_protocol_options(
        tmp_path, wermit_loopback, direction, reliable, streaming,
        slow_start, jumbo):
    """
    Test binary file transfer across all combinations of SET
    RELIABLE, SET STREAMING, SET TRANSFER SLOW-START, and jumbo
    (9024-byte) packet length.  For each combination, one session
    transfers files at -1/exact/+1 bytes around the packet length
    relevant to that combination.  Each file is a separate
    transaction.
    """
    pkt_len = JUMBO_PACKET_LEN if jumbo else KERMIT_PACKET_LEN
    protocol_cmds = protocol_option_cmds(
        reliable, streaming, slow_start, jumbo)
    logger.info(
        "test_kermit_transfer_protocol_options: direction=%s %s",
        direction, protocol_cmds)
    run_transfers_in_one_session(
        tmp_path, wermit_loopback, direction,
        {f"protocol_opts_{size}.dat": pattern_bytes(size)
         for size in (pkt_len - 1, pkt_len, pkt_len + 1)},
        protocol_cmds=protocol_cmds)


@pytest.mark.parametrize("direction", ["send", "get"])
def test_kermit_transfer_text(tmp_path, wermit_loopback, direction):
    """
    Test text file transfer in both SEND and GET directions.
    """
    logger.info(
        "test_kermit_transfer_text: Starting test (direction=%s)", direction)
    text_content = "Line 1: Hello C-Kermit!\nLine 2: Testing text transfer.\n"
    run_transfer_helper(
        tmp_path,
        wermit_loopback,
        direction,
        file_type="text",
        file_name="text_file.txt",
        file_content=text_content,
        is_text=True
    )
    logger.info(
        "test_kermit_transfer_text: Test passed (direction=%s)", direction)


@pytest.mark.parametrize("direction", ["send", "get"])
def test_kermit_transfer_empty(tmp_path, wermit_loopback, direction):
    """
    Test empty (0-byte) file transfer in both SEND and GET directions.
    """
    logger.info(
        "test_kermit_transfer_empty: Starting test (direction=%s)", direction)
    run_transfer_helper(
        tmp_path,
        wermit_loopback,
        direction,
        file_type="binary",
        file_name="empty_file.dat",
        file_content=b"",
        is_text=False
    )
    logger.info(
        "test_kermit_transfer_empty: Test passed (direction=%s)", direction)


def test_kermit_transfer_recursive(tmp_path, wermit_loopback):
    """
    Test recursive file transfer (SEND /RECURSIVE).
    Verifies that nested files and subdirectories are correctly recreated
    on the server, but completely empty directories are skipped.
    GET /RECURSIVE is covered separately in
    test_permissions.py:test_get_recursive_descends_into_subdirectories.
    """
    logger.info("test_kermit_transfer_recursive: Starting test")
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    (client_dir / "file1.txt").write_text("file1 content")

    subdir = client_dir / "nested_subdir"
    subdir.mkdir()
    (subdir / "file2.txt").write_text("file2 content")

    # Add an empty directory
    empty_subdir = client_dir / "empty_subdir"
    empty_subdir.mkdir()

    server_dir = tmp_path / "server"
    server_dir.mkdir()

    logger.info(
        "test_kermit_transfer_recursive: Running client to "
        "recursively send *")
    result = wermit_loopback(
        server_dir,
        "set file type binary, set delay 0",
        f"set file type binary, set delay 0, cd {client_dir}, send /recursive *")
    assert_ok(result)

    # Verify received files and contents
    logger.info(
        "test_kermit_transfer_recursive: Verifying directory structure "
        "and files...")
    dest_file1 = server_dir / "file1.txt"
    dest_file2 = server_dir / "nested_subdir" / "file2.txt"
    dest_empty_dir = server_dir / "empty_subdir"

    assert dest_file1.exists()
    assert dest_file1.read_text() == "file1 content"

    assert dest_file2.exists()
    assert dest_file2.read_text() == "file2 content"

    # Verify empty folder does NOT exist (Kermit protocol limitation)
    assert not dest_empty_dir.exists()

    # Verify that ONLY the expected files and folders exist on the destination
    expected_paths = {
        Path("file1.txt"),
        Path("nested_subdir"),
        Path("nested_subdir/file2.txt"),
    }
    actual_paths = {p.relative_to(server_dir) for p in server_dir.rglob("*")}
    assert actual_paths == expected_paths


@pytest.mark.parametrize("direction", ["send", "get"])
def test_kermit_transfer_preserves_mtime(tmp_path, wermit_loopback, direction):
    """
    Test that file transfer preserves the last modified timestamp.
    On platforms that track timestamps with sub-second precision, the test
    should check with second-level precision.
    """
    logger.info("test_kermit_transfer_preserves_mtime: Starting test "
                "(direction=%s)", direction)
    client_dir, server_dir = make_loopback_dirs(
        tmp_path, f"client_{direction}_mtime", f"server_{direction}_mtime")
    file_name = "mtime_test.txt"
    src_file, dest_file = resolve_transfer_paths(
        client_dir, server_dir, direction, file_name)

    src_file.write_text("Hello, this is a timestamp preservation test.")

    # Define a target timestamp with sub-second precision:
    # 1700000000.5678 (Sun Nov 14 22:13:20 2023 UTC)
    target_mtime = 1700000000.5678

    # Set both atime and mtime on the source file
    os.utime(src_file, (target_mtime, target_mtime))

    # Double check that the OS actually set it (at least to second-level
    # precision)
    src_stat = src_file.stat()
    set_mtime = src_stat.st_mtime
    logger.info("test_kermit_transfer_preserves_mtime: Source file mtime "
                "set to: %f", set_mtime)
    assert int(set_mtime) == 1700000000

    if direction == "send":
        logger.info("test_kermit_transfer_preserves_mtime: Running client "
                    "to SEND file %s", src_file)
        client_cmd = f"set file type binary, set delay 0, send {src_file}"
    else:
        logger.info("test_kermit_transfer_preserves_mtime: Running client "
                    "to GET file %s", file_name)
        client_cmd = (f"set file type binary, set delay 0, "
                      f"cd {client_dir}, get {file_name}")

    result = wermit_loopback(server_dir, "set file type binary, set delay 0",
                             client_cmd)

    assert_ok(result)

    logger.info(
        "test_kermit_transfer_preserves_mtime: Verifying dest file %s",
        dest_file)
    assert dest_file.exists()

    # Verify that the content matches
    assert dest_file.read_text() == "Hello, this is a timestamp preservation test."

    # Verify the last modified timestamp is preserved to the second.
    # Accepts both sub-second precision being preserved and it being
    # lost/rounded.
    dest_mtime = dest_file.stat().st_mtime
    logger.info("test_kermit_transfer_preserves_mtime: Destination file "
                "mtime is %f. Difference: %f",
                dest_mtime, abs(dest_mtime - set_mtime))
    assert abs(dest_mtime - set_mtime) <= 1.0


def _sigwinch_bombardment(target_proc):
    """
    Starts a daemon thread that repeatedly sends SIGWINCH to target_proc, and
    returns (thread, stop_event). Waits 0.3s before the first signal, so callers
    testing mid-transfer interruption aren't likely to be running
    accept() or connect().

    The 50us interval is deliberate.  write() to a loopback socket rarely blocks
    long enough for a signal to land mid-syscall, unlike read() waiting on data
    from the peer, so reliably catching the write side needs a much tighter
    interval than the read side alone would. Going tighter still (such as a bare
    busy loop with no wait() at all) stops helping and instead starves the
    target process of enough CPU time to make progress at all, timing the whole
    test out on pure signal-handling overhead rather than exercising anything
    EINTR-related.

    Caller must, once done, set() the returned event and join() the thread (a
    finally block is a natural place for both).
    """
    stop = threading.Event()

    def bombard():
        stop.wait(0.3)
        while not stop.is_set():
            try:
                target_proc.send_signal(signal.SIGWINCH)
            except (ProcessLookupError, OSError):
                break
            stop.wait(0.00005)

    thread = threading.Thread(target=bombard, daemon=True)
    thread.start()
    return thread, stop


def test_transfer_survives_server_sigwinch(server_dir, wermit_tcp_loopback,
                                           tmp_path):
    """
    Regression test for a bug in ttinl().  A signal interrupting the blocking
    read for a new packet (eg, arriving at a packet boundary) was treated as a
    connection failure and caused the connection to be closed, instead of
    retrying the read the way EINTR should be handled. In practice, this showed
    up as SIGWINCH from a resized controlling terminal killing an in-progress
    transfer.  It doesn't depend on window resizing specifically, just some
    signal arriving at the wrong moment, so any repeated signal reproduces it.

    Sends SIGWINCH to the server throughout a transfer over a TCP connection and
    confirms the transfer still completes correctly.  direction is "send"
    (client sends, server receives) so the server is the one doing the heavy
    reading this exercises; see test_transfer_survives_server_write_ sigwinch
    for the equivalent write-side bug.
    """
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    content = pattern_bytes(2 * MB)
    src_file = client_dir / "sigwinch.dat"
    src_file.write_bytes(content)

    session = wermit_tcp_loopback(
        server_dir, protocol="raw-socket",
        setup_cmds="set file type binary, set delay 0")

    bombarder, stop = _sigwinch_bombardment(session.server_proc)
    try:
        result = session.run_client(
            f"set file type binary, set delay 0, send {src_file}",
            protocol="raw-socket", timeout=30)
    finally:
        stop.set()
        bombarder.join(timeout=scaled(2))
    session.wait_for_server_exit()

    assert_ok(result)
    dest_file = server_dir / "sigwinch.dat"
    assert dest_file.exists()
    assert dest_file.read_bytes() == content


# Number of times test_transfer_survives_server_write_sigwinch retries
# before failing.
#
# Signal delivery during a fast loopback write is timing-dependent. Under
# heavy load, an occasional attempt can fail due to timing jitter. Retrying
# avoids false failures while still detecting real regressions.
WRITE_SIGWINCH_ATTEMPTS = 3


def _attempt_write_sigwinch_transfer(server_dir, wermit_tcp_loopback,
                                     tmp_path, attempt):
    """
    Run one file transfer attempt under SIGWINCH bombardment.

    Return (True, None) on success, or (False, detail) with a failure
    description.
    """
    content = pattern_bytes(2 * MB)
    src_file = server_dir / "sigwinch_write.dat"
    src_file.write_bytes(content)
    client_dir = tmp_path / f"client_{attempt}"
    client_dir.mkdir()
    debug_log = tmp_path / f"server_debug_{attempt}.log"

    session = wermit_tcp_loopback(
        server_dir, protocol="raw-socket",
        setup_cmds=f"log debug {debug_log}, "
                   "set file type binary, set delay 0")

    bombarder, stop = _sigwinch_bombardment(session.server_proc)
    try:
        result = session.run_client(
            f"set file type binary, set delay 0, cd {client_dir}, "
            "get sigwinch_write.dat",
            protocol="raw-socket", timeout=30)
    finally:
        stop.set()
        bombarder.join(timeout=scaled(2))
        # The debug log only exists to slow down the server. Remove it to
        # avoid leaving large files on disk.
        debug_log.unlink(missing_ok=True)
    session.wait_for_server_exit()

    if result.returncode != 0:
        return False, (
            f"Command failed: stdout={result.stdout}\n"
            f"stderr={result.stderr}")
    dest_file = client_dir / "sigwinch_write.dat"
    if not dest_file.exists():
        return False, f"{dest_file} was not created"
    if dest_file.read_bytes() != content:
        return False, f"{dest_file} content does not match the source"
    return True, None


@pytest.mark.slow
def test_transfer_survives_server_write_sigwinch(
        server_dir, wermit_tcp_loopback, tmp_path):
    """
    Regression test for the write-side counterpart of the bug
    test_transfer_survives_server_sigwinch documents.

    Unlike that test, plain signal bombardment against a fast loopback
    transfer rarely catches this condition. write() to a loopback socket
    rarely blocks long enough for a signal to land mid-syscall, so LOG DEBUG
    is enabled to slow the server down.

    Because signal timing varies under load, the test retries up to
    WRITE_SIGWINCH_ATTEMPTS times to distinguish intermittent timing misses
    from a real regression.
    """
    detail = None
    for attempt in range(WRITE_SIGWINCH_ATTEMPTS):
        ok, detail = _attempt_write_sigwinch_transfer(
            server_dir, wermit_tcp_loopback, tmp_path, attempt)
        if ok:
            return
        logger.info(
            "test_transfer_survives_server_write_sigwinch: attempt %d "
            "failed (%s), retrying", attempt + 1, detail)
    pytest.fail(
        "test_transfer_survives_server_write_sigwinch: failed on all "
        f"{WRITE_SIGWINCH_ATTEMPTS} attempts; last failure: {detail}")


@pytest.mark.parametrize("slash", ["/", ""], ids=["slash", "no-slash"])
def test_get_into_existing_directory(tmp_path, wermit_loopback, slash):
    """GET with an existing directory as the as-name stores the file there.

    The directory exists already, so GET must neither try to create it
    nor report an error.
    """
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "f.txt").write_text("hello\n")
    dest = client_dir / "existing"
    dest.mkdir()
    result = wermit_loopback(
        server_dir, "",
        f"cd {client_dir}, get f.txt {dest}{slash}, "
        "echo STATUS=[\\v(status)]",
        timeout=30)
    assert_ok(result)
    assert "STATUS=[0]" in result.stdout, result.stdout
    assert (dest / "f.txt").read_text() == "hello\n", result.stdout


def test_extended_get_after_too_long_name(tmp_path, wermit_loopback):
    """Verify an extended GET works after one fails as too long.

    GET /RECOVER /DELETE sends O-packets.  A name too long for a packet
    fails, and the next GET must not send that GET's O-packet items.
    """
    server = tmp_path / "server"
    client = tmp_path / "client"
    server.mkdir()
    client.mkdir()
    (server / "a.txt").write_bytes(b"hello\n")
    long_name = "x" * 9500
    result = wermit_loopback(
        server, "set delay 0",
        f"cd {client}, set delay 0, "
        f"get /recover /delete {long_name}, echo FIRST=\\v(status), "
        "get /recover /delete a.txt, echo SECOND=\\v(status)")
    assert "GET Packet Too Long" in result.stdout, result.stdout[-2000:]
    assert "SECOND=0" in result.stdout, result.stdout[-2000:]
    assert (client / "a.txt").read_bytes() == b"hello\n"
    assert not (server / "a.txt").exists()


def test_get_delete_refused_when_delete_disabled(tmp_path, wermit_loopback):
    """Verify every GET /DELETE form honors DISABLE DELETE on the server.

    GET /DELETE sends an H packet.  The /RECOVER forms send an Extended
    GET (O packet) with the delete option.  Each must be refused, and the
    file must stay on the server.  One session runs every form.
    """
    forms = ["/delete", "/recover /delete", "/recover /recursive /delete"]
    server = tmp_path / "server"
    client = tmp_path / "client"
    server.mkdir()
    client.mkdir()
    (server / "a.txt").write_bytes(b"hello\n")
    gets = ", ".join(f"get {switches} a.txt, echo STATUS{i}=\\v(status)"
                     for i, switches in enumerate(forms))
    result = wermit_loopback(
        server, "set delay 0\ndisable delete",
        f"cd {client}, set delay 0, {gets}")
    accepted = [switches for i, switches in enumerate(forms)
                if f"STATUS{i}=1" not in result.stdout]
    assert not accepted, (accepted, result.stdout[-2000:])
    assert result.stdout.count("Deleting files is disabled") == \
        len(forms), result.stdout[-2000:]
    assert (server / "a.txt").read_bytes() == b"hello\n"
    assert not (client / "a.txt").exists()


# Each case is (bytes sent, bytes received).
LANGUAGE_EXPANSION_CASES = [
    (b"x\xc4yzEND", b"xAeyzEND"),
    (b"x\xc4y\xc4zEND", b"xAeyAezEND"),
    (b"\xdfq\xd6", b"ssqOe"),
    (b"x\xc4\xc4\xc4yzEND", b"xAeAeAeyzEND"),
    (b"\xdf" * 5 + b"q", b"ss" * 5 + b"q"),
]


def test_language_expansion_keeps_every_byte(tmp_path, wermit_loopback):
    """Verify a receiver keeps every byte when translation expands one.

    With SET LANGUAGE GERMAN and Latin-1 to ASCII translation, the
    receiver writes each umlaut as two letters.  The bytes after it in
    the packet must all reach the file.  A repeated umlaut, sent with a
    repeat prefix, becomes the pair repeated.  One session sends one
    file per case.
    """
    server = tmp_path / "server"
    client = tmp_path / "client"
    server.mkdir()
    client.mkdir()
    for i, (sent, _) in enumerate(LANGUAGE_EXPANSION_CASES):
        (client / f"u{i}.txt").write_bytes(sent)
    sends = ", ".join(f"send /text {client / f'u{i}.txt'}"
                      for i in range(len(LANGUAGE_EXPANSION_CASES)))
    result = wermit_loopback(
        server,
        "set delay 0\nset language german\nset file character-set ascii",
        "set delay 0, set file character-set latin1, "
        f"set transfer character-set latin1, {sends}")
    bad = []
    for i, (sent, received) in enumerate(LANGUAGE_EXPANSION_CASES):
        dest = server / f"u{i}.txt"
        got = dest.read_bytes() if dest.exists() else None
        if got != received:
            bad.append((sent, received, got))
    assert not bad, (bad, result.stdout[-2000:])
    assert_ok(result)


def test_send_init_shortened_after_full_one(tmp_path, wermit_loopback):
    """Verify a shortened Send-Init holds no parameters from an earlier one.

    The first SEND uses the full parameter list.  SET SEND
    NEGOTIATION-STRING-MAX-LENGTH then limits each later one.  The
    limits fall, so each S packet follows a longer one.  Each must end
    at its limit.  That gives limit + 1 parameter bytes.
    """
    limits = [17, 16, 12, 10, 9]
    server = tmp_path / "server"
    client = tmp_path / "client"
    server.mkdir()
    client.mkdir()
    (client / "a.txt").write_bytes(b"hello\n")
    plog = tmp_path / "p.log"
    sends = ", ".join(
        f"set send negotiation-string-max-length {limit}, "
        f"send {client / 'a.txt'}, echo STATUS{limit}=\\v(status)"
        for limit in limits)
    result = wermit_loopback(
        server, "set delay 0, set file collision overwrite",
        f"set delay 0, log packets {plog}, send {client / 'a.txt'}, "
        f"{sends}")
    failed = [limit for limit in limits
              if f"STATUS{limit}=0" not in result.stdout]
    assert not failed, (failed, result.stdout[-2000:])
    # Entries look like "s-00-00-^A" followed by LEN, SEQ, TYPE, data
    # and a 1-byte block check.
    inits = [line[10:] for line in
             plog.read_text(errors="replace").splitlines()
             if line.startswith("s-") and line[12:13] == "S"]
    assert len(inits) == len(limits) + 1, inits
    full = inits[0][3:3 + ord(inits[0][0]) - 32 - 3]
    bad = []
    for limit, init in zip(limits, inits[1:]):
        data = init[3:3 + ord(init[0]) - 32 - 3]
        if data != full[:limit + 1]:
            bad.append((limit, data))
    assert not bad, (bad, full)


def test_shortened_send_init_keeps_settings(tmp_path, wermit_loopback):
    """Verify a shortened Send-Init leaves the user settings unchanged.

    A limit of 8 leaves out CAPAS.  That transfer sends no Attribute
    packet.  A limit of 10 leaves out the extended packet length.  The
    SEND after each one runs with no limit.  Its Send-Init matches the
    first one.  SHOW then reports the settings as SET.
    """
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (client_dir / "a.txt").write_bytes(b"hello\n")
    plog = tmp_path / "p.log"
    send = f"send {client_dir / 'a.txt'}"
    result = wermit_loopback(
        server_dir, "set delay 0, set file collision overwrite",
        f"set delay 0, set window 8, set attributes on, "
        f"log packets {plog}, {send}, "
        f"set send negotiation-string-max-length 8, {send}, "
        f"set send negotiation-string-max-length 0, {send}, "
        f"set send negotiation-string-max-length 10, {send}, "
        f"set send negotiation-string-max-length 0, {send}, "
        "close, show attributes, show protocol")
    assert_ok(result)
    # Entries look like "s-00-00-^A" followed by LEN, SEQ, TYPE and
    # data.  Split the sent packets into one list per transaction.
    transactions = []
    for line in plog.read_text(errors="replace").splitlines():
        if not line.startswith("s-") or len(line) < 13:
            continue
        if line[12] == "S":
            transactions.append([])
        if transactions:
            transactions[-1].append(line[10:])
    assert len(transactions) == 5, transactions
    inits = [t[0] for t in transactions]
    assert inits[2] == inits[0], inits
    assert inits[4] == inits[0], inits
    types = [[pkt[2] for pkt in t] for t in transactions]
    assert "A" not in types[1], types
    assert "A" in types[2], types
    assert re.search(r"^ *Attributes: on", result.stdout, re.M), \
        result.stdout
    assert re.search(r"Window Size:\s+8 set", result.stdout), result.stdout


def test_transaction_log_names_collision_keyword(tmp_path, wermit_loopback):
    """Verify the transaction log names the SET FILE COLLISION keyword.

    rinit() logs the keyword at the start of each receive.  One session
    runs a GET under each keyword.
    """
    keywords = ["reject", "overwrite", "backup"]
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "c.txt").write_bytes(b"new\n")
    tlog = tmp_path / "t.log"
    gets = ", ".join(f"set file collision {keyword}, get c.txt"
                     for keyword in keywords)
    wermit_loopback(
        server_dir, "set delay 0",
        f"set delay 0, cd {client_dir}, log transactions {tlog}, {gets}")
    logged = re.findall(r"Collision action: (\S+)", tlog.read_text())
    assert logged == keywords, tlog.read_text()


@pytest.mark.parametrize("settings", [
    "set window 1, set streaming off",
    "set window 32, set streaming off",
    "set window 32, set streaming on",
], ids=["window1", "window32", "window32-streaming"])
def test_send_packets_fit_small_send_buffer(tmp_path, wermit_loopback,
                                            settings):
    """Verify sent packets fit a send buffer set smaller than a packet.

    The receiver allows 9024-byte packets.  The sender has a 5000-byte
    send buffer and no slow start, so spar() must cut the packet length
    to fit one packet, or a windowful, in that buffer.  Packets past the
    buffer show under AddressSanitizer.
    """
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    # The file fills the send buffer several times over.  It stays well
    # under kern.tty.qsize (65536 in CI).  The NetBSD pty drops bytes
    # from a write that meets a full queue.  A streaming sender can
    # queue the whole file before a slow receiver reads it.
    data = os.urandom(30000)
    (client_dir / "big.bin").write_bytes(data)
    result = wermit_loopback(
        server_dir,
        server_setup_cmds="set window 32, set receive packet-length 9024",
        client_commands=f"cd {client_dir}, set buffers 5000 2000, "
        f"set transfer slow-start off, {settings}, send big.bin, "
        "echo STATUS=\\v(status)")
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "AddressSanitizer" not in result.stderr, result.stderr[:3000]
    assert "STATUS=0" in result.stdout, result.stdout
    assert (server_dir / "big.bin").read_bytes() == data

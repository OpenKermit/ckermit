import os
import signal
import threading
import pytest
from pathlib import Path
import logging
from conftest import (assert_ok, make_loopback_dirs, pattern_bytes,
                      resolve_transfer_paths)

logger = logging.getLogger(__name__)


@pytest.fixture(params=["pseudoterminal", "raw-socket", "telnet", "ssl"])
def loopback_transport(request):
    """Overrides conftest's single-value default so every test in
    this module runs over pty, TCP raw, TCP telnet, and SSL."""
    return request.param


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


@pytest.mark.parametrize("direction", ["send", "get"])
@pytest.mark.parametrize("size", [
    pytest.param(1024, id="1024B"),
    pytest.param(KERMIT_PACKET_LEN - 1, id="pktlen-1"),
    pytest.param(KERMIT_PACKET_LEN, id="pktlen"),
    pytest.param(KERMIT_PACKET_LEN + 1, id="pktlen+1"),
    pytest.param(2 * KERMIT_PACKET_LEN - 1, id="2xpktlen-1"),
    pytest.param(2 * KERMIT_PACKET_LEN, id="2xpktlen"),
    pytest.param(2 * KERMIT_PACKET_LEN + 1, id="2xpktlen+1"),
])
def test_kermit_transfer_binary(tmp_path, wermit_loopback, direction, size):
    """
    Test binary file transfer in both SEND and GET directions, for a
    range of file sizes: 1K and sizes at and
    around exact multiples of KERMIT_PACKET_LEN to test for boundary bugs.
    Verifies that files are byte-identical.

    Passed tmp_path and the wermit_loopback _setup function, as well as the
    parameterized direction and size.
    """
    logger.info(
        "test_kermit_transfer_binary: Starting test (direction=%s, size=%d)",
        direction, size)
    run_transfer_helper(
        tmp_path,
        wermit_loopback,
        direction,
        file_type="binary",
        file_name="binary_file.dat",
        file_content=pattern_bytes(size),
        is_text=False
    )
    logger.info(
        "test_kermit_transfer_binary: Test passed (direction=%s, size=%d)",
        direction, size)


@pytest.mark.parametrize("direction", ["send", "get"])
def test_kermit_transfer_large(tmp_path, wermit_loopback, direction):
    """
    Test binary file transfer of a file well beyond a single packet
    or window, in both SEND and GET directions.
    """
    size = 20 * MB
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
    runs once per other transport)."""
    content = pattern_bytes(2 * MB)
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    src_file = client_dir / "nul_replay.dat"
    src_file.write_bytes(content)
    debug_log = tmp_path / "server_debug.log"

    try:
        result = wermit_loopback(
            server_dir,
            server_setup_cmds=(
                f"log debug {debug_log}, set control unprefix all, "
                "set file type binary, set delay 0"
            ),
            client_commands=(
                "set control unprefix all, set file type binary, "
                f"set delay 0, send {src_file}"
            ),
            timeout=30,
        )
        assert_ok(result)

        dest_file = server_dir / "nul_replay.dat"
        assert dest_file.exists()
        assert dest_file.read_bytes() == content
    finally:
        # The debug log only exists to slow the server down (see
        # docstring); it is not surfaced on failure the way
        # KERMIT_TEST_DEBUG_LOOPBACK's logs are, so there is no reason
        # to keep it around. It can be tens of MB per attempt.
        debug_log.unlink(missing_ok=True)


@pytest.mark.parametrize("loopback_transport", ["pseudoterminal"],
                         indirect=True)
@pytest.mark.parametrize("attempt", range(5))
def test_kermit_transfer_unprefixed_nul_replay(tmp_path, wermit_loopback,
                                               attempt, loopback_transport):
    """
    Regression test for the data-corruption bug fixed in b58e0336.

    Hitting that replay path requires a packet to actually arrive out
    of order, which is normally timing-dependent. Enabling LOG DEBUG on
    the server only (not the client) slows the receiving side enough,
    relative to the sender, to make that happen some of the time,
    without any external system load.

    LOG DEBUG output is the limiting factor on the file size.
    It inflates roughly 30x over the bytes transferred, so a larger
    file catches the race more often but also risks filling a
    tmpfs-backed /tmp.  2 MB keeps that peak well under 1 GB.
    the pre-fix code on NetBSD (where this bug was originally found),
    this catches the corruption in roughly a third of runs of the
    full parametrized set; it is not expected to catch it every time.

    Restricted to the pseudoterminal transport. The race comes from
    LOG DEBUG slowing the server relative to the client, not from
    transport choice, so sweeping all five attempts over
    raw-socket/telnet/SSL too would multiply cost without improving
    the odds of catching it. See
    test_kermit_transfer_unprefixed_nul_replay_transport_smoke for a
    single-attempt check that this same path also runs cleanly over
    the other transports.
    """
    _run_nul_replay_transfer(tmp_path, wermit_loopback)


@pytest.mark.parametrize("loopback_transport",
                         ["raw-socket", "telnet", "ssl"], indirect=True)
def test_kermit_transfer_unprefixed_nul_replay_transport_smoke(
        tmp_path, wermit_loopback, loopback_transport):
    """
    To save time, just one attempt per transport rather than 5.
    The race itself does not depend on transport choice.
    """
    _run_nul_replay_transfer(tmp_path, wermit_loopback)


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
    (9024-byte) packet length. For each combination, transfers files
    at -1/exact/+1 bytes around the packet length relevant to that
    combination.
    """
    pkt_len = JUMBO_PACKET_LEN if jumbo else KERMIT_PACKET_LEN
    protocol_cmds = protocol_option_cmds(
        reliable, streaming, slow_start, jumbo)
    logger.info(
        "test_kermit_transfer_protocol_options: direction=%s %s",
        direction, protocol_cmds)
    for size in (pkt_len - 1, pkt_len, pkt_len + 1):
        run_transfer_helper(
            tmp_path,
            wermit_loopback,
            direction,
            file_type="binary",
            file_name=f"protocol_opts_{size}.dat",
            file_content=pattern_bytes(size),
            is_text=False,
            protocol_cmds=protocol_cmds,
        )


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
    GET /RECURSIVE is not tested as recursive GET is not supported by the
    Kermit protocol.
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
        bombarder.join(timeout=2)
    session.wait_for_server_exit()

    assert_ok(result)
    dest_file = server_dir / "sigwinch.dat"
    assert dest_file.exists()
    assert dest_file.read_bytes() == content


def test_transfer_survives_server_write_sigwinch(
        server_dir, wermit_tcp_loopback, tmp_path):
    """
    Regression test for the write-side counterpart of the bug
    test_transfer_survives_server_sigwinch documents.

    Unlike that test, plain signal bombardment against a fast loopback transfer
    essentially never catches this one.  write() to a loopback socket rarely
    blocks long enough for a signal to land mid-syscall, so this needs LOG DEBUG
    to slow the server down the same way
    test_kermit_transfer_unprefixed_nul_replay does (see its docstring). Even so
    this isn't expected to catch it on every run.
    """
    content = pattern_bytes(2 * MB)
    src_file = server_dir / "sigwinch_write.dat"
    src_file.write_bytes(content)
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    debug_log = tmp_path / "server_debug.log"

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
        bombarder.join(timeout=2)
        # Only exists to slow the server down (see docstring); can be
        # tens of MB, and isn't surfaced on failure like
        # KERMIT_TEST_DEBUG_LOOPBACK's own logs are.
        debug_log.unlink(missing_ok=True)
    session.wait_for_server_exit()

    assert_ok(result)
    dest_file = client_dir / "sigwinch_write.dat"
    assert dest_file.exists()
    assert dest_file.read_bytes() == content

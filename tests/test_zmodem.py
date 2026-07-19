import os
import shutil
import subprocess

import pytest

from conftest import (pattern_bytes, DEBUG_LOOPBACK as DEBUG_ZMODEM,
                      ZMODEM_QUIET_PROTOCOL_CLAUSE, TCP_TIMEOUT_MARGIN,
                      ssl_server_setup_cmds, ssl_client_setup_cmds,
                      start_wermit_pty, finish_wermit_pty,
                      finish_wermit_pty_pair,
                      _wait_for_pty_marker, PORT_COLLISION_RETRIES,
                      PORT_BIND_FAILURE_MARKER)

ZMODEM_BLOCK_SIZE = 1024

MB = 1024 * 1024

pytestmark = pytest.mark.skipif(
    shutil.which("sz") is None or shutil.which("rz") is None,
    reason="lrzsz (sz/rz) commands not available",
)


def run_zmodem_receive(zmodem_remote, tmp_path, content, timeout=45):
    """
    Runs kermit as a Zmodem receiver (kermit's stdin connected to a
    pty hosting sz), which reads content from a source file and
    writes it to dest_dir/test_z_receive.txt. Asserts the transfer
    succeeded, the received file is byte-identical, and its mtime was
    preserved to the second.
    """
    # Setup source directory and file
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    src_file = src_dir / "test_z_receive.txt"
    src_file.write_bytes(content)

    # Set modification time with sub-second precision
    target_mtime = 1700000000.5678
    os.utime(src_file, (target_mtime, target_mtime))

    # Setup dest directory where wermit will run and receive the file
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    # Receive command: wermit connects to a remote hosting sz -- either
    # directly via a pseudoterminal, or over raw TCP, depending on
    # zmodem_remote's mode.
    cmd_str = (f"{ZMODEM_QUIET_PROTOCOL_CLAUSE}, "
              "set terminal autodownload on, set host {HOST}, connect, "
              "close, exit")

    if zmodem_remote.mode == "tcp":
        timeout += TCP_TIMEOUT_MARGIN
    debug_log = tmp_path / "wermit_debug.log" if DEBUG_ZMODEM else None
    returncode, stdout = zmodem_remote(
        ["sz", str(src_file)], cmd_str, dest_dir, timeout=timeout,
        debug_log=debug_log)

    assert returncode == 0, f"Zmodem receive failed: returncode={returncode}, stdout={stdout}"

    received_file = dest_dir / "test_z_receive.txt"
    assert received_file.exists(
    ), f"Received file not found in {dest_dir}. stdout={stdout}"
    assert received_file.read_bytes() == content

    # Verify modification time is preserved to the second
    dest_mtime = received_file.stat().st_mtime
    assert abs(dest_mtime - target_mtime) <= 1.0


def run_zmodem_send(zmodem_remote, tmp_path, content, timeout=45):
    """
    Runs wermit as a Zmodem sender (wermit's stdin connected to a pty
    hosting rz), which sends a source file's content and rz writes it
    to dest_dir/test_z_send.txt. Asserts the transfer succeeded, the
    received file is byte-identical, and its mtime was preserved to
    the second.
    """
    # Setup source file to send
    src_file = tmp_path / "test_z_send.txt"
    src_file.write_bytes(content)

    # Set modification time with sub-second precision
    target_mtime = 1700000000.5678
    os.utime(src_file, (target_mtime, target_mtime))

    # Setup dest directory where rz will run and write the file
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    # Send command: wermit sets protocol to zmodem, hosts rz -- either
    # directly via a pseudoterminal, or over raw TCP, depending on
    # zmodem_remote's mode -- and sends the file.
    cmd_str = (f"{ZMODEM_QUIET_PROTOCOL_CLAUSE}, "
              f"set host {{HOST}}, send {src_file}, close, exit")

    if zmodem_remote.mode == "tcp":
        timeout += TCP_TIMEOUT_MARGIN
    debug_log = tmp_path / "wermit_debug.log" if DEBUG_ZMODEM else None
    returncode, stdout = zmodem_remote(
        ["rz"], cmd_str, dest_dir, timeout=timeout, debug_log=debug_log)

    assert returncode == 0, f"Zmodem send failed: returncode={returncode}, stdout={stdout}"

    received_file = dest_dir / "test_z_send.txt"
    assert received_file.exists(
    ), f"Sent file not found in {dest_dir}. stdout={stdout}"
    assert received_file.read_bytes() == content

    # Verify modification time is preserved to the second
    dest_mtime = received_file.stat().st_mtime
    assert abs(dest_mtime - target_mtime) <= 1.0


def test_zmodem_receive(zmodem_remote, tmp_path):
    """content spans every byte value 0x00-0xFF, including bytes that
    Telnet's NVT layer treats specially (CR, and the byte immediately
    following a "bare" CR), so a "tcp-telnet" zmodem_remote instance
    that mishandles that framing corrupts the transfer instead of
    just passing."""
    content = pattern_bytes(2000)
    run_zmodem_receive(zmodem_remote, tmp_path, content)


def test_zmodem_send(zmodem_remote, tmp_path):
    """See test_zmodem_receive for why content covers the full byte
    range."""
    content = pattern_bytes(2000)
    run_zmodem_send(zmodem_remote, tmp_path, content)


ZMODEM_SIZES = [
    pytest.param(ZMODEM_BLOCK_SIZE - 1, id="blksize-1"),
    pytest.param(ZMODEM_BLOCK_SIZE, id="blksize"),
    pytest.param(ZMODEM_BLOCK_SIZE + 1, id="blksize+1"),
    pytest.param(2 * ZMODEM_BLOCK_SIZE - 1, id="2xblksize-1"),
    pytest.param(2 * ZMODEM_BLOCK_SIZE, id="2xblksize"),
    pytest.param(2 * ZMODEM_BLOCK_SIZE + 1, id="2xblksize+1"),
]


@pytest.mark.parametrize("size", ZMODEM_SIZES)
def test_zmodem_receive_sizes(zmodem_remote, tmp_path, size):
    """
    Zmodem receive at and around exact multiples of
    ZMODEM_BLOCK_SIZE, to exercise sub-packet count/boundary
    arithmetic.
    """
    run_zmodem_receive(zmodem_remote, tmp_path, pattern_bytes(size))


@pytest.mark.parametrize("size", ZMODEM_SIZES)
def test_zmodem_send_sizes(zmodem_remote, tmp_path, size):
    """
    Zmodem send at and around exact multiples of ZMODEM_BLOCK_SIZE,
    to exercise sub-packet count/boundary arithmetic.
    """
    run_zmodem_send(zmodem_remote, tmp_path, pattern_bytes(size))


pytestmark_ssl = pytest.mark.skipif(
    shutil.which("openssl") is None,
    reason="openssl CLI not found on PATH"
)


def _run_ssl_zmodem(wermit_path, get_free_port, ssl_pki,
                     server_dir, remote_dir, remote_argv, timeout=60):
    """
    Runs a Zmodem transfer over a loopback /SSL connection, with the
    wermit-under-test in CONNECT mode (autodownload).  This is the same code
    path a human typing "connect" and letting the far end's Zmodem trigger
    auto-detection would exercise.

    The remote also runs on a pty (unlike zmodem_remote's plain spawn_wermit,
    which gives it none): over /SSL specifically, a remote with no controlling
    tty at all exits its own SEND/RECEIVE command almost instantly without
    transferring anything and without signaling an error, instead of the
    graceful tcgetattr()-failure fallback ttptycmd() otherwise has for a non-tty
    console.

    remote_argv is the rz/sz-equivalent command as a list (e.g.  ["sz",
    str(src_file)] or ["rz"]); the remote runs the matching SET PROTOCOL ZMODEM
    SEND/RECEIVE clause over its own /SSL connection to the wermit under test.
    Returns (returncode, stdout).
    """
    remote_clause = (f"send {remote_argv[1]}" if remote_argv[0] == "sz"
                      else "receive")

    for attempt in range(PORT_COLLISION_RETRIES):
        port = get_free_port()
        server_cmd = (
            "set tcp reverse-dns-lookup off, "
            f"{ssl_server_setup_cmds(ssl_pki)}, "
            f"set host * {port} /ssl, "
            "set terminal autodownload on, "
            f"{ZMODEM_QUIET_PROTOCOL_CLAUSE}, "
            "connect, close, exit"
        )
        proc, master = start_wermit_pty(wermit_path, server_cmd,
                                         str(server_dir))
        prefix, ready = _wait_for_pty_marker(
            master, b"Waiting to Accept", timeout=10)
        if ready:
            break

        bind_failed = PORT_BIND_FAILURE_MARKER.encode() in prefix
        os.close(master)
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except (subprocess.TimeoutExpired, OSError):
            proc.kill()
            proc.wait(timeout=2)
        if not bind_failed or attempt == PORT_COLLISION_RETRIES - 1:
            raise RuntimeError(
                "_run_ssl_zmodem: wermit-under-test did not start "
                "listening; pty output:\n"
                f"{prefix.decode('utf-8', errors='replace')}")

    remote_cmd = (
        "set tcp reverse-dns-lookup off, "
        f"{ssl_client_setup_cmds(ssl_pki)}, "
        f"set host localhost {port} /ssl, "
        f"{ZMODEM_QUIET_PROTOCOL_CLAUSE}, "
        f"{remote_clause}, close, exit"
    )
    rproc, rmaster = start_wermit_pty(wermit_path, remote_cmd,
                                       str(remote_dir))

    # Drain both sides concurrently. Both now have real ptys (unlike
    # zmodem_remote's remote, which uses spawn_wermit's /dev/null
    # stdout instead), and both need a reader for the duration.
    (_, _), (returncode, stdout) = finish_wermit_pty_pair(
        rproc, rmaster, proc, master, timeout=timeout)
    return returncode, prefix.decode("utf-8", errors="replace") + stdout


@pytestmark_ssl
def test_zmodem_receive_ssl_binary(wermit_path, get_free_port, ssl_pki,
                                    tmp_path):
    """
    Regression test for two bugs in ttptycmd() that only show up together.  Test
    with an active SSL/TLS connection, and file content spanning the full
    0x00-0xFF byte range.

    Bug 1 (hang): in_chk() sizes each network read for SSL/TLS using
    SSL_pending(), which reads 0 for every new incoming TLS record until
    something from it has been decrypted, even when a whole record's worth of
    ciphertext is already waiting. ttptycmd() bumped that 0 to 1, capping every
    read to a single byte for the life of the connection. That's slow enough to
    to time out Zmodem. Fixed by offering the whole remaining buffer instead,
    relying on ttinc()'s fast path (see its "my_count > 0" check) to make the
    extra loop iterations cheap.

    Bug 2 (corruption): separately, whenever Telnet's NVT rules insert a NULL
    after a "bare" CR (a CR not immediately followed by LF, with Telnet BINARY
    mode not negotiated), the send-side loop reused the same variable to both
    write the inserted NUL and, two lines later, copy the real byte that follows
    the CR.  Reassigning that variable to 0x00 for the NULL clobbered the real
    byte before the copy ran, so the byte after any bare CR was silently
    replaced by a second NULL.  A 20-byte multiple of ZMODEM_BLOCK_SIZE is used
    specifically so some sub-packet boundary lands right after a CR byte, since
    pattern_bytes() repeats every 256 bytes.

    Only the receive direction is exercised here, not send-and-receive both: the
    remote end of this same transfer runs sz, so it drives ttptycmd()'s
    send-side (escaping) code exactly as much as a dedicated send test would, on
    the same wermit binary. A separate "send" variant would mostly retest the
    same code with the roles swapped, at the cost of needing a second real pty
    (CONNECT mode's autodownload, unlike direct SET PROTOCOL ZMODEM
    SEND/RECEIVE, only triggers on the receiving end).
    """
    size = 5 * ZMODEM_BLOCK_SIZE + 1
    content = pattern_bytes(size)

    remote_dir = tmp_path / "remote"
    remote_dir.mkdir()
    src_file = remote_dir / "test_z_receive.txt"
    src_file.write_bytes(content)

    server_dir = tmp_path / "dest"
    server_dir.mkdir()

    returncode, stdout = _run_ssl_zmodem(
        wermit_path, get_free_port, ssl_pki,
        server_dir, remote_dir, ["sz", str(src_file)])

    assert returncode == 0, f"Zmodem receive over SSL failed: stdout={stdout}"
    received_file = server_dir / "test_z_receive.txt"
    assert received_file.exists(), f"File not received. stdout={stdout}"
    assert received_file.read_bytes() == content


def test_zmodem_receive_large(zmodem_remote, tmp_path):
    """Zmodem receive of a file well beyond a single sub-packet."""
    run_zmodem_receive(
        zmodem_remote, tmp_path, pattern_bytes(20 * MB), timeout=90)


def test_zmodem_send_large(zmodem_remote, tmp_path):
    """Zmodem send of a file well beyond a single sub-packet."""
    run_zmodem_send(
        zmodem_remote, tmp_path, pattern_bytes(20 * MB), timeout=90)

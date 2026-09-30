"""
Tests for Telnet subnegotiation handling in ckctel.c.

Verifies that an unclosed subnegotiation (IAC SB without IAC SE) followed
by peer connection closure does not cause wermit to hang.
"""
import re
import socket
import subprocess
import threading

import pytest

IAC = 255
SB = 250

# Telnet option NEW-ENVIRON (RFC 1572), used for the subnegotiation payload.
TELOPT_NEW_ENVIRON = 39


def test_telnet_truncated_subnegotiation_no_hang(spawn_wermit, wermit_path):
    """Verify unclosed subnegotiation does not hang on peer disconnect."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    proc = spawn_wermit([
        "-H", "-Y", "-C",
        "set command more-prompting off, set delay 0, "
        f"set host 127.0.0.1 {port} /telnet, pause 5, close, exit",
    ])

    try:
        server_sock.settimeout(10)
        conn, _ = server_sock.accept()
        try:
            conn.settimeout(5)
            # Send an incomplete subnegotiation without a terminating IAC SE.
            conn.sendall(
                bytes([IAC, SB, TELOPT_NEW_ENVIRON,
                       ord('X'), ord('Y'), ord('Z')]))
        finally:
            conn.close()
    finally:
        server_sock.close()

    try:
        returncode = proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        pytest.fail(
            "wermit hung after a Telnet subnegotiation was left open "
            "(IAC SB with no closing IAC SE, then connection closed)"
        )

    # Peer disconnection is an error condition, so wermit may exit non-zero.
    # The assertion verifies that the process exited rather than hanging.
    assert returncode is not None


SE = 240
WILL, WONT, DO, DONT = 251, 252, 253, 254
TELOPT_TTYPE = 24
TELOPT_NAWS = 31
MARKER = b"MARKER-OK"


def _serve_once(payload):
    """Start a one-connection Telnet peer that sends payload.

    Sends payload followed by MARKER. Refuses all offered options to
    finish negotiation, then reads until the client closes. Returns
    (port, thread, listening socket).
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(15)

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(30)
            try:
                conn.sendall(payload + b"\r\n" + MARKER + b"\r\n")
                pending = b""
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    pending += data
                    i = 0
                    while i < len(pending):
                        if pending[i] != IAC:
                            i += 1
                        elif i + 2 >= len(pending):
                            break       # Incomplete; wait for more
                        elif pending[i + 1] in (WILL, DO):
                            reply = DONT if pending[i + 1] == WILL else WONT
                            conn.sendall(bytes([IAC, reply,
                                                pending[i + 2]]))
                            i += 3
                        else:
                            i += 2
                    pending = pending[i:]
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return srv.getsockname()[1], thread, srv


def _expect_marker_after(run_wermit, payload):
    """Verify wermit survives payload and then reads MARKER.

    Returns the received data as uppercase hex. INPUT echo is disabled
    because the payload can contain invalid UTF-8 bytes.
    """
    port, thread, srv = _serve_once(payload)
    try:
        result = run_wermit(
            "set delay 0, set input echo off, "
            f"set host 127.0.0.1 {port} /telnet, "
            f"input 10 {MARKER.decode()}, "
            "if success echo GOT-MARKER, "
            "echo HEX=[\\fhexify(\\v(input))], "
            "close, exit",
            timeout=30,
        )
    finally:
        srv.close()
        thread.join(timeout=5)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "GOT-MARKER" in result.stdout, result.stdout
    match = re.search(r"HEX=\[([0-9A-Fa-f]*)\]", result.stdout)
    assert match, result.stdout
    return match.group(1).upper()


def _sb(opt, data):
    """Return a subnegotiation packet for opt with data, quoting IAC."""
    return (bytes([IAC, SB, opt]) + data.replace(b"\xff", b"\xff\xff")
            + bytes([IAC, SE]))


# TSBUFSIZ is 1024, or 2056 with CK_FORWARD_X; cover both edges.
@pytest.mark.parametrize("length", [1022, 1023, 1024, 1025,
                                    2054, 2055, 2056, 2057, 5000])
def test_telnet_subnegotiation_boundary_lengths(run_wermit, length):
    """Verify a TTYPE subnegotiation near the buffer size is handled."""
    _expect_marker_after(run_wermit, _sb(TELOPT_TTYPE, b"A" * length))


@pytest.mark.parametrize("length", [1023, 1024, 2056, 5000])
def test_telnet_subnegotiation_quoted_iacs(run_wermit, length):
    """Verify quoted IAC bytes filling a subnegotiation are handled."""
    _expect_marker_after(run_wermit, _sb(TELOPT_TTYPE, b"\xff" * length))


@pytest.mark.parametrize("opt", [TELOPT_TTYPE, TELOPT_NAWS,
                                 TELOPT_NEW_ENVIRON])
def test_telnet_empty_subnegotiation(run_wermit, opt):
    """Verify a subnegotiation with no data bytes is handled."""
    _expect_marker_after(run_wermit, _sb(opt, b""))


@pytest.mark.parametrize("data", [
    b"\x00",
    b"\x00\x50\x00",
    b"\xff\xff\xff\xff",
    b"\x00\x50\x00\x18" + b"Z" * 3000,
], ids=["too-short", "one-short", "max-values", "trailing-data"])
def test_telnet_naws_odd_lengths(run_wermit, data):
    """Verify NAWS subnegotiations of the wrong length are handled."""
    _expect_marker_after(run_wermit, _sb(TELOPT_NAWS, data))


@pytest.mark.parametrize("data", [
    b"\x01",
    b"\x01\x00" + b"V" * 3000,
    b"\x01" + b"\x00USER\x01" * 400,
    b"\x00\x00" + b"N" * 1500 + b"\x01" + b"V" * 1500,
], ids=["send-empty", "send-long-name", "send-many-names", "is-long"])
def test_telnet_new_environ_long_data(run_wermit, data):
    """Verify long NEW-ENVIRON subnegotiations are handled."""
    _expect_marker_after(run_wermit, _sb(TELOPT_NEW_ENVIRON, data))


@pytest.mark.parametrize("length", [1022, 1023, 1024, 1025,
                                    2054, 2055, 2056, 2057])
def test_telnet_subnegotiation_no_stray_se(run_wermit, length):
    """Verify no byte of IAC SE reaches the data stream.

    At TSBUFSIZ - 1 data bytes, the payload and closing IAC fill
    the buffer. The trailing SE must still be consumed as part of the
    subnegotiation.
    """
    received = _expect_marker_after(run_wermit,
                                    _sb(TELOPT_TTYPE, b"A" * length))
    octets = [received[i:i + 2] for i in range(0, len(received), 2)]
    assert "F0" not in octets, received[:200]


def test_telnet_subnegotiation_bad_terminator(run_wermit):
    """Verify an invalid subnegotiation terminator ends negotiation.

    IAC followed by a non-SE byte ends the subnegotiation without
    dropping subsequent data.
    """
    payload = (bytes([IAC, SB, TELOPT_TTYPE]) + b"A" * 100
               + bytes([IAC, 1]))
    _expect_marker_after(run_wermit, payload)

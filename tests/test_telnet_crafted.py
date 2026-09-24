"""
Tests for Telnet subnegotiation handling in ckctel.c.

Verifies that an unclosed subnegotiation (IAC SB without IAC SE) followed
by peer connection closure does not cause wermit to hang.
"""
import socket
import subprocess

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

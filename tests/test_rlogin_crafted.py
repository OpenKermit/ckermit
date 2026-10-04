"""
Tests for the RLOGIN connection-startup data sent by rlog_ini().

A crafted server accepts the connection and records the startup
data: a NUL, then the local user, remote user, and terminal
type/speed, each terminated by a NUL.
"""
import os
import socket
import subprocess

import pytest

from conftest import assert_ok


def _rlogin_supported(run_wermit):
    result = run_wermit("help set host")
    assert_ok(result, "HELP SET HOST failed")
    return "/RLOGIN" in result.stdout


def _read_startup_data(conn):
    """Read until the fourth NUL, or until the client stops sending."""
    data = b""
    while data.count(b"\0") < 4:
        chunk = conn.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def test_rlogin_long_user_names_sent_intact(run_wermit, wermit_path):
    """Send 255-character local and remote user names in full.

    With SET LOGIN USERID empty, the remote user is the local user,
    taken from USER. Both are capped at 255 characters, and with the
    terminal type and speed the startup data exceeds 512 bytes.
    """
    if not _rlogin_supported(run_wermit):
        pytest.skip("build has no RLOGIN support (not RLOGCODE)")

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    env = dict(os.environ, USER="u" * 300, TERM="t" * 40)
    proc = subprocess.Popen(
        [wermit_path, "-H", "-Y", "-C",
         "set command more-prompting off, set login userid, "
         f"rlogin 127.0.0.1:{port}, exit"],
        env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, start_new_session=True)
    try:
        server_sock.settimeout(15)
        conn, _ = server_sock.accept()
        try:
            conn.settimeout(10)
            data = _read_startup_data(conn)
            conn.sendall(b"\0")
        finally:
            conn.close()
        out, _ = proc.communicate(timeout=15)
    finally:
        server_sock.close()
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    fields = data.split(b"\0")
    assert fields[0] == b"", data
    assert fields[1] == b"u" * 255, data
    assert fields[2] == b"u" * 255, data
    assert fields[3].startswith(b"t" * 15 + b"/"), data
    assert proc.returncode >= 0, out

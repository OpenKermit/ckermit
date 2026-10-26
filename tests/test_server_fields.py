"""Tests for length fields in packets a wermit server receives.

Generic commands, Extended GET parameters and attributes carry each
field after a length character.  A scripted client on a raw TCP socket
sends fields whose length runs past the data.  The server refuses the
command with an error packet and goes on serving.
"""
import socket
import subprocess
import threading

import pytest

from test_kermit_crafted import packet, tochar

INIT = b"~* @-#Y1~"


def _field(s):
    """Return a field: its length character, then the text.

    The control prefix "#" is doubled, as a client encodes it.
    """
    return (bytes([tochar(len(s))]) + s).replace(b"#", b"##")


def _exchange(conn, ptype, data):
    """Send one packet and return (reply type, reply data)."""
    conn.sendall(packet(0, ptype, data))
    buf = b""
    while b"\r" not in buf[buf.find(b"\x01") + 1:] if b"\x01" in buf \
            else True:
        chunk = conn.recv(4096)
        if not chunk:
            return None, b""
        buf += chunk
    pkt = buf[buf.find(b"\x01"):]
    return chr(pkt[3]), pkt[4:pkt.find(b"\r") - 1]


def _serve(wermit_path, tmp_path, commands, setup=""):
    """Send each (type, data) command to a wermit server.

    Each command follows an I packet.  Returns the list of
    (reply type, reply data) pairs.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(15)
    replies = []

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(10)
            try:
                for ptype, data in commands:
                    _exchange(conn, "I", INIT)
                    replies.append(_exchange(conn, ptype, data))
                _exchange(conn, "I", INIT)
                _exchange(conn, "G", b"F")
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        result = subprocess.run(
            [wermit_path, "-H", "-Y", "-Q", "-C",
             f"cd {tmp_path}, set host 127.0.0.1 "
             f"{srv.getsockname()[1]} /raw-socket, {setup}"
             "enable all, server, exit"],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
        thread.join(timeout=10)
    finally:
        srv.close()
    assert result.returncode >= 0, result.returncode
    return replies


@pytest.mark.parametrize("data,message", [
    (b"C" + bytes([tochar(60)]) + b"x", b"Can't change directory"),
    (b"K" + bytes([tochar(60)]) + b"a" + _field(b"b"),
     b"Invalid REMOTE COPY"),
    (b"K" + _field(b"a") + bytes([tochar(60)]) + b"b",
     b"Invalid REMOTE COPY"),
    (b"K" + _field(b"a"), b"Invalid REMOTE COPY"),
    (b"R" + bytes([tochar(60)]) + b"a" + _field(b"b"),
     b"Invalid REMOTE RENAME"),
    (b"R" + _field(b"a"), b"Invalid REMOTE RENAME"),
    (b"V" + _field(b"S") + bytes([tochar(60)]) + b"nm",
     b"Invalid REMOTE ASSIGN"),
    (b"V" + _field(b"S") + _field(b"nm"), b"Invalid REMOTE ASSIGN"),
    (b"I" + bytes([tochar(60)]) + b"user", b"Invalid REMOTE LOGIN"),
], ids=["cd", "copy-first", "copy-second", "copy-missing",
        "rename-first", "rename-missing", "assign-name",
        "assign-missing", "login"])
def test_generic_field_past_the_data(wermit_path, tmp_path, data,
                                     message):
    """Verify a generic command with a field past the data is refused."""
    replies = _serve(wermit_path, tmp_path, [("G", data), ("G", b"A")],
                     "set server login u p, " if data[:1] == b"I" else "")
    assert replies[0] == ("E", message), replies
    assert replies[1][0] in ("Y", "E"), replies   # Still serving


@pytest.mark.parametrize("data", [
    b"O" + bytes([tochar(60)]) + b"1",
    b"F" + _field(b"x") + b"O",
    b"O\x05",
], ids=["length", "no-length", "short-extended-length"])
def test_get_parameter_past_the_data(wermit_path, tmp_path, data):
    """Verify an Extended GET parameter past the data is refused."""
    replies = _serve(wermit_path, tmp_path, [("O", data), ("G", b"A")])
    assert replies[0] == ("E", b"Invalid GET Parameter"), replies
    assert replies[1][0] == "Y", replies


def test_get_end_of_parameters_without_length(wermit_path, tmp_path):
    """Verify Extended GET accepts an end-of-parameters with no length."""
    (tmp_path / "f.txt").write_text("hello\n")
    replies = _serve(wermit_path, tmp_path,
                     [("O", b"F" + _field(b"f.txt") + b"@")])
    assert replies[0][0] == "S", replies


def test_remote_assign_and_copy_still_work(wermit_path, tmp_path):
    """Verify well-formed REMOTE ASSIGN, COPY and RENAME succeed."""
    (tmp_path / "a.txt").write_text("hello\n")
    replies = _serve(wermit_path, tmp_path, [
        ("G", b"V" + _field(b"S") + _field(b"nm") + _field(b"val")),
        ("G", b"K" + _field(b"a.txt") + _field(b"b.txt")),
        ("G", b"R" + _field(b"b.txt") + _field(b"c.txt")),
    ])
    assert [r[0] for r in replies] == ["Y", "Y", "Y"], replies
    assert (tmp_path / "c.txt").read_text() == "hello\n"

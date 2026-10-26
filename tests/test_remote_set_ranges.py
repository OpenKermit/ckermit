"""
Tests for range checks on REMOTE SET values at the server (remset(),
ckcfns.c).

A scripted client on a raw TCP socket sends REMOTE SET (generic S)
packets to a wermit server and reads the reply type: Y accepts the
value, E refuses it.
"""
import socket
import subprocess
import threading

import pytest

from test_kermit_crafted import packet, tochar


def _field(s):
    """Return a REMOTE SET field: length character, then the text.

    The control prefix "#" is doubled, as a client encodes it.
    """
    return (bytes([tochar(len(s))]) + s.encode()).replace(b"#", b"##")


def _replies(wermit_path, tmp_path, settings):
    """Send each setting to a wermit server.  Return reply types.

    A setting is (code, value), or bytes sent as is after the S.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(15)
    types = []

    def exchange(conn, seq, ptype, data):
        conn.sendall(packet(seq, ptype, data))
        buf = b""
        while b"\r" not in buf:
            chunk = conn.recv(4096)
            if not chunk:
                return None
            buf += chunk
        pkt = buf[buf.find(b"\x01"):]
        return chr(pkt[3])

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(10)
            try:
                for setting in settings:
                    if isinstance(setting, bytes):
                        data = b"S" + setting
                    else:
                        code, value = setting
                        data = b"S" + _field(code) + _field(value)
                    exchange(conn, 0, "I", b"~* @-#Y1~")
                    types.append(exchange(conn, 0, "G", data))
                exchange(conn, 0, "I", b"~* @-#Y1~")
                exchange(conn, 0, "G", b"F")
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        subprocess.run(
            [wermit_path, "-H", "-Y", "-Q", "-C",
             f"cd {tmp_path}, set host 127.0.0.1 "
             f"{srv.getsockname()[1]} /raw-socket, "
             "enable set, enable finish, server, exit"],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
        thread.join(timeout=10)
    finally:
        srv.close()
    return types


@pytest.mark.parametrize("code,bad,good", [
    ("302", "99", "0"),                 # File collision
    ("302", "-1", "2"),
    ("401", "-5", "500"),               # Receive packet-length
    ("401", "9", "94"),
    ("300", "99", "1"),                 # File type
    ("301", "7", "1"),                  # File name conversion
    ("310", "9", "0"),                  # Incomplete file disposition
])
def test_remote_set_out_of_range(wermit_path, tmp_path, code, bad, good):
    """Verify the server refuses an out-of-range REMOTE SET value."""
    assert _replies(wermit_path, tmp_path,
                    [(code, bad), (code, good)]) == ["E", "Y"]


@pytest.mark.parametrize("raw", [
    bytes([tochar(90)]) + b"300!1",     # First length past the data
    bytes([tochar(3)]) + b"300",        # No second field
    bytes([0x1D]) + b"1",               # Control character as length
    b"",                                # No fields
])
def test_remote_set_bad_field_length(wermit_path, tmp_path, raw):
    """Verify the server refuses a REMOTE SET with a bad field length."""
    assert _replies(wermit_path, tmp_path,
                    [raw, ("300", "1")]) == ["E", "Y"]


@pytest.mark.parametrize("code,value", [
    ("132", "1"), ("232", "1"), ("133", "1"), ("148", "1"),
    ("134", "1"), ("135", "1"), ("139", "1"), ("141", "1"),
    ("142", "1"), ("145", "1"), ("147", "1"), ("302", "2"),
    ("311", "1"), ("312", "80"), ("313", "1"), ("314", "1"),
    ("315", "1"), ("330", "1"), ("331", "1"), ("400", "3"),
    ("400", "B"), ("402", "5"), ("403", "5"), ("404", "10"),
    ("405", "I6/100"), ("320", "latin1-iso"), ("406", "4"),
    ("410", "1"), ("420", "0"),
])
def test_remote_set_accepts_each_code(wermit_path, tmp_path, code, value):
    """Verify the server accepts a valid value for each REMOTE SET code."""
    assert _replies(wermit_path, tmp_path, [(code, value)]) == ["Y"]

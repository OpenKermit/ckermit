"""Tests for TRANSMIT /BINARY over a Telnet connection (ckuus4.c)."""
import socket
import subprocess
import threading

from conftest import scaled


def _transmit_telnet(wermit_path, path):
    """TRANSMIT path in binary mode on a Telnet connection.

    Return (returncode, bytes received).  wermit's Telnet negotiation
    comes before the file, and IAC DO LOGOUT after it.  The server
    answers none of it.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(scaled(15))
    data = bytearray()

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(scaled(10))
            try:
                while True:
                    b = conn.recv(65536)
                    if not b:
                        break
                    data.extend(b)
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        proc = subprocess.run(
            [wermit_path, "-H", "-Y", "-Q", "-C",
             "set telnet wait off, "
             f"set host 127.0.0.1 {srv.getsockname()[1]} /telnet, "
             "set transmit echo off, "
             f"transmit /binary {path}, close, exit"],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=scaled(30))
        thread.join(timeout=scaled(15))
    finally:
        srv.close()
    return proc.returncode, bytes(data)


def test_transmit_binary_iac_at_buffer_end(wermit_path, tmp_path):
    """Verify a doubled IAC at the end of the send buffer.

    TRANSMIT /BINARY collects 508 bytes before it sends them, and
    doubles each IAC on a Telnet connection.  The file puts an IAC at
    offset 507, so its doubled byte would be the 509th.  Every byte
    must arrive once, with the IAC doubled.
    """
    payload = b"a" * 507 + b"\xff" + b"b" * 100000
    path = tmp_path / "f.bin"
    path.write_bytes(payload)
    rc, data = _transmit_telnet(wermit_path, path)
    assert rc >= 0, f"wermit died with signal {-rc}"
    expected = payload.replace(b"\xff", b"\xff\xff")
    start = data.find(b"a")
    assert start >= 0, data[:64]
    assert data[start:start + len(expected)] == expected
    assert data[start + len(expected):] in (b"", b"\xff\xfd\x12")

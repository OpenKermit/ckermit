"""
Tests for TRANSMIT of a UCS-2 text file (ckuus4.c).
"""
import socket
import subprocess
import threading

import pytest

from conftest import scaled


def _transmit(wermit_path, path, fcs):
    """TRANSMIT path in text mode to a raw socket.  Return the bytes."""
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
            conn.settimeout(scaled(5))
            try:
                while True:
                    b = conn.recv(4096)
                    if not b:
                        break
                    data.extend(b)
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        subprocess.run(
            [wermit_path, "-H", "-Y", "-Q", "-C",
             f"set host 127.0.0.1 {srv.getsockname()[1]} /raw-socket, "
             f"set file character-set {fcs}, "
             "set terminal remote-character-set latin1, "
             "set transmit echo off, set transmit prompt 0, "
             f"transmit /text {path}, close, exit"],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=scaled(30))
        thread.join(timeout=scaled(10))
    finally:
        srv.close()
    return bytes(data)


@pytest.mark.parametrize("encoding", ["utf-16-be", "utf-16-le"])
def test_transmit_ucs2_ends_lines(wermit_path, tmp_path, encoding):
    """Verify LF in a UCS-2 file ends a line, as it does in 8-bit text.

    Each line goes out with a CR in place of the LF.
    """
    path = tmp_path / "u.txt"
    path.write_bytes("﻿ab\ncd\n".encode(encoding))
    assert _transmit(wermit_path, path, "ucs2") == b"ab\rcd\r"

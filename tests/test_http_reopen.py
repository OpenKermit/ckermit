"""
Tests for http_reopen() in ckcnet.c.

When sending a request fails on an open HTTP connection, the client
reopens the connection to the same address and port and resends the
request once.
"""
import socket
import struct
import threading

import pytest

MARKER = b"REOPENED"


def _serve(server_sock, result):
    """Reset the first connection, then answer one GET request."""
    try:
        server_sock.settimeout(15)
        conn, _ = server_sock.accept()
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                        struct.pack("ii", 1, 0))
        conn.close()
        conn, _ = server_sock.accept()
        try:
            conn.settimeout(10)
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                request += chunk
            result.append(request)
            conn.sendall(b"HTTP/1.1 200 OK\r\n"
                         b"Content-Length: %d\r\n"
                         b"Connection: close\r\n\r\n" % len(MARKER) +
                         MARKER)
        finally:
            conn.close()
    except OSError as e:
        result.append(e)


def test_http_reopen_uses_original_port(
    run_wermit, wermit_http_available, get_free_port, tmp_path,
):
    """Reopen on the original port, including one past 255."""
    if not wermit_http_available:
        pytest.skip("wermit built with NOHTTP")

    port = get_free_port()
    assert port > 255
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", port))
    server_sock.listen(2)
    result = []
    server = threading.Thread(target=_serve, args=(server_sock, result))
    server.start()
    downloaded = tmp_path / "out.txt"
    try:
        out = run_wermit(
            f"http open 127.0.0.1 {port}, sleep 2, "
            f"http get /file {downloaded}, http close",
            timeout=30)
    finally:
        server.join(timeout=20)
        server_sock.close()

    assert result and isinstance(result[0], bytes), (result, out.stdout)
    assert result[0].startswith(b"GET /file "), result
    assert downloaded.exists(), out.stdout
    assert downloaded.read_bytes() == MARKER

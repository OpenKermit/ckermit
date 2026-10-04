"""
Tests for HTTP client requests and replies in ckcnet.c.

Verifies parsing of HTTP chunk-size lines, including sizes of 2**32
and lines with chunk extensions. A zero size signals the terminating
chunk in HTTP chunked transfer encoding. Also verifies the request
line HTTP INDEX sends.
"""
import socket
import subprocess
import threading

import pytest

MARKER = b"MARKER"


@pytest.mark.parametrize("size_line", [
    "100000000",                # 2**32
    "6;name=value",             # chunk-extension
], ids=["2pow32", "extension"])
def test_http_get_large_chunk_size_not_truncated(
    spawn_wermit, wermit_path, wermit_http_available, get_free_port,
    tmp_path, size_line,
):
    """Verify wermit reads the chunk payload for a chunk-size line."""
    if not wermit_http_available:
        pytest.skip("wermit built with NOHTTP")

    port = get_free_port()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", port))
    server_sock.listen(1)

    outfile = "out.txt"
    proc = spawn_wermit([
        "-H", "-Y", "-C",
        "set command more-prompting off, "
        f"http open 127.0.0.1 {port}, "
        f"http get /chunk {outfile}, "
        "http close, exit",
    ], cwd=str(tmp_path))

    try:
        server_sock.settimeout(10)
        conn, _ = server_sock.accept()
        try:
            conn.settimeout(5)
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                request += chunk

            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Transfer-Encoding: chunked\r\n"
                b"\r\n" +
                size_line.encode() + b"\r\n" +
                MARKER
            )
            conn.sendall(response)
        finally:
            conn.close()
    finally:
        server_sock.close()

    proc.wait(timeout=15)

    downloaded = tmp_path / outfile
    assert downloaded.exists(), "wermit never wrote the output file"
    assert downloaded.read_bytes() == MARKER, (
        f"chunk-size line {size_line!r} misparsed"
    )


def test_http_index_request_names_directory(
    spawn_wermit, wermit_http_available, get_free_port, tmp_path,
):
    """HTTP INDEX must send the requested directory in its request line."""
    if not wermit_http_available:
        pytest.skip("wermit built with NOHTTP")

    port = get_free_port()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", port))
    server_sock.listen(1)

    proc = spawn_wermit([
        "-H", "-Y", "-C",
        "set command more-prompting off, "
        f"http open 127.0.0.1 {port}, "
        "http index /some/dir/ index.txt, "
        "http close, exit",
    ], cwd=str(tmp_path))

    try:
        server_sock.settimeout(10)
        conn, _ = server_sock.accept()
        try:
            conn.settimeout(5)
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                request += chunk
            conn.sendall(b"HTTP/1.1 200 OK\r\n"
                         b"Content-Length: 0\r\n"
                         b"Connection: close\r\n\r\n")
        finally:
            conn.close()
    finally:
        server_sock.close()

    proc.wait(timeout=15)
    request_line = request.split(b"\r\n", 1)[0]
    assert request_line == b"INDEX /some/dir/ HTTP/1.1", request


@pytest.mark.parametrize("status,exit_code", [
    (b"200 OK", 0),
    (b"404 Not Found", 1),
], ids=["ok", "not-found"])
def test_http_url_command_line_exit_status(
    wermit_path, wermit_http_available, get_free_port, tmp_path,
    status, exit_code,
):
    """An http:// URL on the command line exits with the GET's status."""
    if not wermit_http_available:
        pytest.skip("wermit built with NOHTTP")

    port = get_free_port()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", port))
    server_sock.listen(1)

    def serve():
        server_sock.settimeout(15)
        conn, _ = server_sock.accept()
        with conn:
            conn.settimeout(10)
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                request += chunk
            conn.sendall(b"HTTP/1.1 " + status + b"\r\n"
                         b"Content-Length: 2\r\n"
                         b"Connection: close\r\n\r\nok")

    server = threading.Thread(target=serve, daemon=True)
    server.start()
    try:
        result = subprocess.run(
            [wermit_path, f"http://127.0.0.1:{port}/file.txt"],
            cwd=str(tmp_path), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=30,
            start_new_session=True)
    finally:
        server.join(timeout=10)
        server_sock.close()
    assert result.returncode == exit_code, result.stdout + result.stderr

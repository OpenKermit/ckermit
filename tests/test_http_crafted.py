"""
Tests for http_get_chunk_len() in ckcnet.c with chunk sizes >= 2**32.

On 64-bit platforms, hextoulong() parses chunk sizes into a long. A chunk
size of 2**32 (hex 100000000) must not truncate to zero. A zero size signals
the terminating chunk in HTTP chunked transfer encoding.

This test sends a chunk-size line of 2**32 followed by a marker payload.
It verifies that wermit reads the marker rather than stopping at zero bytes.
"""
import socket

import pytest

CHUNK_LEN_HEX = "100000000"    # 2**32
MARKER = b"MARKER"


def test_http_get_large_chunk_size_not_truncated(
    spawn_wermit, wermit_path, wermit_http_available, get_free_port,
    tmp_path,
):
    """Verify wermit reads HTTP chunks of 2**32 bytes without truncation."""
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
                CHUNK_LEN_HEX.encode() + b"\r\n" +
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
        "chunk-size line of 2**32 truncated to 0 bytes read"
    )

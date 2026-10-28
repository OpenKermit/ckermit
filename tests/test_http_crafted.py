"""
Tests for HTTP client requests and replies in ckcnet.c.

Verifies parsing of HTTP chunk-size lines, including sizes of 2**32
and lines with chunk extensions. A zero size signals the terminating
chunk in HTTP chunked transfer encoding. Also verifies the request
line HTTP INDEX sends, and Content-Length values beyond 32 bits or
that cannot be parsed.
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


def _http_once(run_wermit, tmp_path, response):
    """Serve one HTTP response.  Return wermit's output after HTTP GET."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(15)
    port = srv.getsockname()[1]

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(5)
            request = b""
            try:
                while b"\r\n\r\n" not in request:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    request += chunk
                conn.sendall(response)
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        result = run_wermit(
            f"cd {tmp_path}, http open 127.0.0.1 {port}, "
            "http get /x out.txt, echo CODE=[\\v(http_code)], http close",
            timeout=30)
    finally:
        srv.close()
        thread.join(timeout=5)
    return result


@pytest.mark.parametrize("response,code", [
    (b"HTTP/1.1 " + b"9" * 400 + b" Huge\r\n\r\n", "0"),
    (b"HTTP/1.1 2x0 Odd\r\n\r\n", "0"),
    (b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n", "404"),
    (b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nhi", "200"),
], ids=["long-status", "non-digit", "404", "200"])
def test_http_status_code_parsing(run_wermit, wermit_http_available,
                                  tmp_path, response, code):
    """Verify the status code is bounded and parsed as three digits."""
    if not wermit_http_available:
        pytest.skip("wermit built with NOHTTP")
    result = _http_once(run_wermit, tmp_path, response)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert f"CODE=[{code}]" in result.stdout, result.stdout[-500:]


@pytest.mark.parametrize("modified", [
    b"Mon, 20240101",
    b"garbage",
    b"Mon, 01 Jan 2024 00:00:00 GMT",
], ids=["bare-date", "garbage", "valid"])
def test_http_last_modified_parsing(run_wermit, wermit_http_available,
                                    tmp_path, modified):
    """Verify an unusable Last-Modified date does not crash HTTP GET."""
    if not wermit_http_available:
        pytest.skip("wermit built with NOHTTP")
    response = (b"HTTP/1.1 200 OK\r\nLast-Modified: " + modified +
                b"\r\nContent-Length: 2\r\n\r\nhi")
    result = _http_once(run_wermit, tmp_path, response)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "CODE=[200]" in result.stdout, result.stdout[-500:]
    assert (tmp_path / "out.txt").read_bytes() == b"hi"


def _ipv6_loopback_available():
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        s.bind(("::1", 0))
        s.close()
        return True
    except OSError:
        return False


def _record_requests(responses):
    """Serve one connection on ::1 and record request heads.  Return port.

    responses lists the bytes to send after each request head.
    Returns (port, thread, socket, list of request heads).
    """
    srv = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    srv.bind(("::1", 0))
    srv.listen(1)
    srv.settimeout(15)
    heads = []

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(5)
            buf = b""
            try:
                for response in responses:
                    while b"\r\n\r\n" not in buf:
                        chunk = conn.recv(4096)
                        if not chunk:
                            return
                        buf += chunk
                    head, buf = buf.split(b"\r\n\r\n", 1)
                    heads.append(head.decode("latin-1"))
                    conn.sendall(response)
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return srv.getsockname()[1], thread, srv, heads


OK_RESPONSE = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nhi"


def test_http_host_header_brackets_ipv6(run_wermit, tmp_path):
    """Verify the Host header encloses an IPv6 address in brackets."""
    if not _ipv6_loopback_available():
        pytest.skip("no IPv6 loopback")
    port, thread, srv, heads = _record_requests([OK_RESPONSE])
    try:
        result = run_wermit(
            f"cd {tmp_path}, http open ::1 {port}, "
            "http get /x out.txt, echo CODE=[\\v(http_code)], http close",
            timeout=30)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert "CODE=[200]" in result.stdout, result.stdout
    assert heads, result.stdout
    assert f"\r\nHost: [::1]:{port}" in heads[0], heads


def test_http_proxy_connect_brackets_ipv6(run_wermit, tmp_path):
    """Verify CONNECT through a bracketed IPv6 proxy address.

    The proxy address "[::1]:PORT" must be split at the bracket, and
    the CONNECT target and Host header must bracket the address.
    """
    if not _ipv6_loopback_available():
        pytest.skip("no IPv6 loopback")
    port, thread, srv, heads = _record_requests([
        b"HTTP/1.1 200 Connection established\r\n\r\n", OK_RESPONSE])
    try:
        result = run_wermit(
            f"cd {tmp_path}, set tcp http-proxy [::1]:{port}, "
            "http open ::1 18080, "
            "http get /x out.txt, echo CODE=[\\v(http_code)], http close",
            timeout=30)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert heads, result.stdout
    assert heads[0].startswith("CONNECT [::1]:18080 "), heads
    assert "\r\nHost: [::1]:18080" in heads[0], heads


def _http_get_status(run_wermit, tmp_path, response):
    """Serve one response to HTTP GET.  Return (result, body or None)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(15)
    port = srv.getsockname()[1]

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(5)
            request = b""
            try:
                while b"\r\n\r\n" not in request:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    request += chunk
                conn.sendall(response)
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        result = run_wermit(
            f"cd {tmp_path}, http open 127.0.0.1 {port}, "
            "http get /x out.txt, echo STATUS=[\\v(status)], http close",
            timeout=30)
    finally:
        srv.close()
        thread.join(timeout=5)
    out = tmp_path / "out.txt"
    return result, (out.read_bytes() if out.exists() else None)


CHUNKED_HEAD = (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n"
                b"Connection: close\r\n\r\n")


def test_http_chunk_extension_is_skipped(run_wermit, tmp_path):
    """Verify a long chunk extension does not end the body early."""
    response = (CHUNKED_HEAD +
                b"6;name=" + b"e" * 40 + b"\r\nhello \r\n"
                b"5\r\nworld\r\n0\r\n\r\n")
    result, body = _http_get_status(run_wermit, tmp_path, response)
    assert body == b"hello world", (body, result.stdout)
    assert "STATUS=[0]" in result.stdout, result.stdout


def test_http_malformed_chunk_size_fails(run_wermit, tmp_path):
    """Verify a chunk-size line without hex digits fails the GET."""
    response = CHUNKED_HEAD + b"zz\r\nhello\r\n0\r\n\r\n"
    result, body = _http_get_status(run_wermit, tmp_path, response)
    assert "STATUS=[1]" in result.stdout, result.stdout


@pytest.mark.parametrize("value, expected", [
    (b" 3000000000", b"hello"),         # over 2 GiB
    (b" 4294967298", b"hello"),         # 2**32 + 2
    (b" 9223372036854775807", b"hello"),
    (b" 99999999999999999999", b"hello"),   # overflows 64 bits
    (b" -5", b"hello"),
    (b" 5x", b"hello"),
    (b"", b"hello"),
    (b"3", b"hel"),                     # no blank after the colon
    (b" 3 ", b"hel"),
], ids=["3e9", "2pow32p2", "max64", "overflow", "negative", "garbage",
        "empty", "noblank", "trailing"])
def test_http_content_length_values(run_wermit, tmp_path, value, expected):
    """Verify GET reads the body for large and malformed lengths.

    A valid length limits the body.  A length that cannot be parsed
    reads until the server closes the connection.
    """
    response = (b"HTTP/1.1 200 OK\r\nConnection: close\r\n"
                b"Content-Length:" + value + b"\r\n\r\nhello")
    result, body = _http_get_status(run_wermit, tmp_path, response)
    assert body == expected, (body, result.stdout)
    assert "STATUS=[0]" in result.stdout, result.stdout


def test_ftp_proxy_connect_brackets_ipv6(run_wermit, tmp_path):
    """Verify FTP OPEN through a bracketed IPv6 HTTP proxy.

    ftp_hookup() must split "[::1]:PORT" at the bracket and bracket
    the IPv6 CONNECT target.  The proxy refuses the request.
    """
    if not _ipv6_loopback_available():
        pytest.skip("no IPv6 loopback")
    port, thread, srv, heads = _record_requests([
        b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n"])
    try:
        result = run_wermit(
            f"cd {tmp_path}, set tcp http-proxy [::1]:{port}, "
            "ftp open ::1 2121 /user:u /password:p, "
            "echo STATUS=[\\v(status)]", timeout=30)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert heads, result.stdout + result.stderr
    assert heads[0].startswith("CONNECT [::1]:2121 "), heads

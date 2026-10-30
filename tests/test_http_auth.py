"""
Tests for HTTP Basic authentication credentials (http_basic(), ckcnet.c).
"""
import base64
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@pytest.fixture
def auth_server():
    """Serve /f.txt and record each Authorization header."""
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            seen.append(self.headers.get("Authorization"))
            body = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1], seen
    srv.shutdown()


def _get(run_wermit, port, user, pwd, dest):
    """GET /f.txt with the given credentials and return the result."""
    return run_wermit(
        f"http open 127.0.0.1 {port}, "
        f"http /user:{user} /password:{pwd} get /f.txt {dest}, "
        "echo S=\\v(status), http close", timeout=30)


def test_http_long_credentials_sent_whole(run_wermit, tmp_path,
                                          auth_server):
    """Verify user:password of 255 bytes is sent without truncation."""
    port, seen = auth_server
    user, pwd = "u" * 150, "p" * 104
    result = _get(run_wermit, port, user, pwd, tmp_path / "out.txt")
    assert "S=0" in result.stdout, result.stdout + result.stderr
    assert seen and seen[0].startswith("Basic "), seen
    assert base64.b64decode(seen[0][6:]).decode() == f"{user}:{pwd}"


def test_http_too_long_credentials_fail(run_wermit, tmp_path, auth_server):
    """Verify user:password over 255 bytes fails without a request."""
    port, seen = auth_server
    result = _get(run_wermit, port, "u" * 150, "p" * 105,
                  tmp_path / "out.txt")
    assert "too long" in result.stdout, result.stdout
    assert "S=1" in result.stdout, result.stdout
    assert seen == [], seen

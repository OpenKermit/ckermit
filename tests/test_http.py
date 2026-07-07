import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import base64
import pytest
from conftest import assert_ok


@pytest.fixture
def http_server(tmp_path):
    received_data = {}

    class SilentHTTPRequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            if self.path == "/hello.txt":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                content = b"Hello from mock HTTP server!"
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            elif self.path == "/secret.txt":
                auth_header = self.headers.get('Authorization')
                if not auth_header:
                    self.send_response(401)
                    self.send_header('WWW-Authenticate', 'Basic realm="Test"')
                    self.end_headers()
                    self.wfile.write(b"Unauthorized")
                    return

                try:
                    auth_type, encoded = auth_header.split(None, 1)
                    if auth_type.lower() == 'basic':
                        decoded = base64.b64decode(encoded).decode('utf-8')
                        username, password = decoded.split(':', 1)
                        if username == "testuser" and password == "testpass":
                            self.send_response(200)
                            self.send_header("Content-Type", "text/plain")
                            content = b"Confidential Data"
                            self.send_header("Content-Length",
                                             str(len(content)))
                            self.end_headers()
                            self.wfile.write(content)
                            return
                except Exception:
                    pass

                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Forbidden")
            elif self.path == "/check_headers":
                test_header = self.headers.get("X-Test-Header")
                user_agent = self.headers.get("User-Agent")
                if test_header == "Value" and user_agent == "MyCustomAgent":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    content = b"Headers Verified"
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self.send_response(400)
                    self.end_headers()
                    msg = (
                        f"Bad Headers: test_header={test_header}, "
                        f"user_agent={user_agent}"
                    )
                    self.wfile.write(msg.encode())
            elif self.path == "/redirect_301":
                self.send_response(301)
                port = self.server.server_port
                loc = f"http://127.0.0.1:{port}/hello.txt"
                self.send_header("Location", loc)
                self.end_headers()
                self.wfile.write(b"Redirect")
            elif self.path == "/error_500":
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"Internal Server Error")
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not Found")

        def do_PUT(self):
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            received_data[self.path] = body
            self.send_response(201)
            self.end_headers()
            self.wfile.write(b"Created")

        def do_POST(self):
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            received_data[self.path] = body
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

    server = HTTPServer(("127.0.0.1", 0), SilentHTTPRequestHandler)
    ip, port = server.server_address

    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    yield port, tmp_path, received_data

    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def http_session(port, *commands):
    return ", ".join([f"http open 127.0.0.1 {port}", *commands, "http close", "exit"])


def test_http_get_basic(http_server, run_wermit):
    port, tmp_path, _ = http_server
    dest_file = tmp_path / "hello_received.txt"

    result = run_wermit(http_session(port, f"http get /hello.txt {dest_file}"))
    assert_ok(result, "HTTP GET failed")

    assert dest_file.exists()
    assert dest_file.read_bytes() == b"Hello from mock HTTP server!"


def test_http_get_with_auth(http_server, run_wermit):
    port, tmp_path, _ = http_server
    dest_file = tmp_path / "secret_received.txt"

    result = run_wermit(http_session(
        port, f"http /user:testuser /password:testpass get /secret.txt {dest_file}"
    ))
    assert_ok(result, "HTTP GET with auth failed")

    assert dest_file.exists()
    assert dest_file.read_bytes() == b"Confidential Data"


def test_http_put(http_server, run_wermit, tmp_path):
    port, _, received_data = http_server

    put_file = tmp_path / "put_payload.txt"
    put_content = b"This is PUT payload text content."
    put_file.write_bytes(put_content)

    result = run_wermit(http_session(
        port, f"http put {put_file} /uploaded_put.txt"))
    assert_ok(result, "HTTP PUT failed")

    assert "/uploaded_put.txt" in received_data, (
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert received_data["/uploaded_put.txt"] == put_content


def test_http_post(http_server, run_wermit, tmp_path):
    port, _, received_data = http_server

    post_file = tmp_path / "post_payload.txt"
    post_content = b"This is POST payload text content."
    post_file.write_bytes(post_content)

    result = run_wermit(http_session(
        port, f"http post {post_file} /uploaded_post.txt"))
    assert_ok(result, "HTTP POST failed")

    assert "/uploaded_post.txt" in received_data, (
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert received_data["/uploaded_post.txt"] == post_content


def test_http_headers_and_agent(http_server, run_wermit):
    port, tmp_path, _ = http_server
    dest_file = tmp_path / "headers_received.txt"

    # Injecting custom header using /header and user agent using /agent
    result = run_wermit(http_session(
        port,
        f"http /header:{{{{X-Test-Header:Value}}}} /agent:MyCustomAgent get /check_headers {dest_file}",
    ))
    assert_ok(result, "HTTP headers/agent request failed")

    assert dest_file.exists()
    assert dest_file.read_bytes() == b"Headers Verified"


def test_http_array_switch(http_server, run_wermit, tmp_path):
    port, _, _ = http_server
    dest_file = tmp_path / "array_get.txt"

    # We fetch /hello.txt and save response headers in array &c
    result = run_wermit(http_session(
        port,
        f"http /array:&c get /hello.txt {dest_file}",
        *[f"echo VAL:\\&c[{i}]" for i in range(1, 11)],
    ))
    assert_ok(result, "HTTP array switch request failed")

    headers = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("VAL:"):
            val = line.split(":", 1)[1].strip()
            if val:
                headers.append(val)

    # Verify that we retrieved at least 3 headers
    assert len(headers) >= 3

    # Verify that standard headers are present in subsequent lines
    assert any("Content-Type" in h for h in headers)
    assert any("Content-Length" in h for h in headers)


def test_http_redirect(http_server, run_wermit, tmp_path):
    port, _, _ = http_server
    dest_file = tmp_path / "redirect_received.txt"

    # Try to GET from /redirect_301. Since Kermit doesn't follow redirects
    # automatically and treats 3xx as failure, the command should fail.
    result = run_wermit(http_session(
        port, f"http get /redirect_301 {dest_file}", "if failure exit 1"
    ))

    # Verify that the command failed (returns non-zero or outputs failure)
    assert result.returncode != 0
    assert "Failure: Server reports 301" in result.stdout
    assert not dest_file.exists()


def test_http_error_handling(http_server, run_wermit, tmp_path):
    port, _, _ = http_server
    dest_file = tmp_path / "error_received.txt"

    # Test 404 Not Found
    result_404 = run_wermit(http_session(
        port, f"http get /nonexistent.txt {dest_file}", "if failure exit 1"
    ))
    assert result_404.returncode != 0
    assert "Failure: Server reports 404" in result_404.stdout
    assert not dest_file.exists()

    # Test 500 Internal Server Error
    result_500 = run_wermit(http_session(
        port, f"http get /error_500 {dest_file}", "if failure exit 1"
    ))
    assert result_500.returncode != 0
    assert "Failure: Server reports 500" in result_500.stdout
    assert not dest_file.exists()

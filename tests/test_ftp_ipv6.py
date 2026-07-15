"""
FTP-over-IPv6 tests, covering RFC 2428 EPRT/EPSV
These mirror test_ftp.py's upload/download coverage
but connect over ::1, exercising both active (EPRT) and passive
(EPSV) data connections.
"""
import errno
import socket
import threading
import pytest
from pyftpdlib.authorizers import DummyAuthorizer
from conftest import assert_ok
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer


def _ipv6_loopback_available():
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        s.bind(("::1", 0))
        s.close()
        return True
    except OSError:
        return False


def _build_has_address_family(run_wermit):
    result = run_wermit("show tcp")
    assert_ok(result, "SHOW TCP failed")
    return "address-family:" in result.stdout


@pytest.fixture
def ftp_server_v6(run_wermit, tmp_path):
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    if not _ipv6_loopback_available():
        pytest.skip("no IPv6 loopback available in this environment")

    authorizer = DummyAuthorizer()
    authorizer.add_user("testuser", "testpass",
                        str(tmp_path), perm="elradfmwMT")

    class SilentFTPHandler(FTPHandler):
        def log(self, *args, **kwargs):
            pass

        def log_line(self, *args, **kwargs):
            pass

    server = FTPServer(("::1", 0), SilentFTPHandler)
    server.handler.authorizer = authorizer

    ip, port, flowinfo, scopeid = server.socket.getsockname()

    def run_server():
        try:
            server.serve_forever()
        except OSError as e:
            # close_all() below can close the kqueue/select fd from
            # the main thread while this thread is blocked inside
            # it, causing EBADF. This is an expected shutdown race,
            # not a real failure.
            if e.errno != errno.EBADF:
                raise

    thread = threading.Thread(target=run_server)
    thread.daemon = True
    thread.start()

    yield port, tmp_path

    server.close_all()
    thread.join(timeout=2)


def ftp_session_v6(port, *commands, active=False):
    openswitch = " /active" if active else ""
    return ", ".join([
        f"ftp open ::1 {port}{openswitch} "
        f"/user:testuser /password:testpass",
        *commands,
        "ftp close", "exit"
    ])


@pytest.mark.parametrize("active", [False, True], ids=["epsv", "eprt"])
def test_ftp_ipv6_upload_download(ftp_server_v6, run_wermit, tmp_path,
                                   active):
    port, server_dir = ftp_server_v6

    local_dir = tmp_path / "local"
    local_dir.mkdir()
    local_file = local_dir / "upload.dat"
    content = b"FTP over IPv6 binary data content " * 100
    local_file.write_bytes(content)

    server_file_name = "server_file.dat"
    result = run_wermit(ftp_session_v6(
        port, f"ftp put {local_file} {server_file_name}", active=active))
    assert_ok(result, "IPv6 upload failed")

    uploaded_file = server_dir / server_file_name
    assert uploaded_file.exists()
    assert uploaded_file.read_bytes() == content

    download_file = local_dir / "download.dat"
    result = run_wermit(ftp_session_v6(
        port, f"ftp get {server_file_name} {download_file}", active=active))
    assert_ok(result, "IPv6 download failed")

    assert download_file.exists()
    assert download_file.read_bytes() == content

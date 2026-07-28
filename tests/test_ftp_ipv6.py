"""
FTP-over-IPv6 tests, covering RFC 2428 EPRT/EPSV
These mirror test_ftp.py's upload/download coverage
but connect over ::1, exercising both active (EPRT) and passive
(EPSV) data connections.
"""
import errno
import socket
import subprocess
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


def _ipv6_addrs_by_iface():
    """Map network interface names to assigned IPv6 addresses."""
    try:
        with open("/proc/net/if_inet6") as f:
            lines = f.read().splitlines()
        by_iface = {}
        for line in lines:
            parts = line.split()
            if len(parts) != 6:
                continue
            addr_hex, _prefix, _scope, _flags, _status, iface = parts
            addr = socket.inet_ntop(socket.AF_INET6,
                                     bytes.fromhex(addr_hex))
            by_iface.setdefault(iface, []).append(addr)
        return by_iface
    except OSError:
        pass

    try:
        out = subprocess.run(["ifconfig", "-a"], capture_output=True,
                              text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    by_iface = {}
    iface = None
    for line in out.splitlines():
        if line and not line[0].isspace():
            iface = line.split(":", 1)[0]
            continue
        parts = line.split()
        if iface and len(parts) >= 2 and parts[0] == "inet6":
            addr = parts[1].split("%")[0].split("/")[0]
            by_iface.setdefault(iface, []).append(addr)
    return by_iface


def _link_local_interface_and_address():
    """Return (interface, address) for a non-loopback link-local address."""
    for iface, addrs in _ipv6_addrs_by_iface().items():
        if iface in ("lo", "lo0"):
            continue
        for addr in addrs:
            if addr.startswith("fe80"):
                return iface, addr
    return None


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


@pytest.fixture
def ftp_server_link_local(run_wermit, tmp_path):
    """Fixture providing an FTP server bound to a link-local address."""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    found = _link_local_interface_and_address()
    if not found:
        pytest.skip("no non-loopback link-local address available "
                     "in this environment")
    iface, addr = found

    authorizer = DummyAuthorizer()
    authorizer.add_user("testuser", "testpass",
                        str(tmp_path), perm="elradfmwMT")

    eprt_commands = []

    class SilentFTPHandler(FTPHandler):
        def log(self, *args, **kwargs):
            pass

        def log_line(self, *args, **kwargs):
            pass

        def ftp_EPRT(self, line):
            eprt_commands.append(line)
            return super().ftp_EPRT(line)

    # bind_af_unspecified parses zone suffixes directly in host string.
    server = FTPServer((f"{addr}%{iface}", 0), SilentFTPHandler)
    server.handler.authorizer = authorizer

    ip, port, flowinfo, scopeid = server.socket.getsockname()

    def run_server():
        try:
            server.serve_forever()
        except OSError as e:
            if e.errno != errno.EBADF:
                raise

    thread = threading.Thread(target=run_server)
    thread.daemon = True
    thread.start()

    yield iface, addr, port, tmp_path, eprt_commands

    server.close_all()
    thread.join(timeout=2)


def ftp_session_link_local(iface, addr, port, *commands, active=False):
    openswitch = " /active" if active else ""
    return ", ".join([
        f"ftp open {addr}%{iface} {port}{openswitch} "
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


# Link-local FTP tests.


def test_ftp_link_local_control_connection_and_eprt(
        ftp_server_link_local, run_wermit, tmp_path):
    """Verify FTP EPRT command does not include zone suffix."""
    iface, addr, port, server_dir, eprt_commands = ftp_server_link_local

    local_dir = tmp_path / "local"
    local_dir.mkdir()
    local_file = local_dir / "upload.dat"
    local_file.write_bytes(b"FTP over a link-local control connection ")

    # Script execution continues after FTP failure; check file absence.
    result = run_wermit(ftp_session_link_local(
        iface, addr, port, f"ftp put {local_file} server_file.dat",
        active=True))
    assert "Login successful" in result.stdout
    assert not (server_dir / "server_file.dat").exists(), (
        "the data transfer itself cannot succeed here (see comment above); "
        "only the control connection and EPRT text are under test")

    assert eprt_commands, "active mode should have sent EPRT"
    for cmd in eprt_commands:
        assert "%" not in cmd, (
            f"EPRT command leaked a zone suffix onto the wire: {cmd!r}")


def test_ftp_link_local_passive_fails_cleanly(
        ftp_server_link_local, run_wermit, tmp_path):
    """Verify passive FTP over link-local address fails cleanly."""
    iface, addr, port, server_dir, eprt_commands = ftp_server_link_local

    local_dir = tmp_path / "local"
    local_dir.mkdir()
    local_file = local_dir / "upload.dat"
    local_file.write_bytes(b"FTP over a link-local control connection ")

    result = run_wermit(ftp_session_link_local(
        iface, addr, port, f"ftp put {local_file} server_file.dat",
        active=False))
    assert "Login successful" in result.stdout
    assert not (server_dir / "server_file.dat").exists()
    assert not eprt_commands, "passive mode should never send EPRT"

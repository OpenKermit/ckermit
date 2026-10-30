"""Tests for the reason reported when SET HOST cannot connect."""
import socket

import pytest

from conftest import assert_ok, kermit_wait, scaled


def _closed_port():
    """Return a loopback TCP port with no listener."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_set_host_refused_reports_reason(run_wermit):
    """Verify a refused connection sets \\v(setlinemsg) from errno."""
    port = _closed_port()
    result = run_wermit(f"set host 127.0.0.1 {port} /raw-socket, "
                        "echo MSG=[\\v(setlinemsg)]")
    assert "MSG=[Connection refused]" in result.stdout, result.stdout
    assert f"Can't connect to 127.0.0.1:{port}" in result.stdout, (
        result.stdout)


def test_set_host_unresolved_name(run_wermit):
    """Verify an unresolvable name does not report a stale errno."""
    result = run_wermit("set host no-such-host.invalid 23 /raw-socket, "
                        "echo MSG=[\\v(setlinemsg)]")
    out = result.stdout + result.stderr
    assert "Can't get address for no-such-host.invalid" in out, out
    assert "MSG=[Network connection failure]" in result.stdout, out


def _fill_descriptors():
    """Raise the descriptor limit and occupy descriptors 3 to 1023.

    Runs in the child before exec.  wermit's next socket is then 1024,
    the first descriptor past FD_SETSIZE on Linux, so an FD_SET() on it
    writes past the end of the fd_set.
    """
    import os
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    want = 2048
    if hard != resource.RLIM_INFINITY and hard < want:
        want = hard
    resource.setrlimit(resource.RLIMIT_NOFILE, (want, hard))
    null = os.open("/dev/null", os.O_RDONLY)
    os.set_inheritable(null, True)
    for fd in range(3, 1024):
        if fd != null:
            os.dup2(null, fd)


def test_set_host_with_descriptor_above_fd_setsize(wermit_path):
    """Verify SET HOST and INPUT work with a socket above FD_SETSIZE.

    select() cannot wait on such a descriptor.  The connection is made
    without it, and reads wait with poll().  FD_SET() on it would write
    past the fd_set.  The overflow shows only under AddressSanitizer.
    """
    import resource
    import subprocess
    import threading
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if hard != resource.RLIM_INFINITY and hard < 2048:
        pytest.skip("descriptor limit too low")
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(scaled(15))
    port = srv.getsockname()[1]

    def run():
        try:
            conn, _ = srv.accept()
            conn.sendall(b"HELLO\r\n")
            conn.close()
        except OSError:
            pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        result = subprocess.run(
            [wermit_path, "-H", "-Y", "-C",
             "set command more-prompting off, "
             f"set host 127.0.0.1 {port} /raw-socket, "
             f"echo STATUS=\\v(status), input {kermit_wait()} HELLO, "
             "echo INSTATUS=\\v(instatus), close, exit"],
            capture_output=True, text=True, timeout=scaled(30),
            stdin=subprocess.DEVNULL, start_new_session=True,
            close_fds=False, preexec_fn=_fill_descriptors)
    finally:
        srv.close()
        thread.join(timeout=scaled(5))
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}: {result.stderr}")
    assert "STATUS=0" in result.stdout, result.stdout + result.stderr
    assert "INSTATUS=0" in result.stdout, result.stdout


def _run_above_fd_setsize(wermit_path, cmds):
    """Run cmds with descriptors 3 to 1023 occupied.

    Returns the CompletedProcess.  Skips if the descriptor limit is
    too low.
    """
    import resource
    import subprocess
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if hard != resource.RLIM_INFINITY and hard < 2048:
        pytest.skip("descriptor limit too low")
    return subprocess.run(
        [wermit_path, "-H", "-Y", "-C",
         "set command more-prompting off, " + cmds + ", exit"],
        capture_output=True, text=True, timeout=scaled(30),
        stdin=subprocess.DEVNULL, start_new_session=True,
        close_fds=False, preexec_fn=_fill_descriptors)


def test_http_get_with_descriptor_above_fd_setsize(wermit_path, tmp_path):
    """Verify HTTP GET fails cleanly on a socket above FD_SETSIZE.

    http_inc() cannot wait on the socket with select().  It fails
    instead of writing past the fd_set.  The overflow shows only under
    AddressSanitizer.
    """
    import http.server
    import threading

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    (tmp_path / "f.txt").write_text("hello\n")

    def handler(*a, **k):
        return Quiet(*a, directory=str(tmp_path), **k)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        result = _run_above_fd_setsize(
            wermit_path,
            f"http open 127.0.0.1 {srv.server_address[1]}, "
            f"http get /f.txt {tmp_path}/out.txt, "
            "echo STATUS=\\v(status), http close")
    finally:
        srv.shutdown()
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}: {result.stderr}")
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "STATUS=" in result.stdout, result.stdout + result.stderr


def test_connect_with_descriptor_above_fd_setsize(wermit_path):
    """Verify CONNECT refuses a connection above FD_SETSIZE.

    The kernel completes the connection from the listen backlog.  The
    test does not accept it.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    try:
        result = _run_above_fd_setsize(
            wermit_path,
            f"set host 127.0.0.1 {srv.getsockname()[1]} /raw-socket, "
            "connect, echo DONE, close")
    finally:
        srv.close()
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}: {result.stderr}")
    assert "exceeds FD_SETSIZE" in result.stdout, result.stdout
    assert "DONE" in result.stdout, result.stdout


def test_name2addr_prefers_ipv4(run_wermit):
    """Verify \\fname2addr(localhost) gives the IPv4 address by default."""
    result = run_wermit("echo [\\fname2addr(localhost)]")
    assert "[127.0.0.1]" in result.stdout, result.stdout


def test_vsock_without_address_reports_error(run_wermit):
    """Verify SET HOST /NETWORK-TYPE:VSOCK with no address says why."""
    result = run_wermit("set host /network-type:vsock, "
                        "echo STATUS=\\v(status)")
    if "?CID:PORT required" not in result.stdout:
        features = run_wermit("show features")
        assert_ok(features, "SHOW FEATURES failed")
        if "vsock" not in features.stdout.lower():
            pytest.skip("build has no VSOCK support")
    assert "?CID:PORT required" in result.stdout, result.stdout

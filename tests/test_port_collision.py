import socket
import subprocess

import pytest

from conftest import (_wait_for_tcp_listener, PortCollisionError,
                      assert_ok)


def test_wait_for_tcp_listener_detects_port_collision(tmp_path):
    """
    Regression test for the test suite!

    For the get_free_port() TOCTOU race.  get_free_port() finds
    a free port by binding then immediately releasing it, so between the release
    and the SET HOST bind(), some other process (typically another pytest
    process probing at nearly the same instant) can grab the same port first.
    When that happens ckermit prints "Unable to bind to socket" and exits;
    _wait_for_tcp_listener must recognize that specific message and raise
    PortCollisionError (a RuntimeError subclass), not a plain RuntimeError, so
    callers know to retry with a fresh port rather than fail the test outright.
    """
    log_path = tmp_path / "server.log"
    log_path.write_text(
        "?Unable to bind to socket (errno = 98)\r\n"
        "Can't connect to *:12345\r\n"
    )
    proc = subprocess.Popen(["true"])
    proc.wait()
    with open(log_path) as log_fh:
        with pytest.raises(PortCollisionError):
            _wait_for_tcp_listener(proc, log_path, log_fh, "test",
                                    timeout=1)


def test_wait_for_tcp_listener_generic_failure_is_plain_runtimeerror(
        tmp_path):
    """
    Companion to test_wait_for_tcp_listener_detects_port_collision.

    Confirms a startup failure NOT carrying ckermit's specific
    bind-failure message still raises RuntimeError, and specifically
    not PortCollisionError, since retrying with a fresh port won't fix
    a genuine startup problem.
    """
    log_path = tmp_path / "server.log"
    log_path.write_text("?Sorry, some unrelated startup error\r\n")
    proc = subprocess.Popen(["true"])
    proc.wait()
    with open(log_path) as log_fh:
        with pytest.raises(RuntimeError) as exc_info:
            _wait_for_tcp_listener(proc, log_path, log_fh, "test",
                                    timeout=1)
    assert not isinstance(exc_info.value, PortCollisionError)


@pytest.fixture
def get_free_port(get_free_port):
    """
    Overrides the real get_free_port fixture (see conftest.py) so the
    first port it hands out is already bound and listened-on by this
    process itself.
    """
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    blocked_port = blocker.getsockname()[1]
    calls = {"n": 0}

    def _wrapped():
        calls["n"] += 1
        if calls["n"] == 1:
            return blocked_port
        blocker.close()
        return get_free_port()

    yield _wrapped
    blocker.close()


def test_wermit_tcp_loopback_retries_on_port_collision(
        server_dir, wermit_tcp_loopback):
    """
    End-to-end regression test for the get_free_port() race.
    With the get_free_port override forcing the first probed
    port to be taken, wermit_tcp_loopback's server setup must
    detect the resulting "Unable to bind to socket" failure, retry
    with a freshly probed port, and end up with a working server
    rather than propagating the failure to the test.
    """
    session = wermit_tcp_loopback(server_dir, protocol="raw-socket")
    result = session.run_client("show version")
    assert_ok(result)
    assert "C-Kermit" in result.stdout

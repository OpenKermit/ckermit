"""Tests for SET HOST * 0, a listener on a port the system chooses."""
import socket

import pytest

from conftest import listen_port, start_tcp_listener, _wait_or_kill


def _ipv6_loopback_available():
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            s.bind(("::1", 0))
    except OSError:
        return False
    return True


@pytest.mark.parametrize("host", [
    "127.0.0.1",
    pytest.param("::1", marks=pytest.mark.skipif(
        not _ipv6_loopback_available(), reason="no IPv6 loopback")),
])
def test_set_host_star_port_zero(spawn_wermit, tmp_path, host):
    """Verify SET HOST * 0 reports the chosen port and accepts on it.

    The IPv4 and IPv6 sockets share the port.  A client on either
    loopback address reaches the listener.
    """
    log = tmp_path / "server.log"
    port, proc, log_fh = start_tcp_listener(
        spawn_wermit,
        ["--unbuffered", "-H", "-Y", "-C",
         "set command more-prompting off, "
         "set tcp reverse-dns-lookup off, "
         "set host * 0 /raw-socket, if fail exit 1, "
         "echo ACCEPTED, close, exit 0"],
        log, "port_zero")
    try:
        assert port > 0
        with socket.create_connection((host, port), timeout=10):
            pass
        assert _wait_or_kill(proc, timeout=10) == 0
    finally:
        log_fh.close()
        _wait_or_kill(proc, timeout=1)
    out = log.read_text(errors="replace")
    assert "ACCEPTED" in out, out


def test_listen_port_parses_complete_line():
    """Verify listen_port() reads the port from the full line only."""
    line = "Waiting to Accept a TCP/IP connection on port 12345 ..."
    assert listen_port("Listening ...\n" + line + "\n") == 12345
    assert listen_port(line[:-6]) is None
    assert listen_port("Listening ...\n") is None


def test_listen_port_rejects_ipv4_only_listener():
    """Verify listen_port() raises when the listener has no IPv6 socket."""
    out = ("?WARNING: IPv6 port 12345 is in use after 8 tries.\n"
           "?WARNING: Listening on IPv4 only.\n"
           "Waiting to Accept a TCP/IP connection on port 12345 ...\n")
    with pytest.raises(RuntimeError):
        listen_port(out)

"""
IPv6 tests
"""
import socket
import threading
import time
import pytest
from conftest import assert_ok


def _show_tcp_output(run_wermit):
    result = run_wermit("show tcp")
    assert_ok(result, "SHOW TCP failed")
    return result.stdout


# Maybe we should assume that any machine that has Python has IPv6?  Probably
# valid in 2026, but....  well there's always something weird out there.
def _build_has_address_family(run_wermit):
    return "address-family:" in _show_tcp_output(run_wermit)


@pytest.mark.parametrize("value", ["ipv4", "ipv6", "auto"])
def test_set_tcp_address_family(run_wermit, value):
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")

    result = run_wermit(f"set tcp address-family {value}, show tcp")
    assert_ok(result, f"SET TCP ADDRESS-FAMILY {value} failed")
    assert f"address-family: {value}" in result.stdout


def test_set_tcp_address_family_default_is_auto(run_wermit):
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")

    assert "address-family: auto" in _show_tcp_output(run_wermit)


def test_set_tcp_address_family_rejects_bad_value(run_wermit):
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")

    result = run_wermit("set tcp address-family bogus")
    assert result.returncode != 0


def test_help_set_tcp_mentions_address_family_iff_supported(run_wermit):
    result = run_wermit("help set tcp")
    assert_ok(result, "HELP SET TCP failed")

    if _build_has_address_family(run_wermit):
        assert "ADDRESS-FAMILY" in result.stdout
    else:
        assert "ADDRESS-FAMILY" not in result.stdout


# These check the *parsing* (host/port split visible via debug log),
# not that a connection succeeds.

def _netopen_debug_lines(run_wermit, tmp_path, cmds):
    log_path = tmp_path / "dbg.log"
    run_wermit(f"log debug {log_path}, {cmds}")
    return log_path.read_text(errors="replace")


def test_set_host_bracket_with_port_parses(run_wermit, tmp_path):
    content = _netopen_debug_lines(
        run_wermit, tmp_path, "set host [::1]:23, exit")
    assert "netopen host[::1]" in content
    assert "netopen service requested[23]" in content


def test_set_host_bracket_space_port_parses(run_wermit, tmp_path):
    """A bracketed IPv6 literal with the port given as a separate,
    space-delimited argument (the documented SET HOST syntax) must
    split the same way as the ":port" form."""
    content = _netopen_debug_lines(
        run_wermit, tmp_path, "set host [::1] 23, exit")
    assert "netopen host[::1]" in content
    assert "netopen service requested[23]" in content


def test_set_host_bracket_without_port_parses(run_wermit, tmp_path):
    content = _netopen_debug_lines(
        run_wermit, tmp_path, "set host [::1], exit")
    assert "netopen host[::1]" in content
    assert "netopen service requested[telnet]" in content


def test_set_host_bracket_v6_literal_with_port_parses(run_wermit, tmp_path):
    content = _netopen_debug_lines(
        run_wermit, tmp_path, "set host [2001:db8::1]:23, exit")
    assert "netopen host[2001:db8::1]" in content
    assert "netopen service requested[23]" in content


def test_set_host_malformed_bracket_fails_safely(run_wermit):
    result = run_wermit("set host [::1")
    assert "Malformed address literal" in result.stdout + result.stderr


def test_set_host_bare_v6_with_space_port_fails_safely(run_wermit):
    """A bare (unbracketed) address with colons of its own is not a
    valid SET HOST argument, even with a space-delimited port: HELP
    SET HOST requires square brackets around such addresses so
    Kermit can tell which colon separates the port. This must fail
    with a clear syntax error, not silently connect to the wrong
    host/port."""
    result = run_wermit("set host ::1 23")
    assert result.returncode != 0


def _rlogin_supported(run_wermit):
    result = run_wermit("help set host")
    assert_ok(result, "HELP SET HOST failed")
    return "/RLOGIN" in result.stdout


def test_rlogin_bracket_with_port_parses(run_wermit, tmp_path):
    """RLOGIN's second positional argument is a userid, not a port,
    so the only way to attach a non-default service to a bracketed
    IPv6 literal is the ":service" form. This must split the same
    way plain SET HOST does."""
    if not _rlogin_supported(run_wermit):
        pytest.skip("build has no RLOGIN support (not RLOGCODE)")
    content = _netopen_debug_lines(
        run_wermit, tmp_path, "rlogin [::1]:2105, exit")
    assert "netopen host[::1]" in content
    assert "netopen service requested[2105]" in content


def test_rlogin_plain_hostport_unaffected(run_wermit, tmp_path):
    if not _rlogin_supported(run_wermit):
        pytest.skip("build has no RLOGIN support (not RLOGCODE)")
    content = _netopen_debug_lines(
        run_wermit, tmp_path, "rlogin 127.0.0.1:2105, exit")
    assert "netopen host[127.0.0.1]" in content
    assert "netopen service requested[2105]" in content


def test_set_host_plain_hostport_unaffected(run_wermit, tmp_path):
    """Non-bracketed host:port parsing must be byte-for-byte the same
    as before bracket support was added."""
    content = _netopen_debug_lines(
        run_wermit, tmp_path, "set host 127.0.0.1:9, exit")
    assert "netopen host[127.0.0.1]" in content
    assert "netopen service requested[9]" in content


def test_set_host_url_scheme_with_bracket_and_port_parses(run_wermit, tmp_path):
    """A bracketed IPv6 literal inside a telnet:// URL, not just as a
    bare host:port argument, must also split correctly.  The URL
    parser's own internal host/port scan needs to be bracket-aware
    too, independently of the top-level bare-host case."""
    content = _netopen_debug_lines(
        run_wermit, tmp_path, "set host telnet://[::1]:2323/, exit")
    assert "netopen host[::1]" in content
    assert "netopen service requested[2323]" in content


def test_set_host_url_scheme_with_bracket_no_port_parses(run_wermit, tmp_path):
    content = _netopen_debug_lines(
        run_wermit, tmp_path,
        "set host telnet://[2001:db8::1]/, exit")
    assert "netopen host[2001:db8::1]" in content
    assert "netopen service requested[telnet]" in content


def test_set_host_url_scheme_with_user_and_bracket_parses(run_wermit, tmp_path):
    content = _netopen_debug_lines(
        run_wermit, tmp_path,
        "set host telnet://bob@[::1]:2323/, exit")
    assert "netopen host[::1]" in content
    assert "netopen service requested[2323]" in content


def test_set_host_url_scheme_malformed_bracket_fails_safely(run_wermit):
    result = run_wermit("set host telnet://[::1/")
    assert "Malformed address literal" in result.stdout + result.stderr


def test_set_host_url_scheme_unaffected(run_wermit, tmp_path):
    """Regular (non-bracketed) telnet:// URLs must still work exactly
    as before. Uses a numeric loopback address, not a real hostname,
    so this only exercises parsing and a fast local connection
    refusal, not a real DNS lookup/network round trip."""
    content = _netopen_debug_lines(
        run_wermit, tmp_path,
        "set host telnet://127.0.0.1:2323/, exit")
    assert "netopen host[127.0.0.1]" in content
    assert "netopen service requested[2323]" in content


# These use plain Python sockets as the "remote" side (not another
# wermit), since what's under test here is netopen()'s getaddrinfo()
# resolution and address-family selection, not protocol behavior.


def _ipv6_loopback_available():
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        s.bind(("::1", 0))
        s.close()
        return True
    except OSError:
        return False


def _v4_alias_available(addr):
    """Linux treats all of 127.0.0.0/8 as loopback out of the box, so
    127.0.0.2 is bindable with no setup.  macOS only brings up
    127.0.0.1 by default."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((addr, 0))
        s.close()
        return True
    except OSError:
        return False


class _OneShotListener:
    """A listening socket that accepts exactly one connection in a
    background thread and records the peer address, so a test can
    start it, run a wermit client against it, and then check whether
    (and from where) a connection actually arrived."""

    def __init__(self, family, host, port=0):
        self.sock = socket.socket(family, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if family == socket.AF_INET6:
            self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        self.sock.bind((host, port))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.peer = None
        self._accepted = threading.Event()
        self._thread = threading.Thread(target=self._accept, daemon=True)
        self._thread.start()

    def _accept(self):
        try:
            self.sock.settimeout(5)
            conn, peer = self.sock.accept()
            self.peer = peer
            conn.close()
        except OSError:
            pass
        finally:
            self._accepted.set()

    def wait(self, timeout=5):
        self._accepted.wait(timeout)
        return self.peer

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def test_address_family_ipv4_connects(run_wermit):
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")

    listener = _OneShotListener(socket.AF_INET, "127.0.0.1")
    try:
        result = run_wermit(
            "set tcp address-family ipv4, "
            "set tcp reverse-dns-lookup off, "
            f"set host 127.0.0.1 {listener.port} /raw-socket")
        assert_ok(result, "IPv4 connect failed")
        peer = listener.wait()
        assert peer is not None and peer[0] == "127.0.0.1"
    finally:
        listener.close()


def test_address_family_ipv6_connects(run_wermit):
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    if not _ipv6_loopback_available():
        pytest.skip("no IPv6 loopback available in this environment")

    listener = _OneShotListener(socket.AF_INET6, "::1")
    try:
        result = run_wermit(
            "set tcp address-family ipv6, "
            "set tcp reverse-dns-lookup off, "
            f"set host [::1]:{listener.port} /raw-socket")
        assert_ok(result, "IPv6 connect failed")
        peer = listener.wait()
        assert peer is not None and peer[0] == "::1"
    finally:
        listener.close()


def test_address_family_auto_connects_to_one_of_dual_stack(run_wermit):
    """AUTO against a name resolving to both A and AAAA (localhost)
    tries addresses in resolver order and stops at the first success.
    This doesn't assert which family wins, only that exactly
    one of the two listeners actually receives the connection."""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    if not _ipv6_loopback_available():
        pytest.skip("no IPv6 loopback available in this environment")

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    v4 = _OneShotListener(socket.AF_INET, "127.0.0.1", port=port)
    v6 = _OneShotListener(socket.AF_INET6, "::1", port=port)
    try:
        result = run_wermit(
            "set tcp address-family auto, "
            "set tcp reverse-dns-lookup off, "
            f"set host localhost {port} /raw-socket")
        assert_ok(result, "AUTO connect failed")
        v4_peer = v4.wait(timeout=2)
        v6_peer = v6.wait(timeout=2)
        assert (v4_peer is not None) != (v6_peer is not None), (
            "expected exactly one listener to receive the connection: "
            f"v4_peer={v4_peer} v6_peer={v6_peer}")
    finally:
        v4.close()
        v6.close()


def test_address_family_auto_falls_back_to_ipv4(run_wermit):
    """With no IPv6 listener at all, AUTO must fail over to IPv4
    rather than giving up after the IPv6 attempt is refused."""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    if not _ipv6_loopback_available():
        pytest.skip("no IPv6 loopback available in this environment")

    v4 = _OneShotListener(socket.AF_INET, "127.0.0.1")
    try:
        result = run_wermit(
            "set tcp address-family auto, "
            "set tcp reverse-dns-lookup off, "
            f"set host localhost {v4.port} /raw-socket")
        assert_ok(result, "AUTO fallback-to-IPv4 connect failed")
        peer = v4.wait()
        assert peer is not None and peer[0] == "127.0.0.1"
    finally:
        v4.close()


# local bind address (SET TCP ADDRESS)


def test_tcp_address_v4_binds_matching_candidate(run_wermit):
    """A matching-family SET TCP ADDRESS must actually be used as the
    connection's source address, not just silently accepted.  It's checked
    here by binding to the (non-default) loopback alias 127.0.0.2 and
    confirming the server sees the connection arrive from there."""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    if not _v4_alias_available("127.0.0.2"):
        pytest.skip("127.0.0.2 loopback alias not available "
                     "in this environment")

    listener = _OneShotListener(socket.AF_INET, "127.0.0.1")
    try:
        result = run_wermit(
            "set tcp address 127.0.0.2, "
            "set tcp address-family ipv4, "
            "set tcp reverse-dns-lookup off, "
            f"set host 127.0.0.1 {listener.port} /raw-socket")
        assert_ok(result, "IPv4 connect with SET TCP ADDRESS failed")
        peer = listener.wait()
        assert peer is not None and peer[0] == "127.0.0.2"
    finally:
        listener.close()


def test_tcp_address_family_mismatch_skips_bind_not_connection(run_wermit):
    """A SET TCP ADDRESS whose family doesn't match the candidate being
    tried (IPv4 address, IPv6 destination) must not block the
    connection.  It should just connect without forcing a source
    address for that candidate."""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    if not _ipv6_loopback_available():
        pytest.skip("no IPv6 loopback available in this environment")

    listener = _OneShotListener(socket.AF_INET6, "::1")
    try:
        result = run_wermit(
            "set tcp address 127.0.0.2, "
            "set tcp address-family ipv6, "
            "set tcp reverse-dns-lookup off, "
            f"set host [::1]:{listener.port} /raw-socket")
        assert_ok(result, "IPv6 connect with mismatched SET TCP ADDRESS "
                  "failed")
        peer = listener.wait()
        assert peer is not None and peer[0] == "::1"
    finally:
        listener.close()


def test_tcp_address_invalid_value_rejected(run_wermit):
    """SET TCP ADDRESS validates its argument as an IPv4 literal at set
    time and rejects anything (a soft command failure
    that does not abort the rest of the script), leaving any previous
    value untouched. A subsequent connection must still succeed, just
    without a forced source address."""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")

    listener = _OneShotListener(socket.AF_INET, "127.0.0.1")
    try:
        result = run_wermit(
            "set tcp address not-an-address, "
            "set tcp address-family ipv4, "
            "set tcp reverse-dns-lookup off, "
            f"set host 127.0.0.1 {listener.port} /raw-socket")
        assert_ok(result, "connect after rejected SET TCP ADDRESS failed")
        assert "requires an IPv4 address" in (
            result.stdout + result.stderr)
        peer = listener.wait()
        assert peer is not None
    finally:
        listener.close()


def test_tcp_address_rejects_ipv6_literal(run_wermit):
    """SET TCP ADDRESS is IPv4-only.  An IPv6 literal must be
    rejected"""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")

    result = run_wermit("set tcp address ::1, show tcp")
    assert_ok(result, "SET TCP ADDRESS ::1 command itself should not abort")
    assert "requires an IPv4 address" in (result.stdout + result.stderr)
    assert "address: (none)" in result.stdout


def test_tcp_address6_rejects_ipv4_literal(run_wermit):
    """SET TCP ADDRESS6 is IPv6-only; an IPv4 literal must be
    rejected."""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")

    result = run_wermit("set tcp address6 127.0.0.1, show tcp")
    assert_ok(result, "SET TCP ADDRESS6 127.0.0.1 command itself should "
              "not abort")
    assert "requires an IPv6 address" in (result.stdout + result.stderr)
    assert "address6: (none)" in result.stdout


def test_tcp_address_and_address6_are_independent(run_wermit):
    """SET TCP ADDRESS and SET TCP ADDRESS6 are separate settings: each
    can be set or cleared without disturbing the other, so both an
    IPv4 and an IPv6 local address can be pinned at the same time
    under SET TCP ADDRESS-FAMILY AUTO."""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")

    result = run_wermit(
        "set tcp address 127.0.0.1, set tcp address6 ::1, show tcp")
    assert_ok(result, "setting both ADDRESS and ADDRESS6 failed")
    assert "address: 127.0.0.1" in result.stdout
    assert "address6: ::1" in result.stdout

    result = run_wermit(
        "set tcp address 127.0.0.1, set tcp address6 ::1, "
        "set tcp address6, show tcp")
    assert_ok(result, "clearing ADDRESS6 alone failed")
    assert "address: 127.0.0.1" in result.stdout
    assert "address6: (none)" in result.stdout


def test_tcp_address6_v6_binds_matching_candidate(run_wermit):
    """SET TCP ADDRESS6 must actually be used as the connection's
    source address for an IPv6 candidate, mirroring
    test_tcp_address_v4_binds_matching_candidate."""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    if not _ipv6_loopback_available():
        pytest.skip("no IPv6 loopback available in this environment")

    listener = _OneShotListener(socket.AF_INET6, "::1")
    try:
        result = run_wermit(
            "set tcp address6 ::1, "
            "set tcp address-family ipv6, "
            "set tcp reverse-dns-lookup off, "
            f"set host [::1]:{listener.port} /raw-socket")
        assert_ok(result, "IPv6 connect with SET TCP ADDRESS6 failed")
        peer = listener.wait()
        assert peer is not None and peer[0] == "::1"
    finally:
        listener.close()


# ckgetfqhostname() / reverse-DNS lookup


def test_reverse_dns_lookup_over_ipv6(run_wermit):
    """SET TCP REVERSE-DNS-LOOKUP ON over an IPv6 connection must use
    getnameinfo() (not silently do nothing).
    It relies on ::1 reverse-resolving to "localhost", true on any
    normally configured POSIX system via /etc/hosts."""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    if not _ipv6_loopback_available():
        pytest.skip("no IPv6 loopback available in this environment")

    listener = _OneShotListener(socket.AF_INET6, "::1")
    try:
        result = run_wermit(
            "set tcp reverse-dns-lookup on, "
            "set tcp address-family ipv6, "
            f"set host [::1]:{listener.port} /raw-socket")
        assert_ok(result, "IPv6 connect with reverse-dns-lookup on failed")
        assert "localhost connected on port" in result.stdout
        assert listener.wait() is not None
    finally:
        listener.close()


# tcpsrv_open() dual-socket listener
#
# Unlike the earlier tests in this file, the "remote" side here is
# wermit itself, acting as an IKSD-style listener (SET HOST *), since
# what's under test is tcpsrv_open()'s own socket setup/accept/reverse
# -DNS code, not netopen()'s.


def _start_iksd_listener(spawn_wermit, port, log_path, extra_cmds="",
                          post_cmds=""):
    """Starts a bare SET HOST * listener (no /SERVER; this just
    needs an acceptable raw socket connection) and waits for it to report
    that it's listening.

    Returns the Popen object.  The caller is responsible for it exiting
    (SET HOST * accepts exactly one connection and returns) or being
    cleaned up (spawn_wermit's fixture teardown kills it if not)."""
    server_cmd = [
        "--unbuffered", "-H", "-Y", "-C",
        "set command more-prompting off, "
        "set tcp reverse-dns-lookup off, "
        f"{extra_cmds}set host * {port}{post_cmds}"
    ]
    log_fh = open(log_path, "w")
    proc = spawn_wermit(server_cmd, stdout=log_fh)

    deadline = time.monotonic() + 10
    ready = False
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        log_fh.flush()
        content = log_path.read_text(errors="replace")
        if "Waiting to Accept" in content:
            ready = True
            break
        time.sleep(0.05)
    if not ready:
        log_fh.flush()
        raise RuntimeError(
            "IKSD listener did not start listening (exit=%r); log:\n%s"
            % (proc.poll(), log_path.read_text(errors="replace")))
    return proc, log_fh


def test_iksd_listener_accepts_ipv4(run_wermit, spawn_wermit, get_free_port,
                                     tmp_path):
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")

    port = get_free_port()
    log_path = tmp_path / "srv4.log"
    proc, log_fh = _start_iksd_listener(spawn_wermit, port, log_path)
    try:
        result = run_wermit(
            "set tcp reverse-dns-lookup off, "
            f"set host 127.0.0.1 {port} /raw-socket, close")
        assert_ok(result, "IPv4 client failed to connect to IKSD listener")
        proc.wait(timeout=5)
        assert "127.0.0.1 connected" in log_path.read_text(errors="replace")
    finally:
        log_fh.close()


def test_iksd_listener_accepts_ipv6(run_wermit, spawn_wermit, get_free_port,
                                     tmp_path):
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    if not _ipv6_loopback_available():
        pytest.skip("no IPv6 loopback available in this environment")

    port = get_free_port()
    log_path = tmp_path / "srv6.log"
    proc, log_fh = _start_iksd_listener(spawn_wermit, port, log_path)
    try:
        result = run_wermit(
            "set tcp reverse-dns-lookup off, "
            f"set host [::1]:{port} /raw-socket, close")
        assert_ok(result, "IPv6 client failed to connect to IKSD listener")
        proc.wait(timeout=5)
        assert "::1 connected" in log_path.read_text(errors="replace")
    finally:
        log_fh.close()


def test_iksd_listener_reports_peer_ipv4(run_wermit, spawn_wermit,
                                          get_free_port, tmp_path):
    """\\v(line) (ckgetpeer()) must still resolve the peer's identity
    over the legacy IPv4 codepath after the CK_IPV6 rewrite."""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")

    port = get_free_port()
    log_path = tmp_path / "srv4peer.log"
    proc, log_fh = _start_iksd_listener(
        spawn_wermit, port, log_path,
        post_cmds=", echo PEER=[\\v(line)]")
    try:
        result = run_wermit(
            "set tcp reverse-dns-lookup off, "
            f"set host 127.0.0.1 {port} /raw-socket, close")
        assert_ok(result, "IPv4 client failed to connect to IKSD listener")
        proc.wait(timeout=5)
        content = log_path.read_text(errors="replace")
        assert "PEER=[localhost]" in content, content
    finally:
        log_fh.close()


def test_iksd_listener_reports_peer_ipv6(run_wermit, spawn_wermit,
                                          get_free_port, tmp_path):
    """Same as test_iksd_listener_reports_peer_ipv4, but over the new
    CK_IPV6 getnameinfo() codepath in ckgetpeer()."""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    if not _ipv6_loopback_available():
        pytest.skip("no IPv6 loopback available in this environment")

    port = get_free_port()
    log_path = tmp_path / "srv6peer.log"
    proc, log_fh = _start_iksd_listener(
        spawn_wermit, port, log_path,
        post_cmds=", echo PEER=[\\v(line)]")
    try:
        result = run_wermit(
            "set tcp reverse-dns-lookup off, "
            f"set host [::1]:{port} /raw-socket, close")
        assert_ok(result, "IPv6 client failed to connect to IKSD listener")
        proc.wait(timeout=5)
        content = log_path.read_text(errors="replace")
        assert "PEER=[localhost]" in content, content
    finally:
        log_fh.close()


def test_iksd_listener_dual_stack_binds_both(run_wermit, spawn_wermit,
                                              get_free_port, tmp_path):
    """AUTO (the default) must bind both an IPv4 and an IPv6 socket at
    once, not just whichever the resolver would have preferred.  The
    other two tests each connect via only one family, so neither of
    them alone proves both listeners are up simultaneously."""
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    if not _ipv6_loopback_available():
        pytest.skip("no IPv6 loopback available in this environment")

    port = get_free_port()
    log_path = tmp_path / "srvdual.log"
    proc, log_fh = _start_iksd_listener(spawn_wermit, port, log_path)
    try:
        content = log_path.read_text(errors="replace")
        assert "Binding socket to port" in content
        assert "Binding IPv6 socket to port" in content
    finally:
        log_fh.close()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                proc.kill()


def test_iksd_listener_address_family_ipv4_binds_only_v4(
        run_wermit, spawn_wermit, get_free_port, tmp_path):
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")

    port = get_free_port()
    log_path = tmp_path / "srvv4only.log"
    proc, log_fh = _start_iksd_listener(
        spawn_wermit, port, log_path,
        extra_cmds="set tcp address-family ipv4, ")
    try:
        content = log_path.read_text(errors="replace")
        assert "Binding socket to port" in content
        assert "Binding IPv6 socket to port" not in content
    finally:
        log_fh.close()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                proc.kill()

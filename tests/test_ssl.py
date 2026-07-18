import shutil
import time

import pytest

from conftest import assert_ok

pytestmark = pytest.mark.skipif(
    shutil.which("openssl") is None,
    reason="openssl CLI not found on PATH"
)


def test_ssl_first_exchange_is_not_delayed(server_dir, wermit_tcp_loopback,
                                            ssl_pki):
    """
    Regression test for a stall in the first Kermit protocol exchange
    after an /SSL (or /TLS) handshake completes.

    Right after the TLS 1.3 handshake's Finished message, the server
    proactively sends NewSessionTicket messages that are unrelated to
    application data. in_chk() (ckutio.c) checks SSL_pending() first
    (correctly 0, since nothing has been decrypted yet), but then falls
    back to a raw ioctl(fd, FIONREAD, ...) byte count, which sees the
    still-undecoded ticket bytes sitting in the kernel socket buffer and
    reports them as "data available". This makes ttflui()'s supposedly
    non-blocking input-flush (called from sipkt() just before sending the
    first packet) call SSL_read(), which consumes the ticket internally
    and then blocks in a real read() waiting for the next TLS record.
    That record is the peer's first Kermit packet, which the peer is in
    turn waiting to receive from us. Confirmed via gdb backtraces of both
    ends mid-stall and an openssl s_client -msg trace showing the
    server's two unsolicited NewSessionTicket messages.

    Fixed in ckutio.c's in_chk(): for an active SSL/TLS connection it now
    returns based on SSL_pending() alone instead of falling through to
    the raw FIONREAD byte count when SSL_pending() is 0.

    The above bug was fixed in 4b513721417d05b536847ed1159793ef18a4dc73.

    This same "first exchange" scenario also covers a second, unrelated
    bug fixed in ckctel.c (commit 0b9dc4f26d011f4a15574d31864fbd05c9b502a8,
    "Fix raw SSL/TLS connections waiting for Telnet"): tn_ini() disguised
    the connection as Telnet and, unless inserver was set, called
    tn_wait() to wait for Telnet negotiation responses that a raw-SSL
    peer will never send. On the server side, inserver was not yet
    true at the point tn_ini() runs during accept, so the server took
    the client-side branch and called tn_wait() anyway, which reads the
    connection byte by byte into its own private buffer. This silently
    swallows the client's first Kermit packet if it had already
    arrived, instead of letting the packet reach the protocol engine.
    That race depends on scheduling, so it reproduced rarely at idle
    but reliably (roughly 50-60% of runs) under sustained CPU load
    (verified with stress-ng --cpu 16). Reverting the ckctel.c fix and
    rerunning this exact test under that load reproduces the failure
    (fast, non-zero exit), confirming this is the regression test for
    it. See SSL_TEST_PLAN.md for the full writeup of both bugs.
    """
    session = wermit_tcp_loopback(
        server_dir,
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl verbose on, "
            "set authentication ssl rsa-cert-file "
            f"{ssl_pki['server_crt']}, "
            "set authentication ssl rsa-key-file "
            f"{ssl_pki['server_key']}"
        ),
    )

    start = time.monotonic()
    result = session.run_client(
        "remote pwd",
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl verbose on, "
            f"set authentication ssl verify-file {ssl_pki['ca_crt']}"
        ),
    )
    elapsed = time.monotonic() - start

    assert_ok(result)
    assert "[SSL - OK]" in result.stdout
    assert str(server_dir) in result.stdout

    session.wait_for_server_exit()

    assert elapsed < 3, (
        f"first post-handshake Kermit exchange over /SSL took "
        f"{elapsed:.1f}s (expected well under 3s). See the "
        "NewSessionTicket / in_chk() FIONREAD-fallback stall described "
        "in SSL_TEST_PLAN.md"
    )


@pytest.mark.parametrize("protocol", ["ssl", "tls"])
def test_ssl_happy_path(server_dir, wermit_tcp_loopback, ssl_pki, protocol):
    """
    Baseline positive case: the server presents a certificate signed by
    a CA the client trusts, the connection succeeds, and both ends
    report success, for both /SSL and /TLS.
    """
    tag = protocol.upper()

    session = wermit_tcp_loopback(
        server_dir,
        protocol=protocol,
        setup_cmds=(
            "set authentication ssl verbose on, "
            "set authentication ssl rsa-cert-file "
            f"{ssl_pki['server_crt']}, "
            "set authentication ssl rsa-key-file "
            f"{ssl_pki['server_key']}"
        ),
    )
    result = session.run_client(
        "remote pwd",
        protocol=protocol,
        setup_cmds=(
            "set authentication ssl verbose on, "
            f"set authentication ssl verify-file {ssl_pki['ca_crt']}"
        ),
    )
    server_rc = session.wait_for_server_exit()

    assert_ok(result)
    assert f"[{tag} - OK]" in result.stdout
    assert str(server_dir) in result.stdout
    assert f"[{tag} - OK]" in session.server_output()
    assert server_rc == 0


@pytest.mark.parametrize("direction", ["send", "get"])
def test_ssl_file_transfer(tmp_path, server_dir, wermit_tcp_loopback, ssl_pki,
                           direction):
    """
    A real file transfer completes correctly over an /SSL connection,
    proving the whole data channel is wrapped, not just the handshake
    and the first command.
    """
    client_dir = tmp_path / "client"
    client_dir.mkdir()

    content = bytes(range(256)) * 8
    file_name = "ssl_transfer.dat"
    if direction == "send":
        src_file = client_dir / file_name
        dest_file = server_dir / file_name
    else:
        src_file = server_dir / file_name
        dest_file = client_dir / file_name
    src_file.write_bytes(content)

    session = wermit_tcp_loopback(
        server_dir,
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl rsa-cert-file "
            f"{ssl_pki['server_crt']}, "
            "set authentication ssl rsa-key-file "
            f"{ssl_pki['server_key']}, "
            "set file type binary, set delay 0"
        ),
    )

    if direction == "send":
        client_cmd = f"set file type binary, set delay 0, send {src_file}"
    else:
        client_cmd = (
            f"set file type binary, set delay 0, cd {client_dir}, "
            f"get {file_name}"
        )

    result = session.run_client(
        client_cmd,
        protocol="ssl",
        setup_cmds=f"set authentication ssl verify-file {ssl_pki['ca_crt']}",
        timeout=20,
    )
    session.wait_for_server_exit()

    assert_ok(result)
    assert dest_file.exists()
    assert dest_file.read_bytes() == content


def test_ssl_untrusted_ca_rejected(server_dir, wermit_tcp_loopback, ssl_pki):
    """
    Default verify mode (peer-cert) rejects a server certificate whose
    issuing CA the client doesn't trust: client points verify-file at
    an unrelated CA that did not sign the server's certificate.
    """
    session = wermit_tcp_loopback(
        server_dir,
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl verbose on, "
            "set authentication ssl rsa-cert-file "
            f"{ssl_pki['server_crt']}, "
            "set authentication ssl rsa-key-file "
            f"{ssl_pki['server_key']}"
        ),
    )
    result = session.run_client(
        "remote pwd",
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl verbose on, "
            "set authentication ssl verify-file "
            f"{ssl_pki['untrusted_ca_crt']}"
        ),
    )
    session.wait_for_server_exit()

    assert "[SSL - FAILED]" in result.stdout
    assert str(server_dir) not in result.stdout
    assert "[SSL - SSL_accept error]" in session.server_output()


def test_ssl_verify_no_bypasses_trust(server_dir, wermit_tcp_loopback,
                                      ssl_pki):
    """
    SET AUTHENTICATION SSL VERIFY NO accepts a server certificate
    even when it's signed by a CA the client has no trust relationship
    with at all (the server here uses untrusted_server_crt, signed by
    a completely separate CA the client never references).
    """
    session = wermit_tcp_loopback(
        server_dir,
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl verbose on, "
            "set authentication ssl rsa-cert-file "
            f"{ssl_pki['untrusted_server_crt']}, "
            "set authentication ssl rsa-key-file "
            f"{ssl_pki['untrusted_server_key']}"
        ),
    )
    result = session.run_client(
        "remote pwd",
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl verbose on, "
            "set authentication ssl verify no"
        ),
    )
    session.wait_for_server_exit()

    assert_ok(result)
    assert "[SSL - OK]" in result.stdout
    assert str(server_dir) in result.stdout


@pytest.mark.parametrize("with_client_cert", [True, False],
                         ids=["with-cert", "without-cert"])
def test_ssl_mutual_tls(server_dir, wermit_tcp_loopback, ssl_pki,
                        with_client_cert):
    """
    When the server requires a client certificate
    (verify fail-if-no-peer-cert), a client without one is rejected,
    and a client with a CA-signed certificate succeeds, with the server
    reporting the client's commonName.
    """
    session = wermit_tcp_loopback(
        server_dir,
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl verbose on, "
            "set authentication ssl rsa-cert-file "
            f"{ssl_pki['server_crt']}, "
            "set authentication ssl rsa-key-file "
            f"{ssl_pki['server_key']}, "
            "set authentication ssl verify-file "
            f"{ssl_pki['ca_crt']}, "
            "set authentication ssl verify fail-if-no-peer-cert"
        ),
    )

    client_setup = (
        "set authentication ssl verbose on, "
        f"set authentication ssl verify-file {ssl_pki['ca_crt']}"
    )
    if with_client_cert:
        client_setup += (
            ", set authentication ssl rsa-cert-file "
            f"{ssl_pki['client_crt']}, "
            "set authentication ssl rsa-key-file "
            f"{ssl_pki['client_key']}"
        )

    result = session.run_client(
        "remote pwd", protocol="ssl", setup_cmds=client_setup,
    )
    session.wait_for_server_exit()

    if with_client_cert:
        assert_ok(result)
        assert str(server_dir) in result.stdout
        assert "commonName=test-client" in session.server_output()
    else:
        assert str(server_dir) not in result.stdout
        assert "[SSL - SSL_accept error]" in session.server_output()


def test_ssl_client_rejects_plaintext_server(server_dir, wermit_tcp_loopback,
                                             ssl_pki):
    """
    A client connecting with /SSL to a server that isn't SSL-configured
    at all fails the handshake cleanly instead of silently falling back
    to plaintext.
    """
    session = wermit_tcp_loopback(server_dir)  # plain, no /ssl or /tls

    result = session.run_client(
        "remote pwd",
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl verbose on, "
            f"set authentication ssl verify-file {ssl_pki['ca_crt']}"
        ),
    )
    session.wait_for_server_exit()

    assert "[SSL - FAILED]" in result.stdout
    assert str(server_dir) not in result.stdout


def test_ssl_expired_certificate_warns_but_is_accepted(
        server_dir, wermit_tcp_loopback, ssl_pki):
    """
    Documents current (surprising) behavior rather than asserting an
    ideal one: an expired server certificate is not outright rejected.
    C-Kermit prints a warning and asks the user to confirm; since stdin
    here isn't a terminal, it proceeds anyway instead of blocking or
    refusing, so the connection still succeeds. See SSL_TEST_PLAN.md.
    """
    session = wermit_tcp_loopback(
        server_dir,
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl verbose on, "
            "set authentication ssl rsa-cert-file "
            f"{ssl_pki['expired_crt']}, "
            "set authentication ssl rsa-key-file "
            f"{ssl_pki['expired_key']}"
        ),
    )
    result = session.run_client(
        "remote pwd",
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl verbose on, "
            f"set authentication ssl verify-file {ssl_pki['ca_crt']}"
        ),
    )
    session.wait_for_server_exit()

    assert "certificate has expired" in result.stdout
    assert_ok(result)
    assert str(server_dir) in result.stdout


@pytest.mark.parametrize("protocol,raw_flag_label", [
    ("ssl-raw", "SSL raw?"),
    ("tls-raw", "TLS raw?"),
])
def test_raw_protocol_switch_sets_matching_raw_flag(
        run_wermit, protocol, raw_flag_label):
    """
    Regression test for a bug: in ckuus7.c's SET HOST protocol-switch
    handling, the NP_TLS/NP_TLS_RAW case set
    tls_raw_flag = (protocol == NP_SSL_RAW) ? 1 : 0;
    That compares against the wrong constant, copy-pasted from the
    NP_SSL/NP_SSL_RAW case just above it, so /TLS-RAW never actually
    set tls_raw_flag. /SSL-RAW was unaffected, since it compares
    against the correct NP_SSL_RAW constant.

    ssl_raw_flag and tls_raw_flag are set while SET HOST parses its
    switches, before the actual connection attempt, so connecting to a
    guaranteed-closed local port (1) is enough to exercise the bug
    without needing a real server: the flag gets set (or not) either
    way, then SHOW AUTHENTICATION reports it. (Also required adding
    "SSL raw?"/"TLS raw?" lines to that SHOW output, since neither
    flag was observable through any existing command before this
    test.)

    Verifies the fix in 45954c319bf773ed48fb7ed2a40cda52d38846ea
    """
    result = run_wermit(
        "set tcp reverse-dns-lookup off, "
        f"set host localhost 1 /{protocol}, "
        "show authentication"
    )
    assert_ok(result)
    assert f"{raw_flag_label} yes" in result.stdout, (
        f"expected '{raw_flag_label} yes' for /{protocol}, got:\n"
        f"{result.stdout}"
    )

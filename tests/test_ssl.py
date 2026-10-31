import re
import shutil
import time

import pytest

from conftest import (
    _make_leaf, assert_ok, kermit_wait, PROTOCOL_STARTUP_OFF,
    require_closed_port, require_tls_version, scaled, ssl_client_setup_cmds,
    ssl_server_setup_cmds, start_tcp_listener, TELNET_REFUSE_KERMIT_CLAUSE,
    TelnetTlsClient,
)

pytestmark = pytest.mark.skipif(
    shutil.which("openssl") is None,
    reason="openssl CLI not found on PATH"
)


@pytest.fixture(autouse=True)
def _require_ssl(wermit_ssl_available):
    """Skip each item when wermit has no SSL/TLS support."""
    if not wermit_ssl_available:
        pytest.skip("wermit was not built with SSL/TLS support")


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
    peer will never send.  On the server side, inserver was not yet
    true at the point tn_ini() runs during accept, so the server called
    tn_wait() as well.  tn_wait() keeps a Kermit packet that arrives
    first in tn_wait_buf, and tn_push() hands it back.  The wait
    delays the first exchange until tn_wait() gives up.  The elapsed
    time check catches that delay.  See SSL_TEST_PLAN.md for the full
    writeup of both bugs.
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

    assert elapsed < 10, (
        f"first post-handshake Kermit exchange over /SSL took "
        f"{elapsed:.1f}s (expected well under 10s). See the "
        "NewSessionTicket / in_chk() FIONREAD-fallback stall described "
        "in SSL_TEST_PLAN.md"
    )


def test_ssl_packet_during_server_telnet_wait(server_dir, wermit_tcp_loopback,
                                             ssl_pki):
    """Verify a packet arriving during the server Telnet wait is kept.

    The client turns its wait off and sends its first packet at once.
    The server's tn_wait() reads that packet ahead.  tn_push() hands the
    data back through le_puts().  ttinl() must read it before the rest
    of the packet in mybuf.  Otherwise the server sees a packet with no
    start.  The exchange then stalls until the client's packet timeout.
    The client sets that timeout to 30 seconds.  A stall then takes 30
    seconds.  The exchange takes well under a second without one.
    """
    session = wermit_tcp_loopback(
        server_dir,
        protocol="ssl",
        setup_cmds=ssl_server_setup_cmds(ssl_pki),
    )

    start = time.monotonic()
    result = session.run_client(
        "remote pwd",
        protocol="ssl",
        setup_cmds=(
            "set telnet wait-for-negotiations off, "
            "set send timeout 30 fixed, "
            f"{ssl_client_setup_cmds(ssl_pki)}"
        ),
        timeout=scaled(60),
    )
    elapsed = time.monotonic() - start

    assert_ok(result)
    assert str(server_dir) in result.stdout
    session.wait_for_server_exit()
    assert elapsed < 10, (
        f"first exchange over /SSL took {elapsed:.1f}s (expected well "
        "under 10s).  The server lost the packet it read during tn_wait()."
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


def test_ssl_selfsigned_cert_rejected_by_default(server_dir,
                                                  wermit_tcp_loopback,
                                                  ssl_pki):
    """
    Default verify mode rejects a directly self-signed server
    certificate (X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT), the same as
    one signed by an untrusted CA.
    """
    session = wermit_tcp_loopback(
        server_dir,
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl verbose on, "
            "set authentication ssl rsa-cert-file "
            f"{ssl_pki['selfsigned_server_crt']}, "
            "set authentication ssl rsa-key-file "
            f"{ssl_pki['selfsigned_server_key']}"
        ),
    )
    result = session.run_client(
        "remote pwd",
        protocol="ssl",
        setup_cmds="set authentication ssl verbose on",
    )
    session.wait_for_server_exit()

    assert "[SSL - FAILED]" in result.stdout
    assert str(server_dir) not in result.stdout


def test_ssl_selfsigned_cert_accepted_with_verify_no(server_dir,
                                                      wermit_tcp_loopback,
                                                      ssl_pki):
    """
    SET AUTHENTICATION SSL VERIFY NO accepts a directly self-signed
    server certificate.
    """
    session = wermit_tcp_loopback(
        server_dir,
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl verbose on, "
            "set authentication ssl rsa-cert-file "
            f"{ssl_pki['selfsigned_server_crt']}, "
            "set authentication ssl rsa-key-file "
            f"{ssl_pki['selfsigned_server_key']}"
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
    closed local port (CLOSED_PORT) is enough to exercise the bug
    without needing a real server: the flag gets set (or not) either
    way, then SHOW AUTHENTICATION reports it. (Also required adding
    "SSL raw?"/"TLS raw?" lines to that SHOW output, since neither
    flag was observable through any existing command before this
    test.)

    Verifies the fix in 45954c319bf773ed48fb7ed2a40cda52d38846ea
    """
    port = require_closed_port("localhost")
    result = run_wermit(
        "set tcp reverse-dns-lookup off, "
        f"set host localhost {port} /{protocol}, "
        "show authentication"
    )
    assert_ok(result)
    assert f"{raw_flag_label} yes" in result.stdout, (
        f"expected '{raw_flag_label} yes' for /{protocol}, got:\n"
        f"{result.stdout}"
    )


def test_telnet_no_cert_completes_without_ssl_negotiation(
        server_dir, wermit_tcp_loopback):
    """
    Regression test for IKSD and SET HOST /SERVER offering Telnet
    START-TLS and the AUTHENTICATION option's SSL type by default
    whenever OpenSSL is loadable, even when neither side has a
    certificate configured. Both mechanisms perform a real SSL
    handshake directly on the connection outside Telnet framing, so a
    failed attempt cannot fall back to plaintext on the same
    connection. Before the fix, this either stalled the connection
    ("TLS failed: Disconnecting" followed by a failed reconnect
    attempt against this single-connection test server) or aborted it
    outright ("?Telnet Option negotiation error"), instead of simply
    proceeding as plain Telnet the way a certificate-less server
    should.
    """
    session = wermit_tcp_loopback(server_dir, protocol="telnet")
    result = session.run_client("remote pwd", protocol="telnet")

    assert_ok(result)
    assert "TLS failed" not in result.stdout
    assert "Reconnecting" not in result.stdout
    assert str(server_dir) in result.stdout


def test_telnet_no_cert_does_not_offer_ssl_authentication_type(
        server_dir, wermit_tcp_loopback):
    """
    Isolates the AUTHENTICATION-option half of the fix described in
    test_telnet_no_cert_completes_without_ssl_negotiation: with
    START-TLS itself refused on both ends, the AUTHENTICATION
    option's SSL type is the only remaining way to trigger the same
    failure (a raw SSL handshake attempted with no certificate to
    present).

    ck_tn_auth_request_ssl() (ckuath.c) is the server-side function
    that decides whether to advertise that type in its AUTHENTICATION
    SEND list. Before the fix in 11.0.503, it did so whenever OpenSSL was
    loadable, with no certificate check, so the client would select
    it, attempt the handshake, and fail the same way.
    """
    session = wermit_tcp_loopback(
        server_dir, protocol="telnet",
        setup_cmds="set telopt /server start-tls refused",
    )
    result = session.run_client(
        "remote pwd", protocol="telnet",
        setup_cmds="set telopt start-tls refused",
    )

    assert_ok(result)
    assert "Reconnecting" not in result.stdout
    assert str(server_dir) in result.stdout


def test_telnet_with_cert_negotiates_starttls_automatically(
        server_dir, wermit_tcp_loopback, ssl_pki):
    """
    Regression guard for the two fixes above: a server with a real
    certificate must still offer START-TLS by default over plain
    Telnet (no /SSL or /TLS protocol-switch needed), and the client
    must still complete the handshake automatically, so the
    certificate check that suppresses START-TLS/SSL-authentication
    when no certificate is present must not also suppress them when
    one is.
    """
    session = wermit_tcp_loopback(
        server_dir, protocol="telnet",
        setup_cmds=(
            f"{ssl_server_setup_cmds(ssl_pki)}, "
            f"{TELNET_REFUSE_KERMIT_CLAUSE}"
        ),
    )
    result = session.run_client(
        "remote pwd", protocol="telnet",
        setup_cmds=(
            f"{ssl_client_setup_cmds(ssl_pki)}, "
            f"{TELNET_REFUSE_KERMIT_CLAUSE}"
        ),
    )

    assert_ok(result)
    assert "[TLS -" in result.stdout
    assert "TLS failed" not in result.stdout
    assert str(server_dir) in result.stdout


def test_telnet_server_starttls_handshake_in_same_read(
        server_dir, wermit_tcp_loopback, ssl_pki):
    """Verify a Telnet server reads a ClientHello sent with FOLLOWS.

    The client sends SB START_TLS FOLLOWS and the ClientHello in one
    send, so the server can read both at once.  The handshake must
    still complete.
    """
    session = wermit_tcp_loopback(
        server_dir, protocol="telnet",
        setup_cmds=(
            f"{ssl_server_setup_cmds(ssl_pki)}, "
            f"{TELNET_REFUSE_KERMIT_CLAUSE}"
        ),
    )
    client = TelnetTlsClient(session.port, ssl_pki, [])
    try:
        assert client.wait_tls(timeout=15), session.server_output()
    finally:
        client.sock.close()


def test_ssl_ip_address_matches_certificate_ip_san(server_dir,
                                                   wermit_tcp_loopback,
                                                   ssl_pki):
    """
    Connecting to an IPv4 address matches a certificate's iPAddress
    subjectAltName for that address, without a hostname-mismatch
    warning. 127.0.0.1 contains zero bytes. The certificate also
    lists an IPv6 address that must not be read as IPv4.
    """
    session = wermit_tcp_loopback(
        server_dir,
        protocol="ssl",
        setup_cmds=(
            "set authentication ssl rsa-cert-file "
            f"{ssl_pki['ip_server_crt']}, "
            "set authentication ssl rsa-key-file "
            f"{ssl_pki['ip_server_key']}"
        ),
    )
    result = session.run_client(
        "remote pwd",
        protocol="ssl",
        host="127.0.0.1",
        setup_cmds=(
            "set authentication ssl verbose on, "
            f"set authentication ssl verify-file {ssl_pki['ca_crt']}"
        ),
    )
    session.wait_for_server_exit()

    assert_ok(result)
    assert "does not match" not in result.stdout, result.stdout
    assert "[SSL - OK]" in result.stdout, result.stdout
    listed = [line.split("IPAddr=")[1].strip()
              for line in result.stdout.splitlines()
              if "altSubjectName IPAddr=" in line]
    assert listed == ["192.168.255.254", "127.0.0.1"], result.stdout


def _write_empty_crl(ssl_pki, path):
    """Write a current, empty CRL signed by the trusted test CA."""
    import datetime
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    ca = x509.load_pem_x509_certificate(open(ssl_pki["ca_crt"], "rb").read())
    key = serialization.load_pem_private_key(
        open(ssl_pki["ca_key"], "rb").read(), password=None)
    now = datetime.datetime.now(datetime.timezone.utc)
    crl = (x509.CertificateRevocationListBuilder()
           .issuer_name(ca.subject)
           .last_update(now - datetime.timedelta(days=1))
           .next_update(now + datetime.timedelta(days=30))
           .sign(key, hashes.SHA256()))
    path.write_bytes(crl.public_bytes(serialization.Encoding.PEM))


def test_ssl_crl_file_check_succeeds(tmp_path, server_dir,
                                     wermit_tcp_loopback, ssl_pki):
    """Verify a connection with a CRL that covers the CA succeeds.

    ssl_verify_crl() looks the CRL up by the CA's subject and then by
    its issuer.  For a self-signed CA both give the same CRL.  The second
    lookup must use a fresh object.  A reused object shows only under
    AddressSanitizer.
    """
    pytest.importorskip("cryptography")
    crl = tmp_path / "ca.crl"
    _write_empty_crl(ssl_pki, crl)
    session = wermit_tcp_loopback(
        server_dir,
        protocol="tls",
        setup_cmds=(
            "set authentication ssl rsa-cert-file "
            f"{ssl_pki['server_crt']}, "
            "set authentication ssl rsa-key-file "
            f"{ssl_pki['server_key']}"
        ),
    )
    result = session.run_client(
        "remote pwd",
        protocol="tls",
        setup_cmds=(
            "set authentication ssl verbose on, "
            f"set authentication ssl verify-file {ssl_pki['ca_crt']}, "
            f"set authentication ssl crl-file {crl}"
        ),
    )
    session.wait_for_server_exit()
    assert_ok(result)
    assert "[TLS - OK]" in result.stdout


def _write_long_subject_expired_cert(ssl_pki, crt_path, key_path):
    """Write an expired server cert whose subject prints to about 5 KB."""
    import datetime
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    ca = x509.load_pem_x509_certificate(open(ssl_pki["ca_crt"], "rb").read())
    ca_key = serialization.load_pem_private_key(
        open(ssl_pki["ca_key"], "rb").read(), password=None)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    attrs = [x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME,
                                "unit-%02d-" % i + "u" * 54)
             for i in range(80)]
    attrs.append(x509.NameAttribute(NameOID.COMMON_NAME, "localhost"))
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name(attrs)).issuer_name(ca.subject)
            .public_key(key.public_key()).serial_number(4242)
            .not_valid_before(datetime.datetime(2019, 1, 1))
            .not_valid_after(datetime.datetime(2020, 1, 1))
            .add_extension(x509.SubjectAlternativeName(
                [x509.DNSName("localhost")]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    crt_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))


def test_ssl_expired_long_subject_certificate(tmp_path, server_dir,
                                              wermit_tcp_loopback, ssl_pki):
    """Verify an expired cert with a 5 KB subject is reported safely.

    The verify callback prints the subject and the expiry date into a
    4096-byte error buffer.  Text from the long subject must not fill
    it to the end.  The overflow shows only under AddressSanitizer.
    """
    pytest.importorskip("cryptography")
    crt, key = tmp_path / "long.crt", tmp_path / "long.key"
    _write_long_subject_expired_cert(ssl_pki, crt, key)
    session = wermit_tcp_loopback(
        server_dir,
        protocol="ssl",
        setup_cmds=(
            f"set authentication ssl rsa-cert-file {crt}, "
            f"set authentication ssl rsa-key-file {key}"
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
    assert "certificate has expired" in result.stdout, result.stdout[-800:]
    assert_ok(result)


def test_telnet_starttls_debug_prints_finished_messages(
        server_dir, wermit_tcp_loopback, ssl_pki):
    """Verify TLS DEBUG prints the finished messages within bounds.

    With TLS 1.3 and a SHA-384 suite the finished message is 48 bytes.
    The debug dump must read and write no more than its buffer holds.
    The overflow shows only under AddressSanitizer.
    """
    session = wermit_tcp_loopback(
        server_dir, protocol="telnet",
        setup_cmds=(
            f"{ssl_server_setup_cmds(ssl_pki)}, "
            f"{TELNET_REFUSE_KERMIT_CLAUSE}"
        ),
    )
    result = session.run_client(
        "remote pwd", protocol="telnet",
        setup_cmds=(
            f"{ssl_client_setup_cmds(ssl_pki)}, "
            "set authentication tls debug on, "
            f"{TELNET_REFUSE_KERMIT_CLAUSE}"
        ),
    )
    session.wait_for_server_exit()
    assert_ok(result)
    assert "TLS client finished:" in result.stdout, result.stdout[-800:]
    assert str(server_dir) in result.stdout


def _tls_send_after(ssl_pki, delay, data):
    """Start a one-connection TLS server that sends data after delay.

    Returns (port, thread, listening socket).
    """
    import socket
    import ssl
    import threading
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(ssl_pki["server_crt"], ssl_pki["server_key"])
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(scaled(20))

    def run():
        try:
            conn, _ = srv.accept()
            with ctx.wrap_socket(conn, server_side=True) as s:
                time.sleep(delay)
                s.sendall(data)
                time.sleep(2)
        except (OSError, ssl.SSLError):
            pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return srv.getsockname()[1], thread, srv


@pytest.mark.parametrize("protocol", ["ssl-raw", "tls-raw"])
@pytest.mark.parametrize("delay,instatus,low,high", [
    (2, 0, 1.5, 4.5),
    (12, 1, 3.5, 9),                    # INPUT counts whole seconds
])
@pytest.mark.slow
def test_tls_input_waits_for_timeout(run_wermit, ssl_pki, protocol,
                                     delay, instatus, low, high):
    """Verify INPUT on a TLS connection waits for its full timeout.

    INPUT reads in one-second steps.  The deadline alarm interrupts a
    blocking SSL_read(), and that must count as a timeout rather than
    an I/O error.  Data sent after 2 seconds satisfies "input 5".
    With no data, INPUT times out after 5 seconds with status 1.
    Kermit times INPUT alone.  Process start and the handshake are not
    part of the interval.
    """
    port, thread, srv = _tls_send_after(ssl_pki, delay, b"HELLO\r\n")
    try:
        result = run_wermit(
            f"set authentication ssl verify-file {ssl_pki['ca_crt']}, "
            f"set host localhost {port} /{protocol}, "
            ".t0 := \\v(ftime), input 5 HELLO, "
            "echo INSTATUS=\\v(instatus), "
            "echo DT=\\ffpsubtract(\\v(ftime),\\m(t0)), close",
            timeout=30)
    finally:
        srv.close()
    assert f"INSTATUS={instatus}" in result.stdout, result.stdout
    m = re.search(r"DT=([0-9.]+)", result.stdout)
    assert m, result.stdout
    assert low < float(m.group(1)) < high, result.stdout


@pytest.mark.parametrize("protocol", ["ssl-raw", "tls-raw"])
def test_tls_client_sends_sni(run_wermit, ssl_pki, protocol):
    """Verify SET HOST name port /TLS-RAW sends the host name as SNI."""
    import socket
    import ssl
    import threading
    names = []
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(ssl_pki["server_crt"], ssl_pki["server_key"])
    ctx.sni_callback = lambda sock, name, c: names.append(name)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(scaled(20))

    def run():
        try:
            conn, _ = srv.accept()
            with ctx.wrap_socket(conn, server_side=True) as s:
                s.sendall(b"HELLO\r\n")
                time.sleep(1)
        except (OSError, ssl.SSLError):
            pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        run_wermit(
            f"set authentication ssl verify-file {ssl_pki['ca_crt']}, "
            f"set host localhost {srv.getsockname()[1]} /{protocol}, "
            f"input {kermit_wait()} HELLO, close", timeout=30)
    finally:
        srv.close()
        thread.join(timeout=scaled(5))
    assert names == ["localhost"], names


@pytest.mark.parametrize("server,client", [
    ("ssl-raw", "ssl-raw"), ("tls-raw", "tls-raw"),
    ("ssl-raw", "ssl"), ("tls-raw", "tls"),
    ("ssl", "ssl-raw"), ("tls", "tls-raw"),
])
def test_tls_get_without_telnet_peer_is_prompt(wermit_path, ssl_pki,
                                               spawn_wermit, tmp_path,
                                               server, client):
    """Verify a GET over TLS finishes promptly when a side is raw.

    A raw SSL or TLS side sends no Telnet negotiation and does not
    wait for one in tn_wait().  The /SSL and /TLS sides wait for
    Telnet negotiation.  A wait on the raw side would lose the first
    Kermit packet and delay the GET by about 25 seconds.
    """
    import os
    import subprocess
    srvdir = tmp_path / "s"
    clidir = tmp_path / "c"
    srvdir.mkdir()
    clidir.mkdir()
    data = os.urandom(200000)
    (srvdir / "f.bin").write_bytes(data)
    port, srv, log_fh = start_tcp_listener(
        spawn_wermit,
        ["--unbuffered", "-H", "-Y", "-Q", "-C",
         f"{ssl_server_setup_cmds(ssl_pki)}, "
         f"set host * 0 /{server}, server, exit 0"],
        tmp_path / "server.log", "TLS server", cwd=srvdir)
    try:
        start = time.monotonic()
        result = subprocess.run(
            [wermit_path, "-H", "-Y", "-Q", "-C",
             f"{ssl_client_setup_cmds(ssl_pki)}, "
             f"set host localhost {port} /{client}, if fail exit 3, "
             "get f.bin, echo S=\\v(status), finish, close, exit 0"],
            cwd=clidir, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=scaled(60))
        elapsed = time.monotonic() - start
    finally:
        log_fh.close()
        srv.kill()
        srv.wait()
    assert "S=0" in result.stdout, result.stdout
    assert (clidir / "f.bin").read_bytes() == data
    assert elapsed < 10, elapsed


def test_ssl_server_setup_failure_closes_listeners(run_wermit, ssl_pki):
    """Verify a failed TLS server setup leaves no listening socket.

    A certificate file given as the key makes ssl_tn_init() fail.  With
    /SSL required, SET HOST * fails, and tcpsrv_open() must close both
    the IPv4 and the IPv6 listener.  The OpenSSL error appears on
    stdout.
    """
    import os
    import socket
    if not os.path.isdir("/proc/self/fd"):
        pytest.skip("no /proc/self/fd")
    try:
        socket.socket(socket.AF_INET6, socket.SOCK_STREAM).close()
    except OSError:
        pytest.skip("no IPv6")
    result = run_wermit(
        f"set authentication ssl rsa-cert-file {ssl_pki['server_crt']}, "
        f"set authentication ssl rsa-key-file {ssl_pki['server_crt']}, "
        "set host * 0 /ssl, echo H=\\v(status), "
        "run echo SOCKETS=$(ls -l /proc/$PPID/fd | grep -c socket)",
        timeout=30)
    assert "H=1" in result.stdout, result.stdout
    assert "SOCKETS=0" in result.stdout, result.stdout
    assert "?SSL/TLS initialization failed" in result.stdout, result.stdout
    assert "PrivateKey" in result.stdout, result.stdout


def test_ftp_tls_sends_sni(run_wermit, ssl_pki):
    """Verify FTP over TLS sends the server name as SNI.

    The server answers AUTH TLS, records the name in the handshake,
    and refuses the login.
    """
    import socket
    import ssl
    import threading
    names = []
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(ssl_pki["server_crt"], ssl_pki["server_key"])
    ctx.sni_callback = lambda sock, name, c: names.append(name)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(scaled(20))

    def run():
        try:
            conn, _ = srv.accept()
            conn.settimeout(scaled(10))
            conn.sendall(b"220 hi\r\n")
            f = conn.makefile("rb")
            line = f.readline()
            if not line.upper().startswith(b"AUTH"):
                return
            conn.sendall(b"234 go ahead\r\n")
            with ctx.wrap_socket(conn, server_side=True) as s:
                s.recv(4096)
                s.sendall(b"530 no\r\n")
                time.sleep(1)
        except (OSError, ssl.SSLError):
            pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        run_wermit(
            f"set authentication tls verify-file {ssl_pki['ca_crt']}, "
            f"ftp open localhost {srv.getsockname()[1]} /user:u "
            "/password:p, ftp close", timeout=30)
    finally:
        srv.close()
        thread.join(timeout=scaled(5))
    assert names == ["localhost"], names


@pytest.mark.parametrize("starttls", [True, False],
                         ids=["start-tls", "auth-ssl"])
def test_telnet_tls_checks_server_name(server_dir, wermit_tcp_loopback,
                                       ssl_pki, starttls):
    """Verify a Telnet client checks the server name in both TLS paths.

    The server's certificate names only IP addresses, and the client
    connects to "localhost".  START-TLS and the AUTHENTICATION option's
    SSL type each run a TLS handshake.  Each must warn that the name
    does not match.  Refusing START-TLS on both sides selects the
    AUTHENTICATION option.
    """
    server_setup = (
        "set authentication ssl rsa-cert-file "
        f"{ssl_pki['ip_server_crt']}, "
        "set authentication ssl rsa-key-file "
        f"{ssl_pki['ip_server_key']}, {TELNET_REFUSE_KERMIT_CLAUSE}")
    client_setup = (
        "set authentication ssl verbose on, "
        f"set authentication ssl verify-file {ssl_pki['ca_crt']}, "
        f"{TELNET_REFUSE_KERMIT_CLAUSE}")
    if not starttls:
        server_setup += ", set telopt /server start-tls refused"
        client_setup += ", set telopt start-tls refused"
    session = wermit_tcp_loopback(server_dir, protocol="telnet",
                                  setup_cmds=server_setup)
    result = session.run_client("remote pwd", protocol="telnet",
                                setup_cmds=client_setup)
    assert "[SSL - OK]" in result.stdout or "[TLS - " in result.stdout, (
        result.stdout)
    assert "does not match" in result.stdout, result.stdout


def test_telnet_auth_ssl_matching_server_name(server_dir,
                                              wermit_tcp_loopback, ssl_pki):
    """Verify AUTHENTICATION SSL accepts a certificate for the host.

    START-TLS is refused on both sides.  The server's certificate names
    localhost, and the client connects to localhost.  The session must
    complete with no name warning.
    """
    session = wermit_tcp_loopback(
        server_dir, protocol="telnet",
        setup_cmds=(f"{ssl_server_setup_cmds(ssl_pki)}, "
                    f"{TELNET_REFUSE_KERMIT_CLAUSE}, "
                    "set telopt /server start-tls refused"))
    result = session.run_client(
        "remote pwd", protocol="telnet",
        setup_cmds=("set authentication ssl verbose on, "
                    f"{ssl_client_setup_cmds(ssl_pki)}, "
                    f"{TELNET_REFUSE_KERMIT_CLAUSE}, "
                    "set telopt start-tls refused"))
    assert_ok(result)
    assert "Authenticating with SSL" in result.stdout, result.stdout
    assert "[SSL - OK]" in result.stdout, result.stdout
    assert "does not match" not in result.stdout, result.stdout
    assert str(server_dir) in result.stdout, result.stdout


@pytest.mark.parametrize("subj,san,host,match", [
    ("/CN=probe", "DNS:*", "localhost", False),
    ("/CN=probe", "DNS:l*", "localhost", False),
    ("/CN=probe", "DNS:*.*", "localhost", False),
    ("/CN=probe", "DNS:localhost", "localhost", True),
    ("/CN=probe", "DNS:LOCALHOST", "localhost", True),
    ("/CN=localhost", None, "localhost", True),
    ("/CN=probe", "IP:127.0.0.1", "127.0.0.1", True),
    ("/CN=probe", "IP:::1", "::1", True),
    ("/CN=probe", "IP:192.168.255.254", "127.0.0.1", False),
], ids=["bare-star", "partial-star", "star-dot-star", "exact",
        "case", "cn-only", "ipv4", "ipv6", "wrong-ip"])
def test_ssl_server_name_matching(server_dir, wermit_tcp_loopback, ssl_pki,
                                  tmp_path, subj, san, host, match):
    """Verify certificate names follow RFC 6125 matching.

    A wildcard matches only as the whole leftmost label of a name with
    more labels, so "*", "l*" and "*.*" do not match "localhost".  Case
    does not matter.  The commonName counts only without a dNSName.
    An address matches an iPAddress entry, IPv4 or IPv6.
    """
    try:
        key, crt = _make_leaf(tmp_path, "names", subj, ssl_pki["ca_key"],
                              ssl_pki["ca_crt"], san=san,
                              key=ssl_pki["server_key"])
    except AssertionError as e:
        # LibreSSL's openssl refuses to put "*" or "*.*" in a dNSName.
        if "bad object" in str(e):
            pytest.skip(f"this openssl will not issue {san}")
        raise
    session = wermit_tcp_loopback(
        server_dir, protocol="ssl",
        setup_cmds=f"set authentication ssl rsa-cert-file {crt}, "
                   f"set authentication ssl rsa-key-file {key}")
    result = session.run_client(
        "remote pwd", protocol="ssl", host=host,
        setup_cmds="set authentication ssl verbose on, "
                   f"set authentication ssl verify-file {ssl_pki['ca_crt']}")
    assert "[SSL - OK]" in result.stdout, result.stdout
    if match:
        assert "does not match" not in result.stdout, result.stdout
    else:
        assert "does not match" in result.stdout, result.stdout


def _permissive_openssl_conf(tmp_path):
    """Write an OpenSSL config that allows TLS 1.0 at security level 0.

    Return an environment dictionary with OPENSSL_CONF set to the file.
    """
    import os
    conf = tmp_path / "openssl.cnf"
    conf.write_text(
        "openssl_conf = init\n"
        "[init]\n"
        "ssl_conf = ssl_sect\n"
        "[ssl_sect]\n"
        "system_default = sys_sect\n"
        "[sys_sect]\n"
        "MinProtocol = TLSv1\n"
        "CipherString = DEFAULT@SECLEVEL=0\n")
    return dict(os.environ, OPENSSL_CONF=str(conf))


def _tls_handshake_server(ctx):
    """Start a one-connection TLS server that records the handshake.

    Return (port, thread, listening socket, results).  results holds
    "ok" or the handshake exception string.
    """
    import socket
    import ssl
    import threading
    results = []
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(scaled(20))

    def run():
        try:
            conn, _ = srv.accept()
            with ctx.wrap_socket(conn, server_side=True) as s:
                results.append("ok")
                s.settimeout(scaled(5))
                s.recv(100)
        except (OSError, ssl.SSLError) as e:
            if not results:
                results.append(repr(e))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return srv.getsockname()[1], thread, srv, results


def _run_wermit_env(wermit_path, cmds, env):
    """Run wermit with commands cmds and environment env."""
    import subprocess
    return subprocess.run(
        [wermit_path, "-H", "-Y", "-C",
         f"set command more-prompting off, {cmds}, exit"],
        env=env, capture_output=True, text=True, timeout=scaled(30),
        start_new_session=True)


def _single_version_server_ctx(ssl_pki, version):
    """Return a server context limited to one protocol version.

    Skip the test when this Python or OpenSSL cannot offer it.
    """
    import ssl
    require_tls_version(ssl_pki, version)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(ssl_pki["server_crt"], ssl_pki["server_key"])
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        ctx.minimum_version = getattr(ssl.TLSVersion, version)
        ctx.maximum_version = getattr(ssl.TLSVersion, version)
    except (ValueError, ssl.SSLError) as e:
        pytest.skip(f"server cannot offer only {version}: {e}")
    return ctx


# Each case is (server version, Kermit commands, permissive OpenSSL
# configuration, handshake succeeds).  The permissive configuration
# allows TLS 1.0.  So a refusal under it comes from C-Kermit.  The last
# case follows HELP SET AUTHENTICATION under the system configuration.
MIN_VERSION_CASES = [
    ("TLSv1_1", "", True, False),
    ("TLSv1_2", "", True, True),
    ("TLSv1_1", "set authentication ssl minimum-version tls1.1, ",
     True, True),
    ("TLSv1_2", "set authentication ssl minimum-version tls1.3, ",
     True, False),
    ("TLSv1_1", "set authentication ssl minimum-version tls1.0, "
     "set authentication ssl cipher-list HIGH:MEDIUM:!aNULL:@SECLEVEL=0, ",
     False, True),
]
MIN_VERSION_IDS = ["v1.1-default", "v1.2-default", "v1.1-min-1.1",
                   "v1.2-min-1.3", "v1.1-documented"]


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.parametrize("version,cmds,permissive,accepted",
                         MIN_VERSION_CASES, ids=MIN_VERSION_IDS)
@pytest.mark.parametrize("protocol", ["http", "ssl-raw", "tls-raw"])
def test_client_minimum_version(wermit_path, wermit_http_available,
                                ssl_pki, tmp_path, protocol, version,
                                cmds, permissive, accepted):
    """Verify a client refuses a version below MINIMUM-VERSION.

    The default minimum is TLS 1.2.  SET AUTHENTICATION SSL
    MINIMUM-VERSION lowers or raises it for HTTPS and raw SSL/TLS.
    """
    import os
    if protocol == "http" and not wermit_http_available:
        pytest.skip("wermit built without HTTP")
    ctx = _single_version_server_ctx(ssl_pki, version)
    port, thread, srv, results = _tls_handshake_server(ctx)
    if protocol == "http":
        connect = f"http open /tls localhost {port}"
        close = "http close"
    else:
        connect = f"set host localhost {port} /{protocol}"
        close = "close"
    env = (_permissive_openssl_conf(tmp_path) if permissive
           else dict(os.environ))
    try:
        result = _run_wermit_env(
            wermit_path,
            f"set authentication ssl verify-file {ssl_pki['ca_crt']}, "
            f"{cmds}{connect}, echo STATUS=\\v(status), {close}",
            env)
    finally:
        srv.close()
        thread.join(timeout=scaled(10))
    if accepted:
        assert results == ["ok"], (results, result.stdout)
        assert "STATUS=0" in result.stdout, result.stdout
    else:
        assert results and results[0] != "ok", (results, result.stdout)
        assert "STATUS=1" in result.stdout, result.stdout


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.parametrize("cmds,accepted", [
    ("", False),
    ("set authentication ssl minimum-version tls1.1, ", True),
])
def test_server_minimum_version(spawn_wermit, ssl_pki, tmp_path,
                                cmds, accepted):
    """Verify a raw TLS server refuses a version below MINIMUM-VERSION.

    The client offers only TLS 1.1.  The permissive OpenSSL
    configuration allows it.  So a refusal comes from C-Kermit.
    """
    import socket
    import ssl
    require_tls_version(ssl_pki, "TLSv1_1")
    cctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    cctx.check_hostname = False
    cctx.verify_mode = ssl.CERT_NONE
    try:
        cctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        cctx.minimum_version = ssl.TLSVersion.TLSv1_1
        cctx.maximum_version = ssl.TLSVersion.TLSv1_1
    except (ValueError, ssl.SSLError) as e:
        pytest.skip(f"client cannot offer only TLS 1.1: {e}")
    port, srv, log_fh = start_tcp_listener(
        spawn_wermit,
        ["--unbuffered", "-H", "-Y", "-Q", "-C",
         f"{ssl_server_setup_cmds(ssl_pki)}, {cmds}"
         "set host * 0 /tls-raw, exit 0"],
        tmp_path / "server.log", "TLS server",
        env=_permissive_openssl_conf(tmp_path))
    try:
        sock = socket.create_connection(("127.0.0.1", port),
                                        timeout=scaled(10))
        try:
            with cctx.wrap_socket(sock) as s:
                outcome = s.version()
        except (OSError, ssl.SSLError) as e:
            outcome = repr(e)
    finally:
        log_fh.close()
        srv.kill()
        srv.wait()
    if accepted:
        assert outcome == "TLSv1.1", outcome
    else:
        assert outcome != "TLSv1.1", outcome


@pytest.mark.parametrize("protocol", ["ssl-raw", "tls-raw"])
def test_tls_default_ciphers_exclude_anonymous(wermit_path, tmp_path,
                                               protocol):
    """Verify the default cipher list excludes anonymous suites.

    The server offers only anonymous suites at security level 0.  The
    permissive OpenSSL configuration allows them.  The handshake fails
    because DEFAULT_CIPHER_LIST excludes aNULL.
    """
    import ssl
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers("aNULL:@SECLEVEL=0")
    except (ValueError, ssl.SSLError) as e:
        pytest.skip(f"server cannot offer anonymous suites: {e}")
    port, thread, srv, results = _tls_handshake_server(ctx)
    try:
        result = _run_wermit_env(
            wermit_path,
            "set authentication ssl verify off, "
            f"set host 127.0.0.1 {port} /{protocol}, "
            "echo STATUS=\\v(status), close",
            _permissive_openssl_conf(tmp_path))
    finally:
        srv.close()
        thread.join(timeout=scaled(10))
    assert results and results[0] != "ok", (results, result.stdout)
    assert "STATUS=1" in result.stdout, result.stdout


def _show_auth_ciphers(wermit_path, cmds="", env=None):
    """Run SHOW AUTHENTICATION.  Return (Cipher list line, cipher names)."""
    import os
    result = _run_wermit_env(
        wermit_path, f"{cmds}show authentication",
        env if env is not None else dict(os.environ))
    lines = result.stdout.splitlines()
    start = next(i for i, x in enumerate(lines)
                 if x.startswith(" Cipher list:"))
    names = []
    for line in lines[start + 1:]:
        if not line.startswith("    "):
            break
        names.append(line.strip())
    return lines[start], names


def test_show_auth_lists_default_cipher_list(wermit_path):
    """Verify SHOW AUTHENTICATION lists ciphers from DEFAULT_CIPHER_LIST.

    The listing reflects the effective cipher list and excludes
    anonymous suites.
    """
    import os
    env = dict(os.environ)
    env.pop("SSL_CIPHER", None)
    header, names = _show_auth_ciphers(wermit_path, env=env)
    assert header.endswith("(default)"), header
    assert names, header
    assert not [n for n in names
                if n.startswith(("ADH-", "AECDH-"))], names


def test_show_auth_honors_ssl_cipher_variable(wermit_path):
    """Verify SHOW AUTHENTICATION lists the SSL_CIPHER list.

    SSL_CIPHER replaces the default for connections.  OpenSSL includes
    TLS 1.3 suites separately from the cipher list.
    """
    import os
    cipher = "ECDHE-RSA-AES128-GCM-SHA256"
    env = dict(os.environ, SSL_CIPHER=cipher)
    header, names = _show_auth_ciphers(wermit_path, env=env)
    assert header == f" Cipher list: {cipher} (from SSL_CIPHER)", header
    assert [n for n in names if not n.startswith("TLS_")] == [cipher], \
        names


def test_show_auth_reports_unmatched_cipher_list(wermit_path):
    """Verify SHOW AUTHENTICATION reports a list that names no cipher."""
    import os
    env = dict(os.environ, SSL_CIPHER="BOGUS")
    header, names = _show_auth_ciphers(wermit_path, env=env)
    assert header == " Cipher list: BOGUS (from SSL_CIPHER)", header
    assert names == ["(no cipher matches this list)"], names


def test_set_cipher_list_refuses_unmatched_list(wermit_path):
    """Verify SET AUTHENTICATION SSL CIPHER-LIST refuses an unmatched list."""
    import os
    result = _run_wermit_env(
        wermit_path, "set authentication ssl cipher-list BOGUS",
        dict(os.environ))
    assert '?No cipher matches "BOGUS"' in result.stdout, result.stdout
    assert result.returncode != 0, result.returncode


def test_set_cipher_list_empty_restores_default(wermit_path):
    """Verify an empty SET AUTHENTICATION SSL CIPHER-LIST restores default."""
    import os
    env = dict(os.environ)
    env.pop("SSL_CIPHER", None)
    header, _ = _show_auth_ciphers(
        wermit_path, "set authentication ssl cipher-list AES128-SHA, "
        "set authentication ssl cipher-list, ", env=env)
    assert header.endswith("(default)"), header


@pytest.mark.parametrize("protocol", ["http", "ssl-raw", "tls-raw"])
def test_connect_refuses_unmatched_cipher_list(wermit_path,
                                               wermit_http_available,
                                               protocol):
    """Verify a connection fails when its cipher list matches no cipher.

    SSL_CIPHER bypasses the check in SET AUTHENTICATION SSL
    CIPHER-LIST.  OpenSSL keeps its previous list when the new one
    matches nothing.  So Kermit refuses the connection.  The server sees
    no TLS handshake.
    """
    import os
    import socket
    import threading
    if protocol == "http" and not wermit_http_available:
        pytest.skip("wermit built without HTTP")
    received = []
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(scaled(20))

    def run():
        try:
            conn, _ = srv.accept()
            with conn:
                conn.settimeout(scaled(5))
                received.append(conn.recv(100))
        except OSError:
            pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    port = srv.getsockname()[1]
    if protocol == "http":
        connect, close = f"http open /tls 127.0.0.1 {port}", "http close"
    else:
        connect, close = f"set host 127.0.0.1 {port} /{protocol}", "close"
    try:
        result = _run_wermit_env(
            wermit_path, f"{connect}, echo STATUS=\\v(status), {close}",
            dict(os.environ, SSL_CIPHER="BOGUS"))
    finally:
        srv.close()
        thread.join(timeout=scaled(10))
    assert '?No cipher matches the cipher list "BOGUS"' in result.stdout, \
        result.stdout
    assert "STATUS=1" in result.stdout, result.stdout
    assert received in ([], [b""]), received


@pytest.fixture
def require_cert_file_env(wermit_path):
    """Skip unless the TLS library in wermit reads SSL_CERT_FILE.

    LibreSSL loads the compiled-in CA bundle and ignores the variable.
    """
    import subprocess
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-C",
         "set command more-prompting off, show features, exit"],
        capture_output=True, text=True, timeout=scaled(10))
    if "LibreSSL" in result.stdout:
        pytest.skip("LibreSSL ignores SSL_CERT_FILE")


def _default_ca_env(tmp_path, ca_file):
    """Return an environment that names ca_file as the default CA bundle.

    SSL_CERT_DIR names an empty directory so that the system certificates
    do not apply.
    """
    import os
    empty = tmp_path / "empty-certs"
    empty.mkdir(exist_ok=True)
    return dict(os.environ, SSL_CERT_FILE=str(ca_file),
                SSL_CERT_DIR=str(empty))


@pytest.mark.parametrize("trusted", [True, False],
                         ids=["trusted", "untrusted"])
@pytest.mark.parametrize("protocol", ["ssl-raw", "tls-raw"])
def test_tls_client_verifies_with_default_ca_locations(
        wermit_path, tmp_path, ssl_pki, require_cert_file_env, protocol,
        trusted):
    """Verify the client trusts the CA bundle named by SSL_CERT_FILE.

    The client sets no verify-file.  The server certificate verifies
    only when SSL_CERT_FILE names the CA that signed it.
    """
    import ssl
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(ssl_pki["server_crt"], ssl_pki["server_key"])
    port, thread, srv, results = _tls_handshake_server(ctx)
    ca = ssl_pki["ca_crt"] if trusted else ssl_pki["untrusted_ca_crt"]
    try:
        result = _run_wermit_env(
            wermit_path,
            "set authentication ssl verbose on, "
            f"set host localhost {port} /{protocol}, "
            "echo STATUS=\\v(status), close",
            _default_ca_env(tmp_path, ca))
    finally:
        srv.close()
        thread.join(timeout=scaled(10))
    if trusted:
        assert "STATUS=0" in result.stdout, result.stdout
        assert results == ["ok"], results
    else:
        assert "STATUS=1" in result.stdout, result.stdout
        assert results != ["ok"], results


def test_telnet_starttls_verifies_with_default_ca_locations(
        server_dir, tmp_path, wermit_path, wermit_tcp_loopback, ssl_pki,
        require_cert_file_env):
    """Verify a Telnet START-TLS client trusts the CA in SSL_CERT_FILE.

    The client sets no verify-file.  The handshake runs after Telnet
    negotiation starts, not when SET HOST opens the connection.
    """
    session = wermit_tcp_loopback(
        server_dir, protocol="telnet",
        setup_cmds=(
            f"{ssl_server_setup_cmds(ssl_pki)}, "
            f"{TELNET_REFUSE_KERMIT_CLAUSE}"
        ),
    )
    result = _run_wermit_env(
        wermit_path,
        f"{PROTOCOL_STARTUP_OFF}, "
        "set authentication ssl verbose on, "
        f"{TELNET_REFUSE_KERMIT_CLAUSE}, "
        f"set host localhost {session.port} /telnet, "
        "if failure exit 1, remote pwd, close",
        _default_ca_env(tmp_path, ssl_pki["ca_crt"]))
    session.wait_for_server_exit()
    assert "[TLS - OK]" in result.stdout, result.stdout
    assert str(server_dir) in result.stdout, result.stdout


def test_raw_socket_does_not_read_ca_bundle(wermit_path, tmp_path,
                                            require_cert_file_env):
    """Verify a /RAW-SOCKET connection leaves the CA bundle unread.

    SSL_CERT_FILE names a FIFO.  A thread opens it for writing until
    told to stop.  Each open returns only when a reader opens the FIFO.
    """
    import os
    import socket
    import threading
    fifo = tmp_path / "ca.fifo"
    os.mkfifo(fifo)
    opened = threading.Event()
    stop = threading.Event()

    def writer():
        while not stop.is_set():
            with open(fifo, "wb"):
                opened.set()

    thread = threading.Thread(target=writer, daemon=True)
    thread.start()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    try:
        result = _run_wermit_env(
            wermit_path,
            f"set host 127.0.0.1 {srv.getsockname()[1]} /raw-socket, "
            "echo STATUS=\\v(status), close",
            _default_ca_env(tmp_path, fifo))
        read = opened.is_set()
    finally:
        srv.close()
        stop.set()
        fd = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
        thread.join(timeout=scaled(10))
        os.close(fd)
    assert "STATUS=0" in result.stdout, result.stdout
    assert not read

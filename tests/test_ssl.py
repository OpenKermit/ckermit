import shutil
import time

import pytest

from conftest import (
    _make_leaf, assert_ok, ssl_client_setup_cmds, ssl_server_setup_cmds,
    TELNET_REFUSE_KERMIT_CLAUSE, TelnetTlsClient,
)

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
        run_wermit, wermit_ssl_available, protocol, raw_flag_label):
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

    The /ssl-raw and /tls-raw SET HOST switches only exist in a kermit built
    with SSL/TLS support, so this needs the same skip as anything depending on
    ssl_pki.
    """
    if not wermit_ssl_available:
        pytest.skip("wermit was not built with SSL/TLS support")
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


def test_telnet_no_cert_completes_without_ssl_negotiation(
        wermit_ssl_available, server_dir, wermit_tcp_loopback):
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
    if not wermit_ssl_available:
        pytest.skip("wermit was not built with SSL/TLS support")

    session = wermit_tcp_loopback(server_dir, protocol="telnet")
    result = session.run_client("remote pwd", protocol="telnet")

    assert_ok(result)
    assert "TLS failed" not in result.stdout
    assert "Reconnecting" not in result.stdout
    assert str(server_dir) in result.stdout


def test_telnet_no_cert_does_not_offer_ssl_authentication_type(
        wermit_ssl_available, server_dir, wermit_tcp_loopback):
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
    if not wermit_ssl_available:
        pytest.skip("wermit was not built with SSL/TLS support")

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
    srv.settimeout(20)

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
def test_tls_input_waits_for_timeout(run_wermit, ssl_pki, protocol,
                                     delay, instatus, low, high):
    """Verify INPUT on a TLS connection waits for its full timeout.

    INPUT reads in one-second steps.  The deadline alarm interrupts a
    blocking SSL_read(), and that must count as a timeout rather than
    an I/O error.  Data sent after 2 seconds satisfies "input 5".
    With no data, INPUT times out after 5 seconds with status 1.
    """
    port, thread, srv = _tls_send_after(ssl_pki, delay, b"HELLO\r\n")
    start = time.monotonic()
    try:
        result = run_wermit(
            f"set authentication ssl verify-file {ssl_pki['ca_crt']}, "
            f"set host localhost {port} /{protocol}, "
            "input 5 HELLO, "
            "echo INSTATUS=\\v(instatus), close", timeout=30)
    finally:
        elapsed = time.monotonic() - start
        srv.close()
    assert f"INSTATUS={instatus}" in result.stdout, result.stdout
    assert low < elapsed < high, elapsed


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
    srv.settimeout(20)

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
            "input 5 HELLO, close", timeout=30)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert names == ["localhost"], names


@pytest.mark.parametrize("server,client", [
    ("ssl-raw", "ssl-raw"), ("tls-raw", "tls-raw"),
    ("ssl-raw", "ssl"), ("tls-raw", "tls"),
    ("ssl", "ssl-raw"), ("tls", "tls-raw"),
])
def test_tls_get_without_telnet_peer_is_prompt(wermit_path, ssl_pki,
                                               get_free_port, tmp_path,
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
    port = get_free_port()
    srv = subprocess.Popen(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         f"{ssl_server_setup_cmds(ssl_pki)}, "
         f"set host * {port} /{server}, server, exit 0"],
        cwd=srvdir, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
    try:
        time.sleep(1)
        start = time.monotonic()
        result = subprocess.run(
            [wermit_path, "-H", "-Y", "-Q", "-C",
             f"{ssl_client_setup_cmds(ssl_pki)}, "
             f"set host localhost {port} /{client}, if fail exit 3, "
             "get f.bin, echo S=\\v(status), finish, close, exit 0"],
            cwd=clidir, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=60)
        elapsed = time.monotonic() - start
    finally:
        srv.kill()
        srv.wait()
    assert "S=0" in result.stdout, result.stdout
    assert (clidir / "f.bin").read_bytes() == data
    assert elapsed < 10, elapsed


def test_ssl_server_setup_failure_closes_listeners(run_wermit, ssl_pki,
                                                   get_free_port):
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
    port = get_free_port()
    result = run_wermit(
        f"set authentication ssl rsa-cert-file {ssl_pki['server_crt']}, "
        f"set authentication ssl rsa-key-file {ssl_pki['server_crt']}, "
        f"set host * {port} /ssl, echo H=\\v(status), "
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
    srv.settimeout(20)

    def run():
        try:
            conn, _ = srv.accept()
            conn.settimeout(10)
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
        thread.join(timeout=5)
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
                              ssl_pki["ca_crt"], san=san)
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

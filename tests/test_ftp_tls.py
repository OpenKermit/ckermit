"""Tests for FTP over TLS with protected data connections (ckcftp.c).

A scripted server answers AUTH TLS, then runs the rest of the control
connection over TLS.  With PROT P it wraps each data connection in TLS
as well.  The tests cover PBSZ negotiation in setpbsz() and protected
reads in secure_getbyte().
"""
import socket
import ssl
import threading

import pytest

from conftest import require_tls_version

REPLIES = {
    "USER": b"331 password please\r\n",
    "PASS": b"230 logged in\r\n",
    "SYST": b"215 UNIX Type: L8\r\n",
    "PWD": b'257 "/"\r\n',
    "FEAT": b"211 no features\r\n",
    "EPSV": b"500 not supported\r\n",
    "PBSZ": b"200 PBSZ=0\r\n",
    "PROT": b"200 ok\r\n",
    "SIZE": b"550 no\r\n",
    "MDTM": b"550 no\r\n",
    "QUIT": b"221 bye\r\n",
}


class TlsFtpPeer:
    """A one-connection FTP server that runs over TLS after AUTH TLS.

    files maps a name to the bytes RETR sends.  commands records each
    command received.
    """

    def __init__(self, ssl_pki, replies=None, files=None):
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(ssl_pki["server_crt"],
                                 ssl_pki["server_key"])
        self.table = dict(REPLIES)
        self.table.update(replies or {})
        self.files = files or {}
        self.commands = []
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.srv.settimeout(20)
        self.port = self.srv.getsockname()[1]
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _data(self, data_srv, protected, payload):
        """Accept the data connection and send payload."""
        conn, _ = data_srv.accept()
        data_srv.close()
        conn.settimeout(20)
        if protected:
            conn = self.ctx.wrap_socket(conn, server_side=True)
        with conn:
            conn.sendall(payload)
            if protected:
                try:
                    conn.unwrap()
                except (OSError, ssl.SSLError):
                    pass

    def _run(self):
        try:
            conn, _ = self.srv.accept()
        except OSError:
            return
        # Close the listener so a second connection fails.
        self.srv.close()
        conn.settimeout(20)
        protected = False
        data_srv = None
        try:
            conn.sendall(b"220 hi\r\n")
            f = conn.makefile("rb")
            line = f.readline().rstrip(b"\r\n")
            self.commands.append(line)
            if not line.upper().startswith(b"AUTH"):
                return
            conn.sendall(b"234 go ahead\r\n")
            conn = self.ctx.wrap_socket(conn, server_side=True)
            f = conn.makefile("rb")
            for line in f:
                line = line.rstrip(b"\r\n")
                self.commands.append(line)
                words = line.split(b" ", 1)
                verb = words[0].upper().decode("ascii", "replace")
                arg = words[1] if len(words) > 1 else b""
                if verb == "PROT":
                    protected = arg.upper() == b"P"
                if verb == "PASV":
                    data_srv = socket.socket(socket.AF_INET,
                                             socket.SOCK_STREAM)
                    data_srv.bind(("127.0.0.1", 0))
                    data_srv.listen(1)
                    data_srv.settimeout(20)
                    p = data_srv.getsockname()[1]
                    conn.sendall(b"227 Entering Passive Mode "
                                 b"(127,0,0,1,%d,%d)\r\n"
                                 % (p >> 8, p & 255))
                    continue
                if verb == "RETR" and data_srv:
                    name = arg.decode()
                    if name not in self.files:
                        conn.sendall(b"550 no such file\r\n")
                        continue
                    conn.sendall(b"150 sending\r\n")
                    self._data(data_srv, protected, self.files[name])
                    data_srv = None
                    conn.sendall(b"226 done\r\n")
                    continue
                conn.sendall(self.table.get(verb, b"200 ok\r\n"))
                if verb == "QUIT":
                    break
        except (OSError, ssl.SSLError):
            pass
        finally:
            conn.close()

    def close(self):
        """Close the listener and wait for the server thread."""
        self.srv.close()
        self.thread.join(timeout=10)

    def sent(self, verb):
        """Return the arguments of each command with the given verb."""
        return [ln.split(b" ", 1)[1] if b" " in ln else b""
                for ln in self.commands
                if ln.split(b" ")[0].upper() == verb.encode()]


def _session(run_wermit, ssl_pki, peer, commands, cwd, setup=()):
    """Run commands over a TLS FTP session and return the result.

    setup holds commands that run before FTP OPEN.
    """
    try:
        result = run_wermit(", ".join([
            f"cd {cwd}",
            f"set authentication tls verify-file {ssl_pki['ca_crt']}",
            *setup,
            f"ftp open localhost {peer.port} /user:u /password:p",
            *commands, "ftp close", "exit"]), timeout=60)
    finally:
        peer.close()
    assert result.returncode >= 0, result.returncode
    return result


@pytest.mark.parametrize("size", [0, 1, 4095, 100000])
def test_ftp_tls_protected_get(run_wermit, ssl_pki, tmp_path, size):
    """Verify GET reads a TLS-protected data connection intact."""
    data = bytes(range(256)) * (size // 256) + bytes(size % 256)
    peer = TlsFtpPeer(ssl_pki, files={"f.bin": data})
    result = _session(run_wermit, ssl_pki, peer,
                      ["ftp get f.bin", "echo S=\\v(status)"], tmp_path)
    assert "S=0" in result.stdout, result.stdout
    assert peer.sent("PBSZ") == [b"0"], peer.commands
    assert peer.sent("PROT") == [b"P"], peer.commands
    assert (tmp_path / "f.bin").read_bytes() == data


def test_ftp_tls_clear_data(run_wermit, ssl_pki, tmp_path):
    """Verify GET reads a clear data connection after PROT C."""
    data = b"clear data\n" * 100
    peer = TlsFtpPeer(ssl_pki, files={"f.txt": data})
    result = _session(run_wermit, ssl_pki, peer,
                      ["set ftp data-protection-level clear",
                       "ftp get /binary f.txt", "echo S=\\v(status)"],
                      tmp_path)
    assert "S=0" in result.stdout, result.stdout
    assert b"C" in peer.sent("PROT"), peer.commands
    assert (tmp_path / "f.txt").read_bytes() == data


@pytest.mark.parametrize("reply", [
    b"200 PBSZ=0\r\n",
    b"200 PBSZ=99999999999999999999999\r\n",
    b"200 PBSZ=-5\r\n",
    b"200 PBSZ=\r\n",
    b"200 ok\r\n",
])
def test_ftp_tls_pbsz_replies(run_wermit, ssl_pki, tmp_path, reply):
    """Verify any PBSZ size the server returns leaves GET working."""
    data = b"x" * 50000
    peer = TlsFtpPeer(ssl_pki, {"PBSZ": reply}, files={"f.bin": data})
    result = _session(run_wermit, ssl_pki, peer,
                      ["ftp get f.bin", "echo S=\\v(status)"], tmp_path)
    assert "S=0" in result.stdout, result.stdout
    assert (tmp_path / "f.bin").read_bytes() == data


@pytest.mark.parametrize("reply", [
    b"200 PBSZ=0" + b"A" * 20000 + b"\r\n",
    b"".join(b"200-" + b"B" * 1000 + b"\r\n" for _ in range(20)) +
    b"200 PBSZ=0\r\n",
], ids=["one-line", "multi-line"])
def test_ftp_tls_long_pbsz_reply(run_wermit, ssl_pki, tmp_path, reply):
    """Verify a PBSZ reply longer than reply_buf does not overrun it.

    getreply() copies the PBSZ reply into reply_buf (10240 bytes).  The
    copy must stop at the end of the buffer, for one long line and for
    many continuation lines.
    """
    data = b"x" * 5000
    peer = TlsFtpPeer(ssl_pki, {"PBSZ": reply}, files={"f.bin": data})
    result = _session(run_wermit, ssl_pki, peer,
                      ["ftp get f.bin", "echo S=\\v(status)"], tmp_path)
    assert "AddressSanitizer" not in result.stderr, result.stderr[-2000:]
    assert "S=0" in result.stdout, result.stdout
    assert (tmp_path / "f.bin").read_bytes() == data


def test_ftp_tls_pbsz_refused(run_wermit, ssl_pki, tmp_path):
    """Verify a refused PBSZ ends the session with a message."""
    peer = TlsFtpPeer(ssl_pki, {"PBSZ": b"500 no\r\n"})
    result = _session(run_wermit, ssl_pki, peer,
                      ["echo C=\\v(ftp_connected)"], tmp_path)
    assert "Unable to negotiate PROT buffer size" in result.stdout, \
        result.stdout
    assert "C=0" in result.stdout, result.stdout


def test_ftp_tls_refuses_unmatched_cipher_list(run_wermit, ssl_pki,
                                               tmp_path, monkeypatch):
    """Verify AUTH TLS fails when the cipher list matches no cipher.

    SSL_CIPHER bypasses the check in SET AUTHENTICATION SSL CIPHER-LIST.
    Kermit refuses the TLS session and sends no USER.
    """
    monkeypatch.setenv("SSL_CIPHER", "BOGUS")
    peer = TlsFtpPeer(ssl_pki)
    result = _session(run_wermit, ssl_pki, peer, [], tmp_path)
    assert '?No cipher matches the cipher list "BOGUS"' in result.stdout, \
        result.stdout
    assert not peer.sent("USER"), peer.commands


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.parametrize("cmds,accepted", [
    ([], False),
    (["set authentication ssl minimum-version tls1.1"], True),
])
def test_ftp_tls_minimum_version(run_wermit, ssl_pki, tmp_path,
                                 monkeypatch, cmds, accepted):
    """Verify FTP refuses a version below MINIMUM-VERSION.

    The server offers only TLS 1.1.  The OpenSSL configuration allows
    TLS 1.0 at security level 0.  So a refusal comes from C-Kermit.
    """
    require_tls_version(ssl_pki, "TLSv1_1")
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
    monkeypatch.setenv("OPENSSL_CONF", str(conf))
    peer = TlsFtpPeer(ssl_pki)
    try:
        peer.ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        peer.ctx.minimum_version = ssl.TLSVersion.TLSv1_1
        peer.ctx.maximum_version = ssl.TLSVersion.TLSv1_1
    except (ValueError, ssl.SSLError) as e:
        peer.close()
        pytest.skip(f"server cannot offer only TLS 1.1: {e}")
    _session(run_wermit, ssl_pki, peer, [], tmp_path, setup=cmds)
    assert bool(peer.sent("USER")) == accepted, peer.commands


class FallbackFtpPeer:
    """An FTP server that accepts AUTH and then a fallback connection.

    The first connection answers AUTH TLS with 234 and starts TLS with
    the certificate in crt and key.  Later connections refuse AUTH and
    accept any login in the clear.  commands holds (connection number,
    command) pairs.
    """

    def __init__(self, crt, key):
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(crt, key)
        self.commands = []
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(4)
        self.srv.settimeout(20)
        self.port = self.srv.getsockname()[1]
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _serve(self, n, conn):
        conn.settimeout(10)
        conn.sendall(b"220 hi\r\n")
        for line in conn.makefile("rb"):
            line = line.rstrip(b"\r\n")
            self.commands.append((n, line))
            verb = line.split(b" ")[0].upper()
            if verb == b"AUTH" and n == 0:
                conn.sendall(b"234 go ahead\r\n")
                with self.ctx.wrap_socket(conn, server_side=True) as s:
                    s.recv(100)
                return
            conn.sendall({b"AUTH": b"500 no\r\n",
                          b"USER": b"331 password please\r\n",
                          b"PASS": b"230 logged in\r\n",
                          b"QUIT": b"221 bye\r\n"}.get(verb,
                                                       b"200 ok\r\n"))
            if verb == b"QUIT":
                return

    def _run(self):
        for n in range(3):
            try:
                conn, _ = self.srv.accept()
            except OSError:
                return
            try:
                with conn:
                    self._serve(n, conn)
            except (OSError, ssl.SSLError):
                pass

    def close(self):
        """Close the listener and wait for the server thread.

        shutdown() wakes accept() in the server thread.
        """
        try:
            self.srv.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.srv.close()
        self.thread.join(timeout=15)


@pytest.mark.parametrize("fallback", ["off", "on"])
@pytest.mark.parametrize("cause", ["cipher-list", "certificate"])
def test_ftp_tls_failure_fallback(run_wermit, ssl_pki, tmp_path,
                                  monkeypatch, cause, fallback):
    """Verify a failed TLS session after AUTH TLS ends FTP OPEN.

    The server accepts AUTH TLS.  The TLS session then fails due to an
    unmatched cipher list or an untrusted certificate.  With FTP
    TLS-FALLBACK OFF, Kermit opens no second connection and sends no
    password.  With ON, Kermit reconnects and logs in without
    encryption.
    """
    if cause == "cipher-list":
        monkeypatch.setenv("SSL_CIPHER", "BOGUS")
        crt, key = ssl_pki["server_crt"], ssl_pki["server_key"]
    else:
        crt = ssl_pki["untrusted_server_crt"]
        key = ssl_pki["untrusted_server_key"]
    peer = FallbackFtpPeer(crt, key)
    try:
        result = run_wermit(", ".join([
            f"set authentication tls verify-file {ssl_pki['ca_crt']}",
            f"set ftp tls-fallback {fallback}",
            f"ftp open localhost {peer.port} /user:u /password:secret",
            "echo S=\\v(status)", "exit"]), timeout=60)
    finally:
        peer.close()
    assert peer.commands[0] == (0, b"AUTH TLS"), peer.commands
    if fallback == "off":
        assert "?Not logging in without TLS" in result.stdout, \
            result.stdout
        assert "S=1" in result.stdout, result.stdout
        assert len(peer.commands) == 1, peer.commands
    else:
        assert (1, b"PASS secret") in peer.commands, peer.commands
        assert "S=0" in result.stdout, result.stdout

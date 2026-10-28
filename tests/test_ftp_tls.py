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


def _session(run_wermit, ssl_pki, peer, commands, cwd):
    """Run commands over a TLS FTP session and return the result."""
    try:
        result = run_wermit(", ".join([
            f"cd {cwd}",
            f"set authentication tls verify-file {ssl_pki['ca_crt']}",
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


def test_ftp_tls_pbsz_refused(run_wermit, ssl_pki, tmp_path):
    """Verify a refused PBSZ ends the session with a message."""
    peer = TlsFtpPeer(ssl_pki, {"PBSZ": b"500 no\r\n"})
    result = _session(run_wermit, ssl_pki, peer,
                      ["echo C=\\v(ftp_connected)"], tmp_path)
    assert "Unable to negotiate PROT buffer size" in result.stdout, \
        result.stdout
    assert "C=0" in result.stdout, result.stdout

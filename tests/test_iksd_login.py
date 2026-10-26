"""Tests for IKSD login and the session database state (ckufio.c,
ckuusx.c).

The IKSD runs as the current user on an accepted loopback socket, as
inetd would start it.  fakeshadow.so supplies the shadow entry and the
PAM checks for that user with a known password, so no root access is
needed.  A wermit client connects over Telnet, answers the password
prompt and sends server commands.
"""
import getpass
import os
import platform
import shutil
import socket
import struct
import subprocess
import threading

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PASSWORD = "s3cret-test"


def _elf_info(path):
    """Return (machine, dynamic) for the ELF file at path.

    machine is the e_machine field.  dynamic is True if the file has a
    PT_INTERP program header.  A program without one is statically
    linked and ignores LD_PRELOAD.
    """
    with open(path, "rb") as f:
        data = f.read(65536)
    order = "<" if data[5] == 1 else ">"
    machine, = struct.unpack_from(order + "H", data, 18)
    if data[4] == 2:                    # ELFCLASS64
        phoff, = struct.unpack_from(order + "Q", data, 32)
        phentsize, phnum = struct.unpack_from(order + "HH", data, 54)
    else:
        phoff, = struct.unpack_from(order + "I", data, 28)
        phentsize, phnum = struct.unpack_from(order + "HH", data, 42)
    dynamic = False
    for i in range(phnum):
        off = phoff + i * phentsize
        if off + 4 > len(data):
            break
        p_type, = struct.unpack_from(order + "I", data, off)
        if p_type == 3:
            dynamic = True
    return machine, dynamic


@pytest.fixture(scope="session")
def fakeshadow(tmp_path_factory, wermit_path, wermit_sanitized):
    """Build fakeshadow.so and return its path, or skip.

    Skips if wermit is statically linked or built for a different
    machine than cc, since LD_PRELOAD cannot load fakeshadow.so then.
    """
    if wermit_sanitized:
        pytest.skip("LD_PRELOAD does not run with a sanitizer build")
    if platform.system() != "Linux" or not shutil.which("cc"):
        pytest.skip("fakeshadow needs Linux and cc")
    machine, dynamic = _elf_info(wermit_path)
    if not dynamic:
        pytest.skip("LD_PRELOAD does not run with a static wermit")
    lib = tmp_path_factory.mktemp("fakeshadow") / "fakeshadow.so"
    result = subprocess.run(
        ["cc", "-O1", "-shared", "-fPIC", "-o", str(lib),
         os.path.join(HERE, "fakeshadow.c"), "-lcrypt", "-lpam", "-ldl"],
        capture_output=True, text=True)
    if result.returncode != 0:
        pytest.skip("cannot build fakeshadow.so: " + result.stderr[-200:])
    if _elf_info(str(lib))[0] != machine:
        pytest.skip("fakeshadow.so and wermit differ in machine type")
    return str(lib)


def _has_iksd(wermit_path):
    """Return True if this build has IKSD login support."""
    result = subprocess.run([wermit_path, "--help"], capture_output=True,
                            text=True, stdin=subprocess.DEVNULL, timeout=10)
    return "--userfile" in result.stdout


def _iksd_session(wermit_path, fakeshadow, tmp_path, client_cmds,
                  userfile_lines=None, initfile=None, home=None,
                  client_setup="", login=None, client=None, alias=None):
    """Run a client session against an IKSD and return the client result.

    The IKSD writes debug.log in tmp_path.  userfile_lines, when given,
    are the forbidden-user file.  initfile is the IKSD configuration
    file, and home the user's home directory.  client_setup runs on the client
    before it connects.  login replaces the client's password exchange.
    client, when given, replaces the wermit client.  It takes the port
    and returns the result.  alias is a second name for the user.
    """
    if not _has_iksd(wermit_path):
        pytest.skip("build has no IKSD login support")
    user = getpass.getuser()
    link = tmp_path / "iksd"
    os.symlink(wermit_path, str(link))
    args = [str(link), "-H", "-d", "--dbfile=" + str(tmp_path / "iksd.db")]
    if userfile_lines is not None:
        users = tmp_path / "users"
        users.write_text("".join(ln + "\n" for ln in userfile_lines))
        args.append("--userfile:" + str(users))
    env = dict(os.environ, LD_PRELOAD=fakeshadow, FAKESHADOW_USER=user,
               FAKESHADOW_PASS=PASSWORD)
    if initfile is not None:
        env["FAKESHADOW_IKSDCONF"] = str(initfile)
    if home is not None:
        env["FAKESHADOW_HOME"] = str(home)
    if alias is not None:
        env["FAKESHADOW_ALIAS"] = alias
    if login is None:
        login = (f"input 10 Password:, output {PASSWORD}\\13, "
                 "input 10 IKSD>, if success echo LOGGEDIN")
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(20)
    procs = []

    def serve():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        procs.append(subprocess.Popen(
            args, stdin=conn.fileno(), stdout=conn.fileno(),
            stderr=subprocess.DEVNULL, close_fds=True, cwd=tmp_path,
            env=env))
        conn.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        if client is not None:
            return client(srv.getsockname()[1])
        result = subprocess.run(
            [wermit_path, "-H", "-Y", "-C",
             f"set command more-prompting off, {client_setup}"
             f"set host 127.0.0.1 {srv.getsockname()[1]}, "
             f"{login}, {client_cmds}, exit"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=60)
    finally:
        srv.close()
        thread.join(timeout=5)
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
    return result


def _debug_log(tmp_path):
    """Return the IKSD debug log text."""
    return (tmp_path / "debug.log").read_text(errors="replace")


def test_iksd_login(wermit_path, fakeshadow, tmp_path):
    """Verify a user logs in to the IKSD with the right password."""
    result = _iksd_session(wermit_path, fakeshadow, tmp_path, "echo DONE")
    assert "LOGGEDIN" in result.stdout, result.stdout


def _tls_login(wermit_path, fakeshadow, tmp_path, ssl_pki, listed,
               method="start-tls"):
    """Log in with a client certificate over TLS.

    listed is the certificate the user's ~/.tlslogin holds.  method is
    "start-tls" for Telnet START_TLS, or "auth-ssl" for Telnet AUTH SSL
    with START_TLS refused.  Returns the client result.
    """
    refuse = ("set telopt start-tls refused, "
              if method == "auth-ssl" else "")
    home = tmp_path / "home"
    home.mkdir()
    (home / ".tlslogin").write_bytes(open(listed, "rb").read())
    init = tmp_path / "iksd.ini"
    init.write_text(
        f"set authentication ssl rsa-cert-file {ssl_pki['server_crt']}\n"
        f"set authentication ssl rsa-key-file {ssl_pki['server_key']}\n"
        f"set authentication ssl verify-file {ssl_pki['ca_crt']}\n"
        "set authentication ssl verify peer-cert\n")
    return _iksd_session(
        wermit_path, fakeshadow, tmp_path, "echo DONE",
        initfile=init, home=home,
        client_setup=(
            refuse +
            "set telnet authentication type ssl, "
            f"set authentication ssl rsa-cert-file {ssl_pki['client_crt']}, "
            f"set authentication ssl rsa-key-file {ssl_pki['client_key']}, "
            f"set authentication ssl verify-file {ssl_pki['ca_crt']}, "),
        login="input 15 IKSD>, if success echo LOGGEDIN")


@pytest.mark.parametrize("method", ["start-tls", "auth-ssl"])
def test_iksd_tls_certificate_login(wermit_path, fakeshadow, tmp_path,
                                    ssl_pki, method):
    """Verify a client certificate in ~/.tlslogin logs the user in.

    Telnet START_TLS, or AUTH SSL through ssl_is(), runs the TLS
    handshake.  X509_userok() finds the client's certificate in the
    user's ~/.tlslogin, so no password is asked.
    """
    result = _tls_login(wermit_path, fakeshadow, tmp_path, ssl_pki,
                        ssl_pki["client_crt"], method)
    assert "LOGGEDIN" in result.stdout, result.stdout
    assert "Password" not in result.stdout, result.stdout
    if method == "auth-ssl":
        assert "ssl_is" in _debug_log(tmp_path)


def test_iksd_tls_certificate_not_listed(wermit_path, fakeshadow,
                                         tmp_path, ssl_pki):
    """Verify a client certificate not in ~/.tlslogin needs a password."""
    result = _tls_login(wermit_path, fakeshadow, tmp_path, ssl_pki,
                        ssl_pki["server_crt"])
    assert "LOGGEDIN" not in result.stdout, result.stdout
    assert "Password" in result.stdout, result.stdout


IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240
TTYPE, NEW_ENVIRON, START_TLS = 24, 39, 46


class _TelnetTlsClient:
    """Telnet client that runs START_TLS with a client certificate.

    It agrees to START_TLS, NEW-ENVIRON and TTYPE and refuses other
    options.  It answers SB NEW-ENVIRON SEND with each name in users
    as a USER variable, in order.  It collects the data the server
    sends outside Telnet commands.
    """

    def __init__(self, port, ssl_pki, users):
        import ssl
        self.sock = socket.create_connection(("127.0.0.1", port),
                                             timeout=15)
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        self.ctx.check_hostname = False
        self.ctx.load_verify_locations(ssl_pki["ca_crt"])
        self.ctx.load_cert_chain(ssl_pki["client_crt"],
                                 ssl_pki["client_key"])
        self.users = users
        self.data = b""
        self.buf = b""

    def _send(self, b):
        self.sock.sendall(bytes(b))

    def _sb(self, opt, body):
        self._send([IAC, SB, opt] + list(body) + [IAC, SE])

    def _handle_sb(self, body):
        if not body:
            return
        opt = body[0]
        if opt == START_TLS and body[1:2] == b"\x01":
            import time
            self._sb(START_TLS, [1])
            # The server must read FOLLOWS before the ClientHello
            # arrives.  A ClientHello in the same read is lost.
            time.sleep(0.5)
            self.sock = self.ctx.wrap_socket(self.sock)
        elif opt == NEW_ENVIRON and body[1:2] == b"\x01":
            reply = [0]
            for user in self.users:
                reply += [0] + list(b"USER") + [1] + list(user.encode())
            self._sb(NEW_ENVIRON, reply)
        elif opt == TTYPE and body[1:2] == b"\x01":
            self._sb(TTYPE, [0] + list(b"VT100"))

    def _parse(self):
        """Handle the complete commands in self.buf."""
        b = self.buf
        i = 0
        while i < len(b):
            if b[i] != IAC:
                self.data += b[i:i + 1]
                i += 1
                continue
            if i + 1 >= len(b):
                break
            cmd = b[i + 1]
            if cmd == IAC:
                self.data += b"\xff"
                i += 2
            elif cmd in (DO, DONT, WILL, WONT):
                if i + 2 >= len(b):
                    break
                opt = b[i + 2]
                if cmd == DO:
                    ok = opt in (START_TLS, NEW_ENVIRON, TTYPE)
                    self._send([IAC, WILL if ok else WONT, opt])
                elif cmd == WILL:
                    self._send([IAC, DO if opt in (0, 1, 3) else DONT,
                                opt])
                i += 3
            elif cmd == SB:
                end = b.find(bytes([IAC, SE]), i + 2)
                if end < 0:
                    break
                i, body = end + 2, b[i + 2:end]
                self.buf = b[i:]
                self._handle_sb(body)
                return True
            else:
                i += 2
        self.buf = b[i:]
        return False

    def expect(self, until, timeout=20):
        """Read until any byte string in until appears in new data.

        Returns the data read since the last call.
        """
        import time
        start = len(self.data)
        deadline = time.monotonic() + timeout
        while True:
            # A START_TLS switch must not read past the handshake.
            while self._parse():
                pass
            if any(u in self.data[start:] for u in until):
                break
            if time.monotonic() > deadline:
                break
            self.sock.settimeout(max(0.1, deadline - time.monotonic()))
            try:
                got = self.sock.recv(4096)
            except OSError:
                break
            if not got:
                break
            self.buf += got
        return self.data[start:].decode("latin-1")

    def send_line(self, text):
        """Send text and a carriage return as Telnet data."""
        self._send(list(text.encode()) + [13, 0])

    def run(self, until, timeout=20):
        """Read until any byte string in until appears, then close."""
        self.expect(until, timeout)
        self.sock.close()
        return self.data.decode("latin-1")


def test_iksd_refused_certificate_user_needs_password(
        wermit_path, fakeshadow, tmp_path, ssl_pki):
    """Verify a refused certificate login does not skip later passwords.

    The client certificate is in ~/.tlslogin for a second name for the
    user, so the certificate check validates that name.  The
    forbidden-user file refuses it, and the IKSD prompts for that
    name's password and then for a user.  The client names the user
    with a wrong password.  The IKSD must check that password.
    """
    user = getpass.getuser()
    home = tmp_path / "home"
    home.mkdir()
    (home / ".tlslogin").write_bytes(
        open(ssl_pki["client_crt"], "rb").read())
    init = tmp_path / "iksd.ini"
    init.write_text(
        f"set authentication ssl rsa-cert-file {ssl_pki['server_crt']}\n"
        f"set authentication ssl rsa-key-file {ssl_pki['server_key']}\n"
        f"set authentication ssl verify-file {ssl_pki['ca_crt']}\n"
        "set authentication ssl verify peer-cert\n")

    def client(port):
        """Answer each prompt until the user's password is sent."""
        c = _TelnetTlsClient(port, ssl_pki, ["ckalias"])
        out = ""
        for _ in range(4):
            got = c.expect([b"sername:", b"assword:", b"IKSD>"])
            out += got
            if "sername:" in got:
                c.send_line(user)
            elif f"{user}'s Password:" in got:
                c.send_line("wrong-" + PASSWORD)
                out += c.expect([b"IKSD>", b"sername:", b"incorrect"])
                break
            elif "assword:" in got:
                c.send_line("wrong-" + PASSWORD)
            else:
                break
        c.sock.close()
        return out

    out = _iksd_session(wermit_path, fakeshadow, tmp_path, "",
                        userfile_lines=["ckalias"], initfile=init,
                        home=home, client=client, alias="ckalias")
    log = _debug_log(tmp_path)
    assert "checkuser REFUSED" in log
    assert f"{user}'s Password:" in out, out
    assert "IKSD>" not in out, out

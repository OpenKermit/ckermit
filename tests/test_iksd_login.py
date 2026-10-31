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
import re
import shutil
import socket
import struct
import subprocess
import threading

import pytest

from conftest import kermit_wait, TelnetTlsClient, scaled

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
    """Return True if this build has IKSD login through shadow or PAM.

    fakeshadow.so supplies the password through the shadow and PAM
    functions.  A build with neither reads it from the passwd entry.
    """
    result = subprocess.run([wermit_path, "--help"], capture_output=True,
                            text=True, stdin=subprocess.DEVNULL,
                            timeout=scaled(10))
    assert result.returncode == 0 and result.stdout, (
        f"wermit --help failed: {result!r}")
    if "--userfile" not in result.stdout:
        return False
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-C",
         "set command more-prompting off, show features, exit"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
        timeout=scaled(10))
    assert result.returncode == 0, f"SHOW FEATURES failed: {result!r}"
    return bool(re.search(r"\bCK_(SHADOW|PAM)\b", result.stdout))


def _iksd_conf_path(wermit_path):
    """Return the IKSD configuration file path built into wermit.

    SHOW EXTENDED-OPTIONS prints it as "IKSD conf=".  A build can set
    it with -DIKSDCONF.
    """
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-C",
         "set command more-prompting off, show extended-options, exit"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
        timeout=scaled(10))
    match = re.search(r"^ IKSD conf=(.*)$", result.stdout, re.M)
    assert match, f"no IKSD conf in SHOW EXTENDED-OPTIONS: {result!r}"
    return match.group(1)


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
        pytest.skip("build has no IKSD login through shadow or PAM")
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
        env["FAKESHADOW_IKSDPATH"] = _iksd_conf_path(wermit_path)
    if home is not None:
        env["FAKESHADOW_HOME"] = str(home)
    if alias is not None:
        env["FAKESHADOW_ALIAS"] = alias
    if login is None:
        # A refused login prompts for Username: again.
        login = (f"input {kermit_wait()} Password:, output {PASSWORD}\\13, "
                 f"minput {kermit_wait()} IKSD> Username:, "
                 "if = \\v(minput) 1 echo LOGGEDIN")
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(scaled(20))
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
            timeout=scaled(60))
    finally:
        srv.close()
        thread.join(timeout=scaled(5))
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


@pytest.mark.parametrize("lines", [
    ["{user}x"],
    ["#{user}", " {user}"],
    ["x{user}"],
], ids=["longer-name", "comment-and-space", "suffix"])
def test_iksd_userfile_matches_whole_name(wermit_path, fakeshadow,
                                          tmp_path, lines):
    """Verify the forbidden-user file refuses only the whole name.

    A longer name that starts with the user's name does not refuse it,
    and lines starting with '#' or a space are skipped.
    """
    user = getpass.getuser()
    result = _iksd_session(wermit_path, fakeshadow, tmp_path, "echo DONE",
                           [ln.format(user=user) for ln in lines])
    assert "LOGGEDIN" in result.stdout, result.stdout
    assert "checkuser OK" in _debug_log(tmp_path)


def test_iksd_userfile_refuses_user(wermit_path, fakeshadow, tmp_path):
    """Verify a user listed in the forbidden-user file cannot log in."""
    user = getpass.getuser()
    result = _iksd_session(wermit_path, fakeshadow, tmp_path, "echo DONE",
                           ["other", user + "\tcomment"])
    assert "LOGGEDIN" not in result.stdout, result.stdout
    assert "checkuser REFUSED" in _debug_log(tmp_path)


def test_iksd_records_server_command_state(wermit_path, fakeshadow,
                                           tmp_path):
    """Verify the IKSD records each server command in its slot.

    slotstate() writes the command and its arguments to the INFO field
    of the session record.  The debug log shows the field.
    """
    result = _iksd_session(
        wermit_path, fakeshadow, tmp_path,
        "remote cd /, echo CD=\\v(status), "
        "remote directory /etc/passwd, echo DIR=\\v(status)")
    assert "CD=0" in result.stdout, result.stdout
    assert "DIR=0" in result.stdout, result.stdout
    log = _debug_log(tmp_path)
    assert "slotstate[REMOTE CD /" in log
    assert "slotstate[REMOTE DIR /etc/passwd" in log


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
        # Without a listed certificate the IKSD asks for a password.
        login=(f"minput {kermit_wait()} IKSD> Password:, "
               "if = \\v(minput) 1 echo LOGGEDIN"))


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


def _der_items(der):
    """Return the encoded items inside the DER SEQUENCE der."""
    def header(i):
        n = der[i + 1]
        if n < 0x80:
            return i + 2, n
        k = n & 0x7f
        return i + 2 + k, int.from_bytes(der[i + 2:i + 2 + k], "big")
    start, length = header(0)
    items = []
    i = start
    while i < start + length:
        body, n = header(i)
        items.append(der[i:body + n])
        i = body + n
    return items


def _der_sequence(content):
    """Return a DER SEQUENCE that holds the encoded items in content."""
    n = len(content)
    if n < 0x80:
        length = bytes([n])
    else:
        b = n.to_bytes((n.bit_length() + 7) // 8, "big")
        length = bytes([0x80 | len(b)]) + b
    return b"\x30" + length + content


def _cert_der(path):
    """Return the DER encoding of the PEM certificate at path."""
    return subprocess.run(["openssl", "x509", "-in", str(path),
                           "-outform", "DER"],
                          capture_output=True, check=True).stdout


def test_iksd_tls_certificate_copied_signature(wermit_path, fakeshadow,
                                               tmp_path, ssl_pki):
    """Verify a certificate with a copied signature needs a password.

    The client certificate has a key other than the client's and the
    signature bits of the certificate in ~/.tlslogin.  X509_userok()
    compares the whole certificate.  The IKSD then asks for a password.
    """
    key = ssl_pki["untrusted_ca_key"]
    own = tmp_path / "own.crt"
    subprocess.run(["openssl", "req", "-x509", "-new", "-key", str(key),
                    "-out", str(own), "-days", "2",
                    "-subj", "/CN=test-client"],
                   capture_output=True, check=True)
    tbs, alg, _ = _der_items(_cert_der(own))
    signature = _der_items(_cert_der(ssl_pki["client_crt"]))[2]
    der = tmp_path / "forged.der"
    der.write_bytes(_der_sequence(tbs + alg + signature))
    forged = tmp_path / "forged.crt"
    subprocess.run(["openssl", "x509", "-inform", "DER", "-in", str(der),
                    "-out", str(forged)], capture_output=True, check=True)
    pki = dict(ssl_pki, client_crt=str(forged), client_key=str(key))
    session = tmp_path / "session"
    session.mkdir()
    result = _tls_login(wermit_path, fakeshadow, session, pki,
                        ssl_pki["client_crt"])
    assert "LOGGEDIN" not in result.stdout, result.stdout
    assert "Password" in result.stdout, result.stdout


def test_iksd_tls_changed_user_checks_tls_connection(
        wermit_path, fakeshadow, tmp_path, ssl_pki):
    """Verify a changed USER after START_TLS is checked on the TLS link.

    The client sends USER twice in one NEW-ENVIRON IS.  The first name
    is a second name for the user, and its certificate check logs it
    in.  The second name differs, so tn_rnenv() checks the certificate
    for it on the START_TLS connection.  Both names share a home with
    the certificate in ~/.tlslogin, so no password is asked.
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
        return TelnetTlsClient(port, ssl_pki, ["ckalias", user]).run(
            [b"IKSD>", b"assword:", b"sername:"])

    out = _iksd_session(wermit_path, fakeshadow, tmp_path, "",
                        initfile=init, home=home, client=client,
                        alias="ckalias")
    assert "IKSD>" in out, out
    assert "assword" not in out, out


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
        c = TelnetTlsClient(port, ssl_pki, ["ckalias"])
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


def test_iksd_starttls_handshake_in_same_read(wermit_path, fakeshadow,
                                              tmp_path, ssl_pki):
    """Verify START_TLS works when the ClientHello follows FOLLOWS.

    The client sends SB START_TLS FOLLOWS and the ClientHello in one
    send, so the IKSD can read both at once.  The certificate login
    must still complete.
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
        return TelnetTlsClient(port, ssl_pki, [user]).run(
            [b"IKSD>", b"assword:", b"sername:"])

    out = _iksd_session(wermit_path, fakeshadow, tmp_path, "",
                        initfile=init, home=home, client=client)
    assert "IKSD>" in out, out

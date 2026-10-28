"""Tests for FTP reply parsing in ckcftp.c with crafted server replies.

A scripted one-connection server sends boundary-length or malformed
replies. wermit processes them without crashing, and completes login
when the replies are valid.
"""
import resource
import socket
import subprocess
import threading
import time

import pytest

DEFAULT_REPLIES = {
    "AUTH": b"500 not supported\r\n",
    "USER": b"331 password please\r\n",
    "PASS": b"230 logged in\r\n",
    "SYST": b"215 UNIX Type: L8\r\n",
    "PWD": b'257 "/"\r\n',
    "FEAT": b"211 no features\r\n",
    "EPSV": b"500 not supported\r\n",
    "QUIT": b"221 bye\r\n",
}


def _serve_ftp(greeting, replies):
    """Start a one-connection FTP peer and return (port, thread, socket).

    replies maps a command verb to the raw bytes sent for it,
    overriding DEFAULT_REPLIES. Any other command receives "200 ok".
    """
    table = dict(DEFAULT_REPLIES)
    table.update(replies)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(20)

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(20)
            try:
                conn.sendall(greeting)
                for line in conn.makefile("rb"):
                    verb = line.split(b" ")[0].strip().upper().decode(
                        "ascii", "replace")
                    conn.sendall(table.get(verb, b"200 ok\r\n"))
                    if verb == "QUIT":
                        break
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return srv.getsockname()[1], thread, srv


def _ftp_session(run_wermit, greeting, replies=None, commands=(),
                 timeout=60):
    """Run wermit against the scripted server and return the result."""
    port, thread, srv = _serve_ftp(greeting, replies or {})
    try:
        result = run_wermit(", ".join([
            f"ftp open 127.0.0.1 {port} /user:u /password:p",
            "if success echo OPEN-OK",
            *commands,
            "ftp close",
            "exit",
        ]), timeout=timeout)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    return result


def _multiline(code, lines):
    """Return a multi-line reply formatted with code and lines."""
    body = b"".join(b" " + ln + b"\r\n" for ln in lines)
    return code + b"-start\r\n" + body + code + b" end\r\n"


@pytest.mark.parametrize("length", [255, 256, 1023, 1024, 4095, 4096,
                                    10000])
def test_ftp_long_greeting_line(run_wermit, length):
    """Verify handling of a single-line greeting of the given length."""
    greeting = b"220 " + b"G" * length + b"\r\n"
    result = _ftp_session(run_wermit, greeting)
    assert "OPEN-OK" in result.stdout, result.stdout[-500:]


def test_ftp_greeting_many_lines(run_wermit):
    """Verify handling of a 2000-line multi-line greeting."""
    greeting = _multiline(b"220", [b"line %d" % i for i in range(2000)])
    result = _ftp_session(run_wermit, greeting)
    assert "OPEN-OK" in result.stdout, result.stdout[-500:]


def test_ftp_greeting_long_continuation_lines(run_wermit):
    """Verify handling of a multi-line greeting with 5000-byte lines."""
    greeting = _multiline(b"220", [b"C" * 5000] * 3)
    result = _ftp_session(run_wermit, greeting)
    assert "OPEN-OK" in result.stdout, result.stdout[-500:]


def test_ftp_greeting_bare_lf(run_wermit):
    """Verify handling of replies terminated by LF instead of CRLF."""
    greeting = b"220-first\n 220 inside\n220 last\n"
    result = _ftp_session(run_wermit, greeting)
    assert "OPEN-OK" in result.stdout, result.stdout[-500:]


def test_ftp_empty_and_short_reply_lines(run_wermit, tmp_path):
    """Verify empty and short reply lines with the debug log on.

    The debug log makes getreply() strip each line's trailing controls.
    An empty line has nothing to strip.  A line shorter than its reply
    code field has no text after the code.  An ASan build reports any
    read outside ftp_reply_str.
    """
    reply = b'257-x\r\n\n21\r\n\r\n257 "/"\r\n'
    result = _ftp_session(run_wermit, b"220 hi\r\n", {"PWD": reply},
                          commands=[f"log debug {tmp_path}/debug.log",
                                    "ftp pwd", "echo PWD-DONE"])
    assert "OPEN-OK" in result.stdout, result.stdout[-500:]
    assert "PWD-DONE" in result.stdout, result.stdout[-500:]
    assert result.returncode == 0, result.stderr[-2000:]


def test_ftp_blank_feat_line(run_wermit):
    """Verify a FEAT reply line that holds only blanks.

    The line is longer than every earlier reply, so only zeros follow it
    in ftp_reply_str.  An ASan build reports a scan past the line.
    """
    reply = b"211-Features:\r\n" + b" " * 60 + b"\r\n MDTM\r\n211 End\r\n"
    result = _ftp_session(run_wermit, b"220 hi\r\n", {"FEAT": reply})
    assert "OPEN-OK" in result.stdout, result.stdout[-500:]
    assert result.returncode == 0, result.stderr[-2000:]


def test_ftp_multiline_mismatched_end_code(run_wermit):
    """Verify a multi-line reply with a mismatched intermediate code."""
    greeting = b"220-start\r\n230 not the end\r\n220 end\r\n"
    result = _ftp_session(run_wermit, greeting)
    assert "OPEN-OK" in result.stdout, result.stdout[-500:]


@pytest.mark.parametrize("greeting", [
    b"abc not a code\r\n",
    b"2\r\n",
    b"\r\n",
    b"99999999999999999999 huge\r\n",
], ids=["letters", "one-digit", "empty", "huge-code"])
def test_ftp_malformed_greeting(run_wermit, greeting):
    """Verify a greeting without a valid reply code fails cleanly."""
    _ftp_session(run_wermit, greeting)


@pytest.mark.parametrize("verb", ["SYST", "FEAT"])
def test_ftp_long_reply_to_command(run_wermit, verb):
    """Verify long single- and multi-line replies after login."""
    code = b"215" if verb == "SYST" else b"211"
    reply = _multiline(code, [b"F" * 5000] + [b"x"] * 1000)
    result = _ftp_session(run_wermit, b"220 hi\r\n", {verb: reply})
    assert "OPEN-OK" in result.stdout, result.stdout[-500:]


@pytest.mark.parametrize("reply", [
    b"227 Entering Passive Mode (1,2,3)\r\n",
    b"227 Entering Passive Mode\r\n",
], ids=["too-few", "no-numbers"])
def test_ftp_malformed_pasv_reply(run_wermit, reply):
    """Verify a PASV reply without six numbers is rejected."""
    result = _ftp_session(run_wermit, b"220 hi\r\n", {"PASV": reply},
                          commands=["ftp dir"])
    assert "Passive mode address scan failure" in result.stdout, (
        result.stdout[-500:])


def test_ftp_pasv_long_reply(run_wermit):
    """Verify handling of a PASV reply exceeding the 64-byte buffer.

    The first six numbers name a closed local port, so DIR fails.
    """
    reply = b"227 (127,0,0,1,0,1," + b"1," * 3000 + b"1)\r\n"
    _ftp_session(run_wermit, b"220 hi\r\n", {"PASV": reply},
                 commands=["ftp dir"])


def _serve_nlst(names, pasv_ip=b"127,0,0,1"):
    """Start a one-connection FTP peer that lists names for NLST.

    pasv_ip is the address text sent in the PASV reply.

    Supports PASV for the listing's data connection and refuses every
    RETR. Returns (port, thread, socket, list of RETR arguments).
    """
    table = dict(DEFAULT_REPLIES)
    table.update({"SIZE": b"550 no\r\n", "MDTM": b"550 no\r\n",
                  "RETR": b"550 no\r\n"})
    retrs = []
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(20)

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        data_srv = None
        with conn:
            conn.settimeout(20)
            try:
                conn.sendall(b"220 hi\r\n")
                for line in conn.makefile("rb"):
                    words = line.strip().split(b" ", 1)
                    verb = words[0].upper().decode("ascii", "replace")
                    if verb == "PASV":
                        data_srv = socket.socket(socket.AF_INET,
                                                 socket.SOCK_STREAM)
                        data_srv.bind(("127.0.0.1", 0))
                        data_srv.listen(1)
                        data_srv.settimeout(20)
                        p = data_srv.getsockname()[1]
                        conn.sendall(b"227 Entering Passive Mode "
                                     b"(%s,%d,%d)\r\n"
                                     % (pasv_ip, p >> 8, p & 255))
                        continue
                    if verb == "NLST" and data_srv:
                        conn.sendall(b"150 listing\r\n")
                        data, _ = data_srv.accept()
                        with data:
                            data.sendall(b"".join(n + b"\r\n"
                                                  for n in names))
                        data_srv.close()
                        data_srv = None
                        conn.sendall(b"226 done\r\n")
                        continue
                    if verb == "RETR" and len(words) > 1:
                        retrs.append(words[1])
                    conn.sendall(table.get(verb, b"200 ok\r\n"))
                    if verb == "QUIT":
                        break
            except OSError:
                pass
            finally:
                if data_srv:
                    data_srv.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return srv.getsockname()[1], thread, srv, retrs


@pytest.mark.parametrize("dirlen", [10, 4000, 4087, 5000])
def test_ftp_mget_pathless_names_long_directory(run_wermit, tmp_path,
                                                dirlen):
    """Verify MGET prefixes pathless NLST names with the pattern's path.

    A UNIX server may list only the names in the directory. MGET then
    prefixes each name with the directory from its pattern, unless the
    result does not fit in its 4096-byte buffer.
    """
    directory = "/" + "d" * (dirlen - 1)
    port, thread, srv, retrs = _serve_nlst([b"file.txt"])
    try:
        result = run_wermit(", ".join([
            f"cd {tmp_path}",
            f"ftp open 127.0.0.1 {port} /user:u /password:p",
            "if success echo OPEN-OK",
            "ftp passive on",
            f"ftp mget {directory}/*.txt",
            "ftp close",
            "exit",
        ]), timeout=60)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "OPEN-OK" in result.stdout, result.stdout[-500:]
    if dirlen + len("/file.txt") < 4096:
        expected = f"{directory}/file.txt".encode()
    else:
        expected = b"file.txt"
    assert retrs == [expected], retrs


@pytest.mark.parametrize("recursive", ["/recursive ", ""])
def test_ftp_mget_refuses_unsafe_server_names(run_wermit, tmp_path,
                                              recursive):
    """Verify MGET skips server names that leave the current directory.

    A server listing can name "../x" or an absolute path.  MGET must not
    use such a name as the local filename.  A plain name is still
    retrieved.
    """
    names = [b"../../escaped.txt", b"/tmp/abs-escaped.txt",
             b"sub/../../up.txt", b"ok.txt"]
    port, thread, srv, retrs = _serve_nlst(names)
    try:
        result = run_wermit(", ".join([
            f"cd {tmp_path}",
            f"ftp open 127.0.0.1 {port} /user:u /password:p",
            "if success echo OPEN-OK",
            "ftp passive on",
            f"ftp mget {recursive}*",
            "ftp close",
            "exit",
        ]), timeout=60)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert "OPEN-OK" in result.stdout, result.stdout[-500:]
    assert retrs == [b"ok.txt"], retrs


@pytest.mark.parametrize("retr_reply,settings", [
    (b"150 opening\r\n", ["set ftp timeout 2"]),
    (b"150 opening\r\n425 cannot open data connection\r\n", []),
])
def test_ftp_active_get_server_never_connects(run_wermit, tmp_path,
                                              retr_reply, settings):
    """Verify an active-mode GET ends when no data connection arrives.

    The server accepts PORT and RETR but never connects back.  wermit
    gives up at the FTP timeout, or at once when the server sends a
    further reply on the control connection.
    """
    start = time.monotonic()
    result = _ftp_session(
        run_wermit, b"220 hi\r\n",
        {"RETR": retr_reply, "SIZE": b"550 no\r\n", "MDTM": b"550 no\r\n"},
        commands=[f"cd {tmp_path}", "set ftp passive off", *settings,
                  "ftp get x.txt", "echo GET-STATUS=\\v(status)"],
        timeout=40)
    elapsed = time.monotonic() - start
    assert "OPEN-OK" in result.stdout, result.stdout
    assert "GET-STATUS=1" in result.stdout, result.stdout
    assert elapsed < 15, elapsed


def test_ftp_pasv_address_is_ignored(run_wermit, tmp_path):
    """Verify the data connection goes to the control connection's peer.

    The PASV reply names an unreachable address.  The client takes only
    the port from it, lists the file and requests it.
    """
    port, thread, srv, retrs = _serve_nlst([b"file.txt"],
                                           pasv_ip=b"10,255,255,1")
    try:
        result = run_wermit(", ".join([
            f"cd {tmp_path}",
            f"ftp open 127.0.0.1 {port} /user:u /password:p",
            "set ftp timeout 5",
            "ftp mget *.txt",
            "ftp close",
            "exit",
        ]), timeout=60)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert retrs == [b"file.txt"], (retrs, result.stdout)


def test_ftp_trust_pasv_address_on(run_wermit, tmp_path):
    """Verify TRUST-PASV-ADDRESS ON connects to the PASV reply address.

    The reply names an unreachable address.  The client connects there,
    gives up at the FTP timeout, and requests no file.
    """
    port, thread, srv, retrs = _serve_nlst([b"file.txt"],
                                           pasv_ip=b"10,255,255,1")
    start = time.monotonic()
    try:
        result = run_wermit(", ".join([
            f"cd {tmp_path}",
            "set ftp trust-pasv-address on",
            f"ftp open 127.0.0.1 {port} /user:u /password:p",
            "set ftp timeout 3",
            "ftp mget *.txt",
            "ftp close",
            "exit",
        ]), timeout=60)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert retrs == [], (retrs, result.stdout)
    assert time.monotonic() - start < 30


def test_ftp_trust_pasv_address_show(run_wermit):
    """Verify SHOW FTP reports TRUST-PASV-ADDRESS, OFF by default."""
    result = run_wermit("show ftp, set ftp trust-pasv-address on, "
                        "show ftp, exit")
    lines = [ln for ln in result.stdout.splitlines()
             if "trust-pasv-address" in ln]
    assert len(lines) == 2, result.stdout
    assert lines[0].split()[-1] == "off", lines
    assert lines[1].split()[-1] == "on", lines


def test_ftp_long_proxy_name_for_data_connection(run_wermit):
    """Verify initconn() refuses an HTTP proxy name too long to copy.

    The control connection is direct.  The proxy is set afterward, so
    only the passive data connection goes through it.
    """
    reply = b"227 Entering Passive Mode (127,0,0,1,0,9)\r\n"
    result = _ftp_session(run_wermit, b"220 hi\r\n", {"PASV": reply},
                          commands=[f"set tcp http-proxy {'p' * 1100}",
                                    "ftp dir",
                                    "echo DIR-STATUS=\\v(status)"])
    assert "OPEN-OK" in result.stdout, result.stdout[-500:]
    assert "DIR-STATUS=1" in result.stdout, result.stdout[-500:]
    assert "proxy name too long" in result.stdout, result.stdout[-500:]


def test_ftp_unknown_proxy_host_for_data_connection(run_wermit):
    """Verify initconn() fails when the HTTP proxy host is unknown.

    The client must not send LIST without a data connection.
    """
    reply = b"227 Entering Passive Mode (127,0,0,1,0,9)\r\n"
    result = _ftp_session(run_wermit, b"220 hi\r\n", {"PASV": reply},
                          commands=["set tcp http-proxy nosuch.invalid:9",
                                    "set ftp debug on",
                                    "ftp dir",
                                    "echo DIR-STATUS=\\v(status)"])
    assert "OPEN-OK" in result.stdout, result.stdout[-500:]
    assert "DIR-STATUS=1" in result.stdout, result.stdout[-500:]
    assert "---> LIST" not in result.stdout, result.stdout[-500:]


def test_ftp_show_send_port_commands(run_wermit):
    """Verify SHOW FTP reports SEND-PORT-COMMANDS, not PASSIVE-MODE."""
    result = run_wermit("set ftp passive-mode on, "
                        "set ftp send-port-commands off, show ftp, exit")
    lines = [ln for ln in result.stdout.splitlines()
             if "send-port-commands" in ln]
    assert len(lines) == 1, result.stdout
    assert lines[0].split()[-1] == "off", lines


def _record_connect():
    """Start a one-connection HTTP proxy that refuses CONNECT.

    Returns (port, thread, socket, list of request heads).
    """
    heads = []
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(20)

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(20)
            buf = b""
            try:
                while b"\r\n\r\n" not in buf:
                    chunk = conn.recv(4096)
                    if not chunk:
                        return
                    buf += chunk
                heads.append(buf.split(b"\r\n\r\n", 1)[0]
                             .decode("latin-1"))
                conn.sendall(b"HTTP/1.1 403 Forbidden\r\n"
                             b"Content-Length: 0\r\n\r\n")
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return srv.getsockname()[1], thread, srv, heads


@pytest.mark.parametrize("trust,target", [
    ("off", "127.0.0.1:9"),
    ("on", "10.255.255.1:9"),
])
def test_ftp_proxy_pasv_connect_target(run_wermit, trust, target):
    """Verify the proxy CONNECT target for a passive data connection.

    The PASV reply names 10.255.255.1.  With TRUST-PASV-ADDRESS OFF the
    target is the host named in FTP OPEN.  With ON it is the reply's
    address.
    """
    reply = b"227 Entering Passive Mode (10,255,255,1,0,9)\r\n"
    pport, pthread, psrv, heads = _record_connect()
    try:
        result = _ftp_session(
            run_wermit, b"220 hi\r\n", {"PASV": reply},
            commands=[f"set ftp trust-pasv-address {trust}",
                      f"set tcp http-proxy 127.0.0.1:{pport}",
                      "ftp dir"])
    finally:
        psrv.close()
        pthread.join(timeout=5)
    assert heads, result.stdout[-500:]
    assert heads[0].startswith(f"CONNECT {target} "), heads


def test_ftp_proxy_data_connection_closes_socket(wermit_path):
    """Verify a failed proxy data connection leaves no socket open.

    Each FTP DIR opens a socket for passive mode, and the HTTP proxy
    refuses the connection.  With 40 descriptors, a leak of one socket
    per DIR exhausts them within 100 commands.
    """
    reply = b"227 Entering Passive Mode (127,0,0,1,0,9)\r\n"
    port, thread, srv = _serve_ftp(b"220 hi\r\n", {"PASV": reply})

    def limit():
        resource.setrlimit(resource.RLIMIT_NOFILE, (40, 40))
    try:
        result = subprocess.run(
            [wermit_path, "-H", "-Y", "-Q", "-C", ", ".join([
                "set command more-prompting off",
                f"ftp open 127.0.0.1 {port} /user:u /password:p",
                "set tcp http-proxy 127.0.0.1:1",
                "for \\%i 1 100 1 { ftp dir }",
                "echo LOOP-DONE",
                "ftp close",
                "exit",
            ])],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=120, preexec_fn=limit, start_new_session=True)
    finally:
        srv.close()
        thread.join(timeout=5)
    out = result.stdout + result.stderr
    assert "LOOP-DONE" in result.stdout, out[-500:]
    assert "Too many open files" not in out, out[-500:]


@pytest.mark.parametrize("reply", [
    b"227 Entering Passive Mode (-1,256,255,256,255,0)\r\n",
    b"227 Entering Passive Mode (127,0,0,1,300,1)\r\n",
])
def test_ftp_pasv_fields_out_of_range(run_wermit, reply):
    """Verify PASV fields outside 0-255 are refused."""
    result = _ftp_session(run_wermit, b"220 hi\r\n", {"PASV": reply},
                          commands=["ftp dir", "echo DIR-STATUS=\\v(status)"])
    assert "OPEN-OK" in result.stdout, result.stdout
    assert "out of range" in result.stdout, result.stdout
    assert "DIR-STATUS=1" in result.stdout, result.stdout


def test_ftp_pasv_failure_closes_data_socket(run_wermit):
    """Verify a failed PASV setup does not leave its socket open."""
    import os
    if not os.path.isdir("/proc/self/fd"):
        pytest.skip("no /proc/self/fd")
    result = _ftp_session(
        run_wermit, b"220 hi\r\n",
        {"PASV": b"227 Entering Passive Mode (1,2,3)\r\n"},
        commands=["ftp dir"] * 5 +
                 ["run echo SOCKETS=$(ls -l /proc/$PPID/fd | grep -c socket)"])
    assert "OPEN-OK" in result.stdout, result.stdout
    count = int(result.stdout.split("SOCKETS=")[1].split()[0])
    assert count <= 2, result.stdout


def test_ftp_epsv_port_out_of_range(run_wermit):
    """Verify an EPSV port above 65535 is refused, not truncated."""
    try:
        srv = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        srv.bind(("::1", 0))
    except OSError:
        pytest.skip("no IPv6 loopback")
    srv.listen(1)
    srv.settimeout(20)
    table = dict(DEFAULT_REPLIES)
    table["EPSV"] = b"229 Entering Extended Passive Mode (|||86000|)\r\n"

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(20)
            try:
                conn.sendall(b"220 hi\r\n")
                for line in conn.makefile("rb"):
                    verb = line.split(b" ")[0].strip().upper().decode(
                        "ascii", "replace")
                    conn.sendall(table.get(verb, b"200 ok\r\n"))
                    if verb == "QUIT":
                        break
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        result = run_wermit(", ".join([
            f"ftp open ::1 {srv.getsockname()[1]} /user:u /password:p",
            "ftp dir", "echo DIR-STATUS=\\v(status)", "ftp close", "exit",
        ]), timeout=60)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert "address scan failure" in result.stdout, result.stdout
    assert "DIR-STATUS=1" in result.stdout, result.stdout


def _serve_mlsd(lines):
    """Start a one-connection FTP peer that lists lines for MLSD.

    It advertises MLST in FEAT, supports PASV, and answers RETR with
    "550".  Returns (port, thread, socket, list of RETR arguments).
    """
    retrs = []
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(20)
    table = dict(DEFAULT_REPLIES)
    table.update({"FEAT": b"211-Features:\r\n MLST type*;size*;modify*;"
                          b"\r\n211 End\r\n",
                  "SIZE": b"550 no\r\n", "MDTM": b"550 no\r\n",
                  "RETR": b"550 no\r\n"})

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        data_srv = None
        with conn:
            conn.settimeout(20)
            try:
                conn.sendall(b"220 hi\r\n")
                for line in conn.makefile("rb"):
                    words = line.strip().split(b" ", 1)
                    verb = words[0].upper().decode("ascii", "replace")
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
                    if verb == "MLSD" and data_srv:
                        conn.sendall(b"150 listing\r\n")
                        data, _ = data_srv.accept()
                        with data:
                            data.sendall(b"".join(n + b"\r\n"
                                                  for n in lines))
                        data_srv.close()
                        data_srv = None
                        conn.sendall(b"226 done\r\n")
                        continue
                    if verb == "RETR":
                        retrs.append(words[1] if len(words) > 1 else b"")
                    conn.sendall(table.get(verb, b"200 ok\r\n"))
                    if verb == "QUIT":
                        break
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return srv.getsockname()[1], thread, srv, retrs


def test_ftp_mlsd_names_with_equals_and_space(run_wermit, tmp_path):
    """Verify MLSD names are taken whole after the facts.

    A name may contain '=' and ';'.  A server that leaves out the last
    ';' before the space still gives the right name.
    """
    lines = [b"type=file;size=5; a=b.txt",
             b"type=file;size=5; c;d.txt",
             b"type=file;size=5 e.txt"]
    port, thread, srv, retrs = _serve_mlsd(lines)
    try:
        run_wermit(", ".join([
            f"cd {tmp_path}",
            f"ftp open 127.0.0.1 {port} /user:u /password:p",
            "ftp mget *",
            "ftp close",
            "exit",
        ]), timeout=60)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert sorted(retrs) == [b"a=b.txt", b"c;d.txt", b"e.txt"], retrs


def test_ftp_user_without_password_sends_no_stale_text(run_wermit):
    """Verify FTP USER with no password does not send leftover text.

    GREP leaves its pattern in a buffer that FTP USER uses for the
    password.  With no password given, none is saved, and standard
    input is empty, the PASS command must not carry the pattern.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(20)
    table = dict(DEFAULT_REPLIES)
    table["USER"] = b"331 password please\r\n"
    received = []

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(20)
            try:
                conn.sendall(b"220 hi\r\n")
                for line in conn.makefile("rb"):
                    received.append(line.strip())
                    verb = line.split(b" ")[0].strip().upper().decode(
                        "ascii", "replace")
                    conn.sendall(table.get(verb, b"200 ok\r\n"))
                    if verb == "QUIT":
                        break
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    port = srv.getsockname()[1]
    try:
        run_wermit(", ".join([
            "grep SECRET-PATTERN /dev/null",
            "set ftp autologin off",
            f"ftp open 127.0.0.1 {port}",
            "ftp user u",
            "ftp close",
            "exit",
        ]), timeout=30)
    finally:
        srv.close()
        thread.join(timeout=5)
    passes = [r for r in received if r.upper().startswith(b"PASS")]
    assert passes, received
    assert not any(b"SECRET-PATTERN" in p for p in passes), passes


def _serve_active_retr(payload):
    """Start a one-connection FTP peer for an active-mode RETR.

    On RETR it connects to the PORT or EPRT address, sends payload,
    closes the data connection, and only then sends the 150 and 226
    replies in one write.  So both replies are in wermit's control
    buffer while its data connection waits in the listen queue.
    Return (port, thread, socket).
    """
    table = dict(DEFAULT_REPLIES)
    table.update({"SIZE": b"550 no\r\n", "MDTM": b"550 no\r\n",
                  "REST": b"350 ok\r\n"})
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(20)

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        addr = None
        with conn:
            conn.settimeout(20)
            try:
                conn.sendall(b"220 ready\r\n")
                for line in conn.makefile("rb"):
                    words = line.strip().split(b" ", 1)
                    verb = words[0].upper().decode("ascii", "replace")
                    arg = words[1].decode("ascii") if len(words) > 1 else ""
                    if verb == "PORT":
                        f = [int(x) for x in arg.split(",")]
                        addr = (".".join(map(str, f[:4])), f[4] * 256 + f[5])
                        conn.sendall(b"200 ok\r\n")
                    elif verb == "EPRT":
                        f = arg.split(arg[0])
                        addr = (f[2], int(f[3]))
                        conn.sendall(b"200 ok\r\n")
                    elif verb == "RETR" and addr:
                        with socket.create_connection(addr, 10) as d:
                            d.sendall(payload)
                        conn.sendall(b"150 opening\r\n226 done\r\n")
                    else:
                        conn.sendall(table.get(verb, b"200 ok\r\n"))
                    if verb == "QUIT":
                        break
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return srv.getsockname()[1], thread, srv


def test_ftp_active_get_with_replies_before_accept(run_wermit, tmp_path):
    """Verify an active-mode GET when the replies precede the accept.

    The server connects, sends the file and replies 150 and 226 before
    wermit looks for the data connection.  The connection waits in the
    listen queue, so wermit must accept it rather than take the waiting
    replies for a refusal.
    """
    payload = b"active mode data\n" * 100
    port, thread, srv = _serve_active_retr(payload)
    out = tmp_path / "got.dat"
    try:
        result = run_wermit(", ".join([
            f"ftp open 127.0.0.1 {port} /active /user:u /password:p",
            "ftp type binary",
            f"ftp get f.dat {out}",
            "echo GET=\\v(status)",
            "ftp close",
            "exit",
        ]), timeout=60)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert "GET=0" in result.stdout, result.stdout
    assert out.read_bytes() == payload

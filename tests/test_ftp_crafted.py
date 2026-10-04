"""Tests for FTP reply parsing in ckcftp.c with crafted server replies.

A scripted one-connection server sends boundary-length or malformed
replies. wermit processes them without crashing, and completes login
when the replies are valid.
"""
import socket
import threading

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


def _serve_nlst(names):
    """Start a one-connection FTP peer that lists names for NLST.

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
                                     b"(127,0,0,1,%d,%d)\r\n"
                                     % (p >> 8, p & 255))
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

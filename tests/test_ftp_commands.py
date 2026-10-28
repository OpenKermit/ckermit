"""Tests for FTP login, MLSD facts and update checks (ckcftp.c).

A scripted server records each command it receives and answers from a
table.  It supports PASV for MLSD listings and answers RETR with 550.
"""
import os
import socket
import threading
import time

import pytest

from conftest import scaled

BASE_REPLIES = {
    "AUTH": b"500 not supported\r\n",
    "USER": b"331 password please\r\n",
    "PASS": b"230 logged in\r\n",
    "SYST": b"215 UNIX Type: L8\r\n",
    "PWD": b'257 "/"\r\n',
    "FEAT": b"211-Features:\r\n MLST type*;size*;modify*;\r\n211 End\r\n",
    "EPSV": b"500 not supported\r\n",
    "SIZE": b"550 no\r\n",
    "MDTM": b"550 no\r\n",
    "RETR": b"550 no\r\n",
    "QUIT": b"221 bye\r\n",
}


class FtpPeer:
    """A one-connection FTP server that records the commands it gets.

    replies maps a verb to its reply.  listing holds the MLSD lines.
    files maps a RETR argument (bytes) to the data it sends.
    """

    def __init__(self, replies=None, listing=(), files=None):
        self.table = dict(BASE_REPLIES)
        self.table.update(replies or {})
        self.listing = listing
        self.files = files or {}
        self.commands = []
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.srv.settimeout(20)
        self.port = self.srv.getsockname()[1]
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            conn, _ = self.srv.accept()
        except OSError:
            return
        data_srv = None
        with conn:
            conn.settimeout(20)
            try:
                conn.sendall(b"220 hi\r\n")
                for line in conn.makefile("rb"):
                    line = line.rstrip(b"\r\n")
                    self.commands.append(line)
                    verb = line.split(b" ")[0].upper().decode(
                        "ascii", "replace")
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
                                                  for n in self.listing))
                        data_srv.close()
                        data_srv = None
                        conn.sendall(b"226 done\r\n")
                        continue
                    name = line[5:]
                    if verb == "RETR" and data_srv and name in self.files:
                        conn.sendall(b"150 sending\r\n")
                        data, _ = data_srv.accept()
                        with data:
                            data.sendall(self.files[name])
                        data_srv.close()
                        data_srv = None
                        conn.sendall(b"226 done\r\n")
                        continue
                    conn.sendall(self.table.get(verb, b"200 ok\r\n"))
                    if verb == "QUIT":
                        break
            except OSError:
                pass

    def close(self):
        """Close the listener and wait for the server thread."""
        self.srv.close()
        self.thread.join(timeout=5)

    def sent(self, verb):
        """Return the arguments of each command with the given verb."""
        out = []
        for line in self.commands:
            words = line.split(b" ", 1)
            if words[0].upper() == verb.encode():
                out.append(words[1] if len(words) > 1 else b"")
        return out


def _session(run_wermit, peer, commands, login=True, cwd=None):
    """Run commands against peer and return the result.

    cwd is the local directory.  After FTP OPEN, CD goes to the server.
    """
    if login:
        opener = f"ftp open 127.0.0.1 {peer.port} /user:u /password:p"
    else:
        opener = ("set ftp autologin off, "
                  f"ftp open 127.0.0.1 {peer.port}")
    try:
        local = [f"cd {cwd}"] if cwd else []
        result = run_wermit(", ".join([*local, opener, *commands,
                                       "ftp close", "exit"]),
                            timeout=60)
    finally:
        peer.close()
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    return result


def test_ftp_user_password_and_account(run_wermit):
    """Verify FTP USER sends the password and account when asked."""
    peer = FtpPeer({"PASS": b"332 account please\r\n",
                    "ACCT": b"230 logged in\r\n"})
    result = _session(run_wermit, peer,
                      ["ftp user alice secret acct1",
                       "echo S=\\v(status)"], login=False)
    assert peer.sent("USER") == [b"alice"], peer.commands
    assert peer.sent("PASS") == [b"secret"], peer.commands
    assert peer.sent("ACCT") == [b"acct1"], peer.commands
    assert "S=0" in result.stdout, result.stdout


def test_ftp_user_account_after_login(run_wermit):
    """Verify FTP USER sends a given account after a complete login."""
    peer = FtpPeer({"ACCT": b"202 not needed\r\n"})
    result = _session(run_wermit, peer,
                      ["ftp user alice secret acct1",
                       "echo S=\\v(status)"], login=False)
    assert peer.sent("ACCT") == [b"acct1"], peer.commands
    assert "S=0" in result.stdout, result.stdout


def test_ftp_user_without_password(run_wermit):
    """Verify FTP USER succeeds when USER alone logs in."""
    peer = FtpPeer({"USER": b"230 welcome\r\n"})
    result = _session(run_wermit, peer,
                      ["ftp user alice", "echo S=\\v(status)"],
                      login=False)
    assert peer.sent("USER") == [b"alice"], peer.commands
    assert "S=0" in result.stdout, result.stdout


def test_ftp_user_refused(run_wermit):
    """Verify FTP USER fails and says so when the server refuses."""
    peer = FtpPeer({"PASS": b"530 no\r\n"})
    result = _session(run_wermit, peer,
                      ["ftp user alice secret", "echo S=\\v(status)"],
                      login=False)
    assert "Login failed." in result.stdout, result.stdout
    assert "S=1" in result.stdout, result.stdout


def test_ftp_mlsd_facts(run_wermit, tmp_path):
    """Verify MLSD facts select the files that MGET retrieves.

    Directories and lines with no name are skipped.  A line of facts
    with no space has no name.  An unknown type is fetched as a file.
    Every fact type and some malformed facts are present.
    """
    listing = [
        b"type=cdir;modify=20200101000000; .",
        b"type=pdir; ..",
        b"type=dir;perm=el; sub",
        b"type=file;size=5;modify=20200101000000;perm=r;unique=1;"
        b"charset=UTF-8;lang=en;media-type=text/plain;create=2020; a.txt",
        b"type=file;size=99999999999999999999999; big.txt",
        b"type=file;novalue;size=; b.txt",
        b"type=OS.unix=slink;size=1; link",
        b"type=file;size=5;modify=",
        b"type=file",
        b"x" * 3000 + b"=y; long.txt",
        b"type=file;size=3 c.txt",
    ]
    peer = FtpPeer(listing=listing)
    _session(run_wermit, peer, ["ftp mget *"], cwd=tmp_path)
    assert sorted(peer.sent("RETR")) == [
        b"a.txt", b"b.txt", b"big.txt", b"c.txt", b"link",
        b"long.txt"], peer.commands


@pytest.mark.parametrize("mdtm,fetched", [
    (b"213 20991231235959\r\n", True),
    (b"213 19800101000000\r\n", False),
    (b"213 191010101000000\r\n", False),
    (b"213 garbage\r\n", True),
])
def test_ftp_get_update_compares_dates(run_wermit, tmp_path, mdtm,
                                       fetched):
    """Verify GET /UPDATE fetches a file only when the server's is newer.

    The local file is dated now.  The FTP collision action is DISCARD
    by default, so the test sets it to OVERWRITE.  The last two
    replies are a date from a server with the Y2K bug (year 19100
    for 2000) and one that does not parse.  A file with no usable
    server date is fetched.
    """
    (tmp_path / "f.txt").write_text("local\n")
    peer = FtpPeer({"FEAT": b"211-Features:\r\n MDTM\r\n211 End\r\n",
                    "MDTM": mdtm})
    _session(run_wermit, peer,
             ["ftp get /update /collision:overwrite f.txt"], cwd=tmp_path)
    assert bool(peer.sent("RETR")) == fetched, peer.commands
    assert (tmp_path / "f.txt").read_text() == "local\n"


def test_ftp_get_move_to_long_expansion(run_wermit, tmp_path):
    """Verify GET /MOVE-TO evaluates a long destination in bounds.

    The parser stores \\m(d) as typed and creates a directory of that
    name.  After the transfer, \\m(d) expands to 5000 characters, more
    than a path holds.  The move then fails, and wermit keeps the file.
    """
    peer = FtpPeer(files={b"f.txt": b"data\n"})
    result = _session(run_wermit, peer,
                      [".d := " + "x" * 5000,
                       "ftp get /move-to:\\\\m(d) f.txt",
                       "echo END-MARKER"], cwd=tmp_path)
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "END-MARKER" in result.stdout, result.stdout[-1000:]
    assert peer.sent("RETR") == [b"f.txt"], peer.commands
    assert (tmp_path / "f.txt").read_bytes() == b"data\n"


def test_ftp_mlsd_empty_names_are_skipped(run_wermit, tmp_path):
    """Verify MLSD lines with an empty name do not end the listing.

    With /RECURSIVE a nameless directory must not be entered.
    """
    listing = [b"type=file;size=1; ", b"type=dir; ",
               b"type=file;size=1; z.txt"]
    peer = FtpPeer(listing=listing)
    _session(run_wermit, peer, ["ftp mget /recursive *"], cwd=tmp_path)
    assert peer.sent("RETR") == [b"z.txt"], peer.commands
    assert not peer.sent("CWD"), peer.commands


class AbortPeer:
    """An FTP server whose transfers last until the client stops them.

    RETR sends data until the client closes the data connection or
    sends ABOR.  STOR reads slowly until drain is set, then at full
    speed until the client closes it.  Each transfer ends with a 426
    reply, and ABOR also gets 226.  data_closed is set when the client
    has closed a data connection.
    """

    def __init__(self):
        self.started = threading.Event()
        self.drain = threading.Event()
        self.data_closed = threading.Event()
        self.commands = []
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.srv.settimeout(30)
        self.port = self.srv.getsockname()[1]
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _pump(self, conn, data, verb, stop):
        """Move data until the client closes it, then send 426."""
        try:
            while not stop.is_set():
                if verb == "RETR":
                    data.sendall(b"x" * 4096)
                    time.sleep(0.01)
                elif self.drain.is_set():
                    if not data.recv(1 << 20):
                        break
                else:
                    if not data.recv(1024):
                        break
                    time.sleep(0.05)
        except OSError:
            pass
        if not stop.is_set():
            self.data_closed.set()
            try:
                conn.sendall(b"426 Connection closed\r\n")
            except OSError:
                pass
        data.close()

    def _run(self):
        try:
            conn, _ = self.srv.accept()
        except OSError:
            return
        replies = dict(BASE_REPLIES)
        replies["PWD"] = b'257 "/abort-test"\r\n'
        data_srv = None
        stop = threading.Event()
        with conn:
            conn.settimeout(60)
            try:
                conn.sendall(b"220 hi\r\n")
                for line in conn.makefile("rb"):
                    line = line.strip(b"\r\n\xff\xf4\xf2")
                    self.commands.append(line)
                    verb = line.split(b" ")[0].upper().decode(
                        "ascii", "replace")
                    if verb == "PASV":
                        data_srv = socket.socket()
                        data_srv.bind(("127.0.0.1", 0))
                        data_srv.listen(1)
                        data_srv.settimeout(20)
                        p = data_srv.getsockname()[1]
                        conn.sendall(b"227 Entering Passive Mode "
                                     b"(127,0,0,1,%d,%d)\r\n"
                                     % (p >> 8, p & 255))
                        continue
                    if verb in ("RETR", "STOR") and data_srv:
                        conn.sendall(b"150 transfer starting\r\n")
                        data, _ = data_srv.accept()
                        data_srv.close()
                        data_srv = None
                        stop.clear()
                        self.started.set()
                        threading.Thread(
                            target=self._pump,
                            args=(conn, data, verb, stop),
                            daemon=True).start()
                        continue
                    if verb == "ABOR":
                        stop.set()
                        self.data_closed.set()
                        conn.sendall(b"426 Transfer aborted\r\n"
                                     b"226 Abort successful\r\n")
                        continue
                    conn.sendall(replies.get(verb, b"200 ok\r\n"))
                    if verb == "QUIT":
                        break
            except OSError:
                pass

    def close(self):
        """Close the listener and wait for the server thread."""
        self.srv.close()
        self.thread.join(timeout=5)


@pytest.mark.parametrize("command", ["get f.bin", "put big.bin"])
def test_ftp_transfer_interrupted(wermit_path, tmp_path, command):
    """Verify Ctrl-C ends an FTP transfer and its data connection.

    wermit runs on a pseudoterminal.  Ctrl-C during the transfer runs
    the transfer's cancel handler.  It closes the data connection and
    reads the server's reply, so the control connection stays usable.
    """
    import pty
    import select
    import subprocess
    from conftest import _make_controlling_tty
    (tmp_path / "big.bin").write_bytes(b"y" * 20000000)
    peer = AbortPeer()
    fd, slave = pty.openpty()
    proc = subprocess.Popen(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         "set transfer display brief, "
         f"ftp open 127.0.0.1 {peer.port} /user:u /password:p, "
         f"ftp {command}"],
        stdin=slave, stdout=slave, stderr=slave, cwd=str(tmp_path),
        close_fds=True, preexec_fn=_make_controlling_tty)
    os.close(slave)
    out = b""

    def read_until(marker, secs):
        nonlocal out
        end = time.monotonic() + secs
        while marker not in out and time.monotonic() < end:
            r, _, _ = select.select([fd], [], [], 0.2)
            if r:
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    return
                if not chunk:
                    return
                out += chunk

    try:
        assert peer.started.wait(20), out
        time.sleep(1)
        os.write(fd, b"\x03")
        peer.drain.set()
        closed = peer.data_closed.wait(15)
        read_until(b"C-Kermit>", 15)
        os.write(fd, b"ftp pwd\r")
        read_until(b"/abort-test", 15)
        os.write(fd, b"exit\r")
        read_until(b"\x00never", 5)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        os.close(fd)
        peer.close()
    text = out.decode(errors="replace")
    assert closed, (peer.commands, text[-1000:])
    assert "/abort-test" in text, text[-1000:]


def test_ftp_session_does_not_leak(wermit_path, valgrind, tmp_path):
    """Verify an FTP session with MLSD, MGET and GET /UPDATE leaks nothing.

    valgrind reports no block definitely lost.
    """
    import re
    import subprocess
    listing = [b"type=file;size=5;modify=20200101000000; a.txt",
               b"type=dir; sub", b"type=file;size=3 b.txt"]
    peer = FtpPeer({"FEAT": b"211-Features:\r\n MLST type*;size*;"
                            b"modify*;\r\n MDTM\r\n211 End\r\n",
                    "MDTM": b"213 20200101000000\r\n"}, listing=listing)
    try:
        result = subprocess.run(
            [valgrind, "-q", "--leak-check=full", wermit_path,
             "-H", "-Y", "-Q", "-C",
             f"ftp open 127.0.0.1 {peer.port} /user:u /password:p, "
             "ftp mget *, ftp get /update a.txt, ftp dir, ftp close, "
             "exit 0"],
            cwd=tmp_path, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=scaled(200))
    finally:
        peer.close()
    assert peer.sent("MLSD"), peer.commands
    records = re.split(r"^==\d+== *$", result.stderr, flags=re.M)
    leaked = [r for r in records if "definitely lost" in r]
    assert not leaked, result.stderr

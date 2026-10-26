"""Tests for Telnet FORWARD-X on the client (ckctel.c, ckcnet.c).

A scripted Telnet server offers FORWARD-X, opens a channel and sends X11
data through it.  wermit connects the channel to a fake X server named
by DISPLAY and relays data both ways.
"""
import os
import random
import signal
import socket
import struct
import threading
import time

import pytest

from conftest import finish_wermit_pty, start_wermit_pty

IAC, SB, SE, WILL, WONT, DO, DONT = 255, 250, 240, 251, 252, 253, 254
FWDX = 49
OPEN, CLOSE, DATA, OPTIONS = 1, 2, 3, 4

# X11 connection setup, LSB first, protocol 11.0, no authorization.
X11_SETUP = b"l\x00\x0b\x00\x00\x00\x00\x00\x00\x00\x00\x00"


def _sb(payload):
    """Return a FORWARD-X subnegotiation with IAC doubled."""
    return (bytes([IAC, SB, FWDX]) + payload.replace(b"\xff", b"\xff\xff")
            + bytes([IAC, SE]))


def _fake_x_server():
    """Listen on 127.0.0.1:6000+N and return (socket, N)."""
    for n in range(50, 200):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", 6000 + n))
        except OSError:
            s.close()
            continue
        s.listen(128)
        s.settimeout(20)
        return s, n
    pytest.skip("no free X display port")


class ForwardXServer:
    """A one-connection Telnet server that forwards X11 to the client.

    script is a list of FORWARD-X payloads, and pauses in seconds, sent
    once the client agrees to FORWARD-X.  The server then waits, sends
    "DONE" and closes the connection.  relayed holds the data the
    client sent back on any channel.
    """

    def __init__(self, script, wait=1.0):
        self.script = script
        self.wait = wait
        self.relayed = b""
        self.received = []
        self.agreed = threading.Event()
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.srv.settimeout(20)
        self.port = self.srv.getsockname()[1]
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _parse(self, conn, buf):
        """Handle Telnet commands in buf and return the rest."""
        while True:
            i = buf.find(bytes([IAC]))
            if i < 0 or i + 1 >= len(buf):
                return buf[i:] if i >= 0 else b""
            cmd = buf[i + 1]
            if cmd in (WILL, WONT, DO, DONT):
                if i + 2 >= len(buf):
                    return buf[i:]
                opt = buf[i + 2]
                buf = buf[i + 3:]
                if cmd == DO and opt == FWDX:
                    if not self.agreed.is_set():
                        self.agreed.set()
                        threading.Thread(target=self._play, args=(conn,),
                                         daemon=True).start()
                elif cmd == WILL:
                    conn.sendall(bytes([IAC, DONT, opt]))
                elif cmd == DO:
                    conn.sendall(bytes([IAC, WONT, opt]))
                continue
            if cmd == SB:
                j = i + 2
                body = b""
                while True:
                    k = buf.find(b"\xff", j)
                    if k < 0 or k + 1 >= len(buf):
                        return buf[i:]
                    body += buf[j:k]
                    if buf[k + 1] == SE:
                        buf = buf[k + 2:]
                        break
                    body += b"\xff"
                    j = k + 2
                if body[:1] == bytes([FWDX]):
                    self.received.append(body[1:])
                    if body[1:2] == bytes([DATA]):
                        self.relayed += body[4:]
                continue
            buf = buf[i + 2:]

    def _play(self, conn):
        """Send the script, then DONE."""
        try:
            time.sleep(0.3)
            for payload in self.script:
                if isinstance(payload, float):
                    time.sleep(payload)
                else:
                    conn.sendall(_sb(payload))
            time.sleep(self.wait)
            conn.sendall(b"DONE\r\n")
            time.sleep(0.5)
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def _run(self):
        try:
            conn, _ = self.srv.accept()
        except OSError:
            return
        conn.settimeout(20)
        buf = b""
        try:
            conn.sendall(bytes([IAC, WILL, FWDX]))
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf = self._parse(conn, buf + chunk)
        except OSError:
            pass
        finally:
            conn.close()

    def close(self):
        """Close the listener and wait for the server thread."""
        self.srv.close()
        self.thread.join(timeout=5)


def _channel(n):
    """Return a channel number as two bytes, MSB first."""
    return struct.pack(">H", n)


def _run_action(action, proc, errors):
    """Call action(proc) and append any exception to errors."""
    try:
        action(proc)
    except BaseException as e:
        errors.append(e)


def _session(wermit_path, tmp_path, server, display, action=None):
    """CONNECT to server with DISPLAY set and return (rc, output).

    Only the CONNECT loop relays X11 data, so wermit runs on a
    pseudoterminal.  CONNECT ends when the server closes.  action, when
    given, runs in a thread with the wermit process as its argument.
    The pseudoterminal is read meanwhile.  wermit blocks on output to an
    unread pseudoterminal.
    """
    cmds = ("set exit warning off, set telnet forward-x no-encryption on, "
            f"set host 127.0.0.1 {server.port} /telnet, "
            "if fail exit 1, connect, echo AFTER, exit")
    errors = []
    old = {k: os.environ.get(k) for k in ("DISPLAY", "XAUTHORITY")}
    os.environ["DISPLAY"] = display
    os.environ["XAUTHORITY"] = str(tmp_path / "no-xauthority")
    try:
        proc, master = start_wermit_pty(wermit_path, cmds, tmp_path)
        if action:
            thread = threading.Thread(target=_run_action,
                                      args=(action, proc, errors),
                                      daemon=True)
            thread.start()
        rc, out = finish_wermit_pty(proc, master, timeout=40)
        if action:
            thread.join(timeout=30)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        server.close()
    assert not errors, errors
    assert rc >= 0, rc
    assert "runtime error" not in out and "Sanitizer" not in out, out
    return rc, out


def test_forward_x_relays_data(wermit_path, tmp_path):
    """Verify a forwarded X11 channel carries data both ways."""
    xsrv, n = _fake_x_server()
    got = []

    def handle(c):
        """Record what one X client sends and answer once."""
        try:
            c.settimeout(10)
            data = b""
            while len(data) < len(X11_SETUP) + 5:
                chunk = c.recv(4096)
                if not chunk:
                    break
                data += chunk
            if data:
                got.append(data)
                c.sendall(b"XREPLY" + b"\xff" * 3)
                time.sleep(2)
        except OSError:
            pass
        finally:
            c.close()

    def xserve():
        """Accept X clients.  fwdx_server_avail() connects first."""
        while True:
            try:
                c, _ = xsrv.accept()
            except OSError:
                return
            threading.Thread(target=handle, args=(c,), daemon=True).start()

    xt = threading.Thread(target=xserve, daemon=True)
    xt.start()
    server = ForwardXServer([
        bytes([OPEN]) + _channel(1),
        bytes([DATA]) + _channel(1) + X11_SETUP + b"hello",
        1.0,
        bytes([CLOSE]) + _channel(1),
    ], wait=1.0)
    try:
        rc, out = _session(wermit_path, tmp_path, server,
                           f"127.0.0.1:{n}")
    finally:
        xsrv.close()
        xt.join(timeout=5)
    assert server.agreed.is_set(), out
    assert got and got[0] == X11_SETUP + b"hello", got
    assert b"XREPLY\xff\xff\xff" in server.relayed, server.received
    assert "DONE" in out and "AFTER" in out, out


def _x_listener(accepted=None):
    """Start a fake X server that accepts and drains connections.

    Each accepted connection is appended to accepted, when given.
    Returns (socket, display number).
    """
    xsrv, n = _fake_x_server()

    def drain(c):
        try:
            c.settimeout(10)
            while c.recv(4096):
                pass
        except OSError:
            pass
        finally:
            c.close()

    def serve():
        while True:
            try:
                c, _ = xsrv.accept()
            except OSError:
                return
            if accepted is not None:
                accepted.append(c)
            threading.Thread(target=drain, args=(c,), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()
    return xsrv, n


LSB_AUTH = (b"l\x00\x0b\x00\x00\x00\x12\x00\x10\x00\x00\x00"
            + b"MIT-MAGIC-COOKIE-1\x00\x00" + b"k" * 16)


IGNORED = {
    "open-empty": [bytes([OPEN])],
    "open-short": [bytes([OPEN]) + b"\x00"],
    "close-unknown": [bytes([CLOSE]) + _channel(5)],
    "close-empty": [bytes([CLOSE])],
    "data-empty": [bytes([DATA])],
    "data-with-auth": [bytes([OPEN]) + _channel(1),
                       bytes([DATA]) + _channel(1) + LSB_AUTH],
    "xoff-xon": [bytes([OPEN]) + _channel(1), bytes([6]) + _channel(1),
                 bytes([7]) + _channel(1), bytes([6]), bytes([7])],
    "opt-data": [bytes([5, 1, 2])],
    "channel-ffff": [bytes([OPEN]) + _channel(0xffff),
                     bytes([CLOSE]) + _channel(0xffff)],
    "options": [bytes([OPTIONS]) + b"\x01", bytes([OPTIONS])],
}
for _length in (2050, 2051, 2052, 2053):
    IGNORED[f"options-{_length}"] = [bytes([OPTIONS]) + b"\x00" * _length]

# A refused X11 setup, data for a channel that is not open, and a
# request the client never handles end the session as Telnet errors.
FATAL = {
    "data-unknown": [bytes([DATA]) + _channel(9) + b"data"],
    "data-short-setup": [bytes([OPEN]) + _channel(1),
                         bytes([DATA]) + _channel(1) + b"\x00"],
    "data-bad-byte-order": [bytes([OPEN]) + _channel(1),
                            bytes([DATA]) + _channel(1) + b"Q"
                            + X11_SETUP[1:]],
    "data-huge-lengths": [bytes([OPEN]) + _channel(1),
                          bytes([DATA]) + _channel(1)
                          + b"B\x00\x00\x0b\x00\x00\xff\xff\xff\xff"
                          b"\x00\x00"],
    "screen": [bytes([0, 1])],
    "unknown": [b"\x63"],
}


@pytest.mark.parametrize("name", sorted(IGNORED))
def test_forward_x_ignored_requests(wermit_path, tmp_path, name):
    """Verify the client ignores malformed or unusual FORWARD-X input.

    The session goes on until the server sends DONE and closes.
    OPTIONS near the subnegotiation buffer size gets a reply that fits
    the outgoing buffer.
    """
    xsrv, n = _x_listener()
    server = ForwardXServer(IGNORED[name], wait=0.5)
    try:
        rc, out = _session(wermit_path, tmp_path, server, f"127.0.0.1:{n}")
    finally:
        xsrv.close()
    assert server.agreed.is_set(), out
    assert "DONE" in out and "AFTER" in out, out


@pytest.mark.parametrize("name", sorted(FATAL))
def test_forward_x_fatal_requests(wermit_path, tmp_path, name):
    """Verify FORWARD-X input the client refuses ends only the session."""
    xsrv, n = _x_listener()
    server = ForwardXServer(FATAL[name], wait=0.5)
    try:
        rc, out = _session(wermit_path, tmp_path, server, f"127.0.0.1:{n}")
    finally:
        xsrv.close()
    assert server.agreed.is_set(), out
    assert "AFTER" in out, out


def test_forward_x_no_x_server(wermit_path, tmp_path):
    """Verify the client closes a channel it cannot connect.

    The X server accepts the availability check, and any other
    connection, until the client agrees to FORWARD-X.  Then it stops
    listening, so the client's connection for OPEN is refused.  The
    client answers OPEN with CLOSE for the channel.  The display number
    is chosen at random from a range the other tests do not use, so a
    concurrent run of this test is unlikely to bind the same port.
    """
    displays = list(range(200, 2000))
    random.shuffle(displays)
    for n in displays:
        xsrv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            xsrv.bind(("127.0.0.1", 6000 + n))
        except OSError:
            xsrv.close()
            continue
        break
    else:
        pytest.skip("no free X display port")
    xsrv.listen(4)
    xsrv.settimeout(0.1)
    gone = threading.Event()
    server = ForwardXServer([1.0, bytes([OPEN]) + _channel(3)], wait=1.0)

    def until_agreed():
        deadline = time.monotonic() + 20
        while not server.agreed.is_set() and time.monotonic() < deadline:
            try:
                c, _ = xsrv.accept()
                c.close()
            except OSError:
                pass
        xsrv.close()
        gone.set()

    threading.Thread(target=until_agreed, daemon=True).start()
    rc, out = _session(wermit_path, tmp_path, server, f"127.0.0.1:{n}")
    assert gone.is_set()
    assert server.agreed.is_set(), out
    assert bytes([CLOSE]) + _channel(3) in server.received, server.received
    assert "AFTER" in out, out


def test_forward_x_channel_table_full(wermit_path, tmp_path):
    """Verify OPEN past the channel table gets CLOSE and no X connection.

    The client has room for 64 channels.  It answers the 65th and later
    OPEN requests with CLOSE and does not connect to the X server for
    them.  fwdx_server_avail() makes one more connection to check the
    X server.
    """
    accepted = []
    xsrv, n = _x_listener(accepted)
    server = ForwardXServer([bytes([OPEN]) + _channel(c)
                             for c in range(1, 70)], wait=1.0)
    try:
        rc, out = _session(wermit_path, tmp_path, server, f"127.0.0.1:{n}")
    finally:
        xsrv.close()
    closes = [r for r in server.received if r[:1] == bytes([CLOSE])]
    assert closes == [bytes([CLOSE]) + _channel(c) for c in range(65, 70)], \
        server.received
    assert len(accepted) == 64 + 1, len(accepted)
    assert "AFTER" in out, out


class ResetServer(ForwardXServer):
    """A ForwardXServer that resets the connection when told to.

    Setting reset makes the server thread close the connection with a
    TCP RST.  closed is set once it has.
    """

    def __init__(self, script):
        self.reset = threading.Event()
        self.closed = threading.Event()
        super().__init__(script, wait=30.0)

    def _run(self):
        try:
            conn, _ = self.srv.accept()
        except OSError:
            self.closed.set()
            return
        conn.settimeout(0.1)
        buf = b""
        deadline = time.monotonic() + 30
        try:
            conn.sendall(bytes([IAC, WILL, FWDX]))
            while (not self.reset.is_set()
                   and time.monotonic() < deadline):
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buf = self._parse(conn, buf + chunk)
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                            struct.pack("ii", 1, 0))
        except OSError:
            pass
        finally:
            conn.close()
            self.closed.set()


def test_forward_x_close_after_reset(wermit_path, tmp_path):
    """Verify CONNECT ends when the CLOSE for a channel cannot be sent.

    wermit is stopped while its X server closes the channel and the
    Telnet server resets the connection.  When wermit resumes, one
    select() reports both.  The client reads the X server's end of
    file first and sends CLOSE.  The write fails and closes the
    network connection.  CONNECT ends without touching the closed
    descriptor.
    """
    accepted = []
    xsrv, n = _x_listener(accepted)
    server = ResetServer([bytes([OPEN]) + _channel(1)])

    def reset(proc):
        """Close both ends while wermit is stopped."""
        deadline = time.monotonic() + 20
        while len(accepted) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert len(accepted) == 2, len(accepted)
        time.sleep(0.5)
        os.kill(proc.pid, signal.SIGSTOP)
        try:
            accepted[1].shutdown(socket.SHUT_RDWR)
            server.reset.set()
            assert server.closed.wait(5)
            time.sleep(0.5)
        finally:
            os.kill(proc.pid, signal.SIGCONT)

    try:
        rc, out = _session(wermit_path, tmp_path, server,
                           f"127.0.0.1:{n}", action=reset)
    finally:
        xsrv.close()
    assert "Communications disconnect" in out, out
    assert "AFTER" in out, out

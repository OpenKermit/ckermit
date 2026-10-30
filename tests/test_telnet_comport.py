"""Tests for the Telnet COM-PORT option on the client (ckctel.c).

A scripted Telnet server agrees to COM-PORT-OPTION (RFC 2217).  It
records each subnegotiation the client sends and answers it with the
server form of the same command (code + 100) and the same value.  It
can also send unsolicited notifications, well formed or not.
"""
import socket
import threading
import time

import pytest
from conftest import scaled

IAC, SB, SE, WILL, WONT, DO, DONT = 255, 250, 240, 251, 252, 253, 254
COMPORT = 44


def _sb(payload):
    """Return a COM-PORT subnegotiation with IAC doubled in payload."""
    return (bytes([IAC, SB, COMPORT]) + payload.replace(b"\xff", b"\xff\xff")
            + bytes([IAC, SE]))


class ComPortServer:
    """A one-connection Telnet server that accepts COM-PORT-OPTION.

    received holds the payload of each COM-PORT subnegotiation from the
    client.  unsolicited is a list of payloads sent once the option is
    agreed.
    """

    def __init__(self, unsolicited=()):
        self.unsolicited = list(unsolicited)
        self.received = []
        # Baud rate, data size 8, parity none, one stop bit.
        self.serial = {1: (9600).to_bytes(4, "big"), 2: b"\x08",
                       3: b"\x01", 4: b"\x01"}
        # SET-CONTROL request code: current value.  Outbound flow none,
        # BREAK off, DTR on, RTS on, inbound flow none.
        self.control = {0: 1, 4: 6, 7: 8, 10: 11, 13: 14}
        self.agreed = threading.Event()
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.srv.settimeout(scaled(20))
        self.port = self.srv.getsockname()[1]
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _reply(self, conn, payload):
        """Answer one client subnegotiation as a serial port server.

        A query (value 0, or a SET-CONTROL request code) gets the
        current value.  A setting is stored and echoed.
        """
        if not payload:
            return
        code, value = payload[0], payload[1:]
        if code == 0:                   # SIGNATURE
            if not value:
                conn.sendall(_sb(b"\x64Test COM-PORT server"))
            return
        if code == 1:                   # SET-BAUDRATE
            if value.strip(b"\x00"):
                self.serial[1] = value
            conn.sendall(_sb(bytes([101]) + self.serial[1]))
            return
        if code in (2, 3, 4):           # DATASIZE, PARITY, STOPSIZE
            if value[:1] not in (b"", b"\x00"):
                self.serial[code] = value[:1]
            conn.sendall(_sb(bytes([code + 100]) + self.serial[code]))
            return
        if code == 5 and value:         # SET-CONTROL
            v = value[0]
            groups = {0: (1, 2, 3, 17, 18, 19), 4: (5, 6), 7: (8, 9),
                      10: (11, 12), 13: (14, 15, 16)}
            for req, members in groups.items():
                if v == req:
                    conn.sendall(_sb(bytes([105, self.control[req]])))
                    return
                if v in members:
                    self.control[req] = v
                    conn.sendall(_sb(bytes([105, v])))
                    return
            conn.sendall(_sb(bytes([105, v])))
            return
        if code in (10, 11, 12):        # Masks and PURGE-DATA
            conn.sendall(_sb(bytes([code + 100]) + value))

    def _run(self):
        try:
            conn, _ = self.srv.accept()
        except OSError:
            return
        conn.settimeout(scaled(20))
        buf = b""
        try:
            conn.sendall(b"login: ")
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while True:
                    i = buf.find(bytes([IAC]))
                    if i < 0 or i + 1 >= len(buf):
                        buf = buf[i:] if i >= 0 else b""
                        break
                    cmd = buf[i + 1]
                    if cmd in (WILL, WONT, DO, DONT):
                        if i + 2 >= len(buf):
                            buf = buf[i:]
                            break
                        opt = buf[i + 2]
                        buf = buf[i + 3:]
                        if cmd == WILL:
                            ok = opt == COMPORT
                            conn.sendall(bytes([IAC, DO if ok else DONT,
                                                opt]))
                            if ok and not self.agreed.is_set():
                                self.agreed.set()
                                for p in self.unsolicited:
                                    conn.sendall(_sb(p))
                        elif cmd == DO:
                            conn.sendall(bytes([IAC, WONT, opt]))
                        continue
                    if cmd == SB:
                        end = buf.find(bytes([IAC, SE]), i)
                        while end > 0 and buf[end - 1:end] == b"\xff" \
                                and buf[i:end].count(b"\xff") % 2 == 0:
                            end = buf.find(bytes([IAC, SE]), end + 1)
                        if end < 0:
                            buf = buf[i:]
                            break
                        body = buf[i + 2:end].replace(b"\xff\xff", b"\xff")
                        buf = buf[end + 2:]
                        if body[:1] == bytes([COMPORT]):
                            self.received.append(body[1:])
                            self._reply(conn, body[1:])
                        continue
                    buf = buf[i + 2:]
        except OSError:
            pass
        finally:
            conn.close()

    def close(self):
        """Close the listener and wait for the server thread."""
        self.srv.close()
        self.thread.join(timeout=scaled(5))

    def codes(self):
        """Return the command code of each subnegotiation received."""
        return [p[0] for p in self.received if p]


def _session(run_wermit, server, commands, timeout=30):
    """Connect with COM-PORT-OPTION requested and run commands."""
    try:
        result = run_wermit(", ".join([
            "set telopt com-port-control requested",
            f"set host 127.0.0.1 {server.port} /telnet",
            "if fail exit 1",
            *commands, "close", "exit"]), timeout=timeout)
    finally:
        server.close()
    assert result.returncode >= 0, result.returncode
    return result


def test_comport_settings_are_sent(run_wermit):
    """Verify serial settings go to the server as COM-PORT commands.

    Flow control goes to the server when INPUT conditions the line.
    """
    server = ComPortServer()
    result = _session(run_wermit, server, [
        "set speed 19200", "set parity even", "set stop-bits 2",
        "set flow xon/xoff", "input 1 NEVER", "echo SPEED=\\v(speed)",
    ])
    assert server.agreed.is_set()
    got = server.received
    assert b"\x01" + (19200).to_bytes(4, "big") in got, got
    assert b"\x03\x03" in got, got           # Parity even
    assert b"\x04\x02" in got, got           # Two stop bits
    assert b"\x05\x02" in got, got           # Outbound XON/XOFF
    assert b"\x05\x0f" in got, got           # Inbound XON/XOFF
    assert "SPEED=19200" in result.stdout, result.stdout


def test_comport_show_communications(run_wermit):
    """Verify SHOW COMMUNICATIONS reports the server's port settings."""
    server = ComPortServer()
    result = _session(run_wermit, server, ["show communications"])
    out = result.stdout
    assert "Test COM-PORT server" in out, out
    assert "Data Size            : 8" in out, out
    assert "DTR Signal" in out, out


def test_comport_hangup_drops_dtr(run_wermit):
    """Verify HANGUP turns DTR off and on through the server."""
    server = ComPortServer()
    _session(run_wermit, server, ["hangup"])
    got = server.received
    assert b"\x05\x09" in got, got           # DTR off
    assert got.index(b"\x05\x09") < len(got) - 1, got
    assert b"\x05\x08" in got[got.index(b"\x05\x09"):], got


@pytest.mark.parametrize("payload", [
    b"\x6a\x61",                         # NOTIFY-LINESTATE
    b"\x6b\xb0",                         # NOTIFY-MODEMSTATE
    b"\x6c", b"\x6d",                     # FLOWCONTROL-SUSPEND, RESUME
    b"\x65", b"\x65\x01\x02", b"\x65\x05",  # Bad SET-BAUDRATE lengths
    b"\x65\xff\xff\xff\xff",               # Baud rate 4294967295
    b"\x66", b"\x67", b"\x68", b"\x69",     # Missing values
    b"\x69\x63",                         # Unknown SET-CONTROL value
    b"\x6e", b"\x6f", b"\x70",             # Masks and purge, no value
    b"\x64" + b"S" * 2000,                # Long signature
    b"\x64",                              # Signature request
    b"", b"\xc8\x01",                     # Empty and unknown
], ids=lambda p: p[:3].hex() or "empty")
def test_comport_server_notifications(run_wermit, payload):
    """Verify the client survives any notification from the server.

    The server sends the payload as soon as COM-PORT-OPTION is agreed.
    The session then goes on and closes normally.
    """
    server = ComPortServer(unsolicited=[payload])
    result = _session(run_wermit, server,
                      ["show communications", "echo ALIVE"])
    assert "ALIVE" in result.stdout, result.stdout

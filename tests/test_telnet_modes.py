"""Byte-level tests of the Telnet modes of SET HOST.

/SSL-TELNET and /TLS-TELNET negotiate Telnet at the start.  /SSL-RAW
and /TLS-RAW use no Telnet.  /SSL and /TLS treat the connection as
Telnet but send no options until the peer sends IAC.  /TELNET is
plain Telnet.

A Python peer accepts one connection, sends fixed bytes, and records
every byte the client sends.  Kermit packets prefix 255.  These tests
use INPUT, OUTPUT, and TRANSMIT to put raw bytes on the wire.
"""

import shutil
import socket
import ssl
import threading
import time

import pytest

from conftest import kermit_wait, scaled

pytestmark = pytest.mark.skipif(
    shutil.which("openssl") is None,
    reason="openssl CLI not found on PATH"
)

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240
ECHO, TTYPE, LOGOUT, ENCRYPTION, START_TLS = 1, 24, 18, 38, 46

# A file for binary TRANSMIT: a literal 0xFF and a CR LF.
TRANSMIT_DATA = b"A\xffB\r\n"

RAW = ("ssl-raw", "tls-raw")
PASSIVE = ("ssl", "tls")
ACTIVE = ("ssl-telnet", "tls-telnet")


def telnet_split(raw):
    """Split a Telnet byte stream into data and commands.

    Return (data, cmds).  IAC IAC becomes one 0xFF in data.  Each
    command is a tuple: (verb, option) for WILL, WONT, DO and DONT,
    (SB, option) for a subnegotiation, and (byte,) for others.
    """
    data = bytearray()
    cmds = []
    i = 0
    while i < len(raw):
        c = raw[i]
        if c != IAC or i + 1 >= len(raw):
            data.append(c)
            i += 1
            continue
        verb = raw[i + 1]
        if verb == IAC:
            data.append(IAC)
            i += 2
        elif verb in (WILL, WONT, DO, DONT) and i + 2 < len(raw):
            cmds.append((verb, raw[i + 2]))
            i += 3
        elif verb == SB and i + 2 < len(raw):
            cmds.append((SB, raw[i + 2]))
            end = raw.find(bytes([IAC, SE]), i + 3)
            i = len(raw) if end < 0 else end + 2
        else:
            cmds.append((verb,))
            i += 2
    return bytes(data), cmds


class Peer:
    """A one-connection TCP or TLS peer.

    After the handshake it waits delay seconds and sends send.  It
    records the client's bytes until the client closes.  With answer
    set, it refuses each WILL and DO the client sends.
    """

    def __init__(self, ssl_pki, send, answer=False, delay=0.0):
        self.send = send
        self.answer = answer
        self.delay = delay
        self.received = bytearray()
        self.ctx = None
        if ssl_pki is not None:
            self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.ctx.load_cert_chain(ssl_pki["server_crt"],
                                     ssl_pki["server_key"])
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.srv.settimeout(scaled(20))
        self.port = self.srv.getsockname()[1]
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _refuse(self, conn, start):
        """Refuse each complete WILL and DO in received from start.

        Return the index after the last complete item.
        """
        buf = self.received
        reply = bytearray()
        i = start
        while i < len(buf):
            if buf[i] != IAC:
                i += 1
                continue
            if i + 1 >= len(buf):
                break
            verb = buf[i + 1]
            if verb in (WILL, WONT, DO, DONT):
                if i + 2 >= len(buf):
                    break
                if verb == WILL:
                    reply += bytes([IAC, DONT, buf[i + 2]])
                elif verb == DO:
                    reply += bytes([IAC, WONT, buf[i + 2]])
                i += 3
            elif verb == SB:
                end = buf.find(bytes([IAC, SE]), i + 2)
                if end < 0:
                    break
                i = end + 2
            else:
                i += 2
        if reply:
            conn.sendall(bytes(reply))
        return i

    def _run(self):
        try:
            conn, _ = self.srv.accept()
        except OSError:
            return
        try:
            if self.ctx is not None:
                conn = self.ctx.wrap_socket(conn, server_side=True)
            time.sleep(self.delay)
            conn.sendall(self.send)
            conn.settimeout(0.1)
            deadline = time.monotonic() + scaled(15)
            parsed = 0
            while time.monotonic() < deadline:
                try:
                    chunk = conn.recv(4096)
                except (socket.timeout, TimeoutError):
                    continue
                if not chunk:
                    break
                self.received += chunk
                if self.answer:
                    parsed = self._refuse(conn, parsed)
        except (OSError, ssl.SSLError):
            pass
        finally:
            conn.close()
            self.srv.close()

    def result(self):
        """Wait for the session to end.  Return the bytes received."""
        self.thread.join(scaled(20))
        return bytes(self.received)


def run_session(run_wermit, ssl_pki, tmp_path, switch, send,
                answer=False, delay=0.0, commands=""):
    """Connect wermit to a Peer and run commands.

    The client logs the session in binary, reads until "Z" arrives,
    and runs commands.  Return (session log bytes, peer bytes).
    """
    peer = Peer(None if switch == "telnet" else ssl_pki, send,
                answer=answer, delay=delay)
    xmit = tmp_path / "xmit.bin"
    xmit.write_bytes(TRANSMIT_DATA)
    log = tmp_path / "session.log"
    verify = (f"set authentication ssl verify-file {ssl_pki['ca_crt']}, "
              if switch != "telnet" else "")
    result = run_wermit(
        f"{verify}set host localhost {peer.port} /{switch}, "
        "if fail exit 9, "
        f"set session-log binary, log session {log}, "
        f"set input echo off, input {kermit_wait()} Z, if fail exit 8, "
        f"set transmit echo off, {commands}close, exit",
        timeout=30)
    received = peer.result()
    assert result.returncode == 0, (result.returncode, result.stdout)
    return log.read_bytes(), received


# Every byte value class that Telnet treats specially: a literal 0xFF,
# a command, and CR NUL.
PEER_DATA = bytes([0x41, IAC, IAC, 0x42, IAC, WILL, ECHO, 0x43,
                   0x0D, 0x00, 0x44]) + b"Z"


@pytest.mark.parametrize("switch", RAW)
def test_raw_input_passes_peer_bytes(run_wermit, ssl_pki, tmp_path,
                                     switch):
    """Verify a raw connection reads the peer's bytes unchanged.

    INPUT discards NUL on every connection.  The NUL after CR does not
    reach the session log.
    """
    session, _ = run_session(run_wermit, ssl_pki, tmp_path, switch,
                             PEER_DATA)
    assert session == PEER_DATA.replace(b"\r\x00", b"\r")


@pytest.mark.parametrize("switch", RAW)
def test_raw_output_and_transmit_send_bytes_unchanged(
        run_wermit, ssl_pki, tmp_path, switch):
    """Verify a raw connection sends 0xFF and CR as given.

    No Telnet bytes go out, not even IAC DO LOGOUT at close.
    """
    _, received = run_session(
        run_wermit, ssl_pki, tmp_path, switch, b"Z",
        commands=f"output X\\255Y\\13, "
                 f"transmit /binary {tmp_path / 'xmit.bin'}, ")
    assert received == b"X\xffY\r" + TRANSMIT_DATA


@pytest.mark.parametrize("switch,name", [
    ("ssl-raw", "tcp/ip_ssl"), ("tls-raw", "tcp/ip_tls")])
def test_raw_connection_type(run_wermit, ssl_pki, switch, name):
    """Verify \\v(connection) names a raw SSL or TLS connection."""
    peer = Peer(ssl_pki, b"")
    result = run_wermit(
        f"set authentication ssl verify-file {ssl_pki['ca_crt']}, "
        f"set host localhost {peer.port} /{switch}, if fail exit 9, "
        "echo CONN=\\v(connection), close", timeout=30)
    peer.result()
    assert f"CONN={name}\n" in result.stdout, result.stdout


@pytest.mark.parametrize("switch", PASSIVE)
def test_passive_sends_no_telnet_to_silent_peer(run_wermit, ssl_pki,
                                                tmp_path, switch):
    """Verify /SSL and /TLS send no Telnet command to a quiet peer.

    The peer sends no IAC.  The client starts no Telnet and sends no
    IAC DO LOGOUT at close.
    """
    _, received = run_session(run_wermit, ssl_pki, tmp_path, switch,
                              b"Z", commands="output X, ")
    assert received == b"X"


@pytest.mark.parametrize("switch", PASSIVE + ACTIVE + ("telnet",))
def test_output_and_transmit_double_iac(run_wermit, ssl_pki, tmp_path,
                                        switch):
    """Verify OUTPUT and TRANSMIT send 0xFF as IAC IAC on Telnet.

    /SSL and /TLS treat the connection as Telnet from the start.
    """
    _, received = run_session(
        run_wermit, ssl_pki, tmp_path, switch, b"Z",
        answer=True,
        commands=f"output X\\255Y, "
                 f"transmit /binary {tmp_path / 'xmit.bin'}, ")
    data, _ = telnet_split(received)
    assert b"X\xffY" in data, received
    assert b"A\xffB\r" in data, received


@pytest.mark.parametrize("switch", ("ssl-telnet", "telnet"))
def test_output_doubles_iac_with_quoting_off(run_wermit, ssl_pki,
                                             tmp_path, switch):
    """Verify OUTPUT doubles 0xFF with COMMAND QUOTING OFF.

    A TAKE file carries the literal 0xFF byte.
    """
    script = tmp_path / "out.ksc"
    script.write_bytes(b"set command quoting off\noutput X\xffY\n"
                       b"set command quoting on\n")
    _, received = run_session(run_wermit, ssl_pki, tmp_path, switch, b"Z",
                              answer=True, commands=f"take {script}, ")
    data, _ = telnet_split(received)
    assert b"X\xffY" in data, received


@pytest.mark.parametrize("switch", PASSIVE)
def test_passive_starts_telnet_on_peer_iac(run_wermit, ssl_pki,
                                           tmp_path, switch):
    """Verify a literal 0xFF from the peer starts Telnet on /SSL.

    The client then sends its options, reads the peer's IAC IAC as
    0xFF and CR NUL as CR, and sends IAC DO LOGOUT at close.
    """
    send = bytes([0x41, IAC, IAC, 0x42, 0x0D, 0x00, 0x43]) + b"Z"
    session, received = run_session(run_wermit, ssl_pki, tmp_path,
                                    switch, send, answer=True)
    _, cmds = telnet_split(received)
    assert (WILL, TTYPE) in cmds, cmds
    assert cmds[-1] == (DO, LOGOUT), cmds
    assert session == b"A\xffB\rCZ", session


@pytest.mark.parametrize("switch", PASSIVE)
def test_passive_keeps_literal_iac_read_during_wait(run_wermit, ssl_pki,
                                                    tmp_path, switch):
    """Verify a literal 0xFF read by the tn_ini() wait reaches INPUT.

    The peer's first bytes are IAC IAC.  tn_wait() reads them, starts
    Telnet and hands the data back.  INPUT then reads one 0xFF.
    """
    send = bytes([IAC, IAC, 0x41]) + b"Z"
    session, _ = run_session(run_wermit, ssl_pki, tmp_path, switch, send,
                             answer=True)
    assert session == b"\xffAZ", session


@pytest.mark.parametrize("switch", ACTIVE)
def test_active_negotiates_without_start_tls(run_wermit, ssl_pki,
                                             tmp_path, switch):
    """Verify /SSL-TELNET negotiates Telnet and refuses START_TLS.

    The client sends its options first and refuses START_TLS and
    ENCRYPTION inside TLS.  It reads the peer's data as Telnet NVT
    and sends IAC DO LOGOUT at close.
    """
    send = bytes([IAC, DO, START_TLS, IAC, DO, ENCRYPTION,
                  0x41, IAC, IAC, 0x42, 0x0D, 0x00, 0x43]) + b"Z"
    session, received = run_session(run_wermit, ssl_pki, tmp_path,
                                    switch, send, answer=True,
                                    delay=0.5)
    _, cmds = telnet_split(received)
    assert received[:1] == bytes([IAC]), received
    assert (WILL, TTYPE) in cmds, cmds
    for verb in (WILL, DO):
        for opt in (START_TLS, ENCRYPTION):
            assert (verb, opt) not in cmds, cmds
    assert (WONT, START_TLS) in cmds, cmds
    assert (WONT, ENCRYPTION) in cmds, cmds
    assert cmds[-1] == (DO, LOGOUT), cmds
    assert session == b"A\xffB\rCZ", session

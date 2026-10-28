"""
Tests for Telnet subnegotiation handling in ckctel.c.

Verifies that an unclosed subnegotiation (IAC SB without IAC SE) followed
by peer connection closure does not cause wermit to hang.
"""
import os
import re
import socket
import subprocess
import threading

import pytest

IAC = 255
SB = 250

# Telnet option NEW-ENVIRON (RFC 1572), used for the subnegotiation payload.
TELOPT_NEW_ENVIRON = 39


def test_telnet_truncated_subnegotiation_no_hang(spawn_wermit, wermit_path):
    """Verify unclosed subnegotiation does not hang on peer disconnect."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    proc = spawn_wermit([
        "-H", "-Y", "-C",
        "set command more-prompting off, set delay 0, "
        f"set host 127.0.0.1 {port} /telnet, pause 5, close, exit",
    ])

    try:
        server_sock.settimeout(10)
        conn, _ = server_sock.accept()
        try:
            conn.settimeout(5)
            # Send an incomplete subnegotiation without a terminating IAC SE.
            conn.sendall(
                bytes([IAC, SB, TELOPT_NEW_ENVIRON,
                       ord('X'), ord('Y'), ord('Z')]))
        finally:
            conn.close()
    finally:
        server_sock.close()

    try:
        returncode = proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        pytest.fail(
            "wermit hung after a Telnet subnegotiation was left open "
            "(IAC SB with no closing IAC SE, then connection closed)"
        )

    # Peer disconnection is an error condition, so wermit may exit non-zero.
    # The assertion verifies that the process exited rather than hanging.
    assert returncode is not None


SE = 240
WILL, WONT, DO, DONT = 251, 252, 253, 254
TELOPT_TTYPE = 24
TELOPT_NAWS = 31
MARKER = b"MARKER-OK"


def _serve_once(payload):
    """Start a one-connection Telnet peer that sends payload.

    Sends payload followed by MARKER. Refuses all offered options to
    finish negotiation, then reads until the client closes. Returns
    (port, thread, listening socket).
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(15)

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(30)
            try:
                conn.sendall(payload + b"\r\n" + MARKER + b"\r\n")
                pending = b""
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    pending += data
                    i = 0
                    while i < len(pending):
                        if pending[i] != IAC:
                            i += 1
                        elif i + 2 >= len(pending):
                            break       # Incomplete; wait for more
                        elif pending[i + 1] in (WILL, DO):
                            reply = DONT if pending[i + 1] == WILL else WONT
                            conn.sendall(bytes([IAC, reply,
                                                pending[i + 2]]))
                            i += 3
                        else:
                            i += 2
                    pending = pending[i:]
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return srv.getsockname()[1], thread, srv


def _expect_marker_after(run_wermit, payload):
    """Verify wermit survives payload and then reads MARKER.

    Returns the received data as uppercase hex. INPUT echo is disabled
    because the payload can contain invalid UTF-8 bytes.
    """
    port, thread, srv = _serve_once(payload)
    try:
        result = run_wermit(
            "set delay 0, set input echo off, "
            f"set host 127.0.0.1 {port} /telnet, "
            f"input 10 {MARKER.decode()}, "
            "if success echo GOT-MARKER, "
            "echo HEX=[\\fhexify(\\v(input))], "
            "close, exit",
            timeout=30,
        )
    finally:
        srv.close()
        thread.join(timeout=5)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "GOT-MARKER" in result.stdout, result.stdout
    match = re.search(r"HEX=\[([0-9A-Fa-f]*)\]", result.stdout)
    assert match, result.stdout
    return match.group(1).upper()


def _sb(opt, data):
    """Return a subnegotiation packet for opt with data, quoting IAC."""
    return (bytes([IAC, SB, opt]) + data.replace(b"\xff", b"\xff\xff")
            + bytes([IAC, SE]))


# TSBUFSIZ is 1024, or 2056 with CK_FORWARD_X; cover both edges.
@pytest.mark.parametrize("length", [1022, 1023, 1024, 1025,
                                    2054, 2055, 2056, 2057, 5000])
def test_telnet_subnegotiation_boundary_lengths(run_wermit, length):
    """Verify a TTYPE subnegotiation near the buffer size is handled."""
    _expect_marker_after(run_wermit, _sb(TELOPT_TTYPE, b"A" * length))


@pytest.mark.parametrize("length", [1023, 1024, 2056, 5000])
def test_telnet_subnegotiation_quoted_iacs(run_wermit, length):
    """Verify quoted IAC bytes filling a subnegotiation are handled."""
    _expect_marker_after(run_wermit, _sb(TELOPT_TTYPE, b"\xff" * length))


@pytest.mark.parametrize("opt", [TELOPT_TTYPE, TELOPT_NAWS,
                                 TELOPT_NEW_ENVIRON])
def test_telnet_empty_subnegotiation(run_wermit, opt):
    """Verify a subnegotiation with no data bytes is handled."""
    _expect_marker_after(run_wermit, _sb(opt, b""))


@pytest.mark.parametrize("data", [
    b"\x00",
    b"\x00\x50\x00",
    b"\xff\xff\xff\xff",
    b"\x00\x50\x00\x18" + b"Z" * 3000,
], ids=["too-short", "one-short", "max-values", "trailing-data"])
def test_telnet_naws_odd_lengths(run_wermit, data):
    """Verify NAWS subnegotiations of the wrong length are handled."""
    _expect_marker_after(run_wermit, _sb(TELOPT_NAWS, data))


@pytest.mark.parametrize("data", [
    b"\x01",
    b"\x01\x00" + b"V" * 3000,
    b"\x01" + b"\x00USER\x01" * 400,
    b"\x00\x00" + b"N" * 1500 + b"\x01" + b"V" * 1500,
], ids=["send-empty", "send-long-name", "send-many-names", "is-long"])
def test_telnet_new_environ_long_data(run_wermit, data):
    """Verify long NEW-ENVIRON subnegotiations are handled."""
    _expect_marker_after(run_wermit, _sb(TELOPT_NEW_ENVIRON, data))


@pytest.mark.parametrize("length", [1022, 1023, 1024, 1025,
                                    2054, 2055, 2056, 2057])
def test_telnet_subnegotiation_no_stray_se(run_wermit, length):
    """Verify no byte of IAC SE reaches the data stream.

    At TSBUFSIZ - 1 data bytes, the payload and closing IAC fill
    the buffer. The trailing SE must still be consumed as part of the
    subnegotiation.
    """
    received = _expect_marker_after(run_wermit,
                                    _sb(TELOPT_TTYPE, b"A" * length))
    octets = [received[i:i + 2] for i in range(0, len(received), 2)]
    assert "F0" not in octets, received[:200]


def test_telnet_subnegotiation_bad_terminator(run_wermit):
    """Verify an invalid subnegotiation terminator ends negotiation.

    IAC followed by a non-SE byte ends the subnegotiation without
    dropping subsequent data.
    """
    payload = (bytes([IAC, SB, TELOPT_TTYPE]) + b"A" * 100
               + bytes([IAC, 1]))
    _expect_marker_after(run_wermit, payload)


TELQUAL_SEND = 1


def _serve_new_environ(send_data):
    """Start a Telnet peer that requests NEW-ENVIRON variables.

    Sends DO NEW-ENVIRON and refuses every other option. When the
    client agrees, sends SB NEW-ENVIRON SEND send_data, then MARKER.
    Records everything the client sends in the returned list.
    Returns (port, thread, listening socket, list).
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(15)
    received = []

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(30)
            try:
                conn.sendall(bytes([IAC, DO, TELOPT_NEW_ENVIRON]))
                pending = b""
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    received.append(data)
                    pending += data
                    i = 0
                    while i < len(pending):
                        if pending[i] != IAC:
                            i += 1
                        elif i + 2 >= len(pending):
                            break       # Incomplete; wait for more
                        elif pending[i + 1] in (WILL, DO):
                            opt = pending[i + 2]
                            if (opt == TELOPT_NEW_ENVIRON
                                    and pending[i + 1] == WILL):
                                conn.sendall(
                                    _sb(TELOPT_NEW_ENVIRON,
                                        bytes([TELQUAL_SEND]) + send_data)
                                    + b"\r\n" + MARKER + b"\r\n")
                            else:
                                reply = (DONT if pending[i + 1] == WILL
                                         else WONT)
                                conn.sendall(bytes([IAC, reply, opt]))
                            i += 3
                        else:
                            i += 2
                    pending = pending[i:]
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return srv.getsockname()[1], thread, srv, received


def _new_environ_reply(run_wermit, send_data, userid="kermtest",
                       setup=""):
    """Return the data of the client's NEW-ENVIRON IS reply to send_data.

    Verifies wermit survives the request and then reads MARKER.  The
    data is returned as sent, with IAC still doubled.
    """
    port, thread, srv, received = _serve_new_environ(send_data)
    try:
        result = run_wermit(
            "set delay 0, set input echo off, "
            f"set login userid {userid}, {setup}"
            f"set host 127.0.0.1 {port} /telnet, "
            f"input 10 {MARKER.decode()}, "
            "if success echo GOT-MARKER, "
            "close, exit",
            timeout=30,
        )
    finally:
        srv.close()
        thread.join(timeout=5)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "GOT-MARKER" in result.stdout, result.stdout
    sent = b"".join(received)
    start = sent.find(bytes([IAC, SB, TELOPT_NEW_ENVIRON, 0]))
    assert start >= 0, sent
    end = sent.find(bytes([IAC, SE]), start)
    assert end >= 0, sent
    return sent[start + 4:end]


@pytest.mark.parametrize("length", [16, 17, 40, 300])
def test_telnet_new_environ_send_long_name(run_wermit, length):
    """Verify a requested variable name past 16 bytes is handled.

    No variable has such a name, so the reply is empty.
    """
    assert _new_environ_reply(run_wermit, b"\x00" + b"A" * length) == b""


def test_telnet_new_environ_send_escaped_delimiters(run_wermit):
    """Verify ESC-quoted delimiters are part of the requested name.

    Each request asks for a name containing a quoted VAR byte. No
    variable matches, so the reply is empty.
    """
    send_data = b"\x00X\x02\x00USER" * 5
    assert _new_environ_reply(run_wermit, send_data) == b""


def test_telnet_new_environ_send_user(run_wermit):
    """Verify a request for USER is answered with the login user ID."""
    assert (_new_environ_reply(run_wermit, b"\x00USER")
            == b"\x00USER\x01kermtest")


TELOPT_COMPORT = 44
COMPORT_SIGNATURE = 0
COMPORT_SET_BAUDRATE = 1
COMPORT_SET_CONTROL = 5
COMPORT_SERVER_OFFSET = 100


def _comport_reply(command, data, state):
    """Return the data of a COM-PORT server's reply to a client request.

    A zero value queries the current setting. Any other value is a new
    setting that the server accepts.
    """
    if command == COMPORT_SIGNATURE and not data:
        return b"TestPort"
    if command == COMPORT_SET_BAUDRATE:
        if data == bytes(4):
            return state["baud"]
        state["baud"] = data
        return data
    if data == b"\x00" and command in (2, 3, 4):
        return bytes([{2: 8, 3: 1, 4: 1}[command]])  # 8 data, N, 1 stop
    if command == COMPORT_SET_CONTROL and data in (b"\x00", b"\x0d"):
        return bytes([data[0] + 1])     # No outbound or inbound flow
    return data


def _serve_comport(baud):
    """Start a Telnet peer that is an RFC 2217 COM-PORT server.

    Agrees to COM-PORT, refuses every other option, and answers each
    COM-PORT request. The port's rate starts at baud. Records each
    COM-PORT request as (command, data). Returns (port, thread,
    listening socket, list).
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(15)
    requests = []
    state = {"baud": baud.to_bytes(4, "big")}

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(30)
            pending = b""
            try:
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    pending += data
                    while True:
                        i = pending.find(bytes([IAC]))
                        if i < 0:
                            pending = b""
                            break
                        if i + 2 >= len(pending):
                            pending = pending[i:]
                            break
                        cmd, opt = pending[i + 1], pending[i + 2]
                        if cmd in (WILL, DO, WONT, DONT):
                            if cmd == WILL:
                                reply = DO if opt == TELOPT_COMPORT else DONT
                                conn.sendall(bytes([IAC, reply, opt]))
                            elif cmd == DO:
                                conn.sendall(bytes([IAC, WONT, opt]))
                            pending = pending[i + 3:]
                        elif cmd == SB:
                            end = pending.find(bytes([IAC, SE]), i)
                            if end < 0:
                                pending = pending[i:]
                                break
                            body = pending[i + 2:end]
                            pending = pending[end + 2:]
                            if body[0] == TELOPT_COMPORT and len(body) > 1:
                                requests.append((body[1], body[2:]))
                                reply = _comport_reply(body[1], body[2:],
                                                       state)
                                conn.sendall(
                                    _sb(TELOPT_COMPORT,
                                        bytes([body[1]
                                               + COMPORT_SERVER_OFFSET])
                                        + reply))
                        else:
                            pending = pending[i + 2:]
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return srv.getsockname()[1], thread, srv, requests


def test_telnet_comport_baud_rate_bytes(run_wermit):
    """Verify COM-PORT baud rates are sent and read most significant first.

    The server reports 9600 at connect time; SET SPEED 115200 must
    send 00 01 C2 00.
    """
    port, thread, srv, requests = _serve_comport(9600)
    try:
        result = run_wermit(
            "set delay 0, "
            f"set host 127.0.0.1 {port} /telnet, "
            "echo SPEED1=[\\v(speed)], "
            "set speed 115200, "
            "echo SPEED2=[\\v(speed)], "
            "close, exit",
            timeout=30,
        )
    finally:
        srv.close()
        thread.join(timeout=5)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "SPEED1=[9600]" in result.stdout, result.stdout
    assert ((COMPORT_SET_BAUDRATE, bytes([0, 1, 0xC2, 0]))
            in requests), requests
    assert "SPEED2=[115200]" in result.stdout, result.stdout


TELOPT_FORWARD_X = 49
FWDX_XOFF, FWDX_XON = 6, 7


def _fake_x_display():
    """Listen on an X display TCP port.  Return (display number, socket)."""
    for n in range(10, 60):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", 6000 + n))
        except OSError:
            s.close()
            continue
        s.listen(4)
        return n, s
    pytest.skip("no free X display port")


@pytest.mark.parametrize("cmd", [FWDX_XOFF, FWDX_XON])
@pytest.mark.parametrize("channel", [b"\xff\xff", b"\x00\x40", b"\x00"])
def test_telnet_forward_x_flow_control_unknown_channel(
        run_wermit, monkeypatch, cmd, channel):
    """Verify FORWARD-X XOFF/XON for an unknown channel id is ignored.

    The channel number on the wire is an id, not a table index.  An id
    with no open channel, or a short subnegotiation, must not index the
    channel table.
    """
    display, xsock = _fake_x_display()
    monkeypatch.setenv("DISPLAY", f"127.0.0.1:{display}")
    payload = (bytes([IAC, WILL, TELOPT_FORWARD_X])
               + _sb(TELOPT_FORWARD_X, bytes([cmd]) + channel))
    port, thread, srv = _serve_once(payload)
    try:
        result = run_wermit(
            "set delay 0, set input echo off, "
            "set telopt /client forward-x accepted, "
            "set telnet forward-x no-encryption, "
            f"set host 127.0.0.1 {port} /telnet, "
            f"input 10 {MARKER.decode()}, "
            "if success echo GOT-MARKER, close, exit",
            timeout=30)
    finally:
        srv.close()
        xsock.close()
        thread.join(timeout=5)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "GOT-MARKER" in result.stdout, result.stdout


def test_telnet_stall_inside_iac_times_out(run_wermit):
    """Verify a peer that stops inside an IAC sequence cannot hang a read.

    The server sends one IAC byte during a transfer and then nothing.
    The packet read must still time out, so GET fails within its retry
    limit instead of waiting forever.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(15)
    done = threading.Event()

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            try:
                done.wait(3)
                conn.sendall(bytes([IAC]))
                done.wait(60)
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    port = srv.getsockname()[1]
    try:
        result = run_wermit(
            "set delay 0, set telnet wait off, "
            f"set host 127.0.0.1 {port} /telnet, "
            "set send timeout 2, set receive timeout 2, set retry 3, "
            "get foo, echo STATUS=\\v(status), close, exit",
            timeout=45)
    finally:
        done.set()
        srv.close()
        thread.join(timeout=5)
    assert "STATUS=1" in result.stdout, result.stdout


TELOPT_AUTHENTICATION, TELOPT_ENCRYPTION = 37, 38


@pytest.mark.parametrize("payload", [
    _sb(TELOPT_AUTHENTICATION, b""),
    _sb(TELOPT_AUTHENTICATION, b"\x00"),            # IS, no type
    _sb(TELOPT_AUTHENTICATION, b"\x00\x07"),        # IS, no modifiers
    _sb(TELOPT_AUTHENTICATION, b"\x00\x07\x55"),    # IS, unrequested pair
    _sb(TELOPT_AUTHENTICATION, b"\x02"),            # REPLY, no type
    _sb(TELOPT_AUTHENTICATION, b"\x01\x09"),        # SEND, odd list
    _sb(TELOPT_ENCRYPTION, b""),
    _sb(TELOPT_ENCRYPTION, b"\x07"),                # ENC_KEYID, empty
], ids=["auth-empty", "auth-is-short", "auth-is-no-mod", "auth-is-pair",
        "auth-reply-short", "auth-send-odd", "enc-empty", "enc-keyid"])
def test_telnet_short_auth_encrypt_subnegotiations(run_wermit, payload):
    """Verify short AUTHENTICATION and ENCRYPTION SBs are handled.

    Each handler indexes the subnegotiation by position.  A short one
    must not be read past its end.  The overread shows only under
    AddressSanitizer.  A normal build checks that the session goes on.
    """
    negotiate = bytes([IAC, DO, TELOPT_AUTHENTICATION,
                       IAC, WILL, TELOPT_ENCRYPTION,
                       IAC, DO, TELOPT_ENCRYPTION])
    _expect_marker_after(run_wermit, negotiate + payload)


def test_telnet_new_environ_reply_over_250_bytes(run_wermit):
    """Verify a NEW-ENVIRON reply longer than 250 bytes is sent."""
    setup = "".join(f"set telnet environment {k} {k[0] * 60}, "
                    for k in ("job", "printer", "systemtype", "display"))
    reply = _new_environ_reply(run_wermit, b"", setup=setup)
    assert len(reply) > 250, reply
    for name, val in ((b"JOB", b"j"), (b"PRINTER", b"p"),
                      (b"SYSTEMTYPE", b"s")):
        assert b"\x00" + name + b"\x01" + val * 60 in reply, reply


def test_telnet_new_environ_reply_quotes_value(run_wermit):
    """Verify special bytes in a value are ESC-quoted and IAC doubled.

    Byte 1 (VALUE) is preceded by ESC (2).  Byte 255 (IAC) is sent
    twice.
    """
    reply = _new_environ_reply(run_wermit, b"\x00USER",
                               userid="ab\\1cd\\255ef")
    assert reply == b"\x00USER\x01ab\x02\x01cd\xff\xffef", reply


def _naws_to_server(wermit_path, tmp_path, port, subnegotiations):
    """Send NAWS subnegotiations to wermit as a Telnet server.

    wermit listens with SET HOST * and logs debug output.  The client
    answers DO NAWS with WILL NAWS and refuses every other option.  It
    then sends each subnegotiation and a line that ends the server's
    INPUT.  Returns the widths and heights the server's debug log
    records.
    """
    log = tmp_path / "debug.log"
    proc = subprocess.Popen(
        [wermit_path, "-H", "-Y", "-C",
         "set command more-prompting off, set tcp reverse-dns-lookup off, "
         f"log debug {log}, set host * {port} /telnet, "
         "input 10 DONE, close, exit"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, cwd=str(tmp_path))
    try:
        conn = None
        for _ in range(100):
            try:
                conn = socket.create_connection(("127.0.0.1", port), 1)
                break
            except OSError:
                threading.Event().wait(0.1)
        assert conn is not None, "server never listened"
        with conn:
            conn.settimeout(10)
            pending = b""
            sent = False
            while proc.poll() is None:
                try:
                    data = conn.recv(4096)
                except OSError:         # Timeout, or reset at exit
                    break
                if not data:
                    break
                pending += data
                i = 0
                while i + 2 < len(pending) or (
                        i < len(pending) and pending[i] != IAC):
                    if pending[i] != IAC:
                        i += 1
                        continue
                    cmd, opt = pending[i + 1], pending[i + 2]
                    if cmd == DO and opt == TELOPT_NAWS and not sent:
                        conn.sendall(bytes([IAC, WILL, TELOPT_NAWS]))
                        for sub in subnegotiations:
                            conn.sendall(_sb(TELOPT_NAWS, sub))
                        conn.sendall(b"DONE\r\n")
                        sent = True
                    elif cmd in (WILL, DO):
                        reply = DONT if cmd == WILL else WONT
                        conn.sendall(bytes([IAC, reply, opt]))
                    i += 3 if cmd in (WILL, WONT, DO, DONT) else 2
                pending = pending[i:]
            proc.wait(timeout=20)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
    text = log.read_text(errors="replace")
    return re.findall(r"tn_doop NAWS SB\[(width|height)\]=(\d+)", text)


@pytest.mark.parametrize("data", [b"", b"\x00", b"\x00\x50\x00"],
                         ids=["empty", "one", "three"])
def test_telnet_server_naws_short(wermit_path, tmp_path, get_free_port,
                                  data):
    """Verify a Telnet server ignores NAWS with fewer than four bytes.

    NAWS holds a width and height of two bytes each.  The client sends
    a short NAWS and then a valid one of 100 by 30.  The server must
    record only the valid size.
    """
    sizes = _naws_to_server(wermit_path, tmp_path, get_free_port(),
                            [data, b"\x00\x64\x00\x1e"])
    assert sizes == [("width", "100"), ("height", "30")], sizes


TELOPT_ENCRYPTION = 38


@pytest.mark.parametrize("data,expect", [
    (b"\x01\x01\x02", "SUPPORT DES_CFB64 DES_OFB64"),
    (b"\x01\x01\xc8\x02", "SUPPORT DES_CFB64 \r\n  c8 02"),
    (b"\x01" + b"\x01" * 40, "SUPPORT" + " DES_CFB64" * 15 + " \r\n  01"),
    (b"\x02\xc8\x01", "REPLY UNKNOWN FB64_IV"),
], ids=["support", "support-unknown", "support-long", "reply-unknown"])
def test_telnet_debug_encryption_names(run_wermit, tmp_path, data,
                                       expect):
    """Verify the debug log names ENCRYPTION types within the table.

    tn_sb() decodes each subnegotiation for the debug log.  It names
    each encryption type below ENCTYPE_CNT and shows the rest in hex.
    The decoded line holds at most 15 names after SUPPORT.
    """
    log = tmp_path / "debug.log"
    port, thread, srv = _serve_once(_sb(TELOPT_ENCRYPTION, data))
    try:
        result = run_wermit(
            f"log debug {log}, set delay 0, set input echo off, "
            f"set host 127.0.0.1 {port} /telnet, "
            f"input 10 {MARKER.decode()}, "
            "if success echo GOT-MARKER, close, close debug, exit",
            timeout=30)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "GOT-MARKER" in result.stdout, result.stdout
    text = log.read_bytes().decode(errors="replace")
    assert "TELNET RCVD SB ENCRYPTION " + expect in text, [
        x for x in text.splitlines() if "RCVD SB ENC" in x]


def test_telnet_client_ignores_server_terminal_type(wermit_path, tmp_path):
    """Verify a Telnet client keeps TERM when the server sends TTYPE IS.

    Only a client sends TTYPE IS (RFC 1091).  The server here sends DO
    TTYPE and then TTYPE IS vt52.  The client's TERM must stay xterm.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(15)

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(10)
            try:
                conn.sendall(bytes([IAC, DO, TELOPT_TTYPE]))
                buf = b""
                while bytes([IAC, WILL, TELOPT_TTYPE]) not in buf:
                    data = conn.recv(4096)
                    if not data:
                        return
                    buf += data
                conn.sendall(_sb(TELOPT_TTYPE, b"\x00vt52")
                             + b"\r\n" + MARKER + b"\r\n")
                while conn.recv(4096):
                    pass
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    env = dict(os.environ, TERM="xterm")
    try:
        result = subprocess.run(
            [wermit_path, "-H", "-Y", "-C",
             "set command more-prompting off, set delay 0, "
             "set input echo off, "
             f"set host 127.0.0.1 {srv.getsockname()[1]} /telnet, "
             f"input 10 {MARKER.decode()}, "
             "echo TERM=[\\$(TERM)], close, exit"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=60, env=env)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert "TERM=[xterm]" in result.stdout, result.stdout


def test_telnet_server_takes_client_terminal_type(wermit_path, tmp_path,
                                                  get_free_port):
    """Verify a Telnet server sets TERM from the client's TTYPE IS.

    wermit listens with SET HOST *.  The client answers DO TTYPE with
    WILL TTYPE and TTYPE SEND with TTYPE IS VT220.  The server must set
    TERM to vt220.
    """
    port = get_free_port()
    proc = subprocess.Popen(
        [wermit_path, "-H", "-Y", "-C",
         "set command more-prompting off, set tcp reverse-dns-lookup off, "
         f"set host * {port} /telnet, input 10 DONE, "
         "echo TERM=[\\$(TERM)], close, exit"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, cwd=str(tmp_path),
        env=dict(os.environ, TERM="xterm"))
    try:
        conn = None
        for _ in range(100):
            try:
                conn = socket.create_connection(("127.0.0.1", port), 1)
                break
            except OSError:
                threading.Event().wait(0.1)
        assert conn is not None, "server never listened"
        with conn:
            conn.settimeout(10)
            pending = b""
            sent = False
            ttsend = bytes([IAC, SB, TELOPT_TTYPE, 1, IAC, SE])
            while proc.poll() is None:
                try:
                    data = conn.recv(4096)
                except OSError:
                    break
                if not data:
                    break
                pending += data
                if ttsend in pending and not sent:
                    conn.sendall(_sb(TELOPT_TTYPE, b"\x00VT220")
                                 + b"DONE\r\n")
                    sent = True
                    pending = pending.replace(ttsend, b"")
                i = 0
                while i + 2 < len(pending):
                    if pending[i] != IAC:
                        i += 1
                        continue
                    cmd, opt = pending[i + 1], pending[i + 2]
                    if cmd == DO and opt == TELOPT_TTYPE:
                        conn.sendall(bytes([IAC, WILL, TELOPT_TTYPE]))
                    elif cmd in (WILL, DO):
                        reply = DONT if cmd == WILL else WONT
                        conn.sendall(bytes([IAC, reply, opt]))
                    i += 3 if cmd in (WILL, WONT, DO, DONT) else 2
                pending = pending[i:]
            out, _ = proc.communicate(timeout=20)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
    assert "TERM=[vt220]" in out, out

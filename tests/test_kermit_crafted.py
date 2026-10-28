"""Tests for Kermit packet handling with crafted partner packets.

A scripted partner on a raw TCP socket answers wermit's packets with
packets built here.  Overflows show only under AddressSanitizer.  A
normal build checks that wermit ends the transfer and exits.
"""
import socket
import threading

import pytest

from conftest import scaled


def tochar(x):
    """Return the printable encoding of a small number."""
    return x + 32


def packet(seq, ptype, data, rawseq=None):
    """Return a Kermit packet with a type 1 block check.

    rawseq, when given, is the sequence byte as sent on the wire.
    """
    seqbyte = rawseq if rawseq is not None else tochar(seq & 63)
    body = bytes([seqbyte, ord(ptype)]) + data
    head = bytes([tochar(len(body) + 1)]) + body
    total = sum(head)
    check = tochar((total + ((total & 192) >> 6)) & 63)
    return b"\x01" + head + bytes([check]) + b"\r"


def default_init(npad=0):
    """Return Send-Init parameters with the given pad count."""
    params = bytearray(b"~* @-#Y1~")   # maxl, time, npad, padc, eol, ...
    params[2] = tochar(npad)
    return bytes(params)


def _run_partner(run_wermit, tmp_path, answer, wermit_cmds, timeout=30):
    """Run wermit against a partner.  answer(pkt_bytes) returns a reply."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(15)
    port = srv.getsockname()[1]

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(10)
            buf = b""
            try:
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    buf += data
                    while b"\r" in buf:
                        pkt, buf = buf.split(b"\r", 1)
                        i = pkt.find(b"\x01")
                        if i < 0 or len(pkt) < i + 4:
                            continue
                        reply = answer(pkt[i:])
                        if reply:
                            conn.sendall(reply)
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        result = run_wermit(
            f"cd {tmp_path}, set host 127.0.0.1 {port} /raw-socket, "
            "set send timeout 2, set receive timeout 2, set retry 3, "
            f"{wermit_cmds}, echo STATUS=\\v(status), close, exit",
            timeout=timeout)
    finally:
        srv.close()
        thread.join(timeout=5)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    return result


@pytest.mark.parametrize("npad", [200, 96, 0])
def test_partner_padding_count_is_bounded(run_wermit, tmp_path, npad):
    """Verify a partner's Send-Init pad count is limited to padbuf[].

    The partner asks for npad pad characters in its ACK to wermit's S
    packet, then ends the transfer with an error packet.
    """
    (tmp_path / "f.txt").write_text("hello\n")

    def answer(pkt):
        seq = pkt[2] - 32
        if pkt[3:4] == b"S":
            return packet(seq, "Y", default_init(npad))
        return packet(seq, "E", b"stop")

    result = _run_partner(run_wermit, tmp_path, answer, "send f.txt")
    assert "STATUS=1" in result.stdout, result.stdout


@pytest.mark.parametrize("rawseq", [0x1F, 0x7F, 0xFF])
def test_partner_bad_sequence_number_is_ignored(run_wermit, tmp_path,
                                                rawseq):
    """Verify a packet whose sequence is outside 0-63 is not used.

    The partner answers each packet with an ACK carrying an invalid
    sequence byte, so wermit sees only bad packets until it gives up.
    """
    (tmp_path / "f.txt").write_text("hello\n")

    def answer(pkt):
        return packet(0, "Y", default_init(), rawseq=rawseq)

    result = _run_partner(run_wermit, tmp_path, answer, "send f.txt")
    assert "STATUS=1" in result.stdout, result.stdout


def test_partner_damaged_packets_are_ignored(run_wermit, tmp_path):
    """Verify packets with a bad block check do not index the tables.

    After a valid Send-Init exchange the partner answers every packet
    with a damaged ACK.  rpack() rejects each one, and the sequence
    number it leaves behind must not be used.
    """
    (tmp_path / "f.txt").write_text("x" * 5000)

    def answer(pkt):
        seq = pkt[2] - 32
        if pkt[3:4] == b"S":
            return packet(seq, "Y", default_init())
        good = packet(seq, "Y", b"")
        return good[:-2] + bytes([good[-2] ^ 1]) + good[-1:]

    result = _run_partner(run_wermit, tmp_path, answer, "send f.txt")
    assert "STATUS=1" in result.stdout, result.stdout


@pytest.mark.parametrize("claim", [b"~", b" "], ids=["regular", "long"])
def test_partner_length_beyond_received_bytes(wermit_path, tmp_path,
                                              valgrind, claim):
    """Verify rpack() refuses a packet longer than the bytes received.

    The partner answers the S packet with a packet whose LEN field
    claims more data than it sends.  "~" claims 94 bytes; " " announces
    an extended header that is cut short.  rpack() must not compute the
    block check over buffer space that was never written.
    """
    import subprocess
    (tmp_path / "f.txt").write_text("hello\n")
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
                buf = b""
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    buf += data
                    while b"\r" in buf:
                        pkt, buf = buf.split(b"\r", 1)
                        i = pkt.find(b"\x01")
                        if i >= 0 and len(pkt) > i + 3:
                            seq = pkt[i + 2]
                            conn.sendall(b"\x01" + claim + bytes([seq])
                                         + b"Yab\r")
            except OSError:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        result = subprocess.run(
            [valgrind, "-q", "--error-exitcode=9", wermit_path,
             "-H", "-Y", "-Q", "-C",
             f"cd {tmp_path}, set host 127.0.0.1 "
             f"{srv.getsockname()[1]} /raw-socket, "
             "set send timeout 1, set retry 2, send f.txt, "
             "echo STATUS=\\v(status), close, exit 0"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=scaled(120))
    finally:
        srv.close()
        thread.join(timeout=5)
    assert "uninitialised" not in result.stderr, result.stderr
    assert "STATUS=1" in result.stdout, result.stdout + result.stderr


@pytest.mark.parametrize("rawseq", [0x1F, 0xFF])
def test_streaming_bad_sequence_is_not_reused(run_wermit, tmp_path,
                                              rawseq):
    """Verify a bad sequence number is not used while streaming.

    The partner negotiates streaming and answers the first Data packet
    with a packet whose sequence is outside 0-63.  While streaming,
    rpack() returns 'Y' when nothing has arrived and leaves rsn as it
    was.  input() must not index its tables with the rejected number.
    """
    (tmp_path / "f.txt").write_text("x" * 20000)
    # CAPAS, window, MAXLX1, MAXLX2, four checkpoint fields, WHATAMI
    # with WMI_FLAG and WMI_STREAM.
    init = default_init() + b"  " + b"  " + b"    " + bytes([tochar(40)])
    sent = []

    def answer(pkt):
        seq = pkt[2] - 32
        ptype = pkt[3:4]
        if ptype == b"S":
            return packet(seq, "Y", init)
        if ptype == b"D":
            if sent:
                return b""
            sent.append(seq)
            return packet(seq, "Y", b"", rawseq=rawseq)
        return packet(seq, "Y", b"")

    result = _run_partner(run_wermit, tmp_path, answer,
                          "set streaming on, send f.txt")
    assert "STATUS=" in result.stdout, result.stdout + result.stderr


def test_attribute_refusal_reply_is_bounded(run_wermit, tmp_path):
    """Verify the reply to an attribute packet fits rpbuf[] in gattr().

    The partner sends a file whose A packet holds 40 empty record
    format attributes.  gattr() refuses each one and adds its tag to
    the reply.  The reply must stay within rpbuf[] (20 characters).
    """
    # CAPAS with the attribute bit after the nine basic fields.
    init = default_init() + bytes([tochar(8)])
    replies = {}

    def answer(pkt):
        seq = pkt[2] - 32
        ptype = pkt[3:4]
        if ptype == b"N":
            return packet(0, "S", init) if seq == 0 else b""
        if seq == 0:
            return packet(1, "F", b"f.txt")
        if seq == 1:
            return packet(2, "A", b"/ " * 40)
        replies[seq] = pkt[4:-1]
        return packet(3, "E", b"stop")

    result = _run_partner(run_wermit, tmp_path, answer,
                          "set receive confirm off, receive")
    assert "STATUS=1" in result.stdout, result.stdout
    reply = replies.get(2)
    assert reply is not None, result.stdout
    assert reply.startswith(b"N/"), reply
    assert len(reply) <= 20, reply


@pytest.mark.parametrize("code,reason", [
    (b"@", "@"), (b"A", "unknown"), (b"!", "size")])
def test_attribute_refusal_reason_lookup(run_wermit, tmp_path, code,
                                         reason):
    """Verify getreason() maps each refusal code within reason[].

    The partner refuses the file in its reply to the A packet.  "@" is
    the last entry of reason[].  "A" is one past it and has no name.
    The transaction log records the reason.
    """
    (tmp_path / "f.txt").write_text("hello\n")
    init = default_init() + bytes([tochar(8)])

    def answer(pkt):
        seq = pkt[2] - 32
        ptype = pkt[3:4]
        if ptype == b"S":
            return packet(seq, "Y", init)
        if ptype == b"A":
            return packet(seq, "Y", b"N" + code)
        return packet(seq, "Y", b"")

    log = tmp_path / "t.log"
    _run_partner(run_wermit, tmp_path, answer,
                 f"log transactions {log}, send f.txt, close transactions")
    text = log.read_text(errors="replace")
    assert f"refused: {reason}\n" in text, text


@pytest.mark.parametrize("attr", [
    b"/" + bytes([tochar(13)]) + b"AMJ0000000+!X",
    b"-" + bytes([tochar(4)]) + b"x+!X"],
    ids=["recfm", "gprotect"])
def test_attribute_long_field_is_skipped(run_wermit, tmp_path, attr):
    """Verify gattr() skips the whole of a long attribute.

    The record format attribute keeps ten characters and the generic
    protection attribute one.  The rest of each holds "+!X".  Taken for
    an attribute, it reads as an unknown disposition.
    The receiver must accept the file.
    """
    init = default_init() + bytes([tochar(8)])
    replies = {}

    def answer(pkt):
        seq = pkt[2] - 32
        ptype = pkt[3:4]
        if ptype == b"N":
            return packet(0, "S", init) if seq == 0 else b""
        if seq == 0:
            return packet(1, "F", b"f.txt")
        if seq == 1:
            return packet(2, "A", attr)
        replies[seq] = pkt[3:-1]
        return packet(3, "E", b"stop")

    result = _run_partner(run_wermit, tmp_path, answer,
                          "set receive confirm off, receive")
    assert replies.get(2) == b"Y", (replies, result.stdout)


@pytest.mark.parametrize("lengthk,fsize", [
    (b"18014398509481985", "-1"), (b"3", "3072")],
    ids=["overflow", "small"])
def test_attribute_length_in_k_overflow(run_wermit, tmp_path, lengthk,
                                        fsize):
    """Verify a length in K too large for a file offset is unknown.

    2^54 + 1 K is past the largest file offset.  Multiplied by 1024 it
    wraps to 1024.  gattr() must record the size as unknown (-1).  The
    debug log shows the size gattr() records.
    """
    init = default_init() + bytes([tochar(8)])
    attr = b"!" + bytes([tochar(len(lengthk))]) + lengthk

    def answer(pkt):
        seq = pkt[2] - 32
        ptype = pkt[3:4]
        if ptype == b"N":
            return packet(0, "S", init) if seq == 0 else b""
        if seq == 0:
            return packet(1, "F", b"f.txt")
        if seq == 1:
            return packet(2, "A", attr)
        return packet(3, "E", b"stop")

    log = tmp_path / "debug.log"
    _run_partner(run_wermit, tmp_path, answer,
                 f"log debug {log}, set receive confirm off, receive, "
                 "close debug")
    text = log.read_text(errors="replace")
    assert f"gattr fsize[{fsize}]" in text, [
        x for x in text.splitlines() if "gattr" in x]


@pytest.mark.parametrize("perms,mode", [
    (b"751", 0o751), (b"4755", 0o755), (b"6777", 0o777),
    (b"7" * 13 + b"644", 0o644)],
    ids=["plain", "setuid", "setgid", "long"])
def test_attribute_local_permissions_mask(run_wermit, tmp_path, perms,
                                          mode):
    """Verify a received file gets only the 0777 bits of its sender.

    The partner sends a file with system ID "U1" and the given local
    permissions.  zstime() applies the read, write and execute bits as
    sent.  It drops the setuid, setgid and sticky bits.  A string of
    16 digits keeps its last three.
    """
    init = default_init() + bytes([tochar(8)])
    attr = (b"." + bytes([tochar(2)]) + b"U1"
            + b"," + bytes([tochar(len(perms))]) + perms)
    script = {0: ("F", b"f.txt"), 1: ("A", attr), 2: ("D", b"hello"),
              3: ("Z", b""), 4: ("B", b"")}

    def answer(pkt):
        seq = pkt[2] - 32
        ptype = pkt[3:4]
        if ptype == b"N":
            return packet(0, "S", init) if seq == 0 else b""
        if ptype == b"Y" and seq in script:
            ptype, data = script[seq]
            return packet(seq + 1, ptype, data)
        return b""

    result = _run_partner(run_wermit, tmp_path, answer,
                          "set receive confirm off, receive")
    assert "STATUS=0" in result.stdout, result.stdout
    received = tmp_path / "f.txt"
    assert received.read_bytes() == b"hello"
    assert received.stat().st_mode & 0o7777 == mode, oct(
        received.stat().st_mode)


@pytest.mark.parametrize("offset,sent", [
    (b"!4", b"efghij"), (b"\"-1", b"abcdefghij"), (b"#1x0", None),
    (b"4" + b"9" * 20, None), (b"*12", None)],
    ids=["valid", "nofile", "nondigit", "overflow", "short"])
def test_resend_offset_from_receiver(run_wermit, tmp_path, offset, sent):
    """Verify the sender refuses a file for a malformed RESEND offset.

    The partner answers the A packet with "1", a length character, and
    the length of its partial file.  "!" is a length of 1, '"' of 2,
    "#" of 3, "*" of 10, and "4" of 20.  A valid offset of 4 sends the
    rest of the file.  "-1" means the receiver has no file and sends all
    of it.  A non-digit, an offset past the largest file offset, or a
    length past the data refuses the file.  The sender then sends no
    data and discards the file in its Z packet.
    """
    (tmp_path / "f.txt").write_bytes(b"abcdefghij")
    # CAPAS with the attribute and RESEND bits.
    init = default_init() + bytes([tochar(8 | 16)])
    seen = []

    def answer(pkt):
        seq = pkt[2] - 32
        ptype = pkt[3:4]
        seen.append((ptype, pkt[4:-1]))
        if ptype == b"S":
            return packet(seq, "Y", init)
        if ptype == b"A":
            return packet(seq, "Y", b"1" + offset)
        return packet(seq, "Y", b"")

    log = tmp_path / "t.log"
    result = _run_partner(run_wermit, tmp_path, answer,
                          f"log transactions {log}, set file type binary, "
                          "resend f.txt, close transactions")
    data = b"".join(d for t, d in seen if t == b"D")
    zdata = [d for t, d in seen if t == b"Z"]
    if sent is None:
        assert data == b"", seen
        assert zdata == [b"D"], seen
        assert "refused: RESEND offset" in log.read_text(), result.stdout
    else:
        assert data == sent, seen
        assert zdata == [b""], seen


@pytest.mark.parametrize("name", [b" ", b"   "], ids=["one", "three"])
def test_blank_file_name_becomes_noname(run_wermit, tmp_path, name):
    """Verify a file name of blanks only is received as NONAME.

    nzrtol() strips leading and trailing blanks.  With nothing left it
    must not read before its result buffer.
    """
    script = {0: ("F", name), 1: ("D", b"hello"), 2: ("Z", b""),
              3: ("B", b"")}

    def answer(pkt):
        seq = pkt[2] - 32
        ptype = pkt[3:4]
        if ptype == b"N":
            return packet(0, "S", default_init()) if seq == 0 else b""
        if ptype == b"Y" and seq in script:
            ptype, data = script[seq]
            return packet(seq + 1, ptype, data)
        return b""

    result = _run_partner(run_wermit, tmp_path, answer,
                          "set receive confirm off, receive")
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "STATUS=0" in result.stdout, result.stdout
    assert (tmp_path / "NONAME").read_bytes() == b"hello"


@pytest.mark.parametrize("tail,qbin", [
    (b"~", b"Y"), (b"~#", b"Y"), (b"#", b"Y"), (b"&", b"&")],
    ids=["repeat", "repeat-count", "control", "eighth-bit"])
def test_data_ending_in_prefix_is_refused(run_wermit, tmp_path, tail, qbin):
    """Verify a Data packet that ends inside a prefixed sequence fails.

    The partner sends a file whose Data packet ends with a prefix and
    no operand.  decode() must not take the operand from the block
    check.  The receiver ends the transfer with an error packet and
    writes nothing past the good data.
    """
    params = bytearray(default_init())
    params[6] = qbin[0]                 # 8th-bit prefix field
    init = bytes(params)
    script = {0: ("F", b"f.txt"), 1: ("D", b"abc" + tail),
              2: ("Z", b""), 3: ("B", b"")}
    replies = []

    def answer(pkt):
        seq = pkt[2] - 32
        ptype = pkt[3:4]
        if ptype == b"N" and seq == 0 and not replies:
            return packet(0, "S", init)
        replies.append((ptype, pkt[4:-1]))
        if ptype == b"Y" and seq in script:
            ptype, data = script[seq]
            return packet(seq + 1, ptype, data)
        return b""

    result = _run_partner(run_wermit, tmp_path, answer,
                          "set receive confirm off, "
                          "set file incomplete keep, receive")
    assert "STATUS=1" in result.stdout, result.stdout
    assert (b"E", b"Malformed packet data") in replies, replies
    received = tmp_path / "f.txt"
    if received.exists():
        assert received.read_bytes() in (b"", b"abc"), received.read_bytes()


def ext_packet(seq, ptype, xlen):
    """Return an extended-header packet that claims xlen bytes and has
    none after its header check.

    The header check covers LEN, SEQ, TYPE, LENX1 and LENX2.
    """
    head = bytes([tochar(0), tochar(seq & 63), ord(ptype),
                  tochar(xlen // 95), tochar(xlen % 95)])
    total = sum(head)
    hcheck = tochar((total + ((total & 192) >> 6)) & 63)
    return b"\x01" + head + bytes([hcheck]) + b"\r"


def test_packet_shorter_than_block_check_is_refused(run_wermit, tmp_path):
    """Verify rpack() refuses a packet with a negative data length.

    The partner sends a Data packet with an extended header of length
    0.  Less than the block check, it would give a data length of -1,
    and the header check would serve as its block check.  The receiver
    must NAK it and take the good Data packet that follows.
    """
    init = default_init()
    replies = []

    def answer(pkt):
        seq = pkt[2] - 32
        ptype = pkt[3:4]
        if ptype == b"N" and seq == 0 and not replies:
            return packet(0, "S", init)
        replies.append((ptype, seq))
        if ptype == b"Y" and seq == 0:
            return packet(1, "F", b"f.txt")
        if ptype == b"Y" and seq == 1:
            return ext_packet(2, "D", 0)
        if ptype == b"N" and seq == 2:
            return packet(2, "D", b"hello")
        if ptype == b"Y" and seq == 2:
            return packet(3, "Z", b"")
        if ptype == b"Y" and seq == 3:
            return packet(4, "B", b"")
        return b""

    result = _run_partner(run_wermit, tmp_path, answer,
                          "set receive confirm off, receive")
    assert "STATUS=0" in result.stdout, result.stdout
    assert (b"N", 2) in replies, replies
    assert (tmp_path / "f.txt").read_bytes() == b"hello"


def crc16(data):
    """Return the Kermit Type 3 block check (CRC-CCITT, reversed) of
    data."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return bytes([tochar((crc >> 12) & 0x0F), tochar((crc >> 6) & 0x3F),
                  tochar(crc & 0x3F)])


def packet3(seq, ptype, data, extended=False):
    """Return a Kermit packet with a Type 3 block check.

    With extended, the packet has an extended header.
    """
    if extended:
        xlen = len(data) + 3
        head = bytes([tochar(0), tochar(seq & 63), ord(ptype),
                      tochar(xlen // 95), tochar(xlen % 95)])
        total = sum(head)
        head += bytes([tochar((total + ((total & 192) >> 6)) & 63)])
    else:
        head = bytes([tochar(len(data) + 5), tochar(seq & 63), ord(ptype)])
    body = head + data
    return b"\x01" + body + crc16(body) + b"\r"


def test_short_send_init_after_stale_five(run_wermit, tmp_path):
    """Verify a short Send-Init is not read as forcing a Type 3 check.

    A D packet with a bad block check first leaves '5' at index 11 of
    the receive buffer.
    The partner then sends a Send-Init with four parameters.  It ends
    before that index.  rpack() must read CHKT only from the data field
    and accept the packet with its 1-byte check.
    """
    init = default_init()[:4]
    script = {0: ("F", b"f.txt"), 1: ("D", b"hello"), 2: ("Z", b""),
              3: ("B", b"")}
    sent = []

    def answer(pkt):
        seq = pkt[2] - 32
        ptype = pkt[3:4]
        if ptype == b"N" and seq == 0:
            if not sent:
                sent.append(1)
                bad = packet(0, "D", b"xxxxxxx5xxxx")
                return bad[:-2] + bytes([bad[-2] ^ 1]) + bad[-1:]
            return packet(0, "S", init)
        if ptype == b"Y" and seq in script:
            ptype, data = script[seq]
            return packet(seq + 1, ptype, data)
        return b""

    result = _run_partner(run_wermit, tmp_path, answer,
                          "set receive confirm off, receive")
    assert "STATUS=0" in result.stdout, result.stdout
    assert (tmp_path / "f.txt").read_bytes() == b"hello"


def test_extended_send_init_forcing_type3(run_wermit, tmp_path):
    """Verify CHKT is read from an extended-header Send-Init.

    The partner asks for a forced Type 3 check ('5') in a Send-Init with
    an extended header, and sends every packet with a Type 3 check.
    Parameter 8 is then at index 14 of the buffer, not 11.
    """
    init = bytearray(default_init())
    init[7] = ord("5")
    init = bytes(init)
    script = {0: ("F", b"f.txt"), 1: ("D", b"hello"), 2: ("Z", b""),
              3: ("B", b"")}

    def answer(pkt):
        seq = pkt[2] - 32
        ptype = pkt[3:4]
        if ptype == b"N" and seq == 0:
            return packet3(0, "S", init, extended=True)
        if ptype == b"Y" and seq in script:
            ptype, data = script[seq]
            return packet3(seq + 1, ptype, data)
        return b""

    result = _run_partner(run_wermit, tmp_path, answer,
                          "set receive confirm off, receive")
    assert "STATUS=0" in result.stdout, result.stdout
    assert (tmp_path / "f.txt").read_bytes() == b"hello"


def test_nak_for_next_packet_acks_current(run_wermit, tmp_path):
    """Verify a NAK for packet n+1 is taken as an ACK for packet n.

    With a window of 1, the partner answers the first Data packet with a
    NAK for the next sequence number.  The sender must go on to the next
    packet rather than send the Data packet again.
    """
    (tmp_path / "f.txt").write_text("x" * 300)
    sent = []
    nakked = []

    def answer(pkt):
        seq = pkt[2] - 32
        ptype = pkt[3:4]
        sent.append((ptype, seq))
        if ptype == b"S":
            return packet(seq, "Y", default_init())
        if ptype == b"D" and not nakked:
            nakked.append(seq)
            return packet(seq + 1, "N", b"")
        return packet(seq, "Y", b"")

    result = _run_partner(run_wermit, tmp_path, answer,
                          "set window 1, send f.txt")
    assert "STATUS=0" in result.stdout, result.stdout
    assert sent == [(b"S", 0), (b"F", 1), (b"D", 2), (b"Z", 3),
                    (b"B", 4)], sent


@pytest.mark.parametrize("bct", ["2", "3", "B"])
def test_error_packet_with_type1_check(run_wermit, tmp_path, bct):
    """Verify an E packet with a Type 1 check delivers the whole message.

    The transfer uses block check type bct.  The partner answers the
    F packet with an E packet that carries a Type 1 check.  rpack()
    takes the bytes it held as a longer check back into the data field.
    """
    (tmp_path / "f.txt").write_text("hello\n")
    init = bytearray(default_init())
    init[7] = ord(bct)
    init = bytes(init)
    message = b"Remote message ABCDEFGHIJKLMNOP"

    def answer(pkt):
        seq = pkt[2] - 32
        if pkt[3:4] == b"S":
            return packet(seq, "Y", init)
        return packet(seq, "E", message)

    result = _run_partner(run_wermit, tmp_path, answer,
                          f"set block-check {bct}, send f.txt")
    assert "STATUS=1" in result.stdout, result.stdout
    assert message.decode() + "." in result.stdout, result.stdout


@pytest.mark.parametrize("bct", ["2", "3", "B"])
def test_error_packet_type1_check_length(run_wermit, tmp_path, bct):
    """Verify rpack() records the full length of an E packet's data.

    The partner answers the F packet with an E packet that carries a
    Type 1 check under block check type bct.  The debug log's receive
    buffer dump shows the packet's recorded length (pk_len).  It must
    equal the length of the message.
    """
    (tmp_path / "f.txt").write_text("hello\n")
    init = bytearray(default_init())
    init[7] = ord(bct)
    init = bytes(init)
    message = b"Remote message ABCDEFGHIJKLMNOP"

    def answer(pkt):
        seq = pkt[2] - 32
        if pkt[3:4] == b"S":
            return packet(seq, "Y", init)
        return packet(seq, "E", message)

    log = tmp_path / "debug.log"
    _run_partner(run_wermit, tmp_path, answer,
                 f"log debug {log}, set block-check {bct}, send f.txt")
    lines = log.read_text(errors="replace").splitlines()
    lengths = set()
    for header, row in zip(lines, lines[1:]):
        fields = row.split()
        if header.startswith("buffer inuse") and fields[-3:-2] == ["E"]:
            lengths.add(int(fields[-4]))
    assert lengths == {len(message)}, lengths


def test_packet_longer_than_buffer_count(run_wermit, tmp_path):
    """Verify ttinl() returns the byte count when a packet fills its buffer.

    SET BUFFERS makes the receive buffer about 4000 bytes.  The partner
    answers the S packet with an extended-length packet of 8000 data
    bytes.  The debug log records the count that ttinl() returned to
    rpack().  It must be the number of bytes read, not a data byte.
    """
    (tmp_path / "f.txt").write_text("hello\n")
    size = 8000

    def answer(pkt):
        seq = pkt[2] - 32
        if pkt[3:4] != b"S":
            return None
        xlen = size + 1
        head = bytes([tochar(0), tochar(seq), ord("Y"),
                      tochar(xlen // 95), tochar(xlen % 95)])
        total = sum(head)
        head += bytes([tochar((total + ((total & 192) >> 6)) & 63)])
        return b"\x01" + head + b"A" * size + b"\r"

    log = tmp_path / "debug.log"
    _run_partner(run_wermit, tmp_path, answer,
                 f"set buffers 4000 4000, log debug {log}, "
                 "set retry 2, send f.txt")
    counts = [int(line.split("=")[1])
              for line in log.read_text(errors="replace").splitlines()
              if line.startswith("rpack ttinl len=")]
    assert counts, "no packet was read"
    assert all(3900 < n < size for n in counts), counts

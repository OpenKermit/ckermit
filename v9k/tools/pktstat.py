#!/usr/bin/env python3
"""Count what a C-Kermit packet log says about a run, in both directions.

A packet log is written by ONE of the two Kermits -- in this project always
the host -- so everything in it is relative to that end.  This tool calls
that end LOCAL and the other end REMOTE.  On a Victor *receive* leg the
Victor is remote and the host sends the data; on a Victor *send* leg the
Victor is remote and the host receives it.  Direction is detected from which
side carries the D packets, so it is never a flag you can get wrong.

Why this exists in the shape it does (PORTING.md 16ah, NEXT_SESSION item 5a):
the earlier version measured only the lines the log-writer *sent*, so on a
send leg it reported the ACK stream -- "longest packet 49, retransmissions 0"
for a log whose longest line was 3,614 characters and which contained four
remote resends.  Both halves of that were wrong and both are fixed here.

WIRE BYTES are the point.  The bench does not repeat to better than ~1.3 s
(NEXT_SESSION item 5b), which is larger than several of the effects worth
measuring -- so where an effect shows up as traffic rather than as time,
count it.  Wire bytes are exact and deterministic; the clock is not.

Line format, from logpkt() at ckcfn2.c:3287:

    s-00-01-^A9 S~/ @-#Y3~^>J)0___J"U1@C
    | |  |  `-- the packet, RAW except for the start-of-packet character
    | |  `----- gtimer() % 60: seconds since transfer start, mod 60
    | `-------- packet number mod 100, or "xx" for an event marker
    `---------- s = sent, S = RESENT (ckcfn2.c:2102), r = received,
                # = a note about a received packet, not a packet

ONLY the start-of-packet character is escaped, and only when it is a control
character or 128..159 (ckcfn2.c:3313).  dbchr() (ckuusx.c:3100) renders it as
"^A" -- or "~^A" with the 8th bit on -- so the escape is 1, 2 or 3 characters
standing for one wire byte.  Everything after it is written byte for byte.

Three consequences, all of which the counting has to handle:

  * A SENT line carries the packet's end-of-line terminator (a real CR in the
    file); a RECEIVED line does not, because the receiver logs the packet it
    parsed, and the terminator is not part of the packet.  The terminator is
    still a byte on the wire either way, so it is added back per packet --
    from the negotiated EOL in the S packet, not from an assumption.
  * Padding (NPAD of the S packet) is likewise on the wire and in no line.
    It is zero in every log this project has produced; it is counted anyway,
    because a non-zero value would otherwise silently understate the total.
  * A packet is one line only because Kermit prefixes control characters, so
    no raw LF can appear inside one.  The tool checks that assumption instead
    of trusting it, and warns if a line fails to parse.

Wire bytes are computed twice by different routes -- from the logged line
length and from the packet's own LEN field -- and disagreement is reported.
That catches a truncated log, an embedded LF, or a wrong escape width, none
of which announce themselves.

Validated against the Victor's own hardware byte counter: on 16ah leg BC the
outbound total here is 37,585, of which the Victor was not yet listening for
the first 28-byte S packet, leaving 37,557 -- and the Victor's ISR reported
rxbytes = 37,557, to the byte.  Other legs run ~11 bytes over, which is
startup dead air the host never sent and the log therefore cannot show; it is
the same shift mapoffset.py corrects for.

RECONCILING WITH THE VICTOR.  --rxbytes takes the Victor's own ISR counter
and checks it against what this log says the host put on the wire.  The two
count the same physical bytes by completely independent routes, so the
residual is a measurement:

    host wire bytes - rxbytes = rxfull + startup offset

rxbytes counts only bytes the ISR managed to STORE -- the ring-full path in
ckvisr.asm bumps rxfull and returns without touching it -- so a leg that
overran shows the shortfall exactly.  On 16af leg AJ the host sent 45,461,
the Victor counted 44,720, and the difference is 741, which is the rxfull
that leg reported to the byte.  On a clean leg the residual is a small
startup constant: -11 on every leg with no startup timeout (16af AG and AH,
16ah BD), and +28 on legs where a timeout means the Victor was not yet
listening for the first S packet.  Anything else wants explaining.

Usage:
    pktstat.py LOG [LOG ...]        # one block per log
    pktstat.py --payload N LOG      # override the A packet's file size
    pktstat.py --packets LOG        # one line per packet as well
    pktstat.py --rxbytes N [--rxfull N] LOG     # reconcile with the Victor
"""

import argparse
import re
import sys

LINE = re.compile(rb'^([sSr#])-(xx|\d+)-(\d+)-(.*)$', re.S)

# Packet types, for the type census.  Anything unlisted prints as its letter.
TYPENAME = {
    'D': 'data', 'Y': 'ack', 'N': 'nak', 'S': 'send-init', 'F': 'file-header',
    'Z': 'eof', 'B': 'eot', 'A': 'attributes', 'E': 'error', 'I': 'exchange',
    'G': 'generic', 'C': 'command', 'T': 'reserved', 'X': 'text-header',
}


def unchar(b):
    """Kermit's single-character number encoding: value = char - 32."""
    return b - 32


def escape_width(body):
    """How many characters of `body` stand for the one start-of-packet byte.

    logpkt() escapes only that character, via dbchr(): '~' for the 8th bit,
    then '^X' for a control character or '^?' for DEL.  A printable SOP is
    written as itself.  Read the width off the body rather than assuming 2 --
    a build with a non-default SOP would otherwise shift every field by one.
    """
    if body[:1] == b'~':
        return 3 if body[1:2] == b'^' else 2
    if body[:1] == b'^' and len(body) > 1:
        return 2
    return 1


def parse_packet(body):
    """(type, len_field, wire_length, seq, data_offset) for one logged body.

    `len_field` is the value the log quotes as "longest packet" elsewhere in
    this project -- Kermit's own length, which counts from the SEQ field
    through the block check.  `wire_length` is the byte count of the packet
    as it appeared on the line, from the start-of-packet character through
    the block check, EXCLUDING the end-of-line terminator.

    Short packet:  SOP LEN SEQ TYPE data... check      wire = LEN + 2
    Long packet:   SOP  0  SEQ TYPE LENX1 LENX2 HCHECK data... check
                   with LENX1*95+LENX2 counting data+check, so wire = ext + 7
    """
    off = escape_width(body)
    if len(body) < off + 3:
        return None, None, None, None, None
    ln = unchar(body[off])
    seq = unchar(body[off + 1])
    typ = chr(body[off + 2])
    if ln == 0:                                 # long packet
        if len(body) < off + 6:
            return typ, None, None, seq, None
        ext = unchar(body[off + 3]) * 95 + unchar(body[off + 4])
        return typ, ext, ext + 7, seq, off + 6
    return typ, ln, ln + 2, seq, off + 3


class Params:
    """What the S packet negotiated, insofar as it bears on byte counting.

    Data fields of an S packet, in order: MAXL TIME NPAD PADC EOL QCTL QBIN
    CHKT REPT CAPAS ...  Only three matter here -- how many bytes per packet
    are on the wire but not in the log (NPAD, EOL), and how many trailing
    characters of a packet are block check rather than data (CHKT).

    Strictly these are per-direction: an S packet states what its sender
    wants to RECEIVE.  Both ends have agreed on the same values in every log
    this project has produced, so one set is applied to both directions and
    printed, so that a log where they differ is visible rather than silent.
    """

    def __init__(self):
        self.npad = 0
        self.eol = 1                            # CR, unless S says otherwise
        self.bctl = 1                           # until CHKT is negotiated
        self.seen = False

    def learn(self, body, data_off):
        if self.seen or data_off is None:
            return
        d = body[data_off:]
        if len(d) < 8:
            return
        self.npad = unchar(d[2])
        self.eol = 1 if unchar(d[4]) else 0
        chkt = chr(d[7])
        self.bctl = int(chkt) if chkt in '123' else 1
        self.seen = True

    def per_packet(self):
        """Bytes on the wire per packet that no log line can contain."""
        return self.npad + self.eol


class Side:
    """One direction's totals."""

    def __init__(self):
        self.packets = 0
        self.resends = 0
        self.bytes_line = 0                     # from the logged line length
        self.bytes_len = 0                      # from the packet's LEN field
        self.eol_seen = 0                       # terminators actually logged
        self.longest = 0                        # Kermit's LEN, as quoted
        self.longest_wire = 0
        self.longest_seq = None
        self.types = {}

    def wire(self, params):
        """Bytes this side put on the wire, terminators and padding included."""
        return self.bytes_len + self.packets * params.per_packet()


def read_log(path, payload_override=None):
    raw = open(path, 'rb').read()
    local, remote = Side(), Side()
    params = Params()
    markers = {}
    unparsed = []
    payload = payload_override
    filename = None
    packets = []
    prev_remote_seq = None
    pending_attr = []

    for lineno, line in enumerate(raw.split(b'\n'), 1):
        if not line:
            continue
        m = LINE.match(line)
        if not m:
            unparsed.append((lineno, line[:60]))
            continue
        kind, _num, clock, body = m.groups()
        kind = chr(kind[0])

        if body.startswith(b'<'):                # an event, not a packet
            markers[body.split(b'>')[0].decode('latin-1') + '>'] = \
                markers.get(body.split(b'>')[0].decode('latin-1') + '>', 0) + 1
            continue
        if kind == '#':                          # a note about a packet
            markers['#'] = markers.get('#', 0) + 1
            continue

        typ, lenf, wire, seq, data_off = parse_packet(body)
        if typ is None or wire is None:
            unparsed.append((lineno, line[:60]))
            continue

        outbound = kind in 'sS'
        side = local if outbound else remote
        has_eol = body.endswith(b'\r') or body.endswith(b'\n')
        # The escape stands for one byte; the terminator, when the line has
        # one, is a real byte but is accounted per packet rather than here so
        # that both directions are counted the same way.
        on_line = len(body) - (escape_width(body) - 1) - (1 if has_eol else 0)

        side.packets += 1
        side.bytes_line += on_line
        side.bytes_len += wire
        side.eol_seen += 1 if has_eol else 0
        side.types[typ] = side.types.get(typ, 0) + 1
        if lenf > side.longest:
            side.longest, side.longest_wire, side.longest_seq = lenf, wire, seq
        if kind == 'S':
            side.resends += 1

        if not outbound:
            # The remote resending shows up as the same sequence number
            # arriving twice running: the local Kermit re-ACKs the copy
            # without advancing.  There is no 'R' line -- an inbound
            # retransmission is indistinguishable from a first copy except by
            # its sequence number.
            if seq == prev_remote_seq:
                remote.resends += 1
            prev_remote_seq = seq

        if typ == 'S':
            params.learn(body, data_off)
        elif typ == 'F' and filename is None:
            end = len(body) - params.bctl - (1 if has_eol else 0)
            filename = body[data_off:end].decode('latin-1', 'replace')
        elif typ == 'A':
            pending_attr.append((body, data_off, has_eol))

        packets.append((kind, clock.decode(), typ, lenf, wire, seq))

    if payload is None:
        for body, data_off, has_eol in pending_attr:
            end = len(body) - params.bctl - (1 if has_eol else 0)
            payload = attr_payload(body[data_off:end])
            if payload:
                break

    return dict(local=local, remote=remote, params=params, markers=markers,
                unparsed=unparsed, payload=payload, filename=filename,
                packets=packets)


def attr_payload(data):
    """File size in bytes out of an A packet's data field, or None.

    Fields are <letter><length-char><value> triplets.  '1' is the exact size
    in bytes; '!' is the size in K and is the fallback for a sender that
    omits '1'.
    """
    fields = {}
    i = 0
    while i < len(data) - 1:
        fld = chr(data[i])
        ln = unchar(data[i + 1])
        if ln < 0 or i + 2 + ln > len(data):
            break
        fields[fld] = data[i + 2:i + 2 + ln]
        i += 2 + ln
    for key, scale in (('1', 1), ('!', 1024)):
        try:
            return int(fields[key]) * scale
        except (KeyError, ValueError):
            continue
    return None


def census(types):
    order = sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))
    return ', '.join(f'{TYPENAME.get(t, t)} {n}' for t, n in order)


def report(path, r, show_packets=False, rxbytes=None, rxfull=0):
    local, remote, params = r['local'], r['remote'], r['params']
    sending = local.types.get('D', 0) >= remote.types.get('D', 0)
    if not (local.types.get('D') or remote.types.get('D')):
        sending = local.packets >= remote.packets
    carrier = local if sending else remote

    print(path)
    print('  leg              : local Kermit {} the data'
          .format('SENDS' if sending else 'RECEIVES'))
    if r['filename']:
        print(f"  file             : {r['filename']}")
    if r['payload']:
        print(f"  payload          : {r['payload']:,} bytes")
    print(f'  negotiated       : block check {params.bctl}, '
          f'EOL {params.eol} byte, padding {params.npad}'
          + ('' if params.seen else '   (DEFAULTED -- no S packet in log)'))

    for side, label, arrow, who in ((local, 'outbound', 'local  ->', 'local'),
                                    (remote, 'inbound ', 'local  <-', 'remote')):
        if not side.packets:
            continue
        print(f'  -- {label} ({arrow}) ' + '-' * 32)
        print(f'    packets        : {side.packets}   ({census(side.types)})')
        if side.bytes_len != side.bytes_line:
            print(f'    !! LEN fields total {side.bytes_len:,} against '
                  f'{side.bytes_line:,} on the line -- log truncated,'
                  f' mis-escaped, or carrying a raw LF')
        extra = side.packets * params.per_packet()
        print(f'    packet bytes   : {side.bytes_len:,}'
              f'   (SOP through block check)')
        print(f'    + terminators  : {extra:,}'
              f'   ({params.per_packet()}/packet; '
              f'{side.eol_seen} of them logged)')
        print(f'    = WIRE BYTES   : {side.wire(params):,}')
        print(f'    longest packet : {side.longest:,}'
              f'   ({side.longest_wire:,} wire bytes, seq {side.longest_seq})')
        print(f'    retransmissions: {side.resends}   (by the {who} Kermit)')

    if r['payload']:
        total = carrier.wire(params)
        pct = 100.0 * (total - r['payload']) / r['payload']
        print('  ' + '-' * 47)
        print(f"  expansion        : {r['payload']:,} payload -> "
              f'{total:,} wire bytes, {pct:+.1f}%')

    if rxbytes is not None:
        # The Victor's ISR counter against the host's log: two independent
        # counts of the same bytes.  See the module docstring for how to read
        # the residual.
        sent = local.wire(params)
        residual = sent - rxbytes - rxfull
        print('  ' + '-' * 47)
        print(f'  vs the Victor    : host sent {sent:,}, '
              f'rxbytes {rxbytes:,}, rxfull {rxfull:,}')
        if residual == 0:
            note = 'exact'
        elif residual == -11:
            note = 'the usual -11 startup offset'
        elif residual == 28 and r['markers'].get('<timeout>'):
            note = 'the S packet the Victor was not yet listening for'
        else:
            note = 'UNEXPLAINED -- do not use this leg for a byte comparison'
        print(f'  residual         : {residual:+,}   ({note})')

    marks = dict(r['markers'])
    print(f"  timeouts         : {marks.pop('<timeout>', 0)}")
    if marks:
        print('  other events     : '
              + ', '.join(f'{k} {v}' for k, v in sorted(marks.items())))
    if r['unparsed']:
        print(f"  !! {len(r['unparsed'])} unparsable line(s), first at "
              f"line {r['unparsed'][0][0]}: {r['unparsed'][0][1]!r}")

    if show_packets:
        print('  -- packets ' + '-' * 37)
        for kind, clock, typ, lenf, wire, seq in r['packets']:
            print(f'    {kind}  t+{clock}s  seq {seq:2}  {typ}  '
                  f'len {lenf:>5}  wire {wire:>5}')
    print()


def main():
    ap = argparse.ArgumentParser(
        description='Summarise a C-Kermit packet log, both directions.')
    ap.add_argument('logs', nargs='+', metavar='LOG')
    ap.add_argument('--payload', type=int, default=None,
                    help='file size in bytes; default is from the A packet')
    ap.add_argument('--packets', action='store_true',
                    help='also list every packet')
    ap.add_argument('--rxbytes', type=int, default=None,
                    help="the Victor's rxbytes counter, to reconcile against")
    ap.add_argument('--rxfull', type=int, default=0,
                    help="the Victor's rxfull counter (bytes the ring dropped)")
    a = ap.parse_args()
    for path in a.logs:
        try:
            r = read_log(path, a.payload)
        except OSError as e:
            print(f'{path}: {e}', file=sys.stderr)
            continue
        report(path, r, a.packets, a.rxbytes, a.rxfull)


if __name__ == '__main__':
    main()

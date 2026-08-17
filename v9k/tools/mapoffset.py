#!/usr/bin/env python3
"""Map a byte offset in the received stream onto the host's packet sequence.

The Victor's ISR counts every byte it stores, so its offsets are positions in
the host's send stream -- retransmissions included, in the order they went
out.  Adding up wire lengths from the host's packet log converts an offset
back into "which packet, and was it a resend".

Wire length: SOH LEN SEQ TYPE [data] CHECK EOL.  For a short packet that is
unchar(LEN) + 3; for a long one (LEN == 0) it is data + 9, the extra being
LENX1 LENX2 and the header check.

The Victor's offsets are NOT the host's unless nothing was missed before the
first byte it stored.  PORTING.md 16r's run started 253 bytes into the host's
stream -- nine S retransmissions of startup dead air the Victor never saw --
and unshifted, its first loss mapped into the seventh S retransmission and
read as a startup artifact.  Pass rxbytes and the shift is computed and
applied for you, which is the only reliable way to do it:

usage: mapoffset.py <host.pkt> [--rxbytes N] <offset> [<offset> ...]
"""
import re, sys

u = lambda c: ord(c) - 32

pkts = []          # (start, end, kind, seq, type, wirelen)
pos = 0
for line in open(sys.argv[1], encoding='latin-1'):
    line = line.rstrip('\r\n')
    if '<timeout>' in line:
        pkts.append((pos, pos, '<timeout>', '', '', 0))
        continue
    m = re.match(r'^([sSr])-\d+-\d+-(.*)$', line)
    if not m:
        continue
    kind, b = m.group(1), m.group(2)
    if len(b) < 5:
        continue
    if kind == 'r':                      # what the Victor sent, not received
        continue
    ln, typ, seq = u(b[2]), b[4], u(b[3])
    wire = (u(b[5]) * 95 + u(b[6]) + 9) if (ln == 0 and len(b) >= 7) else ln + 3
    pkts.append((pos, pos + wire, kind, seq, typ, wire))
    pos += wire

print(f"{sys.argv[1]}: {pos} bytes sent to the Victor in "
      f"{sum(1 for p in pkts if p[2] != '<timeout>')} packets\n")

args = sys.argv[2:]
shift = 0
if args and args[0] in ('--rxbytes', '-r'):
    rxbytes = int(args[1])
    args = args[2:]
    shift = pos - rxbytes
    print(f"rxbytes={rxbytes} against {pos} sent: the Victor's stream starts "
          f"{shift} bytes into the host's.")
    if shift < 0:
        print("  NEGATIVE -- the Victor stored more than the host sent.  "
              "Wrong log, or a run the log does not cover.")
    print("  Every offset below is shifted by that amount.\n")

for arg in args:
    off = int(arg) + shift
    hit = None
    for (s, e, kind, seq, typ, wire) in pkts:
        if kind == '<timeout>':
            continue
        if s <= off < e:
            hit = (s, e, kind, seq, typ, wire)
            break
    if hit:
        s, e, kind, seq, typ, wire = hit
        what = "RESEND" if kind == 'S' else "first send"
        print(f"offset {arg:>6} -> {off:6d} -> {what} seq={seq:02d} "
              f"type={typ} ({wire} wire bytes, {off - s} into it, "
              f"{e - off} left)")
    else:
        print(f"offset {arg:>6} -> {off:6d} -> past the end of the log ({pos})")

print("\npacket map:")
for (s, e, kind, seq, typ, wire) in pkts:
    if kind == '<timeout>':
        print(f"  {'':>6}   <timeout>")
    else:
        print(f"  {s:6d}-{e:6d} {'RESEND' if kind=='S' else '      '} "
              f"seq={seq:02d} {typ} {wire}")

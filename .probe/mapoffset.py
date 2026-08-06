#!/usr/bin/env python3
"""Map a byte offset in the received stream onto the host's packet sequence.

The Victor's ISR counts every byte it stores, so its offsets are positions in
the host's send stream -- retransmissions included, in the order they went
out.  Adding up wire lengths from the host's packet log converts an offset
back into "which packet, and was it a resend".

Wire length: SOH LEN SEQ TYPE [data] CHECK EOL.  For a short packet that is
unchar(LEN) + 3; for a long one (LEN == 0) it is data + 9, the extra being
LENX1 LENX2 and the header check.

usage: mapoffset.py <host.pkt> <offset> [<offset> ...]
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

for arg in sys.argv[2:]:
    off = int(arg)
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
        print(f"offset {off:6d} -> {what} seq={seq:02d} type={typ} "
              f"({wire} wire bytes, {off - s} into it, {e - off} left)")
    else:
        print(f"offset {off:6d} -> past the end of the log ({pos})")

print("\npacket map:")
for (s, e, kind, seq, typ, wire) in pkts:
    if kind == '<timeout>':
        print(f"  {'':>6}   <timeout>")
    else:
        print(f"  {s:6d}-{e:6d} {'RESEND' if kind=='S' else '      '} "
              f"seq={seq:02d} {typ} {wire}")

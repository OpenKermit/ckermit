#!/usr/bin/env python3
"""Count what a C-Kermit packet log says about a run.

PORTING.md 16l's two instruments: an uppercase 'S-' line is a retransmission
(ckcfns.c:2002) and a '<timeout>' line is a timeout (ckcfns.c:2900).  The log
escapes control characters, so '^A' is two characters and the type is body[4]
of the escaped packet, not body[3].

Line shape, from the logs themselves:   s-00-00-^A9 S~4 @-#Y3...
                                        `--- s/S/r, two counters, then SOH
"""
import re, sys


def unchar(c):
    return ord(c) - 32


def decode(body):
    """(type, length) for one escaped packet body, length None if not long."""
    if len(body) < 5:
        return None, None
    typ = body[4]
    ln = unchar(body[2])
    if ln == 0 and len(body) >= 7:              # Long packet: LENX1 LENX2
        return typ, unchar(body[5]) * 95 + unchar(body[6])
    return typ, ln


path = sys.argv[1]
sent = resent = timeouts = 0
recv = {}
longest = 0
seq_of_longest = None

for line in open(path, encoding='latin-1'):
    line = line.rstrip('\r\n')
    if '<timeout>' in line:
        timeouts += 1
        continue
    m = re.match(r'^([sSr])-\d+-\d+-(.*)$', line)
    if not m:
        continue
    kind, body = m.group(1), m.group(2)
    typ, ln = decode(body)
    if typ is None:
        continue
    if kind in 'sS':
        sent += 1
        if kind == 'S':
            resent += 1
        if ln and ln > longest:
            longest = ln
            seq_of_longest = body[3]
    else:
        recv[typ] = recv.get(typ, 0) + 1

print(path)
print(f"  packets sent    : {sent}")
print(f"  retransmissions : {resent}")
print(f"  timeouts        : {timeouts}")
print(f"  longest packet  : {longest}")
print(f"  received types  : {recv}")

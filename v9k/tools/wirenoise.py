#!/usr/bin/env python3
"""
wirenoise.py -- a serial relay that corrupts the wire on purpose.

WHY THIS EXISTS.  PORTING.md 16aq's Part 3 set out to show that upstream
edit 18's bulk read arm and the byte loop it replaces recover from
corrupted input identically.  The stimulus was a ten-foot cable wrapped
around mains wiring, and it produced ZERO errors on both arms.  That is an
instrument failure and not a null result: magnetic coupling goes with
CURRENT, not voltage, and quiet house wiring beside a cable is not a
source of either.  The claim is still untested on a wire.

NEXT_SESSION.md's standing rule, third outing by then: before running an
experiment that depends on something happening, MEASURE THAT IT CAN
HAPPEN.  This tool is that measurement made unconditional -- it reports
how many bytes it corrupted, so a leg that produced no errors can be told
apart from a leg whose noise source was never connected.

WHAT IT REPLACES.  The MAME harness is

    socat -d -d TCP-LISTEN:8000,reuseaddr,fork pty,raw,echo=0,link=/tmp/v9000

with MAME connecting to 127.0.0.1:8000 as a client and the host C-Kermit
opening /tmp/v9000.  This program does the same two jobs and adds a third,
so it is a drop-in for that socat line:

    python3 v9k/tools/wirenoise.py --listen 8000 --link /tmp/v9000 \
        --flip 3e-4 --dir to-victor --after 2000 --seed 17

CORRUPTION IS DRIVEN BY BYTE OFFSET, NOT BY A RANDOM SEQUENCE, and that
is the one design decision worth defending.  An A/B needs both arms to
meet the SAME noise, and a plain RNG cannot give that: the moment one arm
retransmits, the two byte streams diverge in length and every subsequent
draw lands somewhere else.  Keying the decision on the offset -- corrupt
byte k if h(seed, k) < p -- means the two arms are corrupted at the same
places for as long as their streams agree, which is the closest to
identical that a retransmitting protocol allows.  It also makes a leg
reproducible from its seed alone.

WHAT IT DOES NOT DO.  It does not simulate line noise: a real bit error
arrives as a framing or parity error at the chip, and this delivers a
clean byte with the wrong value.  What it exercises is the PACKET reader
-- checksum failure, resync, NAK, retransmission -- which is the thing
edit 18 changed.  For the chip's error paths, nothing here is a
substitute for a real line.

Direction names are from the Victor's point of view.  --dir to-victor is
the interesting one: it is what ttinl() has to survive.
"""

import argparse
import errno
import os
import pty
import select
import signal
import socket
import sys
import tty


_M64 = (1 << 64) - 1


def _mix(x):
    """splitmix64's finalizer.  The first version of this function used
    zlib.crc32 over a decimal string and it was WRONG in a way worth
    recording: the corrupted offsets came out at 15, 19, 40, 44, 48, 113,
    117, 146, 213, 217, 246 -- a visible period of 100, because CRC32 over
    short strings that differ in one digit is highly structured.  A
    corruption pattern with a period is not noise; it would have hit the
    same place in every packet and the leg would have measured something
    other than what it claimed.  Checked by eye on a 1024-byte relay,
    which is the cheapest instrument there was."""
    x &= _M64
    x ^= x >> 30
    x = (x * 0xBF58476D1CE4E5B9) & _M64
    x ^= x >> 27
    x = (x * 0x94D049BB133111EB) & _M64
    x ^= x >> 31
    return x


def corrupt_at(seed, direction, offset, prob):
    """Deterministic per-offset decision.  Same seed and same offset give
    the same answer in every run, which is what makes two arms
    comparable and a leg reproducible."""
    if prob <= 0.0:
        return None
    salt = 0x1F if direction == "to-victor" else 0x2E
    h = _mix((seed * 0x9E3779B97F4A7C15) ^ (offset * 0xD1342543DE82EF95) ^ salt)
    if ((h >> 11) / float(1 << 53)) >= prob:
        return None
    # Which bit to flip comes out of the same word, so it costs nothing
    # extra and stays deterministic.
    return 1 << (h & 7)


class Side:
    """One direction of the relay, with its own counters."""

    def __init__(self, name, seed, prob, after, burst):
        self.name = name
        self.seed = seed
        self.prob = prob
        self.after = after
        self.burst = burst
        self.bytes = 0
        self.hits = 0
        self.burst_left = 0
        self.offsets = []

    def pump(self, data):
        if self.prob <= 0.0:
            self.bytes += len(data)
            return data
        out = bytearray(data)
        for i in range(len(out)):
            off = self.bytes + i
            if off < self.after:
                continue
            if self.burst_left > 0:
                self.burst_left -= 1
                out[i] ^= 0xFF
                self.hits += 1
                if len(self.offsets) < 200:
                    self.offsets.append(off)
                continue
            bit = corrupt_at(self.seed, self.name, off, self.prob)
            if bit is not None:
                out[i] ^= bit
                self.hits += 1
                if len(self.offsets) < 200:
                    self.offsets.append(off)
                if self.burst > 1:
                    self.burst_left = self.burst - 1
        self.bytes += len(out)
        return bytes(out)

    def report(self):
        # The offsets are the point of the report: they map onto the host's
        # packet log the same way the ISR's byte offsets do, with
        # v9k/tools/mapoffset.py, so "which packet did the corruption land
        # in" is answerable rather than guessable.
        return "wirenoise: %-9s bytes=%d corrupted=%d%s" % (
            self.name,
            self.bytes,
            self.hits,
            (" at " + ",".join(str(o) for o in self.offsets[:40])) if self.hits else "",
        )


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listen", type=int, default=8000,
                    help="TCP port MAME's -bitb connects to (default 8000)")
    ap.add_argument("--link", default="/tmp/v9000",
                    help="symlink to create for the pty (default /tmp/v9000)")
    ap.add_argument("--flip", type=float, default=0.0,
                    help="per-byte probability of flipping one bit, e.g. 3e-4")
    ap.add_argument("--dir", default="to-victor",
                    choices=["to-victor", "to-host", "both", "none"],
                    help="which direction to corrupt (Victor's point of view)")
    ap.add_argument("--after", type=int, default=0,
                    help="leave the first N bytes of a direction alone, so that "
                         "startup negotiation is not what gets hit")
    ap.add_argument("--burst", type=int, default=1,
                    help="corrupt N consecutive bytes per hit (default 1)")
    ap.add_argument("--seed", type=int, default=1,
                    help="corruption seed; the same seed corrupts the same offsets")
    ap.add_argument("--once", action="store_true",
                    help="exit after the first connection closes instead of "
                         "waiting for another")
    args = ap.parse_args()

    to_victor = Side("to-victor", args.seed,
                     args.flip if args.dir in ("to-victor", "both") else 0.0,
                     args.after, args.burst)
    to_host = Side("to-host", args.seed,
                   args.flip if args.dir in ("to-host", "both") else 0.0,
                   args.after, args.burst)

    lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    lsock.bind(("127.0.0.1", args.listen))
    lsock.listen(1)

    master, slave = pty.openpty()
    tty.setraw(master)
    tty.setraw(slave)
    sname = os.ttyname(slave)
    if os.path.islink(args.link) or os.path.exists(args.link):
        os.unlink(args.link)
    os.symlink(sname, args.link)

    def cleanup(*_):
        print("", file=sys.stderr)
        print(to_victor.report(), file=sys.stderr)
        print(to_host.report(), file=sys.stderr)
        try:
            os.unlink(args.link)
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("wirenoise: pty %s -> %s, listening on 127.0.0.1:%d" %
          (sname, args.link, args.listen), file=sys.stderr)
    print("wirenoise: flip=%g dir=%s after=%d burst=%d seed=%d" %
          (args.flip, args.dir, args.after, args.burst, args.seed),
          file=sys.stderr)

    while True:
        conn, _ = lsock.accept()
        conn.setblocking(False)
        print("wirenoise: MAME connected", file=sys.stderr)
        fds = [conn.fileno(), master]
        while True:
            try:
                r, _, _ = select.select(fds, [], [], 1.0)
            except (OSError, select.error):
                break
            done = False
            for fd in r:
                try:
                    if fd == master:            # host -> MAME -> Victor
                        data = os.read(master, 4096)
                        if not data:
                            done = True
                            break
                        conn.sendall(to_victor.pump(data))
                    else:                       # Victor -> MAME -> host
                        data = conn.recv(4096)
                        if not data:
                            done = True
                            break
                        os.write(master, to_host.pump(data))
                except OSError as e:
                    if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        continue
                    if e.errno == errno.EIO:    # pty with no reader yet
                        continue
                    done = True
                    break
            if done:
                break
        conn.close()
        print("wirenoise: MAME disconnected", file=sys.stderr)
        print(to_victor.report(), file=sys.stderr)
        print(to_host.report(), file=sys.stderr)
        if args.once:
            break

    try:
        os.unlink(args.link)
    except OSError:
        pass


if __name__ == "__main__":
    main()

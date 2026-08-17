#!/usr/bin/env python3
"""ctswatch.py -- the host end's modem lines: watch the inputs, drive RTS.

TWO JOBS, AND THE LOGIC ANALYZER IS THE PRIMARY INSTRUMENT FOR BOTH.  This
tool reads and drives what the HOST's driver sees and asserts; a probe on
the Victor's own pins says what actually happened.  Where they disagree, the
analyzer is right and this tool is telling you about macOS.  PORTING.md
SS16am and HW_TEST_16am.md.

  --toggle-rts N   drop and raise the HOST's RTS N times, 3 s apart.  This
                   is the stimulus for probing the VICTOR's CTS input: it
                   answers "is the pair wired inbound" without needing the
                   host's Kermit to do flow control, which SHOW FEATURES
                   says it cannot.
  (default)        poll TIOCMGET and print every change of the inputs.

WHY IT EXISTS AT ALL.  `kermit -C "show features"` on the bench Mac lists
"Hardware flow control" -- that is CK_RTSCTS, which only decides whether SET
FLOW RTS/CTS is a legal command -- and does NOT list POSIX_CRTSCTS, which is
the only arm of ckutio.c's tthflow() a macOS build could take.  Without it
that function is `int x = 0; return(x);`, the same empty function this port
found in its own build.  So `set flow rts/cts` on the host configured
nothing, and no Kermit leg can tell "our RTS does not arrive" from "nothing
was listening".  SS16al leg GB is the leg that fell into that.

WHAT THIS IS AND IS NOT.  TIOCMGET reads the modem-status inputs straight
from the driver, so it needs no flow control, no protocol and no cooperation
from Kermit.  But it reads them at the END OF A USB CABLE, through an FTDI
and a kernel driver: it says what macOS believes, which is the combination
of the Victor's pin, the RS-232 cable and the adapter.  A probe on the
Victor's own pins separates those.  USE THE ANALYZER FIRST; this is the
cross-check that tells you whether the host end agrees.

    python3 v9k/tools/ctswatch.py /dev/tty.usbserial-XXXXXXXX
    python3 v9k/tools/ctswatch.py /dev/tty.usbserial-XXXXXXXX --toggle-rts 3

Nothing else may hold the port.  Ctrl-C to stop; the watch mode prints a
summary of how many times each input changed, which is the number to record.
"""

import argparse
import fcntl
import os
import struct
import sys
import termios
import time

INPUTS = (("cts", termios.TIOCM_CTS),
          ("dsr", termios.TIOCM_DSR),
          ("dcd", termios.TIOCM_CAR),
          ("ri",  termios.TIOCM_RNG))

OUTPUTS = (("dtr", termios.TIOCM_DTR),
           ("rts", termios.TIOCM_RTS))


def modem_bits(fd):
    """TIOCMGET returns one int; struct-unpack it rather than trusting size."""
    raw = fcntl.ioctl(fd, termios.TIOCMGET, struct.pack("i", 0))
    return struct.unpack("i", raw)[0]


def render(bits, pairs):
    return " ".join("%s=%d" % (name, 1 if bits & mask else 0)
                    for name, mask in pairs)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("port", help="serial device, e.g. /dev/tty.usbserial-ABBFKXM1")
    ap.add_argument("--seconds", type=float, default=120.0,
                    help="how long to watch (default 120)")
    ap.add_argument("--interval", type=float, default=0.02,
                    help="poll interval in seconds (default 0.02)")
    ap.add_argument("--toggle-rts", type=int, metavar="N", default=0,
                    help="drop and raise this end's RTS N times, 3 s apart, "
                         "as a stimulus for a probe on the Victor's CTS")
    args = ap.parse_args()

    # O_NONBLOCK so a port with no carrier does not block the open, O_NOCTTY
    # so this never becomes a controlling terminal.  Read-write ONLY when we
    # intend to drive a line, so a watching run cannot change what it is
    # watching.  Neither mode ever writes a byte to the wire.
    flags = os.O_NONBLOCK | os.O_NOCTTY
    flags |= os.O_RDWR if args.toggle_rts else os.O_RDONLY
    try:
        fd = os.open(args.port, flags)
    except OSError as e:
        sys.exit("cannot open %s: %s" % (args.port, e))

    try:
        first = modem_bits(fd)
    except OSError as e:
        os.close(fd)
        sys.exit("TIOCMGET failed on %s: %s -- is this a real serial port?"
                 % (args.port, e))

    t0 = time.monotonic()
    print("# %s" % args.port)
    print("# MODE: %s" % ("DRIVING this end's RTS %d times" % args.toggle_rts
                          if args.toggle_rts else
                          "WATCHING ONLY -- this run drives nothing"))
    print("# inputs = what the FAR END is asserting.  dtr/rts = this end,")
    print("#   READ BACK from the driver, not driven by this program unless")
    print("#   --toggle-rts was given.  NOTE: opening the port makes macOS")
    print("#   assert DTR and RTS by itself, which the Victor sees as CTS.")
    print("%8s  %-34s  %s" % ("t(s)", "inputs (far end)", "this end (read back)"))
    print("%8.3f  %-34s  %s  <- initial"
          % (0.0, render(first, INPUTS), render(first, OUTPUTS)))

    changes = {name: 0 for name, _ in INPUTS + OUTPUTS}
    prev = first

    if args.toggle_rts:
        # Deliberately crude: drop RTS, hold 3 s, raise, hold 3 s, repeat.
        # Three seconds because it has to be unmistakable on a capture taken
        # by somebody watching a screen, not triggered on an edge.
        print("# driving THIS END's RTS %d times, 3 s low / 3 s high"
              % args.toggle_rts)
        rts = struct.pack("i", termios.TIOCM_RTS)

        def hold(seconds):
            """Poll the inputs while we hold a level, so the run evidences
               itself instead of asserting that it drove something."""
            end = time.monotonic() + seconds
            last = modem_bits(fd)
            while time.monotonic() < end:
                time.sleep(args.interval)
                bits = modem_bits(fd)
                if bits != last:
                    print("%8.3f  %-34s  %s"
                          % (time.monotonic() - t0, render(bits, INPUTS),
                             render(bits, OUTPUTS)))
                    last = bits

        try:
            for i in range(args.toggle_rts):
                fcntl.ioctl(fd, termios.TIOCMBIC, rts)     # RTS off
                got = modem_bits(fd)
                print("%8.3f  DROVE host RTS -> 0  (cycle %d)  read back: %s"
                      % (time.monotonic() - t0, i + 1, render(got, OUTPUTS)))
                if got & termios.TIOCM_RTS:
                    print("#   *** the driver still reports rts=1 -- this "
                          "adapter may not honour TIOCMBIC ***")
                hold(3.0)
                fcntl.ioctl(fd, termios.TIOCMBIS, rts)     # RTS on
                print("%8.3f  DROVE host RTS -> 1  (cycle %d)"
                      % (time.monotonic() - t0, i + 1))
                hold(3.0)
        except OSError as e:
            print("# TIOCMBIS/BIC failed: %s" % e)
        except KeyboardInterrupt:
            print("# interrupted")
        # Put it back the way a Kermit run expects to find it.
        try:
            fcntl.ioctl(fd, termios.TIOCMBIS, rts)
        except OSError:
            pass
        os.close(fd)
        print("# done.  The reading is on the ANALYZER, at the Victor's CTS "
              "input -- not here.")
        return

    try:
        while time.monotonic() - t0 < args.seconds:
            time.sleep(args.interval)
            try:
                bits = modem_bits(fd)
            except OSError as e:
                print("TIOCMGET failed mid-run: %s" % e)
                break
            if bits == prev:
                continue
            for name, mask in INPUTS + OUTPUTS:
                if (bits ^ prev) & mask:
                    changes[name] += 1
            print("%8.3f  %-34s  %s"
                  % (time.monotonic() - t0, render(bits, INPUTS),
                     render(bits, OUTPUTS)))
            prev = bits
    except KeyboardInterrupt:
        print("# interrupted")
    finally:
        os.close(fd)

    print("# transitions: %s"
          % " ".join("%s=%d" % (n, changes[n]) for n, _ in INPUTS + OUTPUTS))
    if changes["cts"] == 0:
        if not args.toggle_rts:
            print("# CTS NEVER MOVED -- and this run drove nothing, so that "
                  "is not a result.  Something has to make it move: the "
                  "Victor's HANGUP, or a transfer with --rtscts.")
        else:
            print("# CTS NEVER MOVED.  Read that against dsr/dcd above "
                  "before concluding anything about the Victor's RTS pin.")
    if changes["cts"] and changes["cts"] == changes["dsr"] == changes["dcd"]:
        print("# cts, dsr and dcd changed the same number of times.  If they "
              "also moved on the SAME samples they may share one far-end "
              "output; if any pair separates by a sample or two they do not.")


if __name__ == "__main__":
    main()

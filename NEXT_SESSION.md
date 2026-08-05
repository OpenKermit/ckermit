# Next session

Handoff for the Victor 9000 port, written 4 August 2026 at the end of the
session that implemented §11b. **The port transfers a file.**

**Read `PORTING.md` first** — §11b is rewritten and §16d is new. This file
is only the "what next".

---

## 1. Where things stand

A C-Kermit send from the Victor completed, end to end, on Victor MS-DOS 3.1
under MAME: S / F / A / D / Z / B, 72 bytes byte-correct at the far end, ten
seconds. That is **milestone step 5** (§13) and it is the thing this port
exists to do. Under emulation, Open Watcom build; never on real hardware,
and the gcc build has not been run since §16c.

| | ia16-elf-gcc, medium | Open Watcom, large |
|---|---|---|
| makefile | `victor9k.mak` | `victorow.mak` |
| 24 modules compile | yes, 4 warnings | yes, 17 warnings |
| warnings are | all pre-existing, all upstream | all pre-existing, all upstream |
| DGROUP after link | 52,728 / 65,536 (80%) | 39,424 (60%) |
| left for heap + stack | 12,808 | 26,112 |
| programs speed/parity/DTR via IOCTL (§11a) | yes | yes |
| **owns the 7201: ISR, ring, polled TX (§11b)** | **yes, built** | **yes, built** |
| **completes a transfer** | not run | **yes (§16d)** |

Reads on the Victor went from "twelve, every one of exactly 2 bytes"
(§16b, §16c) to "six, of 33 / 90 / 8 / 8 / 8 / 8", with no timeout and no
retransmission anywhere, ending `C-Kermit EXIT status=0`.

### What changed

`ckvictor.c` §1e is new: an IRQ1 handler on IVT slot 41h against the
memory-mapped µPD7201, a 512-byte receive ring, a polled transmitter, and
install/release. The OEM `\dev\seriala` driver is now out of the data path
in **both** directions and keeps only its §11a IOCTL job — which is exactly
what `msxv90.asm` has done since 1986.

Around it: `write()` is renamed to `v9k_write()` for the whole build the
same way `read()` already was; `victor/sys/ioctl.h` gained `TIOCMGET` and
the `TIOCM_*` bits; `tcflush()` and `tcdrain()` are real; `tcsetattr()`
installs the driver and re-asserts WR1; and there is a direct-to-the-chip
fallback for a DOS whose serial driver will not answer the IOCTL.

**No new upstream edit. §8 still lists six.** DGROUP +672 in each build, 512
of it the ring. `-fstack-usage` puts the handler at 22 bytes and `tcsetattr`
at 50.

### What it proves, and what it does not

The diagnosis in §16b was right and this is the run that proves the
negative: changing **only** the data path, and nothing above it, turned
twelve two-byte reads into a completed transfer. The protocol engine, the
file system, the timers and the packet framing were never the problem.

It also settled §16b's open hypothesis, from two lines the install path
prints before it touches anything: on Victor MS-DOS 3.1 **IRQ1 was masked at
the 8259 (`0B3h`) and the vector at 41h pointed at segment 0**. Nothing was
servicing the µPD7201's interrupt, measured independently of the CR1
read-back that was the only evidence before. The OEM driver is polled and
unbuffered; that half is now established. Whether the specific failure is a
latched overrun still is not.

Not established: real hardware; anything above 9600; long packets, windows
or streaming; what happens when a floppy write holds the ring longer than
the 533ms it buffers at 9600. The handler keeps two counters for exactly
those questions — bytes lost to a chip overrun, bytes lost to a full ring.
They did not print on the §16d run because they were logged only from the
release path, which runs from `atexit()` after C-Kermit has closed
`DEBUG.LOG`; they are now also logged from `tcsetattr()`, which `ttres()`
calls on the way out. **Read them on the next run** — that is the first
thing 19200 and windowing will need.

---

## 2. Do this next, in rough priority order

**Run §16d's transfer from the gcc build.** One MAME run. Both builds
compile the same §1e from the same `ckvictor.h` and have been byte-identical
on the wire twice, so this is expected to pass — which is the reason to do
it: it is cheap and it converts an inference into a measurement.

**Milestone step 6: `RECEIVE`, then `GET`, then `SERVER`,** still at 9600.
The receive direction drives the ring harder than send did, because the file
writes happen on the Victor end — which is precisely the case §11b has no
interrupt-level flow control for. Read the two loss counters out of
`DEBUG.LOG` afterwards; that is what they are for.

**Wildcard expansion** (§13 step 3a, §15). `-s FILE` works, `-s *.COM` finds
nothing. Blocks multi-file transfer, and it is now the last thing between
this port and being useful. Untouched for four sessions.

**Then step 8: long packets, windows, streaming, one at a time.** This is
where the missing water marks start to matter and where `ttchk()`'s new real
byte count earns its keep.

---

## 3. Things in the new driver that are known-incomplete

Listed so they are not rediscovered as bugs.

- **No interrupt-level flow control.** 3.13 sends XOFF from inside `SERINT`
  at a 3/4-full mark. Not needed with one packet in flight; needed for
  streaming. `tcflow()` is a stub for the same reason, and says so.
- **No stack switch in the handler.** Deliberate — 3.13's `SERINT` does not
  switch either, on this machine, and a dedicated stack would come out of
  the 64K DGROUP. The frame is 22 bytes under gcc, ~30 under Watcom.
  `~/projects/myfreedos`'s `victor_int14.asm` prologue is the reference if
  this ever needs doing properly.
- **The IRQ1 vector is hard-coded to 41h.** Right for Victor MS-DOS 3.1;
  `~/projects/myfreedos` remaps the 8259 and puts its serial ISR at INT 09h,
  so this is the most likely thing to break "one binary, two DOSes". It is
  one constant, in `ckvictor.c` §1e.
- **Ctrl-Break with the line open.** The vector is restored from an
  `atexit()` handler, which covers everything that goes through `exit()`.
  It does not cover a Ctrl-Break that DOS turns into a bare termination, and
  leaving IRQ1 hooked takes the machine down. Not measured on either
  runtime. Fix, if it bites: hook INT 23h, which is `AH=25h` and stays
  inside rule 6.
- **WR2 is left as the OEM driver set it** (`10h`, where 3.13 writes `14h`).
  They differ in one bit, which 3.13 calls interrupt priority, and with one
  channel and receive interrupts only there is no priority decision. The
  transfer works with `10h`. If interrupts ever fail to arrive, this is the
  first thing to try changing.
- **The carrier clause.** `ttgmdm()` reports DCD from RR0, except that it
  forces carrier present when `CLOCAL` is set — otherwise a three-wire cable
  makes `in_chk()` declare the line dead on the first `ttchk()`. The
  reasoning is written out in §11b and in the function; it is the one
  judgement call in the file.

---

## 4. Still open, from before

**The 42KB gap for the interactive parser.** Unchanged: needs 429KB, DOS
offers 387KB (§16a, measured). Three untried angles — a leaner DOS
configuration, trimming ~50KB of what `NOICP` was hiding, or `ZT=-zt128`
(which frees DGROUP but grew the image, so measure the load requirement
rather than assuming).

**Which toolchain the port should use.** Still not decided, and now slightly
less symmetric: Watcom is the one that has completed a transfer.

**`NOGFTIMER`.** Floating-point transfer timers on an 8088 with no FPU pull
in emulation for both builds. Still not turned off.

**`B76800` is really 78125 bps**, 1.7% off its name — same error as
`B38400`, which 3.13 shipped. Cosmetic.

---

## 5. The harness

§16a and §16d have it in full. The landmines all still apply:

- **The Victor boots its hard disk as `A:`**, not `C:`.
- **`~/projects/mame/victor_kermit.img` is the image.** Not an MBR disk, no
  BPB, **mtools cannot read it** — use `vtg_image_util`
  (`~/projects/vtg_image_util`, run as `python3 cli_main.py ...`). A backup
  is beside it as `victor_kermit.img.bak-20260804`.
- **MAME's `-bitb` socket is single-use.** Start `socat` first and let MAME
  be the only thing that connects; probing the port burns it.
- **Test on Victor MS-DOS 3.1, not FreeDOS** (§16a for why).
- **The emulated keyboard mangles characters** in `-autoboot_command`. Put
  the commands in a `.BAT` on the image and autoboot that. `KTEST.BAT` is
  there and is what §16d ran.
- **`-l /dev/seriala`, with forward slashes.**
- **`kermit -V` drops into interactive mode and hangs.** Always give the
  host `kermit` a command file, and a timeout.
- **`~/.kermrc` sets a line that does not exist.** Use `kermit -y <file>`.
- **MAME writes `cfg/` and `nvram/` into its working directory.** Run it
  from `~/projects/mame`.
- **`XFLAGS=-dKEEP_DEBUG` needs `make clean` first.** Not per-file:
  `debug()` compiles to nothing without it, so a partial rebuild dies with
  `E2028: dodebug_ is an undefined reference`.
- **A run costs 12–15 minutes of wall clock** for 200 emulated seconds. Put
  every question you have into one `.BAT` and one debug build.
- The working host receiver is `kermit -y <file>` with `set line
  /tmp/v9000`, `set speed 9600`, `set carrier-watch off`, `set flow none`,
  `log packets <file>`, `log transactions <file>`, `receive`. Start it right
  after MAME; it waits through the boot.

## 6. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victor9k.mak"     # gcc, links ckermit.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"     # Watcom, links ckermitw.exe
```

Both print their DGROUP figure on link. Diagnostic variants, neither set by
any makefile and both needing a `clean` first: `XFLAGS=-dKEEP_ICP` restores
the interactive parser, `XFLAGS=-dKEEP_DEBUG` the debug log. Rule 4 still
applies: report the DGROUP number after any change that could add static
data — and the receive ring in `ckvictor.h` is now one of the levers.

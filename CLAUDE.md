# CLAUDE.md

## What this repository is

The upstream **C-Kermit 11.0** source tree (Columbia University / Frank da Cruz,
~40 years of history, ~100 top-level `.c` files) plus a **Victor 9000 / Sirius 1
port** living on the `victor9k-port` branch.

**Read `PORTING.md` before doing anything on the port.** It is the design
document: architecture, memory budget, what is measured vs. assumed, what is
proven on hardware vs. merely written. It is kept current deliberately — if you
change the plan, change that file in the same commit.

## The port in one paragraph

`CKERMITW.EXE` is a serial-only, file-transfer-only C-Kermit for the Victor
9000, built with **Open Watcom V2** in the **large** model (far code *and* far
data). It runs as an MS-DOS program that drives the µPD7201 serial chip and the
8259 directly, so a single binary works on both **Victor MS-DOS 3.1** and
**FreeDOS for Victor**. Everything that is not the serial port goes through
**INT 21h only**.

There is **one build**. A second one, `ia16-elf-gcc` + newlib in the medium
model, existed until 2026-08-05 and was retired: one near 64K DGROUP could not
hold the command parser and left ~2K of heap for a transfer. PORTING.md §9d and
§16e keep the measurements; git keeps the code. **Do not reintroduce it** —
including "just to measure something."

## Build

The toolchain lives in the `ia16-ubuntu-2` container, which runs under Apple's
native `container` service — **not Docker**. `~/projects` is mounted at
`/mnt/projects` inside it. Open Watcom V2 is at `/opt/open-watcom-v2/rel`.

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"        # 24 objects + link
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak sizes"  # DGROUP report
```

`ckcpro.c` is generated from `ckcpro.w` by `wart`, a **host** tool built with
the host `cc`.

All 24 modules compile. Warnings are 19 lines, all in stock upstream code and
all pre-existing — `debug()` expanding to nothing under `NODEBUG` (W111),
two unreferenced labels, `localtime()` sign mismatch, `execvp()` const
mismatch, and `docmdline(1)` in `ckcmai.c`. **`ckvictor.c` compiles with
none.** It was 17 until `NOFLOAT` (§16j): dropping `GFTIMER` moves `ztime()`
onto upstream's `ZTIMEV7` branch, whose K&R redeclarations of `localtime()`
and `time()` produce two more sign mismatches at `ckutio.c:12319-12320`.
DGROUP is 48,240 of 65,536 (73%) after the linker adds libc; `ckermitw.exe`
is 203,338 bytes and needs 217,594 at load, of the 396,224 the machine
offers.

**It runs on a real Victor 9000, and PORTING.md §16o is the section that
says so.** 6 August 2026: 896 KB, Victor MS-DOS 3.1 booted from a Pico SASI
emulator serving the same `victor_kermit.img` MAME boots, channel A over a
1 m USB-C to RS-232 cable to a Mac running C-Kermit. **Six transfers — two
each at 9600, 19200 and 38400 — every one round-tripped md5-identical.** It
took **no code change**: §16n's binary, eleven upstream edits. Three
results came out of the counters. `rxlost=0 rxfull=0` at 19200 says the
`WR0 = 38h` + specific-EOI acknowledge sequence is right on the **real**
µPD7201, which is the item §10 carried as unproven from §11b onward and the
one that left FreeDOS-for-Victor's IRQ receive disabled. `rxpeak` was **56
of 4096**, against 309–513 under MAME at *half* the rate. And §16n's
half-second clock quantum is confirmed to be the **Victor's**, not MAME's.

**§16p then measured the thing §16o could not, and 38400 is not clean.**
Four 32 KB receives, one per rate plus a buffer A/B, all four byte-exact —
and `rxlost` was **0 at 9600, 0 at 19200, 203 and 207 at 38400**. The
µPD7201 overruns on **0.45% of received bytes** in bursts of ~50, and the
files arrive perfect only because Kermit resends whatever fails a checksum.
The Victor's NAK counts (1, 1, 4, 6) measure the same events from the far
end. **Byte-exact is not the same claim as clean**, and §16l's "the Victor
sends only ACKs, never a NAK" was the emulator's property.

**Two suspects are dead and this is the port's one live defect.** Not the
disk — run 4 did 8× the file writes for the same loss rate. Not the ring —
`rxfull = 0`, `rxpeak` ≤ 2,098 of 4,096. Not our own critical sections
either: every `V9K_CLI()` is setup or teardown, and both the polled
transmitter and the ring drain leave interrupts enabled. **The instrument to
build next is a foreground tag latched at the first loss, plus a count of
loss events as distinct from lost bytes.** §16p also retracts §16n's disk
model: on the real drive the write cost tracks bytes, not calls, so
`V9K_OBUFSIZE = 8192` saves ~0.5 s per 32 KB rather than 4 s. Keep it, but
drop it from throughput arguments.

**It transfers files, both ways, byte-exact, as client and as server.** On
Victor MS-DOS 3.1 under MAME it opens `/dev/seriala`, programs the line
through the OEM driver's IOCTL block (§11a), takes the µPD7201 and IRQ1 over
for the data path (§11b), and runs complete S/F/A/D/Z/B exchanges with a host
C-Kermit at 9600. That is PORTING.md **§16d** (send, milestone step 5),
**§16g** (`-s *.TXT`, one match and three, plus the first reading of the
driver's two loss counters), **§16h** (`RECEIVE`, and a 2,048-byte round trip
over a payload containing every byte value) and **§16i** (`GET`, `-f`
FINISH, and `-x` server mode — **milestone step 6 is complete**, and §16g's
wildcard send is re-measured at its true byte counts, 63/54/74). Loss
counters read `rxlost=0, rxfull=0` everywhere they could be read.

**Server mode needed a decision, not a fix, and §16i is the one to read
before touching it.** C-Kermit 11 initialises every `en_*` capability to
"remote mode only", and a Victor that owns its serial line is by definition
*local*, so a `-x` server ACKs the negotiation and then refuses every command
with a well-formed E packet. `NOICP` removes the prompt where you would type
`ENABLE GET`. `ckvictor.c` therefore settles the capability set from a
**priority-0 XI initializer**, which also parses `--safe-server` (GET, SEND
and FINISH only; the default is everything the build can do) by blanking the
switch out of Watcom's copy of the DOS command tail **before `argv` is
built**, so `cmdlin()` never sees an option it would reject. That is why
server mode cost no upstream edit at all.

**§16h retracts one earlier claim, and the retraction is instructive.** §16d
and §16g called their transfers "byte-correct" while the Victor sent 74 bytes
as 72; that was the DOS runtime translating a *binary* transfer, not C-Kermit
doing text conversion, and it went unnoticed because every fixture was a
`.TXT` file. `ckufio.c` is the Unix file module and never passes `"b"`. Fixed
by a pair that is only correct together — `_fmode = O_BINARY` from an
initializer in `ckvictor.c`, and `#undef NLCHAR` for `VICTOR9K` in `ckcdeb.h`.
It has never run on real hardware.

**§16k is the one to read before touching the receive path, and its first
sentence is that `-d` costs about 25 ms per received byte.** That is enough
to break long packets by itself, and it is why §16j's "receive ceiling in
(480, 968]" was an artifact of the instrument rather than a property of the
port. Under it was a real limit, and it was `V9K_RXBUFSIZ` at 512 with
`rxpeak` sitting at 502 — the suspect §16j talked itself out of. The ring is
now **4096**, `DRPSIZ` is **4000**, and **32,768 bytes transfer byte-exact at
582 cps** with `rxlost=0 rxfull=0`. `MYBUFLEN` was exonerated and no upstream
edit was needed — still eleven. The three ring counters now print to
**stdout at exit in every build**, because a run fast enough to measure is
exactly a run that cannot carry a debug log.

**§16m closes the last open number in the receive path, and the answer is
the same cause as §16l's.** The ~502-byte `rxpeak` that §16k called a stall
is the ring filling during the **host's retransmission** — with a window of
one, the only moment the host transmits without waiting for our ACK. The
handler now latches a byte offset at the peak, and both it and the first
crossing of 256 land *inside the resent packet*. Three hypotheses died by
measurement first: the inter-packet file write (it runs **before** `ack()`,
`ckcpro.w:1700`, so the host is silent through it), the post-ACK window (0
hundredths in the two runs with the largest peaks), and `MYBUFLEN` drain
granularity (`XFLAGS=-dV9K_RXCHUNK=256` predicted 133, measured 504). What
the file writes *do* cost was measured for the first time: 32 × 1,024 bytes,
3.5–7.0 s (its "worst 0.50 s and always the first" is **corrected by §16n**
— that is the clock's quantum, not a property of the first write). **The
per-transfer dead time is ~12.5 s per 32 KB and does not shrink with line
rate**, so 38400 should be expected to give ~1,400 cps, not ~2,400 — a CPU
and disk problem, not a buffer one; **§16n took the disk out of that and
the figures are now 9.8 s and ~1,630 cps.** §16m also retracts two things
from §16l: its run-2 longest
packet was 3,585 not 3,099, and the 537 → 606 cps improvement attributed to
`SET RECEIVE TIMEOUT 20` is run-to-run variance (four runs at that setting
gave 1, 4, 1 and 1 retransmissions). Four runs, four byte-exact, `rxlost=0
rxfull=0` throughout. Still eleven upstream edits.

**§16n is where the throughput work starts, and its answer is that the disk
cost is per call.** `OBUFSIZE` is 1,024 and `ckcker.h` defines it unguarded,
so it cannot be pre-empted from `ckvictor.h` — but it is only ever read to
seed the `int zobufsize` and to bound `SET BUFFERS`, which `NOICP` removes,
while `getiobs()` and `zmchout()` both read the *variable*. A third XI
initializer therefore sets `zobufsize = V9K_OBUFSIZE` (**8192**) before
`main()` reaches `getiobs()`, for **no upstream edit — still eleven**, and
out of far heap rather than DGROUP. Measured twice against §16m run 4 on
identical wire bytes: **32 writes and 4.5 s become 4 and ~1 s, dead time
12.8 s → 9.8, and 603 → 633 cps.** `rxpeak` fell 513 → 309 as well, which
*confirms* §16m — the peak measures our pre-ACK turnaround, so shortening
it shortens the peak. §16n also **corrects §16m's "worst write 0.50 s and
always the first"**: every timing figure the port has ever printed is a
multiple of 50, so **this machine's DOS clock advances by half a second**
and no individual write has ever been timed. Quote `tot=`, never `max=`.

**MAME cannot run this machine above about 9600, so every 38400 figure in
§16m and §16n is arithmetic and no run in this harness can test it.** The
cap is not configuration: above 9600 the emulation is too slow to meet the
serial timing thresholds, and the real host on the other end of the `-bitb`
socket does not slow down to match. **38400 is a real-hardware-only path.**
At 9600 the emulator is faithful — §16n measured 302 s of wall clock for
`-seconds_to_run 300`, twice — which is what makes the 9600 numbers
comparable at all. Two caveats stand: real-time is not cycle-accurate, and
the **disk timing is almost certainly MAME's rather than the Victor's**
(0.124 s per `write()` is very slow for a real drive), so §16n's *direction*
transfers to hardware and the *size* of its saving may not.

**§16l says the retransmissions are not ours, and that is the thing to know
before spending anything on them.** `alarm()` did fire up to a second early
— `time()` is a floor, so a `time()+n` deadline lands in (n−1, n], and the
comment in `ckvictor.c` §0d claiming "never early" was wrong — and the
deadline is now rounded up. But that was never the cause: across two
byte-exact 32,768-byte receives the Victor sent **only ACKs, never a NAK**,
so its receive timer never expired. Every timeout in the log is the
*host's*, and each lands on the packet where C-Kermit's slow start doubles
the length and hands its round-trip estimator 4.1 seconds of line time it
did not predict. `SET RECEIVE TIMEOUT 20` **on the host** took 2 timeouts
and 4 retransmissions to 1 and 1, and 537 cps to 606. Two instruments came
out of it: an uppercase `S-` line in a C-Kermit packet log is a
retransmission (`ckcfns.c:2002`) and a `<timeout>` line is a timeout
(`ckcfns.c:2900`), which makes a log countable in one `grep -c`.

**§16j retracts a number, and it is the one to know before touching packet
sizes.** `dofast()` — the only thing that turns `SBSIZ`/`RBSIZ`/`MAXSP`/
`MAXRP` into a wire packet length — is inside the `#ifndef NOTCPIP` that
opens at `ckcmai.c:3390` and does not close until 3644, its `#endif`
comments misattributed by one level, so **this build never calls it** and
those four symbols had never influenced a byte on the wire. Every transfer
in §16d–§16i ran 90-byte packets and window 1; the I packet printed in §16i
decodes to exactly that. What reaches the wire is `DRPSIZ`/`DFWSIZ`, now
`#ifndef`-guarded (the eleventh edit). The four capacity symbols still
matter — `makebuf()` divides the pool by the window — but they are capacity,
not the packet length. When checking a `#ifdef` region, **count nesting from
line 1, not from the enclosing function**; doing the latter is what hid this.

**`DRPSIZ` is 4000 in the tree, and that rule still stands for changing
it**: no change to the packet length without a run that reaches FINISH and
reports `rxlost`/`rxfull`/`rxpeak`. §16k satisfied it three times over.
`XFLAGS=-dDRPSIZ=90` puts short packets back for one build without a tree
edit.

The interactive command parser is off (`NOICP`), and the reason is RAM, not
DGROUP: with it in, DGROUP measures 60,768 of 65,536 — it *fits* — but the
image needs 429K and the machine offers 387K. `make -f victorow.mak
XFLAGS=-dKEEP_ICP sizes` re-runs that measurement; `ZT=-zt128` takes DGROUP to
19,376 and does not help the RAM problem. See PORTING.md §9d and §16a.

`XFLAGS=-dKEEP_DEBUG` turns on C-Kermit's debug log (`CKERMITW -d -s FOO.BIN`
writes `./debug.log` on the target). It is affordable here because `-zc` puts
the format strings in far code — the image goes from 202,212 bytes to 282,456,
which still loads with 108,728 bytes to spare. It settled §16g–§16j. **But it
is not free in time: about 25 ms per received byte (§16k), which starves the
receive ring on its own. Never use it to measure anything about throughput or
long packets** — that is what the stdout counters are for.

Two cheaper instruments came out of §16h. **The debug log's own line endings
are an `_fmode` oracle** — `debopn()` goes through the same `zopeno()` the
transfer files do, so CRLF means the runtime is translating and bare LF means
it is not, and `CKERMITW -d -h` writes one and exits in a 2.5-minute boot with
no serial line, no `socat` and no host `kermit`. And **`.probe/` holds
throwaway programs** that answer a libc or DOS question in one short boot;
build lines are in the comment at the top of each.

§16m adds two more. **The interrupt handler is a clock you can afford** —
it already sees every received byte, so latching a byte count, a foreground
location tag or anything else there costs a store and no INT 21h, and the
resulting offsets map onto the host's packet log to say *which packet* an
event happened in (`.probe`-adjacent scripts live in the session scratchpad;
the method is in §16m). And **`v9k_ser_get()` must publish the tail inside
its copy loop, not after it** — publishing once at the end makes the handler
see occupancy rising while the ring is being emptied, which silently
mis-attributes every peak to the drain. That bug produced a confident wrong
answer before it was found.

§16i adds a third: **anything decided before `main()` can be witnessed through
`uname()`**, which `sysinit()` reaches in every invocation, so
`CKERMITW -d -h` reports it in that same 2.5-minute boot. `v9k srvcaps safe=`
is the existing example, alongside `v9k fmode witness=`. When testing a
command-line switch this way, **run the unknown-option control too** — under
`NOICP` any `--` argument is `XFATAL("Extended options not configured")`, and
without the control "no error" cannot be told from "silently ignored".

**PORTING.md §16a is the how-to** — the Victor boots its hard disk as `A:`,
the image needs `vtg_image_util` (mtools cannot read it), and MAME's `-bitb`
socket is single-use, so start `socat` first and never probe the port.

## Hard rules

1. **Do not modify upstream C-Kermit files.** The port's value is that the
   protocol engine is untouched. There are exactly eleven guarded upstream
   edits (listed in `PORTING.md` §8); every one is wrapped in `#ifndef` or
   `#ifdef VICTOR9K` and changes nothing on any other platform. If you think
   you need a twelfth, say so explicitly rather than doing it quietly — the
   seventh through eleventh were all agreed that way.
2. **Feature configuration goes in `ckvictor.h`, never in `victorow.mak`.**
   Each `#define` sits next to a comment explaining why. The makefile passes
   `-fi=ckvictor.h` and nothing else.
3. **Victor-specific C goes in `ckvictor.c`.** It is the only non-upstream C
   file and should stay that way.
4. **Two budgets, and do not confuse them.** DGROUP holds `.data`, `.bss`
   and the **stack** — 48,240 of 65,536 (73%) after the link, 17,296 free.
   The **heap is outside it**: `malloc()` is `_fmalloc` in the large model,
   so the packet buffers do not compete for the segment at all. What bounds
   them is real-mode RAM: the machine hands out 396,224 bytes and the image
   needs 217,594, leaving 178,630 — out of which the far heap then takes
   about 25K of packet buffers. **The receive ring is the exception**: at
   4,096 bytes it is `.bss` and comes straight out of the 64K (§16k).
   **Run `make -f victorow.mak sizes` after any change that could add static
   data** and report the number. Before raising `SBSIZ`/`RBSIZ`/`MAXSP`/
   `MAXRP`, measure the *image*, not DGROUP — `python3 .probe/mzsize.py
   ckermitw.exe` is §16a's method made repeatable, and §9 has both budgets
   side by side.
5. **Never define `BIGBUFOK`** (asks for 290,000-byte buffers). **Never remove
   `DYNAMIC`** (without it the packet buffers become >64K static arrays and the
   build fails outright).
6. **INT 21h only** for console and files. No INT 10h, INT 16h, INT 14h, direct
   screen memory, or BIOS data area — Victor MS-DOS 3.1 has no IBM-compatible
   BIOS, and that discipline is the whole reason one binary runs on both DOSes.
7. **Watch stack frames.** 16-bit target with a recursive `traverse()` in
   `ckufio.c`, and the stack is inside DGROUP. Large automatic arrays are the
   hazard — that is what `SCANFILEBUF` was, and what `CKMAXNAM` turned out to
   be (`traverse()` was 1066 bytes/level, now 98). **Open Watcom has no
   `-fstack-usage`**, so this rule lost its cheap instrument with the gcc
   build: after touching `ckufio.c`, `ckuusr.c` or the size limits in
   `ckvictor.h`, **read the source for new automatics** and, if it matters,
   check the prologue's `sub sp,N` in `wdis` output. Say which you did. The
   stack is **8,192 bytes**, set by `option stack=` in `victorow.mak` and
   chosen rather than inherited (§16j); it was `wlink`'s default 2,048
   through §16i, which was most of one `docmd()` frame away from a
   moderately deep `traverse()`.

## Layout of the port

| File | Role |
|---|---|
| `PORTING.md` | design doc, memory budget, hardware map, milestone plan |
| `ckvictor.h` | all ~40 feature `-D` flags, size limits, platform identity |
| `ckvictor.c` | Victor glue, and **no conditional compilation on the compiler**: process-model stubs (§1), `ioctl`/`FIONREAD`/`TIOCMGET` (§0b), the comm-device `read()`/`write()` and the `alarm()` that bounds the read (§0d), the foreground location tag and write/gap timers the interrupt handler latches against `rxpeak` (§0e, PORTING.md §16m), the gaps in Watcom's Unix surface — `gettimeofday`, `uname`, `link`, `kill`, `getpw*`, plus an `access()` that is right about a FAT root and the `_fmode = O_BINARY` initializer that stops the DOS runtime translating transfers (§1d, PORTING.md §16h), the priority-0 initializer that opens the server capability gate and parses `--safe-server` off the command tail before `argv` exists (PORTING.md §16i), the termios half that programs the 7201 and 8253 through the OEM driver's IOCTL block (§1b, PORTING.md §11a), and **the 7201 data path — IRQ1 handler, receive ring, polled transmitter (§1e, PORTING.md §11b)** |
| `victor/sys/termios.h` | the 7201 driver's control surface; no DOS libc has one, reached via `-i=victor` |
| `victor/sys/ioctl.h` | `FIONREAD` and `TIOCMGET`; without the first `conchk()`/`ttchk()` are hard-wired to 0, and without the second `ttchk()` never reaches `FIONREAD` |
| `victorow.mak` | the build: Open Watcom `wcc`/`wlink` + `sizes` target |
| `victorow/` | headers filling gaps in Open Watcom's DOS libc (`pwd.h`, `sys/utsname.h`, `sys/time.h`, `termios.h`, `ckowsys.h`), reached via `-i=victorow` |
| `ckutio.c` | serial, console, timers — **stock upstream**, this is the port |
| `ckufio.c` | file system — **stock upstream** |
| `ckc*.c` | protocol core — do not touch |

## Code style

Match the surrounding file. C-Kermit is K&R-compatible C with dual prototypes:

```c
VOID
#ifdef CK_ANSIC
ck_bracketaddr(char * s, int n)
#else
ck_bracketaddr(s,n) char * s; int n;
#endif /* CK_ANSIC */
{
```

Comments are block-style with the rationale spelled out, and `#endif` carries
the macro name. New code in `ckvictor.c`/`ckvictor.h` follows the same
conventions — 4-space indent, explanation of *why* over *what*.

## Related trees on this machine

- `~/projects/kermit/msr313src` — MS-DOS Kermit 3.13 source, and
  **`msxv90.asm` is the primary reference for §11**: a Victor 9000/Sirius
  serial driver by this same project, for this exact hardware. PORTING.md §11
  takes its integration model wholesale — the OEM `SERIALA` device is a
  *configuration* channel reached by INT 21h `AH=44h AL=02h/03h`, never a data
  path, with the ISR and RX ring ours. `msyv90.asm`/`msuv90.asm` are its screen
  and keyboard halves and are not relevant to this port.
- `~/projects/myfreedos` — FreeDOS port to the Victor. Reference for the
  MS-DOS 3.1 ISR stack-switching prologue and a TX path proven at 38400
  (`kernel/victor_int14.asm`, `kernel/victor_serial_debug.asm`,
  `kernel/victor_pic.asm`, `docs/victor/subsystem-docs/Serial.md`).
- `~/projects/kermit/victor9000` — `vickermit.c`, a 1980s Victor-native Kermit.
  A third opinion on chip init. Where these three disagree, `msxv90.asm` is the
  one that shipped for this machine.
- `~/projects/newlibc/phase3_newlib` — bare-metal Victor newlib. **Out of
  scope** (see `PORTING.md` §2), and doubly so now that the port no longer
  uses newlib at all. Kept in this list only because `PORTING.md` §12 cites
  its `libgloss/dirent.c` and the two defects flagged there.

## Working style for this project

State what was measured and what was assumed, and keep them separate — the
existing doc does this and it has already caught one overstated benchmark. When
something is proven on real hardware, say which hardware and which
configuration; "the serial code works at 38400" and "polled TX on channel A has
carried sustained output at 38400" are different claims.

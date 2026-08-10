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
DGROUP is 48,304 of 65,536 (73%) after the linker adds libc; `ckermitw.exe`
is 205,212 bytes and **needs 219,452 (214K) at load**. Quote that figure —
it is the port's cost and it is the same on every machine. **The 396,224
that appears in older sections is not a RAM size, and §16x retracts it as a
figure for this DOS too**; Victor MS-DOS 3.1 hands out **824,784 at 896K**.
A Victor takes RAM in 128K increments from 128K to 896K.

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

**§16t closed the port's last live defect: 38400 is clean.** `rxlost = 0`,
zero NAKs, zero retransmissions, byte-exact — **identical to a clean 19200
run in every protocol measure** (18 packets, longest 3,991, 37,569 wire
bytes). The cause was **the cost of our own interrupt handler**: at 260 µs a
byte the C version took about twice that, of which ~123 µs was Open
Watcom's twelve-register `__interrupt` prologue plus the `DS` reload it does
per port access. **`ckvisr.asm` is the port's first assembly** — 110
instructions against 185, 10 stack ops against 24, **2 segment loads against
19**, the last because the 7201 (`E004:0-3`) and the 8259 (`E000:0-1`) are
0x40 apart and **one `ES` reaches both**. `XFLAGS=-dV9K_CISR` puts the C
handler back; it stays compiled as the specification. **No twelfth upstream
edit.** Two structural consequences: `ckvictor.c` is no longer the only
non-upstream source, and 29 of its variables lost `static`.

**Four wrong turns are written up in §16t because they generalise.** The
tree said a byte at 38400 was **26 µs**; it is **260 µs**, which §11 had
right all along — *when two figures for one quantity exist, the older has
usually been checked more*. §16r's "the losses are bursts, therefore not
per-byte cost" was a **false dichotomy** — a *marginally* slow handler falls
progressively behind and loses consecutively. **§16s's own instrument was
inflating the defect 2.5×**: the burst table went on the overrun path, which
is rare only while the receiver keeps up — *inside a burst it is the
per-byte path*. And two hypotheses died cheaply and correctly: the other
µPD7201 channel sharing IRQ1 (`norx = 0, othrx = 0`) and the disk — §16s put
a **floppy** under it, 1.5 s writes against 0 on SASI, and lost nothing,
because with a window of one the write happens before `ack()` and the line
is idle.

**§16ah is seven legs on the machine and it closes the port's last unverified
edit.** All seven byte-exact, `rxlost = 0 rxfull = 0` throughout, every leg
with its host clock captured. **Leg BS sent a 32,768-byte file BY NAME at
38400** — inside the range upstream edit 16 repaired — byte-exact and with no
error line at all, so **edit 16 is no longer the one shipped edit with only a
`wdis` reading behind it**. That leg is also the port's **first send-direction
measurement**: **1,386 cps, the fastest figure this port has produced**, and
sending beats receiving by 19% (non-line cost 13.04 s against 18.71) — the
same conclusion §16v and §16af reached about the receive foreground, seen from
the other side. **But the Victor's prefixing costs +24.3% in wire bytes
against the host's +9.7%** over identical data, so §16ae's `V9K_PREFIXING`
initializer is now measured and looks like the wrong policy; one leg with
`cautious` would settle it. **The `errno` change failed on the bench as it did
under MAME** — BC against BE is the best-matched pair the harness can produce,
identical `rxbytes` and packet count, and the treatment was 350 ms *slower* —
so it was removed under the rule written down before the legs ran. **And
§16af's headline figure is superseded: CRC-16 costs 2.6–3.9 s over a 6-bit
checksum, 69–103 µs per wire byte, 10–15% of the transfer — not the 1.00 s,
26 µs and 3.7% §16af published.** That figure was not mismeasured, it was
**under-determined**: it was a difference of two 50 cs readings quoted as one
number. **The limiting fact is that this bench does not repeat to better than
~1.3 s** — BC and BD are the same binary, both clean, eleven wire bytes apart,
and 1.277 s apart, where §16ag's MAME arms held to 1 ms. Budget for ~a third
of bench legs going off-shape, and **do not make a bench claim about an effect
smaller than ~1.3 s on two legs per arm.**

**§16al closed the flow-control work with four legs, and both answers are
worth knowing.** **§1f is free**: leg GP runs `CKPRE`, HEAD *before* the
change, and its **non-line cost** — host clock minus wire bytes × 260 µs,
which is what makes an off-shape leg comparable — is **21.43 s against the
shipping build's 21.54**, so §1f costs **≤ 0.11 s on a 32 KB receive**,
inside the 151 ms spread of the three clean legs, with the residual bias
running *against* that conclusion. **§16ak's "+11%" is therefore withdrawn**:
the same `CKPRE` binary did 18.29 s non-line in §16ah and 21.43 s here, wire
held constant, so **the bench's spread is the host — macOS, USB, the adapter
— and not the Victor.** That is also the standing answer to item 5b and the
reason adjacent pairs work where cross-sitting comparisons do not. **And leg GB, which
looked like it proved our RTS does not stop this host — clean, byte-exact,
identical to its control on every wire measure, eleven hold-offs,
`rxpeak = 2,974` against 2,978 — is RETRACTED BY §16am.** `kermit -C "show
features"` on the bench Mac lists "Hardware flow control" (`CK_RTSCTS`,
which only makes the command legal) and **not `POSIX_CRTSCTS`**, so that
host's `tthflow()` is the same empty function §16aj found in this port's own
build and **`set flow rts/cts` never put `CRTSCTS` on the FTDI port.** The
far end was never configured to stop. **The rule §16aj wrote about this
port's build — a line of upstream source is not evidence that the build
compiles it — applies to the OTHER END OF THE WIRE too, and `SHOW FEATURES`
is `wcc -pl` for a binary you did not build. Before running an experiment
that depends on the far end behaving a particular way, measure that the far
end can.** Three legs went to finding that out afterwards.
**§16an ran it and the port's half works.** On a Saleae: the Victor's RTS is
negative before any driver, positive when the OEM driver loads, blips on
every chip reprogram, drops 175 µs on each `HANGUP`, and **shows eight
pauses of 785 ms to ~1 s during §16al leg GB** — §1f dropping RTS at the
1,024 mark and raising it at 896, on a clean byte-exact 32 KB transfer.
**Data kept arriving for hundreds of milliseconds after each drop**, so the
one live candidate is the host, which §16am had already explained. **The
default now waits on the host, not the port**: `stty -f <port> crtscts
-hupcl` before `kermit`, or a host C-Kermit built from this tree with
`POSIX_CRTSCTS`. **And the scope found something it was not aimed at:
`msleep()` does not sleep** — this build has no
`select`/`nanosleep`/`usleep` so it compiles upstream's `while (m > 0) m--;`
fallback, which `-os` may delete, so `tthang()` cannot hang up a modem and
**`tcsendbreak()` does not send a break** (that one is `ckvictor.c` §1b's
own code). The fix runs into hard rule 6: INT 21h's only clock is `AH=2Ch`
and it advances in 500 ms steps, so sub-second delays need a calibrated busy
loop. **The instrument lesson is the durable one: every flow-control
measurement before this was a counter inside one of the two programs, and
both programs can be right about what they did while nothing happens between
them. When the question is about a wire, measure the wire.**

The sheet that got there — `HW_TEST_16am.md` — uses the **logic analyzer**,
which is the right instrument and not the software watcher the first draft
proposed: `TIOCMGET`
on the host reads through a USB cable, an FTDI and a kernel driver and gives
one lumped answer for pin-and-cable-and-adapter, where a probe on the
Victor's own pins separates them. §11a0 is the precedent (LS153 15F pin 7,
MC1489 14D pin 3) and the TTL side is what to probe — the connector is
±12 V. **Probe `/DTR` alongside `/RTS`: same WR5 byte, same instruction
pair, bit 7 and bit 1, so DTR is a free control.** Stimulus is `CKICP`'s
`HANGUP`, already on the image. **One more thing the analyzer will settle:
§16v's `cts = 1` is not proof the pair is wired inbound** — a floating
MC1489 input can read active, and leg DS only needed CTS to *read* asserted,
so the input-half claim is on the line too.
`V9K_FLOW` stays `FLO_NONE` for a measured reason now; the input half works
and is fast (1,475 cps with the CTS test on the transmitter's per-byte
path). The port's side of the RTS write is right by static analysis —
`msxv90.asm`'s `DTR_RTS_OFF EQU 7DH` confirms WR5 bit 1 is RTS, and the
register pointer is at 0 when the handler writes the `5` — so the three
remaining candidates are the pin, the cable and macOS, and **no instrument
in this tree points at any of them.** One method point to keep: **when a leg
keeps going off-shape, change what you ask of it, not how many times you
ask** — a narrow band (1024/896) gives a *cap* to read where a low mark
(256/64) gave a comparison, and a cap survives a retransmission.

**Two bench sittings in a row were lost to the harness rather than the port,
and the pattern in both is the same: a run sheet that checked one precondition
and not the neighbouring one.** The second was **a full disk** — four legs
failing with `Too many retries` after eleven packets and then silence, every
output file 0 bytes, `Free: 0 B (0.0%)`. **The leg that failed first ran
`CKPRE`, HEAD before the change under test**, which is what says immediately
that the build is not implicated. Staging one 206,758-byte binary onto an
image nobody had checked the free space of since §16ai was the whole cause.
**`vtg_image_util info <img>` belongs in every run sheet's §0 beside the
target-name check**, and the standing answer nobody has used is that
**partition 1 (`D:`) is 9.7 MB and 100% free.** A real port finding came out
of it and should not be lost: **out of disk space makes the Victor hang
rather than fail** — §0d's `alarm()` bounds the read and nothing bounds a
failed write, so the host gives up and the Victor never does.

**The re-run of §16ak's decisive pair was VOID, and the cause is worth more
than the legs would have been.** `RCVDA.DAT`/`RCVDB.DAT` were still on the
image from the first sitting; `SET FILE COLLISION` is `BACKUP`; **BACKUP
cannot work on FAT**. Both legs came back with 287-byte packet logs reading
S, F, A, **Z with data `D`**, and the Victor's own screen said `No files
were transferred (refused: destination file already exists)`. The run sheet
documented that exact trap and its exact signature **one section above the
instruction that walked into it**, and it also asked for a re-run at marks
whose binary it never built or staged. **The fix is structural, not
mnemonic**: `HW_TEST_16al.md` gives every leg a target name that has never
been used *and* opens every receive `.BAT` with `IF EXIST <target> DEL
<target>`. A rule a person has to remember is not a fix; a rule the machine
keeps is. Same for build flags — **a sheet that names a `-d` flag must also
name the staged binary that carries it, or the flag is a suggestion.**

**§16ak ran flow control on the machine: seven legs, all byte-exact, and
the sitting answered "is it safe" while failing to answer "is it
effective".** Safe is settled with the two tightest null pairs this project
has produced: leg DS sent 32,768 bytes with the CTS test on the per-byte
transmit path at **1,475 cps** — equal to the port's fastest — and leg DX,
the same send under `--xonxoff`, landed **3 ms** away; leg DE ran
`--rtscts` at the shipping water marks and was **identical to its control
on every wire measure, 6 ms apart on the clock**. Effective is not: **leg
DB took a timeout and three retransmissions in its first 7,680 bytes**, and
`mapoffset.py` puts its `rxpeak` fourteen bytes into a *resend* — §16m's
finding and §16ag's caveat, printed in the run sheet directly above that
leg. **`V9K_FLOW` stays `FLO_NONE`**: harmless and effective are different
claims and only the second licenses a default. Three things generalise.
**Ask where an `rxpeak` IS before reading it as a cap** — leg DE was
briefly claimed as the positive result on a "65-byte overshoot" until
`mapoffset.py` showed the peak sitting at a packet boundary, exactly where
the two control legs peak. **`stall256` was 2,399 on DB against 47 on its
control and nothing explains it** — that needs the sender to have paused,
but fifteen assert/release cycles cannot produce 2,399 crossings; it is the
only positive hint that our RTS reaches the far end's CTS and it is not
proof. **And the bench repeated to 398 ms this sitting**, against §16ah's
1.3 s, so that figure is a bound and not a floor. Two costs measured:
**XON/XOFF lost 19 bytes in 11 bursts where RTS/CTS at the same marks lost
none** (first non-zero `rxlost` since §16t, cause not established, and
nothing counts the ISR's failed XOFF attempts), and **the three clean
receive legs ran 11% slower than §16ah leg BC on identical wire bytes** —
which may be §1f's cost or may be a cross-sitting artefact, and **the run
sheet had no adjacent pre-change control, which is the error to not repeat.**
`CKPRE.EXE` is on the image; one pair settles it.

**§16aj built the last unimplemented feature — flow control — and the
interesting part is that both of NEXT_SESSION's premises about it were
wrong.** `ckvictor.c` §1f does RTS/CTS and XON/XOFF, both directions, in
both interrupt handlers, with the assert in the handler (the case it exists
for is the one where the foreground is *not* running) and the release in
`v9k_ser_get()`. Water marks 3/4 and 1/4. **Four instructions per byte in
the ISR**, and only four because the high mark is a *variable* set to
`0FFFFh` when flow control is off, so one compare answers both "is it on"
and "have we crossed it". **No upstream edit — still seventeen.** **It ships
OFF**: nothing needs it at a window of one, and selecting RTS/CTS gates the
transmitter on a CTS that §16v measured only in the *other* direction — one
bench leg flips the default. Selection is `--rtscts` / `--xonxoff` /
`--noflow` through §16i's priority-0 XI mechanism, applied into
`cxflow[CXT_DIRECT]` from `v9k_ser_install()`, which is §16ai's lesson
reused: the durable place is the variable upstream copies *from*.
**The premises that failed were both "upstream already hands us the
bits".** `ckutio.c:6252`'s `CRTSCTS` is inside `#ifdef OXOS`, and with no
`POSIX_CRTSCTS` the *whole of `tthflow()`* preprocesses to `int x = 0;
return(x);` — measured with `wcc -pl`, thirty blank `#line` directives.
`ckutio.c:6617`'s `IXON|IXOFF` are set and then **cleared again at 6758**,
inside a `TESTING234` block that is an `if (1)` under an `#ifdef` of its own
`#define`, four lines before the `tcsetattr()` that applies the struct — so
`SET FLOW XON/XOFF` cannot reach a driver through termios on **any** POSIX
build. §1f reads upstream's `flow` variable instead. A third: the only call
to `tcflow(TCOON)` in `ckutio.c` is the argument of a `debug()`, which
`NODEBUG` deletes, so POSIX's lost-XON recovery does not exist here and the
driver carries its own backstop. **All three are report-upstream items, not
edits.** The rule they share is §16j's, learned again: **a line of upstream
source is not evidence that the build compiles it, and `wcc -pl` settles it
in under a second.** Verified under MAME at 9600, four legs byte-exact with
`rxlost=0 rxfull=0`; with the marks lowered to 256/64 `--xonxoff` gives
`held=1 rel=1` and intercepts five host START characters while
`pktstat.py --rxbytes` stays at the clean −11. **§16aj also shows MAME is
not automatically quiet**: its two leg groups drifted 12–15 s apart on a
busier host where §16ag's arms held to 1 ms — run the control adjacent to
the treatment. DGROUP 48,336 (73%), image 206,758, needs 220,950 (215K),
**smallest Victor 384K, unchanged**.

**§16ag took the two free items §16af listed, and only one of them was
free.** `NOCKXXCHAR` ships: `ckcdeb.h:3390` turns `CKXXCHAR` on for any
build defining `UNIX`, it backs two `SET` commands **whose only setters are
behind `#ifndef NOICP`**, and its test on `ttinl()`'s per-byte loop can
therefore never be true in a shipping build. It costs **−512 DGROUP (exactly
`short dblt[256]`, repaying §16af's CRC table to the byte), −756 image**, and
measured **−1.07 s, 2.1%, at 9600 under MAME** over two legs that reproduced
to 1 ms. **The `errno` far call did not ship.** The mechanism is confirmed —
`ckvictor.h` is force-included, so `#define errno (*v9k_errnop)` makes
Watcom's `errno.h` take its `#else` branch, whose `extern int errno`
*expands to a correct declaration of the pointer*, and 27 far calls leave
`ckutio.obj` — but it measured **98 ms slower**, twenty times the spread of
either arm. `XFLAGS=-dV9K_FAST_ERRNO` turns it on and the code stays
compiled either way, so **the shipping binary is byte-identical to the one
the legs measured**. **This is the fifth hand-costed 8088 prediction in this
tree to be wrong and the first to be wrong in sign**, so §16af's "ordering
arguments, never magnitudes" is itself downgraded: they are not reliable for
ordering either. Two readings survive and the harness cannot separate them
(MAME is not cycle-accurate; §16w's layout sensitivity has no null leg
available to a change that alters code size). **The structural point is the
one to carry forward: at 9600 the foreground has 555 µs of slack per byte
and at 38400 it has none**, so a per-byte foreground saving can hide at 9600
— which also means `NOCKXXCHAR`'s 2.1% is probably its *size*, not its two
instructions, and should not be quoted as the cost of the test. One leg came
back off-shape (0 timeouts, 0 resends) and was excluded, but it confirmed
§16m by absence: **`rxpeak` was 17 of 4,096 without a retransmission against
299 with one.** Still seventeen upstream edits.

**The ring was the next binding constraint and §16af closed it.** `rxpeak`
is **2,581 of 4,096** with 1,515 bytes of margin, `rxfull = 0` at block 3
for the first time, and §16k's sizing argument no longer needs redoing
because nothing presses on it. `peaktag = 12` still names foreground packet
decoding, which is where the next lever is: `ttinl()`'s per-byte loop at
~133 µs and the ISR at ~172 are the two largest remaining items, and **only
the second is ours**.

**§16af is the seventeenth upstream edit and it is the one §16ae asked
for.** `chk3()` computed a 16-bit CRC in `long` through two `long[16]`
tables; on an 8088 built with `-0` that put **two software shift loops** in
the per-byte path (`wdis`: `mov cx,8` / `sar dx,1` / `rcr ax,1` / `loop`),
because an 8086 has no shift-by-immediate. A `#ifdef VICTOR9K` arm does the
**same CRC** — same polynomial, same init, no final XOR — in `unsigned int`
through one 256-entry table: **603 8088 cycles per byte become 81**, 36 loop
instructions become 15, and the function loses its stack frame.
`crcta[]`/`crctb[]` are untouched because `ckcfns.c` reads them for the file
CRC and narrowing them would need a second file. On the bench at 38400,
against a same-session baseline control that reproduced §16ae leg PC **to
the byte** (44,720 wire bytes, 3,800 cs): **`rxfull` 741 → 0**, `rxpeak`
4,095-pinned → 2,581, 26 packets and 3 resends → **18 and zero**, 44,720
wire bytes → 37,568, and **38.00 s → 28.00 s, 862 → 1,170 cps, +35.7%**.
**§16ae's uncomfortable trade-off is gone**: CRC-16 now costs **one clock
quantum** over a 6-bit checksum (28.00 vs 27.00 s, 26 µs/wire byte) where it
cost 11.5 s and 142 µs, so there is no speed argument left for shipping
weaker error detection. Correctness is proved twice and they are different
claims — `v9k/proofs/vcrc16.c` checks the table identity exhaustively over all
256 entries and the loop over 20,500 length-and-fill combinations, and four
transfers came back byte-exact. **A block check that is fast and wrong fails
silently**, which is why the probe is exhaustive rather than sampled.

**Three prediction failures are written up in §16af because they generalise.**
An 8088 **cycle** count said the saving was ~104 µs/wire byte; MAME measured
54. That is the fourth hand-costed 8088 figure in this tree to come out
optimistic — §16t's *fetch* model was the earlier one — so **treat both as
ordering arguments, never as magnitudes**. Then, from the MAME leg, this
project asserted §16ae's 142 µs "bundles the overflow recovery" and put the
true figure near 63; the bench says ~80 was arithmetic and ~60 was the
overflow that the arithmetic *caused*, so §16ae had measured block 3's total
penalty correctly and it simply was not all CRC. **And a clean baseline
block-3 figure does not exist and cannot be taken** — the baseline cannot run
block 3 cleanly at 38400, which is the defect itself. The pattern in all
three: a difference between two legs is only a measurement of one mechanism
if the other mechanisms are equal, and an overflowing leg is never equal to a
clean one.

**§16af's null leg is the one to copy.** AH ran the new binary at block 1,
where edit 17 has no mechanism to do anything, and had to reproduce §16ae
leg BX — it did, within one clock quantum. That is what makes the headline
**attributable**: any binary differs from any other in layout, §16w showed
this machine is unusually sensitive to code size, and a floor that had moved
would have meant the rebuild was being measured rather than the edit.
**Spend a leg on the result that is supposed to be nothing.**

**§16u built the throughput instruments and §16v used them on the bench:
1,013 cps at 38400, and the line is no longer the bottleneck.** This project
spent its whole life with elapsed time and cps on the operator's screen and
in no file, because C-Kermit's transfer display goes away under the redirect
that records the `v9k:` counters. §16u closed that with a Victor-side
`elapsed=`/`wire=` line and a `statistics` at the end of every take-file,
validated at 9600 under MAME (632 cps, reproducing §16n's 633 and §16t's
`rxpeak = 294`). §16v then ran both bench legs, byte-exact, `rxlost = 0`:
**38400 → 1,013 cps** (18 packets, zero retransmissions) and 19200 → 820.

**The finding is where the 34 seconds go.** Line time is 9.78 s — **29%**.
Disk is 0.50 s, `txgap` 2.50 s, and **21.2 s (62%) is foreground packet
decoding**, which `peaktag = 12` names: **564 µs per received byte, ~2,800
cycles on a 5 MHz 8088, against a 260 µs byte time.** That is §16t's ISR
defect one level up. **Take the wire out entirely and ~1,353 cps is the
ceiling**, so §16n's ~1,630 projection is dead (it is above that ceiling),
§16t's ≤ 2,780 was loose by 2.7×, and rate is finished as a lever — 19200 →
38400 bought only +17% to +24%. The build compiles `-os`; `-ot` on the
decode path has never been measured and is the open question.

**§16ae answered it, and the answer was the block check, not the wire.**
The session set out to cut wire bytes by unprefixing control characters and
found the host had been doing that all along: **three sessions of "default"
land on 37,5xx wire bytes, which is `cautious`'s number**, so §16w's "close
to worst case for Kermit's prefixing" described a fixture that had already
had the cheap prefixes taken out. The change is also on the wrong end —
`ctlp[]` is read only in `bgetpkt()` and `getpkt()`, the packet *builders*,
so **unprefixing is a sender-side decision** and a receiver's setting cannot
affect what arrives. `ckvictor.c`'s initializer and `V9K_PREFIXING` stay
because they are right for a Victor *sending*, which is **unmeasured**.
What the 2×2 did measure is **`chk3()` at ~142 µs per wire byte, ~17% of
the receive cost** — a 16-bit CRC done in `long` arithmetic (`crcta[]`/
`crctb[]` are `long[16]`, `ckcfn2.c:312`). **`SET BLOCK 1` on the host takes
26.50 s and 1,236 cps against §16v's 34.00 s and 964 on the same clock,
+28%, the fastest run the port has ever done**, and it moves the no-line
ceiling from ~1,353 to **~1,957 cps**. That is not a recommendation to ship
a 6-bit checksum; it is the argument for spending edit 17 on `chk3()`'s
arithmetic and keeping CRC-16 — **which §16af then did, and the CRC now
costs one clock quantum instead of 43%**. **§16t's instruction-fetch model
was low by 2.4× and had been used to argue against taking the
measurement** — the ~200 µs this project quotes for the assembly ISR comes
from that same unchecked model. **And `rxfull != 0` was a live defect**:
three of four block-3 legs pinned `rxpeak` at 4,095 of 4,096 and lost bytes
(556, 640, 649), while all three block-1 legs sat at 2,6xx with a spread of
38. The protocol hid it — all seven legs byte-exact — by resending, which
is why leg PA needed 49,214 wire bytes to move 32,768. **§16af closed it**;
the 142 µs this section measured was ~80 of CRC arithmetic and ~60 of the
overflow that the arithmetic caused, which is why removing the arithmetic
removed both.

**§16v also settled the flow-control default: `cts = 1` on the real cable**,
both legs, a genuine RR0 read with the host holding RTS asserted under `set
flow none`. So RTS/CTS is wired here and is the cheaper path — but **the
bench settles the default, not the feature set: XON/XOFF stays in scope as
an interoperability requirement**, because the far end's wiring is not
something this port can measure. Neither costs an upstream edit; `ckutio.c`
already hands our `tcsetattr()` the right termios bits (`IXON|IXOFF` at
`ckutio.c:6617`, `CRTSCTS` at `6252`), and selection under `NOICP` is §16i's
initializer pattern. Two reading rules survive: the Victor's `elapsed=` and the host's `statistics` **do not
measure the same interval** (the Victor's starts at the first byte received,
before the S packet, and closes at release — 1.7 s wider on a clean run,
15.2 s when a startup timeout intervenes), and **`wire=` is a receive-leg
figure** since it divides `rxbytes`. Quote the pair, never one alone.

**§16q built the instrument §16p asked for.**
`lost evt`/`max`/`tag`/`fd`/`lostat`/`lostend` latch on the overrun path:
`evt` counts bursts, `tag` is §0e's foreground location latched at the
**first** loss rather than at the peak. `evt` near 4 means something holds
the machine off and `tag` names it; `evt` near `rxlost` means the per-byte
path is too slow. **The MAME harness cannot reach this code** — the chip
does not overrun below 38400 and the emulator cannot drive above 9600 — so
`v9k/proofs/vburst.c` replays the arithmetic on the host instead (8 cases, all
pass) and a 32 KB 9600 receive proves only that it costs nothing: byte-exact
with `rxpeak = 309`, identical to §16n's pre-change run. **§16q also
corrects §16p's headline: `rxlost` counts interrupts that found the latched
overrun bit, not bytes**, so one hold-off losing fifty bytes can raise it by
one and "0.45% of received bytes" is a lower bound. Two design points worth
keeping: burst boundaries are measured as a gap in the **byte stream**, not
as consecutive handler entries, because the latter needs a store on the
per-byte path (~5 µs of a 260 µs byte at 38400) inside an instrument built to
ask whether that path is too slow — §16k's mistake, caught by reading `wdis`
rather than by thinking; and `rxbytes` now counts the substituted BELL,
which affects only lossy runs.

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

**The interactive command parser is off by DEFAULT (`NOICP`), and that is a
default rather than a verdict — it is a feature this port intends to ship.**
`ckvictor.h` calls `NOICP` the removal of "the one thing this port most
wants back", and the paragraph that used to say the parser "loads on neither
DOS" rested on the 387K figure §16x retracted. **§16y builds it**
— `XFLAGS=-dKEEP_ICP ZT=-zt2048` links, loads on the Victor and prints a
parser's help text, needing **429,890 (419K)** — **smallest Victor 512K** —
against the shipping build's
219,452. Three fixes got it there and none was an upstream edit: `isfloat()`
in `ckvictor.c` §2b (`NOFLOAT` removes `CKFLOAT`, which removes upstream's),
`__near` on the receive ring (`-zt` would otherwise move it out of the group
`ckvisr.asm` reaches through `DS` — **the one to remember, since `-zt` is
the lever anyone short of DGROUP will reach for**), and the threshold sweep.
**`KEEP_ICP` is not scripting**: `ckvictor.h` defines `NOSPL` separately, so
the build gets a `C-Kermit>` prompt and not `-C`, variables, macros or
`INPUT`. **It does keep `TAKE`** — that is `#ifndef NOICP`, not `NOSPL`
(§16y corrects an earlier claim here). `KEEP_SPL` links via §2c and costs
**637,714 at load against 429,890, +207,824**.

**§16z, §16aa and §16ab regression-tested that build on the machine, and
§16ab is the section to read before touching the parser.** The parser
works, `TAKE` works from the prompt (`PTEST.KSC` ran `echo`, `show
versions` and `exit` in order), `SHOW VERSIONS` works on hardware — the
twelfth upstream edit, and the only way to identify a build on the machine
— and `SET LINE /dev/seriala` now reports **local**, so a speed set from
the prompt reads back for the first time in the port's life.

**Four defects came out of it, all fixed in `ckvictor.c` for no upstream
edit, and they share a shape worth keeping.**

1. One cached `struct termios` for the console and the line, so every
   console mode change through `concb()`/`conres()` overwrote the line's
   `c_ospeed` and `SET SPEED` did not stick. The chip was programmed
   correctly; `ttgspd()` lied.
2. `ttyname()` returned `"CON:"` for **every** descriptor, so `ttopen()`
   concluded the serial line *was* the controlling terminal, set remote
   mode and forced `ttyfd` to 0 — and `SET LINE` then "succeeded".
3. The console prompt echoed every line **twice**, the second copy from
   column 0 on top of the first. Two rounds of source reading blamed a
   missing newline and were wrong. `read(0,...)` was reaching DOS's
   *cooked* line input (INT 21h AH=3Fh via the Watcom runtime), which
   echoes as you type and emits a bare CR on Enter; C-Kermit then read the
   buffered line back one byte at a time and echoed it again itself. Two
   echoers, one carriage return. `v9k_read()` now honours `ICANON` and
   does AH=07h — direct console input, no echo, VMIN 1 — and `ICRNL`/
   `ONLCR` from the earlier round are still needed and still right (§16ac).
   **Confirmed under MAME (§16ad)**, along with `CKICP FILE.KSC` in both
   the relative and absolute forms, `mode: local` after `SET LINE`, and
   `SET SPEED 19200` reading back.
4. `getcwd()` returned DOS's `A:\`. This build defines `UNIX`, so
   `zfnqfp()` joins with `/` and never tests for a separator already on
   the end — the qualified name came out `A:\/NAME`. **One defect, two
   symptoms**: `dotake()` could not open it, and `dotake()` failing is also
   what leaves `cfilef` at 0, which is the only thing that tells `cmdlin()`
   to skip argv[1]. So the file silently failed to open and the *filename*
   was then reported as an invalid option. That is what broke
   the *qualified name* for `CKICP FILE.KSC`; the absolute form took the
   **thirteenth** upstream edit, and that needed two files —
   `isabsolute()` (`ckcmai.c`) and `zfnqfp()`'s own copy of the same test
   (`ckufio.c`) — because fixing only the first moves the failure rather
   than removing it. **`CKICP FILE.KSC` still does not work**, and §16ac
   says why: the `#ifndef NOTCPIP` at `ckcmai.c:3417` is mis-nested and
   compiles out `dotakeini()` and `if (cmdfil[0]) docmdfile(0)` — 70 lines
   of `main()` — so the file is found, qualified, and never run. That is
   §16j's defect and the same region. **Edit 14 fixed it, and it is the
   one edit in this port that is not a no-op elsewhere** — an `#endif`
   cannot be placed conditionally, so upstream's own `#endif` moved to
   where its own comment says it belongs. Watch the second-order effect
   it nearly had: `dofast()` is in the widened region and sets
   `wslotr = RBSIZ/MAXSP = 2`, so the repair would have opened the window
   to two, unmeasured, on a port with no flow control and a 105-byte ring
   margin. That call is now `#ifndef VICTOR9K`. **When a preprocessor
   repair widens what a build compiles, enumerate what newly comes in
   before believing the repair is inert.**

Every one was latent for the port's whole life and **none was reachable
without the parser** — `cmdlin()`'s `-l` passes `lcl = 1`, so `ttopen()`
was told the answer rather than asked; nothing read the speed back; nothing
echoed at a prompt; nothing qualified a relative pathname. **A switch that
turns on a large body of upstream code is an instrument, and the first
thing it measures is the port's own stubs.**

**One defect is left and it is upstream's: the `SET SPEED` keyword table.**
**It is not a wire problem** — 38400 transfers are proven on hardware and
are driven by `-b 38400`, which never touches this table; this is the
interactive command in a `KEEP_ICP` build only.
`cmdini()` builds the speed keyword table with `spdtab[j].kwval = (int)
ss[i] / 10` (`ckuus5.c:1262`) — the cast binds tighter than the divide, so
`(int)38400L` is -27136 on a 16-bit `int` and the keyword's value comes out
-2713. `cmkey()` returns it, `SET SPEED` sees `x < 0` and returns silently.
**Every speed above 32767 is affected, and 76800/115200 are worse** — they
stay positive and are accepted as 11260 and 49660 bps. Only `SET SPEED`
reaches it; `-b` divides as a long (`ckuusy.c:4164`), which is why every
38400 figure this port has published is sound. Fixed as edit 15, `(int) (ss[i] / 10)`,
and verified under MAME: `nlookup DIRECT HIT[38400]=3840`, `tcsetattr
divisor=2`, `ttgspd speed=38400`. Deliberately unguarded — it is a no-op
wherever `int` is 32 bits. §16ad.

**38400 is a hardware ceiling, not a setting, and §11a0 is where that was
established.** `bps = 1,250,000/(16 x count)` with the 8253 in Mode 3, so
count 2 and **39,062.50 bps** is the fastest the machine does
asynchronously — which is what the port has shipped since §16o. The 8253's
1.25 MHz is **measured** at LS153 15F pin 7 (156,250 Hz at count 8 and
9,615 Hz at count 130, both x count = 1,250,000), which also settled a
1.25-vs-1.2288 MHz argument that ran through four documents. Every rate on
this machine is consequently **1.72% fast** and no integer count fixes it.
The 7201's x1 mode reaches higher rates and the datasheet permits it in
async — a 32 KB send at x1 completed byte-exact — but x1 *receive* needs the
two ends matched to ~100 ppm, and the only path to RxCA is through the LS90
chain, so there is no external clock to be had. `B57600`/`B76800`/`B115200`
were removed again for that reason: `ttspdlist()`/`ttsspd()`/`ttgspd()` key
off those `#define`s, so defining one offers a rate that cannot transfer.

**§16x is why that became possible**, and it is a retraction worth knowing.
"The image needs 429K and the machine offers 387K" rested on **396,224**,
which was a *FreeDOS* measurement filed under an MS-DOS 3.1 heading in §16a
and then inherited everywhere. **Victor MS-DOS 3.1 gives 824,784 at 896K**,
and the model is `free = installed RAM − 92,720` — this DOS loads high,
11,584 below the program and 81,136 above, both constant. `v9k/probes/vmem.c`
asks a running machine; `mzsize.py` reports the smallest Victor that can
load a build. **Quote the requirement, not the spare.**

**Two cautions on those machine numbers.** Only **256K and 896K** have been
measured — 256K predicted and confirmed that `CKERMITW` will not load — and
everything else is the model talking. And **MAME misreports 512K and 640K
on `victor9k`**: both claim 759,248 free, which is arithmetically impossible
at 640K, so the sizes this question turns on cannot be settled in emulation.
See PORTING.md §16y, §16x, §9d, §16a.

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
no serial line, no `socat` and no host `kermit`. And **`v9k/probes/` holds
one-shot programs** that answer a libc or DOS question in one short boot;
build lines are in the comment at the top of each. **`v9k/` is the port's
own tree and the top-level `tools/` and `tests/` are upstream's** — do not
put port material in those. `v9k/tools/` holds standing instruments (hard
rule 4 requires one of them), `v9k/proofs/` holds the host programs §8
cites as the correctness argument for a shipped edit, and `make -C
v9k/proofs` builds and runs them. It was `.probe/` until 2026-08-09; a
directory a build rule depends on should not be hidden from `ls`, and the
one name did not fit all three kinds of thing in it.

§16m adds two more. **The interrupt handler is a clock you can afford** —
it already sees every received byte, so latching a byte count, a foreground
location tag or anything else there costs a store and no INT 21h, and the
resulting offsets map onto the host's packet log to say *which packet* an
event happened in (`v9k/tools/mapoffset.py` does exactly this;
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
   protocol engine is untouched. There are exactly seventeen upstream
   edits (listed in `PORTING.md` §8); thirteen are wrapped in `#ifndef` or
   `#ifdef VICTOR9K` and change nothing on any other platform. **14, 15 and
   16 are not, and all three are flagged as such**: 14 moves a mis-nested
   `#endif` (an `#endif` cannot be placed conditionally), 15 fixes a cast
   that binds wrong, and 16 widens an `int` that was holding a `CK_OFF_T`.
   The last two are no-ops wherever `int` is 32 bits and so would be
   actively harmful to guard. If you think you need a seventeenth, say so
   explicitly rather than doing it quietly — the seventh through sixteenth
   were all agreed that way. Say it again if
   the edit turns out to need a second file: 12 and 13 both did, and 13's
   second half was the one that made the first half do anything.
2. **Feature configuration goes in `ckvictor.h`, never in `victorow.mak`.**
   Each `#define` sits next to a comment explaining why. The makefile passes
   `-fi=ckvictor.h` and nothing else.
3. **Victor-specific C goes in `ckvictor.c`.** It is the only non-upstream C
   file and should stay that way. **`ckvisr.asm` (§16t) is the one exception
   and it is assembly, not C** — the µPD7201 receive ISR, which exists
   because Open Watcom's `__interrupt` saves twelve registers with no way to
   ask for fewer. Do not add a second assembly file without the same kind of
   measurement behind it.
4. **Two budgets, and do not confuse them.** DGROUP holds `.data`, `.bss`
   and the **stack** — 48,304 of 65,536 (73%) after the link, 17,232 free.
   The **heap is outside it**: `malloc()` is `_fmalloc` in the large model,
   so the packet buffers do not compete for the segment at all. What bounds
   them is real-mode RAM: **the image needs 219,452 (214K) at load**, and
   the far heap then takes about 25K of packet buffers on top. **The receive
   ring is the exception**: at 4,096 bytes it is `.bss` and comes straight
   out of the 64K (§16k).
   **Run `make -f victorow.mak sizes` after any change that could add static
   data** and report the number. Before raising `SBSIZ`/`RBSIZ`/`MAXSP`/
   `MAXRP`, measure the *image*, not DGROUP — `python3 v9k/tools/mzsize.py
   ckermitw.exe` is §16a's method made repeatable, and §9 has both budgets
   side by side.
   **Quote the requirement, not the spare.** A Victor takes RAM in 128K
   increments from 128K to 896K, so "177,236 spare" is true only of the
   896K bench machine and says nothing about the ones most people have.
   `mzsize.py -a <bytes>` checks against a different machine; `-a 0` prints
   the requirement alone. Every byte added to the image is a byte of the
   smallest Victor this port can ever run on.
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
| `ckvictor.c` | Victor glue, and **no conditional compilation on the compiler**: process-model stubs (§1), `ioctl`/`FIONREAD`/`TIOCMGET` (§0b), the comm-device `read()`/`write()` and the `alarm()` that bounds the read (§0d), the foreground location tag — now including the `fopen`/`fclose` wrappers and the breadcrumb that subdivides "upstream" (§0e, PORTING.md §16m, §16s) — and the write/gap timers the interrupt handler latches against `rxpeak`, the gaps in Watcom's Unix surface — `gettimeofday`, `uname`, `link`, `kill`, `getpw*`, plus an `access()` that is right about a FAT root and the `_fmode = O_BINARY` initializer that stops the DOS runtime translating transfers (§1d, PORTING.md §16h), the priority-0 initializer that opens the server capability gate and parses `--safe-server` off the command tail before `argv` exists (PORTING.md §16i), the termios half that programs the 7201 and 8253 through the OEM driver's IOCTL block (§1b, PORTING.md §11a), **the 7201 data path — IRQ1 handler, receive ring, polled transmitter (§1e, PORTING.md §11b)**, and **flow control — RTS/CTS and XON/XOFF, both directions, water marks in the handler and the release in the ring drain (§1f, PORTING.md §16aj)** |
| `ckvisr.asm` | the µPD7201 receive ISR, by hand — the port's only assembly, and the reason is that Open Watcom's `__interrupt` saves twelve registers with no way to ask for fewer (§16t). Assembled with `wasm`, reads no header, so `ckvictor.c` carries a build-time check that the ring size the two agree on has not drifted. `XFLAGS=-dV9K_CISR` selects the C handler instead. §16aj added the flow-control assert to it: four instructions on the clean per-byte path, and the mark is a variable so one compare answers both "is it on" and "have we crossed it" |
| `victor/sys/termios.h` | the 7201 driver's control surface; no DOS libc has one, reached via `-i=victor` |
| `victor/sys/ioctl.h` | `FIONREAD` and `TIOCMGET`; without the first `conchk()`/`ttchk()` are hard-wired to 0, and without the second `ttchk()` never reaches `FIONREAD` |
| `victorow.mak` | the build: Open Watcom `wcc`/`wlink` + `sizes` target |
| `victorow/` | headers filling gaps in Open Watcom's DOS libc (`pwd.h`, `sys/utsname.h`, `sys/time.h`, `termios.h`, `ckowsys.h`), reached via `-i=victorow` |
| `v9k/tools/` | standing instruments, not disposable: `mzsize.py` (**hard rule 4 requires it**), `pktstat.py`, `mapoffset.py`, `ctswatch.py` (host-side `TIOCMGET`, §16am — the modem lines read without Kermit in the path) |
| `v9k/proofs/` | host programs §8 cites as the correctness argument for a shipped edit — `vcrc16.c` (edit 17) and `vburst.c` (the ISR burst detector). `make -C v9k/proofs` builds *and runs* them |
| `v9k/probes/` | genuine one-shots, kept so the answer stays checkable; build line at the top of each |
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

# Next session

Handoff for the Victor 9000 port, written 7 August 2026. **The port has no
known live defect.** 38400 was the last one and §16t closed it: the cause
was the cost of our own interrupt handler, and `ckvisr.asm` — the port's
first assembly — replaced it.

**Read `PORTING.md` §16t first.** It carries both the fix and four wrong
turns that are worth more than the fix. Then **§16u**, which is short: the
clock and `mdm` instruments are validated end to end, and the reading rule
they came with is that the Victor's `elapsed=` and the host's `statistics`
do not measure the same interval.

---

## 0. Where the port is

**File transfer works, both directions, as client and as server, at 9600,
19200 and 38400, on real hardware, byte-exact.**

38400 now transfers **identically to a clean 19200 run** in every protocol
measure — 18 packets, longest 3,991, 37,569 wire bytes, zero NAKs, zero
retransmissions, `rxlost = 0 rxfull = 0`. Before §16t it needed 37 packets
and lost 1.8% of received bytes.

```
v9k: isr=asm
v9k: rxlost=0 rxfull=0 rxpeak=2621 of 4096
v9k: lost evt=0 max=0 tag=0 fd=0
```

Still **eleven** guarded upstream edits. DGROUP 48,272 of 65,536 (73%),
image 204,764, needs 218,988 with 177,236 spare.

---

## 1. Do this next, in priority order

**1. Measure elapsed time and cps at 38400 on the bench — the instruments
are built, validated and staged, and only the drive is left.** §16u ran
both of them through a 32 KB receive at 9600 under MAME and they work:

```
v9k: elapsed=6700 cs wire=590 B/s        elapsed time : 00:00:52 (51.829 sec)
v9k: mdm cts=1 dsr=1 (...)               effective data rate : 632 cps
```

632 cps reproduces §16n's 633 and `rxpeak = 294` reproduces §16t's 294, so
the harness is the same one. **What §16u adds is a reading rule: the two
elapsed figures differ by 15.2 s and neither is wrong.** The Victor's clock
starts on the first byte received — the host's `kermit -ir` string, before
the S packet — and closes at release, so it spans negotiation and teardown;
the host's `statistics` covers the file. Quote them as a pair. `wire=` is
also a **receive-leg** figure: it divides `rxbytes`, so on a send leg it
would divide the ACK stream.

**Everything for the bench run is already on the image and in the tree:**

| | 38400 | 19200 |
|---|---|---|
| Victor `.BAT` | `STEPCA.BAT` → `STEPCA.OUT` | `STEPCB.BAT` → `STEPCB.OUT` |
| host take-file | `s16uCA.ksc` → `s16uCA.pkt` | `s16uCB.ksc` → `s16uCB.pkt` |
| fixture sent | `rcvca.dat` | `rcvcb.dat` |
| Victor writes | `RCVCA.DAT` | `RCVCB.DAT` |

`CKERMITW.EXE` on the image is now the **204,764** build with the clock and
`mdm` (md5 verified after the copy). Run each as
`kermit -C "take s16uCA.ksc, exit" > s16uCA.host` so the `statistics` output
is kept, then pull `STEPCA.OUT` and `RCVCA.DAT` off the image and md5 the
latter against `rcvca.dat`.

**`cts=1` under MAME is not the answer to the cable question** — the
emulator's `null_modem` asserts the inputs. Only the bench reading counts,
and it decides item 3 below.

What the existing counters already bound, from line time plus the dead time
the Victor measures (`txgap` + `wfile`) — these are **ceilings**, since
`txgap` covers only ACK-sent to next-read and §16m put total dead time much
higher:

| leg | wire bytes | line | measured dead | elapsed ≥ | cps ≤ |
|---|---:|---:|---:|---:|---:|
| **Y** 38400 asm | 37,569 | 9.8 s | 2.0 s | 11.8 s | **2,780** |
| Z 38400 C | 45,412 | 11.8 s | 4.5 s | 16.3 s | 2,010 |
| U 19200 C | 37,569 | 19.6 s | 0.5 s | 20.1 s | 1,630 |

§16n projected **~1,630 cps** at 38400 on the grounds that dead time and not
line time bounds this port, and that projection has shaped every throughput
argument here. Leg Y's *ceiling* is 2,780, so it looks pessimistic — but a
ceiling is not a measurement. One run with the two instruments above settles
it.

**§16u loosens that ceiling, in the direction that matters.** Both the
`line` and `measured dead` columns exclude negotiation and teardown, and
§16u measured that exclusion at about **fifteen seconds at 9600** — one
slow-start timeout at `set receive timeout 20`. So `elapsed ≥` understates
elapsed, `cps ≤` is a genuine but weak ceiling, and 2,780 should not be read
as "nearly achievable". Compare the bench run's host `statistics` against
§16n's 1,630, not its `wire=`.

**2. Re-do the ring sizing, because the old argument is void.** `rxpeak` is
**2,621 of 4,096** — the highest ever recorded — with `peaktag = 12`,
upstream after a ring drain, which is packet decoding. §16m established the
peak measures pre-ACK turnaround *during the host's retransmission*; there
are no retransmissions now, so it measures something else: how far decoding
falls behind during a 3,991-byte packet at full rate. The ring is 64% full
at its worst. **Anything that lengthens packets or opens the window has to
start from this number, not from §16k's.**

**3. Flow control, and it comes before windowing.** `tcflow()` is a stub and
the ISR has no water marks.

Nothing needs it *today*, and the reason is worth knowing exactly:
`rxfull = 0` in every run ever recorded, because with a window of one the
host sends a packet and waits for our ACK, so **bytes in flight never exceed
one packet**. Worst case — the foreground drains nothing for a whole packet
— occupancy equals the packet length. The longest packet is **3,991** wire
bytes and the ring is **4,096**.

**That 105-byte gap is the entire safety margin, and it is an accident**:
`DRPSIZ = 4000` happens to sit under `V9K_RXBUFSIZ`. So flow control gates
*two* things, which is why it outranks windowing rather than being a note
inside it — **you cannot raise `DRPSIZ` past about 4,090 either.**

Design, constrained by two things already established:

- **Mechanism is an open question, and RTS/CTS is the front runner.** The
  hardware has it: the 7201 has a CTS input (`V9K_RR0_CTS`), RTS is an
  output §1b already drives in WR5, and `v9k_ser_mdm()` already reports
  both. Dropping RTS is *two port writes* — no TX-ready test, no state
  coupled to the transmitter — where XON/XOFF needs all three, and it is
  binary-transparent. **What is unknown is whether the bench cable carries
  and crosses the pair.** `HW_TESTING.md` §1.2's "three wires are
  sufficient" is a statement about this port's requirements, not a
  description of the cable — the bullet right after it says the port drives
  DTR and RTS. **The exit report now samples CTS during the transfer, so
  the next run answers it**, and the host would need `set flow rts/cts`.
  XON/XOFF is the fallback if the pair is not wired, and is safe because
  Kermit prefixes control characters so 0x11/0x13 never appear bare.
- **This ISR has no `sti`.** 3.13 does flow control inside `SERINT` but only
  after re-enabling interrupts, then polls TX-ready in a `loop` bounded at
  65,536 turns (`msxv90.asm:srint9`). **Do not copy that** — polling with
  interrupts off blocks receive, which is the defect §16t just fixed.
  Single-shot instead: past the high mark and no XOFF outstanding, test
  TX-ready *once* and write XOFF if clear, otherwise skip and retry on the
  next byte. ~5 instructions per byte against the 75 §16t recovered.
- Water marks 3/4 and 1/4, and an `xofsnt` that distinguishes user-level
  from buffer-level, both straight from 3.13 (`MNTRGH`/`MNTRGL`, and it is
  the same chip on this machine).
- The host harness runs `set flow none`; it needs `set flow rts/cts` or
  `set flow xon/xoff` to match whichever mechanism goes in.

**4. Then windows.** `DFWSIZ` is still 1, and items 2 and 3 are both
preconditions. Do it under MAME first. Note the interaction §16s found: with
a window of one the file write happens *before* `ack()`, so the line is idle
through it — which is why a floppy with 1.5-second writes loses nothing.
**Open the window and that stops being true**, and a 1.5 s write at 38400 is
5,760 bytes against a 4,096-byte ring.

**5. Server mode on hardware** (`-g`, `-f`, `-x`, `--safe-server`) —
`HW_TESTING.md` leg 0.7, still untouched.

**6. FreeDOS for Victor** — `HW_TESTING.md` Tier 4, and the IRQ1 vector
question (41h here, INT 09h there) that is the most likely thing to break
the "one binary, two DOSes" claim.

**7. Report the `ckcmai.c` nesting upstream.** Unchanged since §16j.

**8. `REMOTE DIRECTORY`** still streams its listing and never terminates it
(§16i).

---

## 2. The two builds

`ckvisr.asm` is the default. `XFLAGS=-dV9K_CISR` puts the C handler back in
the vector; it stays compiled in both builds as the specification and the
fallback.

**The exit report says which one ran** — `v9k: isr=asm` or `isr=c`. Two
builds selected by a `-d` flag produce otherwise identical-looking `.OUT`
files, and provenance cost this project time twice before that line existed.

Selecting the assembly handler implies `V9K_LEANLOST`, because it does not
maintain the burst table. Without that, the report would print
`b1 at=0 end=0 n=0` from a table nothing writes.

**If you touch `ckvisr.asm`:**

- It reads no header. `V9K_RXMASK` is a literal `0FFFh`, and `ckvictor.c`
  fails the build if `V9K_RXBUFSIZ` stops being 4096.
- It declares `DGROUP GROUP CONST,CONST2,_DATA,_BSS`. `mov ax,DGROUP`
  assembles to the group *base*; declare a subset and the linker could give
  you `_DATA`'s base while the C half uses the real one, which silently
  corrupts every variable the handler touches. **Verify it after linking**:
  read the immediate out of the executable and compare against the map's
  DGROUP paragraph. §16t has the method.
- The 7201 and the 8259 are both addressed through one `ES` at `E000h` —
  control A `42h`, data A `40h`, channel B `43h`/`41h`, 8259 command `0`.
- **It cannot be exercised at 38400 anywhere but the bench.** Validate what
  can be validated first: a 32 KB receive at 9600 under MAME covers the
  vector, the DGROUP base, the port addressing, the ring arithmetic and
  every counter. That is what §16t did before the drive.

---

## 3. Instruments

- **`v9k:` lines on stdout at exit, every build.** `isr=`, then
  `rxlost/rxfull/rxpeak`, `peaktag/fd/stall256`, `rxbytes/peakat/stallat`,
  `norx/othrx/rr0/oth`, `lost evt/max/tag/fd`, `lostat/lostend`, `wfile`,
  `wcon`, `txgap`, `elapsed/wire`, `mdm` — plus a `b<N>` row per burst in a
  `-dV9K_CISR` build without `-dV9K_LEANLOST`. **`wire=` is bytes on the
  wire per second**, retransmissions and headers included; it is not
  C-Kermit's file cps, which is what the take-files' `statistics` prints.
  **In `mdm`, only `cts` and `dsr` are measurements** — `dcd` is forced on
  by the carrier clause under `CLOCAL`, and `rts`/`dtr` are read back from
  the last WR5 written rather than from the pins.
- **A byte at 38400 is 260 µs, at 19200 520 µs, at 9600 1,040 µs.** The tree
  said 26 µs in seven places until §16t; if you ever see that figure again
  it is a relic. Both ends are 8N1 — `tcgetattr` returns a *cached* struct
  with `CSTOPB` clear, so `CONFIG.SYS`'s `stop(1.5)` never survives.
- **The clock quantum is 0.5 s and it is the Victor's.** Read `tot=`, never
  `max=`. Three samples measure nothing.
- **Byte offsets map onto the host packet log**, resends included:
  `python3 .probe/mapoffset.py host.pkt --rxbytes <rxbytes> <offset>...` —
  **always pass `--rxbytes`**, which computes and applies the startup
  dead-air shift. §16r nearly published a wrong answer for want of it.
- **`python3 .probe/pktstat.py host.pkt`** decodes a log; `grep -c '^S-'`
  counts retransmissions and `grep -c '<timeout>'` counts timeouts.
- **`.probe/vburst.c`** replays the burst detector on the host, 17 cases —
  `cc -o .probe/vburst .probe/vburst.c`. Re-run after touching that logic.
- **`.probe/vasm.c`** records what Open Watcom will and will not do for an
  ISR: `__interrupt` always saves twelve registers, and `#pragma aux` cannot
  be used for one at all. Compile it and read `wdis` before believing
  otherwise.
- **`python3 .probe/mzsize.py ckermitw.exe`** — run this, not `ls -l`.
- **`CKERMITW -d -h` is the 2.5-minute oracle** for anything decided before
  or during `sysinit()`.
- **Do NOT combine `-dKEEP_DEBUG` with anything about throughput** — ~25 ms
  per received byte (§16k).
- **There is no `-fstack-usage` under Open Watcom.**

---

## 4. Things that are known-incomplete

- **`SET FILE COLLISION` is `BACKUP`, and BACKUP cannot work on FAT.** Fresh
  filename per run. Symptom: S, F, A, then **Z with data `D`** and no data
  packets.
- **`REMOTE DIRECTORY` never terminates its listing** (§16i).
- **Most of the default capability set is untested** (§16i). `BYE` never sent.
- **Wildcards are case-sensitive.** `-s *.TXT`.
- **No interrupt-level flow control**, `tcflow()` is a stub, and the ring has
  no water marks. Safe today only because the ring (4,096) exceeds the
  longest packet (3,991) at a window of one — a **105-byte margin that is
  an accident of `DRPSIZ`**. It gates longer packets as well as windowing.
  §1 item 3.
- **No stack switch in the handler** — deliberate, and the assembly one is a
  10-byte frame.
- **The IRQ1 vector is hard-coded to 41h.** Right for MS-DOS 3.1; unknown
  for FreeDOS.
- **Ctrl-Break with the line open** is not covered by `atexit()`.
- **WR2 is left as the OEM driver set it** (`10h` vs 3.13's `14h`). Never
  tested, and no longer suspected of anything — it was on the list only
  while 38400 was unexplained.
- **The carrier clause** in `ttgmdm()` forces carrier present under `CLOCAL`.
- **The assembly ISR's overrun branch has never executed.** 38400 is clean
  now, so nothing reaches it. It is transcribed from the C and reviewed in
  `wdis`, and that is all the evidence there is.
- **Elapsed time and cps are captured at 9600 and nowhere else.** §16u did
  it under MAME — 632 cps, `elapsed=6700 cs`, byte-exact. **No rate above
  9600 has ever had either figure recorded**, which is the whole of §1 item
  1 and is bench-only.
- **`cts` has been read once, under MAME, where it means nothing.** The
  emulator asserts it. Whether the bench cable crosses the pair is still
  open and still gates item 3.

---

## 5. Still open, from before

**The parser build** — `XFLAGS=-dKEEP_ICP` plus `.probe/mzsize.py` settles
the DGROUP half in one build; it does not load, and that was measured.

**Why `binmode.obj`'s near init record does not work here** (§16h).

---

## 6. The harness

**Bench.** Pico SASI serving `victor_kermit.img`; channel A; 1 m USB-C to
RS-232; host `set line /dev/tty.usbserial-*` (in `~/.kermrc`), `set speed
<rate>`, `set carrier-watch off`, `set flow none`, `log packets <unique>`.
Power-cycle the Victor *and* the Pico between runs. Fresh target filename
every run. Do not write to the image while the machine is running.

Take-files in the tree drive the host side:
`kermit -C "take s16tY.ksc, exit"`. Each ends in `statistics`, so redirect
that output if you want the host's cps kept:
`kermit -C "take s16tY.ksc, exit" > s16tY.host`.

**MAME.** Still the right place for anything that would cost a drive to get
wrong, and it validated `ckvisr.asm` before the bench.

- `socat` first (single-use `-bitb`), then MAME, then wait ~110 s before
  starting the host `kermit`. `-seconds_to_run 300` for a 32 KB receive.
- **9600 is the emulator's ceiling**, not a setting.
- **Use `-r`, not `-x`**, when the point is a receive measurement.
- **One `kermit` attempt per MAME run, unique log names** — `log packets`
  truncates.
- The host take-file must `set line /tmp/v9000` explicitly, because
  `~/.kermrc` points at the bench adapter.
- `.BAT` files need CRLF; `-autoboot_command` takes the literal `\n`;
  **digits come through shifted under MAME** so use digit-free `.BAT` names
  (`STEPASM`, not `STEP0`); MS-DOS 3.1 cannot redirect handle 2; the disk
  boots as `A:`; use `vtg_image_util`, never mtools.
- Backups: `victor_kermit.img.bak-20260807-clock` is the last one taken,
  immediately before the 204,764 build went on.
- **On the image now:** `CKERMITW.EXE` is the **204,764** build — assembly
  ISR, clock and `mdm`, md5-verified after the copy and proven by §16u's
  9600 receive. Also `CKLEAN.EXE` (204,388, `-dV9K_CISR -dV9K_LEANLOST`,
  **stale — predates the clock**), `STEPCA.BAT`/`STEPCB.BAT` staged for the
  next bench run at 38400/19200, `STEPCM.BAT` at 9600 (§16u),
  `STEPY`/`STEPZ.BAT` at 38400, `STEPASM.BAT` at 9600, plus a long tail of
  older `STEP*` and `RCV*` files. Delete before reusing a name.

---

## 7. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"        # ckermitw.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak sizes"  # DGROUP report
python3 .probe/mzsize.py ckermitw.exe                       # will it LOAD
cc -o .probe/vburst .probe/vburst.c && .probe/vburst        # burst logic
```

Rule 4 still applies: the heap is **outside** DGROUP, the ring is not, and
`V9K_OBUFSIZE` is heap.

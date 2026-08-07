# Next session

Handoff for the Victor 9000 port, written 7 August 2026. **The port has no
known live defect.** 38400 was the last one and §16t closed it: the cause
was the cost of our own interrupt handler, and `ckvisr.asm` — the port's
first assembly — replaced it.

**Read `PORTING.md` §16v first**, then §16t. §16v is the bench run that
finally measured throughput, and it moves the bottleneck: **the line is no
longer it.** §16t is still the best thing in the file for its four wrong
turns.

---

## 0. Where the port is

**File transfer works, both directions, as client and as server, at 9600,
19200 and 38400, on real hardware, byte-exact — and it runs at 1,013 cps at
38400.**

```
v9k: isr=asm
v9k: rxlost=0 rxfull=0 rxpeak=2589 of 4096
v9k: peaktag=12 fd=0 stall256=26
v9k: elapsed=3400 cs wire=1104 B/s
v9k: mdm cts=1 dsr=1 (dcd=1 rts=1 dtr=1, see comment)
```
```
 elapsed time           : 00:00:32 (32.322 sec)
 effective data rate    : 1013 cps
```

18 packets, longest 3,991, zero NAKs, zero retransmissions, zero timeouts.
Before §16t the same leg needed 37 packets and lost 1.8% of received bytes.

**Two things changed with §16v and they set everything below.** The
throughput bound is now the **foreground decode path** — 62% of a 38400
transfer, 564 µs per received byte against a 260 µs byte time, giving a
**no-line ceiling of ~1,353 cps**. And **`cts = 1` on the real cable**, so
RTS/CTS is available and flow control does not have to be XON/XOFF.

Still **eleven** guarded upstream edits. DGROUP 48,272 of 65,536 (73%),
image 204,764, needs 218,988 with 177,236 spare.

---

## 1. Do this next, in priority order

**1. The foreground decode path, because §16v measured it at 62% of a
38400 transfer.** Throughput is measured and the old item 1 is closed:
**1,013 cps at 38400**, byte-exact, zero retransmissions. Where 34.00 s
went:

```
line time (37,568 B at 38400)      9.78 s   29%
disk      (wfile tot = 50 cs)      0.50 s    1%
txgap     (ACK-sent to next-read)  2.50 s    7%
unaccounted                       21.20 s   62%   <- packet decoding
```

`peaktag = 12` names it — upstream, after a ring drain. That is **564 µs
per received byte, ~2,800 cycles on a 5 MHz 8088, against a 260 µs byte
time**: the same shape as §16t's ISR defect one level up, and the reason
`rxpeak` sits at 2,589 without ever overflowing.

**The number that should govern every throughput decision from here is the
no-line ceiling: ~1,353 cps.** Take the wire out entirely and 24.2 s
remain. §16n's ~1,630 projection is above it and is dead; §16t's ≤ 2,780
ceiling was loose by 2.7×. Doubling 19200 → 38400 bought **+24%** measured,
**+17%** after correcting leg CB for its two retransmissions. **Nothing
above 38400 is worth more than 34%**, so rate is finished as a lever.

**The compile flag has been tried and it is not the lever — see §16w
before spending anything here.** `-ot` fits (235,090 of 396,224, DGROUP
48,576) and is **slower**: 632 → 624 cps and `rxpeak` 294 → 333 on
protocol-identical runs. §16t's own model predicts it — an 8088 fetches
through a four-byte queue over an 8-bit bus at ~4 clocks a byte, so **code
size is execution time** and `-ot`'s 9.2% of extra far code is a cost. The
MAME caveat runs in the safe direction for once. `-os` stays, and the
makefile now says why on both grounds.

So there is **no cheap lever left**, since the decode path is upstream
(hard rule 1). Two things to do before anything expensive:

- **Split the 21.2 s.** It is one subtraction — elapsed minus line minus
  `wfile` minus `txgap` — so nothing yet separates per-byte decode from
  per-packet fixed cost, and the two have completely different fixes. A tag
  or counter around the decode call splits it. §16m's rule applies: the
  interrupt handler is a clock you can afford, the foreground is not, so
  instrument at packet granularity and not per byte.
- **Run a text fixture, because every measurement this port has is on
  adversarial data.** The 32,768-byte fixture holds every byte value, so
  Kermit's control and high-bit prefixing expands it to **37,568 wire
  bytes, 14.7%** — and decode cost is per *wire* byte. Plain ASCII should
  present materially fewer. That is an inference from the packet logs
  bounding it at ~15%, **not a measurement**, and one run settles it. It
  also means **1,013 cps is a worst-case-ish figure**, which is the right
  one to quote but not the whole picture.

**2. Re-do the ring sizing, and §16v gives it a model rather than a
number.** The peak is `rxpeak = 2,589 of 4,096` at 38400 (§16t's 2,621 on
the same leg; two samples, same place). `peaktag = 12` is packet decoding,
and §16v says why: the foreground runs at 564 µs a byte against a 260 µs
byte time, so during a packet it falls behind at about **0.54 bytes per
byte received** and catches up in the silence after. That predicts

```
rxpeak ~= 0.54 x packet length      3,991 x 0.54 = 2,155, measured 2,589
```

which is the right shape and about 20% low, so treat 0.54 as a floor. The
useful consequence is that **the peak now scales with packet length**, which
§16k's argument could not say. It is a model to test, not a result: one run
at `XFLAGS=-dDRPSIZ=2000` would confirm or kill it cheaply, and the rule
still stands that no packet-length change ships without a run that reaches
FINISH and reports `rxlost`/`rxfull`/`rxpeak`.

Note this bounds *observed* occupancy, not the safe bound — item 3's worst
case is still "the foreground drains nothing", which is the packet length.

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

- **Build both. RTS/CTS is the default; XON/XOFF is an interoperability
  requirement, not a fallback.** §16v read **`cts = 1` on the real cable**
  in both legs, with the host running `set flow none` and therefore holding
  RTS asserted throughout — the strong-evidence case, and a genuine read
  since the only forced bit in `v9k_ser_mdm()` is `dcd` under `CLOCAL`. So
  RTS/CTS is available *here*, and it is also the cheaper path: dropping RTS
  is two port writes, no TX-ready test, no state coupled to the transmitter,
  binary-transparent. **But the far end's wiring is not something this port
  can measure or assume**, and a Victor Kermit that only talks to equipment
  with a crossed RTS/CTS pair fails against a lot of what it would actually
  meet. The bench settles the default, not the feature set.
- **Neither mechanism needs an upstream edit — the plumbing is already
  there.** `ckutio.c` translates C-Kermit's `flow` into exactly the termios
  bits our `tcsetattr()` receives: `FLO_XONX` → `c_iflag |= (IXON|IXOFF)`
  (`ckutio.c:6617`), `FLO_RTSC` → `c_cflag |= CRTSCTS` (`ckutio.c:6252`).
  `victor/sys/termios.h` defines all three and already states the split —
  `tcflow()` is the XON/XOFF half, RTS/CTS is the driver's job under
  `CRTSCTS`. **So implement against the termios bits, not against a private
  flag.**
- **Selection is the one open piece, because `NOICP` removes `SET FLOW`.**
  `dfflow` is `FLO_NONE` at `ckutio.c:1202`. §16i's priority-0 XI
  initializer, plus a switch blanked off the DOS command tail before `argv`
  exists, is the pattern that has solved this exact shape twice already
  (server capabilities, `--safe-server`) and cost no upstream edit either
  time. Run the unknown-option control, per §16i.
- **This ISR has no `sti`, and that constraint now bites, because XON/XOFF
  is in scope rather than a fallback.** 3.13 does flow control inside
  `SERINT` but only after re-enabling interrupts, then polls TX-ready in a
  `loop` bounded at 65,536 turns (`msxv90.asm:srint9`). **Do not copy
  that** — polling with interrupts off blocks receive, which is the defect
  §16t fixed and §16v shows we have no headroom to reintroduce. Single-shot
  instead: past the high mark and no XOFF outstanding, test TX-ready *once*
  and write XOFF if clear, otherwise skip and retry on the next byte. ~5
  instructions per byte against the 75 §16t recovered. **RTS/CTS needs none
  of this**, which is the other half of why it is the default.
- Water marks 3/4 and 1/4, and an `xofsnt` that distinguishes user-level
  from buffer-level, both straight from 3.13 (`MNTRGH`/`MNTRGL`, and it is
  the same chip on this machine).
- The host harness runs `set flow none`, from `~/.kermrc`, and needs `set
  flow rts/cts` or `set flow xon/xoff` to match whichever is under test.
  **Note that `set flow none` is what makes §16v's `cts` reading evidence**
  — the host holds RTS asserted only because it is not using it — so a run
  that changes it is no longer a control for that.

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
- **The Victor sent a NAK, once, and it is not explained.** §16v leg CB,
  19200, `s16uCB.pkt:20` — the first in this project's history, against
  §16l's "only ACKs, never a NAK". `rxlost = 0`, so **not** a chip overrun;
  checksum failure versus our own receive timer is not separable from that
  log. Leg CA at the higher rate was perfectly clean, so it is not a rate
  effect. One occurrence, no instrument pointed at it.
- **The 21.2 s of foreground time is one bucket.** §16v measures it by
  subtraction — elapsed minus line minus `wfile` minus `txgap` — so it is
  a total, not a decomposition, and nothing yet separates per-byte decode
  from per-packet fixed cost. §1 item 1.
- **`wire=` is a receive-leg figure.** It divides `rxbytes`, so on a send
  leg it reports the ACK stream over the whole elapsed time. No send leg has
  ever been timed.
- **cps above 38400 is unmeasured and probably uninteresting** — §16v's
  no-line ceiling of ~1,353 cps caps the payoff at 34%.

---

## 5. Still open, from before

**The parser build** — `XFLAGS=-dKEEP_ICP` plus `.probe/mzsize.py` settles
the DGROUP half in one build; it does not load, and that was measured.

**Why `binmode.obj`'s near init record does not work here** (§16h).

---

## 6. The harness

**Bench.** Pico SASI serving `victor_kermit.img`; channel A; 1 m USB-C to
RS-232. Power-cycle the Victor *and* the Pico between runs. Fresh target
filename every run. Do not write to the image while the machine is running.

**`~/.kermrc` already sets up the bench, so a take-file only needs what
differs.** It carries `set line /dev/tty.usbserial-BG022B8M`, `set speed`,
`set parity none`, `set carrier-watch off` and `set flow none`. A take-file
therefore needs the speed for the leg, the log name, the transfer and
`statistics`:

```
set speed 38400
set receive timeout 20
log packets s16uCA.pkt
send rcvca.dat
statistics
```

Redirect to keep the host's cps: `kermit -C "take s16uCA.ksc, exit" >
s16uCA.host`. `s16uCA.ksc` and `s16uCB.ksc` in the tree are the files that
ran §16v; they additionally repeat `set line` and `set parity none`, which
is harmless and was not necessary. **An earlier version of this section
claimed those lines were required and built a rule on it. They were not,
and there is no rule** — see the retraction at the end of §16v, which is
about how the error was made rather than about take-files.

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
  ISR, clock and `mdm`, md5-verified after the copy and proven on hardware
  by §16v at both 38400 and 19200. Also `CKLEAN.EXE` (204,388,
  `-dV9K_CISR -dV9K_LEANLOST`, **stale — predates the clock**),
  `STEPCA.BAT`/`STEPCB.BAT` at 38400/19200 (§16v, and their `.OUT` and
  `RCVCA/RCVCB.DAT` are still there — delete before reusing),
  `STEPCM.BAT` at 9600 (§16u),
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

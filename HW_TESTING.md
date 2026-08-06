# CKERMITW on a real Victor 9000 — test plan

Written 6 August 2026, before any of it had been run. Every measurement in
`PORTING.md` §16–§16n is MAME, on Victor MS-DOS 3.1, at 9600 bps.

> **First hardware runs, 6 August 2026 — it works, at 9600, 19200 and
> 38400.** Files sent from the Victor and received back, repeatedly, at all
> three rates, **md5-identical and `diff`-clean after the round trip**. The
> `v9k:` counters were captured for one 19,808-byte round trip at 19200:
> `rxlost=0 rxfull=0` both directions, `rxpeak=56 of 4096` — one sixth of
> what MAME showed at *half* the line rate.
>
> **38400 retires the two risks Tier 2 was built around**: the OEM driver
> accepts `msxv90.asm`'s undocumented divisor, and the µPD7201
> interrupt-acknowledge sequence holds at a ~260 µs byte interval.
>
> **What is not yet captured is the counter set at 38400**, and the
> session's packet log turned that from a formality into the open question.
> All three Victor → host transfers were clean; in the other direction **the
> Victor NAKed three packets in one transfer**, at a rate the log does not
> record. A NAK is a failed checksum at the Victor — corrupted data on the
> receive path. Every file still arrived md5-identical because that is what
> resends are for, which is precisely why **byte-exact is not the same claim
> as clean**. Rates are proven; cleanliness is not. The disk questions in
> Tier 3 are also still open.

This file is the bench plan. It is modelled on
`~/projects/myfreedos/docs/victor/HW_VALIDATION_PLAN.md`, which is the same
author's plan for the same machine and has already survived a hardware
debugging week — its discipline section in particular is hard-won and is
copied here rather than re-derived.

**Status legend:** ☐ not started · ◐ in progress · ☑ pass · ✗ fail (link the
serial log and the `v9k:` lines)

---

## Why this is worth a session

Four open questions in this port can now be answered *only* here, because
§16n established that **MAME cannot run this machine above about 9600** —
not as a setting, but because the emulation cannot meet the serial timing
thresholds while the host on the other end of the socket runs at a real line
rate:

1. **19200 and 38400.** Never attempted at any level of the stack above the
   FreeDOS debug console's polled TX.
2. **The µPD7201 interrupt-acknowledge sequence.** `ckvictor.c` §1e issues
   `WR0 = 38h` then a specific EOI, which is what `msxv90.asm` does and what
   works under emulation. MAME's µPD7201 is not the part. This is the item
   that stalled the FreeDOS IRQ-driven receive (`irq_enabled = 0` to this
   day) and it gates 38400.
3. **The true cost of a disk write.** §16n fitted 0.124 s fixed per
   `write()` plus ~15 µs/byte and flagged it as "very slow for a real
   drive" — probably MAME's number, not the Victor's. `V9K_OBUFSIZE` at
   8,192 was sized from it.
4. **The clock quantum.** §16n found every timing figure this port has ever
   printed to be a multiple of 50 hundredths and concluded this machine's
   DOS clock advances by half a second. That may equally be an emulation
   artifact. It re-scales how every timing figure in §16m–§16n should be
   read.

Two more that are not about speed:

5. **Does the whole thing work at all off the emulator** — the ISR, the
   ring, the OEM IOCTL block, the DOS file layer.
6. **Which interrupt vector IRQ1 arrives on under FreeDOS for Victor**
   (Tier 4). This is the most likely thing to break the "one binary, two
   DOSes" claim, and it is one constant.

**Outcome of the first session, against that list.** 1 is answered — all
three rates run. 2 is answered at the level that matters most (38400 moves
data correctly) but not at the level of `rxlost`, which is the difference
between the sequence being right and being survivable. 4 is answered and the
answer is that the half-second quantum is the **Victor's**, not the
emulator's. 5 is answered outright. **3 is not**, and it is the one that
looks answered — see Tier 3.2. 6 is untouched.

---

## 0. Methodology — read before every session

- **Power-cycle the Victor *and* the Pico/SASI controller between runs.**
  From the FreeDOS bench notes: a prior SASI reset cascade leaves the
  controller wedged and the next boot loads a corrupt image. That is not a
  build defect and it will waste an hour if it is read as one.
- **MAME-check every build before taking it to the bench.** `CKERMITW -d -h`
  is a 2.5-minute boot with no serial line and no host, and it witnesses
  anything decided before or during `sysinit()`. A full 9600 receive under
  MAME is ~5 minutes and proves the build is not broken in a way the bench
  should be spending time on.
- **One variable per run.** §16n's comparison was tight precisely because
  the wire byte count came out identical; the sessions that went wrong in
  §16j and §16m went wrong by changing two things.
- **Fresh target filename every run.** `SET FILE COLLISION` is `BACKUP`,
  `znewn()` builds `NAME.DAT.~1~`, and that is not a legal 8.3 name, so a
  receive onto an existing name is refused. Symptom: S, F, A, then **Z with
  data `D` and no data packets at all**. Delete leftovers.
- **Capture the six `v9k:` lines for every run**, and the host packet log,
  and date both. `log packets` truncates, so a unique log name per attempt.
- **Quote `tot=`, never `max=`** (§16n) — until Tier 3.1 says otherwise on
  this hardware, no individual event has ever been timed.
- **Never combine `-d` with anything about throughput.** The debug log costs
  ~25 ms per received byte (§16k) and starves the receive ring on its own.
  It is for logic, not for time.
- **Record pass/fail per leg in the tables below** so a flaky result can be
  told from a regression.

---

## 1. Bench setup

### 1.1 The machine and the image

Boot **Victor MS-DOS 3.1**, not FreeDOS, for Tiers 0–3. The reason is not
preference: MS-DOS 3.1 is where every MAME measurement was taken, so it is
the only configuration in which a bench result can be compared against
anything. FreeDOS is Tier 4, deliberately last, and has its own open
question.

The image is `~/projects/mame/victor_kermit.img` — 30 MB, SASI, **boots as
`A:`**, no MBR and no BPB, so mtools cannot read it. Take a dated copy to
the bench and serve it from the Pico SASI emulator.

> **Assumption to confirm on the first session:** that the Pico serves this
> image as-is. The FreeDOS bench work drives the Pico with its own images;
> if the geometry or the container differs, this is where it shows up, and
> it is a media problem rather than a Kermit one.

What must be on the image, and all of it already is:

| | |
|---|---|
| `CKERMITW.EXE` | 203,338 bytes, needs 217,594 of the 396,224 the machine offers |
| `CONFIG.SYS` | loads `porta.exe`, which is what makes `\dev\seriala` exist |
| `STEPH`–`STEPM.BAT` | the run scripts — `-r`, no `-d`, stdout redirected |
| `RCVF`–`RCVK.DAT` | receive fixtures; §16h–§16m leftovers are also there |

Image manipulation, host side, **never while the machine is running**:

```sh
vtg_image_util list ~/projects/mame/victor_kermit.img
vtg_image_util copy ckermitw.exe ~/projects/mame/victor_kermit.img:0:\\CKERMITW.EXE
vtg_image_util copy ~/projects/mame/victor_kermit.img:0:\\RUN1.LOG ./run1.log
```

`.BAT` files need **CRLF** line endings, and MS-DOS 3.1 **cannot redirect
handle 2** — stdout only.

### 1.2 The wire

**Channel A, and the physical layer is the one part of this that is already
proven on this hardware.** `PORTING.md` §10's "38400 bps transmit on µPD7201
channel A" is the FreeDOS boot debug console — same chip, same channel, same
connector, same 1488/1489 line drivers, at the rate MAME cannot reach. The
cable used for FreeDOS serial debugging is the cable this needs.

- Both ends are DTE, so a **null modem / crossover** is required.
- **Three wires are sufficient** (TX, RX, GND). There is no interrupt-level
  flow control in this port — `tcflow()` is a stub — and none is negotiated.
- The port drives **DTR and RTS** through the OEM IOCTL block (§11a) and
  drops them across `tthang()`. Nothing depends on the far end's answer:
  the carrier clause in `ttgmdm()` forces carrier present under `CLOCAL`.
- Host side: USB-serial adapter. Note its device name
  (`/dev/tty.usbserial-*` on macOS) — it replaces `/tmp/v9000` and is the
  **only** change the host half of the harness needs.

> **Assumption to confirm:** that channel A is free. It is the FreeDOS debug
> console's channel, and under MS-DOS 3.1 nothing else wants it — but if the
> bench habitually watches boot output on that line, the two uses collide.

### 1.3 The host side

Unchanged from §16k–§16n except for one word. C-Kermit 9.0.302:

```
set line /dev/tty.usbserial-XXXX     ; was /tmp/v9000
set speed 9600                       ; must match the Victor's -b
set carrier-watch off
set flow none
set receive timeout 20               ; §16l; see the caveat in §16m
log packets run1.pkt
receive
```

`set carrier-watch off` and `set flow none` matter *more* here than under
MAME: the pty presented no handshake lines at all, and a real adapter
presents real ones.

### 1.4 What differs from MAME, in full

| | MAME | Bench |
|---|---|---|
| boot media | `-hard1 victor_kermit.img` | Pico SASI, same image |
| the wire | `null_modem -bitb socket` → `socat` → pty | DB25 → null modem → USB-serial |
| starting a run | `-autoboot_command "\n\nSTEPM\n"` | type it; the real keyboard does not mangle digits |
| ending a run | `-seconds_to_run` expires, MAME exits | watch the screen |
| free speed check | 302 s wall for 300 s emulated | n/a — the machine *is* the clock |
| everything else | | identical |

The last row is the point of this table. Same binary, same `.BAT` files,
same `/dev/seriala`, same fixtures, same host script, same instruments:
`.probe/pktstat.py`, `.probe/mapoffset.py`, `grep -c '^S-'` for
retransmissions and `grep -c '<timeout>'` for timeouts.

---

## 2. Getting results off the machine

The six `v9k:` lines print to **stdout at exit in every build** — that was
done in §16k precisely because a run fast enough to measure is a run that
cannot carry a debug log. Three ways to capture them, cheapest first:

1. **Read them off the screen.** Six lines, and they are the whole
   instrument for Tiers 0–3. Photograph them.
2. **Redirect and `TYPE`.** `STEPM.BAT` already redirects stdout; `TYPE
   RUN1.LOG` puts it back on screen after the transfer.
3. **Ship the log back with Kermit itself** — `CKERMITW -l /dev/seriala -b
   9600 -s RUN1.LOG`. This is the one that scales, because it needs no power
   cycle and no SD card, and it exercises the send direction as a
   side effect.

The lines, and what each is for:

```
v9k: rxlost=  rxfull=  rxpeak=  of         chip overrun / ring overflow / high-water
v9k: peaktag= fd= stall256=                where the foreground was at the peak (§0e)
v9k: rxbytes= peakat= stallat=             byte offsets — map onto the host packet log
v9k: wfile n= max= at #  of   tot=         file writes: count and total centiseconds
v9k: wcon  n= max= tot=                    console writes
v9k: txgap n= max= at #  tot=              transmit gaps
```

`python3 .probe/mapoffset.py run1.pkt <offset>...` turns `peakat`/`stallat`
into "which packet, and was it a resend".

---

## 3. Tier 0 — does it work at all, at 9600

**Everything below this tier is meaningless until this passes**, and it is
the first time any of it has run on real silicon. Same rate, same fixture,
same commands as §16n. A failure here is a hardware-vs-emulator difference
in the ISR, the IOCTL block or the DOS file layer, and it is worth more than
any speed number.

**Run at 19200, not 9600** (see the banner). The rate is noted per leg.

| # | Test | How | Pass criteria | Status |
|---|---|---|---|---|
| 0.1 | It loads | `CKERMITW -d -h`, no line, no host | Prints version and exits; `uname` witness lines correct | ☑ implied — it loaded and transferred; the `-d -h` oracle itself was not run |
| 0.2 | The line configures | `PORTSET A 9600 NONE 1 8`, then any run | No "can't open device"; §11a status check clean | ☑ at 19200 — `Closing /dev/seriala...OK` |
| 0.3 | Send, one file | `CKERMITW -l /dev/seriala -b <rate> -s <file>` | Host receives it; `cmp` byte-exact | ☑ 19,808 bytes at 19200, md5 match |
| 0.4 | Receive, 32 KB | `STEPM.BAT`, fresh name, host `send` | Byte-exact; `rxlost=0 rxfull=0` | ☑ **at 19,808 bytes, not 32 KB** — byte-exact, `rxlost=0 rxfull=0` |
| 0.5 | The counters | read the six lines from 0.4 | `rxpeak` well under 4,096; note `peaktag` | ☑ `rxpeak=56 of 4096`, `peaktag=0`, `stall256=0` |
| 0.6 | Retransmissions | `grep -c '^S-' run1.pkt`, `grep -c '<timeout>'` | Comparable to §16m's 1–4 per 32 KB | ☑ log kept — 13 resends / ~35 timeouts session-wide, but **7 resends and most timeouts are dead air** between runs. In-transfer: 6 resends over nine transactions, and **3 NAKs from the Victor**. No rate recorded per segment |
| 0.7 | GET / server | `-g`, then `-f`, then `-x` (§16i) | As §16i: negotiate, transfer, FINISH | ☐ |

**0.4 was the milestone and it passed.** The port works on the machine it
was written for — the sentence `PORTING.md` §10 had been unable to write for
the whole project. Two qualifications kept deliberately: the fixture was
19,808 bytes of markdown rather than the 32,768-byte all-byte-values fixture
every MAME measurement used, so **the numbers are not directly comparable to
§16k–§16n and every byte value has not been round-tripped on hardware**.

---

## 4. Tier 1 — 19200

One character changes: `-b 19200` on the Victor, `set speed 19200` on the
host. `PORTSET` can stay at 9600 — it only has to make the device exist;
the actual rate is programmed by `tcsetattr()` through the IOCTL block from
`-b`. Divisor 4, true rate 19531.25 (+1.7%, inside async tolerance, and the
error `msxv90.asm` shipped).

This is the gentler half of the interrupt-acknowledge question: the byte
interval halves to ~520 µs but the protocol shape does not change.

| # | Test | How | Pass criteria | Status |
|---|---|---|---|---|
| 1.1 | Line programs | any run at `-b 19200` | IOCTL status clean; bytes flow | ☑ |
| 1.2 | Receive 32 KB | as 0.4 | Byte-exact, `rxlost=0 rxfull=0` | ☑ at 19,808 bytes; `rxbytes=20431`, `wfile n=3 of 8192` |
| 1.3 | Send 32 KB | as 0.3, large file | Byte-exact at the host | ☑ at 19,808 bytes; `rxbytes=184` of returning ACKs |
| 1.4 | cps | from 1.2 | Compare against the dead-time model (§6) | ☐ elapsed not recorded |

**What 1.2 settles beyond "it works".** `rxlost=0` at a ~520 µs byte
interval says the µPD7201 is not overrunning, i.e. **the ISR is being
re-entered correctly on the real part** — `WR0 = 38h` then the 8259's
specific EOI. That is `PORTING.md` §10's leading "written but never run"
item, and the one that left FreeDOS-for-Victor's IRQ-driven receive disabled.
It is evidence at 19200 and not yet an answer at 38400.

**And `rxpeak` collapsed.** 309–513 under MAME at 9600; **56 here at
19200**, with `peakat=116` (inside the S/F negotiation) and `stall256=0`
(the ring never crossed 256 afterwards). §16m established the peak measures
our pre-ACK turnaround while the host resends, so a peak this small means
**that transfer had no retransmissions**.

**Do not generalise it, and 0.6 is why.** The packet log shows the
instrumented run was one of the clean ones, and a different host → Victor
transfer in the same session drew **3 NAKs from the Victor**. `rxpeak = 56`
describes a good run, not the driver.

---

## 5. Tier 2 — 38400

**Two independent risks stack here and they are separable.** Do not read a
failure as one thing.

**Risk A — the OEM driver may refuse the speed.** §11a: the driver's
Appendix A stops at 19.2k. `B38400` and `B76800` are `msxv90.asm`'s, 3.13
shipped 38400, and nothing in the appendix says the driver validates the
divisor. This is exactly the case the §11a status check was added for — a
rejected speed would otherwise come back carry-clear and be
indistinguishable from success. **If the status check fires, the fix is to
program the 8253 divisor directly rather than through the IOCTL block**, and
that is a change to `ckvictor.c` §1b only.

**Risk B — the interrupt-acknowledge sequence.** Divisor 2, a byte every
~260 µs, a three-deep receive FIFO. `rxlost` and `rxfull` distinguish the
two failure modes and that distinction is the whole reason both counters
exist: **`rxlost` non-zero is the chip** (overrun, i.e. the ISR is not being
re-entered — the acknowledge sequence), **`rxfull` non-zero is the ring**
(the foreground is not draining fast enough — a buffer or throughput
problem). They are not the same defect and they have different fixes.

| # | Test | How | Pass criteria | Status |
|---|---|---|---|---|
| 2.1 | Line programs at 38400 | `-b 38400`, IOCTL status | Accepted, or a clean rejection (Risk A) | ☑ **accepted** — Risk A is dead |
| 2.2 | Short send | `-s` a small file | Any bytes at all at the right rate | ☑ |
| 2.3 | Receive 32 KB | as 0.4 | Byte-exact; **read `rxlost` vs `rxfull`** | ◐ byte-exact, repeatedly — **but the counters were not captured** |
| 2.4 | Sustained send 32 KB | as 1.3 | Byte-exact — the TX half is polled and proven | ☑ |
| 2.5 | cps | from 2.3 | §16n predicts ~1,630, not ~2,400 | ☐ elapsed not recorded |

2.4 was expected to be the easy half and was: polled TX on channel A at
38400 was the one thing on this list already proven on this hardware, by the
FreeDOS debug console.

**2.3 is the one leg to go back for.** Byte-exactness is the protocol
working, not the driver being clean: a µPD7201 overrun corrupts a packet,
the checksum catches it, the host resends, and the file still arrives
perfect. `rxlost` is the only thing that tells those apart, and it is the
number that says whether the interrupt-acknowledge sequence is *right* at
38400 or merely *survivable*. `rxfull` likewise separates "the ring is fine"
from "the foreground is only just keeping up". One run, six lines.

---

## 6. Tier 3 — the numbers MAME could only estimate

These cost nothing extra: they are read out of runs done for other reasons.
Each closes a caveat currently standing in `PORTING.md`.

| # | Question | Read from | What it settles | Status |
|---|---|---|---|---|
| 3.1 | Clock quantum | every timing figure in any run | If figures are no longer all multiples of 50, the 0.5 s quantum was MAME's and §16m/§16n's timings can be read finer | ☑ **the quantum is the Victor's.** Every figure in both runs — 50, 50, 100, 0 — is a multiple of 50. §16n's inference survives to hardware; `tot=` not `max=` still stands |
| 3.2 | Disk cost per write | `wfile n= tot=` at 0.4 | Whether 0.124 s/call is the Victor or the emulator | ☐ **not measured.** `n=3 tot=50` is *one* boundary crossing; it implies ~0.17 s/write but from a single crossing the variance swamps the estimate. Indistinguishable from MAME's 0.124 |
| 3.3 | Disk cost per byte | rerun 0.4 with `XFLAGS=-dV9K_OBUFSIZE=1024` | Confirms per-call on real media; says whether 8,192 is right-sized or over-provisioned | ☐ |
| 3.4 | Dead time per 32 KB | elapsed minus line time, at 0.4 and 2.3 | §16n's 9.8 s, and whether the ~1,630 cps projection holds | ☐ elapsed not recorded |
| 3.5 | `rxpeak` behaviour | 0.4, 1.2, 2.3 | §16m says the peak is our pre-ACK turnaround during the host's resend; it should scale with turnaround, not with rate | ☑ measured at 19200: **56**, against 309–513 under MAME at 9600 |

3.2 is the trap in this tier and the first hardware session fell into it:
**three samples cannot measure anything against a half-second clock.** The
buffer is confirmed live — `of 8192` is the buffer printing its own size,
and 19,808 bytes took the 3 writes that implies — but the *cost* needs 3.3,
which turns 4 writes into 32 and is the only way to know whether
`V9K_OBUFSIZE = 8192` was sized against a real disk or an emulated one.

---

## 7. Tier 4 — FreeDOS for Victor, the second DOS

Last, and separately, because it introduces a variable that has nothing to
do with the four questions above. The claim under test is the one this whole
port is built around: **one binary, two operating systems.**

| # | Test | How | Pass criteria | Status |
|---|---|---|---|---|
| 4.1 | It loads | boot FreeDOS-for-Victor, run `CKERMITW -d -h` | Loads and relocates; ~429K parser build is *not* what is being run | ☐ |
| 4.2 | OEM byte | same run | INT 21h `AH=30h` → BH really is `0xFD` | ☐ |
| 4.3 | Is there a `\dev\seriala`? | `PORTSET`/`porta.exe` equivalent | The IOCTL block is an OEM-driver facility; if FreeDOS has none, §11a has nothing to talk to | ☐ |
| 4.4 | IRQ1 vector | a transfer | 41h is right for MS-DOS 3.1; FreeDOS remaps the 8259 and puts its serial ISR at INT 09h | ☐ |
| 4.5 | Transfer | 0.4 at 9600 | Byte-exact | ☐ |

4.3 and 4.4 are the two that can require code. Neither is a surprise —
both are written down as open questions in `PORTING.md` — and 4.4 in
particular is *one constant*, so the shape of the fix is known even though
the value is not.

---

## 8. Failure triage

Symptom → what it most likely means, so a bench session does not spend an
hour re-deriving something already measured under emulation.

| Symptom | Likely cause | Where it is written up |
|---|---|---|
| "Permission denied / can't open device" | device name given as `\dev\seriala`; must be `/dev/seriala`, forward slashes, leading `/` | §16a |
| S, F, A, then **Z with data `D`** and no data packets | target filename already exists; `FILE COLLISION` is BACKUP and cannot work on FAT | §16j |
| First two bytes of each inbound packet, then silence | the OEM driver is in the data path — it should not be; ours takes IRQ1 and the chip | §16b |
| `rxlost` > 0 | µPD7201 receive overrun — the ISR is not being re-entered. Interrupt-acknowledge sequence. | §10, Tier 2 Risk B |
| `rxfull` > 0 | ring overflow — the foreground is not draining. Buffer/throughput, not the chip. | §16k |
| "No files for `-s`" | **not a diagnosis** — `ckuusy.c` prints it when it could not allocate 2,000 bytes for the real message. Check heap headroom. | §16f |
| `-s *.txt` matches nothing | wildcards are case-sensitive against upper-case FAT names. `*.TXT`. | §16i |
| Machine dies after Ctrl-Break | IRQ1 vector restored from `atexit()`, which a bare DOS termination bypasses; the vector then points into freed memory. Power cycle. | §10 open items |
| `REMOTE DIRECTORY` never ends | known, undiagnosed; `--safe-server` refuses it cleanly | §16i |
| Timeouts in the host log | historically the **host's**, not ours — the Victor has never sent a NAK across a 32 KB receive | §16l |

---

## 9. Suggested session ordering

1. **Session A — media and first light.** Get the image booting off the Pico
   and the cable proven, then Tier 0.1–0.4. Stop when a 32 KB receive is
   byte-exact. That single result is the largest gap in this project.
2. **Session B — 9600 completeness.** Tier 0.5–0.7 plus Tier 3.1–3.3. Cheap,
   and it closes three standing caveats in `PORTING.md` without a new rate.
3. **Session C — 19200.** Tier 1 whole.
4. **Session D — 38400.** Tier 2, with Risk A checked before Risk B is
   blamed for anything.
5. **Session E — FreeDOS.** Tier 4.

Each session: power-cycle discipline, MAME pre-check, archive the packet log
and the six `v9k:` lines, fill in the tables above, and write the result into
`PORTING.md` as a numbered section the way §16d–§16n were.

---

## 10. What is deliberately not on this list

- **Windows (`DFWSIZ` > 1).** It is the next throughput increment and it is
  the one that removes the "only one packet in flight" property that the
  missing interrupt-level flow control currently relies on. Do it under MAME
  first, where a lost byte costs a rerun rather than a drive.
- **The `KEEP_ICP` parser build.** It does not load — 429K against 387K
  available — and that was settled by measurement, not by emulation.
- **`-d` for anything timed.** ~25 ms per received byte.
- **Anything requiring a second variable changed at once.**

---

## 11. Assumptions in this document

Stated separately, per the working style, because none of them has been
confirmed:

1. The Pico SASI emulator can serve `victor_kermit.img` unchanged.
2. Channel A is free on the bench and the FreeDOS debug-console cable
   reaches it.
3. The bench machine is the 896 KB configuration MAME was run at — the load
   figures (217,594 of 396,224) assume it.
4. A USB-serial adapter on the host will run 38400 cleanly with three wires
   and no flow control. It should; the FreeDOS debug console does exactly
   this in the other direction.

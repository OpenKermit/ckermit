# Next session

Handoff for the Victor 9000 port, written 6 August 2026. **It runs on real
hardware, and 38400 loses bytes.** Two bench sessions: §16o got it working
at all three rates, §16p measured the counters per rate and found the
µPD7201 overrunning on 0.45% of received bytes at 38400 and only there. No
code changed in either.

**Read `PORTING.md` §16p first, then §16o.** `HW_TESTING.md` is the bench
plan both sessions ran against, with per-leg status filled in.

---

## 0. The one live defect

`rxlost` = **0** at 9600, **0** at 19200, **203** and **207** at 38400, over
four 32 KB receives that were all byte-exact. Kermit resends what fails a
checksum, so the cost is throughput and not data.

**Ruled out already — do not re-test these.** The file writes (run 4 did 8×
as many for the same loss rate), the receive ring (`rxfull = 0`, `rxpeak` ≤
2,098 of 4,096), and every `V9K_CLI()` in `ckvictor.c` (all setup/teardown;
`v9k_ser_put()` and the ring drain leave interrupts enabled).

**Build this instrument first:** a foreground tag latched at the **first
loss**, and a count of loss *events* separate from lost *bytes*. 203 bytes
in 4 bursts and 203 in 203 are different defects and the current counters
cannot tell them apart. The handler already runs per received byte and §16m
established that a store there costs nothing.

Correlation to carry in, not a cause: `txgap` total scales with the failure
— 50 → 150 → 400 → 450 hundredths across the four runs.

---

## 1. What happened this session

**No code changed.** The binary is §16n's: 203,338 bytes, DGROUP 48,240 of
65,536, eleven guarded upstream edits. This session is measurement only.

### The configuration

| | |
|---|---|
| machine | Victor 9000, 896 KB, **Victor MS-DOS 3.1** |
| boot | Pico SASI emulator serving `victor_kermit.img` — **the MAME image, unmodified** |
| serial | µPD7201 channel A, `/dev/seriala`, OEM `porta.exe` |
| cable | 1 m USB-C to RS-232, to an Apple M4 Mac running C-Kermit |
| runs | 9600 ×2, 19200 ×2, 38400 ×2, all successful |

The Pico serving the MAME image as-is is the reason this was cheap: the
image, the `.BAT` files, the fixtures and the host script all move between
emulator and bench unchanged, and the serial device name is the only
difference. `HW_TESTING.md` §1.4 predicted three differences; there were
three.

### What the counters said

One instrumented pair, a 19,808-byte file at 19200, one transfer each way.

- **`rxlost=0 rxfull=0`, both directions.** At a ~520 µs byte interval with
  a three-deep receive FIFO, that says the ISR is re-entered promptly enough
  never to overrun — **the `WR0 = 38h` + specific-EOI acknowledge sequence
  is right on the real µPD7201**. That is §10's leading unproven item since
  §11b, and the same question that left `~/projects/myfreedos`'s IRQ-driven
  receive shipping with `irq_enabled = 0`.
- **`rxpeak = 56 of 4096`**, against 309–513 under MAME at *half* the rate,
  with `peakat=116` (inside the S/F negotiation) and `stall256=0`. §16m
  established the peak measures our pre-ACK turnaround while the host
  resends, so a peak this small means **that transfer had no
  retransmissions**. The packet log confirms it — and confirms the
  instrumented run was one of the clean ones. **Do not read it as a property
  of the port.**

### The packet log, and the finding that outranks everything above

`run1.pkt` was sitting untracked in the tree — the whole session, one host
`kermit` invocation, twelve segments. Session totals of 13 resends and ~35
timeouts are mostly **dead air** while the operator typed at the Victor with
the host still in `receive`; in-transfer it is 6 resends over nine
transactions. But:

- **All three Victor → host transfers were clean.** Zero resends, zero NAKs.
- **One host → Victor transfer drew 3 NAKs *from the Victor*.** A NAK is a
  failed checksum at the Victor: corrupted data on our receive path. §16l's
  "the Victor sends only ACKs, never a NAK" was the **emulator's** property,
  and §16o retracts it for hardware.
- **The rate is not recorded per segment**, so the NAKs cannot be attributed
  to 9600, 19200 or 38400. That is the single most annoying gap in the
  session and it costs nothing to fix: one `kermit` session per rate, one
  log name each.
- One triage entry proved itself: a segment of S, F, A, then **Z with data
  `D`** and no data packets — `SET FILE COLLISION = BACKUP` refusing a name
  that already existed. Third attempt at the same filename.
- **Longest packet 3,991 bytes**, so `DRPSIZ = 4000` long packets are live
  on hardware as a measurement.
- **The half-second clock quantum is the Victor's, not MAME's.** Every
  figure in both runs — 50, 50, 100, 0 — is a multiple of 50. §16n's
  inference survives to hardware and its rule is unchanged: **quote `tot=`,
  never `max=`.**

### What 38400 settled

Both risks `HW_TESTING.md` §5 was built around. The OEM driver **accepts**
`msxv90.asm`'s undocumented divisor even though its Appendix A stops at
19.2k — §11a's status check was added for exactly the rejection that did not
happen — and the data path holds at a ~260 µs byte interval, twice, both
directions.

### The trap this session fell into, and it is worth keeping

**`wfile n=3 tot=50` does not measure the disk.** Three writes and *one*
clock-boundary crossing; inverting §16n's estimator on one crossing gives
~0.17 s per write with variance that swamps it, and it cannot be
distinguished from MAME's 0.124 s. §16n's caveat — that its disk figure is
probably the emulator's — is **still untested**. What is confirmed is that
`V9K_OBUFSIZE = 8192` is live: `of 8192` is the buffer reporting its own
size.

---

## 2. Do this next, in rough priority order

**Two runs at the bench close five open legs.** Both at 38400, both with the
32,768-byte all-byte-values fixture (the one every measurement from §16k on
used), both with `log packets` on the host. One stock, one with
`XFLAGS=-dV9K_OBUFSIZE=1024`. Between them they give:

1. ~~**`rxlost`/`rxfull` per rate.**~~ **Done — §16p, and it is §0 above.**
2. **cps and elapsed at 38400** — §16n projects ~1,630 rather than the
   ~2,400 the line rate suggests, on the grounds that dead time and not line
   time is what bounds this port. That projection has shaped every
   throughput argument here and has never been checked. Nothing but real
   hardware can check it.
3. ~~**The disk cost per write on real media.**~~ **Done — §16p.** 4 writes
   1.00 s, 32 writes 1.50 s: the cost tracks **bytes**, not calls, so
   §16n's per-call model was the emulator's. `V9K_OBUFSIZE = 8192` saves
   ~0.5 s per 32 KB here rather than 4 s. Keep it — far heap, free — but it
   is no longer part of any throughput argument.
4. ~~**The retransmission count.**~~ **Done — §16p**, and it killed the
   `rxpeak = 56` reading: there are retransmissions at every rate. Note the
   9600 log has the *worst* raw counts (18 resends, 15 timeouts) and
   `rxlost = 0` — almost all of it is startup dead air. **Segment the log
   before quoting a `grep -c`.**
5. ~~**Every byte value, round-tripped on hardware.**~~ **Done — §16p.**
   All four runs used the 32,768-byte all-256-values fixture and all four
   came back byte-exact, so §16h's `_fmode = O_BINARY` fix is fully tested
   on hardware.

**Then server mode on hardware** (`-g`, `-f`, `-x`, `--safe-server`) —
`HW_TESTING.md` leg 0.7, untouched.

**Then FreeDOS for Victor** — `HW_TESTING.md` Tier 4, and the IRQ1 vector
question (41h here, INT 09h there) that is the most likely thing to break
the "one binary, two DOSes" claim.

**Then windows.** `DFWSIZ` is still 1. §16m's note stands, and §16o
sharpens it: if the peak really is turnaround-during-resend and resends do
not happen on hardware, a window of 2 changes the ring from an
occasional-peak story to a steady-state one and the sizing argument has to
be redone from the dead time. Do it under MAME first.

**Profile the remaining dead time.** The open end of §16n, and the
instrument does not exist yet — §16o's clock finding means anything sampled
at half-second resolution needs many samples. The cheapest honest approach
is still to widen the §0e foreground tag and have the **interrupt handler**
sample it: a profile by occupancy rather than by clock.

**Report the `ckcmai.c` nesting upstream.** Unchanged from §16j.

**`REMOTE DIRECTORY`** still streams its listing and never terminates it
(§16i).

---

## 3. Instruments

- **`v9k:` lines on stdout at exit, every build.** Six of them —
  `rxlost/rxfull/rxpeak`, `peaktag/fd/stall256`, `rxbytes/peakat/stallat`,
  `wfile`, `wcon`, `txgap`. On hardware, capture them by redirecting stdout
  in a `.BAT` (`STEPM.BAT` is the pattern) and `TYPE`ing it back, or — the
  one that scales — **ship the log off with Kermit itself**, `CKERMITW -l
  /dev/seriala -b 19200 -s RUN1.LOG`.
- **The clock quantum is 0.5 s and it is the Victor's** (§16n, confirmed
  §16o). Read `tot=`, never `max=`; treat few-sample figures as noise. Three
  samples measure nothing.
- **Byte offsets map onto the host packet log**, resends included:
  `python3 .probe/mapoffset.py host.pkt <offset>...`
- **`grep -c '^S-'` counts retransmissions, `grep -c '<timeout>'` counts
  timeouts** (§16l). `python3 .probe/pktstat.py host.pkt` decodes a log.
- **`XFLAGS=-dV9K_OBUFSIZE=1024`** — §16m's disk baseline in one flag.
- **`XFLAGS=-dV9K_RXCHUNK=256`**, **`XFLAGS=-dDRPSIZ=90`** — kept knobs.
- **Do NOT combine `-dKEEP_DEBUG` with anything about throughput.** ~25 ms
  per received byte (§16k).
- **`python3 .probe/mzsize.py ckermitw.exe`** — run this, not `ls -l`.
- **`CKERMITW -d -h` is the 2.5-minute oracle** for anything decided before
  or during `sysinit()`.
- **There is no `-fstack-usage` under Open Watcom.**

---

## 4. Things that are known-incomplete

- **`SET FILE COLLISION` is `BACKUP`, and BACKUP cannot work on FAT.** Fresh
  filename per run. Symptom: S, F, A, then **Z with data `D` and no data
  packets**.
- **`SET TIMER OFF` is not a C-Kermit 9.0.302 command.**
- **`REMOTE DIRECTORY` never terminates its listing** (§16i).
- **Most of the default capability set is untested** (§16i). `BYE` never sent.
- **Wildcards are case-sensitive.** `-s *.TXT`.
- **No interrupt-level flow control**, `tcflow()` is a stub.
- **No stack switch in the handler** — deliberate, ~30-byte frame.
- **The IRQ1 vector is hard-coded to 41h.** Right for MS-DOS 3.1, and §16o
  is six more runs of evidence for that; still unknown for FreeDOS.
- **Ctrl-Break with the line open** is not covered by `atexit()`. On the
  bench this costs a power cycle, and the FreeDOS bench discipline says
  power-cycle the Pico too.
- **WR2 is left as the OEM driver set it** (`10h` vs 3.13's `14h`).
- **The carrier clause** in `ttgmdm()` forces carrier present under `CLOCAL`.
- **No floppy has ever been in the path.** Every hardware run was SASI, so
  §10's question about a floppy write holding the ring is untouched.
- **The receive path overruns at 38400.** 0.45% of received bytes, twice,
  reproducibly (§16p). Cause not diagnosed; see §0 above. This is the port's
  one known-live defect, and 9600 and 19200 are clean.

---

## 5. Still open, from before

**The parser build** — `XFLAGS=-dKEEP_ICP` plus `.probe/mzsize.py` settles
the DGROUP half in one build; it does not load, and that was measured.

**Why `binmode.obj`'s near init record does not work here** (§16h).

---

## 6. The harness

Both harnesses now matter, and `HW_TESTING.md` is the bench half.

**Bench.** Pico SASI serving `victor_kermit.img`; channel A; 1 m USB-C to
RS-232; host `set line /dev/tty.usbserial-*`, `set speed <rate>`, `set
carrier-watch off`, `set flow none`, `log packets <unique>`. Power-cycle the
Victor *and* the Pico between runs. Fresh target filename every run. Do not
write to the image while the machine is running.

**MAME.** Unchanged, and still the right place for anything that would cost
a drive to get wrong:

- `socat` first (single-use `-bitb`), then MAME, then wait ~105 s before
  starting the host `kermit`. `-seconds_to_run 300` for a 32 KB receive.
- **9600 is the emulator's ceiling**, not a setting. §16o is why 19200 and
  38400 numbers now exist at all.
- **`-seconds_to_run` against wall clock is a free speed check** — 302 s for
  300 means the timings mean something.
- **Use `-r`, not `-x`**, when the point is a receive measurement.
- **One `kermit` attempt per MAME run, unique log names** — `log packets`
  truncates.
- `~/projects/mame/victor_kermit.img.bak-20260806-obuf` is the last backup.
- **On the image now:** `CKERMITW.EXE` (203,338), `STEPH`–`STEPM.BAT`,
  `RCVF`–`RCVK.DAT`, plus `HW_TEST1`–`HW_TEST3.MD` from §16o and §16h–§16m
  leftovers. Delete before reusing a name.
- `.BAT` files need CRLF; `-autoboot_command` takes the literal `\n`; digits
  come through shifted under MAME (**the real keyboard does not do this**);
  MS-DOS 3.1 cannot redirect handle 2; the disk boots as `A:`; use
  `vtg_image_util`, never mtools.

---

## 7. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"        # ckermitw.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak sizes"  # DGROUP report
python3 .probe/mzsize.py ckermitw.exe                       # will it LOAD
```

Rule 4 still applies: the heap is **outside** DGROUP, the ring is not, and
`V9K_OBUFSIZE` is heap.

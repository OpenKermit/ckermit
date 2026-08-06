# Next session

Handoff for the Victor 9000 port, written 6 August 2026. **The ~502-byte
stall is identified — it is the host's retransmission — and with it the last
unexplained number in the receive path is gone.**

**Read `PORTING.md` §16m first.** It is this session: the instrument, the
three hypotheses it refuted, the byte-offset evidence that settles it, the
first measurement of what the file writes cost, and two corrections to §16l.

---

## 1. What changed this session

**`ckvictor.c` §0e is new — an instrument, not a behaviour change.** The
foreground keeps one byte saying where it is (library `write()`, polled
transmitter, library `read()`, `v9k_comm_read()`, or upstream code), and the
interrupt handler copies it — plus a byte offset — at the instant it raises
`rxpeak`. Two stores in the interrupt path and no INT 21h near it, which is
the design constraint §16k left behind. Alongside: the non-tty writes are
timed, the ACK-to-next-read gap is timed, and crossings of 256 are counted.
All of it prints to stdout at exit with the ring counters.

**One real bug came out of building it.** `v9k_ser_get()` published the tail
once, after its copy loop. For the length of that copy the handler sees head
moving and tail not, so the ring *appears* to fill while it is being
emptied, and any backlog gets its peak latched during the drain that is
removing it. The first run duly said "we were reading all along" and that
was the instrument, not the port. The tail is now published inside the loop.

**No upstream edit — still eleven.** DGROUP 48,176 → **48,240** (+64, the
counters). Image 202,310 → **203,300**, needs 217,572 of 396,224.

### The answer

With a window of one, the **retransmission is the only moment the host
transmits without waiting for our ACK**. The Victor is still decoding and
writing the original copy when the resend starts arriving, so the ring
fills. Measured, by byte offset:

```
v9k: rxpeak=513 of 4096
v9k: rxbytes=39574 peakat=4570 stallat=4036
offset 4036 -> RESEND seq=06 (272 into it)
offset 4570 -> RESEND seq=06 (806 into it)
```

Same root cause as §16l's timeouts, and equally not in this port. Crossings
track resends across all four runs (1→2, 4→6, 1→3, 1→2).

**Refuted along the way, each by measurement, and each had looked right:**
the inter-packet file write (it runs *before* `ack()`, `ckcpro.w:1700`, so
the host is silent through it), the post-ACK window (**0** hundredths across
29 and 34 gaps in the two runs with the largest peaks), and `MYBUFLEN` drain
granularity (`XFLAGS=-dV9K_RXCHUNK=256` predicted 133 and measured 504 — the
knob is still in the tree, off).

### The number that matters next

**Dead time is ~12.5 s per 32 KB and does not shrink with line rate.**

| | wire bytes | line time | elapsed | dead |
|---|---:|---:|---:|---:|
| run 1 | 39,492 | 41.1 s | 54 s | 12.9 s |
| run 2 | 46,673 | 48.6 s | 61 s | 12.4 s |

Run 2 was slower purely because 4 resends put 7.2 KB more on the wire. Of
the ~12.5 s the file writes are **3.5–7.0 s** (32 × 1,024 bytes, worst 0.50 s,
always the first); the rest is decode and protocol.

So **38400 should be expected to give ~1,400 cps, not ~2,400** — line time
falls by four, this does not move. It is a CPU and disk problem, not a
buffer problem, and the ring at 4,096 already covers the ~2,100-byte peak
the same retransmission would produce there.

### Two corrections to §16l

- Its run-2 **longest packet was 3,585**, not 3,099. This strengthens §16l:
  the host climbed *past* the length that timed out without further trouble.
- Its **537 → 606 cps is variance, not `SET RECEIVE TIMEOUT 20`.** Four runs
  here held that setting constant and got 1, 4, 1 and 1 retransmissions. The
  structural claims in §16l all survived: every timeout is the host's, every
  one lands on a slow-start doubling, and the Victor never NAKs.

---

## 2. Do this next, in rough priority order

**Real hardware.** Still nothing, ever, and now the largest gap by some
distance — the receive path has no unexplained numbers left at 9600.

**If throughput is the goal, attack the ~12.5 s, not the ring.** The two
measured components are the file writes (3.5–7.0 s; `zobufsize` is
`OBUFSIZE` = 1024 and `SET BUFFERS`/`zobufsize` is reachable without an
upstream edit — a bigger output buffer means fewer, larger DOS writes) and
decode. Neither has been optimised or even profiled per-phase. The §0e
tag machinery is already in place to do it.

**Then 8b, windows.** `DFWSIZ` is still 1. Note that §16m's mechanism is a
*consequence* of window 1 — with a window of 2 the host is legitimately
transmitting while we work, all the time, so the ring stops being an
occasional-peak story and becomes a steady-state one. Size it from the
~12.5 s, not from `rxpeak`.

**Report the `ckcmai.c` nesting upstream.** Unchanged from §16j.

**`REMOTE DIRECTORY`** still streams its listing and never terminates it
(§16i).

---

## 3. Instruments

- **`v9k:` lines on stdout at exit, every build.** Now six of them —
  `rxlost/rxfull/rxpeak`, `peaktag/fd/stall256`, `rxbytes/peakat/stallat`,
  `wfile`, `wcon`, `txgap`. A `.BAT` redirecting stdout catches them;
  `STEPK.BAT` is the current pattern.
- **Byte offsets map onto the host packet log**, resends included, which is
  how §16m was settled. `python3 .probe/mapoffset.py host.pkt <offset>...`;
  wire length is `unchar(LEN) + 3`, or data + 9 for a long packet.
- **`grep -c '^S-'` counts retransmissions, `grep -c '<timeout>'` counts
  timeouts** (§16l). `python3 .probe/pktstat.py host.pkt` decodes a log.
- **The packet log escapes control characters**, so the type is body[4].
- **`XFLAGS=-dV9K_RXCHUNK=256`** caps what `v9k_comm_read()` returns —
  refuted as an explanation for `rxpeak`, kept as a knob.
- **`XFLAGS=-dDRPSIZ=90`** — packet length in one flag.
- **Do NOT combine `-dKEEP_DEBUG` with anything about throughput.** ~25 ms
  per received byte (§16k).
- **`python3 .probe/mzsize.py ckermitw.exe`** — run this, not `ls -l`.
- **`CKERMITW -d -h` is the 2.5-minute oracle** for anything decided before
  or during `sysinit()`.
- **There is no `-fstack-usage` under Open Watcom.**

---

## 4. Things that are known-incomplete

- **`SET FILE COLLISION` is `BACKUP`, and BACKUP cannot work on FAT.** Use a
  fresh filename per run and delete leftovers. Symptom: S, F, A, then **Z
  with data `D` and no data packets**.
- **`SET TIMER OFF` is not a C-Kermit 9.0.302 command.**
- **`REMOTE DIRECTORY` never terminates its listing** (§16i).
- **Most of the default capability set is untested** (§16i). `BYE` never sent.
- **Wildcards are case-sensitive.** `-s *.TXT`.
- **No interrupt-level flow control**, `tcflow()` is a stub.
- **No stack switch in the handler** — deliberate, ~30-byte frame.
- **The IRQ1 vector is hard-coded to 41h.**
- **Ctrl-Break with the line open** is not covered by `atexit()`.
- **WR2 is left as the OEM driver set it** (`10h` vs 3.13's `14h`).
- **The carrier clause** in `ttgmdm()` forces carrier present under `CLOCAL`.
- **The DOS clock is quantised.** `AH=2Ch` reports hundredths but advances
  by a tick, so a `0` in any `cs` figure means "under one tick", not zero.
  The aggregates (`tot`) are the trustworthy half of those lines.

---

## 5. Still open, from before

**Nothing has run on real hardware.** All MAME, Victor MS-DOS 3.1.

**The gap for the interactive parser** — `XFLAGS=-dKEEP_ICP` plus
`.probe/mzsize.py` settles it in one build and no MAME run.

**The µPD7201 interrupt-acknowledge sequence.** Unsettled, gates 38400 —
though §16m says the ring is not what stands in the way there.

**Why `binmode.obj`'s near init record does not work here** (§16h).

---

## 6. The harness

§16a, §16d, §16g–§16m have it in full. Unchanged this session, and it ran
four times without trouble:

- `socat` first (single-use `-bitb`), then MAME, then wait ~105 s before
  starting the host `kermit`. `-seconds_to_run 300` for a 32 KB receive.
- **MAME exits on its own** when that expires; wait on the *process* and
  match `[m]ame/mame victor9k` so `pgrep` does not match the polling shell.
  `-log` still writes no `mame.log`.
- **Use `-r`, not `-x`**, when the point is a receive measurement.
- **One `kermit` attempt per MAME run, unique log names** — `log packets`
  truncates.
- **Verify by pulling the file back off the image and `cmp`.**
- `~/projects/mame/victor_kermit.img.bak-20260806-stall` is this session's
  backup.
- **On the image now:** `CKERMITW.EXE` (203,300), `STEPH/STEPI/STEPJ/STEPK
  .BAT` (all `-r`, no `-d`, stdout redirected) and `RCVF/RCVG/RCVH/RCVI.DAT`
  as receive fixtures, plus §16h–§16l leftovers. Delete before reusing a name.
- Everything else from §16i's list still holds: `.BAT` files need CRLF;
  `-autoboot_command` takes the literal `\n`; digits come through shifted;
  MS-DOS 3.1 cannot redirect handle 2; the disk boots as `A:`; use
  `vtg_image_util`, never write to the image while MAME runs.

---

## 7. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"        # ckermitw.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak sizes"  # DGROUP report
python3 .probe/mzsize.py ckermitw.exe                       # will it LOAD
```

Rule 4 still applies: the heap is **outside** DGROUP, the ring is not.

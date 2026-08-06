# Next session

Handoff for the Victor 9000 port, written 6 August 2026. **The file-write
cost is per call, not per byte; an 8 KB output buffer took it from 4.5 s to
about 1 s and the dead time from 12.8 s to 9.8.** This is the first piece of
the throughput work §16m handed over.

**Read `PORTING.md` §16n first.** It is this session: the one-variable
measurement, the model it supports, why it cost no upstream edit, and a
correction to §16m about the clock that changes how every timing figure in
this port should be read.

---

## 1. What changed this session

**One knob and one initializer, both in our own files.** `V9K_OBUFSIZE` in
`ckvictor.h` (**8192**, `#ifndef`-guarded) and a third XI record in
`ckvictor.c` §1d that sets `zobufsize` before `main()` reaches `getiobs()`.

The reason this is not a twelfth upstream edit is worth keeping: `OBUFSIZE`
is 1,024 and `ckcker.h` defines it **unguarded**, so `ckvictor.h` cannot
pre-empt it the way it does `DRPSIZ`. But `OBUFSIZE` is read only to seed
the `int zobufsize` (`ckcmai.c:1652`) and to bound `SET BUFFERS`
(`ckuus7.c:3755`), which `NOICP` removes — while both places that move bytes
read the **variable**: `getiobs()` mallocs `zobufsize` (`ckcmai.c:3795`) and
`zmchout()` flushes at `zobufsize` (`ckcker.h`). `sysinit()` would have been
the natural hook and is `ckutio.c`, which is stock, so the XI table is the
earliest one this port owns.

**No upstream edit — still eleven.** DGROUP **48,240, unchanged** (the
buffer is far heap). Image 203,300 → **203,338**, needs 217,594 of 396,224.

### The answer

Two runs against §16m run 4, same fixture bytes, same `set receive timeout
20`, and — unusually — the **identical 39,574 wire bytes with the same one
timeout and one retransmission**, so the comparison is not confounded by
where the host's estimator gets caught out.

| | §16m r4 (1,024) | 16n r1 | 16n r2 |
|---|---:|---:|---:|
| file writes | 32 | **4** | **4** |
| disk total | 4.50 s | 0.50 s | 1.50 s |
| `rxpeak` | 513 | **309** | **310** |
| elapsed | 54 s | **51 s** | **51 s** |
| cps | 603 | **633** | **631** |

Per byte would have left the total unmoved. It fell threefold to ninefold.
The two sizes fit **~0.124 s fixed per `write()` plus ~15 µs/byte** (~64
KB/s), which predicts 4,096 → 1.5 s, 8,192 → 1.0 s, 16,384 → 0.75 s, and a
floor of 0.6 s for one write. **8,192 collects most of it**; going higher
buys tenths and spends far heap.

**`rxpeak` fell 513 → 309, and that confirms §16m rather than adding to
it.** §16m established the peak is our pre-ACK turnaround measured while the
host resends; take four file writes out of that turnaround and the peak
shortens by 204 bytes, which is 0.21 s at 9600 — about one write. `stallat`
and `peakat` still land inside the resend of seq=06 (3,764–5,717).

### The correction, and it matters for every measurement here

**§16m's "worst single write 0.50 s, and always the first" is wrong, and so
is the assumption underneath it.** Every timing figure this port has printed
— six runs, three independent timers — is a multiple of **50 hundredths**,
and no `max` has ever read anything but 0 or 50. **This machine's DOS clock
advances in half-second steps.**

- **No individual event has ever been timed.** 50 is the smallest non-zero
  reading possible, so "worst write 0.50 s" only means "that write crossed a
  boundary". Which one shows it is near enough a coin flip — §16m saw the
  first write three times and read a pattern into it; here it was #4, then
  #1.
- **Totals are still sound and are the half to quote.** An interval of true
  length *d* < 0.5 s crosses with probability *d*/0.5, so a sum over many
  samples is an unbiased estimate of the total though no term of it is. That
  is why 32 samples give a usable 4.5 s and 4 samples give a noisy 0.5/1.5,
  and why the two runs differ threefold on disk while agreeing on elapsed.

**Quote `tot=`, never `max=`.**

### The number that matters next

**Dead time is 9.8 s per 32 KB, of which about 1 s is now disk.** The rest
is decode and protocol and **has never been profiled**. At 38400 that
projects to ~20 s for 32 KB, **~1,630 cps** (§16m said ~1,400). Still not
the ~2,400 the line rate alone suggests. It is now **a CPU problem, much
less a disk one**.

### The harness limit that bounds all of that

**MAME cannot run this machine above about 9600.** Not a configuration
limit — above 9600 the emulation is too slow to meet the serial timing
thresholds, and the host on the other end of the `-bitb` socket is real and
does not slow down to match. So **38400 is a real-hardware-only path, and
every 38400 figure in §16m and §16n is arithmetic that nothing in this
harness can test.**

At 9600 the emulator is faithful, and both runs measured it for free:
`-seconds_to_run 300`, MAME exited **302 s of wall clock later, twice**.
Emulated time tracks real time to ~1%, which is what makes any of the 9600
numbers comparable. Two caveats stand:

- **Real-time is not cycle-accurate.** The 9.8 s is a faithful measurement
  of the *emulated* machine and an untested estimate of a real one.
- **The disk timing is almost certainly MAME's, not the Victor's.** 0.124 s
  fixed per `write()` is very slow for a real drive. §16n's **direction**
  (per call, not per byte) is safe anywhere; the **size** of the saving may
  not transfer, and 8,192 may be over-provisioned for real hardware. It
  costs only far heap, so leave it — and re-measure on the real machine.

---

## 2. Do this next, in rough priority order

**Real hardware.** Still nothing, ever, and by some distance the largest
gap — and note it is now the *only* route to four of this port's open
questions, since MAME cannot go above 9600: **19200, 38400, the µPD7201
interrupt-acknowledge sequence, and the true cost of a disk write.**

**Profile the remaining 8.8 s.** This is the open end of §16n and the
instrument for it does not exist yet. The §0e tag says *where* the
foreground was when the ring peaked, which is not the same as where it
spends its time — and §16n's clock finding means anything sampled at half-
second resolution needs many samples to say anything. Cheapest honest
instrument is probably to widen the §0e tag to more foreground states and
have the **interrupt handler** sample it (it already runs per received byte,
and §16m established that costs a store and no INT 21h) — a profile by
occupancy rather than by clock, which sidesteps the quantum entirely.

**Then 8b, windows.** `DFWSIZ` is still 1. §16m's note stands: with a window
of 2 the host transmits while we work all the time, so the ring becomes a
steady-state story rather than an occasional-peak one. Size it from the dead
time, not from `rxpeak`.

**`V9K_OBUFSIZE` higher is not worth a run** unless something else changes —
the model says 16,384 saves 0.25 s.

**Report the `ckcmai.c` nesting upstream.** Unchanged from §16j.

**`REMOTE DIRECTORY`** still streams its listing and never terminates it
(§16i).

---

## 3. Instruments

- **`v9k:` lines on stdout at exit, every build.** Six of them —
  `rxlost/rxfull/rxpeak`, `peaktag/fd/stall256`, `rxbytes/peakat/stallat`,
  `wfile`, `wcon`, `txgap`. A `.BAT` redirecting stdout catches them;
  `STEPM.BAT` is the current pattern.
- **The clock quantum is 0.5 s (§16n).** Read `tot=`, never `max=`, and
  treat any figure built from few samples as noisy.
- **Byte offsets map onto the host packet log**, resends included:
  `python3 .probe/mapoffset.py host.pkt <offset>...`; wire length is
  `unchar(LEN) + 3`, or data + 9 for a long packet.
- **`grep -c '^S-'` counts retransmissions, `grep -c '<timeout>'` counts
  timeouts** (§16l). `python3 .probe/pktstat.py host.pkt` decodes a log.
- **The packet log escapes control characters**, so the type is body[4].
- **`XFLAGS=-dV9K_OBUFSIZE=1024`** — §16m's disk baseline in one flag.
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

---

## 5. Still open, from before

**Nothing has run on real hardware.** All MAME, Victor MS-DOS 3.1.

**The gap for the interactive parser** — `XFLAGS=-dKEEP_ICP` plus
`.probe/mzsize.py` settles it in one build and no MAME run.

**The µPD7201 interrupt-acknowledge sequence.** Unsettled, gates 38400 —
though §16m says the ring is not what stands in the way, and §16n says the
disk is no longer most of what does. **Real hardware only**: MAME cannot
reach 38400, so this cannot be settled in the current harness at all.

**Why `binmode.obj`'s near init record does not work here** (§16h).

---

## 6. The harness

§16a, §16d, §16g–§16n have it in full. Unchanged this session, and it ran
twice without trouble:

- `socat` first (single-use `-bitb`), then MAME, then wait ~105 s before
  starting the host `kermit`. `-seconds_to_run 300` for a 32 KB receive.
- **9600 is the harness ceiling**, and it is the emulator, not a setting.
  Do not spend a run trying 19200 or 38400.
- **`-seconds_to_run` against wall clock is a free speed check** — 302 s for
  300 means the emulator kept up and the timings mean something.
- **MAME exits on its own** when that expires; wait on the *process* and
  match `[m]ame/mame victor9k` so `pgrep` does not match the polling shell.
- **Use `-r`, not `-x`**, when the point is a receive measurement.
- **One `kermit` attempt per MAME run, unique log names** — `log packets`
  truncates.
- **Verify by pulling the file back off the image and `cmp`.**
- **Reuse the previous fixture bytes** when the point is an A/B — §16n's
  runs were tight because the wire byte count came out identical.
- `~/projects/mame/victor_kermit.img.bak-20260806-obuf` is this session's
  backup.
- **On the image now:** `CKERMITW.EXE` (203,338), `STEPH`–`STEPM.BAT` (all
  `-r`, no `-d`, stdout redirected) and `RCVF`–`RCVK.DAT` as receive
  fixtures, plus §16h–§16m leftovers. Delete before reusing a name.
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

Rule 4 still applies: the heap is **outside** DGROUP, the ring is not, and
`V9K_OBUFSIZE` is heap.

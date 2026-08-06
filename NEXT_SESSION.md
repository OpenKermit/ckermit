# Next session

Handoff for the Victor 9000 port, written 5 August 2026 (third session that
day). **Step 8a is done. The port sends and receives 4,000-byte packets and
32,768 bytes transfer byte-exact.**

**Read `PORTING.md` §16k first** — it is this session and it retracts two
claims from §16j. §15 closed one question and opened two. §13 step 8a is now
DONE. The headline DGROUP figures in §0 and §1 were stale since §16j and are
corrected.

---

## 1. What changed this session

**The (480, 968] receive ceiling was two ceilings, and the outer one was the
instrument.** `-d` costs about **25 ms per received byte** — `ttinl()` emits
a debug line per byte and `ckhexdump()` dumps the buffer per read; one file
produced 4,274 `TTINL myread char` lines. Against the host's 15-second packet
timeout that is a ceiling in bytes: 480 × 25 ms = 12 s squeaks through, 968 ×
25 ms = 24 s never does. **Every run that established (480, 968] was a `-d`
run.** With `-d` dropped, the same binary at the same `DRPSIZ=4000` delivered
the same 968-byte packet first try, 2,048 bytes in 4 seconds.

**Underneath it the real limit was the ring — the suspect §16j dismissed.**
Without `-d`, packets of 968 and 1,952 ACKed and 3,904 died, with
`rxpeak = 502 of 512`. `V9K_RXBUFSIZ` is now **4096**. `MYBUFLEN` is
exonerated and **no upstream edit was needed** — still eleven.

**`rxpeak` is new and it is what made this readable.** `rxfull = 0` alone
cannot tell "never close" from "ten bytes from the edge", and that was the
whole story. All three counters now print **to stdout at `atexit()` in every
build**, because a run fast enough to measure is exactly a run that cannot
carry a debug log:

```
v9k: rxlost=0 rxfull=0 rxpeak=502 of 4096
```

**The number I got wrong on the way, and it matters for 38400.** I sized the
ring expecting the backlog to scale with packet length. It does not:

| ring | longest packet | `rxpeak` |
|---:|---:|---:|
| 512 | 2,668 | **502** of 512 |
| 4096 | 3,605 | **502** of 4096 |

The same 502 with 8× the ring. It is **one fixed stall of ~523 ms at 9600**,
not a rate deficit. Which stall is *not established* — the inter-packet file
write is the obvious candidate and was not isolated. So 4096 is sized to hold
a whole maximum-length packet, which is the only assumption that survives
something else getting slower.

**Measured, both changes in**, 9600, MS-DOS 3.1 under MAME, Victor as
`CKERMITW -l /dev/seriala -b 9600 -r`, no `-d`:

- **32,768 bytes byte-exact** (`cmp` after pulling it back off the image),
  56 s, **582 cps**, longest packet 3,605
- 16,384 bytes byte-exact on the previous build (ring 512, `rxpeak` 502/512)
- 2,048 bytes byte-exact, 4 s

| | §16j | now |
|---|---:|---:|
| DGROUP | 44,592 (68%) | **48,176 (73%)** |
| `V9K_RXBUFSIZ` | 512 | **4096** |
| `DRPSIZ` | 90 | **4000** |
| `ckermitw.exe` | 202,212 | **202,294** |
| needs at load | 212,900 | **216,566** of 396,224 |
| spare | 183,324 | **179,658** |

---

## 2. Do this next, in rough priority order

**Round the alarm deadline up — one line, in our own file.** This is the top
item and it is the leading explanation for the one timeout and two
retransmissions that survive in the clean 32 KB run (`rxfull = 0`, so not the
ring). Derived from the source, **not measured**:

- `CK_TIMERS` is on and `rttflg` defaults to 1, so `rcvtimo` comes from
  `getrtt()`, computed from `gtimer()` — which has **whole-second
  resolution**. With `mintime = 1` the file-receiver path lands on 3.
- `ckvictor.c`'s `alarm()` records `time() + secs` and fires when `time()`
  reaches it, so `alarm(n)` armed part-way through a second fires in
  **(n−1, n]** — *early*, by up to a full second. **The comment in §0d claims
  the opposite** ("never early") and is wrong.
- At `rcvtimo = 3` that is a 2 s worst case against 4.2 s of line time for a
  3,999-byte packet.

Fix is `v9k_alarm_at = now + secs + 1`. Then re-run the 32 KB fixture and
count retransmissions in the host's packet log.

**Isolate the ~502-byte stall.** It bounds how far the ring could be trimmed
and it is four times as many bytes at 38400. §16k did not isolate it.

**Real hardware.** Still nothing, ever. Unchanged and still the largest gap.

**Then 8b, windows.** `DFWSIZ` is still 1. This is the step that removes the
one-packet-in-flight property the missing flow control relies on, so
`tcflow()` or a much larger ring probably comes first.

**Report the `ckcmai.c` nesting upstream.** Unchanged from §16j — wrong for
every `NOTCPIP` build, and it silently costs `getdialenv()` too.

**`REMOTE DIRECTORY`** still streams its listing and never terminates it
(§16i). Unchanged; use `--safe-server` when you need the log.

---

## 3. Instruments

- **`v9k: rxlost=… rxfull=… rxpeak=… of …` on stdout at exit, every build.**
  The one that mattered this session. A `.BAT` that redirects stdout catches
  it; `STEPE.BAT` is the pattern.
- **`XFLAGS=-dDRPSIZ=90`** — packet length is a one-flag experiment now, both
  here and in `ckcker.h`. This is how the ceiling was bisected.
- **Do NOT combine `-dKEEP_DEBUG` with long packets and believe the result.**
  That is the whole lesson of §16k. `-d` is still the right instrument for
  anything that is not throughput.
- **`python3 .probe/mzsize.py ckermitw.exe`** — run this, not `ls -l`.
- **`CKERMITW -d -h` is the 2.5-minute oracle** — no serial line, no `socat`,
  no host `kermit`. Reaches `sysinit()` → `uname()` and `inibufs`. Does not
  reach `rpar()`, so it cannot tell you the negotiated packet length.
- **Decode the negotiation yourself**: `MAXL TIME NPAD PADC EOL QCTL QBIN
  CHKT REPT CAPAS WINDO MAXLX1 MAXLX2`, each `unchar(c) = c - 32`, long
  length = `MAXLX1*95 + MAXLX2`.
- **Packet lengths straight off the host log**: `awk '{print length($0)}'
  host.pkt | sort -n | tail`. The wire packet is the line minus the 8-char
  `s-NN-TT-` prefix.
- **There is no `-fstack-usage` under Open Watcom.** Read the source for new
  automatics; check `sub sp,N` in `wdis` if it matters.

---

## 4. Things that are known-incomplete

- **One timeout + two retransmissions in a clean 32 KB run.** §2. Not the
  ring (`rxfull = 0`). Not diagnosed.
- **The ~502-byte stall is unidentified.** §2.
- **`SET FILE COLLISION` is `BACKUP`, and BACKUP cannot work on FAT.**
  `znewn()` appends `.~N~` to the whole name — not a legal 8.3 name — so a
  receive onto an existing name is refused with reason "name". Symptom: S, F,
  A, then **Z with data `D` and no data packets at all**. **Use a fresh
  filename per run and delete leftovers from the image.**
- **`REMOTE DIRECTORY` never terminates its listing** (§16i).
- **Most of the default capability set is untested** (§16i). `BYE` never sent.
- **Wildcards are case-sensitive.** `-s *.TXT`, not `*.txt`.
- **No interrupt-level flow control**, `tcflow()` is a stub.
- **No stack switch in the handler** — deliberate, ~30-byte frame.
- **The IRQ1 vector is hard-coded to 41h.** Most likely thing to break "one
  binary, two DOSes".
- **Ctrl-Break with the line open** is not covered by `atexit()`.
- **WR2 is left as the OEM driver set it** (`10h` vs 3.13's `14h`).
- **The carrier clause** in `ttgmdm()` forces carrier present under `CLOCAL`.

---

## 5. Still open, from before

**Nothing has run on real hardware.** All MAME, Victor MS-DOS 3.1.

**The gap for the interactive parser** — `XFLAGS=-dKEEP_ICP` plus
`.probe/mzsize.py` settles it in one build and no MAME run. Not re-measured
since `NOFLOAT`, and note the ring just spent 3,584 bytes of DGROUP.

**The µPD7201 interrupt-acknowledge sequence.** Unsettled, gates 38400.

**Why `binmode.obj`'s near init record does not work here** (§16h). Routed
around, not diagnosed.

---

## 6. The harness

§16a, §16d, §16g–§16k have it in full. What this session added or corrected:

- **Put the Victor in `-r` (receive), not `-x` server mode, when the point is
  a receive measurement.** A failed server run can leave the server wedged so
  the host's `finish` never lands, and then MAME's `-seconds_to_run` kills the
  program before it flushes anything. `-r` always exits.
- **One `kermit` attempt per MAME run, and unique log names per run.** `log
  packets` *truncates*, so attempt 2 destroyed attempt 1's evidence — that
  cost a run this session.
- **Size the fixture to the packet length.** 2,048 bytes reaches the 968-byte
  rung of C-Kermit's slow start; 16 KB reaches ~2,600; 32 KB reaches ~3,600.
- **Verify by pulling the file back off the image and `cmp`**, rather than a
  second transfer — no host `receive` timing to get wrong.
- **Wait on the run script's PID.** `pgrep -f "mame victor9k"` matches your
  own polling shell.
- `~/projects/mame/victor_kermit.img.bak-20260805-ceiling` is the backup from
  before this session's runs.
- **On the image now:** the shipping `CKERMITW.EXE` (202,294, `DRPSIZ` 4000,
  ring 4096), `STEPE.BAT` (`-r`, no `-d`, stdout to `STEPE.OUT`), `STEPC.BAT`
  (the `-d` server run that reproduced §16j), plus §16h–§16j leftovers.
  `RCVA/RCVB/RCVC.DAT` are receive fixtures — delete before reusing a name.
- Everything else from §16i's list still holds: `-bitb` is single-use so start
  `socat` first with `fork`; `.BAT` files need CRLF; `-autoboot_command` takes
  the literal `\n`; digits come through shifted; MS-DOS 3.1 cannot redirect
  handle 2; the disk boots as `A:`; use `vtg_image_util`, never write to the
  image while MAME runs; `kermit -y <file>` always.

---

## 7. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"        # ckermitw.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak sizes"  # DGROUP report
python3 .probe/mzsize.py ckermitw.exe                       # will it LOAD
```

Rule 4 still applies, and so does its second half: the heap is **outside**
DGROUP, so anything that raises the packet buffers is measured against the
machine's 396,224, not against the segment. The **ring is not** — it is
`.bss` and comes straight out of the 64K.

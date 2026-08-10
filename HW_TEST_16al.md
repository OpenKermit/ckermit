# Bench run sheet — four legs: what §1f costs, and whether RTS is honoured

**This document is the thing to work from. Follow it top to bottom.**

**Nothing below needs building, writing or staging.** One new binary is
compiled, staged and round-trip verified; four `.BAT`s are on the image and
verified CRLF **after** landing there; four take-files and four fixtures are
in the tree; the target names are new and have never been used. §0 is a
receipt.

Written 9 August 2026, after PORTING.md §16ak and after the void re-run of
legs DA/DB. **Four legs, two adjacent pairs.**

> ### ✅ ATTEMPT 2 RAN, 9 August 2026. ALL FOUR LEGS BYTE-EXACT.
>
> Written up in PORTING.md **§16al**. Both questions answered:
>
> - **§16ak's +11% is withdrawn.** Leg GP — HEAD *before* §1f — has a
>   non-line cost of **21.43 s** against GQ's **21.54 s**. §1f costs
>   **≤ 0.11 s on a 32 KB receive**, inside the 151 ms spread of the three
>   clean legs. The 3.1 s §16ak saw was **between sittings**, and GP proves
>   it: the same binary that did 18.29 s non-line in §16ah did 21.43 s here.
> - **Leg GB could not answer its question, and PORTING.md §16am says why.**
>   It ran clean and byte-exact with **eleven asserts and eleven releases**
>   and came back `rxpeak = 2,974` against its control's **2,978** — and
>   `kermit -C "show features"` on the bench Mac does **not** list
>   `POSIX_CRTSCTS`, so that host's `tthflow()` is empty and `set flow
>   rts/cts` never put `CRTSCTS` on the FTDI port. **The far end was never
>   configured to stop.** "Our RTS does not reach the far end" is withdrawn
>   and back to unknown. The test that does not route through Kermit is
>   `v9k/tools/ctswatch.py` plus `CKICP`'s `HANGUP` — see §16am.
>
> `V9K_FLOW` stays `FLO_NONE` — now for a measured reason instead of an
> unmeasured one. Results are inline against each leg below.
>
> ### ⚠ ATTEMPT 1 WAS A WASH: THE IMAGE WAS FULL. FIXED — READ THIS BOX.
>
> All four legs failed with `Too many retries`, 31–33 timeouts each, after
> getting eleven or twelve packets in and then going silent forever. **The
> cause was not the build and not §1f**: leg GP runs `CKPRE`, HEAD *before*
> §1f, the binary that transferred cleanly through §16ah and §16ai, and it
> failed identically.
>
> `vtg_image_util info` says it plainly — **`Free: 0 B (0.0%)`**. Every
> output file is **0 bytes**: all four `RCVG*.DAT`, all four `STEPG*.OUT`.
> The Victor received packets, buffered 8,192 (`V9K_OBUFSIZE`), tried to
> flush, had nowhere to put it, and **hung** — and the redirect could not
> write the counters either, which is why there is no `v9k:` line to read.
>
> **My doing, and it is the third harness error in this sequence.** Staging
> `CKFCMID.EXE` put 206,758 bytes onto an image I never checked the free
> space of. §16ai's sheet recorded "2.0 MB free on the image" in its §0
> receipt; **§16aj, and this sheet, both checked the target names and
> neither checked the space.** Between them they added roughly 1.5 MB of
> binaries and received files.
>
> **Fixed:** 59 files removed — my own leg outputs from §16aj/§16ak/§16al
> and three staged binaries with byte-identical copies in the tree
> (`CKFCA`, `CKFCLO`, `CKFCD`). **Every artefact was extracted into
> `v9k/legs/` first**, and a full backup was taken as
> `victor_kermit.img.bak-20260809-full`. Nothing predating this work was
> touched. **Free is now 1.4 MB (13.9%), 273 files**, and the four legs need
> about 140 KB between them.
>
> **A real port finding is buried in this and it should not be lost: out of
> disk space makes the Victor HANG, not fail.** The host times out and gives
> up after 30-odd retries; the Victor never does, because §0d's `alarm()`
> bounds the *read* and nothing bounds a failed write. That is a robustness
> defect worth a `KEEP_DEBUG` leg under MAME against a deliberately full
> image — cheap, safe, and it has never been looked at.

---

## Why there is a second sheet: the re-run produced nothing, and it was the
## harness

The 9 August re-run of DA and DB came back with **287-byte packet logs** and,
on the Victor's own screen:

```
 No files were transferred (refused: destination file already exists).
```

`RCVDA.DAT` and `RCVDB.DAT` were still on the image from the first sitting,
`SET FILE COLLISION` is `BACKUP`, and **BACKUP cannot work on FAT**. The
wire shows the documented signature exactly — `s-03-02-…ZD`, an S, an F, an
A, then a **Z packet carrying data `D`**, and no data packets at all. Both
`RCVD*.DAT` on the image are byte-identical to the first sitting's: nothing
was written.

**Two failures, both in `HW_TEST_16aj.md` and both avoidable:**

1. Its §0 said the target names were clear — true before the *first*
   sitting — and its "After the sitting" section then asked for a re-run of
   DA/DB **without saying to clear the targets or use fresh names.** The
   trap and its signature are documented one section above the instruction
   that walks into it.
2. It asked for the re-run at `-dV9K_RXHIGH=1024 -dV9K_RXLOW=512` and **that
   binary was never built or staged**, so the re-run would have used 256/64
   again even if the names had been clear — and 256/64 is what voided leg DB
   the first time.

**Both are fixed structurally rather than by remembering.** Every leg below
has a **new target name that has never been used**, and every `.BAT` starts
with

```
IF EXIST RCVGx.DAT DEL RCVGx.DAT
```

so the legs are **re-runnable**. That is the fix worth keeping: this trap has
now cost two sittings, and "use a fresh name" is a rule a person has to
remember where `IF EXIST … DEL` is a rule the machine keeps.

---

## 0. Staging — **already done. This section is a receipt.**

| on the image | bytes | md5 | what it is |
|---|---:|---|---|
| `CKPRE.EXE` | 205,228 | `537486a8…` | **HEAD before §1f.** The binary the project measured through §16ai. Leg GP |
| `CKERMITW.EXE` | 206,758 | `c5652a5b…` | the shipping build with §1f. Leg GQ |
| `CKFCMID.EXE` | 206,758 | `c741268d…` | shipping tree with the marks at **1024/896**. Legs GA, GB |

`CKFCMID` differs from `CKERMITW` in **five bytes and three constants** —
`0C00h`→`0400h` for the high mark, `0400h`→`0380h` for the low mark, twice —
at the same three offsets `CKFCLO` used. Same size, same layout, so §16w has
nothing to act on **within** the GA/GB pair.

**`CKPRE` against `CKERMITW` is different and it is deliberate:** 205,228
against 206,758, so code size *is* in play. That is not a confound, it is
part of what §1f costs — §16w established that on an 8088 code size is
execution time.

Built with 19 warnings, unchanged, none in `ckvictor.c` or `ckvisr.asm`.

**Staged and verified CRLF after landing:** `STEPGP` `STEPGQ` `STEPGA`
`STEPGB`. Reused: `TRANS.DAT` (32,768 bytes, md5
`d94d2beda069ef0ef340977e7fd6995d`).

**Checked:** no `RCVG*.DAT`, no `STEPG*.OUT` on the image; no `s16alG*` or
`rcvg*.dat` collisions on the host. Host fixtures `rcvgp.dat` `rcvgq.dat`
`rcvga.dat` `rcvgb.dat` are copies of `TRANS.DAT`.

**FREE SPACE: 1.4 MB (13.9%), 273 files** — re-checked after the cleanup,
and the three binaries, four `.BAT`s and `TRANS.DAT` above were all
re-extracted and md5-verified afterwards, CRLF included. The four legs need
about 140 KB.

> **PUT THIS LINE IN EVERY §0 FROM NOW ON.** A sheet that checks target
> names and not free space checks half the trap. `vtg_image_util info
> <img>` prints it in one command, and **an image at 0 bytes free makes a
> working port look thoroughly broken** — eleven packets, then a hang, on a
> binary that had transferred cleanly twice before.
>
> **The long-term answer is on the disk already and is untested:**
> partition 1 (`D:`) is 9.7 MB and **100% free**, and the partition table
> maps it. Nothing in this project has ever written to it. One MAME boot
> doing `DIR D:` and a redirect to `D:\` would say whether leg outputs can
> simply go there instead of accreting on `A:`.

**Yours:** check `~/.kermrc` names the adapter that is plugged in.

**To rebuild** (you should not need to):

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak clean && \
   make -f victorow.mak XFLAGS='-dV9K_RXHIGH=1024 -dV9K_RXLOW=896'"
# -> ckermitw.exe, 206,758, md5 c741268d…   (copy aside as CKFCMID.EXE)
```

---

## Before every leg

- **The Victor takes about 40 s to load.** All four legs are Victor
  *receives*, so **start the Victor first, wait for the drive to go quiet,
  then start the host.** All four take-files carry `set retry 30`.
- **Run each pair back to back.** Nothing here is comparable across a gap:
  §16ak's sitting held to 398 ms internally while sitting 12–15 s away from
  §16ah's.
- Power-cycle the Victor **and** the Pico between runs.
- Three files per leg: `s16alG<x>.host`, `s16alG<x>.pkt`, `STEPG<x>.OUT`,
  plus the transferred file `cmp`'d against the fixture.
- **`cmp` first, then the counters.**

**Read every log the same way:**

```sh
python3 v9k/tools/pktstat.py --rxbytes <from the .OUT> s16alG<x>.pkt
```

Residual **−11** clean, **+28** with a startup timeout. (On a leg with
`rxlost > 0` it will read further off, by roughly the BELL count — the tool
has no term for BELL substitution and §16ak's leg DC is the worked example.)

---

## Pair 1 — what §1f costs. Legs **GP** then **GQ**, back to back.

```
STEPGP                     (at A>, CKPRE — HEAD before §1f)
```
```sh
kermit -C "take s16alGP.ksc, exit" > s16alGP.host
```
then
```
STEPGQ                     (at A>, CKERMITW — shipping, with §1f)
```
```sh
kermit -C "take s16alGQ.ksc, exit" > s16alGQ.host
```

`cmp` both; extract both `.OUT`s.

**The question.** §16ak's three clean receive legs did 37,557 wire bytes in
**31.137 / 31.143 / 31.535 s**. §16ah leg BC did the identical 37,557 in
**28.057 s**. That is **+11%** — eight times §16ak's own 398 ms spread, and
therefore not noise — but it compares two sittings, which is precisely what
§16aj tells you not to do. **This pair makes it a within-sitting
comparison.**

**Pass condition for both legs is just cleanliness:** `rxlost=0 rxfull=0`,
18 packets, 0 retransmissions, 0 timeouts, 37,557 wire bytes, byte-exact.
**The result is `GQ − GP` on the host clock**, and it is only readable if
both legs are clean and adjacent.

| GQ − GP | reading |
|---|---|
| **≈ 0** (inside a few hundred ms) | §16ak's +11% was two sittings, not a change. **Withdraw the figure.** |
| **≈ +3 s** | §1f costs ~11% of a 38400 receive. That is four ISR instructions, five on the transmit path, and 1,530 bytes of image — and it is a real cost the port has to decide about, because flow control is currently switched off and paying it |

**If GQ − GP is large, do not immediately blame the ISR.** §16w measured
`-ot` costing throughput purely through code size, and §16ag's `NOCKXXCHAR`
gain was probably its size rather than its two instructions. **Four of this
project's hand-costed 8088 predictions have come out wrong, one in sign.**
The pair measures the total; it does not attribute it.

> **RESULT GP — clean enough, and the bias runs the right way.** Byte-exact,
> `rxlost=0 rxfull=0 rxpeak=2355`, **31.979 s**. Off-shape: it took the
> startup race (`pktstat.py` residual **+28**, "the S packet the Victor was
> not yet listening for"), 26 packets, 3 resends, 40,572 wire bytes.
>
> **RESULT GQ — clean.** Byte-exact, `rxlost=0 rxfull=0 rxpeak=2974`, 18
> packets, **0 resends, 0 timeouts**, 37,557 wire bytes, residual −11,
> **31.308 s**.
>
> **THE PAIR: non-line cost 21.43 s (GP) against 21.54 s (GQ).** Subtracting
> the wire's own time is what makes GP comparable despite carrying 3,015
> more bytes. **§1f costs ≤ 0.11 s over 37,557 wire bytes — about 3 µs per
> wire byte — and GP's figure still contains its startup dead air, so the
> true cost is smaller.** The bias runs *against* the conclusion, which is
> what makes it safe to draw from an off-shape leg.
>
> **§16ak's +11% is withdrawn.** The same `CKPRE` binary had a non-line cost
> of **18.29 s** in §16ah and **21.43 s** here. Every leg from the last two
> sittings, with §1f and without, sits at ~21.5 s. The swing is the *host* —
> macOS scheduling, USB, the adapter — not the Victor and not the change.

---

## Pair 2 — is our RTS honoured. Legs **GA** then **GB**, back to back.

```
STEPGA                     (at A>, CKFCMID --noflow)
```
```sh
kermit -C "take s16alGA.ksc, exit" > s16alGA.host
```
then
```
STEPGB                     (at A>, CKFCMID --rtscts)
```
```sh
kermit -C "take s16alGB.ksc, exit" > s16alGB.host
```

**What changed from §16ak's DA/DB, and why.** That pair ran the marks at
**256/64** and the treatment leg went off-shape: a timeout and three
retransmissions inside the first 7,680 bytes, and `rxpeak` latched **fourteen
bytes into a resend** — the one place §16m and §16ag say `rxpeak` means
nothing. A 64-byte release point means every hold-off lasts until 192 bytes
have drained, ~93 ms, over and over, which is enough to disturb C-Kermit's
round-trip estimator during slow start.

**1024/896 is a narrow band rather than a low mark.** Each pause is 128 bytes
of drain — about **62 ms** — and the assert fires often. Short pauses, same
mechanism, much less provocation.

**And the reading is now a CAP rather than a comparison**, which is the part
that matters: a cap survives a retransmission, where DB's comparison did not.

| | GA (`--noflow`, control) | GB (`--rtscts`) |
|---|---|---|
| `flow in/out` | 0 / 0 | **2 / 2** |
| `hi` / `lo` | 65535 / 896 | **1024 / 896** |
| `held` / `rel` | 0 / 0 | **> 0, and equal** |
| **`rxpeak`** | **2,7xx–3,1xx** (§16ak: 2,780 / 2,990 / 3,137) | **?** |

- **`rxpeak` ≈ 1,0xx–1,4xx** — occupancy pinned at the mark. **The far end
  stopped when we asked. Our RTS reaches the host's CTS**, and
  `NEXT_SESSION.md` §1 item 11 closes.
- **`rxpeak` ≈ 2,8xx–3,1xx with `held > 0`** — occupancy followed GA's
  curve. We asserted and nothing happened: **not wired outbound, or not
  honoured.** The default stays `FLO_NONE` and XON/XOFF is this cable's
  mechanism. A result, not a failure.
- **`held = 0`** — the 1,024 mark was never crossed, which cannot happen on
  a leg whose control peaked at 2,8xx. Check `in=2` on the flow line before
  concluding anything about RTS: it means the switch did not take.

**Run `mapoffset.py` on `peakat` before believing `rxpeak`, on both legs:**

```sh
python3 v9k/tools/mapoffset.py s16alGB.pkt --rxbytes <n> <peakat>
```

**A peak inside a resend is not a measurement of anything** — that is what
voided DB, and it is also what corrected the reading of DE, whose peak turned
out to sit at an ordinary packet boundary. On a *capped* leg the peak should
land wherever the mark is first crossed, early, and stay there.

**Also record `stall256` on both.** §16ak's DB gave 2,399 against DA's 47 and
nothing explains it. At a 1024/896 band the 256 mark is crossed only during
the initial ramp, so both legs should read low — **if GB comes back with
thousands again, that is the same unexplained thing twice and it becomes the
most interesting number in the sitting.**

> **RESULT GA — clean control.** Byte-exact, `rxlost=0 rxfull=0
> rxpeak=2978`, `stall256=114`, `held=0 rel=0 hi=65535`, 18 packets, 0
> resends, 0 timeouts, 37,557 wire bytes, **31.324 s**. `peakat=7676`, which
> `mapoffset.py` puts 8 bytes into seq=08 — a packet boundary, where
> occupancy is always highest.
>
> **RESULT GB — CLEAN, AND IT MEASURES THE HOST, NOT THE VICTOR. See
> PORTING.md §16am: the host's C-Kermit has no `POSIX_CRTSCTS`, so nothing
> was listening. Every number below is right and none of it answers the
> question.** Byte-exact, `in=2 out=2
> hi=1024 lo=896`, **`held=11 rel=11`** (equal), `rxlost=0 rxfull=0
> stuck=0`, 18 packets, **0 resends, 0 timeouts**, 37,557 wire bytes —
> **identical to GA on every wire measure** — **31.459 s, 135 ms from its
> control.**
>
> **`rxpeak = 2,974` against GA's 2,978. Four counts.** `peakat=11674` is 7
> bytes into seq=09, another packet boundary. **The Victor dropped RTS
> eleven times and the far end did not pause once.**
>
> This is the leg DB failed to be, and the difference is the design: a
> narrow band gives a **cap** to read instead of a comparison, and a cap
> survives a retransmission. **When a leg keeps going off-shape, change what
> you ask of it, not how many times you ask.**
>
> `stall256` is **47 on GB and 114 on GA** — ordinary. §16ak's DB reported
> 2,399 and this sitting does not reproduce it, so that anomaly belongs to
> the 256/64 configuration (where the high mark and `V9K_RXSTALL` are the
> same number) and **is not evidence that anything paused.**

---

## After the sitting — **decided, 9 August 2026**

1. **`V9K_FLOW` stays `FLO_NONE`**, and `ckvictor.h`'s comment has been
   rewritten to say why with a leg number: the output half of RTS/CTS is
   inert on this cable, measured, not merely unverified. The input half
   works and is proven (§16ak leg DS, 1,475 cps).
2. **§16ak's +11% is withdrawn** everywhere it appears.
3. **Both mechanisms stay in the build.** Nothing about GB argues against
   carrying them — §1f costs ≤ 0.11 s on a 32 KB receive and the marks are
   above every occupancy this port has recorded.

### What would isolate the RTS fault, if it is ever worth isolating

Three candidates, and **no instrument in this tree points at any of them**:
the pin does not move, the cable does not carry Victor-RTS to host-CTS, or
macOS/FTDI does not act on CTS. The port's side is right as far as static
analysis reaches — WR5 bit 1 is RTS by `msxv90.asm`'s own
`DTR_RTS_OFF EQU 7DH`, the handler clears exactly that bit, and the 7201's
register pointer is at 0 when it writes the `5`.

- A **host-side `TIOCMGET` watcher** polling CTS against a **Victor-side RTS
  toggler** (a `v9k/probes/` one-shot) separates "macOS ignores CTS" from
  the other two. Neither exists.
- The **logic analyzer** on the Victor's RTS pin separates "the pin does not
  move" from "the cable does not carry it".

**It is not on the critical path** — the default is off and nothing needs
flow control at a window of one — **but it re-opens the moment `DFWSIZ` or
`DRPSIZ` moves**, because those are what flow control was a precondition
for.

### Still not run

- **The Victor obeying a real XOFF.** §16ak leg DX armed the path and the
  host never sent one.
- ~~**Whether XON/XOFF fares better at reaching this far end.**~~ **DO NOT
  RUN IT.** It would fail for the same reason GB did: the host's own
  XON/XOFF is disabled by `ckutio.c`'s `TESTING234` block, which clears
  `IXON|IXOFF` four lines before the `tcsetattr()` that would apply them.
  **Before running an experiment that depends on the far end behaving a
  particular way, measure that the far end can** — §16am.
- **A counter for the ISR's failed XOFF attempts**, the leading suspect for
  leg DC's 19 overruns.
- **The assert path under ring overflow**, and the `stuck` backstop.
- **Out of disk space makes the Victor hang rather than fail** (attempt 1
  above). A `KEEP_DEBUG` leg under MAME against a deliberately full image
  would diagnose it cheaply and safely.

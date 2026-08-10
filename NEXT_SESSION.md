# Next session

Handoff for the Victor 9000 port, written 9 August 2026, revised after
§16ah and then again at the desk the same day. **No live defect in the
receive path.** §16af closed the last one.

**`HW_TEST_16ai.md` RAN, 9 August 2026 — all seven legs, every transferred
file byte-exact, `rxlost = 0 rxfull = 0` throughout. PORTING.md §16ai is the
write-up.** In one sitting:

- **The prefixing fix is verified and it is exactly what was predicted.**
  Leg CC came back `PX_CAU exactly (32 values)`, **4,512 prefixes, 37,557
  wire bytes, +14.6%**; the control CD came back `PX_ALL exactly (66)`,
  8,869, 41,945, +28.0%. **4,388 wire bytes saved, −10.5%.**
  **CD reproduced §16ah leg BS on every measure** — prefixes, wire bytes,
  packet count, `rxbytes = 216` — with host clocks **29 ms apart** on a bench
  whose spread is 1.3 s. That is the best null leg this project has produced.
- **1,475 cps is the fastest figure the port has ever produced** (CC).
  But CC and CD are 1.397 s apart against a ~1.3 s floor, so **quote the
  wire-byte count as the result and the cps as an illustration.**
- **Server mode works on real hardware, a first.** Leg CS: SEND to the
  server 1,058 cps, GET from the server 1,431, then FINISH — both `SUCCESS`,
  both byte-exact, no E packet. `HW_TESTING.md` leg 0.7 is closed and item 13
  below with it.
- **The parser build transfers, a first.** Leg CH: 32,768 bytes at 38400,
  byte-exact, `rxpeak = 2,852 of 4,096`, 1,213 cps — inside the shipping
  build's band, so the wire protocol did not move. Item 7 is closed.

**The only two failures in the sitting were the run sheet's**, and both are
fixed. See "The harness had two defects" below — they are the kind that make
a working port look broken, so they are worth reading before the next
sitting.

---

## What changed at the desk, 9 August, after §16ah

**A shipping-behaviour defect was found and fixed, and item 5a is
superseded.** `ckvictor.h` has selected `PX_CAU` prefixing since §16ae and
**every leg this project has ever run sent `PX_ALL`.** `main()` reaches
`initproto(PROTO_K,...)` at `ckcmai.c:3295` before `setprefix(prefixing)` at
3413, and `initproto` copies `ptab[protocol].prefix` — statically `PX_ALL`,
and `PX_ALL` is 0 so the `> -1` test passes — over whatever the XI
initializer put in the variable, 118 lines before anything reads it.
Upstream knows this about its own ordering: `ckcmai.c:3319` says
`compat_9()`/`compat_10()` run *"after initproto calls so initial file
transfer settings are not overwritten"*. **An XI record runs before `main()`,
which is the one position from which that guarantee does not hold.** Fixed
by writing `ptab[PROTO_K].prefix`, which is what `initproto` copies *from*.
No upstream edit — still seventeen. **Unverified on the wire; that is legs
CC/CD.**

**How it was found generalises, and it is the reason `pktstat.py` was
rewritten first.** Not by reading the source — the source had been read
twice and produced the comment the fix replaces — but by decoding the prefix
characters out of `s16ahBS.pkt`. **A run's `ctlp[]` table is recoverable from
the wire**, because every value the sender prefixed appears after a QCTL.
Leg BS prefixed exactly the 66 values `setprefix()` sets for `PX_ALL`; the
host, over the identical fixture in the same session, prefixed exactly the 32
it sets for `PX_CAU`. **A setting that is applied and then quietly
overwritten looks exactly like a setting that was never right; only the wire
tells them apart.**

**`pktstat.py` reads send legs now, and counts wire bytes.** It measured only
the lines the log-writer *sent*, so on a send leg it reported the host's ACK
stream — "longest 49, retransmissions 0" for a log whose longest packet is
3,716 and which holds four Victor resends. Both halves fixed. A remote
retransmission has no marker of its own; it is the same sequence number
arriving twice running. **`--rxbytes` reconciles the log against the Victor's
ISR counter**, which counts the same bytes by an independent route:
`host wire bytes − rxbytes = rxfull + startup offset`. On §16af leg AJ that
residual is **exactly the 741 `rxfull` that leg published**; on a clean leg it
is −11, or +28 where a startup timeout means the Victor missed the first S
packet.

**Two of §16ah's published figures are withdrawn.** Its send/receive table
gives 40,726 and 35,950 wire bytes, +24.3% and +9.7%. Counted from the logs
— and cross-checked against `rxbytes` to the byte on leg BC — they are
**41,945 (+28.0%)** and **37,585 (+14.7%)**. The 14.7% is what §1 item 9
already quotes for this fixture, so §16ah's table was the outlier. **The
conclusion survives and is now correctly attributed**: it is `PX_ALL`
measured against `PX_CAU`, not two ends disagreeing about one policy.

**Item 7.0 is done.** `CKICP.EXE` and `CKICPD.EXE` are rebuilt from HEAD,
re-measured and staged: **435,154 / needs 429,890 (419K) / smallest Victor
512K with 1,678 bytes spare**, and **546,422 / needs 533,110 (520K) /
smallest Victor 640K**. The stale 8 August copies are gone. `CKPXALL.EXE` is
new — the same tree and the same 205,228 bytes as `CKERMITW.EXE`, differing
only in one immediate constant, which makes it a control with **no code-size
difference at all** for §16w to bite on.

---

**Flow control is built, run on the machine, and shipped OFF — PORTING.md
§16aj (build), §16ak (seven bench legs), §16al (four more).** RTS/CTS and
XON/XOFF, both directions, both interrupt handlers, `tcflow()` implemented,
`--rtscts` / `--xonxoff` / `--noflow`, **no upstream edit**. Eleven bench
legs, every transferred file byte-exact, `rxfull = 0` throughout.

**Two results decide it, and they point opposite ways:**

- **It is free.** §1f costs **≤ 0.11 s on a 32 KB receive** — leg GP, the
  pre-§1f binary, has a non-line cost of 21.43 s against the shipping
  build's 21.54 (§16al) — and turning RTS/CTS on at the shipping marks was
  **6 ms** from its control (§16ak leg DE). The CTS gate on the
  transmitter's per-byte path ran at **1,475 cps**, the port's fastest
  figure (§16ak leg DS).
- **The output half has never been tested.** §16al leg GB dropped RTS
  **eleven** times on a clean byte-exact leg and `rxpeak` came back **2,974
  against its control's 2,978** — and **§16am retracts it**: the bench
  Mac's C-Kermit has no `POSIX_CRTSCTS`, so its `tthflow()` is empty and
  `set flow rts/cts` never configured the port. The far end was never able
  to pause. `HW_TEST_16am.md` is the leg that answers it without Kermit.

So `V9K_FLOW` stays `FLO_NONE` for a *measured* reason. §1 item 11 has the
three remaining candidates for the RTS fault and the one cheap leg left
(`--xonxoff` at 1024/896 against a `--noflow` control). Shipping build:
DGROUP **48,336 (73%)**, image **206,758**, **needs 220,950 (215K)**,
smallest Victor **384K, unchanged**, md5 `c5652a5b…`.

**§16ak's "+11% for §1f" is WITHDRAWN.** The same `CKPRE` binary had a
non-line cost of 18.29 s in §16ah and 21.43 s in §16al, wire held constant
— **the bench's run-to-run spread is the host, not the Victor**, which is
also the standing answer to §1 item 5b.

**Two upstream defects came out of it and neither is fixed** (§1 item 8):
`ttpkt()`'s `TESTING234` block clears `IXON|IXOFF` four lines before the
`tcsetattr()` that applies them, and the only call to `tcflow(TCOON)` in
`ckutio.c` sits inside a `debug()` argument that `NODEBUG` deletes. **Do
not quote `ckutio.c:6252`/`:6617` as "the plumbing is already there"** —
that claim, which lived in this file, was wrong in both halves.

**Three harness failures cost three sittings in this sequence and each is
now a rule rather than an anecdote:** a re-run into a target name that
already existed (`SET FILE COLLISION BACKUP` cannot work on FAT — put
`IF EXIST <target> DEL <target>` in every receive `.BAT`); a run sheet that
named a `-d` flag without staging the binary that carried it; and **a full
image**, which makes a working port look thoroughly broken — eleven packets,
then a hang, on a binary that had transferred cleanly twice before.
**`vtg_image_util info <img>` goes in every run sheet's §0**, and partition
1 (`D:`) is 9.7 MB, 100% free, and has never been used.

What is open is *verification* rather than repair, and the ordering in §1
reflects that.

**§16ah ran `HW_TEST_16ag.md`'s seven legs and §1 items 1, 2 and 4 are
closed.** All seven byte-exact, `rxlost = 0 rxfull = 0`, host clock captured
on every one. What changed:

- **Upstream edit 16 is verified** (leg BS) — the port's last shipped edit
  with only a `wdis` reading behind it.
- **The `errno` change is removed**, under the rule written before the legs
  ran. It measured slower on both instruments.
- **§16af's CRC-16 cost is superseded** — 69–103 µs per wire byte, not 26.
- **The bench does not repeat to better than ~1.3 s**, which is the fact that
  governs every future A/B on it.

**Read `PORTING.md` §16ah first** — seven bench legs, a closed edit, a
removed change, and a retraction of §16af's headline number — then §16ag for
the two free items of which only one was free, then §16af — the seventeenth upstream edit, the
bench legs that measured it, and three prediction failures that generalise
— then §11a0 for the clock tree and why 38400 is a hardware ceiling, then
§16ae for the block-check analysis §16af rests on. §16t is still the best
thing in the file for its four wrong turns.

**One thing to understand before reading any number below.** The Victor's
clock advances in 50 cs steps, so a one-second difference between two legs
is *one quantum*. §16ah captured the host's millisecond clock on all seven
legs and **the quantum turned out not to be the binding limit — the bench's
own run-to-run spread is.** Two legs of one binary, both clean, eleven wire
bytes apart, came back **1.277 s apart**, where §16ag's MAME arms held to
1 ms. So: **do not make a bench claim about an effect smaller than ~1.3 s
on two legs per arm**, and expect roughly a third of legs to go off-shape
and be unusable for an A/B. That is what retired §16af's "one clock
quantum" (see §16ah), and it governs everything below.

**§16ak is a second data point and it points the other way: 398 ms.** Three
protocol-identical clean receive legs came in at 31.137, 31.143 and 31.535 s
on the same 37,557 wire bytes, and the closest two are **6 ms** apart; the
two send legs are **3 ms** apart. So ~1.3 s is a **bound and not a floor**,
whatever causes it is intermittent, and item 5b is still open with one more
sitting to compare. **Do not relax the rule on one sitting** — but do check
the actual spread of your own null pair before deciding an effect is
invisible.

**And §16aj shows MAME is not automatically the quiet instrument either.**
Its two groups of legs, same fixture and same rate, drifted **12–15 s
apart** because the host machine got busier — the host's own timeout count
went 3 → 5 and C-Kermit's slow start then chose a different packet shape,
24 packets and a longest of 3,991 early against 38 and 3,387 late. §16ag's
1 ms was a property of that sitting, not of the emulator. **Run the control
adjacent to the treatment and compare nothing across a gap.**

---

## 0. Where the port is

**File transfer works, both directions, as client and as server, at 9600,
19200 and 38400, on real hardware, byte-exact.** At 38400 with CRC-16
intact it **receives at ~1,167 cps and sends at 1,386** (§16ah legs BC and
BS) — the send figure is the fastest this port has produced, and sending
beats receiving by 19% *while carrying 13% more wire traffic*, which is the
receive foreground being the bottleneck seen from the other side. **Read
those two against §1 item 5b before differencing them with anything: this
bench does not repeat to better than ~1.3 s.** §16af leg AG, for the
counter shape:

```
v9k: isr=asm
v9k: rxlost=0 rxfull=0 rxpeak=2581 of 4096
v9k: peaktag=12 fd=6 stall256=27
v9k: rxbytes=37568 peakat=15673 stallat=840
v9k: elapsed=2800 cs wire=1341 B/s
v9k: mdm cts=1 dsr=1 (dcd=1 rts=1 dtr=1, see comment)
```

18 packets, longest 3,991, zero NAKs, zero retransmissions, zero timeouts.
cps here is 32,768 ÷ the Victor's `elapsed`, which is the wider interval
(§16u) and therefore conservative. **Leg AG's own host figure was never
captured** and the estimate of ~1,245 that used to sit here should not be
used: §16ah measured the same binary and block check properly (legs BC/BD,
28.057 and 29.334 s) and found the run-to-run spread larger than the
estimate's precision.

**§16af closed the ring defect and dissolved §16ae's trade-off.** Upstream
edit 17 rewrites `chk3()` for `VICTOR9K` — same CRC-16, same polynomial,
same init, no final XOR — in `unsigned int` through one 256-entry table
instead of in `long` through two `long[16]`. On an 8088 built with `-0` the
old form put **two software shift loops** on the per-byte path; 603 cycles
became 81. Measured against a same-session baseline control that reproduced
§16ae leg PC **to the byte**:

| | AJ (baseline × 3) | **AG (edit 17 × 3)** | AH (edit 17 × 1) |
|---|---:|---:|---:|
| `rxfull` | **741** | **0** | 0 |
| `rxpeak` | 4,095 *pinned* | **2,581** | 2,585 |
| `rxbytes` | 44,720 | **37,568** | 37,534 |
| packets / resends | 26 / 3 | **18 / 0** | 18 / 0 |
| `elapsed=` | 3,800 cs | **2,800 cs** | 2,700 cs |

**CRC-16 now costs one clock quantum over a 6-bit checksum** (28.00 vs
27.00 s) where it cost 11.5 s, so there is no speed argument left for
shipping weaker error detection. All four legs (three bench, one MAME)
byte-exact.

**What that leaves.** `rxpeak` at 2,581 of 4,096 means **the ring is no
longer the binding constraint** and §16k's sizing argument no longer needs
redoing. `peaktag = 12` still names foreground packet decoding. Line time
is 9.77 s of AG's 28.00, so the foreground is ~485 µs per wire byte and the
**no-line ceiling is ~1,797 cps** (AH's is ~1,900). §16v's ~1,353 is
superseded.

Also standing from §16v: **`cts = 1` on the real cable**, so RTS/CTS is
available *inbound* and flow control does not have to be XON/XOFF. §16aj
built both and left the default off; the outbound half — our RTS at the
host's CTS — is still unmeasured and is what item 11 now turns on.

**Flow control exists and is switched off** (§16aj, `ckvictor.c` §1f) —
RTS/CTS and XON/XOFF, both directions, in both handlers, `tcflow()`
implemented, four instructions per byte in the ISR. §1 item 11 is the one
leg that decides whether the default changes.

**Seventeen** upstream edits, fourteen of them guarded no-ops elsewhere.
**14, 15 and 16 are the exceptions and are flagged as such** — 14 moves a
mis-nested `#endif` (which cannot be placed conditionally), 15 and 16 each
fix a 16-bit truncation and are provable no-ops wherever `int` is 32 bits.
Edit 17 is guarded even though it did not have to be, because it is an
optimisation for one CPU and not a defect fix.
DGROUP **48,336 of 65,536 (73%)**, image **206,758**, **needs 220,950
(215K) at load — smallest Victor 384K** (§16aj; it was 48,304 / 205,212 /
219,452 through §16ai, and the smallest machine did not move).

**§16y built the interactive command parser.** `XFLAGS=-dKEEP_ICP
ZT=-zt2048` links, loads on the Victor and prints a parser's help text —
**429,890 (419K)** at load — **smallest Victor 512K** — against the shipping
build's 219,452 (384K). **It is a feature this port intends to ship, not an
instrument**; `NOICP` is a default chosen because 384K reaches three times
as many machines, not a verdict that the parser cannot be had. Three fixes,
no upstream edit: `isfloat()` (§2b), `__near` on the receive ring, and the
threshold. **§16z, §16aa and §16ab regression-tested it on the machine.**
Four defects, all latent for the port's whole life and none reachable
without the parser, all fixed in `ckvictor.c` for no upstream edit:

- one cached `struct termios` for the console and the line, so `SET SPEED`
  did not stick (§16z);
- `ttyname()` said every descriptor was `CON:`, so `SET LINE` left the
  program in remote mode (§16aa) — **fixed and confirmed on hardware**,
  `SET LINE local=1`, and `SET SPEED 19200` now reads back;
- no `ICRNL` on console input (§16aa) — fixed and confirmed, `gtword` is
  handed 10 — but **the overprint is still there**, so that was not the
  whole story and §16ab has what is left of the theory;
- `getcwd()` returned `A:\`, and upstream joins paths with `/` without ever
  testing for a separator already on the end, so `zfnqfp()` built
  `A:\/NAME` (§16ab). **That is what broke `CKICP FILE.KSC`.**

`KEEP_SPL` adds the script language for a further **+209,052**, and is
probably not worth it — `TAKE` is on the cheaper switch.

**§16x retracted the memory figure this project had used since §16a.**
396,224 was a FreeDOS measurement filed under an MS-DOS 3.1 heading; Victor
MS-DOS 3.1 gives **824,784 at 896K**, and the model is `free = installed RAM
− 92,720` because this DOS loads high. Measured at 256K and 896K; predicted
and confirmed that `CKERMITW` **does not load on a 256K machine** and does
on 512K. **Quote the requirement, not the spare** — `mzsize.py` now prints
the smallest Victor that can load a build, and that is the number to report.

---

## The harness had two defects, and both made a working port look broken

**1. The machine takes 40–85 seconds to start, and the host gives up first.**
`CKERMITW` is 205 KB and `CKICP` is 435 KB, read off SASI before `main()`
runs. On any leg where the **host** initiates, starting it too soon exhausts
`MAXTRY` (10, `ckcker.h:472`) against a Victor that has not reached `receive`
yet — **and a host that gives up looks exactly like a Victor that failed.**
Leg CE's timeout and leg CH's first attempt were both this. Fixed twice
over: the run sheet now states the wait explicitly, and every host take-file
where the host initiates carries `set retry 30`.

**2. The parser build asks two questions, and the redirect hides them.**
` Accept incoming file "A:/rcvch.dat"? ` and ` OK to exit? `. Redirected to
`STEP<LEG>.OUT` — which is *required*, because the `v9k:` counters only reach
stdout — both sit unanswered forever and the leg looks like a hang. `RXEA.KSC`
now carries `set receive confirm off` and `set exit warning off`.

**The mechanism is worth knowing, because it says something about the
shipping build too.** `fnrconfirm` is `CONFIRM_ON` **by default**
(`ckcmai.c:1408`), scope `LOCAL`, and a Victor driving its own serial line
*is* local — so `rq_confirm_check()` (`ckcfns.c:3567`) reaches the prompt on
**every `RECEIVE` this port has ever run.** `NOICP` builds survive only
because `ckvictor.c` supplies a `getyesno()` that returns yes; a `KEEP_ICP`
build links upstream's instead (`W1027`, decided by link order).

**So that stub is load-bearing and its comment said it was unreachable.**
Corrected in place. **A stub whose comment says it is unreachable has, by
construction, no test proving it** — this one was on the path of every
single receive leg in the project's history.

**And the general defect: the sheet optimised for capture, not visibility.**
Three artefacts per leg, all written to files, nothing on screen to say what
the machine was doing. Fine while everything works, useless the moment it
does not. **If a leg seems to hang, run the Victor side by hand without the
redirect before concluding anything** — that is how CH was diagnosed, and
what was behind the hang was a completely successful transfer.

---

## 1. Do this next, in priority order

**Items 1 through 4 are closed and item 5 is a standing decision, not a
task.** §16af emptied the repair queue, §16ag took the two cheap code
levers, and §16ah spent the bench sitting that items 1, 2 and 4 were
waiting for. What is left starts at **5a**, and the honest summary of it is
that the port has no known defect and no cheap lever — every remaining item
is either a measurement whose instrument is in question (5a, 5b, 9), a
feature nobody has needed yet (11, 12), or a confirmation run (7, 13, 14).

**Read item 5b before planning any of it.** The bench does not repeat to
better than ~1.3 s, which is larger than several of the effects the items
below propose to measure — including 5a's. Where that bites, the way out is
usually a counter rather than a clock.

---

**1. ~~Repeat legs AG and AH with the `.host` redirect.~~ DONE — §16ah legs
BA/BB, and the answer was not the one this item expected.**

The host clock was captured on all seven legs. BA failed to reproduce AG
(1 timeout, 2 resends, 40,555 wire bytes); **BB reproduced §16ae leg BX to
the byte** (37,523). The block-check cost therefore came from BB against
the clean block-3 legs BC and BD, same binary, same session:

| | block 1 | block 3 | Δ | µs / wire byte |
|---|---:|---:|---:|---:|
| BB → BC | 25.475 s | 28.057 s | **2.582 s** | **68.8** |
| BB → BD | 25.475 s | 29.334 s | **3.859 s** | **102.7** |

**§16af's 1.00 s / 26 µs / "at most 3.7%" is withdrawn. CRC-16 costs 10–15%
of the transfer.** Its conclusion survives — 10–15% is not 43%, and the case
for CRC-16 was never a speed case — but the number must not be quoted again.

**The µs-per-8088-cycle constant this item asked for was not obtained**, and
the reason is the bench spread above: the effect and the noise are the same
size. Getting it needs more legs per arm, not a better clock.

**2. ~~Send a 32 KB file BY NAME.~~ DONE — §16ah leg BS, and it delivered
both results it was sent for.**

**Upstream edit 16 is closed.** `-s RCVAG.DAT` on a file of exactly 32,768
bytes — inside the broken range — transferred byte-exact with **no error
line in `STEPBS.OUT` at all**. The signature it was watching for (`kermit
-s NAME:` with an empty message) did not appear. It was the last shipped
edit in this port with only a `wdis` reading behind it.

**And the port has a send measurement for the first time: 1,386 cps, the
fastest figure it has ever produced.**

| | sending (BS) | receiving (BC) |
|---|---:|---:|
| wire bytes for 32,768 | **40,726 (+24.3%)** | 35,950 (+9.7%) |
| non-line cost | **13.04 s** | 18.71 s |
| no-line ceiling | ~2,512 cps | ~1,751 cps |
| **cps** | **1,386** | 1,167 |

Sending beats receiving by 19% **while carrying 13% more traffic**, which
confirms from the other side that the receive foreground is the bottleneck.
**The open question it opens is item 5a.**

**3. ~~`NOCKXXCHAR`.~~ DONE AND SHIPPED, §16ag.** `ckcdeb.h:3390` turned
`CKXXCHAR` on for any build defining `UNIX`, putting a test on `ttinl()`'s
per-byte loop whose only setters are behind `#ifndef NOICP` and which could
therefore never be true. Now defined in `ckvictor.h`.

| | before | after | Δ |
|---|---:|---:|---:|
| DGROUP | 48,816 (74%) | **48,304 (73%)** | −512 |
| file | 205,968 | 205,212 | −756 |
| needs at load | 220,160 (215K) | **219,452 (214K)** | −708 |

Those are the shipping figures today. −512 is exactly `short dblt[256]`,
repaying edit 17's CRC table to the byte;
`wdis` confirms `ignflag`/`dblt` leave `ckutio.obj` entirely; 19 warnings
unchanged. The throughput half is measured too: **−1.07 s, 2.1%, at 9600
under MAME**, two legs reproducing to 1 ms.

**It is `#ifndef KEEP_ICP`.** The first version shipped it unconditionally,
taking `SET SEND DOUBLE-CHARACTER` and `SET RECEIVE IGNORE-CHARACTER` out
of the parser build to save DGROUP in a build that has no parser — on an
invented premise that the parser is only an instrument. **It is a feature
this port intends to ship**; `ckvictor.h` calls `NOICP` the removal of "the
one thing this port most wants back". Guarded, `KEEP_ICP` needs **429,890
(419K), smallest Victor 512K** — the same smallest machine either way, so
the two commands cost margin, not reach.

**Read the 2.1% carefully, because §16ag does not claim it is the test.**
The change removes two instructions from the loop *and* 512 bytes of DGROUP
*and* 756 of code, and at 9600 the foreground has 555 µs of slack per byte,
so per-byte savings have room to hide. The size is the more likely
mechanism. The direction is not in doubt on any reading; the attribution is.

**4. ~~The `errno` far call.~~ REMOVED — §16ah leg 3. Do not reopen it
without reading that section first.**

Built in §16ag, verified in `wdis` (27 far calls leave `ckutio.obj`),
measured **98 ms slower** under MAME at 9600 and **350 ms slower** on the
bench at 38400 on the best-matched pair the harness can produce — BC against
BE, identical `rxbytes` (37,557), identical packet count, both 0/0, one
binary difference. Removed under the decision rule written into
`HW_TEST_16ag.md` *before* the legs ran.

**The caveat, so it is not discovered later:** the treatment arm was n = 1.
Leg BF went off-shape and was excluded. The decision rests on BE being the
best-matched leg available *and* on MAME agreeing. The way back is one
`git revert` and one more pair of legs.

**What it means for `ttinl()`:** the loop's per-byte cost is now known to be
resistant to two separate attacks (§16ag's `NOCKXXCHAR` gain is probably its
*size*, not its instructions; the `errno` far call removal is a measured
loss), which strengthens item 5's argument rather than weakening it.

**5. Do NOT spend edit 18 on `ttinl()`, and do not strip the ISR
counters — reasons, so the decision does not get re-litigated.**

What is left in `ttinl()`'s loop after items 3 and 4 is a redundant
double-mask and double-store of the same byte, and a `DS` reload for the
far destination pointer. A `VICTOR9K` fast path could collapse it. It is
still the wrong trade: it is the **packet reader**, stateful, with six
early-exit paths, whose failure modes are resync and truncation — things a
byte-exact transfer can *pass* while being subtly wrong. `chk3()` was
justifiable because it was self-contained arithmetic checkable exhaustively
on the host in milliseconds, and because computing a 16-bit CRC in `long`
is wrong everywhere and merely free on 32-bit machines. `ttinl()` is not
wrong; it is general. And with the ring no longer under pressure this buys
cps, not correctness — which is the thing §16ae showed this port
over-values.

The ISR's per-byte instrumentation is ~142 of ~678 cycles (the 32-bit
`rxbytes` add/adc, the occupancy subtract, the `rxpeak` and `stall256`
compares). **`rxfull` and `rxpeak` are the instruments that found and
confirmed the defect edit 17 just fixed**, and §16k put them in every build
because a run fast enough to measure cannot carry a debug log. If it is
ever worth doing, drop only the 32-bit `rxbytes` counter (it exists to give
`mapoffset.py` byte offsets) and keep the two that matter.

**5a. ~~Run a Victor send with `cautious` prefixing.~~ SUPERSEDED — the
Victor was never running `cautious`, and the fix is in the tree awaiting
legs CC/CD of `HW_TEST_16ai.md`.**

This item proposed running the arm it believed was already running.
`ckvictor.h` selects `PX_CAU`; `initproto()` overwrote it with `PX_ALL`
before anything read it; §16ah leg BS's "+24.3% against the host's +9.7%" is
therefore `PX_ALL` measured against `PX_CAU` and not two ends disagreeing
about one policy. The header of this file has the mechanism. **The figures
themselves are also withdrawn — 41,945 (+28.0%) and 37,585 (+14.7%) counted
from the logs, against `rxbytes` to the byte on leg BC.**

**What survives, and it is the part worth carrying forward:**

- **Run it as a wire-byte comparison, NOT a timing A/B.** The effect is
  ~4,400 wire bytes, ~1.1 s of line time at 38400, **below item 5b's ~1.3 s
  noise floor**. The clock cannot resolve it and more legs will not change
  that. `pktstat.py` counts prefixes and wire bytes exactly. **When the
  bench cannot resolve an effect in seconds, look for a counter that
  measures the same mechanism in units that do not vary.**
- **`PX_CAU` puts control characters on the wire raw**, which is the point
  of it and also the only way it can go wrong. `cmp` before the counts: a
  leg that is fast and wrong is the failure mode. XON/XOFF stay prefixed
  under `PX_CAU` regardless (`ckcmai.c:2731`), so flow control is not the
  exposure.
- **The control costs nothing extra.** `CKPXALL.EXE` is the same tree and
  the same 205,228 bytes, differing in one immediate constant, so §16w's
  code-size sensitivity has no purchase — unlike §16af, which had to spend a
  whole null leg establishing that.

**5b. Find out why this bench does not repeat, or stop quoting differences
smaller than 1.3 s.**

§16ah legs BC and BD: same binary, same block check, both 0 timeouts and 0
retransmissions, `rxbytes` **37,557 against 37,568** — and **1.277 s apart**.
BE and BF, same binary as each other, 1.310 s apart. §16ag's MAME arms held
to **1 ms and 5 ms**. So the bench's spread is ~250× the emulator's, and it
is the same size as the effect §16af tried to size and 5× the effect §16ag
tried to detect. **2 of 7 legs went off-shape** (1 timeout, 2 resends,
~40,55x wire bytes), against 1 of 7 under MAME.

Ruled out already: **the ring.** `rxpeak` is 2,4xx–2,6xx and `rxfull` is 0 in
every leg. Untested candidates: the host's round-trip estimator making
different decisions run to run (§16l established every timeout in these logs
is the host's, so this is the leading one), thermal or cable variation, and
the Pico SASI's write timing.

**Until this is understood, the rule is arithmetic and not judgement: an
A/B on this bench needs enough legs per arm that the standard error is below
the effect, and two is not enough for anything under ~1.3 s.**

---

### Standing items, renumbered 6 onward after §16af

**6. ~~The x1 sweep.~~ CLOSED 8 August 2026. Do not reopen it without
reading PORTING.md §11a0 first.**

**39,062.50 bps at count 2 is the hardware ceiling, and the port has shipped
it since §16o.** `bps = 1,250,000/(16 x count)`, count >= 2 because the 8253
is in Mode 3, and the operator traced the sheet: **the only path to the
7201's RxCA is through the 74LS90 chain** — no fixed tap around the 8253, no
external clock from the connector. The LS153 selects among LS90 outputs, not
around them.

x1 was tried properly and is not the way past it. It is a real async mode —
the datasheet permits it and a 32 KB **send** at x1 completed byte-exact —
but x1 *receive* accepted 33% of 110-byte packets where x16 was clean at a
three times worse rate mismatch, and closing the rate gap needs the two ends
matched to ~100 ppm against an FTDI that tunes in ~400 ppm steps.

`B57600`/`B76800`/`B115200` are **removed** from `victor/sys/termios.h` and
`__MAX_BAUD` is back to `B38400`. That removal matters: `ttspdlist()`,
`ttsspd()` and `ttgspd()` all key off those `#define`s, so defining one is
enough to let `SET SPEED` and `-b` offer a rate that cannot transfer.

The `XFLAGS="-dV9K_CLKBITS=0x00 -dV9K_COUNT=<n>"` override survives, so the
experiment is repeatable without shipping a broken speed.

**Three things are measurements now that were assumptions a week ago**, and
they are the value of the exercise: the 8253 sees exactly **1,250,000 Hz**
(LS153 15F pin 7, two counts, same product — which also settled the
1.25 vs 1.2288 MHz argument that ran through four documents); **every rate
on this machine is 1.72% fast** and no integer count fixes it, which is what
the x16 control's six errors in 32 KB were showing; and x1's envelope is
`P(packet) = (1 - 9 x rate_error)^L`.

**7. Run the hardware leg for the parser. Verified under MAME.**

**7.0 — ~~PRECONDITION: rebuild and re-stage.~~ DONE 9 August 2026.** Both
binaries are rebuilt from HEAD, re-measured, staged and round-trip verified:
`CKICP.EXE` **435,154, md5 `f5456cae…`, needs 429,890 (419K), smallest
Victor 512K** with 1,678 bytes spare, and `CKICPD.EXE` **546,422, md5
`6d991fc7…`, needs 533,110 (520K), smallest Victor 640K** — which re-measures
the stale "532,904 / 640K" figure rather than re-quoting it. The rest of this
item is now `HW_TEST_16ai.md` legs CF, CG and CH. **The reasoning below is
kept because it is why the rebuild mattered, and because the same trap will
exist again the next time a binary sits on the image across an edit.**

| | landed | in the staged parser binaries? |
|---|---|---|
| edit 16 — `-s <name>` ≥ 32K | `d840218`, 8 Aug 17:49 | **no** |
| edit 17 — fast `chk3()` | `4610f2e`, 9 Aug 07:57 | **no** |
| §16ag `NOCKXXCHAR` (now `#ifndef KEEP_ICP`) | 9 Aug | no, and it is a wash — the guard means the parser build keeps `dblt` either way |

**Edit 17 is the one that matters and it is a trap, not an inconvenience.**
Without it, `chk3()` computes the CRC in `long` through two `long[16]`
tables, which is precisely the defect §16af found: at 38400 with block check
3 it pinned `rxpeak` at 4,095 of 4,096 and lost 556–649 bytes on three legs
of four. **The transfer leg below is at 38400.** Run it against the staged
binary and you would reproduce §16af's ring defect and read it as *"the
parser build breaks transfers"* — a wrong conclusion that would look
thoroughly convincing, because `rxfull` would be non-zero and the resends
real. Edit 16's absence is milder but the same shape: `-s <name>` on the
32 KB fixture would fail for a reason that has nothing to do with the parser.

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak clean && \
   make -f victorow.mak XFLAGS=-dKEEP_ICP ZT=-zt2048"
cp ckermitw.exe ckicp.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak clean && \
   make -f victorow.mak XFLAGS='-dKEEP_ICP -dKEEP_DEBUG' ZT=-zt2048"
cp ckermitw.exe ckicpd.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak clean && make -f victorow.mak"

python3 v9k/tools/mzsize.py ckicp.exe ckicpd.exe      # RECORD BOTH
IMG=~/projects/mame/victor_kermit.img
vtg_image_util copy ckicp.exe  $IMG:0:\\CKICP.EXE
vtg_image_util copy ckicpd.exe $IMG:0:\\CKICPD.EXE
```

**Measured from HEAD for the plain parser build, 9 August:** file 435,154,
DGROUP **59,024 of 65,536 (90%)**, needs **429,890 (419K)**, **smallest
Victor 512K**, 26 warnings. **`CKICPD` has not been rebuilt** — the 532,904
/ 640K figure quoted below and in §6 is the 8 August number and should be
re-measured, not re-quoted.

Then the leg itself. §16ad ran the whole sequence under MAME, so hardware is
confirmation rather than discovery: `CKICPD SPDTEST.KSC -d` and `CKICPD A:\SPDTEST.KSC -d` both
run the script; `SET LINE` reports local; **`SET SPEED 38400` and 19200 both
read back**, with `tcsetattr divisor=` 2 and 4; `SHOW VERSIONS` names the
machine; and the prompt echoes a typed line exactly once.

```
STEPSPD                       (at A>)
CKICPD -d                     (at A>)
take spdtest.ksc              (at the C-Kermit> prompt)
REN DEBUG.LOG SPD3.LOG        (at A>, after Kermit exits)
```

The image was cleaned of `SPD*` and `DEBUG.LOG` after the MAME run, so the
`REN`s will succeed.

What MAME could not settle:

- **Extended keys.** The console now reads INT 21h AH=07h. Whether the
  Victor's keyboard driver uses the 0-then-scan-code convention is unknown,
  so a function or arrow key may deliver a stray NUL. Nothing in this build
  wants arrow keys; it is a "do not be surprised" note.
- **The echo control.** The pre-§16ac binary has never been under MAME, so
  §16ad shows the fix behaving correctly rather than the bug reproducing and
  then going away.
- **A transfer.** Edit 14 widened what `main()` compiles and the shipping
  binary is no longer the one measured at 1,170 cps. `dofast()` is guarded
  out on purpose (§8 item 14), but one 32 KB leg reporting `rxlost=0
  rxfull=0` and a byte-exact md5 is what says the wire protocol did not
  move.

**8. Report edits 14, 15, 16 and 17 upstream — plus the two `ckutio.c`
defects §16aj found and did NOT fix.**

The two new ones are flow control's, they are not 16-bit defects, and
neither is specific to this port:

- **`ckutio.c:6758`** — `ttpkt()`'s `TESTING234` block clears `IXON|IXOFF`
  out of `ttraw` unconditionally, four lines before the `tcsetattr()` that
  applies it and 141 lines after the `FLO_XONX` arm set them. `SET FLOW
  XON/XOFF` therefore cannot reach a driver through termios on any build
  taking the `BSD44ORPOSIX` arm. It is an `if (1)` inside an `#ifdef` of
  its own `#define` — a debugging block left switched on. **Not fixed
  here: it is not a guarded no-op, it changes behaviour everywhere, and
  hard rule 1 says say so rather than do it.**
- **`ckutio.c:10849`** — `ttoc()`'s `tcflow(ttyfd,TCOON)`, the POSIX
  recovery from a lost XON, is the argument of a `debug()` call, so
  `NODEBUG` discards it. It is the only caller of `tcflow()` in the
  module. `ckvictor.c`'s `V9K_FCSPIN` is the port's own backstop for it.

Then the four edits. Two independent defects, both found only because this
port is an unusual build, and neither specific to it:

- **14** — `ckcmai.c`'s `#ifndef NOTCPIP` has been mis-nested for a very
  long time and disables two documented features, the init file and a
  command file named on the command line, in every configuration that turns
  TCP/IP off. §8 item 14 and §16ac have the analysis, including why the
  drifted-closer reading is the right one. Item 8 of this list used to
  cover the `dofast()` half of the same region; one report now.
- **15** — `ckuus5.c`'s `(int) ss[i] / 10` casts before dividing, so `SET
  SPEED` is broken for every rate above 32767 on any 16-bit target. §8
  item 15.
- **16** — `ckuusy.c:3690` stores `zchki()`'s `CK_OFF_T` return, which is
  the *file size*, in a 16-bit `int`, so `-s <name>` refuses any file of
  32,768 bytes or more. **Made, and now run** — §16ah leg BS sent exactly
  32,768 bytes by name, byte-exact, no error line. `wdis` confirms a signed
  32-bit compare where `dx` used to be discarded.
- **17** — `ckcfn2.c`'s `chk3()` computes a 16-bit CRC in `long` through
  two `long[16]` tables. Correct everywhere, and on any 16-bit target with
  no shift-by-immediate it costs two software shift loops per byte. **This
  one is different in kind from 14–16**: they are defects, it is an
  optimisation, and the `#ifdef VICTOR9K` guard is there for that reason
  rather than from necessity. Offer it as a portability improvement with
  the measurement attached (§16af), not as a bug report — upstream has no
  obligation to carry a second table for one CPU.

All three are the same species: a value that needs more than 16 bits
assigned to an `int`. A 16-bit build is the only place they show, which is
why this port keeps finding them.

**8a. `-s` for files of 32,768 bytes or more — the analysis, kept because it
is what to send upstream. VERIFIED ON HARDWARE, §16ah leg BS.**

```c
int fil2snd, rc;                                   /* ckuusy.c:3690 */
...
if ((rc = zchki(*xargv)) > -1 || (rc == -2))       /* ckuusy.c:3726 */
```

`zchki()` returns `CK_OFF_T` — **4 bytes here, measured** — and on success it
returns the **file size** (`ckufio.c:2477`). Assigned to a 16-bit `int`, a
32,768-byte file becomes **-32768**, which is neither `> -1` nor `-2`, so the
send falls through to the failure branch. `zchki()` had *succeeded*, which is
why the error line reads

```
kermit -s TRANS.DAT:
```

with nothing after the colon: nothing set `errno`, because nothing failed.
**An empty `ck_errstr()` on that line is the signature** — it means the file
was found and the caller threw the answer away.

It is periodic, not a simple threshold, because the wrap repeats every 64K:

| size | as int16 | `-s <name>` |
|---:|---:|---|
| 32,767 | 32,767 | works |
| 32,768 | -32,768 | **fails** |
| 65,535 | -1 | **fails** |
| 65,536 | 0 | works |
| 98,304 | -32,768 | **fails** |

**Why it went four sections unnoticed.** §16d sent `TESTFILE.TXT`, 74 bytes.
§16g used `-s *.TXT`, and wildcards take the `nzxpand()` branch — which is
only reached *because* `zchki` appeared to fail, so the wildcard path routes
around the bug. And every 32 KB test this port has run was a **receive**;
`zchki` is not in that path. **The port has never sent a large file by
name.**

Fix: declare `rc` as `CK_OFF_T`. A no-op wherever `int` is 32 bits, so like
edit 15 it should not be guarded — guarding it would ship the broken form
everywhere else. Send it upstream with 14 and 15; all three are plain 16-bit
portability defects.

**Workaround in any unfixed build:** use a wildcard. `-s TRANS.*` transfers
the same 32 KB file correctly, because it reaches `nzxpand()`.

**Then prove it end to end**, because that is the point: a take-file on the
Victor doing `set speed`, `send`, `statistics`. `TAKE` from the prompt
already works, so this is available now and does not wait on item 0.

**Three rules for writing them**, all learned the hard way:

- **CRLF** line endings (`PTEST.KSC` is CRLF and works, and `_fmode` is
  `O_BINARY` here so it is not obvious that it should).
- **Never end a line with `-`** — that is C-Kermit's continuation
  character, and it silently ate four commands out of §16z's test script.
- **The filename must be argv[1] literally.** `prescan()`'s branch is
  guarded by `yargc > 1 && *yargv[1] != '-'` (`ckuus4.c:1610`), so
  `CKICPD -d FILE.KSC` never takes it. Put switches after.

---

**9. The foreground decode path. Still the bound, but §16af moved every
number in this item — the breakdown below is leg AG, not §16v's leg CA.**
**1,170 cps at 38400** with CRC-16, byte-exact, zero retransmissions.
Where 28.00 s goes:

```
line time (37,568 B at 38400)      9.77 s   35%
disk      (wfile tot = 50 cs)      0.50 s    2%
txgap     (ACK-sent to next-read)  0.00 s    0%   <- was 2.50 s at 18 pkts
unaccounted                       17.73 s   63%   <- packet decoding
```

The proportion barely moved (62% → 63%) while the absolute fell 21.2 → 17.7
s, which is the honest way to read edit 17: **it did not change what the
bottleneck is, only how much of it there is.** Per wire byte the foreground
is ~485 µs, down from §16v's 564, and the **no-line ceiling is ~1,797 cps**
— §16v's ~1,353 is superseded and should not be quoted.

`peaktag = 12` names it — upstream, after a ring drain. That is **564 µs
per received byte, ~2,800 cycles on a 5 MHz 8088, against a 260 µs byte
time**: the same shape as §16t's ISR defect one level up, and the reason
`rxpeak` sits at 2,589 without ever overflowing.

**The number that should govern every throughput decision from here is the
no-line ceiling: ~1,797 cps** (leg AG; AH's is ~1,900). Take the wire out
entirely and 18.2 s remain. §16v's ~1,353 was the same calculation on the
pre-edit-17 binary and is superseded. §16n's ~1,630 projection is above it and is dead; §16t's ≤ 2,780
ceiling was loose by 2.7×. Doubling 19200 → 38400 bought **+24%** measured,
**+17%** after correcting leg CB for its two retransmissions. **Nothing
above 38400 is worth more than 34%**, so rate is finished as a lever.

**The compile flag has been tried and it is not the lever — see §16w
before spending anything here.** `-ot` fits (needs 235,090, DGROUP
48,576) and is **slower**: 632 → 624 cps and `rxpeak` 294 → 333 on
protocol-identical runs. §16t's own model predicts it — an 8088 fetches
through a four-byte queue over an 8-bit bus at ~4 clocks a byte, so **code
size is execution time** and `-ot`'s 9.2% of extra far code is a cost. The
MAME caveat runs in the safe direction for once. `-os` stays, and the
makefile now says why on both grounds.

**Both cheap levers are spent, and the decode path is now upstream code.**
§1 item 3 shipped `NOCKXXCHAR`; §1 item 4 built the `errno` far-call removal
and §16ah took it back out for measuring slower on both instruments. What is
left in `ttinl()`'s loop is upstream's, and **§1 item 5 argues against
spending edit 18 on it** — an argument the two failed attacks strengthen
rather than weaken. Two things to do before anything expensive:

- **Split the 17.7 s.** It is one subtraction — elapsed minus line minus
  `wfile` minus `txgap` — so nothing yet separates per-byte decode from
  per-packet fixed cost, and the two have completely different fixes. A tag
  or counter around the decode call splits it. §16m's rule applies: the
  interrupt handler is a clock you can afford, the foreground is not, so
  instrument at packet granularity and not per byte. **§16af makes this
  more attractive than it was**: with resends gone, packet count is now a
  clean 18 in every leg, so a per-packet fixed cost divides out exactly.
- **Run a text fixture, because every measurement this port has is on
  adversarial data.** The 32,768-byte fixture holds every byte value, so
  Kermit's control and high-bit prefixing expands it to **37,568 wire
  bytes, 14.7%** — and decode cost is per *wire* byte. Plain ASCII should
  present materially fewer. That is an inference from the packet logs
  bounding it at ~15%, **not a measurement**, and one run settles it. It
  also means **1,170 cps is a worst-case-ish figure**, which is the right
  one to quote but not the whole picture.

**10. ~~Re-do the ring sizing.~~ LARGELY CLOSED by §16af — `rxpeak` is
2,581 of 4,096 with 1,515 bytes of margin and `rxfull = 0` at block 3, so
nothing is pressing on the ring and there is no sizing crisis to resolve.
What survives is the model below and the `DRPSIZ` ceiling in item 11; the
0.54-bytes-per-byte figure is now wrong in magnitude (the foreground fell
from 564 to ~485 µs a byte) though right in shape. An earlier revision said
"do not re-derive it until item 1 has produced a calibration"; **item 1 is
closed and produced no calibration** — the bench spread and the effect are
the same size (§16ah) — so that gate never opens and is withdrawn. If this
model is ever wanted, the thing to derive it from is `rxpeak`, which is
counted exactly and does not care about the timing noise.**

The superseded reasoning, kept because the *method* is still the right one: The peak is `rxpeak = 2,589 of 4,096` at 38400 (§16t's 2,621 on
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

Note this bounds *observed* occupancy, not the safe bound — the worst case
is still "the foreground drains nothing for a whole packet", which is the
packet length, and it is **item 11** that turns on it. (This used to say
"item 3", from a numbering two revisions old.)

**11. ~~Flow control.~~ BUILT, SHIPPED OFF, AND NOW MEASURED ON THE
MACHINE — PORTING.md §16aj (build), §16ak (seven legs), §16al (four legs).**

`ckvictor.c` §1f is the driver: **RTS/CTS and XON/XOFF, both directions, in
both interrupt handlers**, selected by `--rtscts` / `--xonxoff` /
`--noflow` off the DOS command tail (§16i's priority-0 XI mechanism) or by
`-dV9K_FLOW=`. Water marks 3/4 and 1/4. Assert in the handler because the
case it exists for is the one where the foreground is not running; release
in `v9k_ser_get()`. `tcflow()` implemented. **No upstream edit — still
seventeen.**

**What eleven bench legs settled:**

| | answer | leg |
|---|---|---|
| does the CTS gate wedge the transmitter? | **no** — 32,768 bytes at **1,475 cps**, the port's fastest | §16ak DS |
| does turning it on cost anything? | **no** — byte-identical to its control, **6 ms** apart | §16ak DE |
| what does §1f itself cost? | **≤ 0.11 s on a 32 KB receive**, ~3 µs/wire byte | §16al GP/GQ |
| **does our RTS pin actually move?** | **YES — on a scope. Eight pauses of 785 ms–1 s during leg GB** | §16an |
| **does the far end stop?** | **no, and it is the HOST** — data kept arriving hundreds of ms after each drop, because macOS was never told to watch CTS | §16an |
| does the Victor obey a real XOFF? | **unknown** — the host never sent one | §16ak DX |

**`V9K_FLOW` stays `FLO_NONE`.** The **input** half of RTS/CTS works and is
fast; the **output** half has never actually been tested — see §16am.

**§16an put a logic analyzer on the pin and the port's half works.** The
Victor's RTS is negative before any driver, positive once the OEM driver
loads, blips on every chip reprogram, drops 175 µs on each `HANGUP`, and —
the one that matters — **shows eight pauses of 785 ms to ~1 s during §16al
leg GB**, which is §1f dropping RTS at the 1,024 mark and raising it at 896
on a clean byte-exact 32 KB transfer. **Data kept arriving for hundreds of
milliseconds after each drop**, because the bench Mac's C-Kermit has no
`POSIX_CRTSCTS`, its `tthflow()` is an empty function, and nothing was ever
told to watch that pin (§16am).

**Three candidates are down to one and it is not ours:** the WR5 write
reaches the pin (dead), the cable carries it (strongly indicated — §16an has
a 25 ms tell where `cts` lags `dsr`/`dcd`, and **one two-probe capture at
both ends of the CTS conductor during a `STEPGB` run closes it**), and the
host does not act on CTS (**this is it**).

**So the default waits on the host, not on the port.** The risk that chose
`FLO_NONE` — gating the transmitter on an unmeasured CTS — is retired. What
is missing is the benefit: no far end has been shown to stop because the
only one tested cannot be. `stty -f <port> crtscts -hupcl` before `kermit`
is untested and free; a host C-Kermit built from this tree with
`POSIX_CRTSCTS` is the honest fix. **XON/XOFF has no `stty` shortcut** — its
bits are exactly the `c_iflag` ones `TESTING234` clears.

**And the analyzer found something it was not aimed at: `msleep()` does not
sleep.** The 175 µs `HANGUP` pulse should be 500 ms (`HUPTIME`). This build
has no `select`/`nanosleep`/`usleep`, so `msleep()` compiles upstream's
fallback — `if (m > 0) while (m > 0) m--;` — an empty loop on a local that
`-os` may delete outright. **`tthang()` cannot hang up a modem and
`tcsendbreak()` does not send a break**, and the second is `ckvictor.c` §1b's
own code. See §1 item 16 and the known-incomplete list.

**The instrument lesson is the one to carry:** every flow-control
measurement before this was a counter inside one of the two programs, and
**both programs can be right about what they did while nothing happens
between them.** When the question is about a wire, measure the wire.
`stty` shortcut: its bits are exactly the ones `TESTING234` clears.

**Three method points, all from §16al and all reusable:**

0. **Before running an experiment that depends on the far end behaving a
   particular way, measure that the far end can.** §16aj wrote down "a line
   of upstream source is not evidence that the build compiles it" about this
   port's own build; §16am is the same rule pointed at the *other end of the
   wire*, and **`SHOW FEATURES` is `wcc -pl` for a binary you did not
   build**. Three legs and a fourth about to be scheduled went to finding
   that out afterwards, and the check was one command.
1. **Non-line cost is how you compare an off-shape leg.** Host clock minus
   wire bytes × 260 µs made leg GP usable when its clock alone was not, and
   it is what turned §16ak's unattributable +11% into a withdrawn figure.
2. **When a leg keeps going off-shape, change what you ask of it, not how
   many times you ask.** A narrow band (1024/896) gives a **cap** to read
   where a low mark (256/64) gave a comparison, and a cap survives a
   retransmission.
3. **The bench's run-to-run spread is the HOST.** The same `CKPRE` binary
   had a non-line cost of **18.29 s in §16ah and 21.43 s in §16al** with the
   wire held constant — 172 ms per packet of macOS/USB turnaround. That is
   the standing answer to item 5b and the reason adjacent pairs work and
   cross-sitting comparisons do not.

**Two upstream defects came out of building it**, both in `ckutio.c`, both
found by preprocessing and both on item 8's report list: `:6758`'s
`TESTING234` block clears `IXON|IXOFF` four lines before the `tcsetattr()`
that applies them, and `:10849`'s `tcflow(TCOON)` — the only caller in the
module — sits inside a `debug()` argument that `NODEBUG` deletes. So §1f
reads upstream's **`flow`** variable, not the termios bits. **Do not quote
`ckutio.c:6252`/`:6617` as "the plumbing is already there".**

**Withdrawn:** §16ak's "+11% for §1f". **Isolated, not explained:** §16ak's
`stall256 = 2,399` on leg DB, which §16al did not reproduce (GB 47, GA 114)
— it belongs to the 256/64 configuration, where the high mark and
`V9K_RXSTALL` are the same number, and **is not evidence that anything
paused.**

**Three harness failures cost three sittings in this sequence, and all three
are worth remembering as rules rather than as anecdotes:** a re-run into a
target name that already existed (`SET FILE COLLISION BACKUP` cannot work on
FAT — put `IF EXIST <target> DEL <target>` in every receive `.BAT`); a run
sheet that named a `-d` flag without staging the binary carrying it; and **a
full image** (`vtg_image_util info` belongs in every §0 — partition 1 is
9.7 MB and 100% free and has never been used).

**12. Then windows.** `DFWSIZ` is still 1. Item 11 is no longer a blocker —
the mechanism exists — but it is still a **precondition in practice**: turn
the window up and turn flow control on in the same sitting, or the 105-byte
margin is doing the work alone. Do it under MAME first. Note the interaction §16s found: with
a window of one the file write happens *before* `ack()`, so the line is idle
through it — which is why a floppy with 1.5-second writes loses nothing.
**Open the window and that stops being true**, and a 1.5 s write at 38400 is
5,760 bytes against a 4,096-byte ring.

**13. ~~Server mode on hardware.~~ DONE — §16ai leg CS, and it was a
first.** `CKERMITW -x` driven entirely from the host: SEND to the server
**1,058 cps**, GET from the server **1,431 cps**, then FINISH. Both
`SUCCESS`, both byte-exact, `rxlost = 0 rxfull = 0 rxpeak = 2,332`. **No E
packet**, so §16i's priority-0 capability initializer works on the machine —
a second, independent check on the XI mechanism whose failure §16ai's
headline was about. `HW_TESTING.md` leg 0.7 is closed.

What is left of it: **`--safe-server` is still unrun** (one more leg, with
the unknown-option control per §16i), and `REMOTE DIRECTORY` and `BYE` were
excluded deliberately — the first never terminates its listing (§16i, item
15) and the second cannot be retried without a power cycle.

**14. FreeDOS for Victor** — `HW_TESTING.md` Tier 4, and the IRQ1 vector
question (41h here, INT 09h there) that is the most likely thing to break
the "one binary, two DOSes" claim.

**~~Report the `ckcmai.c` nesting upstream.~~** Folded into item 8 —
§16ac found the same region also swallowing `dotakeini()` and
`docmdfile()`, and edit 14 fixed it. One report, not two.

**15. `REMOTE DIRECTORY`** still streams its listing and never terminates it
(§16i).

**16. `msleep()` does not sleep, and `tcsendbreak()` is this port's own
broken code because of it.** §16an, found by a scope aimed at something
else: `HANGUP` should hold DTR and RTS down for `HUPTIME` = 500 ms and the
capture shows **175 µs**.

`ckutio.c`'s `msleep()` has arms for `select()`, `nanosleep()` and
`usleep()`; this build has none, so it compiles the fallback —

```c
if (m >= 1000) { sleep(m/1000); m %= 1000; if (m < 10) return(0); }
if (m > 0) while (m > 0) m--;              /* an empty decrement loop */
```

— which for any `m` under 1000 is a side-effect-free loop on a local that
`-os` is entitled to delete. Two shipped things depend on it:

- **`tthang()` cannot hang up a modem.** Latent: no modem has ever been on
  this bench.
- **`tcsendbreak()` does not send a break.** `ckvictor.c` §1b sets WR5 bit
  4, calls `msleep(275)` and clears it — so the break is two IOCTL round
  trips long where POSIX says *at least* a quarter second. **This one is
  the port's own code**, and it has never been exercised.

**The fix is the port's and it runs into hard rule 6.** INT 21h's only clock
is `AH=2Ch`, which advances in **500 ms steps** on this machine (§16n), so
anything shorter needs a busy loop calibrated once against it — 1980s style,
and `ckvictor.c` §1d is where it belongs beside the other Watcom gaps.
Calibrate at startup, not per call.

**Neither is on any critical path**, which is exactly why this sat unnoticed
for the port's whole life. Do it when something needs a break or a hangup —
or when `msleep()` turns up in a third place.

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
  `norx/othrx/rr0/oth`, `lost evt/max/tag/fd`, `lostat/lostend`, **`flow`**,
  `wfile`, `wcon`, `txgap`, `elapsed/wire`, `mdm` — plus a `b<N>` row per
  burst in a `-dV9K_CISR` build without `-dV9K_LEANLOST`. **`wire=` is bytes on the
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
- **`rxpeak` measures the host's retransmission, not the transfer.** §16m
  reached that by instrumenting the peak; §16ag confirmed it by absence —
  leg AM ran with no retransmission and came back at **17 of 4,096** where
  every retransmitting leg in the same session sat at 299. So a `rxpeak`
  comparison between two legs is only meaningful if both retransmitted the
  same number of times.
- **Two legs per arm, and do not trust a single pair's spread.** §16ag's
  control arm put two runs of one binary **321 ms** apart while its other
  two arms held to 1 ms and 5 ms, with no explanation offered or found.
- **Byte offsets map onto the host packet log**, resends included:
  `python3 v9k/tools/mapoffset.py host.pkt --rxbytes <rxbytes> <offset>...` —
  **always pass `--rxbytes`**, which computes and applies the startup
  dead-air shift. §16r nearly published a wrong answer for want of it.
- **`python3 v9k/tools/pktstat.py host.pkt`** decodes a log **in both
  directions** — packets and types, **wire bytes**, longest packet, timeouts,
  retransmissions by either end, **prefix counts and the prefixing policy**.
  It read only the log-writer's own half until 9 August 2026 and reported
  "longest 49, retransmissions 0" for a send log with 3,614-character lines
  and four Victor resends; both halves are fixed. A remote retransmission has
  no marker of its own — it is the same sequence number arriving twice
  running. **`--rxbytes N [--rxfull N]` reconciles against the Victor's ISR
  counter**: `host wire bytes − rxbytes = rxfull + startup offset`, where the
  offset is **−11** clean or **+28** with a startup timeout, and anything
  else means the two ends did not see the same transfer. On §16af leg AJ the
  residual is exactly that leg's published `rxfull` of 741.
  **Reach for it whenever an effect is too small to time**: wire bytes are
  counted and deterministic where the bench's clock is not.
  The `PX_*` tables it names policies from are a **transcription** of
  `setprefix()`, in the sense `v9k/proofs/` uses the word — if upstream
  changes, the naming goes quietly wrong while still printing a name. The
  counts are measurements and stay true either way.
- **`v9k: flow in= out= hi= lo= held= rel= xoff= xon= stuck=`** (§16aj).
  `in`/`out` are 0 none, 1 XON/XOFF, 2 RTS/CTS, and they are read from
  upstream's `flow` and not from the termios bits — see §1 item 11 for why
  that distinction is load-bearing. **On a healthy shipping leg every
  counter is 0 and that IS the result**: the high mark is 3,072 and the
  largest occupancy this port has recorded is 2,581, so the insurance did
  not have to pay out. A leg that means to exercise the mechanism builds
  `-dV9K_RXHIGH=256 -dV9K_RXLOW=64` and expects `held` and `rel` to move
  together and **end equal**; `held > rel` leaves the far end held off.
  `stuck` should never move — it counts writes abandoned after seconds of
  hold-off. **Intercepted XON/XOFF are excluded from `rxbytes` on purpose**,
  because they are not in the host's packet log; `pktstat.py --rxbytes` gave
  the same −11 residual with five of them as without (§16aj leg FH), which
  is the check that says the choice was right.
- **A MAME A/B is only comparable within legs run back to back.** §16ag's
  arms held to 1 ms; §16aj's two groups, same fixture, drifted **12–15 s
  apart** because the host machine got busier — the *host's* timeout count
  went 3 → 5 and the packet shape changed with it. The emulator is not the
  variable. Run the control adjacent to the treatment, always.
- **`v9k/probes/macspeed.c`** sets a non-standard bit rate on a macOS port via
  `IOSSIOSPEED`, which is the only way to reach the x1 rates the Victor can
  actually produce (§11a0). `-h` to hold it; give C-Kermit no `set speed`.
- **`make -C v9k/proofs`** builds *and runs* both standing proofs:
  `vburst.c` replays the ISR burst detector (17 cases) and `vcrc16.c`
  checks edit 17's `chk3()` against upstream's over all 256 table entries
  and 20,500 length-and-fill combinations. Re-run after touching either.
  **A proof that is only compiled has not proved anything**, which is why
  the Makefile runs them.
- **`v9k/probes/vasm.c`** records what Open Watcom will and will not do for an
  ISR: `__interrupt` always saves twelve registers, and `#pragma aux` cannot
  be used for one at all. Compile it and read `wdis` before believing
  otherwise.
- **`python3 v9k/tools/mzsize.py ckermitw.exe`** — run this, not `ls -l`. It
  prints **the smallest Victor that can load the build**, which is the
  number to report; `-a 0` gives the requirement alone and `-a <bytes>`
  checks another machine. **Quote the requirement, not the spare** (§16x).
- **`v9k/probes/vmem.c`** asks a running Victor what DOS will give it, INT 21h
  `AH=4Ah` plus `_psp`. Build lines in its header. This is what retired the
  396,224 figure, and it is the way to answer the same question on
  FreeDOS-for-Victor or on real hardware, neither of which has been asked.
- **`CKERMITW -d -h` is the 2.5-minute oracle** for anything decided before
  or during `sysinit()`.
- **Do NOT combine `-dKEEP_DEBUG` with anything about throughput** — ~25 ms
  per received byte (§16k).
- **There is no `-fstack-usage` under Open Watcom.**

---

## 4. Things that are known-incomplete

- **The Victor takes 40–85 s to load the program**, 205 KB shipping and
  435 KB parser, off SASI before `main()` runs. Any leg where the host
  initiates must start the Victor first and *wait*; `MAXTRY` is 10
  (`ckcker.h:472`) and a host that gives up looks exactly like a Victor that
  failed. Host take-files now carry `set retry 30`.
- **`SET FILE COLLISION` is `BACKUP`, and BACKUP cannot work on FAT.**
  Symptom: S, F, A, then **Z with data `D`** and no data packets, a
  ~287-byte packet log, and `No files were transferred (refused:
  destination file already exists)` on the Victor's screen. **This has now
  voided two sittings' worth of legs (§16ak's re-run of DA/DB).** "Fresh
  filename per run" is a rule a person has to remember; the fix that works
  is in the `.BAT` —

  ```
  IF EXIST RCVGB.DAT DEL RCVGB.DAT
  CKFCMID -l /dev/seriala -b 38400 --rtscts -r > STEPGB.OUT
  ```

  **Put that line in every receive `.BAT` from now on**, and still use a
  target name that has never been used, so a re-run cannot silently compare
  itself against an older file.
- **`REMOTE DIRECTORY` never terminates its listing** (§16i).
- **Most of the default capability set is untested** (§16i). `BYE` never sent.
- **Wildcards are case-sensitive.** `-s *.TXT`.
- ~~**`-s <name>` for files of 32,768 bytes or more.**~~ **CLOSED** — §16ah
  leg BS sent exactly 32,768 bytes by name, byte-exact, no error line.
  Upstream edit 16 now has runtime evidence and **no shipped edit in this
  port lacks it.**
- ~~**`pktstat.py` misreads a Victor-send log.**~~ **FIXED 9 August 2026.**
  It reads both directions, counts wire bytes and prefixes, names the
  prefixing policy, and reconciles against `rxbytes`. Checked against all 47
  logs in the tree with no unparsable lines.
- ~~**No interrupt-level flow control**, `tcflow()` is a stub, and the ring
  has no water marks.~~ **BUILT — §16aj**, both mechanisms, both directions,
  `tcflow()` implemented, marks at 3/4 and 1/4. **It ships OFF** and the
  reason is item 11: nothing needs it at a window of one, and selecting
  RTS/CTS gates the transmitter on a CTS nothing has measured in that
  direction. So the 105-byte margin between `DRPSIZ = 4000` and the 4,096
  ring is still what holds today — but it is now an accident with a
  fallback, which is what made it a precondition for items 10 and 12.
- **No stack switch in the handler** — deliberate, and the assembly one is a
  10-byte frame.
- **`msleep()` is a no-op below one second** (§16an), so `tthang()` cannot
  hang up a modem and **`tcsendbreak()` does not send a break** — the latter
  is `ckvictor.c` §1b's own code. Measured on a scope: a `HANGUP` that
  should hold the lines down for `HUPTIME` = 500 ms holds them for 175 µs.
  §1 item 16.
- **Nothing has ever shown the host's CTS moving at the moment the Victor's
  RTS does** (§16an). The cable is strongly indicated to carry it — `cts`
  lags `dsr`/`dcd` by 25 ms on power-down, so it is a separate signal — but
  the watcher runs were taken during power-up, not during a transfer. **One
  two-probe capture, both ends of the CTS conductor during a `STEPGB` run,
  closes it.**
- **Out of disk space makes the Victor HANG, not fail** (§16al attempt 1).
  Eleven or twelve packets in, the 8,192-byte `V9K_OBUFSIZE` flush has
  nowhere to go, and the Victor stops responding **forever** — the host
  times out after 30-odd retries, the Victor never does, because §0d's
  `alarm()` bounds the *read* and nothing bounds a failed write. Never
  diagnosed: a `KEEP_DEBUG` leg under MAME against a deliberately full image
  would do it, cheaply and safely.
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
- **The foreground time is one bucket — 17.7 s at leg AG.** Measured by
  subtraction — elapsed minus line minus `wfile` minus `txgap` — so it is
  a total, not a decomposition, and nothing yet separates per-byte decode
  from per-packet fixed cost. §1 item 9.
- **The bench does not repeat to better than ~1.3 s on protocol-identical
  legs**, and the cause is unknown. That, not the Victor's 50 cs clock, is
  what bounds every per-item cost in this port — §16ah retired §16af's "one
  clock quantum" on exactly this. §1 item 5b.
- ~~**The prefixing fix is unverified on the wire.**~~ **VERIFIED — §16ai
  legs CC/CD.** `PX_CAU exactly (32 values)`, 4,512 prefixes, 37,557 wire
  bytes, byte-exact, against the control's `PX_ALL exactly (66)`, 8,869 and
  41,945. −10.5% traffic.
- **The parser build has two interactive prompts on the receive path that
  the shipping build cannot have**, and a redirect makes them fatal.
  `set receive confirm off` and `set exit warning off` are in `RXEA.KSC`;
  any *new* Victor-side take-file for a `KEEP_ICP` build needs them too.
  This is a property of the build, not a bug — see "The harness had two
  defects" above for why the shipping build is exempt.
- ~~**The RTS/CTS output direction is unmeasured.**~~ **CLOSED on the port's
  side by §16an**: the pin moves, eight times mid-transfer, on a scope. What
  is open is the *host's* side — nothing has been shown to stop for it,
  because the bench Mac's C-Kermit cannot be made to watch CTS.
- **`stall256 = 2,399` on leg DB against 47 on its control, unexplained**
  (§16ak). Occupancy crossed the 256 mark upward fifty times more often on
  the RTS/CTS leg, which needs the sender to have paused — but 15
  assert/release cycles cannot produce 2,399 crossings. It is the only
  positive hint that the host obeys our RTS and it is not proof.
- **Leg DC lost 19 bytes and nothing else in the sitting lost any** (§16ak).
  XON/XOFF at the same water marks as RTS/CTS, 11 bursts, first non-zero
  `rxlost` on this bench since §16t. Cause not established.
- **Nothing counts a FAILED XOFF attempt.** The single-shot assert re-reads
  RR0 on every byte until the transmitter is free. That retry is invisible
  and it is the leading suspect for DC.
- **`pktstat.py`'s reconciliation has no term for BELL substitution.** Leg
  DC's residual is −15 where the formula wants −11, and the difference is
  the 19 BELLs the ISR put in the stream. It needs `--rxlost`.
- **Whether §1f costs 11% of a 38400 receive is open** (§16ak). Three clean
  legs at 31.1–31.5 s against §16ah leg BC's 28.057 s on the identical
  37,557 wire bytes — but cross-sitting. `CKPRE.EXE` is on the image and one
  adjacent pair settles it.
- **Nothing has seen a far end obey our XOFF, and now on hardware too.**
  §16ak leg DX armed the interception path on a real cable and the host
  never sent one — `xoff = 0`. A null, not a failure: the leg still ran
  byte-exact at 1,475 cps.
- **`held = rel` on every leg that asserted** (§16ak), which is the property
  to check; `held > rel` would mean the far end was left held off.
- **The flow-control assert has never run on the ring-full path.**
  `v9k_ringfull` re-enters the water-mark check with occupancy forced to the
  mask; nothing has executed it, the same standing caveat as the assembly
  handler's overrun branch.
- **Four other XI initializers have never been checked for the same
  problem.** `_fmode`, the server capability gate and `zobufsize` all set
  upstream state before `main()`, and `initproto()` is not the only thing
  that re-initialises. `_fmode` and `zobufsize` are witnessed indirectly (a
  binary transfer is byte-exact; `wfile` fell to 4 writes), and the server
  gate was witnessed through `uname()` in §16i — **but none was checked
  against a later upstream write of the same variable.** Leg CS exercises the
  server gate on hardware by a different route. §16aj's flow-control
  initializer is the fourth, and it is the one that was *designed* around
  the trap: it writes nothing upstream owns, and `v9k_ser_install()` puts
  the value into `cxflow[CXT_DIRECT]` one statement before `setflow()`
  reads it.
- **The shipping binary is 44 bytes different from the one the bench ran.**
  §16ah legs BC/BD ran 205,256, which carried the `errno` initializer
  compiled-but-unreachable; removing it took the build to **205,212**. The
  removed code never executed, and §16w's size sensitivity makes the delta
  non-zero in principle. Any future leg reporting `rxlost=0 rxfull=0` and a
  byte-exact md5 sweeps it up; nothing needs to be done for its own sake.
- **`NOCKXXCHAR`'s 2.1% is not attributed.** The change removes two
  instructions per byte, 512 bytes of DGROUP and 756 of code all at once,
  and §16w established this machine is sensitive to the last of those. It
  ships because no reading makes it a loss, not because the mechanism is
  known.
- **`v9k/proofs/` carries transcriptions, not references.** `vcrc16.c` has
  its own copy of upstream's `chk3()` and of `crcta[]`/`crctb[]`;
  `vburst.c` has its own copy of the ISR counter update. They prove
  agreement with *what was transcribed*. If upstream's `chk3()` changes or
  the ISR counters are reworked, both keep passing and mean less than they
  say. `ckvictor.c` has a build-time check for exactly this drift on the
  ring size; there is no equivalent for a host program that never sees the
  target's headers.
- **`wire=` is a receive-leg figure.** It divides `rxbytes`, so on a send
  leg it reports the ACK stream over the whole elapsed time. No send leg has
  ever been timed.
- **cps above 38400 is unmeasured and probably uninteresting** — and it is
  moot anyway, since §11a0 established 39,062.50 bps as a *hardware*
  ceiling. §16af's no-line ceiling of ~1,797 cps caps the payoff at ~54%
  even if the wire were free.

---

## 5. Still open, from before

**The parser build is no longer "still open" — §16y built it.** See §1
**item 7** for what is left of it — the hardware leg, whose one real unknown
is that **no transfer has ever been run with the parser build** — and §16y
for the sizes. (This used to point at §1 item 1, which now means the closed
calibration item.)

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

**Redirect to keep the host's cps, and treat it as mandatory rather than
optional:** `kermit -C "take s16uCA.ksc, exit" > s16uCA.host`. It was
skipped twice — §16ae's seven legs and §16af's three — which cost a whole
sitting to repair; **§16ah captured it on all seven legs and found that the
Victor's 50 cs quantum was never the binding limit anyway, the bench's own
~1.3 s spread is** (§1 item 5b). Capture it regardless: it is what
distinguishes "the difference is below the noise" from "we cannot see the
difference". **Three files per leg: `.host`, `.pkt`, and the Victor's
`.OUT`.** A leg missing the `.host` cannot resolve any difference
smaller than the Victor's 50 cs quantum, which is most of them. `s16uCA.ksc` and `s16uCB.ksc` in the tree are the files that
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
- `.BAT` files need CRLF — **now guaranteed**: `.gitattributes` marks
  `*.BAT` as `text eol=crlf` and the harness `.BAT`s are tracked, so a
  checkout produces CRLF whatever wrote the file, and a leg is reproduced
  rather than regenerated. That was the actual cause of the landmine going
  off twice. `-autoboot_command` takes the literal `\n`;
  **digits come through shifted under MAME** so use digit-free `.BAT` names
  (`STEPASM`, not `STEP0`); MS-DOS 3.1 cannot redirect handle 2; the disk
  boots as `A:`; use `vtg_image_util`, never mtools.
- Backups: `victor_kermit.img.bak-20260807-preregress` is the last one,
  taken before the image was cleared of §16w–§16y experiment files.
- **On the image now.** Names are deliberately distinct because the exit
  report cannot tell two builds apart — keep the `.OUT` names apart too.
  - `CKERMITW.EXE` — the current shipping build, **205,228, needs 219,452
    (214K), smallest Victor 384K, md5 `537486a8…`** — re-staged 9 August
    with the prefixing fix. **This name always means "current shipping"** —
    a stale binary under it is the trap §16ah's staging notes are about.
    (It was 205,212 / md5 `3c31dbf4…` before the fix; the load requirement
    did not move, because the 16 extra bytes land inside a paragraph DOS was
    already rounding up.)
  - `CKPXALL.EXE` — **205,228, md5 `ddb93453…`, `-dV9K_PREFIXING=PX_ALL`.**
    The control for leg CC: same tree, same commit, same size, differing
    only in the immediate constant the prefixing initializer stores, so
    §16w's code-size sensitivity has nothing to act on.
  - `CKAP.EXE` — 205,256, md5 `433148fa…`. **The binary §16ah legs
    BA/BB/BS/BC/BD actually ran**, and §16ag legs AP/AQ before them. It
    differs from what now ships by the 44 bytes of removed `errno` code.
  - `CKFERR.EXE` — 204,888, md5 `415cf233…`, `-dV9K_FAST_ERRNO`. Legs BE/BF,
    and §16ag legs AL/AN. **The change it carries is no longer in the
    tree** (§16ah); the binary is kept because it is a measured artefact.
  - `CKAK.EXE` — §16af's edit-17 build, 205,968, md5 `8d40f7f6…`, which
    §16ag legs AK/AR/AM ran.
  - `STEPBA/BB/BS/BC/BD/BE/BF.BAT` — the seven bench legs of
    `HW_TEST_16ag.md`, staged and verified CRLF *after* landing on the
    image. Host side: `s16ahB*.ksc` and `rcvb*.dat` in the tree.
  - `CKBASE.EXE` — the sixteen-edit baseline, 205,552, staged as §16af's
    control so leg AJ is a *binary* difference and not a rebuild. Keep it:
    any future "did this change help" leg wants the same shape.
  - `STEPAG.BAT` / `STEPAH.BAT` / `STEPAJ.BAT` — §16af's three legs, and
    `STEPAF.BAT` for the MAME leg. All four are tracked in git now, so
    re-stage them from a checkout rather than regenerating.
  - **§16aj's flow-control legs.** `CKFCA.EXE` — the shipping build,
    206,758, md5 `c5652a5b…`, same tree as `CKERMITW.EXE`. `CKFCLO.EXE` —
    **the same 206,758 bytes** with `-dV9K_RXHIGH=256 -dV9K_RXLOW=64`,
    differing in two immediate constants, so `--xonxoff` against
    `--noflow` on it is one binary and one switch with no code-size
    difference for §16w to bite on. `CKFCD.EXE` — 288,106, `KEEP_DEBUG`,
    for the `-d -h` switch witness. `CKPRE.EXE` — 205,228, md5
    `537486a8…`, **HEAD before §1f rebuilt**, which is how leg FZ is a
    binary difference and not a rebuild. `STEPFA/FB/FC/FD/FE/FG/FH/FJ/FZ`
    and `RCVF*.DAT`; host side `s16ajF*.ksc` and `rcvf*.dat` in the tree.
  - `CKICP.EXE` / `CKICPD.EXE` — the parser build, and the same with
    `KEEP_DEBUG`. **Rebuilt and re-staged 9 August**, 435,154 md5
    `f5456cae…` and 546,422 md5 `6d991fc7…`. The 8 August copies predated
    upstream edits 16 and 17 and are gone; without edit 17 a 38400 transfer
    against them reproduces §16af's ring defect and reads as "the parser
    build breaks transfers".
  - `STEPCC/CD/CE/CH/CS.BAT` — the five legs of `HW_TEST_16ai.md`, staged
    and verified CRLF **after** landing on the image. Host side:
    `s16aiC*.ksc` and `rcvce/rcvch/rcvcs.dat` in the tree. `RXEA.KSC`,
    `PTEST.KSC`, `SPDTEST.KSC`, `STEPSPD.BAT` and `TRANS.DAT` are reused
    unchanged from §16y/§16z.
  - **The x1 sweep binaries and their one-line `.BAT`s:**

    | BAT | binary | mode | count | bps |
    |---|---|---|---:|---:|
    | `S96X16` | `CKERMITW -b 9600` | x16 | 8 | 9,766 |
    | `S96X1` | `CKX9600.EXE` | x1 | 130 | 9,615 |
    | **`S96X1S`** | **`CKX96S.EXE`** | **x1 + `DRPSIZ=90`** | **130** | **9,615** |
    | `S384X1` | `CKX384.EXE` | x1 | 33 | 37,879 |
    | `S576` | `CKERMITW -b 57600` | x1 | 22 | 56,818 |
    | `S768` | `CKERMITW -b 76800` | x1 | 16 | 78,125 |
    | `S1152` | `CKERMITW -b 115200` | x1 | 11 | 113,636 |

    `S96X1S` is the unrun one and it belongs to §1 item 6, which is closed. The `CKX*` builds carry
    `-dV9K_CLKBITS`/`-dV9K_COUNT` and therefore **ignore `-b` entirely** —
    one build, one point, no ambiguity about what was on the wire.
  - `SPDTEST.KSC` + `STEPSPD.BAT` (parser regression), `PTEST.KSC`,
    `TRANS.DAT` (32,768 bytes, md5 `d94d2beda069ef0ef340977e7fd6995d`).
  - Older `STEP*`/`RCV*` from §16t and §16v are still there. Delete before
    reusing a name — `REN DEBUG.LOG X.LOG` fails silently if `X.LOG`
    exists, leaving a stale log beside a fresh `.OUT`.

**Expected bit periods on TD, for the analyzer** — the right-hand column is
what you would see if the OEM driver's IOCTL ignored CR4's clock bits the
way it ignores CR1. It does not; this is measured. Kept as the check:

| BAT | expected | if CR4 were ignored |
|---|---:|---:|
| S96X16 | 102.4 µs | 102.4 µs |
| S96X1 / S96X1S | 104.0 µs | 1664.0 µs |
| S384X1 | 26.4 µs | 422.4 µs |
| S576 | 17.6 µs | 281.6 µs |
| S768 | 12.8 µs | 204.8 µs |
| S1152 | 8.8 µs | 140.8 µs |

### Testing the parser at the bench — this is what §16y was for

**The bench is the only place this can be tested, and the reason is the
keyboard.** MAME mangles typed input (§16a: digits arrive shifted, and
`CKERMITW -r` once arrived as `CKERIT_R`), which is why every run in this
project has come from a `.BAT`. An interactive prompt needs a real keyboard,
and the Victor has one.

**Rebuild and re-stage `CKICP.EXE`/`CKICPD.EXE` before any of this** — the
staged copies are from 8 August and predate edits 16 and 17, and step 3
below is a 38400 transfer that would reproduce §16af's ring defect against
them. §1 item 7.0 has the commands.

Type `CKICP` and expect `C-Kermit>`. In rough order:

1. **`show versions`** — proves the parser reads a line, looks up a keyword
   and runs a command. **Console input has never been exercised in this
   port**: every `NOICP` build only ever wrote to the console, so
   `coninc()`/`congks()` through INT 21h are new ground. If anything is
   going to fail, it is more likely this than the parser.
2. **`take ptest.ksc`** — and this one is a **diagnostic, not just a
   feature**. Interactive `TAKE` goes through `cmifip()` (`ckuusr.c` around
   10590), a *different* path from the command-line `argv[1]` route
   (`prescan()` → `findinpath()`, `ckuus4.c:1741`) that §16ac's edit 14
   repaired. So:
   - it works → any residue is isolated to `findinpath()`/`prescan()`;
   - it fails the same way → the problem is lower down, in `zopeni()` or
     `access()` on a FAT root, and §1d is where to look.
   Try `CKICP PTEST.KSC` from the DOS prompt too, as the control that
   reproduces the known failure.
3. **`take rxea.ksc`**, with the host running
   `kermit -C "take s16zREA.ksc, exit" > s16zREA.host` — a full 32 KB
   receive at 38400 driven by the Victor from a file. **No transfer has ever
   been run with the parser build.**
4. **The same by hand** — `set line /dev/seriala`, `set speed 38400`,
   `receive` — if the take-file route fails, since it isolates the parser
   from the file lookup.

Worth knowing before reading results: the parser build **cannot** do `-C`,
variables, macros or `INPUT` (that is `NOSPL`, and `KEEP_SPL` costs another
209 KB), and `SET FILE COLLISION` is still `BACKUP`, which cannot work on
FAT — **use a fresh target name every run.**

---

## 7. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"        # ckermitw.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak sizes"  # DGROUP report
python3 v9k/tools/mzsize.py ckermitw.exe                       # will it LOAD
make -C v9k/proofs                                          # ALL standing proofs
```

Rule 4 still applies: the heap is **outside** DGROUP, the ring is not, and
`V9K_OBUFSIZE` is heap.

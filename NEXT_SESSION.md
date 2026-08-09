# Next session

Handoff for the Victor 9000 port, written 9 August 2026, revised after
§16ah. **No live defect in the receive path.** §16af closed the last one.
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
available and flow control does not have to be XON/XOFF.

**Seventeen** upstream edits, fourteen of them guarded no-ops elsewhere.
**14, 15 and 16 are the exceptions and are flagged as such** — 14 moves a
mis-nested `#endif` (which cannot be placed conditionally), 15 and 16 each
fix a 16-bit truncation and are provable no-ops wherever `int` is 32 bits.
Edit 17 is guarded even though it did not have to be, because it is an
optimisation for one CPU and not a defect fix.
DGROUP 48,304 of 65,536 (73%), image 205,212, **needs 219,452 (214K) at
load — smallest Victor 384K** (§16ah).

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

**5a. Run a Victor send with `cautious` prefixing. One leg, no code change,
and it is the cheapest open question in the file.**

§16ah leg BS measured the send direction for the first time and found the
Victor's prefixing expanding 32,768 bytes to **40,726 wire bytes (+24.3%)**
where the host's `cautious` expanded the same payload to **35,950 (+9.7%)**.
Same fixture, same session, same cable — two *policies* over identical data.

`ckvictor.c`'s prefixing initializer and `V9K_PREFIXING` were kept in §16ae
on the argument that they are "right for a Victor **sending**", which was
explicitly flagged as unmeasured. It is measured now and it looks like the
wrong choice: 4,776 wire bytes of pure overhead, ~1.24 s of line time at
38400.

**Why it is still only a lead.** BS was *faster* than any receive leg despite
carrying 13% more traffic, so the Victor has headroom here and this is not a
defect. And the comparison is policy-vs-policy, not Victor-vs-host: nobody
has run a Victor send with `cautious` to see what it actually costs the
sender. That is the leg — `XFLAGS=-dV9K_PREFIXING=...` or the initializer,
one send leg, against BS as the control.

**Run it as a wire-byte comparison, NOT a timing A/B, and this is the one
thing that makes it answerable at all.** The effect is 4,776 wire bytes,
which is ~1.24 s of line time at 38400 — **below item 5b's ~1.3 s noise
floor**, so the clock cannot resolve it and two legs will not fix that.
**Wire bytes are counted, not timed**: `rxbytes` on a receive leg, and the
packet log on a send leg, are exact and deterministic. Read those against
BS's 40,726 and ignore `elapsed=` entirely. The general form is worth
keeping — **when the bench cannot resolve an effect in seconds, look for a
counter that measures the same mechanism in units that do not vary.**

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

**7.0 — PRECONDITION: rebuild and re-stage `CKICP.EXE` and `CKICPD.EXE`
first. The copies on the image are from 8 August 12:32 and predate two
upstream edits, one of which would make the transfer leg lie.**

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

**8. Report edits 14, 15, 16 and 17 upstream.**

Two independent defects, both found only because this port is an unusual
build, and neither specific to it:

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

**11. Flow control, and it comes before windowing.** `tcflow()` is a stub and
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

**12. Then windows.** `DFWSIZ` is still 1, and items 10 and 11 are both
preconditions. Do it under MAME first. Note the interaction §16s found: with
a window of one the file write happens *before* `ack()`, so the line is idle
through it — which is why a floppy with 1.5-second writes loses nothing.
**Open the window and that stops being true**, and a 1.5 s write at 38400 is
5,760 bytes against a 4,096-byte ring.

**13. Server mode on hardware** (`-g`, `-f`, `-x`, `--safe-server`) —
`HW_TESTING.md` leg 0.7, still untouched.

**14. FreeDOS for Victor** — `HW_TESTING.md` Tier 4, and the IRQ1 vector
question (41h here, INT 09h there) that is the most likely thing to break
the "one binary, two DOSes" claim.

**~~Report the `ckcmai.c` nesting upstream.~~** Folded into item 8 —
§16ac found the same region also swallowing `dotakeini()` and
`docmdfile()`, and edit 14 fixed it. One report, not two.

**15. `REMOTE DIRECTORY`** still streams its listing and never terminates it
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
- **`python3 v9k/tools/pktstat.py host.pkt`** decodes a log; `grep -c '^S-'`
  counts retransmissions and `grep -c '<timeout>'` counts timeouts. **Both
  are receive-leg instruments.** On a Victor-*send* log the length field it
  reads is 0 for long packets and `S-` counts the host retransmitting, so it
  reported "longest 49, retransmissions 0" for a log with 3,614-character
  lines and four Victor resends. Read send logs by hand until it is fixed.
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

- **`SET FILE COLLISION` is `BACKUP`, and BACKUP cannot work on FAT.** Fresh
  filename per run. Symptom: S, F, A, then **Z with data `D`** and no data
  packets.
- **`REMOTE DIRECTORY` never terminates its listing** (§16i).
- **Most of the default capability set is untested** (§16i). `BYE` never sent.
- **Wildcards are case-sensitive.** `-s *.TXT`.
- ~~**`-s <name>` for files of 32,768 bytes or more.**~~ **CLOSED** — §16ah
  leg BS sent exactly 32,768 bytes by name, byte-exact, no error line.
  Upstream edit 16 now has runtime evidence and **no shipped edit in this
  port lacks it.**
- **`pktstat.py` misreads a Victor-send log.** Its "longest packet" reads
  the one-byte LEN field, which is 0 for long packets, and it counts `S-`
  lines, which is the *host* retransmitting. On a send test it reported
  "longest 49, retransmissions 0" for a log whose longest line was 3,614
  characters and which contained four Victor resends. Read the log directly
  for send legs until it is fixed.
- **No interrupt-level flow control**, `tcflow()` is a stub, and the ring has
  no water marks. Safe today only because the ring (4,096) exceeds the
  longest packet (3,991) at a window of one — a **105-byte margin that is
  an accident of `DRPSIZ`**. It gates longer packets as well as windowing.
  §1 item 11. **§16af did not change this**: `rxpeak` fell to 2,581, but
  that is *observed* occupancy, and the safe bound is still "the foreground
  drains nothing for a whole packet", which is the packet length.
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
- **The foreground time is one bucket — 17.7 s at leg AG.** Measured by
  subtraction — elapsed minus line minus `wfile` minus `txgap` — so it is
  a total, not a decomposition, and nothing yet separates per-byte decode
  from per-packet fixed cost. §1 item 9.
- **The bench does not repeat to better than ~1.3 s on protocol-identical
  legs**, and the cause is unknown. That, not the Victor's 50 cs clock, is
  what bounds every per-item cost in this port — §16ah retired §16af's "one
  clock quantum" on exactly this. §1 item 5b.
- **The Victor's send prefixing costs +24.3% in wire bytes against the
  host's +9.7%** over identical data (§16ah leg BS). Measured for the first
  time and never compared against `cautious` on the sending side. §1 item 5a.
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
  - `CKERMITW.EXE` — the current shipping build, 205,212, needs 219,452,
    md5 `3c31dbf4…`. Re-staged and round-trip verified after §16ah removed
    the `errno` code. **This name always means "current shipping"** — a
    stale binary under it is the trap §16ah's staging notes are about.
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
  - `CKICP.EXE` / `CKICPD.EXE` — the parser build, and the same with
    `KEEP_DEBUG`. **STALE: both are from 8 August 12:32 and predate upstream
    edits 16 and 17.** Do not run a 38400 transfer against them — without
    edit 17 they carry the slow `chk3()` and will reproduce §16af's ring
    defect. **§1 item 7.0 rebuilds and re-stages them**, and re-measures
    `CKICPD`, whose "532,904 (520K), 640K minimum" is the 8 August figure.
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

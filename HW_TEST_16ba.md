# §16ba — the FreeDOS console arm, and the `rcvfil()` stall as a measurement

**19 August 2026, no Victor in reach. MAME sitting, 9600, both DOSes.**
**This sheet was written before any leg ran.** §16az's was not, and its own
closing paragraph says that is the thing to fix. Every result section below
is empty until the leg that fills it has run; the leg *table* and §0 are
fixed in advance so that a leg cannot be redefined after seeing its output.

The binary is **§16ay's, unchanged and unrebuilt** — md5
`d76c10b2401d3685f8dd2f2304f717d1`, verified identical in three places
before the sitting: the tree (`ckermitw.exe`), the MS-DOS 3.1 image
(`CKMRG.EXE`) and the FreeDOS image (`CKERMITW.EXE`). **No code change, no
rebuild, no upstream edit — still twenty.** Nothing here is a claim about a
build.

---

## §0 — preconditions

| check | how | status |
|---|---|---|
| **the wire this sitting uses is silent with nothing of ours running** | boot FreeDOS with `AUTOEXEC.BAT` reduced to a REM, `-rs232a null_modem -rs232b null_modem -bitb1 A.txt -bitb2 B.txt`; **channel B must be empty** | ☑ **B = 0 bytes**; A = 2,861, md5-identical to §16az |
| both images backed up before any write | `cp` | ☑ `*.16ba.bak` |
| free space, FreeDOS volume | `hybridfat.py info` | ☑ 32,128 of 32,274 clusters (99.5%) |
| free space, MS-DOS volume | `vtg_image_util info` | ☑ `A:` 480 KB (4.8%), `D:` 99.9%, `E:` 100% |
| target names never used before | `hybridfat.py list` / `vtg_image_util list` | ☑ all fresh |
| every receive `.BAT` opens with `IF EXIST <target> DEL <target>` | §16al's rule, machine-kept | ☑ all nine |
| the staged binary md5 round-trips off **both** images | `get` + `md5` | ☑ `d76c10b2…` in three places |
| the `-d` guard | every leg must report `deb=0` | ☑ `deb=0` on every leg |
| `AUTOEXEC.BAT` saved before being replaced (FreeDOS) | `AUTOEXEC.OLD` already on the image | ☑ |
| **channel B, not channel A, on FreeDOS** | §16az's standing constraint: `entry.asm:280` writes an `H` to `E000:0040` on every INT 21h call | ☑ `COM2` / `-rs232b` throughout |

**Why channel B and not channel A for the silence capture.** §16az captured
channel A and that result stands — 2,861 bytes of kernel trace in 150 s. The
precondition a *leg* needs is that **the wire it is about to use** is silent,
and every leg here runs on B. The tracer is hardwired to `E000:0040`/`0042`
and B is `0041`/`0043`, so B is *expected* to be empty; expected is not
measured, and this is the sitting that measures it. Channel A is captured in
the same run because it costs nothing and reproduces §16az.

---

## What this sitting is for

Two items, and the second grew a leg.

**1. The FreeDOS console arm (§16ao's ANSI branch) has never been seen to
work.** §16av chose it from the same INT 21h `AH=30h` probe that picks the
IRQ1 vector, and recorded that **neither FreeDOS arm had ever executed**;
§16az executed the IRQ1 half and failed to execute this one. Leg FDG ran the
display with `-f` and no host, and C-Kermit only draws the transfer display
*during a transfer*, so a clean screen proved nothing. The leg that settles
it is FDE **re-run without `--nodisplay`**, with the screen captured while
the data phase is running.

**2. The ~27 s stall between the F packet and its ACK.** It is on every 9600
MAME receive on MS-DOS 3.1 in this tree back to §16aj (§16aj FA, §16ar WD,
§16ay UA and UE — 3–4 timeouts, 6–7 retransmissions, all before the first
data packet), §16ay located it inside `rcvfil()`, and **§16az's FreeDOS leg
did not have it.** §16az was explicit that this is *an observation and not a
measurement*: two DOSes, two filesystems, two images, different days, no
adjacent control — §16al's withdrawn "+11%" exactly.

**But a cross-DOS pair alone would repeat that mistake in a smaller way.**
Two things differ between those legs besides the DOS, and both are on
`rcvfil()`'s own path:

- **the root directory it creates the file in.** `rcvfil()` calls `zchko()`,
  which (`ckufio.c:2496`) creates the incoming file, `isatty()`s it, deletes
  it again and only then asks `access(".",W_OK)`. The MS-DOS volume's root
  holds **167 entries**; the FreeDOS volume's holds **56**. A FAT create
  scans the root for a free slot.
- **the transfer display.** `rcvfil()` calls `xxscreen(SCR_FN,...)` — "put it
  on screen if local" — on the same path, and §16az's FreeDOS leg ran
  `--nodisplay` while every MS-DOS leg in the list above ran with the display
  **on**. That is a confound sitting directly on the suspect line.

So the stall is asked as a **2×2 in display, plus a within-DOS arm in
directory size**, and the within-DOS arm is the strong one: same DOS, same
kernel, same disk image, same binary, same wire, one variable.

---

## The legs

All 32,768-byte receives of `TRANS.DAT` (`d94d2beda069ef0ef340977e7fd6995d`)
at 9600, host `kermit` started at t+110 s, `-seconds_to_run 400`.

| leg | DOS | wire | display | destination directory | asks |
|---|---|---|---|---|---|
| — | FreeDOS | A **and** B, bitbanger | — | — | §0 row 1: is B silent? |
| **FDJ** | FreeDOS | COM2 | off | `A:\` root, 56 entries | reproduces §16az FDE; the FreeDOS control |
| **FDHS** | FreeDOS | COM2 | **on** | `A:\` root | **the console arm** — truncated at t+140 s, snapshot lands inside the data phase |
| **FDH** | FreeDOS | COM2 | **on** | `A:\` root | the same leg run to completion, for counters FDHS cannot flush |
| **VA** | MS-DOS 3.1 | `/dev/seriala` | off | `A:\` root, **167 entries** | the MS-DOS arm of the pair |
| **VB** | MS-DOS 3.1 | `/dev/seriala` | **on** | `A:\` root | costs the display against VA; same-day reproduction of §16ay UA |
| **VC** | MS-DOS 3.1 | `/dev/seriala` | off | **`D:\`, empty root** | costs the directory against VA — one variable, one DOS |

Order of execution is the order of the table. FDJ/FDHS/FDH are adjacent to
each other and VA/VB/VC are adjacent to each other, which is the only kind of
comparison this harness has ever supported (§16al).

**FDHS and FDH are one leg run twice and are recorded as such.** MAME writes
its snapshot when `-seconds_to_run` expires, and a run killed mid-transfer
never flushes its redirect — §16az leg FDA's 0-byte `.OUT`, which this tree
has now misread three times. So the picture and the counters cannot come out
of the same run, and FDHS writes to its own target name so that it cannot
truncate FDH's.

### Predictions, written down first

- **Channel B is empty.** If it is not, every FreeDOS leg in §16az is
  contaminated and this sitting stops.
- **The console arm**: unknown, and that is the point. Three outcomes are
  distinguishable in the snapshot — a drawn transfer display (the ANSI arm
  works), a screen full of literal escape sequences (the arm is wrong for
  this console driver), or an undrawn/garbled screen (§16az's FDA, which is
  the kernel's own `victor_trace.c` writing rows 12–24 and is **not ours**).
- **The stall**: no prediction is offered, deliberately. Three mechanisms are
  live — the DOS, the directory, the display — and the legs are arranged so
  that each is measured against a control that differs in one of them.

### What would make this sitting void

- Any leg reporting `deb=1` (§16aw).
- A target name that already existed (§16al).
- A `.OUT` of 0 bytes read as a result rather than as a missing one.
- A `wire=` figure quoted on a send leg (§16v) — there are none here.

---

## Results

**Three legs in the table below — VD, VE and VF — are not in the plan
above and were added after leg VC came back clean.** They are the arms that
turn "the destination directory" into a set of eliminated causes, and each
was decided from the previous leg's result. Saying which legs were planned
and which were improvised is the point of writing the plan down first; the
plan's own predictions section offered no prediction for the stall, and these
three are what that cost.

Ten MAME runs: one capture, eight legs and one leg run twice. **Every
transfer that was allowed to finish came back md5-identical to `TRANS.DAT`
(`d94d2beda069ef0ef340977e7fd6995d`) — eight of eight.** `rxlost = 0
rxfull = 0` and `deb = 0` on every one.

### §0 — the preconditions, and both rows passed

150 s of FreeDOS with `AUTOEXEC.BAT` reduced to a REM, both channels on
bitbangers:

| channel | bytes | |
|---|---:|---|
| A | **2,861** | **md5-identical to §16az's `FDBOOT-chanA-trace.txt`** — the kernel trace reproduced to the byte |
| B | **0** | **silent** |

So the wire every leg below runs on is measured empty, and §16az's channel-A
finding is confirmed by an independent run four weeks later. MAME reported
`Average speed: 100.00% (149 seconds)`, so the emulator was not throttling.

Free space and target names at §0: FreeDOS 32,128 of 32,274 clusters free
(99.5%), MS-DOS `A:` **480 KB (4.8%)**, `D:` 9.7 MB (99.9%), `E:` 9.0 MB
(100%). No target name in this sheet had been used before. The staged binary
round-tripped md5-identical off **both** images and is the same file as
`ckermitw.exe` in the tree: `d76c10b2401d3685f8dd2f2304f717d1` in three
places.

---

### 1. The FreeDOS console arm works — §16ao's item is closed

**Leg FDHS**, snapshot `snap/victor9k/0039.png`, taken 140 s in with the data
phase at **42 per cent**:

```
C-Kermit 11.0.508, 2026/08/09, victor
       Current Directory: A:
    Communication Device: COM2 (remote host is UNIX)
     Communication Speed: 9600
                 Parity: none
             RTT/Timeout: 04 / 12
               RECEIVING: rcvfdhs.dat => rcvfdhs.dat
               File Type: BINARY
               File Size: 32768
            Percent Done: 42 /////////////////
                             ...10...20...30...40...50...60...70...80...90...100
```

...through to the `^\X to cancel file` key legend on the bottom two rows.
**Every field is in its place, the percent bar advances against its scale,
and the screen is not scrolling** — which is the whole claim, because the
display is drawn by cursor addressing and a console that ignored the escape
sequences would scroll instead. This is the **first time the FreeDOS console
arm has been seen to execute**, and with §16az's `irq1=09` it is the second
and last of the two FreeDOS branches §16av shipped unexecuted.

**Leg FDH** ran the same thing to completion: byte-exact, SUCCESS, 54.185 s,
604 cps, and its end-of-run snapshot (`0040.png`) carries the counter block,
ending `Last Message: SUCCESS. Files: 1, Bytes: 32768, 630 CPS`.

**The first attempt at FDHS produced a completely black screen, and the cause
was this sheet's own `.BAT`.** It ran `CKERMITW ... -r > FDHS.OUT`, and §16u
records that C-Kermit's transfer display *goes away under the redirect that
records the `v9k:` counters*. So the picture and the `.OUT` cannot come out
of one run, and a display leg cannot have a redirect at all. **§16az's leg
FDG had that redirect too** — so it could not have engaged the display for a
second, independent reason on top of the one §16az gave (`-f` never starts a
transfer). The counters here are read off the screen instead, which works
because the block is 20 lines and the screen is 25.

Two things the display shows that are worth knowing: `Transfer Rate, CPS: 0`
and `Estimated Time Left: (unknown)` **during** the transfer, correct at the
end. That is `NOFLOAT`/`GFTIMER` (§16j), not a FreeDOS defect.

---

### 2. The `rcvfil()` stall is the destination directory — and it is not the DOS

The F packet is sent, and then either it is ACKed immediately or it times out
at 8, 16 and 24 s and is ACKed at ~26. **Six MS-DOS legs and two FreeDOS legs,
one variable at a time:**

| leg | DOS | destination | entries | free | display | F ACKed | T/R | host clock | cps |
|---|---|---|---:|---:|---|---:|---|---:|---:|
| **VA** | MS-DOS 3.1 | `A:\` | 167 | 4.8% | off | **t+26 s** | 3 / 6 | 78.939 | 415 |
| **VB** | MS-DOS 3.1 | `A:\` | ~174 | ~3.9% | **on** | **t+27 s** | 3 / 6 | 91.507 | 358 |
| **VC** | MS-DOS 3.1 | `D:\` | 3 | 99.9% | off | t+0 | 0 / 0 | 46.148 | 710 |
| **VD** | MS-DOS 3.1 | `D:\` | **167** | 86.3% | off | t+1 | 0 / 0 | 46.496 | 704 |
| **VE** | MS-DOS 3.1 | `E:\` | 10 | **5.3%** | off | t+0 | 0 / 0 | 46.647 | 702 |
| **VF** | MS-DOS 3.1 | `A:\VESUB` | 0 | 3.5% | off | t+2 | 1 / 1 | 49.270 | 665 |
| **FDJ** | FreeDOS | `A:\` | 56 | 99.5% | off | t+1 | 1 / 1 | 50.004 | 655 |
| **FDH** | FreeDOS | `A:\` | 58 | 99.5% | **on** | t+2 | 1 / 1 | 54.185 | 604 |

*VB's two `A:` figures are interpolated, not read at leg time: the volume
was measured at 167 entries / 4.8% free before VA and 178 / 3.5% after VB,
and the legs themselves added the difference.*

Every one of those legs ran **the same binary**, at the same rate, on the same
host, within one hour.

**What the table kills, in the order the legs killed it:**

1. **The display is not the cause.** VA ran `--nodisplay` and stalled exactly
   as §16ay UA did with the display on. `xxscreen(SCR_FN,...)` sits on
   `rcvfil()`'s own path two lines after the suspect and was the best a priori
   candidate; it is out. VB confirms from the other side — display on, same
   stall, same 3/6.
2. **The DOS is not the cause.** VC/VD/VE are MS-DOS 3.1 legs with no stall at
   all. §16az's FreeDOS-versus-MS-DOS observation was real and its explanation
   was wrong, and it was §16az itself that said so — *"it is not yet a cause…
   nothing here separates the DOS from the filesystem from the disk image."*
3. **The root-entry count is not the cause.** VD is VC with `D:\` **padded to
   167 entries**, the same count as `A:\`, and it is 348 ms from VC. So a FAT
   root directory scan is not what costs 26 seconds.
4. **Free-space scarcity is not the cause.** VE filled the untouched third
   volume to **5.3% free** — `A:` was at 4.8% — and it is 499 ms from VC.
5. **The volume is not the cause either.** VF received into a **subdirectory
   of the very volume VA stalled on**: same drive, same fragmentation, same
   3.5% free, same DOS, same binary. F packet ACKed at t+2.

**So the stall belongs to `A:\` — that specific root directory — and to
nothing else this sitting could vary.** VC, VD, VE and VF span a 3.1-second
band (46.148 → 49.270) and VA and VB sit 30 to 45 seconds above it.

**No mechanism is claimed, and that is deliberate.** What is left after five
eliminations is something particular to that root directory that neither its
entry count nor the volume's free space captures — its *capacity*, its
population of deleted (0xE5) slots, the fragmentation of the entries
themselves. `rcvfil()` calls `zchko()` (`ckufio.c:2496`), which creates the
incoming file, `isatty()`s it, deletes it again and only then asks
`access(".",W_OK)`; that is three DOS directory operations on the suspect
directory before a single data byte moves, and it is where the next leg
should look. **The next leg is cheap and obvious: a `-d` run into `A:\`.**
§16aw's rule says never to combine `-d` with a throughput claim, and this is
not one — the stall is a single discrete 26-second event and the debug log
names calls, which is exactly what is wanted.

**`A:\` is where every measurement in this port's history has been taken**,
so the practical consequence is immediate: **the ~27 s stall is in the whole-
run cps of §16aj FA, §16ar WD, §16ay UA and UE, and it is a property of that
directory rather than of the port.** §16ay's warning to say which cps you are
quoting stands, and this sitting supplies the missing figure: **on the same
machine, same DOS, same binary, a clean receive is 46.1–46.6 s and 702–710
cps** where `A:\` gives 78.9 s and 415.

#### And it retracts an instrument verdict

§16ar reported that its new `dec` counter *"cannot tell a decode from a
silence — all four legs read `max = 3250 cs`, 32.5 s, and the guard built for
it never fired"*. **`dec max` reads 3250 on VA and 3350 on VB, and 100, 100,
150 and 150 on the four clean legs — every one of them at decode #3, which is
the F packet.** The counter was not failing to discriminate; it was reporting
this stall, in every leg §16ar ran, and §16ar had no leg without the stall to
compare against. **A counter that reads the same number on every leg of a
sitting is only an artefact if a leg exists that should have moved it.**

---

### 3. What the display costs, on two DOSes, on matched wire

Both pairs are as tight as this project gets — **`rxbytes` identical inside
each pair**, which means the two legs put the same number of bytes on the
wire and differ only in what the foreground did with them.

| | wire (`rxbytes`) | host clock | Victor `elapsed` | `wcon` (console writes) |
|---|---:|---:|---:|---:|
| FDJ (FreeDOS, off) | 39,576 | 50.004 s | 5,190 cs | `n=1 tot=11 cs` |
| FDH (FreeDOS, **on**) | **39,576** | 54.185 s | 5,795 cs | `n=423 tot=601 cs` |
| difference | **0** | +4.181 s | **+6.05 s** | **+5.90 s** |
| VA (MS-DOS, off) | 37,787 | 78.939 s | 10,200 cs | `n=1 tot=0 cs` |
| VB (MS-DOS, **on**) | **37,787** | 91.507 s | 10,850 cs | `n=462 tot=400 cs` |
| difference | **0** | +12.568 s | +6.50 s | +4.00 s |

On FreeDOS the three routes agree: the console writes cost 5.90 s, the
Victor's own clock says 6.05, and the host says 4.18. **Quote ~6 s, about
12% of a 32 KB receive at 9600.**

**On MS-DOS the host clock says +12.568 s and the two Victor-side counters
say +6.50 and +4.00, and that disagreement is not resolved here.** Both legs
carry the `A:\` stall, whose length is set by the host's own 8/16/24 s retry
ladder and moved by one second between them, so the host clock across a
VA/VB pair is measuring the stall as well as the display. **Use FreeDOS's
pair for the display's cost; use MS-DOS's only for the counters.**

**A by-product: FreeDOS's console is slower per write than MS-DOS 3.1's** —
601 cs over 423 writes against 400 cs over 462, 14.2 ms against 8.7. A
candidate is sitting in §16az: `entry.asm:280` busy-waits on the µPD7201's
TBE and writes an `H` **on every INT 21h call**, and a console write is an
INT 21h call. That is a hypothesis with an obvious test (a kernel built with
the trace off) and it is **not** a measurement — one `wcon` tick is not one
INT 21h call.

---

### 4. The half-second clock quantum is Victor **MS-DOS 3.1's**, not the machine's

§16n found that every timing figure this port had ever printed was a multiple
of 50 hundredths and concluded *"this machine's DOS clock advances by half a
second"*; §16o confirmed on real hardware that the quantum is the Victor's and
not MAME's. **Both stand, and this sitting adds the third term: it is the
DOS's.** On the same emulated machine, in the same hour:

| | MS-DOS 3.1 legs | FreeDOS legs |
|---|---|---|
| `wfile max=` | 0, 50, 50, 100, 100 | **28**, 16 |
| `wcon max=` | 0, 50 | **11**, 6 |
| `txgap tot=` | 0, 50, 100 | **67**, 362 |
| `dec max=` | 100, 150, 150, 3250, 3350 | **126**, 176 |
| `nap tot=` | 50 | **71** |

**Every MS-DOS figure is a multiple of 50; not one FreeDOS figure is.**
FreeDOS's INT 21h `AH=2Ch` resolves finer than half a second, so **"quote
`tot=`, never `max=`" (§16n) is an MS-DOS 3.1 rule and does not need to be
applied to a FreeDOS leg** — and, the other way round, a `max=` from a
FreeDOS leg cannot be compared with one from an MS-DOS leg at all. §16az's
unexplained `nap per=` swing (682/819 against MS-DOS's steady 409) is the
same fact seen from the calibration side and is now half-explained: the loop
is calibrating against a different clock, not a wobbly one.

---

## Verdict

**The FreeDOS console arm works** — the last of §16av's two unexecuted
FreeDOS branches, closed with a picture of the transfer display drawn by
cursor addressing on FreeDOS for Victor. §16ao's item is done.

**The `rcvfil()` stall is `A:\`, not FreeDOS-versus-MS-DOS.** Five candidate
causes were eliminated by five legs each differing from a control in one
thing, and the surviving one is the specific directory every measurement in
this port's history has been taken in. **It is not a port defect and it has
never been one**; it is 30–45 s of every 9600 MS-DOS receive figure this tree
has published, and a clean receive on the same machine is 46 s and ~705 cps.

**What is not proven:** the mechanism inside `A:\`. Five things are ruled out
and the sixth is not named. One `-d` leg into `A:\` should settle it.

**No code changed. No upstream edit — still twenty.** Nothing in this sitting
is a claim about the build; every leg ran md5 `d76c10b2…`.

## The method note

The strong result here came from refusing the cross-sitting pair. §16az's
own closing said its FreeDOS/MS-DOS comparison was an observation and not a
measurement, and the obvious repair — run one leg per DOS on the same day —
would have produced a *tighter* version of the same wrong answer, because the
two DOSes still differ in a dozen ways at once. **What made it a measurement
was moving the experiment inside one DOS**: VC, VD, VE and VF are all MS-DOS
3.1, and each differs from VA in exactly one property of the destination.
The cross-DOS pair (FDJ against VA) is in the table and is the *least*
informative row in it.

Second note, and it is §16u's, learned by walking into it: **a leg that has
to show you a screen cannot have a redirect on it.** The counters and the
picture are two artefacts and they need two runs. §16az's FDG had the same
defect and nobody noticed, because it had a second reason to fail.

# HW_TEST_16ao — what does the fullscreen display cost at 38400?

Eight legs, one sitting. Everything is built and staged; nothing in this
sheet needs a compile.

**The question.** §16ao shipped the fullscreen file-transfer display and
proved it correct on this machine, both directions, at 38400. What it did
**not** measure is what it costs. The only figure that exists is `wcon
tot = 450 cs` on a 32 KB receive **at 9600 under MAME** — 3.8% — and that
number does not transfer: §16ag established that at 9600 the foreground has
~555 µs of slack per received byte and **at 38400 it has none**. The
display adds 55 cursor addresses per repaint, each preceded by an
`fflush()`, onto the path §16v measured at 485 µs per wire byte.

**The second question, which matters more.** Does the display cost ring
margin? `rxpeak` was 2,581 of 4,096 at 38400 in §16af with `rxfull = 0`. If
painting a screen mid-transfer pushes occupancy up, that is not a cost, it
is a defect.

---

## The control is the same binary, and that is the good part

Every A/B this project has run compared two binaries and had to reason about
§16w's code-size sensitivity. **This one does not.** `xxscreen()` expands to

```c
if (local && !backgrd && fdispla != XYFD_N) ckscreen(...)
```

and `conbgt()` sets `backgrd = 1` whenever `isatty(0) && isatty(1)` is
false (`ckutio.c:9643`). **So redirecting stdout turns the display off at
runtime, in one binary, with no code-size difference at all** — both arms
execute the same instructions, one of them short-circuits.

| | display | stdout | what you get |
|---|---|---|---|
| **arm A** | OFF | `> STEP<leg>.OUT` | `.host`, `.pkt`, **and the `v9k:` counters in a file** |
| **arm B** | ON | console | `.host`, `.pkt`, **and the counters only on screen** |

**Arm B's counters must be photographed. This is not optional** — `rxfull`
and `rxlost` are the answer to the second question, and there is no other
route to them. MS-DOS 3.1 cannot redirect handle 2, so there is no way to
have the display and the file at once.

**The measurement is therefore the HOST clock**, which both arms capture
identically in `.host`. The Victor's `elapsed=` is available on arm A only.

---

## §0. Preconditions — check all six before the first leg

Two sittings in this project's history were lost to a precondition nobody
checked. These are the ones that cost them.

1. **Free space.** `vtg_image_util info ~/projects/mame/victor_kermit.img`
   → partition 0 must show **> 300 KB free**. It is at **704 KB** as staged.
   Four receive legs write 32 KB each. **Out of disk makes the Victor hang,
   not fail** (§16al) — eleven packets then silence forever.
   Partition 1 (`D:`) is 9.7 MB and 100% free if you ever need room.
2. **The binary.** **`CKERMITW.EXE`, 225,822 bytes, md5
   `3759f47f44202ae8e498c5ac7adf822a`** — HEAD, with the display *and*
   `--nodisplay`. Every `.BAT` in this sheet names `CKDISP`, which was the
   staging name while the display was under test; **`CKDISP.EXE` no longer
   exists on the image** and the `.BAT`s must be re-staged against
   `CKERMITW` before a re-run.

   **The legs recorded in §16ap ran an earlier build** — 225,638 bytes, md5
   `4502705d…`, commit `1962e1a`, before `--nodisplay` added 184 bytes. The
   difference is one XI record that scans the command tail once before
   `main()` and finds nothing; it is outside the timed interval and does not
   affect the figures. A re-run is not comparing the same binary, though, so
   say which one it was.

   **A `--nodisplay` re-run is cheaper than this sheet.** The whole reason
   arm A used a redirect was that no runtime switch existed. It does now, so
   both arms can keep stdout on the console and **both** can report their
   counters — no photographs, and `wcon n=` distinguishes the arms
   directly. If you re-run this, re-run it that way.
3. **The fixture.** `TRANS.DAT` on the image, 32,768 bytes, md5
   `d94d2beda069ef0ef340977e7fd6995d`. The host copies `rcvha.dat` …
   `rcvhh.dat` are byte-identical to it, so **wire bytes are comparable
   across every leg**. They are `.gitignore`d, so regenerate them in the
   tree root if they are missing:

   ```sh
   vtg_image_util copy ~/projects/mame/victor_kermit.img:0:\\TRANS.DAT trans.dat
   for l in ha hb hc hd hg hh; do cp trans.dat rcv$l.dat; done
   md5 -q trans.dat        # must be d94d2beda069ef0ef340977e7fd6995d
   ```
4. **Target names are fresh and every receive `.BAT` deletes first.**
   `SET FILE COLLISION` is `BACKUP` and BACKUP cannot work on FAT; the
   signature is S, F, A, then **Z with data `D`**, a ~287-byte packet log,
   and `No files were transferred (refused: destination file already
   exists)`. `RCVHA`…`RCVHH` have never been used and each `.BAT` opens
   with `IF EXIST … DEL …`.
5. **Power-cycle the Victor *and* the Pico between every leg.**
6. **Do not write to the image while the machine is running.**

---

## Decision rules — read these before running, not after

Written down first so the result cannot be chosen afterwards. This is the
rule that removed the `errno` change in §16ah.

1. **Noise floor is measured this sitting, not assumed.** HA and HC are the
   same leg twice. `spread = |HA − HC|` on the host clock. §16ah saw
   1.277 s, §16ak saw 398 ms — it is a *bound, not a floor*, and it is the
   host (§16al). **If `|mean(arm B) − mean(arm A)| < spread`, the answer is
   "below this sitting's noise floor" and no number is quoted.**
2. **Safety beats cost.** If any arm-B leg shows `rxfull != 0` **or**
   `rxlost != 0` while its adjacent arm-A control is clean, stop treating
   this as a cost measurement: the display is eating ring margin at 38400
   and needs a runtime switch, not a benchmark.
3. **Byte-exact or excluded.** Every leg is md5-compared. A leg that is not
   byte-exact is a failure to report, never a timing sample.
4. **Off-shape legs are compared by non-line cost, not clock.**
   `non-line = host clock − (wire bytes × 260 µs)`. That is what made §16al
   leg GP usable and what withdrew §16ak's "+11%". Expect roughly a third of
   legs to go off-shape.
5. **Adjacent pairs only.** The order below alternates arms deliberately.
   **Compare nothing across a gap** — the same `CKPRE` binary gave 18.29 s
   in §16ah and 21.43 s in §16al with the wire held constant.
6. **`rxpeak` is only comparable between legs with the same retransmission
   count** (§16ag leg AM: 17 of 4,096 without a resend, 299 with one).

---

## The legs

Run in this order. Host command in every case:

```sh
kermit -C "take s16ao<LEG>.ksc, exit" > s16ao<LEG>.host
```

Start the Victor first and **wait for it to load** — `CKDISP` is 225 KB off
SASI and takes 40–85 s before `main()` runs. A host that gives up looks
exactly like a Victor that failed; `set retry 30` is in every take-file.

| leg | dir | rate | display | Victor | host | artefacts |
|---|---|---|---|---|---|---|
| **HA** | recv | 38400 | **off** | `STEPHA` | `s16aoHA.ksc` | `.host` `.pkt` `STEPHA.OUT` |
| **HB** | recv | 38400 | **on** | `STEPHB` | `s16aoHB.ksc` | `.host` `.pkt` **photo** |
| **HC** | recv | 38400 | **off** | `STEPHC` | `s16aoHC.ksc` | `.host` `.pkt` `STEPHC.OUT` |
| **HD** | recv | 38400 | **on** | `STEPHD` | `s16aoHD.ksc` | `.host` `.pkt` **photo** |
| **HE** | send | 38400 | **off** | `STEPHE` | `s16aoHE.ksc` | `.host` `.pkt` `STEPHE.OUT` |
| **HF** | send | 38400 | **on** | `STEPHF` | `s16aoHF.ksc` | `.host` `.pkt` **photo** |
| **HG** | recv | 9600 | **on** | `STEPHG` | `s16aoHG.ksc` | `.host` `.pkt` **photo** |
| **HH** | recv | 9600 | **off** | `STEPHH` | `s16aoHH.ksc` | `.host` `.pkt` `STEPHH.OUT` |

- **HA–HD** are the headline: two controls and two treatments, interleaved.
- **HE/HF** ask whether the answer differs by direction. Sending has less
  foreground pressure (§16ah: 1,386 cps against 1,167), so if the display
  is free anywhere it is here.
- **HG/HH** are the tie to MAME's 3.8%. They are the only legs where a
  9600 comparison is available, and they say whether the emulator's figure
  was honest.

**Before HE/HF**, delete the host's `TRANS.DAT` — the host receives under
that name and `SET FILE COLLISION` bites on the host side too.

**Photographs must show the whole `v9k:` block**, from `isr=asm` down to
`mdm`. On a 25-line screen it fits under the statistics. The two lines that
matter most:

```
v9k: rxlost=0 rxfull=0 rxpeak=NNNN of 4096
v9k: wcon n=NNN max=NN tot=NNN cs
```

---

## Reading it

**The cost, if any:**

```
display cost = mean(HB, HD) − mean(HA, HC)          [host clock, seconds]
             = ... as a fraction of mean(HA, HC)    [percent]
```

Check it against `wcon tot=` from the HB/HD photos, which is the *same
quantity measured a different way* — console-write time in centiseconds,
straight out of §1 item 9's 17.7 s foreground bucket. **If the clock
difference and `wcon tot=` disagree by much more than the spread, one of
them is wrong and the counter is the more trustworthy**: it is counted, not
timed, and it does not care about the host.

**What each outcome licenses:**

- **Below the noise floor, `rxfull = 0`** → the display is free at 38400.
  Record it and close the item. This is the expected result.
- **Measurable but small (< 5%), `rxfull = 0`** → a real cost, worth
  quoting, ships as-is. The display is a feature, not an optimisation.
- **Large (≥ 5%), or `rxfull`/`rxlost` non-zero on arm B** → §16ao needs a
  follow-up: a `--nodisplay` switch through §16i's priority-0 XI mechanism,
  which is the same shape as `--safe-server` and `--rtscts` and costs no
  upstream edit. Do **not** reach for `-dNOCURSES` as the answer: that
  deletes the CRT display too, and it changes code size by 18,880 bytes,
  which puts §16w back in play.

**One thing that will look like a defect and is not.** Arm A's `.OUT` will
report `wcon n=` in the low single digits and arm B's photo will show
several hundred. That is the independent variable working, and it is the
cheapest confirmation that the leg did what the sheet asked.

---

## What this sheet deliberately does not do

- **It does not test the display's correctness.** That is done — §16ao,
  real hardware, both directions, 38400. This is cost only.
- **It does not touch FreeDOS.** The VT52/Z19 sequences will paint noise
  under FreeDOS-for-Victor, whose `victor_ansi.asm:141` parses only `ESC [`.
  That is §1 item 14 and needs a different machine state, not a different
  leg.
- **It does not measure the parser build.** `CKICP.EXE` on the image
  predates §16ao and has no display at all. If you want the fullscreen
  display at the `C-Kermit>` prompt, that binary has to be rebuilt and
  re-measured first — it is the trap §16ai's staging notes are about.

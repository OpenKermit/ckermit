# HW_TEST_16aq — what does the bulk-read arm buy at 38400, and does it survive a bad line?

Upstream **edit 18** puts a bulk arm at the bottom of `ttinl()`'s per-byte
loop: once `myread()` has refilled `mybuf[]`, the arm finds the packet
terminator with `memchr()` and copies the run with `memcpy()` instead of
walking it a byte at a time through the macro. On a 5 MHz 8088 that is the
only way to move bytes without paying instruction fetch at ~4 clocks a byte,
which §16w established is what actually bounds this machine.

**Correctness is already settled twice and this sheet is not about it.**
`v9k/proofs/vttinl.c` compares the arm against the byte loop transcribed out
of `wcc -pl` output — **100,023 cases, 0 failures**, 13 of 13 deliberate
mutants caught. And §16aq's MAME legs JA/JB came back byte-exact with
**identical wire bytes, packet counts and prefix counts**, `rxlost = 0
rxfull = 0` in both. What is open is **cost**, and one question about a bad
line.

---

## Why MAME could not answer it, and what that predicts

Legs JA and JB read **`elapsed = 10,350 cs`, identical**. That is not
"the arm is free"; it is the harness declining to answer, for two reasons
that both point the same way:

1. **§16ag's structural point, for the third time.** At 9600 the foreground
   has ~555 µs of slack per byte and at 38400 it has none. A per-byte
   foreground saving has room to hide at 9600.
2. **The arm barely had anything to chew on.** JA copied 40,840 bytes in
   **3,441 runs — 11.9 bytes per run** — because `rxpeak` was 303 of 4,096.
   The ring never built up, so `myfillbuf()` kept handing back tiny chunks
   and there was nothing for `rep movsw` to amortise over.

**That is the mechanism variable, and it is why this sheet exists.** At
38400 `rxpeak` sits at 2,500–3,000 (§16af leg AG: 2,581), i.e. the foreground
is far enough behind that a refill should return hundreds of bytes. **The
prediction is that the effect scales with how far behind the foreground is,
which is exactly the regime MAME cannot reach (§16n: 9600 is its ceiling).**

**Record `rxbytes / bulk n` on every leg.** If mean run length at 38400 is
not much larger than MAME's 11.9, the arm cannot be doing much and the
result is explained before it is argued about.

### How big should the effect be

§16af put `ttinl()`'s per-byte loop at ~133 µs of the ~485 µs per wire byte.
If the arm cuts that by 3–4×, the saving is ~3.5 s of a ~28 s transfer, or
~13% — comfortably above §16ah's ~1.3 s bench spread.

**Do not trust that number.** It is a hand-costed 8088 prediction, and this
tree has now produced **five** of those and been wrong every time, once in
sign (§16ag's `errno` change, predicted faster, measured 98 ms slower).
Treat it as an ordering argument — "large enough to be worth two legs per
arm" — and nothing more.

---

## The control is the same binary, and that is the good part

`--nobulk` turns the arm off **at run time**, so arm A and arm B are the
same 226,330 bytes in the same places, differing in one compare outside the
loop. §16ap is the precedent and the reason: a control built from a second
binary is also a control for §16w's code-size sensitivity, and this project
has spent whole legs (§16af's null leg AH) establishing that the rebuild was
not what moved. Here there is nothing for that to act on.

**`v9k: bulk sel= n=` is what makes it a control instead of an assumption.**
`sel` is what the command line asked for; `n` is what the arm actually did.
Under MAME: JA `sel=1 n=3441`, JB `sel=0 n=0`. **An equivalence test cannot
see a switch that silently failed** — a correct arm returns the byte loop's
answer either way — which is why the counter exists at all.

---

## §0. Preconditions — check all six before the first leg

Two sittings in this project's history were lost to a precondition nobody
checked. These are the ones that cost them.

1. **Free space.** `vtg_image_util info ~/projects/mame/victor_kermit.img`
   → partition 0 must show **> 300 KB free**. It is at **5.1 MB (52.6%)** as
   staged. Seven legs write 32 KB each. **Out of disk makes the Victor hang,
   not fail** (§16al) — eleven packets then silence forever, because §0d's
   `alarm()` bounds the read and nothing bounds a failed write.
   Partition 1 (`D:`) is 9.7 MB and 100% free if you ever need room.

2. **THE BINARY, AND THIS IS THE TRAP §16ap WALKED INTO.**
   **`CKBULK.EXE`, 226,330 bytes, md5 `a9fa6b5c0f39a1f586c79e836f1a8bfb`** —
   staged and round-trip verified off the image. Every `.BAT` in this sheet
   names **`CKBULK`**, not `CKERMITW`.

   **`CKERMITW.EXE` on the image is deliberately still the 225,822-byte
   pre-edit-18 build.** If a `.BAT` says `CKERMITW --nobulk`, that binary
   has no such switch and answers **`Extended options not configured`** —
   which is the *same string the unknown-option control is supposed to
   produce*, so it reads exactly like a broken switch rather than a stale
   binary. A sheet that names a `-d` flag must also name the staged binary
   that carries it, or the flag is a suggestion.

3. **The fixture is `FIXTURE.DAT`, NOT `TRANS.DAT`.** 32,768 bytes on the
   image, md5 `d94d2beda069ef0ef340977e7fd6995d` — verified by extracting it,
   not by trusting the name. **`TRANS.DAT` is not on this image**; the first
   draft of this sheet said it was, inherited from §16ao, and leg KS would
   have sent a file that does not exist. The tree root still holds
   `TRANS.DAT.~1~`…`~3~` with the same md5, which is what makes the mistake
   easy to make and worth writing down.

   The host copies must be byte-identical to it so **wire bytes are
   comparable across every leg**. They are `.gitignore`d, so regenerate them
   in the tree root if missing:

   ```sh
   vtg_image_util copy ~/projects/mame/victor_kermit.img:0:\\FIXTURE.DAT fixture.dat
   for l in ka kb kc kd kn kp; do cp fixture.dat rcv$l.dat; done
   md5 -q fixture.dat      # must be d94d2beda069ef0ef340977e7fd6995d
   ```

4. **Target names are fresh and every receive `.BAT` deletes first.**
   `SET FILE COLLISION` is `BACKUP` and **BACKUP cannot work on FAT**; the
   signature is S, F, A, then **Z with data `D`**, a ~287-byte packet log,
   and `No files were transferred (refused: destination file already
   exists)`. `RCVKA`…`RCVKP` have never been used and each `.BAT` opens with
   `IF EXIST … DEL …`. A rule a person has to remember is not a fix.

5. **A re-run gets a new leg letter.** §16ap leg HJ re-used `s16aoHB.ksc`
   and destroyed leg HB's `.host` and `.pkt`. §6's unique-log-name rule is
   the bench's too.

6. **Power-cycle the Victor *and* the Pico between every leg, and do not
   write to the image while the machine is running.**

---

## Decision rules — read these before running, not after

Written down first so the result cannot be chosen afterwards. This is the
rule that removed the `errno` change in §16ah.

1. **A leg whose `bulk sel=`/`n=` disagrees with what the `.BAT` asked for
   is VOID, not a null result.** Arm B must show `sel=1` and `n > 0`; arm A
   must show `sel=0` and `n = 0`. This is the one new rule in this sheet and
   it is the one that protects against the §16ai failure — an instrument
   that was overwritten before anything read it, producing a clean null that
   meant nothing. **Read the line before reading the clock.**

2. **Noise floor is measured this sitting, not assumed.** KA and KC are the
   same leg twice, as are KB and KD. `spread = max(|KA−KC|, |KB−KD|)` on the
   host clock. §16ah saw 1.277 s, §16ak saw 398 ms — it is a *bound, not a
   floor*, and §16al established it is the host and not the Victor. **If
   `|mean(arm B) − mean(arm A)| < spread`, the answer is "below this
   sitting's noise floor" and no number is quoted.**

3. **Byte-exact or excluded.** Every leg is md5-compared. A leg that is not
   byte-exact is a failure to report, never a timing sample. For this edit
   in particular: the failure modes are resync and truncation, and a
   byte-exact transfer is the *minimum* bar, not the result.

4. **Safety beats cost.** If any arm-B leg shows `rxlost != 0` or
   `rxfull != 0` while its adjacent arm-A control is clean, stop treating
   this as a cost measurement and report it as a defect.

5. **Off-shape legs are compared by non-line cost, not clock.**
   `non-line = host clock − (wire bytes × 260 µs)`. That is what made §16al
   leg GP usable and what withdrew §16ak's "+11%". Expect roughly a third of
   legs to go off-shape.

6. **Adjacent pairs only.** The order below alternates arms deliberately.
   **Compare nothing across a gap** — the same `CKPRE` binary gave 18.29 s
   in §16ah and 21.43 s in §16al with the wire held constant.

7. **`rxpeak` is only comparable between legs with the same retransmission
   count** (§16ag leg AM: 17 of 4,096 without a resend, 299 with one). And
   **ask where an `rxpeak` IS before reading it as a cap** — `mapoffset.py`,
   per §16ak leg DE.

---

## Part 1 — the cost, four legs, 38400 receive

Alternating, back to back, power-cycle between each.

| leg | arm | `.BAT` | target | host take-file |
|---|---|---|---|---|
| **KA** | B, bulk on | `STEPKA` | `RCVKA.DAT` | `s16aqKA.ksc` |
| **KB** | A, `--nobulk` | `STEPKB` | `RCVKB.DAT` | `s16aqKB.ksc` |
| **KC** | B, bulk on | `STEPKC` | `RCVKC.DAT` | `s16aqKC.ksc` |
| **KD** | A, `--nobulk` | `STEPKD` | `RCVKD.DAT` | `s16aqKD.ksc` |

Victor side, e.g. `STEPKA.BAT` (CRLF, and verify CRLF *after* it lands on
the image):

```
IF EXIST RCVKA.DAT DEL RCVKA.DAT
IF EXIST STEPKA.OUT DEL STEPKA.OUT
CKBULK --nodisplay -l /dev/seriala -b 38400 -r > STEPKA.OUT
```

`STEPKB` and `STEPKD` are the same line with **`--nobulk`** added.

**`--nodisplay` is on every leg deliberately.** §16ap measured the display
at 4–5 s per 32 KB at any line rate, which is larger than the effect under
test. Taking it out of both arms is not optional.

Host side, e.g. `s16aqKA.ksc`:

```
set speed 38400
set receive timeout 20
log packets s16aqKA.pkt
send rcvka.dat
statistics
```

The take-files deliberately do **not** set the line, so `~/.kermrc` is the
single place the adapter name lives — **check it names the adapter actually
plugged in** (§16v used `BG022B8M`, §16af used `ABBFKXM1`).

---

## Part 2 — the other direction, one leg

**KS: bulk on, `-s` a 32,768-byte file by name at 38400.**

This is a regression check, not a measurement. `ttinl()` is the *packet
reader*, so on a send leg it only reads ACKs — tiny packets, no long runs,
and the arm should be almost inert. What it proves is that the arm does not
break the direction it was not designed for. **Expect `bulk n` to be small
and `sel=1`.** If `n` is large on a send leg, something is wrong with the
reasoning above and it is worth understanding before Part 3.

```
IF EXIST STEPKS.OUT DEL STEPKS.OUT
CKBULK --nodisplay -l /dev/seriala -b 38400 -s FIXTURE.DAT > STEPKS.OUT
```

---

## Part 3 — the bad line, two legs

**This is what the 10-foot cable wrapped around mains wiring is for**, and
the framing changed once the preprocessor was consulted, so read this before
running it.

**There is no length field in play.** `ckvictor.h` defines `NOPARSEN`, which
suppresses `PARSENSE`, which is what would have given length-driven packet
reading. This build reads a packet by scanning for `eol` and nothing else.
So the arm's `memchr(src, eol, n)` is looking for **exactly** the byte the
byte loop looks for, on exactly the same stream.

**The consequence is a falsifiable prediction: corruption should make no
difference between the arms.** A mangled or lost terminator makes *both*
run to `max-1` or to the alarm, identically, because neither is reading a
length. There is no fast-resync path in one arm and not the other — that
only existed in the `PARSENSE` version of `ttinl()`, which this build does
not compile.

| leg | arm | `.BAT` | target |
|---|---|---|---|
| **KN** | B, bulk on | `STEPKN` | `RCVKN.DAT` |
| **KP** | A, `--nobulk` | `STEPKP` | `RCVKP.DAT` |

Run both under the **same** noise conditions — same cable routing, same
appliances running, back to back, and say in the write-up what the noise
actually was. Noise is not reproducible between sittings, so **only the
KN/KP comparison means anything; neither leg is comparable to KA–KD.**

**Read, per leg:** md5, `rxlost`, `rxfull`, host timeouts, host
retransmissions, `<crunched:...>` lines in the packet log, and `bulk n`.

**What would falsify the prediction:** KN taking materially more timeouts
than KP, or KN not byte-exact where KP is. Either would mean the arm's
recovery differs from the byte loop's, and the proof's equivalence claim
would need re-examining against whatever the line actually did.

**What a null result here is worth:** it closes the last thing the host
proof cannot reach — real corruption, arriving at real timing, through the
real chip. That is a genuine result and should be written up as one, not as
"nothing happened".

---

## Reading it

Per leg, from `STEPK?.OUT`:

```
v9k: bulk sel=1 n=NNNN          <- rule 1: check this FIRST
v9k: rxlost=0 rxfull=0 rxpeak=NNNN of 4096
v9k: rxbytes=NNNNN
v9k: elapsed=NNNN cs wire=NNN B/s
```

and from the host's `statistics` and `pktstat.py`:

- host clock, wire bytes, packets, retransmissions, timeouts
- **mean run length = `rxbytes / bulk n`** — the mechanism variable.
  MAME at 9600 gave **11.9**. If 38400 gives something in the hundreds, the
  scaling argument in this sheet holds whatever the clock says.

Two standing reading rules: the Victor's `elapsed=` and the host's
`statistics` **do not measure the same interval** (§16u — the Victor's is
wider, ~1.7 s on a clean run), and `wire=` is a receive-leg figure. Quote
the pair, never one alone. And `wcon tot=` / `wfile tot=` / `txgap tot=`
are sums of 0-or-500 ms samples — **`n=` is exact, `tot=` is ±1.5 s on one
leg** (§16ap). Do not quote `tot=` off a single leg.

---

## What this sheet deliberately does not do

- **It does not measure the send direction as a cost.** KS is a regression
  check. The arm is on the receive path.
- **It does not touch `NOPARSEN`.** The misnamed define (`ckvictor.h:1100`
  says "No network directory parse"; `ckcdeb.h:3971` means no parity sense,
  and with it no length-driven packet reading) is a real finding and a
  separate decision. Turning `PARSENSE` on would add per-byte header
  bookkeeping and the lookahead/pushback — i.e. move foreground cost the
  wrong way — and would invalidate this sheet's Part 3 reasoning. **Not in
  this sitting.**
- **It does not open the window.** `DFWSIZ` is still 1, and §1 item 12 is
  worth more than everything in this sheet (line and foreground are
  serialized at window 1, so overlapping them is worth ~+50% against this
  arm's low tens of percent). It needs flow control working end-to-end
  first, which §16an left waiting on the *host* — `stty -f <port> crtscts
  -hupcl` before `kermit`, or a host C-Kermit built with `POSIX_CRTSCTS`.
- **It does not re-run the unknown-option control.** §16aq leg JC did it
  under MAME: `CKBULK --nobulz` → `Extended options not configured`. The
  per-leg `bulk sel=` line covers it at the bench.

---

## Staging receipt

Backup taken before any of this:
`~/projects/mame/victor_kermit.img.bak-20260811-prebulk`.

| on the image | bytes | md5 | what it is |
|---|---:|---|---|
| `CKBULK.EXE` | 226,330 | `a9fa6b5c…` | **edit 18**, arm selectable at run time |
| `CKERMITW.EXE` | 225,822 | `3759f47f…` | HEAD before edit 18 — **left alone on purpose** |
| `FIXTURE.DAT` | 32,768 | `d94d2be…` | the fixture — **not `TRANS.DAT`, which is not on this image** |

Build figures for `CKBULK.EXE`: DGROUP **48,752 of 65,536 (74%)**, far code
191,592, image 226,330, **needs 240,378 (234K) at load, smallest Victor
384K** — unchanged from HEAD, which cost +508 bytes and +16 DGROUP. 18
compiler warnings, all stock upstream, **none added by the edit** (measured
against a stashed baseline, not assumed); `ckvictor.c` still compiles with
none.

**The seven `.BAT` files are staged**, 11 August 2026, and verified the way
§0 asks rather than the way that is convenient: each was copied *back off*
the image and compared to its source, and the CRLF count was taken from the
retrieved copy.

| `.BAT` | bytes | arm | target |
|---|---:|---|---|
| `STEPKA.BAT` | 131 | B, bulk on | `RCVKA.DAT` |
| `STEPKB.BAT` | 140 | A, `--nobulk` | `RCVKB.DAT` |
| `STEPKC.BAT` | 131 | B, bulk on | `RCVKC.DAT` |
| `STEPKD.BAT` | 140 | A, `--nobulk` | `RCVKD.DAT` |
| `STEPKN.BAT` | 131 | B, bulk on, **noisy** | `RCVKN.DAT` |
| `STEPKP.BAT` | 140 | A, `--nobulk`, **noisy** | `RCVKP.DAT` |
| `STEPKS.BAT` | 109 | B, bulk on, **send** | — |

All seven round-trip identical, every line CRLF. **`RCVKA`…`RCVKP` and
`STEPK*.OUT` confirmed absent from the image** — checked, not assumed, since
that is precisely the trap §0 item 4 describes. Free space after staging:
**4.7 MB (48.7%)**, against seven legs writing 32 KB.

**The host side is prepared too**, and it does not live on the image:

- **Six fixtures** `rcvka.dat` `rcvkb.dat` `rcvkc.dat` `rcvkd.dat`
  `rcvkn.dat` `rcvkp.dat`, each 32,768 bytes, each md5
  `d94d2beda069ef0ef340977e7fd6995d`, made from the image's own
  `FIXTURE.DAT` rather than from a tree copy. KS needs none — the host
  receives on that leg.
- **Seven take-files** `s16aqKA.ksc` … `s16aqKS.ksc`, each carrying its own
  leg's decision rules and traps in the comment header, matching
  `s16ahBC.ksc`'s shape. Every one was run through
  `kermit -y /dev/null -C "take <f>, exit"` and produced **no command
  errors**.

**The one thing that is yours, and it is the only thing left.** The
take-files deliberately do **not** `set line` — that is the bench
convention, and it makes `~/.kermrc` the single place the adapter name
lives. It currently reads `/dev/tty.usbserial-ABBFKXM1`, and that device
was **not present** when this was staged. §16v used `BG022B8M`, §16af used
`ABBFKXM1`. **Check it names the adapter actually plugged in before the
first leg**, or every leg will fail identically at `set speed` with
`?SET SPEED has no effect without prior SET LINE`.

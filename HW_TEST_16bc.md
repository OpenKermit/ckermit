# Bench run sheet — §16bc: six MAME-only sittings meet the machine

**This document is the thing to work from. Follow it top to bottom.**

**Written 20 August 2026, BEFORE any leg ran** (§16az's closing asked for
that; §16ba and §16bb established the habit). Every result box below is
empty until the leg that fills it has run. §0, the leg table and the
predictions are fixed in advance so that a leg cannot be redefined after
its output is seen.

**Leg letters are the H series.** `git ls-files | grep STEP` says A, B, C,
D, F, G, J, K, M, N, P, R, S, U, V, W, X, Y and Z are all spent — §16bb
lost three tracked `.BAT` files to exactly this — and **no `STEPH*` exists
anywhere in the tree or in `v9k/legs/`.** `HI` is skipped: it reads as H1.

---

## What this sitting is for

**The machine last saw this port at §16au, 12 August.** Everything since —
§16av, §16aw, §16ax, §16ay, §16az, §16ba, §16bb — is **MAME at 9600**, and
**38400 is a hardware-only path** (MAME cannot drive this machine above
about 9600; PORTING.md §16m). So the shipping binary has never run at the
rate the port ships.

What accumulated in that window:

| | |
|---|---|
| **upstream 11.0.508** | 77 commits, PR #3. Twenty edits verified against the merge's upstream parent, never against a wire at 38400 |
| **edits 19, 20, 21, 22** | `zfcdat()` dates, `REMOTE SPACE`, FAT collision names, the MAIL refusal |
| **§16av's six** | calibrated `nap()`, the collision default written into `ptab`, `ENOSPC` out of `zoutdump()`'s loop, Ctrl-C/INT 23h, the FreeDOS IRQ1 and ANSI console arms, `MAXWLD`/`SSPACE` 256/4096 |

Image **230,224 → 231,172**; needs **243,236 (237K)**; smallest Victor 384K,
unchanged. **§16w established that on this machine code size is execution
time**, and ~950 bytes moved, so a floor that has shifted is a thing this
sitting can see and MAME cannot.

**And one question stopped being blocked between sittings.** §16am found
that every RTS/CTS leg in §16ak, §16al and §16an tested a far end that was
never configured to stop: the bench Mac's C-Kermit **9.0.302 does not list
`POSIX_CRTSCTS`**, so its `tthflow()` is the same empty function this port's
own build compiles. §16bb built a **C-Kermit 11.0.508 client from this
tree** and `SHOW FEATURES` **does** list it. Legs HC/HD are the first
flow-control legs in this project whose far end can honour the signal.

**One item on the old list is already closed and is NOT here**: §1 item 5a,
control-character prefixing, was answered by §16ai legs CC/CD — `PX_CAU
exactly (32 values)`, 4,512 prefixes, 37,557 wire bytes against `PX_ALL`'s
8,869 and 41,945, a 10.5% saving, with a null leg 29 ms from its
predecessor. Do not re-run it.

---

## §0 — preconditions

| check | how | status |
|---|---|---|
| image backed up before any write | `cp` | ☑ **both images, 20 Aug** |
| **free space** | `vtg_image_util info <img>` — **and read it through a FRESH COPY: the tool caches by path (§0a)**. This row exists because an image at 0 bytes free makes a working port look thoroughly broken (§16al: eleven packets, then a hang, on a binary that had transferred cleanly twice) | ☑ **`A:` 888 KB, `D:` 8.4 MB** |
| leg-letter collision | `git ls-files \| grep STEP` — H series free, verified 20 Aug | ☑ |
| target names never used | `vtg_image_util list` — no `RCVH*`, no `STEPH*.OUT` | ☑ checked 20 Aug |
| the thirteen `.BAT`s and twelve `.ksc`s exist **and are staged** | §0a | ☑ **staged and round-tripped 20 Aug** |
| `.BAT` files still CRLF **after** landing on the image | `copy` back, `cat -v` | ☑ 13 of 13 |
| every receive `.BAT` opens with `IF EXIST <target> DEL <target>` **and `IF EXIST <target>.001 DEL <target>.001`** | §16al's rule, §16bb's addition. Machine-kept, not remembered | ☑ **written into all thirteen; see the receipt below** |
| each staged binary's md5 round-trips off the image | `copy` back, `md5` | ☑ `CKBB` `c42c3598…`, `CKICP` `181b6436…` |
| the `-d` guard: every leg reports **`deb=0`** except **HP**, which is `-d` on purpose **and must run `CKHPDBG.EXE`, not `CKBB.EXE`** | §16aw, and the pass-2 failure | ☑ corrected 21 Aug |
| proofs pass | `make -C v9k/proofs` — expect **5 of 5** | ☐ |
| **the host client is 11.0.508 from this tree** | `kermit -C "show versions, exit"` **and** `kermit -C "show features, exit" \| grep CRTSCTS` | ☐ |
| `~/.kermrc` names the adapter that is plugged in | | ☐ |

**Staging.** `CKBB.EXE` — HEAD with edits 21 and 22, **231,172 bytes, md5
`c42c3598d685e3204321c33a724e04b9`** — is the tree's `ckermitw.exe` bit for
bit and is the binary under test in every leg but HM. It was staged for
§16bb; **re-verify the md5 off the bench image rather than assuming the
MAME image and the Pico's copy are the same file.** §16ai's trap is a stale
binary sitting on an image across an edit, and it has cost this project an
item once already.

**One rebuild only, and it is for HM. ~~Do this~~ — DONE 20 August; kept as the record of how:**

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak clean && \
   make -f victorow.mak XFLAGS=-dKEEP_ICP ZT=-zt2048"
cp ckermitw.exe ckicp.exe
python3 v9k/tools/mzsize.py ckicp.exe        # RECORD IT
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak clean && make -f victorow.mak"
md5 -q ckermitw.exe                          # MUST be c42c3598…
```

Expected for `CKICP.EXE` from HEAD: DGROUP **59,632 of 65,536 (90%)**,
needs **453,986 (443K)**, **smallest Victor 640K** — the first upstream
merge ever to move a machine class. The bench Victor is 896K, so it loads;
that is the point of running it rather than a reason not to.

**Nothing else is rebuilt, and that is worth saying out loud: flow control
is a RUN-TIME switch** (`--rtscts` / `--xonxoff` / `--noflow`, §16i's
priority-0 XI mechanism), so HC and HD are **the same binary as HA**. §16w
has nothing to act on inside that pair, which is the property §16aq's
`--nobulk` control had and §16af had to spend a whole null leg to get.

**Shipping configuration under test**, so a `-d` flag in this sheet without
a staged binary beside it is a suggestion and not a setting:

```
V9K_RXBUFSIZ 4096   DRPSIZ 4000   DFWSIZ 1        V9K_OBUFSIZE 8192
V9K_FLOW FLO_NONE   hi 3072 / lo 1024             V9K_PREFIXING PX_CAU
```

---

## §0a — staging. **DONE 20 August. This is a receipt, not a to-do.**

Everything below is **on the image**. Backups taken first:
`victor_kermit.img.bak-20260820-full` and
`tools/freedos_stage1.img.bak-20260820`.

| on `A:` (partition 0) | | |
|---|---|---|
| `STEPHA` `STEPHB` `STEPHC` `STEPHD` `STEPHE` `STEPHJ` `STEPHK` `STEPHL` `STEPHM` `STEPHN` `.BAT` | 10 files | round-tripped off the image and `cmp`'d against the tree — **10 of 10 identical, CRLF intact after landing** |
| `FIXTURE.DAT` | 32,768 | already there, md5 `d94d2bed…` |
| `SPDTEST.KSC` | 331 | already there |

| on `D:` (partition 1) | bytes | md5 |
|---|---:|---|
| `CKBB.EXE` | 231,172 | `c42c3598…` — **rebuilt from HEAD today and bit-identical to what was already staged** |
| `CKICP.EXE` | **460,466** | `181b6436…` — **new**, the post-merge parser build, round-tripped |

| on the FreeDOS image | | |
|---|---|---|
| `STEPHF` `STEPHG` `STEPHH` `.BAT` + `CKBB.EXE` | | all four round-tripped, `CKBB.EXE` md5 `c42c3598…` |

`CKICP.EXE` measured from HEAD: **needs 453,986 (443K), DGROUP 59,632 of
65,536 (90%), smallest Victor 640K** — the predictions in §0 confirmed to the
byte. `ckermitw.exe` rebuilt clean from HEAD reproduces `c42c3598…` exactly.

### Three things the staging found that the sheet had wrong

**1. `TRANS.DAT` IS NOT ON THIS IMAGE.** §16ai leg CC sent it and it went in
some later cleanup. `A:\FIXTURE.DAT` is 32,768 bytes and md5 `d94d2bed…` —
byte-identical — and **edit 16 keys off the file SIZE, not the name**, so
`STEPHB.BAT` sends `FIXTURE.DAT` and the leg is unaffected. Had this not been
checked, HB would have failed at the bench with an error that looks exactly
like the defect edit 16 fixed.

**2. `CKBB.EXE` lives on `D:`, and the A: legs invoke it as
`D:\CKBB.EXE`.** `A:` could not hold another 231 KB copy. The loader reads
the image from `D:`; the program then runs with `A:` as the working directory
and writes there, so **the receive volume is still `A:`** and the match with
§16aq's control holds. Code and data are identical either way.

**3. `A:` was cleaned, from 360 KB free to 888 KB.** It could not hold the
A: legs: four 32 KB receives, ten `.OUT`s at one 8 KB cluster each, and HL's
~180 KB debug log come to ~424 KB. **34 leg artifacts were deleted and every
one was extracted into `v9k/legs/` first** — `RC.LOG` (178 KB), `RE.LOG`
(182 KB) and six `STEPN*.OUT` were **not** in the tree and would have been
lost, not merely deleted; they are now `v9k/legs/A-*`. `A:` is **888 KB free,
156 files**; `D:` is **8.4 MB free**.

**HL still runs last of the A: legs.** Its debug log is ~180 KB and the four
earlier receives are 128 KB of the 888. Extract and `cmp` `RCVHA/HC/HD/HE.DAT`
and delete them before HL. **Out of disk makes this machine HANG, not fail**
(§16av) — `zoutdump()`'s loop was fixed but a full volume is still the failure
mode that looks most like a broken port.

### And a harness finding, which is the one to carry

**`vtg_image_util info` CACHES BY PATH AND WILL HAND YOU A STALE ANSWER.**
The pre-staging backup, whose `list` correctly shows zero `STEPH*.BAT`,
reported **888 KB free** — the *post-cleanup* figure — while the identical
bytes copied to a fresh path reported the true **360 KB**. Every §0 in this
project's run sheets since §16al opens with `vtg_image_util info`, and §16al
lost a whole sitting to a free-space figure nobody had checked. **A
precondition tool that answers from a cache is worse than one that errors**,
which is §16ar's lesson in a new place: *a detector that can see itself and a
detector that cannot see the target give the same confident wrong answer.*
**Read free space through a fresh copy, or read it twice from different
paths, before believing it.**

**Not ours, and recorded so it is not chased:** `verify` reports **61 lost
clusters**, and the untouched pre-staging image reports the same 61. It
predates this sitting.

---

### Fixtures — recipes, because `.gitignore` excludes `*.dat`

The leg files are in git; **the fixtures cannot be**, so they are recorded
here as recipes and checked by md5. Regenerate with:

```python
open('rcvhk1.dat','wb').write(bytes((i*7  + 13)  & 0xFF for i in range(4096)))
open('rcvhk2.dat','wb').write(bytes((i*11 + 200) & 0xFF for i in range(4096)))
open('rcvhp.dat', 'wb').write(bytes((i*3  + 7)   & 0xFF for i in range(512)))
```

| file | bytes | md5 | used by |
|---|---:|---|---|
| `rcvhk1.dat` | 4,096 | `8fe1c6869cb7410cf85057c5c8cbe34d` | HK, first send into each name |
| `rcvhk2.dat` | 4,096 | `a15e88dd51460c75f7143982296482ef` | HK, second send — **different in every byte**, so a silent overwrite is visible on the disk |
| `rcvhp.dat` | 512 | `40257431b1db7d221e47fff0642b8414` | HP — small on purpose; the stall is before any data moves |
| `rcvh{a,c,d,e,f,g,h,l,m,n}.dat` | 32,768 | `d94d2beda069ef0ef340977e7fd6995d` | copies of `trans.dat`, one per receive leg |
| on the image | 32,768 | `d94d2bed…` | `A:\FIXTURE.DAT` — **`TRANS.DAT` is not on this image**; see below |

§16bb leg MA's 9-character target was **silently overwritten** and nothing
said so; identical HK fixtures would have hidden the same thing.

---

## Before every leg

- **The Victor takes about 40 s to load.** On a leg where the Victor
  *receives*, start the Victor first, wait for the drive to go quiet, then
  start the host. On a leg where the Victor *sends* (HB), **start the host
  receiver FIRST** — the Victor is the initiator and gives up if nothing
  answers its S packets.
- **Run each pair back to back.** Nothing here is comparable across a gap.
  The same `CKPRE` binary gave 18.29 s non-line in §16ah and 21.43 s in
  §16al with the wire held constant; **the spread is the host** (§16al).
- Power-cycle the Victor **and** the Pico between runs.
- **A leg ends when the VICTOR exits, not when the host does** (§16bb).
- Four artifacts per leg: `s16bcH<x>.host`, `s16bcH<x>.pkt`,
  `STEPH<x>.OUT`, and the transferred file `cmp`'d against its fixture.
- **`cmp` first, then the counters.** A leg that is fast and wrong is the
  failure mode.

**Read every log the same way:**

```sh
python3 v9k/tools/pktstat.py --rxbytes <from the .OUT> s16bcH<x>.pkt
```

Residual **−11** clean, **+28** with a startup timeout. **Non-line cost =
host clock − (wire bytes × 260 µs)**; that is what makes an off-shape leg
comparable (§16al leg GP). The Victor's `elapsed=` and the host's
`statistics` do **not** measure the same interval — quote the pair, never
one alone (§16v). **`wire=` is a receive-leg figure only**; it divides
`rxbytes`.

**And the arithmetic rule that governs every A/B below: this bench does not
repeat to better than ~0.4–1.3 s** (§16ah 1.277 s; §16ak 398 ms). **Do not
read an effect smaller than that off two legs.** Where an effect is smaller,
the way out is a counter, not more legs.

---

## The legs

Fixtures are listed with their md5s in §0a. The one to know is
**`FIXTURE.DAT`** on `A:` — 32,768 bytes, `d94d2bed…`, inside edit 16's broken
range on purpose. It is byte-identical to the `TRANS.DAT` every 38400 leg
since §16ae used; **that name is no longer on the image** and §0a says why.

| leg | rate | binary | asks |
|---|---|---|---|
| **HA** | 38400 | `CKBB` | **32 KB receive.** The regression that matters. Control is §16aq's bulk arm |
| **HB** | 38400 | `CKBB` | **32,768-byte send BY NAME.** Edit 16's exact range; control is §16ai leg CC |
| **HC** | 38400 | `CKBB --noflow` | flow-control control leg |
| **HD** | 38400 | `CKBB --rtscts` | **the first RTS/CTS leg with a far end that can stop.** Saleae on `/RTS` and `/DTR` across this one |
| **HE** | 38400 | `CKBB --xonxoff` | the other half, if HC/HD are clean and there is time |
| **HF** | 9600 | `CKBB` | **FreeDOS for Victor, COM2** — first time on real silicon. Comparable to §16az leg FDE |
| **HG** | 38400 | `CKBB` | FreeDOS at 38400. No control exists anywhere; this is discovery |
| **HH** | 38400 | `CKBB` | FreeDOS console arm — **no redirect on this leg** |
| **HJ** | 38400 | `CKBB -x` | server sweep: edits 19, 20, 22. `REMOTE HELP` **first** |
| **HK** | 38400 | `CKBB --safe-server` | edit 21 on the wire: forced RENAME, twice into one name |
| **HL** | 9600 | `CKBB -d` | does §16ba's 27 s `rcvfil()` stall exist on the real `A:\`? |
| **HN** | 9600 | `CKBB -d` | HL's control, one **volume** over: the same leg into `D:\` |
| **HM** | 38400 | `CKICP` | the post-merge parser build, 443K, on the 896K machine |

**HA and HB are the sitting.** If time runs out after HD, the sitting has
still done its job: everything from HF down is confirmation or discovery
that can wait for the next one.

---

## Pair 0 — the regression. Legs **HA** then **HB**. **Do these first.**

```
STEPHA                     (at A>, Victor receives)
```
```sh
kermit -C "take s16bcHA.ksc, exit" > s16bcHA.host
```
then
```sh
kermit -C "take s16bcHB.ksc, exit" > s16bcHB.host   &   # host RECEIVES, waits
```
```
STEPHB                     (at A>, Victor SENDS TRANS.DAT by name)
```

### HA — predictions, written down first

The control is **§16aq's bulk arm, three legs, spread 16 ms** — the
tightest set of numbers this bench has ever produced:

| | KA | KC | KN_2 | **HA predicted** |
|---|---:|---:|---:|---|
| host clock | 25.668 s | 25.652 s | 25.659 s | **25.5–25.9 s** |
| cps | 1,277 | 1,277 | 1,277 | **1,27x** |
| `rxpeak` | 481 | 488 | 409 | **4xx** |
| wire bytes | 37,557 | 37,557 | 37,557 | **37,557** |
| packets / to / re | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | **18 / 0 / 0** |

Plus `rxlost=0 rxfull=0 deb=0 nospc=0`, byte-exact md5, `bulk sel=1` with
`n` around 243–249, and residual −11.

| HA against §16aq | reading |
|---|---|
| inside ~1.3 s and all counters in range | **the merge and edits 19–22 cost nothing on the wire.** That is the whole regression, and it is the answer to want |
| slower by more than ~1.3 s, counters clean | code size. §16w. **Do not blame a specific edit** — four hand-costed 8088 predictions in this tree have come out wrong, one in sign |
| `rxfull` non-zero or `rxpeak` near 4,095 | edit 17 or edit 18 is not doing what it did. Check `bulk sel=` **before** the clock (§16aq: an equivalence test cannot see a switch that silently failed) |
| off-shape (timeout, resends, ~40,5xx wire) | re-run, do not adjust. Compare **non-line cost** only if it happens twice |

**Free readings on this leg, no extra legs needed:** `deb=`, `nospc=`,
`coll=` (expect **1**, `XYFX_X`, §16av's fix in force), and **`nap per=`**
— the first real-hardware calibration of §16av's busy loop. MAME said
`per=409` against a 500 ms clock; the 5 MHz 8088 figure is a new fact and
it costs nothing. `n=0 per=0` means nothing asked for a delay this run and
is **not** a defect; any other zero is.

> **RESULT HA — PASS. The port came through six MAME-only sittings unmoved.**
> Byte-exact (`d94d2bed…`), `rxlost=0 rxfull=0 rxpeak=559 of 4096`, `deb=0`,
> `nospc=0`, `coll=1`, `bulk sel=1 n=113`, 18 packets, **0 damaged, 0
> timeouts, 0 retransmissions**, **26.200 s / 1,250 cps** against §16aq's
> 25.652 / 25.659 / 25.668 and 1,277. **+0.54 s, inside the bench's own
> 0.4–1.3 s spread.** Victor `elapsed=2900 cs`, `wire=1295 B/s`.
> **So upstream 11.0.508, edits 19–22 and §16av's six fixes cost nothing on
> the wire**, and §16w's code-size worry did not materialise over ~950 bytes.
>
> **`nap per=286` is new and is the first real-hardware calibration of
> §16av's busy loop** — MAME reads 409 on the same code, so the emulator's
> spin is 43% faster than the machine's. Every MS-DOS leg read exactly 286.
>
> **One number to carry into HL/HN: `dec max=450 at #3`.** §16ba read stalled
> legs at 3250/3350 and clean ones at 100–150. This is 4.50 s at decode #3 at
> **38400 on `A:`**, where FreeDOS leg HG on its own volume reads **132**.

### HB — predictions

Control is **§16ai leg CC**, which is the same direction, the same policy
and the same fixture:

| | CC | **HB predicted** |
|---|---:|---|
| `prefixing policy` | `PX_CAU exactly (32 values)` | **identical** |
| `prefixes ctl` | 4,512 | **4,512** |
| wire bytes | 37,557 | **37,557** |
| packets | 18 | **18** |
| host clock / cps | 22.207 s / 1,475 | **~22.2 s / 1,47x** |

**Read the wire-byte count as the result and the cps as an illustration**
— CC and CD were 1.397 s apart against a ~1.3 s floor.

**And the thing HB is really for:** `-s <name>` on a file of exactly 32,768
bytes is inside the range edit 16 repaired. **The failure signature is an
error line with an empty `ck_errstr()`**; §16ah leg BS produced no error
line at all. This is edit 16's fourth end-to-end confirmation and its
second on hardware.

> **RESULT HB — PASS, and edit 16 is confirmed for the fourth time.**
> 32,768 bytes sent BY NAME, `gothb.dat` byte-exact, **no error line**,
> `rxlost=0 rxfull=0 rxpeak=52`, 18 packets, 0/0/0, **22.324 s / 1,467 cps**
> against §16ai leg CC's 22.207 / 1,475 — **117 ms apart on a bench with a
> 1.3 s floor.** The fixture was `FIXTURE.DAT`, not `TRANS.DAT`; §0a.

---

## Pair 1 — flow control, with a far end that can stop. Legs **HC** then **HD**.

### H0 — the precondition, and it is not optional

§16am's rule, and it has now cost this project three legs and most of a
sitting: **before running an experiment that depends on the far end
behaving a particular way, measure that the far end can.**

```sh
K=~/projects/ckermit-host/wermit                     # NOT `kermit` on $PATH
$K -C "show versions, exit"                          # must say 11.0.508
$K -C "show features, exit" | grep -i crtscts        # must list POSIX_CRTSCTS
strings $K | grep "tthflow POSIX_CRTSCTS tcsetattr"  # the arm really compiled
stty -f /dev/tty.usbserial-XXXX crtscts -hupcl       # and then LEAVE IT
stty -f /dev/tty.usbserial-XXXX -a | grep crtscts    # read it back
```

**Built 21 August in `~/projects/ckermit-host`** — a sibling directory,
because `make macosx` drops `wermit` and ~100 `.o` into the working
directory next to `ckermitw.exe`. Copy `*.c *.h makefile` **and
`ckcpro.w`**; without the last the makefile stops at `wart`.

**AND IT NEEDS `KFLAGS=-DPOSIX_CRTSCTS`, WHICH §16bb DID NOT SAY.** A plain
`make macosx` reports `CK_RTSCTS` alone — `ckcdeb.h:4583` hands
`POSIX_CRTSCTS` out per platform and **Darwin is not in the list**, though
macOS's `<sys/termios.h>:218` has `CRTSCTS` as `CCTS_OFLOW|CRTS_IFLOW`.
**So the flow-control question was still blocked during pass 1**, and leg
HD was void for that reason as well as for `held=0`. The `strings` line
above is the check that matters: `SHOW FEATURES` is generated in `ckuus5.c`
and tells you the symbol was defined *there*; the debug string lives inside
the `#ifdef` in `ckutio.c` and tells you **the arm that drives the port
compiled.** §16aj's rule, turned on the host.

`CK_RTSCTS` alone only makes the *command* legal. **`POSIX_CRTSCTS` is what
puts `CRTSCTS` on the port.** If the client on the bench is still 9.0.302,
**stop and rebuild it** (`make macosx`, in scratch, not the repo) — running
HD without it reproduces §16al leg GB, which looked like a clean positive
result and was retracted one section later.

### The analyzer, because a counter inside either program cannot answer this

§16an is the precedent and its lesson is the durable one: **every
flow-control measurement before it was a counter inside one of the two
programs, and both programs can be right about what they did while nothing
happens between them. When the question is about a wire, measure the
wire.**

- Probe **`/RTS` and `/DTR` on the TTL side** — same WR5 byte, same
  instruction pair, bit 7 and bit 1, so DTR is a free second channel. The
  connector is ±12 V; do not probe there.
- **Add CTS in** if a channel is free. §16v's `cts = 1` is on the
  retraction line: a floating MC1489 input can read active, and leg DS only
  needed CTS to *read* asserted. This capture settles the input half.
- Capture across the whole of HD. §16an saw eight pauses of 785 ms–1 s and
  **data still arriving for hundreds of ms after each drop**, which is the
  signature to compare against.

### Running it

```
STEPHC                     (at A>, CKBB --noflow)
```
```sh
kermit -C "take s16bcHC.ksc, exit" > s16bcHC.host
```
then
```
STEPHD                     (at A>, CKBB --rtscts)
```
```sh
kermit -C "take s16bcHD.ksc, exit" > s16bcHD.host
```

**Marks stay at the shipping 3072 / 1024 and the reason is §16al's.** When
a leg keeps going off-shape, **change what you ask of it, not how many
times you ask**: §16ak's 256/64 put `rxpeak` fourteen bytes into a *resend*
and voided the leg, because a 64-byte release point means every hold-off
lasts until 192 bytes have drained. A high mark at 3/4 with a 1/4 release
gives a **cap** to read, and a cap survives a retransmission.

| | HC (`--noflow`) | HD (`--rtscts`) |
|---|---|---|
| `flow in/out` | 0 / 0 | **2 / 2** |
| `hi` / `lo` | 65535 / 1024 | **3072 / 1024** |
| `held` / `rel` | 0 / 0 | **> 0 and equal** |
| `stuck` | 0 | **0** — non-zero here is CTS never coming back, which usually means the cable |
| `rxpeak` | 4xx (HA's figure) | **the answer** |
| wire bytes | 37,557 | 37,557 |

**The result is `rxpeak` on HD, and it is only a result if HD is otherwise
identical to HC on the wire.** `rxbytes` equal, same packet count, same
retransmissions — a leg that retransmits differently is not comparable and
is re-run, not adjusted (§16ag leg AM).

**And ask where the peak IS before reading it.** §16ak leg DE was briefly
claimed as the positive result until `mapoffset.py` put its peak at a
packet boundary, exactly where the control legs peak:

```sh
python3 v9k/tools/mapoffset.py s16bcHD.pkt \
       --rxbytes <rxbytes= from the .OUT> <peakat= from the .OUT>
```

| HD | reading |
|---|---|
| `held > 0`, `rxpeak` **capped below** HC's, peak **not** in a resend | **RTS/CTS is effective.** That is the first evidence that licenses changing `V9K_FLOW`, and it needs a second pair before it ships |
| `held > 0`, `rxpeak` unchanged, analyzer shows RTS dropping and data continuing | the host still is not stopping. **Check `stty` again before believing the port** |
| `held = 0` | the marks were never crossed at 38400 with a window of 1 — expected, and it means the leg cannot answer. Re-run at a narrower band, **and build and stage the binary that carries it** |

**Harmless and effective are different claims and only the second licenses
a default.** `V9K_FLOW` stays `FLO_NONE` out of this sitting whatever HD
says; one pair is evidence, not a decision.

> **RESULT HC — clean-ish, and it is the control.** Byte-exact, `rxlost=0
> rxfull=0`, `flow in=0 out=0 hi=65535 lo=1024 held=0 rel=0`, **`rxpeak`
> 2,811**, 1 timeout, 2 retransmissions, **27.665 s / 1,184 cps**.
>
> **RESULT HD — THE LEG CANNOT ANSWER, AND IT IS THE THIRD ROW OF THE TABLE
> ABOVE.** Byte-exact, `rxlost=0 rxfull=0`, **`flow in=2 out=2 hi=3072
> lo=1024`** — so the switch took and the marks are right — but **`held=0
> rel=0`**: `rxpeak` reached **2,821 against a high mark of 3,072**, so the
> water mark was **never crossed** and RTS was never asserted. 1 timeout, 2
> retransmissions, **27.697 s** — **32 ms from its control**, identical
> protocol shape.
>
> **This is a structural null, not a host null.** At 38400 with a window of
> 1 the ring never fills to 3/4, because §16au established the far end stops
> to wait for an ACK long before that. **A flow-control leg at the shipping
> marks cannot engage flow control.** Lowering the marks is what §16ak did
> and it voided the leg the other way (`rxpeak` fourteen bytes into a
> resend). **The honest statement is that RTS/CTS remains unmeasured on this
> hardware, and `V9K_FLOW` stays `FLO_NONE`.**
>
> **And the host precondition was NOT met — see leg HJ.** `remote status`
> came back `?No keywords match`, so the bench client is still **9.0.302**,
> not the 11.0.508 build §16bb made. §16am's blocker was therefore still in
> place for this pair. Two independent reasons the leg is void, and **the
> counter found the first one before the host was even suspected**, which is
> the argument for `held=`/`rel=` existing at all.
>
> **`rxpeak` 2,811 and 2,821 against HA's 559** is §16m again: both legs took
> a retransmission and the peak measures the ring filling during it.

### HE — `--xonxoff`, only if HC/HD are clean

§16ak measured **19 bytes lost in 11 bursts** under XON/XOFF where RTS/CTS
at the same marks lost none — the first non-zero `rxlost` since §16t, cause
never established, and **nothing counts the ISR's failed XOFF attempts**.
Watch `xoff`/`xon`/`stuck` and `rxlost`. `stuck > 0` with `xoff > xon` is a
lost XON and the reason `V9K_FCSPIN` exists.

> **RESULT HE — clean, and cheap.** Byte-exact, `rxlost=0 rxfull=0
> rxpeak=719`, **0 timeouts, 0 retransmissions**, `flow in=1 out=1 hi=3072
> lo=1024`, **`held=0 rel=0 xoff=0 xon=0 stuck=0`** — never engaged, same
> structural reason as HD — and **26.121 s / 1,254 cps**, which is *faster*
> than both HC and HD and within 79 ms of HA. **XON/XOFF costs nothing when
> idle**, confirming §16ak's "harmless" half on hardware. It does not
> confirm the effective half; nothing here did.

---

## Tier 2 — FreeDOS for Victor, on real silicon. Legs **HF**, **HG**, **HH**.

**It has never run on a real Victor.** §16az and §16ba are MAME only.

**CHANNEL B, AND THIS IS NOT A PREFERENCE.** The myfreedos kernel's
`entry.asm:280` busy-waits on TBE and writes an `H` to the 7201 at
`E000:0040` **on every INT 21h call**, guarded by `%ifdef VICTOR9000` with
no runtime switch — and hard rule 6 puts every console and file write of
this port through INT 21h. §16az leg FDC on channel A took 5 damaged
packets and 6 resends; leg FDE is the same leg one channel over and every
one of them disappears. **Use `COM2`.** `v9k_ser_selchan()` picks B from a
name ending in `B` or `2`.

**Before the first leg, capture what this machine puts on the wire with
nothing of ours running** (§16az's method lesson, and it settled that
question in 150 seconds where four counter readings had not):

```sh
# Victor booted to the FreeDOS prompt with NOTHING OF OURS RUNNING.
# Capture both channels, separately, one cable move apart.
stty -f /dev/tty.usbserial-XXXX 9600 raw -echo
timeout 60 cat /dev/tty.usbserial-XXXX | xxd > s16bcFDBOOT-chanB.txt
```

**Channel B's capture must be empty.** Channel A's will not be — that is
`entry.asm:280`, and §16az leg FDC is what it costs (5 damaged packets, 6
retransmissions, and a transfer that was *still* byte-exact, which is a fact
about the protocol's error recovery and not about the port). Capture A too
if the cable move is cheap: a machine you have not run on before gets one
capture before it gets a leg.

Then `STEPHF`, `STEPHG`, `STEPHH` at the FreeDOS prompt, each with its
`s16bcH<x>.ksc` on the host:

- **HF, 9600, COM2** — comparable to §16az leg FDE: **685 cps receiving, 0
  damaged, 0 timeouts, 0 resends**. Expect **`v9k: dos oem=fd ver=622
  irq1=09`** and §1b's direct chip-programming fallback (FreeDOS's COM
  device carries attribute `0x8000` with no IOCTL bit, so `AX=4402h` fails).
- **HG, 38400, COM2** — no control exists. Discovery. `rxlost`/`rxfull`
  are the readings that matter, not cps.
- **HH — the console arm, and it MUST NOT HAVE A REDIRECT.** §16u: the
  transfer display goes away under the redirect that records the counters,
  so **a leg that has to show you a screen cannot have a redirect on it**,
  and the picture and the counters need two runs. §16ba's first attempt and
  §16az's leg FDG both died of this. Photograph the screen mid-transfer.
- **Also free on this DOS**: `v9k/probes/vmem.c` for how much memory it
  gives, and **`nap per=` and every `tot=`** — §16ba established that the
  half-second clock quantum is **Victor MS-DOS 3.1's, not the machine's**,
  and not one FreeDOS figure was a multiple of 50. A `max=` cannot be
  compared across the two DOSes.

> **RESULT HF — PASS, and FreeDOS for Victor runs on real silicon.**
> **`v9k: dos oem=fd ver=622 irq1=09`** — §16av's FreeDOS IRQ1 branch,
> written in August and never executed on hardware until now, works.
> Byte-exact, `rxfull=0`, **`rxlost=1`**, `rxpeak=608`, `bulk sel=1 n=8796`,
> 2 timeouts, 4 retransmissions, **60.883 s / 538 cps** against §16az leg
> FDE's 47.830 / 685 under MAME. **The first non-zero `rxlost` since §16ak,
> and at 9600, where there is 555 µs of slack per byte.** Not explained.
>
> **RESULT HG — PASS, AND IT IS THE FASTEST RECEIVE THIS PORT HAS EVER
> DONE.** FreeDOS at **38400**, which no harness has ever been able to
> reach on this DOS. Byte-exact, `rxlost=0 rxfull=0 rxpeak=394`, `bulk
> sel=1 n=85`, **0 damaged, 0 timeouts, 0 retransmissions**, **22.781 s /
> 1,438 cps** — **15% faster than MS-DOS 3.1 on the same machine, same
> binary, same rate, same hour** (HA: 1,250). `dec tot=1063 cs` against
> HA's 1750, and `dec max=132` against HA's **450**. `nap per=341`, and
> HF read 409 — **FreeDOS's calibration is noisy where MS-DOS 3.1's was
> 286 on all five legs**, which is §16ba's clock-quantum finding showing up
> in a third place.
>
> **RESULT HH — FAILURE, and it is a real finding rather than a broken
> leg.** `Too many retries`, **11 retransmissions**, 15.299 s, and
> `RCVHH.DAT` on the image is **626 bytes**. The packet log says exactly
> what happened: S, F (`rcvhh.dat`, ACKed as `A:/rcvhh.dat`), attributes,
> then packets 03 and 04 land — and at **packet 05, where C-Kermit's slow
> start jumps to a ~1,400-byte packet, the Victor NAKs** (`r-05-11-…N`) and
> keeps NAKing every retransmission until the host gives up. **The host
> received 0 damaged packets**; the corruption is all in the Victor's
> receiver.
>
> **HG is the same leg with the console output taken away, and it is
> perfectly clean.** So the finding is: **at 38400 on FreeDOS for Victor,
> console output breaks reception at the first long packet.** The mechanism
> is available and not proven: hard rule 6 puts every console write through
> INT 21h, and §16az established that the myfreedos kernel busy-waits on TBE
> and writes a character to the 7201 **on every INT 21h call**; §16ag
> established that at 38400 the foreground has **no** slack per byte.
>
> **State the attribution carefully. HG and HH differ in TWO things** — the
> display, and the redirect — so what is measured is *console output*, not
> specifically §1g's cursor addressing. And **there is no MS-DOS 38400
> display leg**, so whether this is FreeDOS-specific is untested. §16ba
> measured the display at ~6 s (~12%) on a 9600 MS-DOS receive; here it is
> fatal.

---

## Tier 3 — confirmations. Legs **HJ**, **HK**, **HL**, **HM**.

### HJ — the server sweep at 38400, for edits 19, 20 and 22

**`REMOTE HELP` is the first command** (§16ax's rule: it prints the
capability table out of the `en_*` variables, and it is what caught SPACE
and WHO claiming `Enabled` while both could only fail). Then:

- **dates** — a listing and a `GET`, both dated **now** and not `Jan 1
  1970`. Edit 19 is in `zfcdat()` and hits both the listing and the file
  date attribute.
- **`REMOTE SPACE`** — edit 20, answered from INT 21h `AH=36h`. §16ay saw
  `Free space: 536K` under MAME.
- **`MAIL`** — edit 22. Expect the refusal code `N` **in the A-packet ACK**
  with **no data packets**, the way PRINT already behaves. The control
  behaviour is `E Can't open file` after the first data packet.
- **`REMOTE STATUS`** — needs the 11.0.508 client. Four fields came back
  empty under MAME (Hostname, Server hardware, OS family, and *Current
  directory on server*, which is blank while `REMOTE PWD` in the same leg
  answers). Confirm, do not chase.

**Do not put `BYE` anywhere but last, and ask what a leg's last command
does to the channel the leg reports through** — §16ax leg SA came back
0 bytes because its terminating `REMOTE EXIT` failed on the host and the
server never exited.

> **RESULT HJ — RAN, ANSWERED EVERYTHING, AND THE OUTPUT WAS LOST.**
> The server replied to every command and the host-side captures survive:
>
> - **Edit 19 works on hardware.** `REMOTE DIRECTORY` lists `CKICP.EXE
>   460466 2026-08-20 17:38:02` — **the minute it was staged** — and
>   `CKBB.EXE … 2026-08-19 19:48:40`. Real dates, not `Jan 1 1970`.
> - **Edit 20 works.** `REMOTE SPACE` → **`Free space: 8632K`**, which is
>   `D:`'s 8.4 MB to the kilobyte, out of INT 21h `AH=36h`.
> - **Edit 22 works.** The capability table reads **`MAIL  Disabled`**.
> - §16ax's WHO fix holds: **`REMOTE WHO  Disabled`**, not "Enabled" over a
>   `syscmd()` that `NOPUSH` emptied.
> - `REMOTE PWD` → `D:`, so the `.BAT`'s volume switch took.
>
> **`REMOTE STATUS` failed on the HOST**: `?No keywords match - status`,
> `s16bcHJ.ksc` line 43. **The bench client is C-Kermit 9.0.302, not the
> 11.0.508 build §16bb made** — so §0's H0 precondition was not met, and
> that is also the second reason legs HC/HD are void. **Written into the
> sheet, checked by nobody, and caught only by a leg failing.** A
> precondition with a checkbox is not a precondition.
>
> **And no `STEPHJ.OUT` exists** — see the D: section below.

### HK — edit 21 on the wire

`--safe-server` forces `fncact` to RENAME for the whole session
(`ckcpro.c:503`), so this is not an optional path. Send **twice into one
name**, and use **both** a 9-character target and a 4-character one —
`znewn()`'s two branches are chosen by name length and the control failed
differently in each (4 chars: an E packet with empty text; 9 chars:
**silent overwrite**).

**THE DISK IS THE OBSERVABLE AND THE F-PACKET ACK IS NOT.** `ckcpro.w:1546`
sends `fspec`, which `rcvfil()` fills from the incoming name *before* the
collision switch runs — §16bb leg MB's ACKs said `rcvmb.dat` while the file
on disk was `RCVMB.001`. Read it with `vtg_image_util list`, with no
protocol in the path. Expect `RCVHK.001` and `HK.001`, originals untouched,
`coll=1`.

> **RESULT HK — RAN, AND THE ANSWER IS UNRECOVERABLE.** The packet log
> shows `Frcvhk.dat` and `Fhk.d` both ACKed and data flowing, `SUCCESS`,
> 4.194 s. **But every file it wrote was on `D:` and no `D:` write
> survived**, so the one observable this leg exists for — *what is on the
> disk afterwards* — does not exist. The sheet said in capitals that the
> ACK is not evidence and the disk is; it did not occur to anyone that the
> disk might not keep it. **Re-run required**, and pass 2 puts it on `A:`.

### HL — is the 27 s `rcvfil()` stall on the real `A:\` too?

§16ba killed five candidates and left one: **something about that root
directory itself** — capacity, deleted `0xE5` slots, entry fragmentation —
with `zchko()` doing three DOS directory operations on it before a data
byte moves. A clean 9600 receive is **46.1–46.6 s and 702–710 cps**; `A:\`
gives **78.9 s and 415**.

**This is the one leg that runs `-d` on purpose**, and §16aw permits it
because the stall is a discrete 26-second event and not a throughput claim.
Run it at **9600**, into `A:\`, with **leg HN** — the same leg one volume
over, into `D:\` — immediately after. **One variable.** Expect `deb=1` on
both and **do not quote a cps figure off either.**

Either answer is worth having: it reproduces on a second physical
filesystem, or the 27 s was MAME's and §16ay through §16ba have been
quoting an emulator artefact.

> **RESULT HL — DID NOT RUN.** `D:\CKBB.EXE` was **not found**. Host:
> `FAILURE, Too many retries`, 32 timeouts, 31 retransmissions, 256 s —
> the signature of nothing at the other end.
>
> **RESULT HN — DID NOT RUN**, same cause. So did **HM**.
>
> These three are the whole of the D: failure and they are written up
> below.

### HM — the parser build after the merge

`CKICP.EXE` from HEAD, **443K, a 640K-class build** — the first upstream
merge to move a machine class, on an 896K machine. §16ab is the last time
the parser ran on hardware and that was a pre-merge binary.

```
STEPHM                        (at A>)
CKICP -d                      (at A>)
take spdtest.ksc              (at the C-Kermit> prompt)
```

Checks, all confirmations of §16ad: the prompt echoes a typed line
**exactly once**; `SET LINE /dev/seriala` reports **local**; `SET SPEED
38400` and `19200` both read back (`tcsetattr divisor=` 2 and 4, edit 15);
`SHOW VERSIONS` names the build (edit 12) and is the only way to identify a
binary on the machine; `CKICP A:\SPDTEST.KSC` runs by absolute path
(edits 13, 14).

**Then one 32 KB transfer**, because edit 14 widened what `main()`
compiles and this binary is not the one measured at 1,170 cps. `rxlost=0
rxfull=0` and a byte-exact md5 is what says the wire protocol did not move.
Drive it from the prompt — `set line /dev/seriala`, `set speed 38400`,
`receive` — against `s16bcHM.ksc` on the host. **`SET LINE` must report
`local` and `SET SPEED` must read back**; both were port defects §16ab
found and neither is reachable without the parser.

**Not settleable here and not a surprise if it happens:** extended keys.
The console reads INT 21h `AH=07h` and whether the Victor's keyboard driver
uses the 0-then-scan-code convention is unknown, so a function or arrow key
may deliver a stray NUL. Nothing in this build wants arrow keys.

> **RESULT HM — DID NOT RUN.** `D:\CKICP.EXE` not found, same as HL/HN.
> The build itself is measured and staged: **460,466 bytes, needs 453,986
> (443K), DGROUP 59,632 of 65,536 (90%), smallest Victor 640K** — §0's
> predictions confirmed to the byte. Only the leg is outstanding.

---

## What happened to `D:`, and what pass 2 does about it

**Every leg that ran on `A:` kept its results. Not one `D:` write survived
the sitting.**

| | ran | wrote |
|---|---|---|
| HA HB HC HD HE (`A:`, 19:16–19:23, before the image swap) | yes | **yes** — five `.OUT`s and four 32 KB files, all on the image |
| HF HG HH (FreeDOS volume, 19:36–19:43) | yes | **yes** — `.OUT`s and files present |
| HJ HK (`D:`, 19:49–19:50, after the swap back) | **yes** — the server answered every command | **no** — no `STEPHJ.OUT`, no `STEPHK.OUT`, no `RCVHK.*`, no `GOTHJ.DAT` |
| HL HN HM (`D:`, 19:55+) | **no** — `CKBB.EXE` / `CKICP.EXE` not found | — |

`D:` comes back holding **exactly the 25 files that were staged on it and
nothing else**, byte for byte, 8.4 MB free. So `D:` was **readable** at
19:49 (the server loaded from it, `REMOTE PWD` answered `D:`, `REMOTE
DIRECTORY` listed it correctly and `REMOTE SPACE` reported its free space
to the kilobyte) and **not readable** by 19:55, and **never writable**.

**The cause is not established and nothing in this tree can establish it.**
The operator swapped the MS-DOS image out to run the FreeDOS legs and back
again, and every `D:` result is on the far side of that swap. The two
candidates are the Pico SASI emulator's handling of a second volume across
a media change, and DOS's own buffering never being flushed for a drive it
stopped believing in. **Both are outside this port.** What is inside this
port's control is not depending on it.

### Pass 2 — staged 20 August, all on `A:`

`A:` is the volume this hardware demonstrably reads *and* writes.
**`CKBB.EXE` (`c42c3598…`) and the post-merge `CKICP.EXE` (`181b6436…`) are
now on `A:`**, and six `.BAT`s are rewritten to use them: `STEPHJ` `STEPHK`
`STEPHL` `STEPHM` `STEPHN` `STEPHP`, all round-tripped off the image.

**Room was made by deleting the stale pre-merge parser binaries** —
`CKICP.EXE` 435,154 and `CKICPD.EXE` 546,422, both from §16ai, both
rebuildable from git, and both exactly the §16ai trap: a binary sitting on
an image across an edit, which is how leg HM would have measured a
pre-merge build and called it the merge. **`A:` is now 992 KB free.**

**Three changes beyond the volume, and each removes a second question from
a leg:**

1. **HL and HN lose `-d`.** The instrument for the stall is `dec max=` on
   the `.OUT` plus the F-packet-to-ACK gap in the host's packet log — and
   **leg HA has already shown `dec max=450` on `A:` at 38400 against
   FreeDOS leg HG's 132 on its own volume**, so the counter is sensitive
   enough. `-d` costs ~25 ms per received byte (§16k) and ~180 KB of log.
2. **HN redirects to `A:\STEPHN.OUT` while receiving into `D:\`.** The
   received file must land on `D:` because `D:` *is* the variable; the
   counters, which are the result, are written where they will survive.
   **If `RCVHN.DAT` vanishes again but `STEPHN.OUT` is there, the leg still
   reports.**
3. **New leg HP** is the `-d` run into `A:\` that §16ba asked for, split
   out so neither leg carries two questions. Run it **last**; its clock
   means nothing.

### The rule this sitting earns

**Ask where a leg's result will be WRITTEN, not just whether the leg will
run.** This project has a standing rule from §16ax and §16av — *ask what
the failure under test does to the channel the leg reports through* — and
it has now been paid for a third time in a new way: the channel was not the
serial line and not stdout, it was **the volume**. HJ answered every
question correctly and produced no evidence. **A leg that runs perfectly
and writes to a volume that does not persist is indistinguishable, one day
later, from a leg that never ran.**

Concretely, for every future sheet: **§0 must round-trip a WRITE, not only
a read.** Every §0 in this project since §16al verifies that a staged file
comes *back* off the image byte-identical — which proves the host's writer
and the image, and says nothing about whether *the Victor* can write there.
One `ECHO x > D:\PROBE.TXT` at the start of a sitting, read back after,
would have caught this before HJ and HK were spent.

---

## Pass 2 — 21 August. Everything ran, and the `D:` diagnosis was wrong

**Host: 9.0.302 for HA/HB, and C-Kermit 11.0.508 with `POSIX_CRTSCTS`
verified in the binary for HC–HM.** All twelve legs executed. **HP was not
run.**

### First, the retraction

**`D:` is fine, and pass 1's "no `D:` write survived" was a wrong
conclusion from a real observation.** Leg HN wrote `RCVHN.DAT`, 32,768
bytes, byte-exact, to `D:\` without trouble. The pass-1 evidence was
genuine — `D:` came back holding exactly the 25 staged files — but the
common factor in every lost write and every "file not found" was **the
image swap**, not the volume, and I generalised from one to the other.
There was never a leg that isolated it. **The right reading of pass 1 is:
whatever the media change did, it cost the three legs after it; the volume
was never implicated.** What survives is the cheap part — §0 should
round-trip a *write* as well as a read, because it costs one line — and
**not** the claim about `D:`.

### The regression, and which pass owns it

| leg | pass 1 | pass 2 | control |
|---|---|---|---|
| **HA** | **26.200 s, 1,250 cps, 0/0/0, `rxpeak` 559** | 27.763 s, 1 to / 2 re, `rxpeak` 2,325 | §16aq 25.65x, 1,277 |
| **HB** | **22.324 s, 1,467 cps, byte-exact** | 0.005 s — void, nothing transferred | §16ai CC 22.207, 1,475 |

**Pass 1 owns both.** Pass 2's HA is off-shape and its HB never started.

**And pass 2 is off-shape as a SITTING, which is the more useful
observation.** All four 38400 receives — HA, HC, HD, HE — took **the
identical 1 timeout and 2 retransmissions** and landed at **27.763 /
27.746 / 27.730 / 27.803 s**: a **73 ms** spread across four legs, about
1.5 s above pass 1's clean legs. That is §16al's rule seen from the good
side: **cross-sitting comparison is worthless here and within-sitting
comparison is unusually tight.** HC/HD/HE are therefore a better-matched
trio than this bench has produced before.

### Flow control is answered, and the answer is structural

**With a far end that can genuinely stop** — `POSIX_CRTSCTS` verified by
`strings` in `ckutio.c`'s own arm, not just `SHOW FEATURES` — leg HD still
reports **`held=0 rel=0`**, `hi=3072 lo=1024`, `rxpeak` **2,635**. The mark
was never crossed. HC (`--noflow`) is 16 ms away with `rxpeak` 2,810.

**So the null is not the host and never was.** At 38400 with a window of 1
the ring cannot reach 3/4, because the far end stops to wait for an ACK
first — §16au's regime fact arriving from a third direction. **A
flow-control leg at the shipping water marks cannot engage flow control,
and this is now measured with every precondition met.** `V9K_FLOW` stays
`FLO_NONE`, and the remaining question is narrow: whether lowering the
marks buys anything a window of 1 has not already bought.

**Leg HE has the one non-zero flow counter of the sitting: `xon=2`** — two
host START characters intercepted by the ISR (§16aj's mechanism), `xoff=0`,
`held=0`, `stuck=0`, and it cost nothing: 27.803 s against HC's 27.746.

### The `A:\` stall is real, it is on hardware, and it is 4.4 seconds

**Legs HL and HN are the cleanest pair in this sitting: identical wire
bytes (39,564 each), identical longest packet (3,584), identical
retransmission shape (1 timeout, 1 resend), both byte-exact — one variable,
the volume.**

| | HL (`A:\`) | HN (`D:\`) | Δ |
|---|---:|---:|---:|
| host clock | 57.006 s | 52.602 s | **4.404 s** |
| Victor `elapsed=` | 5,950 cs | 5,500 cs | **4.50 s** |
| **`dec max=`** | **450 at #3** | **100 at #3** | **3.50 s in ONE decode** |
| cps | 574 | 622 | −7.7% |

**Two independent clocks agree to a tenth of a second, and `dec max`
localises it to a single decode interval.** §16ba's finding is confirmed on
real hardware — but **the magnitude is 4.4 s, not the ~27 s MAME showed**,
which is a property of that image's root directory and not of the machine.
**Leg HA carries the same `dec max=450` at 38400**, so it is a fixed
directory cost, independent of line rate, and it is inside every figure
this port has ever quoted for a receive into `A:\`.

**Leg HP — the `-d` mechanism run — was not executed**, so *what* those
directory operations are remains open. `STEPHP.BAT` is on the image.

### Edit 21 is confirmed on hardware, exactly as designed

Leg HK, `--safe-server`, forced RENAME, each name sent twice:

| on disk | md5 | what it is |
|---|---|---|
| `RCVHK.DAT` | `8fe1c686…` | **the original, untouched** |
| `RCVHK.001` | `a15e88dd…` | the second send, renamed |
| `HK.D` | `8fe1c686…` | **the original, untouched** |
| `HK.001` | `a15e88dd…` | the second send, renamed |

**Both branches of `znewn()`, no E packet, no silent overwrite**, 0/0/0,
5.576 s. The control's two failure modes — a refused `NAME.EXT.~1~` for the
4-character target and a **silent overwrite** for the 9-character one — are
both gone. `coll=0` on this leg, which is the forced-RENAME value and not
the port's `XYFX_X` default; that is `ckcpro.c:503` doing its job.

### Edits 20 and 22 on the wire, and edit 15 on hardware

**Leg HJ**: `REMOTE SPACE` → 18 bytes of answer out of INT 21h `AH=36h`
(**edit 20**); `REMOTE DIRECTORY` → a 9,120-byte listing of `A:`'s 156
files; `REMOTE PWD` → `A:`; `REMOTE HELP` → the capability table with
`MAIL Disabled` and `REMOTE WHO Disabled`. **And edit 22 is confirmed
directly in the packet log**: the `mail` A packet is ACKed with data
beginning **`N`** — the refusal code — and the host's very next packet is
`Z`, **no data packets at all**, which is exactly the PRINT behaviour edit
22 was written to give MAIL.

**Leg HM is a full pass and it retires the last unverified upstream edit
on hardware.** The post-merge 443K parser build ran `A:\SPDTEST.KSC` by
absolute path (edits 13, 14), `SHOW VERSIONS` named the build (edit 12),
`SET LINE` reported **`mode: local`**, and **`SET SPEED 38400` read back as
38400 and `19200` as 19200** — **edit 15 on the machine at last**, on the
exact rate whose `(int) ss[i] / 10` cast produced −2713 on a 16-bit `int`.
`dos oem=ff ver=310 irq1=41`, `rxlost=0 rxfull=0`.

### `Terminal input not allowed` — diagnosed, and it is not a port defect

Printed **twice** on the Victor's console during HJ, and the cause is one
line of this sheet's own take-file: `get trans.dat` names a file that is
**not on this image** — `FIXTURE.DAT` is (§0a fixed `STEPHB.BAT` and missed
`s16bcHJ.ksc`). **The server refused correctly**: the packet log shows
`R trans.dat` answered with `E Can't open file`.

The message is upstream's path to that refusal. `ckcfn3.c:2325` sets
`filno = (sndsrc == 0) ? ZSTDIO : ZIFILE`, and with no matching file
`sndsrc` stays 0, so `openi()` calls `zopeni(ZSTDIO,…)` — which at
`ckufio.c:1407` finds `is_a_tty(0)` true on a Victor console and
`fprintf(stderr,"Terminal input not allowed")`. **`openi()` retries once
with the locally-converted name, which is why there are exactly two**, and
`stderr` is not redirected by the `.BAT`, which is why they went to the
screen and not into `STEPHJ.OUT`.

**Cosmetic on this DOS. Worth one note for FreeDOS**: leg HH just showed
that console output can break a 38400 transfer there, and this is console
output emitted from the middle of a server session, with nobody at the
console to read it.

### HH reproduces: two for two, against a control that is two for two clean

| | pass 1 | pass 2 |
|---|---|---|
| **HG** (`--nodisplay`) | 22.781 s, **1,438 cps**, 0/0/0, `rxlost=0` | 23.194 s, **1,412 cps**, 0/0/0, `rxlost=0` |
| **HH** (display on) | **FAILURE**, 11 resends, `RCVHH.DAT` **626 B** | **FAILURE**, 11 resends, `RCVHH.DAT` **1,472 B** |

Both failures die the same way — the Victor NAKs a long data packet
repeatedly until the host quits — at packet **05** in pass 1 and **06** in
pass 2, which is simply how far it got before the length grew. **The host
received 0 damaged packets in both**, so the corruption is entirely in the
Victor's receiver.

**This is the sitting's one new defect and it is a real one.** Keep the
attribution honest: HG and HH differ in the display **and** the redirect,
so what is measured is *console output*, and no MS-DOS 38400 display leg
exists to say whether it is FreeDOS-specific. **HF also came back clean
this time** (`rxlost=0`, 1 timeout, 1 resend, 601 cps against pass 1's
`rxlost=1` and 538) — so pass 1's single lost burst did not reproduce and
should not be carried as a finding.

---

## Pass 2b — the HH photographs, and what leg HP actually cost

### The photographs turn HH from an inference into a measurement

**Primary source: `screenshots/stephh IMG_2032.png` … `IMG_2035.png`** —
the same place §16ao's display captures live. Four frames: three in flight
(2032, 2033, 2034) and **2035, the exit report**.

The sheet took the redirect off HH so the screen could be photographed, and
said in the same breath that **there would therefore be no counters**. That
was wrong in a useful way: **the exit report prints to the console too**, so
a leg with no redirect is not a leg with no counters — it is a leg whose
counters have to be read with a camera. `IMG_2035` has all of them.

```
v9k: dos oem=fd ver=622 irq1=09
v9k: rxlost=38 rxfull=0 rxpeak=1951 of 4096
v9k: peaktag=1 fd=1 stall256=14
v9k: rxbytes=25208 peakat=3760 stallat=601
v9k: bulk sel=1 n=30
v9k: lost evt=23 max=2 tag=1 fd=1
v9k: lostat=2643 lostend=24764
v9k: wcon n=342 max=22 tot=706 cs
v9k: txgap n=17 max=50 at #13 tot=666 cs
v9k: dec n=18 max=192 at #2 tot=944 cs to=0
v9k: elapsed=1999 cs wire=1261 B/s
```

**`rxlost=38` against leg HG's 0**, and the attribution is not inferred —
**the instrument names the location**. §16m's foreground tag and §16q's
first-loss latch both point at the same place:

- **`lost evt=23 max=2 tag=1 fd=1`** — 23 loss bursts, and the foreground
  location latched at the **first** loss is **`tag=1` = `V9K_TAG_WRITE`,
  `fd=1` = the console**.
- **`peaktag=1 fd=1`** — the ring's peak occupancy happened in a console
  write too.
- **`wcon n=342 max=22 tot=706 cs`** — **342 console writes totalling
  7.06 seconds** inside a run whose `elapsed=` is 19.99 s. **35% of the
  leg is spent writing to the screen.**

**So HH is no longer "console output breaks a 38400 receive on FreeDOS" by
elimination. It is: the display costs 7.06 s of foreground in 20 s, the
receiver loses 38 bursts, and the counter that records WHERE says
`write(1)`.** §16m built that tag in August for exactly this shape of
question and it has never before named a defect on its own.

`rxpeak=1951` is worth a second look: the screen shows **`Packet Length:
1951`**, so the ring peaked at exactly one packet — the receiver never got
ahead, it simply lost bytes inside each long packet, which is precisely
why the failure is CRC errors and not a timeout.

### And the FreeDOS console arm is verified — the other half of §16av

`screenshots/stephh IMG_2032.png` answers an item that has been open since
§16ao and that §16az and §16ba both failed to close. **§1g's ANSI arm draws correctly on
FreeDOS for Victor**: the fullscreen display is legible and properly
addressed — header, aligned label column, the `...10...20...` percent
scale, live `Packet Count`, `Packet Length`, `Error Count`, `Last Error`,
and the two-line key help at the foot. §16az leg FDA's "screen garbage"
was retracted as the kernel's own trace region; this is the port's own
output and it is correct. `Communication Device: COM2`, `Speed: 38400`.

The three in-flight frames show the failure developing rather than just its
end state, which no `.OUT` file could have done:

| frame | packets | `Error Count` | CPS | `RTT/Timeout` |
|---|---:|---:|---:|---|
| `IMG_2032` | 8 | 2 | 245 | 01 / 06 |
| `IMG_2033` | 13 | 7 | 147 | 01 / 11 |
| `IMG_2034` | 17 | 12 | — | 01 / 15 |

`Last Error: CRC error` throughout, until `IMG_2034` ends on `FAILURE: Too
many retries`. **That is the Victor's side of the host's "0 damaged packets
received"** — the errors are all inbound, and the host's round-trip
estimator is visibly backing off as they accumulate.

**A camera is an instrument this project should have used sooner.** Every
prior "the display cannot be captured under a redirect" note (§16u, §16az
leg FDG, §16ba) treated that as the end of the matter and cost legs to it.
The display *and* the counters were always both on the screen.

### Leg HP: three errors, all mine, and the sheet contained the rule for two

**HP was run by hand because what was staged for it could not work.**

1. **`STEPHP.BAT` passed `-d` to a binary that has no debug log compiled
   in.** `CKBB.EXE` is the shipping build, which is `NODEBUG`; `-d` needs
   `XFLAGS=-dKEEP_DEBUG`. **The rule against exactly this is quoted in
   `CLAUDE.md` and again in this sheet's own §0** — *a sheet that names a
   `-d` flag must also name the staged binary that carries it, or the flag
   is a suggestion.* Worse, §0's `-d` guard row still said "except HL",
   written before `-d` moved to HP and never updated.
2. **`s16bcHP.ksc` and `rcvhp.dat` were never created.** Pass 2 wrote six
   `.BAT` files and staged them; the host half of HP was never written at
   all. The operator built both by hand to get a run.
3. **The fixture would have been wrong even so.** 32,768 bytes at ~25 ms
   per received byte (§16k) is ~13 minutes of leg and a debug log with no
   room on a volume at 536 KB free — **and the size buys nothing, because
   the stall is in `rcvfil()` BEFORE a data byte moves.**

**What the hand-run leg still produced is worth keeping.** Without `-d`
(`deb=0`) it is a third `A:\` receive, and it reads **`dec max=450 at
#2`** — so the figure is now:

| leg | volume | rate | `dec max` |
|---|---|---|---:|
| HA | `A:\` | 38400 | **450** |
| HL | `A:\` | 9600 | **450** |
| HP | `A:\` | 9600 | **450** |
| **HN** | **`D:\`** | 9600 | **100** |

**Three independent legs at two line rates give the same 450, and the one
leg on the other volume gives 100.** The cost is fixed, rate-independent,
and a property of that root directory. **The mechanism is still not
established** — that is what `-d` was for.

### Pass 3 — staged, and this time the flag has a binary

| | |
|---|---|
| `CKHPDBG.EXE` | **314,168 bytes**, md5 `23e77b89…`, `-dKEEP_DEBUG` from HEAD, round-tripped off the image. Needs **320,920 (313K)**, smallest Victor **512K** — worth noting, it is not a 384K build |
| `STEPHP.BAT` | rewritten to call `CKHPDBG.EXE`, staged, round-tripped |
| `s16bcHP.ksc` | **written** — with what to grep for: `zchko`, `rcvfil`, `znewn`, `zopeno`, and the F-packet-to-ACK timestamps |
| `rcvhp.dat` | **512 bytes**, `40257431…` — small on purpose |

`ckermitw.exe` rebuilt from HEAD after the debug build still reproduces
`c42c3598…`, so nothing shifted underneath. **`A:` is 536 KB free.**
Expect `deb=1` on this leg and no other, and **read the log, not the
clock.**

---

## Leg HP, properly run: the `A:\` stall is `zchko()` creating and deleting a file

**`deb=1`, `CKHPDBG.EXE`, 512-byte fixture, `HP.LOG` 40,859 bytes and
1,724 lines** — small enough to read, which is what the small fixture was
for. Counters: `rxlost=0 rxfull=0 rxpeak=362`, `dec max=700 at #2`,
`elapsed=3700 cs` (all inflated by `-d`; **read the log, not the clock**).

### Where the time is

The log carries `gtimer=` at intervals, which is the only clock in it. The
transfer's timer starts at line 709 and the jumps are:

| log line | `gtimer` | Δ | what is in that span |
|---:|---:|---:|---|
| 709 | 1 | — | the F packet is decoded |
| **787** | **6** | **+5 s** | **the whole of `rcvfil()`'s pre-data block** |
| 827 | 7 | +1 | the F-packet ACK goes out |

**The five seconds sit between the F packet arriving and the ACK leaving**,
which is exactly the gap §16ay first saw and §16ba localised to the volume.

### What is in that block, from the log

```
rcvfil srvcmd 2[rcvhp.dat]
zchko entry[rcvhp.dat]
  isdir stat[rcvhp.dat]=-1              <- stat
  zchko attempting to open[rcvhp.dat]
  zchko open[rcvhp.dat]=7               <- CREATES THE FILE
  zchko isatty[rcvhp.dat]=0
  zdelet[rcvhp.dat]=0                   <- AND DELETES IT AGAIN
  zchko access[.]=0
zchki stat fails[rcvhp.dat]=1           <- stat
rcvfil calling zmkdir[rcvhp.dat]
  zfnqfp -> zgtdir -> v9k_getcwd[A:]
  isdir stat[A:/rcvhp.dat]=-1           <- stat
rcvfil fspec[A:/rcvhp.dat]
```

**Per received file, before one data byte moves: four stats, one file
CREATE and one file DELETE, all in the destination directory.**

### It is upstream's, it is deliberate, and upstream says it is flawed

`ckufio.c`'s `zchko()` opens the file with `O_WRONLY|O_CREAT` **purely so
it can call `isatty()` on the descriptor**, then deletes it again if it did
not already exist. `ckvictor.h:1222` defines `NOUUCP`, which is the arm
that does this. The function's own header comment reads:

> `NOTE: The design is flawed.  There is no distinction among:`
> `. Can I overwrite an existing file?`
> `. Can I create a file (or directory) in an existing directory?`
> `. Can I create a file (or directory) and its parent(s)?`

So the writability test is performed **by actually creating a file**. On a
POSIX filesystem that is cheap. On a **FAT12 root directory** it is a
free-slot scan plus a directory write, and then a second directory write to
remove it.

### Why it is volume-dependent, and how far the evidence goes

`A:`'s root holds **156 files**; `D:` holds ~25. The stats are O(1)-ish
lookups; **the create and the delete are the two operations whose cost
scales with directory occupancy**, and leg HN ran this identical code path
on `D:` and read `dec max=100` against `A:`'s 450. **The cost tracks
directory size, which points at the two writing operations rather than the
four stats.**

**The limit of the evidence, stated plainly: `HP.LOG` has no per-line
timestamps, so the 5 s is attributed to the block and not split within
it.** Splitting it needs either `SET DEBUG TIMESTAMP` or a leg on a volume
with `A:`'s file count and a different history — deleted `0xE5` slots
remain the untested half of §16ba's candidate list.

### What this is and is not

**It is not a port defect and there is nothing to fix here.** It is a
fixed, rate-independent cost — `dec max=450` on `A:` at 9600 *and* at
38400 — that upstream pays once per received file and that FAT makes
expensive. It belongs in the report-upstream list (item 8) beside the other
three `ckufio.c`/`ckcfns.c` findings, with the observation that a
writability probe which creates and deletes a real file is doing an
expensive and slightly dangerous thing: the same function already carries a
2022 fix and a long comment about **not** destroying a pre-existing file,
which is the failure mode this design invites.

**Practical note for anyone running this port:** receiving into a FAT root
directory with many entries costs several seconds per file. Receiving into
a subdirectory, or a less populated volume, does not. §16ba leg VF saw the
same thing from the other side and this says why.

---

## After the sitting

**Pass 1 ran 20 August 2026 on the real Victor 9000.** Eight legs produced
data, **seven transfers were byte-exact** (`d94d2bed…` every one), five legs
are outstanding and re-staged. Results are inline against each leg above.

1. **PORTING.md §16bc.** The headline is that the port came through six
   MAME-only sittings unmoved (HA, +0.54 s on a 1.3 s floor), and there are
   four new facts under it: **FreeDOS runs on real hardware at 38400 and is
   the fastest this port has been** (HG, 1,438 cps, 15% over MS-DOS on the
   same machine and hour); **console output breaks a 38400 FreeDOS receive
   at the first long packet** (HH against HG, one variable, NAKs from
   packet 05 on); **edits 19, 20 and 22 are confirmed on the wire** (HJ);
   and **`nap per=286` is the machine's real calibration** against MAME's
   409.
2. **`NEXT_SESSION.md`**: item 11 (flow control) moves on HD's answer;
   item 14 (FreeDOS) moves on HF/HG/HH; item 7 (the parser leg) closes on
   HM. **Item 5a is already closed by §16ai and should be struck** — it
   still reads as pending.
3. Extract every `.OUT` into `v9k/legs/` and **`git add` them**. §16bb's
   lesson: the leg files that are in git are the ones a mistake cannot
   destroy quietly.
4. If HD is positive, **the next sitting is a second pair, not a default
   change.**

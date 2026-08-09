# Bench run §16af — does edit 17 (the 16-bit `chk3()`) close the ring defect?

**This file is the procedure for the operator at the machine — work from it
rather than from a summary of it.** Three legs, ~15 minutes. Everything is
staged; nothing here needs a rebuild. Each leg produces **three** files and
the run is incomplete without all three; see "Produced by the run" below.

## What is being tested, and why MAME could not test it

Edit 17 rewrites `chk3()` for `VICTOR9K` only: the same CRC-16, same
polynomial, same initial value, same absence of a final XOR, computed in
`unsigned int` through one 256-entry table instead of in `long` through two
16-entry `long` tables. `v9k/proofs/vcrc16.c` proves the algorithms identical
over all 256 table entries and 20,500 length-and-fill combinations.

Two claims are outstanding and **only the bench can settle them**:

1. **`rxfull` returns to 0 at block 3.** §16ae found three of four block-3
   legs pinning `rxpeak` at 4,095 of 4,096 and losing bytes (556, 640, 649)
   while all three block-1 legs sat at 2,6xx with `rxfull = 0`. The µPD7201
   does not overrun below 38400 (§16q) and MAME cannot drive above 9600
   (§16n), so **there is no emulator run that reaches this code at all.**
2. **How much of block 1's speed the edit buys while keeping CRC-16.**

MAME did confirm, at 9600 on a protocol-identical run (`rxbytes = 39,575`
in both, same 1 timeout and 1 retransmission): byte-exact, `rxlost = 0
rxfull = 0`, host elapsed 51.829 s → 49.689 s, 632 → 659 cps. That is
**54 µs saved per wire byte**. It says the edit is correct and helps; it
says nothing about the ring.

## Files, all staged in the repo

| on the image | what |
|---|---|
| `CKERMITW.EXE` | **new** build, edit 17, 205,968 bytes, needs 220,160 (215K) |
| `CKBASE.EXE` | **baseline**, sixteen edits, 205,552 bytes, needs 219,744 (214K) |
| `STEPAG.BAT` `STEPAH.BAT` `STEPAJ.BAT` | one per leg, CRLF already |

| on the Mac | what |
|---|---|
| `s16afAG.ksc` `s16afAH.ksc` `s16afAJ.ksc` | take-files, one per leg |
| `rcvag.dat` `rcvah.dat` `rcvaj.dat` | the 32,768-byte all-byte-values fixture, `d94d2beda069ef0ef340977e7fd6995d` |

**Produced by the run — three files per leg, and the first is the one that
gets forgotten:**

| artefact | from | why it is wanted |
|---|---|---|
| `s16afXX.host` | the `>` redirect on `kermit` | the host `statistics`: the finer of the two clocks |
| `s16afXX.pkt` | `log packets` in the take-file | resend and timeout counts (§16l) |
| `s16afXX.out` + `gotXX.dat` | off the image | the `v9k:` counters and the received file |

Each leg has **its own fixture name and its own output name**, so no leg can
collide with or be mistaken for another — §16ae's convention.

## Stage the image

```sh
cd ~/projects/ckermit
vtg_image_util copy ckermitw.exe ~/projects/mame/victor_kermit.img:0:\\CKERMITW.EXE
vtg_image_util copy CKBASE.EXE   ~/projects/mame/victor_kermit.img:0:\\CKBASE.EXE
for b in AG AH AJ; do
  vtg_image_util copy STEP$b.BAT ~/projects/mame/victor_kermit.img:0:\\STEP$b.BAT
done
```

`CKERMITW.EXE` on the image is **already** the edit-17 build — the §16af
MAME run put it there. Copy it again anyway if the Pico has its own copy of
the image.

## The three legs

Run **AJ and AG back to back**. AJ is a drift control and a control taken an
hour from the thing it controls has drift of its own.

| leg | Victor | host take-file | build | prefixing × block |
|---|---|---|---|---|
| **AJ** | `STEPAJ` | `s16afAJ.ksc` | **CKBASE** | cautious × 3 |
| **AG** | `STEPAG` | `s16afAG.ksc` | CKERMITW | cautious × 3 |
| **AH** | `STEPAH` | `s16afAH.ksc` | CKERMITW | cautious × 1 |

For each leg: start the Victor first so it is listening, then the Mac.

```sh
# Victor:                    A> STEPAG
# Mac, once the Victor is waiting:
kermit -y /dev/null < s16afAG.ksc > s16afAG.host 2>&1
```

**The `> s16afAG.host` redirect is not optional.** It is the only way the
host `statistics` reaches a file, and the host clock is the finer of the two
(the Victor's advances in half-second steps). §16ae lost this figure and so
did §16af's first sitting. **Three files per leg, not two:** `.host`,
`.pkt`, and the Victor's `.OUT`.

Then recover both artefacts:

```sh
vtg_image_util copy ~/projects/mame/victor_kermit.img:0:\\STEPAG.OUT ./s16afAG.out
vtg_image_util copy ~/projects/mame/victor_kermit.img:0:\\RCVAG.DAT   ./gotAG.dat
md5 gotAG.dat rcvag.dat        # must match
```

(If the Pico serves the image read-only to the Victor, the `.OUT` and
`.DAT` come back however §16o's bench normally recovers them — the point is
that **both** files are needed per leg, not just the received data.)

## Reading the result

**Read `rxfull` before anything else, and do not read `cps` first.** The
protocol *hides* this defect: all seven of §16ae's legs were byte-exact,
including the ones that lost 649 bytes, because the block check caught the
damage and the host resent. Byte-exactness is necessary and proves nothing
on its own.

| | §16ae PC (was) | AJ (control, expect) | **AG (predict)** | §16ae BX / AH |
|---|---:|---:|---:|---:|
| `rxfull` | 640 | ~PC | **0** | 0 |
| `rxpeak` | 4,095 *pinned* | ~PC | **2,6xx–3,2xx** | 2,611 |
| `rxbytes` | 44,720 | ~PC | **37,4xx–37,6xx** | 37,523 |
| Victor `elapsed=` | 3,800 cs | ~PC | **2,700–3,000 cs** | 2,650 cs |

A pinned `rxpeak` of 4,095 is a ceiling, not a measurement — it means "at
least this much" and cannot be differenced.

**Outcomes and what each means**

- **`rxfull = 0` and `rxbytes` near 37,5xx** — the edit did what it was made
  for. The 16% of wire bytes that were resend traffic are gone, which is
  worth more than the CPU saving. Ship it; write §16af; `chk3()` closes.
- **`rxfull = 0` but `elapsed` barely moves** — the edit fixed the ring and
  not the clock. Still the more valuable half: `rxfull != 0` is a live
  defect and this closes it.
- **`rxfull` still nonzero** — the CRC was not the whole cause. The
  foreground is still too slow for a 4,000-byte packet at 38400, and the
  next lever is the ring size or `DRPSIZ`, with §16k's sizing argument
  redone from scratch (§16t voided it).
- **AJ does not reproduce PC** — something about today's bench differs from
  §16ae's. AG is then uninterpretable in absolute terms, but **AG − AJ is
  still the honest measurement** and is the number to quote.
- **AH differs from BX** — do not attribute AG's gain to `chk3()`. Edit 17
  has no mechanism to change block 1, so a moved floor means the rebuild
  itself changed something and the comparison is measuring layout.

## Two cautions carried forward

- The Victor's `elapsed=` and the host's `statistics` **do not measure the
  same interval** (§16u): the Victor's opens at the first byte received,
  before the S packet, and closes at release — 1.7 s wider on a clean run.
  Quote the pair, never one alone. `wire=` divides `rxbytes` and is a
  receive-leg figure.
- Every Victor timing figure is a multiple of 50: this machine's DOS clock
  advances by half a second (§16n). On a ~2 s effect that is ±25%, so where
  the two clocks disagree, **the host's is the finer instrument**. Quote
  `tot=`, never `max=`.

## If a leg will not run

- **`.BAT` files must have CRLF.** These three do — `od -c STEPAG.BAT`
  ends `\r \n`. It is the first item on §16a's landmine list and §16ae
  stepped on it anyway.
- MS-DOS 3.1's COMMAND.COM **cannot redirect handle 2**; `2> FILE` puts a
  literal `2` in `argv`. The `.BAT` files use `>` only.
- The device name must be `/dev/seriala` with **forward** slashes.

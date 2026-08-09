# Bench run sheet — the seven legs that need the Victor

**This document is the thing to work from. Follow it top to bottom.** That
sentence is here because §16af lost a whole session's host timings to a run
sheet that existed and was never handed over as one, and §16ae lost the same
figure before it. A document is not an instruction until someone is told to
follow it.

**Nothing below needs building, writing, or staging.** Both binaries are
compiled and on the image, the seven take-files and seven `.BAT`s exist, and
§0 is a receipt showing what was verified rather than a list of chores. An
earlier draft of this document said "copy `s16afAG.ksc` and change the log
name" and opened with a build-and-stage section — which is §16af's handoff
defect one level down: **a procedure with an unwritten step in it is not a
procedure, and neither is one whose first step is "do the setup yourself".**

Written 9 August 2026, after PORTING.md §16ag. Three questions, seven legs,
one sitting. What is left is the part that needs a keyboard and a
power switch.

---

## 0. Staging — **already done. This section is a receipt, not a task.**

Both binaries are built, staged, and **round-trip verified out of the image**
(copied back off and md5'd against the local file). The image is
`~/projects/mame/victor_kermit.img`, which PORTING.md §5224 records as the
one the Pico SASI serves unmodified — the same file MAME boots. Nothing here
needs doing before you sit down at the Victor.

| on the image | bytes | md5 | what it is |
|---|---:|---|---|
| `CKERMITW.EXE` | 205,256 | `433148fa…` | **the shipping build.** Byte-identical to the binary §16ag legs AP/AQ measured. Legs BA, BB, BS, BC, BD |
| `CKFERR.EXE` | 204,888 | `415cf233…` | `-dV9K_FAST_ERRNO`. Byte-identical to the binary §16ag legs AL/AN measured. Legs BE, BF |
| `CKAK.EXE` | 205,968 | `8d40f7f6…` | §16af's edit-17 build, **preserved** — it is what §16ag legs AK/AR/AM ran, and it was sitting on the image under the name `CKERMITW.EXE` |

Also staged: `STEPBA` `STEPBB` `STEPBS` `STEPBC` `STEPBD` `STEPBE` `STEPBF`,
all CRLF, verified as CRLF *after* landing on the image.

**Checked, so you do not have to:** no `RCVBA…RCVBF`, no `STEPB[A-F,S].OUT`
and no `GOTBS` on the image, so nothing will trip `SET FILE COLLISION`
`BACKUP` (which cannot work on FAT; the symptom is S, F, A, then **Z with
data `D`** and no data packets). `RCVAG.DAT` is present at exactly 32,768
bytes, which is what leg BS sends. 2.5 MB free.

**Note the one overwrite.** `CKERMITW.EXE` on the image was §16af's
205,968-byte build and is now the current 205,256-byte one. The old file was
not discarded — it is `CKAK.EXE` on the image and `ckak.exe` in the tree.
It was overwritten rather than left because a stale binary under the name
that means "the shipping build" is a trap, and §2 of `NEXT_SESSION.md` is
about exactly this: the exit report cannot tell two builds apart, so the
names have to.

**The one thing that is yours:** check `~/.kermrc` names the adapter actually
plugged in. §16v used `BG022B8M` and §16af used `ABBFKXM1`. The take-files
deliberately do **not** set the line, so this is the single place the device
name lives — and hard-coding either one into seven files is how it goes
stale.

**To rebuild either binary** (you should not need to):

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak clean && make -f victorow.mak"
# -> ckermitw.exe, 205,256, md5 433148fa…

container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak clean && \
   make -f victorow.mak XFLAGS=-dV9K_FAST_ERRNO"
# -> ckermitw.exe, 204,888, md5 415cf233…   (copy it aside as ckferr.exe)
```

---

## Before every leg

**Three files per leg. A leg missing any of them is a leg to re-run.**

| file | where it comes from | why it is wanted |
|---|---|---|
| `s16ah<LEG>.host` | `kermit -C "take …, exit" > s16ah<LEG>.host` | **the millisecond clock.** The Victor's own clock advances in 50 cs steps, which is the same size as most of the differences being measured. This is the file that has gone missing twice. |
| `s16ah<LEG>.pkt` | `log packets`, already in each take-file | packet count, retransmissions, timeouts; `grep -c '^S-'` and `grep -c '<timeout>'` |
| `s16ah<LEG>.OUT` | `> STEP<LEG>.OUT` on the Victor, then extract | the `v9k:` counters — `rxlost`, `rxfull`, `rxpeak`, `elapsed=` |

Plus the transferred file, `cmp`'d against the fixture.

- Power-cycle the Victor **and** the Pico between runs.
- Delete a stale `X.LOG` before `REN DEBUG.LOG X.LOG` — the REN fails
  silently and leaves the old log beside a fresh `.OUT`.

---

## Leg 1 — calibration. Legs **BA** and **BB**.

**Do this first.** It is not a code change and it unblocks the reading of
everything else: almost every per-item cost in this port is currently known
only to within a factor of two, because the Victor's 50 cs quantum is the
same size as the differences and the host `statistics` was not captured for
§16af's three legs or §16ae's seven.

The specific number it fixes: §16af's cleanest result is that CRC-16 now
costs **one clock quantum** over a 6-bit checksum, i.e. 100 ± 50 cs, i.e.
**13 to 40 µs per wire byte**. Against the 60–90 8088 cycles that separate
the two block checks, that band admits an effective clock anywhere from
**1.5 to 7 MHz**. One sitting with a millisecond clock replaces the band
with a number.

Victor first (it waits in receive), then the host:

```
STEPBA                                              (at A>, block check 3)
```
```sh
kermit -C "take s16ahBA.ksc, exit" > s16ahBA.host
```

then

```
STEPBB                                              (at A>, block check 1)
```
```sh
kermit -C "take s16ahBB.ksc, exit" > s16ahBB.host
```

Extract `STEPBA.OUT`/`STEPBB.OUT` and `RCVBA.DAT`/`RCVBB.DAT`, and `cmp`
against `rcvba.dat`/`rcvbb.dat`.

**Targets, both from §16af (Victor clock):** BA — `rxfull` 0, `rxpeak` 2,581,
`rxbytes` 37,568, 18 packets, 0 resends, `elapsed` 2,800 cs. BB — 0, 2,585,
37,534, 18, 0, 2,700 cs. **A null result against AG and AH is the pass**;
nothing has changed on either path, so a leg that comes back materially
different is measuring the harness.

**Deliverable:** a calibration constant — µs per 8088 cycle on this machine
for a memory-bound loop — that every later estimate is quoted against.
Expected, from §16v's leg CA pair (34.00 s Victor against 32.32 s host):
BA's host figure near **26.3 s and ~1,245 cps**.

---

## Leg 2 — send a 32 KB file BY NAME. Leg **BS**. Two results for one leg.

**It closes upstream edit 16, which shipped unverified.** §8's own words:
*"Proven so far only at the level of generated code… Not yet run end to
end."* A 16-bit `rc` at `ckuusy.c:3690` threw away `zchki()`'s return, which
on success is the **file size**, so `-s <name>` refused any file of 32,768
through 65,535 bytes — periodically, every 64K. **It is the only shipped
edit in this port with no runtime evidence behind it.**

**And it is the port's first send-direction measurement of any kind.**
`V9K_PREFIXING` and `ckvictor.c`'s prefixing initializer govern Victor→host
only — §16ae established that `ctlp[]` is read by the packet *builders* — and
no leg has ever exercised them.

**Note the direction: the host is the receiver here, so start it FIRST.** The
Victor is the initiator and will give up if nothing answers its S packets.

```sh
kermit -C "take s16ahBS.ksc, exit" > s16ahBS.host    &   # host receives, waits
```
```
STEPBS                                              (at A>, sends RCVAG.DAT)
```

`cmp gotbs.dat rcvag.dat`, and extract `STEPBS.OUT`.

**Reading it — three traps:**

- **The tell for the old bug is `kermit -s NAME:` with an EMPTY message
  after the colon.** Nothing set `errno`, because nothing failed — `zchki()`
  had succeeded and the caller threw the answer away.
- **`wire=` is a receive-leg figure.** It divides `rxbytes`, so on a send leg
  it reports the ACK stream over the whole elapsed time. It is not the send
  rate; the host's `statistics` is.
- **`pktstat.py` misreads send logs** — "longest packet" reads the one-byte
  LEN field, which is 0 for long packets, and its `S-` count is the *host*
  retransmitting. Read `s16ahBS.pkt` by hand.

**If it fails**, run `CKERMITW -l /dev/seriala -b 38400 -s RCVAG.*` by hand.
A wildcard reaches `nzxpand()` and routes around the bug entirely, so a
wildcard passing while the name fails **is the confirmation**, not a
workaround to move on from.

---

## Leg 3 — the `errno` far call. Legs **BC/BD** against **BE/BF**.

**Four legs, two per arm.** §16ag built this change, verified the mechanism
in `wdis` — 27 far calls leave `ckutio.obj` — and measured it **98 ms
slower** at 9600 under MAME, so it ships **off**, behind
`XFLAGS=-dV9K_FAST_ERRNO`.

**Why the bench can settle what MAME could not, and it is structural rather
than a matter of precision.** At 9600 the byte time is 1,040 µs against
~485 µs of foreground, so there are **555 µs of slack per byte** for a
per-byte saving to hide in. At 38400 the byte time is 260 µs and the
foreground is *behind* — which is exactly why `rxpeak` sits at 2,581 there
and at 299 at 9600. A per-byte foreground cost absorbed at 9600 is on the
critical path at 38400.

Run them **interleaved**, not as two blocks — BC, BE, BD, BF — so that any
drift in the bench over the sitting lands on both arms:

```
STEPBC     ->  kermit -C "take s16ahBC.ksc, exit" > s16ahBC.host
STEPBE     ->  kermit -C "take s16ahBE.ksc, exit" > s16ahBE.host
STEPBD     ->  kermit -C "take s16ahBD.ksc, exit" > s16ahBD.host
STEPBF     ->  kermit -C "take s16ahBF.ksc, exit" > s16ahBF.host
```

**Two legs per arm is not caution for its own sake.** §16ag's control arm put
two runs of one binary **321 ms** apart while its other two arms held to 1 ms
and 5 ms, with no explanation found. One pair does not establish this
harness's resolution.

**The comparison is only valid if the arms are protocol-identical** —
`rxbytes` equal, same packet count, same retransmissions. A leg that
retransmits differently is not comparable and is **re-run, not adjusted**;
§16ag leg AM is the worked example of excluding one.

**Decision rule, stated in advance so it is not fitted afterwards.** If the
treatment arm is faster by more than the within-arm spread, make
`V9K_FAST_ERRNO` the default and say so in PORTING.md §16ag. If it is not,
the change has failed on both instruments and **should come out of the tree**
rather than stay as a permanent maybe.

---

## What none of these legs covers

- **A transfer on the `KEEP_ICP` parser build.** Edit 14 widened what
  `main()` compiles and the shipping binary is no longer the one measured at
  1,170 cps. One 32 KB leg reporting `rxlost=0 rxfull=0` and a byte-exact
  md5 is what says the wire protocol did not move. `NEXT_SESSION.md` §1
  item 7.
- **Server mode on hardware** — `-g`, `-f`, `-x`, `--safe-server`.
  `HW_TESTING.md` leg 0.7, still untouched.
- **Splitting the foreground bucket.** 17.7 s of leg AG is one subtraction
  and separates nothing. `NEXT_SESSION.md` §1 item 9.

---

## Artefact checklist

| leg | take-file | `.BAT` | fixture | Victor writes | binary |
|---|---|---|---|---|---|
| BA | `s16ahBA.ksc` | `STEPBA.BAT` | `rcvba.dat` | `RCVBA.DAT` | `CKERMITW` |
| BB | `s16ahBB.ksc` | `STEPBB.BAT` | `rcvbb.dat` | `RCVBB.DAT` | `CKERMITW` |
| BS | `s16ahBS.ksc` | `STEPBS.BAT` | image `RCVAG.DAT` | host `gotbs.dat` | `CKERMITW` |
| BC | `s16ahBC.ksc` | `STEPBC.BAT` | `rcvbc.dat` | `RCVBC.DAT` | `CKERMITW` |
| BD | `s16ahBD.ksc` | `STEPBD.BAT` | `rcvbd.dat` | `RCVBD.DAT` | `CKERMITW` |
| BE | `s16ahBE.ksc` | `STEPBE.BAT` | `rcvbe.dat` | `RCVBE.DAT` | `CKFERR` |
| BF | `s16ahBF.ksc` | `STEPBF.BAT` | `rcvbf.dat` | `RCVBF.DAT` | `CKFERR` |

Every fixture is the 32,768-byte all-byte-values file,
md5 `d94d2beda069ef0ef340977e7fd6995d`.

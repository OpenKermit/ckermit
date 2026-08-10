# Bench run sheet — flow control on a real cable

**This document is the thing to work from. Follow it top to bottom.**
Inherited from `HW_TEST_16ag.md` and `HW_TEST_16ai.md`, and still earning
its place.

**Nothing below needs building, writing, or staging.** Both binaries are
compiled, staged and round-trip verified out of the image; seven `.BAT`s are
on the image and verified CRLF **after** landing there; seven take-files and
five fixtures are in the tree; the target names are checked clear. §0 is a
receipt, not a list of chores.

Written 9 August 2026, after PORTING.md §16aj. Seven legs, one sitting.

> **RUN 9 August 2026. All seven legs completed and EVERY TRANSFERRED FILE
> IS BYTE-EXACT.** Results are recorded inline against each leg and written
> up in PORTING.md **§16ak**.
>
> **The sitting answered "is it safe" and did not answer "is it effective".**
> DS and DE say turning RTS/CTS on costs nothing and cannot wedge the
> transmitter. **DB — the leg the sitting was for — went off-shape** (a
> timeout and three retransmissions inside the first 7,680 bytes) and its
> `rxpeak` was latched 14 bytes into a *resend*, which is exactly the
> §16m/§16ag case where `rxpeak` measures the retransmission and not the
> transfer. **The caveat printed under Leg 3 below is the one that fired.**
>
> **Two things this sheet got wrong, and they are mine:** it has a null leg
> but **no adjacent pre-change control**, so an 11% throughput gap against
> §16ah cannot be attributed or dismissed; and it read `rxpeak` as a cap
> without asking where in the packet stream the peak sat. `mapoffset.py`
> answers that in one command and changes the reading of two legs.
>
> **The default has NOT been flipped.** See "After the sitting".

---

## What this sitting is for, in one paragraph

Flow control is **built** — `ckvictor.c` §1f, RTS/CTS and XON/XOFF, both
directions, in both interrupt handlers, no upstream edit — and it **ships
switched off**. It ships off for one reason: selecting RTS/CTS makes the
Victor's transmitter wait for CTS, and §16v measured only the *inbound*
direction of that pair (the host's RTS arriving at our CTS, `cts = 1` in
both legs with the host on `set flow none`). **Nothing has ever measured our
RTS arriving at the host's CTS.** A cable wired one way would turn a working
port into one that never sends a byte, which is a much worse failure than
the one flow control is insuring against.

**Leg DB is the whole sitting.** The rest establishes that the machine is
behaving, that the CTS gate does not wedge the transmitter, that the other
mechanism works too, and that turning the thing on changes nothing when it
is not needed.

**It has already been validated under MAME at 9600** — four legs, byte-exact,
`rxlost = 0 rxfull = 0`, the water mark asserting and releasing once each
with the marks lowered. What MAME *cannot* do is any of this: `-bitb socket`
is a raw byte stream with no modem control at all, so an RTS/CTS leg there
tests nothing on the wire. That is why this sheet exists.

---

## 0. Staging — **already done. This section is a receipt.**

Image is `~/projects/mame/victor_kermit.img`, the same file the Pico SASI
serves and MAME boots. Backup taken before any of this:
`victor_kermit.img.bak-20260809-preflow`.

| on the image | bytes | md5 | what it is |
|---|---:|---|---|
| `CKERMITW.EXE` | 206,758 | `c5652a5b…` | **the shipping build with §1f.** Legs DN, DS, DE, DX |
| `CKFCLO.EXE` | 206,758 | `c22f2366…` | the same tree with `-dV9K_RXHIGH=256 -dV9K_RXLOW=64`. Legs DA, DB, DC |

**`CKFCLO` is an unusually good control and it is worth knowing why.** Same
tree, same commit, same flags but two `-d`s, and **the same 206,758 bytes**.
`cmp` says the entire difference is **five bytes** — the high mark `0C00h`
against `0100h` in one immediate, and the low mark `0400h` against `0040h`
in one immediate and one initialiser:

```
0x244cc   0c -> 01        V9K_RXHIGH  3072 -> 256   (immediate)
0x244d6   00 04 -> 40 00  V9K_RXLOW   1024 -> 64    (immediate)
0x322c2   00 04 -> 40 00  V9K_RXLOW   1024 -> 64    (v9k_rxlow initialiser)
```

So §16w's finding that this machine is sensitive to code size has **no
purchase here** — the layouts are identical. And `CKFCLO` is not an untested
binary: **it is the one that ran §16aj legs FH and FJ under MAME**, byte-exact
both times. A failure at the bench is therefore attributable to the cable and
not to a build nobody has run.

**Staged and verified CRLF *after* landing on the image:** `STEPDN` `STEPDS`
`STEPDA` `STEPDB` `STEPDE` `STEPDC` `STEPDX`. Reused unchanged: `TRANS.DAT`
(32,768 bytes, md5 `d94d2beda069ef0ef340977e7fd6995d`).

**Checked, so you do not have to:** no `RCVD*.DAT` and no `STEPD*.OUT` on the
image, so nothing will trip `SET FILE COLLISION` `BACKUP` — which cannot
work on FAT, and whose symptom is S, F, A, then **Z with data `D`** and no
data packets. No stale `gotd*.dat` on the host. Host fixtures `rcvdn.dat`
`rcvda.dat` `rcvdb.dat` `rcvdc.dat` `rcvde.dat` are all copies of
`TRANS.DAT`.

**The one thing that is yours:** check `~/.kermrc` names the adapter actually
plugged in. §16v used `BG022B8M`, §16af used `ABBFKXM1`. The take-files
deliberately do **not** set the line, so this is the single place the device
name lives.

**`~/.kermrc` also carries `set flow none`, and five of the seven take-files
below deliberately override it.** That matters for one reading in
particular: §16v's `cts = 1` was evidence *because* the host was not using
RTS, so it held RTS asserted throughout. Leg DN keeps `set flow none` for
exactly that reason and is the only leg whose `mdm cts=` line means what
§16v's meant.

**To rebuild anything** (you should not need to):

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak clean && make -f victorow.mak"
# -> ckermitw.exe, 206,758, md5 c5652a5b…, DGROUP 48,336 (73%), needs 220,950 (215K)

container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak clean && \
   make -f victorow.mak XFLAGS='-dV9K_RXHIGH=256 -dV9K_RXLOW=64'"
# -> ckermitw.exe, 206,758, md5 c22f2366…   (copy aside as CKFCLO.EXE)
```

---

## Before every leg

> ### ⏱ THE MACHINE TAKES ABOUT 40 SECONDS TO START. WAIT FOR IT.
>
> Both binaries are 206 KB and the Victor reads the whole thing off SASI
> before `main()` runs. On any leg where the **host sends first** — DN, DA,
> DB, DE, DC — starting the host too soon exhausts `MAXTRY` (10,
> `ckcker.h:472`) against a Victor that has not reached `receive` yet, and
> **a host that gives up looks exactly like a Victor that failed.** That is
> what happened to §16ai legs CE and CH. Start the Victor, wait for the
> drive to go quiet, then start the host. Those five take-files also carry
> `set retry 30`, which is the belt to that braces.
>
> **DS and DX are the other way round** — the Victor sends, so it is the
> initiator, and the **host** goes first and waits.

> ### 👁 THE REDIRECT HIDES EVERYTHING
>
> `> STEPD<x>.OUT` is required — the `v9k:` counters only reach stdout — but
> it swallows the transfer display. The shipping build asks no questions on
> the receive path (`ckvictor.c`'s `getyesno()` answers yes, and §16ai
> explains why that stub is load-bearing), so a redirected leg should not be
> able to hang on a prompt. **If one seems to hang anyway, run the Victor
> side by hand without the redirect before concluding anything.**

> ### ⚡ ONE LEG CAN WEDGE, AND IT IS DS. RUN IT THIRD, NOT LAST.
>
> `--rtscts` makes `v9k_ser_put()` require CTS before every byte. If CTS is
> not actually asserted on this cable the Victor sends **nothing at all** —
> not a slow transfer, not a corrupt one, silence. That is a legitimate
> result and it is the failure the `FLO_NONE` default exists to avoid.
> **Record it and stop the RTS/CTS arm; do not debug the cable at the
> bench.** DC and DX are the XON/XOFF arm and are unaffected.

**Three files per leg. A leg missing a *result* is a leg to re-run** — a leg
missing a *file* whose result you already have is not (§16ai).

| file | where it comes from | why |
|---|---|---|
| `s16ajD<x>.host` | `kermit -C "take …, exit" > s16ajD<x>.host` | the millisecond clock. Capture it even on the counting legs |
| `s16ajD<x>.pkt` | `log packets`, already in each take-file | packets, wire bytes, prefixes, retransmissions, prefixing policy |
| `STEPD<x>.OUT` | `> STEPD<x>.OUT` on the Victor, then extract | the `v9k:` counters, including the new `v9k: flow` line |

Plus the transferred file, `cmp`'d against the fixture. **`cmp` first, always** —
two of these legs put the port in a mode that could plausibly eat a byte, and
a leg that is fast and wrong is the failure mode that survives every counter.

- Power-cycle the Victor **and** the Pico between runs.
- Do not write to the image while the machine is running.

**Read every packet log the same way:**

```sh
python3 v9k/tools/pktstat.py s16ajD<x>.pkt
python3 v9k/tools/pktstat.py --rxbytes <from the .OUT> s16ajD<x>.pkt   # receive legs
```

`host wire bytes − rxbytes = rxfull + startup offset`, offset **−11** clean
or **+28** with a startup timeout.

**The new line to read on every leg:**

```
v9k: flow in=0 out=0 hi=65535 lo=1024 held=0 rel=0 xoff=0 xon=0 stuck=0
```

`in`/`out` are **0** none, **1** XON/XOFF, **2** RTS/CTS, and they come from
upstream's `flow` variable rather than from the termios bits — §16aj has the
two upstream blocks that made the termios route a trap. `hi = 65535` means
flow control is off; it is unreachable because occupancy is masked to 4,095.
`held`/`rel` are ours and **should end equal**. `xoff`/`xon` are the far
end's, and **`stuck` should never move** — it counts writes abandoned after
seconds of hold-off.

---

## Leg 1 — the null leg. Leg **DN**. **Do this first.**

```
STEPDN                                  (at A>, CKERMITW, Victor receives)
```
```sh
kermit -C "take s16ajDN.ksc, exit" > s16ajDN.host
```

Extract `STEPDN.OUT` and `RCVDN.DAT`; `cmp` against `rcvdn.dat`.

Shipping build, no switch, flow control compiled in and switched off. **This
leg is here to say the machine, the cable and the harness are behaving before
anything else in the sitting is attributed to anything** — §16af's rule:
spend a leg on the result that is supposed to be nothing.

**Pass is §16ai leg CE / §16ah leg BC/BD shape:** `rxlost=0 rxfull=0`,
`rxpeak` 2,4xx–2,6xx of 4,096, 18 packets, 0 retransmissions, 0 timeouts,
`rxbytes` ~37,55x, byte-exact — and on the flow line, `in=0 out=0 hi=65535`
with every counter **0**.

**Also record `mdm cts=`.** This is the only leg in the sitting where that
reading is evidence, for the reason in §0: the host is on `set flow none` and
therefore holding RTS asserted.

> **RESULT — PASS.** Byte-exact. `rxlost=0 rxfull=0 rxpeak=2990 of 4096`,
> `rxbytes=37568`, 18 packets, **0 retransmissions, 0 timeouts**, 37,557
> wire bytes (+14.6%), `PX_CAU exactly (32 values)`, reconciliation −11.
> Flow line `in=0 out=0 hi=65535 lo=1024` and every counter 0. `mdm cts=1
> dsr=1`. Host clock **31.535 s, 1,039 cps**.
>
> `peakat=31667`, which `mapoffset.py` puts **2 bytes into seq=14** — the
> boundary between two 4,000-byte packets. That is the natural place for the
> peak and it matters for reading legs DB and DE.

---

## Leg 2 — the CTS gate. Leg **DS**. **Host first.**

```sh
kermit -C "take s16ajDS.ksc, exit" > s16ajDS.host   &   # host receives, waits
```
```
STEPDS                                  (at A>, CKERMITW --rtscts, Victor sends)
```

`cmp gotds.dat trans.dat`; extract `STEPDS.OUT`.

**This is the leg that can wedge, which is why it is third and not last.**
`--rtscts` gates the transmitter on RR0's CTS bit. §16v read `cts = 1` on
this cable in both legs, so it should transfer — and the host is on `set flow
rts/cts` here, so it may drop *its* RTS, which means this also tests that we
notice and resume rather than only that we start.

**Pass:** byte-exact, `stuck = 0`, `in=2 out=2`, cps in leg CC's band
(~1,4xx). **Fail:** no packets at all in `s16ajDS.pkt`. That is CTS not
asserted, §16v's reading was of something else, and the RTS/CTS arm stops
here — DC and DX still run.

> **RESULT — PASS, and it is the strongest result in the sitting.**
> Byte-exact (`gotds.dat`), `in=2 out=2`, **`stuck=0`**, `rxlost=0
> rxfull=0`, 18 packets, 0 retransmissions, 37,557 wire bytes.
> Host clock **22.206 s, 1,475 cps — equal to §16ai leg CC, the fastest
> figure this port has ever produced.**
>
> **The CTS gate costs nothing and cannot wedge the transmitter on this
> cable.** Compare leg DX, the same send with `--xonxoff`: 22.203 s. **Three
> milliseconds apart.** Neither flow-control mode is detectable on the send
> path.

---

## Leg 3 — **the decisive pair. Legs DA and DB, back to back.**

**Nothing in this sitting is comparable across a gap.** §16aj's MAME legs
drifted 12–15 s between two groups on the same fixture because the host
machine got busier; §16ah's bench does not repeat to better than ~1.3 s.
Run DA, then DB, then read them against each other and against nothing else.

```
STEPDA                                  (at A>, CKFCLO --noflow)
```
```sh
kermit -C "take s16ajDA.ksc, exit" > s16ajDA.host
```
then
```
STEPDB                                  (at A>, CKFCLO --rtscts)
```
```sh
kermit -C "take s16ajDB.ksc, exit" > s16ajDB.host
```

`cmp` both against their fixtures; extract both `.OUT`s.

**THE READING IS `rxpeak`, NOT THE CLOCK.** That is §16ai's rule applied:
when the bench cannot resolve an effect in seconds, find a counter that
measures the same mechanism in units that do not vary. Here the effect is
about eight-fold in a counter that is exact.

| | DA (`--noflow`, control) | DB (`--rtscts`) |
|---|---|---|
| `flow in/out` | 0 / 0 | **2 / 2** |
| `hi` | 65535 | **256** |
| `held` / `rel` | 0 / 0 | **> 0, and equal** |
| **`rxpeak`** | **2,4xx–2,6xx** | **?** |

- **`rxpeak` ≈ 256–600** — the far end stopped when we asked. **Our RTS
  reaches the host's CTS**, the pair is wired both ways, and the open
  question in `NEXT_SESSION.md` §1 item 11 is closed. Go on to DE.
- **`rxpeak` ≈ 2,4xx with `held > 0`** — we asserted and the far end kept
  sending. Not wired outbound, or not honoured. **The default stays
  `FLO_NONE` and XON/XOFF is the answer for this cable.** Skip DE. This is a
  result, not a failure, and it is the one the default was chosen against.
- **`held = 0`** — the mark was never crossed, which at 256 would be very
  odd on a leg whose control peaked at 2,5xx. Suspect the switch did not
  take: check `in=2` on the flow line before concluding anything about RTS.

**`held` and `rel` say WE asserted. `rxpeak` says THEY listened.** They are
separate readings and the leg needs both.

**One caveat, from §16ag:** `rxpeak` also moves with retransmissions — leg AM
came back at 17 of 4,096 with no resend where every retransmitting leg in the
same session sat at 299. If DA and DB differ in resend count the comparison
is weaker, but the effect here is thousands and a resend is worth hundreds.

> **RESULT DA — PASS, clean control.** Byte-exact, `rxlost=0 rxfull=0
> rxpeak=2780`, **`stall256=47`**, `peakat=31667` (2 bytes into seq=14, the
> same boundary DN peaked at), `held=0 rel=0 hi=65535`, 18 packets, 0
> retransmissions, 37,557 wire bytes, **31.137 s / 1,052 cps**.
>
> **RESULT DB — OFF-SHAPE. THE LEG DID NOT DECIDE.** Byte-exact, and the
> mechanism plainly ran: `in=2 out=2 hi=256`, **`held=15 rel=15`** (equal),
> `rxlost=0 rxfull=0`, `stuck=0`. But **1 timeout and 3 retransmissions
> inside the first 7,680 bytes**, slow start reset, 25 packets instead of
> 18, longest 3,585 instead of 3,991, 40,544 wire bytes instead of 37,557,
> 32.812 s / 998 cps.
>
> **`rxpeak = 2932`, and `mapoffset.py` puts `peakat=6704` FOURTEEN BYTES
> INTO A RESEND of seq=07.** That is §16m's finding and §16ag's caveat
> exactly: `rxpeak` measures the host's retransmission, and a leg that
> retransmits is not comparable with one that does not. **The caveat printed
> above this box is the one that fired, and it voids the reading this leg
> was designed to give.** Do not read "the host ignored our RTS" out of it.
>
> **One number is real, large and unexplained: `stall256 = 2,399` against
> DA's 47.** That counter increments when occupancy, after a store, equals
> exactly 256 — so occupancy crossed the mark upward 2,399 times, which
> requires it to have fallen back below 256 that many times, which requires
> the sender to have paused. Fifteen assert/release cycles cannot produce
> 2,399 crossings. **Something responded and the shape of the response is
> not accounted for by any model in this tree.** It is the strongest hint
> that the host obeyed and it is not proof of it.

---

## Leg 4 — the shipping candidate. Leg **DE**. *Only if DB passed.*

```
STEPDE                                  (at A>, CKERMITW --rtscts)
```
```sh
kermit -C "take s16ajDE.ksc, exit" > s16ajDE.host
```

**DB proves the mechanism reaches the far end; this proves that turning it on
changes nothing when it is not needed** — and *this* configuration, not DB's,
is what flipping the default would ship. It is the leg that licenses the
change.

**Pass:** `in=2 out=2 hi=3072`, **`held = 0`** — the 3,072 mark is above every
occupancy this port has ever recorded (`rxpeak` 2,581, §16af) — byte-exact,
`rxlost=0 rxfull=0`, and the leg otherwise indistinguishable from DN.

A `held > 0` here is interesting rather than wrong: it means this cable or
this sitting drove the ring deeper than any before it, and DN's `rxpeak` is
the number to read it against.

> **RESULT — PASS, and it is the leg that says the feature is free.**
> Byte-exact, `in=2 out=2 hi=3072`, `rxlost=0 rxfull=0`, 18 packets, **0
> retransmissions, 0 timeouts**, 37,557 wire bytes — **identical to DA and
> DN on every wire measure** — and **31.143 s against DA's 31.137 s. Six
> milliseconds apart.**
>
> **`held = 1 rel = 1`, and the prediction of `held = 0` was wrong**:
> `rxpeak = 3137`, so this leg drove the ring past 3,072 where DN reached
> 2,990 and DA 2,780. The paragraph above anticipated that and it is the
> right reading — this sitting runs the ring a little deeper than §16af's
> 2,581.
>
> **It does NOT show the host obeying.** `peakat=7676` is **8 bytes into
> seq=08**, i.e. the boundary at the end of the 3,905-byte seq=07 — the same
> kind of place DN and DA peaked. An earlier reading of this leg claimed the
> peak stopped 65 bytes after the mark *in the middle of* a packet and was
> therefore the host pausing. `mapoffset.py` says otherwise. **Ask where the
> peak is before reading it as a cap.**

---

## Leg 5 — XON/XOFF, receive. Leg **DC**.

```
STEPDC                                  (at A>, CKFCLO --xonxoff)
```
```sh
kermit -C "take s16ajDC.ksc, exit" > s16ajDC.host
```

The same reading as DB on the other mechanism. This one matters for
*interoperability* rather than for this cable: the far end's wiring is not
something this port can assume, and XON/XOFF needs three wires.

**`cmp` FIRST.** XON/XOFF is in band, which RTS/CTS is not. `PX_CAU` keeps
DC1 and DC3 prefixed (`ckcmai.c:2699`) and `setprefix()` re-prefixes them
unconditionally when flow is `FLO_XONX` (2705), so a raw DC1/DC3 on the wire
is always a command — **but that is an argument and `cmp` is a
measurement.**

**Pass:** byte-exact; `in=1 out=1 hi=256`; `held/rel > 0` and equal;
`rxpeak` ≈ 256–600 if the host obeyed. `xoff`/`xon` may be non-zero — that is
the host's *own* tty flow control arriving, and under MAME five host START
characters showed up on the equivalent leg.

**And check the reconciliation, because it is the check on a design
decision.** The Victor removes intercepted XON/XOFF from the stream and
deliberately does **not** count them in `rxbytes`, because they are not in
the host's packet log and counting them would shift every `mapoffset.py`
offset after the first. Under MAME with five of them the residual was still
exactly **−11**. If it is not −11 here, that decision is what to look at.

> **RESULT — byte-exact, and the leg that argues for RTS/CTS.** `in=1 out=1
> hi=256`, **`held=20 rel=20`** (equal), `stuck=0`, `xoff=0 xon=0` — the
> host never sent us a flow character.
>
> **`rxlost = 19`, in `evt = 11` bursts, `max = 3`. It is the only leg in
> the sitting with any loss at all, and the first non-zero `rxlost` on this
> bench since §16t.** `losttag = 10` — the foreground was in upstream code
> after `ttol()` returned. 3 Victor NAKs and 3 host retransmissions, 31
> packets, 43,356 wire bytes (+32.3%), 34.916 s / 938 cps — **the slowest
> leg of the seven.**
>
> **Cause not established.** RTS/CTS at the same marks (DB) lost nothing, so
> it is not the water marks and not the ring. The obvious suspect is the
> ISR's XOFF path — it reads RR0 and writes the data register, and when the
> transmitter is busy the single-shot retry re-reads RR0 on **every**
> subsequent byte until it succeeds, and **nothing counts those failed
> attempts.** That is a missing counter, not a diagnosis.
>
> **The residual is −15 where the tool wants −11, and that is explained.**
> `rxbytes` includes one substituted BELL per overrun interrupt, and there
> were 19; `pktstat.py`'s reconciliation does not know about BELL
> substitution. The formula needs an `--rxlost` term for lossy legs.

---

## Leg 6 — the Victor obeying a real XOFF. Leg **DX**. **Host first.**

```sh
kermit -C "take s16ajDX.ksc, exit" > s16ajDX.host   &   # host receives, waits
```
```
STEPDX                                  (at A>, CKERMITW --xonxoff, Victor sends)
```

`cmp gotdx.dat trans.dat`; extract `STEPDX.OUT`.

**No leg in this project has ever had the Victor obey a flow-control
character.** The host runs `set flow xon/xoff`, so its tty sends XOFF when
its input buffer fills; the ISR takes it out of the stream, sets
`v9k_txheld`, and `v9k_ser_put()` stops until the XON.

**Pass:** byte-exact, `stuck = 0`, cps in leg CC's band.
**Read:** `xoff > 0` means we obeyed one. `xoff = 0` means the host never
needed to send one — a null, not a failure, and the leg still says the
interception path did not corrupt anything.
**Watch:** `stuck > 0` means a hold-off outlasted `V9K_FCSPIN`, which is
seconds. With `xoff > xon` that is a lost XON — exactly what
`tcflow(TCOON)` would have recovered if upstream's only call to it were not
inside a `debug()` argument that `NODEBUG` deletes (§16aj).

> **RESULT — PASS on everything it could show, NULL on the thing it was
> for.** Byte-exact (`gotdx.dat`), `in=1 out=1`, **`stuck=0`**, `rxlost=0
> rxfull=0`, 18 packets, 0 retransmissions, 37,557 wire bytes, **22.203 s /
> 1,475 cps — three milliseconds from leg DS.**
>
> **`xoff = 0`: the host never sent one**, so **the Victor obeying a real
> XOFF is still unproven** and stays on §16aj's not-known list. What the leg
> does show is that arming the interception path costs nothing and corrupts
> nothing — 1,475 cps and a byte-exact 32 KB.

---

## After the sitting — **what was decided, 9 August 2026**

**The default was NOT flipped, and the reason is not the one this sheet
expected.** It is not that RTS/CTS looks unsafe — DS and DE say the
opposite, and say it with the two tightest null pairs this project has
produced (6 ms and 3 ms). It is that **DB, the one leg that could show the
far end responding, went off-shape and its `rxpeak` is unusable.** Shipping
a default whose *efficacy* has never been measured is exactly what this
project does not do.

Splitting the question, because the sitting split it cleanly:

| | question | answer |
|---|---|---|
| **safe?** | does the CTS gate wedge the transmitter? does turning it on cost anything? | **No, and no.** DS 1,475 cps byte-exact with `stuck=0`; DE byte-identical to its control on every wire measure and **6 ms** apart |
| **effective?** | does the far end stop when we drop RTS? | **Unresolved.** DB's `rxpeak` was latched in a resend. `stall256` 47 → 2,399 says *something* responded; nothing says what |

### Two legs would finish this, and both binaries are already on the image

1. **`CKPRE` against `CKERMITW`, adjacent, 38400 receive — the control this
   sheet should have had.** `CKPRE.EXE` (205,228, md5 `537486a8…`, HEAD
   before §1f) is still on the image from §16aj's MAME work. This sitting's
   three clean receive legs came in at **31.137 / 31.143 / 31.535 s on
   37,557 wire bytes**, where §16ah leg BC did the identical 37,557 in
   **28.057 s**. That is **+11%**, three times this sitting's own ~0.4 s
   spread — but it is a *cross-sitting* comparison, which §16aj itself says
   not to make. **So §1f may cost 11% of a 38400 receive, or nothing, and
   this sheet cannot tell you which.** One adjacent pair settles it.
2. **Re-run DA/DB with a gentler mark — `-dV9K_RXHIGH=1024 -dV9K_RXLOW=512`.**
   256 was too aggressive: it pauses the sender often enough and long enough
   to trip the protocol, which is what produced the timeout that voided the
   leg. 1,024 is still far below the natural peak (2,780–3,137 this sitting),
   so it will fire several times per leg, while leaving the sender enough rope
   not to time out. Read `rxpeak` **and** `mapoffset.py` on `peakat` — a peak
   inside a resend means the leg did not answer.

### One instrument gap and one tool gap, both found by running this

- **Nothing counts a FAILED XOFF attempt.** The single-shot assert re-reads
  RR0 on every byte until the transmitter is free, and that retry is
  invisible. It is the leading suspect for leg DC's 19 overruns and it
  cannot be confirmed or cleared without a counter.
- **`pktstat.py`'s reconciliation has no term for BELL substitution.** DC's
  residual came out −15 where the formula wants −11, and the difference is
  the 19 BELLs the ISR put in the stream for 19 overruns. It needs
  `--rxlost`.

### What this sitting cannot settle

- **Whether an arbitrary far end obeys.** These legs measure one host, one
  cable, one FTDI adapter. That is what "interoperability requirement"
  means and it is why both mechanisms ship.
- **Whether the Victor obeys a real XOFF.** Leg DX armed the path and the
  host never sent one — `xoff = 0`. A null, not a failure.
- **The assert path under ring overflow.** `v9k_ringfull` re-enters the
  water-mark check with occupancy forced to the mask, and nothing has
  executed it. `rxfull` was 0 on all seven legs.
- **The `stuck` backstop.** 0 on every leg; no leg was designed to produce
  a hold-off lasting seconds.
- **Why leg DC lost 19 bytes.** First non-zero `rxlost` on this bench since
  §16t, on the only XON/XOFF receive leg, with RTS/CTS at the same marks
  losing nothing.

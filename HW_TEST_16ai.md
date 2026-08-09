# Bench run sheet — the prefixing fix, the parser build, and server mode

**This document is the thing to work from. Follow it top to bottom.** That
sentence is inherited from `HW_TEST_16ag.md` and it is still earning its
place: §16af lost a whole session's host timings to a run sheet that existed
and was never handed over as one, and §16ae lost the same figure before it.

**Nothing below needs building, writing, or staging.** Both binaries are
compiled, staged and round-trip verified out of the image; five `.BAT`s are
on the image and verified CRLF **after** landing there; five take-files are
in the tree; the fixtures exist and the target names are checked clear.
§0 is a receipt, not a list of chores.

Written 9 August 2026, after PORTING.md §16ah. **The headline changed at the
desk before this sheet was written**, and §1 is that change.

> **RUN THE SAME DAY. All seven legs passed, every transferred file
> byte-exact, `rxlost = 0 rxfull = 0` throughout.** Results are recorded
> inline against each leg and written up in PORTING.md **§16ai**. Two things
> were done for the first time — a transfer on the parser build, and server
> mode on real hardware — and the prefixing fix landed within a byte of
> prediction.
>
> **Both failures in the sitting were this document's, not the port's**, and
> the fixes are in the two boxes under "Before every leg". If you are
> re-running, read those first.

---

## What moved since §16ah, and read this before §1

**`NEXT_SESSION.md` §1 item 5a is superseded.** It said: run a Victor send
with `cautious` prefixing, because §16ah leg BS measured the Victor
expanding 32,768 bytes by +24.3% where the host's `cautious` expanded the
same payload by +9.7%, and that looked like the wrong policy.

**The Victor was never running `cautious`.** `ckvictor.h` has selected
`PX_CAU` since §16ae and every leg this project has ever run sent `PX_ALL`.
`main()` reaches

```
ckcmai.c:3295   initproto(PROTO_K, ...)
                  -> if (ptab[protocol].prefix > -1)
                         prefixing = ptab[protocol].prefix;
ckcmai.c:3413   setprefix(prefixing)
```

and `ptab[PROTO_K].prefix` is statically `PX_ALL` (`ckcmai.c:719`, the
`#else` of `NEWDEFAULTS`, which this build does not define). `PX_ALL` is 0,
so the `> -1` test passes and `initproto` **overwrites** whatever the XI
initializer put in `prefixing` — 118 lines before anything reads it.
Upstream knows this about its own ordering: the comment at `ckcmai.c:3319`
says `compat_9()`/`compat_10()` run *"after initproto calls so initial file
transfer settings are not overwritten."* An XI record runs before `main()`,
which is the one position from which that guarantee does not hold.

**How it was found is the part worth keeping.** Not by reading the source —
the source had been read twice and produced the comment the fix replaces —
but by decoding the prefix characters out of `s16ahBS.pkt`. A run's `ctlp[]`
table is recoverable from the wire, because every value the sender prefixed
appears after a QCTL. Leg BS prefixed **exactly the 66 values `setprefix()`
sets for `PX_ALL`**; the host, over the identical fixture in the same
session, prefixed **exactly the 32 it sets for `PX_CAU`**. 8,869 prefix
characters against 4,512, and that 4,357 difference is the whole of the send
leg's wire-byte excess. **A setting that is applied and then quietly
overwritten looks exactly like a setting that was never right; only the wire
tells them apart.**

`v9k/tools/pktstat.py` now does this in one command, and it also reads send
legs correctly, which it did not before.

**Two published figures are withdrawn.** §16ah's send/receive table gives
40,726 and 35,950 wire bytes, +24.3% and +9.7%. Counted from the logs —
against the Victor's own `rxbytes` counter, which agrees to the byte on leg
BC — they are **41,945 (+28.0%)** and **37,585 (+14.7%)**. The 14.7% figure
is what the rest of the project already quotes for this fixture
(`NEXT_SESSION.md` §1 item 9), so §16ah's table was the outlier. The
*conclusion* survives unchanged and is now correctly attributed: it is
`PX_ALL` measured against `PX_CAU`, not two ends disagreeing about one
policy.

---

## 0. Staging — **already done. This section is a receipt, not a task.**

Image is `~/projects/mame/victor_kermit.img`, the same file the Pico SASI
serves and MAME boots. Backup taken before any of this:
`victor_kermit.img.bak-20260809-preicp`.

| on the image | bytes | md5 | what it is |
|---|---:|---|---|
| `CKERMITW.EXE` | 205,228 | `537486a8…` | **the shipping build, with the prefixing fix.** Legs CC, CE, CS |
| `CKPXALL.EXE` | 205,228 | `ddb93453…` | `-dV9K_PREFIXING=PX_ALL`. **The control for CC.** Leg CD |
| `CKICP.EXE` | 435,154 | `f5456cae…` | `KEEP_ICP`, **rebuilt 9 Aug**. Legs CF, CH |
| `CKICPD.EXE` | 546,422 | `6d991fc7…` | `KEEP_ICP` + `KEEP_DEBUG`, **rebuilt 9 Aug**. Leg CG |

**`CKICP`/`CKICPD` were the stale ones and are not any more.** The copies
that had been on the image since 8 August 12:32 predated upstream edits 16
and **17**, and edit 17 is a trap rather than an inconvenience: without it
`chk3()` computes the CRC in `long` through two `long[16]` tables, which at
38400 with block check 3 pinned `rxpeak` at 4,095 of 4,096 and lost 556–649
bytes on three legs of four (§16af). Leg CH below is a 38400 transfer. Run
it against the old binary and you reproduce that ring defect and read it as
*"the parser build breaks transfers"* — a wrong conclusion that would look
thoroughly convincing, because `rxfull` would be non-zero and the resends
real.

**`CKPXALL` is an unusually good control and it is worth knowing why.** It is
the same tree, the same commit and the same flags as `CKERMITW`, differing
only in the immediate constant the prefixing initializer stores. Both are
**205,228 bytes**. `wdis` shows the entire difference:

```
CKERMITW    mov  word ptr _ptab+0cH,1        ; PX_CAU
CKPXALL     xor  ax,ax / mov ..., ax         ; PX_ALL
```

So §16w's finding that this machine is sensitive to code size has **no
purchase here** — the layouts are identical. §16af had to spend a whole null
leg establishing that for a change that did alter code size; this one gets
it for nothing.

**Staged and verified CRLF *after* landing on the image:** `STEPCC`
`STEPCD` `STEPCE` `STEPCH` `STEPCS`. Already there from earlier sections and
reused unchanged: `STEPSPD.BAT`, `RXEA.KSC`, `PTEST.KSC`, `SPDTEST.KSC`,
`TRANS.DAT` (32,768 bytes).

**Checked, so you do not have to:** no `RCVCE.DAT`, `RCVCH.DAT`, `RCVCS.DAT`,
`STEPC*.OUT` or `DEBUG.LOG` on the image, so nothing will trip `SET FILE
COLLISION` `BACKUP` — which cannot work on FAT, and whose symptom is S, F,
A, then **Z with data `D`** and no data packets. No stale `got*.dat` on the
host. 2.0 MB free on the image.

**The one thing that is yours:** check `~/.kermrc` names the adapter actually
plugged in. §16v used `BG022B8M`, §16af used `ABBFKXM1`. The take-files
deliberately do **not** set the line, so this is the single place the device
name lives.

**To rebuild anything** (you should not need to):

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak clean && make -f victorow.mak"
# -> ckermitw.exe, 205,228, md5 537486a8…

container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak clean && \
   make -f victorow.mak XFLAGS=-dV9K_PREFIXING=PX_ALL"
# -> ckermitw.exe, 205,228, md5 ddb93453…   (copy aside as ckpxall.exe)

container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak clean && \
   make -f victorow.mak XFLAGS=-dKEEP_ICP ZT=-zt2048"
# -> ckermitw.exe, 435,154, md5 f5456cae…   (copy aside as ckicp.exe)
```

---

## Before every leg

> **RUN 9 August 2026. All seven legs done, every file byte-exact.** Results
> are in PORTING.md §16ai. **Two defects in this sheet were found by running
> it and are fixed below** — read the next two boxes before re-running
> anything, because both of them made a working port look broken.

> ### ⏱ THE MACHINE TAKES 40–85 SECONDS TO START. WAIT FOR IT.
>
> `CKERMITW` is 205 KB and `CKICP` is 435 KB, and the Victor reads the whole
> image off SASI before `main()` runs: **about 40 s** for the shipping build,
> **about 85 s** for the parser build. On any leg where the **host** sends
> first, starting it too soon exhausts `MAXTRY` (10, `ckcker.h:472`) against a
> Victor that has not reached `receive` yet — and **a host that gives up looks
> exactly like a Victor that failed.** Leg CE's timeout and leg CH's first
> attempt were both this.
>
> **Start the Victor, wait for the drive to go quiet, then start the host.**
> The host take-files now also carry `set retry 30`, which is the belt to that
> braces — but patience in the host does not help if you cannot see what the
> machine is doing, which is the next box.

> ### 👁 THE REDIRECT HIDES EVERYTHING, INCLUDING QUESTIONS
>
> `> STEP<LEG>.OUT` is required — the `v9k:` counters only reach stdout — but
> it also swallows the transfer display **and any prompt**. A parser build
> asks two questions on the receive path:
>
> ```
>  Accept incoming file "A:/rcvch.dat"?
>  OK to exit?
> ```
>
> Redirected, both sit unanswered forever and the leg looks like a hang. That
> is what happened to CH. `RXEA.KSC` now carries **`set receive confirm off`**
> and **`set exit warning off`**, which is the right layer to fix it at: the
> prompts are correct behaviour for an interactive build, and it is the
> redirect that makes them fatal.
>
> **Why the shipping build never does this**, so the asymmetry is not a
> surprise: `fnrconfirm` is `CONFIRM_ON` *by default* (`ckcmai.c:1408`), scope
> `LOCAL`, and a Victor driving its own line is local — so
> `rq_confirm_check()` reaches the prompt on **every** receive. `NOICP` builds
> survive only because `ckvictor.c` supplies a `getyesno()` that returns yes.
> In a `KEEP_ICP` build the linker keeps *upstream's* and discards ours
> (`W1027`, decided by link order).
>
> **If a leg seems to hang, run the Victor side by hand without the redirect
> before concluding anything.** That is how CH was diagnosed, and the result
> was a completely successful transfer sitting behind an unanswered question.

**Three files per leg. A leg missing any of them is a leg to re-run** — with
one judgement call the 9 August sitting had to make and got right. Leg CH was
run by hand after the scripted attempt hung, so its `STEPCH.OUT` is 0 bytes
and its `v9k:` counters exist as a **photograph of the screen**, transcribed
into §16ai. That is a weaker artefact than a file, but it is legible, it was
read, and the leg's actual question — did the wire protocol move — is
answered by the md5 and `rxlost`/`rxfull`, which are not in doubt. **Do not
re-run a leg whose result you already have just to improve the format of the
evidence.** The rule is about missing *results*, not missing *files*.

| file | where it comes from | why |
|---|---|---|
| `s16ai<LEG>.host` | `kermit -C "take …, exit" > s16ai<LEG>.host` | the millisecond clock. **Capture it even on the counting legs** — it is what distinguishes "the difference is below the noise" from "we cannot see the difference" |
| `s16ai<LEG>.pkt` | `log packets`, already in each take-file | packets, wire bytes, prefixes, retransmissions — all of it now via `pktstat.py` |
| `s16ai<LEG>.OUT` | `> STEP<LEG>.OUT` on the Victor, then extract | the `v9k:` counters |

Plus the transferred file, `cmp`'d against the fixture.

- Power-cycle the Victor **and** the Pico between runs.
- Delete a stale `X.LOG` before `REN DEBUG.LOG X.LOG` — the `REN` fails
  silently and leaves the old log beside a fresh `.OUT`.

**Read every packet log the same way:**

```sh
python3 v9k/tools/pktstat.py s16ai<LEG>.pkt
python3 v9k/tools/pktstat.py --rxbytes <from the .OUT> s16ai<LEG>.pkt   # receive legs
```

The reconciliation is a check neither end can do alone:
`host wire bytes − rxbytes = rxfull + startup offset`, and the offset is
**−11** on a leg with no startup timeout or **+28** on one with. Anything
else means the log and the Victor did not see the same transfer, and the
tool says so in those words.

---

## Leg 1 — the prefixing fix. Legs **CC** and **CD**. **Do this first.**

**Both are send legs, so the host is the receiver and you start the host
FIRST.** The Victor is the initiator here and will give up if nothing
answers its S packets.

```sh
kermit -C "take s16aiCC.ksc, exit" > s16aiCC.host   &   # host receives, waits
```
```
STEPCC                                  (at A>, CKERMITW, PX_CAU)
```

then

```sh
kermit -C "take s16aiCD.ksc, exit" > s16aiCD.host   &
```
```
STEPCD                                  (at A>, CKPXALL, PX_ALL — the control)
```

`cmp gotcc.dat trans.dat` and `cmp gotcd.dat trans.dat`; extract
`STEPCC.OUT` and `STEPCD.OUT`.

**This is a COUNTING leg, not a timing one, and that is the only thing that
makes it answerable at all.** The effect is ~4,400 wire bytes, which is
~1.1 s of line time at 38400 — **below the bench's ~1.3 s noise floor**
(§16ah legs BC and BD: one binary, both clean, eleven wire bytes apart, and
**1.277 s apart**). The clock cannot resolve this and more legs will not
change that. Wire bytes and prefix characters are counted, exactly and
deterministically.

**The pass condition is one line of output:**

```
python3 v9k/tools/pktstat.py s16aiCC.pkt s16aiCD.pkt
```

| | CC (`PX_CAU`) | CD (`PX_ALL`, control) |
|---|---|---|
| `prefixing policy` | **`PX_CAU exactly (32 values)`** | `PX_ALL exactly (66 values)` |
| `prefixes ctl` | ~4,512 | ~8,869 |
| `WIRE BYTES` | ~37,5xx | ~41,945 |

> **RESULT, 9 August 2026 — PASS, and predicted to the byte.** CC came back
> `PX_CAU exactly (32 values)`, **4,512** prefixes, **37,557** wire bytes,
> +14.6%, 18 packets. CD came back `PX_ALL exactly (66 values)`, **8,869**,
> **41,945**, +28.0%, 19 packets. Both byte-exact. **Saving: 4,388 wire
> bytes, −10.5%.**
>
> **The null leg is the best this project has produced.** CD reproduces
> §16ah leg BS on every measure — prefixes, wire bytes, packet count, and
> `rxbytes = 216` — and the host clocks are **29 ms apart** (23.604 against
> 23.633) on a bench whose spread is 1.3 s.
>
> Host clocks: CC **22.207 s / 1,475 cps**, CD 23.604 s / 1,388. **1,475 is
> the fastest figure this port has produced**, but the two legs are 1.397 s
> apart against a ~1.3 s floor — **quote the wire-byte count as the result
> and the cps as an illustration.** And note CC's 37,557 is *identical* to
> leg BC's host-sent figure: same policy, same data, opposite directions,
> same count.

**CD must reproduce §16ah leg BS**, which ran a different binary but the same
effective policy — 8,869 prefixes, 41,945 wire bytes, `PX_ALL exactly`. A CD
that does not means something *other* than prefixing moved between the two
binaries, and **CC is then not attributable either**. That is §16af's
null-leg discipline: spend a leg on the result that is supposed to be
nothing.

**Byte-exactness is not a formality on this leg.** `PX_CAU` puts control
characters on the wire raw — that is the entire point of it and also the only
way it can go wrong. XON/XOFF stay prefixed under `PX_CAU` regardless
(`ckcmai.c:2731`), so flow control is not the exposure; a driver or cable
eating a raw control character would be. **A CC that is fast and wrong is the
failure mode to watch for**, which is why `cmp` comes before the counts.

---

## Leg 2 — the null leg. Leg **CE**.

```
STEPCE                                  (at A>, Victor receives)
```
```sh
kermit -C "take s16aiCE.ksc, exit" > s16aiCE.host
```

Extract `STEPCE.OUT` and `RCVCE.DAT`; `cmp` against `rcvce.dat`.

**Prefixing is a sender-side decision** — `ctlp[]` is read only by
`bgetpkt()` and `getpkt()`, the packet *builders* (§16ae) — so a change to
the Victor's prefixing has **no mechanism** by which it can affect a Victor
receive. This leg is here to check that claim rather than to assert it, and
to confirm the shipping binary did not otherwise move.

**Pass is §16ah leg BC/BD's shape:** `rxlost=0 rxfull=0`, `rxpeak` in
2,4xx–2,6xx of 4,096, 18 packets, 0 retransmissions, 0 timeouts, `rxbytes`
~37,55x, byte-exact.

**Do not read a cps difference against BC or BD.** Those two legs are 1.277 s
apart from each other on one binary. Anything CE does inside ~1.3 s is the
bench, not the change.

> **RESULT — PASS on the counters, off-shape on the clock.** Byte-exact,
> `rxlost = 0 rxfull = 0 rxpeak = 2,478 of 4,096`. But 1 timeout and 2
> retransmissions, 40,544 wire bytes against the clean 37,55x, 30.756 s and
> 1,065 cps — **the startup race, not the change**; the host was started
> before the Victor had finished loading. The null result stands: prefixing
> is sender-side and a Victor receive is untouched.
>
> **Its reconciliation is exact and worth keeping.**
> `pktstat.py --rxbytes 40544 s16aiCE.pkt` gives a residual of **+0** with
> `rxfull = 0` — two independent counts of the same 40,544 bytes agreeing to
> the byte, on a leg that retransmitted twice.

---

## Leg 3 — the parser build. Legs **CF**, **CG**, **CH**.

**§16ad ran the whole interactive sequence under MAME, so CF and CG are
confirmation rather than discovery. CH is discovery: no transfer has ever
been run with the parser build.**

**CF — the prompt.** Type `CKICP` and expect `C-Kermit>`.

1. `show versions` — proves the parser reads a line, looks up a keyword and
   runs a command. **Console input has never been exercised on hardware in
   this port**: every `NOICP` build only ever *wrote* to the console, so
   `coninc()`/`congks()` through INT 21h AH=07h are new ground. If anything
   fails, it is more likely this than the parser.
2. **Watch the echo.** The prompt should echo a typed line **exactly once**.
   Two copies, the second overprinting from column 0, is §16ab's defect —
   DOS's cooked line input echoing as you type and C-Kermit echoing the
   buffered line again. Fixed in §16ac and confirmed under MAME in §16ad,
   but **the pre-fix binary has never been under MAME**, so §16ad shows the
   fix behaving correctly rather than the bug reproducing and going away.
   The machine is the first place both halves are visible.
3. `take ptest.ksc` — a **diagnostic, not just a feature**. Interactive
   `TAKE` goes through `cmifip()` (`ckuusr.c` ~10590), a *different* path
   from the command-line `argv[1]` route (`prescan()` → `findinpath()`,
   `ckuus4.c:1741`) that edit 14 repaired. So: it works → any residue is
   isolated to `findinpath()`/`prescan()`; it fails the same way → the
   problem is lower down, in `zopeni()` or `access()` on a FAT root, and
   `ckvictor.c` §1d is where to look.
4. `CKICP PTEST.KSC` from the DOS prompt, as the control for step 3.
5. `exit`.

**Extended keys are a "do not be surprised" note.** The console reads INT 21h
AH=07h; whether the Victor's keyboard driver uses the 0-then-scan-code
convention is unknown, so a function or arrow key may deliver a stray NUL.
Nothing in this build wants arrow keys.

**CG — the speed regression.**

```
STEPSPD                                 (at A>)
REN DEBUG.LOG SPDCG.LOG                 (at A>, after Kermit exits)
```

Expect, from §16ad under MAME: `SET LINE` reports **local**; `SET SPEED
38400` and `19200` both **read back**, with `tcsetattr divisor=` 2 and 4;
`SHOW VERSIONS` names the machine. **`SET SPEED` reading back at all is
upstream edit 15** — `ckuus5.c:1262` cast before dividing, so `(int)38400L`
came out −27136 and every speed above 32767 was silently rejected. This is
the only place that edit is reachable; `-b` divides as a `long`
(`ckuusy.c:4164`), which is why every 38400 figure this port has published is
sound regardless.

**CH — the first transfer on the parser build.**

```
STEPCH                                  (at A>, CKICP RXEA.KSC)
```
```sh
kermit -C "take s16aiCH.ksc, exit" > s16aiCH.host
```

`cmp` `RCVCH.DAT` against `rcvch.dat`; extract `STEPCH.OUT`.

**What it is asking.** Edit 14 widened what `main()` compiles — it moved a
mis-nested `#endif`, and it is the one edit in this port that is **not** a
no-op elsewhere — so the parser binary is not the binary any throughput
figure in this project was measured on. `dofast()` is inside the widened
region and is guarded out on purpose (§8 item 14), because it sets
`wslotr = RBSIZ/MAXSP = 2` and would have opened the window to two,
unmeasured, on a port with no flow control and a **105-byte** ring margin.
**A byte-exact md5 with `rxlost=0 rxfull=0` is what says the wire protocol
did not move.** Throughput is secondary and the parser build has 6,512 bytes
of near heap against the shipping build's 17,232, so do not be surprised by
a slower number.

> **RESULT — PASS. This leg is DONE and does not need re-running.** The
> scripted attempt hung on an unanswered prompt; run by hand, with a human
> answering it, the transfer completed. `RXEA.KSC` was fixed *afterwards* so
> that a future run of this leg does not need the human — **the fix is not a
> precondition of the result above, and re-running CH would test the
> take-file, not the port.** If someone is at the machine anyway it costs one
> leg to confirm the take-file works unattended and to get the counters into
> a file instead of a photograph; neither is worth a trip.
>
> By hand it transferred **32,768 bytes at 38400, byte-exact,
> `rxlost = 0 rxfull = 0 rxpeak = 2,852 of 4,096`, 1,213 cps** — inside the
> shipping build's 1,167–1,475 band, so no difference to read.
>
> **Ignore this leg's `elapsed=11300 cs`.** The Victor's clock starts at the
> first byte received and closes at release (§16u); it counted the time the
> machine spent at an unanswered prompt. The host's 27 s is the figure. **A
> clock that measures an interval cannot tell a slow line from a stopped
> operator.**

Note `CKICP.EXE` needs **429,890 (419K)** at load — **smallest Victor 512K**,
with 1,678 bytes spare on that machine. `CKICPD.EXE` needs **533,110
(520K)**, smallest Victor **640K**. Both re-measured 9 August; the 532,904
figure in older notes was the 8 August build.

---

## Leg 4 — server mode. Leg **CS**. `HW_TESTING.md` leg 0.7, untouched.

```
STEPCS                                  (at A>, CKERMITW -x, the Victor waits)
```
```sh
kermit -C "take s16aiCS.ksc, exit" > s16aiCS.host
```

The take-file does `send` → `get` → `finish`, with `statistics` after each
transfer. `cmp` `gotcs.dat` against `rcvcs.dat`.

**An E packet in reply to a well-formed command is a specific signature, not
a generic failure.** C-Kermit 11 initialises every `en_*` capability to
"remote mode only", and a Victor that owns its serial line is by definition
*local*, so a `-x` server ACKs the negotiation and then refuses everything.
`NOICP` removes the prompt where you would type `ENABLE GET`. `ckvictor.c`
settles the capability set from a priority-0 XI initializer instead — **and
that is the same initializer mechanism §1 just found being overwritten
elsewhere**, so this leg is now also a check on the mechanism itself, by a
different route. `CKERMITW -d -h` reports `v9k srvcaps safe=` through
`uname()` if it needs isolating.

**Not included, deliberately.** `REMOTE DIRECTORY` streams its listing and
never terminates it (§16i, still open) — it will hang and take the leg with
it. And `BYE` is not sent: it has never been sent in this port's life, and a
leg that ends by shutting the far end down cannot be retried without a power
cycle. `FINISH` leaves the Victor at the DOS prompt with its exit report
written, which is the point of running it.

> **RESULT — PASS, and it is a first: server mode has never run on the
> machine.** SEND to the server **1,058 cps**, GET from the server **1,431
> cps**, then FINISH; both `SUCCESS`, both byte-exact, `rxlost = 0
> rxfull = 0 rxpeak = 2,332`. **No E packet**, so §16i's priority-0
> capability initializer works on hardware — a second, independent check on
> the XI mechanism that leg CC's defect was found in. `HW_TESTING.md` leg 0.7
> is closed. `REMOTE DIRECTORY` and `BYE` remain untested by choice.

`--safe-server` (GET, SEND and FINISH only) is a second run of the same leg
if CS passes; per §16i, **run the unknown-option control too** — under
`NOICP` any `--` argument is `XFATAL("Extended options not configured")`, and
without the control "no error" cannot be told from "silently ignored".

---

## What none of these legs covers

- **Splitting the foreground bucket.** 17.7 s of leg AG is one subtraction —
  elapsed minus line minus `wfile` minus `txgap` — so nothing separates
  per-byte decode from per-packet fixed cost, and the two have completely
  different fixes. `NEXT_SESSION.md` §1 item 9. It needs a counter first.
- **Why the bench does not repeat.** §1 item 5b, and it is the fact that
  governs every A/B on this machine. Unchanged.
- **A text fixture.** Every measurement this port has is on adversarial data:
  the 32,768-byte fixture holds every byte value. §1 item 9. **Leg CC makes
  this more interesting, not less** — `PX_CAU` on ordinary ASCII should cost
  almost nothing over `PX_NON`, because there are few control characters to
  unprefix in the first place.
- **Flow control** (§1 item 11) and **windowing** (item 12), both untouched.

---

## Artefact checklist

| leg | take-file | `.BAT` | fixture | writes | binary |
|---|---|---|---|---|---|
| **CC** | `s16aiCC.ksc` | `STEPCC.BAT` | image `TRANS.DAT` | host `gotcc.dat` | `CKERMITW` |
| **CD** | `s16aiCD.ksc` | `STEPCD.BAT` | image `TRANS.DAT` | host `gotcd.dat` | **`CKPXALL`** |
| **CE** | `s16aiCE.ksc` | `STEPCE.BAT` | `rcvce.dat` | `RCVCE.DAT` | `CKERMITW` |
| CF | — (interactive) | — (type `CKICP`) | `PTEST.KSC` | — | `CKICP` |
| CG | — | `STEPSPD.BAT` | `SPDTEST.KSC` | `SPDCG.LOG` | `CKICPD` |
| CH | `s16aiCH.ksc` | `STEPCH.BAT` | `rcvch.dat` + `RXEA.KSC` | `RCVCH.DAT` | `CKICP` |
| CS | `s16aiCS.ksc` | `STEPCS.BAT` | `rcvcs.dat` | `RCVCS.DAT`, host `gotcs.dat` | `CKERMITW` |

Every `rcv*.dat` fixture and `TRANS.DAT` is the 32,768-byte all-byte-values
file, md5 `d94d2beda069ef0ef340977e7fd6995d`.

**Priority if the sitting is short: CC, CD, CE.** Those three settle a
shipping-behaviour change that is currently in the tree unverified on the
wire. CF–CH and CS are confirmation runs of things that already work
somewhere else.

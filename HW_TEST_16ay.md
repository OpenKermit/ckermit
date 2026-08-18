# §16ay — post-merge regression: C-Kermit 11.0.508 under MAME

**17 August 2026, no Victor in reach.** PR #3 merged 77 upstream commits
(11.0.508 plus the unreleased 11.0.509 work) into the port branch. This sheet
is the regression that says the port still works, and it is a *regression*
rather than an investigation: every leg reproduces a result some earlier
section already established, so a difference is a defect and not a discovery.

## §0 — preconditions, checked before any leg ran

Both of the traps that cost §16al a whole sitting are checked here, and so is
the one §16av added.

| check | answer |
|---|---|
| `vtg_image_util info` — free space on partition 0 | 416 KB (4.2%) **before**, 592 KB after staging; 29 stale 32 KB `RCV*.DAT` deleted to make room (all were documented copies of `TRANS.DAT`) |
| image backed up | `victor_kermit.img.bak-20260817-premerge-regress` |
| every leg's target name fresh | `RCVUA.DAT`, `SNDUB.DAT`, `STEPU?.OUT`, `s16ayU?.*` — none used before |
| every receive `.BAT` opens with `IF EXIST <target> DEL <target>` | yes, all four |
| `.BAT` files CRLF **after** landing on the image | round-tripped and verified |
| staged binary md5 round-trips off the image | `d76c10b2…`, both directions |
| the `-d` guard (§16aw) | every leg must report `deb=0`; no leg uses `-d` |

## The two builds under test

Both from HEAD (`8de15c7`), Open Watcom V2, large model.

| | file | DGROUP | needs at load | smallest Victor | md5 |
|---|---:|---:|---:|---|---|
| shipping (`CKMRG.EXE`) | 230,756 | 48,896 (74%) | 242,852 (237K) | **384K** | `d76c10b2…` |
| parser, `KEEP_ICP ZT=-zt2048` (`CKMRGI.EXE`) | 460,082 | 59,632 (90%) | 453,602 (442K) | **640K** | `66bdfe65…` |

Warnings: **18**, all in stock upstream code and all pre-existing; `ckvictor.c`
and `ckvisr.asm` **0**. `make -C v9k/proofs` — vcrc16, vburst, vttinl and
vwindow all pass.

**The parser build's requirement moved a machine class**: 429,890 (419K,
smallest Victor 512K) at §16ax, 453,602 (442K, 640K) now. The shipping build
did not move a class — 242,786 → 242,852, +66 bytes, still 384K.

## The legs

All four at 9600 under MAME on Victor MS-DOS 3.1, `socat` first, MAME second,
host `kermit` at t+110 s (t+25 s for UB, where the host is the receiver and
has to be waiting).

| leg | what it reproduces | what would count as a regression |
|---|---|---|
| UA | 32 KB receive — edits 11, 17, 18 all live on this path | anything but byte-exact, or `rxlost`/`rxfull` non-zero |
| UB | 32,768-byte send **by name** — upstream edit 16's exact range | `-s` refusing the file, or a non-md5-identical arrival |
| UC | server sweep: REMOTE HELP, PWD, SPACE (edit 20), DIRECTORY (edit 19 dates), TYPE, GET, full-root DIRECTORY, FINISH | a 1970 date, `Can't check space`, or a wedge |
| UD | parser build running `SPDTEST.KSC` **by absolute path** — edits 12, 13, 14, 15 | no `SHOW VERSIONS` output, `mode: remote` after `SET LINE`, or a speed that does not read back |

---

## Results

### Leg UA — 32 KB receive at 9600: PASS

`RCVUA.DAT` is **md5-identical** to `TRANS.DAT` (`d94d2beda069ef0ef340977e7fd6995d`).
Host: SUCCESS, 4 timeouts, 7 retransmissions, 80.768 s, 405 cps, 39,783 wire
bytes (+21.4%, `PX_CAU` exactly — the host's own prefixing, §16ae).

Victor counters, and every one of them reproduces a documented figure:

```
v9k: isr=asm deb=0
v9k: rxlost=0 rxfull=0 rxpeak=306 of 4096
v9k: bulk sel=1 n=14022
v9k: wfile n=4 max=50 at #1 of 8192 tot=150 cs nospc=0
v9k: nap per=409 n=1 req=500 ms tot=50 cs cc=0
v9k: coll=1
v9k: window ask=0 use=0 neg=1 pool=2 ring=1
v9k: elapsed=10400 cs wire=382 B/s
```

| counter | this leg | precedent |
|---|---:|---|
| `rxpeak` | 306 of 4096 | 309 at 9600, §16n; 305 §16ar |
| `bulk sel=1 n=` | 14,022 | edit 18's arm ran — §16aq's "read the counter before the clock" |
| `wfile n=` | 4 writes | 4, §16n (`V9K_OBUFSIZE` 8192) |
| `nap per=` | 409 | 409 on all five §16av legs |
| `coll=` | 1 | REPLACE, §16av |
| `neg=` | 1 | window 1, §16ar |
| `deb=` | 0 | §16aw's guard: no leg carried `-d` |

**The clock is not comparable and the reason is in the packet log**, not in the
build: the host was started at t+110 s and reached its F packet before the
Victor was listening, so three of the four timeouts and four of the seven
retransmissions are the S/F/A exchange at the start. Leg UE re-runs the same
transfer with the host started late, for a figure that can be set beside
§16n's 633 cps.

### Leg UB — 32,768-byte send BY NAME at 9600: PASS, and it re-closes edit 16

`gotub.dat` is **md5-identical** to `TRANS.DAT`. Host: SUCCESS, **0 timeouts,
0 retransmissions, 49.354 s, 663 cps**. The two `<timeout>` lines at the head
of `s16ayUB.pkt` are the host receiver NAKing while the Victor was still
booting — expected, and outside the transfer.

`-s SNDUB.DAT` on a file of **exactly 32,768 bytes** is upstream edit 16's
range, and it neither refused the file nor printed the empty-`errno` message
that was the old bug's tell. This is the second end-to-end confirmation of
edit 16 (§16ah leg BS was the first, at 38400 on the bench) and the first
under MAME.

```
v9k: rxlost=0 rxfull=0 rxpeak=52 of 4096      (the ACK stream)
v9k: bulk sel=1 n=18                          (one per ACK read)
v9k: txgap n=18 max=50 at #5 tot=100 cs       (18 data packets)
v9k: wfile n=0 ... nospc=0                    (send leg: no writes)
```

**663 cps is the fastest 9600 figure this port has recorded in either
direction** (§16n's receive was 633, §16u's 632), which is consistent with
§16ah's finding that sending beats receiving — and the send arm is inert for
edit 18 (`bulk n=18`, ~11 bytes a call), so the merge has not moved it.

### Leg UC — server capability sweep: PASS, including both of §16ax's edits

**0 timeouts, 0 retransmissions**, 32.076 s, and `rxlost=0 rxfull=0
rxpeak=49`. Eight commands, every one answered.

- **`REMOTE HELP` first**, as §16ax's rule requires — and it is also how this
  leg identifies the build on the machine: the header reads
  **`C-Kermit 11.0.508, 2026/08/09, Victor 9000 / Sirius 1`**. The
  capability table is exactly §16ax's: WHO **Disabled** (§16ax zeroed it),
  MAIL/HOST/PRINT Disabled, ASSIGN/QUERY "not configured", everything else
  Enabled.
- **`REMOTE SPACE` → `Free space: 536K`** — **upstream edit 20 works after
  the merge.** `vtg_image_util info` says 592 KB free before the leg wrote
  its two output files, so the INT 21h `AH=36h` answer is the volume's.
- **`REMOTE DIRECTORY SRVA.TXT` → `187  2026-08-16 22:02:02`** — **upstream
  edit 19 works**; no 1970.
- **`GET SRVA.TXT`** landed as `SRVA.TXT.~3~`, **md5-identical** to §16ax's
  `~2~` and to the tree's `SRVA.TXT` (`225c084e…`), **dated Aug 16 22:02** —
  so edit 19 is intact on the file-date *attribute* path as well as in the
  listing.
- **`REMOTE DIRECTORY`, full root: 162 files, 1 directory, 8,312,507 bytes,
  a summary line, and no 1970 date anywhere in 166 lines.** That is §16aw's
  leg RA reproduced at slightly larger scale (157 files then), and it is the
  standing evidence that §16av's `MAXWLD` 256 / `SSPACE` 4096 still hold.
- `FINISH` answered; clean exit.

### Leg UD — the parser build, by absolute path: PASS on all four of its edits

`CKMRGI A:\SPDTEST.KSC` — the same take-file §16ad ran, deliberately reused
rather than rewritten, so this is a reproduction and not a new experiment.

| what it proves | reading |
|---|---|
| edits 13 + 14 — `isabsolute()`, `zfnqfp()`, and the mis-nested `#endif` | the file was found, qualified and **run**: `=== SPDTEST-BEGIN` through `=== SPDTEST-END` |
| edit 12 — `SHOW VERSIONS` under `NOFRILLS` | `C-Kermit 11.0.508, 2026/08/09`, `Built for: Victor 9000 / Sirius 1`, `Running on: MS-DOS Victor` |
| §16ab — the termios cache and `ttyname()` | `Line: /dev/seriala, speed: 9600, **mode: local**` after `SET LINE` |
| edit 15 — `(int) (ss[i] / 10)` | `SET SPEED 38400` reads back **38400**; `SET SPEED 19200` reads back **19200** |

`rxlost=0 rxfull=0 rxpeak=0`, `deb=0`, `nap per=409`: nothing was on the wire,
which is what this leg wanted.

### Leg UE — the timing control, and it retracts leg UA's explanation

UE is UA with the host started at t+150 s instead of t+110 s. It came back
**identical**: `RCVUE.DAT` md5-identical, 39,783 wire bytes, 30 packets,
**4 timeouts, 7 retransmissions**, 80.826 s against 80.768 — **56 ms apart**,
which is the tightest pair this project has produced on any harness.

**So UA's "the host got there before the Victor was listening" was wrong.**
Starting the host 40 s later changed nothing, and the packet log says why:
the S packet is answered at t=0, and then the **F packet times out at 8, 16
and 24 s and is not ACKed until 26** — the Victor is inside `rcvfil()`
deciding on the output filename, not missing the packet. Both legs then run
their whole data phase clean: 27 s → 80.8 s for 32,768 bytes is **609 cps**,
which is §16n's 633 and §16u's 632.

**And it is not new.** The same shape is in two pre-merge logs in this tree:

| leg | when | timeouts | resends | host clock | cps |
|---|---|---:|---:|---:|---:|
| §16aj FA | 9 Aug, pre-merge | 3 | 6 | 75.906 s | 431 |
| §16ar WD | 11 Aug, pre-merge | 4 | 7 | **83.013 s** | 394 |
| **UA** | post-merge | 4 | 7 | 80.768 s | **405** |
| **UE** | post-merge | 4 | 7 | 80.826 s | **405** |

Leg WD is the closest control the tree holds — same harness, same rate, same
timeout-and-resend shape — and the merged build is **2.2 s faster** than it,
not slower. **The 405-vs-633 gap is the fixture, not the port**, and any
future session quoting a whole-run cps at 9600 under MAME should say whether
the ~27 s file-open stall is inside it. That stall is the one thing this
sitting found that nobody has costed; it is not a merge defect, it is an
old one nobody has looked at.

---

## Verdict

**Five legs, five passes, no regression.** Every transfer byte-exact,
`rxlost = 0 rxfull = 0` on all five, `deb = 0` on all five, and every
counter that has a documented value reproduced it. The twenty upstream edits
were verified present and structurally intact by diffing HEAD against the
merge's upstream parent (`616e369^2`) before any leg ran — 539 inserted
lines across 13 files, and all twenty accounted for.

**What moved:** the shipping image, by 66 bytes (230,690 → 230,756; needs
242,786 → 242,852), which does not change the smallest Victor. And the
parser build, by ~25 KB, which **does**: 429,890 (419K, 512K machine) →
453,602 (442K, **640K machine**). `KEEP_ICP` is a regression build and not a
shipping one, so this costs nothing today, but it is the first time an
upstream merge has moved a machine class and it should be watched.

**What was checked and did not need a leg:** the substantive (whitespace-
ignoring) upstream diff over every port-critical file. The two changes that
look like behaviour changes on the receive path — the added parentheses in
`rcvfil()` and in `spar()`'s streaming test — are **precedence no-ops**,
because `&&` already bound tighter than `||` in both. `ckcfn3.c`'s
`reason[(CHAR)c]` is a signed-char index fix on the error-reason path.
`zdtstr()`/`zstrdt()` now copy `localtime()`'s result into an automatic
`struct tm` before reading it, which is adjacent to upstream edit 19 and is
covered by leg UC's dates.

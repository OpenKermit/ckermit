# Next session

Handoff for the Victor 9000 port, written 5 August 2026 (fourth session that
day). **The alarm roundup is in, and the retransmissions it was supposed to
fix turned out not to be ours at all.**

**Read `PORTING.md` §16l first** — it is this session. It keeps §16k's
derivation about `alarm()` firing early (that part was right), retracts the
hypothesis attached to it, and closes the "one timeout and two
retransmissions, not diagnosed" item that has been open since §16k.

---

## 1. What changed this session

**The alarm deadline is rounded up, and it stays.** `ckvictor.c`'s `alarm()`
now records `time() + secs + V9K_ALARM_ROUNDUP`. §16k's derivation was
correct: `time()` is a floor, so a `time()+n` deadline armed at real T+0.9 is
reached only n−0.9 seconds later — the window is **(n−1, n]**, *early*, and
the §0d comment claiming "never early" was wrong. Rounded up it is (n, n+1],
which is the direction a protocol timeout should err in. The roundup is taken
back off the returned time-remaining so `ttoc()`, which subtracts from that
value and re-arms, still works in the seconds its caller asked for.

No upstream edit — **still eleven**. DGROUP **unchanged** at 48,176 of 65,536
(the change is code, not data). Image 202,294 → **202,310**, needs 216,582 of
396,224.

**But it fixed nothing observable, and the packet log says why in one line:
the Victor never times out.** Across two complete 32,768-byte receives, every
single `r-` line decodes to type **`Y`**. **Not one NAK.** A receiver whose
timer fires does not look like that, so no rounding of that timer could have
changed a retransmission.

**The timeouts are the host's, and they land on slow-start doublings.** Both
runs put every timeout on the packet immediately after C-Kermit doubles the
length — run 1 at the first 3,905-byte packet, run 2 at the first 1,953-byte
one — and in both, after the host backs off and climbs again, nothing else
times out. 3,905 bytes at 9600 is **4.1 seconds of line time on its own**,
against an estimate built from packets a quarter that long.

**Measured**, 9600, MS-DOS 3.1 under MAME, `CKERMITW -l /dev/seriala -b 9600
-r`, no `-d`, 32,768-byte fixture of pseudo-random bytes containing all 256
values. **Both byte-exact** (`cmp` after pulling the file back off the image):

| | run 1 | run 2 (`set receive timeout 20` on the host) |
|---|---:|---:|
| host timeouts | 2 | **1** |
| retransmissions | 4 | **1** |
| elapsed / rate | 60 s, 537 cps | **54 s, 606 cps** |
| longest packet | 3,905 | 3,099 |
| `rxpeak` | 547 of 4096 | 500 of 4096 |
| `rxlost` / `rxfull` | 0 / 0 | 0 / 0 |

Nothing on the Victor changed between those two runs. The mitigation is a
**host** setting.

---

## 2. Do this next, in rough priority order

**Isolate the ~502-byte stall.** Now the top item. `rxpeak` reads 502, 502,
547, 500 across two ring sizes, two fixtures and longest-packets from 2,668
to 3,905 — four readings inside 10% of each other, so §16k's "one fixed pause
of about half a second at 9600, not a rate deficit" survives a second
fixture. Still unidentified.

The instrument is cheap and needs no upstream edit: **`v9k_write()` in
`ckvictor.c` sees every write, not just the comm device** — anything that is
not `ttyfd` falls through to the library — and `gettimeofday()` a few hundred
lines below already reads INT 21h `AH=2Ch` for hundredths. Time the non-tty
writes there, keep the max, and print it with the ring counters at
`atexit()`. If the max is ~0.5 s the inter-packet file write is the stall and
the question is closed.

It bounds how far the ring could be trimmed and it is four times as many
bytes at 38400.

**Real hardware.** Still nothing, ever. Unchanged and still the largest gap.

**Then 8b, windows.** `DFWSIZ` is still 1. This is the step that removes the
one-packet-in-flight property the missing flow control relies on, so
`tcflow()` or a much larger ring probably comes first.

**Report the `ckcmai.c` nesting upstream.** Unchanged from §16j — wrong for
every `NOTCPIP` build, and it silently costs `getdialenv()` too.

**`REMOTE DIRECTORY`** still streams its listing and never terminates it
(§16i). Unchanged; use `--safe-server` when you need the log.

---

## 3. Instruments

- **An uppercase `S-` line in a C-Kermit packet log is a retransmission**
  (`logpkt('S',...)`, `ckcfns.c:2002`, commented "Log the resent packet") and
  a `<timeout>` line is a timeout (`ckcfns.c:2900`). So
  `grep -c '^S-' host.pkt` and `grep -c '<timeout>' host.pkt` count a run.
  New this session and it is what made §16l countable.
- **The packet log escapes control characters, so `^A` is two bytes.** The
  type character is body[4], not body[3]. Getting this wrong prints the
  sequence number where the type should be and every packet looks alike.
- **`v9k: rxlost=… rxfull=… rxpeak=… of …` on stdout at exit, every build.**
  A `.BAT` that redirects stdout catches it; `STEPE.BAT` is the pattern.
- **`XFLAGS=-dDRPSIZ=90`** — packet length is a one-flag experiment, both
  here and in `ckcker.h`.
- **Do NOT combine `-dKEEP_DEBUG` with long packets and believe the result.**
  That is the whole lesson of §16k — `-d` costs ~25 ms per received byte.
  It is still the right instrument for anything that is not throughput.
- **`python3 .probe/mzsize.py ckermitw.exe`** — run this, not `ls -l`.
- **`CKERMITW -d -h` is the 2.5-minute oracle** — no serial line, no `socat`,
  no host `kermit`. Reaches `sysinit()` → `uname()` and `inibufs`. Does not
  reach `rpar()`, so it cannot tell you the negotiated packet length.
- **Decode the negotiation yourself**: `MAXL TIME NPAD PADC EOL QCTL QBIN
  CHKT REPT CAPAS WINDO MAXLX1 MAXLX2`, each `unchar(c) = c - 32`, long
  length = `MAXLX1*95 + MAXLX2`. (Confirmed 3,999 and window 1 this session.)
- **There is no `-fstack-usage` under Open Watcom.** Read the source for new
  automatics; check `sub sp,N` in `wdis` if it matters.

---

## 4. Things that are known-incomplete

- **The ~502-byte stall is unidentified.** §2. Now the top item.
- **`SET TIMER OFF` is not a C-Kermit 9.0.302 command** — it is rejected with
  "No keywords match". The dynamic-timer flag `rttflg` is set by the keyword
  form of `SET RECEIVE TIMEOUT` (`ckuus7.c:6960`). A bare number sets the
  override only, which is what run 2 above actually did.
- **`SET FILE COLLISION` is `BACKUP`, and BACKUP cannot work on FAT.**
  `znewn()` appends `.~N~` to the whole name — not a legal 8.3 name — so a
  receive onto an existing name is refused with reason "name". Symptom: S, F,
  A, then **Z with data `D` and no data packets at all**. **Use a fresh
  filename per run and delete leftovers from the image.**
- **`REMOTE DIRECTORY` never terminates its listing** (§16i).
- **Most of the default capability set is untested** (§16i). `BYE` never sent.
- **Wildcards are case-sensitive.** `-s *.TXT`, not `*.txt`.
- **No interrupt-level flow control**, `tcflow()` is a stub.
- **No stack switch in the handler** — deliberate, ~30-byte frame.
- **The IRQ1 vector is hard-coded to 41h.** Most likely thing to break "one
  binary, two DOSes".
- **Ctrl-Break with the line open** is not covered by `atexit()`.
- **WR2 is left as the OEM driver set it** (`10h` vs 3.13's `14h`).
- **The carrier clause** in `ttgmdm()` forces carrier present under `CLOCAL`.

---

## 5. Still open, from before

**Nothing has run on real hardware.** All MAME, Victor MS-DOS 3.1.

**The gap for the interactive parser** — `XFLAGS=-dKEEP_ICP` plus
`.probe/mzsize.py` settles it in one build and no MAME run. Not re-measured
since `NOFLOAT`, and note the ring spent 3,584 bytes of DGROUP in §16k.

**The µPD7201 interrupt-acknowledge sequence.** Unsettled, gates 38400.

**Why `binmode.obj`'s near init record does not work here** (§16h). Routed
around, not diagnosed.

---

## 6. The harness

§16a, §16d, §16g–§16l have it in full. What this session added or corrected:

- **The whole harness is reproducible from scratch in about 6 minutes per
  run.** `socat` first (single-use `-bitb`), then MAME, then wait ~105 s for
  the boot and `-autoboot_delay 30` before starting the host `kermit`. The
  sender's own S-packet retries cover the slack in that estimate.
- **MAME exits on its own** when `-seconds_to_run` expires in this build
  (§16k's observation, confirmed twice more). `-log` still writes no
  `mame.log`, so §16a's "poll for Average speed" does not work — wait on the
  process, and match `[m]ame/mame victor9k` so `pgrep` does not match the
  polling shell.
- **A run takes ~300 emulated seconds for a 32 KB receive**: boot, plus 30 s
  autoboot delay, plus ~60 s of transfer.
- **Put the Victor in `-r` (receive), not `-x` server mode**, when the point
  is a receive measurement. A failed server run can wedge the server so the
  host's `finish` never lands. `-r` always exits.
- **One `kermit` attempt per MAME run, and unique log names per run.** `log
  packets` *truncates*.
- **Verify by pulling the file back off the image and `cmp`.**
- `~/projects/mame/victor_kermit.img.bak-20260805-alarm` is the backup from
  before this session's runs.
- **On the image now:** the shipping `CKERMITW.EXE` (202,310, `DRPSIZ` 4000,
  ring 4096), `STEPF.BAT`/`STEPG.BAT` (both `-r`, no `-d`, stdout to
  `STEPF.OUT`/`STEPG.OUT`), plus §16h–§16k leftovers. `RCVA/RCVB/RCVC.DAT`
  and now `RCVD/RCVE.DAT` are receive fixtures — delete before reusing a
  name.
- Everything else from §16i's list still holds: `-bitb` is single-use so start
  `socat` first with `fork`; `.BAT` files need CRLF; `-autoboot_command` takes
  the literal `\n`; digits come through shifted; MS-DOS 3.1 cannot redirect
  handle 2; the disk boots as `A:`; use `vtg_image_util`, never write to the
  image while MAME runs; `kermit -y <file>` always.

---

## 7. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"        # ckermitw.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak sizes"  # DGROUP report
python3 .probe/mzsize.py ckermitw.exe                       # will it LOAD
```

Rule 4 still applies, and so does its second half: the heap is **outside**
DGROUP, so anything that raises the packet buffers is measured against the
machine's 396,224, not against the segment. The **ring is not** — it is
`.bss` and comes straight out of the 64K.

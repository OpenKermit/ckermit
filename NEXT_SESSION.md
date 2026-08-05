# Next session

Handoff for the Victor 9000 port, written 5 August 2026. **The wildcard send
works, the driver's loss counters have been read, and the send direction has
no known open defects.**

**Read `PORTING.md` first** — §16g is new and is this session; §16f now ends
in it, and §15's "still open" list lost its top item. This file is only the
"what next".

---

## 1. What changed this session

Nothing in the source tree. **This session was measurement**, and it closed
the port's last open defect by failing to reproduce it.

**`-s *.TXT` transfers.** Two MAME runs on Victor MS-DOS 3.1, the §16a
harness unchanged, `XFLAGS=-dKEEP_DEBUG`:

| | run 1 | run 2 |
|---|---|---|
| pattern matches | 1 file | **3 files** |
| S/F/A/D/Z/B | complete | complete, ×3 |
| bytes at the far end | 72 (of 74) | 61, 53, 72 (of 63, 54, 74) |
| byte-correct | yes | yes |
| retransmissions | none | one, a crossed NAK |
| `rxlost` / `rxfull` | **0 / 0** | **0 / 0** |
| exit | `status=0` | `status=0` |

Run 2 is the one that matters most, because more than one match is a
different path: `gnfile()` sets `sndsrc = -1` and every file after the first
comes out of the `znext()` loop driven by `<sseof>Y`. That path had never
executed on this port.

**Cause 4 is closed as retired, not as diagnosed.** §16f called it the port's
one open defect, but every measurement in that section — including the
symptom — came from the `ia16-elf-gcc` build, and the fix for cause 3 was a
replacement `stat()` that only existed there. It does not reproduce under
Open Watcom, and there is no longer a compiler that produces it, so what it
actually was is unanswerable. Recorded that way deliberately.

What §16g *does* explain is the symptom's shape. "Send-Init, ACK, Send-Init"
is exactly what a crossed NAK produces — the host receiver NAKs packet 0
while it waits, the NAK lands after the Victor's S has gone out, the Victor
resends packet 0. Run 2 caught one in the Victor's own log (`[# N]`,
`resend retry=1`) and recovered in a single retry. Whether gcc's ten-retry
loop was the same mechanism failing to converge is a guess and stays one.

**The two loss counters were read for the first time.** §11b has kept them
since it was written; §16d pointed the instrument at the wrong second and got
nothing. `v9k_ser rxlost/rxfull[0]=0` at every `tcsetattr()` on the way out of
both runs. **Zero bytes lost to a µPD7201 overrun, zero to a full ring**,
across a three-file 44-second transaction. That is the first direct
measurement of the driver's error path rather than an inference from "the
transfer completed" — and it says nothing about 38400 or streaming, which is
where they would get interesting.

Rebuilt clean afterwards: DGROUP **39,424 of 65,536 (60%)**, `ckermitw.exe`
**228,554 bytes** — unchanged, as it must be, since no C changed.

---

## 2. Do this next, in rough priority order

**Milestone step 6: `RECEIVE`, then `GET`, then `SERVER`,** at 9600. This is
now the top item. Receive drives the ring harder than send did, because the
file writes happen on the Victor's end — the case §11b has no interrupt-level
flow control for. **Point the loss counters at it**: they are known-zero for
send now, so a non-zero reading during receive is a clean signal rather than
an ambiguous one. `RXTEST.BAT` is already on the image from an earlier
session; check what it says before trusting it.

**Consider raising the stack.** `wlink`'s map says `STACK 2,048` — Watcom's
default, inherited rather than chosen. `traverse()` is 98 bytes/level and the
largest non-recursive frames are `docmd()` at 1152 and `zcopy()` at 1114, so
a deep walk landing in `docmd()` is already most of 2K. `sfile()` alone has a
257-byte `pktnam[]`. There are 26,112 free bytes in DGROUP and nothing else
wants them. `option stack=8k` in `victorow.mak`. Still deliberately not done
in the same change as anything else.

**Then step 8: long packets, windows, streaming, one at a time.** The far
heap means `SBSIZ`/`RBSIZ` can now grow — 9024/9050, the `DYNAMIC` default,
would cost nothing in DGROUP. Measure the *image* against the machine's 387K
(§16a's method), not DGROUP. Note the debug build is already 308,862 bytes,
so that is the headroom being spent.

**`NOGFTIMER`.** Still not turned off, and still why `emu87.lib`/`math87l.lib`
are in the link at all (89 of the image's INT sites). Turning it off drops the
FP emulator entirely and would buy back image space for step 8.

---

## 3. Instruments

- **`XFLAGS=-dKEEP_DEBUG`** — C-Kermit's own debug log. `CKERMITW -d -s
  FOO.BIN` writes `./debug.log` on the target. Needs `make clean` first.
  Image goes 228,554 → 308,862 bytes and still loads. This settled §16g and
  is the instrument for everything now.
- **The driver's own two counters** ride along with it:
  `v9k_ser rxlost/rxfull[N]=M` — N is bytes lost to a chip overrun, M bytes
  lost to a full ring. Logged from `tcsetattr()`, which `ttres()` reaches on
  the way out, so they appear near the end of `DEBUG.LOG`. Baseline is 0/0.
- **`XFLAGS=-dKEEP_ICP`** — restores the interactive parser, for re-running
  §9d's DGROUP measurement. It links (60,768 of 65,536; 19,376 with
  `ZT=-zt128`) and it does **not load** — 429K needed against 387K offered.
- **`.probe/`** holds throwaway programs, not part of the build: `vwild.c`
  (Watcom) and `vmatch.c` (gcc — no longer buildable, kept for the questions
  it asked).
- **There is no `-fstack-usage` equivalent under Open Watcom.** Rule 7 lost
  its cheap instrument. Read the source for new automatics; if it matters,
  read the prologue's `sub sp,N` in `wdis` output. Do not stand a second
  toolchain back up to measure frames.

---

## 4. Things in the driver that are known-incomplete

Unchanged; listed so they are not rediscovered as bugs.

- **No interrupt-level flow control.** 3.13 sends XOFF from inside `SERINT`
  at a 3/4-full mark. Not needed with one packet in flight — and §16g's
  `rxfull=0` is the measurement that says so, at 9600. Needed for streaming.
  `tcflow()` is a stub for the same reason.
- **No stack switch in the handler.** Deliberate — 3.13's `SERINT` does not
  switch either, on this machine. The frame is ~30 bytes, dominated by
  Watcom's fixed 12-register prologue.
- **The IRQ1 vector is hard-coded to 41h.** Right for Victor MS-DOS 3.1;
  `~/projects/myfreedos` puts its serial ISR at INT 09h, so this is the most
  likely thing to break "one binary, two DOSes". One constant, §1e.
- **Ctrl-Break with the line open.** Restored from `atexit()`, which does
  not cover a Ctrl-Break DOS turns into a bare termination. Fix, if it
  bites: hook INT 23h (`AH=25h`, inside rule 6).
- **WR2 is left as the OEM driver set it** (`10h`, where 3.13 writes `14h`).
  First thing to try if interrupts ever fail to arrive.
- **The carrier clause** in `ttgmdm()` forces carrier present under
  `CLOCAL`. The one judgement call in the file; reasoning in §11b.

---

## 5. Still open, from before

**Nothing has run on real hardware.** Everything is MAME, Victor MS-DOS 3.1.
That is now, unambiguously, the largest single gap in the port, and it has not
moved.

**The 42KB gap for the interactive parser.** Needs 429KB, DOS offers 387KB
(§16a, measured).

**The µPD7201 interrupt-acknowledge sequence.** §11b's handler issues
`WR0 = 38h` then the 8259's specific EOI and works under emulation, which is
what 3.13 does. MAME's µPD7201 is not the part, so this is not settled, and
it gates 38400. §16g's zero loss counters are at 9600 and do not speak to it.

**The text/binary decision.** The host logs "Global file mode: binary" while
the Victor sends 74 bytes as 72 — a text-mode send with CRLF→LF. Correct, and
consistent across §16d and §16g, but worth understanding before step 8 turns
on long packets.

---

## 6. The harness

§16a, §16d and §16g have it in full. The landmines:

- **`KTEST.BAT` must have CRLF line endings.** With Unix `\n`, COMMAND.COM
  echoes every line and runs none — and it looks like a corrupted terminal,
  not a corrupted file.
- **MAME does not exit when `-seconds_to_run` expires.** It writes
  `Average speed: ...` to its log and sits there. Poll the log, not the
  process: `until grep -q "Average speed" mame.log; do sleep 10; done`.
- **Budget the emulated seconds.** A 3-file 9600 transfer took 44 s of
  transfer inside a `-seconds_to_run 240` run; 180 was enough for one file.
  Boot plus `-autoboot_delay 30` eats the first ~55 s.
- **MS-DOS 3.1 cannot redirect handle 2.** `2> FILE` puts a literal `2` in
  `argv`.
- **The Victor boots its hard disk as `A:`**, not `C:`.
- **`~/projects/mame/victor_kermit.img` is the image**; mtools cannot read
  it, use `vtg_image_util` (`python3 cli_main.py ...`). Backups beside it:
  `.bak-20260804`, `.bak-before-gcc-run`, `.bak-20260805-wild`.
- **On the image now:** the plain (non-debug) `CKERMITW.EXE`, a `KTEST.BAT`
  that runs the §16g wildcard test, and `ALPHA.TXT` / `BETA.TXT` /
  `TESTFILE.TXT` as the three `*.TXT` fixtures.
- **MAME's `-bitb` socket is single-use.** Start `socat` first, with `fork`,
  and it survives across runs.
- **Test on Victor MS-DOS 3.1, not FreeDOS** (§16a).
- **`-l /dev/seriala`, with forward slashes.**
- **Always give the host `kermit` a command file and a timeout**;
  `~/.kermrc` sets a line that does not exist, so use `kermit -y <file>`.
- **Run MAME from `~/projects/mame`** — it writes `cfg/` and `nvram/` into
  the working directory.
- **`XFLAGS=-dKEEP_DEBUG` needs `make clean` first.**
- **Digits come through shifted in `-autoboot_command`.** Prefer digit-free
  filenames in automated runs — which is why the fixtures are `ALPHA`/`BETA`.
- A run costs 3–5 minutes of wall clock. Put every question into one `.BAT`.
- Host receiver: `kermit -y <file>` with `set line /tmp/v9000`,
  `set speed 9600`, `set carrier-watch off`, `set flow none`,
  `log packets`, `log transactions`, `receive`. Start it right after MAME —
  its NAKs while waiting are normal and the Victor handles them.

## 7. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"        # ckermitw.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak sizes"  # DGROUP report
```

The link prints its DGROUP figure. Rule 4 still applies — report DGROUP after
any change that could add static data — but note the second half of it: the
heap is **outside** DGROUP, so anything that raises the packet buffers has to
be measured against the machine's 387K, not against this segment.

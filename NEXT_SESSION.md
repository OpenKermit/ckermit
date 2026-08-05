# Next session

Handoff for the Victor 9000 port, written 5 August 2026. **The port transfers
a file, and it now has exactly one toolchain.**

**Read `PORTING.md` first** — §3, §4, §9 and §15 were rewritten around the
single build, and §9c/§9d/§14/§16/§16e now carry "history" banners marking
them as a record of a closed question. This file is only the "what next".

---

## 1. What changed this session

**The `ia16-elf-gcc` build was retired. Open Watcom V2 large model is the
only build.**

This was a decision, not a discovery — the evidence had been accumulating for
three sessions and §9d/§16e/§16f is where it is written up. The short form:
one near 64K DGROUP is the wrong shape for this program. It cost the
interactive command parser outright, it forced `SBSIZ`/`RBSIZ` to be halved
before a transfer would complete, it left ~2,090 bytes of heap at the
low-water mark of a *working* run and 212 during a wildcard expansion, and it
could not afford a debug log at all. The large model's far heap and `-zc`
remove every one of those.

What that took out of the tree:

| | before | after |
|---|---:|---:|
| `ckvictor.c` | 3,037 lines | **2,002** |
| `__WATCOMC__` conditionals | 23 blocks | **0** |
| makefiles | 2 | **1** |

Deleted: `victor9k.mak`; `ckvictor.c` sections 0, 0a, 0c, 0e and 1c — the
inline-assembly INT 21h layer (`_read_r`, `_write_r`, `dos_getch`,
`DOS_DS_CALL`), the hand-built `opendir`/`readdir`/`closedir` over the DOS
DTA, the `stat()` that answered `"."`, the `sleep`/`creat`/`utime`/`umask`/
`exec` stubs, `_link_r`/`_kill_r`, and the `V9K_HEAPREPORT` and `V9K_DIRTRACE`
instruments; and the per-compiler `SBSIZ`/`RBSIZ` split in `ckvictor.h`.
Watcom's runtime supplies all of it. `victor/` and `victorow/` both stay.

**Verified: the linked binary is byte-identical to before the change.**
DGROUP 39,424 (60%), `ckermitw.exe` 228,506 bytes, and `ckvictor.c` compiles
with zero warnings.

**Rule 6 was re-measured against Open Watcom** (§12), because the old proof
was a disassembly of `libdos-m.a` and that library is gone. All 239 library
modules in the linked image: 86 × INT 21h, 89 × the 8087 emulator's 34h–3Dh,
one `int 3`. **No BIOS interrupts.** `clibl.lib` does contain BIOS-using
modules — `biosfunc`, `b_disk`, `b_timofd`, `dointr` — and none is linked.
`intdos()` resolves to `intd086`, which hard-codes INT 21h.

---

## 2. Do this next, in rough priority order

**Finish the wildcard send — cause 4. This is the port's one open defect.**
`-s *.TXT` expands correctly, twice, and then does not transfer: the Victor
sends Send-Init, is ACKed, and sends Send-Init again, ten times, until the
host gives up with "Too many retries". **It is not the heap** — that was
established under gcc at 2,068 bytes free, and the heap is outside DGROUP
now.

The lever is the asymmetry: `-s TESTFILE.TXT` works and `-s *.TXT` does not,
and the only difference is the second expansion, the one `gnfile()` does with
`ZX_FILONLY` after the protocol has started. **Build with
`XFLAGS=-dKEEP_DEBUG` and read the `ssfile`/`gnfile` path out of
`DEBUG.LOG`.** That instrument now exists unconditionally, which it did not
when this bug was last worked on.

**Milestone step 6: `RECEIVE`, then `GET`, then `SERVER`,** at 9600. Receive
drives the ring harder than send did, because the file writes happen on the
Victor end — the case §11b has no interrupt-level flow control for. **Read
the two loss counters out of `DEBUG.LOG` afterwards** (bytes lost to a chip
overrun, bytes lost to a full ring); they are logged from `tcsetattr()`,
which `ttres()` reaches on the way out, and they have still never been read.

**Consider raising the stack.** `wlink`'s map says `STACK 2,048` — Watcom's
default, inherited rather than chosen. `traverse()` is 98 bytes/level and the
largest non-recursive frames are `docmd()` at 1152 and `zcopy()` at 1114, so
a deep walk landing in `docmd()` is already most of 2K. There are 26,112 free
bytes in DGROUP and nothing else wants them. `option stack=8k` in
`victorow.mak`. Deliberately not done in the same change as the retirement.

**Then step 8: long packets, windows, streaming, one at a time.** The far
heap means `SBSIZ`/`RBSIZ` can now grow — 9024/9050, the `DYNAMIC` default,
would cost nothing in DGROUP. Measure the *image* against the machine's 387K
(§16a's method), not DGROUP.

---

## 3. Instruments

- **`XFLAGS=-dKEEP_DEBUG`** — C-Kermit's own debug log. `CKERMITW -d -s
  FOO.BIN` writes `./debug.log` on the target. Needs `make clean` first. This
  is the instrument for almost everything now; the two custom ones the gcc
  build needed were deleted with it.
- **`XFLAGS=-dKEEP_ICP`** — restores the interactive parser, for re-running
  §9d's DGROUP measurement. It links (60,768 of 65,536; 19,376 with
  `ZT=-zt128`) and it does **not load** — 429K needed against 387K offered.
- **`.probe/`** holds throwaway programs, not part of the build: `vwild.c`
  (Watcom — asks DOS directly about `.`, trailing separators, `FindFirst` and
  `opendir`, in the root and in a subdirectory) and `vmatch.c` (**gcc — no
  longer buildable**, kept for the questions it asked). Both settled a
  question that reasoning had got wrong.
- **You cannot interpose on `malloc()` under gcc** — written up in §16f so it
  is not tried a third time. Moot now, but the write-up explains why the
  heap instrumentation took the shape it did.
- **There is no `-fstack-usage` equivalent under Open Watcom.** Rule 7 lost
  its cheap instrument. Read the source for new automatics; if it matters,
  read the prologue's `sub sp,N` in `wdis` output. Do not stand a second
  toolchain back up to measure frames.

---

## 4. Things in the driver that are known-incomplete

Unchanged; listed so they are not rediscovered as bugs.

- **No interrupt-level flow control.** 3.13 sends XOFF from inside `SERINT`
  at a 3/4-full mark. Not needed with one packet in flight; needed for
  streaming. `tcflow()` is a stub for the same reason.
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
That is the largest single gap in the port and it has not moved.

**The 42KB gap for the interactive parser.** Needs 429KB, DOS offers 387KB
(§16a, measured). Retiring gcc did not change this — the parser's problem was
never DGROUP under Watcom.

**`NOGFTIMER`.** Floating-point transfer timers on an 8088 with no FPU. Still
not turned off, and now known to be why `emu87.lib`/`math87l.lib` are in the
link at all (89 of the image's INT sites). Turning it off would drop the FP
emulator entirely.

**One unexplained difference, downgraded from two** (§16e): the gcc build's
transfer reported 0 seconds against Watcom's 10. The other — gcc sending the
file as binary (74 bytes) where Watcom sends it as text (72) — no longer has
a second build to be a difference *between*, but the text/binary decision is
still worth understanding before step 8.

**The µPD7201 interrupt-acknowledge sequence.** §11b's handler issues
`WR0 = 38h` then the 8259's specific EOI and works under emulation, which is
what 3.13 does. MAME's µPD7201 is not the part, so this is not settled, and
it gates 38400.

---

## 6. The harness

§16a and §16d have it in full. The landmines:

- **`KTEST.BAT` must have CRLF line endings.** With Unix `\n`, COMMAND.COM
  echoes every line and runs none — and it looks like a corrupted terminal,
  not a corrupted file.
- **MAME does not exit when `-seconds_to_run` expires.** It writes
  `Average speed: ...` to its log and sits there. Poll the log, not the
  process: `until grep -q "Average speed" mame.log; do sleep 10; done`.
- **MS-DOS 3.1 cannot redirect handle 2.** `2> FILE` puts a literal `2` in
  `argv`. Traces on stderr go to the screen, and only the last 25 lines
  reach the snapshot — so keep trace output short or send it to stdout.
- **The Victor boots its hard disk as `A:`**, not `C:`.
- **`~/projects/mame/victor_kermit.img` is the image**; mtools cannot read
  it, use `vtg_image_util` (`python3 cli_main.py ...`). Backups beside it:
  `.bak-20260804` and `.bak-before-gcc-run`.
- **MAME's `-bitb` socket is single-use.** Start `socat` first.
- **Test on Victor MS-DOS 3.1, not FreeDOS** (§16a).
- **`-l /dev/seriala`, with forward slashes.**
- **Always give the host `kermit` a command file and a timeout**;
  `~/.kermrc` sets a line that does not exist, so use `kermit -y <file>`.
- **Run MAME from `~/projects/mame`** — it writes `cfg/` and `nvram/` into
  the working directory.
- **`XFLAGS=-dKEEP_DEBUG` needs `make clean` first.**
- **Digits come through shifted in `-autoboot_command`.** `V9KTEST.COM` was
  typed as `V(KTEST.COM` once and produced a convincing but bogus "No files
  for -s". Prefer digit-free filenames in automated runs.
- A run costs 2–15 minutes of wall clock. Put every question into one
  `.BAT`. A no-serial run at `-seconds_to_run 75` is about 90 seconds and is
  enough for anything that does not touch the wire.
- Host receiver: `kermit -y <file>` with `set line /tmp/v9000`,
  `set speed 9600`, `set carrier-watch off`, `set flow none`,
  `log packets`, `log transactions`, `receive`. Start it right after MAME.

## 7. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"        # ckermitw.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak sizes"  # DGROUP report
```

The link prints its DGROUP figure. Rule 4 still applies — report DGROUP after
any change that could add static data — but note the second half of it now:
the heap is **outside** DGROUP, so anything that raises the packet buffers has
to be measured against the machine's 387K, not against this segment.

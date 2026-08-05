# Next session

Handoff for the Victor 9000 port, written 5 August 2026. **Both builds now
transfer a file, and the wildcard bug is three-quarters solved.**

**Read `PORTING.md` first** — §16e and §16f are new, §8 has grown from six
guarded upstream edits to eight, and §15's top item has been rewritten. This
file is only the "what next".

---

## 1. Where things stand

| | ia16-elf-gcc, medium | Open Watcom, large |
|---|---|---|
| makefile | `victor9k.mak` | `victorow.mak` |
| 24 modules compile | yes, 4 warnings | yes, 17 warnings |
| warnings are | all pre-existing, all upstream | all pre-existing, all upstream |
| DGROUP after link | 52,728 / 65,536 (80%) | 39,424 (60%) |
| left for heap + stack | 12,808 (shared) | 26,112 (heap is outside DGROUP) |
| `SBSIZ`/`RBSIZ` | **1024** — had to be halved | 2048 |
| **transfers a literal file** | **yes (§16e)** | **yes (§16d)** |
| expands `-s *.TXT` | **yes, both passes (§16f)** | yes, always did |
| **transfers a wildcard match** | **no** | not tried |
| debug log (`KEEP_DEBUG`) | **does not fit, measured** | yes |

Nothing has run on real hardware. Everything below is MAME, Victor MS-DOS
3.1.

### What changed this session

**The gcc build completes a transfer** (§16e). This was billed as a cheap
confirmation and was not: with `SBSIZ`/`RBSIZ` at 2048 the gcc build reached
the file-open step of a real transfer and failed there — `TESTFILE.TXT: Not
enough space`, newlib's `fopen()` unable to get a `FILE` and a 1,024-byte
buffer out of a heap that `inibufs()` had already taken 7,180 bytes of.
Halved to 1024, it transfers. That is the first configuration difference
between the two builds, and it is a property of the toolchains — near heap
versus far heap — not of the port.

**The wildcard bug was three bugs** (§16f), none of them where four
sessions of notes were pointing:

1. `initspace()` asks for `SSPACE` (10,000) and halves-and-retries until
   something succeeds, keeping whatever it gets — so on a 12K heap it takes
   everything and starves what comes after. **Fixed**: §8 edit 7, now 2048.
2. `zxpand()` allocates `maxnames` pointers before reading the first
   directory entry, and `MAXWLD` is 1024, so that is 2,048 bytes spent on a
   pattern that may match nothing. **Fixed**: §8 edit 8, now 64.
3. libdos-m's `stat()` **cannot stat the current directory** — `stat(".")`,
   `stat("./")` and `stat(".\")` all return -1, while named files and named
   subdirectories are fine. `traverse()` starts every walk at `"./"` and the
   `ZX_FILONLY` path (the one a transfer uses) asks `xisdir()` about it
   first. **Fixed**: `stat()` in section 1a of `ckvictor.c`.

**"No files for -s" was never the diagnosis.** `ckuusy.c` prints that string
when it could not allocate 2,000 bytes for the real message. Worth
remembering the next time it appears.

`opendir`, `readdir`, `ckmatch` and DOS itself were all correct throughout,
and are now measured to be (§16f) rather than assumed.

---

## 2. Do this next, in rough priority order

**Finish the wildcard send — cause 4.** `-s *.TXT` now expands correctly,
twice, and then does not transfer: the Victor sends Send-Init, is ACKed,
and sends Send-Init again, ten times, until the host gives up with "Too many
retries". **It is not the heap** — 2,068 bytes free at the low-water mark,
the same room the working transfer has.

The lever is the asymmetry: `-s TESTFILE.TXT` works and `-s *.TXT` does not,
and the difference between them is the second expansion, the one `gnfile()`
does with `ZX_FILONLY` after the protocol has started. Reproduce it in the
**Watcom debug build** first — none of the three fixed causes bit that
build, so if it fails there too you get a full `DEBUG.LOG` of the
`ssfile`/`gnfile` path for free, which the gcc build cannot give you.

**Milestone step 6: `RECEIVE`, then `GET`, then `SERVER`,** at 9600. Receive
drives the ring harder than send did, because the file writes happen on the
Victor end — the case §11b has no interrupt-level flow control for. **Read
the two loss counters out of `DEBUG.LOG` afterwards** (bytes lost to a chip
overrun, bytes lost to a full ring); they are logged from `tcsetattr()` now,
which `ttres()` reaches on the way out, and they have still never been read.

**Then step 8: long packets, windows, streaming, one at a time.** Note that
the gcc build now carves a single 1,018-byte window slot where Watcom carves
two — this is where that starts to matter, and where the far heap stops
being a footnote.

---

## 3. Instruments, including one that does not work

- **`XFLAGS=-DV9K_HEAPREPORT`** (§0e of `ckvictor.c`) prints the low-water
  heap headroom at exit: `v9k heap: low-water 2090 bytes free (break at
  62666 of 65536)`. Sampled at every `read()`, `write()` and `opendir()`,
  registers its own `atexit`, so it works in runs that never open a line.
  Watcom says "far heap, not in DGROUP -- not measured", correctly.
- **`XFLAGS=-DV9K_DIRTRACE`** traces `opendir()`'s path, the DOS pattern it
  builds and the `FindFirst` result, plus one entry count per directory. It
  uses `write(2)` and hand-formatted digits **on purpose**: a `printf`
  version re-enters stdio while stdout's own buffer is being allocated and
  the output disappears. That cost a MAME run.
- **You cannot interpose on `malloc()` in the gcc build.** `ld --wrap` dies
  on the far-call relocations (`R_386_OZSEG16 for symbol with no output
  section`); defining `malloc()` in `ckvictor.c` links and is then never
  called. An earlier run drew a conclusion from that silence and the
  conclusion was wrong. Both attempts are written up in §16f so they are not
  tried a third time.
- **`.probe/`** holds two throwaway programs, not part of the build:
  `vwild.c` (Watcom — asks DOS directly about `.`, trailing separators,
  `FindFirst` and `opendir`, in the root and in a subdirectory) and
  `vmatch.c` (gcc — links the port's own `ckclib.o` and asks `ckmatch()` and
  libdos-m's `stat()` the exact questions the port needs answered). Both are
  ~60 lines and both settled a question that reasoning had got wrong.

---

## 4. Things in the driver that are known-incomplete

Unchanged from last session; listed so they are not rediscovered as bugs.

- **No interrupt-level flow control.** 3.13 sends XOFF from inside `SERINT`
  at a 3/4-full mark. Not needed with one packet in flight; needed for
  streaming. `tcflow()` is a stub for the same reason.
- **No stack switch in the handler.** Deliberate — 3.13's `SERINT` does not
  switch either, on this machine. 22 bytes under gcc, ~30 under Watcom.
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

**Which toolchain the port should use.** Now much less symmetric. Watcom
fits the interactive parser, has 26K of far heap, and gets a debug log; gcc
is at 80% DGROUP, had to have its packet buffers halved to transfer a file
at all, cannot have a debug log, and needs custom instruments to answer
questions Watcom answers with `-d`. gcc's only remaining advantage is that
it is the toolchain the port started with.

**The 42KB gap for the interactive parser.** Unchanged: needs 429KB, DOS
offers 387KB (§16a, measured).

**`NOGFTIMER`.** Floating-point transfer timers on an 8088 with no FPU.
Still not turned off.

**Two unexplained differences between the builds' transfers** (§16e): gcc
sends the file as binary where Watcom sends it as text (74 bytes against
72), and gcc's transfer took 0 seconds against Watcom's 10. Neither is
known to be wrong; both are leads.

---

## 6. The harness

§16a, §16d and §16e have it in full. The landmines, including three new ones:

- **`KTEST.BAT` must have CRLF line endings.** With Unix `\n`, COMMAND.COM
  echoes every line and runs none — and it looks like a corrupted terminal,
  not a corrupted file. **New, cost one run.**
- **`-d` is a Watcom-only option.** `NODEBUG` compiles it out of the gcc
  build, which rejects the whole command line. **New, cost one run.**
- **MAME does not exit when `-seconds_to_run` expires.** It writes
  `Average speed: ...` to its log and sits there. Poll the log, not the
  process: `until grep -q "Average speed" mame.log; do sleep 10; done`.
  **New.**
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
- **`XFLAGS=-dKEEP_DEBUG` needs `make clean` first** (Watcom only).
- A run costs 2–15 minutes of wall clock. Put every question into one
  `.BAT`. A no-serial run at `-seconds_to_run 75` is about 90 seconds and is
  enough for anything that does not touch the wire.
- Host receiver: `kermit -y <file>` with `set line /tmp/v9000`,
  `set speed 9600`, `set carrier-watch off`, `set flow none`,
  `log packets`, `log transactions`, `receive`. Start it right after MAME.

## 7. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victor9k.mak"     # gcc, ckermit.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"     # Watcom, ckermitw.exe
```

Both print their DGROUP figure on link. Diagnostic variants, none set by any
makefile: `-dKEEP_ICP` (Watcom, restores the parser), `-dKEEP_DEBUG`
(Watcom, the debug log), `-DV9K_HEAPREPORT` and `-DV9K_DIRTRACE` (gcc, §3
above). Rule 4 still applies — report DGROUP after any change that could add
static data — and note that the heap, not DGROUP, is what has actually been
biting.

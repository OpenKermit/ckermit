# CLAUDE.md

## What this repository is

The upstream **C-Kermit 11.0** source tree (Columbia University / Frank da Cruz,
~40 years of history, ~100 top-level `.c` files) plus a **Victor 9000 / Sirius 1
port** living on the `victor9k-port` branch.

**Read `PORTING.md` before doing anything on the port.** It is the design
document: architecture, memory budget, what is measured vs. assumed, what is
proven on hardware vs. merely written. It is kept current deliberately — if you
change the plan, change that file in the same commit.

## The port in one paragraph

`CKERMIT.EXE` is a serial-only, file-transfer-only C-Kermit for the Victor 9000,
built with `ia16-elf-gcc` (medium model: far code, **one 64K near-data DGROUP**).
It runs as an MS-DOS program that drives the µPD7201 serial chip and the 8259
directly, so a single binary works on both **Victor MS-DOS 3.1** and **FreeDOS
for Victor**. Everything that is not the serial port goes through **INT 21h
only**.

## Build

The toolchain lives in the `ia16-ubuntu-2` container, which runs under Apple's
native `container` service — **not Docker**. `~/projects` is mounted at
`/mnt/projects` inside it.

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victor9k.mak"        # 24 objects
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victor9k.mak sizes"  # DGROUP report
```

`ckcpro.c` is generated from `ckcpro.w` by `wart`, a **host** tool built with
the host `cc`.

All 24 modules compile clean; DGROUP is 32,311 of 65,536 (49.3%). Nothing has
been linked or run on hardware yet — `make` builds objects only.

## Hard rules

1. **Do not modify upstream C-Kermit files.** The port's value is that the
   protocol engine is untouched. There are exactly five guarded upstream edits
   (listed in `PORTING.md` §8); every one is wrapped in `#ifndef` or
   `#ifdef VICTOR9K` and changes nothing on any other platform. If you think you
   need a sixth, say so explicitly rather than doing it quietly.
2. **Feature configuration goes in `ckvictor.h`, never in `victor9k.mak`.**
   Each `#define` sits next to a comment explaining why. The makefile passes
   `-include ckvictor.h` and nothing else.
3. **Victor-specific C goes in `ckvictor.c`.** It is the only non-upstream C
   file and should stay that way.
4. **The 64K DGROUP is the binding constraint.** `.data` + `.bss` + heap +
   stack all share it; currently 32,325 bytes static (49%) with ~10KB headroom
   projected. **Run `make -f victor9k.mak sizes` after any change that could add
   static data** and report the number.
5. **Never define `BIGBUFOK`** (asks for 290,000-byte buffers). **Never remove
   `DYNAMIC`** (without it the packet buffers become >64K static arrays and the
   build fails outright).
6. **INT 21h only** for console and files. No INT 10h, INT 16h, INT 14h, direct
   screen memory, or BIOS data area — Victor MS-DOS 3.1 has no IBM-compatible
   BIOS, and that discipline is the whole reason one binary runs on both DOSes.
7. **Watch stack frames.** 16-bit target, recursive `traverse()` in `ckufio.c`
   at 1066 bytes/level. Large automatic arrays are a real hazard here — that is
   what `SCANFILEBUF` was.

## Layout of the port

| File | Role |
|---|---|
| `PORTING.md` | design doc, memory budget, hardware map, milestone plan |
| `ckvictor.h` | all ~40 feature `-D` flags, size limits, platform identity |
| `ckvictor.c` | Victor glue: process-model stubs + (planned) the 7201 driver |
| `victor/sys/termios.h` | the 7201 driver's control surface; fills a newlib gap, reached via `-Ivictor` |
| `victor9k.mak` | build + `sizes` target |
| `ckutio.c` | serial, console, timers — **stock upstream**, this is the port |
| `ckufio.c` | file system — **stock upstream** |
| `ckc*.c` | protocol core — do not touch |

## Code style

Match the surrounding file. C-Kermit is K&R-compatible C with dual prototypes:

```c
VOID
#ifdef CK_ANSIC
ck_bracketaddr(char * s, int n)
#else
ck_bracketaddr(s,n) char * s; int n;
#endif /* CK_ANSIC */
{
```

Comments are block-style with the rationale spelled out, and `#endif` carries
the macro name. New code in `ckvictor.c`/`ckvictor.h` follows the same
conventions — 4-space indent, explanation of *why* over *what*.

## Related trees on this machine

- `~/projects/myfreedos` — FreeDOS port to the Victor. Source of the µPD7201
  register map and the serial driver to be lifted (`kernel/victor_int14.asm`,
  `kernel/victor_serial_debug.asm`, `kernel/victor_pic.asm`,
  `docs/victor/subsystem-docs/Serial.md`).
- `~/projects/kermit/victor9000` — `vickermit.c`, a 1980s Victor-native Kermit.
  Useful as a second opinion on chip init.
- `~/projects/kermit/msr313src` — MS-DOS Kermit 3.13 source.
- `~/projects/newlibc/phase3_newlib` — bare-metal Victor newlib. **Out of scope**
  for the current plan (see `PORTING.md` §2), but `libgloss/dirent.c` is a
  reference for `opendir`/`readdir` — note the two defects flagged in §12.

## Working style for this project

State what was measured and what was assumed, and keep them separate — the
existing doc does this and it has already caught one overstated benchmark. When
something is proven on real hardware, say which hardware and which
configuration; "the serial code works at 38400" and "polled TX on channel A has
carried sustained output at 38400" are different claims.

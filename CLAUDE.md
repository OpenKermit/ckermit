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

All 24 modules compile, with 4 warnings, all in stock upstream code and all
pre-existing (`docmdline(1)` in `ckcmai.c`, and implicit declarations of
`utime`/`wait`/`gettimeofday`). DGROUP is 52,728 of 65,536 (80%) after the
linker adds libc. `make` links `ckermit.exe`; it has run under MAME
(PORTING.md §16, §16a, §16b, §16c), never on real hardware.

### The second toolchain

The same tree also builds with **Open Watcom V2**, in the same container at
`/opt/open-watcom-v2/rel`, in the **large** model — far code *and* far data:

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"        # 24 objects + link
```

This is a second build of the same port, not a fork: same `ckvictor.h`, same
stock `ckutio.c`/`ckufio.c`, same single non-upstream C file. It exists to
answer §9c's open question, and it does: DGROUP 39,424 (60%) against gcc's
80%, and the interactive command parser — cut from the gcc build because it
did not fit — **does** fit in DGROUP (`make -f victorow.mak XFLAGS=-dKEEP_ICP`,
60,768, or 19,376 with `ZT=-zt128`). It does not fit in RAM: it needs 429K and
the machine offers 387K. See PORTING.md §9d.

**Both binaries transfer a file.** On Victor MS-DOS 3.1 under MAME each
opens `/dev/seriala`, programs the line through the OEM driver's IOCTL block
(§11a), takes the µPD7201 and IRQ1 over for the data path (§11b), and runs a
complete S/F/A/D/Z/B exchange to a host C-Kermit at 9600 — byte-correct at
the far end. That is PORTING.md **§16d** (Watcom) and **§16e** (gcc), and it
is milestone step 5. Neither has ever run on real hardware. A **wildcard**
send is not there yet: `-s *.TXT` expands correctly in both passes now but
still fails to transfer (§16f).

The gcc build needed `SBSIZ`/`RBSIZ` halved to get there, so `ckvictor.h`
now sets those two per compiler. It is the only place the builds differ, and
the reason is near heap versus far heap rather than anything about the
Victor.

**PORTING.md §16a is the how-to** — the Victor boots its hard disk as `A:`,
the image needs `vtg_image_util` (mtools cannot read it), and MAME's `-bitb`
socket is single-use, so start `socat` first and never probe the port.

Rules 1–7 below apply to both builds. Rule 4's DGROUP report for the Watcom
build is `make -f victorow.mak sizes`, which reads `wlink`'s map.

## Hard rules

1. **Do not modify upstream C-Kermit files.** The port's value is that the
   protocol engine is untouched. There are exactly eight guarded upstream
   edits (listed in `PORTING.md` §8); every one is wrapped in `#ifndef` or
   `#ifdef VICTOR9K` and changes nothing on any other platform. If you think
   you need a ninth, say so explicitly rather than doing it quietly — the
   seventh and eighth were both agreed that way.
2. **Feature configuration goes in `ckvictor.h`, never in `victor9k.mak`.**
   Each `#define` sits next to a comment explaining why. The makefile passes
   `-include ckvictor.h` and nothing else.
3. **Victor-specific C goes in `ckvictor.c`.** It is the only non-upstream C
   file and should stay that way.
4. **The 64K DGROUP is the binding constraint, and the heap inside it is
   the sharper one.** `.data` + `.bss` + heap + stack all share it. After the
   link, including libc: **gcc 52,728 (80%), 12,808 left for heap and stack;
   Watcom 39,424 (60%), 26,112 left** — and Watcom's heap is *outside*
   DGROUP, so only the gcc figure is a real ceiling. **Run
   `make -f victor9k.mak sizes` after any change that could add static data**
   and report the number. For the heap itself,
   `XFLAGS=-DV9K_HEAPREPORT` prints the low-water headroom at exit: a
   working transfer leaves ~2,090 bytes, and the failures this port has hit
   (a file it could not open, a wildcard that matched nothing) were both
   that number reaching zero (PORTING.md §16e, §16f).
5. **Never define `BIGBUFOK`** (asks for 290,000-byte buffers). **Never remove
   `DYNAMIC`** (without it the packet buffers become >64K static arrays and the
   build fails outright).
6. **INT 21h only** for console and files. No INT 10h, INT 16h, INT 14h, direct
   screen memory, or BIOS data area — Victor MS-DOS 3.1 has no IBM-compatible
   BIOS, and that discipline is the whole reason one binary runs on both DOSes.
7. **Watch stack frames.** 16-bit target with a recursive `traverse()` in
   `ckufio.c`. Large automatic arrays are the hazard — that is what
   `SCANFILEBUF` was, and what `CKMAXNAM` turned out to be (`traverse()` was
   1066 bytes/level, now 98). **Run `-fstack-usage` after touching `ckufio.c`,
   `ckuusr.c`, or the size limits in `ckvictor.h`**, the same way you run
   `sizes` for DGROUP.

## Layout of the port

| File | Role |
|---|---|
| `PORTING.md` | design doc, memory budget, hardware map, milestone plan |
| `ckvictor.h` | all ~40 feature `-D` flags, size limits, platform identity |
| `ckvictor.c` | Victor glue: process-model stubs, `opendir`/`readdir`/`closedir` and `ioctl` over INT 21h, a `stat()` for the current directory that libdos-m cannot do (§1a, PORTING.md §16f), the comm-device `read()`/`write()` and the `alarm()` that bounds the read (§0d), the heap-headroom instrument (§0e), the termios half that programs the 7201 and 8253 through the OEM driver's IOCTL block (§1b, PORTING.md §11a), and **the 7201 data path — IRQ1 handler, receive ring, polled transmitter (§1e, PORTING.md §11b)** |
| `victor/sys/termios.h` | the 7201 driver's control surface; fills a newlib gap, reached via `-Ivictor` |
| `victor/sys/ioctl.h` | `FIONREAD` and `TIOCMGET`; without the first `conchk()`/`ttchk()` are hard-wired to 0, and without the second `ttchk()` never reaches `FIONREAD` |
| `victor9k.mak` | ia16-elf-gcc build + `sizes` target |
| `victorow.mak` | Open Watcom build + `sizes` target (PORTING.md §9d) |
| `victorow/` | headers only Open Watcom needs (`pwd.h`, `sys/utsname.h`, `sys/time.h`, `termios.h`, `ckowsys.h`), reached via `-i=victorow` and invisible to the gcc build |
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

- `~/projects/kermit/msr313src` — MS-DOS Kermit 3.13 source, and
  **`msxv90.asm` is the primary reference for §11**: a Victor 9000/Sirius
  serial driver by this same project, for this exact hardware. PORTING.md §11
  takes its integration model wholesale — the OEM `SERIALA` device is a
  *configuration* channel reached by INT 21h `AH=44h AL=02h/03h`, never a data
  path, with the ISR and RX ring ours. `msyv90.asm`/`msuv90.asm` are its screen
  and keyboard halves and are not relevant to this port.
- `~/projects/myfreedos` — FreeDOS port to the Victor. Reference for the
  MS-DOS 3.1 ISR stack-switching prologue and a TX path proven at 38400
  (`kernel/victor_int14.asm`, `kernel/victor_serial_debug.asm`,
  `kernel/victor_pic.asm`, `docs/victor/subsystem-docs/Serial.md`).
- `~/projects/kermit/victor9000` — `vickermit.c`, a 1980s Victor-native Kermit.
  A third opinion on chip init. Where these three disagree, `msxv90.asm` is the
  one that shipped for this machine.
- `~/projects/newlibc/phase3_newlib` — bare-metal Victor newlib. **Out of scope**
  for the current plan (see `PORTING.md` §2), but `libgloss/dirent.c` is a
  reference for `opendir`/`readdir` — note the two defects flagged in §12.

## Working style for this project

State what was measured and what was assumed, and keep them separate — the
existing doc does this and it has already caught one overstated benchmark. When
something is proven on real hardware, say which hardware and which
configuration; "the serial code works at 38400" and "polled TX on channel A has
carried sustained output at 38400" are different claims.

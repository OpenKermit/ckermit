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

`CKERMITW.EXE` is a serial-only, file-transfer-only C-Kermit for the Victor
9000, built with **Open Watcom V2** in the **large** model (far code *and* far
data). It runs as an MS-DOS program that drives the µPD7201 serial chip and the
8259 directly, so a single binary works on both **Victor MS-DOS 3.1** and
**FreeDOS for Victor**. Everything that is not the serial port goes through
**INT 21h only**.

There is **one build**. A second one, `ia16-elf-gcc` + newlib in the medium
model, existed until 2026-08-05 and was retired: one near 64K DGROUP could not
hold the command parser and left ~2K of heap for a transfer. PORTING.md §9d and
§16e keep the measurements; git keeps the code. **Do not reintroduce it** —
including "just to measure something."

## Build

The toolchain lives in the `ia16-ubuntu-2` container, which runs under Apple's
native `container` service — **not Docker**. `~/projects` is mounted at
`/mnt/projects` inside it. Open Watcom V2 is at `/opt/open-watcom-v2/rel`.

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"        # 24 objects + link
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak sizes"  # DGROUP report
```

`ckcpro.c` is generated from `ckcpro.w` by `wart`, a **host** tool built with
the host `cc`.

All 24 modules compile. Warnings are 17 lines, all in stock upstream code and
all pre-existing — `debug()` expanding to nothing under `NODEBUG` (W111),
two unreferenced labels, `localtime()` sign mismatch, `execvp()` const
mismatch, and `docmdline(1)` in `ckcmai.c`. **`ckvictor.c` compiles with
none.** DGROUP is 39,424 of 65,536 (60%) after the linker adds libc;
`ckermitw.exe` is 228,554 bytes.

**It transfers a file.** On Victor MS-DOS 3.1 under MAME it opens
`/dev/seriala`, programs the line through the OEM driver's IOCTL block (§11a),
takes the µPD7201 and IRQ1 over for the data path (§11b), and runs a complete
S/F/A/D/Z/B exchange to a host C-Kermit at 9600 — byte-correct at the far end.
That is PORTING.md **§16d**, and it is milestone step 5. It has never run on
real hardware. A **wildcard** send is the one open defect: `-s *.TXT` expands
correctly in both passes but still fails to transfer (§16f).

The interactive command parser is off (`NOICP`), and the reason is RAM, not
DGROUP: with it in, DGROUP measures 60,768 of 65,536 — it *fits* — but the
image needs 429K and the machine offers 387K. `make -f victorow.mak
XFLAGS=-dKEEP_ICP sizes` re-runs that measurement; `ZT=-zt128` takes DGROUP to
19,376 and does not help the RAM problem. See PORTING.md §9d and §16a.

`XFLAGS=-dKEEP_DEBUG` turns on C-Kermit's debug log (`CKERMITW -d -s FOO.BIN`
writes `./debug.log` on the target). It is affordable here because `-zc` puts
the format strings in far code, and it is **the** instrument for the §16f
wildcard defect.

**PORTING.md §16a is the how-to** — the Victor boots its hard disk as `A:`,
the image needs `vtg_image_util` (mtools cannot read it), and MAME's `-bitb`
socket is single-use, so start `socat` first and never probe the port.

## Hard rules

1. **Do not modify upstream C-Kermit files.** The port's value is that the
   protocol engine is untouched. There are exactly eight guarded upstream
   edits (listed in `PORTING.md` §8); every one is wrapped in `#ifndef` or
   `#ifdef VICTOR9K` and changes nothing on any other platform. If you think
   you need a ninth, say so explicitly rather than doing it quietly — the
   seventh and eighth were both agreed that way.
2. **Feature configuration goes in `ckvictor.h`, never in `victorow.mak`.**
   Each `#define` sits next to a comment explaining why. The makefile passes
   `-fi=ckvictor.h` and nothing else.
3. **Victor-specific C goes in `ckvictor.c`.** It is the only non-upstream C
   file and should stay that way.
4. **Two budgets, and do not confuse them.** DGROUP holds `.data`, `.bss`
   and the **stack** — 39,424 of 65,536 (60%) after the link, 26,112 free.
   The **heap is outside it**: `malloc()` is `_fmalloc` in the large model,
   so the packet buffers do not compete for the segment at all. What bounds
   them is real-mode RAM, ~387K, of which the image uses ~229K.
   **Run `make -f victorow.mak sizes` after any change that could add static
   data** and report the number. Before raising `SBSIZ`/`RBSIZ`/`MAXSP`/
   `MAXRP`, measure the *image*, not DGROUP — PORTING.md §16a has the
   method, and §9 has both budgets side by side.
5. **Never define `BIGBUFOK`** (asks for 290,000-byte buffers). **Never remove
   `DYNAMIC`** (without it the packet buffers become >64K static arrays and the
   build fails outright).
6. **INT 21h only** for console and files. No INT 10h, INT 16h, INT 14h, direct
   screen memory, or BIOS data area — Victor MS-DOS 3.1 has no IBM-compatible
   BIOS, and that discipline is the whole reason one binary runs on both DOSes.
7. **Watch stack frames.** 16-bit target with a recursive `traverse()` in
   `ckufio.c`, and the stack is inside DGROUP. Large automatic arrays are the
   hazard — that is what `SCANFILEBUF` was, and what `CKMAXNAM` turned out to
   be (`traverse()` was 1066 bytes/level, now 98). **Open Watcom has no
   `-fstack-usage`**, so this rule lost its cheap instrument with the gcc
   build: after touching `ckufio.c`, `ckuusr.c` or the size limits in
   `ckvictor.h`, **read the source for new automatics** and, if it matters,
   check the prologue's `sub sp,N` in `wdis` output. Say which you did. The
   stack is 2,048 bytes (`wlink` default, inherited not chosen) — PORTING.md
   §15 argues it should probably be raised.

## Layout of the port

| File | Role |
|---|---|
| `PORTING.md` | design doc, memory budget, hardware map, milestone plan |
| `ckvictor.h` | all ~40 feature `-D` flags, size limits, platform identity |
| `ckvictor.c` | Victor glue, and **no conditional compilation on the compiler**: process-model stubs (§1), `ioctl`/`FIONREAD`/`TIOCMGET` (§0b), the comm-device `read()`/`write()` and the `alarm()` that bounds the read (§0d), the gaps in Watcom's Unix surface — `gettimeofday`, `uname`, `link`, `kill`, `getpw*` (§1d), the termios half that programs the 7201 and 8253 through the OEM driver's IOCTL block (§1b, PORTING.md §11a), and **the 7201 data path — IRQ1 handler, receive ring, polled transmitter (§1e, PORTING.md §11b)** |
| `victor/sys/termios.h` | the 7201 driver's control surface; no DOS libc has one, reached via `-i=victor` |
| `victor/sys/ioctl.h` | `FIONREAD` and `TIOCMGET`; without the first `conchk()`/`ttchk()` are hard-wired to 0, and without the second `ttchk()` never reaches `FIONREAD` |
| `victorow.mak` | the build: Open Watcom `wcc`/`wlink` + `sizes` target |
| `victorow/` | headers filling gaps in Open Watcom's DOS libc (`pwd.h`, `sys/utsname.h`, `sys/time.h`, `termios.h`, `ckowsys.h`), reached via `-i=victorow` |
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
- `~/projects/newlibc/phase3_newlib` — bare-metal Victor newlib. **Out of
  scope** (see `PORTING.md` §2), and doubly so now that the port no longer
  uses newlib at all. Kept in this list only because `PORTING.md` §12 cites
  its `libgloss/dirent.c` and the two defects flagged there.

## Working style for this project

State what was measured and what was assumed, and keep them separate — the
existing doc does this and it has already caught one overstated benchmark. When
something is proven on real hardware, say which hardware and which
configuration; "the serial code works at 38400" and "polled TX on channel A has
carried sustained output at 38400" are different claims.

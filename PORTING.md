# Porting C-Kermit 11 to the Victor 9000 / Sirius 1

Running notes for the serial-only Victor 9000 port. Branch: `victor9k-port`.

**Status:** **it transfers a file.** All 24 modules build clean; the binary
runs on Victor MS-DOS 3.1 under MAME, drives the µPD7201 through the driver in
§11b, and completes a Kermit send to a host C-Kermit at 9600 — milestone step 5
(§13, §16d). Under emulation only; nothing here has run on a real Victor.

**Toolchain:** **Open Watcom V2, large model, and only that** — `victorow.mak`.
A second build with `ia16-elf-gcc` + newlib in the medium model existed from
the start of the port until **2026-08-05**, and it worked: it compiled the same
24 modules and completed the same transfer (§16e). It was retired because one
near 64K DGROUP is the wrong shape for this program — it cost the interactive
command parser outright (§9c) and left ~2K of heap for a transfer (§16e, §16f).
The measurements it produced are kept below, marked as history; the code is in
git. **Sections that compare the two toolchains are a record of a closed
question, not a live one.**

**Verdict:** this is a thin-platform port, not a rewrite. The blocker people
expect — a modern flat-memory codebase that cannot be squeezed into 64K — did
not materialise. DGROUP after the link, including libc, is **48,176 bytes of
65,536 (73%)**, with the protocol engine untouched. (39,424 / 60% before the
8K stack of §16j and the 4K receive ring of §16k.)

---

## 1. Why this works at all

C-Kermit was written in 1985 for machines smaller than this one and never
stopped being buildable on them. The tree still carries:

- `ckubs2.mak` — PDP-11 2.11BSD, 16-bit `int`, 64K I/D split, overlays.
- `#ifdef pdp11` blocks in `ckcker.h` that shrink windows and packet buffers.
- A `minix` target for 16-bit 8086.
- `V7MIN`, a "smallest possible build" configuration.

The protocol core is deliberately isolated in the `ckc*.c` files and talks to
the world through a documented function interface (`ttinc`, `ttoc`, `zopeni`,
`conoc`, ...). That boundary is the whole reason this port is cheap.

Two historical warnings are worth heeding, because they are about *data*, not
code: `ckubs2.mak` says C-Kermit 7.0 could no longer fit an interactive parser
on the PDP-11, and the makefile marks the 16-bit `minix` target "too big". Both
refer to a single 64K address space for code **and** data. We have far code
(medium model), so only the data half of that warning applies to us — and the
measurements in §9 say we clear it.

---

## 2. Target: one binary, two operating systems

`CKERMITW.EXE` is an **MS-DOS program that drives the Victor's serial hardware
directly.** It is launched from a DOS prompt, seizes the µPD7201 and the 8259's
serial IRQ for the duration of the run, and hands them back on exit.

It is designed to run unmodified on **both**:

- **Victor MS-DOS 3.1** — the machine's native OS.
- **FreeDOS for Victor** (`~/projects/myfreedos`) — the modern port.

That dual-target property is not aspirational. Everything Kermit touches on the
serial path is fixed by the Victor's wiring, not by OS convention:

| Resource | Address | Varies by OS? |
|---|---|---|
| µPD7201 MPSC, channel A | `0xE000:0040` data, `0xE000:0042` ctrl/RR0 | no — wiring |
| µPD7201 MPSC, channel B | `0xE000:0041` data, `0xE000:0043` ctrl/RR0 | no — wiring |
| 8253 Counter 0 — channel A baud | `0xE000:0020`, ctrl `0xE000:0023` | no — wiring |
| 8253 Counter 1 — channel B baud | `0xE000:0021` | no — wiring |
| 8253 Counter 2 — system tick | — | no — wiring |
| VIA2 (6522) clock enables | `0xE800:0041` PA0=chA, PA1=chB (LOW=internal) | no — wiring |
| 8259 PIC, memory-mapped | `0xE0000`–`0xE0001` | no |
| **Serial IRQ1 → IVT slot** | — | **YES — see below** |

**Exactly one thing differs between the two platforms: the interrupt vector.**

| Environment | PIC `ICW2` | IRQ1 (serial) lands on |
|---|---|---|
| Victor boot ROM | `0x20` | INT 21h–27h range (IRQ1 = INT 21h) |
| **Victor MS-DOS 3.1** (BIOS `IRQ.LST`) | `0x40` | **INT 41h** |
| **FreeDOS for Victor** (`kernel/victor_pic.asm`) | `0x08` | **INT 09h** |

So the driver must resolve its vector at startup rather than hardcoding it.
Detect the host with INT 21h AH=30h — FreeDOS reports OEM `0xFD` in BH — and
hook `0x09` or `0x41` accordingly. **Do not** probe by hooking both: under the
FreeDOS port INT 41h may already hold the fixed-disk parameter *table* pointer,
and writing a code vector over a data vector is an ugly way to fail.

Note that 8253 Counter 2, not Counter 0 or 1, is the system tick (FreeDOS routes
it IR2 → INT 0Ah). Reprogramming Counter 0 for 38400 therefore does **not**
disturb DOS timekeeping on either platform. `SET SPEED` is free to write the
divisor.

### The discipline that makes dual-target hold

Owning the serial hardware gets you half of it. The other half is a rule:

> **Everything that is not the serial port goes through INT 21h. No INT 10h,
> no INT 16h, no INT 14h, no direct screen memory, no BIOS data area.**

Victor MS-DOS 3.1 has no IBM-compatible BIOS video or keyboard. The FreeDOS
port supplies some. Targeting the intersection is what lets one binary run on
both, and it costs almost nothing here:

- **Console** — C-Kermit's entire console surface is seven small functions
  (`conoc`, `conol`, `coninc`, `conchk`, `congm`, `concb`, `conres`). All map
  onto INT 21h AH=06h/07h/08h/0Bh.
- **Files** — the DOS 2.0 handle API (`3Ch`/`3Dh`/`3Eh`/`3Fh`/`40h`/`42h`),
  directory search (`4Eh`/`4Fh`), cwd (`47h`/`3Bh`), mkdir/rmdir (`39h`/`3Ah`),
  file times (`57h`). All present in 3.1. Avoid long filenames (`71xx`) and
  anything DOS 4.0+.
- **INT 23h / INT 24h** — install Ctrl-Break and critical-error handlers, so a
  floppy error mid-transfer does not drop the user into "Abort, Retry, Fail"
  underneath a live protocol.

### Consequences of this decision

- The bare-metal newlib in `~/projects/newlibc/phase3_newlib` — its VFS, FAT
  driver, SASI block layer, crt0, and linker script — is **out of scope.** It is
  a fine piece of work and a possible later target, but it is not on the path to
  this milestone.
- The FreeDOS `INT 14h` driver (`kernel/victor_int14.asm`) is **not used** as an
  API. Its guts are reused as source (see §12), but Kermit does not call it:
  INT 14h AH=00h cannot express any speed above 9600, and it offers no
  "how many bytes are queued" call, which is exactly what `ttchk()` needs.

---

## 3. Toolchain and memory model

Built with **Open Watcom V2** (`wcc`/`wlink`, 16-bit, at
`/opt/open-watcom-v2/rel`) inside the `ia16-ubuntu-2` container, which runs
under Apple's native `container` service — **not Docker**. `~/projects` on the
host is mounted at `/mnt/projects` inside.

```sh
container list --all                                   # ia16-ubuntu-2, running
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"
```

The model is **large**: far code *and* far data. Concretely, three things
follow, and they are the reason this is the toolchain:

- `-zc` puts string literals in far code segments. `.rodata` is the single
  biggest consumer of static data in C-Kermit, and in the large model it
  leaves DGROUP entirely: `CONST` + `CONST2` measure **1,366 bytes**.
- `malloc()` is `_fmalloc` — the **far heap**, outside DGROUP. C-Kermit's
  `DYNAMIC` packet buffers stop competing with static data altogether. What
  bounds them is the 387K the machine offers, not the segment.
- DGROUP holds `.data`, `.bss` and the stack, and nothing else: **48,176 of
  65,536 (73%)** after the link, including libc. It was 39,424 / 60% until
  §16j chose an 8,192-byte stack and §16k a 4,096-byte receive ring.

`-zt<n>` is available and not used by default: it moves data objects of *n*
bytes or more into per-module far data segments. It is worth more than `-zc`
because it moves the keyword *tables*, not just the strings they point at.
See §9d for what it measures.

### History: the toolchain this replaced

Until 2026-08-05 the tree also built with `ia16-elf-gcc 6.3.0` (tkchia's
`ppa:tkchia/build-ia16`) via `victor9k.mak`, in the medium model. That compiler
supports only `-mcmodel=tiny|small|medium` — there is **no compact, large, or
huge model**, verified directly:

```
tiny OK   small OK   medium OK
compact  error: unrecognized command line option '-mcmodel=compact'
large    error: unrecognized ...
huge     error: unrecognized ...
```

So data pointers were always near, and `.data` + `.bss` + heap + stack all had
to fit in one 64K DGROUP. It reached 52,728 of 65,536 (80%) with the
interactive command parser removed to make it fit at all (§9c), leaving 12,808
bytes for heap *and* stack — and §16e measured a transfer completing with about
2,090 bytes of that left. §9d is the comparison; §16e and §16f are where the
near heap stopped being a budget and became a defect.

It is retired, not deleted: `git log` on this branch has `victor9k.mak`,
`ckvictor.c`'s newlib sections, and the inline-assembly INT 21h layer.

---

## 4. Build

```sh
make -f victorow.mak          # build all objects, then link
make -f victorow.mak sizes    # DGROUP report, read from wlink's map
make -f victorow.mak clean
```

The entire feature configuration lives in `ckvictor.h`, force-included ahead of
every file with `-fi=ckvictor.h`. Nothing else in the tree includes it, so it
cannot affect any other platform. Keep new `-D` options *there*, next to the
comment explaining why they exist — not in the makefile.

Two directories are on the include path and nowhere else. `victor/` holds
headers that fill gaps in the toolchain, reached via `-i=victor`:
`victor/sys/termios.h` and `victor/sys/ioctl.h` (§12). `victorow/` holds the
ones specific to Open Watcom's libc, reached via `-i=victorow` (§9d). Same
principle as `ckvictor.h`: on the include path only for this build, so neither
can affect anything else.

---

## 5. Source files: in and out

### In (24 modules)

Per-module sizes are from the retired gcc build and are kept because they are
the only per-module breakdown anyone has taken; the *relative* picture is what
they are useful for. The current build reports whole-program figures only, from
`wlink`'s map — see §4 and §9d.

| Module | Role | text | data+bss |
|---|---|---:|---:|
| `ckcmai.c` | main, initialization | 6480 | 1868 |
| `ckclib.c` | portable string/utility library | 13930 | 1526 |
| `ckcfns.c` | protocol support functions | 21600 | 12036 |
| `ckcfn2.c` | more protocol functions | 10685 | 170 |
| `ckcfn3.c` | packet buffer management | 7934 | 1141 |
| `ckcpro.c` | protocol state machine (from `ckcpro.w`) | 25318 | 1708 |
| `ckucmd.c` | command parser | 32749 | 2932 |
| `ckuusr.c` | command tables, top-level commands | 22170 | 3540 |
| `ckuus2.c` | help text (≈0 under `NOHELP`) | 467 | 14 |
| `ckuus3.c` | SET commands | 20355 | 1870 |
| `ckuus4.c` | more commands | 16344 | 492 |
| `ckuus5.c` | SHOW commands | 26312 | 2432 |
| `ckuus6.c` | more commands | 23453 | 1914 |
| `ckuus7.c` | more SET commands | 26051 | 1620 |
| `ckuusx.c` | screen / file-transfer display | 11014 | 350 |
| `ckuusy.c` | command-line arguments | 11799 | 274 |
| `ckutio.c` | **serial + console + timers** | 12318 | 3148 |
| `ckufio.c` | **file system** | 15760 | 2932 |
| `ckusig.c` | signal handling | 202 | 2 |
| `ckuxla.c` | charset translation — **0 bytes** under `NOCSETS` | 0 | 0 |
| `ckcuni.c` | Unicode — **0 bytes** under `NOUNICODE` | 38 | 2 |
| `ckcnet.c` | networking — ~0 under `NONET`, kept for symbols | 71 | 266 |
| `ckctel.c` | telnet — ~0 under `NONET`, kept for symbols | 38 | 4 |
| `ckvictor.c` | **Victor glue (new, the only non-upstream C file)** | 326 | 4 |

`ckcpro.c` is generated from `ckcpro.w` by `wart`, which is a *host* tool.
Build it with the host compiler (`cc -DSIGTYP=void -o wart ckwart.c`; the
`-DSIGTYP=void` avoids a `sig_t` clash with macOS `<sys/signal.h>`).

`ckuxla.c` and `ckcuni.c` compiling to literally zero bytes is the single
biggest win in the configuration — `ckcuni.c` alone is 770KB of source, almost
entirely translation tables.

### Out

| Module | Size | Why |
|---|---:|---|
| `ckcftp.c` | 558KB | FTP client |
| `ckcnet.c` bulk | 493KB | sockets, TCP/IP |
| `ckuath.c` | 410KB | Kerberos / authentication |
| `ck_ssl.c` | 174KB | SSL/TLS |
| `ck_crp.c` | 165KB | encryption |
| `ckctel.c` bulk | 290KB | telnet protocol |
| `ckudia.c` | 238KB | modem dialing + modem database |
| `ckupty.c` | 50KB | pseudo-terminals (needs `fork`) |
| `ckucon.c` / `ckucns.c` | 81/78KB | CONNECT — one needs `fork()`, the other `select()` on a tty; neither is usable. See §13. |
| `ckuscr.c` | 18KB | UUCP-style scripting |
| `ckcmdb.c` | 7KB | malloc debugging |

---

## 6. Platform abstraction boundaries

This is the map that makes the port cheap. Everything Victor-specific is
reachable from four files.

| Concern | Module | Notes |
|---|---|---|
| Serial / TTY I/O | **`ckutio.c`** | `ttopen`, `ttclos`, `ttpkt`, `ttinc`, `ttinl`, `ttoc`, `ttol`, `ttsspd`, `ttflui`. POSIX termios — see §12. |
| Console / keyboard | **`ckutio.c`** | `coninc`, `conchk`, `conoc`, `conol`, `congm`, `concb`, `conres`. |
| Timers | **`ckutio.c`** | `rtimer`, `gtimer`, `ztime`. |
| File system | **`ckufio.c`** | `zopeni`, `zopeno`, `zinfill`, `zsoutx`, `zclose`, `zchki`, `zchdir`, directory walk. |
| Signals | `ckusig.c` + `ckcsig.h` | Tiny (202 bytes). |
| Networking | `ckcnet.c`, `ckctel.c` | Compiled out. |
| Terminal emulation / CONNECT | `ckucon.c`, `ckucns.c` | Excluded. |

**`ckutio.c` and `ckufio.c` are the port.** Everything above them is unmodified
upstream code. Everything below them is the Open Watcom DOS runtime plus
`ckvictor.c`, which fills its gaps (§12).

---

## 7. Feature flags

All in `ckvictor.h`, grouped with rationale. Summary:

- **Networking:** `NONET NOTCPIP NOSSH NOFTP NOHTTP NOIKSD NORLOGIN NOURL NOBROWSER`
- **Charsets:** `NOCSETS NOUNICODE` ← biggest win
- **Process model:** `NOPTY NOPUSH NOJC NOREDIRECT`
- **Dialing:** `NODIAL MINIDIAL NOLOGDIAL`
- **Scripting/UI:** `NOSPL NOSCRIPT NOSEXP NOLEARN NOHELP NORECALL NOSETKEY NOKVERBS NOXMIT NOMSEND NOFRILLS NOCCTRAP`
- **Logging:** `NODEBUG NOTLOG NOSYSLOG NOCURSES NOTERMCAP NOESCSEQ`
- **Misc:** `NOREALPATH NOTIMEZONE NORANDOM NOUUCP NOWTMP NOPARSEN`

Deliberately **not** defined, because they are the point of the port:
`NOICP` (command parser), `NOXFER`, `NOSERVER`, `NOLOCAL`, `NOLP` (long
packets), `NOWINDOW` (sliding windows), `NORESEND` (restart), `NOSTREAMING`.

Note `V7MIN` exists upstream and looks tempting, but it implies `NOICP`, which
would remove the `C-Kermit>` prompt. Not usable here.

Streaming is **not** network-coupled — it is negotiated protocol behaviour in
`ckcfns.c`/`ckcpro.c` and survives `NONET` intact.

---

## 8. Upstream changes made

Eleven small, guarded edits. None changes behaviour on any other platform.

1. **`ckcdeb.h`** — wrapped the `sig_t` typedef in `#ifndef CK_NO_SIG_T`.
   macOS (and the retired build's newlib) already define `sig_t`. Open Watcom
   does not, so this build leaves `CK_NO_SIG_T` undefined and takes upstream's
   own typedef; the guard is what makes both answers possible.
2. **`ckcker.h`** — wrapped `SCANFILEBUF` in `#ifndef`. It was hard-coded to
   49152 and is used as an **automatic array**, i.e. a 48K stack frame. Fatal
   on a 64K DGROUP; now `-DSCANFILEBUF=2048`.
3. **`ckcfns.c`** — wrapped `RQ_MAXTOK` in `#ifndef`. `rq_tok` is
   `RQ_MAXTOK * (CKMAXPATH+1)` and was the largest static object in the
   program at 9280 bytes; now 2064.
4. **`ckucmd.c`** — added a `VICTOR9K` branch so console input goes through
   `coninc()`/`conchk()` instead of reaching into glibc `FILE` internals
   (`stdin->_IO_read_ptr`), which exist in no libc this port has used.
5. **`ckufio.c`** — added a `VICTOR9K` branch to the directory-entry inode
   check, alongside the existing `Plan9` one. FAT has no inode.
6. **`ckcfnp.h`** — wrapped `void fxdinit( int );` in `#ifndef NODISPLAY`.
   Two lines earlier in the *other* direction, `ckcker.h` already does this:

   ```c
   #ifdef NODISPLAY
   #define fxdinit(a)
   #else
   _PROTOTYP( VOID fxdinit, (int) );
   #endif /* NODISPLAY */
   ```

   so under `NODISPLAY` — which `ckcdeb.h` sets for every `NOCURSES` build —
   the prototype in `ckcfnp.h` expands through that macro to the declaration
   `void ;`. Open Watcom calls that E1026 and stops, in all 15 modules that
   include `ckcfnp.h`. (gcc called it a useless-type-name warning and carried
   on, which is why the edit only became necessary at §9d.) It is a genuine
   upstream inconsistency rather than a Victor accommodation: a platform that
   does not define `NODISPLAY` sees no change at all.

7. **`ckufio.c`** — wrapped `SSPACE` in `#ifndef`, matching what `ckcker.h`
   already does for `SBSIZ`, `RBSIZ`, `MAXSP` and `MAXRP`; now
   `-DSSPACE=2048`. `initspace()` asks malloc for `SSPACE` and, when
   refused, halves the request and retries, **keeping whatever it finally
   gets**. Where the heap is large that is a good bargain. Where the heap was
   the 12K left over inside one 64K DGROUP it was the opposite: the default
   10,000 took the whole thing and every allocation after it failed (§16f).
   The far heap makes that specific failure unlikely, but a fixed allocation
   is still the right shape and the guard is worth having upstream.
8. **`ckcdeb.h`** — wrapped the UNIX `MAXWLD` in `#ifndef`; now
   `-DMAXWLD=64`. `zxpand()` allocates `maxnames` pointers *before* it reads
   the first directory entry, so 1024 is a 2,048-byte malloc whether the
   pattern matches two files or none. §16f.

9. **`ckcdeb.h`** — `#undef NLCHAR` for `VICTOR9K`, in the block that
   already does exactly this for OS/2 and the Atari ST, and directly under
   the comment that asks for it:

   ```
   At this point, if there's a system that uses ordinary CRLF line
   delimitation AND the C compiler actually returns both the CR and
   the LF when doing input from a file, then #undef NLCHAR.
   ```

   Both halves of that condition are true here once the runtime is in
   binary mode, so `feol` becomes 0 and `ckcfns.c` stops converting
   CRLF to LF and back. It is not an accommodation — it is upstream's own
   configuration for a CRLF platform, and the port was silently miscategorised
   as a single-terminator one until §16h. Measured on the target as
   `MAIN feol=0`. **Not correct alone**: it is one half of a pair with
   `ckvictor.c`'s `_fmode` initializer, and either half without the other
   changes which of text and binary transfers is broken rather than fixing
   anything.

10. **`ckcfnp.h`** — wrapped the `ckround()` and `fpformat()` prototypes in
    `#ifdef CKFLOAT`. This is the sixth edit's defect again, in the same
    file and for the same reason: `ckcfnp.h` declares them with a type that
    `NOFLOAT` deletes, while both definitions are **already** guarded —
    `ckclib.c` wraps `isfloat()` and `ckround()` in `#ifdef CKFLOAT` (lines
    2012–2209) and `ckuus4.c` wraps `fpformat()` (line 8029). So upstream's
    own `NOFLOAT` cannot compile in this tree at all, on any platform, and
    the guard is what makes the switch usable rather than a Victor
    accommodation. No other build defines `NOFLOAT`, so nothing changes
    anywhere else.

    What it buys here is the largest single saving in the port's history:
    the 8088 has no 8087, every float goes through Open Watcom's software
    emulator, and dropping `emu87.lib`/`math87l.lib` takes **26,586 bytes**
    off what the image needs at load. §16j.

11. **`ckcker.h`** — wrapped `DRPSIZ`, `DFWSIZ` and `DFBCT` in `#ifndef`,
    the same shape as edits 2, 3, 7 and 8 and matching what that same file
    already does for `SBSIZ`, `RBSIZ`, `MAXSP` and `MAXRP` a few lines
    below; now `DRPSIZ=4000`, `DFWSIZ=1`. No other build defines any of the
    three, so nothing changes elsewhere.

    These initialise `urpsiz` (RECEIVE PACKET-LENGTH) and `wslotr` (WINDOW),
    which `rpar()` encodes into every S and I packet. On most platforms
    nobody overrides them because `dofast()` recomputes both at startup —
    but `dofast()` is inside the `#ifndef NOTCPIP` that opens at
    `ckcmai.c:3390` and does not close until 3644, so a serial-only build
    never calls it and these values are the only thing that reaches the
    wire. Without this edit the port negotiated 90-byte packets for its
    entire history while believing the four capacity symbols controlled it.
    §16j.

Items 2, 3, 6, 7, 8, 10 and 11 are worth offering upstream regardless of this
port.
2, 3, 7 and 8 are latent hazards on any small-memory target — and 7 and 8
share a shape worth naming: an allocation sized for comfort, failing
silently, on a code path whose error message needs its own allocation to be
printed. 6 and 10 are the same defect twice in the same file — a prototype
in `ckcfnp.h` that is not guarded the way its own definition is — and 10 is
the more serious of the pair, because it makes an upstream configuration
switch (`NOFLOAT`) uncompilable everywhere rather than only under one
combination of flags.

---

## 9. Memory budget

Measured from `wlink`'s map, 24 modules, `-ml -0 -os -zc`, **including libc**
(`make -f victorow.mak sizes`):

```
CONST      956  |
CONST2     410  |  string literals that did NOT go far
_DATA   18,258  |
_BSS    17,612  |
STACK    2,048  |
DGROUP  39,424 of 65,536  (60%)     26,112 left in the segment
far code   193,400                  outside DGROUP, ~1MB limit — not a concern
far data         0                  none needed yet
ckermitw.exe   228,554 bytes
```

The heap is **not in this table**, and that is the whole point of the large
model: `malloc()` is `_fmalloc`, so `SBSIZ`/`RBSIZ` and every other runtime
allocation come from the far heap. What bounds them is the ~387K the machine
gives a program (§16a), not the 26,112 bytes left in DGROUP.

So there are two separate budgets now, and confusing them is the mistake this
section exists to prevent:

| Budget | Ceiling | What is in it | Headroom |
|---|---:|---|---:|
| DGROUP | 65,536 | `.data`, `.bss`, **stack** | 26,112 |
| Real mode | ~387K | far code, far data, **heap** | ~158K |

`ckvictor.h` still sets `MAXSP`/`MAXRP` to 1024 and `SBSIZ`/`RBSIZ` to 2048
rather than the `DYNAMIC` defaults of 9024/9050 — not because DGROUP demands
it any more, but because 2048 is what a completed transfer has been measured
at (§16d) and raising it is a step-8 decision to make with a measurement.

If DGROUP headroom is ever needed: `-zt<n>` is the lever, and it is large.
`-zt1024` takes the parser build from 60,768 to 42,528 and `-zt128` to 19,376
(§9d). It costs a segment load per access on an 8088, which is why it is off.

**History.** The retired gcc build measured `.text` 302,896 / `.data` 11,748 /
`.bss` 20,563 = 32,311 static DGROUP before libc, 52,728 (80%) after — with
only 12,808 bytes for heap **and** stack together, since both lived in the same
segment. That single number is most of why §9c, §9a, §9b, §16e and §16f exist.

### 16-bit portability audit

Measured under the Victor configuration, not assumed.

| Issue | Finding |
|---|---|
| `int` is 32 bits | Not assumed. Builds clean at `int` = 16 bits. |
| Objects > 64K | **None.** Largest static object is now `rq_tok` at 2064 bytes. |
| `malloc` > 64K | Avoided. `-DUNIX` makes `ckcdeb.h` define `DYNAMIC`, which turns `bigsbuf`/`bigrbuf` into malloc'd pointers. Without `DYNAMIC` they are `CHAR bigsbuf[SBSIZ+5]` with `SBSIZ = MAXSP*(MAXWS+1) = 2048*33 = 67584` — **over 64K, would not compile**. Do not remove `DYNAMIC`. |
| `BIGBUFOK` | **Never define it.** It asks for 290000-byte buffers. |
| Huge stack frames | `scanfile()`'s 48K automatic array — fixed, now 2088 bytes. |
| Pointer→int casts | Only 4 sites across the whole minimal build; none load-bearing. |
| Varargs | Not used by the protocol core. |
| Flat-address assumptions | None found in the modules that compile. |

Type sizes under this build: `int` 2, `long` 4, **pointer 4 (far, both code
and data)**, `size_t` 2, `CK_OFF_T` = `off_t`.

`CK_OFF_T` is the file-offset type used for RESEND/REGET restart. On a 16-bit
target it resolves to the libc's `off_t`, and if that were `int` rather than
`long`, restart would break above 32KB. **Verified: `sizeof(off_t) == 4`**
(static-assert probe; checked under gcc's medium model, and Watcom's
`<sys/types.h>` declares `off_t` as `long` likewise). Restart is good to 2GB,
far beyond any Victor disk. This question is closed.

Open risks:

1. ~~**`traverse()` in `ckufio.c` is recursive with a 1066-byte stack
   frame.**~~ **Fixed: 98 bytes/level.** See "The `CKMAXNAM` trap" below.
2. `shofea()` (`ckuus5.c`) has the largest frame at 2106 bytes — SHOW FEATURES.
   Harmless but worth knowing.
3. `zcopy()` (`ckufio.c`) is 1114 bytes, essentially all of it `char buf[1024]`
   — a file-copy buffer. Not recursive and reached only from the COPY command
   at top level, so it is a ceiling on peak stack rather than a multiplier.
4. Path lengths: `CKMAXPATH` set to 128. Fine for FAT 8.3, and it feeds several
   table sizes, so do not raise it casually.

### The `CKMAXNAM` trap

The largest stack win in the port, and it was hiding behind a default that
looked deliberate.

`CKMAXNAM` is the longest single filename *segment*. `ckcdeb.h` derives it from
`MAXNAMLEN`, but **`ckcdeb.h` is parsed before `<dirent.h>`**, so `MAXNAMLEN`
is not yet defined and it falls through to `FILENAME_MAX` — which newlib puts
at **1024**. `traverse()` then declares `char nambuf[CKMAXNAM+4]` as an
automatic, and `traverse()` is the recursive directory walk.

Measured with `-fstack-usage`, same source, same flags:

| `CKMAXNAM` | `traverse()` frame | depth-8 walk |
|---|---:|---:|
| 1024 (what the default actually produced) | 1066 bytes/level | 8,528 bytes |
| **16 (now set in `ckvictor.h`)** | **98 bytes/level** | **784 bytes** |

An 11x reduction on the one function whose cost multiplies. 16 is chosen
against FAT 8.3 — the longest legal name is 12 characters — and this port does
not do long filenames, because `readdir()` is DOS FindFirst underneath and
that returns 8.3 and nothing else.

The frame numbers above were taken with gcc's `-fstack-usage` on the retired
build. **The lever is not toolchain-specific — the stack is inside DGROUP in
every memory model — but Open Watcom has no `-fstack-usage` equivalent, so
there is currently no cheap way to re-measure a frame.** That is a real gap
left by the toolchain change; the closest substitute is reading `wdis` output
for the function's prologue. Until something better exists, treat "does this
add a large automatic array?" as a question to answer by reading the source,
and keep the discipline: **check `ckufio.c`, `ckuusr.c` and the size limits in
`ckvictor.h` for automatics before changing them.** Two frames were above 1KB
under gcc (`docmd` 1152, `zcopy` 1114); both are non-recursive.

`MAXNAMLEN` itself is pinned at 12 in `ckvictor.h`. Under the retired build it
was a heap saving, because `struct dirent` doubled as the DOS DTA for the
`readdir()` this port supplied (§12) and newlib's 259-byte default made it a
290-byte struct. Watcom's `<dirent.h>` sizes `d_name[]` from its own
`NAME_MAX`, which is already 12 for DOS, so the define no longer changes any
layout — what it still does is act as the **feature test** `ckufio.c` (~353)
and `ckutio.c` (~212) branch on, and as `ckcdeb.h`'s fallback source for
`CKMAXNAM`. Keep it defined.

---

## 9c. `.rodata` is in DGROUP, and it cost us the command parser

> **History — the retired `ia16-elf-gcc` build.** Everything in this section
> is about the medium model, where every `char *` was near. It is kept because
> it is the argument that produced `NOICP`, and `NOICP` is still on: the
> parser now fits in DGROUP under Open Watcom and does **not** fit in the
> machine's RAM (§9d, §16a). Different wall, same outcome.

**This section supersedes the headline number in §9 *as it stood then*.** The
49.3% figure was real but it was not the whole budget, and the shortfall is
not small.

`make sizes` measures `.data` and `.bss` from `ia16-elf-size`. That tool
reports in Berkeley format, where **`.rodata` is counted in the `text`
column** — so every string literal in the program was being filed under "far
code, 1MB limit, not a concern". It is not far. There is no compact, large or
huge model in `ia16-elf-gcc` (only `tiny`, `small`, `medium` — verified with
`-print-multi-lib`), so a `char *` is always a 16-bit near pointer and
everything it can point at must live in the one 64K DGROUP.

The arithmetic is exact:

```
fartext 236,957  +  rodata 66,578  =  303,535   <- what "text = 303535" was
```

So the real near-data requirement, with the interactive command parser in:

| | bytes |
|---|---:|
| `.rodata` | 66,578 |
| `.data` | 11,748 |
| `.bss` | 20,563 |
| **total near** | **98,889** |
| DGROUP | 65,536 |

`.rodata` **alone** exceeds DGROUP. The linker agrees: `region dsegvma
overflowed by 32816 bytes`.

### What was tried

- **`--gc-sections`** with `-ffunction-sections -fdata-sections`: **zero
  effect**, byte for byte. Everything is reachable from the command tables.
- **A far-data model**: does not exist in this toolchain.
- **`__far` on the literals**: supported by the compiler, and the linker
  script even has `.farrodata.*` output sections — but it needs the qualifier
  on each object, which means editing upstream everywhere. Ruled out by hard
  rule 1.

### What was done: `NOICP`

43KB of the 66.5KB of `.rodata` is the command parser's tables and messages,
concentrated in `ckuus3`–`ckuus7`. Removing it is the only thing that fits:

| | `.rodata` | `.data` | `.bss` | near total |
|---|---:|---:|---:|---:|
| with parser | 66,578 | 11,748 | 20,563 | 98,889 |
| **`NOICP`** | **22,530** | **3,930** | **13,785** | **40,245** |

**This is a real loss.** §13's milestone was "`C-Kermit>` prompt, then SEND".
There is no prompt. What survives is the command-*line* parser in `ckuusy.c`,
which is enough to move a file:

```
CKERMIT -l COM1 -b 9600 -s FOO.BIN
CKERMIT -l COM1 -b 9600 -r
CKERMIT -l COM1 -b 9600 -x          (server)
```

If the prompt is wanted later, the honest options are a different toolchain
with a large data model (§9a already looked at Watcom for the buffers; this
is a much stronger reason), or a hand-written minimal parser in `ckvictor.c`
that reuses none of `ckuus3`–`ckuus7`.

**That first option is what happened**, and it is the reason the tree now
builds with Open Watcom and nothing else. It moved the wall rather than
removing it: see §9d and §16a.

### Heap and stack share what is left, and it is tight

`NOICP` alone still did not link — near data came to 66,272, over by 736.
**`-mnewlib-nano-stdio`** (newlib's reduced printf/scanf) was worth **14,272
bytes** and is now mandatory in both `CFLAGS` and `LDFLAGS`; without it the
build fails at the link.

Final layout, from the linker's own map rather than from `size`:

```
.data + .bss end   52,000
DGROUP             65,536
heap + stack       13,536      <- shared: heap grows up, stack grows down
```

`-mstack-size=` does **not** apply here (it is ELKS-only); the MZ linker
script fills DGROUP to 64K and starts SP at the top.

13,536 bytes for both is genuinely tight, and it bit immediately — see §16.
`SBSIZ`/`RBSIZ` are 2048 each rather than 4096 for this reason.

---

## 9a. Can we put the buffers and stack in their own segments?

> **History, and half-answered.** This section compared two toolchains when
> both were live. The buffer half is now moot: the large model puts `malloc()`
> on the far heap, so the packet pool is already outside DGROUP with no source
> change at all. What remains live is the **stack** half — `-zu` — and the
> `-zt<n>` threshold, both still available and both still unused.

Yes. Both toolchains could, and it was tested rather than assumed. The
question was what it costs and whether it is needed yet.

### What each toolchain supported

| Capability | `ia16-elf-gcc` | OpenWatcom `wcc` |
|---|---|---|
| Extra data segments | `__far` keyword; emits real `.fardata` sections (verified: a 20000-byte `__far` array landed in its own `.fardata` section) | `-mc` / `-ml` / `-mh`: **all** data pointers far (verified 4 bytes) |
| Automatic placement of big objects | none — every object must be annotated by hand | **`-zt<n>`**: objects ≥ n bytes move to `FAR_DATA` automatically. Verified: at `-zt32767` two 20000-byte arrays stayed in `_BSS`; at `-zt1000` a `FAR_DATA` segment appeared and they left DGROUP. |
| Source changes required | **yes**, at every pointer that touches the object | **none** |
| Single object > 64KB | no | yes with `-mh` (a 100,000-byte array compiled) |
| Stack in its own segment | `-mno-callee-assume-ss-data-segment` (documented "experimental") | `-zu` (SS != DGROUP) |

The stack case is more interesting than it first looks. In small/medium models
SS **must** equal DS, because a near pointer to a stack local is just a 16-bit
offset and gets dereferenced through DS. But in compact/large/huge, data
pointers are already far, so `&local` carries SS explicitly and stays valid
with SS != DGROUP. Verified: `-ml -zu` on a function passing a pointer to a
local produced a byte-identical object to `-ml` alone.

So **Watcom large model + `-zu` genuinely gives the stack its own 64K segment,
safely, with no source changes.** That option is still on the table and still
unexercised; `-zu` is not in `victorow.mak`.

### Why we are not doing it yet

1. **There is no pressure.** DGROUP is 39,424 of 65,536 (60%) *including* the
   2,048-byte stack and libc, the packet pool is on the far heap and not in
   this segment at all, and nothing anywhere is over 64KB. (Point 1 as
   originally written measured 32,325/49% static under gcc, before libc.)
2. **The stack is not the problem.** Largest measured frame is 2,106 bytes and
   total stack need is ~8KB — about 12% of the budget.
3. **Far access is expensive under ia16-gcc specifically** — see §9b. Short
   version: gcc cannot keep a far buffer segment and DGROUP addressable at the
   same time, so in a loop that touches both buffers *and* globals it reloads
   `%ds` twice per iteration. That is the inner byte loop of the packet filler,
   and at 38400 on an 8088 with a 4-byte prefetch queue a `mov ds,` per
   iteration is not affordable.
4. **The `__far` blast radius is not local.** The pool is handed out as
   `s_pkt[i].pk_adr`, a plain `CHAR *`, and from there flows through 139+
   `CHAR *` sites across `ckcfns.c` / `ckcfn2.c` / `ckcfn3.c` / `ckcpro.c`.
   Annotating "just the buffers" means annotating the whole protocol engine —
   exactly the upstream divergence this port is trying to avoid.

Points 3 and 4 are about `__far` annotation under gcc and are now moot: the
large model makes every pointer far, so there is nothing to annotate and no
mixed near/far loop to pay for. Points 1 and 2 still stand as written.

### When it would be worth it

The scenario that genuinely needs far data is **large windows × long packets**.
`MAXWS 32` × `MAXSP 4096` is a 132KB packet pool — that cannot fit a single
DGROUP at any tuning.

**This is the section the toolchain decision came out of, and the answer it
gave has been taken:** the right move was never `__far` annotation under
ia16-gcc but the OpenWatcom large model, where the buffers leave DGROUP by
compiler flag and the source stays upstream. `malloc()` is already `_fmalloc`
there, so the 132KB pool costs nothing in DGROUP — what it costs is real-mode
RAM, of which there is ~158K spare (§9).

The switch was not free, and the bill is itemised in §9d: seven new files of
compatibility headers, because Open Watcom's DOS libc never pretended to be
POSIX and newlib did.

---

## 9b. Can the hot code be co-located with the buffers?

The obvious idea: rather than paying for a far pointer on every access, put the
buffer-touching code in the same segment as the buffers, load the segment
register once, and let the inner loop run at near speed. This was measured.

**The idea is sound, and on x86 it hinges on one thing: there are four segment
registers, and the inner loop needs three of them live at once** — one for the
source buffer, one for the destination buffer, and one for the globals in
DGROUP. Whether it works comes down to whether the compiler will keep all
three resident across the loop.

### Buffers only: works, under either compiler

An encode-shaped loop over two `__far` buffers, written with **walking**
pointers (`*p++`) rather than indexing (`s[i]`):

```
                    loop insns   segment reloads in loop
enc_near                    8            0
enc_walk  (far, walking)    9            0      <- both lds/les hoisted to prologue
enc_idx   (far, indexed)   12            5      <- reload per access
```

gcc hoists both segment loads into the prologue and repoints `%ds` at the
destination buffer for the whole function, so those writes carry no prefix at
all. Cost is one `%es:` prefix on the source read: 1 byte, ~2 clocks on 8088.

**Indexing is what kills it, not farness.** An earlier "+34%" figure in this
document was measured on `enc_idx` and overstated the cost of far data in
general. Corrected here.

### Buffers plus globals: collapses under gcc

C-Kermit's real packet filler is not the toy above. `bgetpkt()` is 227 lines
and touches roughly 25 file-scope globals in its inner loop — `size`, `binary`,
`parity`, `rptflg`, `rptn`, `rptq`, `cxseen`, `what`, `myctlq`, `ffc`, `ccp`,
`ccu`, `fmask`, `keep`, `interrupted`, `data`, `first`, `crc16`, `crcta`,
`crctb`, ... That is normal for 1985-vintage C and it is not going to change.

Compiling that shape (far buffers + heavy global access) with ia16-gcc:

```
  1f:  lea    0x1(%si),%cx
  22:  mov    %es:(%si),%dl          <- source buffer, ES
  25:  mov    %ss:0x0,%ax            <- globals via SS override
  ...
  56:  mov    -0x2(%bp),%ds          <- %ds RELOADED inside the loop
  59:  mov    %al,(%bx)
  63:  mov    -0x2(%bp),%ds          <- and again
```

gcc used `%ss:` for the globals but had nowhere to keep the destination
buffer's segment resident, so it reloads `%ds` from a stack slot **twice per
iteration**. Loop body: ~33 instructions with 2 segment reloads, versus ~10 for
the near version. On an 8088 a `mov ds,` also flushes the prefetch queue. This
is strictly worse than not trying.

### Buffers plus globals: works under Watcom large model

Same source, `wcc -ml -zt1000 -oneatx`:

```
        mov  es,cx                       ; source segment  - loaded ONCE
        mov  ds,dx                       ; dest segment    - loaded ONCE
L$1:    mov  al, byte ptr es:-1[si]      ; source: 1 prefix byte
        mov  byte ptr [bx],23H           ; dest:   NO prefix (DS points at it)
        add  word ptr ss:_ffc,1          ; globals via SS: - 1 prefix, no reload
        cmp  word ptr ss:_rptflg,0
        inc  word ptr ss:_what
        cmp  word ptr ss:_cxseen,0
```

Three segments live simultaneously and **zero reloads in the loop body**:

| register | points at | cost per access |
|---|---|---|
| `DS` | destination buffer | none — no prefix |
| `ES` | source buffer | 1 prefix byte |
| `SS` | DGROUP (globals) | 1 prefix byte |

That works because Watcom pegs `SS` to DGROUP, so every global stays reachable
with a one-byte override while `DS` and `ES` are free to point at far buffers.

```
                       loop insns   segment reloads
ia16-gcc, far+globals         33          2  (mov ds, twice per iteration)
Watcom -ml, far+globals       26          0
```

So the answer to "can we co-locate?" is **yes — but it is Watcom that delivers
it, automatically, in large model, with no source changes.**

### Caveats before acting on this

- In Watcom large model **every** `char *` in C-Kermit becomes 4 bytes, not
  just the packet pointers. Pointer-heavy code outside the packet loop pays for
  that in both DGROUP occupancy and cycles.
- The alternative that would make co-location work under gcc — hoisting those
  ~25 globals into locals at function entry and writing them back at exit — is
  a rewrite of `bgetpkt()`/`getpkt()`/`decode()`, i.e. modifying the protocol
  engine. That is the thing this port exists to avoid.

**Net effect on the plan:** this section is the performance half of the case
for Open Watcom, and that case was accepted — the tree builds in large model
and nowhere else. The first caveat above is now simply the cost of doing
business: every `char *` is 4 bytes, and DGROUP still comes to 60%. Nothing
here needs acting on further; the packet pool is on the far heap and the
inner loop is the second table above.

---

## 9d. Open Watcom builds the same port, and the parser comes back

> **This is the section that decided the toolchain, and the decision is
> taken.** It is written as an experiment run alongside a live gcc build,
> because that is what it was. On 2026-08-05 the gcc build was retired and
> Open Watcom became the only build. The comparisons below are the evidence
> for that; they are not a standing choice.

§9c ends with "nothing short of removing the command parser fits, and that is a
property of the toolchain, not of C-Kermit." That was true and it remains true
— **of `ia16-elf-gcc`**. Open Watcom has a real large model, so the claim was
worth testing rather than assuming, and the answer is measured rather than
estimated.

`victorow.mak` builds the identical source tree with Open Watcom V2's 16-bit
`wcc`/`wlink`. It was a second build of the same port, not a fork of it: the
feature configuration is still `ckvictor.h` and only `ckvictor.h`, `ckutio.c`
and `ckufio.c` are still stock upstream, and `ckvictor.c` is still the only
non-upstream C file. Open Watcom V2 is installed in the same `ia16-ubuntu-2`
container, at `/opt/open-watcom-v2/rel`, with the 16-bit DOS libraries
(`lib286/dos/clib{s,m,c,l,h}.lib`) present.

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"
```

### Measured: all 24 modules compile and the program links

Same feature set as the gcc build (`NOICP` on), `-ml -0 -os -zc`:

Figures are current as of §11b, which added 672 bytes to each — 512 of them
the receive ring. The far-code and `.EXE` sizes are as first measured here
and have drifted a little since.

| | ia16-elf-gcc, medium | Open Watcom, large |
|---|---:|---:|
| near data (DGROUP) | 52,728 of 65,536 (80%) | 39,424 of 65,536 (60%) |
| left in the segment | 12,808 for heap **and** stack | 26,112, stack already counted |
| far code | 236,957 | 190,498 |
| far data | none possible | 0 (not needed yet) |
| `.EXE` | 218,448 | 224,928 |

17 warnings, all of them in stock upstream modules and none in the port's own
code: 10 × W111 "meaningless use of an expression" (`debug()` expanding to
nothing under `NODEBUG`), 2 unreferenced labels, `localtime()` called with a
`long *` where Watcom's `time_t` is unsigned, `execvp()` called without the
`const`, and `docmdline(1)` in `ckcmai.c` passing the integer 1 to a
`void *` parameter that is only ever tested for non-null. gcc reports none of
these; none is a defect the large model makes dangerous.

Two structural differences do the work, and neither needs a source change:

- **`-zc` puts string literals in the code segment.** `.rodata` was 66,578
  bytes of DGROUP under gcc (§9c); under Watcom the equivalent (`CONST` +
  `CONST2`) is 1,366 bytes, because everything else went far. All pointers are
  4 bytes in the large model, so nothing has to know.
- **`malloc()` is the far heap.** In the compact, large and huge models
  Watcom's `malloc` is `_fmalloc`. C-Kermit's `DYNAMIC` packet buffers —
  `SBSIZ`/`RBSIZ`, the thing §9/§14 spends the most words budgeting — stop
  competing with DGROUP altogether. The 2048/2048 pools that §9 had to argue
  down from 9024/9050 are a non-issue here.

### Measured: the interactive command parser fits

`KEEP_ICP` (see `ckvictor.h`) turns `NOICP` back off for exactly this
experiment. Full build, parser in, `-zc`:

| data threshold | DGROUP | `.EXE` |
|---|---:|---:|
| default (`-zt` off) | 60,768 of 65,536 | 447,534 |
| `-zt1024` | 42,528 | 455,370 |
| `-zt128` | 19,376 | 469,426 |

`-zt<n>` moves data objects of *n* bytes or more into per-module far data
segments. It is worth more than `-zc` because it moves the keyword **tables**,
not just the strings they point at — the `struct keytab` arrays in
`ckuus3`–`ckuus7` that §9c identified as 43KB of `.rodata`.

So: **`C-Kermit>` fits in DGROUP under Open Watcom, with room to spare.** It
does not follow that it fits in the *machine*, and §16a measures that
separately: the parser build asks DOS for 429KB contiguous, and the largest
block a program actually gets on the test setup is 387KB. Fitting the data
group and fitting the RAM are two different questions and this port has now
hit both walls.

### What this did *not* settle at the time

- **The 7201 driver was still unwritten** (§11) — and §16a is where that
  finally showed up as a wire-level symptom. Since resolved: §11b.
- **Which toolchain the port should ultimately use was not decided here.** This
  section established that the large model removes the constraint that forced
  §9c's amputation. §16a established that the two builds were
  indistinguishable on the wire.

  **Settled since, in Open Watcom's favour.** What decided it was not the
  parser — that still does not load, for a different reason (§16a) — but the
  heap. §16e ran the gcc build to a completed transfer and measured **~2,090
  bytes** of near heap left at the low-water mark, with `SBSIZ`/`RBSIZ` already
  halved to get there; §16f watched a wildcard expansion drive that number to
  **212**. A far heap is not a nicety on this program. The gcc build was
  retired on 2026-08-05.

The console path was an open question here and §16a closed it: under gcc,
`ckvictor.c` supplies newlib's `_read_r`/`_write_r` and does the CR/NL
translation there; Watcom's runtime has its own `read`/`write` over INT 21h
and that override does not exist. Watcom's text-mode stdout turns out to do
the same job — output is correctly formatted on both DOSes.

### What the second toolchain cost — and what retiring the first refunded

Compiling stock upstream Unix modules against a DOS libc that never pretended
to be POSIX needs a compatibility layer that newlib made unnecessary. It was
seven files, all new, none upstream, and they are now simply *the port*:

| File | What it fills |
|---|---|
| `victorow.mak` | build, and the DGROUP report read from `wlink`'s map |
| `victorow/pwd.h` | `struct passwd`; Watcom has no password database at all |
| `victorow/sys/utsname.h` | `uname()`, for `\v(host)` and the version banner |
| `victorow/sys/time.h` | `struct timeval`/`gettimeofday()` for the FP timers |
| `victorow/termios.h` | forwarder to `victor/sys/termios.h`, as newlib's was |
| `victorow/ckowsys.h` | declarations for the process-model stubs. Watcom does not declare `ttyname()` etc. at all, and in a large model an implicit `int` return **truncates a far pointer** |
| `ckvictor.h` header surgery | listed below |
| `ckvictor.c` §1d | `gettimeofday`, `uname`, `link`, `kill`, `getpwent`, and an `intdos()` version of the INT 21h console poll |

Against that, retiring gcc took **`ckvictor.c` from 3,037 lines to 2,002** —
1,113 deleted against 78 added. What went was sections 0, 0a, 0c, 0e and 1c: a
hand-written inline-assembly INT 21h layer (`_read_r`, `_write_r`,
`dos_getch`, and the `DOS_DS_CALL` macro that existed only because ia16-gcc
treats `%ds` as a scratch register), a hand-built
`opendir`/`readdir`/`closedir` over the DOS DTA, a `stat()` that answered
`"."` because `libdos-m`'s could not, stubs for `sleep`/`creat`/`utime`/
`umask`/`exec`, the `_link_r`/`_kill_r` reentrant pair, and the
`V9K_HEAPREPORT` instrument that existed only to watch a near heap that no
longer exists. Watcom's runtime does all of it. The file now contains **no
conditional compilation on the compiler at all**, and neither does
`ckvictor.h`.

The `ckvictor.h` surgery is the interesting part, because it demonstrates the
technique that kept the upstream edit count at one: **`ckvictor.h` is
force-included ahead of every module, so it can include a system header and
then correct what that header defined.** By the time `ckufio.c` reaches its own
`#include`, the guard has already fired and our correction is what it sees.
Used for three things:

- `S_IFBLK`, `S_IFLNK` and `S_IFSOCK` are all `0` in Watcom — honest for FAT,
  but `ziperm()` switches on them and three `case 0:` labels is a hard error.
- `extern long timezone` in `ckufio.c` cannot agree with Watcom's `__near`
  declaration of it once the large model makes a bare `extern` far.
- `mkdir()` takes one argument, not two.

`NO_PARAM_H` and `NO_NL_LANGINFO` are upstream's own knobs for "this system
does not have that header" and are used as such.

---

## 10. What is proven, and what is not

Being precise about this matters, because the two are easy to conflate.

### Proven on real Victor hardware

- **38400 bps transmit on µPD7201 channel A.** 8253 Counter 0 at divisor 2,
  VIA2 PA0 internal clock, polled TX. This is the FreeDOS boot debug console
  (`kernel/victor_serial_debug.asm`, `BAUD_DIV_38400 = 0x02`, built under
  `VICTORFAST=1`) and it has carried sustained kernel output during real
  hardware debugging sessions. The physical layer at 38400 — divisor, clock
  gating, chip init, 1488/1489 line drivers, cabling — is not in question.
  (MAME caps around 9600; 38400 is a real-hardware-only path.)
- **Bidirectional serial at 9600 on channel B**, polled, via the FreeDOS
  INT 14h driver — `CTTY COM2` drove a full shell session on real hardware.

### Proven under MAME, on Victor MS-DOS 3.1

Not the same claim as the two above, and kept separate for that reason.

- **The OEM driver's IOCTL control block** (§11a). Both subfunctions
  answer; `tcsetattr()` programs speed, width, stop bits, parity and the
  modem lines through them; and the values read back as written, including
  DTR and RTS dropping and returning across `tthang()`. Confirmed by
  reading the hardware back, which is more than the two items below have —
  but under emulation, and never on real hardware.
- **A correct Send-Init packet on the wire at 9600**, with retransmission on
  timeout and a protocol `E` packet on giving up (§16a, §16b). Byte-identical
  from the retired gcc build too, which is how §16a established that the two
  were indistinguishable on the wire.
- **A complete file transfer** (§16d, §11b). Our IRQ1 handler on the µPD7201,
  a receive ring, a polled transmitter, and the OEM driver out of the data
  path: S/F/A/D/Z/B all the way through, and a byte-correct 72-byte file at
  the far end. One small file, one literal filename, 9600 bps, window 1,
  short packets. The gcc build did the same thing on the same harness (§16e),
  74 bytes, the difference being a text/binary decision and not an error.
- **A wildcard send, and a multi-file one** (§16g). `-s *.TXT` completing
  against one match and against three, byte-correct, with the `znext()` path
  that multiple matches take exercised for the first time. The same run read
  the driver's two loss counters — `rxlost=0, rxfull=0` — which had never
  been read at all.
- **What DOS itself does with `.` and with trailing separators** (§16f).
  Measured in the root and in a subdirectory, by probe, because two rounds
  of reasoning about it had already gone wrong. `FindFirst(".\*.*")` works
  in both, and `stat("./")` fails in a subdirectory. Watcom's `stat()` does
  answer for `"."` and `"./"`, which is why this port no longer carries the
  replacement `stat()` §16f needed under gcc.

### Written but never run on hardware

- **Our interrupt-driven receive at speed.** §16d proves the mechanism at
  9600 with one packet in flight. It says nothing about 19200 or 38400,
  about long packets, or about a floppy write holding the ring for longer
  than the 533ms it buffers at 9600. The handler's two loss counters exist
  to answer exactly that.
- **The FreeDOS-for-Victor interrupt-driven receive.**
  `kernel/victor_int14.asm` has the whole apparatus: per-channel `SERPORT`
  descriptors, 256-byte RX/TX rings, an IRQ1 ISR with the MS-DOS 3.1
  stack-switching pattern. But both channels ship with `irq_enabled = 0` and
  IRQ1 masked at the PIC. The note dated 2026-07-14 says the IRQ-buffered
  path produced no output and hung `ctty COM2`, and that re-enabling
  requires verifying the µPD7201 interrupt-acknowledge sequence (Reset Tx
  Int Pending `0x28` / RETI) on real hardware. Our own handler now works
  under emulation without that sequence, on the same chip, which is evidence
  about the acknowledge question but not an answer to it — MAME's µPD7201 is
  not the part.

### Why the ISR turned out to be on the critical path for the milestone too

The subsection below was written before §16b, and its conclusion — polled
receive first, the ISR later — was wrong for a reason it could not have
known. Its reasoning about *speed* still holds exactly as written; what it
missed is that the OEM driver could not receive a packet at any speed. §16b
measured that, §11b replaced it, and §16d is the transfer. Kept because the
speed argument is still the argument for windows and streaming.

At 38400 8N1 a byte arrives every ~260µs. The µPD7201's receive FIFO is three
deep, so a polled reader has well under a millisecond of slack. That is fine
until Kermit writes a received packet to floppy or SASI — a multi-millisecond
blocking operation during which polled RX drops bytes on the floor.

But it only bites when the line is busy *while* Kermit is writing. With
window 1 and streaming off, the sender waits for an ACK per packet, so the disk
write happens on an idle line and **polled RX is correct at any speed** — just
slow. Windows and streaming are what make the ISR mandatory.

That gave what looked like a clean staging: polled first for the milestone,
ISR before the speed and windowing work. **It did not survive contact.** The
ISR bring-up turned out to be the whole of getting a file across the wire,
because the polled path we were going to lean on was the OEM driver's and it
loses the packet (§16b). What remains true is the other half: windows and
streaming are what make the ISR mandatory *for throughput*, and §11b's ring
has no interrupt-level flow control yet for exactly that reason.

One thing §16b adds to this: whatever the driver does about *errors* is not
optional even at 9600 with window 1. Measured — the OEM `\dev\seriala`
driver delivers the first two bytes of every inbound packet and then goes
silent. A latched µPD7201 receive overrun is the leading explanation but is
not established (§16b separates the two). Either way a polled reader is
allowed to be slow and is not allowed to leave RR1's error bits standing:
**read RR1 and issue the WR0 Error Reset on every receive path**, polled or
interrupt-driven, from the first version. It also means the first thing the
new driver can do that the OEM one could not is *tell you what went wrong*.

---

## 11. Serial driver: design

**Decision: follow MS-DOS Kermit 3.13's integration model.** `msxv90.asm` in
`~/projects/kermit/msr313src` is a Victor 9000/Sirius serial driver for this
exact machine, written by the same project between 1985 and 1991, and it
solved the problem we are now standing in front of. The plan below is its
structure, with our own code; the constants in it are read out of that source
rather than guessed, and are marked as such.

### The thing 3.13 gets right, and §16b got wrong

Three-line summary of `msxv90.asm`: it opens the OEM device `SERIALA`, uses
the handle **only** to read and write the µPD7201's control registers through
DOS IOCTL, and never once reads or writes data through it. Every use of its
handle in the whole 1,443-line module is `OPEN2` (3Dh), `CLOSE2` (3Eh), or
`IOCTL` (44h) with `AL=02h`/`AL=03h`. There is no `AH=3Fh` and no `AH=40h`.
Data lives on its own interrupt handler against the memory-mapped chip.

So the OEM driver is a **configuration channel**, not a data path. §16b
measured what happens when it is used as one: two bytes per packet and then
silence. 3.13 declined to use it that way in 1986.

That splits this section into two halves that can be built and tested
independently, which is the real reason to copy the model:

| | what it does | how it reaches the hardware |
|---|---|---|
| **11a. Configuration** | speed, bits, parity, DTR/RTS, break | INT 21h `AH=44h AL=03h` on the handle we already have open |
| **11b. Data path** | RX ring, TX, `FIONREAD`, overrun recovery | our ISR, memory-mapped chip |

11a is small, is pure INT 21h, needs no interrupt work, and makes `SET SPEED`
and `tcsetattr()` real on their own. 11b is where the risk is.

**Both are done.** 11a is measured in §16c, 11b in §16d, and the split earned
its keep: 11a shipped and was verified on hardware two sessions before 11b
existed, and when 11b landed there was exactly one new thing that could be
wrong.

### Why we still cannot just use the OEM driver

Unchanged from the previous revision, and now with a fourth reason:

- INT 14h `AH=00h` has three baud bits; `victor_int14.asm`'s table stops at
  index 7 = 9600. 38400 is divisor 2 and cannot be requested through it.
- INT 14h has no "bytes queued" call. `ttchk()` needs exactly that, and
  `ttinl()` wants to pull a whole packet in one go.
- Owning the chip means Kermit does not depend on the host DOS's serial
  state — including the not-yet-root-caused DGROUP writer near `serport_b`.
- **The OEM driver loses the packet** (§16b). Whatever the mechanism, 3.13's
  authors reached the same conclusion with the same hardware.

### 11a. Configuration through the driver's IOCTL control block

**Done, and measured on Victor MS-DOS 3.1 under MAME.** It is in `ckvictor.c`
§1b, it is INT 21h only, and it cost 48 bytes of DGROUP. What follows is the reference data first and the
measurements after.

**The OEM documentation has since been read directly** — *Systems Programmers
Toolkit II*, Appendix A, "Specific implementation for interface port access",
which is the source `msxv90.asm` cites. It confirms the layout field for
field and settles three things this section had inferred or got wrong; those
are marked **[A.2]** below and the code was changed on 2026-08-05 to match.
Two of them are corrections to measurements 3–5, which claimed more than the
interface can deliver.

`AH=44h`, `AL=02h` to read and `AL=03h` to write, `BX` = handle, `CX` = 17,
`DS:DX` = the block. Layout, from `msxv90.asm`'s `pval struc` (which cites
*Systems Programmers Toolkit II*, Appendix A):

```
offset  size  field
  0      2    stype      = 0011h   (port access)
  2      2    status
  4      2    blocktype  = 0000h   (serial)
  6      2    baudr               <-- 8253 divisor, not a baud rate
  8      1    CR0
  9      1    CR1
 10      1    CR2A
 11      1    CR2B
 12      1    CR3
 13      1    CR4
 14      1    CR5
 15      1    CR6
 16      1    CR7
```

The idiom is read-modify-write: `AL=02h` to fetch current values, overwrite
`CR1`–`CR5` and `baudr`, `AL=03h` to put them back. 3.13 does exactly this in
`OPNPRT` and again in `DOBAUD`, `SERHNG` (DTR/RTS for HANGUP) and `SENDBR`.

Appendix A names the nine CR bytes, and they match the port's field comments
one for one: CR0 control, CR1 interrupt enable, CR2A interrupt mode, **CR2B
the channel-B interrupt vector**, CR3 receiver, CR4 sampling, CR5
transmitter, CR6/CR7 SYNC characters.

**[A.2] `stype` is an input, and the appendix says so outright** — "the type
is always 11 hexadecimal", listed under TYPE, not under anything returned.
Measurement 2 found this the expensive way; it is now documented rather than
merely observed.

**[A.2] `AL=02h` does not read the chip.** Appendix A: *"When a request is
made to set the port, the configuration information is saved. Then if the
current configuration is requested the parameter block last used to set the
port is returned to you."* The read returns the driver's **cache of its own
last write**. Read-modify-write is still exactly right — the write applies
the whole block, so preserving fields we do not set preserves what the driver
will apply — but **nothing read through this interface is evidence about the
state of the µPD7201**. §11b reads the chip when that is the question. See
the corrections to measurements 3, 4 and 5.

**[A.2] The `status` word is a second, independent failure channel.** "Status
is returned to reflect if an error occurred… If an error does not occur,
status is returned as false (0)." Two codes are defined:

| status | meaning |
|---|---|
| `0` | no error |
| `01h` | invalid function requested |
| `-1` | invalid type requested |

It is returned **with the carry flag clear**. Until 2026-08-05 the port
checked only carry, which is why measurement 2 below took three runs: the
driver was reporting the bad `stype` as `status = -1` the entire time.
`v9k_portval_io()` now fails the call on a nonzero status, logs it, and
returns `EINVAL`. Cost: 48 bytes of image (228,506 → 228,554), no DGROUP.
**Run on Victor MS-DOS 3.1 and it fires on nothing** — all seven
`tcsetattr()` calls come back `status = 0` and the transfer still completes;
§16c's addendum has that run, and it is also where the cache semantics stop
being a quotation and become a measurement.

**[A.2] The appendix says `CX = 9` and that is not the block size.** Nine is
the count of CR bytes; the appendix's own field list adds to 17. The port
passes 17, which is what `msxv90.asm` passes and what measurement 1 below
proved works on Victor MS-DOS 3.1. The comment in `ckvictor.c` says not to
"correct" it.

(Appendix A's parallel-port block is described as just `{type, status}` with
no `0011h` word, which contradicts its own prose for the serial case. Where
the appendix and the measurement disagree, the measurement wins.)

**We already hold the handle.** `ttopen()` opens `/dev/seriala` and leaves the
descriptor in `ttyfd`, so `tcsetattr()` in `ckvictor.c` §1b can issue this
without opening anything, and `cfsetospeed()` becomes a table lookup plus one
INT 21h. That retires the `TODO(driver)` on `tcsetattr` without touching an
interrupt vector.

Divisor table, from `msxv90.asm`'s `bddat`. The rule is **`78125 / baud`**:

| baud | 300 | 1200 | 2400 | 4800 | 9600 | 19200 | 38400 |
|---|---|---|---|---|---|---|---|
| divisor | 104h | 41h | 20h | 10h | **8** | 4 | **2** |

**[A.2] Appendix A prints the OEM driver's own table**, 50 baud through
19.2k, as low-byte/high-byte pairs. It is `78125 / baud` throughout — a third
independent confirmation of the 1.25 MHz clock, after `msxv90.asm` and
`vickermit.c`. Two consequences for `v9k_divisor[]`:

- **B200 is 390 (`0186h`), not 391.** 200 was the one rate neither shipped
  table carried, so the port had been computing `round(78125/200)` = 391.
  Changed to 390 — matching what shipped beats matching the arithmetic, and
  it is 200.3 bps either way. `victor/sys/termios.h` updated to suit.
- **The appendix's 1.8k entry, `26h` = 38, is a transcription error and is
  not taken.** `78125/38` is 2056 bps, which is *faster* than the same
  table's 2.0k entry (`27h` = 39, 2003 bps) while labelled slower. `2Bh` = 43
  gives 1817 bps and is what the port keeps.

Appendix A stops at 19.2k: **B38400 and B76800 are undocumented by the OEM.**
They are `msxv90.asm`'s, 3.13 shipped 38400, and nothing in the appendix says
the driver validates the divisor — but this is the case where the status
check above earns its keep, since a rejected speed would otherwise come back
carry-clear and be indistinguishable from success. Appendix A also carries
2.0k (`27h`) and 3.6k (`15h`), which the port does not offer because
`ckutio.c` has no arm for them.

#### The baud clock is 1.25 MHz, and the port's own header had it wrong

Worth stating separately because a header in this tree asserted the other
value for four sections. `victor/sys/termios.h` used to say the clock was
1.2288 MHz and the rule `76800 / baud`, with a per-rate divisor in the
comment on every `B*` code. That came from a code comment in the FreeDOS
Victor INT 14h driver (`kernel/victor_int14.asm`, "Crystal: 1.2288 MHz").

It is wrong, and two programs that shipped for this machine say so.
`msxv90.asm`'s `bddat` and `vickermit.c`'s `Rate[]` are byte-identical
where they overlap — 300 → 260, 600 → 130, 1200 → 65, 2400 → 32 — and
`76800 / baud` gives 256, 128, 64, 32 for those. Only `78125 / baud`
reproduces the tables, `msxv90.asm` states that rule in a comment, and
78125 × 16 = 1.25 MHz. The FreeDOS driver's *own* subsystem documentation
(`docs/victor/subsystem-docs/Serial.md`) says 1.25 MHz, contradicting its
code comment, and the two rates it was proven at — 9600 → 8 and 38400 → 2
— are exactly the ones where the two rules agree, so its evidence never
discriminated.

The consequence is that 78125 is odd (5⁷) and **no rate divides it
exactly**: every divisor is approximate, 9600 is really 9765 (+1.7%) and
38400 is really 39062 (+1.7%). That is inside async tolerance and it is
what 3.13 shipped. `victor/sys/termios.h` now carries the corrected rule,
the per-rate error figures, and the table `ckvictor.c` indexes by `B*`
code.

Register values 3.13 writes, for 8-N-1 with the receiver enabled:

| reg | value | |
|---|---|---|
| WR1 | `00h` | `OR 18h` to enable RX interrupts |
| WR2 | `14h` | must be written **first** |
| WR3 | `C1h` | RX 8 bits, RX enable |
| WR4 | `48h` | must be written **second** |
| WR5 | `EAh` | TX 8 bits, TX enable, DTR + RTS |

Order matters and is called out in the source: WR2 first, WR4 second, then
1/3/5 in any order, then the three WR0 commands `10h` (reset ext/status),
`30h` (error reset), `38h` (end of interrupt). `AND 7Dh` on WR5 drops DTR and
RTS, which is how 3.13 implements HANGUP.

Note the character-width encoding is not the obvious one: `00` is 5 bits,
**`01` is seven and `10` is six**, `11` is 8. It sits at WR3 bits 7–6 and
at WR5 bits 6–5. `tcsetattr()` maps `CSIZE` through it.

#### What was implemented

`tcsetattr()` in `ckvictor.c` §1b does the read-modify-write on the
descriptor `ttopen()` left in `ttyfd`, and it is the only place that
programs the line. It sets **WR3** (Rx width, `CREAD`), **WR4** (x16
clock, `CSTOPB`, `PARENB`/`PARODD`) and **WR5** (Tx width, Tx enable, DTR,
RTS) from `c_cflag`, and `baudr` from `c_ospeed`. `tcsendbreak()` sets WR5
bit 4, waits, and puts it back. `B0` drops DTR and RTS without touching
the speed, which is how `tthang()` reaches HANGUP — the same two bits as
3.13's `SERHNG`.

Two deliberate deviations from 3.13, both because we do not own the chip
yet:

- **CR1 and CR2A are preserved, not written.** They are the interrupt
  enables and the interrupt mode, and until §11b installs an ISR the OEM
  driver still owns interrupts here; clearing them would break the
  reception we do have. 3.13 writes both because by that point it has
  taken the vector. Also relevant to §11b: 3.13 found the write IOCTL does
  **not apply CR1 at all** and pokes WR1 at the chip directly afterwards,
  commented *"IOCTL doesn't seem to touch it"*. So this path will never be
  able to enable receive interrupts.
- A console `fd` is rejected before any INT 21h happens. `concb()` and
  `conres()` come through the same `tcsetattr()`, and `ttopen()` sets
  `ttyfd` to 0 when the line *is* the console, so the guard tests
  `fd >= 3 && fd == ttyfd` — the same distinction §0d makes.

#### Measured, on Victor MS-DOS 3.1 under MAME

A `KEEP_DEBUG` Watcom build, `CKERMITW -d -l /dev/seriala -b 9600 -s
TESTFILE.TXT`, `DEBUG.LOG` pulled back off the image.

1. **The OEM driver implements both subfunctions.** Neither `AL=02h` nor
   `AL=03h` ever returned carry. `tcsetattr divisor=8` appears at each of
   the five places C-Kermit sets the line — `ttopen`, `ttsspd`, `ttpkt`,
   `tthang`'s restore, and `ttres` on the way out — each returning 0. So
   speed, width, parity and the modem lines are now real, through the same
   channel 3.13 used, with no interrupt work.

2. **`stype` must be `0011h` on entry to the READ, and getting that wrong
   fails silently.** This took three runs to pin down and is the trap in
   this interface. `stype` looks like an output field; it is not, it is how
   the request identifies itself, and `msxv90.asm` carries `0011h` as a
   structure default on the block it hands to the read as well as the
   write. The three runs, in order:

   | read block on entry | `baudr` came back as | what it was |
   |---|---|---|
   | uninitialised stack | `97BCh` | stack junk, untouched |
   | zeroed, `stype` = 0 | `0` | zeros, untouched |
   | zeroed, `stype` = `0011h` | `8` | the real value |

   **Carry was clear in all three**, and the conclusion drawn here at the
   time — that a driver which ignores the request and one which answers it
   are indistinguishable, so the only way to know is to recognise a value —
   **was wrong**. Appendix A shows why: the driver reports an unrecognised
   type in the block's `status` word as `-1`, carry-clear, and the port was
   not reading it. This is corrected in the code and the failure is now
   logged. The measurement stands; only the inference from it was bad, and
   it is a good illustration of the difference.

   The first of those caught a real defect on its way past: the hang-up
   path deliberately does not set `baudr`, so it wrote `97BCh` straight
   back into the 8253 — an arbitrary divisor programmed into the chip for
   the half second `tthang()` holds DTR down. That is fixed, and the rule
   it produced is worth keeping even now that the read is known to work:
   **read the block to preserve the fields we do not understand, but never
   let a field we control come back from a read.** The last divisor and
   last WR5 we programmed live in two statics for exactly that reason.

3. **The round trip is real.** With `stype` right, the read returns
   `cr4 = 44h` and `cr5 = EAh` — the values `tcsetattr()` had just computed
   for 8-N-1 — and `baudr = 8`. `cr2a` reads back as `10h`, which is the OEM
   driver's own WR2 and *not* the `14h` 3.13 writes: the deliberate
   preservation of CR1/CR2A above is working.

   **[A.2] Correction.** This measurement was written up as *"it verifies
   that we are programming the chip"*. It does not. The read returns the
   driver's cache of the last block written, so the round trip proves the
   driver stored what we sent it and nothing more. What it does establish is
   real and worth having — the request is well formed, the fields land where
   we think they land, and CR2A survives — but the chip is not in evidence.

4. **Hang-up verified at the control-block level.** Across `tthang()`, `cr5`
   goes `EAh` → **`68h`** and back. `EAh AND 7Dh` is `68h`: DTR (bit 7) and
   RTS (bit 1) cleared and nothing else touched. `baudr` reads 8 on both
   sides of it.

   **[A.2] Correction.** This was written up as *"the first thing in this
   port whose effect on the hardware has been confirmed by reading the
   hardware back"*. It is a cache round-trip, not a hardware read-back, and
   that claim is withdrawn. The first genuine hardware read-back in this
   port is §11b's, which reads RR0 and RR1 at the chip.

5. **`cr1` reads back as 0, and that is not evidence.** WR1 holds the
   receive-interrupt enables, and 0 was read here as the OEM driver running
   this port with no receive interrupt at all — §16b's leading explanation
   for the two-byte signature. The hedge at the time was that CR1 is the one
   field 3.13 flagged as not behaving, so a field not applied on write may
   not be reported on read either.

   **[A.2] Correction.** The hedge was right and the reason is stronger than
   stated: `cr1 = 0` is simply the driver's cached CR1 from its own last
   set, so it says nothing whatever about the chip. §11b settled the
   question properly by reading RR1, and §16c's addendum makes it a
   measurement rather than an inference — after §1e writes `WR1 = 18h` at
   the chip and a whole transfer runs on those interrupts, this read still
   reports 0.

6. **Reception is unchanged: 12 reads, every one returning exactly 2**, in
   all three runs. Identical to §16b, on a line whose registers we had
   just programmed through the driver's own interface. §11a is neutral on
   the data path, which is what copying 3.13's split predicted, and it is
   a third measurement that the OEM driver is not a data path. The
   transfer still ends in retransmissions and a protocol `E` packet.
   (Originally written "under a changed and now *verified* configuration";
   per the correction to measurement 3, the configuration was accepted by
   the driver, not verified at the chip.)

#### What §11a does not do

`ttchk()` returns 0, upstream of `FIONREAD`, because `in_chk()` asks
`ttgmdm()` for carrier first and this port had no `TIOCMGET` (§12). The
control block is write-registers only and carries no RR0, so modem status
cannot come from here — 3.13 reads DSR/CD/CTS straight out of RR0. That,
the real byte count, and the data path were all §11b, and are done.

One thing §11a keeps doing after §11b, which is easy to miss: **every call
through `tcsetattr()` still ends by re-asserting WR1 at the chip.** The IOCTL
write may clear the receive-interrupt enable, so if it did not, the interrupt
could go away silently in the middle of a transfer.

### 11b. The data path we own

**Done, and it completes a file transfer.** It is `ckvictor.c` §1e, and it
cost 672 bytes of DGROUP — 512 of them the receive ring. §16d has the
measurement; this section is the design and the reference data.

The shape is the one §16b argued for: **our interrupt handler for receive, a
polled transmitter**, and the OEM `\dev\seriala` driver out of the data path
entirely in both directions. It keeps its IOCTL job from §11a and nothing
else, which is exactly the division `msxv90.asm` has used since 1986.

Memory-mapped, not I/O ports. From `msxv90.asm`:

| device | segment | offsets |
|---|---|---|
| µPD7201 | `E004h` | A data 0, A status 2, B data 1, B status 3 |
| 8253 | `E002h` | A divisor 0, B divisor 1, control 3 |
| 8259 | `E000h` | CW1 0, CW2 1 |

And its `mdminfo` for channel A resolves §2's open question about the vector:
**IVT slot 41h** (`mdintv = 104h`), 8259 unmask `AND 0FDh`, mask `OR 02h`,
specific EOI `61h`. 8253 control byte is `(port << 6) | 36h` — mode 3, binary,
low byte then high byte of the divisor.

The vector is the one constant here that is not a property of the hardware —
it is a property of how the 8259 was programmed at boot. `~/projects/myfreedos`
remaps the PIC in its own kernel and puts its serial ISR at INT 09h. So 41h
is right for Victor MS-DOS 3.1, where it has been used, and is an open
question for FreeDOS for Victor (§15).

DSR is not on this chip at all. `msxv90.asm`'s `getmodem` explains why: the
Victor brings no DSR pin to the 7201, so it comes off the **6522 at `E804h`,
PA3 for channel A and PA5 for channel B, active LOW**. DCD and CTS are RR0
bits 3 and 5.

Ownership protocol, on `SET LINE`:

1. Configure via 11a. If the handle will not answer the IOCTL, fall back to
   programming the chip: WR0 `18h` (channel reset), then the register order
   above. 3.13 has this fallback and prints *"Cannot open com port / Going
   direct to serial controller hardware..."*. **Implemented**, and not
   hypothetical: 11a's IOCTL is measured on Victor MS-DOS 3.1 and nobody has
   measured FreeDOS for Victor, which this binary also has to run on.
2. Save the old vector at 41h and the 8259 mask.
3. Install our ISR, unmask IRQ1, `WR1 |= 18h`.

And the exact inverse on exit — 3.13's `SERRST` **spins on RR1 bit 0 until
the transmitter and shift register are empty** before it tears anything
down, which is copied; otherwise the last packet is truncated. A Kermit that
leaves IRQ1 hooked after exiting will take the machine down.

The release hangs on `atexit()` rather than on `ttclos()`, because C-Kermit
can leave from several places and all of them go through `exit()` — including
`ckusig.c`'s SIGINT handler. What that does **not** cover is a Ctrl-Break
that DOS turns into a bare program termination before the runtime's INT 23h
handler sees it. Known, not measured on either runtime, and the reason to be
careful with Ctrl-Break while the line is open.

Where the install hook goes: `tcsetattr()`, at the end. That is the one place
C-Kermit is guaranteed to reach with the descriptor open and the line already
programmed, and it costs no new interception. Every later call through it
re-asserts `WR1`, because the IOCTL write may have cleared it — 3.13 found
that write subfunction does not apply CR1 (*"IOCTL doesn't seem to touch
it"*). §11a's `cr1 = 0` read-back used to be offered as corroboration; it
cannot be, since the read returns the driver's cache rather than the chip
(§11a **[A.2]**). 3.13's finding is the whole of the evidence, and it is
enough to justify a re-assert that costs one register write.

Note that this displaces the OEM driver's own ISR while its device stays
open. That is safe precisely because we never ask it for data again.

**WR2 is left as the OEM driver set it.** §11a read it back as `10h` where
3.13 writes `14h`; the two differ in one bit, which 3.13's own comment
attributes to interrupt priority (Ra>Rb>Ta>Tb), and with one channel and
receive interrupts only there is no priority decision to make. Reasoned, not
measured — but the transfer in §16d works with `10h`, which is the strongest
form the argument can take. The direct-programming fallback writes `14h`,
because in that path there is no OEM setting to preserve.

#### The ISR is written in C

The handler is `void __interrupt __far`, and the vector is hooked with
`_dos_getvect` / `_dos_setvect` — which are INT 21h `AH=35h`/`25h`, so
hooking it stays inside rule 6. `v9k_getvect`/`v9k_setvect` wrap that pair to
take a segment and an offset rather than a function pointer, which is the
shape the install and release paths want.

The generated code was inspected rather than assumed: Watcom's prologue pushes
a fixed 12-register set plus `DS`, loads `DGROUP` rather than trusting the
interrupted `DS`, ends in `iret`, and emits no stack probe. Being written
ANSI-only is forced — the attribute is part of the function's type and there
is no K&R spelling of it.

(The retired gcc build used `__attribute__((interrupt))` for the same thing,
and had to issue `AH=35h`/`25h` itself. It is worth recording that both
compilers generate a usable real-mode ISR from C; that was not obvious going
in.)

What neither gives is a **stack switch**: a C handler runs on whatever stack
it interrupts.

**We do not switch stacks, deliberately.** A dedicated interrupt stack would
have to come out of the same 64K DGROUP that holds the main stack, and 3.13's
`SERINT` does not switch either, on this machine, and shipped. The handler
holds no arrays and calls nothing; its frame is roughly 30 bytes, dominated by
Watcom's fixed prologue (gcc's `-fstack-usage` reported 22 for the same body).
That is the number to watch if this ever turns out to be the wrong call.
`~/projects/myfreedos`'s `victor_int14.asm` prologue remains the reference for
doing it properly.

### The ISR, and overrun

This is the part §16b says is not optional. Ours is 3.13's `SERINT` with the
terminal-emulator half removed:

1. Read RR0. Read RR1 (select register 1, then read).
2. `WR0 = 38h` (end of interrupt), then the 8259 EOI (`61h`).
3. If RR0 bit 0 (character available) is clear, return.
4. **If RR1 bit 5 (overrun) is set, `WR0 = 30h` — Error Reset — and
   substitute a `BELL` for the character that was lost**, storing both it and
   the real character so the byte stream stays framed.
5. Store into a ring and advance head.
6. ~~XON/XOFF at the interrupt level, with water marks at 3/4 and 1/4 full.~~
   **Not done.** With one channel, a window of 1 and a 512-byte ring there is
   at most one packet in flight, so a correct peer cannot fill it; the ring
   holds 533ms of 9600 bps. It starts to matter with streaming or a real
   window, and `tcflow()` and the water marks arrive together when it does.
   Two counters in the handler — bytes lost to a chip overrun, bytes lost to
   a full ring — go to the debug log at release so this is measurable rather
   than assumed.

Step 4 is the one to take seriously. The chip latches overrun in RR1 and will
not resume until Error Reset, so an ISR that omits it wedges the channel on
the first byte it is late for — which is the shape of what the OEM driver
does to us today. `msxv90.asm`'s own edit history shows this was learned the
hard way on this hardware: *"9 August 1986 Revise SERINT to insert control-G
for overrun chars"* and *"6 November 1986 Fix receiver overrun detection"*.

The ring is 512 bytes, a power of two, with head written only by the handler
and tail only by the foreground. That combination needs **no critical section
at all** on this target: each index has exactly one writer, and a 16-bit
store on an 8088 cannot be interrupted part-way, because interrupts are taken
between instructions. The one lock the driver does need is around any
foreground *select-then-access* pair on the control port — the handler shares
that pointer — which is why `tcdrain()` and the release path bracket their
RR1 reads with `cli`/`sti` and a bare RR0 read does not need to.

`FIONREAD` is now `(head - tail) & mask`: a real number for the first time,
which is what §12 and milestone step 8 have been waiting for. `ttgmdm()` is
fed too, through a `TIOCMGET` that `victor/sys/ioctl.h` defines and
`ckvictor.c` answers out of RR0 and the 6522 — without it `in_chk()` returns
0 before it ever reaches the count (§12).

#### The carrier clause, which is the one judgement call

`in_chk()` asks `ttgmdm()` for carrier **before** it asks how many bytes are
waiting, and treats "no DCD" as a lost connection: it closes the device and
returns -2. A three-wire cable does not carry DCD, so a literal RR0 would end
every transfer at the first `ttchk()` — turning a working port into a broken
one by making `ttgmdm()` honest.

C-Kermit has already said whether it wants carrier to mean anything here.
`ttopen()` and `ttpkt()` call `carrctl()`, whose entire body is *set `CLOCAL`
when carrier is not to be required*, and those are the settings cached in
`victor_ttcur`. So: **when `CLOCAL` is set, report carrier present; otherwise
report RR0 as it reads.** With `CARRIER-WATCH ON`, or a modem connection,
`CLOCAL` is clear and the real bit is what comes back. CTS, DSR, DTR and RTS
are always reported truthfully.

### Sources

`~/projects/kermit/msr313src/msxv90.asm` is the primary reference for
everything above; it is Columbia University code under the same terms as the
rest of this tree. `~/projects/myfreedos` (`kernel/victor_int14.asm`,
`victor_serial_debug.asm`, `victor_pic.asm`) remains the reference for the
MS-DOS 3.1 ISR stack-switching prologue and for a TX path proven at 38400,
and `~/projects/kermit/victor9000/vickermit.c` is a third opinion on chip
init. Where they disagree, `msxv90.asm` is the one that shipped for this
machine.

Channel choice: **use channel A for Kermit** where possible, leaving channel B
for `CTTY COM2`. They share IRQ1, so the ISR must poll both RR0s; but only one
of the two owners can be Kermit at a time.

---

## 12. The layers below C-Kermit

`ckutio.c` and `ckufio.c` are stock Unix modules that compile clean and
express everything in POSIX terms. Keep them. What has to be supplied is the
layer *underneath*, and under the §2 architecture that layer is small.

Much of this section was written against `ia16-elf-gcc` + newlib, whose
`libdos-m.a` was the library underneath at the time. The **conclusions
transferred** — the Open Watcom DOS runtime covers the same INT 21h surface,
and covers rather more of it — but where a specific library is named below,
read it as history and check §9d for what replaced it.

### Does the Unix TTY layer sit on a hosted DOS libc?

**Yes.** This was the main open question and the answer is unambiguous.

`ckutio.c` is 480KB of source and looked like the likeliest place to need a
Victor-specific rewrite. Measured:

| Configuration | Errors |
|---|---:|
| No termios variant selected (falls back to V7 `sgtty`) | 80 |
| `-DPOSIX`, `<sys/termios.h>` missing | 1 |
| `-DPOSIX` with a real `<sys/termios.h>` | **0** |

All 80 errors in the first row were `struct sgttyb`, `RAW`, `CBREAK`, `CRMOD`,
`TANDEM` — the ancient BSD interface, selected only because no termios macro
was defined. With `-DPOSIX` it uses termios and **compiles clean**.

`ckufio.c` needed exactly one change (the inode check, §8).

**Recommendation: keep both modules. Do not write a Victor platform module.**
The termios layer becomes a thin translator onto our own driver, not a call
into someone else's serial API:

| termios call | maps to |
|---|---|
| `cfsetospeed` / `cfsetispeed` | 8253 divisor write (76800 / baud) |
| `cfgetospeed` / `cfgetispeed` | read back the cached divisor |
| `tcsetattr` | µPD7201 WR3/WR4/WR5 — raw 8N1, no processing |
| `tcgetattr` | return the cached `struct termios` |
| `tcflush` | reset ring head/tail |
| `tcsendbreak` | WR5 send-break bit, timed |

and the file descriptor `ckutio.c` opens for the line reads and writes the ring
buffers directly.

**The header exists now: `victor/sys/termios.h`**, reached via `-Ivictor`. It is
the driver's interface, not a generic POSIX header, and two decisions in it are
load-bearing:

*`B*` values are small ordinals (`B9600` is 13), not literal baud rates.* This
is a 16-bit safety property. C-Kermit passes a `B*` value around as an opaque
token through whatever variable is at hand — `tthang()` in `ckutio.c` does
`int spdsav; spdsav = cfgetospeed(&ttcur);` with a plain 16-bit `int`. Under the
BSD convention where `B38400 == 38400` that saves as −27136 and restores a
garbage speed. With ordinals every value is ≤ 16 and nothing can truncate.

*The set of `B*` constants defined **is** the machine's speed capability.*
`ttsspd()` wraps each high-speed arm of its switch in `#ifdef B<rate>`, so an
undefined rate makes C-Kermit reject `SET SPEED` for it rather than program an
impossible divisor. Given `divisor = 76800 / baud`, only exact divisors are
clean:

| baud | divisor | | baud | divisor |
|---:|---:|---|---:|---:|
| 76800 | 1 | | 2400 | 32 |
| 38400 | 2 | | 1200 | 64 |
| 19200 | 4 | | 600 | 128 |
| 9600 | 8 | | 300 | 256 |
| 4800 | 16 | | 150 | 512 |

**57600 and 115200 are not achievable** on the Victor's 1.2288 MHz clock — they
need divisors of 1.33 and 0.67 — and are deliberately left undefined. **76800,
not 115200, is the ceiling** (divisor 1). An earlier draft of this section said
"57600 → 1", which was wrong: divisor 1 yields 76800.

`B1800` is the one inexact entry, present only because `ttsspd()`'s `case 180:`
arm is unguarded; divisor 43 gives 1786 bps (−0.8%), well inside async framing
tolerance. `B110` (divisor 698) and `B134` (divisor 573) match the divisors the
FreeDOS Victor driver already uses.

If per-byte overhead through the library's `read()` turns out to hurt at 38400,
add a `VICTOR9K` fast path in `ttinl()` only — that is one function, not a
rewrite. (As of §11b, `read()` for the communications device is already ours:
it drains the receive ring directly. See `ckvictor.c` §0d.)

### libgloss: mostly already there

An earlier draft of this document said the INT 21h shim would be "the bulk of
the remaining non-driver work." That was wrong, and the correction is the single
most useful measurement in this section. Measured on `libdos-m.a`, the medium
multilib of the retired gcc build — and the Open Watcom DOS runtime is a
superset, which is why retiring gcc *deleted* code rather than adding it (§9d).
Already implemented, over INT 21h:

> `open` `close` `read` `write` `lseek` `stat` `fstat` `isatty` `chdir`
> `getcwd` `mkdir` `rmdir` `unlink` `rename` `access` `chmod` `dup` `dup2`
> `sbrk` `exit` `getpid` `time` `gettimeofday` `times` `putenv` `setenv`
> `realpath` `usleep` `abort`

That is the whole of what `ckufio.c` reaches for, plus most of the process-model
surface. Combined with `dos-m-c0.o` and `dos-mm.ld`, a DOS `.EXE` is a link
away.

### What is actually still missing

| Missing | Notes |
|---|---|
| ~~`<sys/termios.h>`~~ | **Done** — `victor/sys/termios.h`, see below. |
| **The termios functions** | Not a separate work item — this *is* the serial driver (§11). No termios symbol exists in any library in the toolchain, so there is nothing to collide with. |
| ~~`opendir` / `readdir` / `closedir`~~ | **Done** — `ckvictor.c`, over INT 21h `4Eh`/`4Fh`. See below. |
| ~~`utime`, `umask`, `sleep`, `creat`~~ | **Done** — `ckvictor.c`. |
| ~~`ioctl` / `FIONREAD`~~ | **Done**, and it was not on this list. See "The `FIONREAD` hole" below — this was the most consequential gap in the section. |

### Directory reading: done — and then handed back to the library

> **History.** This port supplied its own `opendir`/`readdir`/`closedir` over
> the DOS DTA while it was built with gcc, because newlib's `<sys/dirent.h>`
> declared them and shipped none of them. **Open Watcom's runtime implements
> all three**, over the same FindFirst/FindNext, so as of 2026-08-05 they are
> gone from `ckvictor.c` along with the rest of the retired build. What
> follows is kept because the DTA-contention finding in point 2 is real,
> non-obvious, and will bite anyone who writes this again on any DOS libc.

`<sys/dirent.h>` declares the three functions and then says, verbatim,
`/* FIXME: implement these! */`. `struct __msdos_DIR` is only ever forward
declared, so its definition was entirely ours to choose — nothing in the
toolchain constrains the ABI.

The header's `struct dirent` is not an accident. It is a DOS DTA with field
names on it: `d_dta[21]`, `d_attr` at 21, `d_time` at 22, `d_date` at 24,
`d_size` at 26, `d_name` at 30 — byte for byte what INT 21h `4Eh`/`4Fh` writes.
So the DTA points straight at the caller's `struct dirent` and `readdir()`
copies nothing. `ckvictor.c` asserts those offsets at compile time.

**The DTA is global state, and it is contested.** It belongs to the PSP, not to
a search, and FindNext takes its continuation state from wherever the DTA
currently points. Two consequences, and the second was a surprise:

1. Each open `DIR` carries its own DTA. `traverse()` holds one per directory
   level, so this is the normal case, not an edge case.
2. **The DTA is re-pointed before *every* FindNext, never once at open time.**
   This is not tidiness. `libdos-m.a`'s own `stat()` is implemented over INT 21h
   `1Ah` + `4Eh` — it sets the DTA to its own buffer and does not restore it —
   and `traverse()` calls `stat()` on each entry *inside* the `readdir()` loop.
   Setting the DTA once per `DIR` would leave the next FindNext continuing
   `stat()`'s search instead of ours. Measured from the library disassembly,
   not assumed.

`opendir()` performs the FindFirst so that a nonexistent directory fails at
open (DOS error 3) as every caller assumes, and holds the entry for the first
`readdir()`. DOS error 2 — directory exists, nothing matched — is an empty
`DIR`, not an error.

The reference implementation at
`~/projects/newlibc/phase3_newlib/libgloss/dirent.c` was **not** reused: its two
defects (`LIBGLOSS_MAX_DIRS` of 2, single shared static `current_entry`) are
exactly the two things the recursion cannot tolerate, and it has no answer to
the `stat()` DTA collision above.

Frames: `opendir` 146 bytes (not live during recursion — it returns before the
`readdir()` loop), `readdir` 8 bytes.

### The `FIONREAD` hole

This was not on the missing list and should have been. It is worth more than
either question §15 was tracking.

`ckutio.c` under `-DPOSIX` defines `NOSYSIOCTLH` ("No ioctl's allowed") and
skips `#include <sys/ioctl.h>`. The toolchain has no such header and no `ioctl`
symbol in any library, so **`FIONREAD` was undefined**. `in_chk()` — which is
the whole of `conchk()` and `ttchk()` — then falls through its entire cascade
of FIONREAD / `rdchk()` / `select()` / `poll()` and lands on the branch its own
comment calls *"the hideous hack used in System V and POSIX systems"*, where
the console's character-ready test is inferred from a **SIGQUIT handler**.

MS-DOS has no SIGQUIT. So as the tree stood, both arms returned a constant:

```
conchk()  ->  in_chk(0, 0)      ->  always 0
ttchk()   ->  in_chk(1, ttyfd)  ->  always 0
```

`ckutio.c` says plainly what that costs (~line 800):

> We really, really, REALLY want FIONREAD, because it is the only way to find
> out not just *if* stuff is waiting to be read, but how much, which is
> critical to our sliding-window and streaming procedures.

A `ttchk()` hard-wired to 0 is not cosmetic; it is the input to windowing and
streaming, which are milestone steps 8 and 9.

Fixed with `victor/sys/ioctl.h` (`FIONREAD` plus the prototype) pulled in by
`ckvictor.h`, and `ioctl()` in `ckvictor.c`. Defining `FIONREAD` switches **on**
exactly one reachable call site — `in_chk()`'s `ioctl(fd,FIONREAD,&n)` — and
switches **off** two SIGQUIT workarounds that could never have worked here.
Every other `ioctl()` call in `ckutio.c` is guarded by a `TIOCxxx`/`TCxxx` macro
this port does not define; those belong to the pre-POSIX sgtty interface.
`myfillbuf()`, the other `FIONREAD` consumer, sits inside `#ifdef MYREAD` and is
not compiled.

Console side is INT 21h `AH=0Bh`, which answers *whether* not *how many*, so it
reports at most 1 — enough for `conchk()`, whose callers test against zero.

The serial side was a stub returning 0. It became INT 21h `AX=4406h` (IOCTL,
get input status), the same primitive §16b's blocking read waits on, and that
answers *whether* as well — so at most 1 there too. Honest, but nearly useless
to the caller that wanted it: `sdata()` in `ckcfns.c` only slides its window
when `ttchk()` exceeds `4 + bctu`, so 1 never triggered it and the port sent a
full window before reading ACKs. Upstream has been here before — see the
`GEMDOS` arm of that same test, which exists because the Atari ST's `ttchk()`
could also only return 0 or 1.

**Both of those are fixed as of §11b.** For the communications device
`FIONREAD` is now the depth of the driver's receive ring, `(head - tail) &
mask` — a real count, which is what milestone step 8 needs. `AX=4406h` remains
the answer for every other device and for the line before the driver installs.

There was a *second* reason `ttchk()` reported 0 on the communications device,
missed the first time round and upstream of everything above. `in_chk()` checks
carrier before it checks for bytes:

```c
} else if (xlocal && !netconn && ttcarr != CAR_OFF) {
    x = ttgmdm();               /* So get modem signals */
    if (x > -1) { ...check DCD... } else { ...; return(0); }
```

`ttcarr` initialises to `CAR_AUT`, this port is always `xlocal`, and `ttgmdm()`
on a platform with no `TIOCMGET` and no `K_MDMCTL` falls all the way through to
`return(-3)`. So `in_chk()` returned 0 without ever reaching `FIONREAD`, and
the `AX=4406h` answer above was **correct but unreachable for `ttyfd`**.

Also fixed in §11b, and it needed nothing but a macro: `ckutio.c` selects that
whole arm with `#ifdef TIOCMGET → #define K_MDMCTL`, so defining `TIOCMGET` in
`victor/sys/ioctl.h` is the entire switch, and `ioctl()` answers it out of RR0
and the 6522. Note the two are useless apart — a real byte count that
`in_chk()` never reaches is no count at all, which is why they arrived
together. `conchk()` was never affected: it passes `channel = 0` and skips the
carrier block entirely.

`TIOCMBIS` and `TIOCMBIC` are deliberately left undefined. `tthang()` prefers
them when they exist, and this port hangs up 3.13's way — `B0` through
`tcsetattr()`, dropping DTR and RTS in WR5 (§11a) — so defining the bit-set
pair would silently move `tthang()` onto a second, redundant path.

### What `ckvictor.c` still has to define

The division of labour with the Open Watcom runtime, as it stands after the
gcc build was retired. Anything the library supplies is **not** written out
here — that is what took 1,113 lines off the file (§9d).

**The library's, so not ours:** `open` `close` `read` `write` `lseek` `stat`
`fstat` `creat` `utime` `umask` `sleep` `execl` `execvp` `isatty` `chdir`
`getcwd` `mkdir` `rmdir` `unlink` `rename` `access` `chmod` `dup` `dup2`
`getpid` `putenv` `realpath` `time` `abort`, and `opendir` / `readdir` /
`closedir`. Watcom's `stat()` also answers `"."` and `"./"`, which the
retired build's did not — see §16f.

`NOREALPATH` is redundant against a library that has `realpath`. Left defined:
it costs nothing and removing it would pull `realpath` into the link.

**Genuinely ours, and stubbed or implemented in `ckvictor.c`:** `fork` `wait`
`getuid` `geteuid` `getgid` `getegid` `setuid` `setgid` `getppid` `getpgrp`
`tcgetpgrp` `getlogin` `getpwnam` `getpwuid` `getpwent` `setpwent` `endpwent`
`ttyname` `ctermid` `alarm` `sysconf` `readlink` `link` `kill` `gettimeofday`
`uname`, the whole termios layer and the 7201 driver (§1b, §1e), `ioctl` — and
the symbols owned by excluded modules (`conect`, `connv`, `mdmtyp`, `nvlook`,
`ck_bracketaddr`).

`ioctl` is in no DOS libc, which is the point of `victor/sys/ioctl.h` and of
the `FIONREAD` section above.

### Console: does anything shortcut to BIOS?

**No, for the library this was measured on.** Answered by disassembly, not by
assumption. Every interrupt instruction in `libdos-m.a` — the retired gcc
build's DOS libgloss — is `INT 21h`, 37 of them, no exceptions:

| Object | INT | Object | INT |
|---|---|---|---|
| `libdos-m.a` (all 24 objects that trap) | `21h` only | `libc.a` | **no interrupts at all** |
| `dos-m-c0.o` (crt0) | `21h` ×2 | `libgcc.a` | none |

No `INT 10h`, no `INT 16h`, no `INT 13h`, no `INT 14h`, no BIOS data area. The
standard handles get no special treatment whatsoever: `_read_r` is a bare
`AH=3Fh` and `_write_r` a bare `AH=40h`, with the fd passed straight through to
DOS. **The one-binary-two-DOSes property of §2 holds at the library layer.**

### Re-measured against Open Watcom: rule 6 still holds

The toolchain change put that claim back in doubt, so it was re-run rather
than inherited. Method: take the 239 library modules `wlink`'s map says are
actually in `ckermitw.exe`, extract each with `wlib -x`, disassemble with
`wdis -a`, and tabulate every `int` instruction. Complete result:

| vector | sites | what |
|---|---:|---|
| `21h` | 86 | MS-DOS |
| `34h`–`3Dh` | 89 | **8087 emulator** — `emu87.lib` / `math87l.lib` |
| `3` | 1 | `enterdb`, the debugger-entry stub |

**No `INT 10h`, `13h`, `14h`, `15h`, `16h`, `17h` or `1Ah` anywhere in the
linked image.** `clibl.lib` does contain BIOS-using modules — `biosfunc`
(the `_bios_*` family), `b_disk`, `b_timofd`, and `dointr`, whose `int86()`
carries a dispatch table of all 256 vectors and is what produced a spurious
"every vector appears once" tail on the first scan of the whole library —
**and none of the four is linked.** `intdos()`/`intdosx()` resolve to
`intd086`/`intdx086`, which hard-code `INT 21h`; `_dos_getvect`/`_dos_setvect`
(the §11b vector hook) come from `d_getvec`/`d_setvec`, also `21h`.

The 34h–3Dh block is worth knowing about even though it is not a rule 6
problem: those are the reserved software vectors Watcom's floating-point
emulator hooks at startup, and C-Kermit reaches FP through the transfer-rate
display. They are not BIOS and not hardware; they work identically on both
DOSes.

`kbhit()` is the one Watcom call this port deliberately refuses — it reads the
BIOS keyboard — and `ckvictor.c` §0b says so at the substitute. The scan above
confirms nothing else pulled BIOS in behind it.

(An earlier scan appeared to find `int $0x0` and `int $0xfe` in `libc.a`. That
was 32-bit misdecoding of 16-bit code — `objdump` defaults to `elf32-i386` for
these objects. Under `-Mi8086` there are none. Pass `-Mi8086` when reading this
toolchain's output.)

There is a consequence, and it is the reason the `FIONREAD` section above
exists. DOS handle I/O on `CON` is *cooked*: `AH=3Fh` line-edits and blocks
until Enter. It cannot do the single-character raw read `coninc()` needs, nor
any non-blocking poll. So "no BIOS" is necessary but not sufficient — the raw
console path has to come from the character functions (`AH=06h`/`07h`/`08h`/
`0Bh`), which is what `ioctl(0,FIONREAD)` now uses. **`coninc()`'s own
`read(0,&ch,1)` is still cooked and is the next console work item** (milestone
step 3); the fix is a `read()`/`write()` pair in `ckvictor.c` that intercepts
fds 0–2 and delegates everything else to the library, which the linker resolves
in our favour without touching upstream.

---

## 13. Milestone

```
CKERMIT
C-Kermit> set line com1
C-Kermit> set speed 38400
C-Kermit> send foo.bin
C-Kermit> receive
C-Kermit> server
```

Order of work:

1. ~~**`<sys/termios.h>`.**~~ **Done** — `victor/sys/termios.h`. All 24 modules
   compile clean. (DGROUP at the time: 32,311 static under gcc. Today, from
   `wlink`'s map and including libc: 39,424 of 65,536.)
1a. ~~**`opendir`/`readdir`/`closedir`, the four small stubs, `ioctl`/`FIONREAD`,
   and the guard-macro collisions.**~~ **Done** — all in `ckvictor.c`; still
   24 objects, 0 warnings, DGROUP unchanged (§12, §14).
2. ~~**Link the `.EXE`.**~~ **Done** — `ckermitw.exe`, 228,554 bytes. It
   required `NOICP`, and under the retired gcc build also
   `-mnewlib-nano-stdio` (§9c).
3. ~~**A prompt, on FreeDOS.**~~ **Superseded and done differently.** There is
   no `C-Kermit>` prompt — `NOICP` removed it (§9c). What was proven instead,
   under MAME on FreeDOS for Victor: the binary loads, initialises, parses its
   command line, prints correctly formatted output through an INT 21h-only
   console path, finds a file, starts the protocol engine, and exits cleanly
   (§16). **Not yet proven on Victor MS-DOS 3.1** — that is still the other
   half of the dual-target claim and needs a 3.1 boot image.
3a. ~~**Fix wildcard expansion** (§15, §16f).~~ **Done — §16g.** `-s *.COM`
   found nothing; `-s *.TXT` now transfers, against one match and against
   three. Four causes: `SSPACE`'s greedy allocator and `MAXWLD`'s up-front
   array (both fixed, and both guarded upstream edits), an inability to
   `stat(".")` (a `libdos-m` gap Watcom does not have), and a fourth that
   never reproduced under Open Watcom and is closed as retired rather than
   diagnosed.
3b. ~~**Make `read()` block, and make `alarm()` fire.**~~ **Done** — §16b,
   `ckvictor.c` §0d. The port now retransmits on a timeout and
   gives up in the protocol-defined way instead of dropping the line. This
   also measured the answer to a question step 4 used to leave open: the OEM
   `\dev\seriala` driver delivers the first two bytes of a packet and then
   stops, so **there is no way to reach step 5 without step 4**.
4. ~~**7201 driver in `ckvictor.c`, on MS-DOS Kermit 3.13's model** (§11).~~
   **Done**, in both halves:
   - 4a. ~~**Configuration through the OEM driver's IOCTL control block**
     (`AH=44h AL=03h` on the handle `ttopen()` already holds).~~ **Done** —
     §11a, §16c. Pure INT 21h, and the values read back as written.
   - 4b. ~~**Our own ISR and RX ring** against the memory-mapped chip, with
     RR1 overrun recovery from the first version.~~ **Done** — §11b, §16d.
     Receive was the hard half (§16b); transmit is ours too now, polled, so
     the OEM driver is out of the data path in both directions.
5. ~~**`SEND` one small binary file** at 9600 to a known-good Kermit, short
   packets, window 1, streaming off.~~ **Done — §16d.** 72 bytes off the
   Victor's disk, byte-correct at the far end, under MAME on Victor MS-DOS
   3.1. **This was the real milestone and the port has reached it.** §16g
   completes it: the wildcard and multi-file forms of the same send, and the
   driver's loss counters at zero through all of it. Not yet
   done on real hardware. (The retired gcc build did the same thing, §16e,
   but needed its packet pools halved to fit its near heap — which is the
   measurement that ended the two-toolchain experiment.)
6. ~~**`RECEIVE`, then `GET`, then `SERVER`** — still at 9600.~~ **Done.**
   **`RECEIVE` — §16h**: 2,048 bytes containing every byte value, received
   into `A:\` and sent straight back, byte-exact both ways, loss counters
   0/0. It took two fixes: `access()` cannot be trusted about a FAT root
   (`ckvictor.c`), and the DOS runtime was translating every stream in both
   directions, which is also the correction to §16d's "byte-correct".
   **`GET` and `SERVER` — §16i**: `-g` fetches 512 bytes byte-exact from a
   host server and `-f` shuts it down; `-x` serves `GET` and `SEND`
   byte-exact and exits on FINISH. Server mode needed a decision rather than
   a fix — C-Kermit 11 disables every server capability in local mode, and
   `NOICP` removes the prompt where you would type `ENABLE`, so
   `ckvictor.c` settles it at startup and `--safe-server` narrows it.
   `REMOTE DIRECTORY` streams its listing and never terminates it; that is
   open, and outside this step.
7. ~~**Bring up the RX ISR and ring buffer** as its own task, standalone, on
   real hardware.~~ Superseded by 4b, except for the real-hardware half.
   What is left of it: run §16d's transfer **on a real Victor**, and settle
   the µPD7201 interrupt-acknowledge question `victor_int14.asm` flags —
   ours works under emulation without the sequence, which is evidence and
   not an answer. The dropped-byte instrumentation asked for here exists:
   two counters in the handler, logged at release.
8. **Turn on long packets, then windows, then streaming**, one at a time,
   re-measuring free memory at each step. This is where the ring's missing
   interrupt-level flow control starts to matter (§11b).
   - 8a. **Long packets — DONE.** §16j got the negotiation
     (`MAXL=94, MAXLX=3999, WINDO=1`, up from `MAXL=90, MAXLX=90`) and hit
     what it called a receive ceiling in (480, 968]. §16k found that was
     two ceilings: `-d` at ~25 ms per received byte, and under it
     `V9K_RXBUFSIZ` at 512 with `rxpeak` sitting at 502. The ring is now
     4096 and `DRPSIZ` is **4000** in the tree; **32,768 bytes transfer
     byte-exact at 582 cps**, longest packet 3,605 on the wire,
     `rxlost=0 rxfull=0`.
     Getting even this far was not a matter of raising `SBSIZ`/`RBSIZ`/
     `MAXSP`/`MAXRP`: those reach the wire only through `dofast()`, which no
     `NOTCPIP` build ever calls, so **every transfer in §16d–§16i ran 90-byte
     packets** and those four symbols had never done anything.
   - 8b. **Windows.** `DFWSIZ` is deliberately still 1. This is the step
     that removes the one-packet-in-flight property the missing flow
     control has been relying on, so it wants `tcflow()` implemented first
     or a much larger ring.
   - 8c. **Streaming.**
9. **Push to 19200, then 38400.**

Only after all that is CONNECT worth considering — and it should be written
fresh as a small polling loop over `ttinc()`/`coninc()` in `ckvictor.c`, not
ported from `ckucon.c` (needs `fork()`) or `ckucns.c` (needs `select()`).

---

## 14. Compile log

> **History — the retired `ia16-elf-gcc` build.** This is the record of
> getting 24 upstream modules to compile for a 16-bit DOS target at all, and
> most of it is about problems that are a property of C-Kermit rather than of
> the compiler. The current build's numbers are in §4 and §9.

All 24 modules in §5 compiled with **zero errors** at `-mcmodel=medium -Os`,
reproduced end to end:

```
$ make -f victor9k.mak            → 24 objects + CKERMIT.EXE (218KB), 0 errors
  --- near data (DGROUP), from the linker, including libc ---
    end of .bss = 52000 of 65536 (79%)
    left for heap + stack = 13536
```

**Trust the linker's figure, not object sizes.** That build's `sizes` target
measured objects, and `ia16-elf-size` files `.rodata` under "text"; the real
near-data total was 79%, not 49.3%, and libc added ~26KB on top of the objects.
See §9c — this mismeasurement is what hid the fact that the interactive command
parser could never fit. **`victorow.mak`'s `sizes` target does not repeat the
mistake: it reads `wlink`'s map**, which is the only thing that knows what
ended up in DGROUP.

Warnings: **26 lines, all pre-existing upstream** (20 of them one repeated
`ckcfnp.h` complaint, the rest implicit declarations in code paths this port
does not take). The 23 `MAXWS` redefinition warnings are gone. This session
added none.

**The makefile had no header dependencies** until now, so editing `ckvictor.h`
— which is where the entire configuration lives — rebuilt nothing and `make`
reported success over stale objects. That is fixed (`$(OBJS): $(CONFIG_H)`).
It is mentioned because it briefly produced a false "0 warnings" reading here;
**verify with `rm -f *.o` before trusting any build-wide count.**

`ckutio.c` was the last holdout, blocked solely on `<sys/termios.h>`; supplying
`victor/sys/termios.h` cleared it with no other change.

DGROUP is **unchanged** after adding `opendir`/`readdir`/`closedir`, `ioctl`,
`utime`, `sleep` and `creat`: all of it is code, which is far, and the new
static data is zero. Text grew 685 bytes. The `CKMAXNAM` change moved nothing
in DGROUP either — it is a stack lever, not a static-data one (§9).

**`MAXWS` is resolved.** `ckvictor.h` set it to 8 and it never took effect:
unlike `MAXSP` / `MAXRP` / `SBSIZ` / `RBSIZ`, which `ckcker.h` wraps in
`#ifndef`, `ckcker.h` defines `MAXWS` **unconditionally**, so it always won.
Measured by probe: **`MAXWS` is 32**; `SBSIZ`/`RBSIZ` are 4096 as intended and
`MAXSP`/`MAXRP` 1024 as intended.

The buffer arithmetic in §9 is therefore **intact** — under `DYNAMIC` the pools
are the literal `SBSIZ`/`RBSIZ`, and only the non-`DYNAMIC` path derives them
from `MAXWS`. What `MAXWS = 32` actually costs is ~736 bytes:

| | at `MAXWS` 32 | at `MAXWS` 8 |
|---|---:|---:|
| static `sbufuse[]` + `rbufuse[]` | 128 B | 32 B |
| heap `s_pkt` + `r_pkt` (14 B each) | 896 B | 224 B |

and it buys nothing, because the negotiated window can never exceed what the
pool carves. (This paragraph used to say "because `dofast()` computes
`wslotr = RBSIZ/MAXSP = 4` slots". **`dofast()` is never called in this
build** — §16j — so the window came from `DFWSIZ`, which was 1. The
conclusion is unchanged and the arithmetic was never load-bearing here, but
the reason given for it was wrong.)
The dead `#define` has been removed from `ckvictor.h` (which is what cleared the
warning) and the real value documented there. **Reclaiming the 736 bytes needs
a sixth guarded upstream edit — see §15; not done unilaterally.**

Problems hit and resolved, in order:

| Problem | Resolution |
|---|---|
| `sig_t` conflicts with newlib | `CK_NO_SIG_T` guard |
| `struct zfnfp` incomplete | Self-inflicted: `-DZFNQFP` *suppresses* the struct, which lives inside `#ifndef ZFNQFP`. Let `-DUNIX` define it. |
| `ckucmd.c` uses `stdin->_IO_read_end` | `VICTOR9K` → `coninc`/`conchk` |
| `ckuusx.c` array "too large" | `SCANFILEBUF` 49152 → 2048 |
| `ckufio.c` `d_ino` missing | `VICTOR9K` branch; FAT has no inode |
| `ckufio.c` `getppid` conflict | newlib prototype; stub matches it now |
| `ckutio.c` 80 × `struct sgttyb` | `-DPOSIX` selects termios |
| `ckutio.c` `sys/termios.h` missing | supplied as `victor/sys/termios.h`, reached via `-Ivictor` (§12) |
| `ckvictor.c` prototype conflicts | Rewrote stubs as ANSI matching newlib |
| `MAXWS` redefined (warning) | `ckcker.h` defines it unguarded and always wins; removed the dead `#define` (above) |
| `conchk()`/`ttchk()` constant 0 | `FIONREAD` undefined → SIGQUIT fallback. Supplied `victor/sys/ioctl.h` + `ioctl()` (§12). `ttchk()` needed `TIOCMGET` as well, and a real count from §11b's ring |
| `traverse()` 1066-byte recursive frame | `CKMAXNAM` was 1024 via `FILENAME_MAX`; pinned to 16 → 98 bytes (§9) |
| `opendir` etc. absent | Implemented over INT 21h `4Eh`/`4Fh`, one DTA per `DIR` (§12) |
| `dup2`/`putenv`/`getpid` duplicate | Stubs removed; `libdos-m.a` has all three (§12) |

Two things worth knowing about reading this toolchain, both of which cost time:

- **`objdump` defaults to `elf32-i386`** for these objects and silently
  misdecodes 16-bit code as 32-bit. Always pass `-Mi8086`.
- **The 8088 has no `SETcc`** (386 and later). To get the carry flag out of an
  inline-asm block use `sbb %0,%0` — 0 when clear, −1 when set. That is the
  idiom `libdos-m.a` itself uses in `_write_r`.

---

## 16. It runs. First execution on an emulated Victor 9000

> **History — the retired `ia16-elf-gcc` build, on FreeDOS for Victor.** The
> defects it found are real and two of them shaped the port permanently (the
> CR/NL translation, and the `%ds` scratch-register trap that is the reason
> `DOS_DS_CALL` existed). Both belong to a toolchain that is no longer here.
> §16a onward is Victor MS-DOS 3.1 and is where the port actually lives.

`CKERMIT.EXE` links (218KB) and **runs on FreeDOS for Victor 9000 under MAME**.
This is emulation, not hardware — but it is the Victor machine, the Victor
FreeDOS, and the real binary.

### Reproducing

```sh
# 1. build
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victor9k.mak"

# 2. drop CKERMIT.EXE into the FreeDOS image.  The Victor's disk is NOT an
#    MBR disk -- sector 0 is a 128-byte Victor label ("V9KSYS-"), and the
#    FAT16 filesystem starts at byte 66048.  mtools handles it with an
#    explicit offset:
cp ~/projects/myfreedos/boot/victor/2026.07.17e_freedos_stage1.img k1.img
printf 'drive c:\n file="%s/k1.img"\n offset=66048\n mtools_skip_check=1\n' "$PWD" > mtoolsrc
MTOOLSRC=./mtoolsrc mcopy -o ckermit.exe c:/CKERMIT.EXE

# 3. boot it, typing past FreeCom's date/time prompts
cd ~/projects/mame && ./mame victor9k -rompath ~/projects/mame/roms \
  -ramsize 896K -hard1 k1.img -window -skip_gameinfo \
  -seconds_to_run 85 -snapshot_directory snaps -nomaximize \
  -autoboot_delay 30 -autoboot_command "\n\nCKERMIT -h\n"
# MAME writes a final frame to snaps/victor9k/0000.png
```

**Watch out for the emulated keyboard in `-autoboot_command`:** digits come
through shifted. `V9KTEST.COM` was typed as `V(KTEST.COM`, which produced a
convincing but entirely bogus "No files for -s". Prefer digit-free filenames
in automated runs.

### What works

| | |
|---|---|
| Loads and relocates | MZ image, 2,989 relocations, medium-model far code |
| `crt0`, DGROUP, `main()` | reaches C-Kermit's own initialisation |
| Console output | via our `_write_r`, correctly formatted |
| Command-line parser | `CKERMIT -h` prints usage; `argv[0]` picked up from the PSP |
| Clean exit | returns to `A:\>` |
| **File lookup and transfer start** | `CKERMIT -s CGATEST.COM` finds the file, opens it, starts the protocol, and then blocks in the serial layer — which is correct, because there is no driver yet (§11) |

### What broke, and what it taught

**1. `\n` went out as bare LF.** DOS handle writes are literal, so C-Kermit's
output walked diagonally off the screen. `libdos-m.a`'s `_read_r`/`_write_r`
are bare `AH=3Fh`/`AH=40h` with the fd passed straight to DOS — right for
files, wrong for the console in both directions (handle reads on `CON` are
also cooked, so `coninc()` would block for a whole line). Fixed by overriding
`_read_r`/`_write_r` in `ckvictor.c` — the `_r` forms, not `read`/`write`,
because newlib's stdio calls those directly and intercepting the public
wrappers would catch `conol()` but miss every `printf()`.

**2. `%ds` is a scratch register, and INT 21h reads DS:DX.** This one is worth
remembering. In this memory model `SS == DS == DGROUP`, and ia16-gcc exploits
it: locals and statics are addressed with an `%ss:` prefix, `%ds` is used as a
general scratch register, and it is restored with `push %ss; pop %ds` only on
return. So at any inline-asm site `%ds` may hold anything — in `_write_r` it
held `0x4000`, a spilled copy of the `AH=40h` constant. DOS then wrote from
`0x4000:DX`: **it returned success, the byte count was correct, and the screen
filled with the wrong memory.** Every asm block that hands DOS a pointer now
goes through the `DOS_DS_CALL` macro, which sets DS from SS around the
interrupt (`POP` does not disturb the flags, so the carry test still works).

**3. Do not get the carry flag with a second `"=r"` output.** `sbb %1,%1` looks
natural, but on ia16 the `r` class **includes the segment registers** and gcc
will allocate one. Each block now has exactly one output, in `%ax`, and turns
CF into a value with a branch over a constant load.

**4. `malloc` ran out, and said so.** `CKERMIT -s V9KTEST.COM` answered
`fnlist: no memory for cmargbuf` — a 129-byte allocation failing. Two 4096-byte
packet pools plus `s_pkt`/`r_pkt` had taken nearly all 13,536 bytes of the
shared heap/stack space (§9c). `SBSIZ`/`RBSIZ` are 2048 each now, and the
message is gone. **The heap is the tightest resource in this port** — tighter
than static DGROUP, which still has 21% free.

### Reading this toolchain's output

- **`objdump` defaults to `elf32-i386`** and silently misdecodes 16-bit code
  as 32-bit. Always pass `-Mi8086`. (An early scan "found" `int $0x0` and
  `int $0xfe` in `libc.a` this way; under `-Mi8086` there are none.)
- **The 8088 has no `SETcc`** — 386 and later only.

---

## 16a. Victor MS-DOS 3.1, and the first Kermit packet on a wire

§16 ran the gcc build on **FreeDOS for Victor**. Everything below is on
**Victor MS-DOS 3.1** — the OEM DOS, on `~/projects/mame/victor_kermit.img`
— which is the better target for this: DOS does not touch the serial port
on its own, and unlike the FreeDOS-for-Victor work in progress it is a
stable, vendor-tested build. Two things that looked like C-Kermit defects
under FreeDOS did not reproduce here, and at least one of them was FreeDOS's:
its `%COMSPEC%` points at `C:` while the machine boots as `A:`, so any
program large enough to overwrite FreeCom's transient part leaves the shell
unable to reload its own message strings.

**The Victor boots its hard disk as `A:`, not `C:`.** The image is not an
MBR disk and has no BPB, so mtools cannot touch it; use `vtg_image_util`
(`~/projects/vtg_image_util`, docs in
`~/projects/Victor9000-Disk-Image-Tools/README.md`):

```sh
vtg_image_util list ~/projects/mame/victor_kermit.img          # partitions
vtg_image_util copy ckermitw.exe ~/projects/mame/victor_kermit.img:0:\\CKERMITW.EXE
vtg_image_util copy ~/projects/mame/victor_kermit.img:0:\\DEBUG.LOG ./debug.log
```

### The serial harness

MAME's `-bitb socket` port is **single-use**: it is consumed by the first
connection, so probing it before starting MAME burns it. Run `socat` first
and let MAME be the only thing that connects.

```sh
socat -d -d TCP-LISTEN:8000,reuseaddr,fork pty,raw,echo=0,link=/tmp/v9000 &
~/projects/mame/mame victor9k -rompath ~/projects/mame/roms -ramsize 896K \
  -scsi:0 harddisk -hard1 ~/projects/mame/victor_kermit.img \
  -rs232a null_modem -bitb socket.127.0.0.1:8000 \
  -window -skip_gameinfo -seconds_to_run 120 -autoboot_delay 30 \
  -autoboot_command "\n\nKTEST\n"
```

`fork` matters: each MAME run gets its own child and its own pty, so the
listener survives across runs. `/tmp/v9000` only exists while MAME is
connected. Put the commands in a `.BAT` file on the image and autoboot that
— the emulated keyboard mangles characters (§16 notes digits; `CKERMITW -r`
also arrived as `CKERIT_R`), and a batch file removes the keyboard entirely.

### The Victor's serial port is a DOS device

`CONFIG.SYS` on this image loads `porta.exe` and `portb.exe`, which is what
makes `\dev\seriala` exist; `PORTSET A 9600 NONE 1 8` configures it.

This paragraph used to end "so there is a working OEM serial driver to aim at
long before ours (§11) exists." **That was wrong in both halves.** §16b
measured it losing every inbound packet after two bytes, so it does not work
as a data path; and MS-DOS Kermit 3.13 never used it as one — `msxv90.asm`
touches this device only through IOCTL, to program the chip's registers
(§11). What it *is* good for is exactly that: configuration, and a transmit
path good enough to have proved the whole engine above it.

**The device name has to be given as `/dev/seriala`, with forward slashes.**
C-Kermit treats `\dev\seriala` as a *relative path*, prefixes the working
directory and normalises the separators, and tries to open `A:\/dev/seriala`
— "Permission denied / can't open device". Leading `/` makes it absolute,
and MS-DOS accepts `/` as a separator.

### What ran

| | Open Watcom build | ia16-elf-gcc build |
|---|---|---|
| loads and relocates on MS-DOS 3.1 | yes | yes |
| `-h` usage text, correct CRLF | yes | yes (§16) |
| `argv[0]` from the PSP | `A:\CKERMITW.EXE` | `A:\CKERMITG.EXE` |
| opens `/dev/seriala` at 9600 | yes | yes |
| bytes put on the wire | **39** | **39, byte-identical** |
| completes a transfer | no | no |
| clean exit, device closed | yes | yes |

The 39 bytes, captured off the socat pty, are a correct Kermit Send-Init:

```
k e r m i t   - i r \r 001 9 SP S z / SP @ - # Y 3 ~ ^ ! SP z 0 _ _ _ F " U 1 A F \r
\_____________________/ \_/ ^ ^  ^  \_________________________________/ \___/
  autoupload command    SOH LEN SEQ TYPE=S      S-packet parameters      check
```

`kermit -ir` is the command C-Kermit sends to start a receiver at the far
end (`initproto()` in `ckcmai.c`); then SOH, a 25-byte length, sequence 0,
and type `S` with the negotiation parameters. **The protocol engine, the
file system, the command-line parser and the OEM serial path all work well
enough to put a valid packet on a real wire at 9600 bps.**

### Why the transfer does not complete

Both builds send the S packet exactly **once** and then print "No files were
transferred". That is not a Watcom defect — the two binaries emit the same
39 bytes and fail identically, which is the strongest equivalence result
this port has. It is the missing §11 work arriving from a new direction:

- `alarm()` is a stub that never fires (§1 of `ckvictor.c`), so there is no
  timeout to retry on;
- our `ioctl(FIONREAD)` answers 0 for any descriptor that is not the console,
  because there is no ring buffer to count — `ttchk()` therefore always says
  "nothing waiting";
- a DOS character-device read that has nothing to return comes back
  immediately, which C-Kermit reads as end-of-file rather than as a timeout.

**§16b fixes the first and third of those** and the port now retransmits;
the diagnosis of the second turned out to be incomplete, and §12's
`FIONREAD` section has the correction. Everything below this line stands.

A host-side C-Kermit receiver on the pty (`set line /tmp/v9000`,
`set carrier-watch off`, `receive`) was tried both after and before the
Victor's send, so that ACKs would already be buffered when it read. Neither
changed the outcome, which is consistent with the read side never getting as
far as looking.

### The parser build does not load

`CKERMICP.EXE` (the `KEEP_ICP` build, §9d) fails at load with FreeDOS's
"Allocation of DOS memory failed." Measured rather than guessed — from the MZ
headers, and from a 40-byte `.COM` that asks DOS via INT 21h `AH=4Ah` how
large a block it can have:

| | image | + minalloc | = needs |
|---|---:|---:|---:|
| gcc, serial-only | 206,464 | 33,280 | 239,744 (234K) |
| Watcom, serial-only | 210,192 | 19,024 | 229,216 (224K) |
| Watcom, + parser | 412,734 | 26,432 | **439,166 (429K)** |
| largest block DOS offers | | | **396,224 (387K)** |

42KB short. The machine was configured with `-ramsize 896K`; the kernel and
shell take the rest. So the parser is not out of reach — but it needs either
a leaner DOS or ~50KB trimmed from the image, and "it fits in DGROUP" was
never the same claim as "it loads."

---

### DOSBox is not a usable second target

Worth knowing, since the binary is INT 21h-only and ought to run anywhere.
Under **DOSBox 0.74** every invocation aborts before producing output with
`Exit to error: DOS:Illegal 0x33 Call FF` (INT 21h `AH=33h`, Ctrl-Break
get/set). Plain `dir` works, so the harness is fine. This is an old DOS shim
being strict, not evidence about Victor MS-DOS 3.1 — but it does mean the
fast iteration loop has to be MAME at ~85s per run. DOSBox-X would be worth
trying if a faster loop is wanted.

---

## 16b. The read blocks, the timeout fires, and Kermit starts retrying

§16a left the port sending exactly one Send-Init packet and then giving up.
This section is the fix, and it is entirely inside `ckvictor.c` and
`ckvictor.h` — **no new upstream edit; §8 still lists six.**

### Two defects, not one

The first was known. `myfillbuf()` in `ckutio.c` says in its own comment that
it must block:

> The new `myread()`/`mygetbuf()` always gets something. If it doesn't, then
> make it do so!

On Unix a raw tty read does that (VMIN=1, VTIME=0). On MS-DOS a handle read
of a character device with nothing pending returns 0 immediately;
`myfillbuf()` turns that into -3, `mygetbuf()` reports a dead line, and
`ttinl()` closes the connection.

The second was not known, and the fix does not work without it. §16a listed
"`alarm()` is a stub that never fires" as one of three contributing causes.
It is not a contributing cause — it is a **hard blocker on making the read
block at all**, because it is the only way out of a read that never
completes. Follow `ttinl()`'s two error paths:

| `myread()` returns | `errno` | `ttinl()` does |
|---|---|---|
| -3 | not `EINTR` | `ttclos()`, return -3 — **connection closed** |
| -3 | `EINTR` | `continue` — **retry, forever** |

Neither is a timeout. `ttinl()`'s own comment on the `EINTR` arm says why it
is safe — *"The outer alarm set above this loop still bounds how long these
retries can go on for"* — and that alarm was a stub returning 0. So a
blocking read with an `EINTR` escape would have hung the machine on a dead
line, and one without would have closed the connection on the first quiet
moment. The timeout return `ttinl()` actually documents, -1, is reachable
**only** through the `SIGALRM` handler's `longjmp` out of the read.

### What was done

`ckvictor.h` renames `read` to `v9k_read` for the whole build — an
object-like macro, so it rewrites `<unistd.h>`/`<io.h>`'s declaration into
the declaration of ours and every module gets a prototype that agrees with
its own runtime. `ckvictor.c` §0d supplies it, and **delegates**: anything
that is not `ttyfd` goes straight to the library's `read()`. That is why it
is a rename and not a definition of `read()` over the top of either
library's — §0c's console handling under gcc and Watcom's text-mode
translation both survive untouched. `ckvictor.c` undoes the rename on its
first line so it can still reach the real one.

The wait is INT 21h `AX=4406h` (IOCTL, get input status) in a loop, with the
read issued only once DOS says there is something to read. A read that
returns 0 anyway is not treated as EOF — a serial line has no EOF — so the
only ways out are bytes, a hard error, or the alarm. If `AX=4406h` itself
returns carry, the code claims "ready" and lets `read()` decide, so a device
whose status cannot be queried degrades to being polled rather than waited
on forever.

`alarm()` stops being a stub. There is no interval timer available — hooking
INT 1Ch is not INT 21h (§2) — and none is needed, because the poll above is
the only place this program can block. `alarm()` records a deadline, the
poll tests it, and on expiry the poll reads back the installed `SIGALRM`
handler and **calls it synchronously**. `timerh()` longjmps and `ttinl()`
returns -1, exactly as on Unix. The handler is read back by installing
`SIG_IGN` and restoring what that returned, and nothing is called unless a
real function is there — with `SIG_DFL` installed, the default action for an
unhandled signal terminates the program on some runtimes.

### The Watcom `SIGALRM` number matters

This is the one place the two builds needed different treatment, and it is
easy to get silently wrong. Reading the handler back only works if
`signal()` agreed to store it. newlib's `signal()` is a real userland
dispatch table — `SIGALRM` is 13, `NSIG` is 32 — so the gcc build needed
nothing. Open Watcom's `signal()` stores handlers for 1..12 and rejects
everything else with `SIG_ERR`, and `ckvictor.h` had been giving `SIGALRM`
the value 22 precisely *because* nothing was expected to dispatch it.

`SIGALRM` is now `SIGUSR3` (10) on the Watcom build. DOS never generates it,
C-Kermit never mentions it — it uses `SIGUSR1`/`SIGUSR2`, and only on the
`exec()` paths this port does not have — so the number is free. Had this
been left at 22, the Watcom build would have compiled, linked, run, and
never timed out, with no diagnostic anywhere.

### Measured, on Victor MS-DOS 3.1 under MAME

Same harness as §16a. Host: C-Kermit 9.0.302 on the `socat` pty, `set line
/tmp/v9000`, `set carrier-watch off`, `receive`, `log packets`.

| | before (§16a) | after |
|---|---|---|
| Send-Init packets on the wire | **1** | **13–15, retransmitted** |
| host ACKs the S packet | yes | yes |
| Victor reacts to the ACK | — | **no** |
| how the Victor gives up | "No files were transferred" | `^A3 E` **"Too many retries"** |
| transfer completes | no | no |

The retransmissions are the result. They can only happen if the read
blocked (otherwise the first quiet read closes the line) *and* the alarm
fired (otherwise the retry loop never exits), and the `E` packet is
C-Kermit's own protocol give-up rather than a platform failure. That also
confirms the `longjmp` path specifically: the `EINTR` fallback cannot
produce a timeout, so a retransmission proves `signal()` stored `timerh()`
and the poll called it — which is the `SIGUSR3` decision above, verified on
hardware rather than reasoned about.

Both builds were run; they behave identically, as in §16a. Costs: DGROUP
52,008 under gcc (was 52,000) and 38,704 under Watcom (unchanged);
`v9k_read` is 22 bytes of stack by `-fstack-usage`, with the two helpers
inlined into it.

### What is still missing, and it is not what §16a assumed

§16a's read of this was "nothing arrives on RX". That is wrong, and the
debug build says so precisely. Built with `make -f victorow.mak
XFLAGS=-dKEEP_DEBUG`, run as `CKERMITW -d -l /dev/seriala -b 9600 -s
TESTFILE.TXT`, and `DEBUG.LOG` pulled back off the image with
`vtg_image_util copy`, every one of the twelve receive attempts looks
identical:

```
ttinl timo=8
myfillbuf calling read() fd=6
SVORPOSIX myfillbuf read=2          <-- two bytes, not zero
TTINL myread char=^A                <-- SOH
TTINL myread char=9                 <-- the packet's LEN field
myfillbuf calling read() fd=6       <-- and then nothing, ever
ttinl timout
rpack ttinl len=-1
```

`grep -c` over the log: **12 reads, every one of them returning exactly 2,
24 characters received in total, and no other value anywhere.** The host's
ACK is `^A9 Y~/...` — about 30 bytes — so the Victor takes the first two
characters of every packet and then the receiver stops. The same two
characters, twelve times running: this is deterministic, not lossy.

So the whole software stack above the driver is working. C-Kermit framed
the SOH, read the length field, waited the full 8 seconds for the rest of
the packet, timed out, retransmitted, and eventually gave up in the
protocol-defined way. What fails is **reception on the OEM `\dev\seriala`
driver**, and it fails the same way every time.

### Why it stops after two bytes — hypothesis, not measurement

Keep these apart. **Measured:** twelve reads, every one returning exactly 2,
the same two characters each time. **Not measured:** why.

The leading explanation is a latched µPD7201 receive overrun. The chip holds
overrun in RR1 and will not resume until a WR0 Error Reset, and a polled
driver with no interrupt service and no error path has no way to issue one.
At 9600 bps the third character of a back-to-back packet arrives about 1 ms
after the second, so a driver that is only sampled when DOS asks will fall
behind immediately. The determinism fits: a latch produces the same failure
every time, where mere slowness would produce a varying number of bytes.

One attempt was made to separate "too fast" from "wedged for some other
reason", and it did not settle it. `RXTEST.BAT` ran `COPY /dev/seriala
rxtest.out` while the host fed the port one byte every 120 ms — about a
thirteenth of the 9600-baud character rate — ending each burst with `^Z`,
forty times over three minutes. **`COPY` never terminated and no
`rxtest.out` was created.** That is consistent with the channel wedging even
at eight bytes per second, which would rule overrun *out*; but it is equally
consistent with `COPY`'s own end-of-file handling on this device not being
what was assumed, and the test gives no way to tell which. Recorded so the
next session does not spend another run on it.

§11a adds one measurement that bears on this, and it points the same way:
**the driver's WR1 reads back as 0** — no receive interrupt enabled on
this port. A driver with no receive interrupt has no buffer being filled
behind DOS's back, so it can only ever see the character that happens to
be in the chip when someone calls it, which is exactly the arrangement
that falls a millisecond behind at 9600 and latches an overrun it never
clears. Two cautions keep this short of settled: CR1 is the single field
`msxv90.asm` records as not behaving through this interface, so a 0 may
mean "not reported" rather than "not enabled"; and every other field in
the block does round-trip, which is the reason to weigh it at all.

**§16d removes both cautions.** When §11b's driver installs itself it
records what it found first, and on Victor MS-DOS 3.1 that is `IRQ1 mask =
0B3h` — bit 1 set, IRQ1 masked at the 8259 — and the vector at 41h pointing
at segment 0. Nothing was servicing this chip's interrupt, measured two ways
that do not depend on the IOCTL. The polled-and-unbuffered half of this
explanation is now established. The latched-overrun half still is not, and
the handler's loss counters are what would show it.

What does raise the hypothesis well above a guess is MS-DOS Kermit 3.13.
`msxv90.asm` is a driver for this exact machine by this exact project, and
its interrupt handler reads RR1, tests bit 5, issues `WR0 = 30h` (Error
Reset), and substitutes a `BELL` for the lost character — with edit-history
entries dated August and November 1986 recording that receiver overrun had
to be found and fixed twice. Unrecovered overrun was a real failure mode on
Victor hardware, and its recovery is exactly the code we do not have. See
§11, which now takes 3.13's whole integration model.

The practical consequence does not depend on resolving this: the driver has
to handle receive errors either way, and once §11 owns the chip, RR1 can
simply be read.

**This retires the hope in the previous session's handoff** that a blocking
read alone "would complete a transfer today over the OEM DOS serial
driver". It will not: the OEM driver cannot receive a Kermit packet.
Everything that could be proved without owning the chip has now been
proved, and §11 is the remaining work rather than one of two parallel
options.

---

## 16c. §11a on the wire: the line is ours to configure

Three runs of the same harness, with `tcsetattr()` now programming the
chip through the OEM driver's IOCTL control block. **The measurements live
in §11a** rather than being repeated here; in one line each:

- Both IOCTL subfunctions work on Victor MS-DOS 3.1, and all five of
  C-Kermit's calls to set the line now reach the hardware.
- The register values read back as written, and `tthang()` is visible in
  the read-back as `cr5` going `EAh` → `68h` → `EAh`. **Corrected
  2026-08-05:** this was written up as the first effect on the hardware
  that the hardware confirms. It is not — `AL=02h` returns the driver's
  cache of its own last write, not the chip. See §11a **[A.2]**.
- Getting `stype` wrong on the *read* makes it return nothing with carry
  clear. Two of the three runs went that way; the first wrote stack junk
  into the 8253 during hang-up before it was caught. **Corrected
  2026-08-05:** not silent after all — the driver reports it in the
  block's `status` word, which the port now checks.
- Reception is byte-for-byte what §16b measured — 12 reads, every one of
  exactly 2 — in all three runs. Configuring the OEM driver does not make
  it a data path, and §11b is unchanged as the remaining work.

The one thing worth adding to the harness notes in §16a: `XFLAGS=-dKEEP_DEBUG`
needs `make clean` first. It is not per-file — `debug()` compiles to nothing
without it, so a partial rebuild links `ckvictor.o` against a tree that has
no `dodebug` and fails with `E2028: dodebug_ is an undefined reference`.

### Addendum, 2026-08-05: the status check, and the cache semantics confirmed

A fourth run, after Appendix A was read and `v9k_portval_io()` was given the
status-word check (§11a **[A.2]**). `KEEP_DEBUG` Watcom build, same harness,
`KTEST.BAT` running `CKERMITW -d -l /dev/seriala -b 9600 -s TESTFILE.TXT`
against a host C-Kermit receiver on the `socat` pty.

**The status check changes nothing on Victor MS-DOS 3.1, which is what it
had to show.** In a 1,796-line `DEBUG.LOG` there is not one
`v9k_portval_io driver status` line and not one `v9k_portval_io DOS error`
line. All seven `tcsetattr()` calls — `ttopen`, `ttsspd` ×2, `ttpkt`,
`tthang`'s B0 and restore, and `ttres` — did both subfunctions with carry
clear *and* `status = 0`. Nothing was diverted to the direct-programming
fallback, and the transfer completed: S/F/A/D/Z/B in six exchanges with **no
retransmissions**, `TESTFILE.TXT` byte-correct at 72 bytes, `C-Kermit EXIT
status=0`. Identical to §16d.

**And the run is direct evidence for the cache semantics**, which Appendix A
asserted and nothing here had yet tested:

```
tcsetattr read-back cr1/cr2a[0]=16     <-- cr1 = 0, at ttopen ...
v9k_ser_install channel=0
...
tcsetattr read-back cr1/cr2a[0]=16     <-- ... and cr1 = 0 at ttres,
ttres result=0                              after the whole transfer
```

§1e writes `WR1 = 18h` at the chip on install and again on every
`v9k_ser_reenable()`, and the transfer demonstrably ran on those receive
interrupts — six clean reads, `rxlost/rxfull = 0/0`. **The chip's WR1 was
`18h` and the IOCTL read reports `cr1 = 0` anyway**, on every one of the six
reads after the install. A read that returned chip state could not do that.
This is what §11a's measurement 5 was groping at and is the measurement that
settles it: `AL=02h` returns the driver's cache, so `cr1 = 0` was never
evidence about the µPD7201, and 3.13's *"IOCTL doesn't seem to touch it"* is
the sole support for the WR1 re-assert. `cr2a` still reads `10h`, `cr4`
`44h`, `cr5` `EAh` → `68h` → `EAh` across `tthang()`, all as before — the
cache is faithful to what was written, it is just not the chip.

The loss counters §16d said would print on the next run do print, from
`tcsetattr()`: `v9k_ser rxlost/rxfull[0]=0` at all six sample points.

**Not exercised:** the `B200` divisor correction (390, from Appendix A).
Nothing in this harness runs at 200 baud, and no run of this port ever has.
It is a documentation-sourced change, not a measured one.

---

## 16d. A file crosses the wire

**A C-Kermit file transfer from the Victor 9000 completed**, on Victor
MS-DOS 3.1 under MAME, with §11b's driver owning the µPD7201. This is
milestone step 5 (§13) and it is the first time this port has done the thing
it exists to do.

Same harness as §16a and §16b, unchanged: `socat` listener first, MAME
second, `KTEST.BAT` autobooted, `CKERMITW -d -l /dev/seriala -b 9600 -s
TESTFILE.TXT`. Host receiver: C-Kermit 9.0.302 on the `socat` pty, `set line
/tmp/v9000`, `set speed 9600`, `set carrier-watch off`, `set flow none`,
`receive`, `log packets`.

The host's packet log, in full, after the retransmissions that opened the
conversation:

```
r-00-28-^A9 Sz/ @-#Y3~^! z0___F"U1AF     <-- Send-Init from the Victor
s-00-28-^A9 Y~/ @-#Y3~^>J)0___B"U1@A     <-- our ACK ...
r-01-05-^A1!FTESTFILE.TXT+")             <-- ... which the Victor ACTED ON
s-01-05-^Aw!Y/private/tmp/.../TESTFILE.TXT
r-02-10-^AQ"A."U1""B8#119700101 01:19:28!!11"74,#666-!3@ /"O
s-02-10-^A%"Y.5!
r-03-13-^Ao#DVictor 9~#0 C-Kermit test payload.#JBuilt with Open Watcom, ...
s-03-13-^A%#Y/R9
r-04-15-^A%$Z(,*                          <-- EOF
s-04-15-^A%$Y+&1
r-05-17-^A%%B 8;                          <-- Break: end of transaction
s-05-17-^A%%Y*A)
```

and the transaction log:

```
Receiving TESTFILE.TXT
 mode: binary: 1
 complete, size: 72
 elapsed time (seconds)  : 10
```

The file arrived byte-correct. 72 received against 74 on the Victor's disk
is the two carriage returns of CRLF→LF text conversion, which is what
C-Kermit is supposed to do.

| | §16b / §16c | §11b |
|---|---|---|
| reads | **12, every one of exactly 2 bytes** | **6, of 33 / 90 / 8 / 8 / 8 / 8** |
| Victor reacts to the host's ACK | **no** | **yes** |
| S / F / A / D / Z / B sequence | never past S | **complete** |
| file written at the far end | no | **yes, 72 bytes, correct** |
| timeouts, retransmissions | 12 and 13–15 | **none** |
| exit | protocol `E "Too many retries"` | `C-Kermit EXIT status=0` |

The Victor's own `DEBUG.LOG`, `XFLAGS=-dKEEP_DEBUG`, on the same run. Six
reads, all of whole packets, no timeout anywhere, and `tthang` / `ttres` /
`ttclos` / `conres` all completing in order. `ttgmdm` is in it too, working
for the first time: `TIOCMGET ioctl=0`, `bits=358` — DSR, carrier, CTS, DTR
and RTS — so `in_chk()` gets past its carrier test and reaches the byte
count instead of stopping at a -3.

### Two lines of that log settle §16b's hypothesis

§16b said the OEM driver's two-byte signature looked like a latched receive
overrun on a polled, unbuffered port, and was careful to call that "hypothesis,
not measurement" — the only evidence was CR1 reading back as 0 through an
IOCTL that 3.13 says does not report CR1 reliably. The install path prints
what it found before touching anything:

```
v9k_ser_install old IRQ1 mask=179       <-- 0B3h: bit 1 SET
v9k_ser_install old vector seg=0
```

**IRQ1 was masked at the 8259, and the vector at 41h pointed at segment 0.**
Nothing was servicing the µPD7201's interrupt at all. That is independent of
the CR1 read-back and it says the same thing: the OEM driver runs this port
polled, with no buffer being filled behind DOS's back, so it can only ever
return the character that happens to be in the chip when someone asks. At
9600 the next character is a millisecond behind. §16b's leading explanation
is now the measured configuration; whether the specific mechanism is a
latched overrun is still not directly observed, and the counters below are
what would show it.

The loss counters themselves did not print on this run, and the reason is
worth writing down: they were logged from the release path, and the release
runs from `atexit()`, by which time C-Kermit has already closed `DEBUG.LOG`.
They are now also logged from `tcsetattr()`, which `ttres()` calls on the way
out, so the next run has them. Nothing was lost — six clean reads and no
retransmission is a stronger statement than a zero counter — but the
instrument was pointed at the wrong second.

**What this establishes.** Not just that the driver works — that the whole
diagnosis was right. §16b said the OEM `\dev\seriala` driver delivers the
first two bytes of every inbound packet and then stops, that everything above
the driver was already correct, and that §11's split was the fix. Changing
only the data path, and changing nothing above it, turns twelve two-byte
reads into a completed transfer. The protocol engine, the file system, the
timers and the packet framing were never the problem, and this is the run
that proves the negative.

It also closes §12's two loose ends by using them: `ttchk()` returns a real
count out of the ring, and `ttgmdm()` answers out of RR0, so `in_chk()`
reaches its byte count for the first time instead of stopping at a -3.

**What it does not establish.** Under emulation, not on real hardware. One
file, 74 bytes, one data packet, at 9600 with window 1 and short packets —
which is exactly milestone step 5 and no more. Nothing here says anything
about 19200 or 38400, about long packets, about windowing or streaming, or
about what happens when a floppy write holds the ring for longer than 533ms.
The two counters the handler keeps for precisely those questions — bytes lost
to a chip overrun, bytes lost to a full ring — are what to read next.

The gcc build was not run. Both builds compile the same §1e from the same
`ckvictor.h` and have been byte-identical on the wire twice (§16a, §16b), but
that is an inference here and not a measurement.

---

## 16e. The other toolchain crosses the wire

> **History, and the section that retired that toolchain.** This is the gcc
> build completing a transfer — proof that the port was toolchain-neutral —
> and, in the same run, the measurement that showed the near heap was not
> survivable: ~2,090 bytes left at the low-water mark, with `SBSIZ`/`RBSIZ`
> already halved to get there. Read together with §16f, where the same number
> reaches 212 during a wildcard expansion. gcc was retired on 2026-08-05.

**The gcc build completes a transfer too**, on the same harness, and getting
there took two real fixes rather than the confirmation §16d expected. What
§16d called "an inference and not a measurement" was right to be careful.

```
r-00-33-^A9 Sz/ @-#Y3~^! z0___F"U1AF     <-- Send-Init, gcc build
s-00-33-^A9 Y~/ @-#Y3~^>J)0___B"U1@A
r-01-00-^A1!FTESTFILE.TXT+")
s-01-00-^Aw!Y/private/tmp/.../TESTFILE.TXT
r-02-01-^AQ"A."U1""B8#119700101 02:19:28!!11"74,#777-!7@ &1#
s-02-01-^A%"Y.5!
r-03-01-^As#DVictor 9~#0 C-Kermit test payload.#M#JBuilt with Open Watcom, ...
s-03-01-^A%#Y/R9
r-04-01-^A%$Z(,*                          <-- EOF
s-04-01-^A%$Y+&1
r-05-01-^A%%B 8;                          <-- Break
s-05-01-^A%%Y*A)
```

74 bytes, byte-correct, no retransmission, `complete, size: 74`. Milestone
step 5 now holds for **both** builds.

Two differences from §16d's run are worth recording rather than explaining
away. The gcc build sent the file in **binary** where Watcom sent it as text
— the D packet carries `#M#J` and 74 bytes arrive instead of 72 — so the two
builds are making different file-type decisions somewhere in `scanfile()`,
and neither has been shown to be the wrong one. And the transfer took **0
seconds against 10**, 129 bytes/sec against 6: §16d's ten seconds were spent
somewhere that this run did not spend them, which is unexplained and is a
lead rather than a worry.

### What it took, and what it measures

**The packet buffers had to be halved.** With `SBSIZ`/`RBSIZ` at 2048 the
gcc build got as far as the file-open step of a real transfer and stopped
there, sending a protocol Error and printing, on the Victor's own screen:

```
TESTFILE.TXT: Not enough space
TESTFILE.TXT: Not enough space
 No files were transferred: Can't open file.
```

Twice, because `openi()` tries `zopeni()` a second time with the name
converted to local form. That is newlib's `fopen()` failing to get a `FILE`
and a 1,024-byte `BUFSIZ` buffer, and the arithmetic behind it is in
`ckvictor.h`: `inibufs()` alone wants `SBSIZ+RBSIZ+40` for `bigbufp`,
`RBSIZ+100` for `srvcmd` and `2 x 14 x MAXWS` for `s_pkt`/`r_pkt` — 7,180
bytes of a heap that is 12,808 shared with the stack. 1024/1024 gives 3,072
of it back and the transfer completes.

**This was the first hard difference between the two builds that was a
property of the toolchains and not of the port** — and, three days later, the
argument that ended the experiment. Watcom's large model puts the heap
outside DGROUP, so 2048 costs it nothing; gcc's medium model has one 64K data
group and the heap is what is left in the corner of it. `ckvictor.h` carried
the two sizes per compiler for as long as both builds existed; it now sets
2048/2048 unconditionally and has no conditional compilation in it at all.

### The gcc build has no debug log, measured

`XFLAGS=-DKEEP_DEBUG` does not fit and cannot be made to: the objects alone
come to **68,693 bytes of near data, 104.8% of DGROUP** before libc adds
anything, and the link dies in a page of `relocation truncated to fit`.
Enabling `DEBUG` in just the four modules that matter (`ckufio.c`,
`ckuusx.c` for `dodebug`, `ckuus4.c` for `debopn`, `ckuusy.c` for the `-d`
option) does link, at 61,280 — which leaves 4,256 bytes for heap and stack
together, and `inibufs()` wants 4,108 of that. So the debug log was a
Watcom-only instrument, and the gcc build needed its own — `V9K_HEAPREPORT`,
section 0e of `ckvictor.c`, which went with it. **On the surviving build
`XFLAGS=-dKEEP_DEBUG` gives a real debug log, and it is the instrument to
reach for.**

### `-d` is not a portable command line

The gcc build **rejected `-d`** — `"-d" - invalid command-line option` —
because `NODEBUG` compiles the option out of `ckuusy.c` along with everything
else. §16d's command line was therefore Watcom-only, which cost one MAME run
to discover, and is now simply the command line. Two other harness landmines
cost one run each and belong with the rest in §16a:

- **`KTEST.BAT` must have CRLF line endings.** Written with Unix `\n`,
  COMMAND.COM echoes every line and executes none of them, with a staircase
  display that looks like a corrupted terminal rather than a corrupted file.
- **MAME does not exit when `-seconds_to_run` expires.** It writes
  `Average speed: 100.00% (199 seconds)` to its log and the final snapshot,
  and then sits there. Poll the log for that line, not the process.
- **MS-DOS 3.1's COMMAND.COM cannot redirect handle 2.** `2> FILE` puts a
  literal `2` in `argv` and sends stdout to `FILE`. Anything written to
  stderr goes to the screen, where only the last 25 lines survive to the
  snapshot.

---

## 16f. Wildcards: four causes, three fixed and one retired

§15's top item — `-s FILE` works and `-s *.COM` reports "No files for -s" —
was open for four sessions with a one-line description. It is not one defect.
It is four, they are independent, three of them were fixed here, and the
fourth left with the gcc build without ever being understood. The third is
the one that a fresh reading would have blamed last.

**This section is history for everything except causes 1 and 2.** Those two
are guarded upstream edits and are live in the tree. Cause 3 was a `libdos-m`
gap and its fix is gone with that runtime; cause 4 is closed by §16g.

### What it was not

A probe (`vwild.c`, Open Watcom, throwaway) asked MS-DOS 3.1 directly, in
the root directory and in a subdirectory, what it does with `.` and with
trailing separators. The suspicion going in was that a FAT root has no `.`
entry, so `FindFirst(".\*.*")` would fail there:

```
== ROOT (cwd=A:\)                    == SUBDIR (cwd=A:\TEST)
  FF *.*     rc=0  first=MSDOS.SYS     FF *.*     rc=0  first=.
  FF .\*.*   rc=0  first=MSDOS.SYS     FF .\*.*   rc=0  first=.
  FF ./*.*   rc=0  first=MSDOS.SYS     FF *.COM   rc=18 (no more files)
  ST "."     rc=0  isdir=1             ST "."     rc=0  isdir=1
  ST "./"    rc=0  isdir=1             ST "./"    rc=-1
  OD "./"    n=19 first=MSDOS.SYS      OD "./"    n=2  first=.
```

**Wrong on the main point**: DOS resolves `.` in the root perfectly well,
through `FindFirst` and through `stat`. Worth having anyway for the two
things it did find — `stat("./")` fails in a subdirectory while `stat(".")`
succeeds, so a trailing separator is not free — and for closing the
hypothesis honestly instead of leaving it to be re-guessed.

`opendir()`/`readdir()` — then supplied by section 0a of `ckvictor.c`, since
retired along with the gcc build — were instrumented directly (`V9K_DIRTRACE`,
also retired), which is what §15 asked for in the first place:

```
v9k opendir(./) -> .\*.* rc=0
v9k readdir end, entries=26
```

The whole root directory, enumerated correctly, including the file that was
supposed to match. And `ckmatch()` itself, linked out of the port's own
`ckclib.o` into a second probe and run on the target:

```
ckmatch("*.TXT","TESTFILE.TXT",1,2) = 1
ckmatch("*.TXT","KTEST.BAT",1,2)    = 0
```

So the DOS layer, the directory reader and the pattern matcher were all
correct, and had been all along.

### Cause 1: `initspace()` is greedy, and the heap is not

`v9k heap: low-water 212 bytes free (break at 64602 of 65536)`.

That is the gcc build during a wildcard expansion. The near heap is gone.
`initspace()` in `ckufio.c` asks for `SSPACE` — 10,000 under `DYNAMIC` —
and, when malloc refuses, halves the request and tries again, keeping
whatever it finally gets. On a large machine that is a graceful degradation.
Here it is a vacuum cleaner: it takes everything left, and the allocations
after it fail.

The one that fails visibly is in `ckuusy.c`:

```c
} else {
    if (!failmsg) failmsg = (char *)malloc(2000);
    if (failmsg) { ckmakmsg(failmsg,2000,"kermit -s ",*xargv,": ",ck_errstr()); }
}
...
if (!failmsg) failmsg = "No files for -s";
```

**"No files for -s" is not the diagnosis. It is what gets printed when there
was not enough memory to write the diagnosis.** The real message, the one
with `ck_errstr()` in it, needs 2,000 bytes that the expansion has just
taken. Four sessions of a misleading symptom trace back to those five lines.

Fixed by §8's seventh guarded edit: `SSPACE` becomes overridable and this
port sets 2,048.

### Cause 2: the file-list array is allocated before the first entry is read

Capping `SSPACE` moved the failure and did not remove it —
`low-water 414 bytes`. `zxpand()` allocates `maxnames * sizeof(char *)`
up front, and `MAXWLD` is 1024 for UNIX, so that is a 2,048-byte malloc
taken before a single directory entry has been read, for a pattern that may
match nothing. §8's eighth guarded edit makes it overridable; this port sets
64, which no FAT directory on this machine will reach, and which fails
loudly (`?Too many files (64 max)`) if it ever does.

With both, `-s *.TXT` gets past the command line for the first time.

### Cause 3: libdos-m cannot stat the current directory

And then it still failed, differently and more informatively: `?File not
found`, `SENT: (0 files)`, with the directory trace showing **one** expansion
where there should be two.

`nzxpand()` runs twice for a wildcard send — once in `doarg()` while parsing
the command line, with flags 0, and again in `gnfile()` when the protocol
asks for the file, with `ZX_FILONLY`. Those two flag sets take different
paths through `traverse()`:

```c
if (stathack) {
    if (xrecursive || xfilonly || xdironly || xpatslash)
      itsadir = xisdir(sofar);              /* the transfer's path */
    else
      itsadir = (strncmp(sofar,"./",2) == 0);   /* the command line's */
}
...
if (!itsadir) return;                       /* before opening anything */
```

`sofar` is `"./"`. The command-line pass never calls `stat` at all; the
transfer's pass depends on it entirely. And, measured with the gcc-built
probe:

```
stat(".")           rc=-1
stat("./")          rc=-1
stat(".\")          rc=-1
stat("TESTFILE.TXT") rc=0 isdir=0 size=74
stat("TEST")        rc=0 isdir=1
```

**libdos-m's `stat()` cannot stat the directory you are in.** It is
`FindFirst` underneath and `FindFirst` has no answer for the current
directory; named files and named subdirectories are fine. Watcom's runtime
answers all of them (except `"./"` inside a subdirectory), which is why this
never showed up in that build.

It was fixed in section 1a of `ckvictor.c`, where the other `libdos-m` gaps
lived: a `stat()` that strips trailing separators, answers `""` and `"."`
itself — the current directory always exists and is always a directory, so
that is a fact and not a guess — and hands everything else to the library
unchanged. Unlike the `malloc()` interposition below, that one linked and ran:
both expansions happened, both enumerated all 26 entries.

`-fstack-usage` put that `stat()` at 148 bytes and `opendir()` at 150, both
leaves, with `traverse()` unchanged at 98 bytes per level — the edit to
`ckufio.c` being preprocessor-only — so the deepest chain grew by one leaf
frame rather than by 148 bytes per directory level.

**That replacement `stat()` is gone with the gcc build**, because Watcom's own
answers `"."` and `"./"` and cause 3 never existed there. This subsection is
kept for the finding, not the fix: **`FindFirst` has no answer for the
directory you are in**, and any DOS libc whose `stat()` is `FindFirst`
underneath will break `traverse()`'s `ZX_FILONLY` path the same way. If a
future runtime change reintroduces it, the symptom is a wildcard that expands
once instead of twice.

### Cause 4, and how it ended

`-s *.TXT` expanded, twice, correctly, and **still did not complete a
transfer**: the Victor sent Send-Init, was ACKed, and sent Send-Init again,
ten times, until the host gave up. That was written up here as the port's one
open defect.

It was *not* the heap. That was established twice over: under gcc, headroom at
the low-water mark was 2,068 bytes — the same room the transfer that works
has — and the current build's heap is outside DGROUP entirely, so the
resource the first three causes exhausted no longer exists in that form.

**Cause 4 does not reproduce under Open Watcom.** §16g is the run. It was
never observed under this toolchain — every measurement above, including the
symptom, is from the gcc build, and the fix for cause 3 was a replacement
`stat()` that only ever existed there. So this is not a diagnosis: the defect
left with the build it lived in, and what it actually was is now
unanswerable, because there is no longer a compiler that produces it. Recorded
that way deliberately rather than as a fix.

One thing §16g does explain is the *shape* of the symptom. "Send-Init, ACK,
Send-Init" is exactly what a crossed NAK produces — a host receiver NAKs
packet 0 while it waits, that NAK arrives after the Victor's S has gone out,
and the Victor correctly resends packet 0. §16g caught one, recovered from it
in a single retry, and went on to transfer three files. Whether the gcc build
was the same mechanism failing to converge is a guess and is left as one.

One instrument to record as **not working**, because it cost two runs and
will look attractive again: you could not interpose on `malloc()` in the gcc
build. `ld --wrap=malloc` died with `R_386_OZSEG16 for symbol with no output
section` — the far-call relocations had nothing to point at. Defining
`malloc()` in `ckvictor.c` linked cleanly and was simply never called; a
first-call trace proved it, after an earlier run had drawn a conclusion from
its silence. Under Open Watcom the question is moot for a better reason —
`KEEP_DEBUG` gives a real debug log, which the gcc build could not afford
(§16e).

---

## 16g. The wildcard send works, and the ring loses nothing

**`CKERMITW -d -l /dev/seriala -b 9600 -s *.TXT` completes**, and so does the
multi-file form of it. This closes §16f's cause 4 — the port's last open
defect — and it reads the two driver loss counters for the first time.

Same harness as §16a and §16d, unchanged. `XFLAGS=-dKEEP_DEBUG`, so the image
is 308,862 bytes rather than 228,554 and the Victor writes its own `DEBUG.LOG`
alongside the host's packet log. Host receiver: C-Kermit 9.0.302 on the
`socat` pty, `set speed 9600`, `set carrier-watch off`, `set flow none`,
`receive`, `log packets`, `log transactions`.

### Run 1 — one match

`*.TXT` matched `TESTFILE.TXT` and nothing else, which is the exact case §16f
left failing. It transferred, first attempt, no retransmission anywhere:

```
r-00-55-^A9 Sz/ @-#Y3~^! z0___F"U1AF     <-- Send-Init
s-00-55-^A9 Y~4 @-#Y3~^>J)0___B"U1@F     <-- ACK, acted on
r-01-03-^A1!FTESTFILE.TXT+")             <-- F
r-02-08-^AQ"A."U1""B8#1...               <-- A
r-03-11-^Ao#DVictor 9~#0 C-Kermit ...    <-- D
r-04-14-^A%$Z(,*                         <-- Z
r-05-16-^A%%B 8;                         <-- B
```

72 bytes at the far end against 74 on the Victor's disk — the CRLF→LF of a
text-mode send, same as §16d. `C-Kermit EXIT status=0`.

The Victor's `DEBUG.LOG` shows **both** expansions, which is what §16f's cause
3 was about and what a runtime regression would break first:

```
 184: nzxpand[*.TXT]=0          <-- doarg(), flags 0, 25 entries swept
 961: nzxpand[*.TXT]=1          <-- gnfile(), ZX_FILONLY
1594: gnfile znext A[TESTFILE.TXT]=1
1698: sinit ok[TESTFILE.TXT]=0
```

### Run 2 — three matches, the path that had never run

One match is the easy half of a wildcard. With more than one, `gnfile()` sets
`sndsrc = -1` and every file after the first comes from the `znext()` loop,
driven by `<sseof>Y` — a different path through `ckcfns.c` that this port had
never executed. `ALPHA.TXT` and `BETA.TXT` were added to the image to force
it. **Three files, one transaction, all byte-correct:**

```
files transferred       : 3
total file characters   : 186
elapsed time (seconds)  : 44
```

61, 53 and 72 bytes received against 63, 54 and 74 sent. The log walks the
list and terminates on its own:

```
1707: gnfile znext X[*.TXT]=0     -> B[ALPHA.TXT]=3
2999: gnfile znext X[ALPHA.TXT]=0 -> B[BETA.TXT]=2
3923: gnfile znext X[BETA.TXT]=0  -> B[TESTFILE.TXT]=1
4850: gnfile znext X[TESTFILE.TXT]=0 -> B[]=0
4854: gnfile setting sndsrc back=1
```

### The one retransmission, and why it is not a defect

Run 2 sent Send-Init twice. That is the exact shape §16f reported as cause 4,
so it is worth being precise about: the host receiver NAKs packet 0 while it
waits, one of those NAKs arrived after the Victor's S had gone out, and the
Victor did what Kermit says to do —

```
[# N]                                    <-- NAK, type N, sequence 0
resend seq=0 / resend retry=1
HEXDUMP: ttol s (28 bytes)  01 39 20 53 7a 2f ...
```

— resent packet 0, was ACKed, and went on. One retry, self-recovered. Run 1,
where no NAK crossed, shows none at all.

### The loss counters, read at last

§16d pointed the instrument at the wrong second and got nothing; §11b has kept
these two counters since it was written and nobody had ever seen them. Both
runs, at every `tcsetattr()` on the way out:

```
v9k_ser rxlost/rxfull[0]=0
```

**Zero bytes lost to a µPD7201 overrun, zero lost to a full ring** — across a
three-file, 44-second transaction. The receive ring and the polled transmitter
of §11b are not dropping anything at 9600 with one packet in flight. That is
the first direct measurement of the driver's own error path rather than an
inference from "the transfer completed".

### What this establishes, and what it does not

Milestone step 5 is now genuinely complete: literal and wildcard sends, single
and multiple files, byte-correct, clean exit, no losses. **Still under
emulation, still only Victor MS-DOS 3.1, still 9600 with window 1 and short
packets.** A zero loss counter at 9600 with one packet in flight says nothing
about 19200 or 38400, and nothing about streaming — which is the case §11b has
no interrupt-level flow control for, and the case that would make these
counters interesting. `RECEIVE` is the next thing to point them at, because
that is where the file writes happen on the Victor's end.

---

## 16h. RECEIVE, and the two defects the send direction was hiding

**A file crosses the wire in both directions, byte-exact.** 2,048 bytes to the
Victor and the same 2,048 bytes back in one MAME run on Victor MS-DOS 3.1, with
the driver's loss counters at 0/0 in both directions and `EXIT status=0` on both
invocations. That is milestone step 6's first half.

Getting there cost two defects, and the second one **corrects the record in
§16d and §16g**.

The payload matters. It is 2,048 bytes cycling 0x00–0xFF eight times, so it
contains every byte value — including LF, CR and, decisively, **0x1A**.
§16d's and §16g's fixtures were all `.TXT`.

### Defect 1: `access(".")` cannot be trusted in a FAT root

`CKERMITW -d -l /dev/seriala -b 9600 -r` failed at the first file, with the
Victor sending a protocol error rather than data:

```
s-00-00-  S    Send-Init from the host
r-00-03-  Y    ACK             <-- receive negotiation is fine
s-01-03-  F    RXBIN.DAT
r-00-03-  E    "Write access denied"
```

`rcvfil()` is the only source of that string, and it comes from `zchko()`.
The Victor's own log shows `zchko()` contradicting itself inside four lines:

```
1013: zchko open[RXBIN.DAT]=7      <-- creating the file SUCCEEDS
1016: zchko delete ok[RXBIN.DAT]   <-- and deleting it succeeds
1019: zchko access[.]
1020: zchko access failed:[.]=6    <-- EACCES for the directory it just wrote in
```

`zchko()` creates the incoming file, deletes it again, and only then asks
`access(".",W_OK)` whether it may create files there. Open Watcom's `access()`
(`bld/clib/file/c/accss.c`) is `_dos_getfileattr()` — INT 21h AH=43h — followed
by a read-only-bit test. **A FAT root directory has no directory entry of its
own**, so AH=43h has nothing to read for it. It does not fail. It succeeds and
returns garbage. Measured with `.probe/vaccess.c`:

| path, from `A:\` | `_dos_getfileattr` | attr | `access(W_OK)` |
|---|---|---|---|
| `.` `./` `.\` `\` `A:\` `A:.` | rc=0 | **006b** | −1 EACCES |
| `TEST` (a named subdirectory) | rc=0 | 0010 | 0 |
| `TESTFILE.TXT` | rc=0 | 0020 | 0 |
| `NOSUCH.XYZ` | rc=2 | — | −1 |
| `.` from **inside** `A:\TEST` | rc=0 | **0010** | **0** |

`006b` carries the read-only bit and does *not* carry the directory bit. Asked
by other spellings the same root answers `00ff` (as `\` seen from a
subdirectory) or `0000` (as `A:\` seen from the same place) — three different
answers for one directory, which is what reading a directory entry that does
not exist looks like. A real subdirectory answers `0010` cleanly, which is why
running the same transfer from `A:\TEST` worked first time and was the
experiment that confirmed it.

Fixed in `ckvictor.c` §1d with our own `access()`: for `W_OK`, a directory is
writeable. That is not a workaround — DOS has no per-directory permissions, and
the read-only attribute of a directory entry does not stop you creating files
inside it. Directory-ness is decided with `stat()`, which §16f already
established answers `"."` here. Watcom's semantics are kept everywhere else,
with one library bug not copied: it tests `pmode == W_OK`, so it skips the
read-only check for `R_OK|W_OK`.

This is the same *shape* as §16f's cause 3 — `FindFirst` has no answer for the
directory you are in — but a different call and a different library. The
generalisation worth keeping: **on MS-DOS, ask about the root directory by name
and you will get an answer; it just will not be true.**

### Defect 2: the runtime was translating every transfer, both ways

With the file accepted, 2,048 bytes were sent and **2,056 landed on the
Victor's disk** — the source with every LF turned into CRLF. Sent back, that
file returned as **25 bytes**: the first 26 with the lone CR dropped and
everything from the first 0x1A onward gone.

`ckufio.c` is the **Unix** file module. `zopeni()` is a bare
`fopen(name,"r")` (line 1422) and `zopeno()` only ever builds `"w"` or `"a"`.
Neither consults the `binary` flag — on Unix there is nothing to consult it
for. On DOS that means every transfer, in both directions, went through a
translating stream: LF↔CRLF, and 0x1A as end-of-file on input.

**This is what §16d and §16g were actually looking at.** Both recorded the
Victor sending fewer bytes than the file held — 74→72 in §16d, and 63→61,
54→53, 74→72 in §16g — and both explained it as "the CRLF→LF of a text-mode
send, which is what C-Kermit is supposed to do". The host logs in the same runs
say `Global file mode: binary` and `mode: binary: 1`. In a binary transfer
C-Kermit is supposed to do *nothing of the kind*. So §16d's "the file arrived
byte-correct" was wrong: the file that arrived was byte-correct against what a
DOS text-mode read produced, not against what was on the Victor's disk. Nobody
noticed because every fixture was a `.TXT` file, where the difference is
invisible unless you compare byte counts and mean it. The step-5 result stands
— a Kermit transfer completed, and the protocol engine, driver and file system
all worked — but "byte-correct" belonged to §16h, not to §16d.

The fix is a pair, and **neither half is correct alone**:

- **`_fmode = O_BINARY`** before `main()`, so DOS streams move bytes
  (`ckvictor.c` §1d). Fixes binary; on its own it would leave a text-mode
  *receive* writing LF-only files.
- **`#undef NLCHAR` for `VICTOR9K`** in `ckcdeb.h` (§8 item 9), so `feol`
  becomes 0 and `ckcfns.c` does no end-of-line conversion, because the local
  terminator and the wire's are both CRLF. On its own it would break text
  transfers in the other direction.

Together all four paths are right: binary send and receive byte-exact, text
send CRLF on disk → CRLF on the wire, text receive CRLF on the wire → CRLF on
disk. Measured on the target as `MAIN feol=0` and `v9k _fmode=512`.

### The instrument that did not work, and why it is written down

Open Watcom ships `binmode.obj` for exactly this, and **it does not work in
this program.** That cost most of the session, so the negative result is here
to stop it being rediscovered.

Measured with `.probe/vfmode.c`: in a small test program it sets `_fmode` to
0200 correctly — with the object the toolchain ships in `rel/lib286/dos`
(which is byte-identical to the **small model** build) and with the large-model
build of the same source. Linked into `CKERMITW.EXE`, either object leaves
`_fmode` at 0100. Everything checkable said it should work: the record is in
the XI table (it grows 0x3c → 0x42), `cstart` runs every priority
(`mov ax,0FFh`), `_TEXT` is a single 60,160-byte segment so a near call reaches
the routine, and `_fmode` is the plain variable in both programs.
`.probe/vfmodefp.c` killed the most promising hypothesis — that the 8087
emulator's own XI initializer was interfering, since `NOGFTIMER` drags
`emu87.lib` into CKERMITW and not into the probe — by linking the emulator into
the probe and getting 0200 anyway.

What worked was **registering the initializer ourselves, as a far record**.
`binmode.obj` uses `AXIN`, the near form: `rtn_type = 0` and a two-byte routine
offset, which obliges `initrtns.c` to reach it with a near call. `clibl.lib` is
compiled large, so `struct rt_init` there is `{type, priority, far pointer}`;
asking for `rtn_type = 1` gets the far call that cannot care which segment the
routine landed in. Six bytes in `ckvictor.c`, our model and our flags:

```c
static struct v9k_rt_init __based(__segname("XI")) v9k_fmode_rec =
    { 1, 32, v9k_set_binmode };
```

**Why the near form fails here is still not known** — only that it does, and
that the far form does not. The witness flag in `ckvictor.c` is what makes that
a measurement rather than an inference: `v9k fmode witness=1` says the routine
ran, and `v9k _fmode=512` says the value survived, both logged from `access()`
at the moment before the first incoming file is created. If a future toolchain
change breaks this, those two lines say which half went.

Two cheap instruments came out of this and are worth keeping:

- **CKERMITW's own `debug.log` line endings are an `_fmode` oracle.**
  `debopn()` reaches `zopeno()`, the same `fopen(name,"w")` the transfer files
  use, so CRLF in the log means the runtime is translating and bare LF means it
  is not. `CKERMITW -d -h` writes one and exits: no serial line, no `socat`, no
  host `kermit`, about 2.5 minutes instead of 9.
- `.probe/vaccess.c`, `.probe/vfmode.c` and `.probe/vfmodefp.c`, built per the
  comment at the top of each.

### What this establishes, and what it does not

`RECEIVE` works, and the round trip is byte-exact over a payload containing
every byte value — which is the first time this port has moved a genuinely
binary file. The loss counters read 0/0 through both directions, so §16g's
result now covers receive as well as send: at 9600, with one packet in flight,
the ring drops nothing even when the Victor is writing to disk between packets.

**Still under emulation, still only Victor MS-DOS 3.1, still 9600 with window 1
and short packets.** `GET` and `SERVER` — the rest of milestone step 6 — have
not been tried. And the two `zchki`/`zchko` call sites are the only ones
`access()` was measured against; nothing else in C-Kermit's use of it has been
exercised on this target.

---

## 16i. GET, SERVER, and a capability gate nobody had opened

**Milestone step 6 is complete.** `GET` works, server mode works, and files
cross byte-exact in both directions with the Victor acting as client and as
server. Three MAME runs on Victor MS-DOS 3.1, same harness as §16a/§16d/§16g/
§16h, `XFLAGS=-dKEEP_DEBUG` throughout.

Getting there turned up one thing that is **not** a defect in this port and
one that may be. The first cost most of the session and is the more useful
result, because the answer was a policy decision this port had never been in
a position to make.

### GET: the port drives a server for the first time

`RECEIVE` (§16h) is passive — the Victor waits and something else starts the
conversation. `GET` is the first time the port **asks** for something: it
sends an R packet naming a file and then becomes a receiver. The host ran
`server`; the Victor ran

```
CKERMITW -d -l /dev/seriala -b 9600 -g GETBIN.DAT
```

`GETBIN.DAT` is 512 bytes cycling 0x00–0xFF twice, so it carries every byte
value including LF, CR and 0x1A, on the §16h principle that a `.TXT` fixture
hides exactly the defects that matter.

| | |
|---|---|
| bytes on the host | 512 |
| bytes on the Victor's disk | **512, MD5 identical** |
| `C-Kermit EXIT status` | 0 |
| `tstats filcnt` | 1 |
| `v9k_ser rxlost/rxfull` | 0 / 0 |
| `v9k fmode witness` / `v9k _fmode` | 1 / 512 |
| `MAIN feol` | 0 |

A second invocation, `CKERMITW -d -l /dev/seriala -b 9600 -f`, shut the host's
server down. `-f` is `setgen('F',...)` in `ckuusy.c`, which returns `'g'` —
the generic-command state — and the packet log shows the whole exchange in
four lines: the Victor negotiates, then sends the one-character command.

```
r-00-52-^A9 Iz/ @-#Y3~^! z0___F"U1A<     <-- Victor: I (negotiate)
s-00-52-^A9 Y~/ @-#Y3~^>J)0___C"U1AC     <-- host: ACK
r-00-56-^A$ GF4                          <-- Victor: G, type F = Finish
s-00-56-^A# Y>                           <-- host: ACK, server exits
```

`C-Kermit EXIT status=0`. Both halves of the client side of step 6 work.

### The first server run refused everything

`CKERMITW -d -l /dev/seriala -b 9600 -x` started, negotiated correctly, and
then declined every single thing the host asked for:

```
s-00-04-^A, RRXBIN.DAT H         <-- host: R (GET)
r-00-02-^A/ EGET disabled/
s-00-00-^A9 S~/ @-#Y3~^>J)...    <-- host: S (SEND)
r-00-03-^A0 ESEND disabled7
s-00-00-^A9 I~/ @-#Y3~^>J)...    <-- host: I
r-00-05-^A9 Yz/ @-#Y3~^! z0...   <-- Victor: ACK.  Negotiation is FINE.
s-00-05-^A$ GF4                  <-- host: G F (Finish)
r-00-02-^A2 EFINISH disabledR
```

That middle ACK is the important line. The server's protocol engine, the
7201 driver, the ring and the timers were all working — it parsed each
command and answered with a correctly formed, correctly sequenced E packet.
Nothing was broken. It was **refusing**.

`ckcker.h` line 771 says why:

```c
#define ENABLED(x) ((local && (x & 1)) || (!local && (x & 2)))
```

and `ckcmai.c` initialises every one of the `en_*` variables to **2** —
enabled in remote mode only. A Victor running `-l /dev/seriala` **owns** the
line, and owning the line is exactly what `local` means. So a Victor server
has every capability switched off, by design, in stock C-Kermit 11.

This is upstream policy and it is deliberate. Upstream's own ENABLE help text
(`ckuus2.c`) states it: *"By default, most commands are enabled for REMOTE but
disabled for LOCAL to prevent security issues."* And `compat_10()` in
`ckuus3.c` — `SET COMPATIBILITY 10` — sets this exact list back to 3, which
dates the change: **9 and 10 shipped these at 3; 11 tightened them.** The help
for that command is blunt about which direction is which: *"SET COMPATIBILITY
9 and SET COMPATIBILITY 10 weaken settings that C-Kermit 11 tightened for
security."*

On a full C-Kermit you type `ENABLE GET` at the prompt before `SERVER`.
**`NOICP` removes the prompt.** So the port has to make the decision at
startup, and until server mode was first tried there was nothing to make it
for. `ckvictor.c`'s stub for `compat_10()` carried the comment "C-Kermit 11
defaults are what this port wants regardless"; that was true of everything
except this.

### Where the decision is expressed, and why it is not a tenth upstream edit

In `ckvictor.c`, from an initializer, with a command-line switch:

```
CKERMITW -x                  server offers everything the build can do
CKERMITW -x --safe-server    server offers GET, SEND and FINISH only
```

The default is the full set: `compat_10`'s list plus DELETE, RMDIR,
RETRIEVE, EXIT and BYE. `HOST` is left alone because `NOPUSH` already removed
the thing it would run, and `MAIL` and `PRINT` because this build has no
transport for either — setting those to 3 would turn a refusal into a
failure. `--safe-server` grants the three commands a file transfer needs and
nothing that manipulates the Victor's file system; note the asymmetry, that
`en_ena` keeps its default there, so a peer cannot ENABLE its way back out.

The switch is the interesting part, because `cmdlin()` calls `XFATAL` on any
option it does not know — and under `NOICP` upstream compiles the whole `--`
path down to exactly that:

```c
#else  /* NOICP */
  case '-':
  case '+':
    XFATAL("Extended options not configured");
#endif /* NOICP */
```

So upstream must never see it. It does not, and no upstream file was touched
to arrange that. Open Watcom's startup provides the seam, in two parts read
out of its own source:

- `bld/clib/startup/a/cstrt086.asm` copies the DOS command tail from `PSP:81h`
  to the bottom of the stack and leaves a far pointer to the copy in
  `_LpCmdLine` (lines 309–325) — and only **then** calls `__InitRtns`
  (line 423).
- On 16-bit targets **argv itself is built by an XI initializer**:
  `bld/clib/startup/c/argcv.c` registers `__Init_Argv` at
  `INIT_PRIORITY_THREAD`, which `bld/watcom/h/rtprior.h` defines as **1**.
  `__InitRtns` always runs the lowest priority not yet done.

A record at **priority 0** therefore runs before argv exists. It scans
`_LpCmdLine`, records the switch, and blanks the token with spaces; argv is
then built from a command line that no longer contains it. Priority 0 also
means the FPU and run-time initializers have not run, so the routine calls
nothing at all — no libc, and in particular no `debug()`, because there is no
log yet. What it decided is reported later from `uname()`, which `sysinit()`
reaches in **every** invocation.

Three measurements, all from one 2.5-minute boot with no serial line and no
host — the §16h oracle pattern:

| run | result |
|---|---|
| `CKERMITW -d --bogus-opt -h` | `Extended options not configured` — the control: unknown `--` options really are fatal here |
| `CKERMITW -d --safe-server -h` | usage text, **byte-identical** to the no-flag run; `v9k srvcaps safe=1` |
| `CKERMITW -d -h` | `v9k srvcaps safe=0` |

The control matters. Without it, "our option did not cause an error" would be
consistent with upstream quietly ignoring it, and the blanking would be
unproven.

### Server mode, measured

With the gate open, the same server run that had refused everything:

| | full set | `--safe-server` |
|---|---|---|
| host `get RXBIN.DAT` (Victor sends) | 2048, **identical** | 2048, **identical** |
| host `send` → `SRVBIN`/`SAFEBIN.DAT` (Victor receives) | 512, **identical** | 512, **identical** |
| host `remote directory` | streams, never terminates | **`E REMOTE DIRECTORY disabled`** |
| host `finish` | never sent (see below) | **honoured, server exits** |
| `v9k_ser rxlost/rxfull` | (log lost) | 0 / 0 |
| `v9k srvcaps safe` | 0 | 1 |

Both directions byte-exact, both modes. The safe-mode run is the one to read
as the clean result: it did the two transfers, was refused the one command it
should be refused, took the FINISH, and exited — `[$ GF]` in the log, then
`doexit`. Its exit status is **8**, and that is not a defect either:
`ckcker.h` defines `W_REMO` as 8 and `ckcpro.c` does `xitsta |= (what &
W_KERMIT)`, so 8 says "a REMOTE command failed" — which is precisely the
refusal the run was designed to provoke.

**`REMOTE DIRECTORY` in the full-capability run is the one open item.** The
Victor streamed the entire listing correctly — all 51 entries of `A:\`,
alphabetical, ending at `VMATCH.EXE`, each D packet ACKed — and then never
sent the terminating Z. The host timed out (six of the run's seven timeouts
fall inside that transaction, and one D packet was retransmitted three times;
the two file transfers had one timeout between them), marked it
`incomplete: discarded`, and **never put the following
FINISH on the wire at all** — so the server was still running when MAME's
clock expired, and its `DEBUG.LOG` was never closed or renamed. Whether that
server would have honoured a FINISH is therefore untested; the safe-mode run
says a server in the same state does. `snddir()` in `ckcfns.c` is C-Kermit's
own internal lister, not `ls` through a pipe, so this is entirely inside
upstream's file-send path, and it is not diagnosed.

That is an argument for `--safe-server`, and worth weighing when choosing
which default to ship: the capability that hung is one the milestone does not
need.

### The wildcard send, re-measured against streams that do not translate

§16g's `-s *.TXT` byte counts were taken through the translating streams §16h
later found, so they were re-run. **The difference is exactly what §16h
predicts, and it settles the retraction with numbers:**

| file | on the Victor's disk | §16g received | now |
|---|---|---|---|
| `ALPHA.TXT` | 63 | 61 | **63, identical** |
| `BETA.TXT` | 54 | 53 | **54, identical** |
| `TESTFILE.TXT` | 74 | 72 | **74, identical** |

`files transferred: 3`, `total file characters: 191` — which is 63+54+74. All
three `cmp` clean against the files extracted from the disk image. The
multi-file `znext()` path of §16g is therefore intact **and** now delivers the
bytes that are actually on the disk.

One footnote from getting there, because a DOS user will type it wrong again:
`-s *.txt` matched **nothing** — `nzxpand[*.txt]=0` — where `-s *.TXT` matched
three files. `ckufio.c` line 6262 calls `ckmatch(xpat, s, 1, mopts)`, and
`ckclib.c` line 1344 documents the third argument as *"icase is 1 if
case-sensitive"*. FAT returns names in upper case, so a lower-case pattern
cannot match anything on this file system. Correct behaviour for the Unix
module it is; surprising on this target.

### Sizes

DGROUP **39,440 of 65,536 (60%)**, 26,096 free in the segment; `ckermitw.exe`
is **229,070** bytes. With `KEEP_DEBUG`, DGROUP is **39,792** and the image is
**309,506** — that image measured 309,064 before this section's changes, so
the capability work cost about 440 bytes and `KEEP_DEBUG`'s DGROUP did not
move at all. The two new routines take 10 and 24 bytes of stack (`sub sp`,
read from `wdis`), and they run at startup rather than anywhere near
`traverse()`.

One correction: §16h records the `KEEP_DEBUG` image as 309,046, and a clean
rebuild of the committed tree gives **309,064**. The copy that was on the disk
image measures 309,046 exactly, so that figure was taken from a build made
before the session's last source edit rather than from the tree as committed.

### What this establishes, and what it does not

Milestone step 6 is done: `RECEIVE` (§16h), `GET` and `SERVER`. The port now
works as client and as server, sending and receiving, byte-exact over a
payload containing every byte value, with the loss counters at 0/0 everywhere
they could be read.

**Still under emulation, still only Victor MS-DOS 3.1, still 9600 with window
1 and short packets.** `REMOTE DIRECTORY` does not complete and is not
diagnosed. The full capability set has been exercised only for GET, SEND and
that one failing DIRECTORY — DELETE, RMDIR, CWD, SPACE, TYPE, RENAME and the
rest are enabled by default and **entirely untested**. And `BYE` has never
been sent, so the only way the far end has ever stopped a Victor server is
FINISH.

---

## 16j. Step 8, and the packet length that was never ours

Three changes, in descending order of how much they were worth and ascending
order of how much they taught: the stack, floating point, and long packets.
The third is the one that matters, because chasing it found that **this port
has never sent a packet longer than 90 bytes, and the four symbols everyone
assumed controlled that have never influenced a byte on the wire.**

### The stack is now a number that was chosen

`wlink`'s default for `system dos` is 2,048 bytes and that is what the port
had through §16i — inherited, never decided. §15 had argued for raising it
and deliberately kept it out of the toolchain change. It is now `option
stack=8k` in `victorow.mak`.

The case for it is unchanged: `traverse()` in `ckufio.c` recurses at 98
bytes per level and the two largest non-recursive frames measured are
`docmd()` at 1152 and `zcopy()` at 1114, so a directory walk a few levels
deep that lands inside `docmd()` is already most of 2K. The stack is in
DGROUP (hard rule 4) and there were 26,096 free bytes there.

Cost: DGROUP 39,440 → 45,584, and **6,144 bytes of load memory, not of file
size** — the stack is `.bss`-like, so it lands in the MZ header's `minalloc`
and the `.EXE` does not grow by a byte.

### Floating point, and the largest single saving in the port's history

`NEXT_SESSION.md` carried `NOGFTIMER` as the way to drop `emu87.lib` and
`math87l.lib`. It is not. Measured: `NOGFTIMER` saves 1,424 bytes and
**leaves the emulator linked**, because `CKFLOAT` and not `GFTIMER` is what
drags it in. Only two objects in the whole program reference floating point —
`ckclib.obj` (`_fltused_`) and `ckcfn2.obj` (`__CHP`).

`NOFLOAT` is upstream's own switch and removes it completely:

| | stack-8K baseline | `NOGFTIMER` | `NOFLOAT` |
|---|---:|---:|---:|
| DGROUP | 45,584 | 45,552 | **44,592** |
| far code | 193,878 | 193,090 | **168,296** |
| `ckermitw.exe` | 229,070 | 227,646 | **202,212** |
| needs at load | 239,486 | 238,670 | **212,900** |
| `emu87`/`math87` in the map | 14 | 14 | **0** |

**26,586 bytes** off what the image asks DOS for. Nothing that runs is lost:
`isfloat()`, `ckround()` and `fpformat()` are script-language functions and
`NOSPL` had already removed every caller, and the one live use — the
round-trip-time estimate at `ckcfn2.c:434` — has upstream's integer path four
lines below it at `:442`. The integer form works out about 1.13× larger, so
the adaptive receive timeout becomes slightly more patient, which is the safe
direction here.

It cost the tenth guarded upstream edit (§8) and two warnings. The warnings
are worth recording because they are a real behaviour change: dropping
`GFTIMER` moves `ztime()` off the `gettimeofday()` implementation and onto
upstream's legacy `ZTIMEV7` branch (`ckutio.c:12314`), whose K&R
redeclarations of `time()` and `localtime()` produce sign mismatches at lines
12319–12320. The only functional consequence is that `ztmsec`/`ztusec` stay
at -1 and debug-log timestamps lose their `.mmm` suffix — both readers in
`ckuusx.c` guard on exactly that. The build is now **19 warnings**, still all
in stock upstream code, and `ckvictor.c` still contributes none.

### Long packets: four symbols that do nothing

The plan was one variable at a time — raise `MAXSP`/`MAXRP` to 4000 and
`SBSIZ`/`RBSIZ` to 8192, leaving the window alone — on the arithmetic in
`dofast()` (`ckcfn3.c:352`):

```
maxpktsiz = MAXSP, clamped to 4000
wslotr    = RBSIZ / maxpktsiz
urpsiz    = adjpkl(maxpktsiz, wslotr, RBSIZ)
```

which at 1024/2048 yields two slots of 1,018 — the number `ckvictor.h` and
§16d–§16i had all quoted. DGROUP and image did not move, exactly as
predicted, because under `DYNAMIC` these are far-heap allocations made at
runtime; the Victor confirmed it, `inibufs size 2=16424` with no halving.

**Then the wire said 90.** The Victor's ACK to the host's S packet decodes as
`MAXL=90, WINDO=1, MAXLX1=0, MAXLX2=90` — a 90-byte receive length and window
1, against a host offering 3,999.

`dofast()` is never called. It sits inside the `#ifndef NOTCPIP` that opens
at `ckcmai.c:3390` and **does not close until 3644** — the `#endif` comments
at 3574 and 3644 are misattributed by one level, so the region reads as
unconditional when you look at it locally, and everything in 3575–3643 —
`getdialenv()`, `dofast()`, and a `debug()` line — disappears from any build
that defines `NOTCPIP`. Three independent confirmations:

| method | result |
|---|---|
| `#if`/`#endif` nesting counted **from line 1**, not from the function | 3 blocks open at 3589, outermost `#ifndef NOTCPIP` at 3390 |
| `strings ckcmai.obj` | contains `main argc` (line 3651), **no** `main argc after prescan` (3575), **no** `dofast` |
| preprocessed `ckcmai.c` | `dofast` and `getdialenv` appear **only as prototypes — no call anywhere** |

The first method is the one to remember: counting from the enclosing function
header gave depth 0 and was wrong, because a block opened earlier and closed
inside the range. **Count from line 1.**

With `dofast()` gone, `urpsiz` and `wslotr` keep their initialisers `DRPSIZ`
and `DFWSIZ` — 90 and 1, because the 4095/30 pair is reachable only through
`NEWDEFAULTS`, which is reachable only through `BIGBUFOK`, which hard rule 5
forbids. `NEWDEFAULTS` would not have helped anyway: `makebuf()` divides a
pool by the slot count, so its window of 30 would have carved the 8,192-byte
pool into 273-byte packets.

**This retracts a number, not a result.** Every transfer in §16d, §16g, §16h
and §16i used 90-byte packets and window 1. The transfers were real and the
files were byte-exact; only the claim about *how* they were carried was
wrong. The proof needed no new run — the I packet already printed in §16i
decodes to `MAXL=90, WINDO=1, MAXLX=90`, identical to today's. "Two 1,018-byte
slots" described what `dofast()` would have computed had it been reachable;
it was in `ckvictor.h`, and §9's `MAXWS` paragraph reasoned from the same
`dofast()` arithmetic (corrected in place). §16d–§16i are **not** wrong about
this: they all say "window 1 and short packets", which is exactly what was
happening.

The fix is the **eleventh** guarded upstream edit (§8): `#ifndef` around
`DRPSIZ`, `DFWSIZ` and `DFBCT` in `ckcker.h`, the same shape as edits 2, 3, 7
and 8 — a size constant made overridable. The window stays at 1 deliberately:
with no interrupt-level flow control and a 512-byte RX ring, what has held
`rxlost`/`rxfull` at 0/0 is that the far end waits for an ACK before sending
again, so nothing arrives while the 8088 is writing the last packet to disk.
A longer packet does not disturb that; a second slot does.

### And then the long packets did not work

`DRPSIZ 4000` negotiates exactly as intended. On Victor MS-DOS 3.1 the port
advertised `MAXL=94, WINDO=1, MAXLX=42×95+9 = 3999` — confirmed from both
ends, the host's packet log and the Victor's own `rpar rpsiz=4000` — the host
accepted, and long-format D packets started flowing.

C-Kermit slow-starts the data length rather than jumping to the negotiated
maximum (`spar slow-start spsiz=244` in the Victor's log), and the ramp is
where it died:

| data length | result |
|---:|---|
| 236 | ACKed |
| 480 | ACKed |
| **968** | **Victor timed out, NAKed, host retransmitted twice, transfer dead** |

So there is a receive ceiling somewhere in **(480, 968]** that nothing in the
port's configuration accounts for. `V9K_RXBUFSIZ` is 512 and is the obvious
suspect, but `v9k_comm_read()` drains the ring in a loop and returns what it
has, so at 9600 bps it ought to keep up; `MYBUFLEN` in `ckutio.c` is 1024,
which is above the failure and below the target. **Neither is confirmed.**
The run that showed this never reached FINISH, so the Victor's `DEBUG.LOG` —
and with it `rxlost`/`rxfull`, which would separate those two hypotheses in
one reading — was never flushed.

**`DRPSIZ` is therefore back at the stock 90 in the committed tree.** A build
that negotiates a packet length it cannot honour cannot receive a file at
all, which is worse than one that never asks; the guard that makes 4000
settable is the deliverable here, not the 4000. Raising it back is a
one-constant experiment and it is the first thing the next session should do,
with a fixture small enough that the run reaches FINISH.

> **Superseded by §16k.** That experiment was run. Both hypotheses above are
> resolved and both were partly wrong: the (480, 968] boundary was an
> artifact of `-d` itself at ~25 ms per received byte, and the real limit
> underneath was `V9K_RXBUFSIZ` — the suspect this section dismissed —
> sitting at `rxpeak = 502` of 512. `MYBUFLEN` was exonerated. The ring is
> now 4096 and **`DRPSIZ` is 4000 in the tree**. Read §16k before trusting
> any number in the rest of this section.

What this section actually establishes about step 8, stated plainly: **long
packets negotiate, and carry data to at least 480 bytes. They have not
carried a file.** §16d–§16i's transfers are unaffected — they ran at 90 and
still do. (§16k carries a file: 32,768 bytes, byte-exact.)

### Sizes

DGROUP **44,592 of 65,536 (68%)**, 20,944 free; `ckermitw.exe` **202,212**,
needing **212,900** of the 396,224 the machine offers — **183,324 spare**,
against 162,882 before this section, out of which the far heap then takes
about 25K of packet buffers. With `KEEP_DEBUG`, 282,456 and 287,496 needed.

(§16k's 4096-byte ring then takes DGROUP to **48,176 of 65,536 (73%)** and
the image to 202,294, needing 216,566 — 179,658 spare; §16l's alarm roundup
adds 16 bytes of code and no data, so the current figures are DGROUP
**48,176** and image **202,310**, needing **216,582** — 179,642 spare. The
ones above are this section's.)

`.probe/mzsize.py` is §16a's method made repeatable: it reads the MZ header
and reports image + `minalloc` against 396,224. Run it, not `ls -l`, before
believing a build will load.

### Three things the harness cost this section

**MAME here runs about 1:1 with wall clock**, so `-seconds_to_run` is a real
time budget and 12,288 bytes at the then-unknown 90-byte packet length did
not fit in 500 of them. Size the fixture to the packet length, not to the
principle — 4,096 bytes is two long packets and still carries every byte
value.

**`-log` wrote no `mame.log` in this MAME build**, so §16a's advice to poll
for `"Average speed"` waits forever on a file that never appears. MAME exited
on its own both times; wait on the *process*, not the log.

**`pgrep -f "mame victor9k"` matches your own polling shell**, whose command
line contains the pattern, so the wait never ends and the emulator looks like
it is still running long after it exited. Match the binary path
(`[m]ame/mame victor9k`) or check the job directly.

---

## 16k. The receive ceiling was the instrument, and then it was the ring

§16j left one item at the top of the list: an undiagnosed receive ceiling in
(480, 968] that "nothing in the port's configuration explains". It is
diagnosed. There were two ceilings stacked on top of each other, the outer
one was the debug log, and **the port now negotiates and honours 4,000-byte
packets** — 32,768 bytes byte-exact at 582 cps.

The headline for anyone reading this before touching the receive path:
**`-d` costs about 25 ms per received byte, which is enough to break long
packets by itself.** The instrument this port has leaned on since §16g
cannot be used to measure the thing §16j was trying to measure.

### What §16j actually saw

Reproduced exactly, first run of this session, `DRPSIZ 4000` and
`KEEP_DEBUG`: 236 ACKed, 480 ACKed, 968 dead. The host's packet log shows
the ramp and the host's own timeouts.

But the Victor's `DEBUG.LOG` — flushed this time, because the run reached a
clean exit — says the failure is not a timeout at all:

```
v9k_ser rxlost/rxfull[0]=2483
v9k_ser rxpeak=511
```

`rxlost = 0`, so the µPD7201 never overran the handler and §11b's ISR is not
implicated. `rxfull = 2483`, so the **ring** overran Kermit, 2,483 bytes
thrown away. `rxpeak = 511` of 512, pinned at capacity.

`rxpeak` is new this session and it is what makes the other two worth
reading: `rxfull = 0` alone cannot distinguish "never close" from "one byte
from the edge", and that distinction turned out to be the whole story.

The read sizes in the same log are the mechanism, in order:

```
244, 488, 511, 376, 511, 442, 511, 511, 511
```

The 236-byte packet arrives as one 244-byte read and the 480-byte packet as
one 488-byte read, both comfortably inside the ring. From 968 on, every read
finds the ring full. **The whole session made 18 `read()` calls** — roughly
one per packet.

That kills §16j's model, which is recorded in `ckvictor.h` and was wrong:
the ring "has to cover the longest gap between two of C-Kermit's reads, not
the longest packet, because `myfillbuf()` drains it in one call and comes
straight back". It drains it in one call *into `mybuf[]`*, and `ttinl()`
then walks `mybuf[]` one byte at a time and only calls `read()` again when
it runs out — while the rest of the packet is still arriving.

### The 25 ms per byte, and why it hid the real answer

4,274 `TTINL myread char` lines for one file: `ttinl()` emits a debug line
per byte, and `ckhexdump()` dumps the whole buffer per read. The arithmetic
that follows from the host's packet log is ~25 ms per received byte, and it
corroborates a note already in §16a — "12,288 bytes at 90-byte packets does
not fit in 500 seconds" is the same number seen from the other side.

Against a host packet timeout of 15 s that gives a ceiling in bytes, not in
buffers: 480 × 25 ms = 12 s squeaks through, 968 × 25 ms = 24 s never does.
**That is the (480, 968] boundary, and it is arithmetic about the logging,
not about the hardware.**

The control settles it. Same binary, same `DRPSIZ=4000`, `-d` dropped:

| | with `-d` | without |
|---|---|---|
| 968-byte packet | never delivered | ACKed first try |
| 2,048 bytes | never completed | **4 s, byte-exact** |

### The real ceiling underneath, which was the ring after all

With `-d` gone the ramp goes further and then still stops. 16,384 bytes,
`DRPSIZ 4000`, ring still 512:

| data length | result |
|---:|---|
| 968 | ACKed |
| 1,952 | ACKed |
| **3,904** | timeout, retransmit, and the recovery then collapses |

So §16j's "obvious suspect" was right and the reasoning that dismissed it
was wrong. `V9K_RXBUFSIZ` is now **4096**.

`MYBUFLEN` is exonerated: it is 1,024 and packets of 1,952 and 2,668 crossed
it intact. No upstream edit was needed and none was made.

### The number that was not what I expected

Sizing the ring, the obvious model is that the backlog is proportional to
packet length — the foreground runs a bit slower than the line, so a longer
packet accumulates more. Measured, it is not:

| ring | longest packet on the wire | `rxpeak` |
|---:|---:|---:|
| 512 | 2,668 | **502** of 512 |
| 4096 | 3,605 | **502** of 4096 |

The same 502 with eight times the ring and a third again the packet length.
It is not a rate deficit at all; it is **one fixed stall of about 523 ms at
9600** during which nothing is drained. Which stall is not established — the
file write between packets is the obvious candidate and has not been
isolated, and that is a genuine loose end rather than a formality.

This is why 512 failed the way it did: not too small on average, **ten bytes
from the edge of the one case that matters**, so whether a given packet
survived depended on where that stall landed. 968 and 1,952 survived; 3,904
did not.

4096 is therefore not sized from the measured 502. It holds an entire
maximum-length packet even if the foreground contributes nothing while one
is in flight, which is the only assumption that stays true when something
else gets slower — and with `tcflow()` a stub there is nothing to fall back
on. Cost: 3,584 bytes of DGROUP, 44,592 → **48,176 of 65,536 (73%)**.

### Reading the counters without the log that breaks them

`ckvictor.c` now prints all three to **stdout at `atexit()`, in every
build**:

```
v9k: rxlost=0 rxfull=0 rxpeak=502 of 4096
```

This is not redundancy with the `debug()` lines. A run fast enough to be
worth measuring is exactly a run that cannot carry a debug log, so the
counters had to leave it. A `.BAT` that redirects stdout catches the line;
`STEPE.BAT` in the harness below is the pattern.

### Measured, with both changes in

Victor MS-DOS 3.1 under MAME, 9600 bps, host C-Kermit 9.0.302, Victor as
`CKERMITW -l /dev/seriala -b 9600 -r`, no `-d`:

- **32,768 bytes, byte-exact** (`cmp` against the source after pulling the
  file back off the image), 56 s, 582 cps
- longest packet on the wire **3,605**
- `v9k: rxlost=0 rxfull=0 rxpeak=502 of 4096`
- and 16,384 bytes byte-exact on the previous build, `rxpeak = 502 of 512`

`DRPSIZ` is **4000** in `ckvictor.h`. §16j's standing rule — do not raise it
without a run that reaches FINISH and reports `rxlost`/`rxfull` — is
satisfied three times over.

### Not clean, and the arithmetic for the next session

The 32 KB run still took **one timeout and two retransmissions**, with
`rxfull = 0`. Whatever they are, they are not this ring.

The standing suspicion, derived from the source and **not measured**, is the
timeout itself. `CK_TIMERS` is on and `rttflg` defaults to 1, so `rcvtimo`
is computed by `getrtt()` from `gtimer()`, which has **whole-second
resolution** (`ckutio.c`); with `mintime = 1` the floor is 1 s and the
file-receiver path lands on 3. Meanwhile this port's `alarm()` records
`time() + secs` and fires when `time()` reaches it — so an `alarm(n)` armed
part-way through a second fires in **(n−1, n]**, i.e. *early*, up to a full
second early. The comment in `ckvictor.c` §0d claims the opposite ("fires
somewhere between n and n+1 seconds, never early") and that claim is wrong.

At `rcvtimo = 3` that is a 2 s worst case against 4.2 s of line time for a
3,999-byte packet. **Rounding the deadline up (`time() + secs + 1`) is a
one-line change in our own file** and is the first thing to try. It was not
done this session because it is a behaviour change and this session already
had two.

> **Partly superseded by §16l.** The roundup was done and is in the tree, and
> the analysis above of `alarm()` firing early is correct. But it is **not**
> why the 32 KB run retransmits: the Victor never times out at all. Read
> §16l before spending anything else on this.

---

## 16l. The alarm did fire late, and the retransmissions were never ours

§16k left the roundup at the top of the list, with an explicit warning that
its case was derived and not measured. The change is made and it is right on
its own terms. **The hypothesis attached to it is wrong**, and the packet log
says so in one line: across two complete 32,768-byte receives, the Victor
sent **nothing but ACKs — not one NAK.** Its receive timeout never expired,
so no rounding of it could ever have changed a retransmission.

### The change, which stays

`ckvictor.c`'s `alarm()` now records `time() + secs + V9K_ALARM_ROUNDUP`,
with the roundup taken back off the returned time-remaining so that `ttoc()`
— which subtracts from that value and re-arms — keeps working in the seconds
its caller asked for. The direction §16k derived is real: `time()` is a
floor, so a deadline of `time()+n` armed at real time T+0.9 is reached only
n−0.9 seconds later, i.e. in **(n−1, n]**. The comment in §0d claiming
"never early" was wrong and is replaced with the derivation. Rounded up, the
window is (n, n+1] — late, which is the direction a protocol timeout should
err in.

Cost: nothing in DGROUP (48,176 of 65,536, unchanged — the change is code,
not data), and 16 bytes of image, 202,294 → **202,310**, needing 216,582 of
396,224. No upstream edit; still eleven.

### What the packet log actually shows

Two runs, same 32,768-byte fixture of pseudo-random bytes containing all 256
values, MS-DOS 3.1 under MAME, 9600, `CKERMITW -l /dev/seriala -b 9600 -r`,
no `-d`. **Both byte-exact** (`cmp` after pulling the file back off the
image).

| | run 1 | run 2 (`set receive timeout 20` on the host) |
|---|---:|---:|
| host timeouts | 2 | **1** |
| retransmissions | 4 | **1** |
| elapsed / rate | 60 s, 537 cps | **54 s, 606 cps** |
| longest packet | 3,905 | 3,099 |
| `rxpeak` | 547 of 4096 | 500 of 4096 |
| `rxlost` / `rxfull` | 0 / 0 | 0 / 0 |

`logpkt('S',...)` at `ckcfns.c:2002` is commented "Log the resent packet", so
**an uppercase `S-` line in the packet log is a retransmission** and a
`<timeout>` line is `logpkt('r',-1,"<timeout>",0)` from `ckcfns.c:2900`.
Those two facts make the log countable, and they are the cheapest instrument
this section adds.

Every `r-` line in both runs decodes to type **`Y`**. The Victor ACKs, always,
and never NAKs — which is what a receiver whose timer never fires looks like.
The duplicate ACKs (`r seq=07` twice, `r seq=08` twice in run 1) are the
Victor re-ACKing a packet the *host* sent twice, not the Victor prompting for
anything.

### Where the timeouts do come from

Both runs put every timeout at the same place: **the packet immediately after
C-Kermit's slow start doubles the length.**

```
run 1   s seq=06  1953   ACKed
        s seq=07  3905   <timeout>, resent          <-- first 3.9K packet
run 2   s seq=05   977   ACKed
        s seq=06  1953   <timeout>, resent          <-- first 1.9K packet
```

and in both, after the host backs the length off and climbs again — run 2
reaches 3,099 with no further trouble — nothing else times out. That is a
round-trip estimator being handed a packet whose transmission time just
doubled: 3,905 bytes at 9600 is **4.1 seconds of line time on its own**, and
the estimate feeding the host's timer was built from packets a quarter that
long. Raising the host's floor to 20 s halved the damage and bought 13% of
throughput, and it is a **host** setting — nothing on the Victor changed
between those two runs.

So the standing "one timeout and two retransmissions, not diagnosed" is
diagnosed, and it is not a defect in this port. `SET RECEIVE TIMEOUT` on the
host is the mitigation. (`SET TIMER OFF` is **not** a command in C-Kermit
9.0.302 — it is rejected with "No keywords match"; the dynamic-timer flag
`rttflg` is set by the keyword form of `SET RECEIVE TIMEOUT`, per
`ckuus7.c:6960`.)

### The stall is still there, and now has four readings

`rxpeak` across every long-packet run to date: **502** (§16k, ring 512),
**502** (§16k, ring 4096), **547**, **500**. Four readings inside 10% of each
other across two ring sizes, two fixtures and longest-packets from 2,668 to
3,905. §16k's reading of this — one fixed stall of roughly half a second at
9600, not a rate deficit — survives a second fixture, and it is still
**unidentified**. The inter-packet file write remains the obvious candidate
and remains un-isolated.

`ckvictor.c`'s `v9k_write()` sees *every* write, not just the comm device
(anything that is not `ttyfd` falls through to the library), and
`gettimeofday()` next to it already reads INT 21h `AH=2Ch` for hundredths.
Timing the non-tty writes there is an instrument that needs no upstream edit
and has not been built.

> **Superseded by §16m.** The instrument was built and the stall is
> identified: it is the ring filling during the *host's retransmission*, the
> one moment the host transmits without waiting for our ACK. Same root cause
> as §16l's timeouts, and it is not in this port. The file write was not it.

---

## 16m. The stall is the host's retransmission, and it was never ours

The ~502-byte high-water mark has been on the open list since §16k, called a
stall in §16k, re-measured and left unidentified in §16l, and named as the
top item in the handoff. **It is identified.** The peak is the ring filling
while the host resends a packet the Victor has not finished turning around —
and since §16l established that the timeouts causing those resends are the
host's round-trip estimator being surprised by its own slow start, the last
unexplained number in the receive path turns out to be the second symptom of
a cause already diagnosed and already known to be outside this port.

Getting there cost four runs, three refuted hypotheses and one instrument
that had to be fixed before it could be believed. All four transfers were
byte-exact.

### The instrument, and the bias that had to come out of it first

`ckvictor.c` §0e is new. The foreground keeps one byte saying where it is —
in the library's `write()` (1), in the polled transmitter (2), in the
library's `read()` (3), in `v9k_comm_read()` (4), or in upstream code it
does not own (0) — and the interrupt handler copies that byte at the instant
it raises `rxpeak`. Two stores in the interrupt path, taken only when the
high-water mark moves, and no INT 21h anywhere near it. That last part is
the whole design constraint: §16k's lesson is that an instrument slow enough
to starve the receive changes the number it is reporting.

Alongside it, three things that are affordable because they happen per
packet rather than per byte: the non-tty writes are timed (`v9k_write()`
sees every one of them), the interval between putting an ACK on the wire and
asking for the next byte is timed, and the handler counts how many times
occupancy crosses 256 going up. Everything prints to stdout at `atexit()`
with the ring counters, for the same reason they do.

**The first run's tag was wrong, and the reason is worth keeping.**
`v9k_ser_get()` used to publish the tail once, after the copy loop —
correct, and one store instead of many. But for as long as that copy runs
the handler sees head moving and tail not, so the ring *appears* to keep
filling while it is actually being emptied. A backlog that piled up while
the foreground was somewhere else therefore gets its peak latched during the
drain that is removing it, and the tag reads "we were reading all along" no
matter what really happened. Run 1 duly reported tag 4. The tail is now
published inside the loop, one store per byte, and the instrument is honest.

### Three hypotheses, measured and refuted

**The inter-packet file write** — the standing candidate since §16k. The
writes were timed for the first time: **32 of them, 1,024 bytes each**
(`OBUFSIZE`, `ckcker.h`), totalling 3.5, 7.0, 5.5 and 4.5 seconds across the
four runs, worst single write 0.50 s — and the *first* write, in all three
runs that recorded which one it was. So the disk is a real
cost, 6–11% of a 54-second transfer, and it is not the stall — because
`ckcpro.w:1700` decodes and writes **before** `ack()`, and with a window of
one the host is silent until that ACK arrives. Everything the Victor does
before the ACK is free of ring occupancy by construction. It is not free of
elapsed time, which is a different finding, below.

**The post-ACK window.** Timed directly: in two of the four runs the worst
gap between the ACK going out and the next read was **0 hundredths across
29 and 34 gaps**, while `rxpeak` in those same runs read 544 and 513. A
quantity that is zero when the effect is at its largest is not the cause.

**The drain granularity.** `myfillbuf()` asks for `MYBUFLEN` (1024) and
`ttinl()` then processes the whole bufferful character by character before
asking again, which predicts a peak of MYBUFLEN times the ratio of line rate
to processing rate. The arithmetic fitted beautifully — all five historical
readings collapse to 510–556 µs per character — so the prediction was made
in advance and tested with `XFLAGS=-dV9K_RXCHUNK=256`, which caps what
`v9k_comm_read()` hands back without touching upstream. Predicted `rxpeak`
≈ 133. **Measured 504.** Refuted, cleanly, and the knob stays in the tree
(off unless defined) because a refuted experiment is cheaper to re-run than
to rebuild.

### What it actually is

The handler now also counts every byte it stores and latches that count at
the peak, which turns the question into arithmetic: the Victor's byte
offsets are positions in the host's send stream, and the host's packet log
gives the wire length of every packet it sent, resends included. Run 4:

```
v9k: rxpeak=513 of 4096
v9k: rxbytes=39574 peakat=4570 stallat=4036

offset 4036 -> RESEND seq=06 type=D (1953 wire bytes, 272 into it)
offset 4570 -> RESEND seq=06 type=D (1953 wire bytes, 806 into it)
```

Both the first crossing of 256 and the peak itself land inside the
**retransmission of seq=06** — the packet the host resent after its one
timeout. The original seq=06 occupies 1811–3764 and the resend 3764–5717.
(`.probe/mapoffset.py` does the arithmetic; `.probe/pktstat.py` counts the
log.)

That is the mechanism, and it is the only moment it can happen: **with a
window of one, the retransmission is the one time the host transmits without
waiting for our ACK.** The Victor is still decoding and writing the original
copy of seq=06 when the resend starts arriving, so the ring fills — 806
bytes into the resend, 0.84 s of line time, which is the turnaround for a
1,944-byte packet plus two file writes and agrees with the write timings
above.

The whole chain, end to end: slow start doubles the packet length → the
Victor's pre-ACK turnaround grows with it → the host's estimator, built from
packets a quarter that long, times out (§16l) → it resends → the resend
arrives while the Victor is still turning the original around → `rxpeak`.
One cause, two symptoms, neither of them in this port.

The crossing counter agrees across all four runs:

| | resends | crossings of 256 | `rxpeak` |
|---|---:|---:|---:|
| run 1 | 1 | 2 | 515 |
| run 2 | 4 | 6 | 544 |
| run 3 (`V9K_RXCHUNK=256`) | 1 | 3 | 504 |
| run 4 | 1 | 2 | 513 |

and it explains every invariance that made this so hard to place: the peak
does not scale with ring size, packet length, fixture or drain chunk because
none of those is what sets it.

### The cost that is real, and what it says about 38400

Separately from the stall, the runs put a number on something never
measured: **the dead time is ~12.5 s of a 32,768-byte transfer, and it is
almost identical in runs that differ by 7 s of elapsed time.**

| | wire bytes | line time | elapsed | dead |
|---|---:|---:|---:|---:|
| run 1 | 39,492 | 41.1 s | 54 s | 12.9 s |
| run 2 | 46,673 | 48.6 s | 61 s | 12.4 s |

Run 2 was slower entirely because four retransmissions put 7.2 KB more on
the wire. The Victor's own overhead did not move. Of that ~12.5 s the file
writes are 3.5–7.0 s, measured; the rest is decode and protocol.

This is the number that matters for 38400, and it is not encouraging in the
way one would hope: line time falls by four but the ~12.5 s does not move at
all, so 32 KB would take about 23 s rather than 9 — roughly **1,400 cps, not
2,400**. The ring, meanwhile, is fine: the peak scales with line rate, so
the same event at 38400 is about 2,100 bytes, still comfortably inside 4,096.
**38400 is a CPU and disk problem, not a buffer problem.**

### Two corrections to §16l

**The longest packet in §16l's run 2 was 3,585 data bytes, not 3,099.** The
log's largest sent packet decodes to 3,585 with a 3,602-character line. This
strengthens §16l rather than weakening it: after the timeout the host backed
off and then climbed *past* the length that had timed out, without further
trouble.

**The attribution of 537 → 606 cps to `SET RECEIVE TIMEOUT 20` does not
survive a third and fourth run.** Run 2 of this section used that setting
and reproduced §16l run 1 exactly — 2 timeouts, 4 retransmissions, 61 s,
537 cps — while runs 1, 3 and 4 with the same setting got 1 and 1 at 54 s
and ~603 cps. The setting was held constant and the outcome varied, so what
§16l measured as an improvement is **run-to-run variance in where the host's
estimator first gets caught out**. The structural claim in §16l stands
untouched — every timeout is the host's, every one lands on a slow-start
doubling, and the Victor sends only ACKs and never a NAK, which held across
all four runs here as well.

### Sizes

DGROUP **48,240** of 65,536 (73%), up 64 bytes from §16l's 48,176 — the
counters and latches. Image 202,310 → **203,300**, needing 217,572 of
396,224, 178,652 spare. `ckvictor.c` still compiles with no warnings, and
there is **no upstream edit — still eleven**.

### Measured, and on what

Victor MS-DOS 3.1 under MAME, 9600, host C-Kermit 9.0.302 over a `socat`
pty, `CKERMITW -l /dev/seriala -b 9600 -r`, no `-d`, a 32,768-byte fixture
of pseudo-random bytes containing all 256 values, a fresh target name per
run, `cmp` against the source after pulling the file back off the image.
**Four runs, four byte-exact.** `rxlost=0 rxfull=0` in every one.

Still nothing on real hardware.

---

## 15. Open questions

**Closed since the last revision**

- ~~Why is `MAXWS` redefined?~~ `ckcker.h` defines it unguarded, so it always
  wins; the real value is 32. The §9 buffer arithmetic is unaffected. (§14)
- ~~Does `libdos-m.a` shortcut to BIOS anywhere?~~ **No** — every interrupt in
  the archive is INT 21h, and `libc.a` has none at all. (§12)
- ~~Does **Open Watcom's** `clibl.lib` shortcut to BIOS anywhere?~~ **No** —
  re-measured after the toolchain change, across all 239 library modules
  actually in the linked image: 86 × INT 21h, 89 × the 8087 emulator's
  34h–3Dh, one `int 3`. The four BIOS-using modules in the library
  (`biosfunc`, `b_disk`, `b_timofd`, `dointr`) are not linked. (§12)
- ~~Wildcard expansion: one cause left of four, the port's one open defect.~~
  **Gone.** `-s *.TXT` transfers, single-match and multi-match, byte-correct
  (§16g). Causes 1 and 2 are the guarded `SSPACE` and `MAXWLD` edits and are
  live; cause 3 was a `libdos-m` gap that Watcom does not have; **cause 4 was
  never reproduced under Open Watcom and is closed as retired rather than
  diagnosed** — it left with the build it lived in. (§16f, §16g)
- ~~Do the driver's two loss counters ever fire?~~ **Not at 9600.**
  `rxlost=0, rxfull=0` across a three-file, 44-second transaction — the first
  reading either counter has ever had. Says nothing about 38400 or streaming.
  (§16g) **Now measured for receive too, and still 0/0** (§16h), which is the
  direction that drives the ring hardest because the disk writes are on this
  end.
- ~~The text/binary decision: the host logs "binary" while the Victor sends 74
  bytes as 72.~~ **It was a defect, not a mode.** `ckufio.c` is the Unix file
  module and never passes `"b"`, so the DOS runtime translated every stream in
  both directions — LF↔CRLF, and 0x1A as end-of-file on input. Fixed by a pair
  of changes that are only correct together: `_fmode = O_BINARY` from an
  initializer in `ckvictor.c`, and `#undef NLCHAR` for `VICTOR9K` in
  `ckcdeb.h` (§8 item 9). **This retracts §16d's "byte-correct at the far
  end"** — that claim now belongs to §16h, over a payload containing every
  byte value. (§16h)
- ~~Can `RECEIVE` work at all?~~ **Yes** — and it was blocked by `access()`
  answering EACCES for the FAT root, which `zchko()` asks about immediately
  after successfully creating and deleting a file in that same directory.
  (§16h)
- ~~Real stack size: `wlink`'s 2,048 was inherited, not chosen.~~ **Chosen
  now, and it is 8,192** — `option stack=$(STACK)` in `victorow.mak`. It
  costs 6,144 bytes of DGROUP (39,440 → 45,584) and, because the stack is
  `.bss`-like, 6,144 bytes of `minalloc` rather than any file size. (§16j)
- ~~Would `NOGFTIMER` drop the FP emulator and buy back image space?~~
  **No — that attribution was wrong.** `NOGFTIMER` saves 1,424 bytes and
  leaves `emu87.lib`/`math87l.lib` linked, because `CKFLOAT` and not
  `GFTIMER` is what pulls them in. **`NOFLOAT` removes them entirely**, for
  26,586 bytes, at the cost of the tenth guarded upstream edit and a
  slightly coarser adaptive timeout. (§16j)

- ~~Do `GET` and `SERVER` work?~~ **Yes, both** — milestone step 6 is
  complete. `GET` needed nothing new. **Server mode needed a decision, not a
  fix**: C-Kermit 11 initialises every `en_*` to 2, "remote mode only", and a
  Victor that owns its serial line is by definition local, so the first
  server run ACKed the host's negotiation and then refused every command with
  a well-formed E packet. `ckvictor.c` now settles the capability set at
  startup, from a priority-0 initializer, with `--safe-server` to narrow it
  to GET/SEND/FINISH. **No tenth guarded upstream edit** — the switch is
  removed from Watcom's copy of the command tail before `argv` is built, so
  `cmdlin()` never sees it. (§16i)

**A decision that is yours, not mine**

- **Should `ckcker.h`'s `MAXWS` be wrapped in `#ifndef` — a sixth guarded
  upstream edit?** It would be a one-line change matching what that same file
  already does for `MAXSP`, `MAXRP`, `SBSIZ` and `RBSIZ` four lines below, it
  changes nothing on any other platform (no other build defines `MAXWS`), and
  it reclaims ~736 bytes (§14). Hard rule 1 says to ask rather than do this
  quietly, so it is not done. The alternative is to accept 32, which is what
  the tree does today and is comfortable at 60% DGROUP — and note that 896 of
  those 736-odd bytes are `s_pkt`/`r_pkt`, which are on the **far** heap now,
  so the real DGROUP saving is the 96 bytes of `sbufuse[]`/`rbufuse[]`. This
  has become close to not worth doing.

**Still open**

- **`REMOTE DIRECTORY` streams its listing and never terminates it.** All 51
  entries of `A:\` arrive correctly and each D packet is ACKed; the Z never
  comes, the host times out and discards the transaction, and — the part
  that costs a run — the host then never sends the FINISH that would have
  closed the server, so the Victor's `DEBUG.LOG` is never flushed. `snddir()`
  is C-Kermit's own internal lister, so this is inside upstream's file-send
  path. Not diagnosed. It is enabled by default; `--safe-server` refuses it
  cleanly and the session survives. (§16i)
- **Most of the default capability set has never been exercised.** `-x`
  without `--safe-server` enables DELETE, RMDIR, CWD, SPACE, TYPE, RENAME,
  COPY, MKDIR and the rest. Only GET, SEND and DIRECTORY have been on the
  wire. `BYE` has never been sent either, so FINISH is the only way the far
  end has ever stopped a Victor server. (§16i)
- **Wildcard patterns are case-sensitive against upper-case FAT names.**
  `-s *.txt` matches nothing; `-s *.TXT` matches three files. `ckufio.c` line
  6262 passes `icase=1` to `ckmatch()`, which `ckclib.c` line 1344 documents
  as case-sensitive. Right for the Unix module it is, surprising on DOS, and
  it will be typed wrong again. (§16i)
- **"No files for -s" is not a diagnosis.** Recorded separately because it
  will mislead again: `ckuusy.c` prints that string when it could not
  allocate 2,000 bytes for the real error message. Any time it appears,
  check heap headroom before believing the pattern matched nothing (§16f).
- ~~**The serial arm of `ioctl(fd,FIONREAD)` returns 0** and must be finished
  by the 7201 driver from its RX ring count.~~ **Done** — §11b. It is
  `(head - tail) & mask` now, and `TIOCMGET` was the other half: without it
  `in_chk()` asked `ttgmdm()` for carrier, got -3 and returned 0 before ever
  reaching the count. (§12)
- **Which interrupt vector does IRQ1 arrive on under FreeDOS for Victor?**
  `ckvictor.c` §1e hooks **41h**, which is `msxv90.asm`'s and is right for
  Victor MS-DOS 3.1 (§16d). But `~/projects/myfreedos` remaps the 8259 in
  its own kernel and puts its serial ISR at INT 09h, so the number is a
  property of the boot configuration and not of the hardware. This is the
  most likely thing to break the "one binary, two DOSes" claim, and it is
  one constant.
- **Ctrl-Break with the line open.** The IRQ1 vector is put back from an
  `atexit()` handler, which covers every path through `exit()` including
  `ckusig.c`'s SIGINT handler. It does not cover a Ctrl-Break that DOS turns
  into a bare termination before the runtime's INT 23h handler sees it, and
  a Kermit that exits with IRQ1 pointing into freed memory takes the machine
  down. Not measured on either runtime. The fix, if it bites, is to hook
  INT 23h — which is `AH=25h` and so stays inside rule 6.
- ~~**`coninc()` still does a cooked `read(0,&ch,1)`.**~~ Done — `_read_r`
  now does raw `AH=07h` input with VMIN=1 semantics (§16). **Untested**: no
  path in the current `NOICP` build reads the console, so this code has never
  actually run. It will first matter for `-x` (server mode) interruption.
- ~~**Heap headroom is the binding constraint, not static DGROUP.**~~
  **Closed by the toolchain change, and it is why the toolchain changed.**
  Under gcc the heap and stack shared the 12,808 bytes left in DGROUP; the
  `V9K_HEAPREPORT` instrument measured a working transfer leaving **2,090
  bytes** and a failed wildcard expansion leaving **212**. In the large model
  `malloc()` is `_fmalloc` and the heap is outside DGROUP entirely, so the
  constraint does not exist in that form. The instrument went with the build
  it measured. **What replaces it as the thing to watch is real-mode RAM**:
  §16a's table is the method — image size plus `minalloc` against what
  INT 21h `AH=4Ah` says the machine will give — and the parser build failing
  to load at 429K against 387K available is the standing proof that this
  ceiling is real. Re-measure there, not in DGROUP, before raising
  `SBSIZ`/`RBSIZ`/`MAXSP`/`MAXRP`.
- Does the FreeDOS OEM byte (INT 21h AH=30h → BH) actually come back as `0xFD`
  on the Victor build? The whole dual-target vector detection rests on it. A
  fallback (`SET SERIAL-VECTOR` or a command-line switch) is cheap insurance.
- ~~Does Victor MS-DOS 3.1 install its own handler on IRQ1 for an AUX/COM
  device? If so, Kermit must quiesce it, not just save and restore the
  vector.~~ **Answered by §16d, at least for `porta.exe`.** Taking the vector
  and the chip out from under the OEM driver while its device stays open is
  enough; the transfer completes. That works because nothing ever asks the
  OEM driver for data again — §11a's IOCTL is the only thing left using its
  handle.
- What does the µPD7201 interrupt-acknowledge sequence actually need? Still
  the unproven hardware item (§10) and it gates 38400. §11b's handler issues
  `WR0 = 38h` then the 8259's specific EOI and works under emulation, which
  is what 3.13 does; MAME's µPD7201 is not the part, so this is not settled.
- **`dofast()` is unreachable in this build, and so is `getdialenv()`.**
  Both are inside the `#ifndef NOTCPIP` that opens at `ckcmai.c:3390` and
  closes at 3644, with `#endif` comments misattributed by one level (§16j).
  Routed around rather than fixed: the eleventh guarded upstream edit makes
  `DRPSIZ`/`DFWSIZ` overridable so the port sets the packet length directly.
  **The `ckcmai.c` nesting itself is still wrong**, it is wrong for every
  `NOTCPIP` build and not only this one, and it is worth reporting upstream.
  Note that repairing it would not by itself help here — under the nesting
  the comments *intend*, `dofast()` lands inside `#ifndef NOICP`, which this
  port also defines.
- **`SET FILE COLLISION` is `BACKUP`, and BACKUP cannot work on FAT.**
  `fncact` defaults to `XYFX_B` (`ckcmai.c:1326`) and `znewn()` builds the
  backup name by appending `.~N~` to the whole filename — `LONGBIN.DAT.~1~`,
  which is not a legal 8.3 name. So a receive onto a name that already
  exists is refused, with the attribute-packet reply `N?` and reason
  `reason[30]` = **"name"** (`ckcfn3.c:1386`). §16d–§16i never saw it
  because every run used a fresh filename; §16j hit it the moment a
  truncated run left a 0-byte file behind, and the symptom is a transfer
  that sends S, F, A, then Z with data `D` and no data packets at all.
  Not diagnosed further and not fixed — `SET FILE COLLISION` is an ICP
  command this build does not have, so if it needs changing it changes in
  `ckvictor.h` or an initializer. Until then, **use a fresh name per run**.
- ~~There is an undiagnosed receive ceiling between 480 and 968 bytes, and
  it is the single most important open item.~~ **Diagnosed, and it was two
  ceilings.** The outer one was the instrument: `-d` costs ~25 ms per
  received byte, which starves the ring on its own, and every run that
  established (480, 968] was a `-d` run. The inner one was
  `V9K_RXBUFSIZ` — the "obvious suspect" §16j talked itself out of — now
  **4096**, with `rxpeak` added so `rxfull = 0` can be told from "ten bytes
  from the edge". `MYBUFLEN` is exonerated and needed no upstream edit.
  `DRPSIZ` is **4000** and 32,768 bytes transfer byte-exact. (§16k)
- ~~**What is the ~502-byte stall?**~~ **Identified, and it is the host's
  retransmission.** With a window of one that is the only moment the host
  transmits without waiting for our ACK, so the ring fills while the Victor
  is still turning the original packet around. Both the peak and the first
  crossing of 256 land inside the resent packet, by byte offset. Same root
  cause as the timeouts above, and equally not ours. Refuted along the way,
  each by measurement: the inter-packet file write (it happens *before* the
  ACK, when the host is silent), the post-ACK window (0 hundredths in the
  runs with the largest peaks), and the `MYBUFLEN` drain granularity
  (`V9K_RXCHUNK=256` predicted 133 and measured 504). (§16m)
- **The turnaround costs ~12.5 s per 32 KB and that is what bounds 38400.**
  Measured twice, near-identical in runs whose elapsed times differ by 7 s.
  The file writes are 3.5–7.0 s of it (32 × 1,024 bytes, worst 0.50 s, always
  the first). Line time falls by four at 38400 but this does not move, so
  expect ~1,400 cps rather than ~2,400 — a CPU and disk problem, not a
  buffer one. The ring at 4,096 already covers the ~2,100-byte peak that the
  same retransmission would produce there. (§16m)
- ~~**One timeout and two retransmissions survive in a clean 32 KB run.**~~
  **Diagnosed, and not ours.** The roundup was made and is right, but the
  Victor sends **only ACKs, never a NAK**, across two byte-exact 32 KB
  receives — its timer never fires. Every timeout is the *host's*, and each
  one lands on the packet where C-Kermit's slow start doubles the length
  and hands its round-trip estimator 4.1 seconds of line time it did not
  predict. Four more runs in §16m held `SET RECEIVE TIMEOUT 20` constant and
  got 1, 4, 1 and 1 retransmissions, so §16l's 537 → 606 cps is **variance,
  not the setting** — but everything structural above survived all six runs.
  (§16l, §16m)
- **Window 2** is the increment after that, and it is the one that removes
  the "only one packet in flight" property the missing flow control relies
  on. `DFWSIZ` is still 1.
- **No `-fstack-usage` equivalent under Open Watcom.** Rule 7's discipline
  (measure frames after touching `ckufio.c`, `ckuusr.c` or the size limits)
  lost its cheap instrument with the gcc build. The numbers above are the last
  ones taken. Options, none tried: read `wdis` output for the prologue's `sub
  sp,N`, or keep a scratch gcc build purely as a measuring stick. The second
  is tempting and should be resisted unless the first fails — a second build
  that exists only to measure is how the tree got two of everything.
- `SET LINE` naming: `COM1`/`COM2` for channels A/B is the obvious choice and
  matches the FreeDOS convention, but Kermit is talking to the chip directly, so
  the names are ours to define.

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
  bounds them is real-mode RAM, not the segment -- 805K on the 896K bench
  and 293K on a 384K machine (SS16x; SS16a's "387K" was wrong).
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

Twenty edits, seventeen of them small, guarded and invisible to every
other platform. **Edits 14, 15 and 16 are the exceptions and are flagged as
such**: 14 repairs a mis-nested `#endif` in `ckcmai.c`, and a preprocessor
conditional cannot itself be made conditional; 15 and 16 fix a 16-bit
truncation each, and both are provable no-ops wherever `int` is 32 bits, so
guarding them would mean knowingly shipping the broken form everywhere else.
**Edit 19 is a third 16-bit truncation and is guarded anyway** — the same
argument as 15 and 16 applies to it and was heard and declined; that was
the call made when it was agreed, and it is recorded here so the
inconsistency is visible rather than mysterious.

**Two further upstream defects are FOUND AND NOT FIXED**, both in
`ckutio.c` and both discovered by §16aj while building flow control. They
are listed here because this is the index of everything this port knows
about upstream, and they belong in the same report as 14-17:

- **`ckutio.c:6758`** — `ttpkt()`'s `TESTING234` block, an `if (1)` inside
  an `#ifdef` of its own `#define`, clears `IXON|IXOFF` out of `ttraw`
  unconditionally, four lines before the `tcsetattr()` that applies the
  struct and 141 lines after the `FLO_XONX` arm set them. **`SET FLOW
  XON/XOFF` therefore cannot reach a driver through termios** on any build
  that takes the `BSD44ORPOSIX` arm, which is every POSIX one.
- **`ckutio.c:10849`** — `ttoc()`'s only call to `tcflow(TCOON)`, the POSIX
  recovery from a lost XON, is written **inside a `debug()` argument**, and
  `NODEBUG` defines `debug(a,b,c,d)` as nothing. It is the only caller of
  `tcflow()` in the module, so the whole unstick path vanishes in a
  `NODEBUG` build. A functional side effect inside a logging macro.

**Three more were found by §16ao while building the file-transfer
display, and none is fixed here either:**

- **`ckcdeb.h:6098`** — `NOCURSES` implies `NODISPLAY`. "There is no curses
  library on this platform" is turned into "compile out every file-transfer
  display", including the CRT and SERIAL modes, which need nothing but
  `write()`. `ckcker.h:730` then expands `xxscreen()` and `ckscreen()` to
  nothing. Any build that honestly declares it has no curses silently loses
  its progress display.
- **`ckuusx.c:6372`** — `fxdinit()` gates the fullscreen display on a
  termcap probe even in builds whose curses never reads a termcap.
  `ck_termset()`, the only consumer of what `tgetent()` loads, is called
  four lines below under `#ifndef MYCURSES`. With no TERM in the
  environment it prints "Fullscreen file transfer display disabled" and
  falls back, on information it did not obtain.
- **`ckuusx.c:7070`** — `ck_curpos(row, col) int row, int col;` is a
  malformed K&R declarator; the second `int` is a syntax error. The block
  is only reached when neither termcap nor `MYCURSES` has supplied
  `CK_CURPOS`, which is why **it has apparently never been compiled**.

Neither of the `ckutio.c` pair is touched here, and nor are these three.
Fixing the first `ckutio.c` one is not a guarded no-op — it changes
behaviour on every platform, which is the point of reporting it rather than
patching it (hard rule 1). §16aj has the measurements and what the port
does instead; §16ao has the same for the display three.

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

12. **`ckuusr.c` and `ckuus5.c`** — `#if !defined(NOFRILLS) ||
    defined(VICTOR9K)` around the `SHOW VERSIONS` keyword
    (`ckuusr.c`, `shotab`) and around its `case SHVER:` dispatch
    (`ckuus5.c`). Two halves of one feature, so one edit.

    `shover()` itself is `#ifndef NOSHOW`, not `#ifndef NOFRILLS`, so on any
    build that keeps the command parser and drops the frills the routine is
    **compiled and linked already** and only the two lines that reach it are
    missing. On this port that is not a nicety: `KEEP_ICP` and `KEEP_SPL`
    and `KEEP_DEBUG` produce binaries that look identical on the machine,
    provenance has cost this project time twice (§2 of `NEXT_SESSION.md`),
    and `SHOW VERSIONS` is the only way to ask a running image what it is —
    the Victor has no `strings`. Costs 88 bytes at load in the `KEEP_ICP`
    build and nothing at all in the shipping one, which has no parser to
    type it at.

    The alternative was to make `NOFRILLS` conditional on `KEEP_ICP` in
    `ckvictor.h`, which needs no upstream edit — and it was rejected. That
    switch also gates `zmail()`/`zprint()` in `ckufio.c` and REMOTE
    MAIL/PRINT in `ckcfn3.c` and `ckcfns.c`, so it would pull external
    commands into a `NOPUSH` build and, worse, make the parser build differ
    from the shipping build **inside the protocol engine**. The whole value
    of `KEEP_ICP` as a regression build is that it is the shipping build
    plus a parser.

13. **`ckcmai.c` and `ckufio.c`** — `#ifdef VICTOR9K` arms giving
    `isabsolute()` (`ckcmai.c:1768`) and `zfnqfp()`'s absolute test
    (`ckufio.c:7494`) a DOS pathname. Two halves of one feature, so one
    edit, and **neither half works alone**.

    `isabsolute()`'s UNIX arm tests for a leading `/`, so `A:\FOO.KSC` is
    "relative"; `prescan()` then sends it to `findinpath()`, which under
    `NOSPL` searches an empty path list and exits (§16ab). Fixing that alone
    just moves the failure: `zfnqfp()` spells the same question
    `*s == '/'` and would prepend the current directory to a name that
    already has a drive letter, giving `A:/A:\FOO.KSC`.

    The first half is upstream's own `OS2` arm, six lines below and
    unreachable from a build that cannot define `OS2` — the port has to
    define `UNIX`, because that is what selects `ckutio.c`/`ckufio.c` and
    what makes `ckcdeb.h` define `DYNAMIC` (§1). The letter test is written
    out rather than calling `isalpha()` because `ckcmai.c` does not include
    `<ctype.h>`; its two existing `isalpha()` calls are inside `#ifdef`s no
    supported build compiles, which is a latent defect in its own right.
    The second half calls `isabsolute()` from a module that already calls it
    twice, so on every other platform it is the same test spelled
    differently — the UNIX arm *is* `*path == '/'`, plus the `~` that
    `DTILDE` adds and that a pathname reaching `zfnqfp()` has already been
    through `zzstring()` to expand.

    Note this is the *second* defect on that path and the smaller one.
    The first was ours: `getcwd()` returning `A:\` with a separator upstream
    could not see, fixed in `ckvictor.c` for no upstream edit (§16ab). This
    edit only buys the absolute form.

14. **`ckcmai.c`** — moved one `#endif`. The `#ifndef NOTCPIP` at line
    3417 was closed 70 lines past where its own comment says it belongs:
    the `#endif  /* NOTCPIP */` after the `sstelnet` block actually closed
    the `#ifndef NOICP` on the line below the opener, and the
    `#endif /* NOICP */` at the end of the command-file block actually
    closed `NOTCPIP`. Misattributed by one level, exactly as §16j found for
    the narrower case.

    Compiled out of **every** build that defines `NOTCPIP`, as a result:
    the environment-variable block, `dofast()`, `dotakeini()` (the init
    file) and `if (cmdfil[0]) docmdfile(0)` (a command file named on the
    command line). Such a build silently ignores its init file and, if
    given a command file, reports the *filename* as an invalid option —
    because `docmdfile()` is also what sets `cfilef`, and `cfilef` is the
    only thing that tells `cmdlin()` to skip argv[1] (`ckuusy.c:1597`).

    **This one is not a no-op elsewhere, and it cannot be made one.** An
    `#endif` cannot be placed conditionally; preprocessor nesting balances
    lexically whatever the macros say. So there is no `#ifdef VICTOR9K`
    form of "close this region earlier". What the change does elsewhere is
    restore behaviour upstream plainly intended — the reading is confirmed
    by the code inside the region carrying its own `#ifndef NOICP` guards
    around `dotakeini()` and `docmdfile()`, which would be redundant if the
    whole region were already inside `NOICP`, and by `cmdfil` and `cfilef`
    being declared unconditionally.

    **A second, guarded part comes with it, and it is the interesting
    half.** Restoring the region hands `dofast()` back, and `dofast()` sets
    `wslotr = RBSIZ / MAXSP = 8192 / 4000 = 2`. So the first Victor build
    with the nesting repaired would have negotiated a **window of two** —
    on a port with no interrupt-level flow control, whose 4,096-byte
    receive ring is safe only because a window of one puts at most one
    packet in flight (§16v; the margin is 105 bytes). The call is therefore
    `#ifndef VICTOR9K`, and that guard is a no-op everywhere else. Remove
    it when flow control and windowing are done. **A preprocessor repair
    that silently changes the wire protocol is the thing to watch for
    here**, and this one would have — unmeasured, against a rule
    (`CLAUDE.md`) that says no window or packet-length change ships without
    a run that reaches FINISH and reports `rxlost`/`rxfull`/`rxpeak`.

15. **`ckuus5.c`** — one pair of parentheses in `cmdini()`:

    ```c
    -   spdtab[j].kwval = (int) ss[i] / 10;
    +   spdtab[j].kwval = (int) (ss[i] / 10);
    ```

    The cast bound tighter than the divide. `ss[i]` is a `long`, so on a
    16-bit `int` the truncation happened first: `(int)38400L` is -27136 and
    -27136/10 is -2713. `cmkey()` returns that as the keyword's value, `SET
    SPEED` sees `x < 0` and returns **with no message**, and the speed
    silently does not change. Every rate above 32767 is affected, and 76800
    and 115200 are worse than 38400 because they stay positive — they are
    *accepted*, as 11260 and 49660 bps.

    **Not wrapped in `#ifdef VICTOR9K`, on purpose.** On a platform with a
    32-bit `int` the two expressions compute the same value bit for bit, so
    there is nothing to guard; wrapping it would mean knowingly shipping
    the wrong expression everywhere else. It is the only edit in this set
    that is simultaneously unguarded and a provable no-op elsewhere.

    Only `SET SPEED` reaches this table, which is why a 16-bit build can
    transfer at 38400 indefinitely and never see it: `-b` divides as a long
    already (`ckuusy.c`, `zz = atol(*xargv); i = zz / 10L;`). §16ad.

16. **`ckuusy.c`** — one declaration in `cmdlin()`'s `case 's':`

    ```c
    -   int fil2snd, rc;
    +   int fil2snd;
    +   CK_OFF_T rc;
    ```

    `zchki()` returns `CK_OFF_T`, and on success what it returns is the
    **file's size** (`ckufio.c:2477`). Stored in a 16-bit `int`, a
    32,768-byte file arrives as -32768, which is neither `> -1` nor `-2`,
    so the caller at `ckuusy.c:3727` concludes the file does not exist and
    `-s <name>` refuses to send it. `zchki()` had *succeeded*; nothing set
    `errno`; so the diagnostic comes out as

    ```
    kermit -s TRANS.DAT:
    ```

    with nothing after the colon. **An empty `ck_errstr()` on that line is
    the signature** — it means the file was found and the caller threw the
    answer away.

    It is **periodic, not a ceiling**, because the wrap repeats every 64K:
    32,767 works, 32,768 through 65,535 fail, 65,536 works, 98,304 fails.

    **Not wrapped, for edit 15's reason** — where `int` is 32 bits `rc`
    already holds the whole value and the two declarations are identical.

    **Why it went sixteen sections unnoticed.** §16d sent a 74-byte file.
    §16g used `-s *.TXT`, and a wildcard takes the `nzxpand()` branch —
    which is reached *only because* `zchki` appeared to fail, so the
    wildcard path routes around the defect. And every 32 KB test in this
    port has been a **receive**, and `zchki` is not in the receive path.
    The port had never sent a large file by name. Found on the bench,
    8 August 2026. **Workaround in any unfixed build: send by wildcard.**

    Proven first at the level of generated code — `wdis` shows `dx:ax`
    surviving the call and a signed 32-bit compare (`cmp dx,0xffff` / `jg`)
    where the old form discarded `dx` — and **now run end to end on the
    machine**: §16ah leg BS sent a file of exactly 32,768 bytes, inside the
    broken range, by name, at 38400, byte-exact, with no error line in the
    output at all. The signature this leg watched for — `kermit -s NAME:`
    with an *empty* message after the colon, meaning `zchki()` succeeded and
    the caller discarded the answer — did not appear. **It was the last
    shipped edit in this port with no runtime evidence behind it.**

17. **`ckcfn2.c`** — a `VICTOR9K` arm in `chk3()`, plus the 256-entry
    `crctab16[]` it reads. **The same CRC**: same polynomial, same initial
    value, same absence of a final XOR, computed in `unsigned int` through
    one table instead of in `long` through two.

    ```c
    -   c = crc ^ (long)(*pkt);
    -   crc = (crc >> 8) ^ (crcta[(c & 0xF0) >> 4] ^ crctb[c & 0x0F]);
    +   c = (crc ^ (unsigned int)(*pkt++)) & 0xFF;
    +   crc = ((crc >> 8) & 0xFF) ^ crctab16[c];
    ```

    Upstream holds a 16-bit quantity in `long` variables and indexes two
    `long[16]` tables with it (`ckcfn2.c:312`). On a 32-bit machine that is
    free. On an 8088 built with `-0` it is not, and `wdis` on the shipping
    build says exactly how much: the loop contained **two software shift
    loops**, because an 8086 has no shift-by-immediate —

    ```
    mov cx,4 / L: sar dx,1 / rcr ax,1 / loop L      (c & 0xF0) >> 4
    mov cx,8 / L: sar dx,1 / rcr ax,1 / loop L      crc >> 8
    ```

    — twelve iterations at ~21 cycles on every byte, purely to move bits a
    16-bit variable would not have needed moved, plus four word loads where
    two would do and all three `register` declarations spilled to the frame.
    **603 8088 cycles per byte become 81**; 36 loop instructions become 15;
    the function loses its stack frame entirely. Watcom recognised
    `crc >> 8` as `mov al,ah / xor ah,ah` rather than a shift by CL, which
    is better than the hand estimate that argued for the edit.

    **`crcta[]`/`crctb[]` are left exactly as they are.** `ckcfns.c:260`
    declares them `extern long` and reads them in six places for the
    running file CRC (`\v(crc16)`), a path §16af did not measure. Narrowing
    them would make this a two-file edit, and §8 has twice recorded that an
    edit needing a second file is a different and larger thing than the one
    that was agreed. The cost of that decision is 512 bytes of DGROUP
    duplicating 128 already spent.

    **Guarded, and it did not have to be.** The new form is correct on any
    platform — the two masks are free where `int` is 16 bits and
    load-bearing where it is wider. It is inside `#ifdef VICTOR9K` anyway
    because it is an optimisation for one CPU and not a defect fix, which
    is the distinction 15 and 16 turn on. It changes nothing anywhere else.

    Correctness is proved twice over and the two proofs are different
    claims: `v9k/proofs/vcrc16.c` checks the table identity `crctab16[b] ==
    crcta[b>>4] ^ crctb[b&0x0F]` **exhaustively** over all 256 entries, and
    the loop identity over 20,500 length-and-fill combinations (every length
    0–4099, past `DRPSIZ`, × five patterns). Then §16af transferred 32,768
    bytes byte-exact against a stock C-Kermit at 9600 under MAME and three
    times at 38400 on the machine. **A block check that is fast and wrong
    fails silently**, which is why the probe exists and why it is
    exhaustive rather than sampled.

18. **`ckutio.c`** — a `VICTOR9K` bulk-read arm at the bottom of
    `ttinl()`'s per-byte loop, plus one local and the gate that selects it.
    **Purely additive: no upstream line is changed.** The arm consumes only
    what `myread()` has already buffered, so refills, EOF, `EINTR`, the
    alarm and every error return still happen in untouched upstream code,
    exactly when they did before.

    ```c
    if (v9k_bulk_ok) {
        while (my_count > 0 && i < max-1) {
            CHAR * bsrc = mybuf + my_item + 1;
            int room = (max-1) - i;
            int bk = (my_count < room) ? my_count : room;
            CHAR * bp = (CHAR *)memchr(bsrc,eol,(size_t)bk);
            int blen = bp ? (int)(bp - bsrc) + 1 : bk;
            memcpy(dest+i,bsrc,(size_t)blen);
            i += blen; my_item += blen; my_count -= blen;
            v9k_bulkn++;
            if (bp) { /* same exit as the byte loop's */ }
            n = dest[i-1];
        }
    }
    ```

    **The design rests on a fact the source does not show, and `wcc -pl` is
    what found it.** `ckvictor.h:1100` defines `NOPARSEN` with the comment
    "No network directory parse". That is not what it means: `ckcdeb.h:3971`
    uses it to suppress `PARSENSE`, and `ckcdeb.h:3966` spells out the
    consequence — "**length-driven packet reading**". So this build does
    **not** compile the length-driven `ttinl()` that `ckutio.c` reads like
    it has. It compiles the four-argument form, in which a packet ends at
    `eol` and nowhere else: no length field, no `havelen`, no extended
    header, no sequence-number peek, no mid-packet SOP resync.

    That makes the arm's claim unusually strong. `memchr(src, eol, n)` looks
    for **exactly** the byte the byte loop looks for, on exactly the same
    stream, so the two are equivalent **on corrupted input as well as
    clean** — a mangled terminator makes both run to `max-1` or to the
    alarm, because neither is reading a length. `NOPARSEN` is left as it is;
    see §16aq for why turning `PARSENSE` on would move foreground cost the
    wrong way.

    **The gate**, read once outside the loop, is
    `v9k_bulkin && (ttpmsk == 0377) && !(!xlocal && xfrcan)`. Parity sensed
    would need every byte masked on the way into `dest[]`, which `memcpy()`
    cannot do; the cancellation scan counts *consecutive* `xfrchr` and the
    arm must not swallow the count. Both are dead on this port and both are
    checked anyway, so the arm is inert in any configuration it was not
    reasoned about rather than subtly wrong in it.

    **`v9k_bulkin` is a variable, not an `#ifdef`, and that is the
    instrument.** `--nobulk` turns the arm off at run time, so the control
    leg and the treatment leg are the same 226,330 bytes in the same places
    — §16ap's shape, which leaves §16w's code-size sensitivity nothing to
    act on. `v9k_bulkn` counts the runs copied and prints at exit as
    `v9k: bulk sel= n=`. It is not decoration: **an equivalence test cannot
    see a switch that silently failed**, because a correct arm returns the
    byte loop's answer either way, and a mutation deleting the switch from
    the gate escaped every case in the proof until the counter existed.

    Correctness is proved twice and they are different claims.
    `v9k/proofs/vttinl.c` transcribes the byte loop **out of `wcc -pl`
    output, not out of `ckutio.c`**, and compares the two over **100,023
    cases** — terminator at every offset against every refill granularity,
    five terminator values, overflow, `max` on either side of the
    terminator, EOF and hard error injected at every offset, several packets
    per refill, both gate conditions, and the runtime switch. **13 of 13
    deliberate mutants are caught** and a no-op control stays clean. Then
    §16aq transferred 32,768 bytes byte-exact nine times — twice under MAME
    at 9600 and seven times at 38400 on the machine.

    Two things the proof caught that reading did not: the overflow return
    value (`n` must be carried forward or it is a byte from up to 1023
    positions earlier — both arms return "a positive number `rpack()`
    misreads as a length", so a transfer test cannot separate them), and the
    clamp to the room left in `dest[]` rather than to `my_count` alone.

19. **`ckufio.c`** — one declaration in `zfcdat()`. `unsigned int mtime`
    is assigned `buffer.st_mtime`, a `time_t`, so on a 16-bit target the
    date is truncated mod 65536 and `zdtstr()` renders the remainder as a
    time on **1970-01-01**. This is the third instance of edit 15 and 16's
    shape and the first one found by testing a feature rather than by
    reading:

    ```c
    #ifdef VICTOR9K
        time_t mtime;
    #else
        unsigned int mtime;
    #endif /* VICTOR9K */
    ```

    **It has two symptoms and only one of them is cosmetic.** `nxtdir()`
    calls `zfcdat()` for every entry, so a `REMOTE DIRECTORY` listing dates
    the whole volume to 1970 — and `ckufio.c:4635` calls it for
    `xx->date.val`, the **file date attribute**, so every file a Victor
    server sends carries the wrong date and lands on the client with it.
    §16ax measured both: a file the Victor itself created at 1980-01-01
    00:02 listed as `1970-01-01 11:50:50`, and the `GET` of it arrived on
    the Mac dated 1 January 1970. Anything that compares dates across the
    link — `SET FILE COLLISION UPDATE` is the one in this build — was
    therefore comparing a truncation.

    **Guarded, against the argument that governed 15 and 16.** It is a
    no-op wherever `int` is 32 bits, so by that rule it should be
    unguarded; it is wrapped because that was the decision taken, and §8's
    header says so rather than leaving the inconsistency to be rediscovered.

20. **`ckcpro.w` and `ckcfns.c`** — a `VICTOR9K` arm for `REMOTE SPACE`,
    in the shape of the OS/2 one that has been there all along. **Purely
    additive in both files: no upstream line changes**, and neither arm
    compiles anywhere else.

    Every UNIX build answers `REMOTE SPACE` by running `df` through
    `syscmd()`, and `NOPUSH` compiles `syscmd()`'s body away to
    `return(0)`, so `<generic>U`'s `#else` path could only ever reply
    `Can't check space`. §16ax measured exactly that. `ckcfns.c` gains a
    `sndspace()` beside the OS/2 one, using `memstr`/`memptr` because the
    report is a single line, and `ckvictor.c` §1d gains `v9k_dskspace()` —
    INT 21h `AH=36h`, free clusters × sectors/cluster × bytes/sector, all
    three multiplied **as longs** because the product does not fit in 16
    bits on any volume worth the question.

    **The drive argument is deliberately ignored.** Upstream's caller
    passes `x ? toupper(srvcmd[2]) : 0`, and with no argument on the
    command `srvcmd[2]` is *past the terminating NUL* — honouring it would
    report on whatever letter the previous command left in the buffer. The
    VICTOR9K arm passes 0, which is DOS's default drive, which is the
    volume the server is serving from.

    This is the first upstream edit in the port that **adds a capability**
    rather than repairing or accelerating one. It costs 64 bytes of DGROUP
    (`spctext[64]`) and 288 bytes of image, and it moves the load
    requirement from 236K to **237K** — still 384K of Victor.

Items 2, 3, 6, 7, 8, 10, 11, 13, 14, 15, 16 and 19 are worth offering upstream
regardless of this port, and **14 and 15 are the ones to send first**: it is a plain
defect, it is ~40 years old, and it disables two documented features in any
configuration that turns TCP/IP off.
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

**Current figures, as of §16ax (upstream edits 19 and 20): DGROUP 48,896 of
65,536 (74%), far code 193,864, image 230,690, needs 242,786 (237K) at load,
smallest Victor 384K.** The block below is the ORIGINAL snapshot and is kept
because the commentary under it is what this section is for; it is not the
shipping build's numbers. Every section from §16ag onward states its own, and
`make -f victorow.mak sizes` plus `python3 v9k/tools/mzsize.py ckermitw.exe`
answer the question in two commands.

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
allocation come from the far heap. What bounds them is the RAM the machine
gives a program -- **805K at 896K, 293K at the 384K floor** (§16x; §16a's
"387K" was a FreeDOS figure and is retracted) -- not the 26,112 bytes left
in DGROUP.

So there are two separate budgets now, and confusing them is the mistake this
section exists to prevent:

| Budget | Ceiling | What is in it | Headroom |
|---|---:|---|---:|
| DGROUP | 65,536 | `.data`, `.bss`, **stack** | 26,112 |
| Real mode | 805K at 896K, 293K at 384K | far code, far data, **heap** | see §16x |

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
separately: the parser build asks DOS for 429KB contiguous. **The "387KB"
this paragraph used to cite is retracted by §16x** -- MS-DOS 3.1 gives 805K
at 896K, so 429KB fits there and the parser is blocked by DGROUP and by
`ckvisr.asm`, not by RAM. Fitting the data group and fitting the RAM remain
two different questions, which is what this section is for.

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

- **This port, transferring files in both directions at 9600, 19200 and
  38400** (§16o). Victor 9000, 896 KB, Victor MS-DOS 3.1 booted from a Pico
  SASI emulator serving `victor_kermit.img`, channel A through
  `/dev/seriala`, 1 m USB-C to RS-232 to a Mac running C-Kermit. Six
  transfers, two per rate, each validated by a round trip that came back
  md5-identical. **No code change** — §16n's binary, eleven upstream edits.
  This is the claim the whole project existed to make and everything below
  it in this subsection is a component of it.
- **Our interrupt-driven receive, clean at 9600 and 19200 and NOT at
  38400.** `rxlost = 0` at both lower rates over full 32 KB receives, so the
  `WR0 = 38h` + specific-EOI acknowledge sequence works on the real µPD7201
  up to a ~520 µs byte interval. **At 38400 it does not**: `rxlost = 203`
  and `207` in two runs, 0.45% of received bytes, in bursts of roughly 50.
  Files still arrive byte-exact because Kermit resends what fails a
  checksum — the cost is throughput, not data. Ruled out by measurement as
  causes: the file writes (8× as many changed nothing) and the ring
  (`rxfull = 0`, `rxpeak` ≤ 2,098 of 4,096). (§16o, §16p)
- **The OEM driver programs 38400 through its IOCTL control block.** The
  divisor is `msxv90.asm`'s and undocumented — Appendix A stops at 19.2k —
  and the driver accepts it. (§16o, §11a)
- **This machine's DOS clock advances in half-second steps.** Inferred from
  six emulated runs in §16n and confirmed on hardware: every timing figure
  the port has printed, on either platform, is a multiple of 50 hundredths.
  Quote `tot=`, never `max=`. (§16o)
- **38400 bps transmit on µPD7201 channel A.** 8253 Counter 0 at divisor 2,
  VIA2 PA0 internal clock, polled TX. This is the FreeDOS boot debug console
  (`kernel/victor_serial_debug.asm`, `BAUD_DIV_38400 = 0x02`, built under
  `VICTORFAST=1`) and it has carried sustained kernel output during real
  hardware debugging sessions. The physical layer at 38400 — divisor, clock
  gating, chip init, 1488/1489 line drivers, cabling — is not in question.
  **MAME caps around 9600 and 38400 is a real-hardware-only path.** The cap
  is not configuration: above 9600 the emulator cannot execute the machine
  fast enough to meet the serial timing thresholds, and the other end of the
  `-bitb` socket is a real host at a real line rate that will not wait. So
  no rate above 9600 can be tested in this harness at all — see §16n, which
  also measures the emulator at ~99% of real time *at* 9600.
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
- **XON/XOFF flow control, the half of it this harness can reach** (§16aj).
  `--xonxoff` selected, applied and reported; the water mark asserted and
  released once each on a 32 KB receive with the marks lowered to 256/64;
  five host START characters intercepted out of the stream with the
  `rxbytes` reconciliation still exact at −11; byte-exact, `rxlost = 0
  rxfull = 0`. **What it does NOT show is a far end obeying our XOFF** — a
  `socat` pty is not a serial line. **RTS/CTS cannot be tested here at
  all**: `-bitb socket` is a raw byte stream with no modem control.

### Written but never run on hardware

- ~~**Our interrupt-driven receive at speed.**~~ **Largely closed by §16o**,
  which is why the entry moved up. 19200 is proven clean on hardware
  (`rxlost=0 rxfull=0`); 38400 is proven to transfer but its counters have
  never been read, so "clean at 38400" is the one part of this that remains
  unproven. Nothing here has been tested against a *floppy* write holding
  the ring — every hardware run so far was SASI.
- **Flow control on a real cable, both mechanisms** (§16aj). The default is
  `FLO_NONE` precisely because of this: selecting RTS/CTS makes the
  transmitter wait for CTS, and while §16v measured the host's RTS arriving
  at our CTS, nothing has measured our RTS arriving at the host's. One bench
  leg decides it. The assert path under ring overflow (`v9k_ringfull`
  re-entering the water-mark check) has also never executed, the same
  standing caveat the assembly handler's overrun branch carries.
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

### 11a0. The baud clock tree, measured on the board

7 August 2026, and it settles an argument that had run through four
documents. **CLK5 reads precisely 5 MHz on a logic analyzer**, and the
schematic's serial sheet shows it reaching the 8253's `CLK0` and `CLK1`
through two 74LS90 divide-by-two sections — 12E and 10E, each drawn using
only the `CKA -> QA` half. So:

```
CLK5 5,000,000 Hz --> LS90 12E /2 --> LS90 10E /2 --> 8253 CLK0/CLK1 1,250,000 Hz
8253 count --> LS153 15F mux --> uPD7201 RXCA/TXCA, /16 (WR4 = x16)

    bps = 5,000,000 / (4 * 16 * count) = 78125 / count
```

The board's other oscillator read 14.2–16.5 MHz on the same capture, which
is the sampling quantisation of a 15 MHz square wave rather than a real
spread. 15 / 3 = 5.000 exactly, consistent with CLK5 being divided down from
the master rather than being its own can — which is why it is **not** the
4.9152 MHz baud crystal a machine wanting exact rates would use.

**So every async rate on this machine is 1.72% fast** and no integer count
fixes it: 78125/9600 = 8.14, and 8 gives 9765.63. That is inside async
framing tolerance (~2.5%) and is why it interoperates with a host set to the
nominal rate. `victor/sys/termios.h` labels each `B*` code with both numbers
and those labels are now measurement rather than inference.

This confirms, and retires the argument over, four secondary sources:
`msxv90.asm`'s own "78125/(baud rate)" comment; Appendix A's divisor table
(110 -> 710, 150 -> 520, 300 -> 260, all 78125-derived); `vickermit.c`'s
byte-identical table; and MAME's `15_MHz_XTAL / 12` on `set_clk<0>`/`<1>`,
which reaches 1.25 MHz by a different division and the same answer. **The
one source that disagreed is `~/projects/myfreedos/kernel/victor_int14.asm`,
whose comment says "Crystal: 1.2288 MHz" and whose 110–1200 baud divisors
(698, 512, 256, 128, 64) are 1.7% fast in the other direction.** It works,
because 1.7% is inside tolerance either way, and from 2400 up the two tables
are identical — which is why two ports of the same machine have disagreed
below 2400 without anyone noticing. That file is not in this tree; flagged
for its owner.

### The x1 clock mode, a retraction, and the sweep that settles it

**The operator ran this machine at 115 Kb in 1990** with a different comms
program. That is the governing fact in this subsection: the rate is
achievable on this hardware, so any argument concluding otherwise has an
error in it, and the job is to find the settings rather than to reason about
whether they exist.

**Retraction.** This document and three code comments claimed the uPD7201's
x1 clock mode was synchronous-only. It is not. The NEC datasheet, pin
description for RxCA/RxCB:

> The Receiver Clocks may be 1, 16, 32, or 64 times the data rate in
> asynchronous modes. Receive data is sampled on the rising edge of RxC.

and WR4's clock-mode field is independent of the stop-bit field that selects
async in the first place. x1 async is permitted, and the claim was asserted
three times before anyone opened the datasheet that was on the same machine.

**What the datasheet does not say** is anything about start-bit
re-centring — there is no half-bit delay, no bit-centre search, no sampling
diagram. The only statement is the one quoted. So the open question is not
legality but phase: at one clock per bit the sample point sits wherever the
local generator's phase puts it relative to the incoming bits, and the
receiver cannot tell the start of a start bit from the end of one. That
predicts *marginal* behaviour rather than failure — a stable phase that
lands mid-bit works indefinitely, and a slowly drifting one works until it
crosses a bit boundary. Which is exactly the kind of thing that has to be
measured over time rather than demonstrated once.

**It splits by direction.** Transmit at x1 should be sound — the
transmitter defines its own bit boundaries, "TxD changes on the falling edge
of TxC" — so a Victor *sending* at x1 should frame cleanly. Receive is the
half at risk. The datasheet requires the same multiplier for both, so they
cannot be mixed.

#### The rate table for the sweep

`bps = 1,250,000 / (factor * count)`, count >= 2 for 8253 Mode 3:

| target | factor | count | actual | error | note |
|---|---|---:|---:|---:|---|
| 9600 | x16 | 8 | 9,765.63 | +1.73% | shipping control |
| 9600 | **x1** | **130** | 9,615.38 | **+0.16%** | the discriminator |
| 19200 | x16 | 4 | 19,531.25 | +1.73% | shipping |
| 38400 | x16 | 2 | 39,062.50 | +1.73% | shipping, unchanged control |
| 38400 | x1 | 33 | 37,878.79 | -1.36% | x1 at a proven rate |
| 57600 | x1 | 22 | 56,818.18 | -1.36% | `B57600` |
| 76800 | x1 | 16 | 78,125.00 | +1.73% | `B76800`, now legal |
| 115200 | x1 | 11 | 113,636.36 | -1.36% | `B115200` |

**Run the x1/9600 point first, because it is the one that isolates the
variable.** Its frequency error is +0.16%, an order of magnitude *better*
than the +1.73% this port has run at 9600 for its entire life. So if
x1/9600 fails where x16/9600 succeeds, the cause is the sampling phase and
nothing else. If it succeeds, the phase concern is empty and the rest of the
table is a straight rate sweep.

#### What is in the tree to drive it

`victor/sys/termios.h` gains `B57600`, `B115200`, and a redefined `B76800`
(x1 count 16, replacing the illegal x16 count 1). `ckvictor.c` gains
`v9k_clkbits[]`, a table parallel to `v9k_divisor[]` giving each B code its
WR4 bits 7-6, with a compile-time check that the two stay the same length.
`tcsetattr()` takes the clock mode from it instead of hard-coding x16.
`ttspdlist()` picks all four up automatically — verified through the
preprocessor — so `-b 115200` and `SET SPEED 115200` work with **no upstream
edit**; edit 15 is what makes the keyword table return the right value for
them.

For points with no B code, one build per point:

```sh
make -f victorow.mak XFLAGS="-dV9K_CLKBITS=0x00 -dV9K_COUNT=130"   # x1/9600
```

`0x00` x1, `0x40` x16, `0x80` x32, `0xc0` x64. The override applies to every
speed, so such a build ignores `-b` and `SET SPEED` — deliberately, so there
is no ambiguity about what was on the wire.

#### Protocol

For each point: a 32 KB transfer each direction, checking md5 both ways, and
`rxlost`/`rxfull`/`rxpeak` plus retransmission and timeout counts from the
packet log. Then leave the link up for a few minutes — **the phase concern
predicts intermittency, not immediate failure, so a single clean transfer
does not clear a point.**

**The logic analyzer is the part that makes this decisive**, and it answers a
question the transfer cannot: whether the OEM driver's IOCTL actually
applies CR4. §11a already knows the write subfunction does not apply CR1.
If it silently ignores the clock-mode bits too, the chip stays at x16 and
every x1 point runs at 1/16 the intended rate — which a scope on TxD shows
in seconds and a failed transfer does not distinguish from a phase problem.
**Measure the bit period on TxD before believing any result.**

**MAME cannot run this sweep.** Its RS-232 link is bit-synchronous, so x1
would very likely pass in emulation regardless of what the hardware does —
a false positive. It also caps around 9600 (§16n). Hardware only.

#### First sweep run, 7 August 2026 — x1 takes effect and corrupts

Three points ran on the bench before the session ended. The results narrow
the question sharply and **eliminate one of the two candidate causes.**

```
S96X16  x16 count   8   rxbytes=39503  file=32768  rxlost=0 rxfull=0  60.0 s  clean
S96X1   x1  count 130   rxbytes=20309  file= 1156  rxlost=0 rxfull=0  27.0 s  Protocol error
S384X1  x1  count  33   no output at all -- died before the exit report
```

The Mac gave up on retransmissions in `S96X1`; the operator stopped after
`S384X1`.

**x1 is being applied, and the rate is approximately right.** 1,156 bytes of
the fixture were written correctly — 3.5%, which is the operator's "a few
percent in" — before it degraded. Had the OEM driver's IOCTL ignored CR4's
clock-mode bits, the chip would have stayed at x16 with count 130 and run at
601 bps against a host at 9600; nothing would have framed at all, from the
first byte. So the "CR4 not applied" candidate is **dead**, and the §11a
worry that the write subfunction might drop the clock bits the way it drops
CR1 does not apply.

**It is corruption, not loss.** `rxlost = 0` and `rxfull = 0`: the µPD7201
reported no overrun and the receive ring never filled. 20,309 bytes were
clocked in and **94.3% of them were rejected by the protocol**. The bytes
arrive; their values are wrong. That is the signature of mis-sampling, and
it is not the signature of an overrun, a slow handler, or a ring that is too
small — all three of which this port has seen before and all three of which
show up as `rxlost` or `rxfull`.

So the evidence is consistent with the sampling-phase mechanism §11a0
predicted: at one clock per bit the receiver anchors to the first RxC edge
after the start-bit transition, which is up to a full bit late, and nothing
re-centres it. **Consistent with is not the same as demonstrated**, and the
alternatives are not yet excluded — the LS153 may route something
unexpected in this configuration, or the x1 clock may have an integrity
problem at the mux that x16's oversampling was hiding. The scope settles it.

**What to probe, and both are TTL on small DIPs rather than the 40-pin
7201:**

- **LS153 15F pin 7** (`1Y`) — the receive clock actually reaching the
  7201 for channel A.
- **MC1489 14D pin 3** — the TTL-level received data from the Mac.

Three things to read off them:

1. **RxD bit period** should be 104.17 µs (host at 9600).
2. **RxC period.** 104.0 µs confirms x1 with count 130. If it reads ~6.5 µs
   the chip is at x16 after all and everything above is wrong.
3. **Where the RxC rising edge falls inside each RxD bit cell, and whether
   that offset drifts.** This is the measurement that decides it. The
   mechanism predicts an offset that walks at roughly the 0.16% frequency
   difference — one full bit every ~625 bit times — with corruption
   whenever it crosses a bit boundary.

Running `S96X16` with the same probes is the control: at x16 the RxC period
should be 6.5 µs and the oversampling is directly visible.

**A caution on reading the corruption pattern:** if it is periodic — clean
runs alternating with bursts — that is the phase walking, and it also
explains why 3.5% got through before the protocol gave up. If it is uniform
from the first packet, the mechanism is something else.

#### Second sweep run: the model confirmed, and the envelope it implies

`S96X1S` — x1, count 130, `DRPSIZ=90` — ran 8 August 2026. The Mac reported

```
 Packets sent: 65        Retransmissions: 132
 Timeouts: 1             Damaged packets: 0
 Transfer canceled by receiver.  Receiver's message: "Too many retries."
```

197 attempts for 65 distinct packets is **33.0% first-attempt success**
against a **predicted 39.2%**. Backing the rate error out of the
observation, at ~110 wire bytes per packet:

```
implied p_char 1.003%  ->  implied rate error 0.1114%
                           measured rate error 0.1150%   (scope, TD vs RD)
```

Within 3% of the pin measurement. The Victor side agrees: `rxlost = 0
rxfull = 0` again — still corruption, never overrun — `wfile of 2683` bytes
against 1,156 with long packets, and `txgap n = 198` matching the attempt
count.

**Three points now fit one relation across a 400x range of packet length:**

```
P(packet accepted) = (1 - 9 x rate_error) ^ L        L = wire bytes
```

| what the Victor received | L | predicted | observed |
|---|---:|---:|---:|
| ACKs, send leg | ~10 | 90% | "a few retransmissions" |
| short data, `S96X1S` | ~110 | 39% | **33%** |
| long data, `S96X1` | ~1700-4000 | ~0% | 94.3% rejected |

The 9 is the number of bit times from the start-bit sample to the stop-bit
sample in 8N1; it is the distance over which the two clocks drift apart
before the next start bit re-anchors. At x16 there is no such term at all,
because the half-bit centring absorbs the drift — which is why x16 tolerates
1.73% and x1 does not tolerate 0.115%.

**The mechanism is settled. x1 works, and its capacity is packet length
times rate error.**

#### The envelope, and what it does to the remaining sweep points

At x1 the 8253's count quantisation is coarse — one step at count 130 is
0.77% — so the Victor cannot meet a standard-rate host halfway. Against a
host at the nominal rate:

| target | count | actual | error | P(110-byte packet) |
|---|---:|---:|---:|---:|
| 9600 | 130 | 9,615.38 | 0.16% | 20% |
| 19200 | 65 | 19,230.77 | 0.16% | 20% |
| 38400 | 33 | 37,878.79 | **1.36%** | **0.0001%** |
| 57600 | 22 | 56,818.18 | **1.36%** | **0.0001%** |
| 76800 | 16 | 78,125.00 | **1.73%** | **0.00003%** |
| 115200 | 11 | 113,636.36 | **1.36%** | **0.0001%** |

**So `S384X1`, `S576`, `S768` and `S1152` cannot work as staged**, at any
packet length, against a Mac set to the nominal rate. Their nominal mismatch
is an order of magnitude worse than the one that already costs 67% of
packets at 9600. `S384X1` producing a zero-length `.OUT` on the first sweep
is consistent with this and needs no other explanation.

Those four points are only reachable if **the host is set to the Victor's
computed rate** — 37,879, 56,818, 78,125, 113,636 — which macOS will not do
through termios. `v9k/probes/macspeed.c` does it with `IOSSIOSPEED`:

```sh
cc -O2 -o v9k/probes/macspeed v9k/probes/macspeed.c
v9k/probes/macspeed /dev/cu.usbserial-XXXX 113636 -h
```

`-h` holds the descriptor open, which is required: the rate is a property of
the open port and macOS restores the driver's own idea of it on last close.
Run C-Kermit in another terminal against the same device and **give it no
`set speed` command at all** — `ttpkt()` calls `ttsspd()` whenever a speed
was set, which would put a standard rate back over the top. The helper
prints what `tcgetattr` reads back, but treat that as advisory; a
non-standard rate does not always survive the round trip through termios
even when the hardware has taken it. The scope is the measurement that
counts.

With the host matched, the remaining error is two free-running crystals,
perhaps 100 ppm, and the envelope becomes:

| packet | at 0.115% (nominal mismatch) | at ~100 ppm (matched) |
|---:|---:|---:|
| 110 B | 33% | 90% |
| 500 B | 0.3% | 64% |
| 1000 B | ~0% | 40% |
| 4000 B | ~0% | 2.7% |

**Matching the host does not rescue long packets.** Two independent crystals
cannot hold 4,000 bytes together at x1. A few hundred bytes is the ceiling,
and that is a property of the mode rather than of this implementation.

#### What this is worth, stated against the measured bottleneck

The operator ran 115 Kb on this machine in 1990, and that is now supported
rather than merely asserted: x1 is a real async mode on this hardware, the
Victor transmits 32 KB at x1 cleanly, and the receive side works to a
length that the rate match determines.

But §16v measured the throughput bound as the **foreground decode path** —
564 µs per received byte, a **~1,353 cps ceiling** — against 1,013 cps
already achieved at 38400 with x16 and 4,000-byte packets. So a perfect
113,636 bps x1 link buys at most about a third, and must pay for it with
short packets, more turnarounds, and rate matching at both ends. **Windowing
is what would recover the turnaround cost, and it is gated on flow control**
(NEXT_SESSION.md items 4 and 5). Rate is still not the lever; §16v's
conclusion survives the whole of this subsection.

#### Closed: 39,062.50 bps is the ceiling, and the code now says so

8 August 2026. The operator traced the serial sheet and closed the last
avenue: **the only path to the 7201's RxCA is through the 74LS90 divider
chain.** There is no fixed tap that bypasses the 8253, and no external clock
from the connector that reaches the receiver. The LS153 at 15F selects among
LS90 outputs, not around them.

That makes the ceiling arithmetic and final:

```
bps = 1,250,000 / (16 x count)      count >= 2 (8253 Mode 3)
    = 78,125 / count
    = 39,062.50 at count 2
```

**Which is what the port has shipped since §16o.** `B38400` is count 2, it
was already the fastest thing the machine can do asynchronously, and §16v
measured it at 1,013 cps. The three days of x1 work did not raise the
ceiling; it established where the ceiling is and why.

**What changed in the tree:**

- `victor/sys/termios.h` — `B57600`, `B76800` and `B115200` removed;
  `__MAX_BAUD` back to `B38400`. This matters more than it looks: `ttspdlist()`,
  `ttsspd()` and `ttgspd()` all key off these `#define`s, so defining one is
  enough to let `SET SPEED` and `-b` select a rate that cannot transfer.
  Verified through the preprocessor that the offered list now ends at 38400.
- `ckvictor.c` — `v9k_divisor[]` ends at 2; `v9k_clkbits[]` and its
  compile-time length check are gone; `tcsetattr()` uses x16 directly.
- **The overrides stay.** `XFLAGS="-dV9K_CLKBITS=0x00 -dV9K_COUNT=<n>"`
  still forces any clock mode and count for one build, so the experiment is
  repeatable without a broken rate in the shipping table. Confirmed it still
  builds.

Shipping build: 205,530 bytes, needs **219,738 (214K)**, smallest Victor
384K. Nineteen warnings, the same nineteen.

The x1 sweep binaries (`CKX9600`, `CKX384`, `CKX96S`) and their `.BAT`s are
off the image; `S96X16.BAT` stays, because the x16 control is worth keeping.

**What was actually gained.** Three things that were assumptions on 5 August
are measurements now: the 8253 sees exactly 1,250,000 Hz (LS153 pin 7, two
counts, same product); every rate on this machine is 1.72% fast and no
integer count fixes it; and x1 is a real async mode that transmits 32 KB
byte-exact but cannot receive long packets on a free-running link. None of
that was known before, and the first of them settled an argument that had
run through four documents in two projects.

#### Retractions from this sequence, because there were four

1. **"x1 is synchronous-only."** Wrong. The datasheet permits x1 in async
   and says so in the RxC pin description. Asserted three times before the
   datasheet was opened, and it was on the same machine throughout.
2. **"Roughly half of characters sample too near an edge."** Wrong by ~10x.
   The correct figure is `9 x rate error`.
3. **"x1 is dead / not viable."** Wrong. It is viable with a length
   constraint, and the send leg proves the transmit half outright.
4. **The 102.40 µs Victor bit period was presented in a table of measured
   values and was derived** — from the LS153 pin 7 period times 16. The
   operator caught it, the TD measurement then confirmed the derivation
   exactly, and the correction is the reason the model could be tested at
   all. **Keep measured and derived apart in the same table, always.**

**A second finding from the same sheet, and nobody is using it.** The 8253's
`OUT0`/`OUT1` do not reach the 7201 directly. They are *inputs* to an
**LS153 dual 4-to-1 multiplexer at 15F**, whose `1Y` (pin 7) and `2Y` (pin
9) drive `RXCA`/`TXCA` and `RXCB`/`TXCB`. The OEM's Table C-2 names them
"MUX SERIAL A/B" for exactly this reason. The other mux inputs appear to be
fixed taps off the LS90 chain. **Neither this port nor the FreeDOS driver
programs those select lines**, so the mux sits in whatever state reset or
the OEM driver leaves it. Two consequences worth carrying: there is a degree
of freedom here that has never been touched, and if a fixed tap does feed
one of those inputs it is the only route to a clock the 8253 cannot make —
which matters because the 8253 is in Mode 3 (`36H`) and modes 2 and 3 both
require a count of at least 2, putting divisor 2 (39,062 bps) at the ceiling
and making `B76800`'s divisor 1 unprogrammable.

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
   open, and outside this step.  **(§16aw: it terminates. That claim was the
   debug log, and the feature is closed.)**
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

**§16x retracts that last row.** It is a FreeDOS figure -- the failure
quoted above is FreeDOS's message -- and it sat here under an MS-DOS 3.1
heading and was inherited by every later section. **Victor MS-DOS 3.1 gives
824,784 (805K) at 896K**, so the parser build's 429K would fit; what stops
it today is DGROUP and `ckvisr.asm`. Read §16x before using any number from
this table.

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
  **Structurally prevented since 2026-08-09**, which is the better fix than
  a third recording of the same lesson: `.gitattributes` marks `*.BAT` as
  `text eol=crlf`, so the repository stores LF and **every checkout converts
  to CRLF** — whatever platform, editor or `core.autocrlf` produced the
  file. `git add` on an LF-authored `.BAT` now warns as it stages. The
  harness `.BAT` files are tracked for the same reason (they were not
  before, while their paired `.ksc` take-files were), so a leg is
  reproducible from a checkout rather than regenerated by hand — and
  regenerating them by hand is exactly how §16ae stepped on this after it
  had been documented for several sections.
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
returns garbage. Measured with `v9k/probes/vaccess.c`:

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

Measured with `v9k/probes/vfmode.c`: in a small test program it sets `_fmode` to
0200 correctly — with the object the toolchain ships in `rel/lib286/dos`
(which is byte-identical to the **small model** build) and with the large-model
build of the same source. Linked into `CKERMITW.EXE`, either object leaves
`_fmode` at 0100. Everything checkable said it should work: the record is in
the XI table (it grows 0x3c → 0x42), `cstart` runs every priority
(`mov ax,0FFh`), `_TEXT` is a single 60,160-byte segment so a near call reaches
the routine, and `_fmode` is the plain variable in both programs.
`v9k/probes/vfmodefp.c` killed the most promising hypothesis — that the 8087
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
- `v9k/probes/vaccess.c`, `v9k/probes/vfmode.c` and `v9k/probes/vfmodefp.c`, built per the
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

**`REMOTE DIRECTORY` in the full-capability run is the one open item.**
**RETRACTED BY §16aw: it was not an item at all.** This run carried `-d`,
and `nxtdir()` debugs four times per output character, so the listing was
being produced at roughly one character per 100 ms and MAME's clock expired
before the Z could be reached. With the log shut, a 157-file root lists in
31.077 s with zero timeouts. The observation as it stood: the
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
diagnosed. **(§16aw: it does complete. This run carried `-d`.)** The full capability set has been exercised only for GET, SEND and
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

`v9k/tools/mzsize.py` is §16a's method made repeatable: it reads the MZ header
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
(`v9k/tools/mapoffset.py` does the arithmetic; `v9k/tools/pktstat.py` counts the
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

> **Read §16n's 38400 subsection alongside this.** MAME cannot run this
> machine above about 9600 — the emulation is too slow to meet the timing
> thresholds against a real host on the other end of the socket — so
> everything below is arithmetic and no run in this harness can ever test
> it. §16n also revises the figure to ~1,630 cps.

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

## 16n. The disk cost is per call, and a quarter of the dead time is gone

§16m's parting instruction was to attack the ~12.5 seconds of dead time
rather than the ring, and it named the file writes as the one component that
had been measured: 32 writes of 1,024 bytes costing 3.5–7.0 s of a
54-second transfer. **That is now 4 writes and about 1 second, the dead time
is 9.8 s instead of 12.8, and 32,768 bytes arrive at 633 cps instead of
603.** The cost was per call, not per byte, which is the outcome that made
the change worth making and was not knowable in advance.

### The change, and why it is not a twelfth upstream edit

`OBUFSIZE` is 1,024 here because `ckcker.h` falls through to its "not
`BIGBUFOK`" default, and unlike `DRPSIZ` that default is **unguarded**, so
`ckvictor.h` cannot pre-empt it. It does not have to. `OBUFSIZE` is read in
exactly two places — to give the `int zobufsize` its initial value
(`ckcmai.c:1652`) and to bound `SET BUFFERS` (`ckuus7.c:3755`), which `NOICP`
removes. Everything that moves a byte reads the **variable**:

```
getiobs()   malloc(zobufsize)                 ckcmai.c:3795
zmchout()   flush when zoutcnt >= zobufsize   ckcker.h
```

so anything that runs before `getiobs()` sets the size. `main()` calls it at
`ckcmai.c:3331`, after `sysinit()` at 3176 — but `sysinit()` is `ckutio.c`,
which is stock, so the earliest hook this port owns is the XI table that
§16h and §16i already use. `ckvictor.c` §1d now has a third record, priority
32, far, setting `zobufsize = V9K_OBUFSIZE`. **No upstream edit — still
eleven.**

The cost is far heap, not DGROUP: `zoutbuffer` is a `char *` under `DYNAMIC`
and `malloc()` is `_fmalloc` in the large model, so rule 4's *second* budget
pays and the 64K segment does not move at all.

### Per call or per byte, which was the whole question

Both runs used the identical fixture bytes, the same `set receive timeout
20`, and produced the **identical 39,574 wire bytes with one timeout and one
retransmission** — so unlike §16m's comparison this one is not confounded by
where the host's estimator gets caught out.

| | §16m run 4 (1,024) | 16n run 1 | 16n run 2 |
|---|---:|---:|---:|
| file writes | 32 | **4** | **4** |
| disk total | 4.50 s | 0.50 s | 1.50 s |
| `rxpeak` | 513 | **309** | **310** |
| elapsed | 54 s | **51 s** | **51 s** |
| cps | 603 | **633** | **631** |
| wire bytes | 39,574 | 39,574 | 39,574 |

If the cost were per byte, an 8 KB write would take eight times a 1 KB write
and the total would not move. It fell by a factor of three to nine. **Per
call.** Fitting the two sizes gives about **0.124 s of fixed cost per
`write()` plus 15 µs/byte** (~64 KB/s of actual transfer), which predicts

| `V9K_OBUFSIZE` | writes | disk time for 32 KB |
|---:|---:|---:|
| 1,024 | 32 | 4.5 s |
| 4,096 | 8 | 1.5 s |
| **8,192** | **4** | **1.0 s** |
| 16,384 | 2 | 0.75 s |

so 8,192 collects most of what is available — the floor, one write for the
whole file, is 0.6 s — and the remaining sizes are not worth the far heap.
`V9K_OBUFSIZE` is `#ifndef`-guarded, so `XFLAGS=-dV9K_OBUFSIZE=1024` puts
§16m's baseline back for one build with no tree edit.

### A second effect, which confirms §16m rather than adding to it

`rxpeak` fell from 513 to **309**, on the same fixture and the same
retransmission. That is not a coincidence and it is not independent: §16m
established that the peak is the ring filling while the host resends a
packet the Victor has not finished turning around, so the peak is a direct
measure of **our pre-ACK turnaround**. Shorten the turnaround by removing
file writes from it and the peak shortens with it — 204 bytes, 0.21 s at
9600, about one write. `stallat` is 4,036 and 4,034 against §16m's 4,036,
and `peakat` 4,366 and 4,365 against 4,570; all four still land inside the
resend of seq=06, which occupies 3,764–5,717. Same mechanism, same place,
smaller.

### The correction: the clock is half a second, not a hundredth

**§16m's "worst single write 0.50 s, and always the first" does not survive
looking at the instrument.** Every timing figure this port has ever printed
— across six runs and three independent timers, file writes, console writes
and post-ACK gaps — is a multiple of **50 hundredths**, and no `max` has
ever read anything but 0 or 50:

```
max=0  max=50   tot=0 tot=50 tot=100 tot=150 tot=350 tot=450 tot=550 tot=700
```

So the Victor's DOS clock advances in **half-second steps**. `v9k_centis()`
reports hundredths because `AH=2Ch` has a hundredths field, but the field
only ever holds 0 or 50, and §16m's note that "a 0 means under one tick" was
right in spirit and wrong by a factor of nine about the tick. What follows:

- **No individual write was ever timed.** 50 is the smallest non-zero value
  the instrument can return, so "the worst write took 0.50 s" means only
  "that write crossed a boundary". Which write shows it is close to a coin
  flip — §16m saw it on the first three times running and read a pattern
  into it; here it landed on #4 and then on #1.
- **The totals are still sound, and are the half worth quoting.** A write of
  true duration *d* < 0.5 s crosses a boundary with probability *d*/0.5, so
  the sum over many writes is an *unbiased* estimator of the true total even
  though no single term is. That is why 32 samples (9 crossings → 4.5 s)
  is a usable number and 4 samples (1 and 3 crossings → 0.5 and 1.5 s) is a
  noisy one, and why the two runs here differ threefold on the disk while
  agreeing to a second on elapsed time.

The aggregate-versus-individual warning was already in the handoff; what is
new is that the quantum is 0.5 s, which makes it much stronger than it read.

### What this says about 38400, and what the harness cannot say at all

§16m's arithmetic, with the new dead time: line time for 32 KB falls by four
to about 10.3 s, the dead time is now 9.8 s rather than 12.5, so 32,768
bytes would take **about 20 s, or ~1,630 cps** — up from §16m's ~1,400
projection and still a long way from the ~2,400 the line rate alone
suggests. The conclusion is unchanged and only slightly less bleak:
**38400 is a CPU problem now, much less a disk one.** Of the 9.8 s that
remains, about 1 s is disk; the rest is decode and protocol and has never
been profiled.

**But that projection cannot be tested here, and it is worth being blunt
about why.** §11's "MAME caps around 9600" is not a configuration limit, it
is the emulator running out of time: above 9600 the emulation cannot execute
the machine fast enough to meet the serial timing thresholds, because the
other end of the `-bitb` socket is a *real* host transmitting at a real line
rate through `socat` and does not slow down to match. So **38400 is a
real-hardware-only path for this port, and every 38400 figure in §16m and
§16n is arithmetic, not measurement.** Nothing in this harness will ever
confirm or refute them.

That makes the emulator's own speed at 9600 a number worth having, and both
runs give it for free: `-seconds_to_run 300` and MAME exited **302 s of wall
clock later, in both runs** (launch is `sleep 105` before the host `kermit`
starts, so 07:00:39 → 07:05:41 and 07:07:03 → 07:12:05). **Emulated time
tracked real time to within about 1%** — which is exactly what one would
expect just below the ceiling, and it is what makes the 9600 numbers
comparable at all. If it had drifted, the "dead time" would have been partly
the emulator's and the whole of §16n would be measuring the wrong machine.

Two caveats survive that, and neither is closed:

- **Real-time is not the same as cycle-accurate.** MAME keeping up with the
  wall clock says emulated seconds and real seconds agree; it says nothing
  about whether the emulated 8088 retires instructions at the rate real
  silicon does. The 9.8 s of decode and protocol is a faithful measurement
  of *this emulated machine* and an untested estimate of a real one.
- **The disk timing is almost certainly MAME's and not the Victor's.**
  0.124 s of fixed cost per `write()` is very slow for a hard disk, and the
  emulator has no reason to model the real drive's overheads faithfully. The
  **direction** of §16n's result is safe on any hardware — fewer, larger
  writes cannot be worse — but the **size** of the saving may not transfer,
  and 8,192 could turn out to be over-provisioned for a real Victor. It
  costs far heap and nothing else, so it is not worth pre-emptively undoing;
  it is worth re-measuring the first time this runs on the real machine.

### Sizes

DGROUP **48,240** of 65,536 (73%) — **unchanged**, which is the point of the
far heap. Image 203,300 → **203,338** (+38: one XI record and one function).
Needs 217,594 of 396,224, 178,630 spare. `ckvictor.c` compiles with no
warnings.

### Measured, and on what

Victor MS-DOS 3.1 under MAME, 9600, host C-Kermit 9.0.302 over a `socat`
pty, `CKERMITW -l /dev/seriala -b 9600 -r`, no `-d`, the same 32,768-byte
fixture §16m run 4 used, a fresh target name per run, `cmp` against the
source after pulling the file back off the image. **Two runs, two
byte-exact**, `rxlost=0 rxfull=0` in both.

Still nothing on real hardware.

---

## 16o. It runs on the real machine, at 9600, 19200 and 38400

Every section from §16d to §16n ends with the sentence "still nothing on
real hardware." **That sentence is retired.** On 6 August 2026 the port ran
on a physical Victor 9000 and moved files in both directions at all three
rates, six transfers, every one of them successful.

**It took no code change.** The binary that ran is §16n's — 203,338 bytes,
the same eleven guarded upstream edits, the same `ckvictor.h`. Nothing in
this section is a fix; it is all measurement.

### The configuration

Stated in full because §10 distinguishes what is proven on which hardware
and this is the first entry that earns the top half of that list.

| | |
|---|---|
| machine | Victor 9000, **896 KB** physical RAM |
| operating system | **Victor MS-DOS 3.1** (the OEM DOS, not FreeDOS) |
| boot media | Pico SASI emulator serving `victor_kermit.img` — the same image MAME boots, unmodified |
| serial | µPD7201 **channel A**, `/dev/seriala`, OEM `porta.exe` loaded from `CONFIG.SYS` |
| cable | USB-C to RS-232, **1 m**, previously run at 38400 many times |
| host | Apple M4, macOS, C-Kermit |
| rates | 9600, 19200, 38400 — **two transfers at each** |
| validation | file sent to the Victor, sent back off it, `diff` clean and **md5 identical** to the original |

The Pico serving the MAME image as-is is worth noting on its own: it means
the whole harness — image, `.BAT` files, fixtures, host-side script — moves
between emulator and bench with the serial device name as the only
difference. `HW_TESTING.md` §1.4 predicted three differences and there were
three.

### The counters, from the one instrumented pair

A 19,808-byte file at 19200, one transfer each way. Both directions clean.

```
-s hw_test3.md          -r
rxlost=0 rxfull=0       rxlost=0 rxfull=0
rxpeak=54 of 4096       rxpeak=56 of 4096
peaktag=0 stall256=0    peaktag=0 stall256=0
rxbytes=184             rxbytes=20431
peakat=88 stallat=0     peakat=116 stallat=0
wfile n=0               wfile n=3 of 8192 tot=50 cs
wcon  n=1 tot=50 cs     wcon  n=1 tot=0 cs
txgap n=17 tot=100 cs   txgap n=14 tot=0 cs
```

**Three things come out of that, and one of them is a surprise.**

#### `rxpeak` collapsed, and it is the strongest evidence yet that §16l's timeouts were the emulator's

**56 bytes at 19200, against 309–513 under MAME at 9600.** One sixth the
occupancy at twice the line rate. §16m established what the peak measures —
our pre-ACK turnaround, sampled while the host resends, because with a
window of one that is the only moment the host transmits without waiting for
us. `peakat=116` puts this peak inside the first 116 bytes, which is the S/F
negotiation, and `stall256=0` says the ring never crossed 256 for the whole
remaining transfer.

The reading that suggests is that **this transfer had no retransmissions**:
the real machine turns a packet around fast enough that the host's
round-trip estimator is never caught out, so the resend §16m needed to
produce a peak never happens. The host packet log below confirms that for
*this* transfer and **refutes the generalisation** — do not read `rxpeak =
56` as a property of the port on hardware.

### The packet log, which was kept after all, and it takes half of that back

`run1.pkt` was found in the tree after the counters had already been
written up. It is the whole bench session in one host `kermit` invocation —
twelve segments, three of them dead air while the operator typed at the
Victor's keyboard with the host still in `receive`. **The rate is not
recorded per segment, so none of what follows can be attributed to 9600,
19200 or 38400.**

| lines | direction | file | outcome |
|---|---|---|---|
| 1–12 | Victor → host | `testfile.txt`, 74 B | clean |
| 13–40 | host → Victor | `hw_testing.md` | clean |
| 41–72 | — | — | dead air: 16 timeouts, 16 host NAKs |
| 73–81 | host → Victor | S only | 4 timeouts, 4 S resends — Victor not yet running |
| 82–119 | host → Victor | `hw_testing.md` | **1 timeout, 1 resend** (seq 06) |
| 120–130 | host → Victor | `hw_testing.md` | **refused — Z with data `D`** |
| 131–158 | host → Victor | `hw_testing.md` | clean |
| 159–210 | host → Victor | `hw_testing.md` | **3 NAKs *from the Victor*, 5 resends, 2 timeouts** |
| 211–223 | — | — | dead air: 6 timeouts, 3 S resends |
| 224–251 | Victor → host | `hw_test3.md` | clean |
| 256–283 | Victor → host | `hw_test3.md` | clean |
| 284–311 | host → Victor | `hw_testing.md` | clean |

Session totals are 13 retransmissions and 31–40 timeouts depending on how
they are counted, and **most of both are dead air rather than transfer
failures** — 7 of the 13 resends are the host reoffering its S packet to a
Victor that was not running yet. Counting only inside transfers: **6
retransmissions across nine transactions.**

Three things fall out, and the second is the important one.

**Every Victor → host transfer was clean.** Three of them, zero resends,
zero NAKs. The send direction — polled TX, the half already proven on this
hardware by the FreeDOS debug console — behaved perfectly.

**The Victor sends NAKs on real hardware, and §16l said it never does.**
Three of them in the 159–210 transfer, each answered by a host resend. §16l
established across two byte-exact 32 KB MAME receives that "the Victor sent
only ACKs, never a NAK, so its receive timer never expired", and concluded
every timeout was the host's. **That was a property of the emulator, not of
the port.** A NAK is the Victor telling the host a packet failed its
checksum — that is corrupted data on our receive path, whether from a
µPD7201 overrun or from the line, and it is the first direct evidence of
either on hardware. Note also that this transfer carried the file in 19 D
packets where the clean ones used 8–12: C-Kermit shortens packets after
errors, so the log shows it adapting.

**This is exactly the "byte-exact is not clean" caveat, now with
evidence.** Every file still arrived md5-identical, because that is what
the checksums and resends are *for*. The counters, not the file, are what
say whether the driver is clean — and the run whose counters we have
(`rxpeak = 56`, `rxlost = 0`) was one of the clean segments, which is why it
looked better than the session was.

**One thing the log settles outright:** the longest packet in it is **3,991
bytes**, so `DRPSIZ = 4000` long packets are live on real hardware as a
measurement rather than the arithmetic below.

**And one triage entry proved itself on first contact.** The 120–130 segment
is S, F, A, then **Z whose data field is `D`**, with no data packets at all
— the signature §16j documented for `SET FILE COLLISION = BACKUP` refusing
a name that already exists on FAT. `HW_TESTING.md`'s failure table has the
row; the bench hit it on the third attempt at the same filename.

#### `rxlost=0` at 19200 says the interrupt-acknowledge sequence is right on the real part

At 19200 a byte arrives every ~520 µs and the µPD7201's receive FIFO is three
deep, so a handler that is not being re-entered promptly overruns. It did not,
across 20,431 received bytes. Our `WR0 = 38h` followed by the 8259's specific
EOI — which is what `msxv90.asm` does — is correct on the actual chip and not
merely on MAME's model of it.

This is the item §10 has carried as unproven since §11b, and it is the same
question that left `~/projects/myfreedos`'s IRQ-driven receive shipping with
`irq_enabled = 0` to this day. It is answered at 19200. See below for why
38400 does not yet answer it as cleanly as it looks.

#### The half-second clock is the Victor's, not MAME's

§16n inferred from six emulated runs that this machine's DOS clock advances
in half-second steps, and flagged the possibility that it was an emulation
artifact. **It is not.** Every timing figure in both hardware runs — 50, 50,
100, 0 — is a multiple of 50 hundredths. §16n's rule stands unchanged on
hardware: **quote `tot=`, never `max=`**, and treat any figure built from
few samples as noise.

### What 38400 settles

Two risks `HW_TESTING.md` §5 was built around, and both are retired at the
functional level.

**The OEM driver accepts the undocumented divisor.** §11a noted that the
driver's Appendix A stops at 19.2k, that `B38400` and `B76800` are
`msxv90.asm`'s rather than the OEM's, and that nothing in the appendix says
the driver validates what it is given — with the §11a status check added
precisely so a rejection could not come back carry-clear and look like
success. It did not reject. `tcsetattr()` programs 38400 through the IOCTL
control block on real hardware and the line runs.

**And the data path holds at a ~260 µs byte interval.** Both directions,
twice — **in the sense that the files arrive correct, which §16p shows is
not the same as the chip keeping up.** `rxlost = 203` at 38400. Risk A is
dead; Risk B is alive and is now measured rather than suspected.

### What this does *not* settle, and the first one is easy to overread

- **`rxlost` was never read at 38400, and the packet log makes that the
  most urgent gap in this section.** The transfers were byte-exact, and
  byte-exactness is not the same claim: Kermit checksums every packet and
  resends what fails, so a µPD7201 overrun corrupts a packet, gets caught,
  gets resent, and the file still arrives perfect. Overruns surface as lost
  **throughput**, not lost data. So 38400 is proven to *work* and is not yet
  proven to be *clean*. **And we now know the receive path is not uniformly
  clean**: the Victor NAKed three packets in one transfer, at a rate the log
  does not record. If that transfer was at 38400 it is the
  interrupt-acknowledge sequence starting to fail; if it was at 9600 it is
  something else entirely and more interesting. **The next bench run must
  capture the six `v9k:` lines per rate**, because that is the only
  instrument that can tell an overrun (`rxlost`) from a ring overflow
  (`rxfull`) from line noise (neither counter moves and the checksum still
  fails).
- **The disk cost is still not measured**, and it is the item that looks
  measured. `wfile n=3 tot=50` is three writes and **one** clock-boundary
  crossing. Inverting §16n's estimator on one crossing gives ~0.17 s per
  write with variance that swamps it; it cannot be distinguished from MAME's
  0.124 s. §16n's caveat — that 0.124 s fixed per `write()` is very slow for
  a real drive and probably the emulator's — stands untested. What *is*
  confirmed is that `V9K_OBUFSIZE = 8192` is live on the machine: `of 8192`
  is the buffer reporting its own size, and 19,808 bytes took the 3 writes
  that implies. The measurement needs `XFLAGS=-dV9K_OBUFSIZE=1024` on a
  32 KB fixture, which turns 4 writes into 32 and finally puts enough
  samples under the half-second quantum.
- **No elapsed time or cps was recorded**, so §16n's projection of ~1,630
  cps at 38400 — the one that says the dead time and not the line rate is
  what bounds this port — is still arithmetic. This is now testable and
  nowhere else can test it.
- **The fixture was 19,808 bytes of markdown, not the 32,768-byte
  all-byte-values fixture** every measurement from §16k on used. So none of
  these numbers is directly comparable to §16k–§16n, and **every byte value
  has still never been round-tripped on hardware** — §16h's `_fmode =
  O_BINARY` fix is confirmed to the extent that a text file survived a round
  trip md5-identical, which is real evidence and not the whole test.
- ~~**No host packet log.**~~ There was one — `run1.pkt`, analysed above.
  What it lacks is a **rate per segment**, which is what stops it answering
  the question above. One `kermit` session per rate, with its own log name,
  fixes that for free.
- **FreeDOS for Victor is untouched**, including the IRQ1 vector question
  (41h here, INT 09h there) that is the most likely thing to break the "one
  binary, two DOSes" claim.

### One consistency check, which is arithmetic and not measurement

20,431 wire bytes carried a 19,808-byte file: 623 bytes of overhead, 3.1%.
A markdown file is mostly LFs and printable text, and under `_fmode =
O_BINARY` an LF is a control character that Kermit prefixes with `#` — so
roughly 500 of that 623 is control-character quoting for ~500 lines, leaving
~123 for framing. At `DRPSIZ = 4000` that is about six data packets plus
S/F/A/Z/B, eleven packets at ~11 bytes of framing each. The numbers
reconcile, which is a weak confirmation that **long packets are live on
hardware** — the host packet log would say so directly.

### Sizes

Unchanged. No source change was made for this section: DGROUP 48,240 of
65,536, image 203,338 needing 217,594 of 396,224, **eleven upstream edits**.

### Measured, and on what

Real Victor 9000, 896 KB, Victor MS-DOS 3.1 from a Pico SASI emulator
serving `victor_kermit.img`, µPD7201 channel A through `/dev/seriala`, 1 m
USB-C to RS-232 to an Apple M4 Mac running C-Kermit. **Six transfers — two
at 9600, two at 19200, two at 38400 — all successful**, validated by round
trip with `diff` and md5 against the original. The `v9k:` counters were read
for one 19,808-byte round trip at 19200 and are quoted above.

---

## 16p. 38400 is not clean, and the counters say which of the three it is

§16o said 38400 was proven to transfer and not proven to be clean, and named
the one run that would settle it. That run has happened — four of them, one
per rate plus a buffer A/B — and **the answer is that the µPD7201 overruns
at 38400 and only at 38400.**

All four transfers were **byte-exact against the fixture**. That is the
point: byte-exactness was never the question.

### The four runs

32,768-byte all-byte-values fixture (`RCVK.DAT` from §16n, so these are
comparable to §16k–§16n), `CKERMITW -l /dev/seriala -b <rate> -r`, one host
`kermit` session per rate with its own packet log.

| run | rate | `V9K_OBUFSIZE` | `rxlost` | `rxfull` | `rxpeak` | `stall256` | NAKs from Victor | `rxbytes` | `wfile` | `txgap` |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 9600 | 8192 | **0** | 0 | 569 | 2 | 1 | 39,438 | 4 / 50 cs | 22 / 50 cs |
| 2 | 19200 | 8192 | **0** | 0 | 1705 | 4 | 1 | 42,484 | 4 / 50 cs | 30 / 150 cs |
| 3 | 38400 | 8192 | **203** | 0 | 2009 | 24 | 4 | 42,757 | 4 / 100 cs | 32 / 400 cs |
| 4 | 38400 | 1024 | **207** | 0 | 2098 | 27 | 6 | 47,698 | 32 / 150 cs | 36 / 450 cs |

Loss rate is **0.47% and 0.43%** of received bytes — the same number twice,
which is what makes it a property rather than an accident.

**The NAK count tracks it.** 1, 1, 4, 6 against `rxlost` of 0, 0, 203, 207.
A NAK is the Victor telling the host a packet failed its checksum, so the
two instruments are measuring the same events from opposite ends of the
wire, and they agree. §16o's three unexplained NAKs are explained: that
transfer was at 38400.

**The losses are bursty, not uniform.** 203 bytes across 4 corrupted packets
is ~50 bytes per event, which at 38400 is ~13 ms of blockage. A handler that
was merely too slow per byte would fail at 38400 completely rather than
lose one byte in 220.

### Two causes ruled out by measurement, and a third by reading

**Not the disk.** That is what run 4 was for. It does **eight times the file
writes** — 32 against 4, confirmed by the `of 1024` in its own output — and
loses the same fraction: 0.43% against 0.47%, 6 NAKs against 4. If a
blocking `write()` were what held IRQ1 off, eight times as many of them
would show. `V9K_OBUFSIZE` is not implicated in the overrun at all.

**Not the ring.** `rxfull = 0` in all four runs and `rxpeak` never exceeded
**2,098 of 4,096**. §16k's ring has close to half its capacity spare at the
worst rate. Growing it would not help and shrinking it to 2,048 would be
tight but survivable — neither is worth a run.

**Not our own critical sections.** Every `V9K_CLI()` in `ckvictor.c` is in
`v9k_ser_progline()`, `v9k_ser_reenable()`, `v9k_ser_flush()`,
`v9k_ser_drain()` or the install/release pair — all setup and teardown.
**The polled transmitter does not disable interrupts** (`v9k_ser_put()`, and
its comment says why: no interrupt is enabled for that direction), and
neither does the ring drain. So the hold-off is not something this port
does deliberately.

That leaves DOS itself, the interrupt-acknowledge sequence under load, or
something in the foreground that is slow without being ours. **Not
diagnosed.**

### The instrument this needs, which does not exist yet

The handler latches its foreground tag at the **peak** (§0e, §16m). What is
wanted now is a tag latched at the **first loss**, plus a count of loss
*events* separate from lost *bytes* — 203 bytes in 4 bursts and 203 bytes in
203 bursts are different defects. That is a handful of stores in a handler
that already runs per received byte, which §16m established costs nothing,
and it would say directly what the foreground was doing when the chip
overran.

One hint to carry into it, offered as a correlation and not a cause:
**`txgap` total rises 50 → 150 → 400 → 450 hundredths** across the four
runs. The port spends roughly eight times as long in transmit gaps at 38400
as at 9600. The transmitter does not mask interrupts, so this is not itself
the mechanism, but whatever it is measuring scales with the failure.

### The disk model from §16n does not survive contact with the drive

This is the other thing run 4 bought, and it retracts a number rather than
an argument.

| | writes | disk total |
|---|---:|---:|
| run 3, 8192 | 4 | 1.00 s |
| run 4, 1024 | 32 | 1.50 s |

§16n fitted MAME at **0.124 s fixed per `write()` plus ~15 µs/byte** and
predicted 32 writes would cost about 4 seconds. **They cost 1.5.** Eight
times the calls for one and a half times the time is not a per-call cost;
on this drive the cost tracks **bytes**, which is the opposite of what the
emulator showed. §16n's caveat — that 0.124 s per call is very slow for a
real drive and probably MAME's — was right, and it was right for the reason
it guessed.

So **`V9K_OBUFSIZE = 8192` bought about half a second per 32 KB on real
hardware, not the four seconds §16n measured.** It costs only far heap and
there is no reason to change it, but it is no longer part of any throughput
argument. Note the sample is small — 2 and 3 crossings of a half-second
clock (§16n, §16o) — but the prediction was 8× and the observation is 1.5×,
which is far outside what two or three samples can explain away.

### What the packet logs add

Segmented per transaction, the way §16o's was:

| rate | segments | in-transfer resends | timeouts | NAKs |
|---|---|---:|---:|---:|
| 9600 | 2 (`RUN1.DAT` twice) | 16 then 2 | 13 then 2 | 1 |
| 19200 | 1 | 4 | 3 | 1 |
| 38400 | 3 (`RUN3.DAT`, a stub, `RUN4.DAT`) | 5, 1, 7 | 1, 1, 1 | 4 and 6 |

**The 9600 log is the one to read carefully, because its raw counts are the
worst of the three and its `rxlost` is zero.** 18 resends and 15 timeouts,
almost all in a first attempt that restarted — startup dead air, the host
reoffering its S packet to a Victor that was not listening yet. Raw
`grep -c '^S-'` over a whole session is not a quality measure; §16o said the
same thing and this is the second session in a row where it would have
misled. Segment the log first.

### Sizes

No source change. DGROUP 48,240 of 65,536, image 203,338, **eleven upstream
edits**. The 1024 build differs from stock in **exactly one byte** — offset
147,167, `0x04` against `0x20`, the high half of the immediate in
`v9k_set_obufsize()` — which is worth recording as the cheapest possible
confirmation that an `XFLAGS` define reached the code it was aimed at.

### Measured, and on what

The §16o bench: real Victor 9000, 896 KB, Victor MS-DOS 3.1 from a Pico SASI
emulator, µPD7201 channel A, 1 m USB-C to RS-232 to an Apple M4 Mac running
C-Kermit. Four receives, one per configuration, the same 32,768-byte
fixture every time, **all four byte-exact by `cmp` after pulling the file
back off the image**.

---

## 16q. The instrument §16p asked for, and what `rxlost` actually counts

§16p ended by naming the one instrument that would turn its result into a
diagnosis: a foreground tag latched at the **first loss**, and a count of
loss **events** as distinct from lost **bytes**. That instrument is now in
the handler. **It has not yet seen a loss** — see the last subsection, which
is the whole caveat.

### Reading `rxlost` correctly, which §16p did not

Before the new counters mean anything, the old one has to be re-read, and
this is a correction to §16p rather than an addition to it.

`v9k_rxlost` is incremented from a **single test of the latched RR1 overrun
bit**, once per entry to the handler. So it counts **interrupts that found
an overrun, not bytes that were lost.** A hold-off long enough to lose fifty
bytes presents the handler with one latched bit and whatever the three-deep
receiver managed to keep, and can therefore raise `rxlost` by as little as
one.

So **§16p's "0.45% of received bytes" is a lower bound, not a measurement**,
and the true loss is at least that and possibly much worse. What is
unambiguous is the direction: each increment means at least one byte went
missing, so `rxlost = 0` at 9600 and 19200 still means exactly what §16p
said it meant, and the 38400 result is if anything stronger than reported.

This also sharpens §16p's own arithmetic. It read 203 as "203 bytes across 4
corrupted packets, so ~50 bytes per event". The 4 comes from the NAK count,
which is solid — but if the 203 were 203 *separate* hold-offs they would be
spread across the whole ~11-packet transfer and would corrupt far more than
4 packets. **The NAK count and `rxlost` are only consistent if the losses
are concentrated**, which is evidence for the burst reading that §16p could
only assume. The new counter tests it directly.

### What was added

Seven statics and a handful of stores, all on the overrun path:

| | |
|---|---|
| `lost evt` | bursts. A loss opens a new one when more than `V9K_LOSTGAP` bytes have arrived cleanly since the previous loss |
| `lost max` | the longest burst, which sizes the worst hold-off |
| `lost tag`/`fd` | §0e's foreground tag latched at the **first** loss — the counterpart of `peaktag`, and the one that names a suspect |
| `lostat`/`lostend` | byte offsets of the first and last loss, which `v9k/tools/mapoffset.py` turns into packets |

**A burst is separated by a gap in the stream, not by consecutive entries to
the handler, and that choice is the point.** Consecutive-entry counting
needs the good-byte path to clear the run counter, which Watcom codes as a
DGROUP reload and a store — about 5 µs of a 260 µs byte at 38400, on the one
path that runs per byte, inside an instrument whose entire purpose is to
find out whether the per-byte path is too slow. **That is §16k's mistake
exactly**, and it was caught by reading the `wdis` output rather than by
thinking about it. Measuring the stream gap instead puts every added
instruction on a path that by measurement runs 203 times in 42,757 bytes,
and it is the better definition anyway: one good byte drained in the middle
of a hold-off should not read as two hold-offs. `wdis` confirms the
non-overrun path is now `test al,20H / je / jmp` and touches no memory.

`V9K_LOSTGAP` is 16 because the two scales are nowhere near each other —
losses inside one hold-off land within a few stream positions, distinct
hold-offs are separated by whole packets — so anything from about 8 to 1000
gives the same answer.

### One semantic correction to `rxbytes`

The BELL that the overrun path substitutes for a lost byte now **increments
`rxbytes`**, which it did not before. `rxbytes` is read as a stream offset
to map onto the host's packet log, and the BELL occupies a position in that
stream, so leaving it out made every offset in a lossy run drift low by the
loss count. That is 203 bytes at 38400 — small, but 38400 is exactly the run
where the offsets matter. **Runs with `rxlost = 0` are unaffected, so every
figure in §16k–§16p stands as printed.**

### Validated three ways, and the third one is the gap

**The arithmetic**, by `v9k/proofs/vburst.c` — the counter update transcribed
byte for byte out of the ISR and replayed on the host against synthetic
patterns with known answers. The two readings §16p could not separate now
come back unmistakably different:

```
203 losses, 4 bursts                   evt=4    max=51    ok
203 losses, spread singly              evt=203  max=1     ok
```

plus a burst broken by good bytes, both sides of the `V9K_LOSTGAP`
boundary, a first loss at offset 0, and a clean transfer. All pass.

**That it costs nothing**, by a full 32,768-byte receive at 9600 under MAME
against the §16n binary's own numbers:

| | §16n, before | §16q, after |
|---|---|---|
| bytes | 32,768 byte-exact | 32,768 **byte-exact** |
| `rxpeak` | 309 of 4096 | **309 of 4096** |
| `wfile` | 4 writes | 4 writes, tot 150 cs |
| cps | 633 | 618 (53 s wall) |

`rxpeak` landing on 309 again is the result worth keeping: it is the
handler's own timing made visible, and the instrument did not move it.
MAME ran at 96.99% of real time for 299 s, so the figures are comparable.

**And the third: the loss path itself has never executed.** MAME cannot
drive this machine above about 9600 (§16n) and the chip does not overrun
below 38400 (§16p), so **no run in the emulator harness can reach the code
that was added.** `v9k/proofs/vburst.c` is what stands in for that, and it
proves the arithmetic only — it says nothing about whether the overrun bit
behaves as assumed. The first real exercise of this code is the next bench
session, and the honest status is *written and reasoned, not observed*.

### Sizes

`ckvictor.c` still compiles with **no warnings**, and the ISR prologue is
still pushes and `mov bp,sp` with no `sub sp,N` — no new stack, hard rule 7
checked by reading `wdis` output as §7 requires. DGROUP 48,240 → **48,256**
(+16), image 203,338 → **203,626**, load 217,866 of 396,224 with 178,358
spare. **Still eleven upstream edits** — this is all in `ckvictor.c`.

---

## 16r. The loss is bursty, and it is not where the peak is

§16q's instrument ran at the bench, at 38400, on the first attempt. **The
answer is unambiguous: the losses are bursts.**

```
v9k: rxlost=322 rxfull=0 rxpeak=1532 of 4096
v9k: peaktag=4 fd=6 stall256=31
v9k: rxbytes=43589 peakat=21487 stallat=1096
v9k: lost evt=5 max=179 tag=0 fd=0
v9k: lostat=183 lostend=21484
v9k: wfile n=4 max=50 at #1 of 8192 tot=100 cs
v9k: txgap n=39 max=50 at #3 tot=550 cs
```

**`evt = 5` against `rxlost = 322`.** The two readings §16q's
`v9k/proofs/vburst.c` was built to separate predict `evt` near 322 with
`max = 1` (a handler too slow per byte) or `evt` in single figures with a
large `max` (something holding the machine off). It is the second, with no
room for argument: five events, longest 179. **The per-byte-cost hypothesis
is dead**, and with it the worry that the handler simply cannot run at
38400.

### Five bursts, five NAKs, and they are the same five packets

The host log for this run (`r38400b.pkt`, 48 packets, 13 resends, 8
timeouts) shows the Victor NAKing **seq 03, 05, 10, 13 and 19** — five, and
no others. `lostat` maps 112 bytes into **seq 03**, the first of them;
`lostend` maps into **seq 19**, the last. **One burst corrupts one packet**,
which is what §16p inferred from NAK counts alone and could not show.

### The offset alignment, which nearly produced a wrong answer

`rxbytes = 43,589` against 43,842 bytes sent: **the Victor's stream starts
253 bytes into the host's.** The host sent the S packet nine times before
the Victor first ACKed (8 timeouts, 9 × 28 = 252 bytes) — startup dead air,
§16p's lesson arriving again — and the Victor received none of it.

`v9k/tools/mapoffset.py` maps a Victor offset onto the host's *sent* stream and
therefore needs that shift applied by hand. Unshifted, `lostat = 183` lands
in the seventh S retransmission and the whole result reads as a startup
artifact with a worthless tag. Shifted, it lands in the first NAKed data
packet. Three things agree on the shift: the byte arithmetic (253 ≈ 252),
and both endpoints landing on the first and last packets the Victor NAKed.
**Check `rxbytes` against the host's byte count before mapping any offset**,
and if they differ, that difference is the shift.

### The tag says it is not one of ours, and the peak was never the loss

**`tag = 0`**: at the first loss the foreground was in upstream code — not
`write()` (1), not the polled transmitter (2), not `read()` (3), not
`v9k_comm_read()` (4). Meanwhile **`peaktag = 4`, `fd = 6`**: the ring's
high-water mark was reached with the foreground in the drain, on the comm
device.

Those are two different places, and separating them is the entire reason
§16q exists. §16m established that `rxpeak` measures our pre-ACK turnaround
during the host's retransmission; this says the *loss* is somewhere else
again. **`rxpeak` was never going to lead anywhere on this defect.**
`peakat = 21,487` sits 3 bytes past `lostend = 21,484`, so the peak rides on
the last burst rather than being an independent stall — consistent with the
peak being a consequence of the resend the burst provoked.

The ring is exonerated for the third time: `rxfull = 0`, `rxpeak` 1,532 of
4,096. `txgap` total is **550 hundredths**, the highest recorded and
continuing §16p's correlation with the failure.

### What this does not yet say, and the next instrument

**How long a burst lasts in bytes.** A burst of 179 losses separated by at
most `V9K_LOSTGAP` clean bytes spans anywhere from ~180 to ~3,000 bytes,
which is the difference between:

- **one blocking hold-off** of roughly 46 ms, and
- **a sustained rate deficit** running the length of a whole long packet.

The five NAKs land on packets where C-Kermit's slow start grows the length —
the same pattern §16l found for the host's timeouts — which leans toward the
second, but leaning is not measuring. A burst spanning ~1,700 bytes inside a
1,759-byte packet would settle it, and so would one spanning 200.

Two cheap additions settle it, both on the rare path:

1. **Per-burst first and last offset** — at minimum for the largest burst,
   which gives its span directly.
2. **Latch `tag` at the largest burst, not the first.** Four of the five
   bursts are currently untagged, and the first is not obviously the
   representative one.

A third would help interpret both: **widen §0e's tag vocabulary**. `tag = 0`
covers everything upstream, which is most of the program. The file *open*
that follows the F packet is a DOS call on the path to the first NAKed
packet and is currently indistinguishable from packet decoding.

**One of the two readings above is retracted by §16s**, on the chip's
behaviour rather than on any measurement: the 7201 latches one overrun and
every handler entry clears it, so a single blocking hold-off — of 46 ms or
of any other length — raises `rxlost` exactly once. `max = 179` is 179
separate overflow episodes and cannot be one hold-off. What is left of the
question is the density, which is what §16s's `sp` measures.

### Measured, and on what

The §16o bench, unchanged: real Victor 9000, 896 KB, Victor MS-DOS 3.1 from
a Pico SASI emulator, µPD7201 channel A, 1 m USB-C to RS-232 to an Apple M4
Mac running C-Kermit. One receive at 38400 of the 32,768-byte all-byte-values
fixture, host log `r38400b.pkt`, Victor counters in `STEP0.OUT`. The file
was **not** checked byte-for-byte this time; §16p established byte-exactness
at this rate over two runs and this run was about the counters.

---

## 16s. The three instruments §16r asked for, built and not yet run

§16r ended with one question and named three additions that would answer
it. All three are in the tree. **None of them has been near a Victor**, and
the reason is §16q's: the loss path only executes when the µPD7201
overruns, the chip only overruns at 38400, and MAME cannot drive this
machine above 9600. What was done instead is what §16q did — the arithmetic
is replayed on the host by `v9k/proofs/vburst.c`, now 17 cases, all passing —
and a 38400 bench run is what turns any of this into a measurement.

### 1. A row per burst, and `sp` is the number

`lostat`/`lostend` bracket the first and last loss of the *whole run*.
Across §16r's five bursts that spanned 21,301 bytes and answered nothing.
The table replaces it for the first `V9K_LOSTBURST` = 8 bursts:

```
v9k: b1 at=21305 end=21484 n=179 sp=179 t=12/9 fd=0
```

`sp` is `end - at`: **the span in received bytes between a burst's first
and last loss**, which is the question §16r could not settle.

**Before reading it, one correction to §16r that follows from the chip
rather than from any measurement.** The 7201 is programmed to interrupt on
every received character (`WR1 = 18h`) and its receive FIFO is three deep,
so the latch sets only when a *fourth* byte arrives before the first is
read, and every handler entry clears it with an Error Reset. **A single
blocking hold-off, however long, therefore raises `rxlost` exactly once**:
the FIFO overflows, the foreground releases, the first entry finds the
latch and clears it, and if the per-byte path can keep up — which §16r
established it can — no later entry finds it again. §16r's `max = 179`
cannot be one hold-off of ~46 ms. It is **179 separate overflow episodes**,
each needing at least four byte times of non-service, so that burst covered
at least 179 × 104 µs ≈ **18.6 ms, or ~716 bytes of the host's stream** —
a floor that was derivable from §16r's own numbers and was not derived.

What `sp` adds is the density inside that stretch. **Compare `sp` against
2`n`, not against `n`**: one overrun interrupt advances `rxbytes` twice,
once for the substituted BELL and once for the byte it then reads, so
back-to-back overruns are two stream positions apart and the floor is
`sp` = 2(`n` − 1).

| | |
|---|---|
| `sp` ≈ 2`n` | consecutive handler entries each found the latch — the receiver lost at least as much as it kept for the length of the burst, and every entry was ≥ 4 byte times after the one before. Repeated short hold-offs, or a per-byte path that cannot catch up once the FIFO is full; **not** one long `CLI` region. |
| `sp` ≫ 2`n` | the episodes are spread through a longer stretch in which the handler mostly kept up. A marginal deficit that tips over occasionally, and the tag pair says whether the foreground moved while it ran. |

For §16r's largest burst the two readings are `sp` ≈ 356 against `sp` of
the order of the packet the burst sat in — an order of magnitude apart,
which is the separation an instrument needs.

**`sp` is a lower bound on the span in the *host's* stream, and it cannot
be an upper one.** `rxbytes` counts bytes stored plus one substituted BELL
per overrun *interrupt* (§16q), and an episode that loses fifty bytes
presents the handler with one latched bit — so `sp` under-reports by
whatever was lost and never substituted, by an amount not knowable from
here. That asymmetry makes the two readings unequal in strength: a row
reporting `sp = 1,700` really did cover at least 1,700 received bytes,
while one reporting `sp = 179` may have covered many more.

### 2. Every burst carries its own tag, so there is nothing to choose

§16r asked for the tag to be latched at the largest burst rather than the
first, because four of its five bursts were untagged and the first is not
obviously representative. The table makes that a non-question: each row
carries its own, and the largest burst is whichever row has the largest
`n`. `lost tag`/`fd` stay as they were — first loss of the run — so §16r's
figures remain comparable.

**Two tags per row, not one.** `t=A/B` is §0e's tag at the burst's first
loss and at its last. The first is the suspect: whatever was running when
the receiver fell behind. The pair says whether the foreground moved while
the burst ran — a burst that opens and closes in the same place is one long
operation, one that opens in a file write and closes upstream is a hold-off
whose effects outlived it.

### 3. §0e's vocabulary, widened three ways

§16r's first loss came back `tag = 0`, "upstream", which is most of the
program. Three widenings, none of them on a per-byte path:

| | |
|---|---|
| **5** | `fopen()` — the receive file is *created* here, between the F packet and the first data packet. `ckufio.c`'s `zopeno()` calls the bare `open()` just before it to ask whether the name is a tty; on a new file that fails with ENOENT, so the cost is in `fopen()`. |
| **6** | `v9k_ser_get()`, the copy out of the ring, split out of **4**. Those were one tag and are not one thing: the loop around it is where the foreground *waits* with interrupts enabled and holds nothing off; the copy is real work with the tail moving under the handler. **4 keeps its old meaning** — somewhere in `v9k_comm_read()` — so §16r's `peaktag = 4` stays readable. |
| **7** | `fclose()` — the flush of the `V9K_OBUFSIZE` buffer and the directory update at the end of a receive. |
| **9–15** | the breadcrumb. The four blocking regions used to store `V9K_TAG_NONE` on the way out and now store `V9K_TAG_UPBASE` (8) plus the tag they are leaving, for the same single store. |

The breadcrumb is the one that widens 0, and it is the cheapest of the
three: **9** is upstream since a file write returned (between packets),
**10** is upstream since the ACK went out, **12** is upstream since a ring
drain returned (packet decoding). Those are different places in the
protocol and `tag = 0` could not tell them apart. **0 now means only
"before any of these has ever run"**, so a `tag = 0` in a future run is
itself a finding rather than a shrug.

`fopen()` and `fclose()` are renamed in `ckvictor.h` by the object-like
macro trick `read()` and `write()` already use, and `ckvictor.c` undefines
both. The wrappers delegate unconditionally — there is no Victor behaviour
in them at all, unlike `read()`/`write()`, which have a device to route
around. **No twelfth upstream edit; still eleven.**

That the rename actually took is checkable without a run and was checked:
`wdis ckufio.obj` has **three references to `v9k_fopen_`/`v9k_fclose_` and
none to the library's `fopen_`/`fclose_`**. Worth doing, because a rename
that silently failed would leave the new tags permanently unset and read as evidence
about where the foreground was.

Neither wrapper times anything, deliberately. The clock's quantum is half a
second (§16n) and both calls happen once per transfer, so a timer there
would report 0 or 50 according to whether it crossed a boundary — §16n's
rule applied before the fact rather than after.

### What it cost

**112 bytes of DGROUP, which is the table**, 8 rows × (4 + 4 + 2 + 2 + 1 +
1). DGROUP 48,256 → **48,368 of 65,536 (73%)**; `ckermitw.exe` 203,626 →
**204,058**; load 218,410 with 177,814 spare. `ckvictor.c` still compiles
with no warnings.

**The per-byte path is byte-for-byte unchanged**, and that was checked in
`wdis` rather than assumed — §16q's rule, and §16k's mistake is what it
exists to prevent. Everything added sits inside `if (rr1 &
V9K_RR1_OVERRUN)`, which by measurement ran 322 times in 43,589 bytes and
does not run at all in a clean transfer. The ISR's frame grew by 2 bytes
for the row index.

### What would falsify it

`v9k/proofs/vburst.c` replays the whole update — burst boundaries, the table,
the tag pair — against patterns with known answers, on the host, in one
`cc`. The case that matters is the pair it was extended for: 179 overruns
back to back report `sp = 356`, and the same 179 spread eight good bytes
apart report `sp = 1,780`, while `evt`, `max` and `lostat` are identical in
both.
**If those two came back the same the addition would be worthless**, which
is the same test §16q applied one level up. Overflow is tested too: 12
bursts into 8 rows keeps bursts 1–8 and leaves `lostevt` at 12, so a table
that ran out is visible rather than silent.

Re-run it after touching the loss path. It is still the only test that code
has, and now more so: the per-burst table cannot be exercised under MAME
either.

### The next run, and the trap to carry into it

38400, the 32,768-byte all-byte-values fixture, `STEP0.BAT`'s redirect.
Read `b1`–`b5` and compare `sp` against `n`.

**Difference `rxbytes` against the host's sent byte count before mapping
any offset.** §16r's stream started 253 bytes into the host's — nine S
retransmissions of startup dead air that the Victor never saw — and
unshifted, its first loss read as a startup artifact. `at=` and `end=` in
the table are the same kind of number and need the same shift.

---

## 16t. The handler was the defect, and 38400 is clean

`rxlost = 0` at 38400, on the real machine, with zero NAKs and zero
retransmissions. The receive path's one live defect — open since §16p, and
narrowed but not diagnosed by §16q, §16r and §16s — was the cost of the
interrupt handler itself. Replacing it with hand-written assembly closed it.

```
v9k: isr=asm
v9k: rxlost=0 rxfull=0 rxpeak=2621 of 4096
v9k: lost evt=0 max=0 tag=0 fd=0
```

Against the C handler in the **same bench session, back to back**:

| | leg Z, C | leg Y, assembly | leg U, 19200 C |
|---|---:|---:|---:|
| `rxlost` | 490 | **0** | 0 |
| NAKs from the Victor | 5 | **0** | 0 |
| resends / timeouts | 6 / 1 | **0 / 0** | 0 / 0 |
| packets | 37 | **18** | 18 |
| longest packet | 2,845 | **3,991** | 3,991 |
| wire bytes | 45,412 | **37,569** | 37,569 |

Leg Y is identical to a clean 19200 run in every protocol measure. Both
files byte-exact against the 32,768-byte all-byte-values fixture.

### Four wrong turns, and each one is a lesson that stands

**The byte time was wrong by a factor of ten, and that is what hid the
answer.** §16k-era comments put a byte at 38400 at **26 µs**; it is
**260 µs**, which is what §11 has said since the beginning and what §16o
confirmed at the bench. Every argument of the form "the handler cannot
possibly be that slow" was reasoning from the wrong budget. Corrected in
four places in `ckvictor.c` and in three other files. **When two figures for
the same quantity exist in one tree, the older one has usually been checked
more.**

**§16r's dichotomy was false and it cost three sessions.** It read `evt = 5,
max = 179` as proof that the loss was not per-byte cost, on the grounds that
a slow handler would lose single bytes throughout. A *marginally* slow one
does not: it falls progressively behind and loses consecutively, which is
exactly `evt = 5, max = 179`. §16s corrected half of this from the chip's
latch behaviour; this is the other half. **"The measurement rules out X"
deserves the same scrutiny as "the measurement shows X".**

**The instrument was inflating the defect it measured.** §16s added a
per-burst table to the overrun path and checked, in `wdis`, that the clean
path was untouched — 67 instructions before and after. That was the wrong
path to check. The overrun branch is rare only while the receiver is keeping
up; **inside a burst it is the per-byte path**. Removing it
(`XFLAGS=-dV9K_LEANLOST`) took `rxlost` from 822 to 483 and the longest
burst from 401 to 204, back to back. §16q's rule was right and was applied
to the wrong branch.

**Two hypotheses died cheaply, and both were worth the run.** The µPD7201 is
two channels behind one IRQ, `CONFIG.SYS` loads `porta.exe` *and*
`portb.exe`, and this handler never touched the other channel — so an
unserviced channel B re-asserting after every EOI would have stolen exactly
every other slot. `norx = 0, othrx = 0` at both rates: every interrupt this
program has ever seen was a real byte on its own channel. Separately, a
**floppy** receive (§16s legs S and T) put 1.5-second writes under the ring
— `wfile tot = 600 cs` against 0 on SASI — and lost nothing at 19200,
because with a window of one the file write happens *before* `ack()` and the
line is idle throughout. Both counters cost nothing and both now answer for
free in every run.

### What the handler was spending its time on

The C handler is 185 instructions with `V9K_LEANLOST`, and 52 of them do no
work:

- **24 stack operations.** Open Watcom's `__interrupt` saves all twelve
  registers and there is no way to ask for fewer. `v9k/probes/vasm.c` establishes
  this three ways: `__interrupt` with a C body and with an `_asm` body emit
  the identical prologue, and **`#pragma aux` cannot be used for an ISR at
  all** — its code is inlined at call sites, so taking its address emits a
  reference to a symbol nothing defines. `msxv90.asm`, the same chip on this
  machine at this rate, saves five.
- **14 `mov ax,DGROUP` / `mov ds,ax` pairs.** `V9K_FARB` builds a fresh far
  pointer per port access, so Watcom rebuilds `DS` for every one and again
  for every counter update between them.

On a 5 MHz 8088 the bottleneck is instruction fetch at ~4 clocks a byte.
Those pairs are 70 bytes ≈ 56 µs; the stack traffic ≈ 67 µs. **~123 µs of a
260 µs budget**, which is why the handler sat right at the margin: fine on
most packets, and once tipped, unable to recover until the line went idle at
the end of one. That is also why every burst ended on a packet boundary.

### `ckvisr.asm`

The port's first assembly, and the only way to own the prologue.

| | C (lean) | assembly |
|---|---:|---:|
| instructions | 185 | **110** |
| stack operations | 24 | **10** |
| segment-register loads | 19 | **2** |

The segment collapse is a gift from the hardware map: the 7201 at `E004:0-3`
and the 8259 at `E000:0-1` are `0xE0040-43` and `0xE0000-01` — 0x40 apart,
**both inside one 64 K segment**. `ES` is loaded once with `E000h` and every
port access is `es`-relative: channel A control `42h`, data `40h`, channel B
`43h`/`41h`, the 8259 command port `0`. The C handler cannot express this
because the two segments are separate constants in separate far pointers.

Otherwise it is a faithful transcription: same order, same tests, same
counters. It does **not** maintain the burst table, for the reason above, so
selecting it implies `V9K_LEANLOST` — otherwise the exit report would print
`b1 at=0 end=0 n=0` from a table nothing writes, which is not obviously
wrong and would be read as a measurement.

`XFLAGS=-dV9K_CISR` puts the C handler back in the vector. It stays compiled
in both builds — file-scope rather than `static`, so an unreferenced
definition is not a warning — as the specification and as the fallback.

### What it cost, and what it changed structurally

DGROUP **48,272** of 65,536 (73%), image 204,404, needs 218,580 with 177,644
spare. Both builds compile with no warnings in `ckvictor.c`.

Two structural changes worth stating plainly. **`ckvictor.c` is no longer the
only non-upstream source file**, and **29 of its variables lost `static`** so
a separate translation unit can reach them; all keep the `v9k_` prefix, which
is what makes that safe across 24 modules. Still **eleven** guarded upstream
edits — the handler never needed one.

### How it was checked before it went to the bench

The overrun branch cannot be reached under MAME at any rate the emulator can
drive, so what could be validated was validated:

- **32,768 bytes at 9600 under MAME, `cmp`-clean**, `rxlost=0 rxfull=0`,
  `rxpeak = 294` against §16n's 309 for the same run. That exercises the
  vector install, the DGROUP base, the shared-`ES` port addressing, the ring
  head/tail and occupancy arithmetic and every counter.
- **The linked `mov ax,DGROUP` immediate**, read out of the executable:
  `29a6`, matching the map. `ckvisr.asm` declares the group as a subset of
  what `wcc` emits, and had the linker taken that as authoritative, `DS`
  would have been wrong by the size of `CONST`+`CONST2` — a silent,
  data-dependent corruption of every variable the handler touches.
- **A build-time check on the ring size**, because an assembler cannot read
  `ckvictor.h` and `V9K_RXMASK` is a literal `0FFFh`.

### The number that moved, and the one that did not

**Bytes lost per overrun was 1.03 in every 38400 run** — §16s legs Q, R and
T, §16t legs V, W, X and Z. That is `T/B − 1` for a service period `T` and a
byte time `B`: the handler was taking almost exactly twice as long as a byte.
It is the tightest description of the defect the instruments ever produced,
and it was only readable once `B` was right.

**`rxpeak` is now 2,621 of 4,096, the highest ever recorded**, with
`peaktag = 12` — upstream, after a ring drain, which is packet decoding.
With retransmissions gone the peak no longer measures pre-ACK turnaround
(§16m); it measures how far decoding falls behind during a 3,991-byte packet
at full rate. **The ring is 64% full at its worst, and that is the next
binding constraint** for longer packets or a window above 1. §16k's sizing
argument was built on retransmission behaviour that no longer happens and
has to be redone from this.

### Measured, and on what

The §16o bench, unchanged. Legs V, W, X, Y, Z at 38400 and U at 19200, SASI;
§16s legs S and T to floppy. Host logs `s16t[UVWXYZ].pkt` and
`s16s[PQRST].pkt`, Victor counters in `s16t*.out` and `s16s*.out`. Every
transfer in every leg was byte-exact against the fixture; what varied was
what it cost to get there.

**Still not captured: elapsed time and cps** — which is a narrower claim
than "not measured". It has been on the operator's screen for every run of
this project, and in no file, because **C-Kermit suppresses its transfer
display when stdout is redirected** and a redirect is how every `v9k:`
counter reaches the image. Two instruments close that: the Victor now
prints `elapsed=<cs> wire=<B/s>`, latched on the first read that returns
data so startup dead air is excluded, and every `.ksc` take-file ends in
`statistics`.

What the counters already bound — line time plus the dead time the Victor
measures, so these are **ceilings** on cps rather than values, `txgap`
covering only ACK-sent to next-read:

| leg | wire bytes | line | measured dead | elapsed ≥ | cps ≤ |
|---|---:|---:|---:|---:|---:|
| **Y** 38400 asm | 37,569 | 9.8 s | 2.0 s | 11.8 s | **2,780** |
| Z 38400 C | 45,412 | 11.8 s | 4.5 s | 16.3 s | 2,010 |
| U 19200 C | 37,569 | 19.6 s | 0.5 s | 20.1 s | 1,630 |

§16n's ~1,630 cps projection for 38400 sits at leg Y's *floor*, not near its
ceiling, so it is probably pessimistic — but that is an inference from
bounds and not a measurement, and it stays that way until one run uses the
instruments above.

---

## 16u. The clock works, and the two instruments measure different intervals

The first run in this project's history to put elapsed time and cps **in a
file**. MAME, Victor MS-DOS 3.1, 9600, a 32,768-byte receive with the
assembly ISR, on the 204,764 build that carries §16t's clock and §16t's
`mdm` sample. Byte-exact against the fixture.

```
v9k: isr=asm
v9k: rxlost=0 rxfull=0 rxpeak=294 of 4096
v9k: wfile n=4 max=50 at #1 of 8192 tot=150 cs
v9k: txgap n=30 max=50 at #18 tot=50 cs
v9k: elapsed=6700 cs wire=590 B/s
v9k: mdm cts=1 dsr=1 (dcd=1 rts=1 dtr=1, see comment)
```

and from the host's `statistics`, which is the other half of the pair:

```
 elapsed time           : 00:00:52 (51.829 sec)
 effective data rate    : 632 cps
```

Three things reproduce exactly, which is what makes the rest of it
readable. **632 cps against §16n's 633** for the same transfer over the same
harness. **`rxpeak = 294` against §16t's 294** for the same run. And the
Victor's own arithmetic checks: 39,575 received bytes × 100 ÷ 6,700
hundredths = 590, which is the `wire=` it printed.

### The two elapsed figures differ by 15.2 seconds and neither is wrong

This is the finding, and it is a reading rule rather than a defect.

- **The Victor's clock spans the whole conversation.** It starts on the
  first read that returns data — which is the host's `kermit -ir`
  autoupload string, *before* the S packet — and closes at release. So it
  contains negotiation, the file, the Z/B exchange and teardown.
- **The host's `statistics` covers the file.** That is what "effective data
  rate" means in C-Kermit and it is the figure to quote as cps.
- **The gap in this run has a name.** One timeout and one retransmission,
  the host waiting for the ACK to sequence 05 (`s16uCM.pkt:14`) — §16l's
  slow-start signature, the packet where C-Kermit doubles the length and
  hands its round-trip estimator line time it did not predict. `set receive
  timeout 20` on the host is what sizes it.

**Quote them as a pair and never interchangeably**: `statistics` is the file
cps, `wire=` is the line rate including headers and resends, and the two
elapsed times behind them are not the same interval. §16t's ceilings table
is unaffected as a *bound* — it was built from line time plus measured dead
time, both of which exclude negotiation — but this run shows that what it
excludes is worth about fifteen seconds at 9600, so its `elapsed ≥` column
is loose in the direction that makes `cps ≤` a weak ceiling rather than a
tight one.

One limitation of `wire=` that only shows up on the other leg: it divides
`rxbytes`, so **it is a receive-leg figure**. On a send leg it would divide
the ACK stream by the whole elapsed time and report a small fraction of what
the line actually carried.

### `cts=1` here is not evidence about the bench cable

MAME's `null_modem` asserts the modem inputs, so this reading says only that
`v9k_ser_mdm()` is reached at the right moment and that its bits decode —
which is worth having before the drive, and is all it is worth. The question
§16t added the line to answer, *does the 1 m USB-C to RS-232 cable carry and
cross RTS/CTS*, is unchanged and still bench-only.

### And the DGROUP immediate moved

`mov ax,DGROUP` links as **`29ad`** in this image against §16t's `29a6`,
matching the map both times. It moved because the image grew by 360 bytes.
That is the argument for §16t's check being **per build** rather than done
once: the number it validates is not a constant.

### Measured, and on what

The §16a MAME harness unchanged — `socat` first, MAME second, host `kermit`
at t+110 s, `-seconds_to_run 300`. `STEPCM.BAT` on the image; take-file
`s16uCM.ksc`; host packet log `s16uCM.pkt`; host statistics `s16uCM.host`;
Victor counters `s16uCM.out`; received file `gotCM.dat`, md5-identical to
`rcvcm.dat`. `wfile n = 4` for 32,768 bytes is §16n's `V9K_OBUFSIZE = 8192`
doing exactly what it was sized to do.

---

## 16v. 1,013 cps at 38400, and the line is no longer the bottleneck

The bench run §16u staged. Two legs on the real Victor, both **byte-exact**,
both `rxlost = 0 rxfull = 0`, and both with elapsed time and cps recorded
for the first time at a rate MAME cannot reach.

| leg | wire B | line | elapsed | host | **cps** | `wire=` | pkts | longest | resend/TO |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **CA 38400** | 37,568 | 9.78 s | 34.00 s | 32.32 s | **1,013** | 1,104 | 18 | 3,991 | 0 / 0 |
| CB 19200 | 43,445 | 22.63 s | 41.00 s | 39.95 s | 820 | 1,059 | 28 | 3,896 | 2 / 1 |
| CM 9600 (§16u, MAME) | 39,575 | 41.22 s | 67.00 s | 51.83 s | 632 | 590 | 24 | 3,585 | 1 / 1 |

**Leg CA is a repeat of §16t's leg Y** — 18 packets, longest 3,991, 37,568
wire bytes against Y's 37,569, zero resends both — so it supplies the
elapsed time leg Y never had. That makes the comparison exact, and the
result is that **both published estimates for 38400 were too high**:

| | cps at 38400 |
|---|---:|
| §16n projection | ~1,630 |
| §16t ceiling for leg Y | ≤ 2,780 |
| **measured, leg CA** | **1,013** |

§16u predicted the ceiling would prove loose. It is loose by **2.7×**.

### Where the 34 seconds went

```
line time (37,568 B at 38400, 8N1)      9.78 s    29%
disk       (wfile tot = 50 cs)          0.50 s     1%
txgap      (ACK-sent to next-read)      2.50 s     7%
unaccounted                            21.20 s    62%
```

**Sixty-two percent of the transfer is foreground CPU**, and `peaktag = 12`
names it: upstream, after a ring drain, which is packet decoding. Per
received byte that is **564 µs — about 2,800 cycles on a 5 MHz 8088 —
against a 260 µs byte time at 38400.**

That is the same shape of defect §16t found in the interrupt handler, one
level up. The ISR was costing about twice a byte time and the chip
overran; the foreground costs about **2.2** byte times and the chip does
not, because the ring absorbs the difference within a packet and the
foreground catches up in the silence after it. `rxpeak = 2,589 of 4,096` is
exactly that backlog: of a 3,991-byte packet the foreground keeps up with
about 1,400 bytes and finishes the rest after the last byte lands.

### The consequence, which is a ceiling and not a projection

Take the line out entirely and 24.2 s remain, so **this port cannot exceed
about 1,353 cps at any line rate** without making the foreground cheaper.
§16n's 1,630 is therefore not merely optimistic — **it is above the ceiling
this run's own non-line time implies.** Doubling 19200 to 38400 bought
**+24%** as measured (820 → 1,013), or **+17%** after correcting leg CB for
the two retransmissions that inflated its wire bytes. Everything above
38400 is worth at most 34% more.

The next lever is therefore the decode path and not the wire, and the
obvious first question is that `victorow.mak` compiles with **`-os`**,
optimise for size. That was the right default while DGROUP and the image
budget were the binding constraints; it has never been measured against
`-ot` on the hot path. Nothing here says it would pay — only that this is
the first time the question has been worth asking.

### RTS/CTS is wired, and that settles the flow-control mechanism

**`cts = 1` on the real cable, in both legs.** This is a genuine read: in
`v9k_ser_mdm()` the only forced bit is `dcd` under `CLOCAL`, while CTS comes
straight off RR0. The host ran `set flow none` and therefore held its RTS
asserted throughout, so a set CTS is the strong-evidence case the §16t
comment described. §16u's `cts = 1` under MAME was worth nothing because
`null_modem` asserts the inputs; this one is worth what it says.

So the front runner wins on availability as well as on cost: **RTS/CTS is
the right default** — two port writes on the path §16t spent a session
stripping, and binary-transparent.

**That does not retire XON/XOFF, and the reason is interoperability rather
than this bench.** A Victor Kermit that talks only to equipment with a
wired, crossed RTS/CTS pair is a Victor Kermit that fails against a good
deal of the hardware it would actually meet — and the far end's wiring is
not something this port can measure or assume. Both mechanisms belong in
it; the bench cable settles the *default*, not the feature set.

The plumbing for both already exists and neither needs an upstream edit,
which is the useful part: `ckutio.c` already translates C-Kermit's `flow`
setting into exactly the termios bits `ckvictor.c`'s `tcsetattr()` receives
— `FLO_XONX` sets `c_iflag |= (IXON|IXOFF)` at `ckutio.c:6617`, `FLO_RTSC`
sets `c_cflag |= CRTSCTS` at `ckutio.c:6252`. `victor/sys/termios.h` defines
all three and already documents the split it implies: `tcflow()` is the
XON/XOFF half, and RTS/CTS is the driver's job whenever `CRTSCTS` is set.
Selection under `NOICP` is the one open piece, since there is no `SET FLOW`
prompt — `dfflow` is `FLO_NONE` at `ckutio.c:1202`, and §16i's priority-0
initializer plus a switch parsed off the DOS command tail is the pattern
that has already solved this shape of problem twice.

### Two smaller results

**The Victor sent a NAK — the first one ever recorded.** Leg CB,
`s16uCB.pkt:20`, `r-08-11-…N` for sequence 8, after the host's timeout and
resend of sequence 7. §16l recorded "only ACKs, never a NAK" across two
receives and that is now contradicted on hardware at 19200. `rxlost = 0`, so
it was **not** a chip overrun; whether it was a checksum failure or the
Victor's own receive timer is not determinable from this log. Leg CA at the
higher rate was perfectly clean, so this is not a rate effect.

**§16u's explanation of the two elapsed figures is confirmed.** The Victor
minus host gap is **1.68 s** on CA and **1.05 s** on CB, against 15.2 s at
9600 — and §16u attributed that 15.2 s to a single startup slow-start
timeout. Leg CA had zero timeouts. With none, the gap is just negotiation
and teardown, which is what the clock was designed to include.

### Measured, and on what

The §16o bench: Pico SASI serving `victor_kermit.img`, channel A, 1 m USB-C
to RS-232, the **204,764** build with the assembly ISR, the clock and the
`mdm` sample. `STEPCA.BAT` at 38400 and `STEPCB.BAT` at 19200, each
`CKERMITW -l /dev/seriala -b <rate> -r`. Host take-files `s16uCA.ksc` /
`s16uCB.ksc`, packet logs `s16uCA.pkt` / `s16uCB.pkt`, statistics
`s16uCA.host` / `s16uCB.host`, Victor counters `s16uCA.out` /
`s16uCB.out`, received files `gotCA.dat` / `gotCB.dat`, both md5-identical
to the 32,768-byte all-byte-values fixture.

**One thing in this section was wrong when first written and is corrected
here.** It said a harness rule had come out of the run — that take-files
must be self-contained, because these two "were hand-edited to name both
before they would run". They would have run as generated. `~/.kermrc`
carries `set line`, `set speed`, `set parity none`, `set carrier-watch off`
and `set flow none`, so the added lines were redundant, not repairs. The
committed take-files are still the ones that ran, and there is no rule.

The mistake is worth a sentence because of *how* it was made. `~/.kermrc`
was read during the same session and seen to contain `set line` — the fact
that would have settled it. Rather than resolve the contradiction between
that and "the file had to be edited", the write-up recorded the question as
"not diagnosed" and built a rule on top of it anyway. **A contradiction
parked as an open question is not neutral; it silently licences whatever is
written next.** §16t's four wrong turns are all versions of this, and this
one had the answer already on screen.

---

## 16w. `-ot` fits, and it is slower

§16v ended by naming the compile flag as the first thing to try against the
foreground decode cost: `victorow.mak` builds with **`-os`**, optimise for
size, chosen when DGROUP and the image were the binding constraints and
never measured against `-ot` for speed. It has now been measured. **The
answer is no**, and the reason is a model this tree already had.

### It fits, which was the real risk

| | `-os` (shipping) | `-ot` |
|---|---:|---:|
| DGROUP | 48,272 (73%) | 48,576 (74%) |
| far code | 170,676 | 186,318 |
| file | 204,764 | 222,178 |
| **needs at load** | 218,988 | **235,090** |
| **smallest Victor** | **384K**, 81,508 spare | **384K**, 65,406 spare |

`-ot` costs 304 bytes of DGROUP and 16,102 bytes of image. Both are
affordable, so the question did not die on the budget -- though **§16x is
the better way to read that 16 K**: it is noise against the 896K bench and
**20% of the 384K floor machine's remaining headroom**, which is the number
that decides how widely this port can run.

### And it is slower

A/B under MAME at 9600, 32,768-byte receive, against §16u's run on the same
fixture, take-file and harness. **The two runs are protocol-identical** — 24
packets, longest 3,585, one timeout, one retransmission, and `rxbytes =
39,575` in both — so nothing but the code differs.

| | `-os` | `-ot` | |
|---|---:|---:|---|
| host elapsed | 51.829 s | 52.432 s | +1.2% |
| host cps | **632** | **624** | −1.3% |
| Victor `elapsed=` | 6,700 cs | 6,800 cs | +1 quantum |
| **`rxpeak`** | **294** | **333** | **+13.3%** |

Both byte-exact. **`rxpeak` is the instrument that matters here**, because
it measures how far decoding falls behind the ring and nothing else — and
it moved 13% the *wrong* way. It is also the reproducible one: `-os` gave
294 in §16t and 294 again in §16u, two runs a session apart, against 333
for `-ot`. The cps difference alone would be near the noise floor (§16n saw
632 and 633 across sessions); the `rxpeak` difference is not.

### §16t's own model predicts this

This is not a surprise once the right paragraph is recalled. §16t costed the
interrupt handler by **instruction fetch on a 5 MHz 8088 at ~4 clocks per
instruction byte** — that is how it turned 70 bytes of segment-load pairs
into 56 µs. An 8088 fetches through a four-byte queue over an **8-bit** bus,
so on this part *code size is execution time*. `-ot` grew far code by
**9.2%** buying inlining and unrolling, and on this CPU that trade runs
backwards.

**So `-os` is not a compromise forced by memory. On an 8088 it is also the
fast choice**, and `victorow.mak`'s comment now says so rather than
justifying it on DGROUP alone.

**The MAME caveat runs in the safe direction**, which is worth stating
because it usually does not. If the emulator under-models prefetch-queue
starvation — the most likely way for it to be unfaithful here — then it
*understates* the penalty on large code, and the real 8088 would be at least
as unkind to `-ot`. A bench run could refine the size of the effect; it is
not needed to settle the sign.

### What this leaves, and one thing nobody has measured

The decode path is upstream code (hard rule 1), so with the compile flag
eliminated there is no cheap lever left on the 21.2 s. Before anything
expensive, note what the packet logs already say about its *input*:

**The fixture is close to worst case for Kermit's prefixing, and no run has
ever used ordinary text.** 32,768 payload bytes go out as **37,568 wire
bytes — 14.7% expansion** — because the fixture contains every byte value
and control and high-bit characters are prefixed. Decode cost is per *wire*
byte, so a plain-ASCII file should present materially fewer of them and cost
less per file byte. That is an inference from the logs and **not a
measurement**; the bound it implies is ~15%, and one run with a text fixture
would turn it into a number. It also means **1,013 cps is a figure for
adversarial data**, which is the right thing to quote but not the whole
picture.

### Measured, and on what

The §16a MAME harness. The `-ot` build went on the image as `CKOT.EXE` with
its own `STEPOT.BAT`, deliberately not overwriting `CKERMITW.EXE`, so the
two `.OUT` files could not be confused — §16t's provenance rule. Take-file
`s16wOT.ksc`, host log `s16wOT.pkt`, statistics `s16wOT.host`, counters
`s16wOT.out`, received file `gotOT.dat`, md5-identical to `rcvot.dat`.
**`CKOT.EXE` and `STEPOT.BAT` were deleted from the image afterwards**: a
known-slower binary sitting next to the bench build is a trap, not a record.
The tree rebuilds bit-identical to the shipping 204,764 image.

---

## 16x. 396,224 was wrong, and the Victor gives twice that

**Retraction.** Every memory statement in this tree since §16a has been
measured against **396,224 bytes (387K)**, described as what "the machine
offers" or "hands out". It is wrong for Victor MS-DOS 3.1 — the real figure
at 896K is **824,784 (805K)** — and it was never a RAM size in the first
place. **A Victor takes RAM in 128K increments from 128K to 896K. No Victor
has ever had 396,224 bytes of anything.**

The question that found it was simply "where did that number come from".

### Where it came from

§16a's table, one INT 21h `AH=4Ah` probe, in a subsection headed *"The
parser build does not load"* whose evidence is `CKERMICP.EXE` failing with
**FreeDOS's** "Allocation of DOS memory failed" — filed inside a section
whose opening line is "Everything below is on **Victor MS-DOS 3.1**". So a
FreeDOS-flavoured measurement sat under an MS-DOS 3.1 heading, and every
later section inherited it without re-asking. It reached nine places in
`PORTING.md`, both of `CLAUDE.md`'s budget passages, `NEXT_SESSION.md`, and
`mzsize.py`'s hard-coded `AVAIL`.

### `v9k/probes/vmem.c`, and it was validated before it was believed

INT 21h only: `AH=4Ah` on our own PSP block with `BX = FFFFh`, whose
failure returns the largest block available, plus `_psp` to show what sits
below. Run under Victor MS-DOS 3.1 with `porta.exe` and `portb.exe` loaded:

| `-ramsize` | total | below (`psp`) | **free block** | above |
|---|---:|---:|---:|---:|
| 896K | 917,504 | 11,584 | **824,784** | 81,136 |
| 256K | 262,144 | 11,584 | **169,424** | 81,136 |

**The overhead above is 81,136 bytes at both sizes, to the byte**, and `psp`
is `02D4` in both. That is the whole model: **Victor MS-DOS 3.1 loads high**,
so a program gets one large low block and

```
free = installed RAM - 92,720
```

It was not believed on arithmetic. The model *predicts* 169,424 free at
256K and therefore that `CKERMITW`, needing 218,988, cannot load there. Both
came true in the same run — the probe printed 169,424 and DOS answered
`CKERMITW -h` with **"Program too big to fit in memory"**. A 512K boot,
run before the probe existed, had already loaded it and printed the full
usage text.

### What each machine gives — two measurements and a model

**Read the middle column before using any other one.** This table was first
published with five derived rows formatted exactly like the two measured
ones, and §16y then contradicted a derived row. Measured and derived are
now marked, and they are not the same kind of fact.

| RAM | free | how | `CKERMITW` needs 218,988 |
|---:|---:|---|---|
| 128K | 38,352 | derived | no — and **DOS did not come up** at this size |
| 256K | 169,424 | **measured** | **no**, and the load failure was observed |
| 384K | 300,496 | derived | fits, +81,508 |
| 512K | 431,568 | derived | loads — observed, but see below |
| 640K | 562,640 | derived | fits |
| 896K | 824,784 | **measured, twice** | **fits**, measured |

The model is `free = installed RAM − 92,720`, and it is better motivated
than a two-point fit usually is, because the overhead **decomposes into two
constants that were separately observed**: 11,584 bytes below the program
(`psp = 02D4`, identical in *every* run this port has ever made, including
the broken ones below) and 81,136 above, identical at 256K and 896K. Neither
scales with RAM, which is what a DOS kernel plus drivers plus a shell should
do. It is still two points.

**MAME cannot model 512K or 640K on `victor9k`, so those rows cannot be
confirmed here.** Both report **759,248 bytes free**, identically, which
implies a machine of 851,968 (832K) — not a size the Victor comes in, and at
640K it is arithmetically impossible: 759,248 free plus 11,584 below is more
than the 655,360 bytes such a machine has. It is not the harness: 896K
reproduces 824,784 through the same script that produced the bad readings,
and 256K produced a correct, self-consistent figure. The option is accepted
— MAME rejects `999K` and names 128/256/512/640/768/896 as valid — and then
not honoured. **128K did not boot DOS far enough to run the probe at all.**

So the honest statement of the floor is: **the requirement is 218,988 and
the only sizes this harness can measure are 256K (too small, confirmed) and
896K.** The 384K floor is the model's answer, not a measurement, and no
machine between those two has been verified. On real hardware only the 896K
bench exists.

### It does not reopen the parser, and the reasons are now different

The obvious inference — §9d and §16a dropped `NOICP` because 429K would not
fit in 387K, and 429K fits in 805K — **is wrong, and I checked instead of
publishing it.** `XFLAGS=-dKEEP_ICP` does not link today, for three reasons
that have nothing to do with RAM:

- **DGROUP overflows by 4,736 bytes.** CLAUDE.md's "with it in, DGROUP
  measures 60,768 — it *fits*" is stale; the tree has grown since, most
  visibly the 4,096-byte ring (§16k) and the 8,192-byte stack (§16j).
- **`ZT=-zt128` fixes DGROUP and breaks `ckvisr.asm`** — two `E2083 cannot
  reference address … from frame` errors, because moving objects into far
  segments moves the receive ring out of the group the assembly ISR reaches
  through `DS`. **This is exactly the hazard §16t flagged**, arriving from
  the direction it did not predict. CLAUDE.md's note that `-zt128` "does not
  help the RAM problem" now understates it: it does not link.
- **`isfloat_` is undefined** — `ckucmd.c` wants it and `NOFLOAT` (§16j)
  compiled it out.

So the parser is a real possibility again on a 640K-or-larger machine, at a
cost that is now three specific engineering problems rather than one
impossible number. Nothing here says it is worth doing.

### The reading rule this replaces

**Quote the requirement, not the spare.** `CKERMITW` needs **218,988 (213K)
at load** and that is the same on every machine; "177,236 spare" was only
ever true of the 896K bench. `mzsize.py` now says so in its header, takes
`-a <bytes>` to check another machine and `-a 0` to print the requirement
alone. §16w's `-ot` experiment is the case in point: 16K of extra image
read as noise against 896K and is 5% of the 384K floor machine's budget.

### Measured, and on what

MAME `victor9k` at `-ramsize 896K` and `-ramsize 256K`, Victor MS-DOS 3.1
from `victor_kermit.img`, `porta.exe` and `portb.exe` from `CONFIG.SYS`,
`STEPMEM.BAT` running `VMEM` then `CKERMITW -h`. The 512K load result is
from an earlier boot of the same `.BAT` before `VMEM` existed. **All three
are emulator figures**; the bench machine is 896K, so no free-memory reading
has been taken on real hardware, and the 384K floor is arithmetic on top of
that.

---

## 16y. The parser builds, loads and runs — and it is not the same as scripting

`KEEP_ICP` links, loads on the Victor and prints a parser's help text. The
three blockers §16x listed are gone, and none of them cost an upstream edit.
**Still eleven**, and the shipping build is bit-identical at 204,764 with
`ckvictor.c` compiling with no warnings.

The decision this was for is the trade §16x made possible and the operator
made: **384K is not a floor worth keeping if the price is the parser.**

### The three fixes, and one of them matters beyond this build

**`isfloat_`** — `ckclib.c:2012` wraps it in `#ifdef CKFLOAT` and §16j's
`NOFLOAT` removes `CKFLOAT`. What decided the replacement was reading the
caller rather than the linker error: the only surviving reference is
`nlookup()` at `ckucmd.c:8158`, and it is a validity *assertion* on a
numeric keyword table that never reads `floatval`. So the predicate is what
is needed, not the value — and a `NOFLOAT` build has no business computing
the value, since upstream's accumulates into the type that does not exist
here. `ckvictor.c` §2b, integer syntax, guarded `#ifndef NOICP` /
`#ifdef NOFLOAT`.

**The ring had to be pinned, and this is the one to remember.** `-zt<n>`
moves data objects of n bytes or more into far segments, and it will move a
4,096-byte ring out of DGROUP — which `ckvisr.asm` reaches through `DS`
loaded from the DGROUP base (§16t). The link fails with

```
E2083: file ckvisr.obj(ckvisr): cannot reference address ... from frame ...
```

`v9k_rxbuf`, `v9k_rxhead` and `v9k_rxtail` are now `__near`. **This is worth
a keyword rather than a note about flags**, because `-zt` is the one lever
that buys DGROUP room, so anyone short of room will reach for it, and the
ring is the object that must not move. It costs nothing when `ZT` is empty.

**DGROUP** then wanted a threshold, and sweeping it is worth doing rather
than taking the first that links — `-zt` also decides how much data lands in
the *file* instead of in `minalloc`:

| `ZT` | DGROUP | image |
|---|---:|---:|
| `-zt128` | 28,880 (44%) | 449,002 |
| `-zt512` | 47,024 (71%) | 439,442 |
| `-zt1024` | 52,032 (79%) | 434,946 |
| **`-zt2048`** | **58,480 (89%)** | **433,830** |
| `-zt4096` | over by 640 | — |

**`-zt2048` beats `-zt128` by 15 KB**, because DGROUP `.bss` costs only
`minalloc` while far data is emitted into the image.

### What it needs, and what actually ran

```
ckicp.exe   file 433,830   image 398,550 + minalloc 30,112 = needs 428,662 (418K)
```

Booted at 896K under MAME. The help text is itself the proof that the parser
is in, and the diff is the whole result:

```
NOICP:    Usage: A:\CKERMITW.EXE[-x arg [-x arg]...[-yyy]..]
KEEP_ICP: Usage: A:\CKICP.EXE [filename] [-x arg [-x arg]...[-yyy]..] [ = text ] ]
```

`[filename]` and `[ = text ]` exist only when there is a parser to consume
them.

### And then it refused every command, which is a real bug

`CKICP PTEST.KSC` came back *"invalid command-line option"*, and so did
`CKICP -C "echo PARSER-ALIVE, exit"`.

**The first draft of this section blamed `NOSPL` for both, and that was
wrong about the more important one.** `-C` is indeed `#ifndef NOSPL`
(`ckuusy.c:2230` and `:3542`). But **`TAKE` is not**: the keyword
(`ckuusr.c:1732`) and its handler (`ckuusr.c:10566`) sit outside every
`NOSPL` region — the enclosing one closes at 9833 — and the
argv[1]-as-command-file path is gated on `#ifndef NOICP`, not `NOSPL`
(`dotake(cmdfil)`, `ckcmai.c:2602`; only the `addmac("\\%0",cmdfil)` line
beside it is `NOSPL`).

**So a `KEEP_ICP` build should be able to run `TAKE` files, and the fact
that it cannot is a defect rather than a configuration consequence.** The
path is `prescan()` at `ckuus4.c:1741`: a non-absolute argument goes to
`findinpath()`, and a miss there is fatal. `PTEST.KSC` was in the FAT root
of the boot drive with no `PATH` set, so "`findinpath()` does not look in
the current directory" is the first suspect — and this port has form there,
since §1d carries an `access()` written specifically to be right about a
FAT root. **Not confirmed.** `KEEP_DEBUG` would show it in one boot.

What `KEEP_ICP` does lose to `NOSPL` is therefore narrower than this section
first claimed: `-C`, and the script language proper. The header comment in
`ckvictor.h` was still asserting "the interactive command parser itself is
NOT removed", written before `NOICP` went in further down the same file, and
that is fixed.

`KEEP_SPL` prices the other half, and §2c made it link:

- DGROUP needs **`-zt512`** — 54,832 of 65,536 (83%); `-zt1024` lands on
  exactly 65,536 and is the wall;
- `ckuus4.c` wanted `chkaes_`, `_inesc` and `_oldesc`, all from `ckucns.c`,
  which this port does not build. **The coupling is worth knowing**:
  `doinput()` — the `INPUT` command — excludes ANSI escape sequences from
  the session log, so it reaches into the CONNECT module's recognizer at
  `ckuus4.c:7309`, under `#ifndef NOLOCAL`. `NOLOCAL` has to stay undefined
  because it is what gives local mode and `SET LINE`, so the guard that
  would remove the reference is one this port cannot use. §2c answers with
  "never in an escape sequence", which is the truth for a build with no
  terminal emulator — and **not** by copying `ckucns.c`'s `oldesc[] = -1`,
  which the OR at 7310 would turn into "drop every character `INPUT` reads
  from the session log".

| build | needs at load | smallest Victor (derived) |
|---|---:|---|
| shipping, `NOICP` | 218,988 (213K) | 384K |
| `KEEP_ICP` | 428,662 (418K) | 512K |
| `KEEP_ICP` + `KEEP_SPL` | **637,714 (622K)** | **768K** |

**Scripting is +209,052 bytes on top of the parser, a further 49%**, and it
moves the floor two RAM steps. Given that `TAKE` is on the cheaper switch,
what that buys is variables, macros, `IF`/`WHILE`, functions and `INPUT` —
not the ability to drive the machine from a file.

### Measured, and on what

MAME `victor9k -ramsize 896K`, Victor MS-DOS 3.1, `CKICP.EXE` and
`STEPICP.BAT` on `victor_kermit.img`. **No transfer has been run with this
build** — it has been proved to load and to parse its own command line, and
nothing more. **And which machines it fits cannot be answered here**: §16x's
own table says MAME misreports 512K and 640K, which are exactly the sizes
this question turns on. The requirement, 428,662, is exact and comes from
the MZ header rather than from an emulator.

---

## 16z. The console and the line shared one termios cache

The first regression pass over the `KEEP_ICP` build, 7 August 2026, run by
the operator on the Victor. **The parser works**: the herald prints, `SHOW`
and `SET` parse, `SET LINE /dev/seriala` opens the port, and `TAKE` runs a
command file from the prompt. Four reported symptoms, and they sort into
three that are the configuration doing what it was told and one defect.

### `TAKE` works, and that is the useful result

`PTEST.KSC` is three lines — `echo`, `show versions`, `exit` — and all three
executed, in order, including the `exit` that ended the session. So §1 item 1
of `NEXT_SESSION.md` is **narrower than it was written**: `TAKE` is not
broken, only the `argv[1]`-as-command-file path through `prescan()`
(`ckuus4.c:1741`) is. That also means a take-file is available *now* as a way
to drive the machine, which is what the item wanted it for.

The file is CRLF and worked, which is worth recording because `_fmode` is
`O_BINARY` here (§16h) and it is not obvious that the trailing CR gets
stripped. Write take-files with CRLF; that is the ending that has been run.

### Three non-defects

- **`show versions` — "?No keywords match"**. `NOFRILLS`. Now fixed, and it
  is the twelfth upstream edit; see §8 item 12 for why the cheap route
  (making `NOFRILLS` conditional on `KEEP_ICP` in `ckvictor.h`, no upstream
  edit) was the wrong one.
- **`connect` — "file-transfer-only"**. Ours, `ckvictor.c` §1e-adjacent, and
  deliberate: neither `ckucon.c` (needs `fork()`) nor `ckucns.c` (needs
  `select()` on a tty) is linked.
- **`show communications` says "unknown" before `SET LINE`, and "Modem
  signals unavailable"**. `shoparc()` prints "unknown" when `ttyfd == -1`
  (`ckuus4.c`), and the default line is `dftty = CTTNAM = "/dev/tty"` with
  `dfloc = 0`, i.e. remote. Both correct.

### The defect: `SET SPEED` did not stick

`ckvictor.c`'s `tcsetattr()` stored `victor_ttcur = *t` **before** the test
that decides whether the descriptor is the communication line, and
`tcgetattr()` ignored its `fd` argument entirely. One cached `struct termios`
for two devices.

`ckutio.c` drives both through that pair. `congm()` seeds `ccold`,
`cccbrk` and `ccraw` with `tcgetattr(0,...)` (`ckutio.c:12375-12377`), and
`concb()`, `conbin()` and `conres()` write them back with `tcsetattr(0,...)`
(`ckutio.c:12566` and neighbours). Every one of those console writes landed
on the line's settings, `c_ospeed` included — and `c_ospeed` is what
`ttgspd()` reads and what `SHOW COMMUNICATIONS` prints. `SET SPEED`
programmed the 8253 divisor correctly and then had its *recorded* speed
overwritten by the next console mode change.

**This is a reporting defect, not a wire defect.** `tcsetattr()` computes
the divisor from `t->c_ospeed` and writes the chip before it returns, so the
line ran at the requested rate; nothing that has ever been transferred is in
question. But `ttgspd()` is also how `ttpkt()` and the transfer display
learn the speed, so it was not harmless.

Fixed by giving the console its own `victor_ttcon` and routing on
`V9K_ISCOMM(fd)`, which is the test `tcsetattr()` already used for whether to
touch the chip. Port file, no upstream edit. Costs 32 bytes of `_DATA`.

**Why it survived to here.** Under `NOICP` the console changes state perhaps
twice in a run and nothing reads the speed back afterwards. The interactive
parser calls `concb()` at the top of every command (`ckuus5.c:2779`) and
again from `popclvl()` at the end of every take-file (`ckuus5.c:5107`) — the
parser did not introduce the bug, it introduced a reader for it. That is the
general point worth keeping: **a switch that turns on a large body of
upstream code is an instrument, and the first thing it measures is the port's
own assumptions about what upstream calls and how often.**

### Not yet confirmed on the machine

The mechanism above is read out of the source, and the arithmetic of it is
certain. What is **not** established is that it is the whole of what the
operator saw: `concb()` returns early when `constate == CON_CB`
(`ckutio.c:12452`), so it writes only on a state transition, and no transition
was proved to fall between the `SET SPEED` and the `SHOW COMMUNICATIONS`.
The report also describes `SET SPEED` printing nothing at all, and
`ckuus3.c:12321-12370` has no silent path — it prints one of `?SET SPEED has
no effect without prior SET LINE`, `?SET SPEED fails, speed is <n>`, or
`<line>, <n> bps`. **Treat "the cache was shared" as proved and "that is why
you saw what you saw" as pending**, until the run below.

### The run that settles it

Staged on `victor_kermit.img`: `CKICPD.EXE` (`KEEP_ICP` + `KEEP_DEBUG`,
531,826 at load, smallest Victor 640K), `SPDTEST.KSC`, `STEPSPD.BAT`.
`tcsetattr()` now logs `tcsetattr console fd` / `tcsetattr line fd` with the
`c_ospeed` it was handed, so the two caches are distinguishable in one log.
Three runs, one boot, no `socat` needed — nothing transfers:

```
STEPSPD                             (both argv[1] runs, logs renamed)
CKICPD -d                           then: take spdtest.ksc
```

`STEPSPD.BAT` runs `CKICPD -d SPDTEST.KSC` and then `CKICPD -d
A:\SPDTEST.KSC`, which is §1 item 1's relative-versus-absolute control, and
keeps both debug logs. The third run is the speed sequence with the parser
reading the same file from the prompt, where it is known to work.

---

## 16aa. The run, and it found a different defect

7 August 2026, real Victor hardware, §16o's bench machine. §16z's run
executed, and **§16z's account of `SET SPEED` was wrong.** Not the mechanism
— the two devices really did share one cached `struct termios`, and that is
fixed and stays fixed. It was wrong about the cause of what the operator saw.
`SET SPEED` never got as far as the cache.

Three findings, one of them mine rather than the port's.

### `SHOW VERSIONS` works on hardware

Edit 12 confirmed on the machine, the whole block, from `C-Kermit 11.0.506`
through `CONNECT Command for Victor 9000: not implemented`. That last line is
worth noting on its own: `shover()` prints `connv`, and `connv` is the string
`ckvictor.c` defines for the stub, so **`SHOW VERSIONS` names the port's own
modules and not just upstream's.**

### The defect: `ttyname()` said everything was the console

`SET LINE /dev/seriala` reported success and left the program in **remote**
mode, which is why `SET SPEED` answered `?SET SPEED has no effect without
prior SET LINE` — correctly, by then. `SPD3.LOG`:

```
priv_opn result=7
ttopen untimed ttyfd[/dev/seriala]=7
ttopen ttyname(ttyfd) xlocal[CON:]=0
ttopen setting ttyfd = 0
...
SET LINE local=0
```

`ckvictor.c`'s `ttyname()` was `return("CON:")` for every descriptor.
`ttopen()` decides locality by opening the device and then asking `ttyname()`
what it *really* is (`ckutio.c:3180`), comparing against `cttnam` — which
`sysinit()` filled in from `ttyname(0)`, i.e. `"CON:"`. So the serial line
identified itself as the controlling terminal, `xlocal` went to 0, and the
`NOFDZERO` block at `ckutio.c:2919` then forced **`ttyfd` to 0** as well.

Fixed by returning `NULL` for anything that is not descriptor 0, 1 or 2,
which is what POSIX says and what `ckutio.c` wants — it treats an empty
answer as "not the console" and leaves `xlocal` at 1.

**Why the port has transferred files for its whole life with this in it.**
The entire test is inside `if (*lcl < 0)` — "caller wants us to figure out if
line is controlling tty". `cmdlin()`'s `-l` passes `lcl = 1`, so the shipping
build *tells* `ttopen()` the answer. Only `SET LINE`, which passes -1, asks.
There has never been a `SET LINE` before this build.

That is the same shape as §16z's own defect and the second instance of it in
two sessions: **a stub written to satisfy one caller, correct for that caller,
wrong for the one the parser introduced.** Both were latent for the port's
whole life and neither was reachable without the parser.

### The console had no line discipline, and upstream assumes one

Separately reported by the operator and confirmed in the source: typing at
the prompt echoes correctly, but pressing Enter returns the cursor to column
0 without advancing a line, so the next output overprints the command.

`cmdnewl()` (`ckucmd.c:7714`) echoes the character that terminated the
command **and nothing else**. On Unix the tty has `ICRNL`, so `gtword()` is
handed an LF and `ONLCR` turns the echo back into CR-LF. This console is raw
in both directions — `c_iflag` and `c_oflag` were 0 — so the CR from
`AH=07h` was echoed as a bare CR. Upstream describes the shape of this
exactly, three lines below, in the comment above its own `BSD44` workaround.

Done in `ckvictor.c`, not `ckucmd.c`, so it costs no upstream edit: the
console's cached termios now carries `ICRNL` and `OPOST|ONLCR`, and
`v9k_read()`/`v9k_write()` honour those two bits for descriptors 0 and 1/2
when `isatty()` agrees. **`conbin()` clears `ICRNL` and `OPOST` out of
`ccraw`** (`ckutio.c:12671`, `:12673`), so binary console mode — which is
what remote-mode packet I/O over fd 0 uses — turns the translation off by
the normal route rather than by a special case here. The `isatty()` test is
what keeps every `.OUT` this project has recorded byte-identical: a
redirected stdout is a file, and a file gets what the program wrote.

### `SPD1`/`SPD2` tested nothing, and the reason is worth writing down

Both runs failed identically:

```
"SPDTEST.KSC" - invalid command-line option, type "A:\CKICPD.EXE -h" for help
```

That is **not** §1 item 1 reproducing. `STEPSPD.BAT` ran `CKICPD -d
SPDTEST.KSC`, and `prescan()`'s filename branch is guarded by
`yargc > 1 && *yargv[1] != '-'` (`ckuus4.c:1610`) — *first* argument, not
*an* argument. With `-d` in front, the branch is skipped and the filename
falls through to `cmdlin()`, which rejects it. Upstream behaviour, correctly
documented in its own comment as "Filename as 1st argument".

So the experiment has to be `CKICPD SPDTEST.KSC -d`: the filename first, and
`-d` after, which `prescan()`'s later argument loop still picks up because
the filename branch advances `yargv` past it. `STEPSPD.BAT` now does that.
**§16y's original failure is still unexplained** — it was `CKICP PTEST.KSC`
with no switches at all, which does take the branch.

### The take-file was mine, and `---` is a continuation

None of the four `show communications` commands ran. `SPD3.LOG`:

```
getnct[echo --- after set line ---<CR><LF>]
getnct[show communications<CR><LF>]
CMD(F)[echo --- after set line --show communications<LF>]
```

A trailing `-` is C-Kermit's line-continuation character, and my `echo`
lines ended in `---`. The parser stripped one and appended the next line, so
each `show communications` became part of the preceding `echo`'s argument.
Rewritten without it. **Nothing about this is a port defect**, and the log
shows the continuation machinery working exactly as designed.

### Sizes after both fixes

| build | needs at load | smallest Victor |
|---|---:|---|
| shipping, `NOICP` | 219,372 (214K) | 384K |
| `KEEP_ICP` | 429,070 (419K) | 512K |
| `KEEP_ICP` + `KEEP_DEBUG` | 532,146 (519K) | 640K |

Still twelve guarded upstream edits — both fixes are in `ckvictor.c`.
`ckvictor.c` still compiles with no warnings.

### What is still unconfirmed

Everything above is either measured in `SPD3.LOG` or read out of upstream
source. **Neither fix has run on the machine.** The re-staged run is the
same three legs; §16z's speed sequence has still never executed, because
`SET LINE` never made the program local.

---

## 16ab. `SET LINE` works, and §1 item 1 is diagnosed

7 August 2026, real hardware, §16aa's binaries. Two of §16aa's three fixes
are confirmed on the machine, one is not, and the run also produced the
answer to the oldest open item in `NEXT_SESSION.md`.

### Confirmed: `ttyname()`, and the whole of §16z behind it

```
ttopen ttyname(ttyfd) xlocal[]=1
SET LINE local=1
tcsetattr line fd[7]=13
```

`ttyfd` stays 7, `xlocal` stays 1, and the `tcsetattr line fd[7]` /
`tcsetattr console fd[0]` pair shows the two termios caches going to the
right places. `SET SPEED 19200` then reached `ttsspd` (`cps=1920`, `s=14`)
and `ttgspd` read **19200** back — the first time in this port's life that a
speed set from the prompt has been read back correctly.

`SET SPEED 38400` is a separate question and is **not** answered here: there
is no `ttsspd cps=3840` in the log at all, so it failed in the parser before
reaching `ttsspd`. Not investigated yet.

### Confirmed: `ICRNL`. Not confirmed: the overprint

The input half works. `gtword` is handed **10**, not 13:

```
gtword c=99
gtword c=10
CMD(P)[take spdtest.ksc]
```

The operator still reports the overprint, so `ICRNL` was not the whole
story, and the write-side theory in §16aa is now doubtful too:

- `cmdnewl()` uses **stdio** `putchar`, not `conoc`. Both of upstream's
  `#define putchar conoc` are guarded — `ckcdeb.h:5118` by `datageneral`,
  `ckucmd.c:250` by `GEMDOS` — so neither is in play, and §16aa's `ONLCR`
  in `v9k_write()` never sees the parser's newline at all. It still fixes
  `conoc()`/`conol()`, which do use `write()`.
- **stdout is in text mode**, so stdio should be translating that `\n`
  itself. `SPD1.OUT` and `SPD2.OUT` — stdout, redirected — end in CRLF,
  while `SPD3.LOG` has bare LF, which is §16h's `_fmode` oracle reading
  exactly as designed: files binary, stdout text.
- `cmdnewl()` ends in `fflush(stdout)`, and so do `cmdecho()` and
  `prompt()`, so the parser is not mixing buffered and unbuffered writes.

So on the evidence the newline is emitted and translated, and something
else produces what is on the screen. **This is open**, and the next thing it
needs is a photograph rather than another hypothesis.

### `CKICP FILE.KSC`: one defect, two symptoms

`SPD1.LOG` ends with the answer, in a line printed by the exit path:

```
doclean DeleteStartupFile[A:\/SPDTEST.KSC]=0
```

`cmdfil` is **`A:\/SPDTEST.KSC`**. `zfnqfp()` built it (`ckufio.c:7500`):

```c
if ((p = zgtdir())) {            /* So get current directory */
    x = ckstrncpy(buf,p,len);
    buf[x++] = '/';
```

unconditionally, and `zgtdir()` returns DOS's `A:\`. This build defines
`UNIX`, so every path primitive above it joins with `/` and tests for `/`;
a trailing `\` is a separator upstream cannot see on the end of a string it
assumes has none. The same line explains `zfnqfp path[A:\/A:\]` in the
startup trace, which has been in every debug log this port has ever written
and which nobody read.

**The second symptom is why the message was so misleading.** `dotake()`
could not open `A:\/SPDTEST.KSC`, so `tlevel` stayed at -1, so `docmdfile()`
never reached `cfilef = 1` (`ckcmai.c:2604`) — and `cfilef` is the *only*
thing that tells `cmdlin()` to skip argv[1] (`ckuusy.c:1597`). So the
command file silently failed to open and the filename was then reported as
an invalid option. `findinpath()` was never the suspect it was written up
as: it found the file.

Fixed by renaming `getcwd()` to a `ckvictor.c` wrapper that returns a
Unix-shaped path — separators forward, no trailing one. At a drive root
that is `A:`, and `A:` + `/` + `NAME` is a path INT 21h accepts; it is
COMMAND.COM that will not take `/`, and nothing here goes through
COMMAND.COM. **No upstream edit — still twelve.**

### The absolute-path leg: guarded upstream edit 13

```
A> CKICPD A:\SPDTEST.KSC -d
?No files match - a:\spdtest.ksc
```

No `SPD2.LOG` at all, which is the tell: `prescan()` exited inside the
filename branch, before its argument loop could process `-d`.
`isabsolute()` (`ckcmai.c:1755`) tests only for a leading `/` under `UNIX`,
so `A:\SPDTEST.KSC` is "relative", goes to `findinpath()`, and
`findinpath()` under `NOSPL` searches an **empty** path list — it hands the
name to `cmifip()` and returns NULL when that fails, which lands on
`doexit(BAD_EXIT,xitsta)`.

Fixed as §8's thirteenth guarded edit, and **the half that was asked for was
not sufficient**: `zfnqfp()` spells the same question `*s == '/'`
(`ckufio.c:7494`), so an `isabsolute()` that says yes just moves the failure
to a qualified name of `A:/A:\SPDTEST.KSC`. Both arms are in, and the
reasoning for each is in §8 item 13.

One consequence worth knowing: with the absolute form now taking
`prescan()`'s `else` branch, `findinpath()` is skipped entirely, which also
sidesteps the second problem that path had — `CMDQ` is `\`, and
`findinpath()` pushes the name through the command parser, where `\S` is a
quoted `S`. The relative form still goes through `findinpath()` and still
has it; it works because `SPDTEST.KSC` contains no backslash.

**Not run on hardware.**

### A stack hazard noticed on the way past

`findinpath()` declares `char takepath[4096]` (`ckuus4.c:1337`) — a 4K
automatic on an 8K stack (rule 7). It is `#ifndef NOICP`, so the shipping
build does not have it, but every `KEEP_ICP` build calls it on the argv[1]
path. Read, not measured; no `-fstack-usage` under Open Watcom.

### `Built for:` now names the machine

`SHOW VERSIONS` said `Built for: Unknown Platform`, and so did both of the
`... for Unknown Platform` lines under it. `ckuver.h` assigns `HERALD` to
`ckxsys` (`ckutio.c:292`) and `ckzsys` (`ckufio.c:308`), picks it from a
chain of platform `#ifdef`s that this port matches none of, and ends with an
`#ifndef HERALD` fallback — so defining it in `ckvictor.h` is upstream's own
mechanism and costs **no edit**. It is now ` Victor 9000 / Sirius 1`: the
machine, not the operating system, because one image runs on both DOSes and
`Running on:` already reports which from `uname()`.

The leading space is required, not cosmetic — two of the three places it
prints are `"%s for%s"` in `shover()`, where the space is the separator, and
every arm of upstream's chain has one.

**`CKCPU` is deliberately left undefined next door.** With it undefined,
`ckuus4.c:13706` falls through to `unm_mch` from `uname()`, which already
answers `Victor` — a runtime answer, and a better one than a compile-time
constant. Defining it would replace a correct value with a guess.

### Sizes

Shipping needs **219,532 (214K)**, smallest Victor 384K. `KEEP_ICP` 429,230
(419K), 512K. `KEEP_ICP` + `KEEP_DEBUG` 532,338 (519K), 640K. `ckvictor.c`
compiles with no warnings; the tree's 19 are unchanged, though edit 13
shifts the reported line numbers in `ckcmai.c` and `ckufio.c`.

---

## 16ac. Two echoers, and the region that swallows `main()`

7 August 2026, real hardware, §16ab's binaries. The path fixes worked and
were not enough; the overprint is explained and fixed; and the actual cause
of `CKICP FILE.KSC` turns out to be §16j's defect, one region wider than
§16j recorded.

### The path fixes worked, measured

```
SPD1:  v9k_getcwd[A:]   ...  DeleteStartupFile[A:/SPDTEST.KSC]
SPD2:  isabsolute[A:]=2 ...  DeleteStartupFile[A:\SPDTEST.KSC]
```

`cmdfil` was `A:\/SPDTEST.KSC` before §16ab and is correct in both forms
now — relative through `getcwd()`, absolute through edit 13. Both legs still
printed "invalid command-line option", which is what led to the next
paragraph.

### The overprint: DOS was echoing, and so were we

The operator's description settled it where three rounds of source reading
had not. Screen before Enter, 28 columns:

```
C-Kermit>show communications
```

after Enter:

```
show communicationsnications
```

Columns 0-18 are `show communications` written a second time; columns 19-27
are the tail of the original line, untouched. So something emitted a **bare
CR** and then the command text was echoed **again** from column 0. Two
echoers and one carriage return — not a missing newline, which is what it
looked like and what §16aa and §16ab both chased.

`read(0,...)` goes to the Watcom runtime, which for a character device in
text mode issues INT 21h **AH=3Fh**, and AH=3Fh on CON is DOS's **cooked**
line input. DOS collects the line, echoes it as it is typed, echoes a bare
CR on Enter, and only then returns the first byte. C-Kermit's parser reads
the rest out of DOS's buffer one byte at a time and `cmdecho()`s each one
itself, from column 0.

Fixed in `ckvictor.c`: `v9k_read()` now honours `ICANON`. With it clear —
which is what `concb()` asks for and what this build starts with — a console
read is one INT 21h **AH=07h**, direct console input without echo, VMIN = 1.
`AH=08h` was rejected on purpose: it checks for Ctrl-C, which goes through
INT 23h and can terminate the program with IRQ1 still vectored into our
handler, and §15's Ctrl-Break question is still open. Byte 3 goes to the
parser instead, which is what raw mode means anyway.

**Untested:** extended keys. On an IBM-compatible, AH=07h returns 0 and the
scan code follows on the next call; whether the Victor's keyboard driver
does the same is not known. Nothing in this build reads arrow keys
(`NORECALL`, `NOSETKEY`), so the byte is passed through rather than guessed
at.

Two earlier conclusions survive and were necessary: `ICRNL` (§16aa) is what
makes the parser see LF rather than CR, and it is still right; `ONLCR` in
`v9k_write()` still fixes `conoc()`/`conol()`, which do use `write()`. What
was wrong was the *diagnosis* — §16aa said the newline was emitted and
something else drew the screen, and half of that was true.

### The real `CKICP FILE.KSC` defect: `#ifndef NOTCPIP` again

`SPD1.LOG` jumps straight from `setprefix=0` (`ckcmai.c:3413`) to
`main argc=3` (`ckcmai.c:3678`), with nothing in between — no
`main argc after prescan()`, no `howcalled`, no `main 2 cfilef`. Counting
`#if` nesting from line 1:

```
3417  #ifndef NOTCPIP
3418  #ifndef NOICP
        ... if (sstelnet || inserver) { ... }
3601  #endif  /* NOTCPIP */    <- actually closes NOICP@3418
        ... environment variables ...
3649    dotakeini(0);                        <- the init file
3657    debug(F111,"main 2 cfilef",...)
3658    if (cmdfil[0]) { docmdfile(0); }     <- the command file
3671  #endif /* NOICP */       <- actually closes NOTCPIP@3417
```

**Everything from 3602 to 3670 is inside `#ifndef NOTCPIP`, and this build
defines `NOTCPIP`.** So `prescan()` finds the command file, qualifies it
into `cmdfil` correctly — and nothing ever runs it. `cfilef` therefore stays
0, and `cfilef` is the only thing that tells `cmdlin()` to skip argv[1]
(`ckuusy.c:1597`), which is why the *filename* is reported as an invalid
option. The init file is gone the same way: `dotakeini()` is two lines
above.

**This is §16j's defect and the same `#ifndef NOTCPIP`.** §16j found it
swallowing `dofast()` and concluded that four capacity symbols had never
reached the wire; it did not follow the region to its end. The rule §16j
wrote — *count nesting from line 1, not from the enclosing function* — is
right, and applying it once more would have found this two months earlier.

**Fixed, as guarded upstream edit 14, and it is the first change this port
has made that is not a no-op elsewhere.** An `#endif` cannot be placed
conditionally — preprocessor nesting balances lexically whatever the macros
say — so there is no `#ifdef VICTOR9K` form of "close this region 70 lines
earlier". Upstream's own `#endif` moved to where its own comment says it
belongs. §8 item 14 has the evidence for that reading rather than the
alternative one (a *missing opener* rather than a drifted closer): the code
inside carries its own `#ifndef NOICP` guards around `dotakeini()` and
`docmdfile()`, which would be redundant otherwise, and `cmdfil`/`cfilef` are
declared unconditionally.

**And the repair tried to change the wire protocol on the way past.**
`dofast()` is in the same region, `CK_FAST` is defined on every UNIX build,
and `dofast()` sets `wslotr = RBSIZ / MAXSP = 8192 / 4000 = 2`. So the first
Victor build with the nesting fixed would have negotiated a **window of
two** — on a port with no interrupt-level flow control, whose 4,096-byte
ring is safe only because a window of one puts at most one packet in flight,
with a 105-byte margin. That is exactly the change `CLAUDE.md` says cannot
ship without a run reaching FINISH and reporting
`rxlost`/`rxfull`/`rxpeak`, and it would have arrived unmeasured as a side
effect of a preprocessor repair. The call is now `#ifndef VICTOR9K`, which
*is* expressible as a guard and is a no-op elsewhere. Remove it when
NEXT_SESSION.md items 4 and 5 — flow control, then windows — are done.

The general lesson is the one to keep: **when a preprocessor repair widens
what a build compiles, enumerate what newly comes in before believing the
repair is inert.** The only reason this was caught is that §16j had already
written down what `dofast()` does.

**Attribution, because it was queried and the answer matters:** the
mis-nesting is upstream's and predates every edit in this tree. At `HEAD`,
before edit 13 existed, the region opened at 3390 and closed at 3644 with
`#endif /* NOICP */` — which is precisely the 3390 → 3644 §16j recorded.
Edit 13's `#ifdef VICTOR9K` / `#else` / `#endif` in `isabsolute()` is
balanced and sits ~1,900 lines above; it moved the line numbers by 27 and
nothing else.

**Not run on hardware.**

### Sizes

Shipping needs **219,772 (214K)**, smallest Victor 384K. `KEEP_ICP` 429,486
(419K), 512K. `KEEP_ICP` + `KEEP_DEBUG` 532,722 (520K), 640K. Nineteen
warnings, the same nineteen; `ckvictor.c` clean. **Fourteen** upstream
edits, thirteen of them guarded no-ops elsewhere.

---

## 16ad. Verified under MAME, and one defect left

7 August 2026, MAME `victor9k -ramsize 896K`, Victor MS-DOS 3.1, no serial
line and no host — nothing here transfers. Run before spending hardware
time, which is what it is for.

### `CKICP FILE.KSC` works, both forms

`STEPSPD.BAT` autobooted; both legs produced 2,826 bytes of the script's own
output where they had produced one line of "invalid command-line option".
That confirms three changes at once — edit 14's `#endif`, edit 13's
`isabsolute()`/`zfnqfp()`, and §16ab's `getcwd()` wrapper — and it is the
first time in this port's life that a command file named on the command line
has run.

Also confirmed in the same output: `Built for:  Victor 9000 / Sirius 1`
(with the two spaces upstream's format produces on every platform), both
module lines carrying `for Victor 9000 / Sirius 1`, `Line: /dev/seriala,
speed: 9600, **mode: local**` after `SET LINE`, and `SET SPEED 19200`
reading back as 19200.

### The console echoes once

A Lua `-autoboot_script` was needed rather than `-autoboot_command`, because
the latter posts its whole string at once and DOS type-aheads it into the
keyboard buffer — which is precisely the thing under test. The script posts
`CKICPD -d` at t=61, `show communications` at t=201, and snapshots at t=235;
`emu.add_machine_frame_notifier` is the hook. The snapshot shows

```
C-Kermit>show communications

Communications Parameters:
 Line: /dev/tty, speed: unknown, mode: remote, modem: none
```

— the typed command once, on the prompt line, output starting on a fresh
line below.

**The control was not run.** The pre-§16ac binary has never been under MAME,
so this says "with the fix the console behaves correctly", not "MAME
reproduces the bug and the fix cures it". The mechanism is DOS's, not the
emulator's — cooked INT 21h AH=3Fh versus raw AH=07h, in the same MS-DOS 3.1
binary either way — so it should transfer, but that is an argument and not a
measurement. Extended keys remain untested on both.

### The `SET SPEED` *command* is broken above 32767 bps

**This is not about 38400 on the wire.** File transfer at 38400 is proven
on hardware three times over (§16o, §16t, §16v — 1,013 cps) and none of it
is in question here. Those runs are `STEPCA.BAT` on the image:

```
CKERMITW -l /dev/seriala -b 38400 -r > STEPCA.OUT
```

`-b` on the command line, in the shipping `NOICP` build, which has no `SET
SPEED` command at all. What follows is a defect in the interactive parser's
keyword table, reachable only from a `KEEP_ICP` build, which has never sent
a byte.

Reproduced under MAME, so it needs no hardware. `SET SPEED 38400` returns to
the prompt in silence and the speed does not change:

```
cmkey numeric calling nlookup =1
nlookup DIRECT HIT[38400]=-2713
cmkey nlookup[38400]=-2713
docmd returns=-2713
```

`ckuus5.c:1262`, in `cmdini()`, building `spdtab` from `ttspdlist()`:

```c
spdtab[j].kwval = (int) ss[i] / 10;
```

The cast binds tighter than the division. `ss[i]` is a `long` 38400,
`(int)38400L` is **-27136** on a 16-bit `int`, and -27136/10 is **-2713**.
`cmkey()` returns that as the match value; `ckuus3.c`'s `SET SPEED` sees
`x < 0` and does `return(x)` with no message, which is exactly the reported
symptom.

Every speed above 32767 is affected on a 16-bit target, and two of them fail
in the worse direction:

| speed | kwval | result |
|---|---:|---|
| 19200 | 1920 | correct |
| 38400 | -2713 | rejected silently |
| 57600 | -793 | rejected silently |
| 76800 | 1126 | **accepted as 11260 bps** |
| 115200 | 4966 | **accepted as 49660 bps** |

**Why no transfer ever hit it, concretely.** `-b` takes a different path —
`ckuusy.c:4164` does `zz = atol(*xargv); i = zz / 10L;`, dividing as a long
— and `STEPCA.BAT` above is how every published 38400 measurement was
driven. The `set speed 38400` that appears in `s16uCA.ksc` is the **Mac
host's**, desktop C-Kermit with a 32-bit `int`, where the truncation cannot
happen. The bug needs `SET SPEED`, which needs the command parser.

**And MAME's ~9600 line-rate ceiling does not bear on this**, which is worth
stating because it is the obvious objection. The run had no `-rs232a` and no
`-bitb`: nothing was connected and no byte moved. In that same run `SET
SPEED 19200` **succeeded** — `nlookup DIRECT HIT[19200]=1920`, `ttsspd
cps=1920`, `ttgspd speed=19200` — while 38400 produced no `ttsspd` call at
all. A ceiling on emulated line rate cannot make one keyword parse and the
other not.

The fix is one token, `(int) (ss[i] / 10)`, and unlike edit 14 it really is
a no-op everywhere else: on a platform with 32-bit `int` the two expressions
compute the same value. Not made yet — it would be edit 15 and §8's rule is
to agree upstream edits rather than make them quietly. Worth reporting
upstream alongside 14.

### Harness notes

- **`-logfile` is not a MAME option here** (v0.287); it exits with status 6
  and runs nothing. `-log` writes `error.log`. One run was lost to this.
- **`-autoboot_command` cannot test interactive echo**, for the reason
  above. `-autoboot_script` with a frame notifier can, and can also
  `manager.machine.video:snapshot()` on demand rather than relying on the
  final frame.
- **`STEPSPD.BAT`'s `REN DEBUG.LOG SPD1.LOG` fails silently if the target
  exists**, leaving a stale log next to a fresh `.OUT`. Delete the previous
  `SPD*` files before a run; §16a's landmine list gains one.
- MAME ran 419 emulated seconds in 419 wall seconds, 99.66% — consistent
  with §16n's 1:1.

---

## 16ae. The block check was the lever, and the prefixing baseline was never what it looked like

Two rounds on the bench, seven receive legs, **every one byte-exact**. The
session set out to measure control-character prefixing and ended up
measuring the block check, because the thing it meant to change was already
in the state it was being changed to.

### The 2×2, and it is the round that counts

Round 2 pinned both variables on the host, which round 1 had not. All four
legs run the same shipping `CKERMITW.EXE`, 38400, the 32,768-byte
all-byte-values fixture:

| leg | `set prefixing` | `set block` | rxbytes | `rxpeak` | `rxfull` | elapsed | µs/wire B | cps |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **PA** | all | 3 | 49,214 | 4,095 | **556** | 41.00 s | 833 | 799 |
| **PC** | cautious | 3 | 44,720 | 4,095 | **640** | 38.00 s | 850 | 862 |
| **BK** | all | 1 | 41,909 | 2,592 | 0 | 29.00 s | 692 | 1,130 |
| **BX** | cautious | 1 | 37,523 | 2,611 | 0 | **26.50 s** | 706 | **1,236** |

cps here is 32,768 ÷ the Victor's `elapsed`, which is §16u's wider interval;
§16v's leg CA on that same clock was **964**, not the 1,013 the host
reported. Compare like with like.

**`BX` is the fastest transfer in the port's history.**

### The prefixing baseline was already `cautious`, and that is a retraction

Every wire-byte count this project has published sits at 37,5xx:

| run | host `prefixing` | wire bytes |
|---|---|---:|
| §16v leg CA | not stated (default) | 37,536 |
| §16ae round 1, leg BK | not stated (default) | 37,534 |
| §16ae round 2, leg **BX** | **cautious**, explicit | 37,523 |
| §16ae round 2, leg **BK** | **all**, explicit | 41,909 |

Three sessions of "default" land on the `cautious` number and nowhere near
the `all` number. **The Mac host has been unprefixing control characters
for the whole life of this port**, and §16w's "14.7% expansion, close to
worst case for Kermit's prefixing" was describing a fixture that had
*already* had the cheap prefixes taken out of it.

So the ~13% this section was built to capture had been banked before the
first line of it was written. The effect is real and replicated —
**−9.1% wire bytes at block 3 and −10.5% at block 1** — it simply has
nowhere left to go. `PX_WIL` (`SET PREFIXING MINIMAL`) is the untried
setting if more is wanted.

### And the change was on the wrong end anyway

`ctlp[]` is read in exactly two places, `bgetpkt()` (`ckcfns.c:1798`) and
`getpkt()` (`ckcfns.c:2904`) — both packet **builders**. Nothing in
`decode()` or `bdecode()` consults it, because a bare control character
decodes as itself. **Unprefixing is a sender-side decision**, which is
precisely what makes it safe to do unilaterally, and it means a receiver's
own setting cannot affect what arrives.

Round 1 proved this by measurement before the code was read: leg BK ran the
Victor at `PX_CAU` and put 37,534 bytes on the wire against §16v CA's
37,536. Two bytes.

The `ckvictor.c` initializer and `V9K_PREFIXING` stay, because they are
correct for the direction they govern — a Victor **sending** a file. That
direction is **unmeasured**; no leg in this section tested it.

> **Correction, 9 August 2026 (desk, after §16ah).** The sentence above rests
> on a premise that was never true: **the initializer was not selecting
> anything.** `main()` reaches `initproto(PROTO_K,...)` at `ckcmai.c:3295`
> before `setprefix(prefixing)` at 3413, and `initproto` copies
> `ptab[protocol].prefix` — statically `PX_ALL` — over whatever an XI record
> put in the variable. So **every leg in this project, in both directions,
> ran the Victor at `PX_ALL`**, whatever `V9K_PREFIXING` said. Established by
> decoding the prefix characters out of the packet logs: a run's `ctlp[]`
> table is recoverable from the wire, and §16ah leg BS prefixed exactly the
> 66 values `setprefix()` sets for `PX_ALL`. Fixed in `ckvictor.c` by writing
> `ptab[PROTO_K].prefix`, which is what `initproto` copies *from*; no
> upstream edit. **Unverified on the wire — `HW_TEST_16ai.md` legs CC/CD.**
>
> **This section's structural conclusion is unaffected and was right for the
> right reason**: unprefixing *is* a sender-side decision, which is exactly
> why leg BK's Victor-side setting could not move a receive leg — and it
> could not have moved one even if it had been taking effect. What is wrong
> is only the inference that the initializer was therefore doing its job in
> the other direction.
>
> **Re-derive this section's per-leg byte counts before quoting them.**
> `v9k/tools/pktstat.py` counts wire bytes and prefixes exactly and reads
> both directions; it did neither when this section was written. Leg BK
> comes back at **41,937 wire bytes with the host at `PX_ALL`** and leg BX at
> 37,551 with the host at `PX_CAU`, which is not how the figures here read.

### The block check costs 142 µs per wire byte, and the model was low by 2.4×

Two independent same-round, same-binary comparisons:

| | block 3 | block 1 | Δ |
|---|---:|---:|---:|
| `prefixing all` (PA→BK) | 833 µs | 692 µs | **−141** |
| `prefixing cautious` (PC→BX) | 850 µs | 706 µs | **−144** |

`chk3()` (`ckcfn2.c:1628`) computes a **16-bit CRC in `long` arithmetic** —
`crcta[]`/`crctb[]` are `long[16]` at `ckcfn2.c:312` — so on a 16-bit CPU
it does roughly double the necessary work, and it is **~17% of the receive
cost**.

The estimate this replaces was **~60 µs**, derived here from §16t's
instruction-fetch model. **That model has now been wrong twice in one
session** and both times in the same direction — it also underpinned the
~2.3% figure that argued against the `chk3()` upstream edit. At 142 µs that
edit is worth nearer **5-6%**, keeps CRC-16, and is one self-contained file.
It is still not made, and §8 still lists sixteen.

Reproducibility is good where the conclusion rests: block-1 legs gave
**719 / 692 / 706 µs** across three runs in two sessions.

### The ring is a live defect, and the block check is why

`rxpeak` sorted by block check, all seven legs:

| block check | `rxpeak` | `rxfull` |
|---|---|---|
| **3** | 2,006 · 4,095 · 4,095 · 4,095 | 0 · 649 · 556 · **640** |
| **1** | 2,630 · 2,592 · 2,611 | 0 · 0 · 0 |

Three of four block-3 legs pinned at the 4,096 ceiling and lost bytes. All
three block-1 legs sat at 2,6xx with a spread of 38. **That is not
run-to-run variance** — the CRC's 142 µs is what pushes the foreground past
what the ring can absorb during a 4,000-byte packet.

Nothing was corrupted: all seven files are md5-identical to the fixture,
because the block check catches the damaged packet and the host resends.
The cost shows up as traffic instead — leg PA needed **49,214 wire bytes to
move 32,768**.

§16t said the ring was the next binding constraint and that §16k's sizing
argument had to be redone. This is that arriving as a measured failure.
`rxfull != 0` is now a defect, not headroom.

### What it does to §16v's ceiling

Leg BX: line time is 37,523 × 260 µs = **9.76 s of 26.50**, so the
foreground is **446 µs per wire byte**, down from §16v's 564. Take the wire
out entirely and the ceiling rises from **~1,353 cps to ~1,957**.

### The uncomfortable part

The entire gain is a **6-bit checksum replacing CRC-16** on a cable that has
never shown a line error. That is a real weakening of error detection, and
the far end's line quality is not something this port can assume. What the
measurement justifies is not shipping block 1 — it is spending the
seventeenth upstream edit on `chk3()`'s arithmetic and keeping the CRC.

### Two lessons, both the same shape as §16t's

**A control that is not stated is not a control.** Round 1 left `prefixing`
at the host's default and then attributed a difference to it. The default
was knowable in one command and nobody ran it, so an entire round was spent
measuring a variable that was already at its target value — and the round-1
write-up drew a confident conclusion ("the mechanism did not engage") that
was half right for the wrong reason.

**An estimate that has never been checked is not evidence, however often it
has been cited.** §16t's fetch model earned its authority by predicting the
ISR saving and the sign of §16w's `-ot` result. It was then used to argue
*against* making a measurement — the ~60 µs figure was the reason the
`chk3()` edit was deprioritised. The measurement, when finally taken, was
2.4× the estimate. §16t's own checklist ends with "cycle-count the actual
ISR on Victor hardware before making more complex optimizations", and the
~200 µs figure this session used for the ISR is from that same unchecked
model.

### Measured, and on what

The §16o bench: Pico SASI serving `victor_kermit.img`, channel A, 1 m USB-C
to RS-232, host device `/dev/tty.usbserial-ABBFKXM1`, the **205,552** build.
Victor side `CKERMITW -l /dev/seriala -b 38400 -r > STEPxx.OUT` from
`STEPPA/PC/BK/BX.BAT`. Host take-files `s16aePA/PC/BK/BX.ksc`, packet logs
`s16ae*.pkt`, counters `STEP*.OUT`, received files `RCVPA/PC/BK/BX.DAT`,
**all four md5-identical** to the 32,768-byte fixture
(`d94d2beda069ef0ef340977e7fd6995d`).

Round 1's three legs are superseded and are not tabulated above beyond the
two figures quoted, because they did not pin `prefixing` and so measured a
Victor-side variable that cannot affect a receive. Their `rxpeak` and
`rxfull` values are still evidence and are included in the ring table.

**The host `statistics` output was not captured in either round.** Every cps
in this section is Victor-clock and therefore conservative; §16v's pair for
leg CA was 34.00 s Victor against 32.32 s host, so leg BX's host figure is
probably near 1,300.

**Round 1's `.BAT` files were written with Unix LF line endings and did not
run**; the legs were driven by hand instead. They are CRLF now.

This adds nothing to §16a's landmine list because **it is already the first
item on it** — "`KTEST.BAT` must have CRLF line endings", recorded when it
cost a MAME run several sections ago. A documented landmine stepped on
again is worth a sentence for the same reason §16t's byte-time was: the
tree knew, and the knowledge was in a section nobody re-read before
generating a file for the same target.

**Superseded 2026-08-09: it is no longer possible to step on this one.**
`.gitattributes` marks `*.BAT` as `text eol=crlf` and the harness `.BAT`
files are now tracked, so a checkout produces CRLF unconditionally and a
leg is reproduced rather than regenerated. That is the right shape of
answer to a lesson recorded twice and learned neither time: **a landmine
documented three times is a landmine that wants a mechanism, not a third
paragraph.**

---

## 16af. The seventeenth edit, and the trade-off §16ae could not resolve

§16ae ended by naming what it had *not* done: "What the measurement
justifies is not shipping block 1 — it is spending the seventeenth upstream
edit on `chk3()`'s arithmetic and keeping the CRC." That edit is now made
(§8, item 17) and measured on the machine. **`rxfull` is 0 at block 3 for
the first time in the port's life, and CRC-16 costs one clock quantum over
a 6-bit checksum where it used to cost 11.5 seconds.**

### The four legs

One MAME leg to prove correctness, three bench legs to measure. All four
**byte-exact** against the 32,768-byte all-byte-values fixture
(`d94d2beda069ef0ef340977e7fd6995d`).

| leg | where | build | prefixing × block | `rxbytes` | `rxpeak` | `rxfull` | pkts | resend/TO | `elapsed=` | cps |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| **AF** | MAME 9600 | edit 17 | default × 3 | 39,575 | 299 | 0 | — | 1 / 1 | 6,450 cs | 508 |
| **AJ** | bench 38400 | **baseline** | cautious × 3 | 44,720 | **4,095** *pinned* | **741** | 26 | 3 / 1 | 3,800 cs | 862 |
| **AG** | bench 38400 | **edit 17** | cautious × 3 | **37,568** | **2,581** | **0** | **18** | **0 / 0** | **2,800 cs** | **1,170** |
| **AH** | bench 38400 | edit 17 | cautious × 1 | 37,534 | 2,585 | 0 | 18 | 0 / 0 | 2,700 cs | 1,214 |

cps is 32,768 ÷ the Victor's `elapsed`, which is §16u's wider interval and
therefore conservative. Compare like with like: §16ae's whole table is on
the same clock.

### The control reproduced its target exactly, and that is what makes AG readable

**AJ came back at 44,720 wire bytes and 3,800 cs — §16ae leg PC's figures,
to the byte and to the quantum.** Not "consistent with"; identical. AJ
exists because §16ae's comparison target was measured in a different
session, and its own closing lesson was that a control which is not stated
is not a control — a control which is not *contemporaneous* is only a
little better. Had AJ come back anywhere else, AG would have been
uninterpretable in absolute terms and the session would have produced only
the AG−AJ difference.

The one figure that did not reproduce is `rxfull` itself: 741 today against
PC's 640. That is the expected shape — §16q established `rxlost`/`rxfull`
count *events on a lossy path*, which is the least reproducible thing in
the counter set, and everything that measures work rather than damage
matched exactly.

### The defect is closed

`rxfull` **741 → 0**. `rxpeak` came off the 4,096 ceiling to **2,581** —
*below* all three of §16ae's block-1 legs (2,592 / 2,611 / 2,630), so with
edit 17 the foreground keeps up with a 4,000-byte packet at 38400 better
than a **6-bit checksum** did without it.

A pinned `rxpeak` of 4,095 is a ceiling and not a measurement — it means
"at least this much" and cannot be differenced, which is why §16ae could
only bound the effect and not size it.

The resend traffic follows the ring: **26 packets and 3 retransmissions
become 18 and zero**, one timeout becomes none, and 44,720 wire bytes
become 37,568 — the same 37,568 §16v leg CA moved. That is **16% fewer
bytes on the wire**, and it is worth more than the CPU saving because it is
work that was never useful.

**38.00 s → 28.00 s. 862 → 1,170 cps. +35.7%, on the block check the port
actually ships.**

### The trade-off §16ae called uncomfortable is gone

That section's closing worry was that its entire gain came from replacing
CRC-16 with a 6-bit checksum on a cable that has never shown a line error.
AG and AH settle the cost of not doing that, and they are the cleanest pair
in the port's history — same binary, same session, same cable, **18
packets and zero retransmissions in both**, wire bytes within 34 of each
other, one variable:

| block check, one binary, one session | `elapsed=` | µs/wire byte |
|---|---:|---:|
| CRC-16 (AG) | 28.00 s | 745 |
| 6-bit checksum (AH) | 27.00 s | 719 |
| **cost of keeping CRC-16** | **1.00 s — one clock quantum** | **26** |

Before edit 17 that gap was 11.50 s and §16ae's 142 µs. **Edit 17 removed
116 of the 142, 82% of the block check's measured cost, and CRC-16 now
costs at most 3.7% instead of 43%.** There is no longer a speed argument
for shipping a weaker block check, which is the outcome §16ae asked for
rather than the one it measured.

### AH is a null result and that is the pass

Edit 17 has no mechanism to change the block-1 path: it adds a table a
block-1 transfer never reads and rewrites a function it never calls. AH
therefore had to reproduce §16ae leg BX, and did — 2,700 cs against 2,650
(one quantum), `rxpeak` 2,585 against 2,611 (inside the 38-count spread of
BX/BK/round-1), `rxbytes` 37,534 against 37,523.

This is the leg that makes AG **attributable**. Any binary differs from any
other in layout, and §16w established that this machine is unusually
sensitive to code *size* — `-ot` grew far code 9.2% and cost 13% of
`rxpeak`. A block-1 floor that had moved would have meant the rebuild
itself changed something and AG's delta was measuring layout. **Spend a leg
on the result that is supposed to be nothing**; without it the headline is
an assertion.

### What §16ae's 142 µs actually was, and a correction to a correction

The session that made this edit predicted the saving twice and was wrong
both times, in opposite directions. Worth recording, because the
instruments involved are ones this tree keeps reaching for.

- **The 8088 cycle count said 603 → 81, i.e. ~104 µs/wire byte at 5 MHz.**
  MAME leg AF measured 54. The instruction-cycle model over-predicts, the
  same way §16t's instruction-*fetch* model did — and this is now the
  fourth time a hand-costed 8088 figure in this tree has come out
  optimistic. Treat both models as ordering arguments, never as magnitudes.
- **Then, from AF, this session asserted that §16ae's 142 µs "bundles
  chk3's cost with the overflow recovery" and put the true figure near 63.**
  Directionally right, quantitatively too aggressive. The bench says the
  arithmetic is worth ~80 µs/wire byte (26 remaining + ~54 removed), with
  the balance of the 142 being the overflow the arithmetic *caused*. §16ae
  measured block 3's total penalty correctly; it simply was not all CRC.

The honest decomposition, then: **block 3 on the baseline cost 142 µs/wire
byte over block 1, of which roughly 80 was CRC arithmetic and roughly 60
was ring overflow and resend recovery that the arithmetic triggered.** Edit
17 removes the arithmetic, which removes the overflow, which is why the
measured gain (116 µs) exceeds the arithmetic saving (54–80 µs).

**And a clean baseline block-3 figure does not exist and cannot be
measured.** The baseline cannot run block 3 cleanly at 38400 — that is the
defect. Every block-3 leg the port has ever run on the baseline overflowed.

### Where the ceiling is now

Leg AG: line time is 37,568 × 260 µs = **9.77 s of 28.00**, so the
foreground is **485 µs per wire byte**, down from §16v's 564 and §16ae's
446-at-block-1. Take the wire out entirely and the ceiling is **~1,797
cps**; AH's is ~1,900.

**§16t's "the next binding constraint is the ring" is closed.** `rxpeak` is
2,581 of 4,096 — 63%, with 1,515 bytes of margin — and §16k's sizing
argument no longer needs redoing, because nothing is pressing on it.
`peaktag = 12` still names foreground packet decoding, which is where the
next lever is if anyone wants one: `ttinl()`'s per-byte loop at ~133 µs and
the ISR at ~172 are the two largest remaining items, and **only the second
is ours**.

### One free item found on the way and not taken

`ttinl()`'s inner loop contains `errno = 0;`, and Open Watcom's `errno.h`
defines `errno` as `(*__get_errno_ptr())` — so the shipping build makes a
**far call per received byte**, ~25 µs. It needs no upstream edit:
`ckvictor.h` is force-included, so `#define errno (*v9k_errnop)` ahead of
`errno.h` takes that header's `#else` branch, which then declares the
pointer itself. (The plain `extern int errno` route does not link — the
symbol is not in `clibl.lib`.) Unmeasured, and left for whoever wants ~3%.

### Measured, and on what

The §16o bench: Pico SASI serving `victor_kermit.img`, channel A, 1 m USB-C
to RS-232, host device `/dev/tty.usbserial-ABBFKXM1`. Victor side
`CKERMITW -l /dev/seriala -b 38400 -r > STEPxx.OUT` from
`STEPAG/AH/AJ.BAT`; leg AJ runs `CKBASE.EXE`, the 205,552-byte baseline,
staged alongside so the control is a *binary* difference and not a rebuild.
Edit-17 build is 205,968 bytes, needs **220,160 (215K)** at load, DGROUP
48,816 of 65,536 (74%). Take-files `s16afAG/AH/AJ.ksc`, packet logs
`s16af*.pkt`, counters `s16af*.out`, received files `gotAG/AH/AJ.dat`, all
md5-identical to the fixture. Run sheet: `HW_TEST_16af.md`.

Leg AF is the §16a MAME harness at 9600, mirroring §16u leg CM: take-file
`s16afAF.ksc`, `STEPAF.BAT`, counters `s16afAF.out`, host statistics
`s16afAF.host`, received `gotAF.dat`. **`rxbytes = 39,575` in both AF and
CM, with the same 1 timeout and 1 retransmission**, so the two are
protocol-identical and the only difference is the code — §16w's A/B design.
Host clock 51.829 s → 49.689 s, 632 → 659 cps.

**The host `statistics` was captured for AF and not for AG/AH/AJ**, so
every 38400 figure here is Victor-clock. §16v's pair for leg CA was 34.00 s
Victor against 32.32 s host, which puts AG's host figure near 26.3 s and
~1,245 cps.

**The reason that gap exists is a handoff failure, not a harness one, and
the first write-up of this section got it wrong.** It said the run sheet had
buried the redirect — true, `HW_TEST_16af.md` asked for it once as
punctuation on the end of a command line, with no mention in its artefact
table or its "Reading the result" section. But that only matters to someone
who is *following* the document, and **the document was never handed over as
one.** It was produced and then referred to in passing as "the run sheet",
which reads as a note-to-self about work done, not as an instruction set to
execute. The operator ran the three legs from the leg table and had no
reason to think the file governed anything else.

**A document is not an instruction until someone is told to follow it.**
Both defects are now fixed — the run sheet lists three artefacts per leg and
says why each is wanted, and it is named as the thing to work from — but the
ordering matters for the next time: the internal organisation of a procedure
is worth nothing if the handoff does not establish that there is a procedure.
§16ae lost the same figure, and its own note blamed capture rather than
asking why capture was optional.

---

## 16ag. Two free items, and only one of them was free

§16af's closing paragraph listed one item it had found and not taken — the
`errno` far call in `ttinl()`'s per-byte loop — and `NEXT_SESSION.md` added a
second, `NOCKXXCHAR`, whose size half had been measured and whose throughput
half had not. Neither costs an upstream edit. **Both are now built and both
are measured, and the measurement disagreed with the prediction about which
one was worth having.** `NOCKXXCHAR` ships. The `errno` change does not.

Still **seventeen** upstream edits; only `ckvictor.h` and `ckvictor.c` moved.

### What the two changes are

**`NOCKXXCHAR`.** `ckcdeb.h:3390` turns `CKXXCHAR` on for any build defining
`UNIX`, and this one does. It backs `SET SEND DOUBLE-CHARACTER` and `SET
RECEIVE IGNORE-CHARACTER`, and it puts a test at the top of `ttinl()`'s
per-byte loop. The only writers of `ignflag`/`dblflag`/`dblt` are `ckuus7.c`
(the SET commands) and `ckuus3.c` (SHOW), **both inside `#ifndef NOICP`**, so
in a shipping build the only write that ever happens is the initialiser to 0
at `ckcfn3.c:292-293` and the branch can never be taken. `wdis` confirms
`ignflag` and `dblt` leave `ckutio.obj` entirely.

**The `errno` pointer.** Open Watcom's `errno.h` defines `errno` as
`(*__get_errno_ptr())`, so `errno = 0;` at `ckutio.c:11097` — inside the same
per-byte loop — was a **far call per received byte**. `ckvictor.h` is force
included ahead of every source file, so `#define errno (*v9k_errnop)` there
makes `errno.h` take its `#else` branch, and that branch's
`_WCRTDATA extern int errno;` **expands to a correct declaration of the
pointer itself**. Verified by preprocessing: `ckutio.c` line 4582 reads
`__declspec(__watcall) extern int (*v9k_errnop);`. The same is true of the
three `extern int errno;` lines in `ckcdeb.h`, which is what makes this safe
as a build-wide macro rather than a local dodge. 27 far calls leave
`ckutio.obj`; the per-byte sequence becomes `lds bx,ss:_v9k_errnop` /
`mov word ptr [bx],0`.

Use the library's pointer and not a private `int`: the runtime sets the real
errno through that accessor, so a separate variable would silently disconnect
every library failure from every test of `errno`. (`extern int errno` does
not link in any case — the symbol is not in `clibl.lib`, only the accessor
is exported.)

### Seven legs, six of them protocol-identical

The §16a MAME harness at 9600, one 32,768-byte receive per leg, all seven
**byte-exact** against `d94d2beda069ef0ef340977e7fd6995d` and all seven with
`rxlost = 0 rxfull = 0`. Host `statistics` captured for every one — which is
§16af's handoff lesson applied rather than restated.

| leg | build | image | TO/RS | `rxbytes` | `rxpeak` | Victor | **host** | cps |
|---|---|---:|---|---:|---:|---:|---:|---:|
| **AK** | shipping edit-17 (control) | 205,968 | 1/1 | 39,575 | 299 | 6,550 cs | **49.819 s** | 657 |
| **AR** | control, repeated | 205,968 | 1/1 | 39,575 | 299 | 6,650 cs | **50.140 s** | 653 |
| AM | control, *off-shape* | 205,968 | **0/0** | **37,568** | **17** | 6,400 cs | 48.046 s | 682 |
| **AP** | + `NOCKXXCHAR` | 205,256 | 1/1 | 39,575 | 299 | 6,450 cs | **48.807 s** | 671 |
| **AQ** | + `NOCKXXCHAR`, repeated | 205,256 | 1/1 | 39,575 | 299 | 6,500 cs | **48.806 s** | 671 |
| AL | + `NOCKXXCHAR` + `errno` | 204,888 | 1/1 | 39,575 | 299 | 6,450 cs | 48.902 s | 670 |
| AN | + both, repeated | 204,888 | 1/1 | 39,575 | 299 | 6,500 cs | 48.907 s | 670 |

Leg AK reproduced §16af leg AF — a different session, the same binary —
at 49.819 s against 49.689 and `rxbytes`/`rxpeak` to the digit, which is
what makes the session readable at all.

**The packet logs of AK, AP, AQ, AL, AN and AR are identical apart from the
filename and the timestamp in the attribute packet**, same length to the
byte. This is §16w's A/B design met exactly: the protocol did the same work
in every leg, so the differences are code.

### `NOCKXXCHAR`: −1.0 s, and it ships

**49.819 / 50.140 → 48.807 / 48.806.** Against a control-arm mean near
49.88 that is **−1.07 s, −2.1%**, and 657/653 → 671 cps. The treatment arm
reproduced **to 1 ms**.

The size half repays §16af's CRC table to the byte, which is the neat part:

| | before | after | Δ |
|---|---:|---:|---:|
| DGROUP | 48,816 (74%) | **48,304 (73%)** | −512 |
| image | 205,968 | 205,212 | −756 |
| needs at load | 220,160 (215K) | **219,452 (214K)** | −708 |

−512 is exactly `short dblt[256]`. Warnings unchanged at 19, all
pre-existing upstream; `ckvictor.c` still compiles with none.

**The flag is wrapped in `#ifndef KEEP_ICP`, and the first version of this
section got that backwards.** It shipped the define unconditionally, on the
reasoning that "the parser build is an instrument, and an instrument whose
packet path differs from the shipping build's is measuring the wrong
program." **That premise was invented.** `ckvictor.h` has said since the
port began that `NOICP` removes *"the one thing this port most wants
back"*: the parser is a feature intended to ship, and §16y and §16z–§16ad
built and regression-tested it on the machine. The sentence that misled was
§16ab's — *"a switch that turns on a large body of upstream code is an
instrument, and the first thing it measures is the port's own stubs"* —
which says what enabling the parser **revealed**, not what it is **for**.

Guarded, the saving lands where the commands are dead and the commands
survive where they are live:

| | shipping | `KEEP_ICP` |
|---|---:|---:|
| DGROUP | 48,304 (73%) | 59,024 (90%) |
| needs at load | 219,452 (214K) | 429,890 (419K) |
| smallest Victor | **384K** | **512K** |
| warnings | 19 | 26, unchanged by the guard |

Removing the two commands from the parser build would have bought it 1,764
bytes — 3,442 bytes of 512K margin instead of 1,678 — and **would not have
moved the smallest machine that can load it.** By §16x's rule that is the
figure which governs, so the commands cost margin and not reach, and two
documented commands are worth more than margin that changes nothing.

**What is not established is the mechanism.** The change removes two
instructions from the per-byte loop *and* 512 bytes from DGROUP *and* 756
bytes of code, and §16w established that this machine is sensitive to code
layout. Nothing here separates those. The direction is not in doubt on any
reading; the attribution is.

### The `errno` pointer: +98 ms, and it does not ship

**48.807 / 48.806 → 48.902 / 48.907.** The change is **98 ms slower**,
twenty times the spread of either arm, on the leg it was supposed to win by
about a second.

This is the fifth hand-costed 8088 prediction in this tree to be wrong and
**the first to be wrong in sign**. The four before it — §16t's
instruction-fetch model, §16af's cycle count, and two others §16af lists —
were all optimistic about magnitude. This one predicted ~0.8 s of saving
from removing a far call per byte and got a small loss. §16af's rule was
"treat both models as ordering arguments, never as magnitudes"; **that rule
was too weak, and the correction is that they are not reliable for ordering
either.**

Two readings survive and this harness cannot separate them:

- **MAME is not cycle-accurate.** It is the caveat §16n and §16v have both
  carried, and a change whose entire mechanism is instruction cost is
  precisely the thing an emulator that approximates instruction cost is
  least qualified to judge. A far call is few instructions doing a lot of
  bus work; `lds` is one instruction reading four bytes. Which of those an
  emulator charges more for is a property of the emulator.
- **Layout.** §16w measured this machine losing 13% of `rxpeak` to a 9.2%
  growth in far code. AP and AL differ by 368 bytes and there is no null
  leg available — a change that necessarily alters code size cannot have
  one, which is the limit of §16af leg AH's method rather than an oversight
  here.

**It is off by default and the code stays.** `XFLAGS=-dV9K_FAST_ERRNO`
turns it on. Everything in `ckvictor.c` §1f stays compiled either way, so
the flag is a one-line rebuild and **the shipping binary is byte-identical
(md5 `433148fa…`) to the one legs AP and AQ measured** — ship what was
measured, not a near relative of it.

The bench is what would settle it, and the reason is structural: **at 9600
the foreground has 555 µs of slack per byte** — 1,040 µs of byte time
against §16af's 485 µs of foreground cost — so a per-byte foreground saving
has room to hide in. At 38400 the byte time is 260 µs and the foreground is
*behind*, which is why `rxpeak` climbs to 2,581 there and sits at 299 here.
**A per-byte cost that is absorbed by slack at 9600 is on the critical path
at 38400**, and this port has no instrument at 38400 but the machine itself.

That argument cuts at `NOCKXXCHAR` too, and it should be said plainly: if
slack hides per-byte savings at 9600, then `NOCKXXCHAR`'s −1.07 s is
evidence that its gain is **not** coming from the two instructions it
removes from the loop. The most likely candidate is the 512 bytes of
DGROUP and 756 of code. That does not change the decision — the change is
free and good on every axis — but it does mean **the 2.1% should not be
quoted as "the per-byte test cost 2.1%"**, and it is a second reason the
`errno` result is less surprising than it first looks.

### The one leg that did not run the same protocol, and what it confirmed

Leg AM was meant to be the control repeated and came back with **zero
timeouts and zero retransmissions**, 37,568 wire bytes instead of 39,575.
It is therefore not a second AK sample and is excluded from every
comparison above — that is §16w's rule doing its job rather than a wasted
run, and AR was run to replace it.

It paid for itself anyway. **`rxpeak` was 17 of 4,096, against 299 in every
leg that retransmitted.** §16m concluded that the peak measures the host's
retransmission — with a window of one, the only moment the host transmits
without waiting for our ACK — and predicted therefore that a leg with no
retransmission would have essentially no peak. **AM is that leg and the
peak collapsed by 17×.** §16m's finding was reached by instrumenting the
peak and mapping it onto the packet log; this is the first time it has been
confirmed by the *absence* of the mechanism.

### The control arm was the noisy one, which is backwards

AK and AR are the same binary and differ by **321 ms**; AP/AQ differ by 1 ms
and AL/AN by 5 ms. Three legs of one arm spanning 451 ms while two other
arms hold to single-digit milliseconds is not what a simple noise model
predicts, and there is no explanation for it here. It does not threaten
either result — the `NOCKXXCHAR` difference is 1.07 s against that 451 ms,
and the `errno` comparison is between the two *tight* arms and never touches
the control — but **a repeat that lands 321 ms away is the reason arms get
two legs**, and the next session should not assume 5 ms is this harness's
resolution.

### Measured, and on what

§16a MAME harness: `socat` first, MAME second, host `kermit` at t+110 s,
`-seconds_to_run 300`, `-ramsize 896K`. Take-files `s16agAK/AM/AN/AP/AQ/AR/
AL.ksc`; `STEPAK/AM/AN/AP/AQ/AR/AL.BAT` on the image; host packet logs
`s16ag*.pkt`, host statistics `s16ag*.host`, Victor counters `s16ag*.out`,
received files `gotAK.dat` … `gotAR.dat`, every one md5-identical to the
fixture. Control binary is the on-image `CKERMITW.EXE` at 205,968 bytes
(§16af's edit-17 build); `CKAP.EXE` is `NOCKXXCHAR` only and `CKAL.EXE` is
both changes.

**Shipping build after this section:** DGROUP **48,320 of 65,536 (73%)**,
image **205,256**, **needs 219,480 (214K)** at load, smallest Victor still
384K. (**§16ah revises this**: removing the `errno` code took the build to
48,304 / 205,212 / 219,452.) 19 warnings, all pre-existing upstream, `ckvictor.c` clean. Both
standing proofs re-run and passing.

---

## 16ah. The bench answers three questions, and disagrees with §16af about the fourth

Seven legs at 38400 on the real Victor, `HW_TEST_16ag.md` run as written.
**All seven byte-exact**, `rxlost = 0` and `rxfull = 0` in every one. One
upstream edit is closed, one change is removed, and **§16af's headline figure
for the cost of CRC-16 is superseded — it was low by a factor of 2.6 to 3.9,
and the reason is that it rested on a single pair.**

| leg | binary | block | TO/RS | `rxbytes` | `rxpeak` | Victor | **host** | cps |
|---|---|---:|---|---:|---:|---:|---:|---:|
| **BS** | shipping | 3 | 0/0 | 216 *(ACKs)* | 52 | 2,450 cs | **23.633 s** | **1,386** |
| BB | shipping | **1** | 0/0 | 37,523 | 2,600 | 2,650 cs | **25.475 s** | 1,286 |
| BA | shipping | 3 | 1/2 | 40,555 | 2,494 | 2,950 cs | 27.885 s | 1,175 |
| **BC** | shipping | 3 | 0/0 | 37,557 | 2,568 | 2,900 cs | **28.057 s** | 1,167 |
| **BD** | shipping | 3 | 0/0 | 37,568 | 2,532 | 3,150 cs | **29.334 s** | 1,117 |
| **BE** | `V9K_FAST_ERRNO` | 3 | 0/0 | 37,557 | 2,514 | 3,000 cs | **28.407 s** | 1,153 |
| BF | `V9K_FAST_ERRNO` | 3 | 1/2 | 40,544 | 2,475 | 3,150 cs | 29.717 s | 1,102 |

### Leg BS: upstream edit 16 is closed, and the port has a send measurement

**`-s RCVAG.DAT` on a file of exactly 32,768 bytes worked.** That is the
range edit 16 repaired — a 16-bit `rc` at `ckuusy.c:3690` threw away
`zchki()`'s return, which on success is the file size, so `-s <name>` refused
32,768 through 65,535 bytes and did it again every 64K. The edit shipped in
§8 with a `wdis` reading and the note *"Not yet run end to end."* It has now
been run end to end: **`gotbs.dat` is md5-identical to the fixture, and
`STEPBS.OUT` contains no error line at all.** The failure signature this leg
was watching for — `kermit -s NAME:` with an empty message after the colon,
meaning `zchki()` succeeded and the caller discarded the answer — did not
appear. **It was the only shipped edit in this port with no runtime evidence
behind it, and it is not any more.**

**And it is the first send-direction measurement the port has ever taken**,
which §16ae flagged as the gap: `V9K_PREFIXING` and `ckvictor.c`'s prefixing
initializer govern Victor→host only, because `ctlp[]` is read by the packet
*builders*, and nothing had ever exercised them.

| | Victor **sending** (BS) | Victor **receiving** (BC) |
|---|---:|---:|
| wire bytes for 32,768 | **40,726** | 35,950 |
| expansion | **+24.3%** | +9.7% |
| packets | 20 | 18 |
| line time at 38400 | 10.59 s | 9.35 s |
| elapsed | **23.633 s** | 28.057 s |
| non-line | **13.04 s** | 18.71 s |
| no-line ceiling | **~2,512 cps** | ~1,751 cps |
| **cps** | **1,386** | 1,167 |

Two results, and the second is the interesting one.

**The Victor sends faster than it receives — 1,386 against 1,167, +19%** —
and that is the fastest figure this port has ever produced. The asymmetry is
structural and it confirms from the other side what §16v and §16af concluded
about the receive path: building a packet and pushing it out of a polled
transmitter costs **13.04 s** where decoding one costs **18.71 s**, on the
same machine, over the same payload. The receive foreground is the port's
bottleneck and the send path is not close to it.

**But the Victor's prefixing is much more expensive than the host's: +24.3%
against +9.7%, 4,776 more wire bytes for the same 32,768.** The two are
directly comparable — same fixture, same session, same cable — and they are
two *policies* over identical data, the host running `set prefixing cautious`
and the Victor running its initializer. **The send is still faster despite
carrying 13% more traffic**, which is why this is a lead and not a defect:
the Victor has room, and the prefixing initializer §16ae kept on the argument
that it was "right for a Victor sending" is now measured and looks like the
wrong choice on wire bytes. Nobody has yet run a Victor send with
`cautious` to compare, and that is one leg.

> **Correction, 9 August 2026 (desk).** Two things in that paragraph are
> wrong and the conclusion survives both.
>
> **The numbers.** 40,726 and 35,950 are withdrawn. Counted from the logs —
> and cross-checked against the Victor's own `rxbytes` counter, which agrees
> **to the byte** on leg BC — they are **41,945 (+28.0%)** and **37,585
> (+14.7%)**. The 14.7% figure is what the rest of this document already
> quotes for this fixture, so this table was the outlier. The gap is 4,360
> wire bytes, not 4,776.
>
> **The attribution.** It is not "two policies", one per end. `ckvictor.c`
> selected `PX_CAU` and `initproto()` overwrote it with `PX_ALL` before
> anything read it (see the correction in §16ae), so **this is `PX_ALL`
> measured against `PX_CAU` and the Victor's initializer was inert.** The
> observation that the Victor's traffic is much more expensive is therefore
> *more* firmly established, not less — it is a clean single-variable
> comparison of the two stock policies over identical data — but it is not
> evidence about what a Victor running `cautious` does, because no such leg
> exists. `HW_TEST_16ai.md` legs CC and CD are that leg and its control.
>
> Recovered by decoding prefix characters: leg BS emitted **8,869** of them
> and the host **4,512** over the same 32,768 bytes, and that 4,357
> difference is the whole excess. `v9k/tools/pktstat.py` reports it, and
> also reads send legs correctly, which it did not when this section was
> written — the "read `s16ahBS.pkt` by hand" instruction above is obsolete.

### Leg 3: the `errno` change failed on the bench too, and has been removed

§16ag built it, verified in `wdis` that 27 far calls leave `ckutio.obj`, and
measured it **98 ms slower** under MAME at 9600. It shipped off, behind
`V9K_FAST_ERRNO`, with a decision rule written into `HW_TEST_16ag.md` before
the legs ran: *make it the default if the treatment arm is faster by more
than the within-arm spread; otherwise it has failed on both instruments and
should come out of the tree rather than stay as a permanent maybe.*

**The cleanest pair in the sitting is BC against BE**, and they are as
matched as this harness can produce — **identical `rxbytes` (37,557),
identical packet count (19), both 0/0, one binary difference:**

```
BC  shipping        28.057 s
BE  V9K_FAST_ERRNO  28.407 s      +350 ms
```

The treatment is slower, again. It is also inside the control arm's own
spread (BC 28.057, BD 29.334), so the weaker reading is "indistinguishable"
and the stronger is "slower"; **neither is "faster", which is what the rule
required.** The code is removed — `ckvictor.h`'s macro and `ckvictor.c` §1f
both — and the mechanism is written up here rather than carried in the tree.

**One honest caveat: the treatment arm has n = 1.** Leg BF went off-shape
(1 timeout, 2 retransmissions, 40,544 wire bytes) and is excluded, so BE
stands alone. The decision rests on BE being the best-matched leg available
*and* on MAME having said the same thing at 9600. If anyone wants to reopen
it, the way back is one commit and one more pair of legs, not a rewrite.

**What it cost the shipping binary:** 205,256 → **205,212**, the 44 bytes
being the initializer and pointer that were compiled but unreachable with the
flag off. **That means the binary that now ships is 44 bytes different from
the one legs BC and BD measured**, and §16w established this machine is
sensitive to code size. The delta is 0.02% and the removed code never ran,
but it has not been run, and the honest place for that is the list in §4 of
`NEXT_SESSION.md` rather than a footnote here.

### The calibration leg, which produced a different answer than it was sent for

Leg 1 existed because §16af could only say CRC-16 costs **one clock
quantum** over a 6-bit checksum — 100 ± 50 cs, i.e. 13 to 40 µs per wire
byte — and could not resolve it further on a 50 cs clock. The deliverable was
supposed to be a µs-per-8088-cycle constant.

**It did not produce one, and the reason is the result.**

Leg BA was the AG repeat and **failed to reproduce AG**: 1 timeout, 2
retransmissions, 40,555 wire bytes against AG's 37,568. Leg BB, the AH
repeat, reproduced **§16ae leg BX exactly** — 37,523 wire bytes, to the byte.
So the intended pair was half-delivered. But BB is a clean block-1 leg and
BC and BD are clean block-3 legs **on the same binary in the same session**,
which is a better comparison than BA/BB would have been:

| | block 1 | block 3 | Δ | µs / wire byte |
|---|---:|---:|---:|---:|
| BB → BC | 25.475 s | 28.057 s | **2.582 s** | **68.8** |
| BB → BD | 25.475 s | 29.334 s | **3.859 s** | **102.7** |

**§16af said 1.00 s and 26 µs. The bench says 2.6 to 3.9 s and 69 to 103 µs
— CRC-16 costs 10% to 15% of the transfer, not 3.7%.** The Victor's own
clock says the same thing independently: BB 2,650 cs against BC 2,900 and BD
3,150, a difference of 250–500 cs where §16af's pair differed by 100.

**§16af's figure was not mismeasured; it was under-determined, and this is
the specific way a single pair lies.** AG−AH was one draw from a distribution
this session has now sampled properly, and the draw came out at the small end.
§16af even said the right thing about its own instrument — "a pinned `rxpeak`
is a ceiling and not a measurement" — and then quoted a *difference* of two
50 cs readings as though it were one.

**§16af's conclusion survives, and its number does not.** There is still no
speed argument for shipping a 6-bit checksum: 10–15% is not 43%, edit 17 still
removed most of what §16ae measured, and the correctness case for CRC-16 was
never about speed. But **"CRC-16 now costs one clock quantum" should not be
quoted again**, and §16af's "at most 3.7%" is withdrawn.

### The finding that limits everything above: this bench is not repeatable to better than ~1.3 s

**BC and BD are the same binary, the same block check, both 0/0, `rxbytes`
37,557 against 37,568 — eleven bytes apart — and they are 1.277 s apart.**
BE and BF, same binary as each other, are 1.310 s apart. §16ag's MAME arms
reproduced to **1 ms and 5 ms**.

So the bench's run-to-run spread at 38400 is roughly **250 times MAME's**,
and it is the same size as the effect §16af was trying to size and five times
the effect §16ag was trying to detect. Two consequences worth stating
plainly:

- **Any bench claim about an effect smaller than ~1.3 s needs more than two
  legs per arm.** This is not the same lesson as §16af's leg AH (spend a leg
  on the null result) — that one is about attribution, this one is about
  power. Both are needed and neither substitutes.
- **2 of 7 legs went off-shape** (BA and BF, both 1 timeout / 2
  retransmissions and ~40,55x wire bytes), against 1 of 7 under MAME. Budget
  for roughly a third of bench legs being unusable for an A/B, because a leg
  that retransmits differently is not comparable and is re-run, not adjusted.

The cause is not established here. Candidates, none tested: the host's
round-trip estimator making different decisions run to run (§16l showed every
timeout in these logs is the host's), thermal or cable variation, and the
Pico SASI's write timing. **`rxpeak` is 2,4xx–2,6xx in every leg and
`rxfull` is 0 in every leg**, so it is not the ring, which is the one
candidate this port can already rule out.

### Measured, and on what

The §16o bench: Pico SASI serving `victor_kermit.img`, channel A, 1 m USB-C
to RS-232. `CKERMITW.EXE` (205,256, md5 `433148fa…`) for BA/BB/BS/BC/BD and
`CKFERR.EXE` (204,888, md5 `415cf233…`) for BE/BF, both staged and
round-trip verified off the image before the sitting; `CKAK.EXE` preserves
§16af's 205,968-byte build. Run sheet `HW_TEST_16ag.md`, take-files
`s16ahBA/BB/BS/BC/BD/BE/BF.ksc`, `STEPB*.BAT` on the image, host statistics
`s16ah*.host`, packet logs `s16ah*.pkt`, Victor counters `s16ah*.out`,
transferred files `gotBA.dat`…`gotBF.dat` and `gotbs.dat` — **all seven
md5-identical to `d94d2beda069ef0ef340977e7fd6995d`**.

**Every leg has all three artefacts this time.** §16ae lost the host clock
across seven legs and §16af across three; the run sheet was handed over as
the thing to work from and the redirect was taken on all seven.

**Shipping build after this section:** DGROUP **48,304 of 65,536 (73%)**,
image **205,212**, **needs 219,452 (214K)** at load, smallest Victor 384K.
19 warnings, all pre-existing upstream, `ckvictor.c` clean. Both standing
proofs re-run and passing. Still **seventeen** upstream edits.

---

## 16ai. The prefixing fix is verified, server mode runs on the machine, and the harness had two defects of its own

Seven legs on the real Victor, `HW_TEST_16ai.md` run as written. **Every
transferred file byte-exact**, `rxlost = 0` and `rxfull = 0` in all of them.
The headline landed exactly where the arithmetic said it would; two things
that had never been done on hardware were done; and **the two failures in the
sitting were both in the run sheet rather than in the port.**

### The prefixing fix: predicted, then measured, and the null leg is perfect

`ckvictor.c` had selected `PX_CAU` since §16ae and every leg this project ever
ran sent `PX_ALL`, because `initproto()` at `ckcmai.c:3295` copies
`ptab[protocol].prefix` over the variable 118 lines before `setprefix()` reads
it. The fix writes `ptab[PROTO_K].prefix`. Legs CC and CD are the treatment
and its control, both Victor sends of the 32,768-byte all-byte-values fixture
at 38400:

| | **CC** (`CKERMITW`, `PX_CAU`) | **CD** (`CKPXALL`, `PX_ALL`) | §16ah **BS** |
|---|---:|---:|---:|
| prefixing policy | **`PX_CAU` exactly (32)** | `PX_ALL` exactly (66) | `PX_ALL` exactly (66) |
| control prefixes | **4,512** | 8,869 | 8,869 |
| wire bytes | **37,557** | 41,945 | 41,945 |
| expansion | **+14.6%** | +28.0% | +28.0% |
| packets | 18 | 19 | 19 |
| `rxbytes` (ACKs) | 208 | 216 | 216 |
| Victor `elapsed` | 2,300 cs | 2,400 cs | 2,450 cs |
| host clock | **22.207 s** | 23.604 s | 23.633 s |
| **cps** | **1,475** | 1,388 | 1,386 |

**The saving is 4,388 wire bytes, −10.5%**, and it is a *count*, not a
difference of two clocks. That was the whole design of the leg: the effect is
~1.1 s of line time at 38400, under this bench's ~1.3 s repeatability floor
(§16ah), so it was made answerable by measuring it in units that do not vary.
**When the bench cannot resolve an effect in seconds, find a counter that
measures the same mechanism.**

**CD is the best null leg this project has produced.** It reproduces §16ah
leg BS on *every* measure — same 8,869 prefixes, same 41,945 wire bytes, same
216 `rxbytes`, same 19 packets — and the two host clocks are **29 ms apart**
on a bench whose spread is 1.3 s. That is what makes CC attributable. It was
cheap because `CKPXALL.EXE` is the same tree, the same commit and the same
**205,228 bytes** as `CKERMITW.EXE`, differing only in the immediate constant
the initializer stores, so §16w's code-size sensitivity had nothing to act on
— where §16af had to spend a whole leg establishing the same thing.

**1,475 cps is the fastest figure this port has produced**, beating §16ah leg
BS's 1,386. But CC and CD are 1.397 s apart, which is barely over the noise
floor: **quote the wire-byte count as the result and the cps as an
illustration.** The two legs differ by 4,388 wire bytes = 1.14 s of line time
at 38400, and they came back 1.397 s apart, which is consistent — but a
single pair cannot separate 1.14 from 1.40 on this bench.

**One number is worth keeping for its own sake.** CC's 37,557 wire bytes is
*identical* to leg BC's host-sent figure. Same policy, same data, opposite
directions, same count — which is what "prefixing is a property of the sender
and the data, not of the machine" looks like when it is measured rather than
argued.

### Server mode works on real hardware — leg CS, and it is a first

`CKERMITW -x`, driven entirely from the host: **SEND to the server 1,058 cps,
GET from the server 1,431 cps, then FINISH**, both transfers `SUCCESS` and
byte-exact, `rxlost = 0 rxfull = 0 rxpeak = 2,332`. `HW_TESTING.md` leg 0.7
had been untouched since it was written and §16i's server work had only ever
run under MAME. **No E packet appeared**, so §16i's priority-0 capability
initializer is doing its job on the machine — which is a second, independent
check on the XI mechanism that §1 just found failing elsewhere. `REMOTE
DIRECTORY` and `BYE` were deliberately excluded and remain untested.

### A transfer on the parser build — leg CH, and it is also a first

**`CKICP` transferred 32,768 bytes at 38400, byte-exact, `rxlost = 0
rxfull = 0`, `rxpeak = 2,852 of 4,096`, at 1,213 cps.** Edit 14 widened what
`main()` compiles, so the parser binary is not the one any throughput figure
was measured on, and this is what says the wire protocol did not move. 1,213
against the shipping build's 1,167–1,475 band is inside the noise and should
not be read as a difference.

**The leg is complete and wants no re-run.** Its `STEPCH.OUT` is empty
because the successful run was the hand-driven one, so the counters above are
transcribed from a photograph of the screen rather than read out of a file.
That is a weaker artefact and it is still an answer: the md5 and the loss
counters are what the leg was sent for. `RXEA.KSC` was fixed afterwards so a
future run needs no human — **the fix is not a precondition of this result,
and re-running would measure the take-file rather than the port.**

**The leg's `elapsed=11300 cs` is meaningless and the reason matters**: it
includes the time the machine sat at an interactive prompt waiting for a
human. The Victor's `elapsed` starts at the first byte received and closes at
release (§16u); it does not know the difference between a slow line and a
stopped operator. The host's `statistics` — 27 s, 1,213 cps — is the figure.

### The two failures were the run sheet's, and both generalise

**1. The parser build prompts, and a redirect hides the prompt.** Leg CH hung
indefinitely. Run interactively it turned out to be sitting at
`Accept incoming file "A:/rcvch.dat"?` and then at `OK to exit?`, neither of
which is visible when stdout is redirected to a file — **which the sheet
required, because the `v9k:` counters only reach stdout.**

The mechanism is worth writing down because it is not where anyone would
look. `fnrconfirm` is `CONFIRM_ON` **by default** (`ckcmai.c:1408`), scope
`LOCAL`, and a Victor driving its own serial line *is* local, so
`rq_confirm_check()` (`ckcfns.c:3567`) reaches the prompt on **every**
`RECEIVE` this port has ever run. The shipping build never prompted only
because `ckvictor.c` supplies a `getyesno()` that returns yes. In a
`KEEP_ICP` build the linker keeps *upstream's* `getyesno()` and discards ours
(`W1027`, decided by link order), so the prompt becomes real.

**So that stub is load-bearing, and its comment said it was unreachable.**
It claimed the prompt "cannot happen" without a parser to turn `SET RECEIVE
CONFIRM` on — but nothing has to turn it on; it is the default. Every
scripted receive leg in this project's history has depended on that function
answering yes. Corrected in place. **A stub whose comment says it is
unreachable has, by construction, no test proving it.**

Fixed in the harness rather than the code: `RXEA.KSC` now carries `set
receive confirm off` and `set exit warning off`. That is the right layer —
the prompts are correct behaviour for an interactive build, and it is the
*redirect* that makes them fatal.

**2. The machine takes 40–85 seconds to load the program, and the host gives
up.** `CKERMITW` is 205 KB and `CKICP` is 435 KB, read off a SASI emulator
before `main()` runs. Start the host too soon and it exhausts `MAXTRY`
(10, `ckcker.h:472`) against a Victor that has not reached `receive` yet —
**and a host that gives up looks exactly like a Victor that failed.** Leg
CE's 1 timeout / 2 retransmissions and leg CH's first attempt (12 timeouts,
`FAILURE`) are both this.

Two fixes, and both are wanted. Procedurally, the sheet now says to wait for
the Victor with explicit times rather than leaving it to judgement.
Mechanically, the host take-files for every leg where the **host** initiates
now carry `set retry 30`. Neither is sufficient alone: patience in the host
does not help if the operator is watching a blank screen wondering whether
anything is happening, which is the complaint that surfaced this.

**The general defect is that the sheet optimised for capture and not for
visibility.** Three artefacts per leg, all written to files, and nothing on
the screen to say what the machine was doing. That is fine while everything
works and useless the moment it does not.

### Leg CE, and one instrument result worth keeping

CE went off-shape — 1 timeout, 2 retransmissions, 40,544 wire bytes against
the clean 37,55x, 30.756 s and 1,065 cps — which is the startup race above,
not a defect. It is still byte-exact with `rxlost = 0 rxfull = 0`. **Its
reconciliation is exact**: `pktstat.py --rxbytes 40544` gives a residual of
**+0** against the host's 40,544, with `rxfull = 0`. Two independent counts
of the same 40,544 bytes, agreeing to the byte on a leg that retransmitted
twice.

**Shipping build after this section:** unchanged — DGROUP **48,304 of 65,536
(73%)**, image **205,228**, **needs 219,452 (214K)**, smallest Victor 384K.
The only source change in this section is a corrected comment, and the
binary is byte-identical (md5 `537486a8…`) across it. Still **seventeen**
upstream edits.

## 16aj. Flow control, and the two upstream blocks that make the termios route a trap

`NEXT_SESSION.md` §1 item 11 — the last unimplemented feature and a
precondition for both of the two after it. It is built: **RTS/CTS and
XON/XOFF, both directions, in both interrupt handlers**, selectable without
a parser, instrumented, and **still no upstream edit — seventeen.**

The design in that item survived contact with the machine. Two of its
premises did not, and both were the same mistake: a line of upstream source
was read and believed without asking whether the build compiles it.

### What was built — `ckvictor.c` §1f

Two mechanisms, two directions, named apart because the four combinations
are different code:

| | how we hold the far end off | how it holds us off |
|---|---|---|
| **RTS/CTS** | drop WR5 bit 1 | require RR0 CTS before each byte |
| **XON/XOFF** | transmit one XOFF, once | obey an XOFF seen in the input stream |

The **assert is in the interrupt handler** and the **release is in
`v9k_ser_get()`**, and that split is the whole point: the case flow control
exists for is the one where the foreground is *not running* — inside a
half-second file write, or decoding a packet — so a hold-off the foreground
has to raise cannot be raised when it is needed. The handler already
computes the ring occupancy that the water mark is a test on. The release is
safe in the foreground because draining is the only thing that makes the
ring emptier.

Water marks are 3/4 and 1/4 of the ring, 3.13's `MNTRGH`/`MNTRGL` on this
same chip.

**What it costs the handler is four instructions per byte**, and after §16t
that number needs justifying rather than asserting:

- one byte compare of `v9k_fc_out` before the store, to decide whether an
  XOFF in the stream is data or a command;
- one word compare of the occupancy against `v9k_rxhigh` after it.

Neither needs a second test to know flow control is off. `v9k_rxhigh` is
`0FFFFh` when it is, and occupancy is masked to `0FFFh`, so "is it on" and
"have we crossed it" are one compare — which is why the mark is a variable
and not the `V9K_RXHIGH` constant. Call it ~25 clocks, ~5 µs of the 260 µs
a byte takes at 38400, ~2% of the handler. That is affordable now in a way
it was not before §16af — `rxpeak` is 2,581 of 4,096 and the ring is no
longer the binding constraint — but it is real and it is paid by every
build, including the ones with flow control off.

**The XOFF is single-shot.** 3.13's `SERINT` polls TX-ready in a loop
bounded at 65,536 turns before writing its XOFF (`msxv90.asm:srint9`), after
an `sti`. Neither half is copied: polling with interrupts off blocks
receive, which is the defect §16t fixed, and re-enabling interrupts inside a
handler with no stack switch invites a nested entry on a 10-byte frame. So
the handler tests RR0 once and, if the transmit buffer is busy, does nothing
and tries again on the next received byte. The cost of a missed attempt is
one byte time; the ring has 1,024 bytes of headroom above the mark.

**One race had to be closed.** The handler and the polled transmitter write
the *same* data register, and the transmitter's sequence is "test RR0 for
TxEmpty, then store". An interrupt taken between the two lets the handler
put an XOFF in the buffer that our byte then overwrites — one character lost
from the middle of a packet. The block check would catch it and the packet
would be retransmitted, **so the symptom is a slow line and not a wrong
file, which is exactly the kind of defect that survives a byte-exact
transfer.** `cli`/`sti` around the test and the store closes it for two
instructions against 260 µs of wire time.

### The default is `FLO_NONE`, and that is a measurement argument

Item 11 said RTS/CTS should be the default. It ships off, for two reasons in
this order:

1. **Nothing needs it.** With `DFWSIZ = 1` the far end sends a packet and
   waits for our ACK, so bytes in flight never exceed one packet; the
   longest this port has put on a wire is 3,991 and the ring is 4,096.
   `rxfull` has been 0 in every clean run ever recorded.
2. **Selecting RTS/CTS makes the transmitter wait for CTS, and no
   measurement says our RTS reaches the far end's CTS.** §16v read `cts = 1`
   on the bench cable with the host holding RTS asserted under `set flow
   none` — that settles the *input* half and says nothing about the output
   half. A cable wired one way only would turn a working port into one that
   never sends a byte, which is a far worse failure than the one flow
   control is insuring against.

So the shipping binary behaves exactly as §16ai's did, and **one bench leg —
`--rtscts` at 38400, byte-exact or not — is what flips the default.**

What it unblocks is the reason to have it anyway: **windowing** (`DFWSIZ`),
and **longer packets**, because the 105-byte margin between `DRPSIZ = 4000`
and `V9K_RXBUFSIZ = 4096` is an accident and `DRPSIZ` could not be raised
past ~4,090 without something to fall back on.

### Selection: three switches, and §16i's control run

`NOICP` removes `SET FLOW`, so the choice is made the way `--safe-server`
is made (§16i): a **priority-0 XI initializer** reads Watcom's copy of the
DOS command tail and blanks the switch out of it **before `__Init_Argv`
builds `argv` at priority 1**, so `cmdlin()` never sees an option it would
`XFATAL` on.

    CKERMITW --rtscts     CKERMITW --xonxoff     CKERMITW --noflow

`--noflow` is not redundant even though it is the default: it is **the
control leg**. A binary built with `-dV9K_FLOW=FLO_RTSC` can be run with
flow control off without rebuilding, and §16w established that two binaries
are a confound where one binary and one switch are not.

**Leg FE**, one 2.5-minute MAME boot, no serial line and no host, reading
the choice back through `uname()` into the debug log (§16i's oracle):

| invocation | `v9k flowsel` | `STEPFE*.OUT` |
|---|---:|---|
| `--xonxoff -d -h` | **1** (`FLO_XONX`) | 694 bytes of help |
| `--rtscts -d -h` | **2** (`FLO_RTSC`) | 694 bytes of help |
| `-d -h` | **0** (`FLO_NONE`) | 694 bytes of help |
| `--xonxofz -d -h` | 0 | **34 bytes: `Extended options not configured`** |

The fourth row is §16i's mandatory unknown-option control, and it is the
only thing that distinguishes "recognised" from "silently ignored": a switch
this initializer does not know stays in the tail, reaches `cmdlin()`, and
fatals.

### Where the mode is applied, and the §16ai trap avoided

The same trap as the prefixing defect, on a second variable. What this port
wants to say is "the default flow control for a direct serial line is X",
and the durable place to say it is **not** the variable upstream reads:
`main()` runs `initflow()` at `ckcmai.c:3269`, which fills `cxflow[]` from
its own table and then does `flow = cxflow[cxtype]`. Anything an XI record
put in either is gone before `ttopen()`.

What runs *after* `initflow()` and *before* the value is used is
`v9k_ser_install()` — it is called from `tcsetattr()`, `tcsetattr()` is
called from `ttopen()`, and **every `ttopen()` in this program is followed
within a few lines by `cxtype = CXT_DIRECT` and `setflow()`**, which is the
call that copies `cxflow[cxtype]` into `flow` (`ckuusy.c:3941-3943` for
`-l`, `ckuusr.c:11245` and neighbours for `SET LINE`). So the install writes
`cxflow[CXT_DIRECT]`, one statement before the copy that reads it.

It gets the parser build's precedence right for free: `SET FLOW` sets
`autoflow = 0` (`ckuus3.c:11939`) and `setflow()` returns immediately when
`autoflow` is clear, so a typed setting is not disturbed.

### The two upstream blocks, and this is the part that generalises

Item 11 said, twice, that the plumbing was already there: *"`ckutio.c`
already hands our `tcsetattr()` the right termios bits (`IXON|IXOFF` at
`ckutio.c:6617`, `CRTSCTS` at `6252`)"*. **Both halves are wrong, in
different ways, and each was found by a different instrument.**

**1. `CRTSCTS` at 6252 is inside `#ifdef OXOS`.** The arm this build takes
is the `POSIX_CRTSCTS` one at 5920 — and `ckcdeb.h` hands `POSIX_CRTSCTS`
out per platform (`__linux__`, the BSDs, `IRIX52`, BeOS) and the Victor is
none of them. With no arm taken, **every branch of `tthflow()`
preprocesses away and the whole function reduces to `int x = 0;
return(x);`.** Measured, not read: `wcc -pl` on `ckutio.c` with this build's
flags gives a body of thirty blank `#line` directives. So `ttpkt()`'s
`FLO_RTSC` arm called `tthflow(flow,1,&ttraw)`, which did nothing, and
`CRTSCTS` had never once reached this file. `ckvictor.h` now defines
`POSIX_CRTSCTS`, which takes the arm that is written entirely in
`tcgetattr()`/`tcsetattr()` — both ours. **No upstream edit; it is a
platform description, and the platform does implement that API.**

**2. `IXON|IXOFF` at 6617 is set and then cleared again 141 lines later.**
`ttpkt()`'s `SVORPOSIX` arm puts them in `ttraw.c_iflag` for `FLO_XONX`.
Then, four lines before the `tcsetattr()` that applies the struct:

```c
#define TESTING234
#ifdef TESTING234
    if (1) {
        ...
        ttraw.c_iflag &= ~(INPCK|IGNPAR|IXON|IXOFF);      /* ckutio.c:6758 */
```

A debugging block, `if (1)` inside an `#ifdef` of its own `#define`, left
switched on. It does **not** touch `c_cflag`, so the `CRTSCTS` half
survives. **One mechanism arrives through termios and the other cannot.**

This was not found by reading either. It was found by **leg FB**, which ran
`--xonxoff` with the water marks lowered to 256/64 on a leg whose `rxpeak`
reached 303, and came back `flow in=0 out=0 held=0` — the switch parsed
(leg FE proves it), the mode never arrived. **Leg FD** then ran the same
invocation under `-d` with no host and no `socat` at all, and the debug log
has the whole chain in order:

```
v9k flowsel=1                     the switch parsed
setflow cxtype=1  setflow flow=1  cxflow[CXT_DIRECT] reached "flow"
ttpkt xflow=1                     ttpkt was passed it
tthflow POSIX_CRTSCTS status=0    the hardware arm now compiles
ttpkt TESTING234 rawmode          <- and here the bits go
ttpkt calling tcsetattr(TCSETAW)
v9k_ser_setflow in/out[0]=0       what actually arrived
```

So `ckvictor.c` §1f reads **upstream's own `flow` variable** and not the
termios bits. That is not a private flag and not a workaround: `flow` is
C-Kermit's answer to "what flow control is in effect", it is exactly what
`ttpkt()` was passed, and reading it inside `tcsetattr()` asks the question
at the moment the line is programmed. The `CRTSCTS` and `IXON` bits are
still read, and logged next to it, so the day `ckutio.c:6758` changes is
visible rather than inferred.

**The rule both halves teach is the one §16j already wrote down and this
section had to learn again: a line of upstream source is not evidence that
the build compiles it.** The cheap instrument is `wcc -pl`, and it answered
both in under a second — the first as an empty function body, the second as
two live statements 141 lines apart.

### `tcflow()` is implemented, and its only upstream caller does not exist

POSIX's recovery from a lost XON is `tcflow(TCOON)`, and `ckutio.c` does
call it: `ttoc()` reaches for it when a single-character write has timed out
and flow is XON/XOFF. It is written as

```c
debug(F100,"ttoc tcflow","",tcflow(ttyfd,TCOON));       /* ckutio.c:10849 */
```

and `NODEBUG` defines `debug(a,b,c,d)` as **nothing** (`ckcdeb.h:5486`), so
the call is discarded with the macro. Measured the same way: `tcflow` does
not occur anywhere in the preprocessed `ckutio.c` for this build except in
its own prototype. It is the **only** caller of `tcflow()` in the Unix
module, so in any `NODEBUG` build the entire POSIX unstick path is gone.

`tcflow()` is implemented here anyway — all four actions, mapped onto §1f's
assert and release — because a partial one is worse than none for the next
reader. But the driver cannot delegate its own recovery to it, so
`v9k_ser_put()` carries `V9K_FCSPIN`: a **separate, much longer bound** for
"the peer is holding us off" than the `V9K_TXSPIN` used for "the chip is
broken". A far end whose disk write takes a second is entitled to keep XOFF
asserted for a second, and spending the transmitter's budget on that would
turn ordinary flow control into a write error. When the backstop fires it
counts `stuck` and returns a short write, which `ttol()` already retries.

**A functional side effect inside a `debug()` argument is an upstream defect
and it is not specific to this port**; it belongs on §8's report list with
`TESTING234`.

### The legs

All at 9600 under MAME on Victor MS-DOS 3.1, `socat` first, host `kermit` at
t+110 s, the 32,768-byte all-byte-values fixture, `-seconds_to_run 300`.
**Every one byte-exact against `d94d2beda069ef0ef340977e7fd6995d`, `rxlost =
0` and `rxfull = 0` throughout.**

| leg | binary | switch | marks | wire bytes | pkts | `rxpeak` | `flow in/out` | `held/rel` | `xoff/xon` | host clock |
|---|---|---|---|---:|---:|---:|---|---:|---:|---:|
| **FZ** | pre-change, `537486a8` | — | — | 39,726 | 32 | 298 | *(no line)* | — | — | 77.863 s |
| **FA** | §1f, termios-sourced | — | 3072/1024 | 37,719 | 24 | 104 | 0 / 0 | 0 / 0 | 0 / 0 | 75.906 s |
| **FB** | §1f, termios-sourced | `--xonxoff` | **256/64** | 39,726 | 32 | 303 | **0 / 0** | **0 / 0** | 0 / 0 | 77.890 s |
| **FC** | §1f, termios-sourced | `--noflow` | 256/64 | 39,726 | 32 | 303 | 0 / 0 | 0 / 0 | 0 / 0 | 77.872 s |
| **FG** | §1f, `flow`-sourced | — | 3072/1024 | 40,840 | 38 | 301 | 0 / 0 | 0 / 0 | 0 / 0 | 90.363 s |
| **FH** | §1f, `flow`-sourced | `--xonxoff` | **256/64** | 39,799 | 32 | 303 | **1 / 1** | **1 / 1** | 0 / **5** | 82.797 s |
| **FJ** | §1f, `flow`-sourced | `--noflow` | 256/64 | 40,840 | 38 | 301 | 0 / 0 | 0 / 0 | 0 / 0 | 92.432 s |

**FB is the failure that found `TESTING234`** — `--xonxoff`, marks at 256,
`rxpeak` 303, and the assert never fired because the mode never arrived.
**FH is the same leg after the source of truth moved to `flow`**, and it
fires: `in=1 out=1 hi=256`, `held=1 rel=1`. The two counters end **equal**,
which is the property to check — `held > rel` at exit means the far end was
left held off.

**FG and FJ are identical to the byte**, which is the null this section
needed: same binary, same lowered marks, one switch, and `pktstat.py` gives
40,840 wire bytes, 38 packets, longest 3,387, 8 and 3 retransmissions,
`rxbytes` 40,851 for both. The switch changes nothing when it is off.

**`xon = 5` on FH is a real reading and worth understanding.** The host was
running `set flow xon/xoff`, which puts `IXON|IXOFF` on the `socat` pty, and
a tty line discipline emits START characters of its own. Five of them
arrived, our handler took them out of the stream, and **the reconciliation
proves that was the right thing to do**: `pktstat.py --rxbytes` gives a
residual of **−11 on FH, exactly as on FG and FJ**, which is this harness's
clean-leg constant. Counting the intercepted characters in `rxbytes` would
have made it −16 and broken every `mapoffset.py` offset after the first one.
They are not in the host's packet log because they are not packets, and
`v9k_fc_xon` is where they are reported instead.

Left unsaid by these legs, deliberately: **whether the host obeyed our
XOFF.** One assert on a leg the ring was never in danger on cannot show
that, and a pty is not a serial line.

### The session's own spread, which is a caution and not a result

Do not difference the host clocks in that table across the session.
FZ/FA/FB/FC ran within 2.0 s of each other and FG/FH/FJ within 9.6 s, but
the two groups are 12–15 s apart with the same fixture and, for FG against
FA, functionally the same code. The host machine got busier: the *host's*
timeout count rose from 3 to 5 and its retransmissions from 6 to 8 across
the same span, and the packet shape changed with it — 24 packets and a
longest of 3,991 early, 38 and 3,387 late, because C-Kermit's slow start
makes different decisions when the round trip drifts.

**That is 250× §16ag's MAME arms, which held to 1 ms**, and the difference is
not the emulator — it is what else the host was doing. So: **a MAME A/B is
only comparable within a group of legs run back to back**, and this section
relies only on adjacent pairs (FA against FZ, FG against FJ, FH against FJ).
Every cross-group figure here is provenance, not measurement.

### Cost, and what is still not known

**Shipping build after this section:** DGROUP **48,336 of 65,536 (73%)**,
up 32; image **206,758**, up 1,530; **needs 220,950 (215K)**, up 1,498;
**smallest Victor 384K, unchanged**. 19 warnings, unchanged, none in
`ckvictor.c` or `ckvisr.asm`. `ckvisr.asm`'s DGROUP immediate verified
against the map after linking per §16t — `mov ax,2a21h` against `DGROUP
2a21:0000`. **Seventeen upstream edits.**

**`HW_TEST_16aj.md` is the sitting that answers the first two**, and it is
written and staged: seven legs, two binaries differing in five bytes, the
decisive pair read as `rxpeak` rather than as a clock.

Not known, in the order a bench sitting should take them:

1. **Whether our RTS reaches the far end's CTS.** §16v settled the input
   direction only. This is the one that decides the default, and it cannot
   be answered under MAME at all: `-bitb socket` is a raw byte stream with
   no modem control, so an RTS/CTS leg there tests nothing on the wire.
   (`mdm cts=1` in every MAME leg above is the `CLOCAL` carrier clause and
   the emulated 7201's idle state, not a cable.)
2. **Whether a far end obeys our XOFF**, on a real serial line rather than a
   pty.
3. **The assert path under overrun.** `v9k_ringfull` re-enters the water-mark
   check with occupancy forced to the mask, and nothing has ever executed
   it — the same standing caveat the assembly handler's overrun branch
   carries.
4. **`DRPSIZ` past 4,090 and `DFWSIZ` past 1**, which are what this was a
   precondition for and which still need their own legs.

## 16ak. Flow control on the machine: safe, and not yet shown to be effective

`HW_TEST_16aj.md` run as written, 9 August 2026, seven legs on the real
Victor at 38400. **Every transferred file byte-exact.** `rxfull = 0` and
`stuck = 0` on all seven; `rxlost = 0` on six.

**The sitting split its own question in two and answered one half
decisively.** Turning RTS/CTS on cannot wedge the transmitter and costs
nothing measurable — that is legs DS and DE, and they carry the two tightest
null pairs this project has produced. Whether the far end actually *stops*
when the Victor drops RTS is still open, because the one leg that could show
it went off-shape in exactly the way the run sheet's own caveat warned about.

**The default was not flipped.**

### The seven legs

All at 38400 with block check 3, `PX_CAU`, the 32,768-byte all-byte-values
fixture. `CKERMITW` is the shipping build (206,758, md5 `c5652a5b…`);
`CKFCLO` is the same 206,758 bytes with the water marks at 256/64, differing
in **five bytes** and three constants, so §16w has nothing to act on.

| leg | binary | switch | marks | dir | wire bytes | pkts | resends | `rxpeak` | `held/rel` | `rxlost` | host clock | cps |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **DN** | `CKERMITW` | — | 3072/1024 | recv | 37,557 | 18 | 0 | 2,990 | 0/0 | 0 | 31.535 s | 1,039 |
| **DS** | `CKERMITW` | `--rtscts` | 3072/1024 | **send** | 37,557 | 18 | 0 | 52 | 0/0 | 0 | **22.206 s** | **1,475** |
| **DA** | `CKFCLO` | `--noflow` | 256/64 | recv | 37,557 | 18 | 0 | 2,780 | 0/0 | 0 | 31.137 s | 1,052 |
| **DB** | `CKFCLO` | `--rtscts` | 256/64 | recv | 40,544 | 25 | **3** | 2,932 | **15/15** | 0 | 32.812 s | 998 |
| **DE** | `CKERMITW` | `--rtscts` | 3072/1024 | recv | 37,557 | 18 | 0 | 3,137 | **1/1** | 0 | 31.143 s | 1,052 |
| **DC** | `CKFCLO` | `--xonxoff` | 256/64 | recv | 43,356 | 31 | **6** | 2,031 | **20/20** | **19** | 34.916 s | 938 |
| **DX** | `CKERMITW` | `--xonxoff` | 3072/1024 | **send** | 37,557 | 18 | 0 | 52 | 0/0 | 0 | **22.203 s** | **1,475** |

`held` and `rel` are **equal on every leg that asserted**, which is the
property to check: `held > rel` would mean the far end was left held off.

### Safe: two null pairs, six milliseconds and three

**DS is the strongest result in the sitting.** `--rtscts` puts the CTS test
on `v9k_ser_put()`'s per-byte path, and the failure mode if CTS were not
asserted is *silence* — not a slow transfer, not a corrupt one. It sent
32,768 bytes byte-exact at **1,475 cps, equalling §16ai leg CC, the fastest
figure this port has produced**, with `stuck = 0`. **Leg DX, the same send
with `--xonxoff`, took 22.203 s against DS's 22.206.** Three milliseconds.
Neither mechanism is detectable on the send path.

**DE is the leg that licenses the default, and it passed.** Shipping binary,
shipping water marks, `--rtscts`, and against its control DA:

| | DA (`--noflow`) | **DE (`--rtscts`)** |
|---|---:|---:|
| wire bytes | 37,557 | **37,557** |
| packets / resends / timeouts | 18 / 0 / 0 | **18 / 0 / 0** |
| `rxbytes` | 37,568 | **37,568** |
| host clock | 31.137 s | **31.143 s** |

**Six milliseconds apart, identical on every wire measure.** Turning the
feature on, in the configuration that shipping it would produce, is free.

**`held = 1` on DE, where the run sheet predicted 0** — and the sheet was
wrong for an interesting reason. It reasoned from §16af's `rxpeak = 2,581`
that the 3,072 mark was unreachable. This sitting ran the ring deeper:
2,780, 2,990 and 3,137 across three legs of the same fixture. So the mark
was crossed once, the hold-off asserted and released, and nothing else
changed. **A water mark chosen from one session's high-water reading is a
mark that will occasionally fire.**

### Not effective — or rather, not shown, and the leg that failed to show it

**Leg DB is the one the sitting was for, and it is unusable for the question
it was asked.** The mechanism plainly ran — `in=2 out=2 hi=256`, fifteen
assert/release cycles, `stuck = 0`, byte-exact. But the leg took **a timeout
and three retransmissions inside its first 7,680 bytes**, C-Kermit's slow
start reset, and it finished with 25 packets instead of 18 and a longest
packet of 3,585 instead of 3,991.

**`rxpeak = 2,932`, and `mapoffset.py` puts `peakat = 6,704` fourteen bytes
into a RESEND of seq=07.** That is §16m's finding and §16ag's caveat exactly:
`rxpeak` measures the host's retransmission, so a leg that retransmits is not
comparable with one that does not. The run sheet printed that caveat directly
above the leg. **It fired, and it voids the reading.**

So the sheet's stated decision rule — `rxpeak` ≈ 2,4xx means the far end
ignored us — **must not be applied here.** It was written for a clean leg.

**One number survives and it is unexplained.** `stall256` — the count of
times occupancy, after a store, equals exactly 256 — is **2,399 on DB
against 47 on DA**. Fifty-fold. For occupancy to cross 256 upward 2,399
times it must have fallen back below 256 that many times, and during a
packet this port's foreground *cannot* drain faster than the line delivers
(§16v: 485 µs against 260). **Something made the sender pause, repeatedly.**
But fifteen assert/release cycles cannot produce 2,399 crossings either, and
no model in this tree accounts for the shape. It is the strongest hint that
the host obeyed our RTS and it is **not** proof of it.

### The reading that was wrong, and the tool that corrected it

An earlier reading of leg DE claimed it as the positive result: `rxpeak =
3,137` against a mark of 3,072 is a **65-byte overshoot**, which is exactly
what a working RTS/CTS link with USB and FTDI buffering in the path would
give — and the peak was "8 bytes into a 3,999-byte packet", so the packet
could not have ended there and the sender must have stopped.

**`mapoffset.py` killed it in one command.** Offset 7,678 is 8 bytes into
seq=08, which means it is at the **boundary** where the 3,905-byte seq=07
ends. That is the same kind of place DN and DA peaked — both at offset
31,669, two bytes into seq=14, the boundary at the end of seq=13. **The peak
in all three legs is at a packet boundary, which is where occupancy is
always highest**: the foreground falls behind through a packet and catches up
in the turnaround. DE's 3,137 is a natural peak that happened to clear the
mark, not a cap.

**The rule: ask where a peak IS before reading it as a limit.** `rxpeak`
alone cannot tell "the sender stopped" from "the packet ended", and this
tree has had a tool that answers it since §16m.

### XON/XOFF cost 19 bytes, RTS/CTS cost none, and that is a real difference

**Leg DC is the only leg in the sitting with any loss at all, and the first
non-zero `rxlost` on this bench since §16t.** 19 overruns in `evt = 11`
bursts, `max = 3`, `losttag = 10` (the foreground in upstream code after
`ttol()` returned), 3 Victor NAKs, 3 host retransmissions, 43,356 wire bytes
and 938 cps — the slowest of the seven. Byte-exact: the protocol recovered
all of it.

**RTS/CTS at the same marks on the same binary lost nothing**, so it is not
the water marks, not the ring and not the mark depth.

**Cause not established.** The leading suspect is the ISR's XOFF path: it
reads RR0 and writes the data register, and when the transmit buffer is busy
the single-shot retry re-reads RR0 on **every** subsequent byte until it
succeeds. **Nothing counts those failed attempts**, which is an instrument
gap rather than a diagnosis — and it is the same shape as §16s's mistake,
where an instrument was put on a path that is rare only while the receiver
keeps up.

Either way it is a reason to prefer RTS/CTS where a cable allows it, and it
does not change the case for shipping both: XON/XOFF remains an
interoperability requirement, and 19 recovered bytes in 32 KB is a cost, not
a defect.

**DC's reconciliation is −15 where the tool wants −11, and that is
explained.** `rxbytes` counts one substituted BELL per overrun interrupt and
there were 19 of them; `pktstat.py`'s formula has no term for that. It needs
`--rxlost`. On the six clean legs the residual is exactly −11.

### The gap this run sheet had, and it was a design error

**There is no adjacent pre-change control.** The sheet has a null leg — DN,
the shipping binary with the feature off — but its comparison class is
§16ai's and §16ah's numbers from *other sittings*. That is the one thing
§16aj said not to rely on, written into a sheet by the same session that
wrote the warning.

It matters, because the three clean receive legs came in at **31.137,
31.143 and 31.535 s on 37,557 wire bytes**, and §16ah leg BC did the
identical 37,557 in **28.057 s**. That is **+11%**, about eight times this
sitting's own spread. Either §1f costs 11% of a 38400 receive or the two
sittings are not comparable, **and this data cannot say which.**
`CKPRE.EXE` — 205,228, md5 `537486a8…`, HEAD before §1f — is already on the
image; one adjacent pair settles it.

### The bench repeated to 0.4 s this sitting, not 1.3 s

Three protocol-identical clean receive legs: **31.137, 31.143, 31.535 s** —
a spread of **398 ms**, and the two closest are **6 ms** apart. The two send
legs are **3 ms** apart. §16ah's figure of ~1.3 s, which `NEXT_SESSION.md`
§1 item 5b makes the governing constant for every bench A/B, was **that
sitting's** spread and not the bench's.

**Do not relax the rule on one sitting.** What this says is that the ~1.3 s
is a bound and not a floor, that whatever caused it is intermittent, and
that item 5b's question — why does this bench not repeat — is still open and
now has a second data point to work from. Six milliseconds on legs DA and DE
also means the *effects* this sitting could have resolved were much smaller
than the ones it was designed around.

### The re-run of DA/DB was void, and it was the run sheet again

Legs DA and DB were re-run the same day and **produced no data at all**.
Both packet logs are **287 bytes**; the Victor's screen reads

```
 No files were transferred (refused: destination file already exists).
```

and the wire carries the documented signature exactly — `s-03-02-…ZD`: an S,
an F, an A, then a **Z packet whose data is `D`**, and no data packets.
`RCVDA.DAT` and `RCVDB.DAT` were still on the image from the first sitting,
`SET FILE COLLISION` is `BACKUP`, and BACKUP cannot work on FAT. Both files
on the image are byte-identical to the first sitting's: nothing was written.
`held = 0`, `rxbytes = 129`.

**Two failures, both in `HW_TEST_16aj.md`.** Its §0 recorded the target names
as clear — true before the *first* sitting — and its closing section then
asked for a re-run **without saying to clear them or use fresh ones**, with
the trap and its signature documented one section above the instruction that
walks into it. And it asked for the re-run at `-dV9K_RXHIGH=1024
-dV9K_RXLOW=512` while **never building or staging that binary**, so the
re-run used 256/64 regardless — the setting that voided DB the first time.

**The fix is structural and it is the part worth keeping.** Every leg in
`HW_TEST_16al.md` has a target name that has never been used, and every
`.BAT` opens with `IF EXIST RCVGx.DAT DEL RCVGx.DAT`. **This trap has now
cost two sittings; "use a fresh name" is a rule a person has to remember,
`IF EXIST … DEL` is one the machine keeps.** The same applies to the
binary: a sheet that names a build flag must also name the staged file that
carries it, or the flag is a suggestion.

### Where this leaves the default

`V9K_FLOW` stays `FLO_NONE`. The evidence that turning it on is **harmless**
is now strong and internally controlled. The evidence that it **works** is
one unexplained counter. Those are different claims and only the second one
licenses a default, because a default nobody has seen function is a default
nobody will notice has stopped functioning.

**`HW_TEST_16al.md` is the sitting that finishes it**, four legs in two
adjacent pairs, written and staged: `CKPRE` against `CKERMITW` for the cost
of §1f, and `CKFCMID` (marks **1024/896**) with and without `--rtscts` for
the efficacy. The marks moved from a low mark to a **narrow band** on
purpose — 128 bytes of drain is ~62 ms against 256/64's ~93 ms repeated,
which is what disturbed the round-trip estimator — and the reading becomes
a **cap** rather than a comparison, so a retransmission cannot void it the
way it voided DB.

**Shipping build after this section:** unchanged — DGROUP **48,336 of 65,536
(73%)**, image **206,758**, **needs 220,950 (215K)**, smallest Victor 384K,
md5 `c5652a5b…`. No source change. Still **seventeen** upstream edits.

## 16al. §1f costs nothing measurable, and a leg that could not answer its question

`HW_TEST_16al.md`, second attempt — the first was lost to a full disk (§16ak,
end). Four legs, two adjacent pairs, **all four byte-exact**, `rxlost = 0`
and `rxfull = 0` throughout. **Both questions answered, one of them
negatively, and the negative is the clean one.**

| leg | binary | switch | marks | wire bytes | pkts | resends | `rxpeak` | `held/rel` | host clock | non-line |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| **GP** | `CKPRE` (**pre-§1f**) | — | — | 40,572 | 26 | 3 | 2,355 | — | 31.979 s | 21.43 s |
| **GQ** | `CKERMITW` (§1f) | — | 3072/1024 | 37,557 | 18 | **0** | 2,974 | 0/0 | 31.308 s | 21.54 s |
| **GA** | `CKFCMID` | `--noflow` | 1024/896 | 37,557 | 18 | **0** | 2,978 | 0/0 | 31.324 s | 21.56 s |
| **GB** | `CKFCMID` | `--rtscts` | 1024/896 | 37,557 | 18 | **0** | **2,974** | **11/11** | 31.459 s | 21.69 s |

"non-line" is the host clock minus the wire's own time (wire bytes ×
260 µs), which is what makes GP comparable with the rest despite carrying
3,015 more bytes.

### §16ak's +11% is withdrawn: it was the sitting, not §1f

The three clean legs, all carrying §1f, agree to **151 ms**: 31.308, 31.324,
31.459. **GP — HEAD before §1f, the binary the project measured through
§16ai — has a non-line cost of 21.43 s against GQ's 21.54.** That is
**0.11 s over 37,557 wire bytes, about 3 µs per wire byte**, well inside the
spread of the legs that share a binary and inside §16ak's 398 ms.

**And the residual bias runs the right way**, which is what makes it safe to
conclude from an off-shape leg. GP took the startup race — `pktstat.py`
reports its reconciliation as **+28, "the S packet the Victor was not yet
listening for"** — so its host clock contains dead air that nothing here
subtracts. Removing that would make GP *faster* still, and the conclusion is
that §1f is not measurable, so the uncorrected figure is the conservative
one.

**What §16ak actually saw is between sittings, and GP is the proof.**

| | binary | non-line cost |
|---|---|---:|
| §16ah leg BC | `CKPRE`, pre-§1f | **18.29 s** |
| §16al leg GP | `CKPRE`, pre-§1f | **21.43 s** |
| §16ak legs DA/DE | shipping, §1f | 21.37 / 21.38 s |
| §16al legs GQ/GA/GB | shipping, §1f | 21.54 / 21.56 / 21.69 s |

**The same binary is 3.1 s apart across two sittings**, and every leg from
the last two sittings — with §1f and without — sits together at ~21.5 s.
So §16ak's "+11%, and this data cannot say whether it is §1f" resolves to:
**not §1f.** The figure should not be quoted again.

**What moves between sittings is not the Victor.** The line time is fixed
and the 8088 does not change speed, so a 3.1 s swing in *non-line* cost is
17% of the foreground bucket — 172 ms per packet over 18 packets — and it
has to be arriving from the host side: macOS scheduling, USB latency, the
adapter. That is the same effect §16aj saw under MAME (12–15 s between two
groups) and it is now seen on the bench with the wire held constant. **It is
also the standing answer to §1 item 5b**: the bench's spread is not the
bench, it is the host, and it is why adjacent pairs work and cross-sitting
comparisons do not.

### Our RTS does not stop this host, and the leg is clean

> **RETRACTED BY §16am, the same day.** The heading and the section below
> are kept as written because the retraction is about *what the leg could
> show*, not about its numbers, and rewriting it would hide the mistake.
> `kermit -C "show features"` on the bench Mac does **not** list
> `POSIX_CRTSCTS`, so that host's `tthflow()` is the same empty function
> this port found in its own build — **`set flow rts/cts` never put
> `CRTSCTS` on the FTDI port.** The far end was never configured to stop, so
> leg GB cannot tell "our RTS does not arrive" from "nothing was listening".
> **Everything below about `rxpeak` is correct and means nothing.**

**Leg GB is the measurement §16ak's leg DB failed to be.** It is clean —
0 timeouts, 0 retransmissions, 37,557 wire bytes, 18 packets, byte-exact,
**identical to its control on every wire measure**, host clocks 135 ms
apart. The mechanism ran: `in=2 out=2 hi=1024 lo=896`, **eleven asserts and
eleven releases**, ending equal.

**And `rxpeak` came back 2,974 against the control's 2,978. Four counts.**

`mapoffset.py` puts every peak in the sitting at a packet boundary, which is
where occupancy is always highest: GB's 7 bytes into seq=09, GA's 8 bytes
into seq=08, GQ's 2 bytes into seq=14. **No cap, no shift, no effect at
all.** The Victor dropped RTS eleven times and the far end did not pause
once.

**The design change is what made the leg readable, and it is the part to
carry forward.** §16ak ran this at 256/64 and got a timeout, three
retransmissions and a `rxpeak` latched inside a resend. 1024/896 is a
*narrow band* rather than a low mark — each hold-off is 128 bytes of drain,
~62 ms, instead of 192 bytes repeated — and the reading is a **cap** rather
than a comparison. A cap survives a retransmission; a comparison does not.
**When a leg keeps going off-shape, change what you ask of it, not how many
times you ask.**

### Where the fault is not

The port's side is right as far as static analysis reaches, and that is
worth recording so the next person does not re-derive it:

- **WR5 bit 1 is RTS.** `msxv90.asm` defines `DTR_RTS_OFF EQU 7DH` as "mask
  to turn off DTR and RTS", and `REG5_7201 AND DTR_RTS_OFF` is
  `0EAh AND 7Dh = 68h` — bit 7 cleared for DTR, bit 1 for RTS. `ckvisr.asm`
  clears exactly bit 1 (`and al,0FDh`), and so does the C handler.
- **The register pointer is at 0 when the handler writes the `5`.** Entry
  reads RR0 (pointer 0), writes 1, reads RR1 (pointer self-resets), writes
  the two EOIs — `38h` is a WR0 command whose pointer field is 000 — then
  reads the data port. Nothing leaves the pointer parked.
- **The foreground copy blocks interrupts** across its own two-byte WR5
  sequence, which is the one shape §1e says needs it.

So three candidates remain and **no instrument in this tree points at any of
them**: the RTS pin does not move, the cable does not carry Victor-RTS to
host-CTS, or macOS/FTDI does not act on CTS. *(§16am establishes the third
independently of this leg, which is what retracts it.)* A host-side `TIOCMGET` watcher
against a Victor-side RTS toggler separates the third from the first two;
the logic analyzer separates the first two from each other. **Neither exists
yet and neither is on the critical path**, because the default is off and
nothing needs flow control at a window of one — but the question re-opens
the moment `DFWSIZ` or `DRPSIZ` moves.

**Note what this does NOT say.** The input half works and is proven: §16ak
leg DS put the CTS test on the transmitter's per-byte path and sent 32,768
bytes at **1,475 cps**, the fastest figure this port has produced. It is the
*output* half — our RTS, their CTS — that is inert here.

### One number is now isolated rather than explained

§16ak's leg DB reported `stall256 = 2,399` against its control's 47, and
this section was going to be where that got explained. It did not recur:
**GB is 47 and GA is 114**, ordinary. So the anomaly belongs to the 256/64
configuration specifically — where the high mark and `V9K_RXSTALL` are the
same number, 256 — and not to RTS/CTS. With GB showing no cap at all, the
reading that DB's 2,399 meant "the sender paused" is **much weaker than it
looked**, and it should not be carried forward as evidence of anything.

### Where this leaves the feature

`V9K_FLOW` stays `FLO_NONE`, and the reason has changed from *unmeasured* to
*measured*:

| | before this sitting | after |
|---|---|---|
| does turning it on cost anything? | no (§16ak DS, DE) | **no**, and §1f itself is ≤ 0.11 s on a 32 KB receive |
| does the far end stop? | unknown | **no, on this cable** |

Both mechanisms stay in the build. XON/XOFF remains the interoperability
answer and RTS/CTS remains the cheaper one wherever a cable carries it —
this bench is one cable, and the comment in `ckvictor.h` now says so with
the leg number attached rather than with a caution.

**Shipping build after this section:** unchanged — DGROUP **48,336 of 65,536
(73%)**, image **206,758**, **needs 220,950 (215K)**, smallest Victor 384K,
md5 `c5652a5b…`. The only source change is a corrected comment and the binary
is byte-identical across it. Still **seventeen** upstream edits.

## 16am. The host cannot do hardware flow control either, and that retracts leg GB

**`kermit -C "show features"` on the bench Mac lists "Hardware flow control"
and does not list `POSIX_CRTSCTS`.**

That is the whole of it. `CK_RTSCTS` is what puts "Hardware flow control" in
that list and what makes `SET FLOW RTS/CTS` a legal command;
`POSIX_CRTSCTS` is what compiles the only arm of `tthflow()` a macOS build
could take. Without it every arm preprocesses away and the function is
`int x = 0; return(x);` — **the identical empty function this port found in
its own build in §16aj and fixed by defining the symbol in `ckvictor.h`.**

So `set flow rts/cts` in the host take-files of §16ak and §16al **never put
`CRTSCTS` on the FTDI port**. C-Kermit advertised the feature, accepted the
command, and configured nothing.

### What it retracts

**§16al leg GB.** Eleven asserts, eleven releases, a clean byte-exact leg,
`rxpeak` 2,974 against its control's 2,978 — every number in it is right and
**none of it measures the Victor**, because the far end was never configured
to stop. The leg cannot distinguish "our RTS does not arrive" from "nothing
was listening", and §16am establishes the second independently. **"Our RTS
does not reach the far end's CTS" is withdrawn and goes back to unknown.**

**§16ak leg DC**, the XON/XOFF receive, is weakened the same way but was
never clean enough to carry a conclusion (19 overruns, six resends). The
host-side mechanism there is the tty's `IXON`/`IXOFF` rather than `CRTSCTS`,
and in the 11.0 source `ttpkt()`'s `TESTING234` block clears both four lines
before the `tcsetattr()` that would apply them (§16aj). **The host is
C-Kermit 9.0.302 and that source has not been read**, so for XON/XOFF this
is a strong suspicion and not the measurement `SHOW FEATURES` gives for
RTS/CTS.

And it kills the leg this project was about to run: a `--xonxoff` cap test
against a `--noflow` control **could not have worked**, for the same reason
GB did not. *That* is the useful shape of the mistake — the plan was to run
a third leg of the same experiment without ever having asked whether the far
end was capable of taking part.

### What it does NOT retract

**§16al's GP/GQ pair stands entirely.** It involves no flow control: it
measures §1f's cost at ≤ 0.11 s on a 32 KB receive and withdraws §16ak's
+11%. Nothing in this section touches it.

**§16ak leg DS stands.** The CTS gate on the transmitter's per-byte path
sent 32,768 bytes at 1,475 cps, and that half works *because* the host holds
RTS asserted by default — `set flow none` leaves it up, which is exactly why
§16v's `cts = 1` reading was evidence. The input direction never depended on
the host doing flow control.

**§16ak leg DE stands.** Turning `--rtscts` on at the shipping marks was
6 ms from its control and byte-identical on the wire. That is a statement
about cost, not about efficacy.

### The rule this is the third instance of

§16aj found `tthflow()` empty in the Victor build and `IXON|IXOFF` cleared
by `TESTING234`, and wrote down: **a line of upstream source is not evidence
that the build compiles it.** Both times the cheap instrument was `wcc -pl`.

**This is the same rule pointed at the other end of the wire**, and it took
one command — `SHOW FEATURES` is `wcc -pl` for a binary you did not build.
The generalisation is the one worth keeping: **before running an experiment
that depends on the far end behaving a particular way, measure that the far
end can.** Three bench legs and a fourth about to be scheduled went to
finding that out afterwards.

### The test is the logic analyzer, and that is a better answer than the one
### this section first proposed

The first draft of this section proposed `v9k/tools/ctswatch.py` — poll
`TIOCMGET` on the host while the Victor drops RTS — as *the* test. **It is
not the right primary instrument and the operator said so.** `TIOCMGET`
reads the modem lines at the far end of a USB cable, through an FTDI and a
kernel driver, so it answers "pin **and** cable **and** adapter" as one
lumped question. The three candidates need separating, and only a probe on
the Victor's own pins separates them:

1. the WR5 write does not reach the pin — **this port's problem**;
2. the pin moves and the cable does not carry it — **a pinout question**;
3. both fine and only the host's Kermit is deaf — **established above**.

`HW_TEST_16am.md` is the sitting, and §11a0 is the precedent: it probed
**LS153 15F pin 7** and **MC1489 14D pin 3** to settle the baud clock, so
TTL-side probing on this board is a known quantity. **Probe the TTL side**
— the µPD7201's channel A `/RTS` output, which is the MC1488's input, and
the MC1489 output that carries CTS back — because the connector side is
±12 V, outside a logic input's range.

**Probe `/DTR` alongside `/RTS`, because it is a free control.** They are
bits of the same WR5 byte written by the same instruction pair — bit 7 and
bit 1 — so "DTR moves and RTS does not" would isolate the fault to the RTS
bit specifically, and "neither moves" says the write is not reaching the
chip at all. The stimulus needs no new Victor code: `CKICP.EXE` is on the
image and `HANGUP` goes through `tcsetattr(B0)`, which is `ckvictor.c`'s
`cr5 &= 0x7d` — `msxv90.asm`'s `DTR_RTS_OFF`. Then, if that passes, capture
§16al leg GB itself: eleven assert/release pairs at transfer speed, against
a counter that already says `held = 11`.

**`ctswatch.py` stays, demoted to what it is good for**: what the *host's
driver* believes, and — with `--toggle-rts` — driving the host's RTS as a
stimulus for a probe on the Victor's **CTS input**, which needs no Kermit
and no flow control at either end. It cannot be smoke-tested without the
adapter: a pty returns `ENOTTY` for `TIOCMGET`, which it reports in those
words. Both error paths are exercised; the happy path has never run.

### And §16v's `cts = 1` is weaker than it has been quoted as

Worth writing down before the analyzer goes on, because it changes what
capture 2 is for. §16v read `cts = 1` on the real cable and this project has
carried that ever since as "the host's RTS reaches our CTS". **An MC1489
input left floating does not necessarily present as deasserted** — its
internal bias can leave the output in the active state — so `cts = 1` is
equally consistent with "the pair is wired" and with "nothing is connected
to that pin". §16ak leg DS then transferred at 1,475 cps with the CTS gate
armed, which only requires CTS to *read* asserted, not to be connected to
anything.

So the input half is **not** proven either, and one capture settles it:
drive the host's RTS with `ctswatch.py --toggle-rts` and watch the 7201's
CTS. If it does not follow, the "input half works" claim comes out too.

### And then, if the pin is fine, the host needs fixing

Two ways, in increasing order of effort:

1. **`stty -f <port> crtscts -hupcl` immediately before `kermit`.** This
   should survive: `TESTING234` clears `c_iflag` bits only and never touches
   `c_cflag`, `tthflow()` is empty so it cannot clear `CRTSCTS` either, and
   `ttraw` is seeded from the `ttold` that `ttopen()` reads. **Untested, and
   the risk is that closing the port on `stty` exit resets termios**, which
   `-hupcl` is there to prevent.
2. **Build a host C-Kermit from this tree with `POSIX_CRTSCTS`.** The tree
   is C-Kermit 11.0 and `make macosx` is a normal target. That is the honest
   fix and it is also what any future protocol-level flow-control test
   needs, because option 1 leaves the host's Kermit still believing it did
   the configuring.

Neither is on the critical path. `V9K_FLOW` is `FLO_NONE`, nothing needs
flow control at a window of one, and the question re-opens when `DFWSIZ` or
`DRPSIZ` moves.

**Shipping build after this section:** unchanged — DGROUP **48,336 (73%)**,
image **206,758**, **needs 220,950 (215K)**, smallest Victor 384K, md5
`c5652a5b…`. The only source change is `ckvictor.h`'s corrected comment and
the binary is byte-identical across it. Still **seventeen** upstream edits.

## 16an. The analyzer: our RTS works, the host is deaf, and `msleep()` does not sleep

The operator put a Saleae on the Victor's RTS line and the question three
bench sittings could not answer fell out in one afternoon. **The port's half
of RTS/CTS works.** It has been working the whole time.

**And the instrument choice is the lesson.** Every measurement this project
had made about flow control was a counter inside one of the two programs,
and both programs can be right about what they did while nothing happens
between them. §16am proposed a software watcher on the host as the way out;
the operator pointed out the obvious better answer, and it is better by more
than convenience — `TIOCMGET` reads through a cable, an FTDI and a kernel
driver and returns one lumped verdict, where a probe on the pin separates
the port from the wire from the host. **When the question is about a wire,
measure the wire.**

### What the pin does

| moment | RTS |
|---|---|
| Victor powered on, before any driver | **negative** |
| the OEM `SERIALA` driver loads | **goes positive** |
| `SET LINE`, `SET SPEED` — any chip reprogram | **drops momentarily** |
| each `HANGUP` | **drops for 175 µs** |
| **§16al leg GB, mid-transfer** | **eight pauses, 785 ms to ~1 s, most ~950 ms** |

**The eight pauses are §1f working.** The handler dropped RTS at the 1,024
water mark and the foreground raised it again at 896, on a clean byte-exact
32 KB transfer, and the pin moved every time. The counters said `held = 11`
and the capture shows eight clear ones — close enough to be the same events
and not close enough to claim they are; the short ones at the ends of the
transfer are the likely difference and nothing turns on it.

The ~950 ms hold is longer than the 62 ms this project predicted, and the
reason is that the prediction assumed the sender stops. It does not (below),
so occupancy stays high and the release does not come until the foreground
finishes decoding the packet. **The pause length is a measurement of the
foreground, not of the water marks.**

`SET LINE`/`SET SPEED` blipping RTS is expected — `tcsetattr()` resets the
channel and rewrites WR5 — and it is why §1f's `v9k_ser_setflow()` clears
`v9k_holding` on every `tcsetattr`. That was reasoned when it was written;
it is now confirmed on a scope.

### The cable carries it, and the host ignores it

Data kept arriving **for many hundreds of milliseconds after RTS went low**,
every time. So the far end did not stop — which is exactly what §16am
predicted from `SHOW FEATURES`: the bench Mac's C-Kermit has no
`POSIX_CRTSCTS`, its `tthflow()` is an empty function, and `set flow
rts/cts` never put `CRTSCTS` on the FTDI port. **Nothing was ever told to
watch that pin.**

That the *pin state* nonetheless crosses the cable is indicated by the
watcher runs, and the tell is a 25 ms separation:

```
 45.273  cts=1 dsr=1 dcd=1        the Victor's driver loads
 64.574  cts=1 dsr=0 dcd=0        dsr and dcd drop...
 64.599  cts=0 dsr=0 dcd=0        ...and cts follows 25 ms later
```

If `cts` were tied to the same far-end output as `dsr`/`dcd` it could not
lag them by a sample. It is a separate signal that tracks the Victor's
power-up and driver load in step with what the analyzer sees on RTS.
**Strongly indicated, not proven** — the watcher runs were taken during
power-up, not during a transfer, so no capture yet shows the host's CTS
moving at the moment the Victor's RTS does. **One capture closes it: a
second probe on the CTS conductor at the Mac end during a `STEPGB` run**,
with the first probe still on the Victor's RTS. Both ends of one wire, one
trace.

### So the three candidates are down to one, and it is not ours

| candidate | verdict |
|---|---|
| the WR5 write does not reach the pin | **dead.** The pin moves — HANGUP, chip reprogram, and eight times mid-transfer |
| the cable does not carry RTS→CTS | **strongly indicated dead**, one two-probe capture from certain |
| the host does not act on CTS | **this is it**, and §16am already had the mechanism |

**`ckvictor.h`'s comment is corrected again.** It has now said, in order,
"unmeasured", "measured not to work", "never tested", and finally what the
scope says: **the port's half works and the harness's half does not.**
Three of those four were written from software counters.

### `msleep()` does not sleep, and the 175 µs is how we know

`tthang()` is `tcsetattr(B0)` → `msleep(HUPTIME)` → `tcsetattr(restore)`,
and `HUPTIME` is **500 ms**. The capture says **175 µs**.

`msleep()` in `ckutio.c` has arms for `select()`, `nanosleep()` and
`usleep()`; this build has none of them, so it compiles the fallback:

```c
if (m >= 1000) { sleep(m/1000); m %= 1000; if (m < 10) return(0); }
if (m > 0) while (m > 0) m--;              /* an empty decrement loop */
```

For any `m` under 1000 that is a loop with no side effects on a local
variable, which `-os` is entitled to delete outright — and 175 µs says it
did, or came close. **`msleep()` is a no-op below one second on this port.**

Two shipped things depend on it and both are broken:

- **`tthang()` cannot hang up a modem.** DTR and RTS drop for microseconds
  instead of half a second. No modem has ever been on this bench, which is
  why nothing noticed.
- **`tcsendbreak()` does not send a break.** `ckvictor.c` §1b sets WR5 bit
  4, calls `msleep(duration > 0 ? duration : 275)`, and clears it again —
  so the break is as long as two IOCTL round trips. POSIX says a zero
  duration means *at least* a quarter second. **This is the port's own
  code and it is wrong**, and it has never been exercised.

**The fix is the port's, not upstream's**, and it runs into hard rule 6:
INT 21h only, and the only clock INT 21h offers is `AH=2Ch`, which on this
machine advances in **500 ms steps** (§16n). So sub-second delays need a
busy loop calibrated once against `AH=2Ch` — the same shape as any
1980s-era delay routine, and the honest place for it is `ckvictor.c` §1d
alongside the other Watcom gaps. Not done here; recorded, with the
measurement that found it.

**This is the second time an instrument aimed at one thing found something
else entirely.** §16y's parser switch found four latent stubs; a scope
aimed at RTS found a delay function that does not delay. Both were latent
for the port's whole life and neither was reachable by the tests in front of
them.

### The tool had real defects and they were the operator's to trip over

`v9k/tools/ctswatch.py` was run four times in watch mode and reported
`dtr=1 rts=1` in a column headed "outputs (this end)", which reads as *this
program is asserting these* when it means *the driver reports these*. The
`--toggle-rts` stimulus was never invoked, so capture 2 never happened, and
the tool said nothing about the fact that it was driving nothing. Fixed:

- an explicit `MODE:` banner — `WATCHING ONLY -- this run drives nothing`;
- the column is now `this end (read back)`, with a note that **opening the
  port makes macOS assert DTR and RTS by itself**, which the Victor sees as
  CTS — that is almost certainly what "when I launch python CTS asserts"
  was, and if so it is *also* evidence the inbound pair is wired;
- `--toggle-rts` now polls the inputs *while* it holds each level and reads
  back what it drove, so the mode evidences itself instead of asserting it;
- "CTS never moved" no longer prints as a finding when nothing was driven.

**A watcher that cannot tell you it was only watching is not an
instrument.**

### Where this leaves the default

`V9K_FLOW` stays `FLO_NONE`, and the argument has changed shape completely.
It was chosen because gating the transmitter on an unmeasured CTS risked
turning a working port into a silent one. **That risk is retired**: the pin
moves, the pair is all but certainly wired, and §16ak leg DS already sent
32,768 bytes at 1,475 cps with the gate armed. What is missing now is the
*benefit* — no far end has ever been shown to stop, because the only far end
tested cannot.

So the default waits on the host, not on the port:

1. **`stty -f <port> crtscts -hupcl` immediately before `kermit`.** Untested,
   free to try, and now much more likely to be worth trying: `TESTING234`
   clears `c_iflag` only, an empty `tthflow()` cannot clear `CRTSCTS`, and
   `ttraw` is seeded from the `ttold` that `ttopen()` reads.
2. **A host C-Kermit built from this tree with `POSIX_CRTSCTS`.**

Either one, plus one re-run of §16al legs GA/GB, and `rxpeak` finally caps
or does not for a reason that is about the Victor.

**Shipping build after this section:** unchanged — DGROUP **48,336 (73%)**,
image **206,758**, **needs 220,950 (215K)**, smallest Victor 384K, md5
`c5652a5b…`. Still **seventeen** upstream edits.

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

- ~~**`REMOTE DIRECTORY` streams its listing and never terminates it.**~~
  **RETRACTED BY §16aw — this run was `-d`, and `nxtdir()` debugs four times
  per output character.** With the log shut the same command lists a
  157-file root in 31.077 s, terminating Z included. The observation as it
  stood: all 51
  entries of `A:\` arrive correctly and each D packet is ACKed; the Z never
  comes, the host times out and discards the transaction, and — the part
  that costs a run — the host then never sends the FINISH that would have
  closed the server, so the Victor's `DEBUG.LOG` is never flushed. `snddir()`
  is C-Kermit's own internal lister, so this is inside upstream's file-send
  path. Not diagnosed. It is enabled by default; `--safe-server` refuses it
  cleanly and the session survives. (§16i)
- ~~**Most of the default capability set has never been exercised.**~~
  **Done — §16ax put all of it on the wire.** Six legs under MAME at 9600.
  Working: PWD, CD, MKDIR, RMDIR, DIRECTORY, TYPE, COPY, RENAME, DELETE,
  RETRIEVE, SET, MESSAGE, HELP, SPACE, EXIT and **BYE**, so FINISH is no
  longer the only way the far end can stop a Victor server. Refusing
  cleanly and correctly: HOST (NOPUSH), QUERY and ASSIGN (NOSPL), PRINT
  (refused in the A-packet ACK, so the file is never created), LOGIN, and
  WHO. `--safe-server` verified on the wire for the first time — DIRECTORY,
  DELETE, CD, MKDIR, TYPE and EXIT all refused by name while GET still
  works. Three defects came out of it and all three are fixed: SPACE and
  WHO were advertised while `NOPUSH` made them impossible (SPACE now
  answered by upstream edit 20, WHO now honestly disabled), `REMOTE RMDIR`
  could not remove a directory at all, and every date the server reported
  was truncated to 1970 (upstream edit 19). Still untested: `REMOTE
  STATUS`, which the 9.0.302 host has no command for, and `en_ena`/`en_ret`,
  which this build has no reader for. (§16ax)
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
  to load was long cited here as proof. **§16x retracts the 387K** -- it was
  FreeDOS's, MS-DOS 3.1 gives 805K at 896K, and the parser build is blocked
  by DGROUP and `ckvisr.asm` instead. The ceiling is still real and still
  the thing to watch, but it is `free = installed RAM - 92,720` and the
  binding case is the **384K floor machine**, not the 896K bench.
  Re-measure there, not in DGROUP, before raising
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
- ~~Why does the receive path overrun at 38400?~~ **Answered, and fixed
  (§16t): the cost of our own interrupt handler.** At 260 µs a byte the C
  handler was taking about twice that, of which ~123 µs was Open Watcom's
  twelve-register `__interrupt` prologue and the `DS` reload it does per
  port access. `ckvisr.asm` replaces it — 110 instructions against 185, ten
  stack operations against twenty-four, two segment loads against nineteen —
  and 38400 now runs `rxlost = 0` with zero NAKs and zero retransmissions,
  identical to a clean 19200 run in every protocol measure. Ruled out along
  the way and worth not re-testing: the file writes (§16p, and §16s put a
  floppy with 1.5-second writes under it and lost nothing), the ring
  (`rxfull = 0` throughout), every `V9K_CLI()` in `ckvictor.c`, and the
  other half of the µPD7201 sharing IRQ1 (`norx = 0, othrx = 0` at two
  rates, §16t). Three of the four sessions spent on this were misdirected by
  a byte time that was wrong by 10× and by §16r's false dichotomy; both are
  written up in §16t because the reasoning errors are more reusable than the
  fix.
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
  same retransmission would produce there — **which §16p confirms exactly:
  `rxpeak` at 38400 measured 2,009 and 2,098.** (§16m) **Revised to 9.8 s
  and ~1,630 cps by §16n**, and then **half of §16n's disk arithmetic was
  retracted by §16p**: on the real drive the write cost tracks bytes rather
  than calls, so `V9K_OBUFSIZE = 8192` saves about half a second per 32 KB
  and not four. The dead-time projection itself is **still untested** —
  §16p's runs were about `rxlost` and no elapsed time was recorded. One
  38400 run with a stopwatch closes it, and it should now be expected to
  come in *worse* than ~1,630 cps because 0.45% byte loss buys a
  retransmission storm on top. (§16o, §16p)
- ~~**One timeout and two retransmissions survive in a clean 32 KB run.**~~
  **Diagnosed, and not ours** — **under MAME only; §16o retracts the "never
  a NAK" half on hardware**, where the Victor NAKed three packets in one
  transfer. The roundup was made and is right, but the
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

## 16ao. The port had no file-transfer display at all, and now it has the fullscreen one

**Validated on real hardware at 38400, both directions, 10 August 2026.**
Receiving and sending, the display is correct and the progress bar tracks
the transfer's actual duration. Before this section `CKERMITW` showed
**nothing at all** during a transfer — not a percentage, not a dot, not a
packet type — on any build, in either direction, for the port's entire
life.

### What was wrong, and why four correct-looking explanations came first

`ckvictor.h` defined `NOCURSES`, meaning "there is no curses library here",
which is true. `ckcdeb.h:6098` turns `NOCURSES` into **`NODISPLAY`**, and
`ckcker.h:730` then makes **both** `xxscreen()` and `ckscreen()` expand to
nothing:

```c
#ifdef NODISPLAY
#define xxscreen(a,b,c,d)
#define ckscreen(a,b,c,d)
#endif
```

Upstream conflates "no curses" with "no display of any kind" — the CRT and
SERIAL modes need nothing but `write()` and go with it.

**The chain of investigation is the part worth keeping, because every step
of it was sound and none of it was the answer.** `ckscreen()` has four
runtime gates and each was checked in turn on the machine:

| gate | where | verdict |
|---|---|---|
| `fdispla != XYFD_N` | `ckuusx.c:381` | XYFD_S — fine |
| `local` | `ckcker.h:739`, and again in `rpack()`/`spack()` | **1** — `SHOW COMMUNICATIONS` printed `mode: local` under MAME |
| `!backgrd` | `ckcker.h:739`, `ckuusx.c:4641` | **0** — `conbgt isatty test=1` in a `-d` log |
| `displa` | `ckuus6.c:11649`, `ckuusr.c:5440` | follows `local`, so 1 |

All four passed and the screen was still blank, because **there were no call
sites for them to gate**. `wcc -pl` settled it in one second:

```c
    if (x)
       ;                    /* this was xxscreen(SCR_PT,pkttyp,n,mydata) */
```

`ckscreen` appears **zero** times in the preprocessed `ckcfn2.c`.

**§16aj's rule, learned again and more expensively: a line of upstream
source is not evidence that the build compiles it.** §16aj applied it to
`tthflow()` and §16am to the far end of the wire; here it cost a chain of
four runtime hypotheses, one bench sitting and three MAME legs before anyone
preprocessed the file. **Ask the preprocessor before you ask the machine —
it is faster and it cannot be misread.**

**Two `backgrd` findings survive as facts about this port even though
neither was the cause.** `conbgt()` sets `backgrd = 1` whenever
`isatty(0) && isatty(1)` is false (`ckutio.c:9643`), and the port's
`getpgrp()`/`tcgetpgrp()` stubs both return 1 so the process-group test
contributes nothing. **Every bench leg in this project's history redirects
stdout to `STEP<LEG>.OUT`**, which sets that flag — so even after this
section, *the display does not run on an instrumented leg*. That is
upstream's intent and is correct; it means a throughput leg and a display
leg cannot be the same leg. The first diagnostic run was itself lost to
this: `CKICPD -d -h > output.log` set the exact variable under test, and
`-d` writes its log to disk anyway so the redirect was never needed.
**A diagnostic must not change the thing it measures.**

### The Victor is VT52/Z19, not ANSI, and that was not obvious

Removing `NOCURSES` gets `fdispla = XYFD_S` — the one-line CRT display
(bytes, percent, CPS, packet length, repainted from column 0). That works,
and it is **a regression against MS-DOS Kermit 3.13 on this same machine**,
which has the fullscreen display. So the target is `XYFD_C`.

The console's dialect is **DEC VT52 with Heath/Zenith Z19 extensions**, and
it does **not** interpret ANSI CSI sequences:

| operation | sequence |
|---|---|
| cursor to (row, col) | `ESC Y (row+0x20) (col+0x20)` |
| erase whole screen, home | `ESC E` |
| erase to end of screen | `ESC J` |
| erase to end of line | `ESC K` |

The Victor *Supplementary Technical Reference Manual* says so directly —
"the set of escape sequences is designed to be very similar to a DEC VT52
terminal … some of the more fancy features are borrowed from a Heath Z19
terminal" — but **the conclusive evidence is `msyv90.asm`**, MS-DOS Kermit's
Victor screen driver: it is a VT100 emulator whose entire job is
**translating incoming ANSI into these sequences** (`ESC[r;cH` → `ESC Y` at
`:1322`, `ESC[2J` → `ESC E` and `ESC[0K` → `ESC K` at `:1626-1751`). A
console that understood ANSI would not need that table.

**Hard rule 6 is not in conflict, and that was genuinely uncertain going
in.** The worry was that 3.13 could show this display only because
`msyv90.asm` is a screen driver with the hardware to itself. It is not so:
`msxv90.asm:1100` (POSCUR) writes `ESC Y` with `AH=09h` and the two
coordinate bytes with `AH=02h`, `CMBLNK` sends `ESC E`, `CLEARL` sends
`ESC K`. Direct writes to the `F000:0` screen array exist in `msyv90.asm`
only for the Tektronix bitmap. `vickermit.c:195` does the same in C.
**The fullscreen display costs no BIOS call, no screen memory and no INT
10h.**

### Why upstream's own do-it-yourself curses could not be used

`ckuusx.c:6732` already carries `MYCURSES`, which is nothing but three
`printf`s of escape sequences and even has a VT52 arm. Two independent
things make it unusable here:

1. **`ckuusx.c:6237` is `#define isvt52 0` for every non-VMS build**, so the
   VT52 arm is unreachable and the ANSI arm is what compiles.
2. **That arm is off by one anyway**: `ESC Y (row+037) (col+037)` is +31
   applied to `move()`'s 0-based coordinates, where the Victor wants +32.
   `vickermit.c` gets away with +31 because *its* coordinates are 1-based.

So the port supplies its own, using the mechanism it already uses for
`termios.h` and `sys/ioctl.h`: **`victorow/curses.h`** declares the surface
and **`ckvictor.c` §1g** implements it. The surface is small — `screenc()`
uses `move` 55 times, `printw` 68, `refresh` 11, `clrtoeol` 11, and that is
all. `initscr`/`endwin`/`touchwin`/`clearok` are no-ops because there is no
off-screen image; upstream's own `MYCURSES` makes the same four no-ops,
which is the check on that reasoning.

**No upstream edit. Still seventeen.**

### Two upstream blocks had to be worked around, and both are report items

- **`fxdinit()` gates the display on a termcap probe it does not need**
  (`ckuusx.c:6372`). It reads `getenv("TERM")`, and if empty sets `x = 0`
  *without calling `tgetent()` at all*, prints "Warning: terminal type
  unknown" and "Fullscreen file transfer display disabled", and drops
  `fdispla` to `XYFD_S`. DOS sets no TERM, so that branch is taken every
  time — in a build whose curses never consults a termcap, since
  `ck_termset()`, the only consumer, is called four lines below under
  `#ifndef MYCURSES`. Worked around with a `tgetent()` stub (§1g — it is
  also the only symbol the fullscreen path leaves unresolved at link) and a
  `putenv("TERM=victor")` beside the `_fmode` initializer.
- **`ckuusx.c:7070` does not compile.** `ck_curpos(row, col) int row, int
  col;` is not valid K&R — the second `int` is a syntax error. Every other
  configuration reaches `CK_CURPOS` through termcap or `MYCURSES` first, so
  **nothing has ever built that block**. `ckvictor.h` defines `CK_CURPOS`
  and §1g supplies `ck_cls`/`ck_cleol`/`ck_curpos` in VT52 — which is wanted
  regardless, since that fallback emits ANSI at a console that cannot read
  it.

### The bug this section made, and it is a general one

The first build put every field on screen **correctly and concatenated onto
two lines**. `printw` is `printf`, buffered by Watcom's stdio; `move()` and
`clrtoeol()` go through `conol()` → `write()`, unbuffered. **Two output
paths to one console**, so every `ESC Y` overtook the text it was meant to
place. Fixed with `fflush(stdout)` before each escape sequence and in
`refresh()` — which is what refresh *means* here: not "repaint from an
image", there is no image, but "get the buffered half out".

The comment in the first draft claimed the single output path made ordering
safe. It was wrong because only three of the four calls were on it. **When
a design argument rests on "everything goes through one path", enumerate
what everything is.**

### Numbers

| | before | CRT (`XYFD_S`) | **fullscreen (`XYFD_C`)** |
|---|---:|---:|---:|
| DGROUP | 48,336 (73%) | 48,592 (74%) | **48,736 (74%)** |
| image | 206,758 | 216,070 | **225,638** |
| needs at load | 220,950 (215K) | 231,174 (225K) | **239,702 (234K)** |
| smallest Victor | 384K | 384K | **384K, unchanged** |

18 warning lines, **none in `ckvictor.c`**. The display costs **18,880
bytes of image and does not move the smallest machine it can run on**,
which is the figure that matters (§16x).

**`v9k: wcon` is the instrument, and it is unambiguous**: `n=0` before,
`n=31` with the CRT display, **`n=485 tot=450 cs`** with the fullscreen one
on a 32 KB receive — 4.5 s of console writes in 119 s, **3.8%**. It works
because `ckvictor.h`'s `#define write v9k_write` renames the call in
C-Kermit's sources but not inside Watcom's libc, so `conol()` is counted and
`printf` is not.

### What is measured and what is not

**Measured under MAME at 9600:** a 32,768-byte receive, md5
`315a5931…` identical both ends, `rxlost=0 rxfull=0 rxpeak=368 of 4096`,
the full screen with `Percent Done: 35 /////////////////-` and the
`...10...20...30` scale, `Last Message: SUCCESS. Files: 1, Bytes: 32768,
442 CPS`.

**Measured on real hardware at 38400:** both directions, display correct,
progress accurate to the transfer's duration. **Counter readings were not
captured on the hardware legs and cannot be**, because the display and the
`.OUT` redirect are mutually exclusive (see the `backgrd` note above). So
the hardware result is an operator observation of a *display*, which is the
right kind of evidence for it, and the wire-level figures behind it are
MAME's.

**Not measured here: what the display costs at 38400. §16ap measured it —
4.188 s receiving and 5.035 s sending, and the cost is a constant rather
than a fraction.** At 9600 the foreground has ~555 µs of slack per byte and
at 38400 it has none (§16ag), so 3.8% at 9600 was not transferable as a
percentage, though the 4.5 s behind it was. The specific exposure is the `fflush()` in
`move()`: 55 cursor addresses per repaint now sit on the same foreground
path §16v measured at 485 µs per wire byte. One paired leg — same fixture,
`CKPRE`-style control against `CKDISP` — would settle it, and it needs the
screen photographed rather than redirected.

**A difference between the two DOSes, and it is this port's first.**
FreeDOS-for-Victor's `kernel/victor_ansi.asm:141` parses only `ESC [` and
passes everything else through, so these sequences will render as noise
there. The fallback to `XYFD_S` exists and is automatic whenever the
fullscreen display is unavailable, but **nothing detects the case**. Either
`victor_ansi.asm` grows a VT52/Z19 layer, or the port detects the DOS and
picks a dialect, or FreeDOS gets the CRT display. §1 item 14.

## 16ap. What the display costs: a constant, not a fraction

`HW_TEST_16ao.md`, eight legs, 10 August 2026. **All six received files
md5-identical to the fixture, `rxlost = 0` and `rxfull = 0` on every leg.**

The control is the same binary as the treatment. `xxscreen()` tests
`!backgrd` at runtime and `conbgt()` derives `backgrd` from `isatty(0) &&
isatty(1)`, so **redirecting stdout turns the display off with no code-size
difference at all** — §16w has nothing to act on for the first time in this
project's history. `wcon n=1` on all four control legs and 331–514 on all
four display legs is the check that the variable did what was intended.

| leg | dir | rate | display | wire | pkt | rs | host clock | non-line |
|---|---|---:|---|---:|---:|---:|---:|---:|
| HA | recv | 38400 | off | 37,557 | 18 | 0 | 31.568 | **21.803** |
| HB | recv | 38400 | **on** | 37,557 | 18 | 0 | 35.965 | **26.200** |
| HC | recv | 38400 | off | 40,544 | 25 | 2 | 32.655 | **22.114** |
| HD | recv | 38400 | **on** | 37,557 | 18 | 0 | 35.857 | **26.092** |
| HE | send | 38400 | off | 37,557 | 18 | 0 | 22.283 | **12.518** |
| HF | send | 38400 | **on** | 37,557 | 18 | 0 | 27.318 | **17.553** |
| HG | recv | 9600 | **on** | 46,769 | 30 | 4 | 68.979 | **20.339** |
| HH | recv | 9600 | off | 39,564 | 24 | 1 | 57.091 | **15.944** |

### The headline

**Receive at 38400: the display costs 4.188 s, against a control spread of
0.310 s — 13.5× the noise.** That is 13.0% of a 32 KB transfer. Send costs
5.035 s (22.6%) on the best-matched pair the harness can produce: HE and HF
are **byte-identical on the wire**, 37,557 both, 18 packets, zero
retransmissions each. Receive at 9600 costs 4.395 s (7.7%).

**The three numbers to read together are 4.188, 5.035 and 4.395 — and the
point is that they are the same number.** The display costs about
**4–5 seconds per 32 KB transfer regardless of line rate**, because it is
console-write time and console writes do not care what the serial port is
doing. The percentages differ only because the denominator does: the
faster the transfer, the larger the fraction.

**So §16ao's "3.8% at 9600 under MAME does not transfer" was right for the
wrong reason.** MAME measured `wcon tot = 450 cs`; hardware measures
4.2–5.0 s. **The absolute transferred perfectly; only the percentage did
not**, because MAME's transfer took 119 s where the bench takes 31. This
is the fourth time in this tree a percentage has travelled worse than the
absolute it came from. **Quote the seconds. The percentage is a property of
the denominator.**

### Safety: it does not touch the ring

Decision rule 2 passes cleanly. `rxfull = 0` and `rxlost = 0` on all eight.
On the four legs comparable by §16ag's rule — same retransmission count —
`rxpeak` is **3,032 with the display off (HA) against 2,975 with it on (HB
and HD, identical to each other)**. The display leg is 57 bytes *lower*, so
there is no ring pressure to find; painting happens after the ACK, when the
line is idle, the same reason §16s's floppy cost nothing.

Worth noting in passing: HA's 3,032 of 4,096 is higher than §16af's
published 2,581 and leaves 1,064 bytes of margin. Different sitting, both
clean, and nothing is pressing on it — but 2,581 is not the standing figure
it was.

### What it licenses, by the rule written before the legs ran

`HW_TEST_16ao.md`'s decision rule said **≥ 5% licenses a `--nodisplay`
switch** through §16i's priority-0 XI mechanism. 13.0% receiving and 22.6%
sending are over that, so the rule fired. **`--nodisplay` is built, and it
is `ckvictor.c`'s fourth command-tail switch after `--safe-server`,
`--rtscts`/`--xonxoff`/`--noflow`.** No upstream edit; +184 bytes of image
(225,638 → **225,822**), DGROUP unchanged at 48,736, **smallest Victor
still 384K**.

It writes `fdispla = XYFD_N`, which the `xxscreen()` macro tests *before*
`ckscreen()` is called, so the display costs one compare per packet when it
is off. **§16ai's trap was checked rather than assumed**: every other
writer of `fdispla` in this build is a static initializer, inside
`fxdinit()`, or in the parser — and `fxdinit()` is itself unreachable once
`fdispla` is `XYFD_N`, because its only live caller is `ckscreen()`
(`ckuusx.c:4629`) behind that same macro gate, and the three in `ck_cls()`
and friends are in the `#ifndef CK_CURPOS` region §1g excludes.

**Verified under MAME at 9600**, no redirect, `--nodisplay` on the command
line: 32,768 bytes byte-exact, `rxlost = 0 rxfull = 0 rxpeak = 305`, no
display on screen, and **`wcon n = 1`** — against `n = 514` on §16ap's own
leg HG, the same rate and direction with the display on. **The
unknown-option control was run** per §16i's rule: `CKDISP --nodisplaz -h`
answers `Extended options not configured`, so `--nodisplay` being accepted
means the switch was recognised and not merely ignored.

**`CKDISP … > NUL` was already a way off and remains one.** The display is
suppressed whenever stdout is not a terminal, which is exactly what arm A
of this sheet was. What the switch adds is suppressing the display **while
keeping stdout on the console**, so the `v9k:` counters and any error still
reach the operator — which a redirect takes away and which MS-DOS 3.1
cannot give back, since it will not redirect handle 2.

**A consequence worth writing down: `--nodisplay` makes the display leg and
the throughput leg the same leg again.** §16ao's constraint — that an
instrumented run cannot show the display and a display run cannot be
instrumented — was a property of using the redirect as the switch. It is
now only true of the redirect.

**What should NOT be done is `-dNOCURSES`.** It deletes the CRT display as
well and changes code size by 18,880 bytes, which puts §16w back in play —
the whole reason this sheet's control was a redirect and not a rebuild.

### Leg HJ: `--nodisplay` reproduces the redirect's control on the machine

Run after the switch shipped, on the bench at 38400, against leg HB's own
take-file. **Byte-exact** (`RCVHB.DAT` md5 `d94d2beda…`), `rxlost = 0
rxfull = 0`, `wcon n = 1` **with no redirect** — the command line is
`CKERMITW --nodisplay -l /dev/seriala -b 38400 -r` and nothing appeared on
screen between it and `Closing /dev/seriala`.

Four legs at 38400 receive, and **all four carry 37,557 wire bytes in 18
packets with zero retransmissions** — the tightest set this project has:

| leg | display off by | host clock | cps |
|---|---|---:|---:|
| HA | redirect | 31.568 | 1,038 |
| **HJ** | **`--nodisplay`** | **30.960** | **1,058** |
| HB | *display on* | 35.965 | 911 |
| HD | *display on* | 35.857 | 913 |

**HJ and HA are 0.608 s apart, and both are ~5 s from the display legs.**
So the two ways of switching the display off produce the same control, and
the switch does not add a cost of its own. Against HJ the display costs
**4.951 s**; against HA, 4.343 s; §16ap's published figure, which includes
off-shape HC by non-line cost, is 4.188 s. All three are the same answer.

`rxpeak` is worth a second look now there are four matched legs: **2,974
(HJ, off), 2,975 (HB and HD, on), 3,032 (HA, off)**. HA is the outlier and
the display is not — three of the four sit within one byte of each other
regardless of whether the screen was being painted. §16ap's "no ring
pressure" conclusion is stronger than the two legs it was drawn from.
`peaktag` splits the same way: 12 on HJ, HB and HD, 6 on HA.

**One harness cost, and it is a rule this project already had for MAME.**
HJ re-used `s16aoHB.ksc`, so `> s16aoHB.host` overwrote leg HB's host file
and `log packets s16aoHB.pkt` truncated its packet log — both are
`.gitignore`d, so **leg HB's original artefacts are gone.** Its figures
survive only because they were written into this section. §6 already says
"one `kermit` attempt per MAME run, unique log names — `log packets`
truncates"; it applies at the bench too, and this is the first time it has
bitten there. **A re-run gets a new leg letter, not the old one.**

### A new caveat on an old instrument: `wcon tot=` is unbiased and very noisy

HB and HD are protocol-identical legs 108 ms apart on the host clock, and
their `wcon tot=` readings are **350 cs and 600 cs**. That is not
measurement error, it is the 0.5 s clock quantum (§16n): each console write
is far shorter than a tick, so `v9k_centis_since()` returns 0 unless the
write happens to straddle one, in which case it returns 50. `tot` is
therefore a sum of 0-or-500 ms samples.

The estimator is **unbiased** — a write of duration *d* straddles with
probability *d*/0.5 s and contributes 0.5 s, so E[tot] = *n·d*, the true
total — but its standard error is 0.5 s × √(straddles), which is ±1.3 s on
seven of them. Over the four display legs (350, 600, 450, 700) the mean is
**5.25 s**, against 4.19–5.04 s from the clock. **The two instruments
agree, and they are genuinely independent.**

**The rule: `wcon n=` is exact and `wcon tot=` is ±1.5 s on a single leg.**
Quote `n`; average `tot` over at least four legs or do not quote it. The
same applies to `wfile tot=` and `txgap tot=`, which are built the same way
— §16n's "quote `tot=`, never `max=`" was right and incomplete.

### Two smaller things

**HE at 1,470 cps is within 5 cps of the port's fastest figure ever**
(§16ak leg DS, 1,475). It is a send with the display off, which is the
fastest thing this port does.

**HC and HG went off-shape** — 2 and 4 retransmissions — which is 2 of 8,
consistent with §16ah's "expect roughly a third". Non-line cost made both
usable, which is the third sitting in a row where that method has earned
its place.

---

## 16aq. Upstream edit 18: the bulk-read arm, and the largest single gain this port has measured

**17.6% faster and 6.4× less ring pressure, on three clean legs per arm with
a 16 ms noise floor.** This is the biggest throughput result in the port's
history and the measurement is the least ambiguous one it has produced.

### What the edit is

`ttinl()`'s per-byte loop walks the packet a byte at a time through the
`myread()` macro. Edit 18 adds an arm at the bottom of that loop which finds
the terminator in the already-buffered run with `memchr()` and copies the run
with `memcpy()`. On a 5 MHz 8088 that matters because `repne scasb` and
`rep movsw` **do not refetch**, and §16w established that instruction fetch
at ~4 clocks a byte is what bounds this machine. The library routines were
checked rather than assumed — `memchr` is `repne scasb`, `memcpy` is
`shr cx,1 / rep movsw / adc cx,cx / rep movsb` — and they are far *calls*,
once per run, amortised over the whole run.

Full description, gate and proof: §8 item 18.

### The result

Six legs, three per arm, every one clean shape — 18 packets, 37,557 wire
bytes, 0 timeouts, 0 retransmissions, 0 damaged packets, byte-exact.

| leg | arm | host clock | cps | `rxpeak` | `bulk n` | run len |
|---|---|---:|---:|---:|---:|---:|
| KA | bulk on | 25.668 s | 1,277 | 481 | 243 | 154.6 |
| KC | bulk on | 25.652 s | 1,277 | 488 | 249 | 150.9 |
| KN_2 | bulk on | 25.659 s | 1,277 | 409 | 243 | 154.6 |
| KD | `--nobulk` | 31.137 s | 1,052 | 2,748 | — | — |
| KP_1 | `--nobulk` | 31.137 s | 1,052 | 3,035 | — | — |
| KP_2 | `--nobulk` | 31.146 s | 1,052 | 3,055 | — | — |

- **5.480 s, 17.6%.** Within-arm spread 16 ms and 9 ms, so the effect is
  **343× the floor**.
- **The arms do not come within 5.469 s of touching.** Arm B's worst leg
  beats arm A's best by more than the whole effect. There is no leg-selection
  question to argue about.
- **Non-line cost 15.895 s against 21.375 s — a 25.6% reduction** in the
  foreground work §16v identified as the bottleneck.
- **`rxpeak` 459 against 2,946 — 6.4×**, on legs with identical
  retransmission counts, so §16ag's comparability rule is satisfied.
- **1,277 cps is the port's fastest receive figure**, against §16ah's 1,167.

### Why MAME could not see it, and why that was predictable

Legs JA and JB (9600, MAME) read `elapsed = 10,350 cs`, **identical**, with
`bulk sel=1 n=3441` against `sel=0 n=0`. Two reasons, and both were written
into `HW_TEST_16aq.md` before the bench legs ran:

1. **§16ag's structural point, for the third time.** At 9600 the foreground
   has ~555 µs of slack per byte and at 38400 it has none.
2. **Mean run length was 11.9 bytes**, because `rxpeak` was 303 of 4,096 —
   the ring never filled, so `myfillbuf()` returned tiny chunks and there was
   nothing for `rep movsw` to amortise over. At 38400 the same figure is
   **151–204 bytes**, 13–17× larger.

**Mean run length (`rxbytes / bulk n`) is the mechanism variable and it
transfers where the seconds do not.** It predicted the direction and rough
size of the bench result from a MAME leg that measured no difference at all.

### The sixth hand-costed 8088 prediction, and the first to be wrong low

§16af's ~133 µs per wire byte for `ttinl()`'s loop predicted ~3.5 s and ~13%.
The measurement is 5.48 s and 17.6%. That is the **sixth** such prediction in
this tree and the sixth to be wrong; it is the first to be wrong in the
useful direction. §16af's "ordering arguments, never magnitudes" stands, and
§16ag's downgrade of it — not reliable for ordering either — is not
contradicted here only because the ordering happened to hold.

### The structural consequence: the ring is no longer under any pressure

`rxpeak` at 459 of 4,096 leaves ~3,600 bytes of margin on a clean receive,
where §16af left 1,515. **That is the constraint item 12 was waiting on.**
Windows were gated on ring margin — open the window and the sender no longer
stops after every packet, so the ring must absorb a whole packet of backlog —
and there is now room for it. Line and foreground are still strictly
serialized at `DFWSIZ = 1` (9.77 s + 15.90 s), so overlapping them is worth
more than this edit was.

**One reading that confirms §16m from a new direction.** On the two off-shape
legs, which each took 1 timeout and 2 resends, the arms nearly converge —
`rxpeak` 2,285 (bulk) against 2,569 (`--nobulk`). A faster foreground cannot
help there, because with a window of one the peak measures **the host's
retransmission burst**, the only moment it transmits without waiting for our
ACK. That is §16m's finding, seen through an instrument built for something
else.

### The send direction: inert, as predicted

Leg KS sent 32,768 bytes by name at 38400: byte-exact, **1,471 cps** against
§16ai leg CC's 1,475 — the port's fastest — so no regression. `bulk sel=1
n=18` over 208 ACK bytes, **11.6 bytes per run**. `ttinl()` is the packet
*reader*, so on a send leg it sees only the ACK stream and the arm has
nothing to work on. The sheet named a large `n` here as the result that would
have invalidated its own reasoning; it did not appear.

### Part 3 was attempted and the stimulus did not fire — the question is open

Legs KN and KP were to run bulk and `--nobulk` over a 10-foot cable wrapped
around mains wiring, to test the one claim `vttinl.c` cannot reach: that the
two arms recover from corruption identically. **Both legs came back at 37,557
wire bytes in 18 packets with zero crunched packets, zero timeouts, zero
resends and `rxlost = 0`** — the clean shape, on both arms. The noise did not
happen.

**This is an instrument failure, not a null result, and it must not be
written up as one.** The prediction — that corruption makes no difference
between the arms, because neither reads a length — remains untested.

The probable cause is physics: magnetic coupling goes with **current**, not
voltage, and house wiring with little load drawn through it radiates almost
nothing. A switching load cycling beside the cable is a stimulus where
proximity to quiet wiring is not. A bit-flipping shim between `kermit` and
the FTDI would hit the corrupted-terminator path deterministically, at the
cost of no longer being real-world noise.

**§16am's rule applies again and this is its third outing: before running an
experiment that depends on something happening, measure that it can happen.**
Verify the stimulus moves the error counters before spending a matched pair
on it.

### Harness notes, both about names

**A re-run under an old leg letter destroyed artefacts, exactly as
`HW_TEST_16aq.md` §0 item 5 says it would.** KN and KP were re-run under
their own names once the cable turned up. `s16aqKN.pkt` (run 1) and
`s16aqKP.pkt` + `s16aqKP.host` (run 1) are gone. Run 1's KP host clock,
31.137 s, survives only in `v9k/legs/README-KN-KP.md` and here. Worse than
the loss: `s16aqKN.host` (run 1, 08:55) sat next to `s16aqKN.pkt` (run 2,
11:43) with matching names and a three-hour gap, and read as a pair they
describe a leg that never happened.

**And the naming that avoided a loss caused a different error.** Run 2's KN
statistics went to `s16aqKN_2.host` — which does not match the glob
`s16aqKN.*`, because that pattern needs a literal dot after `KN`. A first
pass over this sitting concluded run 2's host statistics had never been
captured, on the strength of a glob rather than a listing. **`ls s16aqKN*`
and `ls s16aqKN.*` are different questions; when the answer is "the file is
missing", ask the broader one before saying so.**

### This sitting's repeatability is anomalous and should not be quoted forward

Within-arm spreads of **16 ms and 9 ms**, against §16ah's 1.277 s and
§16ak's 398 ms — 25–80× tighter than anything this bench has produced. It
does not threaten the result, which would survive a 1.3 s floor with room to
spare, but "the bench repeats to 16 ms" is not a claim to carry out of one
sitting. Quote it as *at most* 16 ms **here**.

### Sizes

DGROUP **48,752 of 65,536 (74%)**, far code 191,592, image **226,330**,
**needs 240,378 (234K) at load — smallest Victor 384K, unchanged.** The edit
costs +508 bytes of image and +16 of DGROUP. 18 compiler warnings, all in
stock upstream code, **none added** — measured against a stashed baseline
rather than assumed. `ckvictor.c` still compiles with none.

## 16ar. Sliding windows: the mechanism works, and the ring behaves as modelled

**§1 item 12, and the headline is that a window is now a run-time switch on
the shipping binary, negotiated end to end, byte-exact, for NO UPSTREAM
EDIT — still eighteen.** `--window=N` off the DOS command tail (§16i's
priority-0 XI mechanism, the fourth switch after `--safe-server`, the flow
three and `--nodisplay`). DGROUP **48,784 of 65,536 (74%)**, image
**226,936**, **needs 240,984 (235K)**, **smallest Victor 384K, unchanged**.

`DFWSIZ` **is still 1 in the tree.** This section does not change the
default; it builds the lever and measures what it does.

### It writes `ptab`, and that is the whole design

`initproto()` does `wslotr = ptab[protocol].winsize` at `ckcmai.c:2021`,
118 lines before anything reads `wslotr` — so an XI record that sets the
*variable* is undone before it matters. That is exactly the trap that ate
the prefixing setting for the port's entire life (§16ai). The switch writes
`ptab[PROTO_K].winsize`, which is what `initproto()` copies **from**.
**The second time this trap has been walked up to and the first time it was
seen in advance.**

### The pool is the ceiling, and it is 2

Nothing in this build calls `adjpkl()` for the receive direction —
`dofast()` is guarded out (§8 item 14) and the other two call sites are
`REMOTE SET` handlers. So `urpsiz` stays at `DRPSIZ` while `makebuf()`
divides `RBSIZ` by the slot count, and the condition nobody upstream is
going to check is `(DRPSIZ + 6) × slots <= RBSIZ`, i.e. **4,006 × 2 = 8,012
≤ 8,192**. `ckvictor.h`'s `SBSIZ`/`RBSIZ` comment turns out to have
anticipated this exactly — *"at window 1 it is twice what it needs,
deliberately, so that turning the window up to 2 later is a one-line
change"*. It is, and this is it. The switch **clamps rather than shrinks
the packet**, because shrinking `DRPSIZ` to fit would change the packet
length between the two arms and confound the measurement; `cap=` prints the
clamp so it is visible rather than inferred.

### One binary, one digit

`--window=1` against `--window=2` is **the same 8088 instructions in the
same places**, so §16w's code-size sensitivity has nothing to act on. That
is §16aq's `--nobulk` shape reused, and it is now the default way this port
builds a control. `v9k/proofs/vwindow.c` is the parser's correctness
argument — 17 cases, and the ones that matter are the **near misses**
(`--windows=2`, `--window=`, `--window=2x`), which must be left in place so
`cmdlin()` fatals on them, because that fatal is §16i's unknown-option
control. Leg WC ran it on the machine: `--windoz=2` →
`Extended options not configured`, `ask=0`, nothing transferred.

### Four legs under MAME at 9600

Two arms, run twice, the second pair adjacent and with the host quiet.

| | WA / WD (window 1) | WB / WE (window 2) |
|---|---:|---:|
| `neg` (Victor) / host `slots used` | 1 / 1 of 30 | **2 / 2 of 30** |
| `rxpeak` of 4,096 | 305 / **305** | 656 / **655** |
| `peakat` | 4,353 / 4,353 | 30,029 / 30,026 |
| `rxbytes` | 39,794 / 39,794 | 37,864 / 37,864 |
| `rxlost` / `rxfull` | 0 / 0 | 0 / 0 |
| md5 | byte-exact | byte-exact |

**The two runs of each arm reproduce TO THE BYTE.** `pktstat.py --rxbytes`
reconciles at the usual **−11**, so both ends saw the same transfer.

**`rxpeak` doubling is the mechanism becoming visible**, and `mapoffset.py`
puts the window-2 peak inside **seq=20, an ordinary 3,396-byte data
packet** — not a resend, so it is steady-state occupancy and not §16m's
artefact. Ask where the peak is before reading it as a cap; this one is
where it should be.

### The number the sitting was for — **RETRACTED BY §16as**

> **This prediction was wrong and the bench measured 4,095 pinned with
> `rxfull` 179–182.** The model below is valid only where the receiver
> keeps up with the line, which is true at 9600 and false at 38400; the
> real bound is window × packet length. §16as has the analysis. It is left
> here unedited because the *way* it was wrong is the lesson.

Decode time does not care about the line rate; the arrival rate does.
Scaling 655 by 4× for the rate and again by the longer packet the bench
negotiates (3,991 against 3,396) gives a predicted **`rxpeak` of
2,600–3,100 of 4,096 at 38400 with a window of 2** — comparable to §16af's
2,581, which ran clean, with ~1,000–1,500 bytes of margin. **So the bench
leg can be run without growing the ring first**, which is what the ring
growth would have cost: `V9K_RXBUFSIZ` is `.bss` inside DGROUP *and*
`ckvisr.asm` carries `V9K_RXMASK` as a literal `0FFFh`, so 4,096 → 8,192 is
an assembly change, not a constant.

**This is arithmetic on one measured number and it is labelled as such.**
The bench leg reports `rxpeak` itself, which is the check.

### 9600 cannot show the payoff, and did not

Non-line cost (host clock − wire bytes × 1,040 µs): window 1 **39.0 and
41.6 s**, window 2 **32.9 and 41.4 s**. The arms overlap completely, and
**the within-arm spread is up to 8.5 s** — WB and WE are the same binary
and the same 37,864 bytes and 8.5 s apart. At 9600 the line is 39.4 s of an
~80 s transfer and there is nothing to overlap. **§16al's finding
reproduced on the emulator: the spread is the HOST**, since the Victor's
byte counts were identical across it. No cps figure from this sitting is a
window result.

### The instrument this section added, and what is wrong with it

**`dec` splits the foreground bucket §1 item 9 asked about** — last byte of
a packet handed up, to the ACK for it handed down, which is decode plus the
file write plus the protocol state machine. On a receive leg with a window
of one it is also, exactly, the time a window would have to overlap.

**It cannot tell a decode from a silence.** All four legs read
`max = 3250 cs` — 32.5 seconds — and the guard built for it read `to = 0`.
The guard spoils an interval when *our* alarm fires; §16l established long
ago that **every timeout in these logs is the host's**, so our alarm never
expires and the guard is correct about a case that does not occur.
Subtracting `max` by hand gives 64.6 and 73.2 cs against the **68.2 cs that
`rxpeak / line rate` gives independently**, which is why the counter is
kept: it corroborates, it does not adjudicate.

**The rule is §16ai's, learned again on this port's own instrument: when
the clock cannot resolve an effect, find the counter that measures the same
mechanism in units that do not vary.** `rxpeak` is bytes, counted exactly,
with no 0.5 s quantum and no silence in it. **`rxpeak` is the answer here
and `dec` is the cross-check.**

### Two process checks that matched themselves

`pgrep -f "mame victor9k"` **also matches the shell running the wait loop**,
so this sitting spent fifteen minutes concluding MAME had not exited when
it had; and `pgrep -f "projects/mame/mame"` matched **nothing while MAME was
running**, because its `argv[0]` is `./mame`. **A detector that can see
itself and a detector that cannot see the target produce the same
confident wrong answer.** Wait on the child PID.

Related, and the same species: `vtg_image_util dir` is a **usage error**,
and a `grep` over a usage error prints nothing — which reads exactly like
"the target names are fresh". The subcommand is `list`. **A precondition
that errors looks like a precondition that passed; check the exit status.**

### What is next for item 12

**One bench sitting at 38400, and it is written up and staged as
`HW_TEST_16ar.md`** — five legs (`XA`/`XB`/`XD`/`XE` as two adjacent
control-treatment pairs, `XF` for flow control), `CKWINB.EXE` on the image
round-trip verified, `.BAT`s CRLF-verified after landing, target names
clear, fixtures and take-files in the tree. Results go to **§16as**.

The one thing that sitting needs which is not on the image is a **host**
command: `stty -f <port> crtscts -hupcl` before leg XF, because the bench
Mac's C-Kermit has no `POSIX_CRTSCTS` and its `tthflow()` is empty
(§16am, §16an). Without it XF measures nothing.

**Note the leg letters.** WA and WB were superseded by WD and WE — the
first pair ran the pre-`dec`-fix binary and WA was disturbed by a host
command during the transfer — so their `.BAT`s and the binary they named
were removed from the image rather than left as a leg that no longer
resolves. Their figures survive in the table above.

## 16as. Windows on the machine: they work, they cost 9.3%, and the answer is no

**Five bench legs at 38400, every transferred file byte-exact, and §1 item
12 is answered in the negative.** A window of 2 negotiates correctly, runs
correctly, and is **9.3% slower** than a window of 1 while moving **21.4%
more wire bytes**. `DFWSIZ` **stays at 1**. The `--window=N` switch stays,
because the shipping default is unchanged and a future flow-control result
would reopen the question in one leg.

`HW_TEST_16ar.md` is the run sheet, with the results inline.

| leg | window | `rxfull` | `rxpeak` | wire | to/re | clock | non-line | cps |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| XA | 1 | 0 | 2,819 | 40,621 | 1/2 | 27.618 s | 17.057 s | 1,186 |
| **XD** | **1** | **0** | **279** | **37,557** | **0/0** | **25.786 s** | **16.021 s** | **1,271** |
| XB | 2 | 179 | **4,095** | 45,577 | 0/2 | 28.183 s | 16.333 s | 1,163 |
| XE | 2 | 182 | **4,095** | 45,577 | 0/2 | 28.199 s | 16.349 s | 1,162 |
| XF | 2+rtscts | 282 | **4,095** | 45,577 | 0/2 | 28.382 s | 16.532 s | 1,155 |

**Leg XD is the control and it reproduces §16aq exactly** — 37,557 wire
bytes, 0 timeouts, 0 retransmissions, 25.786 s against 25.660. The three
window-2 legs are identical to the byte on the wire (45,577 three times)
and within 199 ms of each other on the clock, so this is not a noisy
sitting: **the bench repeated to ~200 ms here**, against §16ah's 1.3 s and
§16ak's 398 ms.

### The window gained no overlap at all, and that is the finding

Non-line cost — host clock minus wire × 260 µs, which is the quantity a
window is supposed to reduce — is **16.021 s at window 1 and 16.333 /
16.349 at window 2.** It did not fall. Everything the window did was to
overflow the ring and buy two retransmissions.

### Why: the receiver is slower than the line, and a window cannot fix that

| | foreground | line | receiver vs line | ring occupancy |
|---|---:|---:|---|---|
| 9600 (§16ar) | 427 µs/byte | 1,040 µs | **2.4× faster** | bounded — 655 measured |
| **38400** | 427 µs/byte | **260 µs** | **1.64× slower** | **grows until it pins** |

A window converts "line, then foreground, serialized" into "both at once",
and the buffer has to hold the difference. Over a 32 KB transfer that
difference is **16.0 − 9.8 = 6.2 s of line time, about 24 KB** — against a
4,096-byte ring. **The full overlap this port wanted was never within reach
of this ring**, and no allocation fixes it: the ring is `.bss` inside
DGROUP and there are 16,752 bytes free in the whole segment.

So the item-12 premise — *"line and foreground are strictly serialized, so
overlapping them takes a 25.66 s receive toward ~16 s"* — is arithmetically
right and operationally unreachable. **The ceiling it names is real; a
window is not the way to it.** Making the foreground faster is, which is
what edit 18 did.

### §16ar's prediction is RETRACTED, and the error generalises

§16ar predicted `rxpeak` **2,600–3,100 of 4,096** and `rxfull = 0`.
Measured: **4,095 pinned, `rxfull` 179–182.**

The arithmetic was not wrong; the regime was. §16ar modelled occupancy as
**one decode's worth of arrivals**, decode × line rate, and scaled the
9600 measurement by 4. That model is valid **only where the receiver keeps
up with the line**, because only then does the ring drain back to zero
between packets. At 9600 it does. At 38400 it does not, so occupancy grows
monotonically and the real bound is **window × packet length — 2 × 3,991 =
7,982 into a 4,096-byte ring.** Overflow was certain before the leg ran and
one line of arithmetic in the run sheet would have said so.

**The durable form: a number measured on one side of a regime boundary
cannot be scaled across it.** §16ar had both halves of the boundary in hand
— it published 427 µs of foreground and it knew the line rates — and still
scaled the wrong quantity. This is the sixth hand-built prediction in this
tree to come out wrong (§16t, §16af ×3, §16ag, and now this), and the first
whose error was in the *model* rather than in a constant.

### Leg XF: flow control asserted and the far end did not stop

`flow in=2 out=2 hi=3072 lo=1024 held=2 rel=2 stuck=0` — the port's half
worked exactly as §16aj built it and §16an saw on the scope: two asserts,
two releases, `held = rel`. And the wire is **byte-identical to XB and XE**
at 45,577, with `rxfull` *worse* at 282. **Nothing on the far end paused.**

That is §16am and §16an a third time, and it is the standing blocker: the
bench Mac's C-Kermit has no `POSIX_CRTSCTS`, so only `stty` can configure
that port, and whether `stty` was run before this leg is **not recorded**.
Either way the shipping decision is unchanged, but the leg is only a
*confirmation* if it was.

### What would reopen this

A window pays only if the far end can be made to stop. With working
outbound flow control the ring no longer has to hold the whole 24 KB — it
has to hold one flow-control round trip — and `--window=2` becomes one leg
away from a real result. **That, and not the window, is item 12's blocker,
and it has been the same blocker since §16ak.** Everything else is built.

### The instrument, which came out well

`dec` got its first clean reading here. On leg XD: **`dec tot` = 16.50 s
over 19 intervals, against 16.021 s of non-line cost by subtraction** —
one clock quantum apart, by two independent routes. That is the first
*direct* measurement of the foreground bucket §1 item 9 has been asking
about since §16v, and it confirms the subtraction that every figure in
§16v, §16af and §16aq rested on. `to = 0` on all five legs.

## 16at. The window that fits: shorten the packet, not the ring

**§16as's defect is repaired for no DGROUP, no assembly and no upstream
edit — still eighteen — and the repair is a division.** The `--window=N`
clamp now checks the **ring** as well as the buffer pool, and the ring is
the ceiling that was binding all along.

### The line §16ar should have written

A window of W lets the far end hold **W unacknowledged packets**, so
in-flight bytes are **hard-bounded at W × (packet wire length)** —
structurally, not statistically — and the ring must hold all of it, because
nothing drains it while the foreground decodes.

At the shipping `DRPSIZ = 4000` that is **2 × 3,998 = 7,996 into a
4,096-byte ring**, so the ring ceiling is `4096 / 4008 = 1`: **this build
cannot usefully open a window at all**, and §16as measured what happens
when it tries. The clamp now says so — `--window=2` comes back `use=1` —
and the exit line prints **`pool=` and `ring=` separately**, because a
single `cap=` would hide which one bit and checking only the pool is
exactly what cost §16as its sitting.

### Shorten the packet and the window fits

| `DRPSIZ` | pool ceiling | **ring ceiling** | in-flight at W=2 | margin |
|---:|---:|---:|---:|---:|
| 4000 (shipping) | 2 | **1** | 7,996 | **−3,900** |
| 2000 | 4 | **2** | 4,016 | 80 |
| **1800** | 4 | **2** | **3,596** | **500** |
| 1300 | 6 | **3** | 3,924 | 172 |

**`DRPSIZ = 1800` costs nothing measurable to build**: `CKWIN18.EXE` is
226,972 bytes with DGROUP 48,784 — **byte-for-byte the same size as the
shipping build**, because `DRPSIZ` only changes immediates. Growing the
ring instead would have cost 4,096 of DGROUP *and* an edit to
`ckvisr.asm`, whose `V9K_RXMASK` is a literal `0FFFh`.

**And it makes the window its own flow control.** The far end cannot get
more than W packets ahead whatever it wants to do, so nothing here depends
on RTS/CTS — which sidesteps the §16am/§16an blocker §16as ended on. That
blocker was never the only route; it was the only route *at DRPSIZ 4000*.

### Verified under MAME at 9600 — legs YA and YB

| | YA `--window=1` | YB `--window=2` |
|---|---:|---:|
| `window ask/use/neg` | 1 / 1 / 1 | **2 / 2 / 2** |
| `pool` / `ring` | 4 / **2** | 4 / **2** |
| `rxlost` / **`rxfull`** | 0 / **0** | 0 / **0** |
| `rxpeak` of 4,096 | 201 | **635** |
| longest packet | 1,798 wire | 1,742 wire |
| md5 | byte-exact | byte-exact |

**`rxfull = 0` with `rxpeak = 635` is the repair**, against §16as's pinned
4,095 and `rxfull` 179 at the same window size. The clocks are **not
usable** — both legs took timeouts, as every 9600 leg in this harness has
— and 9600 could not show the payoff anyway. That is `HW_TEST_16at.md`,
four bench legs at 38400.

### A number for item 9, and it is the one that was missing

`dec` now has readings at two packet lengths on the same harness. Excluding
the single timeout-contaminated interval in each (§16as: `max` names it):

| | packets | foreground |
|---|---:|---:|
| `DRPSIZ 4000` (leg WD) | 25 | ~15.5 s |
| `DRPSIZ 1800` (leg YA) | 37 | ~17.5 s |

**≈ 167 ms per packet of fixed cost**, which is the per-byte / per-packet
split §1 item 9 has wanted since §16v. **Indicative, not settled** — both
legs carried timeouts and different retransmission counts — but it is the
first separation of the two and it is what says `DRPSIZ 1800` should cost
about +2 s of foreground against the ~9 s of serialization a window
removes.

### Route B: keep the long packets and grow the ring instead

Shortening the packet is not the only way to satisfy W x L, and it is not
obviously the right one -- it pays in **per-packet fixed cost**, which this
tree has never measured cleanly.  The alternative is to grow the ring and
keep the packets, and the ring is now a lever rather than a constant:

| | route A | route B |
|---|---|---|
| ring | 4,096 unchanged | **8,192** |
| DRPSIZ | 1,800 | 3,800 |
| in-flight at W=2 / margin | 3,596 / 500 | 7,616 / 576 |
| DGROUP | **48,784 (74%)** | **52,880 (80%)** |
| needs at load | 241,214 (235K) | 245,310 (239K) |
| **smallest Victor** | **384K** | **384K** |

**Both keep the smallest Victor at 384K**, which is the figure that decides
reach, so the choice is margin against packets rather than reach against
speed.  Route B is verified under MAME -- leg WN, byte-exact, `rxfull = 0`,
`rxpeak = 754 of 8192`, `pool=2 ring=2`.

**Making the ring a lever needed the assembly.** `ckvisr.asm` carried
`V9K_RXMASK` as a literal `0FFFh` with a compile-time check in ckvictor.c
that simply refused any other size.  It is now `IFNDEF`-guarded and set
from the makefile (`RXMASK=-dV9K_RXMASK=1FFFh`), and the compile-time check
became two: a power-of-two test that does not need to know what the
assembler was told, and -- the one that matters -- a **runtime** check.

**The runtime check exists because a mismatch does not fail, it corrupts.**
Head and tail would wrap at different points, silently, on a machine whose
protocol would present the damage as retransmissions.  `ckvisr.asm` now
publishes the mask it was assembled with as `_v9k_isr_rxmask`, and
`v9k_ser_install()` compares it against `V9K_RXMASK` before the handler is
ever put in the vector.  A `#if` cannot do that across two translation
units; one compare per program run can.

**It was tested by building the mismatch deliberately** (leg WM: ring 8192
in C, 4096 in the assembler), and the first version of the check FAILED
that test in two ways worth recording. `v9k_ser_install()`'s return value is
**ignored** at its only call site, so returning -1 fell through to the OEM
driver's polled path -- which SS16b measured losing every inbound packet
after two bytes, i.e. a build error would have presented as a transfer that
mysteriously does not work.  And the message never arrived: stdout is
redirected on every instrumented leg, DOS buffers it, the program then
blocked in receive forever, and the leg produced a **zero-byte `.OUT`**.
It now prints, flushes and exits, and leg WM re-run gives

```
v9k: FATAL ring size mismatch: ckvisr.asm=4096 ckvictor.h=8192
v9k: rebuild with RXMASK=-dV9K_RXMASK=1FFFh, or both defaults
```

**A safety check that has never fired is not known to work**, and this one
was wrong the first time.  Spend the leg that makes it fire.

### A window of more than 2 buys nothing, and here is why

Once the window is open the receiver runs continuously: the sender sends
N+1 while we decode N and cannot send N+2 until we ACK N.  Because decode
(439 us/byte) exceeds line time (260 us/byte), **the foreground is already
saturated at W=2** -- the line goes idle waiting for us, not the reverse.
A third slot can only help when the LINE is the bottleneck, and on this
machine it is not.  That is why route C (a 16 KB ring) is deferred: its
only benefit is *bigger packets*, i.e. fewer of them, so it is worth
considering only if the per-packet cost turns out to be large -- and
`HW_TEST_16at.md` leg ZA is what measures that.

### The prediction for the bench, stated so it can be checked

Foreground 16.5 s (leg XD's `dec tot`) plus ~2 s of extra per-packet cost,
against a 9.8 s line, overlapped: **~18.5 s and ~1,770 cps, about +39% on
§16as leg XD's 25.786 s and 1,271.**

**That is an ordering argument and not a magnitude** — six hand-built
predictions in this tree have been wrong and §16ar was wrong about this
exact quantity. **What is not an estimate is `rxfull = 0`**: that follows
from the W × L bound rather than from a rate comparison, and it is the
claim the bench should check first. If `rxfull` comes back non-zero the
bound itself is wrong and nothing else in the sitting is interpretable.

## 16au. Windows fit, and buy nothing: the serialization was never there

**Eight bench legs at 38400, all byte-exact, `rxfull = 0` on every one. The
W × L bound is confirmed and the window is confirmed to be worth 1 ms.**
`DFWSIZ` stays 1, `DRPSIZ` stays 4000, `V9K_RXBUFSIZ` stays 4096. **§1 item
12 is closed for good**, and not because the ring was too small.

| leg | rt | W | `rxfull` | `rxpeak` | wire | pkts | to/re | clock | non-line | `dec` | cps |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| ZA | A | 1 | 0 | 453 | 37,667 | 28 | 0/0 | 26.677 | 16.884 | 17.00 | 1,228 |
| ZD | A | 1 | 0 | 404 | 37,667 | 28 | 0/0 | 26.438 | 16.645 | 17.00 | 1,239 |
| ZB | A | 2 | 0 | 3,011 | 37,678 | 29 | 0/0 | 26.423 | 16.627 | 17.00 | 1,240 |
| ZE | A | 2 | 0 | 2,607 | 37,678 | 29 | 0/0 | 26.405 | 16.609 | 18.50 | 1,241 |
| BA | B | 1 | 0 | 1,603 | 40,632 | 33 | 1/2 | 27.509 | 16.945 | 17.00 | 1,191 |
| **BD** | B | 1 | 0 | 558 | 37,557 | 18 | 0/0 | **25.789** | 16.024 | 16.00 | **1,271** |
| **BB** | B | **2** | 0 | 4,380 | 37,568 | 19 | 0/0 | **25.788** | 16.020 | 17.50 | **1,271** |
| **BE** | B | **2** | 0 | 4,756 | 37,568 | 19 | 0/0 | **25.804** | 16.036 | 17.50 | 1,270 |

Route A is `DRPSIZ` 1800 on the 4,096 ring; route B is `DRPSIZ` 3800 on an
8,192 ring. Six of eight legs are perfectly clean.

### The bound was right and the window really is open

`rxpeak` respects W × L on both routes — 3,011 / 2,607 against route A's
3,596, and 4,380 / 4,756 against route B's 7,616 — and `rxfull = 0`
everywhere, against §16as's 179–282. The window is genuinely negotiated
(`neg=2`, host `2 of 30`) and genuinely used: **`rxpeak` rises 7.8×, 558 to
4,380**, which is the far end running ahead into the ring during the decode
interval, exactly as intended.

### And it is worth 1 ms

| route | W=1 | W=2 | Δ |
|---|---:|---:|---:|
| B | **25.789 s** | **25.788 / 25.804 s** | **1 ms / 15 ms** |
| A | 26.438 s | 26.423 / 26.405 s | 15 / 33 ms |

**Leg BD reproduces §16as leg XD to 3 ms** (25.789 against 25.786), which
is the null leg doing its job: growing the ring on its own changes nothing,
as predicted.

### The model item 12 rested on is RETRACTED

Since §16v this project has said *"line time and foreground are strictly
serialized, so overlapping them takes a 25.66 s receive toward ~16 s."*
**They were already overlapped.** `ttinl()` processes bytes as they arrive,
so the 9.77 s of "line time" is **not idle time waiting for the wire** — it
is time the CPU spends in the ISR and in `ttinl()`'s per-byte loop. There
was never any idle to reclaim, which is why the ~16 s ceiling this item
chased for six sections does not exist.

The legs show the mechanism directly rather than by inference. With the
window open, `dec` grows **16.00 → 17.50 s** while non-line cost holds at
**16.02**: about **1.5 s of reception moved into the decode interval and
the decode interval grew by exactly that.** Same cycles, relabelled.

> **On a single-CPU machine with no DMA the "I/O" IS CPU work, in an ISR.
> Overlapping I/O with compute cannot create capacity; it can only change
> which bucket the same cycles are counted in.**

That is why edits 17 and 18 worked and this did not. **The only lever on
this machine is doing less work per byte** — never rearranging when the
work happens. Any future throughput idea should be tested against that
sentence first.

### Item 9's number, measured cleanly: ~65 ms per packet

Leg BD (18 packets, 25.789 s) against leg ZD (28 packets, 26.438 s), wire
bytes within 110 of each other, both 0 timeouts and 0 retransmissions:

**0.649 s ÷ 10 packets = 65 ms per packet.**

That is the per-byte / per-packet split §1 item 9 has wanted since §16v,
and the first clean measurement of it. **It also retracts §16at's
139–167 ms**, which was fitted from MAME legs carrying timeouts — a
contaminated estimate, wrong by 2.5×, and the same species of error as
§16as's contaminated `dec`.

**It kills route C on evidence rather than on judgement.** `DRPSIZ` 8000
would remove ~9 packets: **0.6 s, 2.3%**, for 12,288 bytes of DGROUP. The
per-packet term is only ~1.2 s of a 25.8 s transfer, so **`DRPSIZ` 4000 is
already near-optimal** and there is nothing to buy at the top end either.

### Three wrong predictions on one item, and the pattern in them

§16ar predicted the ring would hold (it did not). §16at predicted ~17 s
(it was 25.79). §16at predicted 139–167 ms per packet (it is 65). **The
first was a regime error, the second a model error, the third a
contaminated fit** — and the model error is the one that mattered, because
it had been in this file since §16v and every version of item 12 was built
on top of it. **A number that has been quoted for six sections is not
thereby a measurement.** "Line and foreground are serialized" was an
inference from a subtraction, never an observation, and the subtraction was
consistent with both models.

### What is kept, and why

Nothing ships, but three things stay because they cost nothing and are now
correct and tested: **`--window=N`** with the two-ceiling clamp;
**`V9K_RXBUFSIZ` as a build-time lever** with `RXMASK` in the makefile;
and the **install-time mask check** that leg WM proved fires. Together they
mean the next person to wonder about windows can answer it in one leg
instead of six sections — and cannot corrupt a ring by trying.

---

## 16av. Six defects off the travel list: a sleep that did not sleep, a collision policy that never took, a write loop with no exit, and the DOS this port has never met

Written 15 August 2026, at a desk, with no Victor 9000 in reach. Everything
here is either static analysis, a host-side tool, or a leg under MAME at
9600 — the emulator's ceiling — and nothing in it has been on real hardware.
Six items from `NEXT_SESSION.md` §1 were picked because they can be settled
without the machine; five of them moved, one was diagnosed rather than
fixed, and **two of the six turned into defects that were worse than the
notes describing them.**

Legs are named NA, NB, NC, ND, NF, NR, NS, NT, NU and NX. Every one ran on
Victor MS-DOS 3.1 under MAME at 9600 with `socat` on the `-bitb` socket.

### What shipped

| | before | after |
|---|---:|---:|
| DGROUP | 48,784 (74%) | **48,816 (74%)** |
| image | 227,166 | **230,224** |
| needs at load | 241,214 (235K) | **242,288 (236K)** |
| smallest Victor | 384K | **384K, unchanged** |
| upstream edits | 18 | **18 — none of this needed one** |
| warnings | 18, `ckvictor.c` 0 | **18, `ckvictor.c` 0** |

**The file grew 3,058 bytes and the machine only sees 1,074 of it.** The
rest is relocation-table growth and paragraph padding, which DOS does not
have to hold. That is the standing reason hard rule 4 says to quote
`mzsize.py`'s requirement and not `ls -l`, and this is the first time the
two have been this far apart in one change.

### 1. `msleep()` did not sleep, and now it does — measured at 500 ms

§16an found this with a logic analyzer aimed at something else: a `HANGUP`
that should hold DTR and RTS down for `HUPTIME` = 500 ms held them for
**175 µs**. `ckutio.c`'s `msleep()` tries `select()`, `poll()` and
`usleep()` and then falls through a chain of clock loops to

```c
if (m > 0) while (m > 0) m--;                     /* ckutio.c:12142 */
```

— a side-effect-free loop on a local that `-os` may delete outright.
Confirmed with `wcc -pl` rather than by reading: the preprocessed
`msleep()` is that fallback and nothing else, and the whole build contains
exactly **three** callers — `tthang()`'s `msleep(500)`, one `msleep(10)` on
`ttol()`'s partial-write retry, and this port's own `tcsendbreak()`.

**The repair is upstream's own extension point and cost no edit.** Defining
`NAP` in `ckvictor.h` moves `msleep()` onto its `nap()` arm
(`ckutio.c:12065`), and `ckvictor.c` §1d supplies `nap()`. `ckuus5.c:11397`
then lists NAP in `SHOW FEATURES`, which is now a true statement.

**Why it is a counted loop and not a timed one.** Hard rule 6 is INT 21h
only, and INT 21h's clock is `AH=2Ch`, which advances in **500 ms steps**
on this machine (§16n). Both delays that need this — 275 ms and 500 ms —
are inside a single quantum, so the one clock available cannot resolve
either. Anything shorter than a quantum has to be counted. Whole seconds
are polled against the clock instead, because a count accumulates error and
a poll does not.

The count is calibrated at run time rather than written down: sync to a
tick edge, spin in chunks until the clock moves again, divide the
iterations by the hundredths the move reports. **The delta is read rather
than assumed to be 50** — it costs one subtraction and it means a machine
whose DOS ticks differently calibrates itself instead of being 10× wrong in
silence. Three things bias it and **all three are in the safe direction**,
which is why none is corrected: the calibration loop reads the clock
between chunks and the delay loop does not, so the measured rate is low;
interrupts during calibration make it lower still; and POSIX asks for *at
least* the requested time. A 1/16 margin covers the lot.

**Measured, legs NA/NB/NC/ND/NS:**

```
v9k: nap per=409 n=1 req=500 ms tot=50 cs cc=0
```

`per = 409` spins per centisecond, **identical on all five legs**. `n = 1`,
`req = 500 ms`, `tot = 50 cs` — **half a second, which is one quantum and
exactly what a true 500 ms sleep reads.** The defect read 0. Read `tot`
against `req` in the aggregate and never on one call, for §16n's reason.

**Every run exercises this, which is why it is reported.** `exithangup` is
1 by default (`ckcmai.c:1290`), so `ttclos()` calls `tthang()` on every
exit that had a line open. The port's exit path is now ~1.5 s longer (up to
one second of calibration, once, plus the 500 ms it was always supposed to
take) and DTR and RTS genuinely drop for half a second. `tcsendbreak()` is
fixed by the same change and is still unexercised.

`ttol()`'s `msleep(10)` sites are both error paths — `EWOULDBLOCK` and a
partial write, which upstream's own comment calls "This never happens". Our
`v9k_ser_put()` returns short only when the transmitter is stuck past
`V9K_TXSPIN` or a flow hold-off outlasts `V9K_FCSPIN`, so on a healthy leg
neither is reached and there is no throughput exposure.

### 2. `SET FILE COLLISION`: the port has been refusing files, and not for the reason written down

`NEXT_SESSION.md` has said since §16al that the collision default is BACKUP
and that BACKUP cannot work on FAT, because `znewn()`'s only name form is
`name.~N~` (`ckufio.c:4000`) — two dots and a four-character extension.
**The FAT half is true and the BACKUP half is not.** `ckcmai.c:1326` sets
`fncact = XYFX_B`, and `initproto()` replaces it with
`ptab[PROTO_K].fnca` — statically **`XYFX_D`**, DISCARD (`ckcmai.c:727`) —
before anything reads either. So `znewn()` has never been called on this
port and the shipped behaviour has always been a **flat refusal**. The
observable is identical either way, which is why the wrong explanation
survived: "refused: destination file already exists" is what both produce.

The port now defaults to **REPLACE** (`V9K_COLLISION`, default `XYFX_X`),
for two good reasons and one weak one that is labelled as weak: it is the
DOS convention and what MS-DOS Kermit 3.13 does on this same machine; the
behaviour it replaces is a refusal that has voided two bench sittings; and
upstream picks REPLACE for VMS, which is a weaker argument than it looks
because VMS versions files itself. **The cost is stated rather than
hidden**: a `RECEIVE` into an existing name now destroys that file.
`XFLAGS=-dV9K_COLLISION=XYFX_D` restores the old behaviour.

**IT WALKED INTO §16ai'S TRAP, AND THE COUNTER ADDED TO CATCH IT CAUGHT
IT.** The first version assigned `fncact` and nothing else, exactly as the
prefixing initializer once did, and leg NB came back

```
v9k: coll=4
```

after an initializer that had written 1. `initproto()` at `ckcmai.c:2026`
does `if (ptab[protocol].fnca > -1) fncact = ptab[protocol].fnca;` — the
same shape, in the same function, 118 lines before anything reads it. The
fix writes `ptab[PROTO_K].fnca` as well.

Leg NB is also a clean reproduction of the failure signature: S, F, A, then
**Z with data `D`**, no data packets, a **285-byte** packet log — against
`NEXT_SESSION.md`'s "~287-byte" description — and `No files were
transferred (refused: destination file already exists)` on the Victor's
screen. The receiver's refusal reaches the wire as `N?` in the ACK to the
attribute packet, which `getreason()` decodes as reason "name".

**Verified, legs NC and ND.** NC sent a 4,096-byte fixture into a name the
`.BAT` had deleted; **ND sent a DIFFERENT 4,096-byte fixture into the name
NC had just created**, and nothing deleted between them. ND: `SUCCESS`, **0
timeouts, 0 retransmissions, 6.382 s, 641 cps**, `coll=1` on both legs, and
the file lifted back off the image afterwards has **the md5 of the second
fixture**. Two patterns, one name, the second one wins.

**A server disables this, deliberately, and it matters here.** `ckcpro.c:502`:
if `en_del` is off, C-Kermit changes the collision action to **RENAME** to
protect existing files. `--safe-server` turns `en_del` off, so leg NS came
back `coll=0`. **RENAME goes through `znewn()` and cannot work on FAT
either**, so a `--safe-server` Victor sent a file whose name already exists
will attempt a rename FAT cannot express. The policy is right — a safe
server should not overwrite — and the mechanism fails messily rather than
safely. Two report-upstream items fall out: the fallback wants a choice
that a filesystem without `~N~` names can honour, and the *save* of the old
value is inside `#ifndef NOICP` (`ckcpro.c:508`) while the *restore* is not
(`ckuusx.c:816`), so in a `NOICP` build the change is permanent for the
life of the process.

### 3. Out of disk: an infinite loop in `zoutdump()`, one compare away

§16al lost a bench sitting to a full image: four legs failed with `Too many
retries` after eleven packets and then silence, every output file 0 bytes,
and **the Victor never gave up.** It was recorded as "out of disk space
makes the Victor hang rather than fail" and attributed to §0d's `alarm()`
bounding the read while nothing bounds a failed write. **The real
mechanism is smaller and worse than that:**

```c
while (zoutcnt > 0) {                              /* ckufio.c:2172 */
    if ((x = write(fileno(fp[ZOFILE]),zp,zoutcnt)) > -1) {
        zoutcnt -= x;                              /* x is 0 */
        zp += x;                                   /* x is 0 */
    } else { zoutcnt = 0; return(-1); }
}
```

INT 21h `AH=40h` on a full volume writes what fits and returns **CF clear,
AX short** — zero once there is no room at all. That is not an error by
DOS's definition, Watcom's `write()` passes it through, and `0 > -1` takes
the success branch. **The loop subtracts nothing, advances nothing, and
goes round again for ever.** No timeout can reach it: a receiver that never
asks to read is a receiver no `alarm()` can bound.

On POSIX a regular-file `write()` cannot return 0 for a positive count,
which is why upstream has never defended against it. **The fix is one
compare in `v9k_write()`, which already wraps every write in the program:**
turn "wrote nothing, no error" into the `ENOSPC` DOS declined to raise, and
`zoutdump()` takes its `else` branch. A *short* write is left alone
deliberately — upstream handles it correctly and comes round for the rest,
and the next call is the one that returns 0, so the last bytes that fit
still land.

**Verified, leg NF.** A 30 MB image copy filled to **8.0 KB free**, sent a
32,768-byte file. The host reported

```
status  : FAILURE
reason  : Error writing data
elapsed : 00:00:58
```

— a clean protocol failure in 58 s where the documented behaviour is a hang
that outlives the host. `-dV9K_NOSPC_OFF` puts the hang back, and **that
control leg has not been run**: the treatment fired, which is the half that
matters, but "the fix is what made the difference" rests on the mechanism
above and not on a leg.

**A harness lesson came with it, and it is not small.** Leg NF's
`STEPNF.OUT` is **0 bytes** — the redirect that carries every `v9k:` counter
was itself on the disk under test. An out-of-disk leg cannot report from
the Victor's side unless its output goes somewhere else, and partition 1
(`D:`) is 9.7 MB and empty. `> D:\STEPNF.OUT` next time.

### 4. Ctrl-C: two keystrokes from leaving IRQ1 hooked, and both runtimes are readable

`ckvictor.c` has said since §11b that a Ctrl-Break which DOS turns into a
plain termination is not covered by `atexit()`, "known, not measured on
either runtime". Both halves are readable and reading them turns a vague
caution into a specific defect.

**Open Watcom** (`bld/clib/process/c/signl.c`, `sigsy.c`): `signal()` hooks
INT 23h lazily — any `signal(SIGINT, f)` with `f` other than `SIG_DFL`
calls `__grab_int23()`, and `SIG_DFL` hands the vector back. The handler
calls `raise(SIGINT)`, and `raise()` is the old unreliable-signal kind:

```c
case SIGINT:
  if (func != SIG_IGN && func != SIG_DFL && func != SIG_ERR) {
      _RWD_sigtab[sig] = SIG_DFL;      /* demoted */
      __restore_int23();               /* vector given back */
      (*func)(sig);
  }
```

**A handler fires once.** After that SIGINT is `SIG_DFL`, INT 23h belongs to
DOS, and DOS's own INT 23h terminates the program on the spot: no
`atexit()`, no `v9k_ser_release()`, IRQ1 still vectored into memory about to
be handed to the next program.

**Upstream** (`ckutio.c:1705-1718`, `:2727`): `ttopen()` installs `cctrap`,
whose entire body is `cc_int = 1` — and **`cc_int` is read nowhere in the
tree.** One definition, one assignment, no readers. So the first Ctrl-C of
a session did nothing observable *and* spent the runtime's single shot, and
the second killed the program with the chip still hooked. Two keystrokes,
which is probably why it was never seen: legs are driven from `.BAT` files.

The fix is to be the handler and to re-arm inside it, which the demotion
above obliges every handler on this runtime to do. Installed from
`v9k_ser_install()` rather than an initializer, because `ttopen()`'s
`signal()` runs later and would overwrite an earlier one; the `cctrap` it
displaces cannot be missed. `exit()` from an INT 23h handler is legitimate
rather than merely convenient — DOS calls it at a re-entrant point and
documents that the handler may terminate the process, and Watcom's handler
has already re-enabled interrupts. **`cc=` in the exit report counts it,
and it is 0 on all five legs**, which is the honest reading: the code is
written, its mechanism is established from both runtimes' sources, and
**nothing has pressed Ctrl-C on a Victor.** MAME's keyboard is not the
instrument for that; the bench is.

It deliberately does not try to make Ctrl-C cancel a transfer and continue.
That needs a flag upstream reads, and the only such flag in this build is
the dead one above.

### 5. FreeDOS: the one binary is not one binary, and the vector is only half of it

Item 14 has flagged the IRQ1 vector as "the most likely thing to break the
one-binary-two-DOSes claim". It is worse than a question — the three
answers on this machine are all different, and they are all in
`myfreedos/kernel/victor_pic.asm`'s own header:

| | ICW2 | IRQ1 arrives on |
|---|---:|---|
| Victor boot ROM | 0x20 | INT 21h+ |
| Victor MS-DOS 3.1 | 0x40 | **INT 41h** — what this port hard-coded |
| FreeDOS for Victor | 0x08 | **INT 09h** |

A build that hard-codes 41h would, on FreeDOS, take a vector DOS uses for
something else, leave the real IRQ1 pointing at FreeDOS's own serial
handler, and receive nothing — **while looking, from the C side, exactly
like a chip that never interrupts.**

**ICW2 is write-only**, so the 8259 cannot be asked what base it was given
and the question has to be put to whoever programmed it. INT 21h `AH=30h`
returns the OEM number in BH and FreeDOS answers **0xFD**
(`myfreedos/hdr/version.h:40`, and `kernel.asm:75` carries the same byte).
Anything else is treated as the MS-DOS 3.1 layout, which is the
conservative way round. Only the vector moves: the 8259 mask bit and the
specific EOI encode the IR *level*, so `ckvisr.asm` needs to know nothing
about any of this. `-dV9K_IRQ1_FORCE=0x09` is the control.

**Measured on every leg:**

```
v9k: dos oem=ff ver=310 irq1=41
```

Victor MS-DOS 3.1 reports version 3.10 and OEM 0xFF, so the probe takes the
MS-DOS branch and nothing about the shipping path changed. **The FreeDOS
branch has never executed.**

**The console is the other half, and it is the port's first behavioural
difference between the two DOSes.** §16ao established this console is
VT52/Z19 — `ESC Y`, `ESC E`, `ESC K` — on Victor MS-DOS 3.1. FreeDOS for
Victor supplies its own console driver and it is an ANSI one:
`kernel/victor_ansi.asm` parses `ESC '['` and, at line 154, "Not '[' -
abort sequence, pass through character". So on FreeDOS the VT52 form does
not merely fail to move the cursor, **it prints** — a `Y` and two
coordinate bytes on the screen as text, 55 times per repaint. What that
driver does support covers exactly the three sequences §1g needs
(`ESC[r;cH`, `ESC[2J`, `ESC[K`), so the fix is a dialect switch and not a
reduced display, chosen from the same `AH=30h` probe.
`-dV9K_CON_FORCE_ANSI` / `-dV9K_CON_FORCE_VT52` override it.
**The ANSI arm is written from that driver's source and has never run.**

### 6. `REMOTE DIRECTORY`: two defects, one fixed, one now bounded

Item 15 has said since §16i that `REMOTE DIRECTORY` "streams its listing
and never terminates it". Leg NR, a `KEEP_DEBUG` server on today's tree,
did something else entirely — it answered

```
E No files match                            (on the wire)
?Too many files (64 max) - use SET FILE LISTSIZE to increase   (on the console)
```

**`MAXWLD` is 64 and this project's own test image has 156 files in its
root.** `REMOTE DIRECTORY` with no argument expands `./*` over the working
directory, so the ceiling is what an ordinary listing hits first.
`ckvictor.h` called 64 "a limit this machine will not reach in practice"
and called `SSPACE`'s 2,048 bytes "more than a FAT directory on this
machine can contain" — **both sentences were written without a measurement
and both are false of the image this project has been using all along.**
156 names at 13 bytes is 2,028, and `nzxpand("./*")` keeps the `./` on the
front, which is 2,340. Raised to **`MAXWLD` 256, `SSPACE` 4096**. Neither
moves the load requirement: both are `malloc`'d, and hard rule 4's heap is
outside DGROUP.

**Leg NT, with the new limits, reproduced §16i's original defect with a
packet-level trace it never had.** The listing streams correctly and then:

| seq | wire bytes | sends |
|---:|---:|---:|
| 3–6 | 244–260 | 2–3 |
| 7–13 | 71 → 126 | 1 each |
| **14** | **1,414** | **10 and counting** |

The Victor sends packet 14, the host ACKs it (`s-14-...Y`, a well-formed
5-byte ACK), and the Victor resends the identical packet **~10 seconds
later** — a timeout, not a spin. Ten times, until MAME's clock ran out. It
never answered the FINISH that followed either, and both `STEPNT.OUT` and
`DEBUG.LOG` came back **0 bytes** because the process never exited to flush
them. **That is why §16i could not diagnose it and why this leg could not
either.**

**Leg NU bounds it.** `REMOTE DIRECTORY RCVN*.DAT` — three matches, one
packet — completed perfectly: header, three entries, `Summary: 0
directories, 3 files, 10240 bytes`, then FINISH honoured and a clean exit
with a 166 KB debug log. **So short listings work and long ones wedge**,
and the transition is at the jump from 126 to 1,414 bytes, which is
C-Kermit's slow-start packet-length growth on the *sending* side — §16l's
mechanism seen from the other end. The Victor transmits the long packet
correctly (the host received and ACKed it) and then does not see the reply.

**Two instruments would settle it and neither exists yet.** A debug log
that survives a wedge — `debug()` output is buffered through stdio, so a
flush per line, or per packet, would leave the evidence on disk. And the
Ctrl-C handler built in part 4 above, which is exactly the "make it exit so
the log closes" lever this needs, on a bench where a person can press the
key.

### 7. A corruption injector, because §16aq's stimulus never fired

§16aq's Part 3 set out to show that upstream edit 18's bulk arm and the
byte loop recover from corrupted input identically. The stimulus was a
ten-foot cable wrapped around mains wiring and it produced **zero errors on
both arms** — an instrument failure, not a null result, since magnetic
coupling goes with current and quiet house wiring carries none.

`v9k/tools/wirenoise.py` replaces the `socat` line in the MAME harness: it
listens on the `-bitb` port, creates the `/tmp/v9000` pty, relays both
directions, and corrupts one of them on request. **Corruption is driven by
byte OFFSET, not by a random sequence**, and that is the design decision
worth defending: an A/B needs both arms to meet the same noise, and a plain
RNG cannot give that, because the moment one arm retransmits the two
streams diverge in length and every subsequent draw lands elsewhere.
Keying on the offset means the arms are corrupted in the same places for as
long as their streams agree, and a leg is reproducible from its seed alone.
It reports bytes relayed and bytes corrupted, with offsets, so that a leg
with no errors can be told from a leg whose noise source was never
connected — §16am's rule, made unconditional.

**Its first mixer was wrong and the check that caught it was free.** CRC32
over a decimal string put the corrupted offsets at 15, 19, 40, 44, 48, 113,
117, 146, 213, 217, 246 — **a visible period of 100.** A corruption pattern
with a period is not noise; it would have hit the same place in every
packet and the leg would have measured something other than what it
claimed. Replaced with splitmix64's finalizer and checked over 200,000
offsets: 10,196 hits at p = 0.05, 130 distinct gaps, no structure.

**The leg it was built for has not been run.** The tool is self-tested on
the host — relay, direction control, `--after`, reproducibility, and the
reported offsets matching the observed corruptions exactly — and nothing
has yet been corrupted on a wire.

### What generalises

**A counter added to catch a specific trap caught that exact trap, twice
removed.** `v9k: coll=` was written into the exit report *because* §16ai
said a setting applied before `main()` can be overwritten before anything
reads it. It then reported `coll=4` after an initializer that wrote 1. The
value of the instrument was not that it found something new; it is that the
known failure mode was made visible instead of inferred, and it cost one
`printf`.

**Two comments in `ckvictor.h` asserted that a limit could not be reached,
and an ordinary directory listing reached both.** `MAXWLD` and `SSPACE`
each carried a sentence of the form "this machine will not reach it in
practice", written when the limits were chosen to save DGROUP. Neither had
a measurement. **A limit is a claim about the world and wants a number
beside it**, or it wants a loud failure — these had the second, which is
why nothing was corrupted, but the first would have saved a leg.

**A leg that fills the disk cannot report through a file on that disk**, and
a leg whose program never exits cannot report through a buffered log. Both
were discovered by losing the evidence. The general form: **before running
a leg, ask what the failure under test does to the channel the leg reports
through.**

**The other end of `wcc -pl` is somebody else's source tree.** Two of these
six were settled by reading Open Watcom's `signl.c` and FreeDOS's
`victor_pic.asm` and `victor_ansi.asm` — both installed on this machine,
neither ever opened by this project before. §16aj's rule was "a line of
upstream source is not evidence that the build compiles it"; §16am extended
it to the far end of the wire; this extends it to the runtime and the
operating system. **The libraries are readable. Read them.**

---

## 16aw. `REMOTE DIRECTORY` was never broken: two sessions measured the debug log

Written 16 August 2026, at a desk, no Victor in reach. Five legs under MAME
at 9600 — **RA** for the feature, **RB/RC** for the attribution, **RD/RE**
to make the new guard fire — one `printf`, and **no upstream edit, still
eighteen.** DGROUP 48,816 → **48,832 of 65,536 (74%)**, image 230,224 →
**230,274**, needs **242,354 (236K)**, **smallest Victor 384K, unchanged**,
warnings 18, `ckvictor.c` 0.

**`REMOTE DIRECTORY` lists this project's own 157-file root in 31.077
seconds with zero timeouts and zero retransmissions.** Leg RA, `CKERMITW
-x` with the full capability set, driven entirely from the host:

```
Summary: 1 directory, 157 files, 7129606 bytes

 status                 : SUCCESS
 damaged packets rec'd  : 0
 timeouts               : 0
 retransmissions        : 0
 elapsed time           : 00:00:31 (31.077 sec)
 effective data rate    : 275 cps
```

All 157 entries in order, the one subdirectory, the summary line, the
terminating Z, the B, and then the `finish` that follows it — answered,
`Closing /dev/seriala...OK`, a clean exit with the counters flushed.
`rxlost=0 rxfull=0 rxpeak=20 of 4096`. The file and directory counts agree
with `vtg_image_util info` exactly.

**The binary was `CKRDIR.EXE`, md5 `5b7eb873…` — bit for bit the binary
§16av shipped**, running the command §16av said wedges.

### So §1 item 15's second defect does not exist, and neither did §16i's

"`REMOTE DIRECTORY` streams its listing and never terminates it" has been in
this file since §16i. `NEXT_SESSION.md` has carried "short listings work,
long ones wedge" since §16av. **Both were the debug log**, and the reason
nobody caught it is that *every* `REMOTE DIRECTORY` leg this port has ever
run was run with `-d`: §16i's, and §16av's NR, NT and NU.

The evidence was already in the tree. `s16bNT.pkt` — leg NT's host packet
log, the one artefact of that leg that survived — reads completely
differently once the lengths are decoded instead of the resends counted:

| | leg NT (`-d`) | **leg RA (shipping)** |
|---|---|---|
| data packet lengths | 236, 244, 252, 126, 68, 87, 96, 106, 112, 116, 118, **1406** | **236, 480, 968, 1944, 3896, 738** |
| entries delivered | **56 of 157**, no summary | **157 of 157**, summary |
| timeouts / resends | 13 / 9 | **0 / 0** |
| listing produced at | **~8.7 characters a second** | **~264 characters a second** |
| terminating Z | never reached | sent and ACKed |

**Leg NT's packet lengths were collapsing, not growing**, and that is the
tell that was there to read: C-Kermit's slow start was knocking the length
*down*, because the host kept timing out waiting for a server that produced
a character every 115 ms. Leg RA's grow the way a healthy transfer's do —
236 → 480 → 968 → 1944 → 3896 — until they reach `DRPSIZ`.

**And the packet-14 "loop" was not a loop.** The host NAKed packet 14 three
times while the Victor was still building it; the Victor sent it, then found
three queued NAKs and honoured each one. Three resends, three ACKs, and the
log ends there because the operator gave up — not because anything was
stuck.

### The mechanism, from `wcc -pl` rather than from the source

`nxtdir()` (`ckcfns.c:6637`) hands the packetizer **one character per
call**, and in a `KEEP_DEBUG` build its hot path is four `dodebug()` calls
per character — three inside the `if (deblog)` guard and one outside it:

```c
    if (deblog) {
	dodebug(5,"nxtdir funcnxt",(char *)(""),(long)(funcnxt));
	dodebug(5,"nxtdir funclen",(char *)(""),(long)(funclen));
	dodebug(6,"nxtdir funcbuf",(char *)(funcbuf+funcnxt),(long)(0));
    }
    if (funcnxt < funclen) {
	c = funcbuf[funcnxt++];
	dodebug(0,"nxtdir return 1",(char *)(""),(long)((unsigned)(c & 0xff)));
	return((unsigned)(c & 0xff));
    }
```

The shipping build preprocesses the same lines to a compare, a load, an
increment and a bare `;`. **§16k measured `-d` at about 25 ms per byte;
four calls is ~100 ms a character, and leg NT produced one every 115 ms.**
Two independent routes to the same constant, one of them measured six
sections ago for an unrelated reason.

**Legs RB and RC are the adjacent control, and they are the same binary.**
`CKRDBG.EXE` twice over the same four-entry listing, differing only in
whether `-d` is on the command line — §16aq's and §16ap's shape, so §16w's
code-size sensitivity has nothing to act on:

| | RB (no `-d`) | RC (`-d`) | ratio |
|---|---:|---:|---:|
| elapsed (host clock) | **2.248 s** | **33.787 s** | **15.0×** |
| effective data rate | 131 cps | 8 cps | 16.4× |
| timeouts / resends | 0 / 0 | 1 / 0 | |

**Legs RD and RE replicate it on the rebuilt binary**, which is worth
having because the pair was re-run for an unrelated reason (the guard
below) and therefore constitutes an independent repeat rather than a
re-reading:

| | RD (no `-d`) | RE (`-d`) | ratio |
|---|---:|---:|---:|
| elapsed (host clock) | **1.961 s** | **35.587 s** | **18.1×** |
| effective data rate | 150 cps | 8 cps | 18.8× |
| timeouts / resends | 0 / 0 | 1 / 0 | |

All four byte-correct against `vtg_image_util list`, all four `SUCCESS`,
all four exiting cleanly. The `-d` arms agree to 1 cps across sittings; the
clean arms differ by 287 ms, which is the harness.

### `MAXWLD` and `SSPACE` are now proven at full scale

§16av raised them from 64 / 2048 to 256 / 4096 after leg NR answered
`?Too many files (64 max)` on the console and `E No files match` on the
wire, and **no leg had ever confirmed the fix**, because the leg that would
have — NT — never finished. Leg RA expands 158 entries through `nzxpand()`
and lists every one. That half of item 15 is now measured rather than
argued.

One cosmetic difference from a Unix listing, noted so it is not reported
later as a defect: a directory prints with its size and a leading `d` in
the permissions column (`drwxrwxrwx 0 ... TEST`) rather than as `<DIR>`.
Upstream takes the `<DIR>` branch on `itsadir && len < 0`, and this port's
`zgetfs()` returns 0 rather than -2 for a directory. The entry is correctly
identified either way, and the summary counts it as a directory.

### The guard: `v9k: isr=asm deb=1`

The exit report gains one integer, and the argument for it is the one
already written beside `isr=`: **a `.OUT` file cannot tell you which build
produced it**, and the debug log is a far bigger confounder than the choice
of ISR ever was. The comment two lines above the new `printf` has said since
§16k that `-d` costs ~25 ms a byte and that a run worth measuring cannot
carry a debug log — and three legs carried one anyway, because **a comment
lives in the source and the trap lives in the run sheet.** `deblog` is
defined unconditionally (`ckcmai.c:1372`) and is a constant 0 in a `NODEBUG`
build, so the field costs one `%d`, needs no `#ifdef`, and cannot be wrong.

**It was exercised in both states before being believed, and the first
version of it was wrong.** Legs RB and RC printed `deb=0` on *both* arms —
including the arm that had just spent 33.787 s writing a debug log. The
cause is four lines above the new `printf`, in a comment that had been
right there since §16t: `doexit()` (`ckuusx.c:5478`) sets `deblog = 0` and
`zclose(ZDFILE)`s **before** it calls `exit()`, so an `atexit()` handler
can never see the variable set. The field now latches in
`v9k_ser_install()` — after `prescan()` has opened the log, before any
transfer — and ORs the live value back in at print time. **Legs RD and RE
are the re-run that makes it fire, and it does:**

```
STEPRD.OUT   v9k: isr=asm deb=0    dec tot=650 cs    elapsed=950 cs
STEPRE.OUT   v9k: isr=asm deb=1    dec tot=9950 cs   elapsed=13000 cs
```

One binary, one flag, and the Victor's own clock agreeing with the host's
about the 15×: 6.5 s of decode against 99.5.

That is the second time in this project that a check written to catch a
known trap was itself wrong on its first outing (§16au's ring-mask check
was wrong twice), and both were caught the same way: **by spending the leg
that makes the check fire.** A guard that has only ever been observed
agreeing with the expected answer has not been tested — leg RC agreed with
"the shipping build has no log" while reporting on a build that did.

**The instrument item 15 used to ask for is withdrawn.** It wanted `debug()`
flushed per line so that a wedged run would still leave evidence. There was
no wedge; and per-line flushing would deepen the very cost that produced the
symptom. §16av's Ctrl-C handler remains the right lever for a genuinely
stuck run, and is still unexercised.

### What is on the image, so the next session does not have to guess

| on `victor_kermit.img` | bytes | md5 | what it is |
|---|---:|---|---|
| `CKRDIR.EXE` | 230,224 | `5b7eb873…` | the §16av shipping build. **Leg RA** |
| `CKRDBG.EXE` | 312,758 | `ee5d8b59…` | `KEEP_DEBUG` **with** the `deb=` latch. Legs RD/RE |
| `CKRDR2.EXE` | 230,274 | `5f2a1580…` | the shipping build as it stands after this section |

`STEPRA.BAT` drives leg RA, `STEPRD.BAT` legs RB/RC, `STEPRF.BAT` legs
RD/RE. **Note that `CKRDIR.EXE` is deliberately NOT the current shipping
build** — it is kept as the binary leg RA actually ran, and `CKRDR2.EXE` is
the current one. The `CKRDBG.EXE` that ran legs RB and RC (312,740,
`5592256b…`, the version whose `deb=` was wrong) has been overwritten by
the fixed one, which is why RD/RE exist.

### One report-upstream item, found on the way past

`ckcfns.c:6914`, in `snddir()`, is an `if` with no body:

```c
    if (zfnqfp(name,CKMAXPATH,fnbuf))

    debug(F110,"snddir name 2",name,0);
```

`debug()` carries its own `;` in every build, so the body is an empty
statement and this compiles clean and silent. But `zfnqfp()`'s return value
is discarded, and eight lines later `fnbuf` is the `%s` of the listing's
`"Listing files: %s"` header — on the failure path an **uninitialised
automatic**, so the header prints stack contents and `sprintf` runs to
whatever NUL it finds. Harmless on the path this port takes, because
`zfnqfp()` succeeds; not fixed here, because what the header should say when
qualification fails is upstream's decision. `NEXT_SESSION.md` item 8.

### What generalises

**When a measurement and a working system disagree, suspect the
instrument's cost before the system's correctness.** This one had every
warning sign: the only artefact that survived was the *host's*, both of the
Victor's own channels came back 0 bytes, and the port's own source carried a
comment saying that this exact instrument distorts this exact class of
measurement. It still took two sessions and part of a third, because "long
listings wedge" is a more interesting sentence than "the log is slow" and it
got written down first.

**A collapsing packet length is a diagnosis.** C-Kermit's slow start moves
the packet length in the direction the wire is behaving. Leg NT's went
236 → 68 while the notes described the problem as a length problem at 1,414.
The series was in the log all along and nobody plotted it.

**`grep -c '^S-'` counts resends; it does not say whether they were
warranted.** Nine retransmissions in leg NT were read as the Victor failing
to see ACKs. Every one was the Victor correctly answering a NAK the host had
every right to send. **Count the far end's provocations before reading the
near end's responses as a fault.**

**And a fourth, about this session's own harness:** `pgrep -f "\./mame
victor9k"` inside an `until` loop **matches the shell running the loop**, so
the wait never ends — §16ar found exactly this and wrote it down, and it
cost time here again. `ps -ax -o comm | grep mame$` does not have the
problem. **A detector that can see itself and a detector that cannot see the
target give the same confident wrong answer.**

---

## 16ax. The untested capability set, on the wire

Written 16-17 August 2026, at a desk, no Victor in reach. **Six legs under
MAME at 9600** — SA and SB on the §16aw shipping binary, SE and SC on one
capability change, SF on the two upstream edits this section adds. **Two
upstream edits, 19 and 20 — the count goes from eighteen to twenty**, both
agreed under hard rule 1 before being written. DGROUP 48,832 →
**48,896 of 65,536 (74%)**, image 230,274 → **230,690**, needs **242,786
(237K)** — the first time the requirement has moved since §16aq — and
**smallest Victor 384K, unchanged**. Warnings 18, `ckvictor.c` 0.
md5 `5f2a1580…` → `0bdecef1…`.

§16i has carried this item since the day server mode was built: "most of the
default capability set has never been exercised … `BYE` has never been sent
either, so FINISH is the only way the far end has ever stopped a Victor
server." Every one of them is now a measurement.

### BYE works, and so does everything else the item named

Leg SB's last command was `G L`. The Victor ACKed it, ran `doclean()` and
`zkself()`, and exited through its own `atexit()` handler with the counters
intact — `Closing /dev/seriala...OK`, `rxlost=0 rxfull=0 rxpeak=22 of
4096`, `nap n=2` (the BYE handler's own 750 ms plus `tthang()`'s 500, both
of which only work because §16av made `msleep()` sleep). `zkself()` takes
the `PID_T` branch and ends at `exit(kill(getppid(),1))`, so the process
leaves with a nonzero status; nothing on DOS reads it and the exit is
otherwise clean.

| command | packet | the Victor's answer |
|---|---|---|
| `REMOTE PWD` | `G A` | `Y A:` |
| `REMOTE CD` | `G C` | `Y A:/SRVTMP`, and `A:/` gets back to the root |
| `REMOTE MKDIR` | `G m` | `Y A:/srvtmp/` |
| `REMOTE RMDIR` | `G d` | `Y srvtm/: removed` — **after this section's fix** |
| `REMOTE DIRECTORY` | `G D` | the listing; an empty directory answers `E No files match` |
| `REMOTE TYPE` | `G T` | the file, text mode |
| `REMOTE COPY` | `G K` | ACK, and the copy is in the next listing |
| `REMOTE RENAME` | `G R` | ACK |
| `REMOTE DELETE` | `G E` | `Deleting "SRVD.TXT" … 1 file deleted, 187 bytes freed` |
| `RETRIEVE` | `H` | the file, byte-exact, and gone from the next listing |
| `REMOTE SET` | `G S` | ACK |
| `REMOTE MESSAGE` | `G M` | ACK |
| `REMOTE HELP` | `G H` | the server's own capability table |
| `REMOTE SPACE` | `G U` | ` Free space: 416K` — **after upstream edit 20** |
| `REMOTE EXIT` | `G X` | ACK, clean exit |
| `BYE` | `G L` | ACK, clean exit |

And the refusals, which are as much a result as the successes, because a
server that refuses correctly is a server whose capability gate works:

| `REMOTE HOST` | `C dir` | `E REMOTE HOST disabled` | `NOPUSH`, `en_hos` 0 |
|---|---|---|---|
| `REMOTE QUERY`, `REMOTE ASSIGN` | `G V` | `E Variable query/set not available` | `NOSPL` |
| `REMOTE LOGIN` | `G I` | `E Login ignored.` | no login configured |
| `REMOTE KERMIT` | `K …` | `E Unimplemented server function` | there is no `<serve>K` in `ckcpro.w` on any platform |
| `REMOTE PRINT` | S/F/A | refused **in the A-packet ACK**, reason `+` | `en_pri` 0, `gattr()` `case 'P'` |
| `REMOTE WHO` | `G W` | `E REMOTE WHO disabled` | after this section; it was `Can't do who command` |

**`REMOTE PRINT`'s refusal is the one worth reading closely**, because it is
the one that could have written to the disk and did not. `ckcfn3.c`'s
`gattr()` sees disposition `P`, finds `en_pri` 0, and returns the refusal in
the ACK to the **attribute** packet — before any data arrives and before
`rcv_firstdata()` would have tried to `openc()` a pipe to `lp`. The host
answers with `Z` data `D` (discard) and the fixture on the image is
byte-identical afterwards.

**`MAIL` is the same case handled worse, and that one is upstream's.** The
`case 'M'` arm that would have refused it sits inside `#ifndef NOFRILLS`
(`ckcfn3.c:1769`) while `case 'P'` twelve lines below does not, so with
`NOFRILLS` defined the disposition is never checked. The Victor accepted the
F packet, ACKed the A packet, opened nothing, and answered the **first data
packet** with `E Can't open file`. Same outcome, three round trips later,
with an error message that names the wrong thing. Report-upstream item; not
fixed here.

### `--safe-server` is verified on the wire for the first time

§16i built it and checked it through `uname()`; leg SC ran it. `DIRECTORY`,
`DELETE`, `CD`, `MKDIR`, `TYPE` and `EXIT` each came back with their own
name — `E REMOTE DIRECTORY disabled`, `E REMOTE CD disabled`, `E EXIT
disabled` — and `GET SRVA.TXT` in the middle of them transferred byte-exact.
The gate is per-command and it is the right way round.

### Three defects, and the first was found by the server itself

**`REMOTE HELP` is the instrument this section did not expect to need.**
`sndhlp()` prints the capability table out of the `en_*` variables, so the
server states its own configuration in a form the client can read. It said:

```
 REMOTE SPACE       Enabled       Inquire about disk space on the server.
 REMOTE WHO         Enabled       List who is logged in to the server.
```

while `G U` and `G W` answered `Can't check space` and `Can't do who
command`. Both are served by `syscmd()`, which is a shell pipe, and
`NOPUSH` compiles its body away to `return(0)` — so both were **advertised
and impossible**, which is precisely the "turn a refusal into a failure"
that §16i's own comment in `ckvictor.c` says to avoid for HOST, MAIL and
PRINT. The initializer had the rule written above it and had not applied it
to these two.

WHO is now zeroed rather than merely left alone, because the default 2
prints as "Remote only" and 0 prints as "Disabled" — upstream does the same
thing to `en_hos` under `NOPUSH` (`ckcmai.c:1596`). **SPACE got an answer
instead**: upstream edit 20, `INT 21h AH=36h` in `ckvictor.c` behind a
`VICTOR9K` arm of `sndspace()` and `<generic>U`, both purely additive.
**Leg SF answers ` Free space: 416K` and `vtg_image_util info` reads
`Free: 416.0 KB (4.2%)` on the same volume** — two routes to the same
number, one of them through the FAT the other through DOS, which is what
makes the arithmetic (clusters × sectors/cluster × bytes/sector, all as
longs) a measurement rather than a hope.

**`REMOTE RMDIR` could not remove a directory.** `ckmkdir()` appends `/` to
the name before calling down — "Must end in `/` for `zmkdir()`",
`ckcfn3.c:133` — and on the `UNIXOROSK` arm it does that for **both**
directions. INT 21h `AH=3Ah` will not take a trailing separator, so every
`REMOTE RMDIR` this port has ever served failed with `srvtm/: ` and an empty
`ck_errstr()`. It failed from inside the directory and from the root alike,
which is what ruled out the obvious explanation before the fix was written. **Upstream's own OS/2 arm twenty lines below appends it only
when `fc == 0`**, which is the tell: someone met this on a DOS-shaped file
system before. The fix is a `ckvictor.h` macro and a nine-line function in
`ckvictor.c`, in the shape of the `mkdir()` shim already beside it — **no
upstream edit**, and `mkdir` is untouched because the same name with the
same slash created the directory in the first place.

**Every date the server reported was 1970.** That is upstream edit 19 and
§8 has it; the evidence is a pair of files that differ by one binary:

```
-rw-rw-rw-  187  Jan  1  1970  SRVA.TXT.~1~     leg SC, before edit 19
-rw-rw-rw-  187  Aug 16 22:02  SRVA.TXT.~2~     leg SF, after
```

Same file, same server, same `GET`, both md5 `225c084e…`. The listing moved
the same way — `1970-01-01 02:39:06` became `2026-08-16 22:02:02` — and the
A-packet date went from `19700101` to `120260816`. **The listing is the
symptom you notice and the attribute is the one that matters**: a client
that keeps server dates was keeping a truncation, and `SET FILE COLLISION
UPDATE` compares exactly that field.

### Two capability variables have no reader in this build

`en_ret` is assigned by `ckvictor.c` and tested **nowhere** — `RETRIEVE` is
gated by `en_del` at `<serve>H`, and `ckcfns.c:6179` even carries
`/* en_ret, */` commented out of its own extern list. `en_ena` is tested
only inside `ckuus6.c`'s `doenable()`, which is the local `ENABLE` command
that `NOICP` removes. Both are set to 3 by the initializer and neither
changes anything; they are left in place because they cost nothing and
would matter to a `KEEP_ICP` build, but nobody should test them looking for
an effect.

### What the harness did wrong, and one thing it did right

**Leg SA lost its Victor-side counters, and the cause is that the leg's
last command failed on the host.** `REMOTE EXIT` never reached the wire, so
the server sat in command-wait until `-seconds_to_run` killed MAME under it
and `STEPSA.OUT` came back **0 bytes**. Same shape as §16av's leg NF and its
full-disk redirect: **ask what a leg's terminating command does to the
channel the leg reports through.** Every leg after SA ends in `REMOTE EXIT`,
`BYE` or `FINISH` for that reason.

**Five commands failed in the *host's* parser and none of them was ours.**
`REMOTE PWD`, `HELP`, `EXIT`, `COPY` and `RENAME` all answered `?Not
confirmed` before sending a packet. They are the five that end in
`remcfm()`, and C-Kermit 9.0.302's `remcfm()` falls off the end of an empty
argument into a test for `>` or `|`. **This tree already has the fix** —
`ckuus7.c:7455`, `if (!*s) return(1);`, dated 2014-11-03 — so the bench Mac's
`kermit` is simply eight years older than the source being ported. The
workaround is the redirect form the parser is looking for: `remote pwd >
file`. `REMOTE CDUP` is a different one — 9.0.302 answers "?Sorry, REMOTE
CDUP not supported yet" and never sends `G B` at all.

**That is §16am's rule arriving from a third direction.** §16am found that a
host advertising "Hardware flow control" did not compile `POSIX_CRTSCTS`;
§16aj found that a line of upstream source is not evidence that *this* build
compiles it. Here the far end's *parser* is a version behind, so five
capabilities read as untestable when only the client was at fault.
**Before concluding that a feature does not work, check that the thing
asking for it can ask.**

**And the one that went right: `REMOTE HELP` should be the first command of
any future server leg.** It is one round trip, it costs nothing, and it
prints the whole `en_*` configuration as the server understands it — which
is how a defect that had been shipping since §16i was found in the same
session that was merely trying to exercise it.

### Timings, and why they are not the port's

Legs SB, SE and SF took host timeouts on `COPY` (2), `RENAME` (1), `MKDIR`
(1), `DELETE` of a nonexistent file (2) and an F packet (3) — 10 to 25
seconds for operations that touch one small file. Nothing was lost;
`set retry 10` covered all of them and every leg finished with
`rxlost=0 rxfull=0`. **The common factor is a directory search or a
directory write on a 168-entry FAT root**, and §16n's caveat applies at
full force: MAME's disk timing is almost certainly MAME's and not the
Victor's (0.124 s per `write()` is very slow for a real drive). **These
numbers should not be quoted as the cost of a server command on a Victor**
until a bench sitting has them; what they do establish is that the
commands complete and that the protocol rides out a slow server correctly.

## 16ay. Post-merge regression: upstream 11.0.508 lands, and nothing in the port moved

**17 August 2026, no Victor in reach.** PR #3 merged 77 upstream commits —
C-Kermit 11.0.508 plus the unreleased 11.0.509 work — onto the port branch.
This section is the regression that says the port still works. Run sheet
`HW_TEST_16ay.md`; five MAME legs at 9600 (UA, UB, UC, UD, UE); take-files
`s16ayU*.ksc`; Victor counters `v9k/legs/STEPU*.OUT`. **No upstream edit —
still twenty.** Warnings **18**, `ckvictor.c` and `ckvisr.asm` **0**.
DGROUP **48,896 (74%)**, image **230,756**, needs **242,852 (237K)**,
**smallest Victor 384K, unchanged**. md5 `d76c10b2…`.

### The edits were verified before the legs, and by diff rather than by grep

The merge commit claims all twenty edits are intact. That claim is checkable
exactly, because the merge has an upstream parent: `git diff 616e369^2 HEAD`
over the thirteen files the port touches is, by construction, **the port's
edits and nothing else** — 539 inserted lines, 15 deleted, every one of the
twenty accounted for by reading. That is a stronger check than counting
`VICTOR9K` occurrences, which is what a first pass reached for and which
cannot see an edit that survived as text while losing its guard.

**The other half is the same diff with `-w`**, which is what makes an
upstream sweep this large readable at all: 88 files and 59,006 insertions
collapse to 252 substantive lines across twelve files, because the bulk of
11.0.509 is `expand(1)` converting tabs to spaces. Two of those lines look
like behaviour changes on this port's receive path and are **not**:
`rcvfil()`'s new parentheses and `spar()`'s streaming test both group what
`&&` already bound tighter than `||`. `ckcfn3.c:1427` is a genuine fix on
the error-reason path (`reason[(CHAR) c]`, a signed-char index).
`zdtstr()`/`zstrdt()` now copy `localtime()`'s static result into an
automatic `struct tm` before reading it — adjacent to upstream edit 19, and
leg UC's dates cover it.

### Five legs

| leg | what | result |
|---|---|---|
| UA | 32 KB receive, host at t+110 | byte-exact, `rxpeak 306`, 80.768 s, 405 cps |
| UB | 32,768-byte send **by name** | byte-exact, **0 timeouts, 0 resends**, 49.354 s, **663 cps** |
| UC | server sweep: HELP, PWD, SPACE, DIRECTORY, TYPE, GET, full-root DIRECTORY, FINISH | all answered, 0 timeouts, 0 resends |
| UD | parser build, `SPDTEST.KSC` by absolute path | all four of its edits pass |
| UE | UA with the host at t+150 | **identical to UA within 56 ms** |

`rxlost = 0 rxfull = 0` on all five, `deb = 0` on all five (§16aw's guard),
`nap per = 409` on all five (§16av's), `coll = 1`, `neg = 1`, `bulk sel = 1`
with n = 14,022 / 14,009 on the two receives and 18 on the send — so edit
18's arm ran on the direction it exists for and is inert on the other, which
is §16aq's counter doing its job.

**Leg UB is the second end-to-end confirmation of upstream edit 16** and the
first under MAME: `-s SNDUB.DAT` on a file of exactly 32,768 bytes, inside
the range the 16-bit `rc` used to refuse, transferred byte-exact with no
error line. **Leg UC confirms both of §16ax's edits after the merge** —
`REMOTE SPACE` answers `Free space: 536K` from INT 21h `AH=36h` (edit 20),
and neither the directory listing nor the file-date attribute of a `GET`
reads 1970 (edit 19; the received file is md5-identical to §16ax's and
carries `Aug 16 22:02`). The full-root listing is 162 files and 8,312,507
bytes with a summary line and a clean exit, which is §16aw's leg RA at
slightly larger scale and the standing evidence for §16av's `MAXWLD` 256 /
`SSPACE` 4096.

### The one thing worth carrying forward is a stall nobody has costed

UA and UE both spent **~27 seconds between the F packet and its ACK** —
three timeouts at 8, 16 and 24 s — and then ran the whole data phase clean.
UA's first reading of that was "the host got there before the Victor was
listening"; **leg UE was spent to test it and refuted it**, because starting
the host 40 s later reproduced UA to 56 ms. The Victor answers the S packet
at t = 0 and is inside `rcvfil()` for the next 26 s.

**It is not the merge**: §16aj leg FA (3 timeouts, 6 resends, 75.906 s) and
§16ar leg WD (4 timeouts, 7 resends, 83.013 s) have the same shape from
before it, and leg WD — the closest control this tree holds — is **2.2 s
slower** than UA and UE, not faster. Take the stall out and the data phase
is 32,768 bytes in 53.8 s = **609 cps**, which is §16n's 633 and §16u's 632.
**So a whole-run cps at 9600 under MAME is ~405 and a data-phase cps is
~610, and a session quoting either should say which it has.** The stall
itself is an old, unlooked-at cost on the receive-file-open path and is the
obvious next MAME question.

### What the merge did move: the parser build changed machine class

The shipping build grew 66 bytes and stayed on a 384K Victor. The `KEEP_ICP`
build grew about 25 KB: **429,890 (419K, smallest Victor 512K) at §16ax,
453,602 (442K, smallest Victor 640K) now**, DGROUP 59,024 → **59,632 (90%)**
of 65,536. Nothing ships from that build — it is the regression build §16y
exists for — but it is the first upstream merge to move a machine class, and
the margin left inside DGROUP is now 5,904 bytes. **Watch it on the next
merge**; the lever if it ever matters is `-zt`, and §16y's warning about
`-zt` and the receive ring (`__near`) is still the thing to read first.

## 16az. FreeDOS for Victor: the second DOS runs, and it runs on the second channel

**18 August 2026, no Victor in reach.** Six MAME legs at 9600 on **FreeDOS
for Victor** — the DOS this port has claimed since §16a and had never once
been run on. Run sheet `HW_TEST_16az.md`; legs FDB, FDC, FDE, FDF, FDG plus
one capture that is not a leg; Victor counters `v9k/legs/FD*.OUT` and the
capture at `v9k/legs/FDBOOT-chanA-trace.txt`. **No code change of any kind:
the binary is §16ay's, md5 `d76c10b2…`, bit for bit. No upstream edit —
still twenty.**

### The headline is one line of a counter report

```
v9k: dos oem=fd ver=622 irq1=09
```

`AH=30h` returned BH = 0xFD, `v9k_dosid()` took the FreeDOS arm, and IRQ1
was hooked on **INT 09h** instead of MS-DOS 3.1's 41h. **§16av built that
branch and recorded that neither of its two FreeDOS arms had ever
executed**; this is the first one running. Underneath it, three more things
ran for the first time on this DOS and all worked: `COM1`/`COM2` open as
FreeDOS character devices, **§1b's direct chip-programming fallback**
(FreeDOS's COM device carries attribute `0x8000` with no IOCTL bit, so
`AX=4402h` fails and the §11a IOCTL path is simply not available), and then
the whole §1e data path — assembly ISR, receive ring, polled transmitter —
on INT 09h.

**Both directions are byte-exact.** Leg FDE received 32,768 bytes at **685
cps with 0 damaged packets, 0 timeouts and 0 retransmissions**; leg FDF sent
32,768 bytes **by name** at 646 cps, 0/0, which is the **third** end-to-end
confirmation of upstream edit 16 (§16ah leg BS on the bench, §16ay leg UB
under MAME on MS-DOS) and the first on FreeDOS. `rxlost = 0 rxfull = 0` and
`deb = 0` on every leg; `wfile n = 4` reproduces §16n, `rxbytes = 37,569`
reproduces §16af, `coll = 1` §16av, `neg = 1` §16ar, and `bulk sel = 1` with
n = 11,469 on the receive and **20 on the send** is §16aq's counter showing
edit 18's arm live on the direction it exists for and inert on the other.

### Channel A is not a Kermit wire on this kernel, and a capture is what said so

Leg FDC ran the receive on **channel A** and came back byte-exact — but with
**5 damaged packets, 1 timeout and 6 retransmissions**, all in the S/F
handshake, and `rxbytes = 39,834` against the clean leg's 37,569.

The cause is not ours. Booted with `AUTOEXEC.BAT` cut to `ECHO OFF` and
**nothing of this port running at all**, channel A produced **2,861 bytes in
150 seconds**. It is the myfreedos kernel's own trace, and it is **live
rather than boot-only**: `kernel/entry.asm:280` busy-waits on TBE and writes
an `H` to the µPD7201 channel A data register at `E000:0040` **on every INT
21h call**, with `I42`/`DRWS`/`DWU_ent` from the SASI and disk paths on top
and a `W` from `victor_int13.asm:804`. The guard is `%ifdef VICTOR9000`,
always on for this target: **there is no runtime switch.** Since hard rule 6
puts every console write and every file write of this port through INT 21h,
a Victor transferring a file on that kernel is a Victor generating trace
bytes the whole time.

**The fix cost nothing, because the tracer is hardwired to `E000:0040`/`0042`
and channel B is `0041`/`0043`.** This port already selects channel B from a
device name ending in `B` or `2` (`v9k_ser_selchan()`), FreeDOS exposes
`COM2` on the same INT 14h driver, and MAME has `-rs232b`. Leg FDE is leg FDC
one channel over — same binary, same fixture, same rate, same harness — and
every damaged packet and every retransmission disappears. **That is what
confirms the diagnosis rather than merely asserting it.** The alternative,
rebuilding the myfreedos kernel with those trace sites guarded, is worth
proposing to that project on its own merits — the busy-wait sits inside every
INT 21h call and costs every program on the machine — but this port does not
need it.

**`-bitb` is ambiguous when two null_modems are attached.** FDE's first
attempt asked for a socket on `-rs232b` and a bitbanger file on `-rs232a`,
and the socket bound to the wrong slot: no `/tmp/v9000`, host FAILURE,
0.000 sec. Capture channel A in a run of its own.

### `rxpeak = 19` is §16m confirmed from a new direction

The clean leg's ring peak was **19 of 4,096**, against 306 on §16ay's MS-DOS
receive. That is not a new property of FreeDOS. §16m established that the
peak measures the ring filling during the **host's retransmission**, which
with a window of one is the only moment the host transmits without waiting
for our ACK; this leg had zero retransmissions, and `peakat = 76` puts the
peak 76 bytes into the stream. **A leg with no resends has no peak to
measure, and that is the same finding §16ag reached by absence.**

`norx = 0 othrx = 0` answers the shared-IRQ1 question **by half**: channel A
was being written throughout and produced no spurious interrupts on IRQ1 —
but the tracer is a *polled transmitter*, so this covers the transmit half of
the shared-channel case and not the receive half. Do not quote it as more.

### Two things this sitting could not settle, and one retraction

**The console arm is still unverified.** Leg FDA's screen carried a fragment
reading `FRKJ 0002` and the first reading of it was "our VT52/ANSI console
arm is printing garbage on FreeDOS". **That is retracted**: `victor_trace.c`
writes the *kernel's* debug region to screen rows 12–24, which is where the
fragment was, and nothing in this sitting tells our output from the kernel's.
Leg FDG was spent trying to settle it and **failed to engage the display at
all** — C-Kermit draws the fullscreen display during a transfer, and a FINISH
with no host never starts one, so a clean screen is not evidence. The leg
that settles it is FDE re-run without `--nodisplay`, snapshotted during the
data phase.

**And §16ay's ~27 second stall did not happen here.** Every MS-DOS MAME
receive in this tree back to §16aj spends ~27 s between the F packet and its
ACK — §16ay located it inside `rcvfil()` and called it the obvious next MAME
question. FreeDOS shows none of it. **That is a lever on the question and not
an answer to it**: this is a cross-sitting comparison of two operating
systems on two filesystems and two disk images with **no adjacent control**,
which is exactly the arrangement §16al identified as the one that does not
work and the reason its "+11%" was withdrawn. One pair of legs, one per DOS,
same day, would make it a measurement. Nothing here separates the DOS from
the FAT geometry from the disk image.

One counter to watch on this DOS: **`nap per=` read 682, 819, 682 and 819
across the four legs that reported it**, where §16ay's five MS-DOS legs all
read **409**. §16av's busy loop calibrates against the 500 ms DOS clock at
run time, so a 20% swing inside one sitting says the calibration does not
repeat here. No leg depended on it — `msleep()` backs `tthang()` and
`tcsendbreak()`, and nothing exercised either — but anything that comes to
rely on `nap()` timing on FreeDOS should measure it first.

### Getting a file onto the image: `v9k/tools/hybridfat.py`

The image is the **Victor 9000 hybrid** format
(`~/projects/myfreedos/docs/victor/VICTOR_HYBRID_DISK_STRUCTURE.md`): Victor
drive label at sector 0 for the ROM's IPL vector, stage-1 loader in sectors
1–128, and an **IBM-style FAT16 BPB at sector 129** whose `hidden_sectors`
field is 129 and is the bridge. **Neither mtools nor `vtg_image_util` can
read it** — the first looks for a BPB at sector 0 or an MBR partition table,
the second for Victor virtual volumes — and neither should be pointed at it.
`copy_to_victor_dos.py` in the myfreedos tree cannot do it either and should
not be adapted: it hardcodes a *Victor MS-DOS* geometry (volume at sector 2,
4 sectors/cluster, 38-sector FATs) that matches nothing in this image.

`hybridfat.py` does `info`/`list`/`put`/`get`/`del`. The design point worth
keeping is that **it does not assume 129**: the BPB lives at `hidden_sectors`
and `hidden_sectors` is a field *inside* the BPB, so it tries 129 then 0 and
accepts a candidate only when the sector it was found at agrees with the
field it read. The same tool then works on a plain floppy image, and a wrong
guess fails loudly instead of quietly reading the middle of a FAT. **The
reader was verified before the writer was trusted** — two files already on
the image round-tripped md5-identical, one of them multi-cluster so the chain
walk was exercised — and then `CKERMITW.EXE` in and back out, also identical.

The volume is FAT16, 512 B/sector, **16 sectors/cluster (8 KB)**, 2 FATs of
127 sectors, root at 384 (512 entries), data at 416, 32,274 clusters.
**One unexplained caution:** the file is 506,848 sectors and the BPB declares
516,800 — **9,952 sectors short**. Everything here landed in low clusters and
nothing touched the gap, but a tool that allocates high on this image will
write past the end of the file.

### The method lesson is §16an's, for the third time

Every reading before the capture was a counter inside one of the two
programs, and both were right about what they had done: the Victor said
`rxlost = 0`, the host said five damaged packets, and the first hypothesis on
the table was our own console code. **The question was about a wire and it
was settled in 150 seconds by putting a capture on the wire with nothing of
ours running.** §16an wrote that rule about RTS and §16am wrote the
neighbouring one — measure that the far end can do what your experiment
assumes. This is a third face of it: **before running a leg on a machine you
have not run on before, capture what that machine puts on the wire when your
program is not there.**

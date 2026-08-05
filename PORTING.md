# Porting C-Kermit 11 to the Victor 9000 / Sirius 1

Running notes for the serial-only Victor 9000 port. Branch: `victor9k-port`.

**Status:** all 24 modules of the minimal build compile clean for
`ia16-elf-gcc`, including `ckutio.c` now that `victor/sys/termios.h` supplies
the header the stock newlib is missing. Nothing has been linked or run on
hardware yet.

**Verdict:** this is a thin-platform port, not a rewrite. The blocker people
expect — a modern flat-memory codebase that cannot be squeezed into 64K — did
not materialise. The measured static data is **32,325 bytes, 49% of one 64K
DGROUP**, with the protocol engine untouched.

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

`CKERMIT.EXE` is an **MS-DOS program that drives the Victor's serial hardware
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

Built with `ia16-elf-gcc 6.3.0` (tkchia's `ppa:tkchia/build-ia16`) inside the
`ia16-ubuntu-2` container, which runs under Apple's native `container` service —
**not Docker**. `~/projects` on the host is mounted at `/mnt/projects` inside.

```sh
container list --all                                   # ia16-ubuntu-2, running
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victor9k.mak"
```

`ia16-elf-gcc` supports only `-mcmodel=tiny|small|medium`. There is **no
compact, large, or huge model** — verified directly:

```
tiny OK   small OK   medium OK
compact  error: unrecognized command line option '-mcmodel=compact'
large    error: unrecognized ...
huge     error: unrecognized ...
```

So data pointers are always near, and **`.data` + `.bss` + heap + stack must
all fit in one 64K DGROUP**. `-mcmodel=medium` gives far code (multiple code
segments, ~1MB), which is why 296KB of text is not a problem.

Open Watcom *does* have compact/large/huge and does allow far data. §9a/§9b
concluded it was **not needed** for the serial-only milestone, and that still
holds. It has since been *built*, as a second target of the same tree —
`victorow.mak`, Open Watcom V2 at `/opt/open-watcom-v2/rel` in the same
container. All 24 modules compile and the program links, at 59% DGROUP against
gcc's 79%, and with the interactive command parser §9c had to cut back in. See
**§9d**, which is the measurement §9c asks for.

### The toolchain already targets MS-DOS, at medium model

This was measured, and it removes most of what §12 used to describe as work.
`__MSDOS__` is defined **by default**, and `/usr/ia16-elf/lib/medium/` ships a
complete DOS target for exactly the model we build at:

```
libdos-m.a                              medium-model DOS libgloss (INT 21h)
dos-m-c0.o                              DOS C runtime startup
dos-mm.ld dos-mml.ld dos-mms.ld ...     linker scripts producing a DOS .EXE
```

So the host-OS half of §2 needs almost nothing written. See §12 for the exact
coverage and the short list of what is still missing.

---

## 4. Build

```sh
make -f victor9k.mak          # build all objects, then link
make -f victor9k.mak sizes    # DGROUP report + largest static objects

make -f victorow.mak          # the same tree, Open Watcom large model (§9d)
make -f victorow.mak sizes    # DGROUP report, read from wlink's map
```

The entire feature configuration lives in `ckvictor.h`, force-included ahead of
every file with `-include ckvictor.h`. Nothing else in the tree includes it, so
it cannot affect any other platform. Keep new `-D` options *there*, next to the
comment explaining why they exist — not in the makefile.

`victor/` holds headers that fill gaps in the toolchain, reached via `-Ivictor`
(`-i=victor` under Watcom): `victor/sys/termios.h` and `victor/sys/ioctl.h`
(§12), both toolchain-neutral. `victorow/` holds the ones only Open Watcom
needs, reached via `-i=victorow` and therefore invisible to the gcc build
(§9d). Same principle as `ckvictor.h`: on the include path only for this build,
so it cannot affect anything else.

---

## 5. Source files: in and out

### In (24 modules)

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
upstream code. Everything below them is ours, and lives in `ckvictor.c` plus a
small newlib libgloss (§12).

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

Six small, guarded edits. None changes behaviour on any other platform.

1. **`ckcdeb.h`** — wrapped the `sig_t` typedef in `#ifndef CK_NO_SIG_T`.
   newlib (and macOS) already define `sig_t`.
2. **`ckcker.h`** — wrapped `SCANFILEBUF` in `#ifndef`. It was hard-coded to
   49152 and is used as an **automatic array**, i.e. a 48K stack frame. Fatal
   on a 64K DGROUP; now `-DSCANFILEBUF=2048`.
3. **`ckcfns.c`** — wrapped `RQ_MAXTOK` in `#ifndef`. `rq_tok` is
   `RQ_MAXTOK * (CKMAXPATH+1)` and was the largest static object in the
   program at 9280 bytes; now 2064.
4. **`ckucmd.c`** — added a `VICTOR9K` branch so console input goes through
   `coninc()`/`conchk()` instead of reaching into glibc `FILE` internals
   (`stdin->_IO_read_ptr`), which do not exist in newlib.
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
   `void ;`. gcc calls that a useless-type-name warning and carries on; Open
   Watcom calls it E1026 and stops, in all 15 modules that include
   `ckcfnp.h`. This is the one edit §9d could not avoid, and it is a genuine
   upstream inconsistency rather than a Victor accommodation: a platform that
   does not define `NODISPLAY` sees no change at all.

Items 2, 3 and 6 are worth offering upstream regardless of this port. 2 and 3
are latent hazards on any small-memory target; 6 is a bug on any compiler
stricter than gcc.

---

## 9. Memory budget

Measured, 24 modules, `-mcmodel=medium -Os`:

```
.text = 302,896 bytes    far code, medium model, ~1MB limit — not a concern
.data =  11,748 bytes
.bss  =  20,563 bytes
STATIC DGROUP = 32,311 of 65,536  (49.3%)
free for heap + stack + libc = 33,225 bytes
```

Largest static objects: `rq_tok` 2064, `optlist` 2050, `tbl` 1632,
`cmdtab` 1272, `numbuf` 1056, `cmdatebuf` 1028, `cmdstr` 1025, `mybuf` 1024.
Nothing else over 1KB.

Projected full budget:

| Item | Bytes |
|---|---:|
| Static data + bss | 32,311 |
| Packet buffers (`SBSIZ`+`RBSIZ`, malloc'd) | 8,192 |
| newlib stdio + bss | ~6,000 |
| Serial RX/TX rings (256 + 256) | 512 |
| Stack | ~8,000 |
| **Total** | **~55,000 of 65,536** |

**~10KB headroom.** Tight but real. This is why `ckvictor.h` sets `MAXSP`/
`MAXRP` to 1024 and `SBSIZ`/`RBSIZ` to 4096 rather than the `DYNAMIC` defaults
of 9024/9050, which would have cost 18KB in packet buffers alone.

If headroom is needed later, in order of payoff: cut `RQ_MAXTOK` further,
drop `SHOW` commands (`ckuus5.c`, 2432 bytes of data+bss), reduce `CKMAXPATH`.

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

Type sizes under this build: `int` 2, `long` 4, pointer 2 (near data) / 4 (far
code), `size_t` 2, `CK_OFF_T` = `off_t`.

`CK_OFF_T` is the file-offset type used for RESEND/REGET restart. On a 16-bit
target it resolves to newlib's `off_t`, and if that were `int` rather than
`long`, restart would break above 32KB. **Verified: `sizeof(off_t) == 4`**
(static-assert probe, `-mcmodel=medium`). Restart is good to 2GB, far beyond
any Victor disk. This question is closed.

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
not do long filenames, because `readdir()` returns what DOS FindFirst puts in
the DTA and that is 8.3 and nothing else.

This is the same class of defect as `SCANFILEBUF` (§8) and it was found the
same way: by measuring rather than reading. **`-fstack-usage` is cheap; run it
after any change to `ckufio.c`, `ckuusr.c` or the size limits in
`ckvictor.h`.** Two frames still above 1KB (`docmd` 1152, `zcopy` 1114) are
both non-recursive.

`MAXNAMLEN` itself is now pinned at 12 in `ckvictor.h`, which is a *heap*
saving rather than a stack one: it sizes `d_name[]` inside `struct dirent`,
and `struct dirent` is the DOS DTA for our `readdir()` (§12). newlib defaults
it to 259 in anticipation of long-filename support that does not exist, making
`struct dirent` 290 bytes; at 12 it is 43 bytes — exactly the size of a DTA —
and a `DIR` is 48. `traverse()` holds one open `DIR` per level.

---

## 9c. `.rodata` is in DGROUP, and it cost us the command parser

**This section supersedes the headline number in §9.** The 49.3% figure was
real but it was not the whole budget, and the shortfall is not small.

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

Yes. Both toolchains can, and it was tested rather than assumed. The question
is what it costs and whether it is needed yet.

### What each toolchain supports

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
safely, with no source changes.** ia16-gcc cannot match that in medium model.

### Why we are not doing it yet

1. **There is no pressure.** Static DGROUP is 32,325 of 65,536 (49%), the
   packet pool is 8KB, and nothing anywhere is over 64KB. The largest single
   object is 2,064 bytes.
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

### When it would be worth it

The scenario that genuinely needs far data is **large windows × long packets**.
`MAXWS 32` × `MAXSP 4096` is a 132KB packet pool — that cannot fit a single
DGROUP at any tuning. If that becomes the goal, the right move is **not**
`__far` annotation under ia16-gcc; it is switching to **OpenWatcom large model
with `-zt`**, where the buffers move out of DGROUP by compiler flag and the
source stays upstream.

The cost of that switch is real and should not be paid speculatively: Watcom
uses OMF objects and its own C library, so any newlib work does not carry over.
(Note that under the §2 architecture this is a *smaller* cost than it used to
be — we need far less from the C library now. See §12.)

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

**Net effect on the plan:** unchanged in the near term — at 49% DGROUP with a
4KB/4KB pool there is nothing to fix.

---

## 9d. Open Watcom builds the same port, and the parser comes back

§9c ends with "nothing short of removing the command parser fits, and that is a
property of the toolchain, not of C-Kermit." That was true and it is still
true — **of `ia16-elf-gcc`**. Open Watcom has a real large model, so the claim
was worth testing rather than assuming, and the answer is now measured rather
than estimated.

`victorow.mak` builds the identical source tree with Open Watcom V2's 16-bit
`wcc`/`wlink`. It is a second build of the same port, not a fork of it: the
feature configuration is still `ckvictor.h` and only `ckvictor.h`, `ckutio.c`
and `ckufio.c` are still stock upstream, and `ckvictor.c` is still the only
non-upstream C file. Open Watcom V2 is already installed in the same
`ia16-ubuntu-2` container, at `/opt/open-watcom-v2/rel`, with the 16-bit DOS
libraries (`lib286/dos/clib{s,m,c,l,h}.lib`) present.

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"
```

### Measured: all 24 modules compile and the program links

Same feature set as the gcc build (`NOICP` on), `-ml -0 -os -zc`:

| | ia16-elf-gcc, medium | Open Watcom, large |
|---|---:|---:|
| near data (DGROUP) | 52,000 of 65,536 (79%) | 38,704 of 65,536 (59%) |
| left in the segment | 13,536 for heap **and** stack | 26,832, stack already counted |
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

### What this does *not* settle

- **The 7201 driver is still unwritten** (§11), for either toolchain — and
  §16a is where that finally shows up as a wire-level symptom.
- **Which toolchain the port should ultimately use is not decided here.** This
  section establishes that the large model removes the constraint that forced
  §9c's amputation. §16a establishes that the two builds are
  indistinguishable on the wire. Neither decides the question.

The console path was an open question here and §16a closed it: under gcc,
`ckvictor.c` supplies newlib's `_read_r`/`_write_r` and does the CR/NL
translation there; Watcom's runtime has its own `read`/`write` over INT 21h
and that override does not exist. Watcom's text-mode stdout turns out to do
the same job — output is correctly formatted on both DOSes.

### What the second toolchain cost

Compiling stock upstream Unix modules against a DOS libc that never pretended
to be POSIX needs a compatibility layer that newlib made unnecessary. It is
seven files, all new, none upstream:

| File | What it fills |
|---|---|
| `victorow.mak` | build, and the DGROUP report read from `wlink`'s map |
| `victorow/pwd.h` | `struct passwd`; Watcom has no password database at all |
| `victorow/sys/utsname.h` | `uname()`, for `\v(host)` and the version banner |
| `victorow/sys/time.h` | `struct timeval`/`gettimeofday()` for the FP timers |
| `victorow/termios.h` | forwarder to `victor/sys/termios.h`, as newlib's is |
| `victorow/ckowsys.h` | declarations for the process-model stubs. Watcom does not declare `ttyname()` etc. at all, and in a large model an implicit `int` return **truncates a far pointer** |
| `ckvictor.h` §`__WATCOMC__` | header surgery, listed below |
| `ckvictor.c` §`__WATCOMC__` | `gettimeofday`, `uname`, `link`, `kill`, `getpwent`, and an `intdos()` version of the INT 21h console poll |

The `ckvictor.h` section is the interesting part, because it demonstrates the
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

### Written but never run on hardware

- **Interrupt-driven receive.** `kernel/victor_int14.asm` has the whole
  apparatus: per-channel `SERPORT` descriptors, 256-byte RX/TX rings, an IRQ1
  ISR with the MS-DOS 3.1 stack-switching pattern. But both channels ship with
  `irq_enabled = 0` and IRQ1 masked at the PIC. The note dated 2026-07-14 says
  the IRQ-buffered path produced no output and hung `ctty COM2`, and that
  re-enabling requires verifying the µPD7201 interrupt-acknowledge sequence
  (Reset Tx Int Pending `0x28` / RETI) on real hardware.

### Why the ISR is on the critical path for 38400 but not for the milestone

At 38400 8N1 a byte arrives every ~260µs. The µPD7201's receive FIFO is three
deep, so a polled reader has well under a millisecond of slack. That is fine
until Kermit writes a received packet to floppy or SASI — a multi-millisecond
blocking operation during which polled RX drops bytes on the floor.

But it only bites when the line is busy *while* Kermit is writing. With
window 1 and streaming off, the sender waits for an ACK per packet, so the disk
write happens on an idle line and **polled RX is correct at any speed** — just
slow. Windows and streaming are what make the ISR mandatory.

That gives a clean staging: **polled first for the milestone, ISR before the
speed and windowing work.** The ISR bring-up does not block getting a file
across the wire.

---

## 11. Serial driver: design

Lift the working parts of `kernel/victor_int14.asm` — the `SERPORT` descriptor
layout, the ring buffers, the ISR with its stack-switching prologue, the chip
init sequence — into `CKERMIT.EXE`. Do not call INT 14h at runtime.

Rationale:

- INT 14h AH=00h has three baud bits; the table in `victor_int14.asm` stops at
  index 7 = 9600. 38400 is divisor 2 and simply cannot be requested through the
  standard API.
- INT 14h has no "bytes queued" call. `ttchk()` needs exactly that, and
  `ttinl()` wants to pull a whole packet in one go rather than one byte per
  software interrupt.
- Owning the chip means Kermit does not depend on the host DOS's serial state —
  including the not-yet-root-caused DGROUP writer near `serport_b` that forced
  the `.have_port` descriptor self-repair hack.

Ownership protocol, on `SET LINE`:

1. Detect host DOS → resolve serial IVT slot (`0x41` or `0x09`, §2).
2. Save the old vector and the 8259 mask.
3. Mask IRQ1, reset the channel, program WR4/WR3/WR5/WR1, set the VIA clock
   enable bit, write the 8253 divisor.
4. Install our ISR, unmask IRQ1.

And the exact inverse on `ttclos()` / exit / Ctrl-Break / critical error. A
Kermit that leaves IRQ1 hooked after exiting will take the machine down.

Channel choice: **use channel A for Kermit** where possible, leaving channel B
for `CTTY COM2`. They share IRQ1, so the ISR must poll both RR0s; but only one
of the two owners can be Kermit at a time.

---

## 12. The layers below C-Kermit

`ckutio.c` and `ckufio.c` are stock Unix modules that compile clean for ia16 and
express everything in POSIX terms. Keep them. What has to be supplied is the
layer *underneath*, and under the §2 architecture that layer is small.

### Does the Unix TTY layer sit on newlib?

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

If per-byte overhead through newlib's `read()` turns out to hurt at 38400, add a
`VICTOR9K` fast path in `ttinl()` only — that is one function, not a rewrite.

### libgloss: mostly already there

An earlier draft of this document said the INT 21h shim would be "the bulk of
the remaining non-driver work." That was wrong, and the correction is the single
most useful measurement in this section. `libdos-m.a` in the medium multilib
(§3) already implements, over INT 21h:

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

### Directory reading: done

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
**The serial side is a stub returning 0 and it is the driver's to finish (§11);
it must answer from the RX ring buffer, where the count is real.** Until the
driver exists there is no port to have bytes waiting on, so 0 is correct rather
than a placeholder — but this is now on the critical path for milestone step 8.

### Stubs in `ckvictor.c` that collided — resolved

Determined by diffing `ckvictor.o`'s symbol table against `libdos-m.a` +
`libc.a` + `libg.a`, rather than by waiting for the linker. Exactly the three
predicted, and no others:

| Symbol | Resolution |
|---|---|
| `dup2` | stub removed; library has it (INT 21h `46h`) |
| `putenv` | stub removed; library has it |
| `getpid` | stub removed; library probes INT 21h `AH=87h` with CF pre-set, so it degrades safely on a DOS that lacks it. `getppid` / `getpgrp` / `tcgetpgrp` remain ours. |

`opendir` / `readdir` / `closedir` / `ioctl` are **not** in any library, which
confirms the "FIXME" above — they are ours alone.

`realpath` does exist in the library, so `NOREALPATH` is now redundant. Left
defined: it costs nothing and removing it would pull `realpath` into the link.

**Still genuinely ours, keep stubbed:** `fork` `execl` `execvp` `wait` `getuid`
`geteuid` `getgid` `getegid` `setuid` `setgid` `getppid` `getpgrp` `tcgetpgrp`
`getlogin` `getpwnam` `getpwuid` `ttyname` `ctermid` `alarm` `sysconf`
`readlink` `umask`, plus the symbols owned by excluded modules (`conect`,
`connv`, `mdmtyp`, `nvlook`, `ck_bracketaddr`).

### Console: does anything shortcut to BIOS?

**No. Answered by disassembly, not by assumption.** Every interrupt instruction
in `libdos-m.a` is `INT 21h` — 37 of them, no exceptions:

| Object | INT | Object | INT |
|---|---|---|---|
| `libdos-m.a` (all 24 objects that trap) | `21h` only | `libc.a` | **no interrupts at all** |
| `dos-m-c0.o` (crt0) | `21h` ×2 | `libgcc.a` | none |

No `INT 10h`, no `INT 16h`, no `INT 13h`, no `INT 14h`, no BIOS data area. The
standard handles get no special treatment whatsoever: `_read_r` is a bare
`AH=3Fh` and `_write_r` a bare `AH=40h`, with the fd passed straight through to
DOS. **The one-binary-two-DOSes property of §2 holds at the library layer.**

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
   now compile clean and DGROUP measures 32,311 of 65,536 (49.3%).
1a. ~~**`opendir`/`readdir`/`closedir`, the four small stubs, `ioctl`/`FIONREAD`,
   and the guard-macro collisions.**~~ **Done** — all in `ckvictor.c`; still
   24 objects, 0 warnings, DGROUP unchanged (§12, §14).
2. ~~**Link `CKERMIT.EXE`.**~~ **Done** — 218KB, and it required `NOICP` plus
   `-mnewlib-nano-stdio` to fit (§9c).
3. ~~**A prompt, on FreeDOS.**~~ **Superseded and done differently.** There is
   no `C-Kermit>` prompt — `NOICP` removed it (§9c). What was proven instead,
   under MAME on FreeDOS for Victor: the binary loads, initialises, parses its
   command line, prints correctly formatted output through an INT 21h-only
   console path, finds a file, starts the protocol engine, and exits cleanly
   (§16). **Not yet proven on Victor MS-DOS 3.1** — that is still the other
   half of the dual-target claim and needs a 3.1 boot image.
3a. **Fix wildcard expansion** (§15). `-s FILE` works; `-s *.COM` finds
   nothing. Blocks any multi-file transfer.
4. **7201 driver in `ckvictor.c`, polled, vector auto-detected.** `SET LINE` /
   `SET SPEED` / `SHOW COMMUNICATIONS`. Verify against a loopback plug before
   involving another machine.
5. **`SEND` one small binary file** at 9600 to a known-good Kermit, short
   packets, window 1, streaming off. This exercises the whole engine end to end
   and is the real milestone.
6. **`RECEIVE`, then `GET`, then `SERVER`** — still at 9600, still polled.
7. **Bring up the RX ISR and ring buffer** as its own task, standalone, on real
   hardware. Verify the µPD7201 interrupt-acknowledge sequence that
   `victor_int14.asm` flags as unproven. Instrument dropped-byte counts.
8. **Turn on long packets, then windows, then streaming**, one at a time,
   re-measuring free memory at each step.
9. **Push to 19200, then 38400.**

Only after all that is CONNECT worth considering — and it should be written
fresh as a small polling loop over `ttinc()`/`coninc()` in `ckvictor.c`, not
ported from `ckucon.c` (needs `fork()`) or `ckucns.c` (needs `select()`).

---

## 14. Compile log

All 24 modules in §5 compile with **zero errors** at `-mcmodel=medium -Os`,
reproduced end to end:

```
$ make -f victor9k.mak            → 24 objects + CKERMIT.EXE (218KB), 0 errors
  --- near data (DGROUP), from the linker, including libc ---
    end of .bss = 52000 of 65536 (79%)
    left for heap + stack = 13536
```

**Trust the linker's figure, not `make sizes`.** The `sizes` target measures
objects and files `.rodata` under "text"; the real near-data total is 79%, not
49.3%, and libc adds ~26KB on top of the objects. See §9c — this mismeasurement
is what hid the fact that the interactive command parser could never fit.

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

and it buys nothing, because `dofast()` computes `wslotr = RBSIZ/MAXSP = 4`
slots and the negotiated window can never exceed what a 4096-byte pool carves.
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
| `conchk()`/`ttchk()` constant 0 | `FIONREAD` undefined → SIGQUIT fallback. Supplied `victor/sys/ioctl.h` + `ioctl()` (§12) |
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
makes `\dev\seriala` exist; `PORTSET A 9600 NONE 1 8` configures it. So there
is a working OEM serial driver to aim at long before ours (§11) exists.

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

## 15. Open questions

**Closed since the last revision**

- ~~Why is `MAXWS` redefined?~~ `ckcker.h` defines it unguarded, so it always
  wins; the real value is 32. The §9 buffer arithmetic is unaffected. (§14)
- ~~Does `libdos-m.a` shortcut to BIOS anywhere?~~ **No** — every interrupt in
  the archive is INT 21h, and `libc.a` has none at all. (§12)

**A decision that is yours, not mine**

- **Should `ckcker.h`'s `MAXWS` be wrapped in `#ifndef` — a sixth guarded
  upstream edit?** It would be a one-line change matching what that same file
  already does for `MAXSP`, `MAXRP`, `SBSIZ` and `RBSIZ` four lines below, it
  changes nothing on any other platform (no other build defines `MAXWS`), and
  it reclaims ~736 bytes (§14). Hard rule 1 says to ask rather than do this
  quietly, so it is not done. The alternative is to accept 32 and the 736
  bytes, which is what the tree does today and is perfectly survivable at 49%
  DGROUP.

**Still open**

- **Wildcard expansion returns nothing.** `CKERMIT -s *.COM` reports
  "No files for -s" on a disk full of `.COM` files, while `-s CGATEST.COM`
  finds its file and starts the protocol. So `opendir`/`readdir` are reached
  by one path and not the other, or the scan runs and matches nothing. Not a
  heap problem — it survives the `SBSIZ` fix. **This is the top item.** The
  path to instrument is `nzxpand` → `zxpand` → `fgen` → `splitpath` →
  `traverse` → `opendir("./")` in `ckufio.c`. `NODEBUG` is on, so there is no
  `debug()` log; the cheapest instrument is a temporary `_write_r` trace of
  the pattern string `opendir()` actually receives.
- **The serial arm of `ioctl(fd,FIONREAD)` returns 0** and must be finished by
  the 7201 driver from its RX ring count. Correct today (there is no port yet)
  but on the critical path for milestone steps 8–9, because `ttchk()` is what
  windowing and streaming read. (§12)
- ~~**`coninc()` still does a cooked `read(0,&ch,1)`.**~~ Done — `_read_r`
  now does raw `AH=07h` input with VMIN=1 semantics (§16). **Untested**: no
  path in the current `NOICP` build reads the console, so this code has never
  actually run. It will first matter for `-x` (server mode) interruption.
- **Heap headroom is the binding constraint now, not static DGROUP.** 13,536
  bytes shared between heap and stack, against 21% of DGROUP still free.
  Anything that raises `SBSIZ`/`RBSIZ`/`MAXSP`/`MAXRP` must be checked against
  a real run, not against `make sizes`. (§9c, §16)
- Does the FreeDOS OEM byte (INT 21h AH=30h → BH) actually come back as `0xFD`
  on the Victor build? The whole dual-target vector detection rests on it. A
  fallback (`SET SERIAL-VECTOR` or a command-line switch) is cheap insurance.
- Does Victor MS-DOS 3.1 install its own handler on IRQ1 for an AUX/COM device?
  If so, Kermit must quiesce it, not just save and restore the vector.
- What does the µPD7201 interrupt-acknowledge sequence actually need? This is
  the one unproven hardware item (§10) and it gates 38400.
- Real stack size in the DOS environment — set it explicitly at link time
  (step 2) rather than inheriting a default. Much less alarming than it was:
  `traverse()` is 98 bytes/level now, not 1066 (§9), so the sizing is driven by
  the deepest *non*-recursive chain instead. `docmd()` at 1152 and `zcopy()` at
  1114 are the two largest frames.
- `SET LINE` naming: `COM1`/`COM2` for channels A/B is the obvious choice and
  matches the FreeDOS convention, but Kermit is talking to the chip directly, so
  the names are ours to define.

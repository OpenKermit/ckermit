# Porting C-Kermit 11 to the Victor 9000 / Sirius 1

Running notes for the serial-only Victor 9000 port. Branch: `victor9k-port`.

**Status:** **it transfers a file.** Both toolchains build all 24 modules
clean; the Open Watcom binary runs on Victor MS-DOS 3.1 under MAME, drives the
µPD7201 through the driver in §11b, and completes a Kermit send to a host
C-Kermit at 9600 — milestone step 5 (§13, §16d). Under emulation only;
nothing here has run on a real Victor.

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

Eight small, guarded edits. None changes behaviour on any other platform.

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

7. **`ckufio.c`** — wrapped `SSPACE` in `#ifndef`, matching what `ckcker.h`
   already does for `SBSIZ`, `RBSIZ`, `MAXSP` and `MAXRP`; now
   `-DSSPACE=2048`. `initspace()` asks malloc for `SSPACE` and, when
   refused, halves the request and retries, **keeping whatever it finally
   gets**. Where the heap is large that is a good bargain. Where the heap is
   the 12K left over inside one 64K DGROUP it is the opposite: the default
   10,000 takes the whole thing and every allocation after it fails. §16f.
8. **`ckcdeb.h`** — wrapped the UNIX `MAXWLD` in `#ifndef`; now
   `-DMAXWLD=64`. `zxpand()` allocates `maxnames` pointers *before* it reads
   the first directory entry, so 1024 is a 2,048-byte malloc whether the
   pattern matches two files or none. §16f.

Items 2, 3, 6, 7 and 8 are worth offering upstream regardless of this port.
2, 3, 7 and 8 are latent hazards on any small-memory target — and 7 and 8
share a shape worth naming: an allocation sized for comfort, failing
silently, on a code path whose error message needs its own allocation to be
printed. 6 is a bug on any compiler stricter than gcc.

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

### Proven under MAME, on Victor MS-DOS 3.1

Not the same claim as the two above, and kept separate for that reason.

- **The OEM driver's IOCTL control block** (§11a). Both subfunctions
  answer; `tcsetattr()` programs speed, width, stop bits, parity and the
  modem lines through them; and the values read back as written, including
  DTR and RTS dropping and returning across `tthang()`. Confirmed by
  reading the hardware back, which is more than the two items below have —
  but under emulation, and never on real hardware.
- **A correct Send-Init packet on the wire at 9600**, byte-identical from
  both toolchains, with retransmission on timeout and a protocol `E`
  packet on giving up (§16a, §16b).
- **A complete file transfer, from both toolchains** (§16d, §16e, §11b).
  Our IRQ1 handler on the µPD7201, a receive ring, a polled transmitter, and
  the OEM driver out of the data path: S/F/A/D/Z/B all the way through, and
  a byte-correct file at the far end — 72 bytes under Watcom, 74 under gcc,
  the difference being a text/binary decision and not an error. One small
  file, one literal filename, 9600 bps, window 1, short packets. A
  **wildcard** send still does not complete, in either build (§16f).
- **What DOS itself does with `.` and with trailing separators** (§16f).
  Measured in the root and in a subdirectory, by probe, because two rounds
  of reasoning about it had already gone wrong. `FindFirst(".\*.*")` works
  in both; `stat("./")` fails in a subdirectory; and libdos-m's `stat()`
  cannot stat the current directory under any spelling.

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
§1b, it is INT 21h only, it is shared by both toolchains, and it cost 48
bytes of DGROUP in each. What follows is the reference data first and the
measurements after.

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

**We already hold the handle.** `ttopen()` opens `/dev/seriala` and leaves the
descriptor in `ttyfd`, so `tcsetattr()` in `ckvictor.c` §1b can issue this
without opening anything, and `cfsetospeed()` becomes a table lookup plus one
INT 21h. That retires the `TODO(driver)` on `tcsetattr` without touching an
interrupt vector.

Divisor table, from `msxv90.asm`'s `bddat`. The rule is **`78125 / baud`**:

| baud | 300 | 1200 | 2400 | 4800 | 9600 | 19200 | 38400 |
|---|---|---|---|---|---|---|---|
| divisor | 104h | 41h | 20h | 10h | **8** | 4 | **2** |

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

   **Carry was clear in all three.** A driver that ignores the request and
   one that answers it are indistinguishable from the return status, so
   the only way to know the read worked is to recognise a value in it.

   The first of those caught a real defect on its way past: the hang-up
   path deliberately does not set `baudr`, so it wrote `97BCh` straight
   back into the 8253 — an arbitrary divisor programmed into the chip for
   the half second `tthang()` holds DTR down. That is fixed, and the rule
   it produced is worth keeping even now that the read is known to work:
   **read the block to preserve the fields we do not understand, but never
   let a field we control come back from a read.** The last divisor and
   last WR5 we programmed live in two statics for exactly that reason.

3. **The round trip is real, and it verifies that we are programming the
   chip.** With `stype` right, the read returns `cr4 = 44h` and
   `cr5 = EAh` — the values `tcsetattr()` had just computed for 8-N-1 —
   and `baudr = 8`. `cr2a` reads back as `10h`, which is the OEM driver's
   own WR2 and *not* the `14h` 3.13 writes: the deliberate preservation of
   CR1/CR2A above is working.

4. **Hang-up verified at the register level.** Across `tthang()`, `cr5`
   goes `EAh` → **`68h`** and back. `EAh AND 7Dh` is `68h`: DTR (bit 7) and
   RTS (bit 1) cleared and nothing else touched. `baudr` reads 8 on both
   sides of it. This is the first thing in this port whose effect on the
   hardware has been confirmed by reading the hardware back.

5. **`cr1` reads back as 0, and that is suggestive but not established.**
   WR1 holds the receive-interrupt enables; 0 means the OEM driver is
   running this port with no receive interrupt at all, which is precisely
   the polled, unbuffered arrangement that would fall behind and latch an
   overrun — §16b's leading explanation for the two-byte signature. Do not
   bank it: CR1 is the one field 3.13 explicitly flagged as not behaving,
   and a field that is not applied on write may equally not be reported on
   read. Every other field here round-trips, which is the argument for
   taking it seriously; §11b can settle it by reading RR1.

6. **Reception is unchanged: 12 reads, every one returning exactly 2**, in
   all three runs. Identical to §16b, on a line whose registers we had
   just programmed ourselves and read back to confirm. §11a is neutral on
   the data path, which is what copying 3.13's split predicted, and it is
   a third measurement — under a changed and now *verified* configuration
   — that the OEM driver is not a data path. The transfer still ends in
   retransmissions and a protocol `E` packet.

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

**Done, and it completes a file transfer.** It is `ckvictor.c` §1e, it is
shared by both toolchains, and it cost 672 bytes of DGROUP in each — 512 of
them the receive ring. §16d has the measurement; this section is the design
and the reference data.

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
it"*), and §11a measured CR1 reading back as 0, which is consistent with the
field being neither applied nor reported.

Note that this displaces the OEM driver's own ISR while its device stays
open. That is safe precisely because we never ask it for data again.

**WR2 is left as the OEM driver set it.** §11a read it back as `10h` where
3.13 writes `14h`; the two differ in one bit, which 3.13's own comment
attributes to interrupt priority (Ra>Rb>Ta>Tb), and with one channel and
receive interrupts only there is no priority decision to make. Reasoned, not
measured — but the transfer in §16d works with `10h`, which is the strongest
form the argument can take. The direct-programming fallback writes `14h`,
because in that path there is no OEM setting to preserve.

#### The ISR is written in C, in both toolchains

Both compilers were fed the handler and the generated code inspected:

- **ia16-elf-gcc**: `__attribute__((interrupt))` pushes the scratch
  registers it actually uses plus `DS`, **loads `DGROUP` from a relocation**
  rather than trusting the interrupted `DS`, and ends in `iret`. It rejects
  a handler with named arguments (`error: interrupt function with named
  arguments`), so the handler takes `void` — and so it has to be written
  ANSI-only, since the attribute is part of its type and has no K&R
  spelling.
- **Open Watcom**: `void __interrupt __far`, plus `_dos_getvect` and
  `_dos_setvect` — which are INT 21h `AH=35h`/`25h`, so hooking the vector
  stays inside rule 6. The gcc build issues those two itself; `AH=25h`
  takes `DS:DX`, and `DS` has to hold the *handler's* segment rather than
  DGROUP, which is the one INT 21h call in this file that cannot use
  `DOS_DS_CALL`. Both builds go through one `v9k_getvect`/`v9k_setvect`
  pair taking a segment and an offset, so install and release have no
  `#ifdef` in them.

Neither emits a stack probe in the handler, and neither gives a **stack
switch**: a C handler runs on whatever stack it interrupts.

**We do not switch stacks, deliberately.** A dedicated interrupt stack would
have to come out of the same 64K DGROUP that is this port's binding
constraint, and 3.13's `SERINT` does not switch either, on this machine, and
shipped. The handler holds no arrays and calls nothing; `-fstack-usage`
reports its frame at **22 bytes** under gcc, against roughly 30 for Watcom's
fixed 12-register prologue. That is the number to watch if this ever turns
out to be the wrong call. `~/projects/myfreedos`'s `victor_int14.asm`
prologue remains the reference for doing it properly.

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
3a. **Fix wildcard expansion** (§15, §16f). `-s FILE` works; `-s *.COM`
   found nothing. **Three of four causes fixed** — `SSPACE`'s greedy
   allocator, `MAXWLD`'s up-front array, and libdos-m's inability to
   `stat(".")` — and `-s *.TXT` now expands correctly in both passes. It
   still does not *transfer*: the Victor re-sends Send-Init through its
   ACKs. Not a heap problem this time (§16f).
3b. ~~**Make `read()` block, and make `alarm()` fire.**~~ **Done** — §16b,
   `ckvictor.c` §0d, both builds. The port now retransmits on a timeout and
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
   packets, window 1, streaming off.~~ **Done, in both builds — §16d and
   §16e.** 74 bytes off the Victor's disk, byte-correct at the far end,
   under MAME on Victor MS-DOS 3.1. **This was the real milestone and the
   port has reached it.** Not yet done on real hardware. The gcc build
   needed its packet pools halved to get there (§16e), which is the first
   place the two toolchains have had to be configured differently.
6. **`RECEIVE`, then `GET`, then `SERVER`** — still at 9600. The send
   direction is the one §16d exercised; receive drives the ring harder,
   because the file writes happen on this end.
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
  the read-back as `cr5` going `EAh` → `68h` → `EAh`. It is the first
  effect this port has had on the hardware that the hardware confirms.
- Getting `stype` wrong on the *read* makes it return nothing with carry
  clear. Two of the three runs went that way; the first wrote stack junk
  into the 8253 during hang-up before it was caught.
- Reception is byte-for-byte what §16b measured — 12 reads, every one of
  exactly 2 — in all three runs. Configuring the OEM driver does not make
  it a data path, and §11b is unchanged as the remaining work.

The one thing worth adding to the harness notes in §16a: `XFLAGS=-dKEEP_DEBUG`
needs `make clean` first. It is not per-file — `debug()` compiles to nothing
without it, so a partial rebuild links `ckvictor.o` against a tree that has
no `dodebug` and fails with `E2028: dodebug_ is an undefined reference`.

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

**This is the first hard difference between the two builds that is a
property of the toolchains and not of the port.** Watcom's large model puts
the heap outside DGROUP, so 2048 costs it nothing; gcc's medium model has
one 64K data group and the heap is what is left in the corner of it. So
`ckvictor.h` now sets the two sizes per compiler, which is the only place in
the port where that is true.

### The gcc build has no debug log, measured

`XFLAGS=-DKEEP_DEBUG` does not fit and cannot be made to: the objects alone
come to **68,693 bytes of near data, 104.8% of DGROUP** before libc adds
anything, and the link dies in a page of `relocation truncated to fit`.
Enabling `DEBUG` in just the four modules that matter (`ckufio.c`,
`ckuusx.c` for `dodebug`, `ckuus4.c` for `debopn`, `ckuusy.c` for the `-d`
option) does link, at 61,280 — which leaves 4,256 bytes for heap and stack
together, and `inibufs()` wants 4,108 of that. So the debug log is a
Watcom-only instrument on this port, and the gcc build needs its own
instruments. `V9K_HEAPREPORT` in section 0e of `ckvictor.c` is the first of
them.

### `-d` is not a portable command line

The gcc build **rejects `-d`** — `"-d" - invalid command-line option` — because
`NODEBUG` compiles the option out of `ckuusy.c` along with everything else.
§16d's command line is therefore Watcom-only, which cost one MAME run to
discover. Two other harness landmines cost one run each and belong with the
rest in §16a:

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

## 16f. Wildcards: three causes, two fixed

§15's top item — `-s FILE` works and `-s *.COM` reports "No files for -s" —
has been open for four sessions with a one-line description. It is not one
defect. It is three, they are independent, and two of them are now fixed.
The third is the one that a fresh reading would have blamed last.

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

`opendir()`/`readdir()` in section 0a were then instrumented directly
(`V9K_DIRTRACE`), which is what §15 asked for in the first place:

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

Fixed in section 1a of `ckvictor.c`, where the other libdos-m gaps live: a
`stat()` that strips trailing separators, answers `""` and `"."` itself —
the current directory always exists and is always a directory, so that is a
fact and not a guess — and hands everything else to the library unchanged.
Unlike the `malloc()` interposition below, this one links and runs: both
expansions now happen, both enumerate all 26 entries.

Rule 7's measurement, because this one is called from inside `traverse()`'s
recursion and carries a 128-byte automatic array: `-fstack-usage` puts
`stat()` at **148 bytes** and `opendir()` at 150, both leaves.
`traverse()` itself is unchanged at **98 bytes per level** — the edit to
`ckufio.c` is preprocessor-only — so the deepest chain grows by one leaf
frame, not by 148 bytes per directory level.

### Where it stands, and the instrument that failed

`-s *.TXT` now expands, twice, correctly, in the gcc build. **It still does
not complete a transfer**: the Victor sends Send-Init, is ACKed, and sends
Send-Init again, ten times, until the host gives up. That is *not* the heap
— headroom at the low-water mark is 2,068 bytes with `SBSIZ`/`RBSIZ` at 512,
the same room the transfer that works has — so cause 4 is something else and
is the next session's item. The 512 setting bought a number and no
behaviour, so the tree keeps 1024, which is the value a completed transfer
has actually been measured at.

One instrument to record as **not working**, because it cost two runs and
will look attractive again: you cannot interpose on `malloc()` in the gcc
build. `ld --wrap=malloc` dies with `R_386_OZSEG16 for symbol with no output
section` — the far-call relocations have nothing to point at. Defining
`malloc()` in `ckvictor.c` links cleanly and is simply never called; a
first-call trace proved it, after an earlier run had drawn a conclusion from
its silence. Section 0e's headroom sampling is what is available instead,
and it is enough: it is sampled at `opendir()` precisely because expansion
is the thing the heap cannot afford.


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

- **Wildcard expansion: one cause left of four.** Mostly answered — see
  §16f, which replaces everything this entry used to say. `opendir`,
  `readdir`, `ckmatch` and the DOS layer were all correct throughout; the
  causes were `SSPACE`, `MAXWLD` and libdos-m's `stat(".")`. What remains is
  that `-s *.TXT` expands correctly and then **fails to transfer**: the
  Victor re-sends Send-Init through the host's ACKs until the host gives up,
  with 2,068 bytes of heap headroom, so this one is not memory. Note the
  asymmetry to exploit: the literal-filename send works and the wildcard
  send does not, and the only difference between them is the second
  expansion `gnfile()` does with `ZX_FILONLY`. Instrument that, in the
  Watcom debug build first — it should reproduce, since none of the three
  fixed causes bit that build.
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
- **Heap headroom is the binding constraint now, not static DGROUP.** 12,808
  bytes shared between heap and stack, against 20% of DGROUP still free.
  Anything that raises `SBSIZ`/`RBSIZ`/`MAXSP`/`MAXRP` must be checked against
  a real run, not against `make sizes`. (§9c, §16) **Now measurable**:
  `make -f victor9k.mak XFLAGS=-DV9K_HEAPREPORT` prints the low-water
  headroom at exit. A working transfer leaves 2,090 bytes; the wildcard
  expansion that failed left 212. Under Watcom the heap is outside DGROUP
  and the question does not arise, which is the sharpest argument the
  toolchain decision has yet been given.
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
- Real stack size in the DOS environment — set it explicitly at link time
  (step 2) rather than inheriting a default. Much less alarming than it was:
  `traverse()` is 98 bytes/level now, not 1066 (§9), so the sizing is driven by
  the deepest *non*-recursive chain instead. `docmd()` at 1152 and `zcopy()` at
  1114 are the two largest frames.
- `SET LINE` naming: `COM1`/`COM2` for channels A/B is the obvious choice and
  matches the FreeDOS convention, but Kermit is talking to the chip directly, so
  the names are ours to define.

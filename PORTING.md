# Porting C-Kermit 11 to the Victor 9000 / Sirius 1

Running notes for the serial-only Victor 9000 port. Branch: `victor9k-port`.

**Status:** all 24 modules of the minimal build compile clean for `ia16-elf-gcc`.
Nothing has been linked or run on hardware yet.

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
measurements below say we clear it.

---

## 2. Toolchain and memory model

Built with `ia16-elf-gcc 6.3.0` in the `ia16-ubuntu-2` container.

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

OpenWatcom (`~/projects/open-watcom-v2`, `wcc`) *does* have compact/large/huge
and would allow far data. It was evaluated and **is not needed** — see §9. It
also costs more: `-DUNIX` immediately fails on Watcom's DOS headers
(`sys/param.h` missing), so Watcom would mean inventing a platform identity
from scratch instead of reusing the existing POSIX one.

---

## 3. Build

```sh
make -f victor9k.mak          # build all objects
make -f victor9k.mak sizes    # DGROUP report + largest static objects
```

The entire feature configuration lives in `ckvictor.h`, force-included ahead of
every file with `-include ckvictor.h`. Nothing else in the tree includes it, so
it cannot affect any other platform. Keep new `-D` options *there*, next to the
comment explaining why they exist — not in the makefile.

---

## 4. Source files: in and out

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
| `ckucon.c` / `ckucns.c` | 81/78KB | CONNECT — one needs `fork()`, the other `select()` on a tty; neither is usable. See §8. |
| `ckuscr.c` | 18KB | UUCP-style scripting |
| `ckcmdb.c` | 7KB | malloc debugging |

---

## 5. Platform abstraction boundaries

This is the map that makes the port cheap. Everything Victor-specific is
reachable from four files.

| Concern | Module | Notes |
|---|---|---|
| Serial / TTY I/O | **`ckutio.c`** | `ttopen`, `ttclos`, `ttpkt`, `ttinc`, `ttinl`, `ttoc`, `ttol`, `ttsspd`, `ttflui`. POSIX termios. |
| Console / keyboard | **`ckutio.c`** | `coninc`, `conchk`, `conoc`, `conol`, `congm`, `concb`, `conres`. |
| Timers | **`ckutio.c`** | `rtimer`, `gtimer`, `ztime`. |
| File system | **`ckufio.c`** | `zopeni`, `zopeno`, `zinfill`, `zsoutx`, `zclose`, `zchki`, `zchdir`, directory walk. |
| Signals | `ckusig.c` + `ckcsig.h` | Tiny (202 bytes). |
| Networking | `ckcnet.c`, `ckctel.c` | Compiled out. |
| Terminal emulation / CONNECT | `ckucon.c`, `ckucns.c` | Excluded. |

**`ckutio.c` and `ckufio.c` are the port.** Everything above them is unmodified
upstream code.

---

## 6. Feature flags

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

## 7. Upstream changes made

Five small, guarded edits. None changes behaviour on any other platform.

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

Items 2 and 3 are worth offering upstream regardless of this port; both are
latent hazards on any small-memory target.

---

## 8. 16-bit portability audit

Measured under the Victor configuration, not assumed.

### Resolved

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

### Type sizes under this build

`int` 2, `long` 4, pointer 2 (near data) / 4 (far code), `size_t` 2,
`CK_OFF_T` = `off_t`.

`CK_OFF_T` is the file-offset type used for RESEND/REGET restart. On a 16-bit
target it resolves to newlib's `off_t` (`long`, 32-bit) — good for 2GB, far
beyond any Victor disk. **Verify** your newlib's `off_t` is `long` and not
`int`; if it is `int`, restart breaks above 32KB. This is the one type
assumption worth checking on real hardware.

### Open risks

1. **`traverse()` in `ckufio.c` is recursive** (calls itself at lines 6295 and
   6563) with a **1066-byte stack frame**. Depth is directory nesting depth.
   Eight levels ≈ 8.5KB of a 64K DGROUP. This is the top recursion concern.
   Mitigate by keeping the stack generous, or by capping traversal depth.
2. `shofea()` (`ckuus5.c`) has the largest frame at 2106 bytes — SHOW FEATURES.
   Harmless but worth knowing.
3. Path lengths: `CKMAXPATH` set to 128. Fine for FAT 8.3, and it feeds several
   table sizes, so do not raise it casually.

---

## 9. Memory budget

Measured, 24 modules, `-mcmodel=medium -Os`:

```
.text = 302,935 bytes    far code, medium model, ~1MB limit — not a concern
.data =  11,748 bytes
.bss  =  20,577 bytes
STATIC DGROUP = 32,325 of 65,536  (49%)
free for heap + stack + libc = 33,211 bytes
```

Largest static objects: `rq_tok` 2064, `optlist` 2050, `tbl` 1632,
`cmdtab` 1272, `numbuf` 1056, `cmdatebuf` 1028, `cmdstr` 1025, `mybuf` 1024.
Nothing else over 1KB.

Projected full budget:

| Item | Bytes |
|---|---:|
| Static data + bss | 32,325 |
| Packet buffers (`SBSIZ`+`RBSIZ`, malloc'd) | 8,192 |
| newlib stdio + bss | ~6,000 |
| Stack | ~8,000 |
| **Total** | **~54,500 of 65,536** |

**~11KB headroom.** Tight but real. This is why `ckvictor.h` sets `MAXSP`/
`MAXRP` to 1024 and `SBSIZ`/`RBSIZ` to 4096 rather than the `DYNAMIC` defaults
of 9024/9050, which would have cost 18KB in packet buffers alone.

If headroom is needed later, in order of payoff: cut `RQ_MAXTOK` further,
drop `SHOW` commands (`ckuus5.c`, 2432 bytes of data+bss), reduce `CKMAXPATH`.

**Conclusion: OpenWatcom's far-data models are not required.** They remain the
fallback if the budget is blown later, at the cost of building a new platform
identity from scratch. See §9a for what that fallback actually buys.

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
   total stack need is ~8KB — about 12% of the budget. Moving it out would buy
   back 8KB we are not short of.
3. **Far access is expensive in exactly the wrong place.** The same
   encode-shaped loop compiled near vs far:

   ```
   enc_near  32 instructions
   enc_far   43 instructions   (+34%), 19 segment-register operations
   ```

   That is the inner byte loop of `encode()`/`decode()`. At 38400+ baud on an
   8088 with a 4-byte prefetch queue, segment loads and override prefixes in
   that loop cost real throughput. Far data is the wrong trade for the packet
   pool specifically.
4. **The `__far` blast radius is not local.** The pool is handed out as
   `s_pkt[i].pk_adr`, a plain `CHAR *`, and from there flows through 139+
   `CHAR *` sites across `ckcfns.c` / `ckcfn2.c` / `ckcfn3.c` / `ckcpro.c`.
   Annotating "just the buffers" means annotating the whole protocol engine —
   exactly the upstream divergence this port is trying to avoid.

### When it would be worth it

The scenario that genuinely needs far data is **large windows × long packets**.
`MAXWS 32` × `MAXSP 4096` is a 132KB packet pool — that cannot fit a single
DGROUP at any tuning, and no amount of trimming elsewhere changes it.

If that is the goal, the right move is **not** `__far` annotation under
ia16-gcc. It is switching to **OpenWatcom large model with `-zt`**, where the
buffers move out of DGROUP by compiler flag and the source stays upstream.

The cost of that switch is real and should not be paid speculatively:
Watcom uses OMF objects and its own C library, so the newlib port does not
carry over, and `-DUNIX` fails immediately on Watcom's DOS headers
(`sys/param.h` absent), so a new platform identity has to be built. The newlib
work is the asset here.

**Recommendation:** ship the milestone on ia16-gcc at 49% DGROUP with a 4KB/4KB
packet pool. If throughput measurement later says the window needs to be much
larger, revisit Watcom large model then — and treat it as a deliberate
re-platforming, not a tweak.

---

## 10. Does the Unix TTY layer sit on newlib?

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

`ckufio.c` needed exactly one change (the inode check, §7).

**Recommendation: keep `ckutio.c` and `ckufio.c`. Do not write a Victor
platform module.** The work is in your newlib, not in C-Kermit. Supply a real
POSIX termios and the port is done — `ttsspd()` maps SET SPEED onto
`cfsetospeed()`, so 38400 and above come from your baud-rate table, not from
C-Kermit.

Caveat: the stock ia16 newlib ships `termios.h` as a **dangling include** of a
`<sys/termios.h>` that does not exist, and defines no termios functions. Your
Victor newlib must provide both the header and the implementation.

---

## 11. Platform glue still required

After the 24 modules compile, these remain undefined. Everything else resolves
against newlib. `ckvictor.c` already stubs the process-model calls; this is
what must be **real**:

**Termios — the serial port (your Victor serial API):**
`tcgetattr` `tcsetattr` `tcflush` `tcsendbreak`
`cfgetispeed` `cfgetospeed` `cfsetispeed` `cfsetospeed`

**Directory reading (for `DIR`, wildcards, server file lists):**
`opendir` `readdir` `closedir`

**File system:**
`access` `chdir` `chmod` `getcwd` `mkdir` `rmdir` `utime`

**Misc:** `sleep`

Stubbed in `ckvictor.c`, safe to leave: `fork` `execl` `execvp` `wait`
`getuid` `geteuid` `getgid` `getegid` `setuid` `setgid` `getpid` `getppid`
`getpgrp` `tcgetpgrp` `getlogin` `getpwnam` `getpwuid` `ttyname` `ctermid`
`alarm` `sysconf` `putenv` `readlink` `umask` `dup2`, plus the symbols owned by
excluded modules (`conect`, `connv`, `mdmtyp`, `nvlook`, `ck_bracketaddr`).

Each stub is wrapped in `#ifndef VICTOR_HAVE_<name>`, so if your newlib already
provides one, define that macro. Build first, then add whichever macros the
linker reports as multiply defined — faster than auditing the library up front.

---

## 12. Milestone

```
CKERMIT
C-Kermit> set line /dev/com1        (or whatever your newlib names it)
C-Kermit> set speed 38400
C-Kermit> send foo.bin
C-Kermit> receive
C-Kermit> server
```

Suggested order:

1. **Link it.** Supply termios + dirent + the filesystem calls above. Expect
   this to be the bulk of the remaining work.
2. **`C-Kermit>` prompt.** Proves `ckucmd.c` + `coninc`/`conchk` work. No
   serial port involved. Watch the stack here — `docmd()` is 1152 bytes.
3. **`SET LINE` / `SET SPEED`.** Proves `ttopen`/`ttsspd`.
4. **`SEND` one small binary file** at 9600 to a known-good Kermit, with short
   packets and window 1. This exercises the whole engine end to end.
5. **Turn on long packets, then windows, then streaming**, one at a time, and
   re-measure free memory at each step.
6. **`RECEIVE`, then `GET`, then `SERVER`.**
7. Push the speed to 38400 and beyond.

Only after all that is CONNECT worth considering — and it should be written
fresh as a small polling loop over `ttinc()`/`coninc()` in `ckvictor.c`, not
ported from `ckucon.c` (needs `fork()`) or `ckucns.c` (needs `select()`).

---

## 13. Compile log

Every module in §4 compiles with **zero errors** at `-mcmodel=medium -Os`.

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
| `ckutio.c` `sys/termios.h` missing | newlib gap — must be supplied |
| `ckvictor.c` prototype conflicts | Rewrote stubs as ANSI matching newlib |

---

## 14. Open questions

- Is your newlib's `off_t` a `long`? If it is `int`, RESEND/REGET restart
  breaks above 32KB. (§8)
- Does your newlib provide `opendir`/`readdir`/`closedir`? The stock ia16
  newlib does not, and server mode and wildcards need them.
- How does your serial layer name ports, for `SET LINE`?
- What is the real stack size in your Victor runtime? The `traverse()`
  recursion (§8) makes this matter more than it usually would.
- Does 38400+ need interrupt-driven receive with a ring buffer? At 38400 a
  polled `ttinc()` may drop characters; C-Kermit's flow control will recover,
  but throughput will suffer. Check against the MS-DOS Kermit 3.13 Victor
  serial code in `~/projects/kermit`.

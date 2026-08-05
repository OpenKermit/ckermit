# Next session

Handoff for the Victor 9000 port, written 4 August 2026 at the end of the
session that added the Open Watcom build and first ran it on Victor MS-DOS 3.1.

**Read `PORTING.md` first** — §9d (the Watcom build) and §16a (what ran on
MS-DOS 3.1, and the harness) are new and are where the detail lives. This file
is only the "what next".

---

## 1. Where things stand

Two toolchains build the same tree from the same `ckvictor.h`:

| | ia16-elf-gcc, medium | Open Watcom, large |
|---|---|---|
| makefile | `victor9k.mak` | `victorow.mak` |
| 24 modules compile | yes, 0 warnings | yes, 17 warnings, all upstream |
| DGROUP after link | 52,000 / 65,536 (79%) | 38,704 (59%) |
| `.EXE` | 218,448 | 224,928 |
| runs on FreeDOS for Victor | yes (§16) | yes |
| runs on Victor MS-DOS 3.1 | yes | yes |
| opens `/dev/seriala`, sends a packet | yes | yes, **byte-identical** |
| completes a transfer | **no** | **no** — same cause |

The interactive command parser (`NOICP`) fits in DGROUP under Watcom but the
resulting 429KB image does not fit in the 387KB DOS hands a program. See §9d
and §16a.

### Nothing is committed

The tree is dirty and everything below is uncommitted:

```
M .gitignore CLAUDE.md PORTING.md ckcfnp.h ckvictor.c ckvictor.h victor9k.mak
? victorow.mak victorow/ victor/sys/ioctl.h NEXT_SESSION.md
```

**`ckcfnp.h` is a sixth guarded upstream edit and needs a ruling before it is
committed.** It wraps `void fxdinit( int );` in `#ifndef NODISPLAY`, matching
what `ckcker.h` already does two lines away; without it, 15 modules fail to
compile under Watcom (E1026) because the prototype expands through
`ckcker.h`'s macro to the declaration `void ;`. gcc treats the same line as a
warning. Rationale is in `PORTING.md` §8 item 6. If you would rather not carry
it, the alternatives are both worse: `-DNOANSI` drops all of `ckcfnp.h`, which
is dangerous in a large model where an implicit `int` return truncates a far
pointer, or force-including `ckcker.h` everywhere.

---

## 2. Do this first: make the serial read block

This is the one defect standing between the port and a real file transfer, it
is now understood exactly, and it is **not** toolchain-specific — both builds
fail identically.

`ckutio.c`'s `myfillbuf()` calls `read(ttyfd, ...)` and its own comment says
what it expects:

> The new myread()/mygetbuf() always gets something. If it doesn't, then make
> it do so!

On Unix a raw tty read blocks (VMIN/VTIME). On MS-DOS a character-device read
with nothing pending returns **0 immediately**, so `mygetbuf()` reports EOF
(-2) and C-Kermit disconnects. Measured symptom: exactly one Send-Init packet
on the wire, then "No files were transferred" (§16a).

`ckutio.c` is stock upstream and stays that way, so the fix belongs in
`ckvictor.c` — make `read()` on the communications descriptor behave the way
`myfillbuf()` requires:

1. Poll with INT 21h `AX=4406h` (IOCTL, get input status), `BX` = handle.
   Returns `AL=0xFF` when input is ready, `0x00` when not. Character-device
   status is exactly the primitive needed here.
2. Loop until ready, or until a deadline taken from `time()`, then issue the
   real `AH=3Fh` read. On timeout return -1 with `errno = EINTR`, which is the
   case `mygetbuf()` already documents and the caller checks.
3. Use the same call to make `ioctl(FIONREAD)` honest for the serial
   descriptor. It currently answers 0 for anything that is not the console
   (`ckvictor.c` §0b), which hard-wires `ttchk()` to "nothing waiting" and is
   the input to the sliding-window and streaming logic (`victor/sys/ioctl.h`).

Both calls are INT 21h, so this satisfies hard rule 6 and works on Victor
MS-DOS 3.1 and FreeDOS alike. Under gcc, `ckvictor.c` already overrides
newlib's `_read_r`, so there is precedent for the shape; under Watcom you will
be defining `read()` against the one in `clibl.lib` — check that the linker
takes ours and says so, rather than silently taking the library's.

**Why this is worth doing before the µPD7201 driver:** it would complete a
transfer *today* over the OEM DOS serial driver, which `CONFIG.SYS` already
loads (`porta.exe` → `\dev\seriala`, configured with `PORTSET`). That
exercises the protocol engine, the file system, both packet directions and
the host end of the link — everything except the chip — and gives §11 a
working reference to be measured against. It also splits the remaining risk
in two instead of landing it all on one unwritten driver.

Test it with the harness in §16a; the file to send is already on the image.
Expect the far end (host `kermit`, `set line /tmp/v9000`) to answer the S
packet and the transfer to run at 9600.

---

## 3. Then: the µPD7201 driver (§11)

Unchanged as the plan of record, and still the thing that makes this a real
serial port rather than a passenger on the OEM driver: interrupt-driven RX
into a ring buffer, real `tcsetattr` speed programming, honest `FIONREAD`
counts, and `tcdrain`/`tcflush`/`tcsendbreak` against the chip. The stubs and
their TODOs are at the bottom of `ckvictor.c` (§1b, §3). Register map and a
proven 38400 TX path are in `~/projects/myfreedos`
(`kernel/victor_int14.asm`, `victor_serial_debug.asm`, `victor_pic.asm`,
`docs/victor/subsystem-docs/Serial.md`); `~/projects/kermit/victor9000/vickermit.c`
is a useful second opinion on chip init.

Doing §2 first means this arrives with a known-good comparison: same binary,
same host receiver, `-l /dev/seriala` versus the native driver.

---

## 4. Open, in rough priority order

**The 42KB gap for the interactive parser.** It needs 429KB, DOS offers 387KB
(§16a, measured). Worth knowing whether it is reachable, because the parser is
the one feature this port had to amputate. Three angles, none tried: a leaner
DOS configuration (FreeDOS's 154KB `KERNEL.SYS` plus an 87KB `COMMAND.COM` is
most of the loss; MS-DOS 3.1 is far smaller — measure the max block there,
`FREEMEM.COM` in §16a is 40 bytes of NASM); trimming ~50KB of features that
`NOICP` was hiding; or `ZT=-zt128`, which frees DGROUP but grew the image,
so measure the load requirement rather than assuming.

**Which toolchain the port should use.** Not decided, and it does not need to
be yet — the two are equivalent on the wire and §2 helps both. Watcom buys the
large model, a far heap for the packet buffers, and the parser if the RAM is
ever found. gcc is the incumbent with the longer run history. Deciding early
costs nothing and gains nothing; deciding after §2 is informed.

**The 17 Watcom warnings** (`PORTING.md` §9d). All in stock upstream modules,
none dangerous in a large model, itemised there. Two are worth a glance if you
are touching that code anyway: `localtime()` called with a `long *` where
Watcom's `time_t` is unsigned, and `docmdline(1)` in `ckcmai.c` passing the
integer 1 to a `void *` parameter.

**`NOGFTIMER`.** Floating-point transfer timers on an 8088 with no FPU pull in
emulation for both builds. Not turned off, because doing so would have made the
two builds' measurements non-comparable during the Watcom work. That reason has
expired.

---

## 5. Things that cost time this session

Landmines, so they are only paid for once. The harness itself is in §16a.

- **The Victor boots its hard disk as `A:`**, not `C:`.
- **`~/projects/mame/victor_kermit.img` is the image to use.** It is not an MBR
  disk and has no BPB, so **mtools cannot read it** — use `vtg_image_util`
  (`~/projects/vtg_image_util`, docs in
  `~/projects/Victor9000-Disk-Image-Tools/README.md`). Do not write to the
  image directly. It already holds `CKERMITW.EXE`, `CKERMITG.EXE`,
  `TESTFILE.TXT` and `KTEST.BAT` from this session. The 33 lost clusters
  `verify` reports are in partition 3 and pre-date this work.
- **MAME's `-bitb` socket is single-use.** Start `socat` first and let MAME be
  the only thing that connects; probing the port burns it.
- **Test on Victor MS-DOS 3.1, not FreeDOS.** DOS does not touch the serial
  port on its own, FreeDOS-for-Victor has its own serial debug traffic, and
  its `%COMSPEC%` points at `C:` on a machine that boots as `A:` — so any
  program large enough to overwrite FreeCom's transient part leaves the shell
  unable to reload its message strings. One run was lost to that.
- **The emulated keyboard mangles characters** in `-autoboot_command`: digits
  arrive shifted (§16) and `CKERMITW -r` arrived as `CKERIT_R`. Put the
  commands in a `.BAT` file on the image and autoboot that.
- **`-l /dev/seriala`, with forward slashes.** C-Kermit treats
  `\dev\seriala` as a relative path and tries `A:\/dev/seriala`.
- **`kermit -V` drops into interactive mode and hangs.** Always give the host
  `kermit` a command file, and a `timeout`.
- **`~/.kermrc` sets a line that does not exist** and prints two errors before
  any script runs. They are noise, not your script failing.
- **MAME writes `cfg/` and `nvram/` into its working directory.** Run it from
  `~/projects/mame` or they land in the source tree.
- Each MAME run is 85–140 s. Batch several probes into one boot with a `.BAT`.

---

## 6. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victor9k.mak"     # gcc, links ckermit.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"     # Watcom, links ckermitw.exe
```

Both print their DGROUP figure on link. Diagnostic variants, neither set by
any makefile: `XFLAGS=-dKEEP_ICP` restores the interactive parser,
`XFLAGS=-dKEEP_DEBUG` restores the debug log (`-d` writes `./debug.log`, which
`vtg_image_util copy` can pull back off the image — worth doing early in §2).
Rule 4 still applies: report the DGROUP number after any change that could add
static data.

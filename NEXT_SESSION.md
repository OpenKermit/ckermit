# Next session

Handoff for the Victor 9000 port, written 4 August 2026 at the end of the
session that made `read()` block, made `alarm()` fire, and found out what is
really wrong with reception.

**Read `PORTING.md` first** — §16b is new and is where the detail lives. This
file is only the "what next".

---

## 1. Where things stand

Two toolchains build the same tree from the same `ckvictor.h`:

| | ia16-elf-gcc, medium | Open Watcom, large |
|---|---|---|
| makefile | `victor9k.mak` | `victorow.mak` |
| 24 modules compile | yes, 4 warnings | yes, 17 warnings |
| warnings are | all pre-existing, all upstream | all pre-existing, all upstream |
| DGROUP after link | 52,008 / 65,536 (79%) | 38,704 (59%) |
| `.EXE` | 218,800 | 225,350 |
| runs on FreeDOS for Victor / MS-DOS 3.1 | yes | yes |
| opens `/dev/seriala`, sends a packet | yes | yes, byte-identical |
| **retransmits on timeout** | **yes** | **yes** |
| completes a transfer | **no** | **no** — same cause |

Everything is committed except this session's work; see §6 below for what is
in the working tree.

### What changed, and what it proved

`ckvictor.h` now renames `read()` to `v9k_read()` for the whole build and
`ckvictor.c` §0d supplies it: a poll of INT 21h `AX=4406h` with the read
issued only once DOS says there is input, delegating everything that is not
`ttyfd` to the library's `read()`. `alarm()` stopped being a stub — it
records a deadline that the poll tests, and on expiry the poll reads back the
`SIGALRM` handler `ckutio.c` installed and calls it, so `timerh()` longjmps
and `ttinl()` returns its documented -1. **No new upstream edit; §8 still
lists six.**

The measured result on Victor MS-DOS 3.1 under MAME: the port sends the
Send-Init packet, times out, **retransmits it 13–15 times**, and gives up
with a protocol `E "Too many retries"` packet instead of dropping the line
after one packet. Both builds, identically.

### The real reason transfers do not complete

Not what §16a assumed. A `KEEP_DEBUG` build's `DEBUG.LOG`, pulled back off
the image, says the same thing twelve times running:

```
myfillbuf calling read() fd=6
SVORPOSIX myfillbuf read=2      <-- two bytes
TTINL myread char=^A            <-- SOH
TTINL myread char=9             <-- the LEN field
myfillbuf calling read() fd=6   <-- and then nothing, ever
ttinl timout
```

**The OEM `\dev\seriala` driver delivers the first two bytes of every inbound
packet and then stops.** Twelve reads, every one returning exactly 2. The
whole software stack above it is working — C-Kermit framed the packet, read
its length, waited, timed out, retransmitted, and gave up correctly.

That retires the previous handoff's hope that a blocking read alone would get
a transfer through over the OEM driver. It will not.

---

## 2. Do this: §11, the µPD7201 driver, on MS-DOS Kermit 3.13's model

It is now the only thing left between this port and a file transfer, and the
last session's argument for doing something else first has been measured away.

**§11 was rewritten this session and is the thing to read.** The decision it
records: copy the integration model of `msxv90.asm` in
`~/projects/kermit/msr313src` — a Victor 9000/Sirius serial driver written by
this same project between 1985 and 1991, for this exact hardware.

What that model is, in three lines: 3.13 opens the OEM device `SERIALA`, uses
the handle **only** to read and write the µPD7201's control registers through
DOS IOCTL (`AH=44h`, `AL=02h`/`03h`, a 17-byte control block), and never once
moves data through it. Every use of its handle in 1,443 lines is open, close,
or IOCTL — no `AH=3Fh`, no `AH=40h`. Data lives on its own ISR against the
memory-mapped chip. **The OEM driver is a configuration channel, not a data
path**, and §16b measured what happens when you use it as one.

The payoff is that it splits §11 into two halves that build and test
independently:

- **11a, configuration.** `AH=44h AL=03h` on the descriptor `ttopen()`
  already leaves in `ttyfd` — no new open, no interrupt work, pure INT 21h.
  This alone makes `tcsetattr()`, `SET SPEED` and `SHOW COMMUNICATIONS` real
  and retires the `TODO(driver)` markers in `ckvictor.c` §1b. Do it first.
- **11b, the data path.** Our own ISR and RX ring against the chip at
  `E004h`. This is where the risk is.

§11 now carries the constants read out of `msxv90.asm` rather than guessed:
the three memory-mapped segments (7201 `E004h`, 8253 `E002h`, 8259 `E000h`),
the control-block layout, the WR1–WR5 values **and the order they must be
written in**, the 8253 divisor rule (`78125 / baud`; 9600 = 8, 38400 = 2),
and the answer to §2's open question about the vector — **IVT slot 41h**,
8259 unmask `AND 0FDh`, EOI `61h`.

Three things §16b adds:

1. **Receive is the hard half.** Transmit is already proven end to end
   through the OEM driver at 9600, byte-identical between the two builds, so
   the new driver has a known-good reference on TX and nothing to compare
   against on RX.
2. **Overrun recovery from the first version, not later.** A latched µPD7201
   receive overrun is the leading explanation for the OEM driver's signature
   and is *not established* by our own measurements — but 3.13's ISR reads
   RR1, issues `WR0 = 30h` (Error Reset) and substitutes a `BELL` for the
   lost character, and its edit history records overrun being found and fixed
   twice in 1986 on this hardware. The chip will not resume until Error Reset,
   so an ISR that omits it wedges on the first byte it is late for.
3. **`ttchk()` needs `ttgmdm()` as well as `FIONREAD`.** See §4 below. 3.13
   reads DSR/CD/CTS out of RR0 in `getmodem`/`shomodem`.

Also worth copying: 3.13's `SERRST` spins on RR1 bit 0 until the transmitter
*and* shift register are empty before tearing down, or the last packet is
truncated; and it keeps a fallback that programs the chip directly if the
device will not open.

`~/projects/myfreedos` (`kernel/victor_int14.asm`, `victor_serial_debug.asm`,
`victor_pic.asm`) is still the reference for the MS-DOS 3.1 ISR
stack-switching prologue and a TX path proven at 38400;
`~/projects/kermit/victor9000/vickermit.c` is a third opinion. Where they
disagree, `msxv90.asm` is the one that shipped for this machine.

---

## 3. The two things §0d left honest but unreachable

Both are small, both belong to §11, and both are written up in §12's
`FIONREAD` section.

**`ioctl(FIONREAD)` on the comm device** now answers from `AX=4406h` instead
of a flat 0. It is honest but it answers *whether*, not *how many*, and
`sdata()` in `ckcfns.c` only slides its window when `ttchk()` exceeds
`4 + bctu` — so 1 never triggers it. The real count needs the RX ring.

**`ttchk()` still returns 0 anyway**, upstream of that, and this was missed
the first time round. `in_chk()` checks carrier before it checks for bytes:
`ttcarr` initialises to `CAR_AUT`, this port is always `xlocal`, and
`ttgmdm()` with no `TIOCMGET` and no `K_MDMCTL` falls through to `return(-3)`,
at which point `in_chk()` returns 0 without ever reaching `FIONREAD`. Visible
in the debug log as `in_chk ttgmdm I/O error=0`. The driver has to supply
modem signals, not just a count.

---

## 4. Open, in rough priority order

**The 42KB gap for the interactive parser.** Unchanged from the last handoff:
it needs 429KB, DOS offers 387KB (§16a, measured). Three untried angles — a
leaner DOS configuration, trimming ~50KB of what `NOICP` was hiding, or
`ZT=-zt128` (which frees DGROUP but grew the image, so measure the load
requirement rather than assuming).

**Which toolchain the port should use.** Still not decided and still does not
need to be; the two remain equivalent on the wire, and §0d is shared. The one
new data point is that the Watcom build needed `SIGALRM` moved into
Watcom's 1..12 range to work at all (§16b) — a difference that was invisible
until something actually dispatched the signal.

**`NOGFTIMER`.** Floating-point transfer timers on an 8088 with no FPU pull in
emulation for both builds. Still not turned off; the reason for leaving it
(keeping the two builds comparable during the Watcom work) has expired.

**Wildcard expansion** (§13 step 3a, §15). `-s FILE` works, `-s *.COM` finds
nothing. Blocks multi-file transfer, untouched this session.

**The 17 Watcom warnings and the 4 gcc ones.** All in stock upstream modules,
all pre-existing, itemised in §9d. Note that the gcc build has never been
warning-free — earlier revisions of this file and of `CLAUDE.md` said "0
warnings", which was wrong; it is 4, and they are `docmdline(1)` in
`ckcmai.c` plus implicit declarations of `utime`, `wait` and `gettimeofday`.

---

## 5. Things that cost time, and the harness

§16a has the full harness. The landmines from the last handoff all still
apply — repeated here because they still cost time:

- **The Victor boots its hard disk as `A:`**, not `C:`.
- **`~/projects/mame/victor_kermit.img` is the image.** Not an MBR disk, no
  BPB, **mtools cannot read it** — use `vtg_image_util`
  (`~/projects/vtg_image_util`). A backup from this session is beside it as
  `victor_kermit.img.bak-20260804`. The 33 lost clusters `verify` reports are
  in partition 3 and pre-date this work.
- **MAME's `-bitb` socket is single-use.** Start `socat` first and let MAME be
  the only thing that connects; probing the port burns it.
- **Test on Victor MS-DOS 3.1, not FreeDOS** (see §16a for why).
- **The emulated keyboard mangles characters** in `-autoboot_command`. Put the
  commands in a `.BAT` on the image and autoboot that. `KTEST.BAT` is there.
- **`-l /dev/seriala`, with forward slashes.**
- **`kermit -V` drops into interactive mode and hangs.** Always give the host
  `kermit` a command file, and a `timeout`.
- **`~/.kermrc` sets a line that does not exist** and prints two errors before
  any script runs. Noise, not your script failing.
- **MAME writes `cfg/` and `nvram/` into its working directory.** Run it from
  `~/projects/mame`.
- Each MAME run is 85–140 s for 120 emulated seconds; a `KEEP_DEBUG` run is
  slower still because every `debug()` call hits the disk. Batch probes into
  one boot with a `.BAT`.

New this session:

- **The `KEEP_DEBUG` loop is the good one and it was underused before.**
  `make -f victorow.mak XFLAGS=-dKEEP_DEBUG` (image 304,762 bytes, still
  loads), run `CKERMITW -d ...`, then
  `vtg_image_util copy ...img:0:\\DEBUG.LOG ./debug.log`. It answered in one
  run a question that three wire captures could not: the difference between
  "receives nothing" and "receives exactly two bytes".
- **The host side wants `log packets`.** `kermit -y` with a command file
  containing `set line /tmp/v9000`, `set carrier-watch off`, `log packets
  host-packets.log`, `receive`. The log shows both directions and is how the
  13–15 retransmissions and the final `E` packet were counted.

---

## 6. State of the working tree

Uncommitted:

```
M CLAUDE.md PORTING.md ckvictor.c ckvictor.h NEXT_SESSION.md
```

`ckvictor.c` gains section 0d and a real `alarm()`; `ckvictor.h` gains the
`read` rename and the `SIGALRM` change. **No upstream file is touched** —
`git diff --stat` shows only these. Rules 1 through 7 all hold: DGROUP is
reported above, and `-fstack-usage` puts `v9k_read` at 22 bytes with both
helpers inlined into it.

## 7. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victor9k.mak"     # gcc, links ckermit.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"     # Watcom, links ckermitw.exe
```

Both print their DGROUP figure on link. Diagnostic variants, neither set by
any makefile: `XFLAGS=-dKEEP_ICP` restores the interactive parser,
`XFLAGS=-dKEEP_DEBUG` restores the debug log. Rule 4 still applies: report
the DGROUP number after any change that could add static data.

# Next session

Handoff for the Victor 9000 port, written 4 August 2026 at the end of the
session that implemented §11a — the port now programs the serial line, and
the hardware reads back what it wrote.

**Read `PORTING.md` first** — §11a is rewritten and §16c is new. This file
is only the "what next".

---

## 1. Where things stand

Two toolchains build the same tree from the same `ckvictor.h`:

| | ia16-elf-gcc, medium | Open Watcom, large |
|---|---|---|
| makefile | `victor9k.mak` | `victorow.mak` |
| 24 modules compile | yes, 4 warnings | yes, 17 warnings |
| warnings are | all pre-existing, all upstream | all pre-existing, all upstream |
| DGROUP after link | 52,056 / 65,536 (79%) | 38,752 (59%) |
| `.EXE` | 218,800 | 225,964 |
| runs on FreeDOS for Victor / MS-DOS 3.1 | yes | yes |
| opens `/dev/seriala`, sends a packet | yes | yes, byte-identical |
| retransmits on timeout | yes | yes |
| **programs speed/parity/DTR via IOCTL** | **yes** | **yes** |
| completes a transfer | **no** | **no** — same cause |

Everything is committed (`8688f81`), working tree clean.

### What changed, and what it proved

`tcsetattr()` stopped being a cache. It hands the OEM driver the 17-byte
port-access control block over INT 21h `AH=44h AL=02h/03h`, on the
descriptor `ttopen()` already left in `ttyfd`, and sets the µPD7201's WR3,
WR4 and WR5 plus the 8253 divisor. `tcsendbreak()` is real. `B0` drops DTR
and RTS, so `tthang()` hangs up. No new upstream edit; **§8 still lists
six**, and `CLAUDE.md` rule 1 said "five" until this session — it now says
six, which is what §8 has always listed.

Measured on Victor MS-DOS 3.1 under MAME, three runs (§11a has the detail):

- Both subfunctions work; all five places C-Kermit sets the line reach the
  chip.
- **The values read back as written** — `cr4=44h`, `cr5=EAh`, `baudr=8` —
  and `tthang()` is visible as `cr5` going `EAh → 68h → EAh`. That is the
  first effect this port has had on the hardware that the hardware
  confirms.
- **`stype` must be `0011h` on entry to the *read*.** Get it wrong and the
  call returns **carry-clear with the block untouched**. Two of three runs
  went that way before it was understood, and the first one wrote stack
  junk into the 8253 during hang-up. If you add another IOCTL here, prove
  the read worked by recognising a value in it — the status will not tell
  you.

### Reception is exactly where §16b left it

**12 reads, every one returning exactly 2 bytes, in all three runs** — on a
line whose registers we had just programmed and read back to confirm. §11a
is neutral on the data path, which is what copying 3.13's split predicted.
The OEM driver still cannot receive a Kermit packet.

One new data point on *why*: **the driver's CR1 reads back as 0**, i.e. no
receive interrupt enabled — the polled, unbuffered arrangement that would
fall behind at 9600 and latch an overrun. Do not bank it: CR1 is the single
field `msxv90.asm` records as not behaving through this interface, so 0 may
mean "not reported". §11b settles it by reading RR1.

---

## 2. Do this: §11b, the data path

It is now the only thing between this port and a file transfer. §11a
retired everything that could be done without owning the chip.

**§11 is the thing to read.** It carries the constants out of `msxv90.asm`
rather than guesses: the memory-mapped segments (7201 `E004h`, 8253
`E002h`, 8259 `E000h`), **IVT slot 41h**, 8259 unmask `AND 0FDh`, EOI
`61h`, the WR1–WR5 values and the order they must be written in.

Checked this session, so you can plan around it:

- **The ISR can be C in both toolchains.** ia16-elf-gcc's
  `__attribute__((interrupt))` pushes the scratch registers and `DS`,
  **loads `DS` from `DGROUP` itself**, and ends in `iret`; it rejects
  named arguments. Watcom has `void __interrupt __far` plus
  `_dos_getvect`/`_dos_setvect`, which are INT 21h `AH=35h`/`25h` and so
  stay inside rule 6. The gcc build needs those two by hand.
- **Neither gives a stack switch.** A C handler runs on whatever stack it
  interrupts. `~/projects/myfreedos`'s `kernel/victor_int14.asm` prologue
  is the reference, and this is the part that will not be C.

Three things §16b and §11a insist on:

1. **Receive is the hard half.** Transmit is proven end to end at 9600,
   byte-identical between the builds, so the new driver has a known-good
   reference on TX and nothing to compare against on RX.
2. **Overrun recovery from the first version.** The chip latches overrun in
   RR1 and will not resume until `WR0 = 30h` (Error Reset), so an ISR that
   omits it wedges on the first byte it is late for — the shape of what the
   OEM driver does to us today. 3.13's edit history records this being
   found and fixed twice in 1986 on this hardware.
3. **`ttchk()` needs `ttgmdm()` as well as `FIONREAD`** — see §3 below.

Also worth copying: 3.13's `SERRST` spins on RR1 bit 0 until the
transmitter *and* shift register are empty before tearing down, or the last
packet is truncated; and it keeps a fallback that programs the chip
directly if the device will not open. A Kermit that leaves IRQ1 hooked on
exit takes the machine down, so the teardown matters as much as the setup.

Suggested shape, given TX already works and RX does not: **our ISR for RX,
polled TX** (WR1 with receive interrupts only). That keeps the known-good
half known-good.

---

## 3. The two things §0d left honest but unreachable

Both are small, both belong to §11b, both written up in §12's `FIONREAD`
section. **Unchanged this session** — §11a could not reach either, and now
it is clear why.

**`ioctl(FIONREAD)`** answers *whether*, not *how many*. `sdata()` in
`ckcfns.c` only slides its window when `ttchk()` exceeds `4 + bctu`, so 1
never triggers it. The real count needs the RX ring.

**`ttchk()` returns 0 anyway**, upstream of that. `in_chk()` checks carrier
before bytes; `ttcarr` starts at `CAR_AUT`, this port is always `xlocal`,
and `ttgmdm()` with no `TIOCMGET` falls through to `return(-3)`, at which
point `in_chk()` returns 0 without reaching `FIONREAD`. Visible in the
debug log as `in_chk ttgmdm I/O error=0`. **§11a cannot fix this**: the
control block is write-registers only and carries no RR0. 3.13 reads
DSR/CD/CTS out of RR0 directly, which needs §11b.

---

## 4. Open, in rough priority order

**The 42KB gap for the interactive parser.** Unchanged: it needs 429KB, DOS
offers 387KB (§16a, measured). Three untried angles — a leaner DOS
configuration, trimming ~50KB of what `NOICP` was hiding, or `ZT=-zt128`
(which frees DGROUP but grew the image, so measure the load requirement
rather than assuming).

**Which toolchain the port should use.** Still not decided and still does
not need to be; the two remain equivalent on the wire, and §11a is shared.

**`NOGFTIMER`.** Floating-point transfer timers on an 8088 with no FPU pull
in emulation for both builds. Still not turned off; the reason for leaving
it has expired.

**Wildcard expansion** (§13 step 3a, §15). `-s FILE` works, `-s *.COM` finds
nothing. Blocks multi-file transfer, untouched this session.

**Should `B76800` keep its name?** It is divisor 1 = 78125 bps, 1.7% off
what it is called. Same error as `B38400`, which 3.13 shipped, so this is
cosmetic — noted only because the corrected clock (§11a) made it visible.

---

## 5. Things that cost time, and the harness

§16a has the full harness. The landmines all still apply:

- **The Victor boots its hard disk as `A:`**, not `C:`.
- **`~/projects/mame/victor_kermit.img` is the image.** Not an MBR disk, no
  BPB, **mtools cannot read it** — use `vtg_image_util`
  (`~/projects/vtg_image_util`, run as `python3 cli_main.py ...`). A backup
  is beside it as `victor_kermit.img.bak-20260804`. The 33 lost clusters
  `verify` reports are in partition 3 and pre-date this work.
- **MAME's `-bitb` socket is single-use.** Start `socat` first and let MAME
  be the only thing that connects; probing the port burns it.
- **Test on Victor MS-DOS 3.1, not FreeDOS** (§16a for why).
- **The emulated keyboard mangles characters** in `-autoboot_command`. Put
  the commands in a `.BAT` on the image and autoboot that. `KTEST.BAT` is
  there.
- **`-l /dev/seriala`, with forward slashes.**
- **`kermit -V` drops into interactive mode and hangs.** Always give the
  host `kermit` a command file, and a `timeout`.
- **`~/.kermrc` sets a line that does not exist.** Use `kermit -y <file>`,
  which replaces the init file and avoids the noise entirely.
- **MAME writes `cfg/` and `nvram/` into its working directory.** Run it
  from `~/projects/mame`.
- Each `KEEP_DEBUG` run is 8–11 minutes wall clock for 160 emulated
  seconds. Batch probes into one boot.

New this session:

- **`XFLAGS=-dKEEP_DEBUG` needs `make clean` first.** It is not per-file:
  `debug()` compiles to nothing without it, so a partial rebuild links
  `ckvictor.o` against a tree with no `dodebug` and dies with
  `E2028: dodebug_ is an undefined reference`.
- **A run costs ~10 minutes, so put every question you have into one
  `.BAT` and one debug build.** Three runs went on what one well-designed
  build would have answered, because each only logged one field.
- The working host receiver is `kermit -y <file>` with `set line
  /tmp/v9000`, `set speed 9600`, `set carrier-watch off`, `set flow none`,
  `log packets <file>`, `receive`.

## 6. State of the working tree

Clean. `8688f81` is this session's commit; `git diff --stat` against its
parent touches only `CLAUDE.md`, `PORTING.md`, `ckvictor.c` and
`victor/sys/termios.h`. **No upstream file is touched.** Rules 1–7 all
hold: DGROUP reported above, and `-fstack-usage` puts `tcsetattr` at 34
bytes and `tcsendbreak` at 40.

## 7. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victor9k.mak"     # gcc, links ckermit.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"     # Watcom, links ckermitw.exe
```

Both print their DGROUP figure on link. Diagnostic variants, neither set by
any makefile and both needing a `clean` first: `XFLAGS=-dKEEP_ICP` restores
the interactive parser, `XFLAGS=-dKEEP_DEBUG` the debug log. Rule 4 still
applies: report the DGROUP number after any change that could add static
data.

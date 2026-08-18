# §16az — FreeDOS for Victor: the second DOS runs, on the second channel

**18 August 2026, no Victor in reach.** Six MAME legs at 9600 on
**FreeDOS for Victor**, which this port has claimed to support since §16a and
has never once been run on. Legs FDB, FDC, FDE, FDF, FDG plus one capture
that is not a leg. Victor counters `v9k/legs/FD*.OUT`; the capture is
`v9k/legs/FDBOOT-chanA-trace.txt`. **No code change of any kind** — the
binary is §16ay's, bit for bit — and **no upstream edit; still twenty.**

**This sheet was not written before the sitting, and saying so is the point.**
It is the record of what was run, in the order it was run, including the leg
that was spent on a precondition nobody had checked. §0 below is what a
*future* FreeDOS sitting should check first, and every row in it exists
because this one did not.

---

## §0 — preconditions for any FreeDOS leg

| check | this sitting | how |
|---|---|---|
| **channel A is not a Kermit wire on this kernel** | **NOT CHECKED — cost leg FDC** | boot with `-rs232a null_modem -bitbanger <file>` and nothing of ours running; the file must be **empty** |
| image backed up | yes, before any write | `cp` (259 MB) |
| target names fresh | `RCVFDC.DAT`, `RCVFDE.DAT`, `FD?.OUT` — none used before | `hybridfat.py list` |
| every receive `.BAT` opens with `IF EXIST <target> DEL <target>` | yes, all of them | §16al's rule |
| `.BAT` files CRLF **after** landing on the image | round-tripped and verified | `hybridfat.py get` + `cat -v` |
| staged binary md5 round-trips off the image | `d76c10b2…`, both directions | `hybridfat.py get` + `md5` |
| free space on the volume | 32,183 of 32,274 clusters (99.7%) free | `hybridfat.py info` |
| the `-d` guard (§16aw) | every leg reports `deb=0`; no leg used `-d` | the `.OUT` |
| **`AUTOEXEC.BAT` saved before being replaced** | yes, as `AUTOEXEC.OLD` on the image | the leg driver replaces it |

**The first row is the one that matters and it is new.** See "What channel A
actually carries", below.

---

## The image, and why neither mtools nor `vtg_image_util` can touch it

`tools/freedos_stage1.img` is the **Victor 9000 hybrid** format described in
`~/projects/myfreedos/docs/victor/VICTOR_HYBRID_DISK_STRUCTURE.md`: a Victor
drive label at sector 0 for the ROM's IPL vector, the stage-1 loader in
sectors 1–128, and then an **IBM-style FAT16 BPB at sector 129** whose
`hidden_sectors` field is 129 and is the bridge between the two worlds.

mtools looks for a BPB at sector 0 or in an MBR partition table and finds
neither. `vtg_image_util` expects Victor virtual volumes and finds a FAT.
**Do not point either at this image.**

What is actually there, read out of the BPB rather than assumed:

```
BPB sector   129  (hidden_sectors, OEM 'V9KFDOS')
volume       FREEDOS  FAT16
geometry     512 B/sec, 16 sec/clus (8192 B), 2 FATs x 127 sec
layout       FAT1 130  root 384 (512 ent)  data 416
clusters     32274 total
```

**Caution, unexplained and not chased:** the file is **506,848 sectors** and
the BPB declares a volume of **516,800** — 9,952 sectors short. Every file
this sitting wrote landed in the low clusters, so nothing touched the gap,
but a tool that allocates high on this image will write past the end of the
file. Nothing here depends on it and nothing here explains it.

### The tool

**`v9k/tools/hybridfat.py`** — `info` / `list` / `put` / `get` / `del` on the
FAT16 volume of a hybrid image. The one design point worth keeping is that
**it does not assume 129**: the BPB is at `hidden_sectors` and
`hidden_sectors` is *inside* the BPB, so it tries 129 and then 0 and accepts
a candidate only when the sector it found agrees with the field it read.
That makes the same tool work on a plain floppy image and makes a wrong
guess fail loudly instead of silently reading the middle of a FAT.

`copy_to_victor_dos.py` in the myfreedos tree **cannot do this job** and
should not be adapted to: it hardcodes a *Victor MS-DOS* geometry
(volume at sector 2, 4 sectors/cluster, 38-sector FATs, root 32 sectors)
that matches nothing in this image, and it has no overwrite path.

**The reader was verified before the writer was trusted**: `get` on two files
already on the image — `FC.EXE` (14,835 bytes, two clusters, so the chain
walk is exercised) and `ANSITEST.COM` (159 bytes, one) — both md5-identical
to their host originals. Then `CKERMITW.EXE` in and back out, md5-identical.

---

## The build under test

**Unchanged from §16ay.** HEAD `4ac5e20`, Open Watcom V2, large model.

| | file | DGROUP | needs at load | smallest Victor | md5 |
|---|---:|---:|---:|---|---|
| shipping (`CKERMITW.EXE`) | 230,756 | 48,896 (74%) | 242,852 (237K) | **384K** | `d76c10b2…` |

`make -f victorow.mak` was run and had nothing to do. **That is deliberate:
this sitting is a claim about a DOS, not about a build, and the binary that
ran here is the same one §16ay measured on Victor MS-DOS 3.1.**

Host: FreeDOS for Victor, `FreeCom 0.87`, reporting **DOS 6.22, OEM 0xFD**.

---

## The legs

| leg | what | channel | host |
|---|---|---|---|
| FDA | first run, display on, `-f` | A | none |
| FDB | `-f`, `--nodisplay` — the identity oracle | A | none |
| — | **channel A capture, nothing of ours running** | A | none |
| FDC | 32 KB receive | **A** | sends at t+110 |
| FDE | 32 KB receive | **B** | sends at t+110 |
| FDF | 32,768-byte send by name | **B** | receives from t+40 |
| FDG | display on, `-f` | B | none |

Harness: `socat` first, MAME second, exactly §16a — except that the socket
goes to **`-rs232b`** from leg FDE onward.

```sh
socat -d -d TCP-LISTEN:8000,reuseaddr,fork pty,raw,echo=0,link=/tmp/v9000 &
~/projects/mame/mame victor9k -rompath ~/projects/mame/roms -ramsize 896K \
  -scsi:0 harddisk -hard1 tools/freedos_stage1.img \
  -rs232b null_modem -bitb socket.127.0.0.1:8000 \
  -window -skip_gameinfo -seconds_to_run 400 -snapshot_directory snaps -nomaximize
```

**`-bitb` is ambiguous with two null_modems attached.** Leg FDE's first
attempt asked for `-rs232b null_modem -bitb socket…` *and* `-rs232a
null_modem -bitbanger file`, and the socket bound to the wrong slot:
`/tmp/v9000: No such file or directory`, host FAILURE, 0.000 sec. Capture
channel A in its own run.

There is no `-autoboot_command` anywhere in this sitting. **`AUTOEXEC.BAT`
is the leg selector** — one line, `FDx` — which removes the emulated keyboard
entirely (§16a's reason) and is why the original is saved as `AUTOEXEC.OLD`.

---

## Results

### Leg FDA — the first run, and it produced nothing

`CKERMITW -l COM1 -b 9600 -f > FDA.OUT`, display on, `-seconds_to_run 150`.

**`FDA.OUT` came back 0 bytes.** The program had not exited when MAME was
killed under it, so DOS never flushed the redirect — §16au's failure mode
exactly, and the third time this project has read a zero-byte `.OUT` as a
result rather than as a missing one. The screen showed kernel text and a
fragment reading `FRKJ 0002`.

**The first reading of that fragment was "our console arm is printing
garbage on FreeDOS", and it is RETRACTED here.** `victor_trace.c` in the
myfreedos kernel writes its own debug region to **screen rows 12–24**, which
is where the fragment was. Nothing in this sitting distinguishes our output
from the kernel's on that screen, and leg FDG below did not manage to
either. **The console arm on FreeDOS remains unverified.**

### Leg FDB — the identity oracle: PASS, and it is the headline

`CKERMITW --nodisplay -l COM1 -b 9600 -f > FDB.OUT`, no host, no `socat`,
nothing on the wire. `-f` is the cheapest thing that opens the line,
programs the chip, installs the ISR and then exits on its own, so the exit
report is reached without a fixture.

```
v9k: dos oem=fd ver=622 irq1=09
```

**That is the FreeDOS branch, and §16av records it as never having
executed.** `AH=30h` returned BH = 0xFD, `v9k_dosid()` took the FreeDOS arm,
and IRQ1 was hooked on **INT 09h** rather than MS-DOS 3.1's 41h. The rest of
the report says the whole path underneath it works:

```
Protocol error
Closing COM1...OK
v9k: isr=asm deb=0
v9k: rxlost=0 rxfull=0 rxpeak=0 of 4096
v9k: txgap n=12 max=6 at #1 tot=6 cs
v9k: nap per=682 n=2 req=900 ms tot=127 cs cc=0
v9k: coll=1
```

- `COM1` **opened and closed cleanly.** FreeDOS's COM device is a character
  device with attribute `0x8000` and no IOCTL bit (`kernel/io.asm`), so
  `AX=4402h` fails and §1b's direct-programming fallback ran — the path
  written for this DOS in §11a and never before executed either.
- `txgap n=12` — the polled transmitter put **twelve FINISH packets** on the
  wire.
- `Protocol error` is the correct outcome with nobody answering.
- `nap per=682` — §16av's calibrated busy loop ran and produced an answer.

### What channel A actually carries — the capture, and it is not a leg

Booted with `AUTOEXEC.BAT` reduced to `ECHO OFF` and a REM, **nothing of ours
running at all**, `-rs232a null_modem -bitbanger`. 150 seconds produced
**2,861 bytes** on channel A.

It is the FreeDOS kernel's own trace, and **it is live, not boot-only**:

```
init_kernel entry
sv21o=3BDA
...
LT_ent
LT_exec
HHHHHHHHHHHHHHHHHHHHDO_mfc
DO_ret
HHDWU_ent
...
HHHDRWS
HDRWS
H
```

The `H` stream is **`kernel/entry.asm:280`**, which on every INT 21h call
busy-waits on TBE and writes an `H` to the µPD7201 channel A data register at
`E000:0040`:

```asm
%ifdef VICTOR9000
                ; TRACE: Output 'H' to serial to confirm INT 21h handler reached
                mov     [cs:i21_save_ax], ax
                mov     [cs:i21_save_es], es
                mov     ax, 0E000h
                mov     es, ax
.i21_wait:      test    byte [es:0x42], 0x04    ; TBE?
                jz      .i21_wait
                mov     byte [es:0x40], 'H'
```

`I42` / `DRWS` / `DWU_ent` / `DO_mfc` are the SASI and disk paths on top of
it, and `victor_int13.asm:804` writes a `W` the same way. **There is no
runtime switch** — the guard is `%ifdef VICTOR9000`, which is always on for
this target — so turning it off is a myfreedos kernel rebuild.

**This port uses INT 21h for every console write and every file write (hard
rule 6), so on this kernel a Victor transferring a file is a Victor
generating trace bytes on channel A the whole time.**

### Leg FDC — 32 KB receive on channel A: byte-exact, and *that* is the surprise

`RCVFDC.DAT` **md5-identical** to `TRANS.DAT` (`d94d2beda069ef0ef340977e7fd6995d`).
Host: SUCCESS, **5 damaged packets, 1 timeout, 6 retransmissions**, 50.050 s,
654 cps.

```
v9k: rxlost=0 rxfull=0 rxpeak=309 of 4096
v9k: rxbytes=39834 peakat=4397 stallat=4344
v9k: peaktag=10 fd=0 stall256=1
v9k: bulk sel=1 n=11938
v9k: elapsed=5201 cs wire=765 B/s
```

The packet log puts every damaged packet in the startup handshake — the host
retransmits its S packet six times and its F packet five, and lines 17, 20,
23, 26 and 29 are `r-xx-00-<crunched:chk3>`. One `<timeout>` at packet 06,
and the data phase is otherwise clean.

**The transfer completed byte-exact while the kernel injected trace bytes into
the same wire.** That is a fact about the protocol's error recovery and not
about the port, and it should not be read as either. What it does justify:
`rxbytes = 39,834` here against **37,569** on the clean channel-B leg — 2,265
bytes of difference, which is the tracer plus what the tracer's corruption
cost in retransmission.

### Leg FDE — 32 KB receive on channel B: PASS, and perfectly clean

**The tracer is hardwired to `E000:0040`/`0042` — channel A only.** Channel B
is `0041`/`0043` and nothing in the kernel writes it. This port already
selects channel B from a device name ending in `B` or `2` (`v9k_ser_selchan()`),
and FreeDOS exposes `COM2` as a character device on the same INT 14h driver.
So the fix costs nothing: `-l COM2`, and `-rs232b` on the MAME side.

`RCVFDE.DAT` **md5-identical** to `TRANS.DAT`. Host: SUCCESS, **0 damaged
packets, 0 timeouts, 0 retransmissions**, 47.830 s, **685 cps**.

```
v9k: isr=asm deb=0
v9k: dos oem=fd ver=622 irq1=09
v9k: rxlost=0 rxfull=0 rxpeak=19 of 4096
v9k: peaktag=6 fd=0 stall256=0
v9k: rxbytes=37569 peakat=76 stallat=0
v9k: norx=0 othrx=0 rr0=00 oth=00
v9k: bulk sel=1 n=11469
v9k: wfile n=4 max=11 at #1 of 8192 tot=44 cs nospc=0
v9k: nap per=682 n=1 req=500 ms tot=71 cs cc=0
v9k: coll=1
v9k: dec n=19 max=127 at #3 tot=870 cs to=0
v9k: window ask=0 use=0 neg=1 pool=2 ring=1
v9k: elapsed=4971 cs wire=755 B/s
```

**This is the leg that confirms the diagnosis** rather than merely asserting
it: same binary, same fixture, same rate, same harness, one channel over, and
every one of leg FDC's five damaged packets and six retransmissions
disappears.

Counters against their precedents:

| counter | FDE | precedent |
|---|---:|---|
| `rxbytes` | 37,569 | 37,568/37,569 — §16af, `cautious` prefixing |
| `wfile n=` | 4 | 4 — §16n, `V9K_OBUFSIZE` 8192 |
| `bulk sel=1 n=` | 11,469 | edit 18's arm ran, §16aq |
| `coll=` | 1 | REPLACE, §16av |
| `neg=` | 1 | window 1, §16ar |
| `deb=` | 0 | §16aw's guard |
| `norx`/`othrx` | 0 / 0 | the shared-IRQ1 question |
| `rxpeak` | **19** of 4096 | **306 on MS-DOS — see below** |

**`rxpeak = 19` is not a new result, it is §16m confirmed from a new
direction.** §16m established that the peak measures the ring filling during
the *host's retransmission*, because with a window of one that is the only
moment the host transmits without waiting for our ACK. This leg had **zero
retransmissions**, and the peak accordingly collapsed from 306 to 19.
`peakat = 76` puts it 76 bytes into the stream, i.e. nowhere interesting.

**`norx = 0 othrx = 0` is a partial answer and should not be quoted as a
full one.** Channel A was being written by the tracer throughout this leg and
generated no spurious interrupts on the shared IRQ1 — but the tracer is a
*polled transmitter*, so this tests the transmit half of the shared-channel
case and not the receive half.

### Leg FDF — 32,768-byte send by name on channel B: PASS

Host received `SNDFDD.DAT`, **md5-identical** to `TRANS.DAT`. Host: SUCCESS,
**0 timeouts, 0 retransmissions**, 50.652 s, 646 cps.

```
v9k: rxlost=0 rxfull=0 rxpeak=118 of 4096
v9k: rxbytes=284
v9k: bulk sel=1 n=20
v9k: txgap n=18 max=16 at #2 tot=48 cs
v9k: wfile n=0 max=0 at #0 of 0 tot=0 cs nospc=0
v9k: elapsed=5020 cs wire=5 B/s
```

`-s SNDFDD.DAT` on a file of **exactly 32,768 bytes** is upstream edit 16's
range; it neither refused the file nor printed the empty-`errno` message that
was the old bug's tell. **Third end-to-end confirmation of edit 16** (§16ah
leg BS on the bench, §16ay leg UB under MAME on MS-DOS), and the first on
FreeDOS.

`txgap n = 18` is 18 data packets, matching §16ay leg UB exactly.
`bulk sel=1 n=20` at ~14 bytes a call is edit 18's arm **inert on the send
direction**, which is §16aq's counter doing its job and reproduces UB's
`n=18`. `wfile n=0` — a send leg writes nothing.

**`wire=5 B/s` is meaningless on a send leg and is not a defect.** §16v's
rule: `wire=` divides `rxbytes`, so it is a receive-leg figure. Here
`rxbytes` is 284, the ACK stream.

### Leg FDG — the console arm: INCONCLUSIVE, and it is recorded as such

`CLS` then `CKERMITW -l COM2 -b 9600 -f` with the fullscreen display **on**,
snapshot at 210 s. The screen came back **clean** — `A:\>` and nothing else —
and `FDG.OUT` is an ordinary `Protocol error` report.

**This did not test the thing it was built for.** C-Kermit's fullscreen
transfer display is drawn during a *transfer*; a FINISH with no host on the
other end never engages it, so a clean screen here is not evidence that the
display works. **The FreeDOS console arm (§16ao's ANSI branch, chosen by the
same `AH=30h` probe that picked INT 09h) is still unverified.** The leg that
would settle it is FDE re-run **without** `--nodisplay` and with a snapshot
taken while the data phase is running.

---

## Comparison with Victor MS-DOS 3.1, and the caveat that goes with it

| | §16ay UA (MS-DOS) | FDE (FreeDOS, chan B) |
|---|---:|---:|
| host clock | 80.768 s | **47.830 s** |
| whole-run cps | 405 | **685** |
| timeouts / resends | 4 / 7 | **0 / 0** |
| `rxpeak` | 306 | **19** |
| `wfile n=` | 4 | 4 |
| ~27 s F-packet stall | **yes** | **no** |

**Read this as an observation and not as a measurement of either DOS.** It is
a cross-sitting comparison of two different operating systems on two
different disk images and two different filesystems, run on different days,
with **no adjacent control** — which is precisely the arrangement §16al
identified as the one that does not work, and the reason its "+11%" was
withdrawn. The port's own rule is adjacent pairs or nothing.

What *is* worth carrying: **§16ay's ~27 second stall between the F packet and
its ACK, which is on every MS-DOS MAME receive in this tree going back to
§16aj, did not happen here.** §16ay located it inside `rcvfil()` on the
receive-file-open path and called it "the obvious next MAME question". A DOS
on which it does not occur is a lever on that question, and it is available
for the cost of one leg per side. **It is not yet a cause** — FreeDOS's FAT16
with 8 KB clusters and MS-DOS 3.1's volume are different code and different
geometry, and nothing here separates the DOS from the filesystem from the
disk image.

**One counter to watch: `nap per=` was 682, 819, 682 and 819 across the four
legs that reported it**, where §16ay's five MS-DOS legs all read **409**.
§16av's busy loop calibrates against the 500 ms DOS clock at run time, so a
20% swing within one sitting means the calibration is not repeatable on this
DOS or this host. Nothing in this sitting depends on it — `msleep()` is used
by `tthang()` and `tcsendbreak()`, neither of which any leg exercised — but a
session that comes to rely on `nap()` timing on FreeDOS should measure it
first.

---

## Verdict

**Six legs. The port runs on FreeDOS for Victor and transfers files
byte-exact in both directions**, with the same binary §16ay measured on
Victor MS-DOS 3.1 — no code change, no rebuild, no upstream edit.

**What is now proven that was not:** the FreeDOS half of the `AH=30h` IRQ1
selection (`oem=fd ver=622 irq1=09`), which §16av shipped and flagged as
never executed; §1b's direct chip-programming fallback, for a DOS whose
serial driver will not answer the §11a IOCTL; the polled transmitter, the
assembly ISR, the receive ring and edit 18's bulk arm, all on INT 09h.

**What is not proven:** the console ANSI arm (leg FDG failed to engage it);
the receive half of the shared-IRQ1 case; and anything at all above 9600,
which is MAME's ceiling and not this DOS's.

**The standing constraint on all future FreeDOS work is that channel A is not
a Kermit wire on this kernel.** Use `COM2`/`-rs232b`, or rebuild the myfreedos
kernel with `entry.asm:280` and its neighbours guarded. The second is worth
proposing upstream to that project — the trace is unconditional in a shipping
kernel and it costs a busy-wait on TBE inside every INT 21h call, which is a
cost to every program on the machine and not only to this one.

## The method lesson, which is §16an's for the third time

Every reading in this sitting before the capture was a counter inside one of
the two programs, and both programs were right about what they did. The
Victor said `rxlost=0`; the host said five damaged packets; neither could say
why, and the first hypothesis on the table was our own console arm. **The
question was about a wire, and it was settled in 150 seconds by putting a
capture on the wire with nothing of ours running.** §16an wrote that rule
about RTS; §16am wrote the neighbouring one about measuring that the far end
can do what an experiment assumes. This adds a third face of the same thing:
**before running a leg on a machine you have not run on before, capture what
that machine puts on the wire when your program is not there.**

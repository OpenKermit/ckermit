# Next session

Handoff for the Victor 9000 port, written 5 August 2026. **`RECEIVE` works, a
file makes the round trip byte-exact, and two defects were fixed — one of which
had been quietly corrupting every transfer since §16d.**

**Read `PORTING.md` first** — §16h is new and is this session; §8 now lists
nine guarded upstream edits, not eight; milestone step 6 is half done; and
§15's "closed" list gained three items. This file is only the "what next".

---

## 1. What changed this session

**Milestone step 6, first half: `RECEIVE`.** 2,048 bytes to the Victor and the
same 2,048 bytes back, in one MAME run on Victor MS-DOS 3.1, `EXIT status=0`
both ways, loss counters `rxlost=0 rxfull=0` in **both** directions.

The payload is why this one counts: 0x00–0xFF cycled eight times, so it
contains every byte value — including LF, CR and **0x1A**. Every fixture before
this was a `.TXT` file.

| | before | after |
|---|---|---|
| `RECEIVE` into `A:\` | `E "Write access denied"` | works |
| 2048 bytes received, on disk | 2056 | **2048, identical** |
| that file sent back | **25 bytes** | **2048, identical** |
| `feol` | 10 | **0** |
| `_fmode` | 0100 (O_TEXT) | **0200 (O_BINARY)** |

**Defect 1 — `access(".")` in a FAT root.** `zchko()` creates the incoming
file, deletes it, then asks `access(".",W_OK)` for permission to do what it
just did — and got EACCES. A FAT root has no directory entry of its own, so
INT 21h AH=43h does not fail for it, it **succeeds and returns garbage**:
`006b` (read-only set, directory bit clear) as `.`, `00ff` or `0000` by other
spellings. A named subdirectory answers `0010` cleanly, which is why the same
transfer into `A:\TEST` worked first time. Fixed with our own `access()` in
`ckvictor.c` §1d.

**Defect 2 — the runtime was translating every transfer, both ways, and had
been all along.** `ckufio.c` is the **Unix** file module: `zopeni()` is a bare
`fopen(name,"r")` and `zopeno()` only ever builds `"w"`/`"a"`. Neither consults
`binary`. On DOS that means LF↔CRLF on every stream and 0x1A as end-of-file on
input.

**This retracts §16d's and §16g's "byte-correct".** Those runs recorded 74→72,
63→61, 54→53 and called it text-mode conversion; the host logs in the same runs
say `Global file mode: binary`. It was the DOS runtime mangling a binary
transfer. The step-5 result stands — a transfer completed, engine and driver
and file system all worked — but "byte-correct at the far end" is §16h's claim
now, not §16d's.

Fixed by a **pair**, and neither half is correct alone:
- `_fmode = O_BINARY` from an initializer in `ckvictor.c` §1d.
- `#undef NLCHAR` for `VICTOR9K` in `ckcdeb.h` — the **ninth** guarded upstream
  edit, agreed, and sitting in the block that already does this for OS/2 and
  the Atari ST, under the comment that asks for it.

**Open Watcom's `binmode.obj` does not work in this program**, and the negative
result is written up in §16h so it is not rediscovered. It sets `_fmode`
correctly in a small test program — with the shipped object *and* the
large-model one — and leaves it at 0100 in `CKERMITW.EXE`. What works is
registering the initializer ourselves as a **far** record (`rtn_type = 1`);
`binmode.obj` uses the near form. **Why the near form fails here is still not
known.** The witness flag in `ckvictor.c` (`v9k fmode witness=1`,
`v9k _fmode=512`, logged from `access()`) is what makes that a measurement.

Sizes after a clean rebuild: DGROUP **39,424 of 65,536 (60%)** — unchanged, as
it should be, since everything added is code. `ckermitw.exe` **228,660 bytes**
(was 228,554); the `KEEP_DEBUG` image is **309,046**.

---

## 2. Do this next, in rough priority order

**Finish milestone step 6: `GET`, then `SERVER`,** at 9600. `RECEIVE` is done;
these two have not been tried at all. `GET` is the interesting one — it needs
the Victor to *send* a command and then receive, which is the first time the
port drives both directions inside one transaction.

**Re-run a wildcard send now that binary mode is real.** §16g's `-s *.TXT`
result was measured through the translating streams, so its byte counts are
not what they will be now. Cheap, and it re-establishes the multi-file
`znext()` path against a correct baseline.

**Consider raising the stack.** Unchanged from last session and still
deliberately not bundled with anything else. `wlink`'s map says `STACK 2,048`
— Watcom's default, inherited rather than chosen. `traverse()` is 98
bytes/level and the largest non-recursive frames are `docmd()` at 1152 and
`zcopy()` at 1114, so a deep walk landing in `docmd()` is already most of 2K.
The new `access()` adds a 68-byte leaf frame (`sub sp,38H` plus pushes, read
from `wdis`). There are 26,112 free bytes in DGROUP and nothing else wants
them. `option stack=8k` in `victorow.mak`.

**Then step 8: long packets, windows, streaming, one at a time.** The far heap
means `SBSIZ`/`RBSIZ` can grow — 9024/9050, the `DYNAMIC` default, would cost
nothing in DGROUP. Measure the *image* against the machine's 387K (§16a's
method), not DGROUP.

**`NOGFTIMER`.** Still not turned off, and still why `emu87.lib`/`math87l.lib`
are in the link (89 of the image's INT sites). Turning it off drops the FP
emulator and buys back image space for step 8. §16h ruled it out as the cause
of the `binmode.obj` mystery, so nothing depends on leaving it in.

---

## 3. Instruments

- **`XFLAGS=-dKEEP_DEBUG`** — C-Kermit's own debug log. `CKERMITW -d -s
  FOO.BIN` writes `./debug.log` on the target. Needs `make clean` first.
  Image goes 228,660 → 309,046 bytes and still loads.
- **The debug log's line endings are an `_fmode` oracle** (new, §16h).
  `debopn()` goes through the same `zopeno()` the transfer files use, so CRLF
  pairs mean the runtime is translating and bare LF means it is not.
  `CKERMITW -d -h` writes one and exits — **no serial line, no `socat`, no
  host `kermit`, ~2.5 minutes instead of ~9.** Use it before spending a full
  transfer run on anything file-I/O shaped.
- **The witness lines** `v9k fmode witness=` and `v9k _fmode=` appear once per
  run, from `access()`, immediately before the first incoming file is created.
  Expect `1` and `512`. `0` means the XI record stopped being reached; `1`
  with `256` means something put `_fmode` back.
- **The driver's two counters**: `v9k_ser rxlost/rxfull[N]=M`, logged from
  `tcsetattr()`, which `ttres()` reaches on the way out. Baseline 0/0, now in
  both directions.
- **`.probe/`** holds throwaway programs, not part of the build. Build lines
  are in the comment at the top of each. `vaccess.c` (what DOS says about the
  root directory), `vfmode.c` and `vfmodefp.c` (whether `binmode.obj` works,
  with and without the FP emulator), `vwild.c`, and `vmatch.c` (gcc — no
  longer buildable, kept for the questions it asked).
- **`XFLAGS=-dKEEP_ICP`** — restores the interactive parser, for re-running
  §9d's DGROUP measurement. It links and it does **not load** — 429K needed
  against 387K offered.
- **There is no `-fstack-usage` equivalent under Open Watcom.** Read the
  source for new automatics; if it matters, read the prologue's `sub sp,N` in
  `wdis` output.

---

## 4. Things in the driver that are known-incomplete

Unchanged; listed so they are not rediscovered as bugs.

- **No interrupt-level flow control.** 3.13 sends XOFF from inside `SERINT` at
  a 3/4-full mark. Not needed with one packet in flight — and `rxfull=0` now
  says so for **receive** as well as send, at 9600. Needed for streaming.
  `tcflow()` is a stub for the same reason.
- **No stack switch in the handler.** Deliberate — 3.13's `SERINT` does not
  switch either, on this machine. The frame is ~30 bytes.
- **The IRQ1 vector is hard-coded to 41h.** Right for Victor MS-DOS 3.1;
  `~/projects/myfreedos` puts its serial ISR at INT 09h, so this is the most
  likely thing to break "one binary, two DOSes". One constant, §1e.
- **Ctrl-Break with the line open.** Restored from `atexit()`, which does not
  cover a Ctrl-Break DOS turns into a bare termination. Fix, if it bites: hook
  INT 23h (`AH=25h`, inside rule 6).
- **WR2 is left as the OEM driver set it** (`10h`, where 3.13 writes `14h`).
  First thing to try if interrupts ever fail to arrive.
- **The carrier clause** in `ttgmdm()` forces carrier present under `CLOCAL`.
  Reasoning in §11b.

---

## 5. Still open, from before

**Nothing has run on real hardware.** Everything is MAME, Victor MS-DOS 3.1.
That is now, unambiguously, the largest single gap in the port, and it has not
moved.

**The 42KB gap for the interactive parser.** Needs 429KB, DOS offers 387KB
(§16a, measured).

**The µPD7201 interrupt-acknowledge sequence.** §11b's handler issues
`WR0 = 38h` then the 8259's specific EOI and works under emulation, which is
what 3.13 does. MAME's µPD7201 is not the part, so this is not settled, and it
gates 38400. The zero loss counters are at 9600 and do not speak to it.

**Why `binmode.obj`'s near init record does not work here** (§16h). Routed
around, not diagnosed. Only matters again if the far record ever stops working
— the witness lines are there for exactly that.

---

## 6. The harness

§16a, §16d, §16g and §16h have it in full. The landmines:

- **`-autoboot_command` takes the literal two-character escape `\n`, not a real
  newline.** Writing `$'\n\nFOO\n'` in bash sends 0x0A bytes, MAME types
  nothing, and the run looks exactly like a program that hung. Use
  `"\n\nFOO\n"` in double quotes. Cost a full run this session.
- **`.BAT` files must have CRLF line endings.** With Unix `\n`, COMMAND.COM
  echoes every line and runs none.
- **MAME does not exit when `-seconds_to_run` expires.** It writes
  `Average speed: ...` to its log and sits there. Poll the log, not the
  process: `until grep -q "Average speed" mame.log; do sleep 10; done`.
- **Budget the emulated seconds.** A 2048-byte binary receive plus the same
  file sent back took ~150 s of transfer inside `-seconds_to_run 480`. Boot
  plus `-autoboot_delay 30` eats the first ~60 s. A probe-only run is fine at
  150.
- **Start the host `kermit` ~60 s after MAME**, and give it `set retry 20`.
  Sooner and it burns its retries against a machine that is still booting.
- **`grep` the extracted `DEBUG.LOG` with `-a`.** It contains NUL bytes, so
  plain `grep` silently prints nothing and looks like "no match".
- **MS-DOS 3.1 cannot redirect handle 2.** `2> FILE` puts a literal `2` in
  `argv`. Handle 1 and `>>` both work.
- **The Victor boots its hard disk as `A:`**, not `C:`.
- **`~/projects/mame/victor_kermit.img` is the image**; mtools cannot read it,
  use `vtg_image_util` (`python3 cli_main.py ...`). Backups beside it, newest
  `.bak-20260805-recv`.
- **On the image now:** the plain (non-debug) `CKERMITW.EXE`, `RECV.BAT` (the
  §16h receive-then-send-back test), `RXBIN.DAT` (the 2048-byte all-byte-values
  fixture), the `.probe` executables `VACCESS/VFMODEA/VFMODEB/VFMODEC/VFMODEF/
  VFMODEG.EXE` and their `.BAT` drivers, plus `ALPHA.TXT`/`BETA.TXT`/
  `TESTFILE.TXT` from §16g.
- **MAME's `-bitb` socket is single-use.** Start `socat` first, with `fork`,
  and it survives across runs.
- **Test on Victor MS-DOS 3.1, not FreeDOS** (§16a).
- **`-l /dev/seriala`, with forward slashes.**
- **Always give the host `kermit` a command file and a timeout**; `~/.kermrc`
  sets a line that does not exist, so use `kermit -y <file>`.
- **Run MAME from `~/projects/mame`** — it writes `cfg/` and `nvram/` into the
  working directory.
- **`XFLAGS=-dKEEP_DEBUG` needs `make clean` first.**
- **Digits come through shifted in `-autoboot_command`.** Prefer digit-free
  filenames in automated runs.
- A transfer run costs 8–9 minutes of wall clock; a boot-and-run-a-program run
  costs ~2.5. Put every question into one `.BAT`.

## 7. Rebuilding

```sh
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak"        # ckermitw.exe
container exec -i ia16-ubuntu-2 bash -c \
  "cd /mnt/projects/ckermit && make -f victorow.mak sizes"  # DGROUP report
```

The link prints its DGROUP figure. Rule 4 still applies — report DGROUP after
any change that could add static data — but note the second half of it: the
heap is **outside** DGROUP, so anything that raises the packet buffers has to
be measured against the machine's 387K, not against this segment.

# Next session

Handoff for the Victor 9000 port, written 5 August 2026. **Milestone step 6 is
complete: `GET` and `SERVER` both work, the port transfers byte-exact as
client and as server, and §16g's wildcard send has been re-measured at its
true byte counts.**

**Read `PORTING.md` first** — §16i is new and is this session; milestone step 6
is struck through in §13; §15 gained three "still open" entries and lost one.
This file is only the "what next".

---

## 1. What changed this session

**`GET`, and the first time the port drives a server.** `CKERMITW -g
GETBIN.DAT` against a host `server`: 512 bytes cycling 0x00–0xFF twice, **MD5
identical** on the Victor's disk, `EXIT status=0`, `filcnt=1`, `rxlost/rxfull
0/0`. A second invocation, `-f`, sent a `G F` the host ACKed and shut its
server down.

**`SERVER`, after the session's one real discovery.** The first `-x` run
refused *everything* — and the packet log shows it ACKing the host's `I`
packet correctly in between the refusals, so nothing was broken:

```
s-00-04-^A, RRXBIN.DAT H       -> r-00-02-^A/ EGET disabled
s-00-00-^A9 S~/ @-#Y3~...      -> r-00-03-^A0 ESEND disabled
s-00-05-^A$ GF4                -> r-00-02-^A2 EFINISH disabled
```

`ENABLED()` in `ckcker.h` is `(local && (x&1)) || (!local && (x&2))`, and
C-Kermit 11 initialises every `en_*` to **2** — remote mode only. A Victor
that owns its serial line **is** local, so a `-x` server has every capability
switched off. That is upstream policy, stated in upstream's own ENABLE help
("enabled for REMOTE but disabled for LOCAL to prevent security issues"), and
`compat_10()` dates it: 9 and 10 shipped these at 3, and 11 tightened them.
Normally you type `ENABLE GET`; `NOICP` removes the prompt.

**The decision is now made at startup, in `ckvictor.c`, and it is still nine
guarded upstream edits.**

```
CKERMITW -x                  everything the build can do  (default)
CKERMITW -x --safe-server    GET, SEND and FINISH only
```

The switch is parsed by an XI initializer at **priority 0**, which blanks it
out of Watcom's copy of the DOS command tail *before* `__Init_Argv` builds
`argv` at priority 1 — so `cmdlin()` never sees an option it would kill the
program over. §16i has the two source citations that make that orderly rather
than lucky.

**Measured, after the change:**

| | full set | `--safe-server` |
|---|---|---|
| host `get RXBIN.DAT` | 2048, identical | 2048, identical |
| host `send` → Victor | 512, identical | 512, identical |
| host `remote directory` | streams, never ends | `E REMOTE DIRECTORY disabled` |
| host `finish` | never sent (see §4) | honoured, server exits |
| `v9k srvcaps safe` | 0 | 1 |

**The wildcard send, re-measured now that the streams do not translate** —
this is the number that closes §16h's retraction:

| file | on disk | §16g | now |
|---|---|---|---|
| `ALPHA.TXT` | 63 | 61 | **63, identical** |
| `BETA.TXT` | 54 | 53 | **54, identical** |
| `TESTFILE.TXT` | 74 | 72 | **74, identical** |

Sizes: DGROUP **39,440 of 65,536 (60%)**, `ckermitw.exe` **229,070**;
`KEEP_DEBUG` DGROUP 39,792, image **309,506**. The capability work cost ~440
bytes, all far code.

---

## 2. Do this next, in rough priority order

**Real hardware.** Nothing has ever run on one, and with step 6 closed this is
now the only thing between the port and "it works". Everything below is
smaller than this.

**Decide what `-x` should offer by default.** It currently offers everything,
and one of those capabilities (`REMOTE DIRECTORY`) hangs — see §4. Flipping
the default to the safe set is a two-line change in `v9k_set_srvcaps()`; the
switch would then select the full set instead. This is a judgement call about
who is on the far end, not a bug fix.

**`REMOTE DIRECTORY`.** Streams all 50 entries correctly, never sends the
terminating Z. `snddir()` is C-Kermit's own lister, so it is upstream code all
the way down. Cheap first step: `--safe-server` refuses it, so a run that
needs a clean FINISH is not blocked while this is open.

**Then step 8: long packets, windows, streaming, one at a time.** The far heap
means `SBSIZ`/`RBSIZ` can grow — 9024/9050, the `DYNAMIC` default, would cost
nothing in DGROUP. Measure the *image* against the machine's 387K (§16a's
method), not DGROUP.

**Consider raising the stack.** Unchanged, and still deliberately not bundled
with anything else. `wlink`'s map says `STACK 2,048` — Watcom's default,
inherited rather than chosen. `traverse()` is 98 bytes/level and the largest
non-recursive frames are `docmd()` at 1152 and `zcopy()` at 1114. The two new
routines this session add 10 and 24 bytes and run at startup. There are 26,096
free bytes in DGROUP. `option stack=8k` in `victorow.mak`.

**`NOGFTIMER`.** Still not turned off, and still why `emu87.lib`/`math87l.lib`
are in the link. Turning it off drops the FP emulator and buys back image space
for step 8. §16h ruled it out as the cause of the `binmode.obj` mystery.

---

## 3. Instruments

- **`XFLAGS=-dKEEP_DEBUG`** — C-Kermit's own debug log. Needs `make clean`
  first. Image 229,070 → 309,506 and still loads.
- **`CKERMITW -d -h` is the 2.5-minute oracle.** No serial line, no `socat`,
  no host `kermit`. It reaches `sysinit()` → `uname()`, so **anything decided
  before `main()` can be witnessed there** — `v9k srvcaps safe=` and
  `v9k fmode witness=` both are. The log's own line endings are the `_fmode`
  oracle (CRLF = the runtime is translating).
- **Run the control when testing a command-line switch.** Under `NOICP` any
  `--` argument is `XFATAL("Extended options not configured")`, so
  `CKERMITW -d --bogus-opt -h` is what distinguishes "our option was consumed"
  from "upstream ignored it". Without it the test proves nothing.
- **The witness lines**: `v9k srvcaps safe=` (0 full, 1 safe),
  `v9k fmode witness=` / `v9k _fmode=` (expect 1 and 512).
- **The driver's two counters**: `v9k_ser rxlost/rxfull[N]=M`, from
  `tcsetattr()`, which `ttres()` reaches on the way out. 0/0 everywhere so far.
- **`.probe/`** holds throwaway programs, not part of the build. Build lines
  in the comment at the top of each.
- **`XFLAGS=-dKEEP_ICP`** — restores the parser, for re-running §9d's
  measurement. Links, does **not** load: 429K needed against 387K.
- **There is no `-fstack-usage` under Open Watcom.** Read the source for new
  automatics; if it matters, read the prologue's `sub sp,N` in `wdis` output.

---

## 4. Things that are known-incomplete

- **`REMOTE DIRECTORY` never terminates its listing** (§16i). It is enabled by
  default. When it fails the host also never sends the following FINISH, so
  the Victor's server stays up and its `DEBUG.LOG` is never flushed — which
  costs you the whole run's Victor-side log. Use `--safe-server` for any run
  where you need the log.
- **Most of the default capability set is untested.** DELETE, RMDIR, CWD,
  SPACE, TYPE, RENAME, COPY, MKDIR are all enabled and have never been on the
  wire. `BYE` has never been sent; FINISH is the only shutdown ever tried.
- **Wildcards are case-sensitive.** `-s *.txt` matches nothing on a FAT
  volume; `-s *.TXT` matches. `ckufio.c:6262` passes `icase=1`, which
  `ckclib.c:1344` documents as case-sensitive. You will type this wrong again.
- **No interrupt-level flow control.** Not needed with one packet in flight —
  `rxfull=0` in every direction at 9600. Needed for streaming. `tcflow()` is a
  stub for the same reason.
- **No stack switch in the handler.** Deliberate — 3.13's `SERINT` does not
  switch either. The frame is ~30 bytes.
- **The IRQ1 vector is hard-coded to 41h.** Right for Victor MS-DOS 3.1;
  `~/projects/myfreedos` puts its serial ISR at INT 09h, so this is the most
  likely thing to break "one binary, two DOSes". One constant, §1e.
- **Ctrl-Break with the line open.** Restored from `atexit()`, which does not
  cover a Ctrl-Break DOS turns into a bare termination. Fix, if it bites: hook
  INT 23h (`AH=25h`, inside rule 6).
- **WR2 is left as the OEM driver set it** (`10h`, where 3.13 writes `14h`).
  First thing to try if interrupts ever fail to arrive.
- **The carrier clause** in `ttgmdm()` forces carrier present under `CLOCAL`.

---

## 5. Still open, from before

**Nothing has run on real hardware.** Everything is MAME, Victor MS-DOS 3.1.
Unchanged, and now the largest gap by a wide margin.

**The 42KB gap for the interactive parser.** Needs 429KB, DOS offers 387KB
(§16a, measured).

**The µPD7201 interrupt-acknowledge sequence.** §11b's handler issues
`WR0 = 38h` then the 8259's specific EOI and works under emulation, which is
what 3.13 does. MAME's µPD7201 is not the part, so this is not settled, and it
gates 38400. The zero loss counters are at 9600 and do not speak to it.

**Why `binmode.obj`'s near init record does not work here** (§16h). Routed
around, not diagnosed. The far record this port registers itself is now used
twice — `_fmode` at priority 32 and the capability set at priority 0 — so the
mechanism has more riding on it than it did.

---

## 6. The harness

§16a, §16d, §16g, §16h and §16i have it in full. The landmines:

- **`-autoboot_command` takes the literal two-character escape `\n`, not a
  real newline.** Use `"\n\nFOO\n"` in double quotes.
- **`.BAT` files must have CRLF line endings.** With Unix `\n`, COMMAND.COM
  echoes every line and runs none.
- **MAME does not exit when `-seconds_to_run` expires.** Poll the log, not the
  process: `until grep -q "Average speed" mame.log; do sleep 10; done`.
- **The host `kermit`'s stdout is buffered until it exits**, so `echo` markers
  in a `-y` command file all arrive at once at the end. Watch the transaction
  log for live progress, not stdout.
- **Budget the emulated seconds.** 9600 with short packets runs about 14 cps
  host→Victor and 55 cps Victor→host — a 2048-byte send takes ~110 s, the same
  file back ~36 s. Each program load off the emulated disk is another ~15 s.
  Boot plus `-autoboot_delay 30` eats the first ~60 s.
- **Start the host `kermit` after the Victor is ready**, and give it
  `set retry 20`. If the Victor is the passive side (`-r`, `-x`), start the
  host later; if the Victor is active (`-s`, `-g`, `-f`), have the host
  waiting first.
- **`grep` the extracted `DEBUG.LOG` with `-a`.** It contains NUL bytes.
- **MS-DOS 3.1 cannot redirect handle 2.** `2> FILE` puts a literal `2` in
  `argv`. Handle 1 and `>>` both work.
- **The Victor boots its hard disk as `A:`**, not `C:`.
- **`~/projects/mame/victor_kermit.img` is the image**; mtools cannot read it,
  use `vtg_image_util` (`python3 cli_main.py ...`). Backups beside it, newest
  `.bak-20260805-get`. **Never write to the image while MAME is running.**
- **On the image now:** the `KEEP_DEBUG` `CKERMITW.EXE`, and from this session
  `GSRV.BAT`/`SRV.BAT`/`SAFE.BAT`/`WILD.BAT`, `GETBIN.DAT` and `SRVBIN.DAT`
  and `SAFEBIN.DAT` (512 each), `RXBIN.DAT` (2048), plus the logs
  `GETDBG/FINDBG/SAFESRV/WILD2/FULLCAP/SAFECAP.LOG` and the §16h leftovers.
- **MAME's `-bitb` socket is single-use.** Start `socat` first, with `fork`.
- **Test on Victor MS-DOS 3.1, not FreeDOS** (§16a).
- **`-l /dev/seriala`, with forward slashes.**
- **Always give the host `kermit` a command file**; `~/.kermrc` sets a line
  that does not exist, so use `kermit -y <file>`.
- **Run MAME from `~/projects/mame`** — it writes `cfg/` and `nvram/` into the
  working directory.
- **`XFLAGS=-dKEEP_DEBUG` needs `make clean` first.**
- **Digits come through shifted in `-autoboot_command`.** Prefer digit-free
  filenames in automated runs.
- A transfer run costs 8–10 minutes of wall clock; a boot-and-run-a-program
  run costs ~2.5. Put every question into one `.BAT`.

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

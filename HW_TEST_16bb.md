# §16bb — file collision on FAT, the MAIL disposition, and text mode

**19 August 2026, no Victor in reach. MAME sitting, 9600, Victor MS-DOS 3.1,
channel A.** **This sheet was written before any leg ran** (§16az's closing
asked for that and §16ba established the habit). Every result section is
empty until the leg that fills it has run; §0, the leg table and the
predictions are fixed in advance so a leg cannot be redefined after its
output is seen.

**Leg letters are the M series.** They were written as NA-NG and those
collided with §16av's, three of whose `.BAT` files are tracked in git and
were overwritten; they are restored and the incident is at the end of this
sheet. The legs ran under the N names and the artifacts are renamed; the
`.BAT` and `.ksc` files in the tree are the M series with fresh target
names throughout, which §16al's rule required of a re-run anyway.

**Two upstream edits, both agreed before being written — the count goes to
twenty-two.**

- **21** — `ckufio.c`'s `znewn()`, `#ifdef VICTOR9K`, calling
  `v9k_backupname()` in `ckvictor.c`.
- **22** — `ckcfn3.c`'s `gattr()`, `case 'M'` made live under
  `#if !defined(NOFRILLS) || defined(VICTOR9K)`.

---

## §0 — preconditions

| check | how | status |
|---|---|---|
| image backed up before any write | `cp` | ☐ |
| free space | `vtg_image_util info` — **`A:` is at 4.1%; everything this sitting stages goes on `D:`** | ☐ |
| target names never used before | `vtg_image_util list` on partition 1 | ☐ |
| every receive `.BAT` opens with `IF EXIST <target> DEL <target>` — **and with `IF EXIST <target>.001 DEL <target>.001`, which is new and is the whole point of this sitting** | §16al's rule, machine-kept | ☐ |
| each staged binary's md5 round-trips off the image | `copy` back, `md5` | ☐ |
| the `-d` guard: every leg reports `deb=0` | §16aw | ☐ |
| the control binary is HEAD-before-the-edits | `md5` against §16ay/§16ba's | ☑ **`d76c10b2…`, bit-identical** |
| proofs pass | `make -C v9k/proofs` | ☑ 5 of 5, `vznewn` 6,013 checks |

**The control is not merely "before the change": it is the same binary
§16ay and §16ba ran**, byte for byte, which is a stronger statement than
this project has usually been able to make about a control. `mzsize.py`:
control 230,756 → needs 242,852 (237K); treatment 231,172 → needs 243,236
(237K); **smallest Victor 384K, unchanged.** DGROUP 48,896 of 65,536 (74%),
**unchanged** — `v9k_backupname()` builds its name in a stack frame that
`znewn()`'s own `buf2[ZNEWNBL+12]` already pays for on the branch this arm
returns before reaching, so hard rule 7's budget does not move either.

**Everything runs on `D:`, and for three reasons.** `A:` has 408 KB free
and this sitting stages 693 KB of binaries; §16av leg MF is the standing
warning about a redirect on a volume under test; and §16ba established that
receiving into `A:\` costs a **~27 s stall** in `rcvfil()` that has nothing
to do with anything asked here.

---

## What this sitting is for

**1. Two of upstream's six file-collision actions have never worked on this
machine, and one of them is not optional.** `znewn()` (`ckufio.c:3925`)
makes a unique name by appending `".~<n>~"` to a name that already has an
extension. `ckcpro.c:503` forces `fncact` to `XYFX_R` — RENAME — for the
whole session on any server whose DELETE is disabled, "to undo any file
collision action that could result in deletion or modification of existing
files", **and `--safe-server` disables DELETE**. So a safe server on this
machine has never been able to receive a filename twice, and nothing has
ever watched it try. Edit 21 replaces the extension instead
(`RCVMB.DAT` → `RCVMB.001`) and finds the number by probing, because the
wildcard upstream expands describes a name FAT cannot hold and therefore
always matches nothing.

**2. `NOFRILLS` compiles out the MAIL refusal and leaves the acceptance.**
`gattr()`'s `case 'M'` is guarded and `case 'P'`, eight lines below and
identical in every other respect, is not. §16ax saw the consequence from
the outside and named it: PRINT is refused in the A-packet ACK before any
data, MAIL "is the same case handled worse". Edit 22 makes `case 'M'` live
here.

**3. Text mode has never been run in either direction.** `ckcdeb.h` undefs
`NLCHAR` for `VICTOR9K`, so `feol` is 0 and C-Kermit does no end-of-line
conversion of its own; `_fmode` is `O_BINARY`, so the runtime does none
either. §16h says those two are "only correct together" and nothing has
ever tested the pair in *text* mode — every transfer this port has made,
in five months of legs, has been binary.

---

## The legs

Fixtures, all fresh: `rcvbb1.dat` and `rcvbb2.dat`, 4,096 bytes each
(`1fe47cb2…`, `598c0a90…`), and `textlf.txt`, 2,200 bytes of LF-terminated
ASCII (`2be61470…`). Small on purpose — nothing here is a throughput claim.

Host client is **C-Kermit 9.0.302** for MA–MF, which is the client every
previous sitting used, and **C-Kermit 11.0.508 built from this tree** for
MG, which is the only leg that needs it. That split is deliberate: MG asks
for a command 9.0.302 does not have, and the other six should not change
harness in the same sitting.

| leg | binary | collision | asks |
|---|---|---|---|
| **MA** | `CKPRE21` (control) | `--safe-server` → forced RENAME | **What does the second receive of one name actually do today?** Two target names, `RCVMA.DAT` (9 chars) and `MA.D` (4), because `znewn()`'s two branches are chosen by name length and this port lands in a different one for each. |
| **MB** | `CKBB` (treatment) | `--safe-server` → forced RENAME | The same leg with edit 21. Expect `RCVMB.001` and `MB.001`, both files present, both byte-exact. |
| **MC** | `CKBAK` (`-dV9K_COLLISION=XYFX_B`) | BACKUP, plain `-r` | The **other** caller of `znewn()`, and the action upstream documents as its default. The *old* file must move aside; the new one keeps the name. |
| **MD** | `CKPRE21` (control) | — | `mail` a file to the server. Expect the failure §16ax described from the far end: ACK, data phase starts, then `Can't open file`. |
| **ME** | `CKBB` (treatment) | — | The same, with edit 22. Expect refusal in the **A-packet ACK**, no data packets, no file created. |
| **MF** | `CKBB` | — | **Text mode, both directions.** Send `textlf.txt` in TEXT mode; get it back in BINARY mode; the returned bytes are then literally what is on the Victor's disk. |
| **MH** | `CKBB` | — | **ADDED AFTER MF FAILED ITS OWN PRECONDITION.** `set transfer mode manual` + `set file type text`, one send, and the answer read off the image rather than out of a round trip. |
| **MG** | `CKBB` | — | `REMOTE STATUS` — never asked in this port's life — plus `REMOTE HELP` and `REMOTE PWD` from a client whose `remcfm()` is not eight years old (§16ax). Also the only text-mode **send** the shipping build can make. |

MA/MB are adjacent and MC follows them; MD/ME are adjacent. MH was added
during the sitting, after MF's packet log showed it had not run in text mode
at all — the row above is what it was rewritten to ask. That ordering
is the only kind of comparison this harness supports (§16al).

### Predictions, written down first

**MA is the one with a real fork in it, and the leg exists to say which
way it goes.** `CKMAXNAM` is 16 here, so `znewn()`'s branch is chosen by
the length of the name:

- `MA.D` (4 chars) takes **branch A**: `k + MAXBUDIGITS + 3 < max` holds,
  and the name comes out `D:\MA.D.~1~` — two dots, which DOS cannot
  create. Predict an open failure and an error to the client.
- `RCVMA.DAT` (9 chars) takes **branch B**, the "backup name would be too
  long" path, and by inspection that path writes its `sprintf` **past the
  string's own terminator** (`xlen` = 13 against a 12-character name), so
  the name it returns is the ORIGINAL, unchanged. If that reading is
  right, the control **silently overwrites** — which is precisely the
  outcome `ckcpro.c:503` forces RENAME to prevent, and is worse than
  failing.

Both readings are static analysis and neither has ever been observed.
**Whichever way MA falls, it is the first measurement of this behaviour.**

- **MB**: both names land beside their originals. `pktstat.py` on the log,
  `md5` on all four files off the image.
- **MC**: `RCVMC.001` holds fixture 1 and `RCVMC.DAT` holds fixture 2 —
  the reverse of MB, because BACKUP moves the *old* file and RENAME
  redirects the *new* one. Getting these two backwards is the easy
  mistake and is why both legs are here.
- **MD/ME**: the difference is *where in the exchange* the refusal happens,
  so read the packet log, not the error text. MD should show S, F, A, then
  **data packets** and then an E; ME should show S, F, A and an immediate
  refusal with **no data packet at all**.
- **MF**: the file off the image is 2,240 bytes and matches
  `textcrlf.expected` (`80e691ea…`). If it comes back 2,200 and matches
  `textlf.txt`, the receive side is not converting and text mode is
  broken in the direction that matters most.
- **MG**: no prediction for `REMOTE STATUS`; it has never run. For the
  wire format, an explicit one: because `feol` is 0, the port will send
  server-generated text with **bare LF** where a Unix build would send
  CRLF. That is visible in the packet log and is a property of the
  platform pair (`NLCHAR` undef + `_fmode` binary), not a defect in
  either edit.

### What would make this sitting invalid

- Any leg reporting `deb=1` (§16aw).
- Any leg whose `.OUT` is 0 bytes — ask what the leg's last command does
  to the channel it reports through (§16ax leg SA, §16av leg MF).
- A target name that already existed. `SET FILE COLLISION` is REPLACE in
  the shipping build and RENAME under `--safe-server`, so a stale target
  does not announce itself the way `BACKUP` used to.

---

## Results

### MA — the control, and BOTH predicted failures happened in the same leg

**`v9k: coll=0`.** `XYFX_R` is 0, so `--safe-server` did force RENAME for
the whole session and everything below is the forced-RENAME path, not the
port's REPLACE default. `rxlost=0 rxfull=0 rxpeak=309`, `deb=0`,
`nospc=0`, one timeout and one retransmission across four sends (ordinary
for 9600 under MAME).

| send | as-name | outcome on the wire | on disk afterwards |
|---|---|---|---|
| 1 | `rcvma.dat` | completed | — |
| 2 | `rcvma.dat` | **completed** | `RCVMA.DAT` = **fixture 2**, `598c0a90…` |
| 3 | `na.d` | completed | — |
| 4 | `na.d` | **`E` with empty text, before any data packet** | `MA.D` = **fixture 1**, `1fe47cb2…` |

**No `.001` and no `.~1~` exists on the volume.** Both readings written
down in advance are confirmed, and they are two different failures of one
function:

- **`RCVMA.DAT` — nine characters — took `znewn()`'s branch B and the
  server SILENTLY OVERWROTE the existing file.** Branch B's `sprintf`
  lands past the string's own terminator, so the name came back unchanged
  and RENAME renamed nothing. **This is the failure that matters**:
  `ckcpro.c:503` forces RENAME precisely so that a server with DELETE
  disabled cannot modify an existing file, and the file was modified.
  `--safe-server` was not safe.
- **`MA.D` — four characters — took branch A and failed cleanly**: the
  name became `D:\MA.D.~1~`, DOS would not create it, and the server sent
  an error packet before any data. The existing file survived. **The E
  packet's text is EMPTY**, which is §16ah's signature for "the call
  succeeded and the caller threw the answer away" seen from the far end.

**The severity is the finding.** The note this sitting inherited said
BACKUP and RENAME "cannot work on FAT", which reads as "they fail". One
of them fails; the other **quietly does the opposite of what it was asked
to do**, and no counter, log line or protocol message says so. Which of
the two you get is decided by the LENGTH OF THE TARGET NAME.

### MB — the treatment, and it does exactly what it was specified to do

All four sends `OK`, **no E packet anywhere in the log**, `coll=0` (still
forced RENAME), `rxlost=0 rxfull=0 rxpeak=306`, `deb=0`, `nospc=0`,
`wfile n=4`.

| file | md5 | which fixture | meaning |
|---|---|---|---|
| `RCVMB.DAT` | `1fe47cb2…` | 1 | **the original, untouched** |
| `RCVMB.001` | `598c0a90…` | 2 | the second file, renamed |
| `MB.D` | `1fe47cb2…` | 1 | **the original, untouched** |
| `MB.001` | `598c0a90…` | 2 | the second file, renamed |

Both of MA's failures are gone, including the silent one, and the
direction is right: RENAME redirects the **incoming** file and leaves the
existing one alone.

### MC — BACKUP, the other caller of `znewn()`, and it goes the other way

`v9k: coll=2` (`XYFX_B`), plain `-x` server so nothing forced anything.
Both sends OK, `rxlost=0 rxfull=0 deb=0`.

| file | md5 | which fixture | meaning |
|---|---|---|---|
| `RCVMC.001` | `1fe47cb2…` | 1 | **the OLD file, moved aside** |
| `RCVMC.DAT` | `598c0a90…` | 2 | the new file, keeping the name |

Exactly the reverse of MB, which is the point of running both: RENAME
redirects the **incoming** file, BACKUP moves the **existing** one. The
prediction table called that out in advance because getting the two
backwards is the easy mistake and both would otherwise look like "two
files, one renamed".

### MD and ME — the MAIL disposition, and the difference is where it stops

Both legs sent one 4,096-byte file with disposition `M` and a mail
address. The interesting line is the **A-packet ACK**, and the two arms
differ in exactly the way §16ax predicted from the far end.

| | MD (control) | ME (edit 22) |
|---|---|---|
| A packet ACK | `Y` with **empty data** — accepted | `Y` with data **`N`** — the refusal code |
| data packets | yes | **none at all** |
| how it ended | **`E Can't open file`** | clean `Z`, `B`, ordinary end of transfer |
| file created | no, but only because `openc()` failed | no, and it was never going to be |

The client is told `FAIL` in both arms, so a user watching only the exit
status sees no difference. What changes is that the refusal now happens
**before the transfer starts** and names the reason, instead of arriving
as an error about a file the client never named. `REMOTE HELP` already
said `MAIL  Disabled`; as of edit 22 that is true rather than decorative.

### MG — `REMOTE STATUS` runs, for the first time in this port's life

The command needed a client this project did not have: `<generic>Q` and
`sndstatus()` have been compiled in since the beginning and the bench
Mac's C-Kermit 9.0.302 has no `REMOTE STATUS` to send. **A C-Kermit
11.0.508 client built from this tree** (`make macosx`) sent one and the
Victor answered:

```
    SERVER: C-Kermit 11.0.508, 2026/08/09, Victor 9000 / Sirius 1
    OPEN SOURCE
    C-Kermit full version number: 11.0.508
    Hostname:
    Server hardware:  ( bits)
    Server operating system family:
    Current directory on server:
    Last file sent by server: (none)
    Last file received by server: (none)
    Filename length limit: 16
    Pathname length limit: 128
```

`16` and `128` are `CKMAXNAM` and `CKMAXPATH`, correct. **Four fields come
back empty and one of them is odd**: `Current directory on server` is
blank while `REMOTE PWD`, in the same leg, answers `D:`. So the two
commands do not read the directory the same way, and that is a new open
item — small, and only visible because a client that can ask finally
exists.

`REMOTE HELP` in the same leg is the whole capability table, and it is
consistent for the first time: `MAIL Disabled` beside `REMOTE PRINT
Disabled`, `REMOTE HOST Disabled` and `REMOTE WHO Disabled` (§16ax zeroed
that one), with SPACE enabled because edit 20 gave it an answer. And the
five commands §16ax lost to `remcfm()` typed normally.

### MF and MH — text mode, and the first attempt tested nothing

**MF was designed wrong and its own packet log says so.** Its A packet
carries the file-type attribute **`B8` — binary** — the same value leg MA's
binary fixture sent, and there is not one quoted CR (`#M`) anywhere in its
data packets. The host's `set file type text` had been overridden: this Mac
runs `transfer mode automatic`, which decides per file and decided binary.
**The leg's own precondition — that the transfer is in text mode — was never
checked before its result was read.** §16am's rule, from a third direction:
*before running an experiment that depends on a setting, measure that the
setting took.* For a Kermit transfer that check costs nothing, because the
**A packet carries the answer** and the packet log already records it.

MF's second flaw would have hidden the first even if the mode had taken.
It got the file back with `set file type binary` and compared — but **for a
GET the SENDER decides the mode**, so a text-out/text-back round trip is
lossless whatever either end does to line endings, and the comparison
cannot see through it. The observable that does not lie is **the file on
the image**, read with `vtg_image_util` and no protocol in the path.

**MH is the leg MF should have been**: `set transfer mode manual`, `set
file type text`, one send, and the answer read off the disk.

| | MF (binary, as it turned out) | MH (text, verified in the A packet) |
|---|---|---|
| file-type attribute | `B8` | **`A`** |
| quoted CR on the wire | **0** | **40** — one per line |
| on the Victor's disk | 2,200 bytes, LF only, `2be61470…` | **2,240 bytes, CR 40 / LF 40, `80e691ea…`** |
| verdict | bytes preserved exactly — correct for binary | **line endings converted to the DOS convention — correct for text** |

**So `#undef NLCHAR` + `_fmode = O_BINARY` is the right pair, and it is
measured now rather than argued.** §16h called them "only correct
together" and nothing had ever run a text-mode transfer to check. The
mechanism is worth stating because it is not the obvious one: with
`feol = 0` **the Victor converts nothing in either direction**. It gets a
correct DOS text file because CRLF is *both* the Kermit wire format and
the DOS file format, so the sender's conversion is the only one needed and
raw pass-through is exactly right. A receiver that "helpfully" converted
would break it.

**The one place that is not conformant, predicted in advance and
confirmed: server-generated text goes out with bare LF.** Leg MG's
`REMOTE STATUS`/`REMOTE HELP` stream carries **38 `#J` and zero `#M`**.
Those strings are built with `\n` in C, and the LF→CRLF conversion at
`ckcfns.c:2829` is gated on `feol`. It is invisible against a Unix client,
which maps a bare LF onto its own line terminator, and it would put bare
LFs into a DOS file on a DOS client. **This is a property of the platform
pair — OS/2 undefines `NLCHAR` too — and not of either edit.** Left alone:
nothing needs it, and fixing it means either an upstream change or a
port-level hook in the packet builder. Recorded so it is not rediscovered
as a port defect.

### A reading that MB corrected in MA — the ACK name is not evidence

The first pass at MA read the F-packet ACK as the decisive observable:
the server ACKs the file header with the name it has chosen, so an ACK
carrying the original name looks like proof that no rename happened.
**It is not.** `ckcpro.w:1546` sends `fspec`, and `rcvfil()` fills
`fspec` from `ofn1` — the incoming name — *before* the collision switch
runs. **MB proves it directly**: its ACKs carry `rcvmb.dat` and `nb.d`
while the files on disk are `RCVMB.001` and `MB.001`.

So what settles MA is the **disk**: `RCVMA.DAT` holding fixture 2 with no
`.001` beside it. The correction is worth keeping for two reasons — it is
a live instrument caveat for any future collision leg, and it is an
instance of the thing this project keeps relearning: **the treatment leg
corrected the control leg's reading.** A control run alone would have
produced the right conclusion for the wrong reason.

### A void leg, and the rule it produces

**The first attempt at MB was VOID and the cause was mine, not the
port's.** All four sends failed, the packet log was **0 bytes**, and the
host said `/tmp/v9000: No such file or directory`. I had started MB as
soon as leg MA's *host* output appeared — but the host `kermit` finishes
long before MAME does, and MAME holds the single-use `-bitb` socket for
the whole of `-seconds_to_run`. Two emulators were briefly connected to
one `socat` listener; the second took the `/tmp/v9000` symlink, died 104 s
in, and left the link pointing at a dead pty.

**The rule: a leg ends when MAME exits, not when the host does.** `socat`'s
own log is the instrument — one `PTY is` line per leg and one `exiting`
line per leg, and the gap between them is that leg's real duration. MA's
was 19:49:29 → 19:55:29, exactly the 360 s it was given.

This is the same species as §16ax leg SA and §16av leg MF: **ask what the
leg's own machinery is doing to the channel it reports through.** Here the
channel was the wire itself.

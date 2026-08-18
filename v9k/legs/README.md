# Leg artefacts — the Victor side of the bench and MAME sittings

The `v9k:` counters printed to stdout at exit, one file per leg, extracted
off the SASI image with `vtg_image_util`. **These are the third artefact of
the three each leg produces**; the other two — `s16a*<leg>.host` and
`s16a*<leg>.pkt` — are in the tree root and are covered by `.gitignore`.

They are here because the image is a 9.7 MB volume that has run out of space
once already (PORTING.md §16al, first attempt), and because a `.OUT` is the
only place `rxlost`/`rxfull`/`rxpeak`, the §1f flow counters and `elapsed=`
are recorded at all.

| prefix | sitting |
|---|---|
| `STEPF*.OUT`, `FE*.LOG` | §16aj, MAME at 9600 — the flow-control build validated, and the switch witness read back through `uname()` |
| `STEPD*.OUT` | §16ak, seven bench legs at 38400 |
| `STEPG*.OUT` | §16al, four bench legs — two of them 0 bytes, which is the full-disk failure and is kept as the evidence for it |
| `STEPR*.OUT` | §16aw, five MAME legs — `REMOTE DIRECTORY` and the `deb=` latch |
| `STEPU*.OUT` | §16ay, five MAME legs — the post-merge regression of upstream 11.0.508. UA/UE receive, UB send by name, UC the server sweep, UD the parser build (no wire, so `rxpeak = 0` is the expected reading there) |
| `FD*.OUT` | §16az, six MAME legs at 9600 on **FreeDOS for Victor** — the first runs of this port on that DOS. FDB is the `dos oem=fd ver=622 irq1=09` identity oracle (no wire, so `rxpeak = 0` is expected); FDC is the channel-A receive the kernel's own serial trace corrupted; FDE and FDF are the clean channel-B receive and send; FDG is the console leg that failed to engage the display. `FDBOOT-chanA-trace.txt` is not a leg — it is 150 s of channel A with **nothing of ours running**, and it is the evidence that `entry.asm:280` writes an `H` to the 7201 on every INT 21h call |
| `STEPS*.OUT` | §16ax, six MAME legs — the server capability sweep. `STEPSA.OUT` is 0 bytes and is kept for the same reason `STEPG*` are: leg SA's terminating `REMOTE EXIT` failed in the **host's** parser, so the server never exited and MAME was killed under it |

**The received files are not here and that is deliberate.** Every one was
md5-identical to `TRANS.DAT`, `d94d2beda069ef0ef340977e7fd6995d`, so twelve
copies of one 32,768-byte fixture would be twelve copies of a file already in
the tree. The four zero-length ones from §16al's first attempt are not kept
either; the 0-byte `STEPG*.OUT` files record the same failure and cost
nothing.

`STEPFD.OUT` and the four `FE*.LOG` are the no-serial-line diagnostics: `-d
-h` runs that report what an XI initializer decided, through `uname()`,
without opening the line (§16i's oracle).

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

**The received files are not here and that is deliberate.** Every one was
md5-identical to `TRANS.DAT`, `d94d2beda069ef0ef340977e7fd6995d`, so twelve
copies of one 32,768-byte fixture would be twelve copies of a file already in
the tree. The four zero-length ones from §16al's first attempt are not kept
either; the 0-byte `STEPG*.OUT` files record the same failure and cost
nothing.

`STEPFD.OUT` and the four `FE*.LOG` are the no-serial-line diagnostics: `-d
-h` runs that report what an XI initializer decided, through `uname()`,
without opening the line (§16i's oracle).

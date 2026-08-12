# KN and KP were run twice, and the second run overwrote the first

HW_TEST_16aq §0 item 5 says a re-run gets a new leg letter, because re-using
one destroys the previous leg's artefacts.  KN and KP were re-run under the
same names on 11 August 2026 after the long cable turned up, so this file
records what the FIRST run was and what survived it.

## Run 1 — the RELIABLE cable (not a noise leg)

The long cable could not be found, so KN and KP ran on the reliable one.
They are therefore **two more clean-cable legs, one per arm**, and that is
how PORTING.md §16aq uses them: folded into the non-line-cost comparison and
nowhere else.  They are NOT evidence about a bad line.

| leg | arm | host clock | wire | rxpeak | bulk n | shape |
|---|---|---:|---:|---:|---:|---|
| KN | B, bulk on | 27.248 s | 40,621 | 2,285 | 199 | 1 timeout, 2 resends |
| KP | A, --nobulk | 31.137 s | 37,557 | 3,035 | 0 | clean |

## Run 2 — the LONG cable, and it induced no noise at all

Both legs came back at 37,557 wire bytes in 18 packets with zero crunched
packets, zero timeouts, zero resends and `rxlost = 0` — the clean shape, on
both arms.  **The stimulus did not fire**, so Part 3's question is still
open; these are two more clean legs and that is all.  Host statistics are
`s16aqKN_2.host` (25.659 s) and `s16aqKP.host` (31.146 s).

Victor-side counters survive in full as `STEPKN-cleancable.OUT` and
`STEPKP-cleancable.OUT`.

**What survived, exactly.**  Run 2 wrote KN's statistics to
`s16aqKN_2.host`, so BOTH of KN's host clocks exist.  Run 1's copies are
kept as `s16aqKN-cleancable.host` and `STEPKN-cleancable.OUT`.

Genuinely lost to run 2: **`s16aqKN.pkt`** (run 1's packet log, overwritten
11:43) and **`s16aqKP.pkt` + `s16aqKP.host`** (run 1's pair, overwritten
11:46).  Run 1's KP host clock, 31.137 s with 0 timeouts and 0
retransmissions, survives only in this file and in PORTING.md §16aq.  Its
Victor-side counters survive in full as `STEPKP-cleancable.OUT`.

**Two hazards, and the second one caught a reader out.**

`s16aqKN.host` (run 1, 08:55) sits next to `s16aqKN.pkt` (run 2, 11:43) with
matching names and a three-hour gap.  Read as a pair they describe a leg that
never happened.  **When a re-run has happened under an old name, check the
timestamps of every artefact in the set before reading any of them
together.**

And the naming that AVOIDED a loss caused a different error: `s16aqKN_2.host`
does not match the glob `s16aqKN.*`, because that pattern needs a literal dot
after `KN`.  A first pass over this sitting concluded run 2's host statistics
had never been captured, on the strength of a glob rather than a listing.
**`ls s16aqKN*` and `ls s16aqKN.*` are different questions; when the answer
is "the file is missing", ask the broader one before saying so.**

## Run 2 — the LONG cable

The actual Part 3 noise legs.  See PORTING.md §16aq.

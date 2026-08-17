# Bench run sheet — put the analyzer on RTS and CTS

**Two captures, no file transfer, no Kermit protocol. Half an hour.**

Written 10 August 2026, after PORTING.md §16am retracted §16al leg GB.

---

## Why the analyzer and not another leg

Three bench legs tried to answer "does the far end stop when the Victor
drops RTS" and none could, because **the far end was never able to stop.**
`kermit -C "show features"` on the bench Mac lists "Hardware flow control" —
that is `CK_RTSCTS`, which only decides whether `SET FLOW RTS/CTS` is a
legal command — and does **not** list `POSIX_CRTSCTS`, the only arm of
`ckutio.c`'s `tthflow()` a macOS build could take. Without it that function
is `int x = 0; return(x);`, the same empty function §16aj found in this
port's own build. `set flow rts/cts` configured nothing.

**The analyzer is better than any software instrument here, and by more than
convenience.** `v9k/tools/ctswatch.py` reads the modem lines at the *end of
a USB cable*, through an FTDI and a kernel driver — it answers "pin AND
cable AND adapter" as one lumped question. **A probe on the Victor's own
pins separates them**, which is exactly what three candidates need:

1. the WR5 write does not reach the pin — **this port's problem**;
2. the pin moves but the cable does not carry it — **a pinout question**;
3. both fine and only the host's Kermit is deaf — **already established**.

§11a0 has the precedent and the board map: it probed **LS153 15F pin 7** and
**MC1489 14D pin 3** to settle the baud clock, so TTL-side probing on this
board is a known quantity.

> **Probe the TTL side, not the connector.** The Victor drives RS-232
> through MC1488s at ±12 V, which is outside a Saleae logic input's range
> and at the edge of its analog range. The signals you want are the
> **µPD7201 channel A `/RTS` output** (which is the 1488's input) and the
> **MC1489 output that carries CTS back to the 7201**. Establishing those
> two pin numbers is the one piece of work this sheet cannot do for you —
> §11a0's LS153/MC1489 notes are the model, and the 1489 at 14D is already
> identified.

---

## Capture 1 — does the Victor's RTS pin move?

**Probe `/RTS` and `/DTR` together.** That is the whole trick: both are bits
of the **same WR5 byte** written by the same instruction pair, DTR is bit 7
and RTS is bit 1 (`msxv90.asm`'s `DTR_RTS_OFF EQU 7DH`, and `0EAh AND 7Dh =
68h`). So DTR is a free control:

- both move → the write reaches the chip and the RTS bit is right;
- **DTR moves and RTS does not** → the write reaches the chip and something
  about the RTS bit specifically is wrong. That is the one outcome that
  makes this the port's bug, and it would be a surprise;
- neither moves → the write is not reaching the chip at all.

**Stimulus, and it needs no new Victor code.** `CKICP.EXE` is on the image
and `HANGUP` goes through `tcsetattr(B0)`, which `ckvictor.c` implements as
`cr5 &= 0x7d` — held ~3 s, then put back.

```
CKICP                                   (at A>, wait ~85 s for it to load)
set line /dev/seriala                   (at the C-Kermit> prompt)
set speed 38400
hangup
hangup
hangup
exit
```

Three of them, because one transition is an event and three is a pattern.
`SET LINE` should report **local** and `SET SPEED 38400` should read back
(§16ab); if either does not, the `HANGUP` is not going where you think.

**Then the real thing, if capture 1 passes.** The transfer leg puts eleven
assert/release pairs on the pin instead of three, at transfer speed rather
than at 3-second intervals — which is a much better picture of what the
mechanism actually does:

```
STEPGB                                  (at A>, CKFCMID --rtscts, marks 1024/896)
```
```sh
kermit -C "take s16alGB.ksc, exit" > s16amGB.host
```

Everything for that leg is already staged and its `.BAT` clears its own
target. `held`/`rel` in `STEPGB.OUT` should be 11 again, and **the capture
should show 11 falling edges on RTS**. If the counter says 11 and the pin
shows 0, that is candidate 1 and it is decisive.

> **RESULT — capture 1: PASS.** RTS negative before any driver, positive
> when the OEM driver loads, a momentary drop on every chip reprogram
> (`SET LINE`, `SET SPEED`), and **175 µs on each `HANGUP`**.
>
> **The 175 µs is a second finding.** It should be `HUPTIME` = 500 ms.
> `msleep()` compiles upstream's `while (m > 0) m--;` fallback on this
> build, which `-os` may delete — so `tthang()` cannot hang up a modem and
> `tcsendbreak()` does not send a break. PORTING.md §16an, §1 item 16.
>
> **RESULT — transfer capture: PASS, and it is the result.** §16al leg GB
> shows **eight pauses with RTS low, 785 ms to ~1 s, most ~950 ms**, against
> a counter that said `held = 11`. §1f drops RTS at the 1,024 mark and
> raises it at 896, and the pin moves every time.
>
> **And the far end does not stop:** data kept arriving for many hundreds of
> milliseconds after each drop. That is §16am's `POSIX_CRTSCTS` finding seen
> on the wire — nothing was told to watch the pin.
>
> The ~950 ms hold is longer than the 62 ms predicted, and the prediction
> assumed the sender stops. It does not, so occupancy stays high and the
> release waits for the foreground to finish the packet. **The pause length
> measures the foreground, not the water marks.**

---

## Capture 2 — is the pair wired inbound?

This one is worth doing even though §16v read `cts = 1`, because **that
reading is not proof the pair is wired.** An MC1489 input left floating does
not necessarily present as deasserted — its internal bias can put the output
in the active state — so `cts = 1` is equally consistent with "the host's
RTS arrives" and with "nothing is connected to that pin". §16ak leg DS then
transferred happily with the CTS gate armed, which only requires CTS to
*read* asserted, not to be connected to anything.

**Probe the MC1489 output that feeds the 7201's CTS.** Stimulus from the
Mac, which needs no Kermit and no flow control:

```sh
python3 v9k/tools/ctswatch.py /dev/tty.usbserial-XXXXXXXX --toggle-rts 3
```

It drops and raises the host's RTS three times, 3 s apart, via
`TIOCMBIC`/`TIOCMBIS`, prints a timestamped line per edge, and restores RTS
on the way out. Nothing else may hold the port.

- **CTS at the 7201 follows** → the pair is wired inbound, §16v's reading
  was real, and leg DS's CTS gate was gating on something.
- **CTS does not move** → §16v's `cts = 1` was a floating input reading
  active, and **that is a retraction**: the input half of RTS/CTS has never
  been demonstrated either.

> **RESULT — capture 2: NOT RUN, and the tool is why.** Four runs were made
> in watch mode without `--toggle-rts`, so nothing drove the host's RTS. The
> tool reported `dtr=1 rts=1` under a column headed "outputs (this end)",
> which reads as *this program is asserting these* when it means *the driver
> reports these*. **Fixed** — an explicit `MODE: WATCHING ONLY -- this run
> drives nothing` banner, the column relabelled `this end (read back)`, and
> `--toggle-rts` now polls the inputs while it holds each level and reads
> back what it drove.
>
> **One observation from those runs is probably evidence anyway.** "When I
> launch python CTS asserts" — **opening the port makes macOS assert DTR and
> RTS by itself**, and the Victor sees the host's RTS as its CTS. If the
> probe was on the Victor's CTS, that is the inbound pair working. One
> `--toggle-rts 3` run confirms it now that the mode reports itself.
>
> **What the watcher runs did show:** `cts` lags `dsr`/`dcd` by 25 ms on
> power-down (`64.574 cts=1 dsr=0 dcd=0` then `64.599 cts=0`), so `cts` is a
> separate far-end signal and not tied to whatever drives the other two.
> That is the indication that the cable carries RTS→CTS — **strongly
> indicated, not proven.** The two-probe capture below closes it.

---

## Still open after this sitting

**One capture closes the cable question:** a second probe on the CTS
conductor **at the Mac end**, with the first still on the Victor's RTS,
during a `STEPGB` run. Both ends of one wire, one trace, and the 25 ms
inference above becomes a measurement.

## What each combination means

| capture 1 (our RTS) | capture 2 (their RTS) | reading |
|---|---|---|
| moves | follows | **the port and the cable are both fine.** The only thing broken is the host's C-Kermit, and "Fixing the host" below is the whole remaining job |
| moves | still | outbound wired, inbound not — and §16v's `cts = 1` is a floating input. Retract the input-half claim |
| still, DTR moves | either | **the port's bug**, and a narrow one: the WR5 write lands but the RTS bit does not do what `msxv90.asm` says it does |
| neither moves | either | the WR5 write is not reaching the chip on this path at all — check that `HANGUP` really reached `tcsetattr(B0)` before blaming the hardware |
| moves | follows, but the transfer capture shows 0 edges | `held = 11` is counting asserts that never happen — a code path issue in §1f, not a wiring one |

---

## Fixing the host, once the pins are known good

Two ways, in increasing order of effort. **Neither is on the critical path**
— `V9K_FLOW` is `FLO_NONE` and nothing needs flow control at a window of one.

1. **`stty -f /dev/tty.usbserial-XXXXXXXX crtscts -hupcl`, then start
   `kermit` immediately.** This *should* survive into a transfer:
   `TESTING234` clears `c_iflag` bits only and never touches `c_cflag`, an
   empty `tthflow()` cannot clear `CRTSCTS` either, and `ttraw` is seeded
   from the `ttold` that `ttopen()` reads. **Untested**, and the risk is
   that closing the port when `stty` exits resets termios, which `-hupcl` is
   there to prevent. If it works, §16al legs GA/GB re-run unchanged and the
   `rxpeak` cap test finally means something.
2. **Build a host C-Kermit from this tree with `POSIX_CRTSCTS`.** The tree
   is C-Kermit 11.0 and `make macosx` is a normal target. The honest fix,
   and what any protocol-level flow-control test wants — option 1 leaves the
   host's Kermit still believing it did the configuring.

**XON/XOFF has no `stty` shortcut.** The host's `IXON|IXOFF` are exactly the
`c_iflag` bits `TESTING234` clears, four lines before the `tcsetattr()` that
would apply them. A host built from this tree would need that line changed
too — which is the upstream defect §16aj filed, seen from the other end.

---

## The rule this sitting exists to pay for

**Before running an experiment that depends on the far end behaving a
particular way, measure that the far end can.** Three bench legs and a
fourth about to be scheduled went to finding that out afterwards, and the
check was one command against a binary nobody had to build.

**And the corollary this sheet is:** when the question is about a wire,
measure the wire. Every instrument in this project up to now has been a
counter inside one of the two programs, and both programs can be right about
what they did while nothing happens between them.

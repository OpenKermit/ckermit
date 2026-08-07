/*
  vburst.c -- does the burst detector in ckvictor.c's ISR actually separate
  the two defects PORTING.md SS16p could not?

  Build and run on the HOST, not the target:

      cc -o .probe/vburst .probe/vburst.c && .probe/vburst

  The reason this exists.  The loss path in v9k_ser_isr() only runs when the
  uPD7201 overruns, and SS16p established that it overruns at 38400 and at no
  lower rate.  MAME cannot drive this machine above about 9600 (SS16n), so
  there is no run in the emulator harness that reaches the code at all -- the
  9600 validation run exercises everything around it and nothing in it.  That
  leaves the arithmetic untested until the next bench session, which is
  exactly the sort of thing that arrives at the drive broken.

  So the counter update is transcribed here, byte for byte from the ISR, and
  replayed against synthetic loss patterns whose answers are known.  This
  proves the arithmetic, not the hardware: it says nothing about whether the
  chip's overrun bit behaves as assumed, only that IF the losses have a given
  shape THEN these counters report that shape.

  The cases that matter are the two SS16p is trying to tell apart:

      203 losses in 4 bursts     -> evt 4,   max about 51
      203 losses spread evenly   -> evt 203, max 1

  If those two came back the same, the instrument would be worthless.
*/

#include <stdio.h>
#include <string.h>

#define V9K_LOSTGAP 16

/* --- transcribed from v9k_ser_isr(), with the port I/O taken out ------- */

static unsigned int  v9k_rxlost, v9k_lostevt, v9k_lostrun, v9k_lostmax;
static unsigned long v9k_rxbytes, v9k_lostat, v9k_lostend;
static unsigned char v9k_losttag, v9k_wtag;

static void
reset(void)
{
    v9k_rxlost = v9k_lostevt = v9k_lostrun = v9k_lostmax = 0;
    v9k_rxbytes = v9k_lostat = v9k_lostend = 0L;
    v9k_losttag = 0; v9k_wtag = 0;
}

/* One entry to the handler that found the overrun bit set. */
static void
loss(void)
{
    v9k_rxlost++;
    if (!v9k_lostevt) {
        v9k_lostevt = 1;
        v9k_lostrun = 1;
        v9k_losttag = v9k_wtag;
        v9k_lostat  = v9k_rxbytes;
    } else if (v9k_rxbytes - v9k_lostend > (unsigned long)V9K_LOSTGAP) {
        v9k_lostevt++;
        v9k_lostrun = 1;
    } else
      v9k_lostrun++;
    if (v9k_lostrun > v9k_lostmax)
      v9k_lostmax = v9k_lostrun;
    v9k_lostend = v9k_rxbytes;
    v9k_rxbytes++;                      /* the BELL occupies a position */
}

/* One entry that stored a good byte. */
static void
good(void)
{
    v9k_rxbytes++;
}

/* --- the cases --------------------------------------------------------- */

static int fails = 0;

static void
check(const char * what, unsigned int evt, unsigned int max,
      unsigned int wevt, unsigned int wmax)
{
    int ok = (evt == wevt && max == wmax);

    printf("%-38s evt=%-4u max=%-4u  %s", what, evt, max,
           ok ? "ok\n" : "FAIL");
    if (!ok) {
        printf(" (wanted evt=%u max=%u)\n", wevt, wmax);
        fails++;
    }
}

int
main(void)
{
    int i, j;

    /*
      SS16p's run 3, on the hold-off reading: 42,757 bytes received, 203
      losses arriving as 4 bursts of ~51 consecutive misses.  This is the
      answer that says "something holds the machine off four times".
    */
    reset();
    for (i = 0; i < 4; i++) {
        for (j = 0; j < 51; j++)        /* 51, 51, 51, 50 = 203 */
          if (i * 51 + j < 203) loss();
        for (j = 0; j < 10000; j++) good();
    }
    check("203 losses, 4 bursts", v9k_lostevt, v9k_lostmax, 4, 51);

    /*
      The same 203 losses, spread one at a time through the same transfer.
      This is the answer that says "the handler is too slow per byte", and
      it has to come back different or the instrument decides nothing.
    */
    reset();
    for (i = 0; i < 203; i++) {
        loss();
        for (j = 0; j < 210; j++) good();
    }
    check("203 losses, spread singly", v9k_lostevt, v9k_lostmax, 203, 1);

    /* A burst broken by a few good bytes drained mid-hold-off is still one
       burst -- that is the whole reason the gap is measured in the stream
       rather than in consecutive handler entries. */
    reset();
    for (i = 0; i < 10; i++) { loss(); good(); good(); good(); }
    check("burst with 3 good bytes between", v9k_lostevt, v9k_lostmax, 1, 10);

    /* And the boundary either side of V9K_LOSTGAP. */
    reset();
    loss(); for (j = 0; j < V9K_LOSTGAP - 1; j++) good(); loss();
    check("gap of exactly LOSTGAP: one burst", v9k_lostevt, v9k_lostmax, 1, 2);

    reset();
    loss(); for (j = 0; j < V9K_LOSTGAP; j++) good(); loss();
    check("gap of LOSTGAP+1: two bursts", v9k_lostevt, v9k_lostmax, 2, 1);

    /* The first loss at offset 0, where lostend is still 0 and the
       subtraction would not mean anything -- the !lostevt arm. */
    reset();
    loss(); loss();
    check("first loss at offset 0", v9k_lostevt, v9k_lostmax, 1, 2);

    /* A clean transfer prints zeros, which has to be visible next to one
       that does not. */
    reset();
    for (j = 0; j < 32768; j++) good();
    check("no loss at all", v9k_lostevt, v9k_lostmax, 0, 0);

    /* lostat/lostend bracket the losses in the stream. */
    reset();
    for (j = 0; j < 1000; j++) good();
    loss();
    for (j = 0; j < 20000; j++) good();
    loss();
    printf("%-38s at=%lu end=%lu  %s", "lostat/lostend bracket",
           v9k_lostat, v9k_lostend,
           (v9k_lostat == 1000L && v9k_lostend == 21001L) ? "ok\n" : "FAIL\n");
    if (!(v9k_lostat == 1000L && v9k_lostend == 21001L)) fails++;

    printf("\n%s\n", fails ? "FAILURES" : "all cases pass");
    return(fails ? 1 : 0);
}

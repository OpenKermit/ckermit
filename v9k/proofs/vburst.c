/*
  vburst.c -- does the burst detector in ckvictor.c's ISR actually separate
  the two defects PORTING.md SS16p could not?

  Build and run on the HOST, not the target:

      cc -o v9k/proofs/vburst v9k/proofs/vburst.c && v9k/proofs/vburst

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

  SS16s ADDED THE PER-BURST TABLE and it is replayed here too.  SS16r ran the
  instrument above at the bench and got evt=5 max=179, which killed the
  per-byte hypothesis and left one question: how many BYTES does a burst
  cover?  The table answers it with a first and last offset per burst, and
  the case that matters now is the one that separates

      179 back-to-back overruns     -> sp about 356, one per handler entry
      179 spread over a long packet -> sp about 1,780, a marginal deficit

  Compare sp against 2n, not n: an overrun interrupt advances rxbytes twice,
  once for the substituted BELL and once for the byte it then reads.

  which is the same shape of question one level down, and the same reason
  for testing it here: no run in the MAME harness can reach this code.
*/

#include <stdio.h>
#include <string.h>

#define V9K_LOSTGAP   16
#define V9K_LOSTBURST 8

/* --- transcribed from v9k_ser_isr(), with the port I/O taken out ------- */

static unsigned int  v9k_rxlost, v9k_lostevt, v9k_lostrun, v9k_lostmax;
static unsigned long v9k_rxbytes, v9k_lostat, v9k_lostend;
static unsigned char v9k_losttag, v9k_wtag;
static unsigned int  v9k_wtagfd, v9k_lostfd;

static unsigned long v9k_bat[V9K_LOSTBURST], v9k_bend[V9K_LOSTBURST];
static unsigned int  v9k_bn[V9K_LOSTBURST],  v9k_bfd[V9K_LOSTBURST];
static unsigned char v9k_btag[V9K_LOSTBURST], v9k_bendtag[V9K_LOSTBURST];

static void
reset(void)
{
    v9k_rxlost = v9k_lostevt = v9k_lostrun = v9k_lostmax = 0;
    v9k_rxbytes = v9k_lostat = v9k_lostend = 0L;
    v9k_losttag = 0; v9k_wtag = 0; v9k_wtagfd = 0; v9k_lostfd = 0;
    memset(v9k_bat,0,sizeof(v9k_bat));
    memset(v9k_bend,0,sizeof(v9k_bend));
    memset(v9k_bn,0,sizeof(v9k_bn));
    memset(v9k_bfd,0,sizeof(v9k_bfd));
    memset(v9k_btag,0,sizeof(v9k_btag));
    memset(v9k_bendtag,0,sizeof(v9k_bendtag));
}

/* One entry to the handler that found the overrun bit set. */
static void
loss(void)
{
    unsigned int bi;

    v9k_rxlost++;
    if (!v9k_lostevt
        || v9k_rxbytes - v9k_lostend > (unsigned long)V9K_LOSTGAP) {
        if (!v9k_lostevt) {
            v9k_losttag = v9k_wtag;
            v9k_lostfd  = v9k_wtagfd;
            v9k_lostat  = v9k_rxbytes;
        }
        v9k_lostevt++;
        v9k_lostrun = 1;
        bi = v9k_lostevt - 1;
        if (bi < V9K_LOSTBURST) {
            v9k_bat[bi]  = v9k_rxbytes;
            v9k_btag[bi] = v9k_wtag;
            v9k_bfd[bi]  = v9k_wtagfd;
        }
    } else
      v9k_lostrun++;
    if (v9k_lostrun > v9k_lostmax)
      v9k_lostmax = v9k_lostrun;
    v9k_lostend = v9k_rxbytes;

    bi = v9k_lostevt - 1;
    if (bi < V9K_LOSTBURST) {
        v9k_bend[bi]    = v9k_rxbytes;
        v9k_bn[bi]      = v9k_lostrun;
        v9k_bendtag[bi] = v9k_wtag;
    }
    /*
      Two stream positions per overrun interrupt, which is the ISR's own
      arithmetic and is what sp has to be read against: the substituted
      BELL takes one and the byte the handler then reads takes the next.
      Back-to-back overruns are therefore 2 apart, not 1.
    */
    v9k_rxbytes += 2;
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

/* One row of the SS16s table: how many losses, and how many bytes they
   covered.  sp is what the whole revision exists to produce. */
static void
span(const char * what, unsigned int row, unsigned int wn, unsigned long wsp)
{
    unsigned long sp = v9k_bend[row] - v9k_bat[row];
    int ok = (v9k_bn[row] == wn && sp == wsp);

    printf("%-38s n=%-4u sp=%-5lu %s", what, v9k_bn[row], sp,
           ok ? "ok\n" : "FAIL");
    if (!ok) {
        printf(" (wanted n=%u sp=%lu)\n", wn, wsp);
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
    loss(); for (j = 0; j < V9K_LOSTGAP - 2; j++) good(); loss();
    check("gap of exactly LOSTGAP: one burst", v9k_lostevt, v9k_lostmax, 1, 2);

    reset();
    loss(); for (j = 0; j < V9K_LOSTGAP - 1; j++) good(); loss();
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
           (v9k_lostat == 1000L && v9k_lostend == 21002L) ? "ok\n" : "FAIL\n");
    if (!(v9k_lostat == 1000L && v9k_lostend == 21002L)) fails++;

    /* --- SS16s: the per-burst table -------------------------------------- */

    /*
      The reading the table exists for, both halves of it, against the same
      179 losses SS16r measured.  The dense case is one overrun per handler
      entry, which is the floor: 2 stream positions each, sp = 2(n-1).  The
      sparse case spreads the same count over a long packet.  lostevt,
      lostmax and lostat are identical in the two, which is exactly why
      SS16r could not choose -- sp is the only thing that differs.
    */
    reset();
    for (j = 0; j < 21000; j++) good();
    for (i = 0; i < 179; i++) loss();
    span("179 overruns, back to back", 0, 179, 356);

    reset();
    for (j = 0; j < 21000; j++) good();
    for (i = 0; i < 179; i++) { loss(); for (j = 0; j < 8; j++) good(); }
    span("179 overruns, over a long packet", 0, 179, 1780);

    /* Rows are independent: three bursts, three spans, in order. */
    reset();
    for (i = 0; i < 3; i++) {
        for (j = 0; j < 5; j++) { loss(); good(); }
        for (j = 0; j < 5000; j++) good();
    }
    span("burst 1 of 3", 0, 5, 12);
    span("burst 2 of 3", 1, 5, 12);
    span("burst 3 of 3", 2, 5, 12);

    /*
      More bursts than rows.  The table stops, lostevt does not -- which is
      what makes an overflow visible rather than silent, and is why the exit
      report prints both.
    */
    reset();
    for (i = 0; i < 12; i++) {
        loss(); loss();
        for (j = 0; j < 5000; j++) good();
    }
    check("12 bursts into 8 rows", v9k_lostevt, v9k_lostmax, 12, 2);
    span("last row kept", V9K_LOSTBURST - 1, 2, 2);
    /* And it is the EIGHTH burst in that row, not the twelfth: each
       iteration above covers 2 overruns (2 positions each) + 5000 good
       = 5004 stream positions. */
    printf("%-38s at=%lu  %s", "row 8 holds burst 8, not burst 12",
           v9k_bat[V9K_LOSTBURST - 1],
           (v9k_bat[V9K_LOSTBURST - 1] == 7L * 5004L) ? "ok\n" : "FAIL\n");
    if (v9k_bat[V9K_LOSTBURST - 1] != 7L * 5004L) fails++;

    /*
      The tags.  btag is taken at the first loss of a burst and bendtag at
      the last, so a foreground that moves during the burst shows up as a
      mismatched pair -- which is the whole reason there are two.
    */
    reset();
    v9k_wtag = 1;                       /* V9K_TAG_WRITE                */
    loss();
    v9k_wtag = 12;                      /* V9K_TAG_AFTER(TAG_DRAIN)     */
    good(); loss();
    printf("%-38s t=%u/%u  %s", "tag pair spans the burst",
           (unsigned)v9k_btag[0], (unsigned)v9k_bendtag[0],
           (v9k_btag[0] == 1 && v9k_bendtag[0] == 12) ? "ok\n" : "FAIL\n");
    if (!(v9k_btag[0] == 1 && v9k_bendtag[0] == 12)) fails++;

    printf("\n%s\n", fails ? "FAILURES" : "all cases pass");
    return(fails ? 1 : 0);
}

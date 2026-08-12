/*
  vttinl.c -- is the VICTOR9K bulk-read arm in ttinl() byte-for-byte
  equivalent to the loop it bypasses?

  Build and run on the HOST, not the target:

      cc -O2 -Wall -o v9k/proofs/vttinl.bin v9k/proofs/vttinl.c && \
          v9k/proofs/vttinl.bin

  or just "make -C v9k/proofs".

  ----------------------------------------------------------------------
  WHY THIS EXISTS

  PORTING.md upstream edit 18 puts a bulk arm at the bottom of ttinl()'s
  per-byte loop: once myread() has refilled mybuf[], the arm scans the
  buffered run for the packet terminator with memchr() and copies it into
  the caller's packet buffer with memcpy(), instead of walking it one byte
  at a time through the macro.  On an 8088 that matters more than it looks
  like it should -- "rep movsw" and "rep scasb" are the only way to move
  bytes without paying the four-clocks-per-instruction-byte fetch penalty
  that PORTING.md SS16w established is what actually bounds this machine.

  The objection to touching ttinl() at all is NEXT_SESSION.md item 5's, and
  it is a good one: this is the packet reader, and its failure modes are
  resync and truncation -- things a byte-exact transfer can PASS while
  being subtly wrong.  A transfer test cannot distinguish "the arm is
  correct" from "the arm is wrong in a way this fixture never provoked."

  So the argument for the edit has to be made here instead, the way
  vcrc16.c makes it for edit 17: both loops are transcribed, driven from
  one simulated line, and compared on every observable they share --
  return value, byte count, buffer contents, the NUL, AND the residual
  state of mybuf[], which is the one that bites.  ttinl() is called once
  per packet and leaves my_count/my_item pointing into the middle of a
  buffer that the NEXT call continues from.  An arm that returns the right
  packet and the wrong residual corrupts the packet after it, and nothing
  in a single-packet test can see that.

  ----------------------------------------------------------------------
  WHAT IS TRANSCRIBED, AND FROM WHERE

  Not from ckutio.c.  From the PREPROCESSOR OUTPUT of ckutio.c under this
  build's own flags:

      wcc -ml -0 -os -zq -zc -bt=dos -i=victorow -i=victor -i=$WATCOM/h \
          -fi=ckvictor.h -pl -fo=ckutio.i ckutio.c

  which is CLAUDE.md's standing rule -- a line of upstream source is not
  evidence that the build compiles it -- and here it changed the design.

  ckvictor.h:1100 defines NOPARSEN, with the comment "No network directory
  parse."  That is not what NOPARSEN means.  ckcdeb.h:3971 uses it to
  suppress PARSENSE, and the comment above it at ckcdeb.h:3966 spells out
  the consequence: "Automatic parity detection.  This actually implies a
  lot more now: length-driven packet reading [...]".

  So this build does NOT compile the length-driven ttinl() that ckutio.c
  reads like it has.  It compiles the four-argument form at
  ckutio.c:11007, whose entire per-byte body is:

      errno = 0;
      n = myread();
      if (n < 0) { ... }
      if (!xlocal && xfrcan && ((n & ttpmsk) == xfrchr)) { ... } else ccn = 0;
      dest[i++] = n & ttpmsk;
      if ((n & ttpmsk) == eol) { dest[i] = 0; ...; return(i); }

  There is no length field, no havelen, no extended-length header, no
  sequence-number peek, and no mid-packet SOP resync -- every one of those
  is inside #ifdef PARSENSE.  The packet ends at eol and nowhere else.

  That makes the bulk arm's correctness claim MUCH stronger than it would
  have been against the length-driven loop.  memchr(src, eol, n) is looking
  for exactly the byte the loop is looking for, on exactly the same stream.
  The two are not "equivalent on well-formed input" -- they are equivalent,
  full stop, wherever the gate below holds.  Corrupted input included: a
  lost or mangled terminator makes both of them run to max-1 or to the
  alarm, identically, because neither one is reading a length.

  ----------------------------------------------------------------------
  THE GATE

  The arm runs only when all of these hold, and falls back to the byte loop
  otherwise.  They are checked once per call, outside the loop:

    ttpmsk == 0377    Parity none.  With parity sensed ttpmsk is 0177 and
                      every byte needs masking on the way into dest[],
                      which memcpy() cannot do.  This port sets parity
                      none; ckutio.c computes ttpmsk = ttprty ? 0177 : 0377.

    !(!xlocal && xfrcan)
                      The cancellation scan counts consecutive xfrchr and
                      gives up after xfrnum of them.  It is dead in this
                      port (xlocal is 1: cmdlin() passes lcl=1, and
                      SS16aa's ttyname() fix keeps it that way), but if it
                      ever is not, the arm must not swallow the count.

  Both are runtime tests, which is deliberate.  v9k_bulkin is a variable
  and not an #ifdef so that --nobulk can turn the arm off IN THE SAME
  BINARY: SS16ap's control leg is the shape to copy, because a control
  built from a second binary is also a control for SS16w's code-size
  sensitivity, and this project has spent whole legs establishing that the
  rebuild was not what moved.

  ----------------------------------------------------------------------
  THE DIVERGENCE THIS FOUND

  Worth recording, because it is the entire reason to write the proof
  rather than reason about the arm and ship it.

  When the buffer fills to max-1 without a terminator, the byte loop falls
  out of the while and does "ttimoff(); return(n);" -- n being the last
  byte myread() handed back.  The bulk arm's n is the byte it read BEFORE
  the copy, so it returned a byte from up to 1023 positions too early.
  Both return "a positive number that rpack() will misread as a length",
  so both are wrong in the same direction and a transfer test sees a
  crunched packet either way -- which is exactly how this would have got
  through.  Case OVERFLOW below pins it; the arm sets n = dest[i-1].
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

typedef unsigned char CHAR;

#define MYBUFLEN 1024                   /* ckutio.c, non-BIGBUFOK, non-pdp11 */
#define EINTR_ 16                       /* what the .i shows for EINTR       */

/* ---------------------------------------------------------------------
   The simulated line.

   myfillbuf() on the target is "n = v9k_read(fd, mybuf, sizeof(mybuf))",
   which hands back whatever the interrupt handler's ring holds at that
   instant -- one byte when the foreground is keeping up, hundreds when it
   is not.  That variability is the thing the arm has to be right about, so
   it is a parameter here and the tests sweep it.
   --------------------------------------------------------------------- */

typedef struct {
    const CHAR * data;
    int          len;
    int          pos;
    int          chunk;                 /* bytes per myfillbuf() call     */
    int          errat;                 /* fail after this many delivered */
    int          errret;                /* what myfillbuf() then returns  */
} SRC;

/* ---------------------------------------------------------------------
   State shared by both implementations, reset between runs.
   Names and initial values from ckutio.c:8384-8390.
   --------------------------------------------------------------------- */

static CHAR mybuf[MYBUFLEN];
static int  my_count = 0;
static int  my_item  = -1;

static int  sim_errno   = 0;
static int  wasclosed   = 0;
static int  ttclos_n    = 0;
static int  ttimoff_n   = 0;

/* Globals ttinl() reads.  Defaults are this port's values. */
static int  ttprty   = 0;
static int  ttpmsk   = 0377;
static int  needpchk = 0;
static int  netconn  = 0;
static int  xlocal   = 1;
static int  xfrcan   = 0;
static int  xfrchr   = 3;
static int  xfrnum   = 3;
static int  streaming = 0;
static int  sndtyp   = 0;

static int  v9k_bulkin = 1;

/*
  How many byte runs the arm actually copied.  Not decoration: an
  equivalence test CANNOT see a --nobulk that is ignored, because an arm
  that is correct produces the reference's answer whether it was supposed
  to run or not.  The mutation that deleted the switch escaped every case
  in this file until this counter existed.  The target needs the same
  thing for the same reason -- ckvictor.c prints it as "v9k: bulk n=", so
  a control leg can prove which arm ran instead of assuming it.
*/
static long bulk_runs = 0;

static SRC * src;

static void ttimoff(void) { ttimoff_n++; }
static void ttclos(int x) { (void)x; ttclos_n++; }

static void
reset_state(SRC * s)
{
    memset(mybuf, 0, sizeof(mybuf));
    my_count = 0;
    my_item  = -1;
    sim_errno = 0;
    wasclosed = 0;
    ttclos_n  = 0;
    ttimoff_n = 0;
    src = s;
    s->pos = 0;
}

/* --- transcribed from ckutio.i: myfillbuf() ---------------------------- */

static int
sim_myfillbuf(void)
{
    int n;
    sim_errno = 0;
    if (src->errat >= 0 && src->pos >= src->errat) {
        if (src->errret < 0) sim_errno = 5;      /* EIO, not EINTR */
        return(src->errret);
    }
    n = src->len - src->pos;
    if (n > src->chunk) n = src->chunk;
    if (n > MYBUFLEN)   n = MYBUFLEN;
    if (n <= 0) return(0);                       /* EOF */
    memcpy(mybuf, src->data + src->pos, (size_t)n);
    src->pos += n;
    return(n);
}

/* --- transcribed from ckutio.i: mygetbuf() ----------------------------- */

static int
sim_mygetbuf(void)
{
    int x;
    sim_errno = 0;
    if (my_count <= 0)
      my_count = sim_myfillbuf();
    x = my_count;
    if (my_count <= 0) {
        my_count = 0;
        my_item  = -1;
        if (!netconn && xlocal && sim_errno) {
            if (sim_errno != EINTR_) {
                x = -3;
                ttclos(0);
            }
        }
        return((x < 0) ? -3 : -2);
    }
    --my_count;
    return((unsigned)(0xff & mybuf[my_item = 0]));
}

/* --- transcribed from ckutio.i: the myread() macro --------------------- */

#define sim_myread() \
  (--my_count < 0 ? sim_mygetbuf() : 255 & (int)mybuf[++my_item])

/* ---------------------------------------------------------------------
   REFERENCE -- ttinl(), exactly as this build compiles it.

   Transcribed from ckutio.i lines 14325-14486 with three substitutions
   and no other change:

     - the timo/alarm/setjmp wrapper is dropped.  It bounds how long the
       loop may run and cannot change what it produces; the arm does not
       touch it, and simulating longjmp here would test the harness.
     - printf()/debug() go away (debug() is already nothing under NODEBUG).
     - errno becomes sim_errno.

   The dead "else if (n == 0 && streaming ...)" arm inside "if (n < 0)" is
   kept as it is compiled.  It cannot fire.  It is transcribed rather than
   tidied because the point of a transcription is that it is one.
   --------------------------------------------------------------------- */

static int
ref_ttinl(CHAR * dest, int max, int timo, CHAR eol)
{
    register int i, n = -1;
    int ccn = 0;

    ttpmsk  = ttprty ? 0177 : 0377;
    (void)  (needpchk ? 0177 : ttpmsk);         /* sopmask: unused here */
    i = 0;

    *dest = '\0';

    while (i < max - 1) {
        sim_errno = 0;
        n = sim_myread();
        if (n < 0) {
            if (n == -3) {
                if (sim_errno == EINTR_) {
                    continue;
                } else {
                    wasclosed = 1;
                    ttimoff();
                    ttclos(0);
                    return(n);
                }
            } else if (n == -2 && netconn) {
                wasclosed = 1;
                ttimoff();
                ttclos(0);
                return(-3);
            }
            else if (n == 0 && streaming && sndtyp == 'D')
              return(0);
            break;
        }
        if (!xlocal && xfrcan && ((n & ttpmsk) == xfrchr)) {
            if (++ccn >= xfrnum) {
                if (timo) ttimoff();
                return(-2);
            }
        } else ccn = 0;

        dest[i++] = n & ttpmsk;

        if (((n & ttpmsk) == eol)) {
            dest[i] = '\0';
            if (timo) ttimoff();
            if (streaming && sndtyp == 'D')
              return(-1);
            return(i);
        }
    }
    ttimoff();
    return(n);
}

/* ---------------------------------------------------------------------
   TREATMENT -- the same function with edit 18's arm at the bottom of the
   loop.  Every line above the "#ifdef VICTOR9K" marker is identical to
   the reference; the arm is purely additive, which is what keeps the edit
   to one guarded block and leaves every error and timeout path upstream's.

   The arm drains only what myread() has ALREADY buffered.  It never reads
   the line itself, so refills, EOF, EINTR and the alarm all continue to
   happen in upstream's code exactly when they did before.
   --------------------------------------------------------------------- */

static int
bulk_ttinl(CHAR * dest, int max, int timo, CHAR eol)
{
    register int i, n = -1;
    int ccn = 0;
    int bulk_ok;

    ttpmsk  = ttprty ? 0177 : 0377;
    (void)  (needpchk ? 0177 : ttpmsk);
    i = 0;

    *dest = '\0';

    /* The gate.  Read once: neither term can change inside the loop. */
    bulk_ok = v9k_bulkin && (ttpmsk == 0377) && !(!xlocal && xfrcan);

    while (i < max - 1) {
        sim_errno = 0;
        n = sim_myread();
        if (n < 0) {
            if (n == -3) {
                if (sim_errno == EINTR_) {
                    continue;
                } else {
                    wasclosed = 1;
                    ttimoff();
                    ttclos(0);
                    return(n);
                }
            } else if (n == -2 && netconn) {
                wasclosed = 1;
                ttimoff();
                ttclos(0);
                return(-3);
            }
            else if (n == 0 && streaming && sndtyp == 'D')
              return(0);
            break;
        }
        if (!xlocal && xfrcan && ((n & ttpmsk) == xfrchr)) {
            if (++ccn >= xfrnum) {
                if (timo) ttimoff();
                return(-2);
            }
        } else ccn = 0;

        dest[i++] = n & ttpmsk;

        if (((n & ttpmsk) == eol)) {
            dest[i] = '\0';
            if (timo) ttimoff();
            if (streaming && sndtyp == 'D')
              return(-1);
            return(i);
        }

/* --- VICTOR9K: bulk drain of what myread() left behind ----------------- */

        if (bulk_ok) {
            while (my_count > 0 && i < max - 1) {
                CHAR * s = mybuf + my_item + 1;
                CHAR * p;
                int room = (max - 1) - i;
                int k    = (my_count < room) ? my_count : room;
                int len;

                p   = (CHAR *)memchr(s, eol, (size_t)k);
                len = p ? (int)(p - s) + 1 : k;

                bulk_runs++;
                memcpy(dest + i, s, (size_t)len);
                i       += len;
                my_item += len;
                my_count -= len;

                if (p) {
                    dest[i] = '\0';
                    if (timo) ttimoff();
                    if (streaming && sndtyp == 'D')
                      return(-1);
                    return(i);
                }
                /*
                  No terminator in this run.  The reference's n at this
                  point would be the last byte it stored, and n is what
                  falls out of the while as the return value when the
                  buffer fills -- so it has to be carried forward or the
                  overflow return is a byte from up to 1023 positions ago.
                  Exact because the gate has already established
                  ttpmsk == 0377.
                */
                n = dest[i - 1];
            }
        }

/* --- end VICTOR9K ------------------------------------------------------ */
    }
    ttimoff();
    return(n);
}

/* ---------------------------------------------------------------------
   The comparison.  Every observable the two share.
   --------------------------------------------------------------------- */

static int  failures = 0;
static long cases    = 0;
static long last_bulk_runs = 0;         /* from the most recent treatment */

typedef struct {
    int  rc;
    int  my_count;
    int  my_item;
    int  srcpos;
    int  wasclosed;
    int  ttclos_n;
    long bulk_runs;
    int  len;                           /* bytes to compare in dest[]   */
    CHAR dest[MYBUFLEN * 8 + 8];
} RESULT;

static void
run_one(int (*fn)(CHAR *, int, int, CHAR), SRC * s, int max, CHAR eol,
        RESULT * r)
{
    SRC copy = *s;
    memset(r, 0, sizeof(*r));
    reset_state(&copy);
    memset(r->dest, 0xAA, sizeof(r->dest));     /* poison, not zero */
    bulk_runs    = 0;
    r->rc        = (*fn)(r->dest, max, 1, eol);
    r->bulk_runs = bulk_runs;
    r->my_count  = my_count;
    r->my_item   = my_item;
    r->srcpos    = copy.pos;
    r->wasclosed = wasclosed;
    r->ttclos_n  = ttclos_n;
    r->len       = (r->rc > 0 && r->rc < max) ? r->rc + 1 : max;
}

static void
compare(const char * what, SRC * s, int max, CHAR eol)
{
    RESULT a, b;
    const char * why = NULL;

    cases++;
    run_one(ref_ttinl,  s, max, eol, &a);
    run_one(bulk_ttinl, s, max, eol, &b);

    if      (a.rc        != b.rc)        why = "return value";
    else if (a.my_count  != b.my_count)  why = "residual my_count";
    else if (a.my_item   != b.my_item)   why = "residual my_item";
    else if (a.srcpos    != b.srcpos)    why = "bytes consumed from the line";
    else if (a.wasclosed != b.wasclosed) why = "wasclosed";
    else if (a.ttclos_n  != b.ttclos_n)  why = "ttclos() calls";
    else if (memcmp(a.dest, b.dest, (size_t)a.len)) why = "packet contents";

    last_bulk_runs = b.bulk_runs;

    if (why) {
        if (failures < 12) {
            int j;
            printf("  FAIL [%s] %s\n", what, why);
            printf("        max=%d eol=%d chunk=%d srclen=%d errat=%d\n",
                   max, (int)eol, s->chunk, s->len, s->errat);
            printf("        ref : rc=%d my_count=%d my_item=%d pos=%d\n",
                   a.rc, a.my_count, a.my_item, a.srcpos);
            printf("        bulk: rc=%d my_count=%d my_item=%d pos=%d\n",
                   b.rc, b.my_count, b.my_item, b.srcpos);
            if (!strcmp(why, "packet contents")) {
                for (j = 0; j < a.len; j++)
                  if (a.dest[j] != b.dest[j]) {
                      printf("        first difference at %d: %02x vs %02x\n",
                             j, a.dest[j], b.dest[j]);
                      break;
                  }
            }
        }
        failures++;
    }
}

/* ---------------------------------------------------------------------
   Fixtures
   --------------------------------------------------------------------- */

static CHAR buf[MYBUFLEN * 8];

/*
  A packet body of "everything except the terminator", so that any byte the
  arm could mistake for eol is present at some offset in some case.  Under
  PX_CAU the peer prefixes SOH, CR, the eol and XON/XOFF (ckcmai.c:2718-2731)
  so those cannot legitimately arrive raw -- but the arm must not DEPEND on
  that, because a corrupted line does not honour prefixing.  So they are
  planted here on purpose.
*/
static int
fill_body(CHAR * p, int n, CHAR eol, int seed)
{
    int j, v = seed;
    for (j = 0; j < n; j++) {
        v = (v * 37 + 11) & 0xff;
        if ((CHAR)v == eol) v ^= 0x40;
        if ((CHAR)v == eol) v ^= 0x01;
        p[j] = (CHAR)v;
    }
    return(n);
}

static const int chunks[] = { 1, 2, 3, 5, 7, 13, 64, 127, 255, 512, 1024 };
#define NCHUNK ((int)(sizeof(chunks)/sizeof(chunks[0])))

int
main(void)
{
    SRC s;
    int ci, plen, j;
    CHAR eol;
    int eols[] = { 13, 10, 3, 0, 255 };
    int ne = (int)(sizeof(eols)/sizeof(eols[0]));
    int ei;

    printf("vttinl -- ttinl() bulk-read arm (upstream edit 18)\n");
    printf("  reference transcribed from ckutio.i (NOPARSEN => no PARSENSE)\n\n");

    /* ---- 1. Terminator at every offset, every refill granularity ----- */
    printf("  [1] eol at every offset x every refill size\n");
    for (ci = 0; ci < NCHUNK; ci++) {
        for (plen = 1; plen <= 600; plen++) {
            eol = 13;
            fill_body(buf, plen - 1, eol, plen + ci);
            buf[plen - 1] = eol;
            fill_body(buf + plen, 200, eol, plen);   /* next packet's start */
            s.data = buf; s.len = plen + 200; s.pos = 0;
            s.chunk = chunks[ci]; s.errat = -1; s.errret = 0;
            compare("offset sweep", &s, MYBUFLEN, eol);
        }
    }

    /* ---- 2. Several eol values, including 0 and 255 ------------------ */
    printf("  [2] terminator values 13, 10, 3, 0, 255\n");
    for (ei = 0; ei < ne; ei++) {
        eol = (CHAR)eols[ei];
        for (ci = 0; ci < NCHUNK; ci++) {
            for (plen = 1; plen <= 300; plen++) {
                fill_body(buf, plen - 1, eol, plen * 3 + ei);
                buf[plen - 1] = eol;
                fill_body(buf + plen, 100, eol, ei);
                s.data = buf; s.len = plen + 100; s.pos = 0;
                s.chunk = chunks[ci]; s.errat = -1; s.errret = 0;
                compare("eol values", &s, MYBUFLEN, eol);
            }
        }
    }

    /* ---- 3. OVERFLOW: no terminator before max-1 --------------------- */
    /*
      The case that found the n divergence.  max is swept so the buffer
      fills on a refill boundary, one before it, and one after it.
    */
    printf("  [3] overflow -- buffer fills before any terminator\n");
    eol = 13;
    fill_body(buf, sizeof(buf), eol, 7);            /* no eol anywhere */
    for (ci = 0; ci < NCHUNK; ci++) {
        for (j = 2; j <= 2200; j++) {
            s.data = buf; s.len = (int)sizeof(buf); s.pos = 0;
            s.chunk = chunks[ci]; s.errat = -1; s.errret = 0;
            compare("overflow", &s, j, eol);
        }
    }

    /* ---- 4. max exactly at, just before, just after the terminator --- */
    printf("  [4] max landing on either side of the terminator\n");
    eol = 13;
    for (ci = 0; ci < NCHUNK; ci++) {
        for (plen = 2; plen <= 400; plen++) {
            int d;
            fill_body(buf, plen - 1, eol, plen);
            buf[plen - 1] = eol;
            fill_body(buf + plen, 64, eol, 1);
            for (d = -2; d <= 2; d++) {
                int m = plen + 1 + d;
                if (m < 2) continue;
                s.data = buf; s.len = plen + 64; s.pos = 0;
                s.chunk = chunks[ci]; s.errat = -1; s.errret = 0;
                compare("max boundary", &s, m, eol);
            }
        }
    }

    /* ---- 5. EOF and hard error at every offset ----------------------- */
    printf("  [5] EOF (-2) and read error (-3) mid-packet\n");
    eol = 13;
    for (ci = 0; ci < NCHUNK; ci++) {
        int r;
        for (r = 0; r < 2; r++) {
            for (plen = 1; plen <= 400; plen += 1) {
                fill_body(buf, 700, eol, plen);
                buf[600] = eol;                     /* terminator past the fault */
                s.data = buf; s.len = 700; s.pos = 0;
                s.chunk = chunks[ci];
                s.errat = plen;                     /* fail after this many */
                s.errret = r ? -1 : 0;              /* error vs EOF */
                compare("fault injection", &s, MYBUFLEN, eol);
            }
        }
    }

    /* ---- 6. Back-to-back packets out of one buffer -------------------- */
    /*
      The residual-state case, and the reason my_count/my_item are compared
      at all.  One myfillbuf() of 1024 can hold several whole packets; the
      arm must leave the buffer positioned so the NEXT ttinl() reads the
      next packet and not the middle of this one.
    */
    printf("  [6] several packets per refill -- residual buffer state\n");
    eol = 13;
    for (ci = 0; ci < NCHUNK; ci++) {
        for (plen = 1; plen <= 200; plen++) {
            int off = 0, k;
            for (k = 0; k < 6 && off + plen < (int)sizeof(buf); k++) {
                fill_body(buf + off, plen - 1, eol, plen + k);
                buf[off + plen - 1] = eol;
                off += plen;
            }
            s.data = buf; s.len = off; s.pos = 0;
            s.chunk = chunks[ci]; s.errat = -1; s.errret = 0;
            compare("multi-packet", &s, MYBUFLEN, eol);
        }
    }

    /* ---- 7. The gate: every configuration that must disable the arm --- */
    /*
      Not a performance question.  If the gate is wrong the arm runs where
      its assumptions do not hold, so each of these is driven through the
      same comparison with the arm ON: the treatment must still equal the
      reference because the gate should have refused.
    */
    printf("  [7] the gate -- parity sensed, and the cancellation scan\n");
    eol = 13;
    for (ci = 0; ci < NCHUNK; ci++) {
        for (plen = 1; plen <= 300; plen++) {
            fill_body(buf, plen - 1, eol, plen);
            buf[plen - 1] = eol;
            fill_body(buf + plen, 64, eol, 2);
            s.data = buf; s.len = plen + 64; s.pos = 0;
            s.chunk = chunks[ci]; s.errat = -1; s.errret = 0;

            ttprty = 1;                             /* parity sensed */
            compare("gate: parity", &s, MYBUFLEN, eol);
            ttprty = 0;
        }
    }

    /*
      The cancellation scan needs xfrnum CONSECUTIVE xfrchr to fire, and a
      pseudo-random body does not contain three 0x03 in a row -- the first
      version of this case set the flags, ran, and proved nothing.  A
      mutation that deleted the xfrcan half of the gate passed it.  So the
      runs are planted, at every offset, at every length either side of the
      threshold.
    */
    printf("  [7b] the gate -- planted runs of the cancellation character\n");
    xlocal = 0; xfrcan = 1; xfrchr = 3; xfrnum = 3;
    eol = 13;
    for (ci = 0; ci < NCHUNK; ci++) {
        int runlen, at;
        for (runlen = 1; runlen <= 5; runlen++) {
            for (at = 0; at < 120; at++) {
                plen = 160;
                fill_body(buf, plen - 1, eol, at + runlen);
                for (j = 0; j < plen - 1; j++)       /* keep the run unique */
                  if (buf[j] == (CHAR)xfrchr) buf[j] ^= 0x20;
                for (j = 0; j < runlen && at + j < plen - 1; j++)
                  buf[at + j] = (CHAR)xfrchr;
                buf[plen - 1] = eol;
                fill_body(buf + plen, 64, eol, at);
                s.data = buf; s.len = plen + 64; s.pos = 0;
                s.chunk = chunks[ci]; s.errat = -1; s.errret = 0;
                compare("gate: xfrcan", &s, MYBUFLEN, eol);
            }
        }
    }
    xlocal = 1; xfrcan = 0;

    /* ---- 8. Arm switched off at runtime ------------------------------ */
    /*
      --nobulk has to give the reference back exactly, because that is what
      makes it a control leg: SS16ap's point is that a control from the same
      binary leaves SS16w's code-size sensitivity nothing to act on.
    */
    printf("  [8] --nobulk gives the reference back byte for byte\n");
    {
        long ran_on = 0, ran_off = 0;
    eol = 13;
    for (ci = 0; ci < NCHUNK; ci++) {
        for (plen = 1; plen <= 300; plen++) {
            fill_body(buf, plen - 1, eol, plen);
            buf[plen - 1] = eol;
            s.data = buf; s.len = plen; s.pos = 0;
            s.chunk = chunks[ci]; s.errat = -1; s.errret = 0;

            v9k_bulkin = 1;
            compare("nobulk: on", &s, MYBUFLEN, eol);
            ran_on += last_bulk_runs;

            v9k_bulkin = 0;
            compare("nobulk: off", &s, MYBUFLEN, eol);
            ran_off += last_bulk_runs;
        }
    }
    v9k_bulkin = 1;
    /*
      The equivalence comparison above CANNOT fail if --nobulk is ignored,
      because an arm that is correct returns the reference's answer whether
      or not it was meant to run.  So the switch is checked behaviourally
      instead: the arm must do work when it is on and none at all when it
      is off.  A mutation deleting v9k_bulkin from the gate escaped every
      other case in this file.
    */
    if (ran_on == 0) {
        printf("  FAIL [8] the arm never ran with v9k_bulkin = 1\n");
        failures++;
    }
    if (ran_off != 0) {
        printf("  FAIL [8] --nobulk ignored: the arm copied %ld runs\n",
               ran_off);
        failures++;
    }
    }

    /* ---- 9. Streaming return path ------------------------------------ */
    printf("  [9] streaming && sndtyp == 'D' return path\n");
    streaming = 1; sndtyp = 'D';
    eol = 13;
    for (ci = 0; ci < NCHUNK; ci++) {
        for (plen = 1; plen <= 300; plen++) {
            fill_body(buf, plen - 1, eol, plen);
            buf[plen - 1] = eol;
            s.data = buf; s.len = plen; s.pos = 0;
            s.chunk = chunks[ci]; s.errat = -1; s.errret = 0;
            compare("streaming", &s, MYBUFLEN, eol);
        }
    }
    streaming = 0; sndtyp = 0;

    printf("\n  %ld cases, %d failures\n", cases, failures);
    if (failures) {
        printf("  FAILED -- the arm is not equivalent.  Do not ship edit 18.\n");
        return(1);
    }
    printf("  PASS -- bulk arm is byte-for-byte the compiled byte loop.\n");
    return(0);
}

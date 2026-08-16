/*
  vwindow.c -- the correctness argument for ckvictor.c's --window=N switch.

  PORTING.md SS1 item 12.  --window=N is how a sliding-window leg and its
  control become ONE binary (SS16aq's lesson), so the switch is load-bearing
  for the measurement and not just for the feature: a parse that silently
  fails gives ask=0, the build falls back to DFWSIZ = 1, and the "window 2"
  leg is a window 1 leg wearing a label.  That is the same silent failure
  v9k/proofs/vttinl.c exists to catch for edit 18's bulk arm.

  This is a TRANSCRIPTION, in the sense v9k/proofs/README uses the word: the
  parse loop below is copied from ckvictor.c's v9k_set_window(), it is not
  the same code, and if that function changes this keeps passing and means
  less than it says.  Two things make that acceptable here -- the loop is
  twenty lines with no dependencies, and the target-side counter
  (v9k: window ask= use= neg= pool= ring=) observes the REAL binary on every leg,
  so this is the cheap check and the leg is the authoritative one.

  What it proves:

    1. The switch is recognised, case-insensitively, anywhere in the tail.
    2. The value parses, and only a well-formed value is accepted.
    3. Near misses are LEFT ALONE for argv, so cmdlin() reports them --
       under NOICP any unrecognised "--" argument is a fatal, which is
       SS16i's unknown-option control and the thing that must keep working.
    4. The token is blanked in place and NOTHING ELSE IS, so the rest of
       the command tail still reaches argv intact.  This is the half that
       cannot be seen from the exit counter: a switch that parsed but did
       not blank would fatal before the transfer, and a switch that blanked
       too much would silently eat -b or -l.
    5. BOTH clamps -- the buffer pool and, the one that actually binds,
       the RING.  A window of W lets the far end hold W unacknowledged
       packets, so in-flight is hard-bounded at W x (DRPSIZ + 8) and the
       ring must hold all of it.  Nothing upstream checks either, because
       this build never calls adjpkl() on the receive side.  Checking only
       the pool is what PORTING.md SS16as measured the cost of.

  Build and run:  make -C v9k/proofs        (or: cc -O2 -Wall -o vwindow.bin
                  vwindow.c && ./vwindow.bin)
*/

#include <stdio.h>
#include <string.h>

/* From ckvictor.h / ckcker.h, what the clamp is made of. */
#ifndef V9K_DRPSIZ
#define V9K_DRPSIZ 4000
#endif
#define V9K_RBSIZ      8192
#define V9K_MAXWS      32
#define V9K_RXBUFSIZ   4096
#define V9K_PKT_WIRE_XTRA 8

#define V9K_SW_WINDOW "--window="

static int failures = 0;

/*
  The packet length the clamp is computed against.  A variable rather than
  the #define because the WHOLE POINT of the ring ceiling is that it moves
  with DRPSIZ -- at 4000 it is 1 and at 1800 it is 2, and that difference is
  the experiment PORTING.md SS16as leaves open.  A proof that could only see
  one DRPSIZ would not be testing the mechanism.
*/
static int g_drpsiz = V9K_DRPSIZ;

/*
  Transcribed from ckvictor.c v9k_set_window().  __far is dropped -- it is a
  memory model, not behaviour -- and the ptab/wslotr stores at the end are
  replaced by returning the values, because those are the target's business
  and this is the parser's.
*/
static int
v9k_parse_window(char * cmdline, int * use)
{
    char * p;
    char * tok;
    char * q;
    char * lit;
    int n, cap;
    int ask = 0;

    *use = 0;
    p = cmdline;
    if (!p)
      return(0);

    while (*p) {
        while (*p == ' ' || *p == '\t')
          p++;
        if (!*p)
          break;
        tok = p;
        while (*p && *p != ' ' && *p != '\t')
          p++;

        q   = tok;
        lit = V9K_SW_WINDOW;
        while (q < p && *lit) {
            char a = *q;
            if (a >= 'A' && a <= 'Z') a += 'a' - 'A';
            if (a != *lit)
              break;
            q++; lit++;
        }
        if (*lit)
          continue;

        n = 0;
        while (q < p && *q >= '0' && *q <= '9')
          n = n * 10 + (*q++ - '0');
        if (q != p || n < 1)
          continue;

        ask = n;
        while (tok < p)
          *tok++ = ' ';
    }

    if (ask < 1)
      return(0);

    {   /* Two ceilings; the RING is the one SS16as was overrun by. */
        int pool = V9K_RBSIZ / (g_drpsiz + 6);
        int ring = V9K_RXBUFSIZ / (g_drpsiz + V9K_PKT_WIRE_XTRA);

        cap = (pool < ring) ? pool : ring;
    }
    if (cap < 1)
      cap = 1;
    if (cap > V9K_MAXWS)
      cap = V9K_MAXWS;

    n = ask;
    if (n > cap)
      n = cap;
    *use = n;
    return(ask);
}

/*
  The expected tail, built rather than hand-counted -- getting a run of
  spaces right by eye is exactly the kind of error that makes a test report
  a bug in the code under test.  blanked() states the property directly:
  every listed token becomes spaces of the SAME LENGTH and nothing else in
  the string moves.  It is independent of the parser, which is what keeps
  this from being a tautology.
*/
static const char *
blanked(const char * in, const char * const * toks, int ntoks)
{
    static char out[256];
    int i, j;

    strcpy(out,in);
    for (i = 0; i < ntoks; i++) {
        char * at = strstr(out,toks[i]);
        if (!at) {
            printf("  (test bug: [%s] not in [%s])\n", toks[i], in);
            failures++;
            continue;
        }
        for (j = 0; toks[i][j]; j++)
          at[j] = ' ';
    }
    return(out);
}

static void
check(const char * what, const char * in,
      int want_ask, int want_use, const char * want_tail)
{
    char buf[256];
    int ask, use;

    strcpy(buf,in);
    ask = v9k_parse_window(buf,&use);

    if (ask != want_ask || use != want_use || strcmp(buf,want_tail) != 0) {
        printf("  FAIL %-34s  in=[%s]\n", what, in);
        printf("       ask=%d want %d   use=%d want %d\n",
               ask, want_ask, use, want_use);
        printf("       tail=[%s]\n       want=[%s]\n", buf, want_tail);
        failures++;
    } else {
        printf("  ok   %-34s  ask=%d use=%d\n", what, ask, use);
    }
}

int
main(void)
{
    printf("vwindow: ckvictor.c --window=N   DRPSIZ %d: "
           "pool %d, ring %d -> cap %d\n",
           V9K_DRPSIZ,
           V9K_RBSIZ / (V9K_DRPSIZ + 6),
           V9K_RXBUFSIZ / (V9K_DRPSIZ + V9K_PKT_WIRE_XTRA),
           (V9K_RBSIZ / (V9K_DRPSIZ + 6) <
            V9K_RXBUFSIZ / (V9K_DRPSIZ + V9K_PKT_WIRE_XTRA))
             ? V9K_RBSIZ / (V9K_DRPSIZ + 6)
             : V9K_RXBUFSIZ / (V9K_DRPSIZ + V9K_PKT_WIRE_XTRA));

    /* 1/2: recognised, value parsed, token blanked, rest intact. */
    {
        static const char * w2[]  = { "--window=2" };
        static const char * w1[]  = { "--window=1" };
        static const char * wU[]  = { "--WINDOW=2" };
        static const char * w12[] = { "--window=1", "--window=2" };
        static const char * w8[]  = { "--window=8" };
        static const char * w999[]= { "--window=999" };
        const char * in;

        in = "--window=2 -l /dev/seriala -b 38400 -r";
        check("plain, with a real tail", in, 2, 1, blanked(in,w2,1));

        in = "--window=1 -r";
        check("window 1 (the control arm)", in, 1, 1, blanked(in,w1,1));

        in = "-r --window=2";
        check("not first in the tail", in, 2, 1, blanked(in,w2,1));

        in = "--WINDOW=2 -r";
        check("case folded", in, 2, 1, blanked(in,wU,1));

        in = "--window=1 --window=2";
        check("last one wins", in, 2, 1, blanked(in,w12,2));

        /*
          5: THE CLAMP.  At the shipping DRPSIZ = 4000 the ring ceiling is
          4096/4008 = ONE, so every one of these comes back use=1 -- which
          is the whole repair: SS16as ran use=2 here and pinned the ring.
        */
        in = "--window=8 -r";
        check("clamped by the RING, not the pool", in, 8, 1, blanked(in,w8,1));

        in = "--window=999 -r";
        check("clamped, absurd value", in, 999, 1, blanked(in,w999,1));

        /* 4: whitespace must not shift the blanking. */
        in = "-r\t--window=2   -b 38400";
        check("tabs and multiple spaces", in, 2, 1, blanked(in,w2,1));
    }

    /*
      3: near misses.  Every one of these must be LEFT IN PLACE, so that
      cmdlin() sees it and fatals -- SS16i's unknown-option control is the
      thing that distinguishes "ignored" from "accepted", and it only works
      if this parser declines to blank what it did not understand.
    */
    check("no switch at all",
          "-l /dev/seriala -r", 0, 0, "-l /dev/seriala -r");
    check("wrong name, shares a prefix",
          "--windows=2 -r", 0, 0, "--windows=2 -r");
    check("truncated name",
          "--wind=2 -r", 0, 0, "--wind=2 -r");
    check("no value",
          "--window= -r", 0, 0, "--window= -r");
    check("no equals sign",
          "--window 2 -r", 0, 0, "--window 2 -r");
    check("zero is not a window",
          "--window=0 -r", 0, 0, "--window=0 -r");
    check("trailing junk on the value",
          "--window=2x -r", 0, 0, "--window=2x -r");
    check("leading junk",
          "x--window=2 -r", 0, 0, "x--window=2 -r");
    check("empty tail",
          "", 0, 0, "");

    /*
      6: the ceiling as a function of DRPSIZ, which is the bit SS16as
      needed and did not have.  in-flight is hard-bounded at
      W x (DRPSIZ + 8) because a window of W lets the far end hold W
      unacknowledged packets, and the RING must hold all of it since
      nothing drains it while the foreground decodes.
    */
    printf("\n  -- ceiling vs DRPSIZ (ring %d, pool %d) --\n",
           V9K_RXBUFSIZ, V9K_RBSIZ);
    {
        static const struct { int drpsiz, want; const char * note; } t[] = {
            { 4000, 1, "SHIPPING -- no window fits, SS16as's defect" },
            { 2100, 1, "still 1: 2 x 2108 = 4216 > 4096" },
            { 2000, 2, "2 x 2008 = 4016, fits with 80 to spare" },
            { 1800, 2, "route A -- 2 x 1808 = 3616, 480 spare" },
            { 1300, 3, "3 x 1308 = 3924" },
            {   90, 32, "short packets: MAXWS is the binding limit" },
            { 8000, 1, "ring holds none; never returns 0" },
        };
        int i, use, save = g_drpsiz;

        for (i = 0; i < (int)(sizeof(t)/sizeof(t[0])); i++) {
            char buf[64];
            g_drpsiz = t[i].drpsiz;
            strcpy(buf,"--window=32 -r");
            v9k_parse_window(buf,&use);
            if (use != t[i].want) {
                printf("  FAIL DRPSIZ %5d -> cap %d, want %d\n",
                       t[i].drpsiz, use, t[i].want);
                failures++;
            } else {
                printf("  ok   DRPSIZ %5d -> cap %2d   %s\n",
                       t[i].drpsiz, use, t[i].note);
            }
        }
        g_drpsiz = save;
    }

    printf("vwindow: %s\n", failures ? "FAILED" : "all cases pass");
    return(failures ? 1 : 0);
}

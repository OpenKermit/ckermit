/*
  vznewn.c -- does upstream edit 21 make a name FAT can hold, and is it
  the RIGHT name?

  Build and run on the HOST, not the target:

      make -C v9k/proofs vznewn

  What is being proved.  ckufio.c's znewn() builds a unique name by
  appending ".~<n>~" to a name that already has an extension, so on this
  machine it produced "A:\RCVDA.DAT.~1~" -- two dots, which FAT cannot
  hold.  Both collision actions that call it (BACKUP and RENAME) were
  therefore dead here, and RENAME is forced on every --safe-server by
  ckcpro.c:503, so a safe server could receive a filename exactly once.
  Edit 21 hands the job to v9k_backupname() in ckvictor.c, which replaces
  the extension instead: "A:\RCVDA.001".

  Two properties, and they are different claims:

    1. LEGALITY.  Every name it returns is a FAT 8.3 name -- one dot in
       the filename part, one to eight characters before it, exactly
       three after.  A name that is unique and unusable is no better than
       what it replaced.

    2. UNIQUENESS, and specifically the LOWEST free number.  The function
       probes rather than expanding a wildcard, so this is where a
       fencepost would live.  Every case below checks that the name it
       returns does not exist AND that no lower-numbered name is free.

  Plus the failure contract: when it cannot make a name it must return 0
  AND LEAVE THE CALLER'S BUFFER ALONE, because znewn() then falls through
  to upstream's code and uses that buffer.  A half-rewritten buffer would
  be worse than the defect.

  THE FUNCTION UNDER TEST IS NOT TRANSCRIBED HERE.  v9k/proofs/README and
  NEXT_SESSION.md both carry the standing complaint that these proofs hold
  their own copies of the code they check, so they keep passing when the
  original changes and then mean less than they say.  This one extracts
  v9k_backupname() from ckvictor.c at build time into vznewn_gen.h -- see
  the Makefile -- so it cannot drift by construction.  What it does supply
  is access(), because the real one is INT 21h.
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define CK_ANSIC
#define CKMAXPATH 128

/* ------------------------------------------------------------------ */
/* The directory the function is probing, and the access() that sees it */
/* ------------------------------------------------------------------ */

#define MAXENT 1200
static char dir[MAXENT][CKMAXPATH+16];
static int ndir = 0;

static void
dirclear(void) { ndir = 0; }

static void
diradd(const char * name) {
    if (ndir >= MAXENT) { printf("FAIL: test directory full\n"); exit(1); }
    strcpy(dir[ndir++],name);
}

static int naccess = 0;                 /* Probe count, for the record */

static int
v9k_test_access(const char * path, int mode) {
    int i;
    (void)mode;
    naccess++;
    for (i = 0; i < ndir; i++)
      if (!strcmp(dir[i],path))
        return(0);                      /* Exists */
    return(-1);                         /* Does not */
}
#define access v9k_test_access

/* The extracted function.  Generated from ckvictor.c by the Makefile. */
#include "vznewn_gen.h"

#undef access

/* ------------------------------------------------------------------ */
/* Checking                                                            */
/* ------------------------------------------------------------------ */

static int failures = 0;
static int checks = 0;

static void
fail(const char * what, const char * in, const char * got, const char * want) {
    printf("FAIL: %s\n      input  %s\n      got    %s\n      wanted %s\n",
           what,in,got,want);
    failures++;
}

/*
  Is the filename part of this path a legal FAT 8.3 name?  One dot, one
  to eight characters before it, exactly three after, and no second dot
  anywhere in the name part.  The drive letter's colon is not part of the
  name and neither are the directories.
*/
static int
fat83(const char * path) {
    const char * p, * name = path, * dot = NULL;
    int base, ext, dots = 0;

    for (p = path; *p; p++)
      if (*p == '/' || *p == '\\' || *p == ':')
        name = p + 1;
    for (p = name; *p; p++)
      if (*p == '.') { dots++; dot = p; }
    if (dots != 1) return(0);
    base = (int)(dot - name);
    ext  = (int)strlen(dot + 1);
    return(base >= 1 && base <= 8 && ext == 3);
}

/*
  The whole contract, in one call: run the function and check everything
  that must be true of a success.  Returns the number it reported.
*/
static int
expect(const char * label, const char * in, int wantn, const char * wantname) {
    char buf[CKMAXPATH+16];
    char probe[CKMAXPATH+16];
    int n, i;

    checks++;
    strcpy(buf,in);
    n = v9k_backupname(buf,sizeof(buf));

    if (n != wantn) {
        char g[64], w[64];
        sprintf(g,"returned %d (name \"%s\")",n,buf);
        sprintf(w,"returned %d",wantn);
        fail(label,in,g,w);
        return(n);
    }
    if (n == 0) {                       /* Failure contract: buffer intact */
        if (strcmp(buf,in))
          fail(label,in,buf,"the buffer to be left alone");
        return(0);
    }
    if (wantname && strcmp(buf,wantname)) {
        fail(label,in,buf,wantname);
        return(n);
    }
    if (!fat83(buf)) {
        fail(label,in,buf,"a legal FAT 8.3 name");
        return(n);
    }
    if (v9k_test_access(buf,0) == 0) {
        fail(label,in,buf,"a name that does not already exist");
        return(n);
    }
    for (i = 1; i < n; i++) {           /* Lowest free number, not just A free one */
        strcpy(probe,buf);
        probe[strlen(probe)-3] = (char)('0' + (i / 100));
        probe[strlen(probe)-2] = (char)('0' + ((i / 10) % 10));
        probe[strlen(probe)-1] = (char)('0' + (i % 10));
        if (v9k_test_access(probe,0) != 0) {
            fail(label,in,buf,"the LOWEST free number");
            printf("      %s was free and was skipped\n",probe);
            return(n);
        }
    }
    return(n);
}

int
main(void) {
    char buf[CKMAXPATH+16];
    char name[CKMAXPATH+16];
    int i, n;

    printf("vznewn: upstream edit 21, v9k_backupname() extracted from ckvictor.c\n\n");

    /* 1. The case the defect is about: the name RENAME needs, twice. */
    dirclear();
    diradd("A:\\RCVDA.DAT");
    expect("first backup","A:\\RCVDA.DAT",1,"A:\\RCVDA.001");

    dirclear();
    diradd("A:\\RCVDA.DAT");
    diradd("A:\\RCVDA.001");
    expect("second backup","A:\\RCVDA.DAT",2,"A:\\RCVDA.002");

    /* 2. Numbering carries past the first digit and stays three wide. */
    dirclear();
    diradd("A:\\RCVDA.DAT");
    for (i = 1; i <= 9; i++) {
        sprintf(name,"A:\\RCVDA.%03d",i);
        diradd(name);
    }
    expect("tenth","A:\\RCVDA.DAT",10,"A:\\RCVDA.010");

    dirclear();
    diradd("A:\\RCVDA.DAT");
    for (i = 1; i <= 99; i++) {
        sprintf(name,"A:\\RCVDA.%03d",i);
        diradd(name);
    }
    expect("hundredth","A:\\RCVDA.DAT",100,"A:\\RCVDA.100");

    /* 3. A gap is filled, not skipped -- the probe must find the LOWEST. */
    dirclear();
    diradd("A:\\RCVDA.DAT");
    diradd("A:\\RCVDA.001");
    diradd("A:\\RCVDA.003");
    diradd("A:\\RCVDA.004");
    expect("gap at 2","A:\\RCVDA.DAT",2,"A:\\RCVDA.002");

    /* 4. Shapes of name.  All of these come out of a FAT directory, so
          all of them are names the port can actually be handed. */
    dirclear();
    expect("no extension","A:\\RCVDA",1,"A:\\RCVDA.001");
    dirclear();
    expect("subdirectory","A:\\SUB\\RCVDA.DAT",1,"A:\\SUB\\RCVDA.001");
    dirclear();
    expect("forward slashes","A:/SUB/RCVDA.DAT",1,"A:/SUB/RCVDA.001");
    dirclear();
    expect("no path at all","RCVDA.DAT",1,"RCVDA.001");
    dirclear();
    expect("drive, no directory","A:RCVDA.DAT",1,"A:RCVDA.001");
    dirclear();
    expect("one-character name","A:\\X.T",1,"A:\\X.001");
    dirclear();
    expect("eight-character name","A:\\ABCDEFGH.TXT",1,"A:\\ABCDEFGH.001");
    dirclear();
    expect("trailing dot","A:\\RCVDA.",1,"A:\\RCVDA.001");

    /* 5. Longer than eight is not a name FAT gave us, but it must still
          come back legal rather than come back long. */
    dirclear();
    expect("over-long base","A:\\LONGFILENAME.DAT",1,"A:\\LONGFILE.001");

    /* 6. The failure contract. */
    dirclear();
    expect("empty name","",0,NULL);
    dirclear();
    expect("ends in a separator","A:\\SUB\\",0,NULL);
    dirclear();
    expect("root itself","A:\\",0,NULL);

    dirclear();                         /* 999 taken -> 0, buffer intact */
    diradd("A:\\RCVDA.DAT");
    for (i = 1; i <= 999; i++) {
        sprintf(name,"A:\\RCVDA.%03d",i);
        diradd(name);
    }
    expect("all 999 taken","A:\\RCVDA.DAT",0,NULL);

    checks++;                           /* Buffer too small -> 0 */
    dirclear();
    strcpy(buf,"A:\\RCVDA.DAT");
    n = v9k_backupname(buf,(int)strlen(buf) + 4);
    if (n != 0 || strcmp(buf,"A:\\RCVDA.DAT")) {
        char g[64];
        sprintf(g,"returned %d (name \"%s\")",n,buf);
        fail("buffer too small","A:\\RCVDA.DAT",g,"returned 0, buffer intact");
    }

    /* 7. Sweep: every starting shape, every number 1..999, checked for
          legality and lowest-free.  This is the part that would catch a
          fencepost the hand-written cases above happen to miss. */
    {
        static const char * bases[] = {
            "A:\\A.B", "A:\\AB.CDE", "A:\\ABCDEFGH.IJK", "A:\\SUB\\N.O",
            "N.O", "A:\\NOEXT"
        };
        int b, sweep = 0;
        for (b = 0; b < (int)(sizeof(bases)/sizeof(bases[0])); b++) {
            for (n = 1; n <= 999; n++) {
                char want[CKMAXPATH+16];
                char cut[CKMAXPATH+16];
                char * dot;

                dirclear();
                diradd(bases[b]);
                /* Build the name we expect, by the test's own rules */
                strcpy(cut,bases[b]);
                dot = NULL;
                { char * q, * nm = cut;
                  for (q = cut; *q; q++)
                    if (*q=='/'||*q=='\\'||*q==':') nm = q+1;
                  for (q = nm; *q; q++) if (*q=='.') dot = q;
                  if (dot && dot > nm) *dot = '\0';
                  if ((int)strlen(nm) > 8) nm[8] = '\0';
                }
                for (i = 1; i < n; i++) {
                    sprintf(name,"%s.%03d",cut,i);
                    diradd(name);
                }
                sprintf(want,"%s.%03d",cut,n);
                expect("sweep",bases[b],n,want);
                sweep++;
            }
        }
        printf("sweep: %d cases over %d starting names\n",
               sweep,(int)(sizeof(bases)/sizeof(bases[0])));
    }

    printf("\n%d checks, %d access() probes, %d failures\n",
           checks,naccess,failures);
    if (failures) {
        printf("vznewn: FAILED\n");
        return(1);
    }
    printf("vznewn: all pass\n");
    return(0);
}

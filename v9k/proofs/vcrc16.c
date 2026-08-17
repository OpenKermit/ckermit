/*
  vcrc16.c -- is ckcfn2.c's VICTOR9K chk3() the same CRC as upstream's?

  Build and run on the HOST, not the target:

      cc -o v9k/proofs/vcrc16 v9k/proofs/vcrc16.c && v9k/proofs/vcrc16

  The reason this exists.  PORTING.md SS16af replaces chk3()'s arithmetic for
  VICTOR9K only: upstream computes a 16-bit CRC in long variables through two
  16-entry long tables, which on an 8088 built with -0 costs two software
  shift loops per byte and four word loads where two would do.  The guarded
  version does the same CRC in unsigned int through one 256-entry unsigned
  int table.

  A block check that is fast and wrong is worse than one that is slow, and
  the failure mode is silent -- both ends compute the same wrong value only
  if the change is symmetric, which it is not, because the far end is a
  stock C-Kermit.  So the two must agree on every input, not merely on the
  fixture that happens to be at hand.

  Two things are proved here and they are different claims:

    1. The table identity.  crctab16[b] == crcta[b >> 4] ^ crctb[b & 0x0F]
       for all 256 b.  This is the whole basis of the collapse from two
       lookups to one, and it is exhaustive rather than sampled.

    2. The loop identity.  Both functions return the same value over every
       length from 0 to 4100 -- past DRPSIZ, which is 4000 -- on data that
       includes every byte value, every byte value repeated, and the
       all-zero and all-0xFF edges that a checksum tends to get wrong.

  What this does NOT prove is anything about speed; that is a bench matter,
  and the figure to read is elapsed= against rxfull.  Nor does it prove the
  Watcom code generation is correct -- it proves the algorithm is, on a host
  where int is 32 bits, which is the one place the two versions could differ
  for a reason that would not show up here.  The masks are written so that
  they cannot: see the note on crc & 0xFFFF below.
*/

#include <stdio.h>
#include <string.h>

/* ------------------------------------------------------------------ */
/* Upstream, transcribed from ckcfn2.c:312 and ckcfn2.c:1628           */
/* ------------------------------------------------------------------ */

static long crcta[16] = { 0L, 010201L, 020402L, 030603L, 041004L,
  051205L, 061406L, 071607L, 0102010L, 0112211L, 0122412L, 0132613L, 0143014L,
  0153215L, 0163416L, 0173617L
};

static long crctb[16] = { 0L, 010611L, 021422L, 031233L, 043044L,
  053655L, 062466L, 072277L, 0106110L, 0116701L, 0127532L, 0137323L, 0145154L,
  0155745L, 0164576L, 0174367L
};

static unsigned int
chk3_upstream(unsigned char * pkt, int len) {
    register long c, crc;
    for (crc = 0; len-- > 0; pkt++) {
	c = crc ^ (long)(*pkt);
	crc = (crc >> 8) ^ (crcta[(c & 0xF0) >> 4] ^ crctb[c & 0x0F]);
    }
    return((unsigned int) (crc & 0xFFFF));
}

/* ------------------------------------------------------------------ */
/* The guarded version, transcribed from the same two places           */
/* ------------------------------------------------------------------ */

static unsigned int crctab16[256] = {
    0x0000, 0x1189, 0x2312, 0x329B, 0x4624, 0x57AD, 0x6536, 0x74BF,
    0x8C48, 0x9DC1, 0xAF5A, 0xBED3, 0xCA6C, 0xDBE5, 0xE97E, 0xF8F7,
    0x1081, 0x0108, 0x3393, 0x221A, 0x56A5, 0x472C, 0x75B7, 0x643E,
    0x9CC9, 0x8D40, 0xBFDB, 0xAE52, 0xDAED, 0xCB64, 0xF9FF, 0xE876,
    0x2102, 0x308B, 0x0210, 0x1399, 0x6726, 0x76AF, 0x4434, 0x55BD,
    0xAD4A, 0xBCC3, 0x8E58, 0x9FD1, 0xEB6E, 0xFAE7, 0xC87C, 0xD9F5,
    0x3183, 0x200A, 0x1291, 0x0318, 0x77A7, 0x662E, 0x54B5, 0x453C,
    0xBDCB, 0xAC42, 0x9ED9, 0x8F50, 0xFBEF, 0xEA66, 0xD8FD, 0xC974,
    0x4204, 0x538D, 0x6116, 0x709F, 0x0420, 0x15A9, 0x2732, 0x36BB,
    0xCE4C, 0xDFC5, 0xED5E, 0xFCD7, 0x8868, 0x99E1, 0xAB7A, 0xBAF3,
    0x5285, 0x430C, 0x7197, 0x601E, 0x14A1, 0x0528, 0x37B3, 0x263A,
    0xDECD, 0xCF44, 0xFDDF, 0xEC56, 0x98E9, 0x8960, 0xBBFB, 0xAA72,
    0x6306, 0x728F, 0x4014, 0x519D, 0x2522, 0x34AB, 0x0630, 0x17B9,
    0xEF4E, 0xFEC7, 0xCC5C, 0xDDD5, 0xA96A, 0xB8E3, 0x8A78, 0x9BF1,
    0x7387, 0x620E, 0x5095, 0x411C, 0x35A3, 0x242A, 0x16B1, 0x0738,
    0xFFCF, 0xEE46, 0xDCDD, 0xCD54, 0xB9EB, 0xA862, 0x9AF9, 0x8B70,
    0x8408, 0x9581, 0xA71A, 0xB693, 0xC22C, 0xD3A5, 0xE13E, 0xF0B7,
    0x0840, 0x19C9, 0x2B52, 0x3ADB, 0x4E64, 0x5FED, 0x6D76, 0x7CFF,
    0x9489, 0x8500, 0xB79B, 0xA612, 0xD2AD, 0xC324, 0xF1BF, 0xE036,
    0x18C1, 0x0948, 0x3BD3, 0x2A5A, 0x5EE5, 0x4F6C, 0x7DF7, 0x6C7E,
    0xA50A, 0xB483, 0x8618, 0x9791, 0xE32E, 0xF2A7, 0xC03C, 0xD1B5,
    0x2942, 0x38CB, 0x0A50, 0x1BD9, 0x6F66, 0x7EEF, 0x4C74, 0x5DFD,
    0xB58B, 0xA402, 0x9699, 0x8710, 0xF3AF, 0xE226, 0xD0BD, 0xC134,
    0x39C3, 0x284A, 0x1AD1, 0x0B58, 0x7FE7, 0x6E6E, 0x5CF5, 0x4D7C,
    0xC60C, 0xD785, 0xE51E, 0xF497, 0x8028, 0x91A1, 0xA33A, 0xB2B3,
    0x4A44, 0x5BCD, 0x6956, 0x78DF, 0x0C60, 0x1DE9, 0x2F72, 0x3EFB,
    0xD68D, 0xC704, 0xF59F, 0xE416, 0x90A9, 0x8120, 0xB3BB, 0xA232,
    0x5AC5, 0x4B4C, 0x79D7, 0x685E, 0x1CE1, 0x0D68, 0x3FF3, 0x2E7A,
    0xE70E, 0xF687, 0xC41C, 0xD595, 0xA12A, 0xB0A3, 0x8238, 0x93B1,
    0x6B46, 0x7ACF, 0x4854, 0x59DD, 0x2D62, 0x3CEB, 0x0E70, 0x1FF9,
    0xF78F, 0xE606, 0xD49D, 0xC514, 0xB1AB, 0xA022, 0x92B9, 0x8330,
    0x7BC7, 0x6A4E, 0x58D5, 0x495C, 0x3DE3, 0x2C6A, 0x1EF1, 0x0F78
};

/*
  The two masks are load-bearing on a host where int is wider than 16 bits
  and free on the target, which is the only reason this function is
  testable here at all.  On the Victor unsigned int IS 16 bits, so crc >> 8
  brings in zeros and crc & 0xFFFF is the identity; anywhere else, the high
  bits would accumulate garbage that the table index masks away but the
  return value would not.
*/
static unsigned int
chk3_victor(unsigned char * pkt, int len) {
    register unsigned int crc;
    register unsigned int c;

    crc = 0;
    while (len-- > 0) {
	c = (crc ^ (unsigned int)(*pkt++)) & 0xFF;
	crc = ((crc >> 8) & 0xFF) ^ crctab16[c];
    }
    return((unsigned int) (crc & 0xFFFF));
}

/* ------------------------------------------------------------------ */

#define MAXLEN 4100			/* Past DRPSIZ, which is 4000 */

static unsigned char buf[MAXLEN];

static int failures = 0;

static void
compare(char * what, int len) {
    unsigned int a, b;

    a = chk3_upstream(buf,len);
    b = chk3_victor(buf,len);
    if (a != b) {
	if (failures < 20)
	  printf("  FAIL %-22s len %5d  upstream %04X  victor %04X\n",
		 what, len, a, b);
	failures++;
    }
}

int
main() {
    int i, len;
    unsigned long seed;

    printf("vcrc16 -- chk3() equivalence, upstream vs VICTOR9K\n\n");

    /* 1.  The table identity, exhaustively. */

    printf("1. table identity, all 256 entries\n");
    for (i = 0; i < 256; i++) {
	unsigned int want = (unsigned int)
	  ((crcta[(i & 0xF0) >> 4] ^ crctb[i & 0x0F]) & 0xFFFF);
	if (crctab16[i] != want) {
	    printf("  FAIL crctab16[%3d] = %04X, want %04X\n",
		   i, crctab16[i], want);
	    failures++;
	}
    }
    printf("   %s\n\n", failures ? "FAILED" : "ok, all 256 agree");

    /* 2.  The loop identity, over every length and several fill patterns. */

    printf("2. loop identity, len 0..%d, five fill patterns\n", MAXLEN - 1);

    for (i = 0; i < MAXLEN; i++)	/* Every byte value, cycling */
      buf[i] = (unsigned char)(i & 0xFF);
    for (len = 0; len < MAXLEN; len++)
      compare("cycle 00..FF", len);

    memset(buf,0x00,sizeof(buf));	/* All zero */
    for (len = 0; len < MAXLEN; len++)
      compare("all 00", len);

    memset(buf,0xFF,sizeof(buf));	/* All ones */
    for (len = 0; len < MAXLEN; len++)
      compare("all FF", len);

    memset(buf,'A',sizeof(buf));	/* A run, as the fixture has */
    for (len = 0; len < MAXLEN; len++)
      compare("all 'A'", len);

    seed = 12345UL;			/* Reproducible pseudo-random */
    for (i = 0; i < MAXLEN; i++) {
	seed = seed * 1103515245UL + 12345UL;
	buf[i] = (unsigned char)((seed >> 16) & 0xFF);
    }
    for (len = 0; len < MAXLEN; len++)
      compare("pseudo-random", len);

    printf("   %s\n\n", failures ? "FAILED" : "ok, 20500 lengths agree");

    /* 3.  A witness, so a future reader can check a third implementation
       against this one without running anything.  Note that this is NOT
       the 906E that tables of CRC check values give for "123456789" with
       this polynomial: those assume init FFFF and a final XOR of FFFF, and
       Kermit's block check does neither.  Same polynomial, different
       parameterisation, and confusing the two is the obvious way to
       "correct" a working block check into a broken one. */

    memcpy(buf,"123456789",9);
    printf("3. witness: chk3(\"123456789\") = %04X upstream, %04X victor\n",
	   chk3_upstream(buf,9), chk3_victor(buf,9));
    printf("   (init 0, no final XOR -- not the 906E of CRC-16/X-25)\n\n");

    printf("%s\n", failures ? "SOME TESTS FAILED" : "all tests passed");
    return(failures ? 1 : 0);
}

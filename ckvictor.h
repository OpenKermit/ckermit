/*  C K V I C T O R . H  --  Build configuration for Victor 9000 / Sirius 1  */

/*
  Serial-only C-Kermit for the Victor 9000 (Sirius 1) under Victor MS-DOS,
  built by Open Watcom V2 (wcc/wlink) in the LARGE model -- far code and
  far data.  victorow.mak is the build.

  This header is force-included ahead of every source file:

      wcc -ml -fi=ckvictor.h ...

  Nothing else in the tree includes it, so it cannot affect any other
  platform.  It exists because the feature set is expressed as ~40 -D
  options and putting them on the command line makes the build unreadable.

  TARGET MODEL
    CPU            8088, real mode, 16-bit
    int            16 bits          long   32 bits
    code           far, multiple code segments, up to 1MB
    data           far.  String literals go to far code (-zc) and malloc()
                   is the far heap, so DGROUP holds .data, .bss and the
                   stack and nothing else.

  DGROUP is no longer the binding constraint it was -- 39,424 of 65,536
  after the link, including libc -- but it is still a 64K ceiling and every
  size choice below exists to keep occupancy down.  Do not raise them
  without re-measuring ("make -f victorow.mak sizes"); see PORTING.md SS9.

  A second toolchain, ia16-elf-gcc + newlib in the medium model, built this
  same port until 2026-08-05.  It is retired: one near 64K DGROUP could not
  hold the interactive command parser and left ~2K of heap for a transfer.
  PORTING.md SS9d and SS16e keep the measurements; git keeps the code.
*/

#ifndef CKVICTOR_H
#define CKVICTOR_H

/* ------------------------------------------------------------------ */
/* Platform identity                                                    */
/* ------------------------------------------------------------------ */
/*
  We present as UNIX + POSIX.  That is not a pretence: the Watcom DOS
  runtime supplies open/close/read/write/lseek/stat and dirent, this file
  and ckvictor.c supply the POSIX termios layer and the process model, and
  that is exactly the surface ckutio.c and ckufio.c use.  Claiming UNIX also
  makes ckcdeb.h define DYNAMIC, which is essential -- it turns the packet
  buffers into malloc'd pointers instead of >64K static arrays.
*/
#ifndef UNIX
#define UNIX
#endif
#ifndef POSIX
#define POSIX
#endif
#ifndef VICTOR9K
#define VICTOR9K
#endif

/* Open Watcom does not declare sig_t, so C-Kermit's own typedef is the one
   we want; CK_NO_SIG_T stays undefined. */

/* ------------------------------------------------------------------ */
/* Open Watcom: filling the gaps in its Unix surface                    */
/* ------------------------------------------------------------------ */
/*
  Most of what follows is header surgery.  ckvictor.h is force-included
  ahead of every module, so including a system header HERE and adjusting
  what it defined is the only place where the adjustment sticks: by the
  time ckufio.c gets to its own #include, the include guard has already
  fired and our edits are what it sees.  No upstream file is touched.
*/

/*
  There is no <sys/param.h>.  NO_PARAM_H is ckcdeb.h's own knob for saying
  so (ckcdeb.h ~6350), so this costs nothing but the define.
*/
#ifndef NO_PARAM_H
#define NO_PARAM_H
#endif /* NO_PARAM_H */

/*
  Signals MS-DOS does not have.  Watcom's <signal.h> stops at SIGIOVFL
  (12); these three are referenced by name in ckutio.c and ckusig.c.

  SIGHUP and SIGQUIT are only reached on paths this configuration disables
  (NOJC, NOCCTRAP) or that degrade safely, so their values are ours to
  choose and are kept above Watcom's highest; signal() rejects them with
  SIG_ERR and nothing ever raises them.

  SIGALRM is different, and this is the subtle one.  ckvictor.c SS0d fires
  the alarm by reading back the handler ckutio.c installed and calling it,
  which only works if signal() agreed to store it.  Watcom's signal()
  stores handlers for 1..12 and rejects everything else, so SIGALRM has to
  be a number inside that range or every protocol timeout is lost.  SIGUSR3
  is the one to take: DOS never generates it, C-Kermit never mentions it
  (it uses SIGUSR1 and SIGUSR2, and only in the exec() paths this port does
  not have), and it is unreachable for its own sake here.
*/
#include <signal.h>
#ifndef SIGHUP
#define SIGHUP  20                      /* Hangup                       */
#endif /* SIGHUP */
#ifndef SIGQUIT
#define SIGQUIT 21                      /* Quit                         */
#endif /* SIGQUIT */
#ifndef SIGALRM
#define SIGALRM SIGUSR3                 /* Alarm clock -- see above     */
#endif /* SIGALRM */

/*
  Watcom defines S_IFBLK, S_IFLNK and S_IFSOCK as 0 -- honestly, since FAT
  has no block devices, symlinks or sockets.  But ziperm() in ckufio.c
  builds an "ls -l" type character with

      switch (mode & S_IFMT) { ... case S_IFBLK: ... case S_IFLNK: ... }

  and three cases with the value 0 is a hard error (E1039), not a warning.
  The #ifdef guards upstream wraps S_IFLNK and S_IFSOCK in do not help,
  because both ARE defined -- just to zero.

  So: undefine the two that upstream tests for, and give S_IFBLK a value no
  st_mode can ever hold.  Nothing on this platform ever produces any of the
  three, so no behaviour changes; only the switch stops colliding.

  S_ISLNK()/S_ISSOCK() go with them.  They are written in terms of the
  macros being removed, and ckufio.c tests for the S_IS* spelling first
  (zgetfs(), isdir()) -- so leaving them behind would just move the error
  from "duplicate case" to "S_IFLNK has not been declared".  On a FAT
  filesystem the honest answer to "is this a symlink" is no, and with the
  macro gone that is the branch upstream takes.

  <fcntl.h> is pulled in alongside <sys/stat.h> because it defines the
  same three macros a second time; adjusting them before both guards have
  fired only makes the second header put them back.
*/
#include <sys/stat.h>
#include <fcntl.h>
#undef S_IFLNK
#undef S_IFSOCK
#undef S_ISLNK
#undef S_ISSOCK
#undef S_IFBLK
#define S_IFBLK 0x3000                  /* Unused S_IFMT value on DOS   */

/*
  nl_langinfo() and <langinfo.h>.  Watcom has neither.  This is ckcdeb.h's
  own knob for saying so (ckcdeb.h ~7000), and the function it removes is
  only reachable from the date parser's locale path.
*/
#ifndef NO_NL_LANGINFO
#define NO_NL_LANGINFO
#endif /* NO_NL_LANGINFO */

/*
  The Unix surface Watcom does not declare -- the process model, the one
  terminal, and gettimeofday() for the floating-point transfer timers.
  ckvictor.c defines all of it; these two headers are the declarations, and
  being force-included means ckvictor.c is checked against them too.  See
  victorow/ckowsys.h.
*/
#include <ckowsys.h>
#include <sys/time.h>

/*
  ckufio.c declares "extern long timezone;" (~line 214).  Watcom's <time.h>
  declares it as "extern long __near timezone", and in the large model a
  bare declaration means __far, so the two disagree (E1057).  ckufio.c
  never READS the variable in this configuration -- the SVORPOSIX branch of
  zstrdt() calls tzset() and nothing else -- so the cheapest correct fix is
  to point the name at a variable of our own, defined in ckvictor.c.  The
  library's timezone is left exactly as it is.
*/
#include <time.h>
#define timezone v9k_timezone
extern long v9k_timezone;

/*
  Watcom's mkdir() takes one argument; the Unix one takes two.  A
  function-like macro whose expansion names the same function is not
  re-expanded, so this rewrites the call and nothing else -- no wrapper,
  no rename, and zmkdir() keeps working.
*/
#include <direct.h>
#define mkdir(path,mode) mkdir(path)

/*
  The Watcom DOS runtime supplies execl/execvp, sleep(), creat(), utime(),
  umask(), opendir/readdir/closedir and a stat() that answers "." itself,
  so ckvictor.c does not write any of them out; see its section 1a.  The
  VICTOR_HAVE_<name> guards that used to be needed here are gone with the
  stubs they suppressed.
*/

/* ------------------------------------------------------------------ */
/* Size limits -- the 64K DGROUP budget                                 */
/* ------------------------------------------------------------------ */

/*
  scanfile() declares "unsigned char buf[SCANFILEBUF]" as an AUTOMATIC.
  The stock 49152 would blow the entire stack on the first call.
*/
#define SCANFILEBUF 2048

/*
  MS-DOS paths are short.  CKMAXPATH is multiplied by RQ_MAXTOK and by
  several other tables, so it is a strong lever on total data size.
*/
#define CKMAXPATH 128

/* rq_tok is RQ_MAXTOK*(CKMAXPATH+1) bytes: 16*129 = 2064 rather than 9280. */
#define RQ_MAXTOK 16

/*
  CKMAXNAM is the longest single filename SEGMENT (not path).  This is the
  most valuable size lever in the whole file, and it is a STACK lever, not
  a DGROUP one.

  Left to itself it does not come out at anything sane here.  ckcdeb.h sets
  CKMAXNAM from MAXNAMLEN, and where neither is defined it falls through to
  FILENAME_MAX, which a hosted libc puts in the hundreds or thousands.
  traverse() in ckufio.c then declares

      char nambuf[CKMAXNAM+4];

  as an AUTOMATIC, and traverse() is the recursive directory walk that holds
  one frame per directory level.  Measured (with gcc's -fstack-usage, on the
  retired build, but the array is the same array):

      CKMAXNAM 1024 (default)   traverse = 1066 bytes/level
      CKMAXNAM 16               traverse =   98 bytes/level

  A depth-8 walk therefore costs 784 bytes of stack instead of 8528.  The
  stack is inside DGROUP in every memory model, so this stays a real lever.
  Same class of hazard as SCANFILEBUF.

  16 is chosen against FAT 8.3: the longest legal name is 12 characters
  ("12345678.123"), so 16 leaves room and keeps the buffer even-sized.  This
  port does not do long filenames -- DOS FindFirst, which is what Watcom's
  readdir() is underneath, returns 8.3 and nothing else.
*/
#define CKMAXNAM 16

/*
  MAXNAMLEN is a feature test as much as a size here.  ckufio.c (~353) and
  ckutio.c (~212) both branch on whether it is defined -- the BSD-vs-System-V
  distinction they were written against -- and ckcdeb.h uses it as its source
  for CKMAXNAM when that is not set directly.

  12 is the honest value for FAT 8.3.  It does NOT size Watcom's struct
  dirent, which uses its own NAME_MAX (also 12 for DOS); this port no longer
  supplies opendir()/readdir(), so nothing here depends on that layout.
*/
#ifndef MAXNAMLEN
#define MAXNAMLEN 12
#endif

/*
  FIONREAD, and the ioctl() prototype that goes with it.  ckutio.c cannot
  include this itself -- under -DPOSIX it defines NOSYSIOCTLH and skips the
  include -- and without FIONREAD both conchk() and ttchk() are hard-wired
  to return 0.  See victor/sys/ioctl.h, which explains the whole problem.
*/
#include <sys/ioctl.h>

/*
  read() is renamed for every module in the build, and ckvictor.c SS0d
  supplies the replacement.  It is the one call that has to behave
  differently here than MS-DOS makes it behave: a handle read of a
  character device with nothing pending returns 0, and ckutio.c's
  myfillbuf() -- stock upstream, and staying that way -- requires a read
  that blocks until it has something.

  A rename rather than a definition of read() over the top of the library's,
  because the replacement delegates: everything that is not the
  communications device goes to the real read(), so the console handling in
  ckvictor.c SS0c and Watcom's text-mode translation both survive intact.
  ckvictor.c undefines it at the top so that read() there means the
  library's.

  Nothing is declared here on purpose.  <unistd.h> and <io.h> declare
  read(), and this macro turns those declarations into the declaration of
  v9k_read() -- which is how every module gets a prototype that agrees with
  its own runtime's, without this file having to guess at the spelling.
  The two macros below are only for ckvictor.c, which does have to write
  the definition out.

  Object-like, not function-like, for exactly that reason: a function-like
  macro rewrites calls but mangles the declarations, turning read()'s
  parameter list into "v9k_read((int __fd),(void *__buf),...)".  Renaming
  the bare token is safe here because no module in the build uses "read" as
  anything but this call -- verified across all 24.
*/
#define V9K_RTYPE  int
#define V9K_RCOUNT unsigned

#define read v9k_read

/*
  write() is renamed for the same reason and by exactly the same mechanism,
  and it arrived with the driver in ckvictor.c SS1e.

  Once this port owns the uPD7201, it owns BOTH directions.  MS-DOS Kermit
  3.13 uses its SERIALA handle for open, close and IOCTL and never for a
  byte of data (PORTING.md SS11), and half-owning the chip is worse than
  either extreme: the OEM driver's transmit path and our receive interrupt
  would be selecting registers on the same control port, and its notion of
  what the line is doing would be built out of a receiver we had emptied
  behind its back.  So ttol() and ttoc()'s write() has to land on our
  transmitter, and this is how.

  It delegates exactly as read() does -- everything that is not the
  communications device, and everything written before the driver is
  installed, goes straight to the library's write(), so DEBUG.LOG, the
  console and every file C-Kermit creates are untouched.

  Same audit as read(): no module in the build uses "write" as an
  identifier -- the 60-odd other occurrences across the 24 are all inside
  string literals and comments, which the preprocessor does not touch.
*/
#define V9K_WTYPE  int
#define V9K_WCOUNT unsigned

#define write v9k_write

/*
  fopen() and fclose(), renamed by the same object-like-macro trick and for
  a much smaller reason: ckvictor.c section 0e's foreground tag.
  PORTING.md SS16r found its first loss tagged 0, "somewhere upstream", and
  0 covers packet decoding, stdio and the DOS file open after the F packet
  alike.  These two put the open and the close of the receive file into
  tags of their own, at the cost of two stores per transfer.

  The wrappers delegate unconditionally -- there is no Victor behaviour
  here at all, unlike read() and write(), which have a communications
  device to route around.  Same audit as those two: no module in the build
  uses either token as anything but the call, and <stdio.h>'s declarations
  become the declarations of ours.  ckvictor.c undefines both.
*/
#define fopen  v9k_fopen
#define fclose v9k_fclose

/*
  The uPD7201 receive ring (ckvictor.c SS1e).  It is the only new static
  array this port adds and it comes straight out of DGROUP, so it is here
  with the other size levers rather than buried in the driver.

  WHAT THIS HAS TO COVER, CORRECTED.  It used to say here that the ring
  covers "the longest gap between two of C-Kermit's reads, not the longest
  packet", because myfillbuf() drains it in one call and comes straight
  back.  That is the wrong model and it is what made 512 look sufficient.

  myfillbuf() does drain the ring in one call, but into mybuf[], and
  ttinl() then walks mybuf[] one byte at a time and only calls read()
  again when it runs out.  The rest of the packet is still arriving the
  whole time.  So what the ring has to hold is not a gap between reads --
  it is the BACKLOG the foreground accumulates over one packet, and that
  backlog is proportional to the packet length whenever the foreground is
  even slightly slower than the line.  On this machine it is.

  Measured at 9600 bps, MS-DOS 3.1 under MAME (PORTING.md SS16k), both
  runs byte-exact with rxlost = 0:

      ring  512   packets to 2,668 on the wire   rxpeak = 502 of 512
      ring 4096   packets to 3,605 on the wire   rxpeak = 502 of 4096

  Read those two lines together, because the second is the informative
  one: the peak backlog is the SAME 502 bytes with eight times the ring
  and a third again the packet length.  It is not proportional to
  anything.  The foreground keeps up with the line on average; what 502 is
  is one fixed-duration stall -- about 523ms at 9600 -- during which
  nothing is drained at all.  (Which stall is not established; the file
  write between packets is the obvious candidate and has not been
  isolated.)

  That is why 512 failed the way it did.  It was not too small for the
  average case, it was ten bytes from the edge of the ONE case that
  matters, and a longer packet only has to leave that stall more room to
  land inside the data rather than in the turnaround.  Hence packets of
  968 and 1,952 that ACKed first time and 3,904 that never arrived.

  So 4096 is not sized from a rate at all.  It holds an entire
  maximum-length packet, which is the only assumption that stays true when
  something else gets slower -- and there is nothing to fall back on if it
  does not, because there is no flow control here (tcflow() is a stub).
  Against a measured 502 it is an eight-fold margin.

  Cost is 3,584 bytes of DGROUP over the old 512 -- measured 44,592 ->
  48,176 of 65,536 (73%), against 20,944 that were free.  This is one of
  the few things in this file that really does come out of the segment.

  512 was also what MS-DOS Kermit 3.13 chose for this machine
  (msxv90.asm's "source" buffer, BUFSIZ) -- but 3.13 never negotiated long
  packets, so that precedent does not carry to this build.

  Must be a power of two: the head and tail pointers are masked with
  V9K_RXBUFSIZ-1, which is what lets the interrupt handler and the
  foreground share them with no critical section at all.

  ckvictor.c maintains rxpeak alongside rxlost/rxfull and prints all three
  to stdout at exit in EVERY build.  That is deliberate and PORTING.md
  SS16k is the reason: -d costs about 25ms per received byte, which
  starves this ring by itself, so the debug log cannot be where the ring's
  own numbers are read.
*/
#define V9K_RXBUFSIZ 4096

/*
  Packet buffers.  With DYNAMIC these are malloc'd, and in the large model
  malloc() is the FAR heap -- outside DGROUP entirely.  So unlike every
  other size in this file these do not compete for the 64K; what bounds
  them is the 387K the machine has in total.

    SBSIZ/RBSIZ are the total buffer pools, carved at runtime into
    (window slots) x (negotiated packet length).

  These four are the CAPACITY.  They are not what reaches the wire, and
  believing otherwise cost this port a session -- see DRPSIZ/DFWSIZ below.
  Through SS16i they were 1024/1024/2048/2048.

  8192 and 4000 are chosen to hold two 4,000-byte packets exactly:
  inibufs() mallocs SBSIZ+RBSIZ+40 = 16,424 and hands each half to
  makebuf(), which divides a pool by the negotiated slot count.  So the
  pool has to be at least (packet length) x (window), and at window 1 it is
  twice what it needs -- deliberately, so that turning the window up to 2
  later is a one-line change here and not a re-measurement.

  MAXSP/MAXRP at 4000 rather than the protocol's 9024 ceiling because
  dofast() clamps to 4000 anyway (ckcfn3.c:361) and a 9,024-byte packet is
  9.4 seconds of 9600 bps line time to lose to one bad byte.

  Cost, all of it on the far heap and none in DGROUP: 16,424 for the pools
  plus RBSIZ+100 = 8,292 for srvcmd, against the ~183K the image leaves
  free (PORTING.md SS16j).  Under DYNAMIC there is no static array of
  either size -- ckcfn3.c:334 and ckcmai.c:1017 are pointers -- which is
  why hard rule 5 says never to remove DYNAMIC.
*/
#define MAXSP 4000                      /* Max long packet, send    */
#define MAXRP 4000                      /* Max long packet, receive */
#define SBSIZ 8192                      /* Send buffer pool         */
#define RBSIZ 8192                      /* Receive buffer pool      */

/*
  And these two are what actually reaches the wire.

  DRPSIZ and DFWSIZ initialise urpsiz and wslotr, which rpar() encodes into
  the MAXLX1/MAXLX2 and WINDO fields of every S and I packet this program
  sends.  On a normal build nobody sets them, because dofast() overwrites
  both at startup from the four capacity symbols above.  **This build never
  calls dofast().**  It is inside the #ifndef NOTCPIP that opens at
  ckcmai.c:3390 and does not close until 3644 -- the #endif comments at
  3574 and 3644 are misattributed by one level -- so every NOTCPIP build
  silently loses it, along with getdialenv().  Confirmed three ways in
  PORTING.md SS16j, the least arguable being that the preprocessed ckcmai.c
  contains "dofast" only as a prototype, with no call anywhere.

  So until SS16j the port negotiated MAXL=90, WINDO=1, MAXLX=90 -- the stock
  DRPSIZ/DFWSIZ -- through its entire history, and SBSIZ/RBSIZ/MAXSP/MAXRP
  had never once influenced a byte on the wire.  The I packet quoted in
  SS16i decodes to exactly that; the evidence was in the document before
  anyone read it.

  DFWSIZ stays at 1 on purpose.  There is no interrupt-level flow control
  here (ckvictor.c SS1e; tcflow() is a stub), and what holds rxlost/rxfull
  at 0/0 is that the far end waits for an ACK before sending again -- so
  nothing arrives while the 8088 is writing the last packet to disk.  A
  longer packet does not disturb that; a second window slot does.  SS13
  step 8 says one at a time, and the packet length is the one that costs
  nothing.

  Needs the #ifndefs in ckcker.h: the ELEVENTH guarded upstream edit,
  PORTING.md SS8.

  WHY THIS IS 4000, AND WHY IT WAS 90 FOR ONE SESSION IN BETWEEN.

  SS16j set 4000, watched the ramp die, and put it back:

      236 bytes  -> ACKed
      480 bytes  -> ACKed
      968 bytes  -> dead

  and recorded a "receive ceiling in (480, 968] that nothing in the port's
  configuration explains".  Two things were wrong with that, and SS16k has
  both on the target.

  FIRST, the ceiling was an artifact of the instrument.  Every run that
  established it was a -d run, and -d costs about 25ms per received byte
  -- 4,274 "TTINL myread char" lines for one file.  That starves the ring
  by itself: rxfull reached 2,483 and rxpeak pinned at 511 of 512.  The
  identical binary at the identical DRPSIZ=4000 with -d dropped delivered
  the same 968-byte packet on the first try, and 2,048 bytes byte-exact in
  four seconds.  The debug log could not measure this because the debug
  log was causing it.

  SECOND, there was a real ceiling underneath, and it was the ring after
  all -- the "obvious suspect" SS16j talked itself out of.  Without -d,
  packets of 968 and 1,952 ACKed first time and 3,904 never arrived, with
  rxpeak 502 of 512.  V9K_RXBUFSIZ is now 4096 and the margin is eightfold
  rather than tenbyte; see the ring's own comment above for why the number
  is what it is, because the reason is not the one you would guess.

  Measured with both changes in, 9600 bps, MS-DOS 3.1 under MAME:

      32,768 bytes, byte-exact, 56s, 582 cps
      longest packet on the wire 3,605
      v9k: rxlost=0 rxfull=0 rxpeak=502 of 4096

  NOT yet clean: that run still took one timeout and two retransmissions,
  with rxfull = 0 -- so whatever they are, they are not this ring.  The
  standing suspicion is the timeout itself; see PORTING.md SS16k, which has
  the arithmetic and no measurement to back it.

  Which is why both are wrapped in #ifndef here as well as in ckcker.h: the
  packet length is then a one-flag experiment and not a tree edit,

      make -f victorow.mak clean
      make -f victorow.mak XFLAGS="-dDRPSIZ=90"

  which is how SS16k bisected the ceiling and how you go back to short
  packets if a change here turns out to be wrong.  wcc puts $(XFLAGS) after
  -fi=ckvictor.h on the command line, but -d options are processed before
  the forced include either way, so the guard is what makes the override
  win rather than collide.

  Do NOT combine that with -dKEEP_DEBUG and believe the result.  SS16k is
  the whole story: -d costs about 25ms per received byte, which is enough
  to starve the receive ring on its own, so a -d run cannot measure
  anything about long packets.  The counters print to stdout in every
  build precisely so that they never have to.
*/
#ifndef DRPSIZ
#define DRPSIZ 4000                     /* RECEIVE PACKET-LENGTH    */
#endif /* DRPSIZ */
#ifndef DFWSIZ
#define DFWSIZ 1                        /* WINDOW: see above        */
#endif /* DFWSIZ */

/*
  V9K_OBUFSIZE -- how much of a received file is held before it is written.

  PORTING.md SS16m put the first number on the disk: 32 writes of 1,024 bytes
  in a 32,768-byte receive, 3.5 to 7.0 seconds of a 54-second transfer, worst
  single write half a second and always the first.  That is 6 to 11% of the
  elapsed time, and it is part of the ~12.5 seconds of dead time that does
  NOT shrink when the line gets faster -- which is why SS16m says 38400 should
  be expected to give ~1,400 cps rather than ~2,400.  The disk is the largest
  measured component of it.

  1,024 is OBUFSIZE from ckcker.h, and that is the "Not BIGBUFOK" fallback,
  which the file defines UNGUARDED --

      #else / * Not BIGBUFOK * /
      #define INBUFSIZE 1024
      #define OBUFSIZE 1024

  -- so unlike DRPSIZ above it cannot be pre-empted from here.  It does not
  have to be.  OBUFSIZE is only ever read twice: to initialise the int
  zobufsize (ckcmai.c:1652) and to bound SET BUFFERS, which this build does
  not have.  Everything that actually moves bytes reads the VARIABLE --
  getiobs() mallocs zobufsize (ckcmai.c:3795) and zmchout() flushes at
  zobufsize (ckcker.h) -- so anything that runs before getiobs() can set the
  size with no upstream edit at all.  ckvictor.c SS1d has that initializer,
  next to the two that are already there, and it is an XI record for the
  same reason the _fmode one is: getiobs() is
  called from main(), and the XI table is the only hook this port has that
  is guaranteed to be earlier.

  The cost is far heap, not DGROUP: zoutbuffer is a char * under DYNAMIC and
  malloc() is _fmalloc in the large model, so this does not touch the 64K
  (rule 4).  8,192 takes 7K more of the ~150K that is left after the packet
  buffers, and turns 32 writes into 4.

  Whether that bought anything was the open question, and PORTING.md SS16n
  answered it: the cost is PER CALL.  Two runs against SS16m run 4, same
  fixture and the same 39,574 wire bytes with the same single retransmission,
  took the disk from 32 writes and 4.5 s to 4 writes and about 1 s, the dead
  time from 12.8 s to 9.8, and 32,768 bytes from 603 to 633 cps.  Fitting
  the two sizes gives ~0.124 s fixed per write() plus ~15us/byte, so

      1,024  32 writes  4.5 s        8,192   4 writes  1.0 s
      4,096   8 writes  1.5 s       16,384   2 writes  0.75 s

  and 8,192 collects most of what there is -- one write for the whole file
  would still cost 0.6 s.  Going higher buys tenths and spends far heap.

  The instrument that says so is the "v9k: wfile" line, which reports n, the
  worst reading, which write it was, how many bytes it carried, and the
  total.  Read the TOTAL and not the worst: SS16n found this machine's DOS
  clock advances in half-second steps, so a single write has never actually
  been timed.

      make -f victorow.mak clean
      make -f victorow.mak XFLAGS="-dV9K_OBUFSIZE=1024"

  puts SS16m's baseline back for one build without a tree edit.
*/
#ifndef V9K_OBUFSIZE
#define V9K_OBUFSIZE 8192               /* File OUTPUT buffer bytes */
#endif /* V9K_OBUFSIZE */

/*
  MAXWS is deliberately NOT set here.  It used to be, at 8, and it never
  took effect: unlike MAXSP / MAXRP / SBSIZ / RBSIZ, which ckcker.h wraps in
  #ifndef, ckcker.h defines MAXWS unconditionally --

      #ifdef pdp11
      #define MAXWS  8
      #else
      #define MAXWS 32
      #endif

  -- so ckcker.h always wins and the compiler warns about the redefinition.
  Measured: MAXWS is 32.  Setting it here only produced a warning and a
  false entry in the memory budget.

  The good news is that this does NOT disturb the buffer arithmetic.  Under
  DYNAMIC the pools are the literal SBSIZ/RBSIZ above; only the non-DYNAMIC
  path derives them as MAXSP*(MAXWS+1).  What MAXWS = 32 instead of 8 really
  costs is:

      static  sbufuse[32] + rbufuse[32]      128 bytes (was 64 at MAXWS 8)
      heap    s_pkt + r_pkt, 14 bytes each   896 bytes (was 224)

  about 736 bytes more than the port needs, since dofast() computes
  wslotr = RBSIZ/MAXSP = 4 slots and the negotiated window can never exceed
  what the 4096-byte pool can carve.

  Reclaiming it means wrapping ckcker.h's MAXWS in #ifndef -- a sixth
  guarded upstream edit, and one that matches what that file already does
  for its four neighbours.  Not done unilaterally; see PORTING.md SS15.
*/

/*
  String space for wildcard expansion.

  ckufio.c's initspace() asks malloc for SSPACE bytes and, if it is
  refused, halves the request and tries again until something succeeds --
  keeping whatever it finally got.  DYNAMIC's default is 10,000 bytes, and
  "whatever was left" is not a size this port wants to depend on: 2048
  holds 150 or so 8.3 names, which is more than a FAT directory on this
  machine can contain, and it is a fixed cost.

  This was the sharper of two levers when the heap lived inside DGROUP;
  with the far heap it is a smaller matter, but a fixed allocation is still
  the right shape.  Overriding it needs ckufio.c's #ifndef -- the seventh
  guarded upstream edit, PORTING.md SS8.
*/
#define SSPACE 2048

/*
  How many names one wildcard may expand to.

  ckufio.c keeps the matches in an array of maxnames pointers and zxpand()
  mallocs the whole array before it reads the first directory entry, so
  the default of 1024 is a 2,048-byte allocation whether the pattern
  matches two files or none.  Alongside SSPACE above that was most of the
  heap.  64 names is a limit this machine will not reach in practice --
  and a wildcard send that hits it fails loudly, with "?Too many files (64
  max)", which is the opposite of the silence this port has been chasing.

  Needs the #ifndef in ckcdeb.h: the eighth guarded upstream edit,
  PORTING.md SS8.
*/
#define MAXWLD 64

/* Do NOT define BIGBUFOK: it asks for 290000-byte buffers. */

/* ------------------------------------------------------------------ */
/* Subsystems removed -- networking and security                        */
/* ------------------------------------------------------------------ */
/*
  These take ckcnet.c, ckctel.c, ckcftp.c, ckuath.c, ck_ssl.c and ck_crp.c
  out of the picture.  ckcnet.c and ckctel.c still compile (to ~100 bytes
  total) and are kept in the link so their few referenced symbols resolve
  without editing the mainline code.
*/
#define NONET                           /* No networking at all       */
#define NOTCPIP                         /* No TCP/IP                  */
#define NOSSH                           /* No SSH                     */
#define NOFTP                           /* No FTP client              */
#define NOHTTP                          /* No HTTP client             */
#define NOIKSD                          /* No Internet Kermit Service */
#define NORLOGIN                        /* No rlogin                  */
#define NOURL                           /* No URL parsing             */
#define NOBROWSER                       /* No browser dispatch        */

/* ------------------------------------------------------------------ */
/* Subsystems removed -- character sets                                 */
/* ------------------------------------------------------------------ */
/*
  This is the single biggest win in the whole configuration.  NOCSETS and
  NOUNICODE reduce ckuxla.c and ckcuni.c to literally zero bytes of code
  and data -- ckcuni.c alone is 770KB of source, almost all translation
  tables.  Transfers are still fully correct in binary mode and in text
  mode for ASCII, which is all the Victor needs.
*/
#define NOCSETS                         /* No charset translation     */
#define NOUNICODE                       /* No Unicode tables          */

/* ------------------------------------------------------------------ */
/* Subsystems removed -- process model                                  */
/* ------------------------------------------------------------------ */
/*
  MS-DOS has no fork/exec, no pseudo-terminals and no job control, so
  everything that depends on spawning a second process must go.
*/
#define NOPTY                           /* No pseudo-terminals        */
#define NOPUSH                          /* No external commands/shell */
#define NOJC                            /* No job control (suspend)   */
#define NOREDIRECT                      /* No REDIRECT / pipes        */

/* ------------------------------------------------------------------ */
/* Subsystems removed -- dialing                                        */
/* ------------------------------------------------------------------ */
/*
  ckudia.c is 238KB of modem database.  A direct serial connection needs
  none of it.  MINIDIAL additionally trims what little remains.
*/
#define NODIAL                          /* No DIAL command / modem db */
#define MINIDIAL                        /* Minimum modem support      */
#define NOLOGDIAL                       /* No dial logging            */

/* ------------------------------------------------------------------ */
/* Subsystems removed -- scripting and interactive conveniences         */
/* ------------------------------------------------------------------ */
/*
  NOSPL removes the script language (variables, macros, IF/WHILE, functions)
  -- ~1100 references, and a large amount of both code and data.  The
  interactive command parser itself is NOT removed; NOICP is deliberately
  left undefined because "C-Kermit>" with SEND/RECEIVE/GET/SERVER is the
  entire point of the milestone.
*/
#define NOSPL                           /* No script language         */
#define NOSCRIPT                        /* No UUCP-style script       */
#define NOSEXP                          /* No S-expressions           */
#define NOLEARN                         /* No learned scripts         */
#define NOHELP                          /* No built-in help text      */
#define NORECALL                        /* No command recall/edit     */
#define NOSETKEY                        /* No key mapping             */
#define NOKVERBS                        /* No keyboard verbs          */
#define NOXMIT                          /* No TRANSMIT command        */
#define NOMSEND                         /* No multi-file MSEND        */
#define NOFRILLS                        /* No minor conveniences      */
#define NOCCTRAP                        /* No setjmp ^C trapping      */

/* ------------------------------------------------------------------ */
/* Subsystems removed -- logging, debugging, terminal                   */
/* ------------------------------------------------------------------ */
/*
  NODEBUG is worth a lot: debug() calls are threaded through every module
  and each one costs code plus format strings in DGROUP.
*/
/*
  KEEP_DEBUG turns the debug log back on for a diagnostic build, the same
  way KEEP_ICP turns the command parser back on:

      make -f victorow.mak XFLAGS=-dKEEP_DEBUG
      CKERMITD -d -s FOO.BIN          (writes ./debug.log on the target)

  Never defined by the makefile.  It is affordable here because -zc puts
  the format strings in far code; it was not affordable under the retired
  gcc build, where the same switch pushed the objects alone to 104.8% of
  DGROUP before libc added anything.  (PORTING.md SS16e.)
*/
#ifndef KEEP_DEBUG
#define NODEBUG                         /* No debug log               */
#endif /* KEEP_DEBUG */
#define NOTLOG                          /* No transaction log         */
#define NOSYSLOG                        /* No syslog                  */
#define NOCURSES                        /* No curses fullscreen       */
#define NOTERMCAP                       /* No termcap                 */
#define NOESCSEQ                        /* No escape-sequence parsing */

/* ------------------------------------------------------------------ */
/* Odds and ends not available or not wanted                            */
/* ------------------------------------------------------------------ */
#define NOREALPATH                      /* No realpath()              */
#define NOTIMEZONE                      /* No timezone database       */
#define NORANDOM                        /* No random numbers          */
#define NOUUCP                          /* No UUCP lockfiles          */
#define NOWTMP                          /* No wtmp accounting         */
#define NOPARSEN                        /* No network directory parse */

/*
  No floating point, and it is worth more than anything else in this list.

  The 8088 in a Victor has no 8087, so every float operation goes through
  Open Watcom's software emulator -- emu87.lib and math87l.lib, which the
  linker pulls in whole.  Measured (PORTING.md SS16j): dropping them takes
  25,582 bytes off far code and 992 off DGROUP, and what the image needs at
  load from 239,486 to 212,900.  That is 26,586 bytes of the machine's 387K,
  bought by turning off arithmetic this port does not do.

  NOFLOAT is upstream's own switch: ckcdeb.h undefines CKFLOAT, GFTIMER and
  FNFLOAT together.  What it costs here is nothing that runs:

    - isfloat(), ckround() and fpformat() are script-language functions and
      NOSPL has already removed every caller.
    - GFTIMER only makes the elapsed-time statistics fractional.
    - The one live use is the round-trip-time estimate in ckcfn2.c, and
      upstream ships the integer path for it four lines below the float one
      (ckcfn2.c:434 vs :442).  The integer form works out about 1.13 times
      larger, so the adaptive receive timeout gets slightly more patient --
      the safe direction on a 9600 bps line with an 8088 at the far end.

  NOGFTIMER alone was tried first and is not worth having: it saves 1,424
  bytes and leaves the emulator linked, because CKFLOAT and not GFTIMER is
  what drags it in.

  Needs two #ifdef CKFLOAT guards in ckcfnp.h, which declares ckround() and
  fpformat() with a type that NOFLOAT deletes while both definitions are
  already guarded.  That is the TENTH guarded upstream edit, PORTING.md SS8,
  and it is the same defect as the sixth in the same file.
*/
#define NOFLOAT                         /* No floating point at all   */

/* ------------------------------------------------------------------ */
/* The interactive command parser -- OFF, and it is RAM, not DGROUP     */
/* ------------------------------------------------------------------ */
/*
  NOICP removes the "C-Kermit>" prompt.  It is the one thing this port most
  wants back, and the reason it is off has changed.

  It used to be DGROUP.  Under the retired ia16-elf-gcc build every string
  literal was near, the parser's tables and messages in ckuus3-7 were 43KB
  of .rodata, and the program simply did not link (PORTING.md SS9c).  The
  large model removes that: -zc puts literals in far code, and with the
  parser in, DGROUP measures 60,768 of 65,536 -- it FITS, with 4,768 to
  spare, and -zt128 takes it to 19,376 (PORTING.md SS9d).

  What it does not fit is the machine.  The parser build asks DOS for
  429KB contiguous and the largest block a program gets on the test setup
  is 387KB, so it loads on neither DOS (PORTING.md SS16a).  Fitting the
  data group and fitting the RAM are two different questions and this port
  has hit both walls.

  What survives is exactly the milestone that matters -- the protocol
  engine, the file system, and the command-LINE parser in ckuusy.c, which
  is what actually moves a file:

      CKERMIT -l COM1 -b 9600 -s FOO.BIN      send
      CKERMIT -l COM1 -b 9600 -r              receive
      CKERMIT -l COM1 -b 9600 -x              server

  Four symbols owned by the removed modules are still referenced by code
  that survives; they are stubbed in ckvictor.c.
*/
/*
  KEEP_ICP is the switch for re-testing that measurement.  It is never
  defined by the makefile; it exists so the experiment can be repeated with
  one -d and without editing this file:

      make -f victorow.mak clean
      make -f victorow.mak XFLAGS=-dKEEP_ICP sizes
      make -f victorow.mak XFLAGS=-dKEEP_ICP ZT=-zt128 sizes
*/
#ifndef KEEP_ICP
#define NOICP                           /* No "C-Kermit>" prompt      */
#endif /* KEEP_ICP */

/*
  Deliberately NOT defined -- these are the features being ported:

    NOXFER    file transfer               (SEND / RECEIVE / GET)
    NOSERVER  server mode                 (SERVER)
    NOLOCAL   local mode / SET LINE       (needed to own a serial port)
    NOLP      long packets
    NOWINDOW  sliding windows
    NORESEND  RESEND / REGET  (restart)
    NOSTREAMING  streaming
*/

#endif /* CKVICTOR_H */

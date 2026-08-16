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

/*
  POSIX_CRTSCTS -- and this one is load-bearing rather than cosmetic.

  ckcdeb.h defines CK_RTSCTS for every UNIX build (line 246), so C-Kermit
  believes this platform can do RTS/CTS and offers it.  It does NOT define
  POSIX_CRTSCTS, because that symbol is handed out per-platform (__linux__,
  the BSDs, IRIX52, BeOS) and the Victor is none of them.  The consequence
  is not a missing feature, it is a SILENTLY EMPTY FUNCTION: with none of
  those arms taken, every branch of ckutio.c's tthflow() preprocesses away
  and the whole body reduces to "int x = 0; return(x);".  Measured, not
  read -- wcc -pl on ckutio.c with this build's flags, where tthflow()'s
  body is thirty blank #line directives.

  So ttpkt()'s FLO_RTSC arm called tthflow(flow,1,&ttraw), which did
  nothing, and CRTSCTS never reached our tcsetattr().  NEXT_SESSION.md's
  "the plumbing is already there -- CRTSCTS at ckutio.c:6252" was reading a
  line inside #ifdef OXOS.  Defining this takes the POSIX arm instead
  (ckutio.c:5920), which is written entirely in tcgetattr()/tcsetattr() --
  both ours -- so the bit now arrives in c_cflag and the cached termios
  this port hands back to tcgetattr() describes the line honestly.

  It is confined: three uses in ckutio.c (the tthflow arm, two FLO_KEEP
  lines in ttvt(), and one in ttpkt()) plus a string in SHOW FEATURES.  No
  upstream edit.

  IT IS NOT WHAT THE DRIVER DECIDES ON, and that is worth knowing here
  because the obvious reading of this #define is that it would be.  The
  matching IXON|IXOFF for XON/XOFF never survives ttpkt(): ckutio.c:6758
  clears them again unconditionally four lines before the tcsetattr() that
  applies the struct.  So one of the two mechanisms arrives through termios
  and the other cannot, and ckvictor.c SS1f reads upstream's "flow"
  variable for both rather than being right by accident for one.  This
  #define stays because it makes the platform's own description true, not
  because anything depends on it.
*/
#ifndef POSIX_CRTSCTS
#define POSIX_CRTSCTS
#endif /* POSIX_CRTSCTS */

/*
  What the build says it was built FOR.  ckuver.h assigns HERALD to ckxsys
  (ckutio.c:292) and ckzsys (ckufio.c:308), picks it from a long chain of
  platform #ifdefs, and ends with

      #ifndef HERALD
      #define HERALD " Unknown Platform"
      #endif

  so defining it here is upstream's own mechanism and costs no edit.  Every
  arm of that chain starts with a space and this one has to as well: two of
  the three places it is printed are "%s for%s" in shover(), where the
  space is the separator.

  The machine and not the operating system, because that is what the binary
  is built for -- one image runs on Victor MS-DOS 3.1 and on FreeDOS for
  Victor, and SHOW VERSIONS reports which one it is running on separately,
  out of uname().  Sirius 1 is the same machine sold outside the USA.

  Left alone next door: CKCPU.  With it undefined, ckuus4.c's \\v(machine)
  falls through to unm_mch from uname(), which already answers "Victor" --
  a runtime answer, and a better one than a compile-time constant.
*/
#ifndef HERALD
#define HERALD " Victor 9000 / Sirius 1"
#endif /* HERALD */

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
  getcwd(), renamed by the same trick, and this one is a correctness fix.

  This build defines UNIX, so every path primitive above it joins with '/'
  and tests for '/'.  DOS hands back "A:\" for the root of a drive -- a
  separator upstream cannot see, on the end of a string upstream assumes
  has none.  zfnqfp() (ckufio.c:7500) does

      x = ckstrncpy(buf,zgtdir(),len);  buf[x++] = '/';

  unconditionally, so a relative name became "A:\/NAME", which DOS will not
  open.  That is what stopped "CKICP FILE.KSC" from running a take-file: the
  file was found, its qualified name was mangled, dotake() failed, and
  because dotake() failing is also what leaves cfilef at 0, cmdlin() then
  went on to reject the filename as an unknown option.  One defect, two
  symptoms, and the second one is the message everybody saw.
  PORTING.md SS16ab.

  ckvictor.c's wrapper returns a Unix-shaped path: separators forward, no
  trailing one.  At the root of a drive -- the only directory this project
  has ever run in -- that is "A:", and "A:" + "/" + "NAME" is a path DOS
  accepts.  INT 21h takes '/' as a separator throughout; it is COMMAND.COM
  that does not, and nothing here goes through COMMAND.COM.
*/
#define getcwd v9k_getcwd

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
#ifndef V9K_RXBUFSIZ
#define V9K_RXBUFSIZ 4096
#endif /* V9K_RXBUFSIZ */

/*
  How many wire bytes a DRPSIZ-byte packet actually costs, over and above
  DRPSIZ itself.  MEASURED, not assumed: at DRPSIZ = 4000 the longest
  packet SS16as saw on the wire was 3,991 data with 3,998 wire bytes, so
  the framing and the terminator come to 7.  8 is used because the only
  consumer bounds a buffer with it, and rounding the wrong way there is how
  a ring overflows.

  The consumer is ckvictor.c's --window=N clamp, and PORTING.md SS16as is
  why it exists: a window of W lets the far end hold W unacknowledged
  packets, so in-flight bytes are hard-bounded at W x (DRPSIZ + this), and
  the RING has to hold every one of them because nothing drains it while
  the foreground is decoding.  At the shipping DRPSIZ that ceiling is
  4096 / 4008 = ONE -- this build cannot usefully open a window at all, and
  SS16as measured what happens when it tries.
*/
#define V9K_PKT_WIRE_XTRA 8

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
  both at startup from the four capacity symbols above.  **This build does
  not call dofast(), and the reason changed with SS16ac.**

  It used to be an accident: dofast() sat inside the #ifndef NOTCPIP whose
  #endif comments were misattributed by one level, so every NOTCPIP build
  silently lost it along with getdialenv(), the init file and any command
  file named on the command line.  SS16j confirmed that three ways, the
  least arguable being that the preprocessed ckcmai.c contained "dofast"
  only as a prototype.

  SS16ac repaired the nesting -- guarded upstream edit 14 -- because the
  init file and the command file are wanted.  dofast() is then explicitly
  guarded out for VICTOR9K instead, and the reason is at the call site:
  wslotr = RBSIZ / MAXSP = 2, so taking it back would open the window to
  TWO on a port that has no interrupt-level flow control and whose 4,096-
  byte ring is safe only because one packet is in flight at a time.  Remove
  that guard when flow control and windowing are actually done.

  So until SS16j the port negotiated MAXL=90, WINDO=1, MAXLX=90 -- the stock
  DRPSIZ/DFWSIZ -- through its entire history, and SBSIZ/RBSIZ/MAXSP/MAXRP
  had never once influenced a byte on the wire.  The I packet quoted in
  SS16i decodes to exactly that; the evidence was in the document before
  anyone read it.

  DFWSIZ stays at 1 on purpose, and it is now the DEFAULT rather than the
  only setting -- see --window=N in ckvictor.c (PORTING.md SS1 item 12).

  What holds rxlost/rxfull at 0/0 at a window of one is that the far end
  waits for an ACK before sending again, so nothing arrives while the 8088
  is decoding the last packet and writing it to disk.  A longer packet does
  not disturb that; a second window slot does.  SS13 step 8 says one at a
  time, and the packet length is the one that costs nothing.

  That safety is also the cost: line and foreground are strictly SERIALIZED,
  9.77 s and 15.90 s of a 25.66 s receive after edit 18 (SS16aq), and a
  window is the only thing that overlaps them.  SS16aq took rxpeak to 459 of
  4,096, so the ring margin that gated this is no longer scarce -- which is
  why the switch exists now and did not before.

  Two things bound it, and neither is in ckcker.h:

    THE POOL.  Nothing in this build calls adjpkl() for the receive
    direction -- dofast() is guarded out (SS8 item 14) and the other two
    callers are REMOTE SET handlers -- so urpsiz stays at DRPSIZ while
    makebuf() divides RBSIZ by the slot count.  The condition is
    (DRPSIZ + 6) x slots <= RBSIZ, which is 4,006 x 2 = 8,012 <= 8,192:
    the ceiling is exactly 2 at these sizes, and it is the one the
    SBSIZ/RBSIZ comment above says was designed in.  v9k_set_window()
    clamps to it and prints the clamp.

    THE RING.  Through the whole decode interval the far end is now
    sending and nothing is draining, so rxpeak rises from 459 to about
    (dec tot / dec n) x 38.46 bytes at 38400 -- which is what the "dec"
    counter (ckvictor.c section 0e) was added to measure BEFORE the window
    is opened.  Over 4,096 and rxfull goes non-zero.

  Raising the window past 2 means raising SBSIZ/RBSIZ, which are far heap
  and cost load RAM rather than DGROUP.  Do not raise them until a leg says
  a window pays.

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
  V9K_PREFIXING -- how many control characters the far end is asked to
  prefix, and therefore how many wire bytes arrive.

  PORTING.md SS16v measured the throughput bound as the foreground decode
  path, 564us per received WIRE byte against a 260us byte time, so the
  cheapest lever left is to make fewer wire bytes.  SS16w measured what
  upstream's default costs on the all-byte-values fixture: 32,768 payload
  bytes went out as 37,568 wire bytes, 14.7% of them prefixes.

  Upstream initialises prefixing = PX_ALL at ckcmai.c:1312 -- prefix every
  control character -- because this build does not define NEWDEFAULTS.
  PX_CAU is upstream's own "cautious" setting, and setprefix() keeps CR,
  XON/XOFF, IAC, DEL and the packet-start character prefixed regardless
  (ckcmai.c:2699).  The values are ckcker.h's PX_ALL / PX_CAU / PX_WIL /
  PX_NON, which is why this expands in ckvictor.c and not here: -fi puts
  this file ahead of ckcker.h, so the names are not in scope yet.

  Selecting it is ckvictor.c's XI initializer, for the reason the comment
  there gives -- prefixing is an upstream VARIABLE with an upstream
  initialiser, so pre-empting it in this file would be an upstream edit,
  and NOICP leaves no SET PREFIXING to type.

      make -f victorow.mak clean
      make -f victorow.mak XFLAGS="-dV9K_PREFIXING=PX_ALL"

  builds the control leg.  That control is not optional when measuring
  this: the shipping binary has moved since SS16v's leg CA (SS16z through
  SS16ad), so CA is not a baseline for it and the prefixing change cannot
  be attributed without one built from the same tree.
*/
#ifndef V9K_PREFIXING
#define V9K_PREFIXING PX_CAU            /* Control-char prefixing   */
#endif /* V9K_PREFIXING */

/*
  V9K_COLLISION -- what RECEIVE does when the name already exists.

  Upstream defaults to BACKUP everywhere but VMS, and BACKUP CANNOT WORK
  ON FAT: the only name znewn() knows how to build is "name.~N~"
  (ckufio.c:4000), which is two dots and a four-character extension.  The
  rename fails and the file is refused, which is a confusing way to spell
  "refuse" and has voided two of this project's own bench sittings.

  REPLACE overwrites, which is the DOS convention and what MS-DOS Kermit
  3.13 does on this same machine.  It is a real cost, stated plainly: a
  RECEIVE into an existing name destroys that file.  XYFX_D puts the old
  effective behaviour (refuse) back, and it is the value to build with if
  that trade is not wanted:

      make -f victorow.mak XFLAGS=-dV9K_COLLISION=XYFX_D

  APPEND (XYFX_A) is the third policy this filesystem can support.  RENAME
  goes through znewn() as well and is no more available than BACKUP.

  Expanded in ckvictor.c, not here, so the XYFX_ name does not have to be
  in scope at the point this header is force-included.
*/
#ifndef V9K_COLLISION
#define V9K_COLLISION XYFX_X            /* RECEIVE overwrites       */
#endif /* V9K_COLLISION */

/*
  V9K_FLOW -- interrupt-level flow control, and V9K_RXHIGH/V9K_RXLOW are its
  water marks.  PORTING.md SS1 item 11; the driver is ckvictor.c SS1f.

  BOTH MECHANISMS ARE BUILT.  RTS/CTS is two port writes with no TX-ready
  test and is binary-transparent; XON/XOFF is an interoperability
  requirement rather than a fallback, because the far end's wiring is not
  something this port can measure.  SS16v read cts = 1 on the bench cable in
  both legs with the host holding RTS asserted under "set flow none", so the
  host's RTS reaches our CTS here -- which settles the INPUT half of RTS/CTS
  and says nothing about the output half.

  THE DEFAULT IS FLO_NONE, AND THAT IS A MEASUREMENT ARGUMENT, NOT A
  PREFERENCE.  Two reasons, in order of weight:

    1. Nothing needs it.  With DFWSIZ = 1 the far end sends a packet and
       waits for our ACK, so bytes in flight never exceed one packet; the
       longest this port has put on a wire is 3,991 and the ring is 4,096.
       rxfull has been 0 in every clean run ever recorded.  Flow control
       here is insurance against a longer packet or a second window slot,
       and both of those are still ahead of it.
    2. THE PORT'S HALF OF RTS/CTS WORKS AND THE HOST'S DOES NOT, which is
       measured on a logic analyzer rather than argued.  PORTING.md SS16an.

       The Victor's RTS pin moves: negative before any driver, positive
       when the OEM driver loads, a blip on every chip reprogram, 175us on
       each HANGUP, and -- the one that matters -- EIGHT PAUSES OF 785ms TO
       ~1s DURING SS16al LEG GB, which is SS1f dropping RTS at the 1,024
       water mark and raising it again at 896 on a clean byte-exact 32 KB
       transfer.  Data kept arriving for hundreds of milliseconds after
       each drop, because the far end was never told to watch that pin:
       `kermit -C "show features"` on the bench Mac does not list
       POSIX_CRTSCTS, so its tthflow() is the same empty function this
       build had before this file defined the symbol.

       So this comment has now said, in order, "unmeasured", "measured not
       to work", "never tested", and finally what the scope says.  Three of
       those four were written from counters inside the two programs, and
       BOTH PROGRAMS CAN BE RIGHT ABOUT WHAT THEY DID WHILE NOTHING HAPPENS
       BETWEEN THEM.  When the question is about a wire, measure the wire.

       WHAT IS LEFT IS THE HOST, NOT THIS PORT.  The risk that chose
       FLO_NONE -- gating the transmitter on a CTS nobody had measured,
       which on a one-way cable would turn a working port into a silent one
       -- is retired: the pin moves, the pair is all but certainly wired
       (SS16an has the 25ms tell, and one two-probe capture would close it),
       and SS16ak leg DS already sent 32,768 bytes at 1,475 cps with the CTS
       gate on the per-byte path.  What is missing is the BENEFIT: no far
       end has ever been shown to stop, because the only far end tested
       cannot be made to.

       So the default waits on the host.  Either `stty -f <port> crtscts
       -hupcl` immediately before kermit -- untested, free, and plausible
       because TESTING234 clears c_iflag only and an empty tthflow() cannot
       clear CRTSCTS either -- or a host C-Kermit built from this tree with
       POSIX_CRTSCTS.  Either one plus a re-run of SS16al legs GA/GB and
       rxpeak caps or does not for a reason that is about the Victor.

  So the feature ships built, selectable and instrumented, and the shipping
  binary behaves exactly as the byte-exact legs of SS16ah/SS16ai did:

      CKERMITW --rtscts    ...     RTS/CTS both directions
      CKERMITW --xonxoff   ...     XON/XOFF both directions
      CKERMITW --noflow    ...     explicit none (the default)

      make -f victorow.mak XFLAGS="-dV9K_FLOW=FLO_RTSC"

  parsed off the DOS command tail before argv exists, the same priority-0 XI
  mechanism --safe-server uses (PORTING.md SS16i), because NOICP removes SET
  FLOW.  A KEEP_ICP build's SET FLOW overrides either: it clears autoflow,
  and this port sets cxflow[CXT_DIRECT] rather than flow, so upstream's own
  precedence does the right thing with no special case.  The FLO_* names are
  ckcdeb.h's, which is why this expands in ckvictor.c and not here.

  WATER MARKS.  3/4 and 1/4 of the ring, which is 3.13's MNTRGH/MNTRGL on
  this same chip.  At 3,072 the high mark is above every occupancy this port
  has ever recorded (rxpeak 2,581 at 38400, SS16af), which is the point:
  turning flow control on must not change a transfer that was already
  working.  It also means the assert path DOES NOT RUN in a normal leg, so
  the counters on the "v9k: flow=" line are the only thing that can say
  whether it ever fired -- and a leg that wants to exercise it should build
  with -dV9K_RXHIGH=256 -dV9K_RXLOW=64 rather than wait for a defect.
*/
#ifndef V9K_FLOW
#define V9K_FLOW FLO_NONE               /* Default flow control     */
#endif /* V9K_FLOW */

#ifndef V9K_RXHIGH
#define V9K_RXHIGH (V9K_RXBUFSIZ - (V9K_RXBUFSIZ / 4))   /* 3/4 full   */
#endif /* V9K_RXHIGH */

#ifndef V9K_RXLOW
#define V9K_RXLOW  (V9K_RXBUFSIZ / 4)                    /* 1/4 full   */
#endif /* V9K_RXLOW */

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

  RAISED FROM 2048, AND THE SENTENCE ABOVE IT IS WHY IT HAD TO BE.  "More
  than a FAT directory on this machine can contain" was written without a
  measurement and is false of this project's own test image, whose root
  holds 156 files: 156 8.3 names at 13 bytes apiece is 2,028, and
  nzxpand("./*") stores them with the "./" still on the front, which is
  2,340.  A REMOTE DIRECTORY of the working image therefore could not fit
  in the string space, and that -- with MAXWLD below -- is what leg NR
  found.  4096 holds ~270 such names.

  A FAT12 root can hold more than that (512 entries is the usual figure
  for a partition this size), so this is a working limit and not a proof.
  What makes it acceptable is that overrunning it FAILS LOUDLY: ckufio.c
  prints "?Too many files (N max)".  What made the old value unacceptable
  is not that it was small but that the comment claimed it could not be
  reached.
*/
#define SSPACE 4096

/*
  How many names one wildcard may expand to.

  ckufio.c keeps the matches in an array of maxnames pointers and zxpand()
  mallocs the whole array before it reads the first directory entry, so
  the default of 1024 is a 2,048-byte allocation whether the pattern
  matches two files or none.  Alongside SSPACE above that was most of the
  heap.  A wildcard send that hits the limit fails loudly, with "?Too many
  files (N max)", which is the opposite of the silence this port has been
  chasing.

  Needs the #ifndef in ckcdeb.h: the eighth guarded upstream edit,
  PORTING.md SS8.

  RAISED FROM 64, WHICH THIS COMMENT USED TO CALL "a limit this machine
  will not reach in practice".  Leg NR reached it with no wildcard at all:
  REMOTE DIRECTORY on a server expands "./*" over the working directory,
  and this project's own image has 156 files in its root, so the server
  answered "?Too many files (64 max)" on the console and "E No files
  match" on the wire.  That is what NEXT_SESSION.md item 15 had recorded
  since SS16i as "REMOTE DIRECTORY streams its listing and never
  terminates it" -- a different symptom, from a 51-file image, and the
  ceiling is what the same command does today.

  256 pointers is 1,024 bytes of far heap in the large model, against the
  ~33KB of slack a 384K Victor has after the image and the packet buffers.
  It does not move the load requirement at all, because the array is
  malloc'd: see hard rule 4, the heap is outside DGROUP.
*/
#define MAXWLD 256

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
  -- ~1100 references, and a large amount of both code and data.

  The comment here used to end "the interactive command parser itself is NOT
  removed; NOICP is deliberately left undefined", which stopped being true
  further down this file when NOICP went in, and the stale half was
  misleading in a specific way: it read as though scripting and the parser
  were one decision.  They are two, and SS16y is what separated them.

  NOSPL IS DEFINED INDEPENDENTLY OF NOICP, so a KEEP_ICP build gets the
  "C-Kermit>" prompt and NOT the script language.  What that costs is

      -C "commands"        ckuusy.c:2230 and :3542, both #ifndef NOSPL
      variables, macros, IF/WHILE/FOR, \f...() functions, INPUT

  and, importantly, NOT take-files: TAKE's keyword (ckuusr.c:1732) and
  handler (ckuusr.c:10566) are outside every NOSPL region, and the
  argv[1]-as-command-file path is #ifndef NOICP (ckcmai.c:2602).  An earlier
  version of this comment said take-files went with NOSPL; they do not, and
  SS16y has the correction.  A KEEP_ICP build that cannot run one is hitting
  the findinpath() defect in prescan(), not a missing feature.

  KEEP_SPL exists so the cost can be measured with one -d, the same idiom as
  KEEP_ICP, and it is never defined by the makefile.  It needs -zt512 (83%
  of DGROUP; -zt1024 lands exactly on 65,536) and section 2c's stubs, and it
  costs 637,714 bytes at load against KEEP_ICP's 428,662 -- +209,052, which
  moves the smallest usable machine from 512K to 768K:

      make -f victorow.mak XFLAGS=-dKEEP_ICP ZT=-zt2048              418K
      make -f victorow.mak XFLAGS="-dKEEP_ICP -dKEEP_SPL" ZT=-zt512  622K
*/
#ifndef KEEP_SPL
#define NOSPL                           /* No script language         */
#endif /* KEEP_SPL */
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
/*
  NOCURSES is NOT defined here, and the reason is not obvious.

  What this port wants is "no curses library", and NOCURSES is the switch
  that says so.  But ckcdeb.h:6098 turns NOCURSES into NODISPLAY, and
  ckcker.h:730 then makes xxscreen() and ckscreen() expand to NOTHING --
  which deletes the ENTIRE file-transfer display, CRT and SERIAL modes
  included, not just the fullscreen one.  Upstream conflates "no curses"
  with "no display at all".

  Nothing else in this build would define CK_CURSES on its own (ckcdeb.h
  reaches it only through SOLARIS, VMS, CK_NCURSES, MYCURSES or
  CK_WREFRESH, none of which apply), so leaving NOCURSES undefined gives
  fdispla = XYFD_S -- the one-line CRT display, which is conol()/write() and
  INT 21h only.  Verified with wcc -pl: ckscreen appears in the preprocessed
  ckcfn2.c, and no curses header is reached.

  -dNOCURSES puts the old behaviour -- no display at all -- back for one
  build, and it is worth having: it is the control for measuring what the
  display costs.
*/

/*
  CK_CURSES asks for the FULLSCREEN transfer display, fdispla = XYFD_C --
  the one MS-DOS Kermit 3.13 shows on this machine and the one C-Kermit
  shows on a Mac.  XYFD_S, the line that NOCURSES-undefined gets you on its
  own, is a regression against 3.13 and this port does not want to ship one.

  There is no curses library for DOS here and none is wanted.  What
  ckuusx.c's screenc() actually needs is move(), clear(), clrtoeol(),
  printw() and four no-ops, and on the Victor those are four escape
  sequences written with INT 21h.  victorow/curses.h declares them and
  ckvictor.c section 1g implements them -- the same header-plus-glue split
  as victor/sys/termios.h.  Read victorow/curses.h before touching any of
  it: it carries the evidence that this console is VT52/Z19 and not ANSI,
  and the two independent reasons upstream's own MYCURSES cannot be used.

  Two consequences to know.  fxdinit() disables the fullscreen display
  unless getenv("TERM") is non-empty AND tgetent() succeeds, even though
  nothing in this build reads a termcap -- section 1g stubs tgetent() and
  section 1d's initializer supplies a TERM, which is what makes XYFD_C
  survive to the transfer.  And the escape sequences are MS-DOS 3.1's:
  FreeDOS-for-Victor's kernel/victor_ansi.asm parses only ESC [ and passes
  everything else through, so on that DOS this display will paint noise.
  The fallback path exists and is automatic, but nothing DETECTS the case
  yet -- it is the first thing in this port that is not the same on both
  DOSes.  See NEXT_SESSION.md item 14.
*/
#define CK_CURSES                       /* Fullscreen transfer display */

/*
  CK_CURPOS says "cursor control is already provided", which stops
  ckuusx.c:7055 compiling its own ANSI-emitting version of ck_cls(),
  ck_cleol() and ck_curpos().  ckvictor.c section 1g provides them in VT52
  instead.  Two reasons, and the second is the one to remember: that
  fallback would print "[2J" at a console that cannot read it, and it does
  not compile anyway -- ckuusx.c:7070's K&R declarator is malformed and no
  other configuration has ever reached it.
*/
#define CK_CURPOS                       /* Section 1g has cursor control */
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
  NAP -- and this one turns something ON rather than off.

  ckutio.c's msleep() tries select(), poll() and usleep() before it reaches
  a chain of clock loops and, at the end of it, a bare "while (m > 0) m--;"
  that -os may delete outright.  This build has none of the first three, so
  the fallback is what it compiled, and a logic analyzer caught the
  consequence: a HANGUP that should hold DTR and RTS down for HUPTIME =
  500ms held them for 175us (PORTING.md SS16an).  tcsendbreak(), which is
  this port's own code in ckvictor.c section 1b, was sending a "quarter
  second" break two IOCTL round trips long.

  Defining NAP selects msleep()'s nap() arm at ckutio.c:12065, and
  ckvictor.c section 1d supplies nap() -- a busy loop calibrated once
  against the DOS clock, because INT 21h's clock advances in 500ms steps
  here (SS16n) and both delays that need this are inside one quantum.  It
  is upstream's own extension point, so no upstream edit.

  ckuus5.c:11397 puts NAP in SHOW FEATURES on the strength of this
  #define, which is now accurate.
*/
#define NAP                             /* msleep() calls our nap()   */

/*
  Packet character doubling and ignoring, and this one is on the per-byte
  receive path, which is why it gets a comment rather than a line.

  ckcdeb.h:3390 turns CKXXCHAR on for any build that defines UNIX, and this
  one does (see "Platform identity" above).  It backs two commands, SET SEND
  DOUBLE-CHARACTER and SET RECEIVE IGNORE-CHARACTER, and it puts a test at
  the top of ttinl()'s per-byte loop:

      cmp   word ptr ss:_ignflag,0
      je    L$310
      shl   bx,1
      mov   ax,seg _dblt
      mov   ds,ax
      test  byte ptr _dblt[bx],1

  The only writers of ignflag/dblflag/dblt are ckuus7.c (the SET commands)
  and ckuus3.c (SHOW), both inside "#ifndef NOICP".  In a shipping build the
  only write that ever happens is the initialiser to 0 at ckcfn3.c:292-293,
  so the branch is never taken and the table is never read.  What it costs
  is the two instructions before the "je" on every received byte, and

      short dblt[256]                                       512 bytes of DGROUP

  which is exactly what PORTING.md SS16af's CRC table cost, so this repays
  edit 17 to the byte.  Measured: DGROUP 48,816 -> 48,304, image 205,968 ->
  205,212, needs 220,160 -> 219,452 at load.  Warnings unchanged at 19.

  IT IS GUARDED BY "#ifndef KEEP_ICP", and the reason is that the two SET
  commands are only dead where the parser is.  A KEEP_ICP build can reach
  them, and the interactive parser is a FEATURE THIS PORT INTENDS TO SHIP --
  see the NOICP comment below, which calls it "the one thing this port most
  wants back".  Taking two documented commands out of a user-facing build to
  save DGROUP in a build that does not contain them is the wrong way round.

  What the guard costs, measured rather than projected, is in the table
  above for the shipping build and here for the parser one.  The number that
  governs it is PORTING.md SS16x's: what matters is the SMALLEST VICTOR THAT
  CAN LOAD THE BUILD, not the spare.  That does not move -- both forms need
  a 512K machine -- so the cost is margin on that machine and not reach.
*/
#ifndef KEEP_ICP
#define NOCKXXCHAR                      /* No SET SEND DOUBLE-CHAR    */
#endif /* KEEP_ICP */

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

  IT ALSO FITS THE MACHINE, AND THIS PARAGRAPH USED TO SAY THE OPPOSITE.
  It said the parser build asks DOS for 429KB while the largest block a
  program gets is 387KB, so it "loads on neither DOS".  Both halves are
  wrong.  The 387KB came from 396,224, which PORTING.md SS16x retracted --
  it was a FreeDOS measurement filed under an MS-DOS 3.1 heading, and
  Victor MS-DOS 3.1 actually gives 824,784 free at 896K, the model being
  free = installed RAM - 92,720.  And SS16y then BUILT the parser and
  LOADED IT ON THE REAL VICTOR, where it prints a parser's help text.

  So the honest statement is a machine size and not a wall:

      shipping build      needs 219,452 (214K)      smallest Victor 384K
      KEEP_ICP            needs 429,890 (419K)      smallest Victor 512K
      KEEP_ICP+KEEP_DEBUG needs 532,904 (520K)      smallest Victor 640K

  NOICP is therefore a DEFAULT and not a verdict.  It is off because the
  file-transfer milestone is what the port was built for and 384K reaches
  three times as many machines as 512K -- not because the parser cannot be
  had.  Anything that trades a user-facing feature away "because the parser
  build is only an instrument" has the intent backwards; see the NOCKXXCHAR
  comment above, which was written that way once and corrected.

  What the default build keeps is the milestone that matters -- the protocol
  engine, the file system, and the command-LINE parser in ckuusy.c, which
  is what actually moves a file:

      CKERMIT -l COM1 -b 9600 -s FOO.BIN      send
      CKERMIT -l COM1 -b 9600 -r              receive
      CKERMIT -l COM1 -b 9600 -x              server

  Four symbols owned by the removed modules are still referenced by code
  that survives; they are stubbed in ckvictor.c.
*/
/*
  KEEP_ICP builds the parser back in.  It is never defined by the makefile,
  so the default build is the small one, but it is a SUPPORTED
  CONFIGURATION and not an experiment -- SS16y built it, SS16z through
  SS16ad regression-tested it on the machine and fixed four defects it
  exposed, and SS1 item 7 of NEXT_SESSION.md is its remaining hardware leg.

      make -f victorow.mak clean
      make -f victorow.mak XFLAGS=-dKEEP_ICP ZT=-zt2048 sizes

  -zt2048 is not optional decoration: without it the near/far data
  threshold leaves DGROUP over the line.  And the receive ring must stay
  __near, or -zt moves it out of the group ckvisr.asm reaches through DS
  (PORTING.md SS16y).  KEEP_SPL adds the script language on top for a
  further ~209KB and is a separate question.
*/
#ifndef KEEP_ICP
#define NOICP                           /* No "C-Kermit>" prompt      */
#endif /* KEEP_ICP */

/*
  UPSTREAM EDIT 18's two variables, declared here because this header is
  force-included (-fi=ckvictor.h) and ckutio.c is stock upstream: the edit
  itself must not carry a declaration of anything Victor-specific, or it
  stops being one guarded block.  Both are DEFINED in ckvictor.c.

  v9k_bulkin selects the bulk arm at RUN TIME (--nobulk turns it off) so
  that the control leg and the treatment leg are the same binary -- §16ap's
  finding, and the only shape that leaves §16w's code-size sensitivity
  nothing to act on.  v9k_bulkn counts the runs the arm copied, and it is
  the only way to tell an arm that was switched off from an arm whose
  switch silently failed: equivalence cannot show the difference, because a
  correct arm returns the byte loop's answer either way.  Reported at exit
  as "v9k: bulk sel= n=".  See v9k/proofs/vttinl.c.
*/
extern int  v9k_bulkin;                 /* 1 = arm enabled, 0 = --nobulk */
extern long v9k_bulkn;                  /* Runs copied; 0 = never ran    */

/*
  nap() is declared here for the same reason: ckutio.c calls it from
  msleep()'s NAP arm and stock upstream carries no declaration of it,
  because on the systems that have one it comes from a system header.
  Without this the call is an implicit int(), which is a new warning in a
  file that has 18 of them and no room for a nineteenth.
*/
int nap(long);                          /* ckvictor.c section 1d      */

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

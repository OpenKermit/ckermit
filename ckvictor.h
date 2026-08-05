/*  C K V I C T O R . H  --  Build configuration for Victor 9000 / Sirius 1  */

/*
  Serial-only C-Kermit for the Victor 9000 (Sirius 1) under Victor MS-DOS.
  Two toolchains build it, from this one configuration:

      ia16-elf-gcc + newlib   medium model, far code, ONE near 64K DGROUP
      Open Watcom  wcc/wlink  large model, far code AND far data

  This header is force-included ahead of every source file:

      ia16-elf-gcc -mcmodel=medium -include ckvictor.h ...
      wcc -ml -fi=ckvictor.h ...

  Nothing else in the tree includes it, so it cannot affect any other
  platform.  It exists because the feature set is expressed as ~40 -D
  options and putting them on the command line makes the build unreadable.

  TARGET MODEL
    CPU            8088, real mode, 16-bit
    int            16 bits          long   32 bits
    code           far, multiple code segments, up to 1MB, in both models
    data           NEAR ONLY under ia16-elf-gcc, which has no compact/large/
                   huge model: .data + .bss + heap + stack all share one 64K
                   DGROUP.  Under Open Watcom's large model, string literals
                   go to far code (-zc) and malloc() is the far heap.

  The 64K data group is the binding constraint for this port -- absolutely
  under gcc, and still worth watching under Watcom.  Every size choice below
  exists to keep DGROUP occupancy down, and the numbers were measured on the
  gcc build.  Do not raise them without re-measuring; see PORTING.md SS9/SS9d.
*/

#ifndef CKVICTOR_H
#define CKVICTOR_H

/* ------------------------------------------------------------------ */
/* Platform identity                                                    */
/* ------------------------------------------------------------------ */
/*
  We present as UNIX + POSIX.  That is not a pretence: the newlib port
  supplies open/close/read/write/lseek/stat, a POSIX termios layer, and
  dirent, which is exactly the surface ckutio.c and ckufio.c use.  Claiming
  UNIX also makes ckcdeb.h define DYNAMIC, which is essential -- it turns
  the packet buffers into malloc'd pointers instead of >64K static arrays.
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

/* newlib already provides sig_t; suppress C-Kermit's own typedef.
   Open Watcom does not, so there C-Kermit's own typedef is the one we
   want -- see the Open Watcom section below. */
#ifndef __WATCOMC__
#ifndef CK_NO_SIG_T
#define CK_NO_SIG_T
#endif /* CK_NO_SIG_T */
#endif /* __WATCOMC__ */

/* ------------------------------------------------------------------ */
/* Open Watcom                                                          */
/* ------------------------------------------------------------------ */
/*
  Everything from here to the end of this section is inert under
  ia16-elf-gcc.  It exists because the port is built by two toolchains:

    ia16-elf-gcc + newlib   medium model, ONE near 64K DGROUP  (victor9k.mak)
    Open Watcom  wcc/wlink  large model, far code AND far data (victorow.mak)

  The Watcom experiment is about the constraint documented at NOICP below:
  under gcc every string literal is near, DGROUP overflows, and the
  interactive command parser had to be cut.  Watcom has a real large model,
  so this section is the price of finding out whether that buys the parser
  back.

  Most of what follows is header surgery.  ckvictor.h is force-included
  ahead of every module, so including a system header HERE and adjusting
  what it defined is the only place where the adjustment sticks: by the
  time ckufio.c gets to its own #include, the include guard has already
  fired and our edits are what it sees.  No upstream file is touched.
*/
#ifdef __WATCOMC__

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
  newlib declares all three, which is why the gcc build compiles without
  them being spelled out anywhere.

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
  not have), and it is unreachable for its own sake here.  Under newlib no
  such trick is needed -- SIGALRM is 13, NSIG is 32, and signal() stores it.
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
  nl_langinfo() and <langinfo.h>.  Watcom has neither; newlib has both,
  which is why ckutio.c's locale_dayname() compiles under gcc.  This is
  ckcdeb.h's own knob for saying so (ckcdeb.h ~7000), and the function it
  removes is only reachable from the date parser's locale path.
*/
#ifndef NO_NL_LANGINFO
#define NO_NL_LANGINFO
#endif /* NO_NL_LANGINFO */

/*
  The Unix surface Watcom does not declare -- the process model, the one
  terminal, and gettimeofday() for the floating-point transfer timers.
  newlib declares all of it and defines none of it; ckvictor.c defines it
  for both toolchains.  These two headers are the declarations Watcom is
  missing, and being force-included means ckvictor.c is checked against
  them too.  See victorow/ckowsys.h.
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
  The Watcom DOS runtime supplies these itself, so the stubs of the same
  name in ckvictor.c must not be compiled.  Each guard is the one that file
  already uses to let a real library win.  (opendir/readdir/closedir are in
  the same position, but they are a whole section rather than one stub;
  ckvictor.c switches those on __WATCOMC__ directly.)
*/
#define VICTOR_HAVE_EXEC                /* execl/execvp, <unistd.h>     */
#define VICTOR_HAVE_SLEEP               /* sleep(), <unistd.h>          */
#define VICTOR_HAVE_CREAT               /* creat(), <io.h>              */
#define VICTOR_HAVE_UTIME               /* utime(), <utime.h>           */
#define VICTOR_HAVE_UMASK               /* umask(), <io.h>              */

#endif /* __WATCOMC__ */

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
  CKMAXNAM from MAXNAMLEN, but ckcdeb.h is parsed before <dirent.h>, so
  MAXNAMLEN is not yet defined and it falls through to FILENAME_MAX --
  which newlib puts at 1024.  traverse() in ckufio.c then declares

      char nambuf[CKMAXNAM+4];

  as an AUTOMATIC, and traverse() is the recursive directory walk that holds
  one frame per directory level.  Measured with -fstack-usage:

      CKMAXNAM 1024 (default)   traverse = 1066 bytes/level
      CKMAXNAM 16               traverse =   98 bytes/level

  A depth-8 walk therefore costs 784 bytes of stack instead of 8528.  On a
  target whose entire stack shares one 64K DGROUP that is the difference
  between working and not.  This is the same class of hazard as SCANFILEBUF.

  16 is chosen against FAT 8.3: the longest legal name is 12 characters
  ("12345678.123"), so 16 leaves room and keeps the buffer even-sized.  This
  port does not do long filenames -- readdir() below returns what DOS
  FindFirst puts in the DTA, which is 8.3 and nothing else.
*/
#define CKMAXNAM 16

/*
  MAXNAMLEN sizes d_name[] inside struct dirent, and struct dirent doubles
  as the DOS Disk Transfer Area for our opendir()/readdir() (ckvictor.c).
  newlib's <sys/dirent.h> defaults it to 259 in anticipation of long-filename
  support that does not exist, making struct dirent 290 bytes.  DOS FindFirst
  writes exactly 13 bytes of name, so 12 is the honest value and makes the
  struct 43 bytes -- which is precisely the size of a DOS DTA.

  traverse() holds one open DIR per directory level, so this is 43 bytes per
  level of heap rather than 290.
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
#ifdef __WATCOMC__
#define V9K_RTYPE  int
#define V9K_RCOUNT unsigned
#else
#define V9K_RTYPE  _READ_WRITE_RETURN_TYPE
#define V9K_RCOUNT size_t
#endif /* __WATCOMC__ */

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
#ifdef __WATCOMC__
#define V9K_WTYPE  int
#define V9K_WCOUNT unsigned
#else
#define V9K_WTYPE  _READ_WRITE_RETURN_TYPE
#define V9K_WCOUNT size_t
#endif /* __WATCOMC__ */

#define write v9k_write

/*
  The uPD7201 receive ring (ckvictor.c SS1e).  It is the only new static
  array this port adds and it comes straight out of DGROUP, so it is here
  with the other size levers rather than buried in the driver.

  It has to cover the longest gap between two of C-Kermit's reads, not the
  longest packet: myfillbuf() drains it in one call and comes straight
  back, so the ring is only accumulating while Kermit is doing something
  else -- writing the last packet's data to a floppy, mostly.  512 bytes is
  533ms at 9600 bps and 133ms at 38400.  It is also what MS-DOS Kermit 3.13
  chose for this machine (msxv90.asm's "source" buffer, BUFSIZ).

  Must be a power of two: the head and tail pointers are masked with
  V9K_RXBUFSIZ-1, which is what lets the interrupt handler and the
  foreground share them with no critical section at all.
*/
#define V9K_RXBUFSIZ 512

/*
  Packet buffers.  With DYNAMIC these are malloc'd from the near heap, so
  they compete directly with everything else in DGROUP.

    SBSIZ/RBSIZ are the total buffer pools, carved at runtime into
    (window slots) x (negotiated packet length).

  9024/9050 (the DYNAMIC default) would take 18K of a 64K data group for
  packet buffers alone.

  These were 4096 each, and that did not survive contact with a real link.
  The heap is not a free-standing resource: it grows UP from the end of
  .bss while the stack grows DOWN from the top of the same 64K, and after
  the linker was done there were only 13,536 bytes for the two of them
  together (SS14).  Two 4096-byte pools plus s_pkt/r_pkt took essentially
  all of it, and C-Kermit said so on the Victor, in as many words:

      A:\>CKERMIT -s V9KTEST.COM
      fnlist: no memory for cmargbuf

  -- a malloc of CKMAXPATH+1, i.e. 129 bytes, failing outright.  The same
  exhaustion is why "-s *.COM" silently reported "No files": the expansion
  allocates too, and gets nothing.

  2048 each still carves, for example, a 2-slot window of 1024-byte long
  packets, which is more than a 38400 bps line needs, and the milestone
  (SS13 step 5) runs short packets with window 1 anyway.  Raise only with
  the linker's __heap_end_minimum figure in hand, not by eye.

  AND THEY ARE STILL TOO BIG FOR THE GCC BUILD.  2048/2048 is what the
  Watcom build transferred a file with (SS16d), but Watcom has a far heap
  outside DGROUP and gcc does not.  Under gcc the same numbers cost, at
  inibufs() time:

      bigbufp   malloc(SBSIZ + RBSIZ + 40)      4,136
      srvcmd    malloc(RBSIZ + 100)             2,148
      s_pkt, r_pkt  2 x 14 x MAXWS(32)            896
                                              -------
                                                7,180  of 12,808

  and the 5,628 left has to hold the stack as well.  It does not: SS16e
  measured the gcc build reaching the file-open step of a real transfer and
  failing there, with C-Kermit printing "TESTFILE.TXT: Not enough space" --
  newlib's fopen() wanting a FILE and a 1,024-byte BUFSIZ buffer and not
  getting them.  Halving both pools gives 3,072 of that back.

  So the two builds differ here, deliberately and for a reason that is a
  property of the toolchains and not of the port: near heap versus far heap.
  Everything else in this file is shared.  Both settings still satisfy the
  milestone -- dofast() carves RBSIZ/MAXSP window slots, so gcc gets one
  1,018-byte slot and Watcom two, and step 5 runs window 1 with short
  packets either way.  Step 8 (long packets, windows, streaming) is where
  the difference will start to show, and where the Watcom build's far heap
  stops being a footnote.
*/
#define MAXSP 1024                      /* Max long packet, send    */
#define MAXRP 1024                      /* Max long packet, receive */
#ifdef __WATCOMC__
#define SBSIZ 2048                      /* Send buffer pool         */
#define RBSIZ 2048                      /* Receive buffer pool      */
#else
/*
  512 each was tried as well, and is NOT what is here.  A wildcard send
  expands the pattern twice -- once in doarg() while parsing the command
  line and again in gnfile() when the protocol asks for the file -- and at
  1024 that left only 532 bytes of heap at the low-water mark.  Halving
  again gives back 1,536 (1,024 of bigbufp, 512 of srvcmd, which is sized
  from RBSIZ) and does take the headroom back to 2,068, comfortably where
  the transfer that worked was.  It did not make the wildcard send
  complete, so the change bought a number and no behaviour, and 1024 is
  the setting a finished transfer has actually been measured at (SS16e).
  See PORTING.md SS16f for what the remaining failure looks like.
*/
#define SBSIZ 1024                      /* Near heap: half as much  */
#define RBSIZ 1024
#endif /* __WATCOMC__ */

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
  keeping whatever it finally got.  That is sensible where the heap is
  large and cheap.  Here it is neither: DYNAMIC's default is 10,000 bytes
  against a gcc near heap of about 12,700 shared with the stack, so the
  expansion swallows the heap and every allocation after it fails.  What
  the user sees is "No files for -s" -- not because nothing matched, but
  because ckuusy.c could not get 2,000 bytes for the message that would
  have said so.  Measured on Victor MS-DOS 3.1: 212 bytes free at the
  low-water mark (PORTING.md SS16f).

  2048 holds 150 or so 8.3 names, which is more than a FAT directory on
  this machine can contain, and it is a fixed cost rather than "whatever
  was left".  Overriding it needs ckufio.c's #ifndef -- the seventh
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

  Never defined by either makefile.  Worth the DGROUP under Watcom, where
  -zc puts the format strings in far code; under gcc it is expensive.

  MEASURED, and it is why the gcc build has no debug log at all: with
  KEEP_DEBUG the objects alone come to 68,693 bytes of near data, 104.8% of
  DGROUP before libc adds anything, and the link fails with a page of
  "relocation truncated to fit".  The debug log is a Watcom-only instrument
  on this port.  (PORTING.md SS16e.)

  V9K_HEAPREPORT is the diagnostic that replaces it for the one question the
  gcc build actually needs answered -- how much room is left between the top
  of the heap and the stack.  Section 0e of ckvictor.c; costs nothing when
  off; also never set by a makefile:

      make -f victor9k.mak XFLAGS=-DV9K_HEAPREPORT
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

/* ------------------------------------------------------------------ */
/* The interactive command parser -- OFF, and this one hurts            */
/* ------------------------------------------------------------------ */
/*
  NOICP removes the "C-Kermit>" prompt.  It was the one thing this port
  most wanted to keep, and it is off because the program does not fit
  without it.  This is measured, not estimated:

                          .rodata   .data    .bss     near total
      with the parser      66,578  11,748  20,563        98,889
      NOICP                22,530   3,930  13,785        40,245
                                                 DGROUP =  65,536

  The trap is that .rodata -- every string literal in the program -- lives
  in DGROUP.  ia16-elf-gcc offers only tiny/small/medium models; there is
  no compact, large or huge model, so a "char *" is always a 16-bit near
  pointer and the string it points at must be inside the one 64K data
  group.  The only far-data mechanism is an explicit __far qualifier on
  each object, which would mean editing upstream source everywhere.

  The command parser's tables and messages are 43KB of that .rodata,
  concentrated in ckuus3-7.  Nothing short of removing them fits, and
  --gc-sections does not help: everything is reachable from the tables.

  What survives is exactly the milestone that matters -- the protocol
  engine, the file system, and the command-LINE parser in ckuusy.c, which
  is what actually moves a file:

      CKERMIT -l COM1 -b 9600 -s FOO.BIN      send
      CKERMIT -l COM1 -b 9600 -r              receive
      CKERMIT -l COM1 -b 9600 -x              server

  See PORTING.md SS9c.  Four symbols owned by the removed modules are
  still referenced by code that survives; they are stubbed in ckvictor.c.
*/
/*
  KEEP_ICP is the switch for re-testing that measurement.  It is never
  defined by either makefile; it exists so the experiment can be repeated
  with one -D and without editing this file:

      make -f victorow.mak clean
      make -f victorow.mak XFLAGS=-dKEEP_ICP sizes

  Under ia16-elf-gcc the answer is still no, for the reason above.  Under
  Open Watcom's large model the string literals are in far code segments
  and the answer is different; see PORTING.md.
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

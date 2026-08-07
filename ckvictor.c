/*  C K V I C T O R . C  --  Victor 9000 platform glue for C-Kermit  */

/*
  Serial-only C-Kermit for the Victor 9000 (Sirius 1) under Victor MS-DOS.

  This module supplies the small number of symbols that the portable
  C-Kermit modules reference but that neither the Open Watcom DOS runtime
  nor the modules we chose to leave out of the link can provide.  It is
  deliberately the ONLY Victor-specific C file: everything else in the
  build is unmodified upstream code.

  There are three kinds of thing here:

    1. Unix process-model calls that MS-DOS does not have (fork, exec,
       wait, uid/gid, job control).  C-Kermit only calls these on paths
       that the feature flags in ckvictor.h have already disabled, so
       these stubs exist to satisfy the linker and to fail loudly and
       safely if a path is ever reached that we did not anticipate.

    2. Symbols owned by modules we excluded from the link
       (ckucon.c/ckucns.c CONNECT, ckudia.c dialer, ckcnet.c networking).

    3. Console helpers that ckucmd.c now routes through coninc()/conchk()
       on this platform.  These are REAL and must be implemented against
       the Victor console; see the TODO block at the bottom.

  Every stub is wrapped in "#ifndef VICTOR_HAVE_<name>".  If a future
  runtime provides one, define that macro (e.g. -dVICTOR_HAVE_ALARM) and
  the duplicate here disappears.  The five that Open Watcom's own DOS
  runtime supplies -- exec, sleep, creat, utime, umask, plus a stat() that
  answers "." -- are not written out at all; see section 1a.
*/

/*
  ckvictor.h is force-included ahead of this line by victorow.mak, and it
  renames read() to v9k_read() and write() to v9k_write() for the whole
  build.  This file is where those two live and is the one place that still
  has to reach the real ones, so the renames are undone here -- before any
  header is pulled in, so that <unistd.h> / <io.h> declare read() and
  write() rather than redeclaring ours.  See ckvictor.h and section 0d.
*/
#undef read
#undef write

#include "ckcdeb.h"
#include "ckcker.h"

/*
  These give us pid_t / uid_t / gid_t / ssize_t so the definitions below
  match the declarations C-Kermit is compiled against exactly.  The Unix
  process calls it wants are declared in victorow/ckowsys.h and defined
  nowhere, which is why this file exists.
*/
#include <sys/types.h>
#include <unistd.h>
#include <sys/stat.h>
#include <pwd.h>
#include <dirent.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <time.h>
#include <utime.h>
#include <signal.h>                     /* Section 0d's alarm           */
#include <sys/ioctl.h>
#include <sys/termios.h>

/*
  This port reaches MS-DOS through the Open Watcom DOS runtime rather than
  through this file.  That runtime already implements open/read/write/lseek/
  stat, the console, and opendir/readdir/closedir over the FindFirst/FindNext
  DTA, and it ships intdos(), so the one INT 21h call still issued by hand
  here (section 0b, FIONREAD) needs no inline assembler.  <sys/utsname.h> is
  here because Watcom has no uname() and section 1d stubs one; see
  victorow/sys/utsname.h.
*/
#include <dos.h>
#include <stdarg.h>
#include <sys/utsname.h>

/* The one DOS function number this file still spells out (section 0b). */
#define DOS_CHK_STDIN   0x0b            /* Check standard input status  */

/*
  ckufio.c's "extern long timezone" is aliased to this by ckvictor.h,
  because Watcom's own timezone is declared __near and a bare extern in
  the large model is __far.  Nothing reads it: see the comment there.
*/
long v9k_timezone = 0L;


/* ------------------------------------------------------------------ */
/* 0b. Device input status, and ioctl -- FIONREAD and TIOCMGET          */
/* ------------------------------------------------------------------ */

/*
  The two sections that follow are the driver's customers, and the driver
  itself is section 1e, a long way down the file next to the termios half
  it belongs with.  These are its entry points, declared here so that 0b
  and 0d can be read in place.  Every one of them answers for the
  communications device only, and every one of them is inert -- returning
  0, or "not mine" -- until v9k_ser_install() has taken the chip over.
*/
extern int ttyfd;                       /* ckutio.c's serial descriptor */

_PROTOTYP( static int v9k_ser_active, (void) );        /* Is the chip ours?*/
_PROTOTYP( static int v9k_ser_count,  (void) );        /* Bytes in the ring*/
_PROTOTYP( static int v9k_ser_get, (char *, int) );    /* Out of the ring  */
_PROTOTYP( static int v9k_ser_put, (const char *, int) ); /* Polled write  */
_PROTOTYP( static int v9k_ser_mdm,    (void) );        /* RR0 -> TIOCM_*   */

/*
  Two polls, one for each kind of device, and then the one ioctl this port
  implements -- the reason victor/sys/ioctl.h exists.  in_chk() in ckutio.c
  calls ioctl(fd,FIONREAD,&n) and is the whole of conchk() and ttchk(); see
  that header for why the alternative was a SIGQUIT handler that cannot
  work on MS-DOS.

  Console: INT 21h AH=0Bh returns AL=0xFF if a character is waiting at
  standard input and AL=0x00 if not.

  Anything else: INT 21h AX=4406h (IOCTL, get input status) with the handle
  in BX, which answers the same question for any character device.  This is
  what makes the read in section 0d block, and it is the honest answer for
  the communications device in place of the flat 0 that stood here before.

  Both answer "whether", not "how many", so through those two the answer is
  at most 1.  That is what a poll of either device can honestly say, and it
  is enough for conchk(), whose callers test it against zero.  It was NOT
  enough for ttchk()'s other caller: sdata() in ckcfns.c only slides its
  window when ttchk() exceeds 4+bctu, so a 0/1 answer meant this port
  filled a window before reading ACKs.

  On the communications device neither is used any more.  Once section 1e
  has taken the uPD7201 over, FIONREAD is the depth of its receive ring --
  a real number, which is what SS12 and the milestone were waiting for --
  and TIOCMGET is RR0.  The two calls below remain the answer for every
  other device, and for the communications device before the driver is
  installed or if it never is.

  TIOCMGET matters more than it looks.  in_chk() -- which IS ttchk() --
  asks ttgmdm() for carrier BEFORE it asks how many bytes are waiting, so
  while ttgmdm() returned -3 the whole of FIONREAD was correct and
  unreachable for fd == ttyfd.  See victor/sys/ioctl.h.
*/

/* AH=44h is IOCTL; AL=06h is "get input status". */
#define DOS_IOCTL_INSTAT 0x4406

/*
  This is deliberately NOT kbhit(): the Watcom DOS kbhit() reads the BIOS
  keyboard, and this port is INT 21h only (Victor MS-DOS 3.1 has no
  IBM-compatible BIOS -- PORTING.md, and the whole reason one binary runs on
  two DOSes).  intdos() puts AH=0Bh behind a C interface.
*/
static int
dos_stdin_ready() {
    union REGS r;

    r.h.ah = DOS_CHK_STDIN;
    intdos(&r,&r);
    return((r.h.al) ? 1 : 0);
}

/*
  A carry return means DOS would not answer the question (bad handle, or a
  driver that does not implement the subfunction).  Reporting "ready" in
  that case is deliberate: the caller in section 0d responds by attempting
  the read, so a device whose status we cannot ask about degrades to being
  polled by read() itself instead of being waited on forever.
*/
static int
#ifdef CK_ANSIC
dos_dev_input_ready(int fd)
#else
dos_dev_input_ready(fd) int fd;
#endif /* CK_ANSIC */
{
    union REGS r;

    r.w.ax = DOS_IOCTL_INSTAT;
    r.w.bx = (unsigned int)fd;
    intdos(&r,&r);
    if (r.w.cflag)                      /* Cannot ask: say ready         */
      return(1);
    return((r.h.al) ? 1 : 0);
}

/*
  Written ANSI-only rather than in this file's usual dual-prototype style:
  a variadic function cannot be declared K&R and still be read with
  va_start.  The toolchain always defines CK_ANSIC, so the K&R arm would
  be dead code that never compiled.
*/
int
ioctl(int fd, int request, ...) {
    int * countp;
    va_list ap;

    if (request != FIONREAD && request != TIOCMGET) {
        errno = EINVAL;
        return(-1);
    }
    va_start(ap,request);
    countp = va_arg(ap,int *);
    va_end(ap);

    if (!countp) { errno = EFAULT; return(-1); }

    /*
      Modem signals come from the chip or from nowhere.  Refusing the call
      rather than inventing an answer is deliberate: ttgmdm() turns a -1
      into "I could not read the signals", which in_chk() is careful NOT to
      treat as a lost carrier, whereas a made-up zero would look exactly
      like a dropped line and close the connection.
    */
    if (request == TIOCMGET) {
        if (fd < 3 || fd != ttyfd || !v9k_ser_active()) {
            errno = ENOTTY;
            return(-1);
        }
        *countp = v9k_ser_mdm();
        return(0);
    }

    if (fd >= 3 && fd == ttyfd && v9k_ser_active())
      *countp = v9k_ser_count();        /* The real depth of the ring   */
    else if (fd == 0)                   /* Console: AH=0Bh              */
      *countp = dos_stdin_ready();
    else                                /* Any other device: AX=4406h   */
      *countp = dos_dev_input_ready(fd);

    return(0);
}

/* ------------------------------------------------------------------ */
/* 0d. Making read() block on the communications device                 */
/* ------------------------------------------------------------------ */

/*
  ckutio.c's myfillbuf() says what it needs, in its own comment:

      "The new myread()/mygetbuf() always gets something.  If it doesn't,
       then make it do so!"

  On Unix that is what a raw tty read does (VMIN=1, VTIME=0).  On MS-DOS a
  handle read of a character device with nothing pending returns 0 at once;
  myfillbuf() turns that into -3, mygetbuf() reports a dead line, and
  ttinl() closes the connection.  Measured symptom before this section
  existed: exactly one Send-Init packet on the wire and then "No files were
  transferred" (PORTING.md SS16a).

  ckutio.c is stock upstream, so the blocking has to happen underneath it.
  ckvictor.h renames read() to v9k_read() for every module in the build,
  and this is that function.  Everything that is not the communications
  device goes straight through to the library's read(), so Watcom's console
  handling and its text-mode translation are left exactly as they were --
  which is the reason for renaming rather than defining read() over the top
  of the library's.
*/

/*
  alarm() was a stub that returned 0 and never fired, on the reasoning that
  this port's timeouts come from C-Kermit's own protocol timer.  That is
  not true of the timeout that matters here.  ttinl() -- the packet reader
  -- arms alarm(timo) around a setjmp and expects SIGALRM to longjmp out of
  the read; that longjmp IS its timeout return of -1.  With alarm() dead
  there are only two ways out of a read that never completes, and ttinl()
  treats neither as a timeout: it closes the connection on a -3 whose errno
  is not EINTR, and it retries forever on one whose errno is EINTR.  So no
  packet would ever be retransmitted, and a link that dropped mid-transfer
  would hang instead of recovering.

  MS-DOS has no interval timer this port is allowed to use -- hooking INT
  1Ch is not INT 21h (hard rule 6) -- but it does not need one.  The only
  place this program can block is the poll below, so the alarm only has to
  be looked at there: record a deadline in alarm(), test it in the poll,
  and when it has passed, call the SIGALRM handler synchronously.  timerh()
  longjmps and ttinl() returns -1, exactly as on Unix.

  Resolution is whole seconds because time() is what both runtimes agree
  on, and because alarm()'s own argument is in seconds.  That resolution
  costs a second in the wrong direction, and an earlier version of this
  comment had the direction backwards.  time() is a floor: arm alarm(n)
  at real time T+0.9 and time() reports T, so a deadline of T+n is
  reached at real T+n -- only n-0.9 seconds later.  A deadline of time()+n
  therefore fires in (n-1, n], which is *early*, by up to a full second.

  That is not the noise the old comment assumed it was.  CK_TIMERS is on
  and rttflg defaults to 1, so rcvtimo comes from getrtt(), which is
  itself computed from gtimer()'s whole seconds; on the file-receiver
  path it lands on 3.  A 2-second worst case against the 4.2 seconds of
  line time a 3,999-byte packet takes at 9600 is a timeout that fires
  while the packet is still arriving.

  So the deadline is rounded up by one second, which turns (n-1, n] into
  (n, n+1] -- late, never early, which is the direction a protocol
  timeout wants to err in.  The fudge is added to the deadline and taken
  back off the returned time-remaining, so that the value ttoc() and
  ttinc() subtract from and re-arm with stays the number of seconds the
  caller actually asked for.
*/
#define V9K_ALARM_ROUNDUP ((time_t)1)   /* time()'s floor, compensated  */

static time_t v9k_alarm_at = (time_t)0; /* time() value it expires at   */
static int    v9k_alarm_on = 0;         /* Whether one is armed at all  */

/*
  Read the installed SIGALRM handler back by installing SIG_IGN and putting
  straight back whatever that returned.  Calling nothing unless a real
  function is there is the point of the exercise: with SIG_DFL installed,
  the default action for an unhandled signal is to terminate the program on
  some runtimes, and this one has to be able to time out harmlessly when
  nobody is listening.

  Returns 1 if the alarm has expired, 0 if it has not (or is not armed).
  If a handler was installed it does not return at all -- timerh() longjmps
  past us into ttinl().
*/
static int
v9k_alarm_check() {
    sig_t h;                            /* ckcdeb.h's, as ckutio.c uses */

    if (!v9k_alarm_on)                  /* alarm(0), or never armed --  */
      return(0);                        /* ttinl(timo=0): no timeout    */
    if (time((time_t *)0) < v9k_alarm_at)
      return(0);

    v9k_alarm_on = 0;                   /* One shot, as alarm(2) is     */
    debug(F101,"v9k alarm expired at","",(int)v9k_alarm_at);
    h = signal(SIGALRM,SIG_IGN);        /* Peek ...                     */
    if (h == SIG_ERR)                   /* ... signal() refused the     */
      return(1);                        /* number: nothing was changed  */
    signal(SIGALRM,h);                  /* ... otherwise put it back    */
    if (h != SIG_DFL && h != SIG_IGN)
      (*h)(SIGALRM);                    /* timerh(): does not return    */
    return(1);
}

/* ------------------------------------------------------------------ */
/* 0e. Where was the foreground when the ring filled?                   */
/* ------------------------------------------------------------------ */

/*
  PORTING.md SS16k and SS16l measured the same thing four times without being
  able to name it: rxpeak reads 500 to 547 across two ring sizes, two
  fixtures and longest-packets from 2,668 to 3,905 bytes.  At 9600 that is
  about half a second in which the handler below kept storing bytes and
  nobody took any out.  rxpeak says how big the pause is; it does not say
  what the foreground was doing, and every candidate -- the inter-packet
  file write, the console, the drain loop itself -- predicts the same
  high-water mark.

  So the handler latches one thing more.  The foreground keeps a single byte
  saying where it is, at the four places in this file that can hold it up,
  and the handler copies that byte at the moment it raises rxpeak.  Cost in
  the interrupt path: two stores, taken only when the high-water mark moves.
  No INT 21h anywhere near it, which is the whole point -- SS16k's lesson is
  that an instrument slow enough to starve the receive changes the number it
  was asked to report, and the debug log at 25ms a byte is exactly that.

  What each value means when it comes back out at exit:

    0  Upstream code.  Not inside anything below, so the time went on
       decoding, on stdio's own buffering, or somewhere else we do not own.
    1  The library's write(), for a descriptor that is not the comm device
       -- zoutdump()'s file write, V9K_OBUFSIZE bytes at a time (it was
       ckcker.h's OBUFSIZE, 1024, when this was written; SS1d below now sets
       the size and ckvictor.h says why).  The standing candidate, and
       v9k_wtagfd carries the descriptor so the console can be told from
       the file.
    2  v9k_ser_put(), the polled transmitter: an ACK on its way out.  Its
       spin is bounded at 60000 turns, which the comment there calls "a few
       tenths of a second" -- the same time scale as the stall, so it is a
       candidate and not just bookkeeping.
    3  The library's read(), again for something that is not the comm
       device.
    4  v9k_comm_read() itself.  This is the important one to be able to
       rule out: if the peak is latched here, Kermit was reading the whole
       time and simply could not keep up, which is a rate deficit rather
       than a stall -- the opposite of what SS16k concluded from rxpeak
       alone.
*/
#define V9K_TAG_NONE  0
#define V9K_TAG_WRITE 1
#define V9K_TAG_TTOL  2
#define V9K_TAG_READ  3
#define V9K_TAG_DRAIN 4

static volatile unsigned char v9k_wtag   = V9K_TAG_NONE;
static volatile unsigned int  v9k_wtagfd = 0;

/*
  Hundredths of a second since midnight, from INT 21h AH=2Ch -- Watcom's
  _dos_gettime, the same clock gettimeofday() reads a few hundred lines
  below and the only one this machine offers finer than a second.

  "Finer than a second" is all it is.  PORTING.md SS16n went back over every
  figure this file has ever printed -- six runs, three independent timers --
  and every one is a multiple of FIFTY hundredths, with no max ever reading
  anything but 0 or 50.  AH=2Ch has a hundredths field and MS-DOS 3.1 on
  this machine only ever puts 0 or 50 in it, so the real quantum is HALF A
  SECOND.

  Which is a warning about how to read anything timed with this, and SS16n
  has the arithmetic: a single interval shorter than the quantum reads 0 or
  50 according to whether it happened to cross a boundary, so no individual
  event here has ever been timed.  A SUM is different -- an interval of true
  length d < 0.5 crosses with probability d/0.5, so adding up many of them
  is an unbiased estimate of the total even though no term of it is.  Quote
  the tot= figures, never the max=.

  One INT 21h and no more, so it is affordable twice around a write() that
  happens 4 times in a 32K receive.  It is emphatically NOT affordable per
  byte, which is why the tag above counts rather than times.
*/
#define V9K_CENTIS_DAY 8640000L         /* 24 * 60 * 60 * 100           */

static long
v9k_centis() {
    struct dostime_t t;

    _dos_gettime(&t);
    return(((((long)t.hour * 60L + (long)t.minute) * 60L
             + (long)t.second) * 100L) + (long)t.hsecond);
}

/* Elapsed since t0, in hundredths, across midnight if it has to be. */
static long
#ifdef CK_ANSIC
v9k_centis_since(long t0)
#else
v9k_centis_since(t0) long t0;
#endif /* CK_ANSIC */
{
    long now = v9k_centis();

    return(now >= t0 ? now - t0 : now + V9K_CENTIS_DAY - t0);
}

/*
  And the other half of the same question: how long the writes we can see
  actually take.  Split by descriptor, because the two suspects are on
  opposite sides of it -- fd > 2 is the file zoutdump() is filling, fd <= 2
  is the console.
*/
static unsigned int v9k_wf_n = 0, v9k_wc_n = 0;     /* How many          */
static long v9k_wf_max = 0L, v9k_wc_max = 0L;       /* Worst one, centis */
static long v9k_wf_tot = 0L, v9k_wc_tot = 0L;       /* All of them       */
static unsigned int v9k_wf_maxn = 0;                /* Which write it was*/
static unsigned int v9k_wf_maxb = 0;                /* And how big       */

/*
  The gap that the protocol makes it possible to measure at all.

  With a window of one, the host is silent from the end of the packet it is
  sending until the ACK for it comes back -- so everything Kermit does
  BEFORE the ACK (decoding, the file write) is free, and only what it does
  AFTER can let the ring fill.  That makes "how long between putting an ACK
  on the wire and asking for the next byte" the exact quantity SS16l could
  not get at, and it is two INT 21h calls per packet to measure: one when
  the transmitter is done, one when the read comes back round.

  Timed here rather than in the handler because it is foreground-to-
  foreground; the handler's job is only to say how many bytes piled up
  while this was going on, which is rxpeak.
*/
static int  v9k_gap_pend = 0;           /* An ACK has just gone out     */
static long v9k_gap_at   = 0L;          /* When the transmitter finished*/
static unsigned int v9k_gap_n = 0;      /* How many gaps measured       */
static long v9k_gap_max  = 0L;          /* The worst, in hundredths     */
static long v9k_gap_tot  = 0L;          /* All of them                  */
static unsigned int v9k_gap_maxn = 0;   /* Which one was the worst      */

/*
  The wait itself.  Two ways to do it, and which one runs is the whole
  difference between PORTING.md SS16b and a working transfer.

  Once section 1e owns the uPD7201, this drains 1e's receive ring, which
  the interrupt handler has been filling all along -- so the bytes are
  already in memory before Kermit ever asks for them, and "block until
  something arrives" is just "spin until the ring is not empty".

  Before that, and for any line the driver did not take, it polls DOS for
  input status and reads only once DOS says there is something to read; a
  read issued blind is what returns 0 and starts the whole failure off.
  That is the path SS16b measured, and it delivers the first two bytes of
  every inbound packet and then nothing, twelve times out of twelve.  It is
  kept because it is the honest fallback for a device that is not ours, and
  because it is what runs if the install ever fails.

  A read that comes back with 0 anyway is not treated as EOF: the poll
  either raced or the device does not implement the status subfunction (see
  dos_dev_input_ready), and in both cases the right answer is to keep
  waiting.  A serial line has no EOF to report, so the only honest ways out
  of this loop are bytes, a hard error, or the alarm.
*/
static int
#ifdef CK_ANSIC
v9k_comm_read(int fd, void * buf, unsigned int n)
#else
v9k_comm_read(fd,buf,n) int fd; void * buf; unsigned int n;
#endif /* CK_ANSIC */
{
    int rc;

    if (v9k_gap_pend) {                 /* Section 0e: close the gap    */
        long dt;

        v9k_gap_pend = 0;
        dt = v9k_centis_since(v9k_gap_at);
        v9k_gap_n++;
        v9k_gap_tot += dt;
        if (dt > v9k_gap_max) {
            v9k_gap_max  = dt;
            v9k_gap_maxn = v9k_gap_n;   /* Countable against the pkt log */
        }
    }

    /*
      An experiment, off unless asked for: hand back at most this many
      bytes per call.  ckutio.c's myfillbuf() asks for MYBUFLEN (1024) and
      then processes the whole bufferful character by character before it
      asks again, so the ring fills for the length of that processing and
      the high-water mark should be MYBUFLEN times the ratio of the line
      rate to the processing rate -- which is what would make rxpeak the
      same 500-odd bytes at every packet length and every ring size, as it
      has been since SS16k.  Capping what we return shortens the interval
      between drains without touching upstream, so if that reading is right
      then rxpeak falls in proportion and nothing else changes.

      Build it with XFLAGS=-dV9K_RXCHUNK=256, the same one-flag idiom as
      -dDRPSIZ=90.
    */
#ifdef V9K_RXCHUNK
    if (n > V9K_RXCHUNK)
      n = V9K_RXCHUNK;
#endif /* V9K_RXCHUNK */

    v9k_wtag = V9K_TAG_DRAIN;           /* Section 0e: we are draining  */
    for (;;) {
        if (v9k_ser_active()) {
            rc = v9k_ser_get((char *)buf,(int)n);
            if (rc > 0) {
                v9k_wtag = V9K_TAG_NONE;
                return(rc);
            }
        } else if (dos_dev_input_ready(fd)) {
            rc = (int)read(fd,buf,n);   /* Undef'd above: the real one  */
            if (rc != 0) {              /* Bytes, or a genuine error    */
                v9k_wtag = V9K_TAG_NONE;
                return(rc);
            }
        }
        if (v9k_alarm_check()) {
            /*
              Only reached when the alarm expired with no handler to run.
              EINTR is the case mygetbuf() and ttinl() already document, so
              the caller retries -- and the retry blocks again rather than
              spinning, because the alarm cleared itself above.
            */
            v9k_wtag = V9K_TAG_NONE;
            errno = EINTR;
            return(-1);
        }
    }
}

/* Declared here rather than in ckvictor.h: everywhere else in the build the
   rename makes <unistd.h> / <io.h> declare it, and their spelling is the
   one it has to agree with. */
_PROTOTYP( V9K_RTYPE v9k_read, (int, void *, V9K_RCOUNT) );


V9K_RTYPE
#ifdef CK_ANSIC
v9k_read(int fd, void * buf, V9K_RCOUNT n)
#else
v9k_read(fd,buf,n) int fd; void * buf; V9K_RCOUNT n;
#endif /* CK_ANSIC */
{
    V9K_RTYPE rc;

    /*
      fd > 2 as well as fd == ttyfd because ttopen() sets ttyfd to 0 in
      remote mode, where the "line" is the console and section 0c owns it.
    */
    if (fd > 2 && fd == ttyfd)
      return((V9K_RTYPE)v9k_comm_read(fd,buf,(unsigned int)n));

    v9k_wtagfd = (unsigned int)fd;      /* Section 0e                   */
    v9k_wtag   = V9K_TAG_READ;
    rc = read(fd,buf,n);
    v9k_wtag   = V9K_TAG_NONE;
    return(rc);
}

/*
  And the other direction.  ttol() and ttoc() in ckutio.c are the only
  writers to the communications device and both of them call write(), so
  this is where C-Kermit's transmit path meets the transmitter in section
  1e.  Anything else -- DEBUG.LOG, the console, every file the protocol
  creates -- goes to the library's write() untouched, which is the same
  delegation v9k_read() does and for the same reason.

  Until the driver is installed this is a pure pass-through, so the OEM
  serial driver keeps carrying transmit exactly as it did in SS16a and SS16b,
  where it put a byte-correct Send-Init packet on the wire.
*/
_PROTOTYP( V9K_WTYPE v9k_write, (int, const void *, V9K_WCOUNT) );

V9K_WTYPE
#ifdef CK_ANSIC
v9k_write(int fd, const void * buf, V9K_WCOUNT n)
#else
v9k_write(fd,buf,n) int fd; const void * buf; V9K_WCOUNT n;
#endif /* CK_ANSIC */
{
    V9K_WTYPE rc;
    long t0, dt;

    if (fd > 2 && fd == ttyfd && v9k_ser_active()) {
        v9k_wtag = V9K_TAG_TTOL;        /* Section 0e                   */
        rc = (V9K_WTYPE)v9k_ser_put((const char *)buf,(int)n);
        v9k_wtag = V9K_TAG_NONE;
        /*
          v9k_ser_put() is polled and does not return until the last byte
          is in the chip, so this is as close to "the ACK is on the wire"
          as the foreground can stand; the gap starts here.
        */
        v9k_gap_at   = v9k_centis();
        v9k_gap_pend = 1;
        return(rc);
    }

    /*
      Everything else -- and this is the only place in the program that sees
      the file writes, so it is where they get timed.  Two INT 21h calls
      around a call that happens of the order of 32K/V9K_OBUFSIZE times in a
      32K receive: unmeasurable against the transfer, and the only way to put
      a number on the candidate PORTING.md SS16l left standing.  It is also
      what says whether V9K_OBUFSIZE bought anything, so it gets cheaper to
      run the bigger the buffer gets.
    */
    v9k_wtagfd = (unsigned int)fd;
    v9k_wtag   = V9K_TAG_WRITE;
    t0 = v9k_centis();
    rc = write(fd,buf,n);
    dt = v9k_centis_since(t0);
    v9k_wtag   = V9K_TAG_NONE;

    if (fd > 2) {                       /* A file: zoutdump(), usually  */
        v9k_wf_n++;
        v9k_wf_tot += dt;
        if (dt > v9k_wf_max) {
            v9k_wf_max  = dt;
            v9k_wf_maxn = v9k_wf_n;
            v9k_wf_maxb = (unsigned int)n;
        }
    } else {                            /* The console                  */
        v9k_wc_n++;
        v9k_wc_tot += dt;
        if (dt > v9k_wc_max)
          v9k_wc_max = dt;
    }
    return(rc);
}


/* ------------------------------------------------------------------ */
/* 2. Symbols from excluded modules                                     */
/* ------------------------------------------------------------------ */

/*
  CONNECT.  Not part of the first milestone -- the Victor build is for
  file transfer only.  ckucns.c (select-based) and ckucon.c (fork-based)
  are both unusable here: one needs select() on a tty, the other needs
  fork().  A future Victor CONNECT would be a small polling loop over
  ttinc()/coninc() and belongs in this file rather than in either of
  those modules.
*/
char *connv = "CONNECT Command for Victor 9000: not implemented";

int
conect() {
    printf("?CONNECT is not supported in this build.\n");
    printf(" This is a file-transfer-only C-Kermit for the Victor 9000.\n");
    return(-1);
}

/*
  Dialer.  ckudia.c is excluded (NODIAL); mdmtyp is the modem-type
  variable it would otherwise own.  0 == none/direct.
*/
int mdmtyp = 0;

/*
  Networking.  ckcnet.c compiles to almost nothing under NONET but
  ck_bracketaddr() is referenced from the command parser's address
  handling.  With no networking there is never an IPv6 literal to
  bracket, so copy through unchanged.
*/
VOID
#ifdef CK_ANSIC
ck_bracketaddr(char * s, int n)
#else
ck_bracketaddr(s,n) char * s; int n;
#endif /* CK_ANSIC */
{
    return;
}

/*
  Network-directory / variable lookup used by the command parser.  With
  NOSPL and NONET there are no variables to look up.
*/
char *
#ifdef CK_ANSIC
nvlook(char * s)
#else
nvlook(s) char * s;
#endif /* CK_ANSIC */
{
    return(NULL);
}

/* ------------------------------------------------------------------ */
/* 1. Unix process model -- absent on MS-DOS                            */
/* ------------------------------------------------------------------ */

/*
  MS-DOS is single-tasking and has no process hierarchy, no separate
  process image, and no notion of users.  Everything below returns the
  value that makes C-Kermit take the "not available / single user /
  I am the only process" branch.

  fork() returning -1 is the important one: any code that tries to spawn
  will see the failure and report it rather than running off into
  undefined behaviour.
*/

#ifndef VICTOR_HAVE_FORK
pid_t fork(void) { return((pid_t)-1); }
#endif

/* execl()/execvp() are not here: the Watcom DOS runtime has both, and on
   this port every caller is behind NOPUSH. */

#ifndef VICTOR_HAVE_WAIT
pid_t wait(int * statusp) { if (statusp) *statusp = 0; return((pid_t)-1); }
#endif

/*
  Identity.  Single-user machine: everyone is uid 0 / gid 0.  C-Kermit
  uses these mainly for file-permission display and for deciding whether
  it is running setuid, neither of which applies here.
*/
#ifndef VICTOR_HAVE_IDS
uid_t getuid(void)  { return((uid_t)0); }
uid_t geteuid(void) { return((uid_t)0); }
gid_t getgid(void)  { return((gid_t)0); }
gid_t getegid(void) { return((gid_t)0); }
int setuid(uid_t u) { return(0); }
int setgid(gid_t g) { return(0); }
#endif

/*
  getpid() is NOT here: libdos-m.a supplies one (it probes INT 21h AH=87h
  with the carry flag pre-set, so it degrades safely on a DOS that does not
  implement it).  Defining our own as well is a duplicate-symbol error at
  link time -- verified by comparing this object's symbol table against the
  archive rather than by waiting for the linker to say so.

  The rest of the group has no library equivalent and stays ours.  There is
  no process hierarchy and no job control, so "I am my own process group and
  I own the terminal" is both the true answer and the one that makes
  C-Kermit take the right branch.
*/
#ifndef VICTOR_HAVE_PIDS
pid_t getppid(void) { return((pid_t)0); }
pid_t getpgrp(void) { return((pid_t)1); }
pid_t tcgetpgrp(int f) { return((pid_t)1); }
#endif

/*
  Password database.  There is none.  Returning NULL makes C-Kermit fall
  back to environment variables / defaults for the user name and home
  directory.
*/
#ifndef VICTOR_HAVE_GETPW
struct passwd * getpwnam(const char * nam) { return((struct passwd *)0); }
struct passwd * getpwuid(uid_t uid)        { return((struct passwd *)0); }
#endif

#ifndef VICTOR_HAVE_GETLOGIN
char * getlogin(void) { return((char *)0); }
#endif

/*
  Terminal naming.  There is exactly one console.
*/
#ifndef VICTOR_HAVE_TTYNAME
char * ttyname(int f) { return("CON:"); }
char *
ctermid(char * s) {
    if (s) { s[0]='C'; s[1]='O'; s[2]='N'; s[3]=':'; s[4]='\0'; return(s); }
    return("CON:");
}
#endif

/*
  alarm().  Records a deadline for section 0d to notice; there is no
  interval timer behind it, and section 0d explains why there does not need
  to be.  The return value is the time left on any previous alarm, which
  ttinc() uses to restore an outer timeout after an inner one.
*/
#ifndef VICTOR_HAVE_ALARM
unsigned
#ifdef CK_ANSIC
alarm(unsigned secs)
#else
alarm(secs) unsigned secs;
#endif /* CK_ANSIC */
{
    time_t now = time((time_t *)0);
    unsigned left = 0;

    /* Compared rather than subtracted: Watcom's time_t is unsigned, so a
       deadline already in the past would wrap into a huge "time left".
       The roundup comes back off here so that callers which subtract from
       this value and re-arm -- ttoc() does exactly that -- are working in
       the seconds they asked for rather than in ours. */
    if (v9k_alarm_on && v9k_alarm_at > now + V9K_ALARM_ROUNDUP)
      left = (unsigned)(v9k_alarm_at - now - V9K_ALARM_ROUNDUP);

    if (secs) {
        v9k_alarm_at = now + (time_t)secs + V9K_ALARM_ROUNDUP;
        v9k_alarm_on = 1;
    } else {
        v9k_alarm_on = 0;
    }
    debug(F111,"v9k alarm secs/at",ckitoa((int)secs),(int)v9k_alarm_at);
    return(left);
}
#endif

/*
  sysconf(): no runtime configuration query.
*/

#ifndef VICTOR_HAVE_SYSCONF
long sysconf(int name) { return(-1L); }
#endif

/*
  putenv() and dup2() are NOT here either -- both are in libdos-m.a (dup2
  over INT 21h AH=46h).  They were stubbed in an earlier draft of this file,
  before the library's contents had been examined; keeping the stubs would
  now be a link error.

  Filesystem calls with no FAT equivalent.
*/
/*
  readlink() is declared without __restrict: Open Watcom's C is C89 and has
  no such keyword, and it has no declaration of readlink() either, so
  victorow/ckowsys.h declares the plain form and this has to match it.
*/
#ifndef VICTOR_HAVE_READLINK
ssize_t
readlink(const char * path, char * buf, size_t n) {
    return((ssize_t)-1);
}
#endif

/*
  umask(), sleep(), creat(), utime() and stat() are NOT here.  The Watcom
  DOS runtime supplies all five, and its stat() answers "." and "./" --
  measured on Victor MS-DOS 3.1, and the reason wildcard expansion works at
  all, since traverse() in ckufio.c begins every walk by asking xisdir()
  about "./" (PORTING.md SS16f).
*/

/* ------------------------------------------------------------------ */
/* 1b. termios -- the serial driver's control surface, software half    */
/* ------------------------------------------------------------------ */

/*
  See victor/sys/termios.h for the design, and PORTING.md SS11a for how
  this reaches the hardware.

  Two halves.  The SOFTWARE half is the cached struct termios, the B*
  speed codes and the bookkeeping ckutio.c drives; it is what lets the
  console share this code, where there is nothing to program.  The
  HARDWARE half applies the cached settings to the uPD7201 and the 8253
  by handing the OEM serial driver a 17-byte control block through DOS
  IOCTL -- speed, character width, stop bits, parity, DTR and RTS.

  It does that with the descriptor ttopen() already left in ttyfd.  There
  is no second open, no interrupt vector and no memory-mapped access: the
  whole of this section is INT 21h, which is why it could be built and
  tested before the driver in SS11b exists.

  This is MS-DOS Kermit 3.13's model, not an invention.  msxv90.asm drives
  this same chip on this same machine and uses its SERIALA handle for
  exactly three things -- open, close, and this IOCTL.  It never reads or
  writes data through it.  PORTING.md SS16b measured what happens when you
  do: the first two bytes of every inbound packet arrive and the rest
  never does.  So the OEM driver is a configuration channel here, and the
  data path is SS11b's problem.

  Nothing below moves a byte.

  ckutio.c keeps several struct termios of its own (ttold, ttraw, ttcur,
  ...) and treats tcgetattr as "read back what I set".  Caching one
  current setting here matches that and costs 32 bytes.

  That last paragraph was true of the whole section until section 1e
  existed.  It still is of everything except the four calls below that now
  reach it: tcsetattr() ends by installing the driver, and tcflush(),
  tcdrain() and the release path are 1e's.  Nothing here moves a byte; 1e
  does.
*/
_PROTOTYP( static int  v9k_ser_install,  (int) );
_PROTOTYP( static VOID v9k_ser_reenable, (void) );
_PROTOTYP( static VOID v9k_ser_release,  (void) );
_PROTOTYP( static VOID v9k_ser_flush,    (void) );
_PROTOTYP( static VOID v9k_ser_drain,    (void) );
_PROTOTYP( static VOID v9k_ser_selchan,  (void) );
_PROTOTYP( static VOID v9k_ser_progline,
           (unsigned char, unsigned char, unsigned char, unsigned int) );

/*
  The driver's control block.  AH=44h, AL=02h to read it and AL=03h to
  write it, BX = handle, CX = 17, DS:DX = the block.  Layout from
  msxv90.asm's "pval" structure, which cites Systems Programmers Toolkit
  II, Appendix A; that appendix has since been read directly and agrees
  field for field.  The nine CR bytes are the uPD7201's write registers;
  on channel A, CR2A is its WR2 and CR2B is channel B's, which the OEM
  documentation names the interrupt vector.

  The four 16-bit fields come first and the nine bytes after, so the
  struct has no interior padding; the trailing pad to an even size is why
  the length below is a literal 17 rather than sizeof.

  Appendix A says to pass CX = 9, which is the count of CR bytes and not
  the size of anything it describes -- its own field list adds up to the
  17 below.  17 is what msxv90.asm passes and what PORTING.md SS11a
  measured working on Victor MS-DOS 3.1.  Do not "correct" it to 9.

  Note also that AL=02h does NOT read the chip.  Appendix A: "when a
  request is made to set the port, the configuration information is
  saved.  Then if the current configuration is requested the parameter
  block last used to set the port is returned to you."  So a read returns
  the driver's cache of its own last write.  That is still exactly what
  the read-modify-write in tcsetattr wants -- the driver applies the whole
  block, so preserving the fields we do not set preserves what it will
  apply -- but nothing that comes back from here is evidence about the
  state of the uPD7201.  Section 1e reads the chip when that is the
  question.
*/

#define V9K_IOCTL_RDCTL 0x4402          /* Receive control data         */
#define V9K_IOCTL_WRCTL 0x4403          /* Send control data            */
#define V9K_PVAL_LEN    17              /* Bytes DOS moves either way   */

struct v9k_portval {
    unsigned short stype;               /* 0011h = port access          */
    unsigned short status;              /* 0 = ok; see v9k_portval_io   */
    unsigned short blocktype;           /* 0000h = serial               */
    unsigned short baudr;               /* 8253 DIVISOR, not a baud rate*/
    unsigned char  cr0;
    unsigned char  cr1;                 /* WR1: interrupt enables       */
    unsigned char  cr2a;                /* WR2: interrupt mode          */
    unsigned char  cr2b;                /* WR2 ch B: interrupt vector   */
    unsigned char  cr3;                 /* WR3: Rx width, Rx enable     */
    unsigned char  cr4;                 /* WR4: clock, stop bits, parity*/
    unsigned char  cr5;                 /* WR5: Tx width/enable,DTR,RTS */
    unsigned char  cr6;                 /* WR6: SYNC character          */
    unsigned char  cr7;                 /* WR7: SYNC character          */
};

/*
  Read or write the block.  Returns 0, or -1 with errno set if the driver
  will not answer -- which is not fatal and is handled at the one call
  site.

  There are TWO failure channels here and only one of them is the carry
  flag.  Carry means DOS itself refused the call, and AX is the DOS error.
  The status word in the block is the driver's own, and Appendix A defines
  it: false (0) if no error, 01h for an invalid function, -1 for an
  invalid type.  It is returned with CARRY CLEAR.

  That second channel is not a formality.  PORTING.md SS11a spent three
  runs discovering that a read issued with stype = 0 comes back carry-
  clear with the block untouched; the driver was reporting that as
  status = -1 the whole time and this code was not looking.  It is also
  the only way we would ever learn that a divisor outside the OEM's
  documented range (Appendix A stops at 19.2k; we offer 38.4k and 76.8k)
  had been rejected.
*/
static int
#ifdef CK_ANSIC
v9k_portval_io(int fd, int wr, struct v9k_portval * p)
#else
v9k_portval_io(fd,wr,p) int fd; int wr; struct v9k_portval * p;
#endif /* CK_ANSIC */
{
    union REGS r;
    struct SREGS sr;

    segread(&sr);
    r.w.ax = (unsigned int)(wr ? V9K_IOCTL_WRCTL : V9K_IOCTL_RDCTL);
    r.w.bx = (unsigned int)fd;
    r.w.cx = (unsigned int)V9K_PVAL_LEN;
    r.w.dx = FP_OFF(p);                 /* Large model: p is already far*/
    sr.ds  = FP_SEG(p);
    intdosx(&r,&r,&sr);
    if (r.w.cflag) {
        debug(F111,"v9k_portval_io DOS error",wr ? "write" : "read",
              (int)r.w.ax);
        errno = (int)r.w.ax;
        return(-1);
    }
    if (p->status) {                    /* Carry clear and still failed */
        debug(F111,"v9k_portval_io driver status",wr ? "write" : "read",
              (int)p->status);
        errno = EINVAL;
        return(-1);
    }
    return(0);
}

/*
  B* code -> 8253 divisor.  Indexed by the ordinals in sys/termios.h, so
  the order of the two lists has to stay in step.

  These are msxv90.asm's "bddat" values, which vickermit.c reproduces
  byte for byte; the rule behind them is 78125/baud.  See sys/termios.h
  for why the numerator is 78125 and not the 76800 an earlier revision
  assumed.

  B200 was the one entry neither of those two tables had, and it used to
  be round(78125/200) = 391.  Systems Programmers Toolkit II, Appendix A
  prints the OEM driver's own table and it says 390 (0186h), so that is
  what is here now: matching what shipped beats matching the arithmetic,
  and 78125/390 is 200.3 bps either way.

  Appendix A also prints 1.8k as 26h = 38, and that one is NOT taken.
  78125/38 is 2056 bps -- faster than the same table's 2.0k entry (27h =
  39, 2003 bps) while labelled slower -- where 2Bh = 43 gives 1817.  A
  transcription error, and 43 is what stays.  Appendix A's table stops at
  19.2k; B38400 and B76800 below are msxv90.asm's and are outside
  anything the OEM documents, which is one of the reasons
  v9k_portval_io() now reads the driver's status word.

  B0 is not a speed -- POSIX gives it the meaning "hang up" -- so its
  entry is never used; tcsetattr drops DTR and RTS and leaves the divisor
  alone, which is how msxv90.asm's SERHNG implements HANGUP.
*/
static unsigned int v9k_divisor[] = {
       0,                               /* B0     hang up               */
    1562, 1041,  710,  580,  520,       /* B50   B75   B110  B134  B150 */
     390,  260,  130,   65,   43,       /* B200  B300  B600  B1200 B1800*/
      32,   16,    8,    4,    2,       /* B2400 B4800 B9600 B19200     */
                                        /*                       B38400 */
       1                                /* B76800                       */
};

/*
  The last divisor we actually programmed.  The hang-up path changes the
  modem lines and must NOT change the speed, so it has to put back a
  divisor rather than leave the field at whatever is in the block.

  The read does round-trip "baudr" correctly -- PORTING.md SS11a measured 8
  coming back -- but only when the request is well formed, and a
  malformed one returns carry-clear and an untouched block.  A silent
  failure that leaves a stale value in a field we then write into the 8253
  is not worth the risk when the value is this cheap to remember.
  Initialised to 9600, which is what ttopen() sets before anything can
  hang up.
*/
static unsigned int v9k_lastdiv = 8;

/*
  And the WR5 we last programmed, for the same reason: tcsendbreak has to
  set one bit and put the register back, and it cannot learn the other
  seven bits from a read it does not trust.  EAh is the chip's 8-bit,
  transmitter-enabled, DTR-and-RTS-asserted state, which is both what
  msxv90.asm programs and what tcsetattr computes for CS8.
*/
static unsigned char v9k_lastcr5 = 0xea;

static struct termios victor_ttcur = {
    0,                                  /* c_iflag: raw                 */
    0,                                  /* c_oflag: no processing       */
    CS8 | CREAD | CLOCAL,               /* c_cflag: 8N1, no modem ctl   */
    0,                                  /* c_lflag: no echo, no canon   */
    { 0 },                              /* c_cc                         */
    B9600,                              /* c_ispeed                     */
    B9600                               /* c_ospeed                     */
};

int
#ifdef CK_ANSIC
tcgetattr(int fd, struct termios * t)
#else
tcgetattr(fd,t) int fd; struct termios * t;
#endif /* CK_ANSIC */
{
    if (!t) { errno = EFAULT; return(-1); }
    *t = victor_ttcur;                  /* Cached, not read from chip   */
    return(0);
}

int
#ifdef CK_ANSIC
tcsetattr(int fd, int action, const struct termios * t)
#else
tcsetattr(fd,action,t) int fd; int action; const struct termios * t;
#endif /* CK_ANSIC */
{
    struct v9k_portval pv;
    unsigned int width, divisor;
    unsigned char cr3, cr4, cr5;
    int ok;

    if (!t) { errno = EFAULT; return(-1); }
    victor_ttcur = *t;

    /*
      The console goes through this same call -- concb()/conres() in
      ckutio.c keep their own struct termios -- and there is nothing to
      program there.  Only the communications device has a uPD7201 behind
      it.  ttopen() sets ttyfd to 0 when the line IS the console, so the
      test has to exclude the standard descriptors as well; section 0d
      makes the same distinction for the same reason.
    */
    if (fd < 3 || fd != ttyfd)
      return(0);

    if (t->c_ospeed > B76800) { errno = EINVAL; return(-1); }

    /*
      Rx and Tx character width share an encoding on this chip and it is
      not the obvious one: 00 is 5 bits, 01 is SEVEN, 10 is SIX and 11 is
      8.  It sits at WR3 bits 7-6 and at WR5 bits 6-5.
    */
    switch (t->c_cflag & CSIZE) {
      case CS5: width = 0; break;
      case CS6: width = 2; break;
      case CS7: width = 1; break;
      default:  width = 3; break;       /* CS8 -- what Kermit always uses*/
    }
    cr3 = (unsigned char)((width << 6)
                          | ((t->c_cflag & CREAD) ? 0x01 : 0x00));
    cr5 = (unsigned char)((width << 5)
                          | 0x08                /* Transmitter enable   */
                          | 0x80                /* DTR asserted         */
                          | 0x02);              /* RTS asserted         */
    cr4 = (unsigned char)(0x40                  /* x16 clock            */
                          | ((t->c_cflag & CSTOPB) ? 0x0c : 0x04));
    if (t->c_cflag & PARENB) {
        cr4 |= 0x01;                            /* Parity enable        */
        if (!(t->c_cflag & PARODD))
          cr4 |= 0x02;                          /* 1 is EVEN, 0 is odd  */
    }

    /*
      B0 means hang up, so drop DTR and RTS and leave the divisor alone.
      3.13's SERHNG is the same two bits, and ckutio.c's tthang() reaches
      it the same way: set B0, sleep, set the speed back.
    */
    if (t->c_ospeed == B0) {
        cr5 &= 0x7d;
        divisor = v9k_lastdiv;          /* Keep the speed, not the junk */
    } else {
        divisor = v9k_divisor[t->c_ospeed];
        v9k_lastdiv = divisor;
    }
    v9k_lastcr5 = cr5;

    /*
      Read-modify-write, so that whatever the driver last set in the
      fields we do not understand survives.  Note "last set", not "has":
      the read returns the driver's cache of its own last write, not the
      chip (Appendix A, quoted at v9k_portval_io).  That is the right
      thing to preserve here anyway, because the write applies the whole
      block -- but it means no value that comes back below is evidence
      about the uPD7201.

      Zero it first so that nothing uninitialised can ever be written back,
      then stamp the two header words BEFORE the read.  They are not output
      fields: they are how the request identifies itself, and msxv90.asm's
      "pval" carries stype = 0011h as a structure default on the block it
      hands to the read as well as the write.  Appendix A says the same --
      "the type is always 11 hexadecimal" -- and getting it wrong returns
      a block of nothing with the carry clear and the complaint in the
      status word, which is measured in PORTING.md SS11a.

      CR1 and CR2A are deliberately left as they were read.  CR1 is the
      interrupt enable and section 1e owns it now, at the chip, because
      3.13 found this IOCTL does not apply it; every path out of here ends
      by putting it back.  CR2A is the interrupt mode, and 1e's install
      explains why it is left alone.
    */
    memset((char *)&pv,0,sizeof(pv));
    pv.stype     = 0x0011;              /* Port access                  */
    pv.blocktype = 0x0000;              /* Serial                       */

    ok = (v9k_portval_io(fd,0,&pv) < 0) ? 0 : 1;
    if (!ok) {
        debug(F101,"tcsetattr IOCTL 4402 failed","",errno);
    } else {
        debug(F111,"tcsetattr read-back cr1/cr2a",
              ckitoa((int)pv.cr1),(int)pv.cr2a);
        debug(F111,"tcsetattr read-back cr4/cr5",
              ckitoa((int)pv.cr4),(int)pv.cr5);
        debug(F101,"tcsetattr read-back baudr","",(int)pv.baudr);

        pv.baudr = divisor;
        pv.cr3   = cr3;
        pv.cr4   = cr4;
        pv.cr5   = cr5;
        if (v9k_portval_io(fd,1,&pv) < 0) {
            debug(F101,"tcsetattr IOCTL 4403 failed","",errno);
            ok = 0;
        } else
          debug(F101,"tcsetattr divisor","",(int)divisor);
    }

    /*
      If the driver would not answer, program the chip ourselves.  MS-DOS
      Kermit 3.13 has exactly this fallback, and it is not hypothetical
      here: SS11a measured both IOCTL subfunctions working on Victor MS-DOS
      3.1, and nobody has measured FreeDOS for Victor, which this binary is
      also meant to run on.  Failing to program the line used to mean
      running at whatever speed the driver was already set to; now that
      section 1e owns the chip, it means programming it directly.  Either
      way it is not a reason to refuse to open the line -- ttopen() treats
      a -1 from here as a failure to open at all.
    */
    if (!ok)
      v9k_ser_progline(cr3,cr4,cr5,(t->c_ospeed == B0) ? 0 : divisor);

    /*
      Last, take the chip over, or put back the receive-interrupt enable
      that the IOCTL write or the reset above may just have cleared.  This
      is the one place C-Kermit is guaranteed to reach with the descriptor
      open and the line programmed, which is why the install lives here
      rather than behind a hook of its own.
    */
    if (v9k_ser_active())
      v9k_ser_reenable();
    else
      v9k_ser_install(fd);
    return(0);
}

speed_t
#ifdef CK_ANSIC
cfgetospeed(const struct termios * t)
#else
cfgetospeed(t) const struct termios * t;
#endif /* CK_ANSIC */
{
    return(t ? t->c_ospeed : (speed_t)B0);
}

speed_t
#ifdef CK_ANSIC
cfgetispeed(const struct termios * t)
#else
cfgetispeed(t) const struct termios * t;
#endif /* CK_ANSIC */
{
    return(t ? t->c_ispeed : (speed_t)B0);
}

/*
  The Victor drives both directions from one 8253 divisor, so split
  speeds are not representable.  Setting either sets both; ckutio.c only
  ever sets them to the same value.
*/
int
#ifdef CK_ANSIC
cfsetospeed(struct termios * t, speed_t speed)
#else
cfsetospeed(t,speed) struct termios * t; speed_t speed;
#endif /* CK_ANSIC */
{
    if (!t) { errno = EFAULT; return(-1); }
    if (speed > B76800) { errno = EINVAL; return(-1); }
    t->c_ospeed = t->c_ispeed = speed;
    return(0);
}

int
#ifdef CK_ANSIC
cfsetispeed(struct termios * t, speed_t speed)
#else
cfsetispeed(t,speed) struct termios * t; speed_t speed;
#endif /* CK_ANSIC */
{
    return(cfsetospeed(t,speed));
}

int
#ifdef CK_ANSIC
tcflush(int fd, int queue)
#else
tcflush(fd,queue) int fd; int queue;
#endif /* CK_ANSIC */
{
    /*
      Only the input queue exists to be flushed.  The transmitter is polled
      (section 1e) so there is never anything queued in this direction --
      v9k_ser_put() does not return until the last byte is in the chip.
      TCOFLUSH and the output half of TCIOFLUSH are therefore satisfied by
      doing nothing, not ignored.
    */
    if (fd < 3 || fd != ttyfd)
      return(0);
    if (queue == TCIFLUSH || queue == TCIOFLUSH)
      v9k_ser_flush();
    return(0);
}

int
#ifdef CK_ANSIC
tcdrain(int fd)
#else
tcdrain(fd) int fd;
#endif /* CK_ANSIC */
{
    if (fd < 3 || fd != ttyfd)
      return(0);
    v9k_ser_drain();                    /* RR1 bit 0: transmitter empty */
    return(0);
}

int
#ifdef CK_ANSIC
tcflow(int fd, int action)
#else
tcflow(fd,action) int fd; int action;
#endif /* CK_ANSIC */
{
    /*
      Still a stub, and now deliberately so rather than for want of a
      driver.  ttoc() calls tcflow(TCOON) only when a single-character
      write has timed out and SET FLOW is XON/XOFF, to unstick a
      transmitter it thinks is held off by an XOFF -- and this port has no
      interrupt-level flow control to hold it off with (section 1e).  With
      one channel, a window of 1 and a 512-byte ring there is nothing yet
      for a water mark to protect.  If streaming ever goes in, this and
      the ISR's high/low marks arrive together.
    */
    return(0);
}

int
#ifdef CK_ANSIC
tcsendbreak(int fd, int duration)
#else
tcsendbreak(fd,duration) int fd; int duration;
#endif /* CK_ANSIC */
{
    struct v9k_portval pv;

    if (fd < 3 || fd != ttyfd)          /* See tcsetattr for the test   */
      return(0);

    memset((char *)&pv,0,sizeof(pv));
    pv.stype     = 0x0011;              /* Before the read -- see above */
    pv.blocktype = 0x0000;
    if (v9k_portval_io(fd,0,&pv) < 0)
      return(0);
    pv.baudr     = v9k_lastdiv;         /* Do not disturb the speed     */

    /*
      WR5 bit 4 holds the transmit data line low; the chip keeps it there
      until the bit is cleared, so the duration is ours to time.  POSIX
      says a zero duration means "at least a quarter of a second"; 275ms
      is what 3.13's SENDBR waits.
    */
    pv.cr5 = (unsigned char)(v9k_lastcr5 | 0x10);
    if (v9k_portval_io(fd,1,&pv) < 0)
      return(0);
    msleep(duration > 0 ? duration : 275);
    pv.cr5 = v9k_lastcr5;
    return((v9k_portval_io(fd,1,&pv) < 0) ? -1 : 0);
}

/* ------------------------------------------------------------------ */
/* 1e. The uPD7201 data path -- our interrupt, our ring, our transmit   */
/* ------------------------------------------------------------------ */

/*
  Section 1b configures the line through the OEM serial driver.  This
  section moves the bytes, and it does not use the OEM driver at all: it
  talks to the uPD7201 at its memory-mapped address, hooks the interrupt
  the 8259 raises for it, and keeps a receive ring of its own.  Together
  they are PORTING.md SS11's two halves, and the split is MS-DOS Kermit
  3.13's -- msxv90.asm opens SERIALA, uses the handle for IOCTL and for
  nothing else, and puts the data path here.

  The reason it has to be here is measured, not theoretical.  SS16b and
  SS16a put a byte-correct Send-Init packet on the wire through the OEM
  driver's write() and then read the reply through its read(): twelve
  reads, every one returning exactly two bytes, three separate runs, on a
  line whose registers SS11a had just programmed and read back to confirm.
  The OEM driver transmits and cannot receive.  3.13's authors reached the
  same conclusion with the same hardware in 1986.

  What is here:

    - an interrupt handler on IVT slot 41h that empties the receiver into
      a 512-byte ring, and resets the chip's error latch when it has to;
    - a polled transmitter, because transmit was never the broken half and
      because a receive-only interrupt is the smaller thing to get right;
    - the real answers to FIONREAD (the depth of the ring) and TIOCMGET
      (RR0), which is what makes ttchk() mean something for the first time;
    - install and release, and the direct-to-the-chip fallback for a DOS
      whose serial driver does not implement the SS11a IOCTL.

  Two things it deliberately does not have.

  There is NO STACK SWITCH.  A C interrupt handler runs on whatever stack
  it interrupted, and the compiler will not give us one (PORTING.md SS11b);
  a dedicated stack would have to come out of the same 64K DGROUP that
  already holds the main stack.  3.13's SERINT does not switch
  either, on this machine, and it shipped.  The handler below holds no
  arrays, calls nothing, and its frame is reported by -fstack-usage next to
  every other function in the build -- which is the number to watch if this
  ever turns out to be the wrong call.

  There is NO INTERRUPT-LEVEL FLOW CONTROL.  3.13 sends XOFF from inside
  SERINT at a 3/4-full water mark.  With one channel, a window of 1 and a
  512-byte ring there is at most one packet in flight, so the ring cannot
  be driven full by a correct peer; it would start to matter with streaming
  or a real window, and the counters below are there to say so if it does.

  Constants -- the segments, the vector, the 8259 masks and EOI, the
  register values and the order they have to be written in -- are read out
  of msxv90.asm rather than guessed.  ~/projects/myfreedos's
  kernel/victor_int14.asm and victor_pic.asm agree independently on the
  addresses and on the RR0 bit assignments.
*/

/*
  Memory-mapped, not I/O ports: IN and OUT do not reach any of this.

  On the 7201 the "control" address is both the status port to read and the
  command port to write.  Reading it gives RR0; writing a register number
  to it points the read/write pointer at that register, and the pointer
  resets itself to 0 after the next access -- which is the property that
  lets the handler below and the foreground share the port without a lock,
  as long as neither ever leaves the pointer parked.
*/
#define V9K_SEG_7201    0xE004          /* uPD7201 serial controller    */
#define V9K_SEG_8253    0xE002          /* Baud rate counters           */
#define V9K_SEG_8259    0xE000          /* Interrupt controller         */
#define V9K_SEG_6522    0xE804          /* The 6522 that also has DSR   */

#define V9K_OFF_CTLA    2               /* Channel A control/status     */
#define V9K_OFF_DATA    0               /* Channel A data               */
#define V9K_OFF_CTLB    3               /* Channel B control/status     */
#define V9K_OFF_DATB    1               /* Channel B data               */

#define V9K_8253_CTL    3               /* 8253 control word            */
                                        /* Divisor port = channel number*/
#define V9K_8259_CMD    0               /* OCW2 -- where the EOI goes   */
#define V9K_8259_IMR    1               /* OCW1 -- the interrupt mask   */

/*
  IR1 on the 8259 is "all from the 7201", and under the Victor's own ROM
  configuration it arrives as INT 41h -- msxv90.asm carries the vector as
  mdintv = 104h, which is 4 x 41h, with the 8259 mask bit and the specific
  end-of-interrupt byte that go with it.

  This is the one constant here that is not a property of the hardware.  It
  is a property of how the 8259 was programmed at boot, and
  ~/projects/myfreedos remaps the PIC in its own kernel -- its serial ISR
  goes in at INT 09h.  So this number is right for Victor MS-DOS 3.1, which
  is where it has been used, and is an open question for FreeDOS for
  Victor.  PORTING.md SS15.
*/
#define V9K_IRQ1_VEC    0x41            /* 3.13's mdintv = 104h = 4*41h */
#define V9K_IRQ1_BIT    0x02            /* Its bit in the 8259 mask     */
#define V9K_IRQ1_EOI    0x61            /* Specific EOI for IRQ1        */

/* RR0, read from the control address.  Agreed by msxv90.asm and by
   myfreedos's victor_int14.asm. */
#define V9K_RR0_RXRDY   0x01            /* A character is waiting       */
#define V9K_RR0_TXEMPTY 0x04            /* Transmit buffer is free      */
#define V9K_RR0_DCD     0x08            /* Carrier detect input         */
#define V9K_RR0_CTS     0x20            /* Clear to send input          */

/* RR1, reached by writing 1 to the control address and reading it back. */
#define V9K_RR1_ALLSENT 0x01            /* Transmitter AND shift empty  */
#define V9K_RR1_OVERRUN 0x20            /* Receiver overrun, LATCHED    */

/* WR0 commands, written to the control address with the pointer at 0. */
#define V9K_CMD_RESET   0x18            /* Channel reset                */
#define V9K_CMD_EXTRST  0x10            /* Reset external/status ints   */
#define V9K_CMD_ERRRST  0x30            /* Error reset -- see the ISR   */
#define V9K_CMD_EOI     0x38            /* End of interrupt (channel A) */

/* WR1: interrupt on every received character, nothing else.  3.13's
   REG1_7201 or ENABLE_INT.  Bit 1 (transmit interrupt) stays clear
   because the transmitter here is polled. */
#define V9K_WR1_RXINT   0x18
#define V9K_WR1_OFF     0x00

/*
  Reaching a fixed physical address needs a far pointer even in the large
  model: data is far, but nothing can name segment E004h without saying so.
  MK_FP folds to a constant when the offset is one.
*/
#define V9K_FARB(seg,off) (*(volatile unsigned char __far *)MK_FP((seg),(off)))

/* The channel we were given.  Set by v9k_ser_install() from the device
   name; everything else reads these. */
static unsigned int  v9k_chan    = 0;           /* 0 = A, 1 = B         */
static unsigned int  v9k_off_ctl = V9K_OFF_CTLA;
static unsigned int  v9k_off_dat = V9K_OFF_DATA;
static unsigned char v9k_dsrbit  = 0x08;        /* 6522 PA3 for A       */

#define V9K_CTL   V9K_FARB(V9K_SEG_7201,v9k_off_ctl)
#define V9K_DAT   V9K_FARB(V9K_SEG_7201,v9k_off_dat)

/*
  WR2 and the end-of-interrupt command live on channel A whichever channel
  is carrying the data -- they are chip-wide, not per-channel, and 3.13
  writes both to STATA_7201 explicitly even when it is running channel B.
*/
#define V9K_CTLA  V9K_FARB(V9K_SEG_7201,V9K_OFF_CTLA)

#define V9K_IMR   V9K_FARB(V9K_SEG_8259,V9K_8259_IMR)
#define V9K_EOI   V9K_FARB(V9K_SEG_8259,V9K_8259_CMD)

/*
  Blocking interrupts.  Needed in exactly one shape: any foreign sequence
  that writes a register number and then reads or writes it, because the
  handler uses the same pointer.  A bare read of RR0 does not need it --
  the handler always leaves the pointer at 0 -- and neither does anything
  touching the ring.
*/
#define V9K_CLI() _disable()
#define V9K_STI() _enable()

/*
  The ring.  Single producer (the handler, which only ever advances head),
  single consumer (v9k_ser_get, which only ever advances tail), and a power
  of two so that the wrap is a mask.  That combination needs no critical
  section at all: each index is written by exactly one side, and a 16-bit
  store on an 8088 cannot be interrupted part-way -- interrupts are taken
  between instructions, not inside them.

  Size and the reasoning behind it are in ckvictor.h with the other DGROUP
  levers.
*/
#define V9K_RXMASK (V9K_RXBUFSIZ - 1)

static volatile unsigned char v9k_rxbuf[V9K_RXBUFSIZ];
static volatile unsigned int  v9k_rxhead = 0;   /* Handler writes here  */
static volatile unsigned int  v9k_rxtail = 0;   /* Foreground reads here*/

/*
  Three counters, for the debug log only.  They are the difference between
  "the transfer was slow" and "the ring is too small", and none of them is
  guessable from the outside.

  rxpeak is the high-water mark, and it is what makes the other two worth
  reading.  rxfull == 0 on its own says only "it did not overflow", which
  is the same answer whether the ring was one byte from the edge or never
  held more than four; the difference is exactly what you need when you are
  deciding whether V9K_RXBUFSIZ is the thing standing between this port and
  a longer packet (PORTING.md SS16j).  Maintained in the handler, which
  costs a subtract, a mask and a compare per byte -- 2us or so of the 26us
  a byte takes at 38400, and this is the only place that knows.
*/
static volatile unsigned int  v9k_rxlost = 0;   /* Chip overran us      */
static volatile unsigned int  v9k_rxfull = 0;   /* Ring overran Kermit  */
static volatile unsigned int  v9k_rxpeak = 0;   /* Most it ever held    */

/*
  And three more that turn rxpeak from a number into a lead.  Section 0e has
  the argument; in short, rxpeak alone cannot separate "one long pause" from
  "never quite keeping up", and it cannot say which of this file's four
  blocking places the pause was in.

  peaktag/peakfd are section 0e's tag and descriptor, copied at the instant
  the high-water mark moves.  rxstall counts how many times occupancy passed
  V9K_RXSTALL going up, which is the difference between one stall in a
  transfer and one per packet -- and that in turn is the difference between
  a fixed cost and a rate deficit.  All three are set only in the handler,
  and none costs more than a compare and a store per byte.
*/
#define V9K_RXSTALL 256                 /* "Well behind", in bytes      */

static volatile unsigned char v9k_peaktag  = V9K_TAG_NONE;
static volatile unsigned int  v9k_peakfd   = 0;
static volatile unsigned int  v9k_rxstall  = 0;

/*
  And where in the stream it happened, which is what turns a number into a
  packet.  rxbytes counts every byte the handler stores; latching it at the
  peak and at the first crossing gives two byte offsets, and the host's own
  packet log converts an offset into "which packet" by adding up the packet
  lengths -- so the question "is the peak sitting on the retransmission?"
  becomes arithmetic rather than argument.

  A 32-bit increment per byte is about 1.6us on a 5MHz 8088, against 26us a
  byte at 38400.  Long rather than int because a transfer bigger than 64K
  would otherwise wrap the answer silently.
*/
static volatile unsigned long v9k_rxbytes  = 0L;    /* Every byte stored */
static volatile unsigned long v9k_peakat   = 0L;    /* Offset at rxpeak  */
static volatile unsigned long v9k_stallat  = 0L;    /* First crossing    */

/*
  And the same treatment for the loss itself, which is what PORTING.md SS16p
  ended by asking for.  SS16p measured rxlost at 0, 0, 203 and 207 across the
  four rates and could not say what shape the loss had, because rxlost is a
  running total and a total cannot tell 203 separate misses from four bursts
  of fifty.  Those are different defects: 203 misses is a handler that is too
  slow per byte, four bursts is something that holds the machine off four
  times and has nothing to do with per-byte cost.

  Read rxlost carefully first, because it is not what SS16p called it.  Each
  entry to the handler can raise it at most ONCE -- it is set from a single
  test of the latched RR1 bit -- so it counts INTERRUPTS THAT FOUND AN
  OVERRUN, not bytes.  A hold-off long enough to lose fifty bytes presents
  the handler with one latched bit and the three the receiver managed to
  keep, so it can raise rxlost by as little as one.  rxlost is therefore a
  LOWER bound on bytes lost, and SS16p's "0.45% of received bytes" is a lower
  bound too.  What is unambiguous is that each increment means at least one
  byte went missing.

  So the four below bracket the shape rather than the size:

    lostevt   bursts.  A loss opens a new one when more than V9K_LOSTGAP
              bytes have been received cleanly since the previous loss, and
              continues the current one otherwise.  If this comes back 4
              against rxlost 203, the loss is four bursts and the foreground
              is being held off; if it comes back near 203, the handler is
              losing single bytes all through the transfer and the cause is
              per-byte cost after all.
    lostmax   the longest of those runs, which sizes the worst hold-off.
    lostat    byte offset at the FIRST loss, with losttag/lostfd -- section
              0e's tag, latched at the loss the way peaktag is latched at
              the peak.  This is the one that names a suspect: the peak is
              a consequence of the hold-off and the first loss is inside it.
    lostend   byte offset at the last loss.  With lostat it says whether the
              losses cluster in one stretch of the transfer or run through
              it, which the host's packet log then converts into packets.

  Separating the bursts by a gap in the STREAM rather than by "consecutive
  entries to the handler" is deliberate, and it is what keeps this free.
  Consecutive-entry counting needs the good-byte path to clear the run,
  which Watcom codes as a DGROUP reload and a store -- about 5us of a 26us
  byte at 38400, on the one path that runs per byte, in an instrument whose
  entire purpose is to find out whether the per-byte path is too slow.  That
  is SS16k's mistake exactly.  Measuring the gap instead puts every added
  instruction on a path that by measurement runs 203 times in 42,757 bytes,
  and it is the better definition anyway: one good byte drained in the
  middle of a hold-off should not read as two hold-offs.

  V9K_LOSTGAP is 16 because the two scales are nowhere near each other.
  Losses inside one hold-off land within a few stream positions of each
  other -- the receiver is three deep -- while distinct hold-offs are
  separated by whole packets, which are thousands of bytes here.  Any
  threshold between about 8 and 1000 gives the same answer.
*/
#define V9K_LOSTGAP 16                  /* Clean bytes that end a burst */

static volatile unsigned char v9k_losttag  = V9K_TAG_NONE;
static volatile unsigned int  v9k_lostfd   = 0;
static volatile unsigned int  v9k_lostevt  = 0;     /* Bursts, not bytes */
static volatile unsigned int  v9k_lostrun  = 0;     /* Inside one now    */
static volatile unsigned int  v9k_lostmax  = 0;     /* Longest burst     */
static volatile unsigned long v9k_lostat   = 0L;    /* Offset, first loss*/
static volatile unsigned long v9k_lostend  = 0L;    /* Offset, last loss */

static int v9k_ser_on   = 0;            /* Have we taken the chip?      */
static int v9k_ser_atx  = 0;            /* atexit() registered yet?     */
static unsigned int  v9k_oldvec_seg = 0;
static unsigned int  v9k_oldvec_off = 0;
static unsigned char v9k_oldimr = 0;    /* 8259 mask as we found it     */

/*
  Interrupt vectors, through INT 21h AH=35h and AH=25h -- which is the
  whole reason hooking one does not break hard rule 6.  Watcom's
  _dos_getvect/_dos_setvect are exactly those two calls; the pair below
  wraps them to take and return a segment and an offset rather than a
  function pointer, which is what the install and release paths want.
*/
static VOID
#ifdef CK_ANSIC
v9k_getvect(int vec, unsigned int * seg, unsigned int * off)
#else
v9k_getvect(vec,seg,off) int vec; unsigned int * seg; unsigned int * off;
#endif /* CK_ANSIC */
{
    void __far * p = (void __far *)_dos_getvect((unsigned int)vec);

    *seg = FP_SEG(p);
    *off = FP_OFF(p);
}

static VOID
#ifdef CK_ANSIC
v9k_setvect(int vec, unsigned int seg, unsigned int off)
#else
v9k_setvect(vec,seg,off) int vec; unsigned int seg; unsigned int off;
#endif /* CK_ANSIC */
{
    _dos_setvect((unsigned int)vec,
                 (void (__interrupt __far *)())MK_FP(seg,off));
}

/*
  The handler.  Written ANSI-only for the same reason ioctl() above is: the
  attribute that makes it an interrupt routine is part of its type, and
  there is no K&R spelling of it.

  Watcom's __interrupt __far pushes a fixed register set plus DS, loads
  DGROUP rather than trusting the interrupted DS, and ends in iret.  It
  emits no stack probe here.

  The body is 3.13's SERINT with the terminal-emulator half taken out:

    1. Read RR0 and RR1 before anything is acknowledged.
    2. Tell the 7201 the interrupt is over, then the 8259 -- 3.13 does both
       early so the machine is not held off while we work.
    3. Nothing waiting: return.
    4. OVERRUN.  This is the step PORTING.md SS16b says is not optional.  The
       chip LATCHES an overrun in RR1 and will not resume receiving until
       WR0 gets an Error Reset, so a handler that skips it wedges the
       channel on the first byte it was late for -- which is the exact shape
       of what the OEM driver does to us today.  msxv90.asm's edit history
       records this being found and fixed twice on this hardware in 1986.
       3.13 also stores a BELL in place of whatever was lost, and that is
       copied: the packet is ruined either way and will be retransmitted,
       but the length stays right, so ttinl() still finds the next SOH
       where it expects it rather than one byte early.
    5. Store, and drop the byte if Kermit has not kept up.  Dropping the
       NEWEST byte rather than overwriting the oldest is deliberate -- the
       oldest bytes are the front of a packet Kermit is about to read.
*/
static void __interrupt __far
v9k_ser_isr(void)
{
    unsigned char rr0, rr1, c;
    unsigned int nh;

    rr0 = V9K_CTL;                      /* RR0: pointer is already at 0 */
    V9K_CTL = 1;                        /* Point at RR1 ...             */
    rr1 = V9K_CTL;                      /* ... and read it; pointer     */
                                        /*     resets itself to 0 again */
    V9K_CTLA = V9K_CMD_EOI;             /* 7201 end of interrupt        */
    V9K_EOI  = V9K_IRQ1_EOI;            /* 8259 specific EOI for IRQ1   */

    if (!(rr0 & V9K_RR0_RXRDY))         /* Nothing for us               */
      return;

    if (rr1 & V9K_RR1_OVERRUN) {        /* Latched -- clear it or wedge */
        V9K_CTL = V9K_CMD_ERRRST;
        v9k_rxlost++;
        /*
          New burst or continuation of the one in progress?  See the comment
          on v9k_lostevt: this is the whole difference between the two
          defects PORTING.md SS16p could not separate.  The !v9k_lostevt arm
          is for the very first loss, where lostend is still 0 and the
          subtraction would not mean anything yet.
        */
        if (!v9k_lostevt) {             /* The first loss of the run     */
            v9k_lostevt = 1;
            v9k_lostrun = 1;
            v9k_losttag = v9k_wtag;     /* Section 0e, latched HERE      */
            v9k_lostfd  = v9k_wtagfd;
            v9k_lostat  = v9k_rxbytes;
        } else if (v9k_rxbytes - v9k_lostend > (unsigned long)V9K_LOSTGAP) {
            v9k_lostevt++;              /* Clean run since: a new burst  */
            v9k_lostrun = 1;
        } else
          v9k_lostrun++;                /* Still inside the same one     */
        if (v9k_lostrun > v9k_lostmax)
          v9k_lostmax = v9k_lostrun;
        v9k_lostend = v9k_rxbytes;

        nh = (v9k_rxhead + 1) & V9K_RXMASK;
        if (nh != v9k_rxtail) {         /* Mark the gap, as 3.13 does   */
            v9k_rxbuf[v9k_rxhead] = (unsigned char)'\007';
            v9k_rxhead = nh;
            /*
              Counted, which it was not before this section.  The BELL
              stands in for a byte the host really sent, so it occupies a
              position in the stream, and rxbytes is read as a stream
              offset to map onto the host's packet log.  Leaving it out
              made every offset in a lossy run drift low by the loss count
              -- 203 bytes at 38400, which is small but is exactly the run
              where the offsets matter.  Runs with rxlost = 0 are
              unaffected, so SS16k-SS16p's figures stand as printed.
            */
            v9k_rxbytes++;
        }
    }

    c  = V9K_DAT;
    nh = (v9k_rxhead + 1) & V9K_RXMASK;
    if (nh != v9k_rxtail) {
        v9k_rxbuf[v9k_rxhead] = c;
        v9k_rxhead = nh;
        v9k_rxbytes++;
        nh = (nh - v9k_rxtail) & V9K_RXMASK;    /* Occupancy after us   */
        if (nh > v9k_rxpeak) {
            v9k_rxpeak  = nh;
            v9k_peaktag = v9k_wtag;             /* Section 0e: and who  */
            v9k_peakfd  = v9k_wtagfd;           /* was holding us up    */
            v9k_peakat  = v9k_rxbytes;          /* and where in the file*/
        }
        if (nh == V9K_RXSTALL) {                /* Crossed it going up  */
            if (!v9k_rxstall)
              v9k_stallat = v9k_rxbytes;
            v9k_rxstall++;
        }
    } else
      v9k_rxfull++;                     /* Ring full: this byte is gone */
}

/*
  Its address, as a segment and an offset, for v9k_setvect() above.  The
  handler is in far code, so this is a plain far pointer taken apart.
*/
#define V9K_ISR_SEG FP_SEG((void __far *)v9k_ser_isr)
#define V9K_ISR_OFF FP_OFF((void __far *)v9k_ser_isr)

/*
  Which of the two channels we were told to drive, from the SET LINE name
  -- "/dev/seriala", "SERIALB", "COM2".  Anything that does not end in a B
  or a 2 is channel A, which is both the default and what SS11's "use
  channel A for Kermit, leave B for CTTY COM2" prefers.

  Idempotent, and called from both the install and the direct-programming
  fallback, because either can be the first to touch the chip.
*/
static VOID
v9k_ser_selchan() {
    extern char ttname[];               /* ckcmai.c: the SET LINE name  */
    int n;
    char last;

    n = (int)strlen(ttname);
    last = n ? ttname[n-1] : 'a';
    if (last == 'b' || last == 'B' || last == '2') {
        v9k_chan    = 1;
        v9k_off_ctl = V9K_OFF_CTLB;
        v9k_off_dat = V9K_OFF_DATB;
        v9k_dsrbit  = 0x20;             /* 6522 PA5 for channel B       */
    } else {
        v9k_chan    = 0;
        v9k_off_ctl = V9K_OFF_CTLA;
        v9k_off_dat = V9K_OFF_DATA;
        v9k_dsrbit  = 0x08;             /* 6522 PA3 for channel A       */
    }
}

/*
  Program the line at the chip, for a DOS whose serial driver will not
  answer the SS11a IOCTL.  3.13 has exactly this fallback and says so on the
  screen ("Cannot open com port / Going direct to serial controller
  hardware..."); it matters here because this binary is meant to run on
  FreeDOS for Victor as well as on Victor MS-DOS 3.1, and only the latter
  has been measured.

  The write order is not free and msxv90.asm calls it out: channel reset,
  then WR2 first, then WR4 second, then 1/3/5 in any order.  WR2 goes to
  channel A whichever channel this is.  Its value here is 3.13's 0x14 --
  when the IOCTL has failed there is no OEM setting to preserve, which is
  the only reason SS11a leaves it alone in the normal path.

  The 8253 control byte is (channel << 6) | 36h -- mode 3, binary, low byte
  of the divisor then high byte -- and the divisor goes to the port with
  the channel's own number.
*/
static VOID
#ifdef CK_ANSIC
v9k_ser_progline(unsigned char cr3, unsigned char cr4, unsigned char cr5,
                 unsigned int divisor)
#else
v9k_ser_progline(cr3,cr4,cr5,divisor)
    unsigned char cr3; unsigned char cr4; unsigned char cr5;
    unsigned int divisor;
#endif /* CK_ANSIC */
{
    v9k_ser_selchan();
    V9K_CLI();
    V9K_CTL  = V9K_CMD_RESET;           /* Reset this channel           */
    V9K_CTLA = 2;   V9K_CTLA = 0x14;    /* WR2 first, and chip-wide     */
    V9K_CTL  = 4;   V9K_CTL  = cr4;     /* WR4 second                   */
    V9K_CTL  = 3;   V9K_CTL  = cr3;
    V9K_CTL  = 5;   V9K_CTL  = cr5;
    if (divisor) {
        V9K_FARB(V9K_SEG_8253,V9K_8253_CTL) =
            (unsigned char)((v9k_chan << 6) | 0x36);
        V9K_FARB(V9K_SEG_8253,v9k_chan) = (unsigned char)(divisor & 0xff);
        V9K_FARB(V9K_SEG_8253,v9k_chan) = (unsigned char)(divisor >> 8);
    }
    V9K_STI();
}

/*
  Put back the one register the SS11a IOCTL cannot be trusted with.  3.13
  found that the write subfunction does not apply CR1 and pokes WR1 at the
  chip afterwards, commented "IOCTL doesn't seem to touch it"; SS11a
  measured CR1 reading back as 0 on this driver, which is consistent with
  it either not applying the field or not reporting it.  Either way, every
  tcsetattr() after the install has to end here or the receive interrupt
  might quietly go away in the middle of a transfer.
*/
static VOID
v9k_ser_reenable() {
    if (!v9k_ser_on)
      return;
    /*
      And the two loss counters, here rather than only in the release path,
      because by the time atexit() runs the debug log is already closed --
      measured, the release's own debug() lines do not reach DEBUG.LOG.
      tcsetattr() is called from ttres() on the way out, so the last time
      through this is the end-of-session figure.
    */
    debug(F111,"v9k_ser rxlost/rxfull",
          ckitoa((int)v9k_rxlost),(int)v9k_rxfull);
    debug(F101,"v9k_ser rxpeak","",(int)v9k_rxpeak);
    V9K_CLI();
    V9K_CTL  = 1;   V9K_CTL = V9K_WR1_RXINT;
    V9K_CTL  = V9K_CMD_EXTRST;
    V9K_CTL  = V9K_CMD_ERRRST;
    V9K_CTLA = V9K_CMD_EOI;
    V9K_STI();
}

/*
  Give the chip back.  The exact inverse of the install below, and the
  order matters as much: a Kermit that exits with IRQ1 still pointing into
  its own freed memory takes the machine down with the next character.

  It waits for the transmitter first.  3.13's SERRST spins on RR1 bit 0 --
  transmitter buffer AND shift register empty -- before it tears anything
  down, because the alternative is truncating the last packet on the wire,
  and the last packet is usually the one that says the transfer finished.
*/
static VOID
v9k_ser_release() {
    unsigned int spin;
    unsigned char rr1;

    if (!v9k_ser_on)
      return;

    for (spin = 60000U; spin; spin--) { /* Bounded: a dead chip must not */
        V9K_CLI();                      /* hang the exit path            */
        V9K_CTL = 1;
        rr1 = V9K_CTL;
        V9K_STI();
        if (rr1 & V9K_RR1_ALLSENT)
          break;
    }

    V9K_CLI();
    V9K_IMR = (unsigned char)(V9K_IMR | V9K_IRQ1_BIT);  /* Mask IRQ1    */
    V9K_CTL = 1;   V9K_CTL = V9K_WR1_OFF;               /* No RX ints   */
    v9k_ser_on = 0;
    V9K_STI();

    /* Now that nothing can fire, DOS may have the vector back.  Then put
       the mask bit back the way we found it rather than simply leaving
       IRQ1 masked, in case the host DOS's own driver wanted it. */
    v9k_setvect(V9K_IRQ1_VEC,v9k_oldvec_seg,v9k_oldvec_off);
    if (!(v9k_oldimr & V9K_IRQ1_BIT))
      V9K_IMR = (unsigned char)(V9K_IMR & ~V9K_IRQ1_BIT);

    debug(F101,"v9k_ser_release rxlost","",(int)v9k_rxlost);
    debug(F101,"v9k_ser_release rxfull","",(int)v9k_rxfull);

    /*
      And the same three to STDOUT, in every build, which is not
      redundancy.  They are the only evidence that separates "the ring is
      too small" from "the chip overran the handler", and the debug log
      cannot be where they live: -d costs about 25ms per received byte
      (PORTING.md SS16k), which starves the ring by itself and so changes
      the very number it is being asked to report.  Measured: with -d a
      968-byte packet never gets through and rxfull reaches 2,483; without
      it the same packet ACKs first time.  A run that is fast enough to be
      worth measuring is exactly a run that cannot carry a debug log, so
      one line on the way out is the only way to read this at all.

      atexit() and not the debug log's own site for the same reason the
      comment in v9k_ser_reenable() gives in reverse: by the time this
      runs DEBUG.LOG is closed, but stdout is still open, and a .BAT that
      redirects it catches this line.
    */
    printf("v9k: rxlost=%u rxfull=%u rxpeak=%u of %u\n",
           (unsigned)v9k_rxlost, (unsigned)v9k_rxfull,
           (unsigned)v9k_rxpeak, (unsigned)V9K_RXBUFSIZ);

    /*
      Section 0e, on the same terms and for the same reason.  peaktag says
      where the foreground was when the ring was fullest, stall says how
      many times it got that far behind at all, and the two write lines are
      what the only writes this program can see actually cost.  Hundredths,
      from INT 21h AH=2Ch.
    */
    printf("v9k: peaktag=%u fd=%u stall%u=%u\n",
           (unsigned)v9k_peaktag, (unsigned)v9k_peakfd,
           (unsigned)V9K_RXSTALL, (unsigned)v9k_rxstall);
    printf("v9k: rxbytes=%lu peakat=%lu stallat=%lu\n",
           v9k_rxbytes, v9k_peakat, v9k_stallat);

    /*
      The loss instrument, and the two lines are meant to be read together
      with the rxlost above.  evt against that rxlost is the shape of the
      defect -- near it means single misses all through, far below it means
      bursts -- and max sizes the worst one.  losttag is section 0e's tag
      latched at the FIRST loss rather than at the peak, which is the whole
      point: the peak is downstream of the hold-off and the first loss is
      inside it.  Printed unconditionally even when evt is 0, because "no
      loss at this rate" is a result that has to be visible next to one that
      is not.
    */
    printf("v9k: lost evt=%u max=%u tag=%u fd=%u\n",
           v9k_lostevt, v9k_lostmax,
           (unsigned)v9k_losttag, (unsigned)v9k_lostfd);
    printf("v9k: lostat=%lu lostend=%lu\n",
           v9k_lostat, v9k_lostend);
    printf("v9k: wfile n=%u max=%ld at #%u of %u tot=%ld cs\n",
           v9k_wf_n, v9k_wf_max, v9k_wf_maxn, v9k_wf_maxb, v9k_wf_tot);
    printf("v9k: wcon n=%u max=%ld tot=%ld cs\n",
           v9k_wc_n, v9k_wc_max, v9k_wc_tot);
    printf("v9k: txgap n=%u max=%ld at #%u tot=%ld cs\n",
           v9k_gap_n, v9k_gap_max, v9k_gap_maxn, v9k_gap_tot);
}

/*
  Take the chip.  Called from tcsetattr() once the line has been programmed
  -- that is the one place C-Kermit is guaranteed to reach with the
  descriptor open and the speed already set, and it costs no new hook.

  This displaces the OEM driver's own interrupt handler while its device
  stays open, which is safe for exactly one reason: we never ask it for a
  byte again.  Section 0d's read and the write above both route past it
  from here on, and section 1b keeps using its IOCTL, which is a different
  thing entirely.

  The order is mask, hook, configure, unmask.  Masking first means the
  window where the vector points at us but the chip is not set up yet
  cannot fire.
*/
static int
#ifdef CK_ANSIC
v9k_ser_install(int fd)
#else
v9k_ser_install(fd) int fd;
#endif /* CK_ANSIC */
{
    if (v9k_ser_on)
      return(0);

    v9k_ser_selchan();

    v9k_oldimr = V9K_IMR;
    V9K_IMR = (unsigned char)(v9k_oldimr | V9K_IRQ1_BIT);

    v9k_getvect(V9K_IRQ1_VEC,&v9k_oldvec_seg,&v9k_oldvec_off);
    v9k_setvect(V9K_IRQ1_VEC,V9K_ISR_SEG,V9K_ISR_OFF);

    V9K_CLI();
    v9k_rxhead = v9k_rxtail = 0;
    v9k_rxlost = v9k_rxfull = 0;
    V9K_CTL  = 1;   V9K_CTL = V9K_WR1_RXINT;
    V9K_CTL  = V9K_CMD_EXTRST;
    V9K_CTL  = V9K_CMD_ERRRST;
    V9K_CTLA = V9K_CMD_EOI;
    while (V9K_CTL & V9K_RR0_RXRDY)     /* Drop whatever the OEM driver */
      (void)V9K_DAT;                    /* left sitting in the receiver */
    v9k_ser_on = 1;
    V9K_STI();

    V9K_IMR = (unsigned char)(V9K_IMR & ~V9K_IRQ1_BIT);

    /*
      WR2 is left exactly as the OEM driver set it.  SS11a read it back as
      10h where 3.13 writes 14h, and the two differ in one bit, which
      3.13's own comment attributes to interrupt priority (Ra>Rb>Ta>Tb).
      With one channel and receive interrupts only there is no priority
      decision to be made, and both values select the same 8086 vector
      mode -- so this is one fewer register to disturb and to put back.
      Reasoned, not measured: if interrupts never arrive, it is the first
      thing to try changing.
    */

    /*
      Getting the vector back on the way out is not optional: after exit
      this program's memory is somebody else's, and an IRQ1 still pointing
      into it takes the machine down with the next character on the line.
      ttclos() is not enough on its own -- C-Kermit can be told to exit
      from several places -- so the release is hung on atexit(), which
      covers every path that goes through exit(), including the SIGINT
      handler in ckusig.c.

      What it does NOT cover is a Ctrl-Break that DOS turns into a plain
      program termination without the runtime's INT 23h handler getting
      there first.  Known, not measured on either runtime, and it is the
      reason to be careful with Ctrl-Break while the line is open.
    */
    if (!v9k_ser_atx) {                 /* Once, and only once          */
        v9k_ser_atx = 1;
        atexit(v9k_ser_release);
    }
    debug(F101,"v9k_ser_install channel","",(int)v9k_chan);
    debug(F101,"v9k_ser_install old IRQ1 mask","",(int)v9k_oldimr);
    debug(F101,"v9k_ser_install old vector seg","",(int)v9k_oldvec_seg);
    return(0);
}

static int
v9k_ser_active() {
    return(v9k_ser_on);
}

/*
  How many bytes are in the ring.  head and tail are each written by one
  side only, so this can read both without stopping anything; head may
  advance while we look, which only ever makes the answer conservative.

  This is what FIONREAD returns for the communications device, and it is
  the number sdata() in ckcfns.c has been asking for since section 0b --
  it slides its send window only when ttchk() exceeds 4+bctu, so the 0-or-1
  it used to get meant the window filled before any ACK was read.
*/
static int
v9k_ser_count() {
    if (!v9k_ser_on)
      return(0);
    return((int)((v9k_rxhead - v9k_rxtail) & V9K_RXMASK));
}

/*
  Take up to n bytes out of the ring.  Returns 0 when it is empty, which is
  what makes section 0d's loop spin rather than report end of file.

  The tail is advanced inside the loop, one byte at a time, and it did not
  used to be.  Publishing it only at the end is correct -- one store, and
  nothing else writes it -- but it makes the handler's view of occupancy
  wrong for as long as the copy runs: head keeps moving, tail does not, so
  the ring appears to keep filling while it is actually being emptied.  That
  costs nothing in the data path and everything in section 0e's tag, because
  a backlog that piled up while the foreground was elsewhere gets its peak
  latched here, during the drain that is removing it, and the tag then reads
  "we were reading all along" no matter what really happened.  One store per
  byte buys an honest instrument.
*/
static int
#ifdef CK_ANSIC
v9k_ser_get(char * buf, int n)
#else
v9k_ser_get(buf,n) char * buf; int n;
#endif /* CK_ANSIC */
{
    int i = 0;
    unsigned int t;

    if (!v9k_ser_on || n <= 0)
      return(0);
    t = v9k_rxtail;
    while (i < n && t != v9k_rxhead) {
        buf[i++] = (char)v9k_rxbuf[t];
        t = (t + 1) & V9K_RXMASK;
        v9k_rxtail = t;                 /* Ours alone, so publish it now */
    }
    return(i);
}

/*
  Throw away everything waiting to be read -- the ring, and whatever the
  chip is still holding.  tcflush()'s TCIFLUSH, which ttflui() reaches
  before every packet exchange.

  Clearing the error latch on the way out is not decoration: if the reason
  Kermit is flushing is that it fell behind, the latch is exactly what is
  set, and leaving it set means the flush is the last thing that ever
  happens on this channel.
*/
static VOID
v9k_ser_flush() {
    if (!v9k_ser_on)
      return;
    V9K_CLI();
    while (V9K_CTL & V9K_RR0_RXRDY)
      (void)V9K_DAT;
    V9K_CTL = V9K_CMD_ERRRST;
    v9k_rxtail = v9k_rxhead;
    V9K_STI();
}

/*
  Wait until the transmitter and its shift register are both empty --
  tcdrain(), and 3.13's SERRST spin.  Bounded for the same reason the
  release path's copy is: this must not be able to hang the program.
*/
static VOID
v9k_ser_drain() {
    unsigned int spin;
    unsigned char rr1;

    if (!v9k_ser_on)
      return;
    for (spin = 60000U; spin; spin--) {
        V9K_CLI();
        V9K_CTL = 1;
        rr1 = V9K_CTL;
        V9K_STI();
        if (rr1 & V9K_RR1_ALLSENT)
          return;
    }
    debug(F100,"v9k_ser_drain gave up waiting for the transmitter","",0);
}

/*
  Polled transmit, which is 3.13's OUTCHR: wait for RR0 to say the transmit
  buffer is free, then store the byte at the data address.  No interrupt is
  enabled for this direction (WR1 bit 1 stays clear) and none is wanted --
  transmit was never the half that was broken.

  The spin is bounded.  3.13 counts a full 16-bit register and gives up;
  60000 turns of this loop is a few tenths of a second on a 5 MHz 8088,
  which is hundreds of character times at 9600 bps and still short enough
  that a dead line does not hang the program.  A partial write is reported
  as a partial write: ttol() retries the remainder, which is exactly what
  it does with a short write from any other Unix.
*/
#define V9K_TXSPIN 60000U

static int
#ifdef CK_ANSIC
v9k_ser_put(const char * buf, int n)
#else
v9k_ser_put(buf,n) const char * buf; int n;
#endif /* CK_ANSIC */
{
    int i;
    unsigned int spin;

    for (i = 0; i < n; i++) {
        for (spin = V9K_TXSPIN; spin; spin--)
          if (V9K_CTL & V9K_RR0_TXEMPTY)
            break;
        if (!spin) {
            debug(F101,"v9k_ser_put transmitter stuck","",i);
            errno = EIO;
            return(i ? i : -1);
        }
        V9K_DAT = (unsigned char)buf[i];
    }
    return(n);
}

/*
  Modem signals, for ttgmdm() by way of ioctl(TIOCMGET).  RR0 carries DCD
  and CTS.  DSR does not exist on this chip at all -- 3.13's getmodem
  explains that the 7201 has no pin for it on the Victor, so it comes off
  the 6522 that also runs the keyboard and the CRT brightness, PA3 for
  channel A and PA5 for B, and a ZERO there means the line is ACTIVE.

  DTR and RTS are reported from the last WR5 we programmed rather than
  read: they are outputs, WR5 is write-only, and section 1b is the only
  thing that ever changes them.

  The carrier clause is the one judgement call in this file, so it is
  spelled out.  in_chk() -- ttchk() -- asks this for carrier BEFORE it asks
  how many bytes are waiting, and treats "no DCD" as a lost connection: it
  closes the device and returns -2.  A three-wire cable between two Victors,
  or between a Victor and anything else, does not carry DCD, so a literal
  RR0 would end every transfer at the first ttchk().  But C-Kermit has
  already told us whether it wants carrier to mean anything: ttopen() and
  ttpkt() call carrctl(), whose entire body is "set CLOCAL when carrier is
  not to be required", and the settings it set are the ones cached in
  victor_ttcur.  So when CLOCAL is on, say the carrier is there.  With
  CARRIER-WATCH ON, or a modem connection, CLOCAL is clear and RR0 is
  reported as it reads.
*/
static int
v9k_ser_mdm() {
    unsigned char rr0;
    int z = 0;

    if (!v9k_ser_on)
      return(0);

    rr0 = V9K_CTL;                      /* Pointer is at 0: this is RR0 */
    if (rr0 & V9K_RR0_DCD) z |= TIOCM_CAR;
    if (rr0 & V9K_RR0_CTS) z |= TIOCM_CTS;
    if (!(V9K_FARB(V9K_SEG_6522,1) & v9k_dsrbit))
      z |= TIOCM_DSR;                   /* Active LOW on the 6522       */

    if (v9k_lastcr5 & 0x80) z |= TIOCM_DTR;
    if (v9k_lastcr5 & 0x02) z |= TIOCM_RTS;

    if (victor_ttcur.c_cflag & CLOCAL)  /* See above                    */
      z |= TIOCM_CAR;
    return(z);
}


/* ------------------------------------------------------------------ */
/* 1d. Gaps in the Open Watcom DOS runtime                              */
/* ------------------------------------------------------------------ */

/*
  The Unix surface C-Kermit calls and Watcom does not have at all.
  getpwent()/setpwent()/endpwent() complete the passwd stubs in section 1
  -- see victorow/pwd.h for why NULL is the right answer rather than a
  placeholder.

  FAT has no hard links and MS-DOS has no other process to signal, but
  ckufio.c calls link() (zrename's fallback) and kill() (zkill), so both
  must exist even though nothing can succeed.
*/

int
#ifdef CK_ANSIC
link(const char * old, const char * new)
#else
link(old,new) const char * old; const char * new;
#endif /* CK_ANSIC */
{
    errno = EMLINK;
    return(-1);
}

int
#ifdef CK_ANSIC
kill(pid_t pid, int sig)
#else
kill(pid,sig) pid_t pid; int sig;
#endif /* CK_ANSIC */
{
    errno = ESRCH;
    return(-1);
}

struct passwd * getpwent(void) { return((struct passwd *)0); }
VOID setpwent(void) { }
VOID endpwent(void) { }

/*
  _fmode -- make the DOS runtime stop translating, before main() runs.

  ckufio.c is the UNIX file module.  zopeni() is a bare fopen(name,"r")
  and zopeno() only ever builds "w" or "a"; neither consults the "binary"
  flag, because on Unix there is nothing to consult it for.  On DOS the
  runtime then turns LF into CRLF on the way out and CRLF into LF on the
  way in, and treats ^Z as end of file on input -- which corrupted every
  binary transfer in BOTH directions (PORTING.md SS16h).  All of C-Kermit's
  own end-of-line conversion happens in ckcfns.c under !binary, and with
  "#undef NLCHAR" for VICTOR9K in ckcdeb.h it does none at all, because the
  local line terminator and the wire's are both CRLF.  So the runtime must
  not do it a second time: every stream this program opens wants raw bytes.

  Open Watcom ships binmode.obj to set exactly this.  It does not work in
  this program.  Measured on Victor MS-DOS 3.1 (.probe/vfmode.c,
  .probe/vfmodefp.c): it sets _fmode correctly in a small test program,
  with or without the floating-point emulator linked, and leaves _fmode at
  0100 in CKERMITW.EXE -- with the object the toolchain ships (which is the
  SMALL model build) and equally with the large-model build of the same
  source.  Everything checkable says it should work: its record is in the
  XI table (the table grows 0x3c -> 0x42), cstart runs every priority
  ("mov ax,0FFh"), and _TEXT is one 60,160-byte segment so a near call
  reaches it.  The cause is not known, and rather than ship a mechanism
  that cannot be explained, this file registers its own initializer.

  The difference that matters is FAR.  Watcom's object uses AXIN, the NEAR
  form: rtn_type 0 and a two-byte routine offset, which obliges the walker
  in initrtns.c to reach it with a near call.  clibl.lib is compiled large,
  so struct rt_init there is {type, priority, FAR pointer} -- exactly the
  six bytes below -- and rtn_type 1 asks for the far call that cannot care
  which segment the routine landed in.  The witness is not decoration: it
  is what distinguishes "the initializer never ran" from "it ran and
  something put _fmode back", and access() below reports it into the debug
  log at the one moment it matters.
*/
int v9k_fmode_witness = 0;              /* Set by the initializer below */
static int v9k_fmode_told = 0;          /* Reported to the debug log once */

#pragma pack(push,1)
struct v9k_rt_init {                    /* initrtns.c's large-code layout */
    unsigned char  rtn_type;            /* 0 = near routine, 1 = far     */
    unsigned char  priority;            /* 0 highest, 255 lowest         */
    void (__far * rtn)(void);
};
#pragma pack(pop)

static void __far
v9k_set_binmode(void)
{
    v9k_fmode_witness = 1;
    _fmode = O_BINARY;
}

/*
  32 is INIT_PRIORITY_LIBRARY, the same priority binmode.obj asks for --
  early enough that nothing has opened a stream yet, late enough that the
  runtime's own data is up.  __based(__segname("XI")) drops the record into
  the table between XIB and XIE that __InitRtns() walks.
*/
static struct v9k_rt_init __based(__segname("XI")) v9k_fmode_rec =
    { 1, 32, v9k_set_binmode };

/*
  Server capabilities, and the command-line switch that chooses how many.

  C-Kermit 11 initialises every ENABLE variable in ckcmai.c to 2, and
  ENABLED() in ckcker.h reads

      (local && (x & 1)) || (!local && (x & 2))

  so 2 means "enabled in remote mode only".  A Victor running

      CKERMITW -l /dev/seriala -b 9600 -x

  OWNS the line, which is exactly what makes it LOCAL -- so every server
  command is disabled.  Measured, PORTING.md SS16i: the first run of server
  mode answered the host's I packet with a correct ACK and then refused
  each command with a well-formed E packet -- "GET disabled", "SEND
  disabled", "FINISH disabled".  The protocol engine and the driver were
  working; the capability gate was shut.

  This is stock upstream policy, not a defect and not something this port
  introduced.  Upstream's own ENABLE help says it: "By default, most
  commands are enabled for REMOTE but disabled for LOCAL to prevent
  security issues."  C-Kermit 9 and 10 shipped these at 3 (both modes);
  11 tightened them, which is why compat_10() above -- SET COMPATIBILITY
  10 -- exists to put them back.

  On a full C-Kermit the answer is to type ENABLE GET at the prompt before
  SERVER.  NOICP removes the prompt, so the decision has to be made at
  startup, and this is where the port makes it:

      CKERMITW -x                  server offers everything it can do
      CKERMITW -x --safe-server    server offers GET, SEND and FINISH only

  The default is the full set -- everything the build can actually perform,
  which is compat_10's list plus DELETE/RMDIR/RETRIEVE/EXIT/BYE.  HOST is
  left alone because NOPUSH already removed the thing it would run, and
  MAIL and PRINT because this build has no transport for either; setting
  those to 3 would only turn a refusal into a failure.  --safe-server is
  for a line whose far end is not entirely yours: it grants the three
  commands a file transfer needs and nothing that manipulates the Victor's
  file system.  Note the asymmetry -- en_ena stays at its default under
  --safe-server, so a peer cannot ENABLE its way back out of it.

  These variables are read only by the server-command handlers in
  ckcpro.w, so a -s, -r or -g run never consults them; setting them here
  costs those invocations nothing.

  HOW THE SWITCH IS PARSED, because it is not obvious and it is not a
  tenth upstream edit.  ckuusy.c's cmdlin() would call XFATAL on an option
  it does not know, so upstream must never see this one.  Open Watcom's
  cstart (bld/clib/startup/a/cstrt086.asm) copies the DOS command tail from
  PSP:81h to the bottom of the stack and leaves a far pointer to the copy
  in _LpCmdLine, all BEFORE it calls __InitRtns -- and on 16-bit targets
  argv itself is built by an XI initializer, __Init_Argv, at
  INIT_PRIORITY_THREAD, which is 1 (bld/clib/startup/c/argcv.c,
  bld/watcom/h/rtprior.h).  __InitRtns always runs the lowest priority not
  yet done, so a record at priority 0 runs before argv exists.  This one
  reads the copy, records the switch, and blanks it with spaces; argv is
  then built from a command line that no longer contains it, and cmdlin()
  parses what it expects.

  Priority 0 also means the floating-point and run-time initializers have
  not run yet, so this routine calls nothing -- no libc, and in particular
  no debug(), because the log is not open.  What it decides is reported
  from uname() instead, which sysinit() reaches in EVERY invocation --
  including "CKERMITW -d -h", which writes a debug log and exits without
  opening the line, so the switch is checkable in one 2.5-minute boot with
  no serial line and no host.  "v9k srvcaps safe" in DEBUG.LOG is the
  witness: 0 for the full set, 1 for --safe-server.
*/

int v9k_srvcaps_safe = 0;               /* --safe-server was given      */
static int v9k_srvcaps_told = 0;        /* Reported to the debug log once */

extern char __far * _LpCmdLine;         /* Watcom's copy of the DOS tail */

extern int en_xit, en_cwd, en_cpy, en_del, en_mkd, en_rmd, en_dir, en_fin,
    en_get, en_ren, en_sen, en_set, en_spa, en_typ, en_who, en_bye,
    en_asg, en_que, en_ret, en_ena;

#define V9K_SAFE_SERVER "--safe-server"

/*
  One token of the command line against a literal, case-insensitively and
  without libc, because at priority 0 there is no libc worth trusting.
  Written out by hand for the same reason.
*/
static int __far
v9k_tokeq(tok, end, lit) char __far * tok; char __far * end; char * lit; {
    char a, b;

    while (tok < end && *lit) {
        a = *tok++;
        b = *lit++;
        if (a >= 'A' && a <= 'Z') a += 'a' - 'A';
        if (b >= 'A' && b <= 'Z') b += 'a' - 'A';
        if (a != b)
          return(0);
    }
    return(tok == end && *lit == '\0');
}

static void __far
v9k_set_srvcaps(void)
{
    char __far * p;
    char __far * tok;

    p = _LpCmdLine;
    if (p) {
        while (*p) {
            while (*p == ' ' || *p == '\t')
              p++;
            if (!*p)
              break;
            tok = p;
            while (*p && *p != ' ' && *p != '\t')
              p++;
            if (v9k_tokeq(tok,p,V9K_SAFE_SERVER)) {
                v9k_srvcaps_safe = 1;
                while (tok < p)             /* Blank it: cmdlin() must   */
                  *tok++ = ' ';             /* never see an option it     */
            }                               /* would call XFATAL on.      */
        }
    }

    /* What a file transfer needs, in either direction, plus the command
       that lets the far end shut the server down again. */
    en_get = en_sen = en_fin = 3;

    if (!v9k_srvcaps_safe) {
        en_xit = en_cwd = en_cpy = en_del = en_mkd = en_rmd = en_dir =
          en_ren = en_set = en_spa = en_typ = en_who = en_bye = en_asg =
          en_que = en_ret = en_ena = 3;
    }
}

/*
  Priority 0: before __Init_Argv at priority 1, which is the whole point.
  Far record for the same reason the one above is far -- PORTING.md SS16h.
*/
static struct v9k_rt_init __based(__segname("XI")) v9k_srvcaps_rec =
    { 1, 0, v9k_set_srvcaps };

/*
  The file output buffer size, for the same reason and by the same mechanism.

  ckcker.h defines OBUFSIZE as 1024 on the branch this build takes, and
  defines it UNGUARDED, so ckvictor.h cannot pre-empt it the way it does
  DRPSIZ.  It does not need to.  OBUFSIZE is read exactly twice -- to give
  the int zobufsize its initial value (ckcmai.c:1652), and to bound SET
  BUFFERS, which NOICP removes.  The two places that move bytes both read
  the variable:

      getiobs()   malloc(zobufsize)              ckcmai.c:3795
      zmchout()   flush when zoutcnt >= zobufsize  ckcker.h

  so setting the variable before getiobs() runs is the whole change.  main()
  calls getiobs() at ckcmai.c:3331, well after sysinit() at 3176 -- but
  sysinit() is ckutio.c, which is stock, so the earliest hook this port owns
  is the XI table.  Priority 32 rather than 0 because unlike --safe-server
  this has nothing to say about argv and every reason to want the runtime up:
  it is a plain int store, but the buffer it sizes is malloc'd later.

  What it costs is far heap, not DGROUP -- zoutbuffer is a char * under
  DYNAMIC and malloc() is _fmalloc in the large model, so rule 4's second
  budget is the one that pays.  What it is FOR, and how to tell whether it
  worked, is the comment on V9K_OBUFSIZE in ckvictor.h: PORTING.md SS16m
  measured 32 writes and 3.5-7.0 seconds, and the "v9k: wfile" line at exit
  reports the same four numbers for any other size.
*/
extern int zobufsize;                   /* ckcmai.c                     */

static void __far
v9k_set_obufsize(void)
{
    zobufsize = V9K_OBUFSIZE;
}

static struct v9k_rt_init __based(__segname("XI")) v9k_obufsize_rec =
    { 1, 32, v9k_set_obufsize };

/*
  access().  Watcom HAS one; it is wrong about the directory you are in
  when that directory is the root, which is where CKERMITW normally runs.

  Its implementation (bld/clib/file/c/accss.c) is two lines:

      if (_dos_getfileattr(path,&attrs)) return(-1);
      if ((attrs & _A_RDONLY) && pmode == W_OK) return(EACCES);
      return(0);

  -- INT 21h AH=43h, and then the read-only bit.  But a FAT root directory
  has no directory entry of its own, so AH=43h has nothing to read for it.
  It does not fail: it SUCCEEDS and hands back a garbage attribute word,
  measured on Victor MS-DOS 3.1 as 006b for ".", "./", ".\", "\", "A:\"
  and "A:.", as 00ff for "\" seen from a subdirectory, and as 0000 for
  "A:\" seen from the same place.  006b has the read-only bit set and does
  NOT have the directory bit, so Watcom takes the second branch and reports
  EACCES for the directory the program is sitting in.  A named subdirectory
  answers cleanly (0010), and so does "." once the current directory is one.

  That broke RECEIVE outright.  ckufio.c's zchko() creates the incoming
  file, deletes it again, and only then asks access(".",W_OK) whether it
  may create files there; the answer came back no and rcvfil() turned it
  into the protocol error "Write access denied" (PORTING.md SS16h).

  So: for W_OK, a directory is writeable.  That is not a workaround, it is
  what DOS means -- there are no per-directory permissions, and the
  read-only attribute of a directory entry does not stop you creating files
  inside it.  Directory-ness is decided with stat(), which SS16f already
  established answers "." here where libdos-m's did not, and which the same
  probe shows answering every spelling of the root correctly.  Everything
  else keeps Watcom's semantics, with one bug not copied: the library tests
  "pmode == W_OK", so it skips the read-only check for R_OK|W_OK.

  For F_OK and R_OK the getfileattr call has already answered the question
  -- the entry either resolves or it does not -- and DOS has no unreadable
  files.
*/
int
#ifdef CK_ANSIC
access(const char * path, int mode)
#else
access(path,mode) const char * path; int mode;
#endif /* CK_ANSIC */
{
    unsigned attrs;
    struct stat st;

    /* Once, and from the call that stands immediately before the first
       incoming file is created: did the initializer above run, and did
       _fmode survive?  See the comment on v9k_fmode_witness.  Expect
       witness=1 and _fmode=512 (0200h, O_BINARY); witness=0 would mean
       the XI record stopped being reached, and witness=1 with _fmode=256
       would mean something put it back. */
    if (!v9k_fmode_told) {
        v9k_fmode_told = 1;
        debug(F101,"v9k fmode witness","",v9k_fmode_witness);
        debug(F101,"v9k _fmode","",(int)_fmode);
    }

    if (_dos_getfileattr(path,&attrs) != 0)
      return(-1);                       /* No such entry; errno is set  */

    if (!(mode & W_OK))                 /* Existence or readability     */
      return(0);

    if (stat(path,&st) == 0 && S_ISDIR(st.st_mode))
      return(0);                        /* A directory: see above       */

    if (attrs & _A_RDONLY) {
        errno = EACCES;
        return(-1);
    }
    return(0);
}

/*
  gettimeofday().  ckutio.c's rftimer()/gftimer() subtract two of these to
  get elapsed seconds for the transfer-rate display; nothing needs an
  absolute time of day out of it, only that successive calls advance
  monotonically and with better resolution than one second.

  time() supplies the seconds and INT 21h AH=2Ch (Watcom's _dos_gettime)
  the hundredths.  Reading two clocks means they can disagree if the
  second ticks between the calls -- which would show up as a whole second
  of error in a delta, not a rounding error -- so the second is read twice
  and the pair is retried if it moved.  The loop can spin at most once.
*/
int
#ifdef CK_ANSIC
gettimeofday(struct timeval * tv, void * tz)
#else
gettimeofday(tv,tz) struct timeval * tv; void * tz;
#endif /* CK_ANSIC */
{
    struct dostime_t t;
    time_t before, after;

    if (!tv) { errno = EFAULT; return(-1); }

    do {
        before = time((time_t *)0);
        _dos_gettime(&t);
        after  = time((time_t *)0);
    } while (before != after);

    tv->tv_sec  = after;
    tv->tv_usec = (long)t.hsecond * 10000L;

    /* The second argument is deprecated and every caller passes NULL;
       see victorow/sys/time.h for why it is not even a struct here. */
    return(0);
}

/*
  uname().  Asked only as a last resort for "what is this machine called",
  after gethostname() has failed (ckuusx.c getlocalname()), and for the
  version banner (ckutio.c).  A Victor has no hostname, so the constants
  below ARE the answer.  See victorow/sys/utsname.h.
*/
int
#ifdef CK_ANSIC
uname(struct utsname * n)
#else
uname(n) struct utsname * n;
#endif /* CK_ANSIC */
{
    if (!n) { errno = EFAULT; return(-1); }

    /* Once, and from here rather than from anywhere later, because
       sysinit() reaches uname() in EVERY invocation -- including
       "CKERMITW -d -h", which writes a debug log and exits without
       opening the line.  That makes the switch checkable in one 2.5-minute
       boot with no serial line and no host.  0 is the full capability set,
       1 is --safe-server; see the comment on v9k_set_srvcaps(). */
    if (!v9k_srvcaps_told) {
        v9k_srvcaps_told = 1;
        debug(F101,"v9k srvcaps safe","",v9k_srvcaps_safe);
    }

    ckstrncpy(n->sysname, "MS-DOS",  _UTSNAME_LENGTH);
    ckstrncpy(n->nodename,"victor",  _UTSNAME_LENGTH);
    ckstrncpy(n->release, "",        _UTSNAME_LENGTH);
    ckstrncpy(n->version, "",        _UTSNAME_LENGTH);
    ckstrncpy(n->machine, "Victor",  _UTSNAME_LENGTH);
    return(0);
}

/* ------------------------------------------------------------------ */
/* 2a. Symbols orphaned by NOICP                                        */
/* ------------------------------------------------------------------ */

/*
  NOICP removes the interactive command parser, which takes ckuus3.c and
  ckuus4.c largely with it -- but four symbols they own are still
  referenced from code that survives.  This is a rough edge in upstream's
  NOICP configuration, not something this port introduced.

  See PORTING.md SS9c for why NOICP is on at all: with the parser in, the
  program's near data is 98,889 bytes against a 65,536-byte DGROUP.
*/

#ifndef VICTOR_HAVE_COMPAT
/*
  compat_9() / compat_10() reconfigure defaults to match C-Kermit 9 or 10
  (file collision BACKUP, transfer mode AUTOMATIC, and so on).  They are
  reached only from ckcmai.c's command-line handling of the corresponding
  compatibility switch.  With no parser there is nothing to ask for them,
  and C-Kermit 11 defaults are what this port wants regardless.
*/
int compat_9(void)  { return(0); }
int compat_10(void) { return(0); }
#endif /* VICTOR_HAVE_COMPAT */

#ifndef VICTOR_HAVE_GETBASENAME
/*
  Last path component.  ckcfns.c uses it to compare incoming files by name
  rather than by full path, so it has to be right: getting it wrong means
  file-collision checks compare the wrong strings.  Both separators are
  accepted because DOS takes either, and ':' ends a drive prefix.
*/
char *
#ifdef CK_ANSIC
getbasename(char * s)
#else
getbasename(s) char * s;
#endif /* CK_ANSIC */
{
    char * p;

    if (!s) return(s);
    for (p = s; *p; p++) ;              /* Find the end                 */
    while (p > s) {
        --p;
        if (*p == '/' || *p == '\\' || *p == ':')
          return(p + 1);
    }
    return(s);
}
#endif /* VICTOR_HAVE_GETBASENAME */

#ifndef VICTOR_HAVE_GETYESNO
/*
  Ask the user a yes/no question.  There is no user to ask in a build with
  no command parser, so this answers yes (1); the contract is
  0 = no, 1 = yes, 3 = yes-to-all, anything else = quit/EOF.

  The only caller that survives NOICP is rq_confirm_check() in ckcfns.c,
  and it calls this ONLY when SET RECEIVE CONFIRM has been turned on --
  which, with no parser, cannot happen.  So this is unreachable in
  practice; answering yes is the behaviour that matches the default
  (confirmation off, accept the file) if it ever is reached.
*/
int
#ifdef CK_ANSIC
getyesno(char * msg, int flags)
#else
getyesno(msg,flags) char * msg; int flags;
#endif /* CK_ANSIC */
{
    return(1);
}
#endif /* VICTOR_HAVE_GETYESNO */

/* ------------------------------------------------------------------ */
/* 3. TO BE IMPLEMENTED against real Victor hardware                    */
/* ------------------------------------------------------------------ */

/*
  NOTHING BELOW THIS LINE IS A STUB YOU CAN SHIP.

  These are the functions that actually have to work for the milestone
  (SET LINE / SET SPEED / SEND / RECEIVE / GET / SERVER).  They are
  listed here as a checklist; the real implementations live in
  ckutio.c and ckufio.c, which compile clean already, and which reach the
  hardware through the Open Watcom DOS runtime and this file:

    Console  (ckutio.c -> INT 21h, via the Watcom runtime)
      coninc(timeout)   read one char from keyboard, timeout in seconds
      conchk()          how many chars are waiting (0 if none)
      conoc(c)          write one char to screen
      conol(s)          write a string to screen
      congm()/concb()/conres()  save / set cbreak / restore console mode

    Serial   (ckutio.c -> your termios layer or Victor serial API)
      ttopen(name,&local,modem,timo)   open the serial port
      ttclos(x)                        close it
      ttpkt(speed,flow,parity)         put line in packet mode
      ttinc(timo) / ttinl(...)         read
      ttoc(c) / ttol(s,n)              write
      ttsspd(speed)                    SET SPEED  (38400 and up)
      ttflui()                         flush input

    Timing   (ckutio.c)
      rtimer()/gtimer()  elapsed seconds, from the Victor tick counter
      ztime(&s)          wall-clock time string

    Files    (ckufio.c -> Watcom open/read/write/lseek/stat)
      zopeni/zopeno/zinfill/zsoutx/zclose/zchki  -- these are already
      written in portable terms and should need no Victor changes.

  The point of this port is that all of the above already exist in
  ckutio.c/ckufio.c in portable POSIX form.  What this file supplies is
  the layer underneath them, not new C-Kermit code.
*/

/*  C K V I C T O R . C  --  Victor 9000 platform glue for C-Kermit  */

/*
  Serial-only C-Kermit for the Victor 9000 (Sirius 1) under Victor MS-DOS.

  This module supplies the small number of symbols that the portable
  C-Kermit modules reference but that neither newlib nor the modules we
  chose to leave out of the link can provide.  It is deliberately the ONLY
  Victor-specific C file: everything else in the build is unmodified
  upstream code.

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

  Every stub is wrapped in "#ifndef VICTOR_HAVE_<name>".  If your newlib
  already provides one, define that macro (e.g. -DVICTOR_HAVE_SLEEP) and
  the duplicate here disappears.  Start by building without any of them
  and add whichever ones the linker complains about being multiply
  defined -- that is faster than auditing the library up front.
*/

#include "ckcdeb.h"
#include "ckcker.h"

/*
  These give us pid_t / uid_t / gid_t / ssize_t so the definitions below
  match newlib's declarations exactly.  newlib DECLARES all of the process
  calls but DEFINES none of them, which is why this file exists.
*/
#include <sys/types.h>
#include <unistd.h>
#include <sys/stat.h>
#include <pwd.h>

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

#ifndef VICTOR_HAVE_EXEC
int execl(const char * path, const char * a0, ...) { return(-1); }
int execvp(const char * file, char * const argv[]) { return(-1); }
#endif

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

#ifndef VICTOR_HAVE_PIDS
pid_t getpid(void)  { return((pid_t)1); }
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
  alarm()/sysconf(): no interval timers, no runtime configuration query.
  C-Kermit's timeouts on this platform come from the protocol layer's own
  timer, driven by the Victor tick counter (see ztime()/rtimer()).
*/
#ifndef VICTOR_HAVE_ALARM
unsigned alarm(unsigned secs) { return(0); }
#endif

#ifndef VICTOR_HAVE_SYSCONF
long sysconf(int name) { return(-1L); }
#endif

/*
  Environment.  newlib gives us getenv(); putenv() is only used by paths
  that hand an environment to a child process, and there are none.
*/
#ifndef VICTOR_HAVE_PUTENV
int putenv(char * s) { return(-1); }
#endif

/*
  Filesystem calls with no FAT equivalent.
*/
#ifndef VICTOR_HAVE_READLINK
ssize_t
readlink(const char * __restrict path, char * __restrict buf, size_t n) {
    return((ssize_t)-1);
}
#endif

#ifndef VICTOR_HAVE_UMASK
mode_t umask(mode_t m) { return((mode_t)0); }
#endif

#ifndef VICTOR_HAVE_DUP2
int dup2(int a, int b) { return(-1); }
#endif

/* ------------------------------------------------------------------ */
/* 3. TO BE IMPLEMENTED against real Victor hardware                    */
/* ------------------------------------------------------------------ */

/*
  NOTHING BELOW THIS LINE IS A STUB YOU CAN SHIP.

  These are the functions that actually have to work for the milestone
  (SET LINE / SET SPEED / SEND / RECEIVE / GET / SERVER).  They are
  listed here as a checklist; the real implementations live in
  ckutio.c and ckufio.c, which compile clean for ia16 already, and which
  reach the hardware through your newlib:

    Console  (ckutio.c -> your console driver)
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

    Files    (ckufio.c -> newlib open/read/write/lseek/stat)
      zopeni/zopeno/zinfill/zsoutx/zclose/zchki  -- these are already
      written in portable terms and should need no Victor changes.

  The point of this port is that all of the above already exist in
  ckutio.c/ckufio.c in portable POSIX form.  What you supply is the
  newlib layer underneath them, not new C-Kermit code.
*/

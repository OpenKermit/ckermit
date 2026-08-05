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

/*
  ckvictor.h is force-included ahead of this line by both makefiles, and it
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
  match newlib's declarations exactly.  newlib DECLARES all of the process
  calls but DEFINES none of them, which is why this file exists.
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
#ifndef __WATCOMC__
#include <sys/reent.h>
#endif /* __WATCOMC__ */

#ifdef __WATCOMC__
/*
  The Open Watcom build (victorow.mak) reaches MS-DOS through the library
  rather than through this file.  Watcom's DOS runtime already implements
  the whole of section 0 below -- open/read/write/lseek/stat, the console,
  and opendir/readdir/closedir over the same FindFirst/FindNext DTA that
  section 0a builds by hand -- and it ships intdos(), so the one thing we
  still have to do for ourselves (section 0b, FIONREAD) needs no inline
  assembler.  <sys/utsname.h> is here because Watcom has no uname() and
  section 1 stubs one; see victorow/sys/utsname.h.
*/
#include <dos.h>
#include <stdarg.h>
#include <sys/utsname.h>

/*
  Section 0's DOS function numbers go with it; this is the only one the
  Watcom build still issues by hand (section 0b).
*/
#define DOS_CHK_STDIN   0x0b            /* Check standard input status  */

/*
  ckufio.c's "extern long timezone" is aliased to this by ckvictor.h,
  because Watcom's own timezone is declared __near and a bare extern in
  the large model is __far.  Nothing reads it: see the comment there.
*/
long v9k_timezone = 0L;
#endif /* __WATCOMC__ */

#ifndef __WATCOMC__
/* ------------------------------------------------------------------ */
/* 0. Talking to MS-DOS                                                 */
/* ------------------------------------------------------------------ */

/*
  This toolchain ships no <dos.h> and no int86()/intdos(), so the INT 21h
  calls below are written as inline asm.  Three things make that simpler
  here than it looks:

    - Medium model means data is NEAR.  A "char *" is a 16-bit offset, so
      the DX half of every DS:DX argument below is just the pointer
      itself.  The DS half is NOT free -- see the fourth point.

    - The 8088 has no SETcc (that is 386 and later), so the carry flag has
      to be turned into a value inside the asm block.  Every block below
      does that with a branch over a constant load, leaving exactly ONE
      output operand, in %ax.

      Do NOT do it with a second "=r" output and "sbb %1,%1", however
      natural that looks.  On ia16 the "r" class includes the SEGMENT
      registers, and gcc will cheerfully allocate one: the first version
      of _write_r below compiled to "mov $0x4000,%ax; mov %ax,%ds",
      pointing DS at segment 0x4000 and corrupting every subsequent data
      reference.  It got as far as MAME and printed a screen of garbage.
      One output, in a named register, and the problem cannot arise.

    - "memory" is on the clobber list everywhere DOS writes through a
      pointer we handed it, because the compiler cannot see those stores.

    - EVERY pointer handed to INT 21h needs DS set explicitly, and this is
      the subtle one.  DOS reads buffer addresses from DS:DX.  In this
      memory model SS == DS == DGROUP, and ia16-gcc exploits that: it
      addresses locals and statics with an %ss: prefix and treats %ds as a
      general SCRATCH REGISTER, restoring it with "push %ss; pop %ds" only
      on return.  So at the point of an asm block, %ds may hold anything
      at all -- in _write_r below it held 0x4000, a spilled copy of the
      AH=40h constant.  The call then wrote from 0x4000:DX.

      The failure is quiet and convincing: DOS returns success, the byte
      COUNT is right, and the screen fills with the wrong memory.  It took
      a run under MAME to see it.  DOS_DS_CALL sets DS from SS around the
      interrupt; POP does not disturb the flags, so the carry test after
      it is still valid.
*/

/*
  int $0x21 with DS pointed at DGROUP, and DS restored afterwards.
  Use this for every call that passes a pointer; the plain "int $0x21"
  is only safe for calls that pass no address at all.
*/
#define DOS_DS_CALL(after)   "push %%ds\n\t"   \
                             "push %%ss\n\t"   \
                             "pop %%ds\n\t"    \
                             "int $0x21\n\t"   \
                             "pop %%ds\n\t"    \
                             after

/*
  Only the directory calls and the console poll live here.  Everything
  else -- open, read, write, lseek, stat and the rest -- is already
  implemented over INT 21h by libdos-m.a and must not be duplicated.
*/

#define DOS_SET_DTA     0x1a            /* Set Disk Transfer Address    */
#define DOS_FIND_FIRST  0x4e            /* Find first matching file     */
#define DOS_FIND_NEXT   0x4f            /* Find next matching file      */
#define DOS_CHK_STDIN   0x0b            /* Check standard input status  */

/*
  Attribute mask for FindFirst.  DOS always returns ordinary and read-only
  files; the mask says which SPECIAL kinds to include as well.  Directories
  are essential -- traverse() recurses on them.  Hidden and system are
  included so that a wildcard expansion sees the same files a Unix readdir()
  would.  Volume label (0x08) is deliberately left out: it is not a file and
  would confuse the name matching.
*/
#define DOS_FIND_ATTRS  0x16            /* hidden | system | directory  */

static VOID
#ifdef CK_ANSIC
dos_set_dta(void * p)
#else
dos_set_dta(p) void * p;
#endif /* CK_ANSIC */
{
    __asm__ __volatile__ (DOS_DS_CALL("")
                          :
                          : "a" ((unsigned int)(DOS_SET_DTA << 8)),
                            "d" (p)
                          : "cc");
}

/*
  FindFirst / FindNext.  Both fill the current DTA.  Return 0 on success,
  or the DOS error code (2 = file not found, 3 = path not found,
  18 = no more files) on failure.
*/

static int
#ifdef CK_ANSIC
dos_find_first(const char * pattern, unsigned int attrs)
#else
dos_find_first(pattern,attrs) const char * pattern; unsigned int attrs;
#endif /* CK_ANSIC */
{
    unsigned int ax;

    __asm__ __volatile__ (DOS_DS_CALL("jc 1f\n\t"
                                      "xor %%ax,%%ax\n"
                                      "1:")
                          : "=a" (ax)
                          : "0" ((unsigned int)(DOS_FIND_FIRST << 8)),
                            "d" (pattern), "c" (attrs)
                          : "cc", "memory");
    return((int)ax);
}

static int
dos_find_next() {
    unsigned int ax;

    __asm__ __volatile__ ("int $0x21\n\t"
                          "jc 1f\n\t"
                          "xor %%ax,%%ax\n"
                          "1:"
                          : "=a" (ax)
                          : "0" ((unsigned int)(DOS_FIND_NEXT << 8))
                          : "cc", "memory");
    return((int)ax);
}

/* ------------------------------------------------------------------ */
/* 0a. Directory reading -- opendir / readdir / closedir                */
/* ------------------------------------------------------------------ */

/*
  newlib's <sys/dirent.h> declares these three and then says, verbatim,
  "FIXME: implement these!".  struct __msdos_DIR is only ever forward
  declared, so its definition is entirely ours.

  The header's struct dirent is not an accident -- it is a DOS DTA with
  field names on it:

      offset  0   d_dta[21]     reserved for DOS's own search state
              21  d_attr        attribute
              22  d_time        time
              24  d_date        date
              26  d_size        size (long)
              30  d_name[]      ASCIIZ 8.3 name, 13 bytes

  which is byte-for-byte the layout INT 21h 4Eh/4Fh writes.  So we point
  the DTA straight at the caller's struct dirent and let DOS fill it in;
  readdir() copies nothing.  (Verified at compile time below.)

  THE DTA IS GLOBAL STATE, AND IT IS CONTESTED.  It belongs to the PSP, not
  to a search, and DOS's FindNext takes its continuation state from
  whatever the DTA currently points at.  Two things follow:

    1. Each open DIR carries its own DTA, so nested walks do not corrupt
       each other.  traverse() in ckufio.c recurses with one open DIR per
       directory level, so this is not a theoretical concern -- it is the
       normal case.  (The reference implementation in
       ~/projects/newlibc/phase3_newlib/libgloss/dirent.c gets this wrong
       twice over: a single shared static entry, and LIBGLOSS_MAX_DIRS of
       2.  Neither survives a depth-3 walk.)

    2. We re-point the DTA before EVERY FindNext, never once at open time.
       This is not tidiness.  libdos-m.a's own stat() is implemented over
       INT 21h 1Ah + 4Eh -- it sets the DTA to its own buffer and does not
       put it back -- and traverse() calls stat() on each entry inside the
       readdir() loop.  Setting the DTA once per DIR would leave the very
       next FindNext continuing stat()'s search instead of ours.
*/

struct __msdos_DIR {
    struct dirent d_ent;                /* also this DIR's DOS DTA      */
    int           d_pending;            /* an unread entry is in d_ent  */
    int           d_done;               /* FindFirst/Next said no more  */
#ifdef V9K_DIRTRACE
    int           d_seen;               /* Entries handed out so far    */
#endif /* V9K_DIRTRACE */
};

#ifdef V9K_HEAPREPORT
_PROTOTYP( VOID v9k_heapmark, (void) );  /* Section 0e, defined below */
#endif /* V9K_HEAPREPORT */

#ifdef V9K_DIRTRACE
/*
  The trace primitive.  write(2) and nothing else -- see the note at the
  call in opendir() for why this cannot be printf.  Up to two strings, two
  more strings, and one number, which covers every call site here without
  needing varargs (and varargs would want stdio to be useful anyway).
*/
static VOID
#ifdef CK_ANSIC
v9k_trace(char * a, char * b, char * c, char * d, char * e, int n)
#else
v9k_trace(a,b,c,d,e,n) char *a, *b, *c, *d, *e; int n;
#endif /* CK_ANSIC */
{
    char buf[160];
    char num[8];
    char * s[5];
    int i, k, j, neg;

    s[0] = a; s[1] = b; s[2] = c; s[3] = d; s[4] = e;
    k = 0;
    for (i = 0; i < 5; i++) {
        if (!s[i])
          continue;
        for (j = 0; s[i][j] && k < (int)sizeof(buf) - 12; j++)
          buf[k++] = s[i][j];
    }
    neg = (n < 0);
    if (neg) n = -n;
    j = 0;
    do { num[j++] = (char)('0' + (n % 10)); n /= 10; } while (n && j < 7);
    if (neg) buf[k++] = '-';
    while (j > 0) buf[k++] = num[--j];
    buf[k++] = '\r';
    buf[k++] = '\n';
    write(2,buf,(unsigned)k);           /* #undef'd at the top of this
                                           file: the library's, not ours */
}
#endif /* V9K_DIRTRACE */

/*
  If <sys/dirent.h> ever drifts away from the DTA layout, fail here at
  compile time rather than by returning garbage filenames at run time.
*/
#define VICTOR_DTA_OFF(f) ((int)__builtin_offsetof(struct dirent,f))

typedef char victor_dta_layout_check[
    (sizeof(struct dirent) >= 43
     && VICTOR_DTA_OFF(d_attr) == 21
     && VICTOR_DTA_OFF(d_time) == 22
     && VICTOR_DTA_OFF(d_date) == 24
     && VICTOR_DTA_OFF(d_size) == 26
     && VICTOR_DTA_OFF(d_name) == 30) ? 1 : -1];

DIR *
#ifdef CK_ANSIC
opendir(const char * path)
#else
opendir(path) const char * path;
#endif /* CK_ANSIC */
{
    DIR * d;
    char pattern[CKMAXPATH];
    int n, rc;

    if (!path) path = "";

    /*
      Build the DOS search pattern, "<path>\*.*".

      Two details matter here, and both are about not trusting DOS to be
      liberal:

        - "." is dropped rather than passed through.  ckufio.c asks for the
          current directory as "" or ".", which would give "./*.*"; that
          relies on DOS resolving a "." component, which not every DOS does
          the same way.  "*.*" alone is unambiguous everywhere.

        - Separators are rewritten to '\'.  ckufio.c is a Unix module and
          uses '/' throughout (its ISDIRSEP is '/'), and most DOS versions
          do accept '/' in INT 21h paths -- but "most" is not the standard
          this port holds itself to (SS2), and Victor MS-DOS 3.1 is old
          enough to be worth not gambling on.
    */
    if (path[0] == '.' && path[1] == '\0')
      path = "";

    n = (int)strlen(path);
    if (n + 5 >= (int)sizeof(pattern)) {
        errno = ENAMETOOLONG;
        return((DIR *)0);
    }
    memcpy(pattern,path,(size_t)n);
    for (rc = 0; rc < n; rc++)          /* '/' -> '\' for DOS           */
      if (pattern[rc] == '/') pattern[rc] = '\\';
    if (n > 0 && pattern[n-1] != '\\' && pattern[n-1] != ':')
      pattern[n++] = '\\';
    memcpy(pattern+n,"*.*",4);          /* includes the NUL */

    if (!(d = (DIR *) malloc(sizeof(struct __msdos_DIR)))) {
        errno = ENOMEM;
        return((DIR *)0);
    }

    /*
      Do the FindFirst now, so that opendir() fails on a directory that
      does not exist -- which is what every caller assumes -- rather than
      succeeding and returning an empty directory.  The entry it produces
      is held for the first readdir().
    */
#ifdef V9K_HEAPREPORT
    v9k_heapmark();                     /* Section 0e: see the note there
                                           on why expansion is sampled  */
#endif /* V9K_HEAPREPORT */
    dos_set_dta(&d->d_ent);
    rc = dos_find_first(pattern,DOS_FIND_ATTRS);

#ifdef V9K_DIRTRACE
    /*
      PORTING.md SS15 asked for exactly this: "the cheapest instrument is a
      temporary _write_r trace of the pattern string opendir() actually
      receives", and _write_r is what it has to be.  printf was tried first
      and is not usable here: stdout's buffer is itself the first thing the
      program allocates, so a trace that goes through stdio re-enters stdio
      during its own initialisation, and the measurement disappears -- which
      is a whole MAME run spent learning that the instrument was broken and
      not the code.  v9k_trace() is write(2) and hand-formatted digits: no
      buffering, no allocation, nothing to re-enter.
    */
    v9k_trace("v9k opendir(",(char *)path,") -> ",pattern," rc=",rc);
#endif /* V9K_DIRTRACE */

    d->d_pending = (rc == 0);
    d->d_done    = (rc != 0);
#ifdef V9K_DIRTRACE
    d->d_seen    = 0;
#endif /* V9K_DIRTRACE */

    if (rc == 3) {                      /* Path not found: no such dir  */
        free((char *)d);
        errno = ENOENT;
        return((DIR *)0);
    }
    /*
      rc == 2 (file not found) means the directory exists but nothing
      matched -- an empty directory.  That is a valid DIR that yields no
      entries, not an error.
    */
    return(d);
}

struct dirent *
#ifdef CK_ANSIC
readdir(DIR * d)
#else
readdir(d) DIR * d;
#endif /* CK_ANSIC */
{
    if (!d) { errno = EBADF; return((struct dirent *)0); }

    if (d->d_pending) {                 /* Held over from FindFirst     */
        d->d_pending = 0;
#ifdef V9K_DIRTRACE
        d->d_seen = 1;
#endif /* V9K_DIRTRACE */
        return(&d->d_ent);
    }
    if (d->d_done)
      return((struct dirent *)0);

    dos_set_dta(&d->d_ent);             /* See note above -- every time */
    if (dos_find_next() != 0) {
        d->d_done = 1;
#ifdef V9K_DIRTRACE
        /* One line per directory, not one per file: the screen holds 25
           lines and a root directory is longer than that. */
        v9k_trace("v9k readdir end, entries=",(char *)0,(char *)0,
                  (char *)0,(char *)0,d->d_seen);
#endif /* V9K_DIRTRACE */
        return((struct dirent *)0);     /* No more; errno unchanged     */
    }
#ifdef V9K_DIRTRACE
    d->d_seen++;
#endif /* V9K_DIRTRACE */
    return(&d->d_ent);
}

int
#ifdef CK_ANSIC
closedir(DIR * d)
#else
closedir(d) DIR * d;
#endif /* CK_ANSIC */
{
    if (!d) { errno = EBADF; return(-1); }
    free((char *)d);                    /* DOS searches hold no handle  */
    return(0);
}

/* ------------------------------------------------------------------ */
/* 0c. The console: raw input and CRLF output                           */
/* ------------------------------------------------------------------ */

/*
  libdos-m.a's _read_r and _write_r are bare INT 21h AH=3Fh / AH=40h with
  the file descriptor passed straight through to DOS.  That is exactly
  right for files, and wrong for the console in both directions:

    OUTPUT  DOS handle writes are literal.  A '\n' moves the cursor down
            and leaves it in the same column, so C-Kermit's output walks
            diagonally off the right of the screen.  This is visible the
            first time the program prints anything -- "CKERMIT -h" under
            MAME produced a perfect staircase.  Console output needs
            LF -> CR LF; nothing else does.

    INPUT   DOS handle reads on CON are COOKED.  AH=3Fh line-edits and
            does not return until Enter.  coninc() asks for one character
            and expects one character, so it would block a whole line.

  We override _read_r and _write_r rather than read() and write() because
  newlib's stdio calls the _r forms directly -- intercepting the public
  wrappers would catch ckutio.c's conol() but miss every printf().  Ours
  are the only definitions the linker sees, so libdos-m.a's copies are
  never pulled in.

  Everything that is not fd 0/1/2 falls through to exactly the INT 21h
  call libdos-m.a would have made, so file I/O is unchanged.

  Per SS2, all of this is INT 21h and none of it is BIOS: AH=07h (raw
  console input, no echo), AH=0Bh (input status), AH=40h (handle write).
*/

#define DOS_HANDLE_READ  0x3f
#define DOS_HANDLE_WRITE 0x40
#define DOS_RAW_STDIN    0x07           /* Read char, no echo, no ^C    */

/* Defined with the rest of the console poll in SS0b below. */
_PROTOTYP( static int dos_stdin_ready, (void) );

/* Raw INT 21h handle write.  Returns bytes written, or -1 with CF set. */
static int
#ifdef CK_ANSIC
dos_write(int fd, const char * buf, unsigned int len)
#else
dos_write(fd,buf,len) int fd; const char * buf; unsigned int len;
#endif /* CK_ANSIC */
{
    unsigned int ax;

    if (!len) return(0);
    __asm__ __volatile__ (DOS_DS_CALL("jnc 1f\n\t"
                                      "mov $-1,%%ax\n"
                                      "1:")
                          : "=a" (ax)
                          : "0" ((unsigned int)(DOS_HANDLE_WRITE << 8)),
                            "b" ((unsigned int)fd),
                            "c" (len),
                            "d" (buf)
                          : "cc", "memory");
    return((int)(short)ax);             /* -1 on error, else the count  */
}

static int
#ifdef CK_ANSIC
dos_read(int fd, char * buf, unsigned int len)
#else
dos_read(fd,buf,len) int fd; char * buf; unsigned int len;
#endif /* CK_ANSIC */
{
    unsigned int ax;

    if (!len) return(0);
    __asm__ __volatile__ (DOS_DS_CALL("jnc 1f\n\t"
                                      "mov $-1,%%ax\n"
                                      "1:")
                          : "=a" (ax)
                          : "0" ((unsigned int)(DOS_HANDLE_READ << 8)),
                            "b" ((unsigned int)fd),
                            "c" (len),
                            "d" (buf)
                          : "cc", "memory");
    return((int)(short)ax);             /* -1 on error, else the count  */
}

/* One character from the keyboard, raw: no echo, no line editing. */
static int
dos_getch() {
    unsigned int ax;

    __asm__ __volatile__ ("int $0x21"
                          : "=a" (ax)
                          : "0" ((unsigned int)(DOS_RAW_STDIN << 8))
                          : "cc");
    return((int)(ax & 0xff));
}

_ssize_t
#ifdef CK_ANSIC
_write_r(struct _reent * r, int fd, const void * buf, size_t n)
#else
_write_r(r,fd,buf,n) struct _reent * r; int fd; const void * buf; size_t n;
#endif /* CK_ANSIC */
{
    const char * p = (const char *)buf;
    unsigned int i, run;
    int rc;

    if (fd != 1 && fd != 2) {           /* Files: unchanged behaviour   */
        rc = dos_write(fd,p,(unsigned int)n);
        if (rc < 0) { if (r) r->_errno = EIO; return((_ssize_t)-1); }
        return((_ssize_t)rc);
    }

    /*
      Console.  Emit maximal runs of non-newline text in one DOS call,
      and CR LF for each '\n'.  No buffer is used -- writing straight
      out of the caller's memory keeps this off the 64K DGROUP, which
      matters more here than the extra INT 21h calls cost.
    */
    for (i = 0; i < (unsigned int)n; ) {
        for (run = 0; i + run < (unsigned int)n && p[i+run] != '\n'; run++) ;
        if (run > 0) {
            if (dos_write(fd,p+i,run) < 0) {
                if (r) r->_errno = EIO;
                return((_ssize_t)-1);
            }
            i += run;
        }
        if (i < (unsigned int)n) {      /* Sitting on a '\n'            */
            if (dos_write(fd,"\r\n",2) < 0) {
                if (r) r->_errno = EIO;
                return((_ssize_t)-1);
            }
            i++;
        }
    }
    return((_ssize_t)n);                /* Report the caller's count    */
}

_ssize_t
#ifdef CK_ANSIC
_read_r(struct _reent * r, int fd, void * buf, size_t n)
#else
_read_r(r,fd,buf,n) struct _reent * r; int fd; void * buf; size_t n;
#endif /* CK_ANSIC */
{
    char * p = (char *)buf;
    unsigned int i;
    int c, rc;

    if (fd != 0) {                      /* Files: unchanged behaviour   */
        rc = dos_read(fd,p,(unsigned int)n);
        if (rc < 0) { if (r) r->_errno = EIO; return((_ssize_t)-1); }
        return((_ssize_t)rc);
    }
    if (!n) return(0);

    /*
      Raw console, VMIN=1 / VTIME=0 semantics: block for the first
      character, then take whatever else is already buffered without
      waiting.  coninc() asks for one byte and gets one byte.

      DOS reports Enter as CR.  C-Kermit's line reader wants NL, and
      ckucmd.c compares against '\n', so translate here -- the mirror of
      what _write_r does on the way out.
    */
    c = dos_getch();
    if (c == '\r') c = '\n';
    p[0] = (char)c;

    for (i = 1; i < (unsigned int)n && dos_stdin_ready(); i++) {
        c = dos_getch();
        if (c == '\r') c = '\n';
        p[i] = (char)c;
    }
    return((_ssize_t)i);
}
#endif /* __WATCOMC__ -- end of sections 0, 0a and 0c */

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

/* AH=44h is IOCTL; AL=06h is "get input status".  Both builds need it, so
   unlike DOS_CHK_STDIN it is spelled out here rather than per-toolchain. */
#define DOS_IOCTL_INSTAT 0x4406

#ifdef __WATCOMC__
/*
  The Watcom half of the same call.  It is deliberately NOT kbhit(): the
  Watcom DOS kbhit() reads the BIOS keyboard, and this port is INT 21h only
  (Victor MS-DOS 3.1 has no IBM-compatible BIOS -- PORTING.md, and the whole
  reason one binary runs on two DOSes).  intdos() puts the same AH=0Bh call
  behind a C interface, which is what the gcc build needed inline asm for.
*/
static int
dos_stdin_ready() {
    union REGS r;

    r.h.ah = DOS_CHK_STDIN;
    intdos(&r,&r);
    return((r.h.al) ? 1 : 0);
}

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
    if (r.w.cflag)                      /* See the gcc arm below for why */
      return(1);                        /* an error means "say ready"    */
    return((r.h.al) ? 1 : 0);
}
#else /* __WATCOMC__ */
static int
dos_stdin_ready() {
    unsigned int ax;

    __asm__ __volatile__ ("int $0x21"
                          : "=a" (ax)
                          : "0" ((unsigned int)(DOS_CHK_STDIN << 8))
                          : "cc");
    return((ax & 0xff) ? 1 : 0);
}

/*
  Neither of these passes DOS a pointer, so both use the plain "int $0x21"
  rather than DOS_DS_CALL -- see the note on DS at the top of section 0.

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
    unsigned int ax;

    __asm__ __volatile__ ("int $0x21\n\t"
                          "jnc 1f\n\t"
                          "mov $0x00ff,%%ax\n"
                          "1:"
                          : "=a" (ax)
                          : "0" ((unsigned int)DOS_IOCTL_INSTAT),
                            "b" ((unsigned int)fd)
                          : "cc");
    return((ax & 0xff) ? 1 : 0);
}
#endif /* __WATCOMC__ */

/*
  Written ANSI-only rather than in this file's usual dual-prototype style:
  a variadic function cannot be declared K&R and still be read with
  va_start.  Both toolchains always define CK_ANSIC, so the K&R arm would
  be dead code that never compiled.

  gcc's __builtin_va_* are spelled out rather than <stdarg.h> in the gcc
  build; Watcom has no such builtins, so there it is the standard header.
*/
int
ioctl(int fd, int request, ...) {
    int * countp;
#ifdef __WATCOMC__
    va_list ap;
#else
    __builtin_va_list ap;
#endif /* __WATCOMC__ */

    if (request != FIONREAD && request != TIOCMGET) {
        errno = EINVAL;
        return(-1);
    }
#ifdef __WATCOMC__
    va_start(ap,request);
    countp = va_arg(ap,int *);
    va_end(ap);
#else
    __builtin_va_start(ap,request);
    countp = __builtin_va_arg(ap,int *);
    __builtin_va_end(ap);
#endif /* __WATCOMC__ */

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
  transferred" (PORTING.md SS16a), on both builds, identically.

  ckutio.c is stock upstream, so the blocking has to happen underneath it.
  ckvictor.h renames read() to v9k_read() for every module in the build,
  and this is that function.  Everything that is not the communications
  device goes straight through to the library's read(), so section 0c's
  console handling under gcc and Watcom's text-mode translation are both
  left exactly as they were -- which is the reason for renaming rather than
  defining read() over the top of either library's.
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
  on, and because alarm()'s own argument is in seconds.  A deadline of
  time()+n therefore fires somewhere between n and n+1 seconds, never
  early; Kermit's timeouts are 5-10 seconds, so the jitter is noise.
*/
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
    h = signal(SIGALRM,SIG_IGN);        /* Peek ...                     */
    if (h == SIG_ERR)                   /* ... signal() refused the     */
      return(1);                        /* number: nothing was changed  */
    signal(SIGALRM,h);                  /* ... otherwise put it back    */
    if (h != SIG_DFL && h != SIG_IGN)
      (*h)(SIGALRM);                    /* timerh(): does not return    */
    return(1);
}

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

    for (;;) {
        if (v9k_ser_active()) {
            rc = v9k_ser_get((char *)buf,(int)n);
            if (rc > 0)
              return(rc);
        } else if (dos_dev_input_ready(fd)) {
            rc = (int)read(fd,buf,n);   /* Undef'd above: the real one  */
            if (rc != 0)                /* Bytes, or a genuine error    */
              return(rc);
        }
        if (v9k_alarm_check()) {
            /*
              Only reached when the alarm expired with no handler to run.
              EINTR is the case mygetbuf() and ttinl() already document, so
              the caller retries -- and the retry blocks again rather than
              spinning, because the alarm cleared itself above.
            */
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
#ifdef V9K_HEAPREPORT
    v9k_heapmark();
#endif /* V9K_HEAPREPORT */
    /*
      fd > 2 as well as fd == ttyfd because ttopen() sets ttyfd to 0 in
      remote mode, where the "line" is the console and section 0c owns it.
    */
    if (fd > 2 && fd == ttyfd)
      return((V9K_RTYPE)v9k_comm_read(fd,buf,(unsigned int)n));
    return(read(fd,buf,n));
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
  where it put a byte-correct Send-Init packet on the wire in both builds.
*/
_PROTOTYP( V9K_WTYPE v9k_write, (int, const void *, V9K_WCOUNT) );

V9K_WTYPE
#ifdef CK_ANSIC
v9k_write(int fd, const void * buf, V9K_WCOUNT n)
#else
v9k_write(fd,buf,n) int fd; const void * buf; V9K_WCOUNT n;
#endif /* CK_ANSIC */
{
#ifdef V9K_HEAPREPORT
    v9k_heapmark();
#endif /* V9K_HEAPREPORT */
    if (fd > 2 && fd == ttyfd && v9k_ser_active())
      return((V9K_WTYPE)v9k_ser_put((const char *)buf,(int)n));
    return(write(fd,buf,n));
}

/* ------------------------------------------------------------------ */
/* 0e. Heap headroom -- the binding constraint, measured                */
/* ------------------------------------------------------------------ */

#ifdef V9K_HEAPREPORT
/*
  PORTING.md SS15 says heap headroom, not static DGROUP, is what limits the
  gcc build, and SS16e is where that stopped being an inference: the gcc
  build reached the file-open step of a real transfer and MS-DOS Kermit
  printed "TESTFILE.TXT: Not enough space" -- newlib's fopen() could not get
  its FILE and its BUFSIZ buffer.

  In the medium model the heap and the stack share what is left of the one
  64K DGROUP: the heap grows up from the end of .bss and the stack grows
  down from the top, so the free space at any instant is SP minus the
  current break.  Nothing in the C library reports that number, and a debug
  build is not available to ask -- the debug log does not fit in this build
  (SS16e).  So we take it ourselves, at every read() and write() of the
  transfer and at every opendir(), and keep the smallest one.

  Sampling from opendir() is not decoration: wildcard expansion is the other
  thing the near heap is too small for, and it fails silently -- ckufio.c's
  zxpand() returns 0 when its malloc is refused, and ckuusy.c prints "No
  files for -s" when the buffer for the REAL message could not be had, so
  an exhausted heap and a pattern that matched nothing print the same line.
  Interposing on malloc() to catch that directly was tried twice and does
  not work on this toolchain -- ld's --wrap dies on the far-call
  relocations, and a malloc() defined here simply never gets called -- so
  the headroom at the moment of the expansion is the measurement that is
  actually available.  (SS16f.)

  Cost when V9K_HEAPREPORT is off: nothing at all, not even the two words.
  It is a diagnostic switch, like KEEP_DEBUG, and it is not set by either
  makefile:

      make -f victor9k.mak XFLAGS=-DV9K_HEAPREPORT

  The Watcom build has a far heap outside DGROUP, so SP and the break are
  not in the same address space and the subtraction would be meaningless.
  It reports nothing there and says so at exit.
*/
static unsigned int v9k_heaplow = 0xffffU;   /* Low-water headroom       */
static unsigned int v9k_heapmin = 0xffffU;   /* Break at that moment     */
static int v9k_heapatx = 0;                  /* atexit() registered yet? */

_PROTOTYP( VOID v9k_heapreport, (void) );

VOID
v9k_heapmark() {
#ifndef __WATCOMC__
    unsigned int sp, brk;
    char * p;

    /*
      Register the report from here rather than from the install path in
      section 1e, which only runs when a line is opened.  The runs that
      most need this number -- a wildcard expansion that never touches the
      serial port -- would otherwise measure and then say nothing.
    */
    if (!v9k_heapatx) {
        v9k_heapatx = 1;
        atexit(v9k_heapreport);
    }
    __asm__ __volatile__ ("movw %%sp,%0" : "=r" (sp));
    p = (char *) sbrk(0);
    brk = (unsigned int)(size_t) p;     /* Near pointer: 16 bits        */
    if (sp > brk && (unsigned int)(sp - brk) < v9k_heaplow) {
        v9k_heaplow = (unsigned int)(sp - brk);
        v9k_heapmin = brk;
    }
#endif /* __WATCOMC__ */
}


VOID
v9k_heapreport() {
#ifndef __WATCOMC__
    if (v9k_heaplow == 0xffffU)
      printf("v9k heap: never sampled\n");
    else
      printf("v9k heap: low-water %u bytes free (break at %u of 65536)\n",
             v9k_heaplow, v9k_heapmin);
#else
    printf("v9k heap: far heap, not in DGROUP -- not measured\n");
#endif /* __WATCOMC__ */
}
#endif /* V9K_HEAPREPORT */

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
       deadline already in the past would wrap into a huge "time left". */
    if (v9k_alarm_on && v9k_alarm_at > now)
      left = (unsigned)(v9k_alarm_at - now);

    if (secs) {
        v9k_alarm_at = now + (time_t)secs;
        v9k_alarm_on = 1;
    } else {
        v9k_alarm_on = 0;
    }
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
  __restrict is spelled out because newlib's <unistd.h> declares readlink()
  that way and the definition has to agree.  Open Watcom's C is C89 and has
  no such keyword -- and no declaration of readlink() either, so there is
  nothing to agree with; victorow/ckowsys.h declares the plain form.
*/
#ifdef __WATCOMC__
#define VICTOR_RESTRICT
#else
#define VICTOR_RESTRICT __restrict
#endif /* __WATCOMC__ */

#ifndef VICTOR_HAVE_READLINK
ssize_t
readlink(const char * VICTOR_RESTRICT path, char * VICTOR_RESTRICT buf,
         size_t n) {
    return((ssize_t)-1);
}
#endif

#ifndef VICTOR_HAVE_UMASK
mode_t umask(mode_t m) { return((mode_t)0); }
#endif

/* ------------------------------------------------------------------ */
/* 1a. Small gaps in libdos-m.a                                         */
/* ------------------------------------------------------------------ */

/*
  sleep() over the usleep() the library already has.  Looped a second at a
  time rather than computed as secs*1000000: "unsigned int" is 16 bits here,
  so the multiplication would have to be widened by hand anyway, and any
  sleep longer than about 71 minutes would overflow even 32 bits of
  microseconds.  The loop has neither problem.
*/
#ifndef VICTOR_HAVE_SLEEP
unsigned int
#ifdef CK_ANSIC
sleep(unsigned int secs)
#else
sleep(secs) unsigned int secs;
#endif /* CK_ANSIC */
{
    while (secs-- > 0)
      usleep(1000000UL);
    return(0);                          /* Never interrupted: no signals */
}
#endif /* VICTOR_HAVE_SLEEP */

/*
  stat() of the CURRENT directory.

  libdos-m's stat() is FindFirst underneath, and FindFirst has no answer for
  the directory you are already in: measured on Victor MS-DOS 3.1, stat("."),
  stat("./") and stat(".\") all return -1, while stat("TEST") on a real
  subdirectory and stat("TESTFILE.TXT") on a real file both work.  A Unix
  stat() answers all five.

  That one gap is enough to break wildcard expansion outright.  traverse()
  in ckufio.c begins every walk at "./" and asks xisdir() whether it is a
  directory; when the answer is no it returns before it opens anything.  The
  path that matters is the one gnfile() uses during a transfer, because
  ZX_FILONLY takes it through exactly that test -- so "-s *.TXT" would find
  its file while parsing the command line and then report "?File not found"
  when it went to send it.  (PORTING.md SS16f.)

  Rather than special-case the spellings, normalise: drop trailing
  separators, and answer for "" and "." directly.  The current directory
  always exists and is always a directory, so this is a fact and not a
  guess.  Everything else is handed to the library unchanged, which keeps
  this to the gap and no wider -- ordinary files and named subdirectories
  still go through libdos-m's own stat().

  This is a definition of stat(), not a wrapper around it: ours is in an
  object file and the library's is in an archive member that nothing else
  pulls in, so ours is the one that links.  (An attempt to interpose on
  malloc() the same way did NOT take -- see SS16f -- so this is checked on
  the target rather than assumed.)
*/
#ifndef __WATCOMC__                     /* Watcom's own stat() answers
                                           "." and "./" -- measured, and
                                           _stat_r is newlib's spelling  */
#ifndef VICTOR_HAVE_STAT
_PROTOTYP( int _stat_r, (struct _reent *, const char *, struct stat *) );

int
#ifdef CK_ANSIC
stat(const char * VICTOR_RESTRICT path, struct stat * VICTOR_RESTRICT buf)
#else
stat(path,buf) const char * path; struct stat * buf;
#endif /* CK_ANSIC */
{
    char fixed[CKMAXPATH];
    int n;

    if (!path || !buf) {
        errno = EFAULT;
        return(-1);
    }
    n = (int)strlen(path);
    if (n > 0 && n < (int)sizeof(fixed)) {
        memcpy(fixed,path,(size_t)n + 1);
        /*
          Strip trailing separators, but never turn "\" or "A:\" -- which
          name the root and are the one place a trailing separator is part
          of the name -- into something else.
        */
        while (n > 1 &&
               (fixed[n-1] == '/' || fixed[n-1] == '\\') &&
               fixed[n-2] != ':') {
            fixed[--n] = '\0';
        }
        path = fixed;
    }

    if (!*path || (path[0] == '.' && path[1] == '\0')) {
        memset((char *)buf,0,sizeof(struct stat));
        buf->st_mode = (mode_t)(S_IFDIR | 0755);
        buf->st_nlink = 1;
        return(0);
    }
    return(_stat_r(_REENT,path,buf));
}
#endif /* VICTOR_HAVE_STAT */
#endif /* __WATCOMC__ */

/*
  creat() is open() with the classic three flags.  The library has open()
  but not this spelling of it.
*/
#ifndef VICTOR_HAVE_CREAT
int
#ifdef CK_ANSIC
creat(const char * path, mode_t mode)
#else
creat(path,mode) const char * path; mode_t mode;
#endif /* CK_ANSIC */
{
    return(open(path,O_WRONLY|O_CREAT|O_TRUNC,mode));
}
#endif /* VICTOR_HAVE_CREAT */

/*
  utime() -- set a file's modification time, INT 21h AH=57h AL=01h with the
  handle in BX and the packed DOS date/time in DX:CX.  C-Kermit calls this
  when SET FILE INCOMPLETE / date preservation is in play.

  The file has to be open to have a handle, so this opens it read-write,
  stamps it and closes it.  Passing a null "times" argument means "now",
  which DOS gives us for free: we simply do not write a new stamp, and
  closing the file leaves DOS's own update in place.
*/
#ifndef VICTOR_HAVE_UTIME
int
#ifdef CK_ANSIC
utime(const char * path, const struct utimbuf * times)
#else
utime(path,times) const char * path; const struct utimbuf * times;
#endif /* CK_ANSIC */
{
    int fd;
    unsigned int dosdate, dostime;
    struct tm * t;
    time_t when;

    if ((fd = open(path,O_RDWR)) < 0)
      return(-1);

    if (!times) {                       /* "Now": let DOS do it on close */
        close(fd);
        return(0);
    }
    when = times->modtime;
    if (!(t = localtime(&when))) { close(fd); errno = EINVAL; return(-1); }

    /* DOS packs the date as yyyyyyym mmmddddd, year relative to 1980. */
    dosdate = (unsigned int)(((t->tm_year - 80) & 0x7f) << 9)
            | (unsigned int)(((t->tm_mon + 1) & 0x0f) << 5)
            | (unsigned int)(t->tm_mday & 0x1f);
    /* and the time as hhhhhmmm mmmsssss, seconds in two-second units. */
    dostime = (unsigned int)((t->tm_hour & 0x1f) << 11)
            | (unsigned int)((t->tm_min & 0x3f) << 5)
            | (unsigned int)((t->tm_sec / 2) & 0x1f);

    __asm__ __volatile__ ("int $0x21"
                          :
                          : "a" ((unsigned int)0x5701),
                            "b" ((unsigned int)fd),
                            "c" (dostime),
                            "d" (dosdate)
                          : "cc");
    close(fd);
    return(0);
}
#endif /* VICTOR_HAVE_UTIME */

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
  II, Appendix A.  The nine CR bytes are the uPD7201's write registers; on
  channel A, CR2A is its WR2 and CR2B is channel B's.

  The four 16-bit fields come first and the nine bytes after, so the
  struct has no interior padding under either toolchain; the trailing pad
  to an even size is why the length below is a literal 17 rather than
  sizeof.
*/

#define V9K_IOCTL_RDCTL 0x4402          /* Receive control data         */
#define V9K_IOCTL_WRCTL 0x4403          /* Send control data            */
#define V9K_PVAL_LEN    17              /* Bytes DOS moves either way   */

struct v9k_portval {
    unsigned short stype;               /* 0011h = port access          */
    unsigned short status;
    unsigned short blocktype;           /* 0000h = serial               */
    unsigned short baudr;               /* 8253 DIVISOR, not a baud rate*/
    unsigned char  cr0;
    unsigned char  cr1;                 /* WR1: interrupt enables       */
    unsigned char  cr2a;                /* WR2: interrupt mode          */
    unsigned char  cr2b;
    unsigned char  cr3;                 /* WR3: Rx width, Rx enable     */
    unsigned char  cr4;                 /* WR4: clock, stop bits, parity*/
    unsigned char  cr5;                 /* WR5: Tx width/enable,DTR,RTS */
    unsigned char  cr6;
    unsigned char  cr7;
};

/*
  Read or write the block.  Returns 0, or -1 with the DOS error left in
  errno if the driver will not answer -- which is not fatal and is handled
  at the one call site.
*/
static int
#ifdef CK_ANSIC
v9k_portval_io(int fd, int wr, struct v9k_portval * p)
#else
v9k_portval_io(fd,wr,p) int fd; int wr; struct v9k_portval * p;
#endif /* CK_ANSIC */
{
#ifdef __WATCOMC__
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
        errno = (int)r.w.ax;
        return(-1);
    }
    return(0);
#else /* __WATCOMC__ */
    unsigned int ax;

    /* Passes DOS a pointer, so DS_CALL and not a bare int $0x21.  See
       the note on DS at the top of section 0. */
    __asm__ __volatile__ (DOS_DS_CALL("jc 1f\n\t"
                                      "xor %%ax,%%ax\n"
                                      "1:")
                          : "=a" (ax)
                          : "0" ((unsigned int)(wr ? V9K_IOCTL_WRCTL
                                                   : V9K_IOCTL_RDCTL)),
                            "b" ((unsigned int)fd),
                            "c" ((unsigned int)V9K_PVAL_LEN),
                            "d" (p)
                          : "cc", "memory");
    if (ax) {
        errno = (int)ax;
        return(-1);
    }
    return(0);
#endif /* __WATCOMC__ */
}

/*
  B* code -> 8253 divisor.  Indexed by the ordinals in sys/termios.h, so
  the order of the two lists has to stay in step.

  These are msxv90.asm's "bddat" values, which vickermit.c reproduces
  byte for byte; the rule behind them is 78125/baud, and B200 is the one
  entry neither of those two tables has.  See sys/termios.h for why the
  numerator is 78125 and not the 76800 an earlier revision assumed.

  B0 is not a speed -- POSIX gives it the meaning "hang up" -- so its
  entry is never used; tcsetattr drops DTR and RTS and leaves the divisor
  alone, which is how msxv90.asm's SERHNG implements HANGUP.
*/
static unsigned int v9k_divisor[] = {
       0,                               /* B0     hang up               */
    1562, 1041,  710,  580,  520,       /* B50   B75   B110  B134  B150 */
     391,  260,  130,   65,   43,       /* B200  B300  B600  B1200 B1800*/
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
      Read-modify-write, so that whatever the driver has in the fields we
      do not understand survives.

      Zero it first so that nothing uninitialised can ever be written back,
      then stamp the two header words BEFORE the read.  They are not output
      fields: they are how the request identifies itself, and msxv90.asm's
      "pval" carries stype = 0011h as a structure default on the block it
      hands to the read as well as the write.  Zeroing them and expecting
      the driver to fill them in returns a block of nothing -- measured,
      PORTING.md SS11a.

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
  it interrupted, and neither toolchain will give us one (PORTING.md SS11b);
  a dedicated stack would have to come out of the same 64K DGROUP that is
  already this port's binding constraint.  3.13's SERINT does not switch
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
  Reaching a fixed physical address needs a far pointer in both models --
  the gcc build's data is near and the Watcom build's is far, but neither
  can name segment E004h without one.  Watcom has MK_FP; ia16-elf-gcc has
  __far and builds the same thing out of an integer, segment in the high
  half.  Both fold to a constant when the offset is one.
*/
#ifdef __WATCOMC__
#define V9K_FARB(seg,off) (*(volatile unsigned char __far *)MK_FP((seg),(off)))
#else
#define V9K_FARB(seg,off)                                               \
    (*(volatile unsigned char __far *)                                  \
       (((unsigned long)(seg) << 16) | (unsigned long)(unsigned int)(off)))
#endif /* __WATCOMC__ */

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
#ifdef __WATCOMC__
#define V9K_CLI() _disable()
#define V9K_STI() _enable()
#else
#define V9K_CLI() __asm__ __volatile__ ("cli" : : : "cc")
#define V9K_STI() __asm__ __volatile__ ("sti" : : : "cc")
#endif /* __WATCOMC__ */

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
  Two counters, for the debug log only.  They are the difference between
  "the transfer was slow" and "the ring is too small", and neither is
  guessable from the outside.
*/
static volatile unsigned int  v9k_rxlost = 0;   /* Chip overran us      */
static volatile unsigned int  v9k_rxfull = 0;   /* Ring overran Kermit  */

static int v9k_ser_on   = 0;            /* Have we taken the chip?      */
static int v9k_ser_atx  = 0;            /* atexit() registered yet?     */
static unsigned int  v9k_oldvec_seg = 0;
static unsigned int  v9k_oldvec_off = 0;
static unsigned char v9k_oldimr = 0;    /* 8259 mask as we found it     */

/*
  Interrupt vectors, through INT 21h AH=35h and AH=25h -- which is the
  whole reason hooking one does not break hard rule 6.  Both toolchains get
  the same pair, taking and returning a segment and an offset rather than a
  function pointer, so that the install and release paths below have no
  #ifdef in them.

  Watcom has _dos_getvect/_dos_setvect, which are those two calls.  The gcc
  build has to issue them itself, and AH=25h is one of the calls that takes
  its argument in DS:DX, so DS has to be loaded with the HANDLER's segment
  rather than with DGROUP -- which is why this one does not use
  DOS_DS_CALL.

  BX carries the segment rather than a "r"-class operand on purpose: on
  ia16 the general register class includes the segment registers, and
  letting the compiler choose is how the first version of _write_r came to
  load DS with a spilled constant (see the note at the top of section 0).
*/
#ifdef __WATCOMC__
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
#else /* __WATCOMC__ */
static VOID
#ifdef CK_ANSIC
v9k_getvect(int vec, unsigned int * seg, unsigned int * off)
#else
v9k_getvect(vec,seg,off) int vec; unsigned int * seg; unsigned int * off;
#endif /* CK_ANSIC */
{
    unsigned int s, o;

    __asm__ __volatile__ ("push %%es\n\t"
                          "int $0x21\n\t"
                          "movw %%es,%%ax\n\t"
                          "pop %%es"
                          : "=a" (s), "=b" (o)
                          : "0" ((unsigned int)(0x3500 | (vec & 0xff)))
                          : "cc");
    *seg = s;
    *off = o;
}

static VOID
#ifdef CK_ANSIC
v9k_setvect(int vec, unsigned int seg, unsigned int off)
#else
v9k_setvect(vec,seg,off) int vec; unsigned int seg; unsigned int off;
#endif /* CK_ANSIC */
{
    __asm__ __volatile__ ("push %%ds\n\t"
                          "movw %%bx,%%ds\n\t"
                          "int $0x21\n\t"
                          "pop %%ds"
                          :
                          : "a" ((unsigned int)(0x2500 | (vec & 0xff))),
                            "b" (seg),
                            "d" (off)
                          : "cc", "memory");
}
#endif /* __WATCOMC__ */

/*
  The handler.  Written ANSI-only for the same reason ioctl() above is: the
  attribute that makes it an interrupt routine is part of its type in both
  toolchains, and there is no K&R spelling of it.

  ia16-elf-gcc's __attribute__((interrupt)) pushes the scratch registers it
  actually uses plus DS, loads DGROUP from a relocation rather than trusting
  the interrupted DS, and ends in iret.  Watcom's __interrupt __far does the
  same with a fixed register set.  Neither emits a stack probe here.

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
#ifdef __WATCOMC__
static void __interrupt __far
v9k_ser_isr(void)
#else
static void __attribute__((interrupt))
v9k_ser_isr(void)
#endif /* __WATCOMC__ */
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
        nh = (v9k_rxhead + 1) & V9K_RXMASK;
        if (nh != v9k_rxtail) {         /* Mark the gap, as 3.13 does   */
            v9k_rxbuf[v9k_rxhead] = (unsigned char)'\007';
            v9k_rxhead = nh;
        }
    }

    c  = V9K_DAT;
    nh = (v9k_rxhead + 1) & V9K_RXMASK;
    if (nh != v9k_rxtail) {
        v9k_rxbuf[v9k_rxhead] = c;
        v9k_rxhead = nh;
    } else
      v9k_rxfull++;                     /* Ring full: this byte is gone */
}

/*
  Its address, as a segment and an offset, for v9k_setvect() above.  Both
  toolchains put the handler in far code, so this is a plain far pointer
  taken apart -- Watcom has the macros for it and ia16-elf-gcc represents a
  far pointer as a 32-bit value with the segment in the high half.
*/
#ifdef __WATCOMC__
#define V9K_ISR_SEG FP_SEG((void __far *)v9k_ser_isr)
#define V9K_ISR_OFF FP_OFF((void __far *)v9k_ser_isr)
#else
#define V9K_ISR_SEG \
    ((unsigned int)(((unsigned long)(void __far *)&v9k_ser_isr) >> 16))
#define V9K_ISR_OFF \
    ((unsigned int)((unsigned long)(void __far *)&v9k_ser_isr))
#endif /* __WATCOMC__ */

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
    }
    v9k_rxtail = t;                     /* One store, ours alone        */
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

#ifndef __WATCOMC__
/* ------------------------------------------------------------------ */
/* 1c. newlib reentrant syscalls with no MS-DOS equivalent              */
/* ------------------------------------------------------------------ */

/*
  newlib's libc.a defines link() and kill() as thin wrappers over _link_r
  and _kill_r, and ships neither.  They are pulled into the link by
  signal.c (raise() calls _kill_r), not by anything C-Kermit asks for.

  FAT has no hard links, and MS-DOS has no other process to signal.
*/

int
#ifdef CK_ANSIC
_link_r(struct _reent * r, const char * old, const char * new)
#else
_link_r(r,old,new) struct _reent * r; const char * old; const char * new;
#endif /* CK_ANSIC */
{
    if (r) r->_errno = EMLINK;
    return(-1);
}

int
#ifdef CK_ANSIC
_kill_r(struct _reent * r, int pid, int sig)
#else
_kill_r(r,pid,sig) struct _reent * r; int pid; int sig;
#endif /* CK_ANSIC */
{
    if (r) r->_errno = ESRCH;
    return(-1);
}
#endif /* __WATCOMC__ */

#ifdef __WATCOMC__
/* ------------------------------------------------------------------ */
/* 1d. Gaps in the Open Watcom DOS runtime                              */
/* ------------------------------------------------------------------ */

/*
  These are the mirror image of section 1c: things newlib declares and
  Watcom does not have at all.  getpwent()/setpwent()/endpwent() complete
  the passwd stubs in section 1 -- see victorow/pwd.h for why NULL is the
  right answer rather than a placeholder.

  link() and kill() are the same two calls section 1c stubs for newlib,
  minus the reentrancy wrapper: FAT has no hard links and MS-DOS has no
  other process to signal.  ckufio.c calls both (zrename's fallback, and
  zkill), so these must exist even though nothing can succeed.
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
    ckstrncpy(n->sysname, "MS-DOS",  _UTSNAME_LENGTH);
    ckstrncpy(n->nodename,"victor",  _UTSNAME_LENGTH);
    ckstrncpy(n->release, "",        _UTSNAME_LENGTH);
    ckstrncpy(n->version, "",        _UTSNAME_LENGTH);
    ckstrncpy(n->machine, "Victor",  _UTSNAME_LENGTH);
    return(0);
}
#endif /* __WATCOMC__ */

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

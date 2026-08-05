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
  renames read() to v9k_read() for the whole build.  This file is where
  v9k_read() lives and is the one place that still has to reach the real
  one, so the rename is undone here -- before any header is pulled in, so
  that <unistd.h> / <io.h> declare read() rather than redeclaring ours.
  See ckvictor.h and section 0d.
*/
#undef read

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
};

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
    dos_set_dta(&d->d_ent);
    rc = dos_find_first(pattern,DOS_FIND_ATTRS);

    d->d_pending = (rc == 0);
    d->d_done    = (rc != 0);

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
        return(&d->d_ent);
    }
    if (d->d_done)
      return((struct dirent *)0);

    dos_set_dta(&d->d_ent);             /* See note above -- every time */
    if (dos_find_next() != 0) {
        d->d_done = 1;
        return((struct dirent *)0);     /* No more; errno unchanged     */
    }
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
/* 0b. Device input status, and ioctl -- FIONREAD only                  */
/* ------------------------------------------------------------------ */

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

  Both answer "whether", not "how many", so FIONREAD reports at most 1.
  That is what a poll of either device can honestly say, and it is enough
  for conchk(), whose callers test it against zero.  It is NOT enough for
  ttchk()'s other caller: sdata() in ckcfns.c only slides its window when
  ttchk() exceeds 4+bctu, so a 0/1 answer means this port fills a window
  before reading ACKs.  Upstream has been through this before -- see the
  GEMDOS arm of that same test, and ckcfn2.c's note that the count is only
  a hint -- so it costs throughput and nothing else.  The real count needs
  the uPD7201 driver's RX ring (PORTING.md SS11).

  There is a second reason ttchk() still answers 0 on the communications
  device today, upstream of anything here: in_chk() asks ttgmdm() for
  carrier first, and with CARRIER-WATCH left at its default of AUTO and no
  TIOCMGET on this platform, ttgmdm() returns -3 and in_chk() returns 0
  without ever reaching FIONREAD.  So the code below is correct and
  currently unreachable for fd == ttyfd.  Both halves belong to SS11.
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

    if (request != FIONREAD) {
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

    if (fd == 0)                        /* Console: AH=0Bh              */
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

extern int ttyfd;                       /* ckutio.c's serial descriptor */

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
  The wait itself.  Poll for input status, and read only once DOS says
  there is something to read -- a read issued blind is what returns 0 and
  starts the whole failure off.

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
        if (dos_dev_input_ready(fd)) {
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
    /*
      fd > 2 as well as fd == ttyfd because ttopen() sets ttyfd to 0 in
      remote mode, where the "line" is the console and section 0c owns it.
    */
    if (fd > 2 && fd == ttyfd)
      return((V9K_RTYPE)v9k_comm_read(fd,buf,(unsigned int)n));
    return(read(fd,buf,n));
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
  See victor/sys/termios.h for the design.  What is here is the SOFTWARE
  half only: the cached struct termios, the B* speed codes, and the
  bookkeeping ckutio.c drives.  Every one of these is a place where the
  uPD7201 and 8253 will be programmed (PORTING.md SS11), and each is marked
  with the register it will eventually touch.

  This half is worth having on its own: it is what lets the program link
  and lets SET SPEED / SHOW COMMUNICATIONS be exercised before any
  hardware exists.  It is NOT a serial port.  Nothing below moves a byte.

  ckutio.c keeps several struct termios of its own (ttold, ttraw, ttcur,
  ...) and treats tcgetattr as "read back what I set".  Caching one
  current setting here matches that and costs 32 bytes.
*/

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
    if (!t) { errno = EFAULT; return(-1); }
    victor_ttcur = *t;
    /*
      TODO(driver): uPD7201 WR4 (clock/stop bits/parity), WR3 (RX width,
      RX enable), WR5 (TX width, TX enable, RTS/DTR), and the 8253 divisor
      for c_ospeed.  Until then this records intent and nothing more.
    */
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
    /* TODO(driver): reset the RX and/or TX ring head/tail pointers. */
    return(0);
}

int
#ifdef CK_ANSIC
tcdrain(int fd)
#else
tcdrain(fd) int fd;
#endif /* CK_ANSIC */
{
    /* TODO(driver): spin until the TX ring empties and WR0 TX-empty set. */
    return(0);
}

int
#ifdef CK_ANSIC
tcflow(int fd, int action)
#else
tcflow(fd,action) int fd; int action;
#endif /* CK_ANSIC */
{
    /* TODO(driver): assert/release RTS, or send XON/XOFF. */
    return(0);
}

int
#ifdef CK_ANSIC
tcsendbreak(int fd, int duration)
#else
tcsendbreak(fd,duration) int fd; int duration;
#endif /* CK_ANSIC */
{
    /* TODO(driver): uPD7201 WR5 send-break bit, held for `duration'. */
    return(0);
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

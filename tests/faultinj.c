/*
  faultinj.c: LD_PRELOAD fault injection for the C-Kermit test suite.

  The tests build this file into a shared object and preload it into
  wermit.  It makes the Nth call of one library function fail.

  Environment:
    FAULT_FUNC    malloc, read, readeof, write, open, openpty or fork.
    FAULT_N       1-based number of the call to fail.  0 fails nothing.
    FAULT_COUNT   Number of consecutive calls to fail, from FAULT_N.
                  Default 1.
    FAULT_REPORT  If set, the path of a file that receives the number of
                  calls of FAULT_FUNC when the process exits.
    FAULT_BT      If set, SIGSEGV, SIGBUS and SIGABRT print a backtrace on
                  stderr before the process dies.
    FAULT_SYSLOG  If set, the path of a file that receives each syslog()
                  message, one per line, in place of the system log.

  malloc covers malloc(), calloc() and realloc().  read covers read() and
  recv() and returns -1 with EIO.  It also covers __read_chk() and
  __recv_chk().  _FORTIFY_SOURCE turns some read() and recv() calls into
  these.  readeof makes them return 0.  write
  covers write() and send() and returns -1 with EIO.  open covers open(),
  open64(), fopen() and fopen64().  They fail with EACCES.  openpty
  fails with ENOENT, and fork with EAGAIN.

  read, readeof and write count only calls on descriptors above 2, so
  stdin, stdout and stderr are not affected.  The library removes
  LD_PRELOAD from the environment, so child processes run unchanged.

  This file is for glibc on Linux.  The malloc wrappers call
  __libc_malloc() and friends.  read(), write() and open() go to
  syscall().  fopen(), openpty() and fork() use dlsym().
*/
#define _GNU_SOURCE
#include <dlfcn.h>
#include <execinfo.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>

extern void *__libc_malloc(size_t);
extern void *__libc_calloc(size_t, size_t);
extern void *__libc_realloc(void *, size_t);

#define F_NONE 0
#define F_MALLOC 1
#define F_READ 2
#define F_READEOF 3
#define F_WRITE 4
#define F_OPEN 5
#define F_OPENPTY 6
#define F_FORK 7

static int func = F_NONE;               /* Function class to fail */
static long target = 0;                 /* FAULT_N */
static long span = 1;                   /* FAULT_COUNT */
static long calls = 0;                  /* Calls of func so far */
static const char *report = NULL;       /* FAULT_REPORT */
static const char *syslogfile = NULL;   /* FAULT_SYSLOG */

/* Count a call of class f.  Return 1 if this call must fail. */
static int
hit(int f)
{
    if (f != func)
        return 0;
    calls++;
    return target > 0 && calls >= target && calls < target + span;
}

static void
write_report(void)
{
    char buf[32];
    long fd;
    int n;

    if (!report)
        return;
    fd = syscall(SYS_openat, AT_FDCWD, report,
                 O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0)
        return;
    n = snprintf(buf, sizeof(buf), "%ld\n", calls);
    if (n > 0 && (size_t)n < sizeof(buf))
        (void)syscall(SYS_write, (int)fd, buf, (size_t)n);
    (void)syscall(SYS_close, (int)fd);
}

/* Print a backtrace for a fatal signal, then die from it. */
static void
crash_bt(int sig)
{
    void *frames[64];
    int n;

    n = backtrace(frames, 64);
    backtrace_symbols_fd(frames, n, 2);
    signal(sig, SIG_DFL);
    raise(sig);
}

__attribute__((constructor))
static void
faultinj_init(void)
{
    const char *s;

    s = getenv("FAULT_FUNC");
    if (s) {
        if (!strcmp(s, "malloc"))
            func = F_MALLOC;
        else if (!strcmp(s, "read"))
            func = F_READ;
        else if (!strcmp(s, "readeof"))
            func = F_READEOF;
        else if (!strcmp(s, "write"))
            func = F_WRITE;
        else if (!strcmp(s, "open"))
            func = F_OPEN;
        else if (!strcmp(s, "openpty"))
            func = F_OPENPTY;
        else if (!strcmp(s, "fork"))
            func = F_FORK;
    }
    if ((s = getenv("FAULT_N")))
        target = strtol(s, NULL, 10);
    if ((s = getenv("FAULT_COUNT")))
        span = strtol(s, NULL, 10);
    if (span < 1)
        span = 1;
    report = getenv("FAULT_REPORT");
    syslogfile = getenv("FAULT_SYSLOG");
    if (report)
        atexit(write_report);
    if (getenv("FAULT_BT")) {
        signal(SIGSEGV, crash_bt);
        signal(SIGBUS, crash_bt);
        signal(SIGABRT, crash_bt);
    }
    unsetenv("LD_PRELOAD");             /* Child processes run unchanged */
}

void *
malloc(size_t n)
{
    if (hit(F_MALLOC)) {
        errno = ENOMEM;
        return NULL;
    }
    return __libc_malloc(n);
}

void *
calloc(size_t n, size_t m)
{
    if (hit(F_MALLOC)) {
        errno = ENOMEM;
        return NULL;
    }
    return __libc_calloc(n, m);
}

void *
realloc(void *p, size_t n)
{
    if (hit(F_MALLOC)) {
        errno = ENOMEM;
        return NULL;
    }
    return __libc_realloc(p, n);
}

ssize_t
read(int fd, void *buf, size_t n)
{
    if (fd > 2) {
        if (hit(F_READ)) {
            errno = EIO;
            return -1;
        }
        if (hit(F_READEOF))
            return 0;
    }
    return (ssize_t)syscall(SYS_read, fd, buf, n);
}

ssize_t
write(int fd, const void *buf, size_t n)
{
    if (fd > 2 && hit(F_WRITE)) {
        errno = EIO;
        return -1;
    }
    return (ssize_t)syscall(SYS_write, fd, buf, n);
}

ssize_t
recv(int fd, void *buf, size_t n, int flags)
{
    if (fd > 2) {
        if (hit(F_READ)) {
            errno = EIO;
            return -1;
        }
        if (hit(F_READEOF))
            return 0;
    }
    return (ssize_t)syscall(SYS_recvfrom, fd, buf, n, flags, NULL, NULL);
}

ssize_t
__read_chk(int fd, void *buf, size_t n, size_t buflen)
{
    if (n > buflen)
        abort();
    return read(fd, buf, n);
}

ssize_t
__recv_chk(int fd, void *buf, size_t n, size_t buflen, int flags)
{
    if (n > buflen)
        abort();
    return recv(fd, buf, n, flags);
}

ssize_t
send(int fd, const void *buf, size_t n, int flags)
{
    if (fd > 2 && hit(F_WRITE)) {
        errno = EIO;
        return -1;
    }
    return (ssize_t)syscall(SYS_sendto, fd, buf, n, flags, NULL, 0);
}

/* Return the mode argument of open() when flags need one. */
static mode_t
open_mode(int flags, va_list ap)
{
    if ((flags & O_CREAT) || (flags & O_TMPFILE) == O_TMPFILE)
        return (mode_t)va_arg(ap, int);
    return 0;
}

int
open(const char *path, int flags, ...)
{
    va_list ap;
    mode_t mode;

    va_start(ap, flags);
    mode = open_mode(flags, ap);
    va_end(ap);
    if (hit(F_OPEN)) {
        errno = EACCES;
        return -1;
    }
    return (int)syscall(SYS_openat, AT_FDCWD, path, flags, mode);
}

int
open64(const char *path, int flags, ...)
{
    va_list ap;
    mode_t mode;

    va_start(ap, flags);
    mode = open_mode(flags, ap);
    va_end(ap);
    if (hit(F_OPEN)) {
        errno = EACCES;
        return -1;
    }
    return (int)syscall(SYS_openat, AT_FDCWD, path, flags, mode);
}

FILE *
fopen(const char *path, const char *how)
{
    static FILE *(*real)(const char *, const char *) = NULL;

    if (hit(F_OPEN)) {
        errno = EACCES;
        return NULL;
    }
    if (!real)
        real = (FILE *(*)(const char *, const char *))
            dlsym(RTLD_NEXT, "fopen");
    return real ? real(path, how) : NULL;
}

FILE *
fopen64(const char *path, const char *how)
{
    static FILE *(*real)(const char *, const char *) = NULL;

    if (hit(F_OPEN)) {
        errno = EACCES;
        return NULL;
    }
    if (!real)
        real = (FILE *(*)(const char *, const char *))
            dlsym(RTLD_NEXT, "fopen64");
    return real ? real(path, how) : NULL;
}

struct termios;
struct winsize;

int
openpty(int *amaster, int *aslave, char *name,
        const struct termios *termp, const struct winsize *winp)
{
    static int (*real)(int *, int *, char *, const struct termios *,
                       const struct winsize *) = NULL;

    if (hit(F_OPENPTY)) {
        errno = ENOENT;
        return -1;
    }
    if (!real)
        real = (int (*)(int *, int *, char *, const struct termios *,
                        const struct winsize *))dlsym(RTLD_NEXT, "openpty");
    if (!real) {
        errno = ENOSYS;
        return -1;
    }
    return real(amaster, aslave, name, termp, winp);
}

pid_t
fork(void)
{
    static pid_t (*real)(void) = NULL;

    if (hit(F_FORK)) {
        errno = EAGAIN;
        return -1;
    }
    if (!real)
        real = (pid_t (*)(void))dlsym(RTLD_NEXT, "fork");
    if (!real) {
        errno = ENOSYS;
        return -1;
    }
    return real();
}

/* Append one message to FAULT_SYSLOG, or send it to the system log. */
static void
log_message(int pri, const char *fmt, va_list ap)
{
    static void (*real)(int, const char *, va_list) = NULL;
    char buf[1024];
    long fd;
    int n;

    if (!syslogfile) {
        if (!real)
            real = (void (*)(int, const char *, va_list))
                dlsym(RTLD_NEXT, "vsyslog");
        if (real)
            real(pri, fmt, ap);
        return;
    }
    n = vsnprintf(buf, sizeof(buf) - 1, fmt, ap);
    if (n < 0)
        return;
    if ((size_t)n > sizeof(buf) - 2)
        n = (int)sizeof(buf) - 2;
    buf[n++] = '\n';
    fd = syscall(SYS_openat, AT_FDCWD, syslogfile,
                 O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0)
        return;
    (void)syscall(SYS_write, (int)fd, buf, (size_t)n);
    (void)syscall(SYS_close, (int)fd);
}

void
syslog(int pri, const char *fmt, ...)
{
    va_list ap;

    va_start(ap, fmt);
    log_message(pri, fmt, ap);
    va_end(ap);
}

void
vsyslog(int pri, const char *fmt, va_list ap)
{
    log_message(pri, fmt, ap);
}

void
__syslog_chk(int pri, int flag, const char *fmt, ...)
{
    va_list ap;

    (void)flag;
    va_start(ap, fmt);
    log_message(pri, fmt, ap);
    va_end(ap);
}

void
__vsyslog_chk(int pri, int flag, const char *fmt, va_list ap)
{
    (void)flag;
    log_message(pri, fmt, ap);
}

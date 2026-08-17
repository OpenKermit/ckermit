/*  C K O W S Y S . H  --  Unix system calls Open Watcom does not declare  */

/*
  The Victor has no Unix process model, so ckvictor.c stubs one: fork()
  fails, everyone is uid 0, there is one terminal and it is called CON:.
  That much is toolchain-independent.  What is NOT toolchain-independent
  is who DECLARES those calls.

  newlib declares every one of them in <unistd.h> and friends -- it simply
  defines none of them, which is the gap ckvictor.c fills.  Open Watcom's
  DOS runtime does not declare them at all, because MS-DOS genuinely has
  none of them.  Without declarations, ckutio.c and ckufio.c call them as
  implicit-int functions, and on a 16-bit target that is not cosmetic:

      char * n = ttyname(0);         -- ttyname returns a FAR pointer

  compiles as "int ttyname()" and truncates the pointer to its offset.
  Watcom says so (W131 "no prototype found", W102 "type mismatch"), and
  those warnings are the reason this header exists rather than a -w option
  turning them off.

  It is included from the __WATCOMC__ section of ckvictor.h, which is
  force-included ahead of every module -- including ckvictor.c itself, so
  the definitions there are checked against these declarations.

  Reached via -i=victorow.  See PORTING.md.
*/

#ifndef _CKOWSYS_H
#define _CKOWSYS_H

#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Process model -- section 1 of ckvictor.c */
pid_t   fork(void);
int     kill(pid_t __pid, int __sig);
pid_t   wait(int * __statusp);
pid_t   getppid(void);
pid_t   getpgrp(void);
pid_t   tcgetpgrp(int __fd);

/* Identity: single-user machine, everyone is uid 0 */
uid_t   getuid(void);
uid_t   geteuid(void);
gid_t   getgid(void);
gid_t   getegid(void);
int     setuid(uid_t __uid);
int     setgid(gid_t __gid);
char *  getlogin(void);

/* The one console */
char *  ttyname(int __fd);
char *  ctermid(char * __s);

/* No interval timers, no runtime configuration query */
unsigned alarm(unsigned __secs);
long    sysconf(int __name);

/* FAT has neither symbolic nor hard links */
ssize_t readlink(const char * __path, char * __buf, size_t __n);
int     link(const char * __old, const char * __new);
mode_t  umask(mode_t __mask);

#ifdef __cplusplus
}
#endif

#endif /* _CKOWSYS_H */

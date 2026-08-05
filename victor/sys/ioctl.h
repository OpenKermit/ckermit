/*  S Y S / I O C T L . H  --  FIONREAD for the Victor 9000  */

/*
  This header exists for exactly one macro: FIONREAD.

  ckutio.c wants it badly, and says so itself (ckutio.c ~line 800):

      We really, really, REALLY want FIONREAD, because it is the only way
      to find out not just *if* stuff is waiting to be read, but how much,
      which is critical to our sliding-window and streaming procedures,
      not to mention efficiency of CONNECT, etc.

  Without it, in_chk() -- which is what conchk() and ttchk() are -- falls
  all the way through its cascade of FIONREAD / rdchk() / select() / poll()
  and lands on the branch its own comment calls "the hideous hack used in
  System V and POSIX systems", where the console's character-ready test is
  inferred from a SIGQUIT handler.  MS-DOS has no SIGQUIT, so on this
  platform both arms of in_chk() return a hard-coded 0 forever:

      conchk()  ->  in_chk(0, 0)      ->  always 0
      ttchk()   ->  in_chk(1, ttyfd)  ->  always 0

  A ttchk() that always answers "nothing waiting" is not a cosmetic
  problem.  It is the input to the sliding-window and streaming logic.

  ckutio.c does not include this file on its own: under -DPOSIX it defines
  NOSYSIOCTLH ("No ioctl's allowed") and skips the include.  So ckvictor.h,
  which is force-included ahead of every module, pulls it in instead.  That
  is why only the macro and the prototype live here -- by the time ckutio.c
  is parsed, FIONREAD is simply already defined, and its first and best
  branch is the one that compiles.

  Defining FIONREAD switches on exactly one reachable call site,
  in_chk()'s ioctl(fd, FIONREAD, &n).  It switches OFF two SIGQUIT-based
  workarounds (esctrp() and the console hack above) that could never have
  worked here.  Every other ioctl() call in ckutio.c is guarded by a TIOCxxx
  or TCxxx macro that this port does not define -- those paths belong to the
  pre-POSIX sgtty interface, and we use termios.

  The implementation is in ckvictor.c.  No library in the toolchain
  defines ioctl(), so there is nothing to collide with -- the same
  situation as <sys/termios.h>.

  Reached via -Ivictor.  See PORTING.md SS12.
*/

#ifndef _SYS_IOCTL_H
#define _SYS_IOCTL_H

#ifdef __cplusplus
extern "C" {
#endif

/*
  The value is ours to choose; nothing on this platform interprets it but
  our own ioctl().  It is kept small and positive deliberately: the request
  argument is an int on a 16-bit target, and the traditional BSD encoding
  (_IOR('f',127,int) == 0x4004667f) does not fit in one.
*/
#define FIONREAD 1

/*
  ckutio.c calls this as ioctl(fd, FIONREAD, &n) where n is a plain int,
  so the third argument is an "int *".  Declared variadic to match the
  shape every caller expects.
*/
extern int ioctl(int fd, int request, ...);

#ifdef __cplusplus
}
#endif

#endif /* _SYS_IOCTL_H */

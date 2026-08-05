/*  S Y S / I O C T L . H  --  FIONREAD and TIOCMGET for the Victor 9000  */

/*
  This header exists for two macros, FIONREAD and TIOCMGET.  They are the
  two questions ckutio.c asks about a serial line that MS-DOS has no answer
  for, and in_chk() asks them in that order but needs the second one first.
  FIONREAD came with SS0b; TIOCMGET arrived with the driver in SS11b, and
  the note on it below explains why one without the other was no use.

  FIONREAD first.

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
  And the modem signals, for the same reason and by the same route.

  ttgmdm() in ckutio.c is a long cascade of platform arms, and the only one
  this port can reach is the generic "Sys V R3 / 4.3 BSD style" arm --
  ioctl(fd, TIOCMGET, &bits).  ckutio.c selects it by testing whether
  TIOCMGET is defined:

      #ifdef TIOCMGET
      #define K_MDMCTL
      #endif

  so defining it here is the whole of the switch.  Without it ttgmdm()
  falls all the way through to "Sorry, I don't know how" and returns -3,
  and that is not a cosmetic loss: in_chk() -- which IS ttchk() -- asks for
  carrier BEFORE it asks how many bytes are waiting, and a -3 makes it
  return 0 without ever reaching FIONREAD above.  Measured in the debug log
  as "in_chk ttgmdm I/O error=0" (PORTING.md SS11a).  So FIONREAD was
  correct and unreachable on the communications device until this existed.

  The values are ours to choose, like FIONREAD's, with two constraints.
  TIOCMGET must not collide with FIONREAD, and the TIOCM_* bits are the
  ones ckutio.c ORs into its own BM_* result -- it names each of them in an
  #ifdef, so any bit assignment works as long as they are distinct.  These
  are the traditional BSD values, which is what ckutio.c's own NEEDMDMDEFS
  block (~line 1024, unreachable here) would have supplied.

  Only the GET direction exists.  TIOCMBIS and TIOCMBIC are deliberately
  left undefined: tthang() prefers them when they are there, and this port
  hangs up the way MS-DOS Kermit 3.13 does, by setting B0 through
  tcsetattr() and letting that drop DTR and RTS in the uPD7201's WR5
  (PORTING.md SS11a).  Defining the bit-set pair would silently move
  tthang() onto a second, redundant path.

  The implementation is in ckvictor.c SS1e, which reads DCD and CTS out of
  the uPD7201's RR0 and DSR out of the 6522 that also runs the keyboard --
  the Victor has no DSR pin on the 7201 at all.  See PORTING.md SS11b.
*/
#define TIOCMGET 2

#define TIOCM_DTR 0x0002                /* Data Terminal Ready          */
#define TIOCM_RTS 0x0004                /* Request To Send              */
#define TIOCM_CTS 0x0020                /* Clear To Send                */
#define TIOCM_CAR 0x0040                /* Carrier Detect               */
#define TIOCM_RNG 0x0080                /* Ring Indicator               */
#define TIOCM_DSR 0x0100                /* Data Set Ready               */

/*
  ckutio.c calls this as ioctl(fd, FIONREAD, &n) where n is a plain int,
  so the third argument is an "int *".  Declared variadic to match the
  shape every caller expects.  TIOCMGET has the same shape.
*/
extern int ioctl(int fd, int request, ...);

#ifdef __cplusplus
}
#endif

#endif /* _SYS_IOCTL_H */

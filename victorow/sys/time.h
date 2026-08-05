/*  S Y S / T I M E . H  --  struct timeval for the Open Watcom build  */

/*
  Open Watcom's DOS runtime has BSD-style time in <sys/timeb.h> (ftime)
  but no <sys/time.h>, no struct timeval and no gettimeofday().  newlib has
  all three, which is why the ia16-elf-gcc build never needed this file.

  ckutio.c's floating-point timers -- rftimer()/gftimer(), compiled because
  ckcdeb.h turns GFTIMER on for every UNIX build -- are the only user:

      static struct timeval tzero;
      gettimeofday(&tzero, (struct timezone *)0);

  and gftimer() then subtracts two of them to get elapsed seconds as a
  CKFLOAT.  That is what drives the transfer-rate display.  The
  implementation is in ckvictor.c, over INT 21h AH=2Ch.

  There is deliberately NO struct timezone here, and the second parameter
  is a void *.  Two reasons, and the second one is the real one:

    - Every caller in C-Kermit passes a null pointer for it anyway, as
      POSIX has recommended since 4.2BSD deprecated the argument.

    - ckvictor.h has to redirect the NAME "timezone" (ckufio.c's "extern
      long timezone" cannot agree with Watcom's __near declaration of it
      in the large model).  A macro cannot tell a variable name from a
      struct tag, so anything spelled "struct timezone" would be renamed
      along with it.  Not having one sidesteps that entirely:
      ckutio.c's "(struct timezone *)0" is then just a null pointer of an
      incomplete type, which converts to void * silently and correctly.

  Reached via -i=victorow.  See PORTING.md.
*/

#ifndef _SYS_TIME_H
#define _SYS_TIME_H

#include <time.h>

#ifdef __cplusplus
extern "C" {
#endif

struct timeval {
    time_t tv_sec;                      /* Seconds                      */
    long   tv_usec;                     /* Microseconds                 */
};

int gettimeofday(struct timeval * __tv, void * __tz);

#ifdef __cplusplus
}
#endif

#endif /* _SYS_TIME_H */

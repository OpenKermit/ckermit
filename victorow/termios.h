/*  T E R M I O S . H  --  <termios.h> for the Open Watcom build  */

/*
  ckutio.c includes <termios.h> under BSD44ORPOSIX (ckutio.c ~line 707).
  Open Watcom has no such header -- MS-DOS has no terminal driver to
  describe -- so this file supplies it.

  The ia16-elf-gcc build does not need this one either, but for the
  opposite reason: newlib DOES ship <termios.h>, as a one-line include of
  <sys/termios.h>, which newlib then fails to ship.  Filling that gap is
  what victor/sys/termios.h is for.  This file is the same one-line
  forwarder newlib has, so that both toolchains end up looking at the same
  declarations -- the uPD7201 driver's control surface, implemented in
  ckvictor.c.

  Reached via -i=victorow; the file it names is reached via -i=victor.
*/

#ifndef _TERMIOS_H
#define _TERMIOS_H

#include <sys/termios.h>

#endif /* _TERMIOS_H */

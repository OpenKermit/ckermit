/*  C U R S E S . H  --  the Victor 9000 console, as much curses as
    C-Kermit's fullscreen file-transfer display actually asks for.

  There is no curses library for DOS here, and this port does not want one.
  What it wants is the fullscreen transfer display -- the one MS-DOS Kermit
  3.13 has on this same machine -- and that display turns out to need a very
  small surface: move(), clear(), clrtoeol(), printw(), and four functions
  that do nothing on a terminal you address directly.  ckuusx.c's screenc()
  uses move 55 times, printw 68, refresh 11 and clrtoeol 11, and that is the
  whole list.

  So this header is the declaration half and ckvictor.c section 1g is the
  implementation half, the same split as victor/sys/termios.h and
  victorow/pwd.h.  It is reached by -i=victorow, and ckuusx.c picks it up at
  its "#include <curses.h>" under CK_CURSES.

  WHY NOT UPSTREAM'S MYCURSES.  ckuusx.c already carries a do-it-yourself
  curses (ckuusx.c:6732) that is nothing but printf of escape sequences, and
  it even has a VT52 arm -- which is what this machine speaks.  Two things
  make it unusable here and both are worth writing down:

    1. ckuusx.c:6237 is "#define isvt52 0" for every non-VMS build, so the
       VT52 arm is unreachable and the ANSI arm is what you get.  The Victor
       does not speak ANSI (see below).

    2. That arm is off by one anyway.  It sends ESC Y (row+037) (col+037)
       -- +31 -- applied to move()'s 0-based coordinates, where the Victor
       wants +32.  vickermit.c:195 gets away with +31 because ITS
       coordinates are 1-based.

  THE MACHINE.  The Victor's OEM console driver is a DEC VT52 emulator with
  Heath/Zenith Z19 extensions.  It does NOT interpret ANSI CSI sequences.
  The Supplementary Technical Reference Manual says so in as many words --
  "the set of escape sequences is designed to be very similar to a DEC VT52
  terminal ... some of the more fancy features are borrowed from a Heath Z19
  terminal" -- and the strongest confirmation is that MS-DOS Kermit's
  msyv90.asm is a VT100 emulator whose entire job is TRANSLATING incoming
  ANSI into these sequences (ESC[r;cH -> ESC Y at msyv90.asm:1322,
  ESC[2J -> ESC E and ESC[0K -> ESC K at :1626-1751).  A console that
  understood ANSI would not need that table.

  HARD RULE 6 IS NOT IN CONFLICT, and that was not obvious in advance.  3.13
  reaches this display with INT 21h and nothing else: msxv90.asm:1100
  (POSCUR) writes ESC Y with AH=09h and then the two coordinate bytes with
  AH=02h; CMBLNK sends ESC E, CLEARL sends ESC K.  Direct writes to the
  F000:0 screen array in msyv90.asm are only for the Tektronix bitmap.  So
  the fullscreen display costs no BIOS call, no screen memory and no INT 10h,
  and one binary still runs on both DOSes as far as this rule is concerned.

  WHAT IT DOES COST is a difference BETWEEN the two DOSes, which is a
  separate question and is not settled here: FreeDOS-for-Victor's
  kernel/victor_ansi.asm parses only ESC [ and passes anything else through,
  so these sequences will render as noise there.  The fallback is automatic
  -- fxdinit() drops fdispla to XYFD_S, the CRT display, whenever the
  fullscreen one is not available -- but nothing yet DETECTS the case.  See
  PORTING.md and NEXT_SESSION.md item 14.
*/

#ifndef CKV_CURSES_H
#define CKV_CURSES_H

/*
  Screen geometry.  Upstream reads LINES and COLS the way curses publishes
  them; ckuusx.c also honours a LINES environment variable over the top.
  The Victor's text screen is 80x25, and the 25th line is the status line
  the OEM driver reserves (ESC x1 enables it), so 24 is what a full-screen
  application may use.
*/
extern int LINES, COLS;

/*
  stdscr and curscr are window handles in a real curses.  There are no
  windows here -- every write goes straight at the console -- so they are
  the same 0 upstream's own MYCURSES branch uses (ckuusx.c:6192).  Guarded
  because that branch may have defined them first.
*/
#ifndef stdscr
#define stdscr 0
#endif /* stdscr */
#ifndef curscr
#define curscr 0
#endif /* curscr */

/*
  printw() is curses' printf.  With no window layer to interpose, it IS
  printf.  (CK_WREFRESH is not defined for this platform, so upstream never
  reaches wrefresh()/clearok(); see ckcdeb.h:6155-6185.)
*/
#ifndef printw
#define printw printf
#endif /* printw */

/*
  The four that do something, and the four that do not.  Dual prototypes to
  match the rest of the tree.
*/
#ifdef CK_ANSIC
int move( int, int );                   /* Cursor to row, column (0-based) */
int clear( void );                      /* Erase screen, cursor home       */
int clrtoeol( void );                   /* Erase to end of line            */
int initscr( void );                    /* No-op: nothing to allocate      */
int refresh( void );                    /* No-op: no buffered window       */
int endwin( void );                     /* No-op                           */
int touchwin( int );                    /* No-op                           */
int clearok( int, int );                /* No-op                           */
#else
int move();
int clear();
int clrtoeol();
int initscr();
int refresh();
int endwin();
int touchwin();
int clearok();
#endif /* CK_ANSIC */

/*
  tgetent() is termcap's, not curses', and this build has no termcap -- but
  ckuusx.c:6378 calls it from fxdinit() regardless of which curses is in
  use, so it must at least be declared here or the call is implicit and the
  link is unresolved.  ckvictor.c section 1g has the stub and the reason.
*/
#ifdef CK_ANSIC
int tgetent( char *, char * );
#else
int tgetent();
#endif /* CK_ANSIC */

#endif /* CKV_CURSES_H */

/*  S Y S / T E R M I O S . H  --  POSIX termios for the Victor 9000  */

/*
  The ia16-elf newlib ships <termios.h> as a dangling include of this file,
  which does not exist in the toolchain:

      /usr/ia16-elf/include/termios.h:4:25: fatal error:
          sys/termios.h: No such file or directory

  and it defines no termios functions at all.  ckutio.c compiles clean under
  -DPOSIX except for this one gap, so supplying the header is what unblocks
  the 24th and last module of the build.

  This is NOT a generic POSIX termios.  It is the control surface of the
  Victor's uPD7201 serial driver, expressed in the shape ckutio.c already
  knows how to drive.  See PORTING.md SS11-12.  The implementation lives in
  ckvictor.c; nothing in any toolchain library defines these symbols, so
  there is nothing to collide with.

  Reached via <termios.h>.  Build with -Ivictor so that "#include
  <sys/termios.h>" finds this file.
*/

#ifndef _SYS_TERMIOS_H
#define _SYS_TERMIOS_H

#ifdef __cplusplus
extern "C" {
#endif

/* ------------------------------------------------------------------ */
/* Types                                                                */
/* ------------------------------------------------------------------ */

/*
  tcflag_t is 16 bits, not the 32 you would see on a modern system.  Every
  flag field below fits in 16 bits with room to spare (the widest is c_iflag
  at 14 flags), and this is a 64K DGROUP: ckutio.c keeps roughly six static
  struct termios around (ttold, ttraw, tttvt, ttcur, ccold, ccraw, cccbrk),
  so the narrower type is worth having.
*/
typedef unsigned int   tcflag_t;
typedef unsigned char  cc_t;
typedef unsigned int   speed_t;

#define NCCS 20

struct termios {
    tcflag_t c_iflag;                   /* Input modes                  */
    tcflag_t c_oflag;                   /* Output modes                 */
    tcflag_t c_cflag;                   /* Control modes                */
    tcflag_t c_lflag;                   /* Local modes                  */
    cc_t     c_cc[NCCS];                /* Control characters           */
    speed_t  c_ispeed;                  /* Input speed  (B* code)       */
    speed_t  c_ospeed;                  /* Output speed (B* code)       */
};

/* ------------------------------------------------------------------ */
/* Speeds                                                               */
/* ------------------------------------------------------------------ */

/*
  These are SMALL ORDINALS, System V style -- B9600 is 13, not 9600.

  That choice is deliberate and it is a 16-bit safety property, not a
  stylistic preference.  C-Kermit treats a B* value as an opaque token and
  passes it through whatever variable is at hand; ckutio.c's tthang() does

      int spdsav;
      spdsav = cfgetospeed(&ttcur);       ... cfsetospeed(&ttcur,spdsav);

  with a plain 16-bit int.  Under the BSD convention where B38400 == 38400
  that saves as -27136 and restores a garbage speed; at B76800 it is worse.
  With ordinals every speed is <= 16 and nothing can truncate anywhere.

  ttsspd() reaches these through a switch on (baud/10) whose high-speed arms
  are each wrapped in "#ifdef B<rate>".  So this list IS the machine's speed
  capability: leaving a rate undefined makes C-Kermit correctly reject it
  rather than program a divisor that cannot be generated.

  The Victor derives its baud clock from an 8253 counter fed at 1.25 MHz in
  x16 mode, so

      divisor = 1250000 / (baud * 16) = 78125 / baud

  and 78125 = 5^7 is odd, so NO rate divides it exactly: every entry below
  is approximate and the table in ckvictor.c is the rounded value, not a
  formula.  B7200, B14400, B28800, B57600 and B115200 are ABSENT because
  their divisors (10.9, 5.4, 2.7, 1.4, 0.7) round to errors of 2% to 46%.
  Divisor 1 is the ceiling and it is 78125 bps; B76800 names it, 1.7% low.

  The 1.25 MHz figure is not an assumption.  An earlier revision of this
  header said 1.2288 MHz and 76800/baud, copied from a code comment in the
  FreeDOS Victor INT 14h driver.  Two programs that actually shipped for
  this machine -- MS-DOS Kermit 3.13's msxv90.asm and the 1980s Victor-
  native vickermit.c -- carry byte-identical divisor tables, and those
  tables are 78125/baud: 300 -> 260, 600 -> 130, 1200 -> 65, 2400 -> 32.
  76800/baud would make those 256, 128, 64 and 32.  The FreeDOS driver's
  own subsystem documentation says 1.25 MHz, contradicting its code
  comment, and the two rates it was proven at (9600 -> 8, 38400 -> 2) are
  the ones where the two rules happen to agree.  See PORTING.md SS11a.

  B1800 (divisor 43 -> 1817 bps, +0.9%) is here only because ckutio.c's
  "case 180:" arm is unguarded.  B38400 is divisor 2 -> 39062 bps, +1.7%;
  3.13 shipped that and async framing tolerates roughly 2.5%.
*/

#define B0          0                   /* Hang up: drop DTR and RTS    */
#define B50         1                   /* divisor 1562  (   50.02 bps) */
#define B75         2                   /* divisor 1041  (   75.05 bps) */
#define B110        3                   /* divisor  710  (  110.04 bps) */
#define B134        4                   /* divisor  580  (  134.70 bps) */
#define B150        5                   /* divisor  520  (  150.24 bps) */
#define B200        6                   /* divisor  391  (  199.81 bps) */
#define B300        7                   /* divisor  260  (  300.48 bps) */
#define B600        8                   /* divisor  130  (  600.96 bps) */
#define B1200       9                   /* divisor   65  ( 1201.92 bps) */
#define B1800      10                   /* divisor   43  ( 1816.86 bps) */
#define B2400      11                   /* divisor   32  ( 2441.41 bps) */
#define B4800      12                   /* divisor   16  ( 4882.81 bps) */
#define B9600      13                   /* divisor    8  ( 9765.63 bps) */
#define B19200     14                   /* divisor    4  (19531.25 bps) */
#define B38400     15                   /* divisor    2  (39062.50 bps) */
#define B76800     16                   /* divisor    1  (78125.00 bps) */

#define __MAX_BAUD B76800

/* ------------------------------------------------------------------ */
/* c_iflag -- input modes                                               */
/* ------------------------------------------------------------------ */

#define IGNBRK  0x0001                  /* Ignore break                 */
#define BRKINT  0x0002                  /* Break sends SIGINT           */
#define IGNPAR  0x0004                  /* Ignore parity errors         */
#define PARMRK  0x0008                  /* Mark parity errors           */
#define INPCK   0x0010                  /* Enable parity check          */
#define ISTRIP  0x0020                  /* Strip to 7 bits              */
#define INLCR   0x0040                  /* Map NL to CR on input        */
#define IGNCR   0x0080                  /* Ignore CR                    */
#define ICRNL   0x0100                  /* Map CR to NL on input        */
#define IUCLC   0x0200                  /* Map upper to lower case      */
#define IXON    0x0400                  /* Enable XON/XOFF on output    */
#define IXANY   0x0800                  /* Any char restarts output     */
#define IXOFF   0x1000                  /* Enable XON/XOFF on input     */
#define IMAXBEL 0x2000                  /* Ring bell on input overflow  */

/* ------------------------------------------------------------------ */
/* c_oflag -- output modes                                              */
/* ------------------------------------------------------------------ */

#define OPOST   0x0001                  /* Enable output processing     */
#define OLCUC   0x0002                  /* Map lower to upper case      */
#define ONLCR   0x0004                  /* Map NL to CR-NL on output    */
#define OCRNL   0x0008                  /* Map CR to NL on output       */
#define ONOCR   0x0010                  /* No CR output at column 0     */
#define ONLRET  0x0020                  /* NL performs CR function      */

/* ------------------------------------------------------------------ */
/* c_cflag -- control modes                                             */
/* ------------------------------------------------------------------ */

/*
  CSIZE is a 2-bit field.  The uPD7201 supports all four widths in WR3
  (receive) and WR5 (transmit); Kermit packet mode always uses CS8.
*/
#define CSIZE   0x0003                  /* Character size mask          */
#define CS5     0x0000
#define CS6     0x0001
#define CS7     0x0002
#define CS8     0x0003
#define CSTOPB  0x0004                  /* Two stop bits                */
#define CREAD   0x0008                  /* Enable receiver              */
#define PARENB  0x0010                  /* Enable parity                */
#define PARODD  0x0020                  /* Odd parity                   */
#define HUPCL   0x0040                  /* Drop DTR on last close       */
#define CLOCAL  0x0080                  /* Ignore modem status lines    */
#define CRTSCTS 0x0100                  /* RTS/CTS hardware flow        */

/* ------------------------------------------------------------------ */
/* c_lflag -- local modes                                               */
/* ------------------------------------------------------------------ */

/*
  The driver is always raw: it has no line discipline, so ICANON, ECHO and
  the signal-generating modes are accepted and stored but do nothing on the
  serial port.  They matter only on the console, where ckutio.c uses the
  same struct for congm()/concb()/conres().
*/
#define ISIG    0x0001                  /* Enable INTR/QUIT/SUSP        */
#define ICANON  0x0002                  /* Canonical (line) input       */
#define ECHO    0x0004                  /* Echo input                   */
#define ECHOE   0x0008                  /* Echo erase as BS-SP-BS       */
#define ECHOK   0x0010                  /* Echo kill                    */
#define ECHONL  0x0020                  /* Echo NL even without ECHO    */
#define NOFLSH  0x0040                  /* No flush after INTR/QUIT     */
#define TOSTOP  0x0080                  /* SIGTTOU for background write */
#define IEXTEN  0x0100                  /* Extended input processing    */

/* ------------------------------------------------------------------ */
/* c_cc -- control character indices                                    */
/* ------------------------------------------------------------------ */

#define VINTR    0
#define VQUIT    1
#define VERASE   2
#define VKILL    3
#define VEOF     4
#define VTIME    5
#define VMIN     6
#define VSWTC    7
#define VSTART   8
#define VSTOP    9
#define VSUSP   10
#define VEOL    11
#define VREPRINT 12
#define VDISCARD 13
#define VWERASE 14
#define VLNEXT  15
#define VEOL2   16

/*
  VMIN and VTIME share slots with VEOF and VEOL on many systems.  They do
  not here -- the indices above are distinct -- so ckutio.c can set the raw
  read policy without disturbing the canonical characters.
*/

/* ------------------------------------------------------------------ */
/* tcsetattr() actions                                                  */
/* ------------------------------------------------------------------ */

#define TCSANOW   0                     /* Change immediately           */
#define TCSADRAIN 1                     /* Change after output drains   */
#define TCSAFLUSH 2                     /* Drain output, flush input    */

/* ------------------------------------------------------------------ */
/* tcflush() queue selectors                                            */
/* ------------------------------------------------------------------ */

#define TCIFLUSH  0                     /* Flush received, not read     */
#define TCOFLUSH  1                     /* Flush written, not sent      */
#define TCIOFLUSH 2                     /* Flush both                   */

/* ------------------------------------------------------------------ */
/* tcflow() actions                                                     */
/* ------------------------------------------------------------------ */

#define TCOOFF 0                        /* Suspend output               */
#define TCOON  1                        /* Restart output               */
#define TCIOFF 2                        /* Transmit a STOP character    */
#define TCION  3                        /* Transmit a START character   */

/* ------------------------------------------------------------------ */
/* Functions                                                            */
/* ------------------------------------------------------------------ */

/*
  Implemented in ckvictor.c against the uPD7201 / 8253 / VIA2 directly --
  see PORTING.md SS11.  In summary:

    cfsetospeed/cfsetispeed   record a B* code; the 8253 divisor is written
                              when tcsetattr() applies the settings
    tcsetattr                 uPD7201 WR3/WR4/WR5 (width, stop bits, parity,
                              Rx/Tx enable) + 8253 counter + VIA2 clock gate
    tcgetattr                 return the cached struct -- the chip's write-
                              only control registers cannot be read back
    tcflush                   reset the driver's ring buffer head/tail
    tcsendbreak               WR5 send-break bit, held for the duration
    tcdrain                   spin until the transmit ring empties and the
                              uPD7201 reports Tx buffer empty (RR0 bit 2)
    tcflow                    XON/XOFF; hardware RTS/CTS is handled in the
                              driver when CRTSCTS is set

  A note on tcgetattr: because the settings are cached rather than read from
  the chip, the cache is the single source of truth and every path that
  touches the hardware must go through tcsetattr to keep it honest.
*/

int      tcgetattr(int __fd, struct termios *__t);
int      tcsetattr(int __fd, int __action, const struct termios *__t);
int      tcflush(int __fd, int __queue);
int      tcdrain(int __fd);
int      tcflow(int __fd, int __action);
int      tcsendbreak(int __fd, int __duration);

speed_t  cfgetispeed(const struct termios *__t);
speed_t  cfgetospeed(const struct termios *__t);
int      cfsetispeed(struct termios *__t, speed_t __speed);
int      cfsetospeed(struct termios *__t, speed_t __speed);

#ifdef __cplusplus
}
#endif

#endif /* _SYS_TERMIOS_H */

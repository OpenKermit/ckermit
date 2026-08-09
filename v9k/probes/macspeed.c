/*
  macspeed.c -- set an arbitrary, non-standard bit rate on a macOS serial
  port, and optionally hold it there.

  HOST-SIDE, unlike everything else in v9k/probes/.  It exists because of
  PORTING.md SS11a0: the Victor's x1 clock mode produces rates the 8253's
  count quantisation puts nowhere near a standard one --

      count 130 ->   9,615.38      count  22 ->  56,818.18
      count  65 ->  19,230.77      count  16 ->  78,125.00
      count  33 ->  37,878.79      count  11 -> 113,636.36

  -- and at x1 the tolerable rate error is roughly 1/(9 x packet length),
  so a 1.36% nominal mismatch is fatal where 1.7% is harmless at x16.  The
  Victor cannot meet the host halfway: at count ~130 one step is 0.77%.
  So the host has to move, and macOS will not do these rates through
  termios.  IOSSIOSPEED will.

  Build:  cc -O2 -o v9k/probes/macspeed v9k/probes/macspeed.c

  Use:    v9k/probes/macspeed /dev/tty.usbserial-BG022B8M 9615 -h

  -h holds the descriptor open and sleeps.  That matters: IOSSIOSPEED is a
  property of the open port, and macOS restores the driver's idea of the
  speed on last close.  Hold it here, run C-Kermit in another terminal
  against the same device, and DO NOT give C-Kermit a "set speed" command --
  ttpkt() calls ttsspd() whenever a speed was set, which would put a
  standard rate back over the top of this one.  Ctrl-C when the run is done.

  -p is the mode that actually works with C-Kermit, and -h is kept only as
  the diagnostic that proved why.  Sharing the port does not work: C-Kermit's
  ttopen() does tcgetattr() then tcsetattr(), inherits the non-standard speed
  and hands it straight back, and macOS rejects that with EINVAL --

      set line /dev/cu.usbserial-XXXX
      tcsetattr: Invalid argument

  which is the same trap upstream documents in ckutio.c's own macOS path
  ("Set baudrate to standart one so tcsetattr() will not fail").  So -p puts
  a pty in between: this program owns the real port at the odd rate, and
  C-Kermit talks to a pty where every termios call succeeds and the speed is
  meaningless.  Point "set line" at the slave name printed on startup.

  It prints what tcgetattr reads back afterwards.  Treat that as advisory:
  a non-standard rate does not always survive the round trip through
  termios even when the hardware has taken it.  The measurement that counts
  is a scope on the line, which is how SS11a0's numbers were obtained in
  the first place.
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <termios.h>
#include <sys/ioctl.h>
#include <sys/select.h>
#include <util.h>

#ifndef IOSSIOSPEED
/* <IOKit/serial/ioss.h>: _IOW('T', 2, speed_t) */
#define IOSSIOSPEED _IOW('T', 2, speed_t)
#endif

int
main(int argc, char ** argv)
{
    const char * dev;
    unsigned long want;
    speed_t sp;
    struct termios t;
    int fd, hold = 0, bridge = 0, i;

    if (argc < 3) {
        fprintf(stderr,
                "usage: %s <device> <bps> [-h | -p]\n"
                "   -h  hold the port open (diagnostic only; see the header)\n"
                "   -p  bridge to a pty -- THIS is the one to use with kermit\n",
                argv[0]);
        return 2;
    }
    dev  = argv[1];
    want = strtoul(argv[2], NULL, 10);
    for (i = 3; i < argc; i++)
      if (!strcmp(argv[i], "-h")) hold = 1;

    if (want == 0) {
        fprintf(stderr, "%s: bad rate\n", argv[0]);
        return 2;
    }

    for (i = 3; i < argc; i++)
      if (!strcmp(argv[i], "-p")) bridge = 1;

    fd = open(dev, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) { perror(dev); return 1; }

    /*
      Clear O_NONBLOCK now that it is open -- it was only needed to get past
      a carrier wait on a port with nothing asserting DCD.
    */
    if (fcntl(fd, F_SETFL, 0) < 0) { perror("fcntl"); close(fd); return 1; }

    if (tcgetattr(fd, &t) < 0) { perror("tcgetattr"); close(fd); return 1; }
    printf("before: ospeed %lu\n", (unsigned long) cfgetospeed(&t));

    /*
      Raw, and a STANDARD speed in the struct, because macOS refuses
      tcsetattr() with a non-standard one -- the IOSSIOSPEED goes on top
      afterwards.  This ordering is upstream's, from ckutio.c's macOS path.
    */
    cfmakeraw(&t);
    t.c_cflag |= (CLOCAL | CREAD);
    t.c_cflag &= ~CRTSCTS;
    cfsetospeed(&t, B9600);
    cfsetispeed(&t, B9600);
    if (tcsetattr(fd, TCSANOW, &t) < 0) { perror("tcsetattr"); close(fd); return 1; }

    sp = (speed_t) want;
    if (ioctl(fd, IOSSIOSPEED, &sp) < 0) {
        fprintf(stderr, "IOSSIOSPEED %lu: %s\n", want, strerror(errno));
        close(fd);
        return 1;
    }

    if (tcgetattr(fd, &t) == 0)
      printf("after:  ospeed %lu   (asked for %lu)\n",
             (unsigned long) cfgetospeed(&t), want);

    if (bridge) {
        int mfd, sfd;
        char slave[256];
        struct termios pt;

        if (openpty(&mfd, &sfd, slave, NULL, NULL) < 0) {
            perror("openpty"); close(fd); return 1;
        }
        /*
          The pty has to be raw too, or its line discipline will echo the
          protocol back at C-Kermit and mangle control characters.  Its
          "speed" is meaningless -- the real rate is on fd, above -- which is
          the whole point: every termios call C-Kermit makes on the pty
          succeeds, including the tcsetattr that fails on the real port.
        */
        if (tcgetattr(sfd, &pt) == 0) {
            cfmakeraw(&pt);
            pt.c_cflag |= (CLOCAL | CREAD);
            tcsetattr(sfd, TCSANOW, &pt);
        }

        printf("\nbridge up:  %s  <->  %s at %lu bps\n", slave, dev, want);
        printf("in C-Kermit:  set line %s      (and NO 'set speed')\n", slave);
        printf("Ctrl-C when the transfer is done.\n\n");
        fflush(stdout);

        for (;;) {
            fd_set r;
            char buf[1024];
            int n, hi;

            FD_ZERO(&r);
            FD_SET(fd, &r);
            FD_SET(mfd, &r);
            hi = (fd > mfd ? fd : mfd) + 1;
            if (select(hi, &r, NULL, NULL, NULL) < 0) {
                if (errno == EINTR) continue;
                perror("select"); break;
            }
            if (FD_ISSET(fd, &r)) {             /* Victor -> C-Kermit */
                n = read(fd, buf, sizeof(buf));
                if (n > 0) (void) write(mfd, buf, n);
                else if (n < 0 && errno != EAGAIN && errno != EINTR) break;
            }
            if (FD_ISSET(mfd, &r)) {            /* C-Kermit -> Victor */
                n = read(mfd, buf, sizeof(buf));
                if (n > 0) (void) write(fd, buf, n);
                /* EIO here just means no process has the slave open yet. */
                else if (n < 0 && errno != EAGAIN && errno != EINTR
                         && errno != EIO) break;
            }
        }
        close(mfd); close(sfd); close(fd);
        return 0;
    }

    if (!hold) {
        printf("NOT holding the port -- the rate reverts on close."
               " Re-run with -p (or -h).\n");
        close(fd);
        return 0;
    }

    printf("holding %s at %lu bps; Ctrl-C when the transfer is done.\n",
           dev, want);
    printf("NOTE: C-Kermit's own tcsetattr will fail EINVAL on this port."
           " Use -p instead.\n");
    fflush(stdout);
    for (;;) pause();
    /* NOTREACHED */
}

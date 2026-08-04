/*  C K V I C T O R . H  --  Build configuration for Victor 9000 / Sirius 1  */

/*
  Serial-only C-Kermit for the Victor 9000 (Sirius 1) under Victor MS-DOS,
  built with ia16-elf-gcc against a newlib-based C runtime.

  This header is force-included ahead of every source file:

      ia16-elf-gcc -mcmodel=medium -include ckvictor.h ...

  Nothing else in the tree includes it, so it cannot affect any other
  platform.  It exists because the feature set is expressed as ~40 -D
  options and putting them on the command line makes the build unreadable.

  TARGET MODEL
    CPU            8088, real mode, 16-bit
    int            16 bits          long   32 bits
    code           far  (medium model, multiple code segments, up to 1MB)
    data           NEAR ONLY -- ia16-elf-gcc has no compact/large/huge model,
                   so .data + .bss + heap + stack must all fit one 64K DGROUP.

  The 64K data group is the binding constraint for this port.  Every size
  choice below exists to keep DGROUP occupancy down.  Do not raise these
  numbers without re-measuring; see PORTING.md for the current budget.
*/

#ifndef CKVICTOR_H
#define CKVICTOR_H

/* ------------------------------------------------------------------ */
/* Platform identity                                                    */
/* ------------------------------------------------------------------ */
/*
  We present as UNIX + POSIX.  That is not a pretence: the newlib port
  supplies open/close/read/write/lseek/stat, a POSIX termios layer, and
  dirent, which is exactly the surface ckutio.c and ckufio.c use.  Claiming
  UNIX also makes ckcdeb.h define DYNAMIC, which is essential -- it turns
  the packet buffers into malloc'd pointers instead of >64K static arrays.
*/
#ifndef UNIX
#define UNIX
#endif
#ifndef POSIX
#define POSIX
#endif
#ifndef VICTOR9K
#define VICTOR9K
#endif

/* newlib already provides sig_t; suppress C-Kermit's own typedef. */
#ifndef CK_NO_SIG_T
#define CK_NO_SIG_T
#endif

/* ------------------------------------------------------------------ */
/* Size limits -- the 64K DGROUP budget                                 */
/* ------------------------------------------------------------------ */

/*
  scanfile() declares "unsigned char buf[SCANFILEBUF]" as an AUTOMATIC.
  The stock 49152 would blow the entire stack on the first call.
*/
#define SCANFILEBUF 2048

/*
  MS-DOS paths are short.  CKMAXPATH is multiplied by RQ_MAXTOK and by
  several other tables, so it is a strong lever on total data size.
*/
#define CKMAXPATH 128

/* rq_tok is RQ_MAXTOK*(CKMAXPATH+1) bytes: 16*129 = 2064 rather than 9280. */
#define RQ_MAXTOK 16

/*
  Packet buffers.  With DYNAMIC these are malloc'd from the near heap, so
  they compete directly with everything else in DGROUP.

    SBSIZ/RBSIZ are the total buffer pools, carved at runtime into
    (window slots) x (negotiated packet length).

  9024/9050 (the DYNAMIC default) would take 18K of a 64K data group for
  packet buffers alone.  4096 each still allows, for example, a 4-slot
  window of 1000-byte long packets, which is far more throughput than a
  38400 bps line needs.  Raise later if measurement says there is room.
*/
#define MAXSP 1024                      /* Max long packet, send    */
#define MAXRP 1024                      /* Max long packet, receive */
#define MAXWS 8                         /* Sliding window slots     */
#define SBSIZ 4096                      /* Send buffer pool         */
#define RBSIZ 4096                      /* Receive buffer pool      */

/* Do NOT define BIGBUFOK: it asks for 290000-byte buffers. */

/* ------------------------------------------------------------------ */
/* Subsystems removed -- networking and security                        */
/* ------------------------------------------------------------------ */
/*
  These take ckcnet.c, ckctel.c, ckcftp.c, ckuath.c, ck_ssl.c and ck_crp.c
  out of the picture.  ckcnet.c and ckctel.c still compile (to ~100 bytes
  total) and are kept in the link so their few referenced symbols resolve
  without editing the mainline code.
*/
#define NONET                           /* No networking at all       */
#define NOTCPIP                         /* No TCP/IP                  */
#define NOSSH                           /* No SSH                     */
#define NOFTP                           /* No FTP client              */
#define NOHTTP                          /* No HTTP client             */
#define NOIKSD                          /* No Internet Kermit Service */
#define NORLOGIN                        /* No rlogin                  */
#define NOURL                           /* No URL parsing             */
#define NOBROWSER                       /* No browser dispatch        */

/* ------------------------------------------------------------------ */
/* Subsystems removed -- character sets                                 */
/* ------------------------------------------------------------------ */
/*
  This is the single biggest win in the whole configuration.  NOCSETS and
  NOUNICODE reduce ckuxla.c and ckcuni.c to literally zero bytes of code
  and data -- ckcuni.c alone is 770KB of source, almost all translation
  tables.  Transfers are still fully correct in binary mode and in text
  mode for ASCII, which is all the Victor needs.
*/
#define NOCSETS                         /* No charset translation     */
#define NOUNICODE                       /* No Unicode tables          */

/* ------------------------------------------------------------------ */
/* Subsystems removed -- process model                                  */
/* ------------------------------------------------------------------ */
/*
  MS-DOS has no fork/exec, no pseudo-terminals and no job control, so
  everything that depends on spawning a second process must go.
*/
#define NOPTY                           /* No pseudo-terminals        */
#define NOPUSH                          /* No external commands/shell */
#define NOJC                            /* No job control (suspend)   */
#define NOREDIRECT                      /* No REDIRECT / pipes        */

/* ------------------------------------------------------------------ */
/* Subsystems removed -- dialing                                        */
/* ------------------------------------------------------------------ */
/*
  ckudia.c is 238KB of modem database.  A direct serial connection needs
  none of it.  MINIDIAL additionally trims what little remains.
*/
#define NODIAL                          /* No DIAL command / modem db */
#define MINIDIAL                        /* Minimum modem support      */
#define NOLOGDIAL                       /* No dial logging            */

/* ------------------------------------------------------------------ */
/* Subsystems removed -- scripting and interactive conveniences         */
/* ------------------------------------------------------------------ */
/*
  NOSPL removes the script language (variables, macros, IF/WHILE, functions)
  -- ~1100 references, and a large amount of both code and data.  The
  interactive command parser itself is NOT removed; NOICP is deliberately
  left undefined because "C-Kermit>" with SEND/RECEIVE/GET/SERVER is the
  entire point of the milestone.
*/
#define NOSPL                           /* No script language         */
#define NOSCRIPT                        /* No UUCP-style script       */
#define NOSEXP                          /* No S-expressions           */
#define NOLEARN                         /* No learned scripts         */
#define NOHELP                          /* No built-in help text      */
#define NORECALL                        /* No command recall/edit     */
#define NOSETKEY                        /* No key mapping             */
#define NOKVERBS                        /* No keyboard verbs          */
#define NOXMIT                          /* No TRANSMIT command        */
#define NOMSEND                         /* No multi-file MSEND        */
#define NOFRILLS                        /* No minor conveniences      */
#define NOCCTRAP                        /* No setjmp ^C trapping      */

/* ------------------------------------------------------------------ */
/* Subsystems removed -- logging, debugging, terminal                   */
/* ------------------------------------------------------------------ */
/*
  NODEBUG is worth a lot: debug() calls are threaded through every module
  and each one costs code plus format strings in DGROUP.
*/
#define NODEBUG                         /* No debug log               */
#define NOTLOG                          /* No transaction log         */
#define NOSYSLOG                        /* No syslog                  */
#define NOCURSES                        /* No curses fullscreen       */
#define NOTERMCAP                       /* No termcap                 */
#define NOESCSEQ                        /* No escape-sequence parsing */

/* ------------------------------------------------------------------ */
/* Odds and ends not available or not wanted                            */
/* ------------------------------------------------------------------ */
#define NOREALPATH                      /* No realpath()              */
#define NOTIMEZONE                      /* No timezone database       */
#define NORANDOM                        /* No random numbers          */
#define NOUUCP                          /* No UUCP lockfiles          */
#define NOWTMP                          /* No wtmp accounting         */
#define NOPARSEN                        /* No network directory parse */

/*
  Deliberately NOT defined -- these are the features being ported:

    NOICP     interactive command parser  ("C-Kermit>" prompt)
    NOXFER    file transfer               (SEND / RECEIVE / GET)
    NOSERVER  server mode                 (SERVER)
    NOLOCAL   local mode / SET LINE       (needed to own a serial port)
    NOLP      long packets
    NOWINDOW  sliding windows
    NORESEND  RESEND / REGET  (restart)
    NOSTREAMING  streaming
*/

#endif /* CKVICTOR_H */

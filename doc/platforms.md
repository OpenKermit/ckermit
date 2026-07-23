# C-Kermit Platform-Specific Notes

## Linux

Official binaries for this release are built on Ubuntu 24.04 and are built with
SSL support.  They should be broadly compatible with recent releases of most
distributions.

If you have issues with those binaries, try the static builds.  Due to
significant variations between distributions, Linux binaries are additionally
available in a static build, which is linked against musl libc.  These have no
dependencies from the running system, and thus should be portable to many
versions and distributions of Linux in the chosen architecture.  However, since
they do not use the system's libraries (such as OpenSSL), they don't benefit
from security updates that your distribution may make to system libraries like
OpenSSL.  Therefore, I recommend not using SSL facilities on the static
binaries.  (Very few people use SSL in Kermit these days anyhow.)  The static
binaries are helpful for bootstrapping connectivity to a new (or old!) system,
for instance.

While the statically-linked version does have ncurses built in, C-Kermit
degrades gracefully if you lack a terminfo database.  Therefore, it is a truly
standalone binary.

## macOS

Official binaries for this release are built on macOS 26 and are built without
SSL support.

Because there is no base-system support for building against standard OpenSSL
libraries, a binary that is just "run anywhere" on any macOS machine cannot use
OpenSSL.  While we test the SSL build in CI, the built binaries are built
without SSL for maximum compatibility.

## FreeBSD

Official binaries for this release are built on FreeBSD 15.1 and are built
without SSL support.

## OpenBSD

Official binaries for this release are built on OpenBSD 7.9 and are built
without SSL support.

## NetBSD

Official binaries for this release are built on NetBSD 10.1 and are built
without SSL support.

### Weird problems on NetBSD

This is only applicable when using pseudoterminals (ptys), which are used for
`SSH`, when explicitly requested from `SET HOST`, and when using external
protocols like ZModem.

NetBSD has a kernel bug in which the kernel can sometimes return a value
indicating more data was successfully written down the pty than actually was,
causing loss of bytes of data.  When in default mode, C-Kermit detects this and
automatically shrinks its packet size to compensate! When in streaming mode,
this is fatal to the transfer, and was detected when I added streaming mode
tests.  The workaround is to run `sysctl -w kern.tty.qsize=65536` or to set it
in `/etc/sysctl.conf`; a comment in that file implies this issue is known
already as it is required for other system components as well. 

- John Goerzen, July 2026

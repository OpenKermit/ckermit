# OpenKermit C-Kermit Changelog

# C-Kermit 11.0.509 (not yet released)

- Fixed a bug in statements like `\fcvtdate(..., -4)` where there was no space
  between the day and the year, producing outputs like `Sat Nov 262005` instead
  of `Sat Nov 26 2005`.

- Fixed an out-of-bounds month lookup in shuffledate() for month values
  outside 1-12, and corrected off-by-one whitespace stripping in date
  parsing.  Added unit tests for these date-handling functions.

- Fixed an issue where SIGWINCH window-resize signals were not forwarded to
  child processes after running an external protocol such as Zmodem.

- Fixed pty cleanup after external protocol execution, preventing a
  transfer-interrupting Ctrl-C from terminating PTY connections.

- Fixed a bug in the telnet buffer processing loop that could cause individual
  or repeated 1-second stalls in certain circumstances

- Enable SET DEBUG TIMESTAMPS during tests to help pinpoint timeouts and
  performance problems

- Save off localtime() results in zdtstr()/zstrdt() to prevent mtime skew when
  SET DEBUG TIMESTAMPS is ON.

- Ran with various warning-enable options, cleaning up warnings along the way.

- Fixed bugs identified during the warning sweep:
  - Corrected operator precedence grouping in `\femail()`.
  - Fixed array indexing with signed `char`.
  - Fixed uninitialized seek offsets in `FILE SEEK`.
  - Fixed an uninitialized buffer read during DNS TXT record lookups.
  - Fixed a comment-parsing defect in `cmcvtdate()`.
  - Replaced an unbounded `vsprintf()` in `ckxprintf()` with `vsnprintf()` and
    added GCC format attributes to printf wrappers.
  - Fixed a potential buffer overflow in UNIX domain socket path handling in
    `ckcnet.c`.
  - `SET DIAL TIMEOUT` reset `DIAL ESCAPE-CHARACTER` to 43.  Also, 
    an unexpected `DIAL STRING` parameter caused control to pass to `DIAL
    FLOW-CONTROL`.  These bugs introduced in C-Kermit 6.0.192 of 1996, commit
    4b5eddeab4bc511701864c151fb0bebb067278d5.
  - `REPEAT` and `CD` switch value handling could fall into handler for
    different commands.
  - `\funtab()` with a parameter over the maximum length would fall into
    `\funhex()`.
  - `FILE SEEK /FIND` without an argument corrupted `rsize`.

# C-Kermit 11.0.508

August 9, 2026

- Added support for [VSOCK](vsock.md) sockets on Linux.  These are used as a
  lightweight way to communicate between a host and a guest VM.

- Made a number of improvements to the test suites such that they are less flaky
  on the BSD VMs they run within in CI.
  
- Added documentation for the OpenVMS support that was updated in 11.0.507.

# C-Kermit 11.0.507

August 5, 2026

- Fixed a bug (in commit 70ac526a7) where a pty didn't have IXON forced off,
  which manifested itself when doing an unprefixed send to gkermit.  The bug
  had existed since the introduction of the pty code in commit d0f8b1da7 in
  2000.

- Applied fixes for compilation under OpenVMS x86_64.  Thank you Tony
  Nicholson for this submission.

- List IPv6 support in `SHOW FEATURES`.

# C-Kermit 11.0 wide announcement (11.0.506)

August 3, 2026

This is the public announcement of the release, and is a summary of all changes
since the last full release, 9.0.302 in 2011.

## Dedication

> I dedicate this release of C-Kermit to Frank da Cruz.
>
> Frank was directly involved with Kermit for 44 years, from its initial design
> in 1981 all the way through 2025.  He maintained Kermit as an Open Source
> project after Columbia University ended its sponsorship.  I know of no other
> Open Source project where the founder remains so personally involved for so
> long.
>
> When Kermit was begun, transfers between different hardware and operating
> systems were difficult or impossible.  Frank helped build a bridge.  Kermit
> glued systems together, from the International Space Station to pocket
> calculators, and set a new standard for interoperability.  It continues to do
> so.
> 
> Kermit is still one of the quietly-working pillars of computing today,
> enabling everything from firmware upgrades to radios.  And, yes, it still
> reliably transfers files over serial lines.
>
> As we start to spend a lot of time in the Kermit codebase, we do so standing
> on the shoulders of a giant.  Thanks, Frank, for your decades of work on
> Kermit.
> 
> John Goerzen, July 2026

## Summary

C-Kermit 11 is a major new release, the first non-beta since the last 9.x
release in 2011.  It represents a significant effort to modernize and improve the
C-Kermit codebase.

Since all C-Kermit 10.x releases were betas, some people may be upgrading from
9.x and others from 10.x.  Since some changes were labeled as "9.x DEV" or
various alphas, but also never released, I indicate in which version a change
was made with "9", "10", and "11" tags accordingly.  Please see the
[history](https://www.openkermit.org/history) and
[FAQ](https://www.openkermit.org/faq) pages for more information on the
relationship between the different Kermit versions.

## Major Architectural Improvements

- [11] Introduced C-based unit tests and a Python-based regression test suite.
  Together, these test suites have been responsible for identifying nearly all
  of the bug fixes in the v11 release as noted below.  Timing analysis of the
  test suite also led to most of the performance fixes.  Running the tests under
  load led to the discovery and fix of numerous race conditions.

  - [11] Also introduced compatibility tests that test the current release
    against gkermit, E-Kermit (eksw), and the last C-Kermit full release prior
    to 11.0 (9.0.302 from 2011).  This also led to a fix for a bug dating back
    to C-Kermit 9.0.304 of 2012.

- [11] Added CI.  All changes now are validated on Linux, MacOS, FreeBSD, and
  NetBSD using the above test suites.  Over 1700 test cases are being
  run.
  
- [11] Binaries for multiple platforms are automatically built from CI at
  release time.

- [10] Codebase-wide modernization to support ANSI C and function prototyping,
  satisfying strict requirements in newer compilers while retaining backward
  compatibility with pre-ANSI systems.

## New Features

- [11] C-Kermit's TCP stack now supports IPv6, while degrading gracefully to
  IPv4 on hosts that don't have IPv6 connectivity, or whose system libraries
  don't support IPv6.  For more, see the new 
  [IPv6 in C-Kermit document](ipv6.md).
    
- [11] There's now a tool that will extract all the help text from C-Kermit and
  write a nice Markdown file that acts as an up-to-date command reference for
  your specific platform.  A generated version of this can be found at 
  [HELP reference](help-reference.md).
  
- [11] `SET COMPATIBILITY 9` and `SET COMPATIBILITY 10` to easily change
  settings to maximize compatibility with C-Kermit 9.0.302 and 10.0 Beta.12,
  respectively.  This restores previous behavior, which weakens Kermit's
  security posture.  These settings can also be applied at startup by invoking
  Kermit as `kermit9` or `kermit10`.
  
- [9] Android platform support, including NDK builds and a vanity herald.

- [9] Locale support for dates, times, and error messages (with Spanish
  and German translations), controllable via the --nolocale command-line
  option and K_NOLOCALE environment variable.

- [9] A new `CHANGE` command to search and replace strings in files, using
  standard directory and touch file-selection switches.

- [9] A new `FOPEN /STDIN` command to allow Kermit scripts to read standard
  input from a pipe.

## Major Improvements

- [11] External protocol (Zmodem and the like) support has seen significant
  performance increases in many cases, due to elimination of inefficiencies in
  the pty code that supports it.

- [11] Codebase-wide dead code elimination and general simplification.  This
  removes code that was never used in any build on any platform, and makes code
  auditing and analysis easier.  Despite many new features, the C-Kermit 11
  codebase (excluding comments) is about 2600 lines smaller than the last 10.x
  beta!

- [11] Now compatible with OpenSSL 3.x and 4.x. The OpenSSL runtime version
  check was relaxed to allow minor version updates, and support was added for
  compiling with `NO_OPENSSL_VERSION_CHECK` to disable the compatibility check.
  
- [11] Static binaries are now supported on Linux, with both glibc and musl
  libc.  Official musl static binaries for Linux on amd64 and arm64 are built
  for each release.
  
- [11] Added a number of new pieces of documentation.

- [10] Support for serial-port speeds up to 4,000,000 bps.

- [9] Modernized FTP/SSL and Telnet/SSL negotiations to default to TLS 1.0+
  and disable SSLv3 by default (POODLE mitigation), adding the use-ssl-v3
  bug option for fallback compatibility.

## Major Bugfixes

- [11] Certain packet sizes on the boundary between small and extended packet
  sizes could lead to a transfer being hung on all platforms.  Fixed the bug in
  commit d560c580d and added extensive tests around this scenario.  Bug
  introduced in C-Kermit 10.0 Beta.05 of 2022.
  
- [11] Fixed a data corruption bug that occurred during packet size
  renegotiation due to improperly using strlen() to determine the size of binary
  data that may contain NULL bytes. (commit b58e0336)  This issue was only
  observed by running the test suite on NetBSD, but the code pattern indicates
  it could occur on any platform given the correct circumstances.  The bug was
  introduced in C-Kermit 5A(188) in 1992 in commit a213649d.

- [11] Numerous pty issues were remedied on MacOS; some had been going back decades.
  In particular, MacOS FIONREAD appears to be unreliable, and assuming it to be
  reliable led to some hard-to-track-down hangs.
  
- [11] C-Kermit now is fully able to process filenames with embedded spaces due
  to numerous bugfixes in commit b06df3874.  Among them:
  
  - You can now use `GET` to retrieve a file whose name has embedded spaces
    (previously you could only `SEND` such a file).

  - `MGET` had bugs around quoting that inadvertently would strip necessary quote characters.

  - The Kermit Protocol treats a space as a delimeter between filenames, unless
    it is enclosed in braces.  The C-Kermit client accepts both double quotes
    and braces as quoting characters.  The client now will properly quote all
    filenames containing spaces with braces when sent to the server, regardless
    of which scheme the user selected.

  - Several `REMOTE` commands were broken with filenames with embedded spaces or
    escaped delimiters.

  - Numerous bugs relating to escaping of embedded quote/brace characters as
    part of filenames were fixed.

  - `GET` and `SEND` used inconsistent quoting rules.

- [11] Recursive transfer fixed on MacOS in commit f60a87eb46.  The bug appears
  to have been introduced in C-Kermit 10.0 Beta.01, commit 1755b856b in 2022.

- [11] Fixed filename collision (overwrite) detection on MacOS.  Same origin as
  the recursive issue.

- [11] Fixed a packet size negotiation bug that manifest itself in talking to
  E-Kermit (eksw).  The bug was introduced in C-Kermit 9.0.305 of 2021-11-16.

- [11] Make sure timeval usec is initialized.  It was used uninitialized,
  leading to undefined behavior that could corrupt the modification date by many
  seconds or minutes.  The relevant code was added in C-Kermit 8.0.200 (commit
  c88d9b8561 in 2001), but usec may not have been widely used at the time.

- [11] Added new `SET PROTOCOL STARTUP-STRING` to allow easy inhibiting of all
  startup strings where necessary.

- [11] When transferring multiple files in text mode, the system would detect
  Unicode encoding on only the first, and blindly apply that assumption to all
  the rest.  Commit 93ffe0241.

- [11] Fixed a bug where raw TLS connections could hang waiting for Telnet
  negotiation in commit 0b9dc4f2.  The issue appears to date back to at least
  C-Kermit 8.0.211 of 2004.

- [11] Fixed a bug in ttopen where pipe connections did not execute the
  configured command.
  
- [11] Found and fixed numerous buffer overruns and memory leaks.

- [11] Tracked down a pseudoterminal failure on NetBSD.  It turns out to be a
  kernel bug in which the kernel can sometimes return a value indicating more
  data was successfully written down the pty than actually was, causing loss of
  bytes of data.  When in default mode, C-Kermit detects this and automatically
  shrinks its packet size to compensate!  (This is what exposed the strlen() bug
  mentioned elsewhere.)  When in streaming mode, this is fatal to the transfer,
  and was detected when I added streaming mode tests.  The workaround is to run
  `sysctl -w kern.tty.qsize=65536` or to set it in `/etc/sysctl.conf`; a comment
  in that file implies this issue is known already.

- [11] Several other pty issues were also remedied on NetBSD. 

- [11] Fix IKSD server refusing all connections when built with SSL support but
  not configured with an SSL cert.  This had been a long-standing C-Kermit bug.
  Fixed in commit 5160132b.  Appears to have been introduced in C-Kermit 8.0.200
  in 2001 with the introduction of the SSL code at that time.
  
- [10] Fixed the `TOUCH` command, which had been nonfunctional.

- [9] Fixed a crash on 64-bit platforms (such as OpenBSD sparc64) during file
  transfers due to conflicting int/long declarations.

- [9] Fixed a crash in Open Watcom Windows builds caused by inconsistent
  extern declarations of the vmode variable.

- [9] Fixed S-Expression processor core dumps when given invalid operators.

- [9] Fixed the `DIRECTORY /BRIEF` command to correctly honor the `/EXCEPT`
  switch.

- [9] Fixed a bug in zchko() that caused FTP GET commands to segment fault on
  systems with NOUUCP defined.

- [9] Added CK_64BIT support, significantly increasing command, macro,
  variable, and packet buffer sizes on 64-bit architectures.

## Security and Reliability Improvements

- [11] More durable privilege dropping (priv_chk)

- [11] Elimination of a number of unbounded writes to buffers

- [11] Disable auto transfer mode by default, which switched between text and
  binary transfer modes based on a heuristic.  For full details, see commit
  cdd2e257e and the discussion at https://bugs.debian.org/1121901 .  The
  heuristic for attempting to guess the type of files is now disabled to avoid
  data corruption, letting Kermit always follow the user's expressed transfer
  type wishes by default.

- [11] Fix CVE-2025-68920, insecure defaults that previously would let a
  malicious remote kermit server perform actions on your local workstation.
  Further discussion in commit 9ee170a85 and full details at
  http://bugs.debian.org/1123025 .  See more details under changed behavior
  below for how to adjust this in the rare event you might need to.

- [11] Switch the default `SET FILE COLLISION` from BACKUP to REJECT.  The
  previous default would let a malicious remote overwrite sensitive local files
  (eg, `.bashrc`) which could lead to a security issue.

- [11] Fixed a bug where the CLEAR APC command could bypass APC safety checks or
  cause the parser to hang.
  
- [11] Disabled MAIL and PRINT handling by default (dc67bddb), and hardened the
  handling of them to prevent shell injection attacks (23ec7368).

- [11] Added new receive confirmation, which prompts for confirmation before
  receiving a file with a name that wasn't specifically requested locally.  This
  is governed by a new `SET RECEIVE CONFIRM` option, which defaults to `ON`.
  This does not prompt when running headless (ie, server or iksd).

- [10] Changed the default value of SET VARIABLE-EVALUATION to SIMPLE
  (non-recursive) to avoid evaluation issues with backslashes in pathnames on
  Windows and OS/2.

- [9] Fixed a bug where TOUCH /MODTIME could destroy existing files under
  certain conditions.

See the section below on changed behavior for highlights on the impact of
changed defaults.  This impact is expected to be rare.

## Additional improvements and bugfixes

- [11] Fixed an unhandled exception warning on NetBSD

- [11] Prevent Kermit from killing all of the user's processes in certain edge
  cases where it may try to kill PID -1.  Fixed in commit 72fa00b3.  Bug
  introduced in C-Kermit 9.0.302 of 2011.

- [11] Correct use of ziperm vs. ziperms for non-CK_PERMS platforms.  Fixed in
  commit 3fcd731c.  Appears to have been latent since C-Kermit 7.0 in 2000.

- [11] Updated the list of text and binary extensions to have more modern filetypes,
  and fixed typos in the old list.
  
- [11] Improve transfer error reporting.  Previously, errors might be reported
  on the transfer screen, then immediately wiped when switching back to the
  regular screen.  Now report them on the regular screen also.  A comment from
  2001 suggested that after this work was done, a failed autodownload could drop
  the user back into CONNECT mode just like a successful one did.  So, changed
  the default for `SET TERMINAL AUTODOWNLOAD ERROR` from `STOP` to `CONTINUE`.

- [11] Added new `SET FILE SYSTEM-ID` setting, which facilitates using C-Kermit
  to translate files between different platform conventions even when used on a
  single platform.  It also facilitates testing these functions.

- [11] Allow pseudoterminals to work even when Kermit itself is not called from
  a controlling terminal.

- [11] Fixed Unicode text detection for very small files in commit dfd875f3e.
  Issue dates back to the introduction of this code in C-Kermit 9.0.302 in 2011.

- [11] Several improvements to help text

- [11] Fixed japanese-roman character set

- [10, 11] OS/2 compatibility improvements

- [11] Fixed command prompt formatting in anonymous IKSD when the home
  directory is root (/).

- [11] Fixed Gentoo builds after the ncurses tinfo library split.

- [11] Fixed SET HOST to work properly after an ssh command had been issued
  earlier in the same session. (10eb1924)  Bug introduced in C-Kermit 9.0.302 of
  2011.

- [11] Fixed several issues where EINTR from read() could cause C-Kermit to
  improperly close a connection.  In one case, signals such as SIGWINCH at
  particular times triggered this issue on Linux; in another, the test suite
  caused it on NetBSD.
  
- [11] Coincidentally, fixed a bug in winchh(), which is the handler for
  SIGWINCH, in which is fails to restore errno before returning, so an error
  from a call it makes can lead the interrupted code to believe an error other
  than EINTR occurred.
  
- [11] Fixed a bug in SSL network read that was triggered by ZModem over SSL,
  which resulted in exceptionally slow performance in certain circumstances
  
- [11] Fixed an issue with the telnet protocol handling of a NULL after a bare
  CR
  
- [11] Fixed build issues on OpenBSD

- [11] Fixed a bug on OpenBSD that could cause ZModem transfers to be truncated
  under heavy load

- [11] Now give an accurate error message instead of "write access to UUCP
  lockfile" about errors that had nothing to do with the lockfile
  
- [11] Fixing recursive receive, which led to a deep dive into C-Kermit permissions.
  See the new [C-Kermit permissions documentation](permissions.md).

- [11] Added a workaround to the client to deal with old broken IKSD servers.

- [11] Fixed a telnet negotiation race related to EINTR and select

- [11] Fixed Unicode BOM detection issue that may manifest on big-endian
  architectures.  Fixed in commit da4699ca2.  Dates back to at least C-Kermit
  8.0.200 of 2001, and possibly further.

- [11] Fixed backspace after typing the space in "ssh "

- [11] Fix macOS linker working, thanks to jj1bdx.

- [11] Added help text for `HELP SHOW`, describing each sub-option.

- [11] Properly define CK_WREFRESH on Linux and macOS.  The original definition dates
  to C-Kermit 5A(190) in 1994 and appears to have just never been updated for these platforms.
  
- [10] Kermit scripts can now run as Unix pipelines

- [10] Added the `VDIRECTORY` command (with V as a one-letter synonym) as a
  shortcut for the DIRECTORY command.

- [10] Added new commands: `GREP /DISPLAY`, `GREP /VERBATIM`, `GREP /MACRO`, and
  `GREP /ARRAY`.

- [10] Added the ckubuildlog utility script to automate creating build report
  entries.

- [10] Added `REMOTE CDUP` and `REMOTE STATUS` server commands for conformity
  with DECSYSTEM-20 Kermit.

- [10] Fixed the `DIRECTORY` command to correctly handle multiple file
  specifications.

- [10] Fixed macOS `COPY /APPEND` to work correctly in ckubuildlog.

- [9] Fixed date parsing to correctly process leap years (e.g. 29-Feb) when
  calculating relative dates.

- [9] Fixed a memory leak in the `CHANGE` command where a dynamic buffer was
  not freed on repeated use.

- [9] Fixed local array persistence in macros where arrays declared local
  persisted after macro return.

- [9] Added substring filtering to the `SHOW FUNCTIONS` command (e.g. SHOW
  FUNCTION pid).

- [9] Reworked Linux makefile target to query ld for library paths dynamically
  rather than using hardcoded system paths.

## Summary of new and changed commands and scripting functions

- [11] `SET COMPATIBILITY`

- [11] `SET TCP ADDRESS-FAMILY` (see [IPv6 documentation](ipv6.md))

- [11] `SET TCP ADDRESS6` (see [IPv6 documentation](ipv6.md))

- [11] `SET FILE SYSTEM-ID`

- [11] `SET PROTOCOL STARTUP-STRING`

- [11] `SET RECEIVE CONFIRM`

- [10] `VDIRECTORY` (synonym `V`)

- [10] `SET VARIABLE-EVALUATION`

- [10] `REMOTE CDUP` and `REMOTE STATUS`

- [10] `GREP` switches `/DISPLAY`, `/VERBATIM`, `/MACRO`, and `/ARRAY`

- [9] `CHANGE`

- [9] `TOUCH /MODTIME`, `/LIST`, and `/SIMULATE`

- [9] `FOPEN /STDIN`

- [9] `SET EXIT MESSAGE` and `SHOW EXIT`

- [9] `SET TEMP-DIRECTORY` and `SHOW TEMP-DIRECTORY`

- [9] Added the `\ffilecompare()` function to compare file contents.

- [9] Added the `\fdayname()` and `\fmonthname()` functions for locale-aware day
  and month names.

- [9] Added the `\fpictureinfo()` function to extract camera and scanner Exif
  metadata (width, height, and date taken).

- [9] Added the `\fnfileinfo()` function to populate an array with file
  metadata.

- [9] Added the `IF BINARY`, `IF TEXT`, and `IF FUNCTION` conditional tests.

## Summary of changed behavior

All items highlighted here are expected to rarely if ever cause an issue in the
wild.

Invoking Kermit as `kermit9` or `kermit10` (copy or symlink `kermit` or `wermit`
to those names) or using `SET COMPATIBILITY` will revert these changed settings
to Kermit 9.0.302 or 10.0 Beta.12 settings as appropriate, restoring most of the
old behavior (which weakens Kermit's security protections).

- [11] The default `SET FILE COLLISION` has changed from `BACKUP` to `REJECT`
  for security reasons.  See the options for `COLLISION` under `HELP SET FILE`
  for more details.  This is the one most likely to be user-visible.

- [11] On systems supporting IPv6, the same approach as telnet(1) on Linux will
  be used: if name resolution returns IPv6 and IPv4 addresses, the IPv6 address
  will be tried first if the system is configured with IPv6 addresses.  If the
  IPv6 address fails to connect, the IPv4 address will be tried next.  The
  previous behavior, which was always IPv4, can be restored with `SET TCP
  ADDRESS-FAMILY IPV4`.

- [11] Previous C-Kermit already used `SET FILE TYPE BINARY`, but unfortunately
  they had transfer-mode set to automatic, which would override the binary file
  type in surprising circumstances, leading to data loss.  The default is now
  `SET TRANSFER-MODE MANUAL`.  Previous behavior can be restored by using `SET
  TRANSFER-MODE AUTOMATIC`.  See discussion above under security and at
  https://bugs.debian.org/1121901 .

- [11] You may still set transfer-mode to be automatic.  If you do, the sets of
  extensions used to help determine text or binary files have been revised with
  modern filetypes, and had typos corrected.  (976a9742)

- [11] When C-Kermit is used as a client, it may connect to an untrusted remote
  system (for instance, a BBS).  By default, the remote Kermit was able to make
  changes to, and retrieve data from, the local system.  This scenario would be
  been used exceptionally rarely for legitimate purposes.  You can type `enable
  ?` to see the list of commands you can re-enable.  See the discussion above
  under CVE-2025-68920.  (9ee170a8 and dc67bddb)
  
- [11] Since C-Kermit now properly reports errors during autodownload, the
  default for `SET TERMINAL AUTODOWNLOAD ERROR` has changed from `STOP` to
  `CONTINUE` as suggested by a comment in 2001.

- [11] A minor change to the handling of paths in received files, allowing
  `/RECURSIVE` to work for received files by default again (with more path
  safeguards).  For more details, see the [permissions
  documentation](permissions.md).  This mostly restores the pre-11.0 behavior
  for recursive receives, but with added safeguards.
  
- [11] Added new receive confirmation, which prompts for confirmation before
  receiving a file with a name that wasn't specifically requested locally.  This
  is governed by a new `SET RECEIVE CONFIRM` option, which defaults to `ON`.
  This does not prompt when running headless (ie, server or iksd).  It will
  generally not trigger on things requested via `GET` since the user is known to
  have requested a file.  `SET RECEIVE CONFIRM OFF` will restore previous
  behavior.
  
- [11] The bugfixes for filenames with embedded spaces or quoting
  characters/braces in commit b06df3874 may cause requests that previously
  failed to now succeed.

- [10] The default `SET VARIABLE-EVALUATION` setting has changed from
  `RECURSIVE` to `SIMPLE` to prevent pathnames containing backslashes from
  being incorrectly evaluated recursively.

- [10] wtmp and syslog logging are no longer enabled by default and must
  be explicitly enabled at compile time.
  
- [10] The `\v(version)` variable and `--version` command-line parameters no
  longer show major.minor.edit, just major.minor.  The edit number is still part
  of the startup herald and the `VERSION` command's banner, and of
  `\v(fullversion)`.

- [9] The `MOVE` command was changed to be a synonym for `RENAME` by default
  (previous behavior can be restored with compile-time -DOLDMOVE).

- [9] Default command prompt on Unix now collapses the home directory path
  prefix to `~/`.

- [9] The `SET TELNET WAIT` setting is no longer silently overridden to ON
  by Telnet option negotiations.

- [9] Removed the undocumented `ok` keyword as an alias for `SUCCESS` in IF
  statements.

## C-Kermit 11.0.506 updates since 11.0.505

- Skip FTP tests when Kermit is built with -DNOFTP, as the Gentoo package does.

- Address macOS linker warning.  Patch from jj1bdx.

- Added help text for `HELP SHOW`, describing each sub-option.

- Properly define CK_WREFRESH on Linux and macOS.  The original definition dates
  to C-Kermit 5A(190) in 1994 and appears to have just never been updated for these platforms.

- [security] Added new receive confirmation, which prompts for confirmation
  before receiving a file with a name that wasn't specifically requested
  locally.  This is governed by a new `SET RECEIVE CONFIRM` option, which
  defaults to `ON`.  This does not prompt when running headless (ie, server or
  iksd).

- C-Kermit now is fully able to process filenames with embedded spaces due to numerous bugfixes in commit b06df3874.  Among them:

  - You can now use `GET` to retrieve a file whose name has embedded spaces
    (previously you could only `SEND` such a file).

  - `MGET` had bugs around quoting that inadvertently would strip necessary quote characters.

  - The Kermit Protocol treats a space as a delimeter between filenames, unless
    it is enclosed in braces.  The C-Kermit client accepts both double quotes
    and braces as quoting characters.  The client now will properly quote all
    filenames containing spaces with braces when sent to the server, regardless
    of which scheme the user selected.

  - Several `REMOTE` commands were broken with filenames with embedded spaces or
    escaped delimiters.

  - Numerous bugs relating to escaping of embedded quote/brace characters as
    part of filenames were fixed.

  - `GET` and `SEND` used inconsistent quoting rules.

- Added new document about [filenames with spaces, wildcards, and escaping](spaces-wildcards.md) 

- Introduced compatibility tests that test the current release
  against gkermit, E-Kermit (eksw), and the last C-Kermit full release prior
  to 11.0 (9.0.302 from 2011).

- Fixed a packet size negotiation bug that manifest itself in talking to
  E-Kermit (eksw).  The bug was introduced in C-Kermit 9.0.305 of 2021-11-16.

- `SET COMPATIBILITY 9` and `SET COMPATIBILITY 10` to easily change
  settings to maximize compatibility with C-Kermit 9.0.302 and 10.0 Beta.12,
  respectively.  This restores previous behavior, which weakens Kermit's
  security posture.  These settings can also be applied at startup by invoking
  Kermit as `kermit9` or `kermit10`.
  
# C-Kermit 11.0.505

- Now support OpenSSL v4.0.  Support for older OpenSSL remains also.  CI is
  currently building with 3.5.

- Added new `SHOW INTERFACES` command, which shows the interfaces and IP
  addresses available on the local machine.  Useful when establishing
  a connection across a local LAN.

- Enhance support for IPv6 link-local addresses.  Together with
  `SHOW INTERFACES`, this helps establish connections over even ad-hoc wifi
  where there is no DHCP.

- Fixed two issues compiling with -DNOLOGIN, dating back to the year 2000.
  These were discovered by running the test suite using the Gentoo build's
  options.

  1. `--unbuffered`, `--version`, etc. were improperly not recognized due to
     a mismatch with ifdef/else/endif

  2. The permissions for `MKDIR` and `CD` were sometimes not enforced for
     similar reasons.

- Fixed compilation errors with Kerberos 5 on Linux and NetBSD.
  Note: Kerberos is not currently exercised by the test suite, so you should
  consider this support less proven than the rest of the system.

# C-Kermit 11.0 announcement (11.0.504)

This was the quieter launch of C-Kermit 11.0.  A blog post and more public
announcement will happen with 11.0.506, so the text below will be revised and
updated for that release.

## Summary

C-Kermit 11 is a major new release, the first non-beta since the last 9.x
release in 2011.  It represents a significant effort to modernize and improve the
C-Kermit codebase.

Since all C-Kermit 10.x releases were betas, some people may be upgrading from
9.x and others from 10.x.  Since some changes were labeled as "9.x DEV" or
various alphas, but also never released, I indicate in which version a change
was made with "9", "10", and "11" tags accordingly.  Please see the
[history](https://www.openkermit.org/history) and
[FAQ](https://www.openkermit.org/faq) pages for more information on the
relationship between the different Kermit versions.

## Major Architectural Improvements

- [11] Introduced C-based unit tests and a Python-based regression test suite.
  Together, these test suites have been responsible for identifying nearly all
  of the bug fixes in the v11 release as noted below.  Timing analysis of the
  test suite also led to most of the performance fixes.  Running the tests under
  load led to the discovery and fix of numerous race conditions.
  - [11] Also introduced compatibility tests that test the current release
    against gkermit, E-Kermit (eksw), and the last C-Kermit full release prior
    to 11.0 (9.0.302 from 2011).

- [11] Added CI.  All changes now are validated on Linux, MacOS, FreeBSD, and
  NetBSD using the above test suites.  Approximately 1000 test cases are being
  run.
  
- [11] Binaries for multiple platforms are automatically built from CI at
  release time.

- [10] Codebase-wide modernization to support ANSI C and function prototyping,
  satisfying strict requirements in newer compilers while retaining backward
  compatibility with pre-ANSI systems.

## New Features

- [11] C-Kermit's TCP stack now supports IPv6, while degrading gracefully to
  IPv4 on hosts that don't have IPv6 connectivity, or whose system libraries
  don't support IPv6.  For more, see the new 
  [IPv6 in C-Kermit document](ipv6.md).
    
- [11] There's now a tool that will extract all the help text from C-Kermit and
  write a nice Markdown file that acts as an up-to-date command reference for
  your specific platform.  A generated version of this can be found at 
  [HELP reference](help-reference.md).

- [9] Android platform support, including NDK builds and a vanity herald.

- [9] Locale support for dates, times, and error messages (with Spanish
  and German translations), controllable via the --nolocale command-line
  option and K_NOLOCALE environment variable.

- [9] A new `CHANGE` command to search and replace strings in files, using
  standard directory and touch file-selection switches.

- [9] A new `FOPEN /STDIN` command to allow Kermit scripts to read standard
  input from a pipe.

## Major Improvements

- [11] External protocol (Zmodem and the like) support has seen significant
  performance increases in many cases, due to elimination of inefficiencies in
  the pty code that supports it.

- [11] Codebase-wide dead code elimination and general simplification.  This
  removes code that was never used in any build on any platform, and makes code
  auditing and analysis easier.  Despite many new features, the C-Kermit 11
  codebase (excluding comments) is about 2600 lines smaller than the last 10.x
  beta!

- [11] Now compatible with OpenSSL 3.x. The OpenSSL runtime version check was
  relaxed to allow minor version updates, and support was added for compiling
  with `NO_OPENSSL_VERSION_CHECK` to disable the compatibility check.
  
- [11] Static binaries are now supported on Linux, with both glibc and musl
  libc.  Official musl static binaries for Linux on amd64 and arm64 are built
  for each release.

- [10] Support for serial-port speeds up to 4,000,000 bps.

- [9] Modernized FTP/SSL and Telnet/SSL negotiations to default to TLS 1.0+
  and disable SSLv3 by default (POODLE mitigation), adding the use-ssl-v3
  bug option for fallback compatibility.

## Major Bugfixes

- [11] Certain packet sizes on the boundary between small and extended packet sizes
  could lead to a transfer being hung on all platforms.  Fixed the bug and
  added extensive tests around this scenario.
  
- [11] Fixed a data corruption bug that occurred during packet size
  renegotiation due to improperly using strlen() to determine the size of binary
  data that may contain NULL bytes. (b58e0336)  This issue was only observed by
  running the test suite on NetBSD, but the code pattern indicates it could
  occur on any platform given the correct circumstances.

- [11] Numerous pty issues were remedied on MacOS; some had been going back decades.
  In particular, MacOS FIONREAD appears to be unreliable, and assuming it to be
  reliable led to some hard-to-track-down hangs.
  
- [11] Recursive transfer fixed on MacOS.

- [11] Fixed filename collision (overwrite) detection on MacOS.

- [11] Fixed a packet size negotiation bug that manifest itself in talking to
  E-Kermit (eksw).  The bug was introduced in C-Kermit 9.0.305 of 2021-11-16.

- [11] Make sure timeval usec is initialized.  It was used uninitialized, leading to
  undefined behavior that could corrupt the modification date by many seconds or
  minutes.

- [11] Added new `SET PROTOCOL STARTUP-STRING` to allow easy inhibiting of all
  startup strings where necessary.

- [11] When transferring multiple files in text mode, the system would detect Unicode
  encoding on only the first, and blindly apply that assumption to all the rest.

- [11] Fixed a bug where raw TLS connections could hang waiting for Telnet
  negotiation.

- [11] Fixed a bug in ttopen where pipe connections did not execute the
  configured command.
  
- [11] Found and fixed numerous buffer overruns and memory leaks.

- [11] Tracked down a pseudoterminal failure on NetBSD.  It turns out to be a
  kernel bug in which the kernel can sometimes return a value indicating more
  data was successfully written down the pty than actually was, causing loss of
  bytes of data.  When in default mode, C-Kermit detects this and automatically
  shrinks its packet size to compensate!  (This is what exposed the strlen() bug
  mentioned elsewhere.)  When in streaming mode, this is fatal to the transfer,
  and was detected when I added streaming mode tests.  The workaround is to run
  `sysctl -w kern.tty.qsize=65536` or to set it in `/etc/sysctl.conf`; a comment
  in that file implies this issue is known already.

- [11] Several other pty issues were also remedied on NetBSD. 

- [11] Fix IKSD server refusing all connections when built with SSL support but not
  configured with an SSL cert.  This had been a long-standing C-Kermit bug.
  
- [10] Fixed the `TOUCH` command, which had been nonfunctional.

- [9] Fixed a crash on 64-bit platforms (such as OpenBSD sparc64) during file
  transfers due to conflicting int/long declarations.

- [9] Fixed a crash in Open Watcom Windows builds caused by inconsistent
  extern declarations of the vmode variable.

- [9] Fixed S-Expression processor core dumps when given invalid operators.

- [9] Fixed the `DIRECTORY /BRIEF` command to correctly honor the `/EXCEPT`
  switch.

- [9] Fixed a bug in zchko() that caused FTP GET commands to segment fault on
  systems with NOUUCP defined.

- [9] Added CK_64BIT support, significantly increasing command, macro,
  variable, and packet buffer sizes on 64-bit architectures.

## Security and Reliability Improvements

- [11] More durable privilege dropping (priv_chk)

- [11] Elimination of a number of unbounded writes to buffers

- [11] Disable auto transfer mode by default, which switched between text and
  binary transfer modes based on a heuristic.  For full details, see commit
  cdd2e257e and the discussion at https://bugs.debian.org/1121901 .  The
  heuristic for attempting to guess the type of files is now disabled to avoid
  data corruption, letting Kermit always follow the user's expressed transfer
  type wishes by default.

- [11] Fix CVE-2025-68920, insecure defaults that previously would let a
  malicious remote kermit server perform actions on your local workstation.
  Further discussion in commit 9ee170a85 and full details at
  http://bugs.debian.org/1123025 .  See more details under changed behavior
  below for how to adjust this in the rare event you might need to.

- [11] Switch the default `SET FILE COLLISION` from BACKUP to REJECT.  The
  previous default would let a malicious remote overwrite sensitive local files
  (eg, `.bashrc`) which could lead to a security issue.

- [11] Fixed a bug where the CLEAR APC command could bypass APC safety checks or
  cause the parser to hang.
  
- [11] Disabled MAIL and PRINT handling by default (dc67bddb), and hardened the
  handling of them to prevent shell injection attacks (23ec7368).

- [10] Changed the default value of SET VARIABLE-EVALUATION to SIMPLE
  (non-recursive) to avoid evaluation issues with backslashes in pathnames on
  Windows and OS/2.

- [9] Fixed a bug where TOUCH /MODTIME could destroy existing files under
  certain conditions.

See the section below on changed behavior for highlights on the impact of
changed defaults.  This impact is expected to be rare.

## Additional improvements and bugfixes

- [11] Fixed an unhandled exception warning on NetBSD

- [11] Prevent Kermit from killing all of the user's processes in certain edge
  cases where it may try to kill PID -1.

- [11] Correct use of ziperm vs. ziperms for non-CK_PERMS platforms.  Appears to
  have been latent since C-Kermit 7.0 in 2000.

- [11] Updated the list of text and binary extensions to have more modern filetypes,
  and fixed typos in the old list.
  
- [11] Improve transfer error reporting.  Previously, errors might be reported
  on the transfer screen, then immediately wiped when switching back to the
  regular screen.  Now report them on the regular screen also.  A comment from
  2001 suggested that after this work was done, a failed autodownload could drop
  the user back into CONNECT mode just like a successful one did.  So, changed
  the default for `SET TERMINAL AUTODOWNLOAD ERROR` from `STOP` to `CONTINUE`.

- [11] Added new `SET FILE SYSTEM-ID` setting, which facilitates using C-Kermit
  to translate files between different platform conventions even when used on a
  single platform.  It also facilitates testing these functions.

- [11] Allow pseudoterminals to work even when Kermit itself is not called from
  a controlling terminal.

- [11] Fixed Unicode text detection for very small files

- [11] Several improvements to help text

- [11] Fixed japanese-roman character set

- [10, 11] OS/2 compatibility improvements

- [11] Fixed command prompt formatting in anonymous IKSD when the home
  directory is root (/).

- [11] Fixed Gentoo builds after the ncurses tinfo library split.

- [11] Fixed SET HOST to work properly after an ssh command had been issued
  earlier in the same session. (10eb1924)

- [11] Fixed several issues where EINTR from read() could cause C-Kermit to
  improperly close a connection.  In one case, signals such as SIGWINCH at
  particular times triggered this issue on Linux; in another, the test suite
  caused it on NetBSD.
  
- [11] Coincidentally, fixed a bug in winchh(), which is the handler for
  SIGWINCH, in which is fails to restore errno before returning, so an error
  from a call it makes can lead the interrupted code to believe an error other
  than EINTR occurred.
  
- [11] Fixed a bug in SSL network read that was triggered by ZModem over SSL,
  which resulted in exceptionally slow performance in certain circumstances
  
- [11] Fixed an issue with the telnet protocol handling of a NULL after a bare
  CR
  
- [11] Fixed build issues on OpenBSD

- [11] Fixed a bug on OpenBSD that could cause ZModem transfers to be truncated
  under heavy load

- [11] Fixed a race, most prominently manifested on OpenBSD, where C-Kermit may
  attempt to kill a child, but the signal arrives after that PID has been
  assigned a new process, causing unintended side-effects.  Other platforms
  don't seem to recycle PIDs as fast.
  
- [11] Now give an accurate error message instead of "write access to UUCP
  lockfile" about errors that had nothing to do with the lockfile
  
- [11] Correctly build the BSD binaries without SSL

- [11] Fixing recursive receive, which led to a deep dive into C-Kermit permissions.
  See the new [C-Kermit permissions documentation](permissions.md).

- [11] Added a workaround to the client to deal with old broken IKSD servers.

- [11] Fixed a telnet negotiation race related to EINTR and select

- [11] Fixed Unicode BOM detection issue that may manifest on big-endian
  architectures.

- [11] Switched all BSDs to use base system OpenSSL instead of
  separately-installed OpenSSL
  
- [11] Fixed backspace after typing the space in "ssh "
  
- [10] Kermit scripts can now run as Unix pipelines

- [10] Added the `VDIRECTORY` command (with V as a one-letter synonym) as a
  shortcut for the DIRECTORY command.

- [10] Added new commands: `GREP /DISPLAY`, `GREP /VERBATIM`, `GREP /MACRO`, and
  `GREP /ARRAY`.

- [10] Added the ckubuildlog utility script to automate creating build report
  entries.

- [10] Added `REMOTE CDUP` and `REMOTE STATUS` server commands for conformity
  with DECSYSTEM-20 Kermit.

- [10] Fixed the `DIRECTORY` command to correctly handle multiple file
  specifications.

- [10] Fixed macOS `COPY /APPEND` to work correctly in ckubuildlog.

- [9] Fixed date parsing to correctly process leap years (e.g. 29-Feb) when
  calculating relative dates.

- [9] Fixed a memory leak in the `CHANGE` command where a dynamic buffer was
  not freed on repeated use.

- [9] Fixed local array persistence in macros where arrays declared local
  persisted after macro return.

- [9] Added substring filtering to the `SHOW FUNCTIONS` command (e.g. SHOW
  FUNCTION pid).

- [9] Reworked Linux makefile target to query ld for library paths dynamically
  rather than using hardcoded system paths.

## Summary of new and changed commands and scripting functions

- [11] `SET TCP ADDRESS-FAMILY` (see [IPv6 documentation](ipv6.md))

- [11] `SET TCP ADDRESS6` (see [IPv6 documentation](ipv6.md))

- [11] `SET FILE SYSTEM-ID`

- [11] `SET PROTOCOL STARTUP-STRING`

- [10] `VDIRECTORY` (synonym `V`)

- [10] `SET VARIABLE-EVALUATION`

- [10] `REMOTE CDUP` and `REMOTE STATUS`

- [10] `GREP` switches `/DISPLAY`, `/VERBATIM`, `/MACRO`, and `/ARRAY`

- [9] `CHANGE`

- [9] `TOUCH /MODTIME`, `/LIST`, and `/SIMULATE`

- [9] `FOPEN /STDIN`

- [9] `SET EXIT MESSAGE` and `SHOW EXIT`

- [9] `SET TEMP-DIRECTORY` and `SHOW TEMP-DIRECTORY`

- [9] Added the `\ffilecompare()` function to compare file contents.

- [9] Added the `\fdayname()` and `\fmonthname()` functions for locale-aware day
  and month names.

- [9] Added the `\fpictureinfo()` function to extract camera and scanner Exif
  metadata (width, height, and date taken).

- [9] Added the `\fnfileinfo()` function to populate an array with file
  metadata.

- [9] Added the `IF BINARY`, `IF TEXT`, and `IF FUNCTION` conditional tests.

## Summary of changed behavior

All items highlighted here are expected to rarely if ever cause an issue in the
wild.

- [11] The default `SET FILE COLLISION` has changed from `BACKUP` to `REJECT`
  for security reasons.  See the options for `COLLISION` under `HELP SET FILE`
  for more details.  This is the one most likely to be user-visible.

- [11] On systems supporting IPv6, the same approach as telnet(1) on Linux will
  be used: if name resolution returns IPv6 and IPv4 addresses, the IPv6 address
  will be tried first if the system is configured with IPv6 addresses.  If the
  IPv6 address fails to connect, the IPv4 address will be tried next.  The
  previous behavior, which was always IPv4, can be restored with `SET TCP
  ADDRESS-FAMILY IPV4`.

- [11] Previous C-Kermit already used `SET FILE TYPE BINARY`, but unfortunately
  they had transfer-mode set to automatic, which would override the binary file
  type in surprising circumstances, leading to data loss.  The default is now
  `SET TRANSFER-MODE MANUAL`.  Previous behavior can be restored by using `SET
  TRANSFER-MODE AUTOMATIC`.  See discussion above under security and at
  https://bugs.debian.org/1121901 .

- [11] You may still set transfer-mode to be automatic.  If you do, the sets of
  extensions used to help determine text or binary files have been revised with
  modern filetypes, and had typos corrected.  (976a9742)

- [11] When C-Kermit is used as a client, it may connect to an untrusted remote
  system (for instance, a BBS).  By default, the remote Kermit was able to make
  changes to, and retrieve data from, the local system.  This scenario would be
  been used exceptionally rarely for legitimate purposes.  You can type `enable
  ?` to see the list of commands you can re-enable.  See the discussion above
  under CVE-2025-68920.  (9ee170a8 and dc67bddb)
  
- [11] Since C-Kermit now properly reports errors during autodownload, the
  default for `SET TERMINAL AUTODOWNLOAD ERROR` has changed from `STOP` to
  `CONTINUE` as suggested by a comment in 2001.

- A minor change to the handling of paths in received files, allowing
  `/RECURSIVE` to work for received files by default again (with more path
  safeguards).  For more details, see the [permissions
  documentation](permissions.md).  This mostly restores the pre-11.0 behavior
  for recursive receives, but with added safeguards.

- [10] The default `SET VARIABLE-EVALUATION` setting has changed from
  `RECURSIVE` to `SIMPLE` to prevent pathnames containing backslashes from
  being incorrectly evaluated recursively.

- [10] wtmp and syslog logging are no longer enabled by default and must
  be explicitly enabled at compile time.
  
- [10] The `\v(version)` variable and `--version` command-line parameters no
  longer show major.minor.edit, just major.minor.  The edit number is still part
  of the startup herald and the `VERSION` command's banner, and of
  `\v(fullversion)`.

- [9] The `MOVE` command was changed to be a synonym for `RENAME` by default
  (previous behavior can be restored with compile-time -DOLDMOVE).

- [9] Default command prompt on Unix now collapses the home directory path
  prefix to `~/`.

- [9] The `SET TELNET WAIT` setting is no longer silently overridden to ON
  by Telnet option negotiations.

- [9] Removed the undocumented `ok` keyword as an alias for `SUCCESS` in IF
  statements.

# Older changes

You can find them in [changelog-old.txt](changelog-old.txt), the git history of
this project, or https://kermitproject.org/ckupdates.html .

For even older information, you can consult the [C-Kermit 9.0 Update
Notes](https://www.kermitproject.org/ckermit90.html).

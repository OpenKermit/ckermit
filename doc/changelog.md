# OpenKermit C-Kermit Changelog

# C-Kermit 11.1.515 (NOT YET RELEASED)

## Summary

C-Kermit 11.1 is a correctness and security release.  As part of preparing this
release, over 900 compiler warnings were eliminated and a code review was
performed.

Where appropriate, descriptions of bugfixes identify the major C-Kermit version
in which the bug was introduced and are prefixed with a tag (such as "[9]",
indicating the bug was introduced in C-Kermit 9).  History of C-Kermit only goes
back to version 4, so bugs tagged as "[4]" may actually go back further.

Most bugfixes are accompanied by the introduction of new regression tests
covering their situations.

## Major Architectural Improvements

- Eliminated over 900 `-Wconversion` warnings.  Each conversion between integer
  types of different widths or signedness is now explicit or removed.  This
  work identified numerous bugs, which are among those listed below.

- C-Kermit now needs OpenSSL 1.0.2 or later, or LibreSSL, for SSL and TLS.
  ck_ssl.h stops the build with an older OpenSSL.  The code for OpenSSL 0.9.x,
  1.0.0, and 1.0.1, is removed.  OpenSSL 1.0.2 provides library functions that
  replace buggy custom code in C-Kermit.

## New Features

- `SET AUTHENTICATION SSL MINIMUM-VERSION { SSL3.0, TLS1.0, TLS1.1,
  TLS1.2, TLS1.3 }` sets the lowest protocol version that Telnet, raw
  SSL/TLS, IKSD, HTTPS and FTP connections accept.  The default is TLS1.2.
  OpenSSL 3 also needs `@SECLEVEL=0` in the cipher list for a version
  older than TLS 1.2.  SHOW AUTHENTICATION displays the setting.

- `SET FTP TLS-FALLBACK { ON, OFF }` selects what FTP OPEN does when the
  server accepts AUTH TLS or AUTH SSL and the TLS session fails.  OFF is
  the default and closes the connection.  ON reconnects and tries the next
  authentication type.  If none succeeds, ON logs in without encryption.
  Releases before 11.1 behaved as ON does.

- `SET FTP TRUST-PASV-ADDRESS { ON, OFF }` selects the address of a
  passive-mode data connection.  OFF, the default, connects to the
  control connection's address.  ON connects to the address in the PASV
  reply, as releases before 11.1 did.  It suits a server that names a
  different host for data.

## Major Improvements

- [8, 9] The default file-list string space on 64-bit builds is now 32MB
  instead of 2GB.  Wildcard expansion allocates this space on first use.  Lazy
  allocation on modern operating systems often hid the 2GB allocation.  The
  102,400-name list limit leaves an average of over 300 bytes per name.  A
  larger expansion fails with "?String space exhausted".  `SET FILE
  STRINGSPACE` raises the limit, and `SHOW FILE` displays it.  `SET FILE
  STRINGSPACE` with a value of 1024 or less also failed.  Commit 0fd869b4
  introduced the two-billion default in C-Kermit 9.0.302 of 2011.  Commit
  c88d9b85 introduced the STRINGSPACE bug in C-Kermit 8.0.200 of 2001.

## Major Bugfixes

- [6, 7, 8, 11] Files of 2GB or more failed in several places.  HTTP PUT and
  POST sent a wrong Content-Length.  `kermit -s` and command-line FTP `-p`
  rejected 2-4 GiB files.  REMOTE DELETE skipped 2-4 GiB files, and DELETE
  reported a wrong bytes-freed total.  WAIT FILE treated a file of 2^32-1 bytes
  as deleted.  HTTP Content-Length values over 2GB, or negative or empty ones,
  became 0, so a large download produced an empty file and reported success.
  Commit 4b5eddea introduced the REMOTE DELETE and DELETE bugs in C-Kermit
  6.0.192 of 1996.  Commit d0f8b1da introduced the HTTP PUT/POST and WAIT bugs
  in C-Kermit 7.0.197 of 2000.  Commit c88d9b85 introduced the `-s`, FTP `-p`,
  and HTTP Content-Length type bugs in C-Kermit 8.0.200 of 2001.  Commit
  42cfd07f introduced the clamp to 0 in C-Kermit 11.0.501 of 2026.

- [8] FTP GET in binary mode reported success when the local file could
  not be written, such as on a full disk, and left a truncated file.  In
  text mode the failure came only from the server's reply, and SET FILE
  INCOMPLETE AUTO kept the partial file.  GET now stops at the first
  failed write and fails.  Bug was introduced in commit c88d9b85, in
  C-Kermit 8.0.200 of 2001.

- [11] GET or RECEIVE with an existing directory as the destination (e.g. `get
  foo.txt /some/dir/`) failed with "?Syntax error".  A regression from the
  -Wshadow work, present in 11.0.511 through 11.0.514.  Bug was introduced in
  commit 9be7054f in C-Kermit 11.0.511.

- [11] INPUT on a TLS connection failed after one second with an I/O error.
  Bug was introduced in commit 4521c6b6 in C-Kermit 11.0.510 of 2026.

- External protocol transfers (ZMODEM and others):

  - [7] When the child process of SET HOST /PTY or an external protocol could
    not signal that its pty was ready, Kermit reported the connection as
    failed, but the child ran the command anyway.  Kermit also left the pty
    open and did not reap the child.  Bug was introduced in commit d0f8b1da in
    C-Kermit 7.0.197 of 2000.

  - [9] A transfer could be reported as failed with "No files were transferred"
    after it succeeded.  Bug dates from the introduction of ttptycmd() in
    C-Kermit 9.0.302 of 2011.

  - [9] The program's last output could be lost.  Bugs were introduced in
    commit 0fd869b4 in C-Kermit 9.0.302 of 2011.

  - [9] Ctrl-C during a transfer left the protocol program running with its pty
    open, and left the connection non-blocking.  On systems without openpty(),
    it also left SIGCHLD ignored for the rest of the session.  Bugs were
    introduced in commit 0fd869b4 in C-Kermit 9.0.302 of 2011.

  - [9, 11] Fixed a bug relating to buffering external protocol data,
    significantly improving performance.  The code that waited was introduced in
    commit 0fd869b4 in C-Kermit 9.0.302 of 2011.  Commit 04e8275d in C-Kermit
    11.0.501 of 2026 replaced the wait with the 100 ms poll.  Commit ce6628a3 in
    C-Kermit 11.0.509 of 2026 introduced the 2-second stall.

  - [11] On the BSDs, an external protocol over a SET HOST /PTY connection did
    not notice when the connection ended.  Bug was introduced in commit
    dab36d9a in C-Kermit 11.0.501 of 2026.

  - [11] An external protocol over an SSL or TLS connection held each burst of
    incoming data for 2 seconds.  Steady traffic held it until the traffic
    stopped.  lrz 0.13 gave up on the transfer and older versions were slow.
    Bug was introduced in commit 04e8275d in C-Kermit 11.0.501 of 2026.  Bug
    originally reported at
    https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1150880

## Security and Reliability Improvements

C-Kermit 11.1 corrects these security issues.  Most issues tagged "[11]" fall
into one of two categories.  First, tighter security defaults in C-Kermit 11.0
exposed weaknesses in older code.  Second, hardening code added in 11.0 had
gaps.  Few are corrections for security regressions in 11.0, aside from `SET
COMPATIBILITY`.

### File transfer and the server

- [4] A Kermit server ran REMOTE WHO and REMOTE SPACE through the shell with the
  client's text unquoted.  `remote who {x;touch y}` ran a command on the server
  even with DISABLE HOST.  The server now runs who and df without the shell.  A
  Unix server refuses a REMOTE WHO name.  The Unix who command reads its
  argument as a login database file, and the passed username was interpreted as
  a filename.  This appears to have been broken on Unix hosts since the very
  beginning.  A REMOTE SPACE argument must name an existing directory.  A REMOTE
  SPACE directory name with spaces now works.  A command too long for the
  command buffer is refused instead of overflowing it.  Bug dates from C-Kermit
  4C(057) of 1985.

- [4] A Kermit server or receiver now refuses a server command, GET command, or
  file name that decodes to more than its command buffer holds.  Before, repeat
  counts could make such a packet write past the buffer.  This bug was present
  in the oldest extant version of C-Kermit, version 3.0 of 1984.

- [4, 5, 6, 7] The server trusted the field lengths in generic commands,
  Extended GET parameters, attribute packets and REMOTE SET.  A length past the
  data made it read stale buffer contents.  REMOTE SET values were also stored
  without range checks.  REMOTE LOGIN copied a user name of up to 255 bytes
  into a 64-byte stack buffer in builds without BIGBUFOK.  REMOTE CD, COPY and
  RENAME took a last field over 94 characters as empty, so REMOTE CD went to
  the home directory.  Each field is now checked, and a long last field is used
  whole.  The REMOTE CD bug was introduced in commit 16d830ec in C-Kermit
  4F(095) of 1989.  The others were introduced in commits a213649d (5A(188) of
  1992), 609e2f39 (5A(190) of 1994), 4b5eddea (6.0.192 of 1996) and d0f8b1da
  (7.0.197 of 2000).

- [4, 5, 7] Malformed packets were accepted or read past their data.  A packet
  whose data ended with a repeat, control or 8th-bit prefix and no operand was
  decoded with the operand taken from the block check.  A trailing repeat
  prefix wrote 224 copies of a block check byte to the file.  Such a packet now
  ends the transfer with the error "Malformed packet data".  A packet whose
  length was shorter than its block check passed with a negative data length.
  With an extended header of length 0, the header check served as the block
  check, so a packet of any type was accepted.  Such a packet is now refused as
  a bad length.  A malformed packet could leave a sequence number outside 0-63
  that was later used as a table index.  rpack() computed the block check of a
  packet that claimed more bytes than arrived over unwritten buffer space.
  spar() read past the Send-Init parameters it was given.  Bugs were introduced
  in commits f16b451f (4C(057) of 1985), 9438f560 (4E(072) of 1989), a213649d
  (5A(188) of 1992) and d0f8b1da (7.0.197 of 2000).

- [5] Attribute handling read and wrote outside its buffers.  A receiver wrote
  one byte past its 21-byte attribute reply buffer for each refused attribute
  beyond the 20th.  A sender could refuse many attributes in one packet and
  overwrite static data.  The reply now keeps the first 20 reasons.  A sender
  read one entry past its table of refusal reasons when the receiver refused a
  file with reason "A".  The transaction log and file transfer display showed a
  stray string such as "January", or Kermit could crash.  The reason is now
  "unknown".  A received file name of only blanks or control characters made
  the receiver read one byte before its name buffer.  The file is still stored
  as NONAME.  Bugs were introduced in commit a213649d in C-Kermit 5A(188) of
  1992.

- [6] With HOST disabled, a Kermit server still ran shell commands for
  REMOTE QUERY.  `remote query kermit command(...)` called `\fcommand()`,
  and `\fexecute()` could reach RUN.  The query now runs with PUSH refused
  unless HOST is enabled.  Bug was introduced in C-Kermit 6.0.192 of 1996.
  That release first allowed functions in REMOTE QUERY.

- [6, (11)] A sender could have a file appended to any existing file in the
  receive directory by marking it RESEND.  This bypassed FILE COLLISION
  REJECT and RECEIVE CONFIRM, with no prompt.  The receiver now refuses a
  RESEND unless its collision setting allows it or it asked for a REGET.
  The append path was introduced in commit 4b5eddea in C-Kermit 6.0.192
  of 1996.
  
  C-Kermit 11.0.501 (9ee170a8) made REJECT the default which, because of this
  bug in C-Kermit 6.0.192, didn't achieve the desired hardening effect for
  appends.  The same happened with RECEIVE CONFIRM was added in C-Kermit
  11.0.506 (b06df387), both in 2026.

- [7] A receiver gave a file the setuid, setgid and sticky bits when a Unix
  sender's permissions held them.  A sender could leave a setuid program in the
  receiver's directory.  The receiver now keeps only the read, write, and
  execute bits.  A C-Kermit sender sends no other bits, so this change is
  unlikely to cause a real-world regression.  A permission string of more than
  10 digits also overflowed.  An attribute packet with permissions but no date
  set the file mode from uninitialized memory.  Bugs were introduced in commit
  d0f8b1da in C-Kermit 7.0.197 of 2000.

- [7] A server with DISABLE DELETE still deleted each file it sent for GET
  /RECOVER /DELETE, and for GET /RECOVER /RECURSIVE /DELETE.  The client sends
  these as an Extended GET, and the server did not check DISABLE DELETE for it.
  They are now refused with "Deleting files is disabled", as GET /DELETE is.
  Bug was introduced in commit d0f8b1da in C-Kermit 7.0.197 of 2000.

- [8, 11] ENABLE and DISABLE with LOCAL, REMOTE or BOTH set the whole
  value.  With the 11.0 default of REMOTE only, `disable cd remote`
  enabled CD for the local side.  APC from the remote host uses that side.
  Each now changes only its half.  The assignment was introduced in commit
  c88d9b85 in C-Kermit 8.0.200 of 2001.  It became harmful when commits
  9ee170a8 and dc67bddb changed the defaults in C-Kermit 11.0.501 of
  2026.

- [11] RECEIVE CONFIRM did not prompt for files a recursive GET placed outside
  the requested directory, such as `.ssh/authorized_keys` from `get /recursive
  reports/*`.  It did prompt for files the user had named by path or as-name.
  Names are now matched by basename, the as-name counts, and the root is the
  requested directory.  Bugs were introduced in commit b06df387 in C-Kermit
  11.0.506 of 2026.

- [11] SET COMPATIBILITY 9 and 10, and `kermit9` and `kermit10`, set RECEIVE
  PATHNAMES ABSOLUTE instead of C-Kermit 9's AUTO, and could re-enable
  functions that ENABLE refuses or that DISABLE ENABLE had locked.  A later SET
  PROTOCOL restored the earlier collision and pathname settings.  HELP SET
  COMPATIBILITY now states exactly what each mode changes.  Modes 9 and 10 make
  the same changes: FILE COLLISION BACKUP, TRANSFER MODE AUTOMATIC, TERMINAL
  AUTODOWNLOAD ERROR STOP, RECEIVE CONFIRM OFF, TCP ADDRESS-FAMILY IPV4,
  RECEIVE PATHNAMES AUTO, and the listed ENABLE settings for both sides.
  Neither restores the C-Kermit 9 prompt, `SET TELNET WAIT`, or `SET TCP
  CONNECT-TIMEOUT`.  The CONNECT-TIMEOUT default has been 30 seconds since
  11.0.510.  Bugs were introduced in commits f8e56a89 and 1260091f in C-Kermit
  11.0.506 of 2026.

- HELP ENABLE, HELP DISABLE, HELP REMOTE QUERY, HELP REMOTE ASSIGN and
  `doc/permissions.md` now state that REMOTE QUERY and REMOTE ASSIGN
  together let a client run any Kermit command on a server, and how to
  restrict that.  The permissions documents now list IKSD, started by
  inetd with `-A`, as governed by REMOTE.

### FTP and HTTP

- [8] FTP MGET /RECURSIVE wrote server names such as `../../x` or
  absolute paths as local files.  It now skips them.  Bug was introduced
  in commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [8, 11] The FTP PASV reply was used as given, so a server could direct the
  data connection to any host.  The data connection now goes to the control
  connection's address.  Through an HTTP proxy, it goes to the server named
  in FTP OPEN.  `SET FTP TRUST-PASV-ADDRESS ON` restores the old behavior.
  An EPSV port above 65535 wrapped.  The PASV bug was
  introduced in commit c88d9b85 in C-Kermit 8.0.200 of 2001.  The EPSV bug was
  introduced in commit 36668be5 in C-Kermit 11.0.501 of 2026.

- [8] A malicious FTP server overflowed a static buffer in the client with a
  long PBSZ reply after AUTH TLS.  Builds with SSL/TLS reached this in the
  default configuration.  In GSSAPI, Kerberos 4, and SRP builds, a long ADAT
  reply did the same, and a long protected (6xx) reply overflowed a stack
  buffer.  Each copy now stops at the end of its buffer.  Bugs were introduced
  in commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [8] In GSSAPI, Kerberos 4, and SRP builds, a PBSZ size too small for the
  protection overhead let a protected PUT overflow its buffer.  A text-mode PUT
  larger than 8 KiB stored a NUL one byte past the buffer, and the base64
  decoder wrote one byte past its output.  These bugs were also introduced in
  commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [8] MLSD file names that contained '=' were misread, and a line of facts
  with no name was taken as a file named after its last fact.  With
  /RECURSIVE a nameless directory line crashed the client.  Bugs were
  introduced in commit 7b4ce026 in C-Kermit 8.0.206 of 2002.

- [8] A long HTTP chunk extension looked like the last chunk, so the body
  was cut short with success, and a malformed chunk size ended the body
  the same way.  A Last-Modified date that did not parse crashed HTTP GET.
  Both date from commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [8] FTP GET /MOVE-TO evaluates its destination again after each file.  A
  destination that expanded past the length of a path overflowed a stack
  buffer, and Kermit crashed.  The destination is now cut at the length of a
  path, and the move fails.  Bug was introduced in commit c88d9b85 in C-Kermit
  8.0.200 of 2001.

- [9] FTP USER with no password and no saved password sent the server
  text left by an earlier command, such as a GREP pattern, as the
  password.  It now prompts for the password.  Bug was introduced in
  commit 0fd869b4 in C-Kermit 9.0.302 of 2011.

### Connections, Telnet and TLS

- [5, 7, 8] The debug log recorded passwords.  It now records their lengths.
  HTTP Basic credentials stayed in memory after use, and a user:password over
  127 bytes was truncated without notice.  Bugs were introduced in commits
  a213649d (5A(188) of 1992), 609e2f39 (5A(190) of 1994), d0f8b1da (7.0.197 of
  2000) and 7b4ce026 (8.0.206 of 2002).

- [5, 7, 8] Buffer overflows from local input: the RLOGIN startup data with a
  long USER, an HTTP proxy name filling its buffer, a long HTTP proxy name in
  FTP, a CONNECT-mode backslash code of 10 or more characters (crashed), and
  MGET with a pattern directory of 4096 bytes or more.  Added regression tests
  to cover these bugs, but the RLOGIN and proxy tests detect the overflow only
  under AddressSanitizer.  Bugs were introduced in commit 609e2f39 in C-Kermit
  5A(190) of 1994 (CONNECT), commit d0f8b1da in C-Kermit 7.0.197 of 2000
  (RLOGIN), and commit c88d9b85 in C-Kermit 8.0.200 of 2001 (proxy, MGET).

- [6, 7, 8, 9, 11] With 1024 or more descriptors open, connections and
  reads wrote past an fd_set on the stack.  The connect bug was introduced
  in commit a32e1321 in C-Kermit 11.0.510 of 2026.  The other waits date
  from commits 4b5eddea, d0f8b1da, c88d9b85 and 0fd869b4 in C-Kermit
  6.0.192 of 1996 through 9.0.302 of 2011.

- [6, 7] A malicious Telnet server could overflow a stack buffer and a heap
  buffer with a crafted NEW-ENVIRON SEND request during connection negotiation.
  The stack overflow was introduced in commit 4b5eddea in C-Kermit 6.0.192 of
  1996.  The heap overflow was introduced in commit d0f8b1da in C-Kermit
  7.0.197 of 2000.

- [7] A malicious Telnet server could write past a static buffer by sending
  4095 or more bytes during connection negotiation.  Kermit keeps data that
  arrives while it waits for negotiation replies in a 4096-byte buffer.  One
  wait could fill the buffer, and the next wait stored a byte before it checked
  for room.  The wait now reads nothing when the buffer is full.  Bug was
  introduced in commit d0f8b1da in C-Kermit 7.0.197 of 2000.

- [7] An IKSD that accepted a client certificate for a user, and then
  refused that user (for instance from the forbidden-user file), prompted
  for a login with the certificate still accepted.  Any other user then
  logged in with any password.  The IKSD now drops the certificate login
  when the automatic login fails, and skips the password only for the
  user that authentication validated.  Bug was introduced in commit
  d0f8b1da in C-Kermit 7.0.197 of 2000.

- [7, 8] Malformed Telnet subnegotiations from a peer read or wrote past
  buffers.  With the debug log or SET TELNET DEBUG on, an ENCRYPTION
  subnegotiation could crash Kermit.  The decoder for the log looked up each
  encryption type in a table of 12 with no bound, and wrote one name per byte
  into a 16-entry array on the stack.  This happened even when ENCRYPTION was
  not negotiated.  Unknown types now show in hex.  A Telnet server or IKSD took
  the screen size from a NAWS subnegotiation with fewer than four bytes.  It
  read the IAC SE and bytes left from an earlier subnegotiation, and set LINES
  and COLUMNS from them.  Such a subnegotiation is now ignored.  A Telnet
  server offering FORWARD-X could overflow a buffer with a long OPTIONS request
  and leak a socket for each channel past the 64th.  Bugs were introduced in
  commits d0f8b1da (7.0.197 of 2000) and 29169c5e (8.0.201 of 2002).

- [7] A Telnet client set TERM from a terminal type the server sent with
  TTYPE IS.  Programs that Kermit ran later inherited it.  Only a client
  sends TTYPE IS, so a client now ignores it.  A Telnet server or IKSD
  still takes the client's type.  Bug was introduced in commit d0f8b1da
  in C-Kermit 7.0.197 of 2000.

- [8] A TLS client matched each label of a certificate's host name as a
  Kermit pattern.  A certificate for `*` or `l*` matched "localhost", and
  '?', '[...]' and an empty label also matched.  Kermit now uses
  `X509_check_host()`, so a wildcard matches only as the whole leftmost
  label of a name with more labels.  Addresses use `X509_check_ip_asc()`, so
  an IPv6 address in a certificate now matches.  Bug was introduced in
  commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [8] A Telnet client that used the AUTHENTICATION option's SSL type did
  not check that the server's certificate named the host.  A server could
  refuse START-TLS and offer that type, and any certificate from a trusted
  CA then passed.  The client now makes the same checks as for START-TLS.
  Bug was introduced in commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [8] A TLS client certificate was accepted for an account in `.tlslogin` when
  its signature bits matched a listed certificate.  The whole certificate must
  now match.  An IKSD sent the client certificate's name fields to the client
  in clear, and printed uninitialized memory when the commonName was missing.
  Bugs were introduced in commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [8] When OpenSSL had too little entropy, Kermit seeded it from the time
  and process ID.  It now refuses SSL and TLS.  Bug was introduced in
  commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [8, 9] TLS certificate checks never matched an IP address SAN containing a
  zero byte (such as 127.0.0.1), read past the SAN's buffer, and could not
  match any IP SAN on big-endian 64-bit hosts.  The overread and big-endian bug
  were introduced in commit c88d9b85 in C-Kermit 8.0.200 of 2001.  The
  zero-byte bug was introduced in commit 0fd869b4 in C-Kermit 9.0.302 of 2011.

- [8, 10] FTP over TLS, Telnet and raw SSL/TLS connections sent no server
  name (SNI), so a server could return the wrong certificate.  The FTP bug
  dates from commit c88d9b85 in C-Kermit 8.0.200 of 2001.  The others date
  from commit 8fed15a6 in C-Kermit 10.0 Beta.09 of 2023.

- [8] The default cipher list was `HIGH:MEDIUM:LOW:+ADH:+EXP`.  It enabled
  anonymous, export, and low-strength suites.  An anonymous suite gives no
  protection against interception.  OpenSSL 3 at its default security level
  offered none of these suites.  OpenSSL at security level 0, older OpenSSL
  versions, and LibreSSL offered them.  The default cipher list is now
  `HIGH:MEDIUM:!aNULL:!eNULL:!EXPORT:!LOW`.  SET AUTHENTICATION SSL
  CIPHER-LIST and the SSL_CIPHER environment variable still override it.
  Bug was introduced in commit 4e0c0d29 in C-Kermit 8.0.211 of 2004.

- [8] When an FTP server accepted AUTH TLS or AUTH SSL and the TLS session
  failed, FTP OPEN reconnected and tried the next authentication type.
  When that failed too, FTP OPEN sent the user name and password in the
  clear.  A failed handshake, an untrusted certificate, or a certificate
  for the wrong host triggered this fallback.  An attacker who broke the
  TLS session could then read the password.  FTP OPEN now closes the
  connection without logging in.  `SET FTP TLS-FALLBACK ON` restores the
  previous behavior.  When a server refuses AUTH, FTP OPEN still logs in
  without encryption.  Bug was introduced in commit c88d9b85 in C-Kermit
  8.0.200 of 2001.

- [8] Telnet, raw SSL/TLS, IKSD, HTTPS and FTP connections set no minimum
  protocol version.  HTTPS and Telnet left SSLv3 enabled.  So the library's
  minimum applied.  These connections now require TLS 1.2 or later.  `SET
  AUTHENTICATION SSL MINIMUM-VERSION` lowers the minimum for a legacy
  system.  Bug was introduced in commit c88d9b85 in C-Kermit 8.0.200 of
  2001.

### Dialing and serial lines

- [6, 7] DIAL and LOOKUP read past a stack buffer when a portable phone number
  had a country code longer than 127 digits or an area code longer than 23.
  The dial log line was sized from an uninitialized buffer.  Bugs were
  introduced in commit 4b5eddea in C-Kermit 6.0.192 of 1996 (DIAL and LOOKUP)
  and commit d0f8b1da in C-Kermit 7.0.197 of 2000 (dial log).

### Scripting and commands

These bugs are in the command language.  A remote user can trigger them at the
`IKSD>` prompt.  A server's client can trigger them with REMOTE ASSIGN and
REMOTE QUERY.  Scripts that handle data from a remote host, such as
`\v(input)` or a received file, also reach them.

- [5, 7, 8, 10] WHILE with a condition over about 230 characters, GREP
  /ARRAY with a line over 10,000 characters, and filename completion on a
  nearly full command line overflowed buffers.  GREP /ARRAY also dropped
  the last character of each element.  ARRAY CLEAR, SET and COPY with a
  range past the end of an array touched memory beyond it, and ARRAY
  RESIZE leaked, ignored allocation failure and left links stale.  Bugs
  were introduced in commits a213649d (5A(188) of 1992), d0f8b1da (7.0.197
  of 2000), c88d9b85 (8.0.200 of 2001) and 8fed15a6 (10.0 Beta.09 of
  2023).

- [5, 6, 9] Variable, macro and function expansion miscounted its buffers and
  left values unterminated.  A value copied into a longer string counted one
  byte less than it used.  ASSIGN of a value built from many such copies wrote
  past the command buffer.  ASSIGN (and `.name := value`) of a value that
  expanded past the command buffer stored it with no terminator.  A value too
  long for the place it was expanded into left that place without a terminator.
  Commands that went on with the cut value read past their buffer.  IF DECLARED
  with a long value read past a 32-byte buffer.  Several places expanded a
  value into a buffer one byte too small for the expansion and its terminator:
  an array subscript, a DO argument, the variable of an S-expression `++` or
  `--`, a function name or `\m()` name built from variables, the SET DIAL
  PBX-INSIDE-PREFIX of a PBX call, and the program path in SHOW FEATURES.
  OUTPUT, SET KEY and the key definitions of SET TERMINAL, SET DIALER and SET
  MOUSE wrote one byte past the command buffer when the expanded text filled it
  exactly.  A value that does not fit is now cut and terminated at the end of
  its buffer.  Bugs were introduced in commits a213649d (5A(188) of 1992),
  609e2f39 (5A(190) of 1994) and 4b5eddea (6.0.192 of 1996).  For `\%x`
  variables and array elements under SET VARIABLE-EVALUATION SIMPLE, the
  miscount was introduced in commit 0fd869b4 (9.0.302 of 2011).

- [5, 7, 8] Several functions read or wrote past their buffers.  `\fdoy2date()`
  with a long time after the date overflowed a static buffer.  `\fstripb()` of
  a single character that matched its bracket, such as `\fstripb(x,x)`, copied
  with a length of -1 and wrote far past its result buffer.  With a numeric
  bracket mask it wrote one byte before the buffer.  It now returns the
  character.  `\faaconvert()` with the same array for names and values wrote
  into the name array after it was freed.  It now returns its bad-array error.
  `\fmjd2date()` accepted any number and overflowed.  It now takes dates from
  0000-01-01 through 9999-12-31.  `\feval()` of a bad name at the end of an
  expression read past it.  The floating-point functions that take a number of
  decimal places, such as `\ffpadd()` and `\ffpdiv()`, wrote past the end of
  the result buffer for a large request.  They now format at most 200 places.
  `\ffiles()`, `\fdirectories()` and the other file-list functions with an
  empty pattern and an array stored a name left from an earlier expansion in a
  list sized for none.  The list had no end, and the next such call read past
  it.  Bugs were introduced in commits a213649d (5A(188) of 1992), d0f8b1da
  (7.0.197 of 2000) and c88d9b85 (8.0.200 of 2001).

- [6, 8] SET PROTOCOL with a 71-character default command overflowed a
  stack buffer.  SET SERVER GET-PATH with more than 128 directories
  overflowed a stack array.  The SET PROTOCOL bug was introduced in commit
  c88d9b85 in C-Kermit 8.0.200 of 2001.  The GET-PATH bug was introduced in
  commit 4b5eddea in C-Kermit 6.0.192 of 1996.

- [8] TRANSMIT /BINARY on a Telnet connection with TRANSMIT ECHO OFF wrote past
  its send buffer when a doubled IAC byte fell at the end of the buffer.  The
  rest of the file then went on past the buffer and was not sent.  Bug was
  introduced in commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [9] RENAME and CHANGE wrote past stack buffers with long path names.  RENAME
  /REPLACE overflowed when the replacements made the new name longer than the
  longest path name, and Kermit could crash.  RENAME now fails for that file
  with "?New name too long".  RENAME with a wildcard and /LOWER, /UPPER,
  /REPLACE, /FIXSPACES or /CONVERT overflowed when the files were in a
  directory whose path was longer than about 2,000 bytes.  CHANGE overflowed
  its source directory buffer when the current directory and the file pattern
  together were longer than the longest path name.  The RENAME bugs were
  introduced in commit 0fd869b4 in C-Kermit 9.0.302 of 2011.  The CHANGE bug
  was introduced in commit 6100ebcc in C-Kermit 304(dev17) of 2016.

- S-expressions:

  - [8] SET SEXPRESSION DEPTH-LIMIT in a macro that an S-expression called
    freed the result stack that the S-expression still used, and Kermit
    crashed.  The command is now refused there.  An S-expression nested exactly
    to the depth limit, or one level deeper, read and wrote one entry past the
    result stack.  So did any S-expression after a limit of 0 or less.  Bugs
    were introduced in commit c88d9b85 in C-Kermit 8.0.200 of 2001.

  - [8] S-expression arguments ran past their buffers.  An S-expression that
    called a macro wrote one or two bytes past its argument list when an
    argument began at the end of the list's buffer.  An S-expression of a
    variable whose value starts with a quote, such as `(x)` after `.x :=
    '(abc)`, returned uninitialized memory and read past it.  It now returns
    `abc`.  Splitting a string could leave a word without its terminating NUL
    when the word was a quoted group, such as `'(a b)`, and an earlier split
    had left a large enough buffer.  The word then took on bytes past its
    buffer.  A macro called from an S-expression got such an argument.  Bugs
    were introduced in commits c88d9b85 (8.0.200 of 2001) and 4e0c0d29 (8.0.211
    of 2004).

## Additional improvements and bugfixes

- [11] The debug log is flushed at the end of each line instead of after
  every fragment written to it.  A killed process still leaves every
  complete line on disk.  The `CK_DEBUG_UNBUFFERED` environment variable
  is removed.  It had no effect, since every fragment was flushed.  The
  per-fragment flush was introduced in commits 43c4c8ce and 62c2d7d8 in
  C-Kermit 11.0.501 of 2026.

### File transfer and the server

- [5] RESEND took the receiver's partial file length with no check.  A
  non-digit or a length past the largest file offset gave a wrong offset,
  and the receiver appended the wrong part of the file.  The sender now
  refuses the file, and the receiver keeps its partial file as it was.  A
  length of "-1" still sends the whole file.  Bug was introduced in commit
  609e2f39 in C-Kermit 5A(190) of 1994.

- [5, 7] A receiver with SET LANGUAGE set to a language that writes one
  character as two, such as German `Ä` as `Ae`, lost one later byte of the
  packet for each such character.  A repeated character that becomes two, sent
  with a repeat count, was received as the first letter repeated and the second
  once.  German `ÄÄÄ` became `AAAe` instead of `AeAeAe`.  The lost byte was
  introduced in commit d0f8b1da in C-Kermit 7.0.197 of 2000.  The repeat bug
  was introduced in commit a213649d in C-Kermit 5A(188) of 1992.

- [5, 6, 7] A sender with SET BUFFERS smaller than the default could build
  packets larger than its send buffer when the receiver allowed long packets.
  This happened with a window of 1, with a window and SET TRANSFER SLOW-START
  OFF, and with streaming.  The packet length is now cut so that one packet, or
  a windowful, fits.  Bug was introduced in commit a213649d in C-Kermit 5A(188)
  of 1992 (window of 1), commit 4b5eddea in C-Kermit 6.0.192 of 1996 (slow
  start off), and commit d0f8b1da in C-Kermit 7.0.197 of 2000 (streaming).

- [5, 7] A receiver multiplied a length-in-K attribute by 1024 with no overflow
  check.  A length past the largest file offset wrapped, and the file transfer
  display used the wrapped size.  Such a length is now unknown.  A receiver
  read the rest of a record format attribute longer than 10 characters, or a
  generic protection attribute longer than 1, as more attributes.  A file could
  be refused for an attribute the sender did not send.  Bugs were introduced in
  commit a213649d in C-Kermit 5A(188) of 1992 (length in K) and commit d0f8b1da
  in C-Kermit 7.0.197 of 2000 (record format and protection).

- [6] With a window of 1, a sender took a NAK for the next packet as a NAK for
  the current one and sent the current packet again.  The Kermit protocol, and
  the code's comment, take it as an ACK for the current packet.  Bug was
  introduced in commit 4b5eddea in C-Kermit 6.0.192 of 1996.

- [6, 7, 9] Send-Init handling had several faults.  The partner's system ID was
  not terminated.  After SET SEND NEGOTIATION-STRING-MAX-LENGTH with a value
  from 9 to 16, or a value that cut off the system ID, the Send-Init parameters
  could run on with parameters left from an earlier, longer Send-Init.  A
  receiver looked for a forced Type 3 block check (CHKT "5") at a fixed place
  in the buffer.  A short Send-Init could be refused when an earlier packet had
  left a "5" there.  A Send-Init with an extended header that asked for the
  forced check was refused.  CHKT is now read from the data field.  Bugs were
  introduced in commits 4b5eddea (6.0.192 of 1996), d0f8b1da (7.0.197 of 2000)
  and 0fd869b4 (9.0.302 of 2011).

- [7] An extended GET after a failed one (GET /RECOVER /DELETE, for
  example) sent the old request without the new name.  Bug was introduced
  in commit d0f8b1da in C-Kermit 7.0.197 of 2000.

- [7] A server answering REMOTE HOST, REMOTE SPACE or another command that runs
  a program killed the program when its output ended, before the program
  exited.  When the kill came first, the exit status said "killed", and the
  server marked the reply as discarded, so the client reported failure although
  it showed the whole reply.  The server now waits up to two seconds for the
  program to exit, and kills it only after that.  Bug was introduced in commit
  d0f8b1da in C-Kermit 7.0.197 of 2000.

- [7, 11] On MacOS, a streaming send over a pty connection could hang or take
  2 seconds per packet.  FIONREAD is broken on MacOS and can report more bytes
  available than can be read.  The sender then waited for an ACK that was not
  there.  Before C-Kermit 11.0.501 it waited with no timeout and hung the
  transfer.  Since then, it waited 2 seconds per packet.  Kermit now confirms
  the count with select().  The code that hung was introduced in commit
  d0f8b1da in C-Kermit 7.0.197 of 2000, though the underlying bug is in MacOS.
  Commit 4a48cd29 in C-Kermit 11.0.501 of 2026 replaced the hang with the
  2-second wait.  That improved the behavior without fixing it.

- [7] Fixed a bug regarding input flushing on the BSDs.  Kermit flushes the
  input before reading its first packet.  On the BSD platforms, flushing a pty
  master with TIOCFLUSH FREAD caused the slave's input queue to also empty out.
  This didn't cause data loss, but could cause a delay, since the first protocol
  messages could be lost.  Bug was introduced in commit d0f8b1da in C-Kermit
  7.0.197 of 2000.

- [8] SET TRANSFER DISPLAY FULLSCREEN with TERM unset or unknown to
  terminfo ended Kermit at the start of the next transfer, on systems
  whose curses has no newterm(), such as NetBSD.  Kermit now uses the CRT
  display, as it does elsewhere.  The fallback message no longer prints a
  null pointer when TERM is unset.  Bug was introduced when the terminal
  type check of SET TRANSFER DISPLAY was disabled in C-Kermit 8.0.201 of
  2002.

- [8] A failed write of a Data packet abandoned the file without telling
  the receiver.  The FINISH that followed then took a minute or more to
  fail.  The packet is now resent like a lost one.  Bug was introduced in
  commit 7b4ce026 in C-Kermit 8.0.206 of 2002.

- [11] Timeouts use a monotonic clock.  They used the time of day, so a
  clock step lengthened or shortened them.  Bug was introduced in commit
  4521c6b6 in C-Kermit 11.0.510 of 2026.

- [11] "No files were transferred" appeared after REMOTE PWD, REMOTE DIRECTORY,
  FINISH and BYE, and after successful ZMODEM and other external-protocol
  transfers.  With the CRT, BRIEF and SERIAL displays it repeated a cause the
  display had already shown.  Now the result of a transaction is printed only
  where nothing visible states it.  Bug was introduced in commit 52027325 in
  C-Kermit 11.0.501 of 2026.

- `*.ts` is no longer a default text pattern.  MPEG transport stream video uses
  `.ts` as well as TypeScript, and sending such a video in text mode damages
  it.  A `.ts` file now takes the prevailing transfer mode.  `*.ts` came with
  commit 976a9742 in C-Kermit 11.0.501 of 2026.

### FTP and HTTP

- [7, 8] HTTP reconnects went to the wrong port for ports above 255, and HTTP
  INDEX left the directory out of its request line.  The port bug was
  introduced in commit c88d9b85 in C-Kermit 8.0.200 of 2001.  The INDEX bug was
  introduced in commit d0f8b1da in C-Kermit 7.0.197 of 2000.

- [8] In active mode, a server that never opened the data connection hung
  the client.  The wait now ends after SET FTP TIMEOUT, or 60 seconds when
  the timeout is 0.  Bug was introduced in commit c88d9b85 in C-Kermit
  8.0.200 of 2001.

- [8] PUT /RECOVER read a SIZE reply too large for a file offset as a
  wrapped value.  The server could make Kermit append part of the file to
  different remote contents.  Kermit now sends the whole file.  Bug was
  introduced in commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [8] With SET FTP SERVER-TIME-OFFSET, the seconds of a server file time
  were replaced by its minutes.  03:04:55 with an offset of +1 became
  04:04:04.  Bug was introduced in commit 7b4ce026 in C-Kermit 8.0.206 of
  2002.

- [8] Command-line HTTP (`kermit http://...`) exited with success after a
  failed transfer such as a 404.  Command-line FTP's "No files to put/get"
  messages were swapped.  An FTP GET /UPDATE with no local file date passed
  NULL to the date comparison.  Bugs were introduced in commit c88d9b85 in
  C-Kermit 8.0.200 of 2001.

- [10] Ctrl-C during an FTP transfer went back to the prompt without
  closing the data connection or reading the server's reply, so the next
  FTP command read the wrong reply.  Bug was introduced in commit
  ca1addda in C-Kermit 10.0 Beta.10 of 2023.

- [8] SHOW FTP displayed the PASSIVE-MODE setting as SEND-PORT-COMMANDS.
  Bug was introduced in commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [11] IPv6 addresses were not bracketed in the HTTP Host header and in
  the HTTP and FTP proxy CONNECT targets, and a bracketed proxy address
  was split at its first colon.  The code dates from commits c88d9b85
  (8.0.200 of 2001) and 4e0c0d29 (8.0.211 of 2004) and became wrong when
  commit 36668be5 added IPv6 in C-Kermit 11.0.501 of 2026.

### Connections, Telnet and TLS

- [4] OUTPUT sent a 255 byte as a bare IAC on a Telnet connection.  The peer
  read it and the byte after it as a Telnet command.  OUTPUT now sends 255 as
  IAC IAC, as TRANSMIT does.  This includes COMMAND QUOTING OFF.

- [7, 8] SIGHUP while the debug log was open could deadlock Kermit inside
  the signal handler.  SIGHUP and SIGWINCH are now handled outside it.
  Bugs were introduced in commits d0f8b1da in C-Kermit 7.0.197 of 2000,
  and 7b4ce026 in C-Kermit 8.0.206 of 2002.

- [7, 8] On big-endian 64-bit hosts, the local IP address lookup returned
  0.0.0.0 and the Telnet COM-PORT baud rate was sent and read wrongly.  Added
  regression tests to cover these bugs.  The tests can fail only on a
  big-endian host.  The address bug was introduced in commit d0f8b1da in
  C-Kermit 7.0.197 of 2000.  The COM-PORT bug was introduced in commit c88d9b85
  in C-Kermit 8.0.200 of 2001.

- [7, 8] SHOW AUTHENTICATION listed the OpenSSL default ciphers instead of
  the ciphers a connection offers.  It also ignored the SSL_CIPHER
  environment variable.  It now lists the ciphers from the effective cipher
  list and shows the source of that list.  It also reports when the list
  matches no cipher.  Bugs were introduced in commit d0f8b1da in C-Kermit
  7.0.197 of 2000 and commit 4e0c0d29 in C-Kermit 8.0.211 of 2004.

- [7, 8] `SET AUTHENTICATION SSL CIPHER-LIST` with no argument set the list
  to `ALL`.  `ALL` includes anonymous suites.  An empty argument now
  restores the default cipher list.  The command also accepted a list that
  matched no cipher.  An unmatched list from SET, the `-T cipher=` option,
  or SSL_CIPHER left the OpenSSL default in place.  Connections then used
  the OpenSSL default without warning.  SET now refuses an unmatched list.
  Telnet, raw SSL/TLS, HTTPS, and FTP connections also fail with "?No
  cipher matches the cipher list".  Bugs were introduced in commit d0f8b1da
  in C-Kermit 7.0.197 of 2000 (SET) and commit c88d9b85 in C-Kermit 8.0.200
  of 2001 (connections).

- [7] A 0xFF data byte that arrived while a Telnet connection waited for
  negotiation replies was lost along with the following byte.  The wait kept
  one IAC of the peer's IAC IAC.  The reader then took it as a command.  On an
  /SSL or /TLS connection whose peer sent IAC IAC first, the 0xFF also came
  after the data that followed it.  The wait now keeps IAC IAC in order.

- [7] A Telnet server or IKSD could hang or fail in START-TLS.  The server
  sends its SB START_TLS FOLLOWS first.  A client may send its TLS handshake
  right after its FOLLOWS.  When the server read both at once, the handshake
  stayed in Kermit's input buffer and OpenSSL waited for it on the socket.
  A Kermit client can trigger this under load.  The server now reads one
  byte at a time until the client's FOLLOWS ends.  Bug was introduced in
  commit d0f8b1da in C-Kermit 7.0.197 of 2000.

- [8, 11] A failed SSL/TLS setup on SET HOST gave no reason.  The OpenSSL error
  now appears.  A failed SET HOST lost its error, so `\v(setlinemsg)` read
  "Network connection failure" instead of the reason.  SET HOST
  /NETWORK-TYPE:VSOCK with no address returned an arbitrary status.  It now
  asks for CID:PORT.  Bugs were introduced in commit c88d9b85 in C-Kermit
  8.0.200 of 2001 (SSL/TLS), commit 36668be5 in C-Kermit 11.0.501 of 2026 (SET
  HOST) and commit 8209ea02 in C-Kermit 11.0.508 of 2026 (VSOCK).

- [8] A Kermit packet that arrived while a Telnet connection waited for
  negotiation replies could be lost.  The wait read the packet ahead and
  handed it back.  The packet reader took the rest of the packet first.  The
  transfer then stalled until a packet timeout.  Over /SSL and /TLS it
  happened when the client sent its first packet within the server's 1 s
  wait.  SET TELNET WAIT-FOR-NEGOTIATIONS OFF on the client or SET PROTOCOL
  STARTUP-STRING OFF made that likely.  The packet reader now takes the
  handed-back data first.

- [8] /SSL and /TLS connections sent IAC DO LOGOUT on close to a peer that
  never sent Telnet.  These connections start Telnet only when the peer sends
  IAC.  Close now sends DO LOGOUT only once Telnet has started.

- [9] /SSL-RAW and /TLS-RAW connections sent Telnet bytes.  TRANSMIT doubled
  0xFF, OUTPUT sent CR as CR LF, and closing sent IAC DO LOGOUT.  The
  connection was marked as Telnet once it opened.  Raw connections now stay
  raw and use the local echo setting of SET HOST /RAW-SOCKET.
  `\v(connection)` now reports `tcp/ip_ssl` or `tcp/ip_tls` for them.  It
  had reported `tcp/ip_telnet`, and /TLS-RAW was not recognized.

- [11] /SSL and /TLS connections skipped the wait for Telnet negotiation.
  Only raw SSL and TLS should skip that wait.  Bug was introduced in commit
  0b9dc4f2 in C-Kermit 11.0.501 of 2026.

### IKSD

- [7] When the IKSD cannot write its address and PID into the database lock
  file, it removes the temporary file and does not update the database.  A
  build with syslog support (`-DDOSYSLOG`) logs the failure.  It used to
  install a lock file without a PID.  If the IKSD ended while it held that
  lock, the lock never looked stale and blocked every later database update.
  Bug was introduced in commit d0f8b1da in C-Kermit 7.0.197 of 2000.

- [7, 11] The IKSD forbidden-user file refused any login name that was a
  prefix of a listed name.  The file was left open after a refusal, the
  database lock stayed when the database name was missing, and a stale
  IPv6 lock was not recognized.  The prefix and lock bugs were introduced
  in commit d0f8b1da in C-Kermit 7.0.197 of 2000.  The IPv6 bug was introduced
  in commit 36668be5 in C-Kermit 11.0.501 of 2026.

- [7] A Telnet server or IKSD that received a second, different USER after
  a START-TLS certificate login checked the client certificate for the new
  user on the wrong connection.  The check always failed and asked for a
  password.  It now uses the START-TLS connection, as the check of the
  first USER does.  Bug was introduced in commit d0f8b1da in C-Kermit
  7.0.197 of 2000.

- [7] An IKSD started with an `--anonroot` path longer than 1024 bytes wrote
  the path past the directory field of its session database record, into the
  next field.  The path is now cut at the end of the field.  Bug was introduced
  in commit d0f8b1da in C-Kermit 7.0.197 of 2000.

### Dialing and serial lines

- [5] When SET LINE cannot write its PID into the UUCP lock file, it removes
  the temporary file, prints a warning and uses the device without a lock.  It
  used to install a lock file without a PID.  Such a lock never looks stale, so
  the device stayed locked until someone removed the file.  Bug was introduced
  in commit a213649d in C-Kermit 5A(188) of 1992.

- [6] LOOKUP and DIAL crashed when a dialing directory before a good one
  could not be opened.  Bug was introduced in commit 4b5eddea in C-Kermit
  6.0.192 of 1996.

- [7] When a name in the dialing directory had several numbers and one was a
  PBX internal call, DIAL and LOOKUP gave the internal call type to another
  number in the list.  The internal number kept the local type, or no type.
  SET DIAL SORT and SET DIAL RESTRICT then used the wrong types.  Bug was
  introduced in commit d0f8b1da in C-Kermit 7.0.197 of 2000.

- [11] `%%` in SET MODEM DIAL-COMMAND sends one `%` again, as it did
  before C-Kermit 11.0.501.  Since then DIAL replaced the first `%s` with
  the number and sent `%%` as two characters.  HELP SET MODEM DIAL-COMMAND
  now describes the rule.  Added regression tests that drive DIAL
  against a scripted modem on a pseudoterminal.  The change came with
  commits 9f732296 and 55973561 in C-Kermit 11.0.501 of 2026.

### Scripting and commands

- [4, 5, 6] When built with musl, Esc completion at the command prompt showed
  nothing until the next keystroke.  musl does not flush stdout on getchar()
  as other C libraries do.  The parser now flushes stdout before each read.
  The keyword default dates from commit f16b451f in C-Kermit 4C(057) of 1985.
  Partial filename completion dates from commit a213649d in C-Kermit 5A(188)
  of 1992.  Directory completion dates from commit 4b5eddea in C-Kermit
  6.0.192 of 1996.

- [5] On Unix, WHO with a user name passed that name to who.  who read
  the argument as a login database file.  WHO now refuses a user name
  unless the CK_WHO environment variable is set.  HELP WHO describes
  CK_WHO.  Bug was introduced in commit a213649d in C-Kermit 5A(188) of
  1992.

- [5, 6, 7, 8, 9] Division or modulus of the most negative integer by -1 killed
  Kermit with SIGFPE, and that number printed as "OVERFLOW".  `\fmax()`,
  `\fmin()`, `\fmod()` and `\frandom()` truncated values to 32 bits.  Numbers
  of 20 digits wrapped instead of stopping at the largest value.  An
  S-expression with such a number gives a floating-point result.  `\fradix()`,
  `\fhex2n()` and `\foct2n()` returned 0 or an empty string instead of -1 for
  values past 2^63-1.  ARRAY RESIZE to 2147483647 elements overflowed a signed
  integer when it computed the size.  It now reports "Dimension too large", as
  DECLARE does.  Bugs were introduced in commits a213649d (5A(188) of 1992),
  4b5eddea (6.0.192 of 1996), d0f8b1da (7.0.197 of 2000), c88d9b85 (8.0.200 of
  2001) and 0fd869b4 (9.0.302 of 2011).

- [5, 8] Expansion and S-expression depth counts stayed raised.  Each expansion
  that failed because its value did not fit left the nesting count of the
  expander one level higher.  Ctrl-C during the expansion of a variable or
  function left it raised by the levels in progress.  After about 100 such
  failures, or enough interrupts, a correct command failed with "Definition is
  circular or too deep".  Ctrl-C during an S-expression left the S-expression
  depth raised.  `\v(sdepth)` stayed above 0, each interrupt took one level
  from the depth limit, and SET SEXPRESSION DEPTH-LIMIT was refused at the
  prompt.  The expansion count now goes back down on every return.  Ctrl-C
  returns both depths to 0.  Bugs were introduced in commits a213649d (5A(188)
  of 1992) and c88d9b85 (8.0.200 of 2001).

- [5, 7] With stdin at end of file, ASK /TIMEOUT, SHOW KEY, GETC, GETOK and the
  text and password prompts looped forever.  Bugs were introduced in commits
  a213649d (5A(188) of 1992), d0f8b1da (7.0.197 of 2000) and 29169c5e (8.0.201
  of 2002).

- [7, 9, 11] Floating-point functions and S-expressions lost precision with
  large integers.  On systems that do floating point in an x87 FPU, such as
  32-bit x86 Linux, CEILING, FLOOR, TRUNCATE, ROUND, ABS, MAX and MIN gave
  inexact results for integers past 2^53.  An integer past the 64-bit range
  could compare equal to the largest integer.  Integer results past 64 bits
  wrapped instead of moving to floating point.  The digit-at-a-time conversion
  was introduced in commit d0f8b1da in C-Kermit 7.0.197 of 2000.  The `++`,
  `--`, ABS, MAX, MIN and comparison bugs were introduced in commit 0fd869b4 in
  C-Kermit 9.0.302 of 2011.  The CEILING, FLOOR, TRUNCATE and ROUND bug was
  introduced in commit cfc424ff, and the wrap in commit ba8d78d5, both in
  C-Kermit 11.0.512 of 2026.

- [7] WAIT n FILE succeeded on timeout even if the event never happened.  Bug
  was introduced in commit d0f8b1da in C-Kermit 7.0.197 of 2000.

- [7, 10] COPY named the source file when it failed to write the
  destination.  TRANSMIT of a UCS-2 text file did not end lines at LF.
  Esc at SET TERMINAL LOCAL-CHARACTER-SET offered a name that "?" does not
  list.  `\v(fullversion)` ended in " ." on release builds.  The first
  three were introduced in commit d0f8b1da in C-Kermit 7.0.197 of 2000;
  the last in commit 0c0c21f5 in C-Kermit 10.0 Beta.05 of 2022.

- [8, 11] TYPE /WIDTH showed empty lines, or lines cut to the /TAIL count,
  instead of each line truncated to the given width.  It also put a NUL byte
  after each tab it expanded.  That extra byte moved the next tab stop one
  column.  TYPE /WIDTH also copied the whole tab-expanded line back into its
  buffer.  With UCS-2 output that copy could exceed the buffer, but TYPE /WIDTH
  stops at the first NUL byte of UCS-2 text, so this cannot happen today.  The
  width regression came from the -Wshadow work, present in 11.0.510 through
  11.0.514, and was introduced in commit 4ddb464e in C-Kermit 11.0.510.  The
  tab bugs were introduced in commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [8] The S-expression power operator took one multiplication for each unit of
  an integer exponent.  `(^ 2 9000000000000000000)` ran for centuries, and
  integer overflow went unchecked.  It now squares and multiplies.  An
  overflow gives the floating-point result.  Bug was introduced in commit
  c88d9b85 in C-Kermit 8.0.200 of 2001.

- [8] `\fsexpression()` with an empty first argument and another argument
  crashed Kermit when it was the first S-expression of the session.  Bug was
  introduced in commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [9] `\ffilecompare()` crashed Kermit when the first file could be opened
  and the second could not.  Bug was introduced in commit 04917e78 in
  C-Kermit 304(dev05) of 2013.

- [9] `\v(tmpdir)` gave the text "tmpdir", or whatever was in its result
  buffer, when TMPDIR, CK_TMP, TEMP or TMP ended with a slash.  It now gives
  that directory.  Kermit's temporary directory comes from `\v(tmpdir)` at
  startup, so Kermit used the same wrong name.  Bug was introduced in commit
  6100ebcc in C-Kermit 9.0.304 Dev.17 of 2016.

- [10] COPY /TOSCREEN and COPY /INTERPRET end a line only at LF.  The code
  took vertical tab for CR, so both commands ended a line at a vertical tab,
  and COPY /INTERPRET turned each vertical tab into a line break.  CR and
  vertical tab are now copied as they are.  Both commands also left out the
  last line of a file that did not end with a newline.  COPY /INTERPRET
  expanded each line into the buffer that held the destination name.  With a
  wildcard and a directory as the target, the second and later files went to a
  path made from the start of the previous file's last line.  Bugs were
  introduced in commit 0c0c21f5 in C-Kermit 10.0 Beta.05 of 2022.

- [10] `\fcvtdate()` did not convert Apache log dates such as
  `[02/Jan/2024:03:04:05 +0000]`.  It removed every colon, including those
  of the time.  It now replaces only the colon after the year, and accepts
  the brackets.  Dates like `2024:01:02` lost their colons and converted,
  and still do.  Bug was introduced in commit 7c4bb07e in C-Kermit 10.0
  Dev.24 of 2020.

- [11] `\fname2addr()` returns an IPv4 address when the name has one, as before
  IPv6 support, unless `SET TCP ADDRESS-FAMILY` selects IPv6.  Under the
  default `AUTO` it had returned the resolver's first answer, so
  `\fname2addr(localhost)` gave `::1`.  It still returns an IPv6 address for a
  name that has only one, and a numeric argument in any form the resolver
  accepts, such as `0x1F`, comes back in standard form.  Bug was introduced in
  commit 36668be5 in C-Kermit 11.0.501 of 2026.

- [11] A '*' in a wildcard no longer matched a '.' inside a name when another
  metacharacter followed it, so `\ffiles(a*?b)` missed `a.b`.  Bug was
  introduced in commit a664a9cc in C-Kermit 11.0.509 of 2026.

- [11] Abbreviations such as SET COM, SHOW IN, SET TCP ADDRESS and SET
  RECEIVE CON had become ambiguous with new keywords, and GET /co meant
  /confirm instead of /command.  The new keywords were added in C-Kermit
  11.0.501, 11.0.505 and 11.0.506 of 2026.

- [11] A doublequote after an escaped backslash, as in `"\\"`, did not end a
  quoted field.  Bug was introduced in commit b06df387 in C-Kermit 11.0.506 of
  2026.

### Memory and descriptor leaks

- [5, 6, 7, 8, 9, 10] COPY, DECLARE, DIRECTORY, IF MATCH, `\fcvtdate()`,
  function calls with an empty last argument, wildcard expansion that
  filled the file list, URLs, MKDIR, TAKE with arguments, SET DIAL list
  commands, the SRV lookup, the dialing directory conversion and lookup,
  the pty fork failure path and the controlling terminal check leaked
  memory or descriptors.  An allocation failure in several places crashed
  instead of failing.  These date from C-Kermit 5A(188) of 1992 through
  10.0 Dev.24 of 2020.  No regression test covers the leaks in code only
  IKSD guests or failing system calls reach.

### Builds, help and documentation

- [5, 6, 7, 9, 11] HELP and SHOW stated wrong defaults.  HELP gave SET FUNCTION
  ERROR (ON, not OFF), SET IKS CDMESSAGE (OFF, not ON), SET UNKNOWN-CHAR-SET
  (KEEP, not DISCARD), SET WINDOW-SIZE (30, not one) and SET TERMINAL
  CHARACTER-SET (the same set on both sides, not TRANSPARENT).  HELP SET
  TRANSFER MODE and HELP SET FILE named AUTOMATIC as the TRANSFER MODE default.
  The default is MANUAL.  HELP SET INCOMPLETE, SET TCP LINGER and SET SERVER
  DISPLAY also stated wrong defaults.  HELP SET VARIABLE-EVALUATION and the
  11.0.504 and 11.0.506 notes said the default was `SIMPLE`.  The default is
  `RECURSIVE`, as it has been since the command was added in C-Kermit 9.0.302.
  SHOW FILE and SHOW PROTOCOL showed the FILE COLLISION default as "discard"
  instead of "reject".  HELP SET DIAL RETRIES gave 0 as the default.  It now
  says that RETRIES counts attempts, and that without a setting DIAL makes 10
  attempts for country code 1 and one otherwise.  HELP SET HOST now says that
  SET HOST with no host name closes the connection.  HELP REMOTE QUERY offered
  the Kermit-variable help for system and user variables.  The errors date from
  commits a213649d (5A(188) of 1992), 4b5eddea (6.0.192 of 1996), d0f8b1da
  (7.0.197 of 2000) and 0fd869b4 (9.0.302 of 2011), and from commits cdd2e257
  and 4f611d0c (11.0.501 of 2026).

- HELP RESEND, HELP SET RECEIVE CONFIRM, HELP SET FTP TIMEOUT, HELP
  FIREWALL and HELP SET FTP PASSIVE-MODE now describe the new RESEND,
  RECEIVE CONFIRM, FTP active-mode timeout and FTP PASV rules.

- [7] A build without streaming support (`-DNOSTREAMING`) could not send
  files.  The sender never read the receiver's replies, and it got no send
  buffer for each packet after the first.  Bugs were introduced in commit
  d0f8b1da in C-Kermit 7.0.197 of 2000.

- [8] Builds with NOTOMACROS, such as hpux0500, kept the Telnet
  PRAGMA-LOGON option in the STDERR option's state.  The SSPI-LOGON,
  PRAGMA-HEARTBEAT and IBM-SAK options each used the slot of the option
  before them, and the debug log showed the wrong names.  Bug was
  introduced in commit c88d9b85 in C-Kermit 8.0.200 of 2001.

- [10, 11] `make netbsd` under GNU make failed with a shell syntax error from
  its build log step.  Builds with NOLISTEN, on HP-UX with IPv6, and with C90
  compilers failed.  A build with -DNODISPO accepted mail, print and RESEND
  dispositions.  The `make netbsd` bug was introduced in commit ca1addda in
  C-Kermit 10.0 Beta.10 of 2023.  The others were introduced in commits
  36668be5 and 3b1a95d6 (11.0.501), 8209ea02 (11.0.508) and 30ab9d4f
  (11.0.512), all of 2026.

## Summary of changed behavior

- [4, 6] A server with HOST disabled refuses PUSH within REMOTE QUERY.
  REMOTE WHO and REMOTE SPACE run without the shell.  A Unix server
  refuses a REMOTE WHO name.  REMOTE SPACE refuses a name that is not an
  existing directory.

- [5] On Unix, WHO refuses a user name unless the CK_WHO environment
  variable names the command to run.

- [4] A malformed packet ends the transfer with "Malformed packet data".
  A packet shorter than its block check is refused.

- [5] SET LINE uses the device without a lock, with a warning, when it
  cannot write its lock file.

- [5] `\fmjd2date()` accepts dates from 0000-01-01 through 9999-12-31.

- [5, 6, 7, 8, 9] `\fmax()`, `\fmin()`, `\fmod()` and `\frandom()` take
  64-bit values.

- [6, 11] A receiver refuses a RESEND unless its FILE COLLISION setting
  allows it or it asked for a REGET.

- [7] A receiver gives a received file only the read, write and execute
  bits of the sender's permissions.

- [7] A Telnet client ignores TTYPE IS from the server.

- [7] A server waits up to two seconds for a program run by REMOTE HOST
  and similar commands to exit before it kills it.

- [7] The IKSD does not update its database when it cannot write the
  database lock file.

- [7, 8] `\fstripb(x,x)` returns the character.

- [8] FTP GET fails at the first failed write of the local file.

- [8] FTP MGET /RECURSIVE skips server names that leave the current
  directory.

- [8] FTP OPEN does not log in when TLS fails after the server accepts
  AUTH TLS or AUTH SSL.  `SET FTP TLS-FALLBACK ON` logs in without
  encryption.

- [8] FTP passive data connections go to the control connection's
  address, not to the address in the PASV reply.  `SET FTP
  TRUST-PASV-ADDRESS ON` uses the address in the reply.

- [8] TLS host name checks use `X509_check_host()`.  A wildcard matches
  only as the whole leftmost label of a name with more labels.

- [8] Kermit refuses SSL and TLS when OpenSSL has too little entropy.

- [8] The default SSL/TLS cipher list excludes anonymous, unencrypted,
  export, and low-strength suites.

- [8] Telnet, raw SSL/TLS, IKSD, HTTPS and FTP connections require TLS 1.2
  or later.  `SET AUTHENTICATION SSL MINIMUM-VERSION` changes the minimum.

- [8] The floating-point functions format at most 200 decimal places.

- [8] SET SEXPRESSION DEPTH-LIMIT is refused in a macro that an
  S-expression called.

- [8, 11] S-expression integer results that overflow become floating
  point, including the power operator.

- [8, 11] `ENABLE` and `DISABLE` with `LOCAL` or `REMOTE` change only that
  side.

- [9] Kermit waits up to two seconds for an external protocol program's
  exit status, and relays its output until end of file.

- [9] The default file-list string space on 64-bit builds is 32MB.  `SHOW
  FILE` displays it.

- [9] `RENAME` fails with "?New name too long" when a new name does not
  fit.

- [10] `COPY /TOSCREEN` and `COPY /INTERPRET` end lines only at LF.

- [10] `\fcvtdate()` converts Apache log dates.

- [11] RECEIVE CONFIRM prompts for files a recursive GET places outside
  the requested directory.

- [11] `SET COMPATIBILITY 9` and `10`, and `kermit9` and `kermit10`, set
  RECEIVE PATHNAMES AUTO and no longer re-enable functions that ENABLE
  refuses.

- [11] "No files were transferred" appears only where nothing visible
  states the result.  A successful FULLSCREEN transfer prints a one-line
  summary when the display is erased.

- [11] `%%` in SET MODEM DIAL-COMMAND sends one `%`.

- [11] `\fname2addr()` prefers an IPv4 address under `SET TCP
  ADDRESS-FAMILY AUTO`.

- [11] The `CK_DEBUG_UNBUFFERED` environment variable is removed.

- `*.ts` is no longer a default text pattern.

- C-Kermit needs OpenSSL 1.0.2 or later, or LibreSSL.

## Changes in earlier releases that didn't make it into the changelog

- C-Kermit 11.0.501: FTP reports the host name as typed and looks it
  up in `.netrc` by that name, not by the canonical name.  A `.netrc`
  entry for the canonical name no longer matches an alias.  Commit
  c3c8dea2.

- C-Kermit 11.0.509: `\v(authtype)` no longer reports
  `X_509_CERTIFICATE` when no authentication took place.  Commit
  76190cb0.

- C-Kermit 11.0.509: an external protocol run over a Telnet
  connection answers the host's unsolicited WILL and DO with DONT and
  WONT.  Commit ce6628a3.

- C-Kermit 11.0.509: calling a macro whose name begins with `_` read
  past a table and could crash Kermit.  Commit 81405312.

- C-Kermit 11.0.512: an empty `/MOVE-TO:` or `/RENAME-TO:` on SEND or
  GET clears that setting.  Commit cfc424ff.

# C-Kermit 11.0.514

September 30, 2026

- Fixed a bug in a test that could cause a spurious failure with certain-sized
  tmpdirs.  Fixes #40.  Making a new release with the fix to unblock Fedora.
- Fixed a bug in tests where an IPv6 port collision while testing was
  mishandled.

# C-Kermit 11.0.513

September 30, 2026

- Fixed the armhf binary build in Github CI.  The platform was already being
  tested, but the final binaries weren't being built.

- On platforms where long is 32 bits but time_t is 64 bits, keep received
  times in excess of the 32-bit limit intact, skipping an unnecessary
  conversion truncation.  This bug dates back to C-Kermit 5A of 1992 in
  commit a213649d and threads through changes since.

- Added additional tests for time_t that run everywhere, including platforms
  where time_t is 32 bits.  Some of the tests added previously intentionally
  skip on those platforms, as they were validating proper 64-bit operation.
  This ensures adequate coverage everywhere.

- Fix a bug in which tests could fail when started locally with a controlling
  tty (as opposed to the CI environment which lacks that).

# C-Kermit 11.0.512

September 30, 2026

This is primarily a cleanup and maintenance release.  I have been adding
numerous tests in anticipation of more work reducing warnings on modern
toolchains, with the aim of having a good chance of catching any accidental
regressions.  Along the way, the tests and analysis have surfaced some bugs,
which have been fixed.

Additionally, due to being broken for over 25 years and the impracticality of
restoring support, I removed support for 16-bit Unix platforms from the
codebase.  This removed over 1900 lines of code from the project.  See further
notes in commit 30ab9d4f.  For instance, I had made a solid effort to get
C-Kermit to build again on 2BSD on PDP-11, but according to the historic notes,
C-Kermit 7 was already iffy on that platform, and the last real published
binaries were from C-Kermit 6.  Memory issues with the compiler, preprocessor,
and compiled binaries were significant and insurmountable without significantly
harming both the maintainability of the code and the featureset present on the
old platforms.

At the same time, I added the first 32-bit platform as part of CI, which is
32-bit Linux armhf.  This serves the twin goals of providing a useful binary
for platforms such as Raspberry Pi, and providing a measure of validation in CI
that we don't break things on 32-bit platforms.

Additional changes:

- Behavior change: In some cases, particularly when reliable isn't assumed,
  file names could be silently truncated if they were larger than would fit in
  a single packet.  Now, an error packet is generated and returned if the
  filename would require truncation.  This is an unusual case impacting files
  with very long names, so I don't think it likely anyone will notice this
  change, but it should avoid unpleasant surprises.

- Behavior change: rounding -0 now produces 0 instead of -0.

- Report `sizeof(time_t)` in `SHOW FEATURES` and associated regression test.
  Note 32-bit Linux platforms have transitioned to 64-bit `time_t`, but this is
  not universally true across the BSDs, so we don't require 64-bit `time_t` on
  every CI platform.

- Fix a number of time-related overflows.

- Fix a heap buffer overflow in getlocalipaddrs() and add associated test.
  64-bit platforms try to read 8 bytes from a 4-byte allocation.  However, on
  Linux at least, this isn't an exploitable security hole as `malloc()` on Linux
  allocates more than 8 bytes at a time anyhow.  The original bug was introduced
  when the code in question was written, in C-Kermit 7.0.197 of 2000, commit
  d0f8b1da7aea5bf3912e4289bfb23c988b0e7c60.

- Close pipe fds on exec where appropriate.  This prevents leakage and issues
  with failing to shut down.

- Added testing for `\fsexpression()` past 4GB.  Fixed `\fsexpression()` wrong
  results near the 2^53 double boundary, discovered by new tests.

- Fixed handling in cases where a filename length causes a packet to exceed
  the current packet size.

- Fixed invalid JPEG segment length handling in `\fpictureinfo()`

- Fixed `FILE COUNT` for files >2GB in size on platforms that support a 64-bit
  `CK_OFF_T`.  Platforms that don't support that won't support large file size
  reporting anyhow.

- Fix incorrect handling of file dates before 1970 or after 2106.

- Fix a `shxpand()` buffer overflow, detected with ASan.

- `SHOW TERMINAL` now properly will reflect `SET TERMINAL AUTODOWNLOAD ASK`
  on all platforms.

- Fix building unit tests on ppc64 platforms.

- Fix IPv6 tests on systems were /etc/hosts gives a name for ::1 that isn't
  localhost.
  
- Reject a `SEND AS-NAME` that doesn't fit in a buffer instead of leaking stack.

- Fixed an asan-detected issue in newerrmsg()

- When a `SEND` or `GET` switch is given more than once, fixed edge cases that
  could cause a double free.
  
- Used safer string generation for switch values and login names (`makestr()`
  instead of `malloc()` and `strcpy()`)

- Correct an obscure data corruption bug that could occur when a telnet command
  arrives at a certain buffer boundary.

- Several chunk length handling fixes in the HTTP client code:
  - Fixed a length truncation bug on 64-bit platforms and added a regression
    test for it.  The original bug was introduced in C-Kermit 8.0.200 of 2001,
    commit c88d9b8561c0c9babcb830522e7f521ce8898c04.
  - Use `CK_OFF_T` instead of `int` for the chunk size, causing 32-bit
    platforms to use a 64-bit size, enabling support for large chunks on
    32-bit platforms.
  - Fixed parsing the chunk size when an extension (beginning with a
    semicolon) follows it.  Previously, it would truncate a numeric digit.

- Added numerous additional tests:
  - Validating `off_t` and general large file (>2GB, >4GB) support on 32-bit
    and 64-bit platforms
  - For `DIR` and `DIR /SUMMARY` with files >4GB, including on 32-bit platforms
  - For `REGET` resuming files >4GB, validating encoding/decoding large file
    sizes in the Kermit protocol
  - Testing `\fsexpression()` past 4GB.
  - Added a test for telnet IAC negotiation.
  - Generally, many regression tests in preparation for work to remove
    -Wconversion warnings.
  - Tests for filename length, including the prompt in autodownload ask mode.
  - Tests for username length.
  - Testing `\fjoin` CSV quoting of a large field.
  - Testing `GET` handling of large patterns for `/MOVE-TO`, `/AS-NAME`,
    `/FILTER`, and `/EXCEPT` with large parameters.
  - Testing `SEND`, `CONNECT`, and `ADD SEND-LIST` with values >255 chars.
  - Test IKSD login with large username and password.
  - Direct telnet and FTP tests with supplied protocol data

# C-Kermit 11.0.511

September 19, 2026

- Continued the warning sweep begun with 11.0.509.  Addressed numerous -Wshadow
  warnings.

- CI: Allowed retrying of certain timing-dependent tests due to flakiness on Mac
  and OpenBSD.

- Tests: Set a 2-second timeout on IPv6 tests expected to fail.

# C-Kermit 11.0.510

September 17, 2026

- Refactor to reduce use of siglongjmp(), eliminating races

- Added `SET TCP CONNECT-TIMEOUT` to provide a new timeout for establishing a
  TCP connection, defaulting to 30 seconds.  This can be useful for scripts and
  tests.  The previous default was no timeout enforced by C-Kermit; setting this
  value to 0 will restore that behvior.

- Continued the warning sweep begun with 11.0.509.  Along the way, fixed these
  bugs:
  - A chmod failure was ignored when `SET ATTRIBUTE PROTECTION` is on.  Fixed in
    commit 4ddb464e1.  Bug dates back to C-Kermit 7.0.197 of 2000, commit
    d0f8b1da, when this code was introduced.

- Include time.h earlier in ckcnet.c to address compilation issue on Gentoo

# C-Kermit 11.0.509

August 20, 2026

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

- Converted tabs to spaces in the source.  Inconsistent use of tabs vs. spaces
  was causing confusion, for humans and also possibly for gcc with
  -Wmisleading-indentation.  This was done using the expand(1) command.

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

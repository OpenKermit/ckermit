# IPv6 in C-Kermit

C-Kermit introduced IPv6 support in version 11.0.

This support includes full IPv6 support for Kermit's own sockets (raw, telnet,
and SSL/TLS) as well as the FTP and HTTP clients.  The FTP client adds support
for EPRT and EPSV as necessary for IPv6.

## Notes on usage

`SET TCP ADDRESS-FAMILY` lets you configure whether to use IPv4, IPv6, or both
(the default).

When giving a string that contains an IP address and a port number separated
by colons, an IPv6 address (which itself contains colons) must be enclosed
in `[` and `]` brackets.  This mimics behavior in other situations (such as
URLs) where similar situations are encountered.  When a port number is not
expected, neither are brackets.

A new option `SET TCP ADDRESS6` exists as an analog to `SET TCP ADDRESS`,
letting you specify a local binding address for IPv6.

A link-local address (`fe80::/10`) is only meaningful together with a
zone identifying which interface it's on, since the same link-local
address can exist on every interface of a multihomed host at once.
Give the zone as a suffix on the address, separated by `%`: either an
interface name (`fe80::1%eth0`) or its numeric index (`fe80::1%2`).
Combined with the bracket-and-port syntax above, a full example looks
like:

    SET HOST [fe80::1%eth0]:23

`SET TCP ADDRESS6` accepts the same `%interface`/`%index` suffix, and
applies it to both outgoing connections and the IPv6 listening socket
(`SET HOST *`). Connecting to a link-local address with no zone at
all fails, since the kernel has no way to tell which interface to use.

## Areas where IPv6 is unsupported

Where additional libraries must be called differently for IPv6, these occur in
rarely-used corners of C-Kermit.  Supporting the many possible combinations of
system and library IPv6 support is complex, and we don't have an easy way to
instrument the test suite for them.  Therefore, these areas of the code remain
IPv4-only:

- Kerberos 4 (the wire protocol is incompatible with IPv6, so it will never
  suport IPv6)

- Some aspects of Kerberos 5 (such as `SET AUTHENTICATION KERBEROS5 ADDRESSES`)

- GSSAPI; IPv6 support requires different GSSAPI calls

- X11 forwarding will work across an IPv6 connection, but will always listen on
  an IPv4 socket locally.

- The SSL code doesn't yet support IPv6 literals in the SAN field.  SSL in
  general is IPv6-capable; this is an exceptionally rare edge case that adds
  complexity to the code that seemed not worth it in the end.
  
- rlogin has not been rigorously defined for IPv6 contexts and rlogin behavior
  is untested there, though may work.

# Author

- John Goerzen, July 2026

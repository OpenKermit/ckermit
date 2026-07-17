# C-Kermit on high latency links

Here I discuss using C-Kermit for links with very high latencies (measured in
minutes, hours, or even days).  This can include radio networks such as
[Meshtastic](https://meshtastic.org), satellite links, email as a carrier, etc.

Default C-Kermit is inappropriate for these settings because timeouts will cause
excessive retransmits within a few seconds.  However, C-Kermit is quite flexible
and can easily be configured for success in these situations.

The default timeout and retry values are far too aggressive for RTTs (round trip
times) of this scale.  They'll abort a transfer before an ACK (packet
acknowledgment) could arrive.  Tuning prevents that problem.

Also, for links carried over a reliable transport like TCP/IP, C-Kermit's
streaming mode can work around the timeout problem in a different way and is
active by default.

Very few network protocols are able to handle latency of this kind, but C-Kermit
is!


## Root causes of the issue

- The initial per-packet timeout `DMYTIM` defaults to 8 seconds.

- The default retry limit `MAXTRY` is 10 attempts per packet.  Once exceeded,
  the transfer is canceled.

- Therefore, with defaults, the first packet exchange gives up after roughly 10
  x 8 = 80 seconds. On a link with an RTT measured in minutes or hours, the
  transfer aborts long before any acknowledgment could arrive.

- `chktimo()` only stretches the timeout automatically for serial
  connections, based on line speed versus packet size.
  For network connections it does nothing; the
  8-second default stands until explicitly overridden.

- A dynamic RTT-based timer adapts the timeout starting with the 4th packet of a
  transaction. It starts from the same 8-second baseline and caps itself at
  roughly 3x a rolling estimate.  On a very long or bursty-latency link, this
  adaptation can shrink the timeout inappropriately once a filled pipeline
  starts delivering packets back to back, which is the opposite of the desired
  behavior.

## Tunable parameters

These parameters already exist and cover the problem; no new
tunables are needed.

### `SET SEND TIMEOUT`

This is a local, per-side timer controlling how long this Kermit waits before
deciding to resend. Setting it sets the local override flag `timef` to 1, which
makes this Kermit ignore whatever timeout value the other side requested and use
the local value instead

`CK_TIMERS` is compiled in by default, so this value has no protocol-imposed
ceiling; it can be set to hundreds or thousands of seconds. It can be fixed or
dynamic, with explicit minimum and maximum bounds in the dynamic case:

```
SET SEND TIMEOUT 3600 FIXED
```

or

```
SET SEND TIMEOUT 300 DYNAMIC 200 7200
```

`FIXED` is recommended over `DYNAMIC` on very high or variable-
latency links, since the adaptive algorithm can be misled once a
large window fills the pipe and packets start arriving in bursts.

### `SET RETRY`

Maximum retries per packet, 0 to 999.c:11843). A value of 0 means unlimited. Set
this generously, or to 0, so a transient loss does not abort the whole transfer.

### `SET WINDOW` and `SET PACKET-LENGTH`

`SET WINDOW n` (up to `MAXWS` = 32) and
`SET RECEIVE/SEND PACKET-LENGTH` (up to about 9042 bytes by default)
allow multiple outstanding packets instead of waiting for an ACK after each one. This
matters once RTT starts increasing.

[Current defaults](help-reference.md#set-protocol) are reasonable in many cases,
with the window set to 30, and packet lengths defaulting to 90 (send) and 4000
(receive).  However, when the underlying transport supports higher packet sizes, it may be helpful to set them at the outset rather than letting Kermit auto-tune to the higher sizes, since the auto-tuning process could take quite awhile to kick in with high RTTs.  Do that with:

```
SET RECEIVE PACKET-LENGTH 9024
SET SEND PACKET-LENGTH 9024
```

### SET RELIABLE and SET STREAMING

If the underlying path is a reliable transport (for example, TCP/IP), streaming
mode removes ACK-waiting and per-packet timeouts entirely, assuming the
underlying transport provides reliability.

Both RELIABLE and STREAMING [default to AUTO](help-reference.md#set-streaming).
This means streaming may already be active by default for a TCP-based path with
no configuration required.

If the long-latency path is serial or radio rather than TCP,
streaming does not activate automatically. Enabling it there requires
an explicit `SET RELIABLE ON`, and should only be done if the link is
trusted not to silently corrupt data. Deep space and HF radio type
links generally do not meet that bar, and should rely on tuned
`SEND TIMEOUT` / `RETRY` / `WINDOW` values instead.

## Wire protocol limit (not a bug, does not matter in practice)

`SET RECEIVE TIMEOUT`, the value one Kermit asks its peer to wait for packets
before resending, is capped at 0-94 seconds. This is because the value is
encoded as a single printable ASCII character in the Send-Init packet, per the
original Kermit protocol specification. This ceiling cannot be raised without
breaking wire compatibility.

It doesn't matter in practice since `SET SEND TIMEOUT` on each side takes
priority over whatever the peer requested.  So as long as both ends configure
`SET SEND TIMEOUT` locally, the 94-second field becomes irrelevant.

If you like to configure C-Kermit remotely, note that `SET SEND TIMEOUT` is a
local decision and cannot be pushed to a server-mode peer via `REMOTE SET`
beyond the 94-second field. `SET RETRY`, by contrast, can be pushed to a remote
server via `REMOTE SET RETRY`, since it is a generic server parameter rather
than a Send-Init field.

## Recommended configuration for a minutes/hours RTT link

Apply on both ends, since `SET SEND TIMEOUT` is local to each side:

```
SET SEND TIMEOUT <a few multiples of the expected one-way delay> FIXED
SET RETRY 0
SET WINDOW 32
SET RECEIVE PACKET-LENGTH 9024
```

If the path is actually carried over TCP/IP, even tunneled or
relayed, confirm `SET RELIABLE` and `SET STREAMING` are `AUTO` or
`ON` on both sides. This removes Kermit-level timeout math from the
transfer entirely and defers to the transport's own retransmission.

If the path is a raw, lossy channel with hour-scale delay rather than
TCP, streaming is not safe to enable, since delivery is not
guaranteed. In that case, rely on the tuned `SEND TIMEOUT` / `RETRY`
/ `WINDOW` combination above.

## See Also

[C-Kermit reference](help-reference.md)

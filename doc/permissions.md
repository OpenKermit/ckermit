# Permissions in C-Kermit

C-Kermit is somewhat unique in that it is both client and server software.
Also, because of the circumstances in which it operates, those distinctions are
sometimes harder to reason about.

# Background

The Kermit protocol is a generic protocol for performing actions on a remote
machine.  It can transfer files, delete or rename files, create and remove
directories, and so forth.  Think of it as a standardized alternative to using
ssh to connect to a remote and typing commands at the shell.

Kermit commands can flow in both directions on the protocol.  In the usual
setup, you are sitting at a workstation connecting to a server.  You want to
control the server, not let the server control you.  The defaults in C-Kermit
starting with 11.0 are designed to address risks from the possibility of a
malicious server, and are generally set to prevent the server from altering your
machine.

But right away you probably want to make exceptions.  It is really handy to run
`kermit -s filename.zip` on the server to send a file.  If your local Kermit is
in autodownload mode, that transfer begins immediately.  But you don't want a
remote Kermit to overwrite a local file.  And you probably don't want it to
place files outside the current working directory.  But then, a recursive
download from the remote, by nature, involves placing files in other
directories.  This is all configurable.

The set of permissions around this go back decades in C-Kermit.  Little has
changed with C-Kermit 11.0 except some defaults and tighter isolation to permit
recursive transfers to proceed while still blocking other directory-escaping
attempts.  C-Kermit 11.0 also adds output to `SHOW SERVER` to make it more clear
to you exactly what controls are operating at any given moment.

# Local/Remote Mode, ENABLE/DISABLE, and RECEIVE PATHNAMES

This discussion is primarily about commands sent using the Kermit protocol.

As you will see, we talk about local and remote mode.  There is a lot of detail
below, but broadly:

Kermit is in local mode when it is the one you are typing to using the keyboard
on the local machine.  Think of it as the controller.  You want it to be able to
control the remote, but not for the remote to be able to send Kermit commands to
it (with some limited exceptions as I hinted above).

Kermit is in local mode when it is the "far" end of the connection.  In that
mode, it is being controlled by the local machine.

So it follows that a Kermit in remote mode should allow a lot more kinds of
Kermit protocol commands than one in local mode.

We'll discuss three related settings:

- Local mode and remote mode: what they mean, and how a connection
  ends up in one or the other.
- ENABLE/DISABLE for CD, MKDIR, and other server capabilities,
  including the LOCAL/REMOTE/BOTH distinction.
- How SET RECEIVE PATHNAMES interacts with ENABLE/DISABLE CD and
  MKDIR to decide whether, and where, an incoming file with
  directory components in its name gets written.

This all matters for security. A recursive SEND or a server replying to
`GET /RECURSIVE` embeds relative directory paths in the filenames it transmits.
Getting these settings wrong can mean recursive transfers that mysteriously
fail, or a file landing somewhere you did not intend.

## Local mode vs. remote mode

C-Kermit's [manpage](manpage.pdf) defines it this way:

> Kermit is said to be in Local mode if it has made a connection to another
> computer, e.g. by dialing it or establishing a Telnet connection to it. The
> other computer is remote, so if you start another copy of Kermit on the remote
> computer, it is said to be in Remote mode (as long as it has not made any
> connections of its own).

Local mode means this copy of Kermit initiated the connection.

A Kermit started with no connection starts in remote mode.  But, since there is
no connection, there are no Kermit protocol commands, so the distinction is
meaningless at that point.

These put a connection into local mode:

- `SET HOST`, `SSH`, `TELNET`, `DIAL`, and similar commands that make
  an outbound connection, once the connection succeeds. Failed
  attempts leaves the mode unchanged.
- The `-F <fd>` startup option, which adopts an already-open
  connection, such as one handed to Kermit by inetd or systemd.
- `SET HOST * <port>`, which listens for n incoming
  TCP connection. See the exception below.

### Example: a client connecting to a server over SSH

Say you SSH from your workstation to `server1`, then, once logged in, type
`kermit` and `SERVER` by hand to start a Kermit server there.

Now, your workstation is in local mode. It made the connection.

Meanwhile, `server1` is in remote mode. That Kermit process never made or adopted
a connection; it is just reading commands from the terminal SSH gave it.

This is the modern version of the classic setup (using serial lines) C-Kermit
was designed around.  It's why  most server capabilities, including CD and
MKDIR, default to REMOTE rather than LOCAL or BOTH.

### The exception: `SET HOST *`

If a Kermit listens for and accepts connections with `SET HOST * <port>`, it is
in local mode, but permissions checks treat it as remote anyway. This keeps a
standalone C-Kermit listener working with the same REMOTE-only defaults as the
classic SSH-and-manually-started-server case above.

Connection shapes that matter in practice:

| Connection Method                                            | Mode   | Treated As |
|--------------------------------------------------------------|:------:|:----------:|
| Interactive login and manual `SERVER` command                | Remote | REMOTE     |
| `SET HOST *` (Kermit listens on TCP)                         | Local  | REMOTE     |
| `-F <fd>` (adopted socket such as inetd or IKSD)             | Local  | LOCAL      |
| Outbound client (`SET HOST`, `SSH`, `TELNET`)ide)            | Local  | LOCAL (usually moot, since this applies to whichever side *receives* a file) |

The first two rows are both treated as REMOTE, so a manually started server and
a `SET HOST *` listener both work with C-Kermit's out-of-the-box defaults
unmodified. The third row, an adopted connection, is the exception: it is
treated as LOCAL, so its default REMOTE-only capabilities behave as disabled
until you enable them for LOCAL or BOTH. If you run Kermit this way and
recursive uploads are refused, that is why.

### Mode Verification

`SHOW SERVER` reports all of this, alongside the per-capability settings:

```
Connection mode:      Local
Incoming TCP accept:  Yes
Governing ENABLE bit: REMOTE
Internet server:      No
```

- **Connection mode**: local or remote.
- **Incoming TCP accept**: whether this connection came from a
  `SET HOST *` listener.
- **Governing ENABLE bit**: Indicates whether `LOCAL` or `REMOTE` are the
  effective rules for this connection.  Read this line if you only want the
  bottom line. In the example above, this is a `SET HOST *` listener: local
  mode, but governed by REMOTE.
- **Internet server**: whether this is an IKSD (Internet Kermit
  Service Daemon) session.

From a script, `IF LOCAL` reports the same mode:

```
if local echo Local, if not local echo Remote
```

`IF LOCAL` cannot distinguish a `SET HOST *` listener from an adopted
connection; both report local mode. Only `SHOW SERVER`'s "Governing
ENABLE bit" line makes that distinction.

### Startup Order Considerations

Evaluating `SHOW SERVER` or `IF LOCAL` from a startup init file
(`-y <file>`) can report a stale answer; connection-establishing
startup options such as `-F` are applied later in startup, after the
init file has already run. This happens regardless of the order
`-F` and `-y` appear on the command line.

To accurately check the connection mode, do so from a command-line action
(`-C`), the interactive prompt, or a script run after startup. All of these run
after every startup option has taken effect.

## ENABLE and DISABLE

```
ENABLE capability [ LOCAL | REMOTE | BOTH ]
DISABLE capability [ LOCAL | REMOTE | BOTH ]
```

Server capabilities (such as `CD`, `MKDIR`, `DELETE`, `SEND`, and `GET`) are
configured independently for `LOCAL`, `REMOTE`, `BOTH`, or neither. `LOCAL` and
`REMOTE` are separate settings. Permission evaluation depends on the governing
mode of the active connection.

Most capabilities, including `CD` and `MKDIR`, default to `REMOTE`. For adopted
connections (`-F`), enabling capabilities across both modes (`ENABLE CD BOTH`,
`ENABLE MKDIR BOTH`) grants permissions regardless of connection origin.  This
is a useful step if, for instance, a server using an adopted connection refuses
recursive uploads.


### Applicability of Capability Rules

`ENABLE` and `DISABLE` settings govern incoming protocol requests sent using the
Kermit protocol. They do not normally restrict interactive commands entered
directly at the local Kermit prompt.

Continuing the SSH example: you SSH to `server1`, then type `kermit` there.

- Typing `DELETE somefile` executes that command. `DISABLE DELETE`
  has no effect, because you are running the command yourself, not
  asking the server to do it over the protocol.
- Typing `SERVER` changes this. Kermit now waits for protocol
  requests from whatever is connected to it. A `REMOTE DELETE
  somefile` sent from your workstation is checked against
  `ENABLE`/`DISABLE DELETE`.

So ENABLE/DISABLE controls what a connected Kermit peer may ask this server to
do using the Kermit protocol, not what commands this process can run.

### Permissions Enforcement in IKSD

IKSD supports both the Kermit CLI and the Kermit protocol.  If its CLI worked
the same way as regular Kermit above, ENABLE/DISABLE would be pointless there;
anyone could type `DELETE anything` without ever typing `SERVER`.

To prevent this, an IKSD session checks ENABLE/DISABLE for interactive commands
too, from the moment the session starts, not only once `SERVER` is typed. This
covers CD, DELETE, PURGE, overwriting an existing file during a transfer, and
MKDIR/RMDIR.  IKSD also disables MAIL, REMOTE WHO, REMOTE HOST, and PRINT for
every session, and blocks outbound connections (`SET HOST`, `SSH`, and similar)
from within it.

The same `ENABLE CD`/`ENABLE DELETE` settings that govern protocol requests on
an ordinary server also govern what an anonymous IKSD user can type directly at
the prompt. An anonymous archive, for instance, needs `CD`.

## RECEIVE PATHNAMES Interaction with `CD` and `MKDIR`

`SET RECEIVE PATHNAMES { OFF, RELATIVE, ABSOLUTE, AUTO }` controls what happens
when an incoming filename includes directory components, something a recursive
`SEND`, or a recursive reply to `GET /RECURSIVE`, does routinely.

A `..` path segment anywhere in the incoming name is rejected, with "Access
denied," under every mode except ABSOLUTE.  This rejection happens before any
mode-specific handling, so OFF and RELATIVE do not "clean up" a `..`; it never
reaches them.

With that rejection aside, path modes operate like this:

- **OFF**: Strip all directory components (including leading `/` or `~`),
  retaining only the base filename.
- **RELATIVE**: honor the directory structure, but confine it to a
  descendant of your current directory. A leading `/`
  or `~` is neutralized rather than rejected.
- **ABSOLUTE**: Retain the complete incoming path without modification,
  including leading `/` and `..` segments. Use only with trusted senders.
- **AUTO** (default): behaves as RELATIVE if the sender indicates
  this is a recursive transfer, otherwise as OFF.

A separate, unrelated permission check can also refuse a file with "Write access
denied." Before any mode-specific handling runs, C-Kermit checks whether the
raw, unmodified incoming name would be writable. An absolute name pointing
somewhere you lack permission to write, such as `/etc/whatever`, can be refused
even though `OFF` or `RELATIVE` would otherwise have safely confined or stripped
it.

### Server Mode Path Restrictions: ENABLE/DISABLE `CD` and `MKDIR`


Only when receiving files in server mode, `ENABLE CD` and `ENABLE MKDIR` provide
an initial gating mechanism prior to `SET RECEIVE PATHNAMES` processing:

- **CD** controls whether an arriving filename with a directory
  component is accepted at all. If not, the transfer is refused with
  "Access denied," before RECEIVE PATHNAMES is even consulted.
- **MKDIR**: Controls whether required target subdirectories can be created.
  If disabled, transfers requiring directory creation fail with "Directory
  creation failure".

In non-server client receives, which is the common case for an ordinary client,
`ENABLE CD` and `ENABLE MKDIR` checks do not apply. `SET RECEIVE PATHNAMES`
alone dictates target file locations.

In short, for a plain client receive, ```SET RECEIVE PATHNAMES`` (default AUTO)
confines the file to a descendant of your current or download directory.

And for a Kermit SERVER receiving an upload with directory
components:

- `ENABLE CD` controls whether an embedded path is accepted
- `ENABLE MKDIR` controls whether needed subdirectories can be created
- `SET RECEIVE PATHNAMES` controls where files are put after being accepted


## See also

- `HELP SET RECEIVE PATHNAMES`, `HELP ENABLE`, `HELP GET`, `HELP SEND`
- `HELP SET SERVER`, `SHOW SERVER`

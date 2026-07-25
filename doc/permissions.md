# Permissions in C-Kermit

C-Kermit is somewhat unique in that it is both client and server software.
Also, because of the circumstances in which it operates, those distinctions are
sometimes harder to reason about.

The Kermit protocol not only supports transfer of files, but it is also a
generic protocol for performing actions on a remote machine.  It can delete or
rename files, create and remove directories, and so forth.  Think of it as a
standardized alternative to using ssh to connect to a remote and typing commands
at the shell.

Kermit commands can flow in both directions on the protocol.  In the usual
setup, you are sitting at a workstation connecting to a server.  You want to
control the server, not let the server control you.  The defaults in C-Kermit
starting with 11.0 are designed to address risks from the possibility of a
malicious server, and are generally set to prevent the server from altering your machine.

But right away you probably want to make exceptions.  It is really handy to run
`kermit -s filename.zip` on the server to send a file.  If your local Kermit is
in autodownload mode, that transfer begins immediately.  But you don't want a
remote Kermit to overwrite a local file.  And you probably don't want it to
place files outside the current working directory.  But then, a recursive
download from the remote, by nature, involves placing files in other
directories.

The set of permissions around this go back decades in C-Kermit.  Little has
changed with C-Kermit 11.0 except some defaults and some tighter isolation to
permit recursive transfers to proceed while still blocking other
directory-escaping attempts.  C-Kermit 11.0 also adds output to `SHOW SERVER` to
make it more clear to you exactly what controls are operating at any given
moment.

# Scope of our discussion

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
Kermit commands than one in local mode.

# Local/Remote Mode, ENABLE/DISABLE, and RECEIVE PATHNAMES

This page covers three related settings:

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

Local mode means this copy of Kermit initiated the connection. It is not a
statement about physical location or transport.

A freshly started `kermit`/`wermit` process with no connection starts in remote
mode.  But, since there is no connection, there are no Kermit protocol
commands, so the distinction is meaningless at that point.

These put a connection into local mode:

- `SET HOST`, `SSH`, `TELNET`, `DIAL`, and similar commands that make
  an outbound connection, once the connection succeeds. A failed
  attempt leaves the mode unchanged.
- The `-F <fd>` startup option, which adopts an already-open
  connection, for example one handed to Kermit by inetd or a similar
  internet-service supervisor.
- `SET HOST * <port>`, which listens for and accepts an incoming
  connection. See the exception below.

### Example: a client connecting to a server over SSH

Say you SSH from your workstation to `server1`, then, once logged in, type
`kermit` and `server` by hand to start a Kermit server there.

- Your workstation is in local mode. It made the connection.
- `server1` is in remote mode. That Kermit process never made or
  adopted a connection; it is just reading commands from the
  terminal SSH gave it.

This is why most server capabilities, including CD and MKDIR, default to REMOTE
rather than LOCAL or BOTH: this is the standard setup C-Kermit was designed
around.

### The exception: `SET HOST *`

If, instead of logging in and typing `kermit` by hand, the far end is a Kermit
process that listens for and accepts your connection with `SET HOST * <port>`,
it is in local mode too, but permissions checks treat it as remote anyway. This
keeps a standalone C-Kermit listener working with the same REMOTE-only defaults
as the classic SSH-and-manually-started-server case above.

Connection shapes that matter in practice:

| How the connection was made                                | Mode  | Treated as |
|--------------------------------------------------------------|:---:|:---:|
| Logged in some other way, then typed `kermit`/`server` by hand | Remote | REMOTE |
| `SET HOST *` (Kermit itself listens and accepts)            | Local | REMOTE |
| `-F <fd>` (an already-connected socket handed to Kermit, e.g. by inetd or an IKSD-style internet service) | Local | LOCAL |
| `SET HOST`/`SSH`/etc. (outbound, the client side)            | Local | LOCAL (usually moot, since this gate applies to whichever side *receives* a file) |

The first two rows are both treated as REMOTE, so a manually started server and
a `SET HOST *` listener both work with C-Kermit's out-of-the-box defaults
unmodified. The third row, an adopted connection, is the exception: it is
treated as LOCAL, so its default REMOTE-only capabilities behave as disabled
until you enable them for LOCAL or BOTH. If you run Kermit this way and
recursive uploads are refused, that is why.

### Checking which mode applies

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
- **Governing ENABLE bit**: LOCAL or REMOTE, whichever one
  ENABLE/DISABLE actually consults for this connection. Read this
  line if you only want the bottom line. In the example above, this
  is a `SET HOST *` listener: local mode, but governed by REMOTE.
- **Internet server**: whether this is an IKSD (Internet Kermit
  Service) session.

From a script, `IF LOCAL` reports the same mode:

```
if local echo Local, if not local echo Remote
```

`IF LOCAL` cannot distinguish a `SET HOST *` listener from an adopted
connection: both report local mode. Only `SHOW SERVER`'s Governing
ENABLE bit line makes that distinction.

### Startup order surprises

Checking `SHOW SERVER` or `IF LOCAL` from a startup init file
(`-y <file>`) can report a stale answer; connection-establishing
startup options such as `-F` are applied later in startup, after the
init file has already run. This happens regardless of the order
`-F` and `-y` appear on the command line.

Check connection mode instead from a command-line action (`-C`), the
interactive prompt, or a script run after startup. All of these run
after every startup option has taken effect.

## ENABLE and DISABLE

```
ENABLE capability [ LOCAL | REMOTE | BOTH ]
DISABLE capability [ LOCAL | REMOTE | BOTH ]
```

Each server capability, such as CD, MKDIR, DELETE, SEND, or GET
(`SHOW SERVER` lists them all), is independently enabled for LOCAL,
REMOTE, BOTH, or neither. LOCAL and REMOTE are independent settings,
not two ends of one scale. "Is CD enabled" is the wrong question;
"is CD enabled for this connection's mode" is the right one.

Most capabilities, including CD and MKDIR, default to REMOTE only.  If a server
deployed as an adopted connection refuses recursive uploads, `ENABLE CD BOTH`
and `ENABLE MKDIR BOTH` constitute the simplest fix since they allow the
capability regardless of connection mode.

### When do these rules apply?

ENABLE/DISABLE governs commands that arrive over the Kermit protocol from a
connected peer.  It does not govern commands you type yourself.

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

### Does IKSD permit the same things?

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
the prompt. An anonymous archive needs CD, and, for anything uploadable, MKDIR,
enabled for whichever mode its deployment counts as (see the connection-shape
table above). That is a deliberate choice by the site operator, not a gap in the
check.

## RECEIVE PATHNAMES, and how it interacts with CD and MKDIR

`SET RECEIVE PATHNAMES { OFF, RELATIVE, ABSOLUTE, AUTO }` controls what happens
when an incoming filename includes directory components, something a recursive
SEND, or a recursive reply to `GET /RECURSIVE`, does routinely.

A `..` path segment anywhere in the incoming name is rejected outright, with
"Access denied," under every mode except ABSOLUTE.  This rejection happens
before any mode-specific handling, so OFF and RELATIVE do not "clean up" a `..`;
it never reaches them.

With that rejection aside, each mode handles the remaining path as follows:

- **OFF**: keep only the base filename. Discard any directory part,
  including a leading `/` or `~`.
- **RELATIVE**: honor the directory structure, but confine it to a
  descendant of your current or download directory. A leading `/`
  or `~` is neutralized rather than rejected or stripped.
- **ABSOLUTE**: honor the incoming pathname exactly as given,
  leading `/` and `..` included. This is an explicit statement of
  trust in the sender. Use it only when you trust the sender as much
  as you would trust a local `cp` command run with the same
  argument.
- **AUTO** (the default): behaves as RELATIVE if the sender signals
  in advance that this is a recursive transfer, otherwise as OFF.
  This is why an ordinary recursive SEND or GET already lands safely
  with no configuration: AUTO's protections apply automatically and
  do not depend on server mode or ENABLE CD.

A separate, unrelated permission check can also refuse a file with "Write access
denied." Before any mode-specific handling runs, C-Kermit checks whether the
raw, unmodified incoming name would be writable. An absolute name pointing
somewhere you lack permission to write, such as `/etc/whatever`, can be refused
even though OFF or RELATIVE would otherwise have safely confined or stripped it.

### Where ENABLE/DISABLE CD and MKDIR fit in

CD and MKDIR are a separate, earlier gate that applies in the context of
receiving files only while running as a Kermit SERVER:

- **CD** controls whether an arriving filename with a directory
  component is accepted at all. If not, the transfer is refused with
  "Access denied," before RECEIVE PATHNAMES is even consulted.
- **MKDIR** controls, independently, whether the subdirectories a
  recursive transfer needs may actually be created. A file can pass
  the CD check and still fail with "Directory creation failure" if
  MKDIR is not also enabled.

Outside server mode, the common case for an ordinary client receiving someone
else's recursive SEND, or running `GET /RECURSIVE`, neither CD nor MKDIR
applies. RECEIVE PATHNAMES alone decides where the file goes.

In short, for aplain client receive, ```SET RECEIVE PATHNAMES`` (default AUTO)
confines the file to a descendant of your current or download directory.

And for a Kermit SERVER receiving an upload with directory
components:

- `ENABLE CD` controls whether an embedded path is accepted at all
- `ENABLE MKDIR` controls whether needed subdirectories can be create
- `SET RECEIVE PATHNAMES` controls where files are put after being accepted


## See also

- `HELP SET RECEIVE PATHNAMES`, `HELP ENABLE`, `HELP GET`, `HELP SEND`
- `HELP SET SERVER`, `SHOW SERVER`

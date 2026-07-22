# Introduction to C-Kermit

*This is a modified version of the page I initially published at <https://www.complete.org/kermit/> in August 2023.  I have lightly revised it for use here. - John Goerzen, July 2026*

C-Kermit is one of those things I'm fond of that's really hard to describe.  It
is:

-   A file transfer protocol for running over serial lines, [modems](https://www.complete.org/modem/), or TCP/IP.  The protocol is quite flexible, supporting everything from tiny embedded devices with 90-byte packets to large packets and streaming over ssh.
-   A FTP- or SFTP-like system-agnostic protocol for looking at directories of files on remote systems, renaming files, deleting them, etc. with a standard interface.
-   Capable of operating under extremely challenging conditions, including 7-bit connections, connections that otherwise "eat" certain characters, and [very high latency connections](high-latency.md).
-   A modem dialer.
-   A fully-functional standalone TCP server.
-   A system for inband communication over a single connection.
-   On Windows, a terminal emulator.  (On Linux/Mac/BSD, it runs within a terminal emulator already, so doesn't need to provide that functionality).
-   A thin wrapper around ssh providing new features.
-   A scripting engine, which can be used to automate terminal interaction, file transfer, and more.  There are some pretty neat [kermit scripts](scripting.md) out there - everything from renaming JPEGs based on embedded metadata to budgeting.
-   It's also a Telnet, SSH, FTP, and HTTP(S) client.

You can [download kermit for hundreds of platforms](https://www.openkermit.org/downloads/), many of which are decades out of date.  They all interoperate.  It is rather impressive.  In fact, a new version of [Kermit for TOPS-20](https://kermitproject.org/kermit-20.html) was released in 2024!  (TOPS-20 was active between 1976 and 1988).  C-Kermit, which this page describes, began in 1985 and, through the [Open Kermit project](https://www.openkermit.org/), still is active today.

There are many Kermit implementations; this page is primarily about C-Kermit, the most up-to-date and featureful implementation for \*nix.  For many years, C-Kermit wasn't fully open-source, but since 2011, has been released under a BSD license.

I operate the [quux.org Kermit Server](https://www.complete.org/quux-org-kermit-server/) - open to the public for you to experiment with!

The [extensive documentation](https://www.openkermit.org/doc/) gives  gives a
lot of detail about the program.

I also wrote about Kermit in my article [Try the Last Internet Kermit Server](https://www.complete.org/try-the-last-internet-kermit-server/) from 2024.


## Quick tour: as a ssh wrapper {#quick-tour-as-a-ssh-wrapper}

You can very easily use something like this:

```text
kermit -C 'ssh user@host'
```

Now, you are logged in to the remote host, using the same OpenSSH you always use.  You can happily do all your work as usual.  Now let's say you're at the shell, you've been editing a file on the remote end, and you'd like to copy it to your local machine.

In a traditional setup, you'd open a new local window, then have to copy the full path name and run scp to bring it across.  With Kermit, you can just type this at your shell prompt:

```text
kermit -Iis filename.tar.gz
```

It will send a special byte sequence that your local kermit will pick up on, and enter transfer mode.  The file will be transferred, complete with integrity checking.  Then you'll be right back at your shell.

You can even send directories:

```text
cd /usr/share/doc
kermit -Ii -C 'send /recursive libthreadar-dev, exit'
```

Here we gave a short Kermit script with `-C`.  `send` is a Kermit command, and this tells it to send the file, then exit.

You can [read much more about C-Kermit with ssh](ssh.md).  This is particularly helpful if you often ssh from one host to another, run things under sudo, etc; since Kermit runs inband with the data stream for your terminal, it is just as easy to transfer files from 4 shells deep as it is here.

## Kermit Modes {#kermit-modes}

Kermit has these modes:

-   Command mode.  This is a command-line interface and should be familiar to people that are used to the traditional FTP client, or to CLIs on things like routers and firewalls, or shells.  You can use commands like `cd` and `dir` to view files on your local system, or `remote cd` (aka `rcd`), `rdir`, etc. to view files on the local system.  Commands like `get` and `send` transfer files.  This is similar to the mode you get when you press Ctrl-] in telnet.  If you just invoke `kermit` with no parameters, you are in command mode.
-   Connect mode.  In this mode, you are connected to the remote system.  When you are in command mode and run `ssh somehost`, you will automatically be put into connect mode.  This is very much like the mode you are in when you type `ssh somehost` at the shell.
-   Server mode.  In this mode, kermit is waiting for Kermit protocol commands from the remote.  These commands might include things like listing directories, transferring files, etc.
-   Transfer mode.  This mode happens when a file is actively being transferred.

You can flip between modes:

-   When in command mode, if you have an active connection, just type `c` and hit return to go back to connect mode.  Or, use a command like `SSH`, `TELNET`, `SET HOST`, etc. to establish a connection.
-   When in connect mode, press Ctrl-Backslash and then hit `c` to return to command mode.  Ctrl-Backslash in kermit is very similar to the `RET ~` in OpenSSH; you can press `Ctrl-\ ?` to see other connect-mode actions.
-   You can explicitly enter server mode by running `kermit -x`, typing the `server` command while in command mode.

Kermit also has a feature where it will automatically start server mode on the remote.  Here's an example:

```text
jgoerzen@hephaestus:/tmp/t$ kermit
C-Kermit 11.0.499, 2026/07/16, for Linux+SSL (64-bit)
 Copyright (C) 1985, 2025,
  Trustees of Columbia University in the City of New York.
 Copyright (C) 2025-2026, John Goerzen
 Open Source 3-clause BSD license since 2011.
Type ? or HELP for help.
(/tmp/t/) C-Kermit>
```

OK, I've launched kermit.  Here I am in command mode with my local user.  Let's ssh to the remote; that will put me into connect mode:

```text
(/tmp/t/) C-Kermit>ssh auxuser@localhost
Connecting via command "ssh -e none auxuser@localhost"
 Escape character: Ctrl-\ (ASCII 28, FS): enabled
Type the escape character followed by C to get back,
or followed by ? to see other options.
----------------------------------------------------
auxuser@hephaestus:~$
```

OK, now I'm in connect mode.  I can send a file:

```text
auxuser@hephaestus:~$ kermit -Iis /bin/sh
Return to your local Kermit and give a RECEIVE command.

KERMIT READY TO SEND...
----------------------------------------------------
----------------------------------------------------
 SENT: [/usr/bin/dash] To: [/tmp/t/sh] (OK)

auxuser@hephaestus:~$
```

I didn't actually have to give the RECEIVE command, because my local kermit saw the special sequence to initiate a transfer, and automatically jumped into transfer mode.

Incidentally, C-Kermit commands are case-insensitive.  By convention going back decades, they are usually written in uppercase in documentation, but you can type them however you want at the prompt.  In this page, I normally type them in lowercase in the terminal but reference them in uppercase in the documentation.

(If you are using an underlying filesystem that is case-sensitive, filenames will still be case-sensitive; I'm just talking about command and parameter names here.)

Now let's go into command mode and do some stuff.  I'll hit Ctrl-\\ and then press c.

```text
(/tmp/t/) C-Kermit>rpwd
/home/auxuser
```

So we see the current working directory on the remote.  But wait a minute, `RPWD` (aka `REMOTE PWD`) uses the kermit protocol, but at the remote I was just at the shell.  What happened?

Kermit was smart enough to know there wasn't a kermit connection running, so it just sent `kermit -x` to the remote, placing it in server mode.  Clever!

I can even do something like this:

```text
(/tmp/t/) C-Kermit>get /usr/bin/bzip2
```

Since all these transfers are on my local machine, they're so fast I don't even see the transfer-in-progress status screen.  Rest assured it does exist and you'll see it on slower connections.

Now, I could type `CONNECT` (or just `C`) to return to the remote.  But the remote is in server mode, so I'd be greeted by silence if I did that.  I have two ways to get the remote out of server mode:

1.  I could just connect and send a few Ctrl-Cs
2.  I can send the `FINISH` (or just `F`) command before returning.

Let's do the second:

```text
(/tmp/t/) C-Kermit>finish
(/tmp/t/) C-Kermit>c
Connecting via command "ssh -e none auxuser@localhost"
 Escape character: Ctrl-\ (ASCII 28, FS): enabled
Type the escape character followed by C to get back,
or followed by ? to see other options.
----------------------------------------------------

C-Kermit server done

auxuser@hephaestus:~$ history | tail -n 3
  799  kermit -Iis /bin/sh
  800  kermit -x
  801  history | tail -n 3
```

Look at that - it's the `kermit -x` invocation right there in history even.


## Kermit in Kermit {#kermit-in-kermit}

You can of course do something like this:

1.  Fire up local `kermit`
2.  Run `ssh hostname`
3.  While you're in ssh over there, fire up `kermit` on the remote.  Now, when you're in connect mode, you're sending commands to the remote kermit, and when you're in command mode, you're sending commands to the local kermit.  Potentially confusing -- and also potentially useful.

This is what you will encounter if you use the [quux.org Kermit Server](https://www.complete.org/quux-org-kermit-server/) - try it out!


## Performance {#performance}

These settings make kermit fast over a reliable (ssh, etc) connection.  You can add them to your `~/.kermrc` if you never need to use unreliable serial links:

```text
set reliable on
set clearchannel on
set receive packet-length 9000
set window 32
set control unprefix all
set transfer slow-start off
```


## Security {#security}

The Kermit protocol can work in either direction.  Prior to C-Kermit 11.0, this was enabled by default.  As of C-Kermit 11.0, the default is now such that the local can control the remote, not vice-versa.

For Kermit versions prior to 11.0, if you connect to untrusted remote systems, I recommend running `disable all` to prevent the remote from doing much to your local system other than sending files.  For instance, `rcd` is enabled by default and allows the remote to change the directory for you to receive files.

## Further reading

The guide on [ssh over Kermit](ssh.md) is effectively part 2 of this tour.  It gives useful context even if you don't intend to run Kermit over ssh.

See the [documentation pages](https://www.openkermit.org/doc/).

The older [Kermit Project's C-Kermit Tutorial](https://www.kermitproject.org/ckututor.html) is also still highly relevant and will take you down some additional paths.

# Author

John Goerzen, July 2026.

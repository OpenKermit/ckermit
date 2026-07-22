# C-Kermit over ssh

This page demonstrates how helpful it can be to run C-Kermit as a wrapper over ssh.

Please read the [Introduction and Tour](intro.md), and especially the [ssh
section of the intro](intro.md#quick-tour-as-a-ssh-wrapper), before continuing.
That sets out some background that will be helpful for this conversation.

We'll look into two common examples: nested ssh, and tar over Kermit.

## Nested ssh

Let's look at a situation many of us face frequently: sshing to one host, then from there to another, and from there maybe sudo to another account.  It can be quite difficult to make scp or rsync work across all of this, and if you even can, time-consuming to set up.

Since the Kermit protocol runs in-band with your terminal session, you can exchange files from anywhere you might be.

Let's open a nested connection.

```text
jgoerzen@zephyr:/tmp/t$ kermit -C 'ssh -A erwin'
C-Kermit 10.0.416 Beta.12, 2025/03/22, for Linux+SSL (64-bit)
 Copyright (C) 1985, 2025,
  Trustees of Columbia University in the City of New York.
  Open Source 3-clause BSD license since 2011.
Type ? or HELP for help.
Connecting via command "ssh -e none -A erwin"
 Escape character: Ctrl-\ (ASCII 28, FS): enabled
Type the escape character followed by C to get back,
or followed by ? to see other options.
----------------------------------------------------
jgoerzen@erwin:~$ ssh -e none alexandria
jgoerzen@alexandria:~$ su -
Password: 
root@alexandria:~# 
```

OK, so far this is normal.

I want to note the use of `-e none` in the ssh command line.  By default, ssh intercepts the tilde character `~` for its own purposes, which can interfere with Kermit file transfers (especially those towards the remote).  `-e none` tells ssh to present a clean connection, which is what we need.  When you run the SSH command from the Kermit command prompt (or via `kermit -C`), kermit uses the value set for `SET SSH COMMAND` to know what to run.  The default for that is `ssh -e none`, so when you type `ssh` at kermit, it automatically adds the `-e none`.

When I manually jumped from one host to the next, I had to add that manually to make sure I maintained a clean connection.  You can easily automate this in ~/.ssh/config.

Now let's say all of a sudden we'd like to get a copy of a file only root on alexandria can read.  Let's pretend that file is `/bin/bash`.  We can send that all the way back to our local kermit on zephyr with one command:

```text
root@alexandria:~# kermit -Iis /bin/bash
Return to your local Kermit and give a RECEIVE command.

KERMIT READY TO SEND...
----------------------------------------------------
----------------------------------------------------
 SENT: [/usr/bin/bash] To: [/tmp/t/bash] (OK)
```

Boom.  That easy!

We can do the opposite also.  Let's say we want to receive a file on alexandria.  In order to do this, we'll press Ctrl-Backslash and then hit `c` to go to the Kermit command line back on the local machine (zephyr).  Then we'll give the command to send a file.  The local kermit knows the remote isn't already running kermit, so gives the shell instructions to start it to receive the file.

```text
root@alexandria:~# 
                       [[ here I type Ctrl-\ C ]]
(Back at zephyr.lan.complete.org)
----------------------------------------------------
(/tmp/t/) C-Kermit>send /bin/grep
(/tmp/t/) C-Kermit>
```

There we go - /bin/grep sent all the way across the link.

Since I was in Kermit command-line mode, I remain there.  I can type CONNECT or C (it's case-insensitive) to return to the shell prompt on alexandria.  Let's do that, and inspect the file there.

```text
c    
Connecting via command "ssh -e none -A erwin"
 Escape character: Ctrl-\ (ASCII 28, FS): enabled
Type the escape character followed by C to get back,
or followed by ? to see other options.
----------------------------------------------------

root@alexandria:~# ls -l grep
-rwxr-xr-x 1 root root 203152 Jan  4  2024 grep
```

The "Connecting via command" string doesn't mean it's establishing a new connection; it's re-entering the session you already established, and reminding you how it was established.  Anyhow, we can see the file was transferred properly.

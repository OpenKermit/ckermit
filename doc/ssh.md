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
jgoerzen@workstation:/tmp/t$ kermit -C 'ssh -A server1'
C-Kermit 10.0.416 Beta.12, 2025/03/22, for Linux+SSL (64-bit)
 Copyright (C) 1985, 2025,
  Trustees of Columbia University in the City of New York.
  Open Source 3-clause BSD license since 2011.
Type ? or HELP for help.
Connecting via command "ssh -e none -A server1"
 Escape character: Ctrl-\ (ASCII 28, FS): enabled
Type the escape character followed by C to get back,
or followed by ? to see other options.
----------------------------------------------------
jgoerzen@server1:~$ ssh -e none server2
jgoerzen@server2:~$ su -
Password: 
root@server2:~# 
```

OK, so far this is normal.

I want to note the use of `-e none` in the ssh command line.  By default, ssh intercepts the tilde character `~` for its own purposes, which can interfere with Kermit file transfers (especially those towards the remote).  `-e none` tells ssh to present a clean connection, which is what we need.  When you run the SSH command from the Kermit command prompt (or via `kermit -C`), kermit uses the value set for `SET SSH COMMAND` to know what to run.  The default for that is `ssh -e none`, so when you type `ssh` at kermit, it automatically adds the `-e none`.

When I manually jumped from one host to the next, I had to add that manually to make sure I maintained a clean connection.  You can easily automate this in ~/.ssh/config.

Now let's say all of a sudden we'd like to get a copy of a file only root on server2 can read.  Let's pretend that file is `/bin/bash`.  We can send that all the way back to our local kermit on workstation with one command:

```text
root@server2:~# kermit -Iis /bin/bash
Return to your local Kermit and give a RECEIVE command.

KERMIT READY TO SEND...
----------------------------------------------------
----------------------------------------------------
 SENT: [/usr/bin/bash] To: [/tmp/t/bash] (OK)
```

Boom.  That easy!

We can do the opposite also.  Let's say we want to receive a file on server2.  In order to do this, we'll press Ctrl-Backslash and then hit `c` to go to the Kermit command line back on the local machine (workstation).  Then we'll give the command to send a file.  The local kermit knows the remote isn't already running kermit, so gives the shell instructions to start it to receive the file.

```text
root@server2:~# 
                       [[ here I type Ctrl-\ C ]]
(Back at workstation.aaa.aaa.aaa)
----------------------------------------------------
(/tmp/t/) C-Kermit>send /bin/grep
(/tmp/t/) C-Kermit>
```

There we go - /bin/grep sent all the way across the link.

Since I was in Kermit command-line mode, I remain there.  I can type CONNECT or C (it's case-insensitive) to return to the shell prompt on server2.  Let's do that, and inspect the file there.

```text
c    
Connecting via command "ssh -e none -A server1"
 Escape character: Ctrl-\ (ASCII 28, FS): enabled
Type the escape character followed by C to get back,
or followed by ? to see other options.
----------------------------------------------------

root@server2:~# ls -l grep
-rwxr-xr-x 1 root root 203152 Jan  4  2024 grep
```

The "Connecting via command" string doesn't mean it's establishing a new connection; it's re-entering the session you already established, and reminding you how it was established.  Anyhow, we can see the file was transferred properly.

## Tar (and other piped commands) over Kermit

This is fine for one file, but you can take it further.  You can actually pipe commands over Kermit.  While Kermit does have a recursive send itself, let's say you want to send a directory as a tar file.

```text
jgoerzen@workstation:~/tmp/t$ kermit -C 'ssh server2'
C-Kermit 11.0.499, 2026/07/16, for Linux+SSL (64-bit)
 Copyright (C) 1985, 2025,
  Trustees of Columbia University in the City of New York.
 Copyright (C) 2025-2026, John Goerzen
 Open Source 3-clause BSD license since 2011.
Type ? or HELP for help.
Connecting via command "ssh -e none server2"
 Escape character: Ctrl-\ (ASCII 28, FS): enabled
Type the escape character followed by C to get back,
or followed by ? to see other options.
----------------------------------------------------
jgoerzen@server2:~$ cd /usr
jgoerzen@server2:/usr$ kermit -Ii -C 'SEND /COMMAND "tar -zcf - bin 2>/dev/null" bin.tar.gz , quit'
C-Kermit 11.0.499, 2026/07/16, for Linux+SSL (64-bit)
 Copyright (C) 1985, 2025,
  Trustees of Columbia University in the City of New York.
 Copyright (C) 2025-2026, John Goerzen
 Open Source 3-clause BSD license since 2011.
Type ? or HELP for help.
Return to your local Kermit and give a RECEIVE command.

KERMIT READY TO SEND...
9 S~/ @-#Y3~^@~}0___^"U1A!
----------------------------------------------------
----------------------------------------------------
jgoerzen@server2:/usr$ 
```

Note the `2>/dev/null` part of that command.  tar normally writes errors and warnings to stderr.  They can be things like permission denied while reading a file.  `SEND /COMMAND` sends stdout **and stderr** to the remote side.  If these warnings wind up interleaved with the tar file stream, they will corrupt it.  So, I defensively send stderr to /dev/null as part of the command, preventing that kind of issue.

While the transfer is in progress, I see a screen like this (portions redacted):

```text
C-Kermit 11.0.499, 2026/07/16, workstation.aaa [192.aaa.aaa.aaa]

   Current Directory: /tmp/t
        Network Host: ssh -e none server2
        Network Type: TCP/IP
              Parity: none
         RTT/Timeout: 08 / 00
           RECEIVING: bin.tar.gz => bin.tar.gz
           File Type: BINARY
           File Size:
        Bytes So Far: 190281357
                          ...10...20...30...40...50...60...70...80...90..100
 Estimated Time Left: (unknown)
  Transfer Rate, CPS: 3929529
        Window Slots: STREAMING
         Packet Type: D 
        Packet Count: 21834 
       Packet Length: 9032 
         Error Count: 0
          Last Error:
        Last Message:

X to cancel file, Z to cancel group, <CR> to resend last packet,
E to send Error packet, ^C to quit immediately, ^L to refresh screen.
```

Let's exit from kermit and see what we got:

```text
jgoerzen@workstation:/tmp/t$ ls -lh bin.tar.gz
-rw-rw-r-- 1 jgoerzen jgoerzen 245M Jul 22 15:49 bin.tar.gz
```

And see if it came through right:

```text
jgoerzen@workstation:/tmp/t$ tar -ztf bin.tar.gz | tail
bin/x86_64-linux-gnu-gcc-10
bin/fakeroot-tcp
bin/smbclient
bin/fusermount3
bin/combinediff
bin/bzless
bin/virt-xml-validate
bin/systemd-umount
bin/zipsplit
bin/apt-get
```

Looks right!

You can use /COMMAND in both directions.  Here I showed `SEND /COMMAND`, but you can also use `RECEIVE /COMMAND`.  That causes the received data to be piped to a command instead of written to a file on disk.

## Manual receive

So far, whenever you have initiated a transfer from the remote, the local end starts automatically receiving the file.  That's because the default for `SET TERMINAL AUTODOWNLOAD` is `ON`.  If we want to receive in some other way, such as `RECEIVE /COMMAND`, then we need to have manual control over the receive side of things.  Let's play that out:

```text
jgoerzen@workstation:/tmp/t$ kermit
C-Kermit 11.0.499, 2026/07/16, for Linux+SSL (64-bit)
 Copyright (C) 1985, 2025,
  Trustees of Columbia University in the City of New York.
 Copyright (C) 2025-2026, John Goerzen
 Open Source 3-clause BSD license since 2011.
Type ? or HELP for help.
(/tmp/t/) C-Kermit>set terminal autodownload off
(/tmp/t/) C-Kermit>ssh server2
Connecting via command "ssh -e none server2"
 Escape character: Ctrl-\ (ASCII 28, FS): enabled
Type the escape character followed by C to get back,
or followed by ? to see other options.
----------------------------------------------------
jgoerzen@server2:~$ cd /usr
jgoerzen@server2:/usr$ kermit -Ii -C 'SEND /COMMAND "tar -zcf - bin 2>/dev/null" bin.tar.gz , quit'
C-Kermit 11.0.499, 2026/07/16, for Linux+SSL (64-bit)
 Copyright (C) 1985, 2025,
  Trustees of Columbia University in the City of New York.
 Copyright (C) 2025-2026, John Goerzen
 Open Source 3-clause BSD license since 2011.
Type ? or HELP for help.
Return to your local Kermit and give a RECEIVE command.

KERMIT READY TO SEND...
                           [[ here I typed Ctrl-\ C ]]

(Back at workstation.aaa.aaa.aaa)
----------------------------------------------------
(/tmp/t/) C-Kermit>receive /COMMAND "tar -ztf - | tail -n 5 > /tmp/t/tarlog.txt"
(/tmp/t/) C-Kermit>!cat tarlog.txt
bin/bzless
bin/virt-xml-validate
bin/systemd-umount
bin/zipsplit
bin/apt-get
(/tmp/t/) C-Kermit>
```

Here, we generated a tar file 

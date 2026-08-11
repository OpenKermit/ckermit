# Using vsock to communicate between host and guest VMs

On Linux, say you're running KVM to run a guest VM.  You'd like to transfer files between the host machine and the VM.  There are several options for that:

- Sharing some filesystem from the host (requires support in the guest and
  careful configuration)

- Using network tools (requires setting up a network on both the host and the
  guest and all the configuration and security that goes with that)

- Running something like C-Kermit over an emulated serial line (can be slow, and
  qemu's methods of bridging serial lines can be finicky and buggy)

- Using [vsock](https://www.man7.org/linux/man-pages/man7/vsock.7.html), but few
  programs support it, so (until now) you had to set up bridges with socat and
  other hacks.

As of C-Kermit 11.0.508, vsock support is now native in C-Kermit.

# vsock basics

vsock supports stream (like TCP) and datagram (like UDP) transports.  We will,
of course, use stream transport here.  vsock support doesn't require a
configured network interface.  In fact, it doesn't support such.

A vsock address is a 32-bit CID (akin to an IP address) and a 32-bit port.  By
convention, CID 0 is reserved, CID 1 is localhost, CID 2 is the host machine,
and guest VMs can use CID 3 and above.  Unlike TCP 16-bit port, the port number
is 32 bits wide.

If you are invoking qemu directly, you will run a VM with something like this on
the command line:

`-device vhost-vsock-pci,guest-cid=3`

If you're using libvirt, something like this in your machine definition:

```
<devices>
  ...
  <vsock model='virtio'>
    <cid auto='no' address='3'/>
  </vsock>
</devices>
```

# Kermit usage

Let's say you've configured the guest as CID 3.  You have access to it, perhaps
via `virsh console` or VNC.  (You can run C-Kermit across `virsh console` but it
will be a lot slower than vsock.)  On the guest, you'll type something like:

`set host /network-type:vsock *:5353`

This has Kermit listening for a connection.

A more complete session on the guest might look like this:

```
ENABLE ALL BOTH
SET RECEIVE CONFIRM OFF
SET HOST /SERVER /NETWORK-TYPE:VSOCK *:5353
```

This is an unusual situation where the server is running in interactive mode,
but you directly control the other end, so probably don't want to have to
confirm all the actions.  See [permissions](permissions.md) for more.

Then, on the host, you'll run something like:

`set host /network-type:vsock 3:5353`

This will establish the connection.

It's all ready to go.  You can use `GET`, `SEND`, `RDIR`, `RDEL`, etc. to
control the remote end.

# A note on security

vsock provides no particular security.  It's like opening a port on localhost.
You can't access it remotely, though, that helps compared with TCP.

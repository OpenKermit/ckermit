# C-Kermit

Welcome to C-Kermit!  C-Kermit is a project of [Open
Kermit](https://www.openkermit.org/), the home of continuing development of
C-Kermit.

C-Kermit is a communications package.  It has a text UI, a portable [scripting
language](scripting) (similar in concept to the shell, but with built-in
screen-scraping automation like expect and built-in file transfer), an
implementation of the Kermit file transfer protocol protocol, network client and
server, serial port interface, [BBS client](ckermit/bbs), and more.  Kermit runs
on hundreds of platforms, from the long-dead computers of the 1970s, pocket
calculators of the 1990s, and  modern desktop and mobile OSs.

I need to emphasize here the difference between the Kermit protocol and the
C-Kermit software. The protocol is primarily used for transferring files, but
also in the more sophisticated implementations such as C-Kermit, can be used to
perform actions on the remote such as renaming files, creating directories, and
so forth.  C-Kermit is an implementation of the protocol, but also adds a lot of
other features, such as a scripting language and X/Y/ZModem support.

The C-Kermit of today is a direct continuation of the original C-Kermit released
in 1985.

**IMPORTANT NOTE**: If you are reading this page on Github, the canonical place
to view it instead is <https://www.openkermit.org/ckermit/>.  That integrates
with the rest of the Kermit Project website.

Begin with [downloads](https://www.openkermit.org/downloads/) and then
[documentation](https://www.openkermit.org/doc/) on how to get started.

Here you can find specific C-Kermit information:

- [Introduction to C-Kermit](intro.md), including a tour
- [C-Kermit as an ssh wrapper](ssh.md) shows how C-Kermit makes ssh a lot more useful.  And it is another good way of learning about Kermit, even if you aren't going to use it as a ssh wrapper.
- The [current changelog](changelog.md), 2022-present
- The [old changelog](changelog-old.txt), which itself is a copy of http://kermitproject.org/ckupdates.html
- A recent generated [reference document](help-reference.md)
- [Platform-specific notes](platforms) for your specific operating system
- Notes on using C-Kermit:
  - [IPv6](ipv6.md)
  - [Calling BBSs](bbs.md)
  - [On very high-latency links](high-latency.md)
  - [C-Kermit Scripting](scripting.md)

For more information, see the wider [Open Kermit project](https://www.openkermit.org/).  Take particular note of these pages there:

- [Kermit documentation](https://www.openkermit.org/doc/)
- [FAQ](https://www.openkermit.org/faq/)

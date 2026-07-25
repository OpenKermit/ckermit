import fcntl
import os
import pty
import subprocess
import termios
import time


def _make_controlling_tty():
    """
    Makes the pty slave this process's controlling terminal, so
    wermit's foreground-process-group detection function conbgt()
    sees it as a real interactive session instead of a
    backgrounded one. Without this, kermit stays a member of the
    parent Python's process group with no controlling terminal.
    conbgt() may interpret that as "running in the background" and
    respond by suppressing the prompt entirely, leaving the test
    blocked on OpenBSD at least.
    """
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


def test_ssh_space_backspace(wermit_path):
    """
    Test that typing 'ssh ' and then backspacing over the space at the command
    prompt does not emit an error ('?Invalid argument').
    """
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        [str(wermit_path), "-H", "-Y", "-Q"],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True,
        preexec_fn=_make_controlling_tty,
    )
    os.close(slave)

    try:
        time.sleep(0.3)
        os.read(master, 2048)

        # Type 'ssh '
        os.write(master, b"ssh ")
        time.sleep(0.2)
        out_space = os.read(master, 2048)

        # Backspace over space
        os.write(master, b"\x7f")
        time.sleep(0.2)
        out_bs = os.read(master, 2048)

        assert b"Invalid argument" not in out_space
        assert b"Invalid argument" not in out_bs
        assert out_bs.startswith(b"\x08 \x08")
    finally:
        proc.kill()
        proc.wait()
        os.close(master)

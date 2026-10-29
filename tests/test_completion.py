"""
Tests for filename completion in cmifi2() (ckucmd.c) through a pty.
"""
import os
import pty
import subprocess

from conftest import PROMPT, _make_controlling_tty, read_pty_until


def _complete(wermit_path, cwd, typed, expect):
    """Type typed into an interactive wermit and return what it echoes.

    typed is written in 1 KB pieces.  The read ends when expect
    appears, when the terminal echoes Esc as ^[, or after 10 seconds.
    Return the echo, with "DEAD" appended if wermit exited.  Fail when
    wermit prints no prompt or the terminal echoes Esc.  Either means
    wermit did not take over the pty.
    """
    fd, slave = pty.openpty()
    proc = subprocess.Popen([wermit_path, "-H", "-Y"], stdin=slave,
                            stdout=slave, stderr=slave, cwd=cwd,
                            preexec_fn=_make_controlling_tty)
    os.close(slave)
    out = b""

    try:
        read_pty_until(
            fd, b"", (PROMPT,), 10,
            message="wermit printed no prompt, so the pty setup is wrong")
        for i in range(0, len(typed), 1024):
            os.write(fd, typed[i:i + 1024])
            out = read_pty_until(fd, out, (), 0.01)
        out = read_pty_until(fd, out, (expect, b"^["), 10)
        echoed = out.decode(errors="replace")
        if proc.poll() is not None:
            echoed += "DEAD"
    finally:
        # Close the master first.  On NetBSD a session leader that exits
        # with output pending waits for the master to read it.
        proc.kill()
        os.close(fd)
        proc.wait()
    assert "^[" not in echoed, (
        "the terminal echoed Esc, so wermit did not take over the pty: "
        f"{echoed[-2000:]!r}")
    return echoed


def test_partial_completion(wermit_path, tmp_path):
    """Verify Esc completes a name up to where the matches differ."""
    (tmp_path / "alphaone.txt").write_text("x")
    (tmp_path / "alphatwo.txt").write_text("x")
    echoed = _complete(wermit_path, tmp_path, b"type alp\x1b",
                       b"type alpha")
    assert "type alpha" in echoed, repr(echoed)


def test_directory_completion(wermit_path, tmp_path):
    """Verify Esc completes a directory name with its separator."""
    (tmp_path / "subdirectory").mkdir()
    (tmp_path / "subdirectory" / "f.txt").write_text("x")
    echoed = _complete(wermit_path, tmp_path, b"type subd\x1b",
                       b"type subdirectory/")
    assert "type subdirectory/" in echoed, repr(echoed)


def test_completion_at_end_of_command_buffer(wermit_path, tmp_path):
    """Verify completion stops at the end of the command buffer.

    32700 spaces fill most of the buffer.  Completing a 241-character
    common prefix would run past its end.  The overflow shows only under
    AddressSanitizer.  A normal build checks that wermit is still running.
    wermit refuses the overlong command and prompts again.
    """
    name = "a" + "x" * 240
    (tmp_path / (name + "1.txt")).write_text("x")
    (tmp_path / (name + "2.txt")).write_text("x")
    echoed = _complete(wermit_path, tmp_path,
                       b"type " + b" " * 32700 + b"a\x1b", PROMPT)
    assert "AddressSanitizer" not in echoed, echoed[-2000:]
    assert "DEAD" not in echoed, echoed[-2000:]
    assert PROMPT.decode() in echoed, echoed[-2000:]

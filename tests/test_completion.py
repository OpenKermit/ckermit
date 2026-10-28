"""
Tests for filename completion in cmifi2() (ckucmd.c) through a pty.
"""
import os
import pty
import subprocess

import pytest

from conftest import PROMPT, read_pty_until


def _complete(wermit_path, cwd, typed, expect):
    """Type typed into an interactive wermit and return what it echoes.

    typed is written in 1 KB pieces.  The read ends when expect
    appears, when the terminal echoes Esc as ^[, or after 10 seconds.
    Returns the echo, with "DEAD" appended if wermit exited.
    """
    fd, slave = pty.openpty()
    proc = subprocess.Popen([wermit_path, "-H", "-Y"], stdin=slave,
                            stdout=slave, stderr=slave, cwd=cwd,
                            start_new_session=True)
    os.close(slave)
    out = b""

    try:
        read_pty_until(fd, b"", (PROMPT,), 10)
        for i in range(0, len(typed), 1024):
            os.write(fd, typed[i:i + 1024])
            out = read_pty_until(fd, out, (), 0.01)
        out = read_pty_until(fd, out, (expect, b"^["), 10)
        echoed = out.decode(errors="replace")
        if proc.poll() is not None:
            echoed += "DEAD"
    finally:
        proc.kill()
        proc.wait()
        os.close(fd)
    return echoed


def _require_completion(echoed):
    """Skip when the terminal setup does not give Esc completion."""
    if "^[" in echoed:
        pytest.skip("this terminal setup does not give Esc completion")


def test_partial_completion(wermit_path, tmp_path):
    """Verify Esc completes a name up to where the matches differ."""
    (tmp_path / "alphaone.txt").write_text("x")
    (tmp_path / "alphatwo.txt").write_text("x")
    echoed = _complete(wermit_path, tmp_path, b"type alp\x1b",
                       b"type alpha")
    _require_completion(echoed)
    assert "type alpha" in echoed, repr(echoed)


def test_directory_completion(wermit_path, tmp_path):
    """Verify Esc completes a directory name with its separator."""
    (tmp_path / "subdirectory").mkdir()
    (tmp_path / "subdirectory" / "f.txt").write_text("x")
    echoed = _complete(wermit_path, tmp_path, b"type subd\x1b",
                       b"type subdirectory/")
    _require_completion(echoed)
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
    _require_completion(echoed)
    assert "AddressSanitizer" not in echoed, echoed[-2000:]
    assert "DEAD" not in echoed, echoed[-2000:]

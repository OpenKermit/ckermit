"""
Tests of the protocol start string over a pseudoterminal.

Before a SEND or a server command, a local Kermit writes the start
string (`kermit -ir`, `kermit -x`) to the remote shell.  The remote
shell here waits 1 s before it reads.  So the string is still in the
pty when the client flushes input before its first packet.
"""

import os
import subprocess

import pytest

from conftest import scaled


@pytest.fixture
def slow_shell(tmp_path, wermit_path):
    """Return a remote shell script and the client and remote dirs."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    kermit = bindir / "kermit"
    kermit.write_text(f'#!/bin/sh\nexec {wermit_path} -H "$@"\n')
    kermit.chmod(0o755)
    rdir = tmp_path / "r"
    rdir.mkdir()
    cdir = tmp_path / "c"
    cdir.mkdir()
    shell = tmp_path / "rsh"
    shell.write_text(f"#!/bin/sh\ncd {rdir} || exit 1\n"
                     f"PATH={bindir}:$PATH\nexport PATH\n"
                     "sleep 1\nexec sh\n")
    shell.chmod(0o755)
    return shell, cdir, rdir


@pytest.mark.parametrize("op", ["send", "get"])
def test_start_string_survives_input_flush(wermit_path, slow_shell, op):
    """Verify a start string the shell has not read yet still arrives.

    sipkt() flushes input before the first packet.  On a pty master
    that flush must discard the bytes from the remote, not the start
    string queued for it.
    """
    shell, cdir, rdir = slow_shell
    data = "start string test\n" * 50
    if op == "send":
        (cdir / "f.txt").write_text(data)
        cmd, dest = "send f.txt", rdir / "f.txt"
    else:
        (rdir / "f.txt").write_text(data)
        cmd, dest = "get f.txt", cdir / "f.txt"
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         "set command more-prompting off, set transfer display none, "
         "set send timeout 2, set retry 3, "
         f"set host /network-type:pseudoterminal {shell}, "
         f"{cmd}, echo RES=\\v(status), close, exit 0"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        cwd=cdir, env=dict(os.environ), timeout=scaled(60))
    assert "RES=0" in result.stdout, result.stdout + result.stderr
    assert dest.read_text() == data

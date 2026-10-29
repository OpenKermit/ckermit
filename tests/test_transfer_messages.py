"""Tests for the messages Kermit prints when a transaction ends
(proto() in ckcpro.w).

The CRT, BRIEF and SERIAL displays show each file's result and each
error with its cause.  The FULLSCREEN display erases its screen when it
ends, and DISPLAY NONE shows nothing, so after those Kermit prints the
result: "No files were transferred" with the cause for a failure, and a
summary for a successful FULLSCREEN transfer.  A failed server command
shows its reason once in every mode.  An external protocol program
reports its result, and Kermit adds a line only for a failure.

wermit runs on a pseudoterminal against a Kermit server on another
pseudoterminal, or against an external protocol peer.
"""
import os
import re
import subprocess
import sys

import pytest

from conftest import PROTOCOL_STARTUP_OFF, run_wermit_pty, scaled

DISPLAYS = ["fullscreen", "crt", "brief", "serial", "none"]
NO_FILES = "No files were transferred"


def _rmcup():
    """Return the string that ends xterm's alternate screen, or "".

    With it, the FULLSCREEN display is erased when it ends.  Some systems'
    xterm entries, FreeBSD's among them, have none, and the last screen
    stays visible.  The query runs in a subprocess.  Python's curses
    honors only the first setupterm() in a process, and other tests in
    this process need theirs.
    """
    code = ("import curses, sys\n"
            "try:\n"
            "    curses.setupterm('xterm')\n"
            "    cap = curses.tigetstr('rmcup') or b''\n"
            "except curses.error:\n"
            "    cap = b''\n"
            "sys.stdout.buffer.write(cap)\n")
    result = subprocess.run([sys.executable, "-c", code],
                            stdout=subprocess.PIPE, timeout=scaled(30))
    return result.stdout.decode("latin-1")


RMCUP = _rmcup()
UNSEEN = {"none"} | ({"fullscreen"} if RMCUP else set())


def _visible(out):
    """Return the output left on the screen, one stripped line each.

    The FULLSCREEN display uses the alternate screen where xterm has one,
    and the terminal discards it when the display ends.
    """
    if RMCUP and RMCUP in out:
        out = out.split(RMCUP)[-1]
    out = re.sub(r"\x1b[\[\(>=][0-9;?]*[A-Za-z]?", "", out)
    return "\n".join(line.strip() for line in out.replace("\r", "")
                     .splitlines() if line.strip())


@pytest.fixture(autouse=True)
def known_terminal(monkeypatch):
    """Give wermit a terminal type that has a fullscreen display."""
    monkeypatch.setenv("TERM", "xterm")


@pytest.fixture
def server(tmp_path, wermit_path):
    """Set up a Kermit server and return (host, client directory)."""
    srvdir = tmp_path / "s"
    clidir = tmp_path / "c"
    srvdir.mkdir()
    clidir.mkdir()
    (srvdir / "g.txt").write_text("x\n")
    (srvdir / "old.txt").write_text("new\n")
    (clidir / "old.txt").write_text("old\n")
    (tmp_path / "f.txt").write_text("hello\n" * 100)
    script = tmp_path / "srv.ksc"
    script.write_text(f"cd {srvdir}\nset delay 0\nenable all\nserver\n")
    return f"{wermit_path} {script}", clidir


def _run(wermit_path, display, host, cmds, cwd):
    """Run cmds against host with the given display.  Return the text."""
    rc, out = run_wermit_pty(
        wermit_path,
        f"{PROTOCOL_STARTUP_OFF}, "
        f"set delay 0, set transfer display {display}, "
        f"set host /network-type:pseudoterminal {host}, {cmds}, "
        "echo STATUS=\\v(status), close, exit", cwd, timeout=60)
    return _visible(out)


@pytest.mark.parametrize("display", DISPLAYS)
def test_successful_transfer(wermit_path, server, tmp_path, display):
    """Verify a successful transfer reports success, and only once."""
    host, clidir = server
    out = _run(wermit_path, display, host, f"send {tmp_path}/f.txt", clidir)
    assert "STATUS=0" in out, out
    assert NO_FILES not in out, out
    if display == "fullscreen" and RMCUP:
        assert "Transfer complete: 1 file, 600 bytes." in out, out
    else:
        assert "Transfer complete:" not in out, out


@pytest.mark.parametrize("display", DISPLAYS)
def test_missing_file(wermit_path, server, display):
    """Verify a GET of a missing file shows the cause exactly once."""
    host, clidir = server
    out = _run(wermit_path, display, host, "get nosuch.txt", clidir)
    assert "STATUS=1" in out, out
    assert out.count("File not found") == 1, out
    if display in UNSEEN:
        assert f"{NO_FILES}: File not found." in out, out
    else:
        assert NO_FILES not in out, out


@pytest.mark.parametrize("display", DISPLAYS)
def test_refused_file(wermit_path, server, display):
    """Verify a file refused by FILE COLLISION REJECT is reported."""
    host, clidir = server
    out = _run(wermit_path, display, host,
               "set file collision reject, get old.txt", clidir)
    assert (clidir / "old.txt").read_text() == "old\n"
    if display in UNSEEN:
        assert "(refused: destination file already exists)" in out, out
    else:
        assert NO_FILES not in out, out
        assert re.search(r"Refused[:,] name|REFUSED", out), out


@pytest.mark.parametrize("display", DISPLAYS)
def test_failed_server_command(wermit_path, server, tmp_path, display):
    """Verify a failed REMOTE command shows its reason exactly once."""
    host, clidir = server
    out = _run(wermit_path, display, host,
               f"remote cd {tmp_path}/nosuchdir", clidir)
    assert "STATUS=1" in out, out
    assert out.count("Can't change directory") == 1, out
    assert "Command failed" not in out, out
    assert NO_FILES not in out, out


@pytest.mark.parametrize("display", DISPLAYS)
def test_successful_server_command(wermit_path, server, display):
    """Verify a successful REMOTE command adds no result line."""
    host, clidir = server
    out = _run(wermit_path, display, host, "remote pwd", clidir)
    assert "STATUS=0" in out, out
    assert NO_FILES not in out and "Transfer complete:" not in out, out


@pytest.mark.parametrize("display", DISPLAYS)
@pytest.mark.zmodem
def test_external_protocol_failure(wermit_path, tmp_path, display):
    """Verify a failed external protocol transfer is reported.

    The peer cancels the ZMODEM transfer, so rz exits with an error.
    """
    import shutil
    if not shutil.which("rz"):
        pytest.skip("rz not installed")
    peer = tmp_path / "cancel.sh"
    peer.write_text("#!/bin/sh\nsleep 1\n"
                    "printf '\\030\\030\\030\\030\\030"
                    "\\010\\010\\010\\010\\010'\nsleep 3\n")
    os.chmod(peer, 0o755)
    out = _run(wermit_path, display, str(peer),
               "receive /protocol:zmodem", tmp_path)
    assert "STATUS=1" in out, out
    assert NO_FILES in out, out


@pytest.mark.parametrize("display", DISPLAYS)
@pytest.mark.zmodem
def test_external_protocol_success(wermit_path, tmp_path, display):
    """Verify a successful external protocol transfer adds no line."""
    import shutil
    if not shutil.which("rz"):
        pytest.skip("rz not installed")
    (tmp_path / "f.txt").write_text("hello\n" * 100)
    rdir = tmp_path / "r"
    rdir.mkdir()
    # The peer is rz itself, so Kermit must not type "rz" at it.  Both
    # sides escape control characters.  Without -e, sz and rz stall now
    # and then on OpenBSD after the ZFILE header.
    out = _run(wermit_path, display, "rz -e -y",
               "set protocol zmodem {} {} {sz -e %s} {sz -e %s} "
               "{rz -e} {rz -e}, "
               "set protocol startup-string off, "
               f"send /protocol:zmodem {tmp_path}/f.txt", rdir)
    assert "STATUS=0" in out, out
    assert NO_FILES not in out, out
    assert (rdir / "f.txt").exists()


@pytest.mark.parametrize("cmds,expected,absent", [
    ("send {tmp}/f.txt", None, [NO_FILES, "Transfer complete:"]),
    ("get nosuch.txt", NO_FILES + ": File not found.", []),
    ("remote cd {tmp}/nosuchdir", "?Can't change directory", [NO_FILES]),
], ids=["send-ok", "get-missing", "remote-cd-failed"])
def test_messages_without_terminal(run_wermit, server, tmp_path, cmds,
                                   expected, absent):
    """Verify the result is reported once when there is no terminal.

    Without a terminal Kermit runs as a background process, and the
    file transfer display shows nothing, as in a script run by cron.
    """
    host, clidir = server
    result = run_wermit(
        f"cd {clidir}, {PROTOCOL_STARTUP_OFF}, set delay 0, "
        f"set host /network-type:pseudoterminal {host}, "
        f"{cmds.format(tmp=tmp_path)}, close", timeout=60)
    out = result.stdout
    if expected:
        assert out.count(expected) == 1, out
    for text in absent:
        assert text not in out, out
    assert "Command failed" not in out, out


@pytest.mark.parametrize("term", [None, "no-such-terminal"],
                         ids=["unset", "unknown"])
def test_fullscreen_unknown_terminal(wermit_path, server, tmp_path,
                                     monkeypatch, term):
    """Verify FULLSCREEN with an unknown terminal falls back to CRT.

    SET TRANSFER DISPLAY FULLSCREEN still selects the display.  The
    transfer must complete, with the CRT display, instead of curses
    ending the program.
    """
    if term is None:
        monkeypatch.delenv("TERM", raising=False)
    else:
        monkeypatch.setenv("TERM", term)
    host, clidir = server
    out = _run(wermit_path, "fullscreen", host, f"send {tmp_path}/f.txt",
               clidir)
    assert "STATUS=0" in out, out
    assert "Fullscreen display not supported" in out, out
    assert "[OK]" in out, out

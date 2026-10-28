"""
Tests that HELP states the defaults that SHOW reports.
"""
import pytest


@pytest.mark.parametrize("helpcmd,helptext,showcmd,showtext", [
    ("help set incomplete", "AUTO, the default",
     "show file", "File incomplete:         auto"),
    ("help set tcp", "The default is OFF.", "show tcp", "Linger: off"),
    ("help set server", "screen.  Default is ON.",
     "show server", "Server display:      on"),
])
def test_help_default_matches_show(run_wermit, helpcmd, helptext,
                                   showcmd, showtext):
    """Verify a HELP default statement agrees with SHOW."""
    result = run_wermit(f"{helpcmd}, {showcmd}")
    assert helptext in result.stdout, result.stdout
    assert showtext in result.stdout, result.stdout


def test_local_charset_default_is_visible_name(wermit_path):
    """Verify Esc fills in the visible name of the file character set.

    With FILE CHARACTER-SET LATIN1-ISO, SET TERMINAL LOCAL-CHARACTER-SET
    offers it as the default.  The invisible synonym iso-8859-1 comes
    first in the table.
    """
    import os
    import pty
    import subprocess
    from conftest import PROMPT, read_pty_until
    fd, slave = pty.openpty()
    proc = subprocess.Popen([wermit_path, "-H", "-Y"], stdin=slave,
                            stdout=slave, stderr=slave,
                            start_new_session=True)
    os.close(slave)
    try:
        read_pty_until(fd, b"", (PROMPT,), 10)
        os.write(fd, b"set file character-set latin1-iso\r")
        read_pty_until(fd, b"", (PROMPT,), 10)
        os.write(fd, b"set terminal local-character-set \x1b")
        out = read_pty_until(fd, b"", (b"latin1-iso", b"^["), 10)
        line = out.decode(errors="replace")
    finally:
        proc.kill()
        proc.wait()
        os.close(fd)
    if "^[" in line:
        pytest.skip("this terminal setup does not give Esc completion")
    assert "local-character-set latin1-iso" in line, repr(line)


@pytest.mark.parametrize("helpcmd,phrase", [
    ("help resend", "Otherwise it refuses the file."),
    ("help set receive", "Names are compared without their directory"),
    ("help set ftp timeout", "When the timeout is 0, that wait lasts 60"),
    ("help associate", "RECEIVE CHARACTER-SET (q.v.) is AUTOMATIC"),
    ("help associate", "SET TRANSFER CHARACTER-SET change only their own"),
    ("help set send", "TRANSFER CHARACTER-SET change only their"),
    ("help enable", "also DISABLE QUERY and DISABLE ASSIGN"),
    ("help disable", "also DISABLE QUERY and DISABLE ASSIGN"),
    ("help remote query", "runs any command the client defines"),
    ("help remote assign", "run the variable"),
    ("help set host", "SET HOST with no host name closes the current"),
    ("help set dial", "10 for country code 1, and 1 (no redialing)"),
    ("help set function", "cause a command to fail. ON by default."),
    ("help set iks", "This feature is OFF by default."),
    ("help set terminal", "both are the same character set"),
    ("help set window", "The default is 30, or fewer if SET BUFFERS"),
    ("help set unknown-char-set", "KEEP (the default)"),
])
def test_help_describes_behavior(run_wermit, helpcmd, phrase):
    """Verify HELP describes the RESEND, CONFIRM and FTP timeout rules."""
    result = run_wermit(helpcmd)
    assert phrase in " ".join(result.stdout.split()), result.stdout


@pytest.mark.parametrize("kind,text", [
    ("system", "Remote variable name\r\n"),
    ("user", "Remote variable name\r\n"),
    ("kermit", "Remote variable name or function\r\n"),
])
def test_remote_query_help(wermit_path, kind, text):
    """Verify ? after REMOTE QUERY <type> describes that type."""
    import os
    import pty
    import subprocess
    from conftest import PROMPT, _make_controlling_tty, read_pty_until
    fd, slave = pty.openpty()
    proc = subprocess.Popen([wermit_path, "-H", "-Y"], stdin=slave,
                            stdout=slave, stderr=slave,
                            preexec_fn=_make_controlling_tty)
    os.close(slave)
    try:
        read_pty_until(fd, b"", (PROMPT,), 10)
        os.write(fd, f"remote query {kind} ?".encode())
        out = read_pty_until(fd, b"", (text.encode(),), 15)
        line = out.decode(errors="replace")
    finally:
        # Close the master first.  On NetBSD a session leader that exits
        # with output pending waits for the master to read it.
        proc.kill()
        os.close(fd)
        proc.wait()
    assert text in line, repr(line)

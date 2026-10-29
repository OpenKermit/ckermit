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

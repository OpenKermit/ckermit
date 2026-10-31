"""Built-in terminfo fallback entries in musl static builds.

tools/build-musl-libs.sh compiles ncurses with fallback entries for
common terminal types.  ncurses consults them only after the terminfo
database lookup fails.  A musl static binary on a system that lacks a
terminfo entry for one of those types still finds the type.
"""
import os
import re
from pathlib import Path

import pytest

from conftest import assert_ok, run_wermit_pty

# A fallback type that Debian and Ubuntu ship in ncurses-term, not in
# ncurses-base.
FALLBACK_ONLY = "putty"

# The terminfo directories build-musl-libs.sh compiles into ncurses.
COMPILED_DIRS = ("/usr/share/terminfo", "/etc/terminfo", "/lib/terminfo")

FULLSCREEN = "set transfer display fullscreen, quit"


def _in_terminfo_db(name):
    """Return True if any terminfo directory ncurses searches has name.

    Directories hold entries under the first character of the name or
    under its hexadecimal code.
    """
    dirs = list(COMPILED_DIRS)
    dirs.append(os.path.expanduser("~/.terminfo"))
    dirs.append(os.environ.get("TERMINFO", ""))
    dirs.extend(os.environ.get("TERMINFO_DIRS", "").split(":"))
    subdirs = (name[0], format(ord(name[0]), "x"))
    return any(Path(d, s, name).exists()
               for d in dirs if d for s in subdirs)


@pytest.fixture
def musl_curses(run_wermit):
    """Skip unless wermit is a musl static build with curses support."""
    result = run_wermit("show features")
    assert_ok(result)
    target = re.search(r"^Target: (\S+)", result.stdout, re.M)
    if target is None or not target.group(1).endswith("+musl"):
        pytest.skip("not a musl static build")
    if "CK_CURSES" not in result.stdout:
        pytest.skip("built without curses")


def test_fallback_entry_without_database(wermit_path, tmp_path,
                                         monkeypatch, musl_curses):
    """Verify a fallback-only terminal type resolves.

    An unknown type produces the "terminal type unknown" warning.  The
    fallback type produces none, although no terminfo database on the
    host holds it.
    """
    if _in_terminfo_db(FALLBACK_ONLY):
        pytest.skip(f"terminfo database holds {FALLBACK_ONLY}")

    monkeypatch.setenv("TERM", "kermit-no-such-term")
    rc, out = run_wermit_pty(wermit_path, FULLSCREEN, tmp_path)
    assert rc == 0, out
    assert "terminal type unknown" in out, out

    monkeypatch.setenv("TERM", FALLBACK_ONLY)
    rc, out = run_wermit_pty(wermit_path, FULLSCREEN, tmp_path)
    assert rc == 0, out
    assert "terminal type unknown" not in out, out

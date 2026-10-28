"""
Tests for per-call leaks in pattern matching, DIRECTORY and URL
parsing.

Each case runs a command twice under valgrind.  No block allocated by
the named function may be definitely lost.
"""
import re
import subprocess

import pytest


@pytest.mark.parametrize("cmds,func", [
    ("if match abc a{b,x}c echo M", "ckmatch"),
    ("dir /except:*.dat", "domydir"),
    ("dir /after:2020-01-01", "domydir"),
    ("http open http://u:p@localhost:9/x", "urlparse"),
], ids=["match-braces", "dir-except", "dir-after", "http-url"])
def test_no_leak_per_call(wermit_path, valgrind, tmp_path, cmds, func):
    """Verify the command leaks nothing from func."""
    (tmp_path / "a.txt").write_text("a\n")
    (tmp_path / "b.dat").write_text("b\n")
    result = subprocess.run(
        [valgrind, "-q", "--leak-check=full", wermit_path,
         "-H", "-Y", "-Q", "-C",
         f"set command more-prompting off, {cmds}, {cmds}, exit 0"],
        cwd=tmp_path, stdin=subprocess.DEVNULL, capture_output=True,
        text=True, timeout=120)
    # valgrind separates loss records with "==pid== " lines.
    records = re.split(r"^==\d+== *$", result.stderr, flags=re.M)
    leaked = [r for r in records if "definitely lost" in r and func in r]
    assert not leaked, result.stderr

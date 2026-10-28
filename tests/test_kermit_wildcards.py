"""Tests for Kermit wildcard matching of file names (ckmatch())."""
import pytest

NAMES = ["a.b", "ab.cb", "x.y.z", ".hidden", ".hz"]


@pytest.mark.parametrize("pattern,expected", [
    ("a*?b", ["a.b", "ab.cb"]),
    ("*?z", ["x.y.z"]),
    ("*.*", ["a.b", "ab.cb", "x.y.z"]),
    ("*z", ["x.y.z"]),
    ("?*", ["a.b", "ab.cb", "x.y.z"]),
    ("*", ["a.b", "ab.cb", "x.y.z"]),
    (".*", [".hidden", ".hz"]),
    (".h*z", [".hz"]),
])
def test_wildcard_dot_in_name(run_wermit, tmp_path, pattern, expected):
    """Verify '*' matches a dot inside a name but not a leading dot.

    A name that starts with '.' matches only a pattern that starts
    with '.'.  The rule applies to the start of the name, so a '*'
    followed by another metacharacter still matches an inner dot.
    """
    d = tmp_path / "d"
    d.mkdir()
    for name in NAMES:
        (d / name).write_text("x")
    script = tmp_path / "t.ksc"
    script.write_text(
        f"cd {d}\n"
        f"echo COUNT=[\\ffiles({pattern})]\n"
        "while true {\n"
        "    assign f \\fnextfile()\n"
        "    if not def f break\n"
        "    echo NAME=[\\m(f)]\n"
        "}\n")
    result = run_wermit(f"take {script}")
    names = sorted(line[6:-1] for line in result.stdout.splitlines()
                   if line.startswith("NAME=["))
    assert names == sorted(expected), result.stdout
    assert f"COUNT=[{len(expected)}]" in result.stdout, result.stdout


def test_stringspace_default(run_wermit):
    """Verify the default file-list string space is 32 million bytes."""
    result = run_wermit("show file")
    assert "Stringspace:             32000000" in result.stdout, \
        result.stdout


def test_stringspace_exhausted_then_raised(run_wermit, tmp_path):
    """Verify a small string space fails and SET FILE STRINGSPACE fixes it."""
    for i in range(60):
        (tmp_path / f"file_with_a_rather_long_name_number_{i}.txt").touch()
    result = run_wermit(
        f"cd {tmp_path}, set file stringspace 2000, echo N=\\ffiles(*), "
        "set file stringspace 100000, echo N=\\ffiles(*)")
    assert "String space 2000 exhausted" in result.stdout, result.stdout
    assert "N=0" in result.stdout, result.stdout
    assert "N=60" in result.stdout, result.stdout


@pytest.mark.parametrize("size", ["100", "1024"])
def test_stringspace_minimum_is_accepted(run_wermit, tmp_path, size):
    """Verify SET FILE STRINGSPACE at or below 1024 sets 1024 bytes."""
    (tmp_path / "one.txt").touch()
    result = run_wermit(
        f"cd {tmp_path}, set file stringspace {size}, "
        "echo N=\\ffiles(*), show file")
    assert "allocation failure" not in result.stdout, result.stdout
    assert "Stringspace:             1024" in result.stdout, result.stdout
    assert "N=1" in result.stdout, result.stdout

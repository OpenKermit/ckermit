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

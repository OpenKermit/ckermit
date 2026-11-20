"""Tests for Kermit wildcard matching of file names (ckmatch())."""
import os

import pytest

from test_largefile import _parse_sizeofs

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
    """Verify the default file-list string space.

    It is 32 million bytes in a build with 64-bit longs and 10 million
    bytes otherwise.
    """
    sizeofs = _parse_sizeofs(run_wermit("show features").stdout)
    size = 32000000 if sizeofs["long"] == 8 else 10000000
    result = run_wermit("show file")
    assert f"Stringspace:             {size}" in result.stdout, \
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


def _path_limits(base):
    """Return (PATH_MAX, NAME_MAX) for base, or skip the test.

    wermit sizes its wildcard path buffer from PATH_MAX.
    """
    try:
        path_max = os.pathconf(base, "PC_PATH_MAX")
        name_max = os.pathconf(base, "PC_NAME_MAX")
    except (OSError, ValueError):
        pytest.skip("pathconf() cannot report the path limits")
    if not 0 < path_max <= 65536 or name_max < 250:
        pytest.skip(f"PATH_MAX {path_max} or NAME_MAX {name_max} unusable")
    return path_max, name_max


def _dir_of_length(base, length):
    """Create and return a directory path of about length bytes.

    The path is within 2 bytes of length.  Components are at most 200
    bytes.
    """
    path = str(base)
    while len(path) < length - 2:
        path = os.path.join(path, "d" * min(200, length - len(path) - 1))
        os.mkdir(path)
    return path


def _touch_at(directory, name):
    """Create file name in directory.

    The full path can exceed PATH_MAX.  Open directory and create name
    relative to that file descriptor.
    """
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.close(os.open(name, os.O_CREAT | os.O_WRONLY, 0o644,
                         dir_fd=fd))
    finally:
        os.close(fd)


def _assert_clean(result):
    """Assert wermit exited normally with no sanitizer report."""
    assert result.returncode >= 0, (result.returncode, result.stderr)
    assert "Sanitizer" not in result.stderr, result.stderr[-3000:]


def test_wildcard_match_past_path_buffer_skipped(run_wermit, tmp_path):
    """Verify a match too long for the path buffer is skipped.

    The directory path is about PATH_MAX - 100 bytes.  A 250-byte name
    in that directory does not fit in the path buffer and is not listed.
    A 90-byte name fits and is listed.
    """
    path_max, _ = _path_limits(tmp_path)
    d = _dir_of_length(tmp_path, path_max - 100)
    _touch_at(d, "l" * 250)
    _touch_at(d, "s" * 90)
    result = run_wermit(f"echo N=[\\ffiles({d}/*)] F=[\\fnextfile()]")
    _assert_clean(result)
    assert f"N=[1] F=[{d}/{'s' * 90}]" in result.stdout, result.stdout


def test_wildcard_literal_segment_past_path_buffer(run_wermit, tmp_path):
    """Verify a literal segment after a long match is not found.

    The pattern is DIR/*/NAME.  The "*" segment matches a 241-byte
    directory name.  The matched prefix is then longer than the pattern.
    Adding the 250-byte literal NAME exceeds the path buffer.
    """
    path_max, _ = _path_limits(tmp_path)
    d = _dir_of_length(tmp_path, path_max - 320)
    os.mkdir(os.path.join(d, "x" * 241))
    pattern = f"{d}/*/{'f' * 250}"
    assert len(pattern) < path_max
    result = run_wermit(f"echo N=[\\ffiles({pattern})]")
    _assert_clean(result)
    assert "N=[0]" in result.stdout, result.stdout


MIDDLE_TREE = ["a/g", "a/xq/f", "a/xq/h.txt", "a/xq/yz/f", "a/.hd/f",
               "b/xr/f"]


def _list_matches(run_wermit, tmp_path, function, pattern):
    """Return sorted matches from \\f<function>(pattern) in MIDDLE_TREE."""
    d = tmp_path / "d"
    for name in MIDDLE_TREE:
        (d / name).parent.mkdir(parents=True, exist_ok=True)
        (d / name).write_text("x")
    pattern = pattern.replace("DIR", str(d))
    script = tmp_path / "t.ksc"
    script.write_text(
        f"cd {d}\n"
        f"echo COUNT=[\\f{function}({pattern})]\n"
        "while true {\n"
        "    assign f \\fnextfile()\n"
        "    if not def f break\n"
        "    echo NAME=[\\m(f)]\n"
        "}\n")
    result = run_wermit(f"take {script}")
    names = sorted(line[6:-1].replace(f"{d}/", "DIR/")
                   for line in result.stdout.splitlines()
                   if line.startswith("NAME=["))
    assert f"COUNT=[{len(names)}]" in result.stdout, result.stdout
    return names


@pytest.mark.parametrize("pattern,expected", [
    ("a/x*/f", ["a/xq/f"]),
    ("a/?q/f", ["a/xq/f"]),
    ("a/[x]q/f", ["a/xq/f"]),
    ("*/x*/f", ["a/xq/f", "b/xr/f"]),
    ("a/*/y*/f", ["a/xq/yz/f"]),
    ("a/x*/yz/f", ["a/xq/yz/f"]),
    ("*/x?/*", ["a/xq/f", "a/xq/h.txt", "b/xr/f"]),
    ("a/.*/f", ["a/.hd/f"]),
    ("a/*/f", ["a/xq/f"]),
    ("a/z*/f", []),
    ("DIR/*/x*/f", ["DIR/a/xq/f", "DIR/b/xr/f"]),
])
def test_wildcard_in_middle_segment(run_wermit, tmp_path, pattern,
                                    expected):
    """Verify a non-final wildcard segment matches directory names.

    The segment pattern matches the directory name only.  A directory
    whose name starts with '.' matches only a segment that starts with
    '.'.
    """
    assert _list_matches(run_wermit, tmp_path, "files", pattern) == \
        expected


def test_wildcard_in_middle_segment_directories(run_wermit, tmp_path):
    """Verify \\fdirectories() with a wildcard in a middle segment."""
    assert _list_matches(run_wermit, tmp_path, "directories",
                         "*/x?/*") == ["a/xq/yz"]

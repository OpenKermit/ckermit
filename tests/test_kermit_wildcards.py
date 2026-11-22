"""Tests for Kermit wildcard matching of file names (ckmatch())."""
import os
import random
import re
import shutil

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


@pytest.fixture
def long_path_base(tmp_path):
    """Return a directory for paths near PATH_MAX.

    Remove the directory at teardown whether or not the test passed.
    Tools that remove a tree by full path name fail on paths past
    PATH_MAX.  shutil.rmtree() works relative to directory file
    descriptors where the platform supports them.
    """
    base = tmp_path / "long"
    base.mkdir()
    yield base
    shutil.rmtree(base, ignore_errors=True)


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


def test_wildcard_match_past_path_buffer_skipped(run_wermit,
                                                 long_path_base):
    """Verify a match too long for the path buffer is skipped.

    The directory path is about PATH_MAX - 100 bytes.  A 250-byte name
    in that directory does not fit in the path buffer and is not listed.
    A 90-byte name fits and is listed.
    """
    path_max, _ = _path_limits(long_path_base)
    d = _dir_of_length(long_path_base, path_max - 100)
    _touch_at(d, "l" * 250)
    _touch_at(d, "s" * 90)
    result = run_wermit(f"echo N=[\\ffiles({d}/*)] F=[\\fnextfile()]")
    _assert_clean(result)
    assert f"N=[1] F=[{d}/{'s' * 90}]" in result.stdout, result.stdout


def test_wildcard_literal_segment_past_path_buffer(run_wermit,
                                                   long_path_base):
    """Verify a literal segment after a long match is not found.

    The pattern is DIR/*/NAME.  The "*" segment matches a 241-byte
    directory name.  The matched prefix is then longer than the pattern.
    Adding the 250-byte literal NAME exceeds the path buffer.
    """
    path_max, _ = _path_limits(long_path_base)
    d = _dir_of_length(long_path_base, path_max - 320)
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


@pytest.mark.parametrize("string,pattern,expected", [
    ("a.b.c", "*.{c,d}", True),
    ("a.b.e", "*.{c,d}", False),
    ("xa.c.a.d", "*a.{c,d}", True),
    ("a.bc.d", "*.?", True),
    ("a.b.cx", "*.[bc]x", True),
    ("/x-1.2/.tmp/pic.jpg", "*.{jpg,jpeg,gif}", True),
    ("/x-1.2/.tmp/pic.png", "*.{jpg,jpeg,gif}", False),
    ("ay", "{*[x]q,*y}", True),
    ("ab", "{*[x]q,ab}", True),
])
def test_match_literal_after_star(run_wermit, string, pattern, expected):
    """Verify '*' and a literal try each occurrence of the literal.

    The rest of the pattern after the literal can need a later
    occurrence than the first.  A failed brace alternative leaves the
    next alternative to be tried.
    """
    result = run_wermit(
        f"if match {string} {{{pattern}}} echo RESULT=YES, "
        "else echo RESULT=NO")
    want = "RESULT=YES" if expected else "RESULT=NO"
    assert want in result.stdout, result.stdout


@pytest.mark.parametrize("string,pattern,expected", [
    ("a.b.jpg", "*.{jpg,gif}", True),
    ("/p.q/pic.jpeg", "*.{jpg,jpeg,gif}", True),
    ("a.yb.zx", "*.?x", True),
    ("x.tar.tar.gz", "*.tar.{gz,bz2}", True),
    ("a.b.jpg", "a*.{jpg}", True),
    ("ab.jpg", "*.{jpg,gif}", True),
    ("a.b.png", "*.{jpg,gif}", False),
    ("a.yb.zy", "*.?x", False),
])
def test_match_star_literal_backtracks(run_wermit, tmp_path, string,
                                       pattern, expected):
    """Verify IF MATCH and \\fsearch() agree on '*', literal, and meta.

    The literal that follows '*' can need a later occurrence than the
    first.  \\fsearch() returns 1 for a match that starts at the first
    character and 0 for no match.
    """
    script = tmp_path / "t.ksc"
    script.write_text(
        f"if match {{{string}}} {{{pattern}}} echo M=[1]\n"
        f"echo S=[\\fsearch({pattern},{string})]\n")
    result = run_wermit(f"take {script}")
    assert ("M=[1]" in result.stdout) == expected, result.stdout
    search = "S=[1]" if expected else "S=[0]"
    assert search in result.stdout, result.stdout


@pytest.mark.parametrize("pattern,string,expected", [
    ("?b", "ab", 1),
    ("?.b", "xa.b", 2),
    ("[ab]c", "zbc", 2),
    ("\\\\-c", "ab-c", 3),
    ("a?c", "zabc", 2),
    ("*ab*[xy]", "abde.x", 1),
    ("ab*[xy]", "zabde.x", 2),
    ("ab*?y", "zabdexy", 2),
    ("*ab*{x,y}", "abde.ab.x", 1),
    ("ab*{x,y}", "zabcxy", 2),
    ("{x,y}?", "abyz", 3),
    ("?b", "xyz", 0),
])
def test_search_returns_leftmost_position(run_wermit, tmp_path, pattern,
                                          string, expected):
    """Verify \\fsearch() returns the start of the leftmost match.

    The match can start with '?', '[', a quoted character, or a brace
    group.  A failed try after '*' does not change the start.
    """
    script = tmp_path / "t.ksc"
    script.write_text(f"echo S=[\\fsearch({{{pattern}}},{{{string}}})]\n")
    result = run_wermit(f"take {script}")
    assert f"S=[{expected}]" in result.stdout, result.stdout


@pytest.mark.parametrize("call,expected", [
    ("\\fsearch(b,bb,1,2)", 2),
    ("\\fsearch(?,abc,1,2)", 2),
    ("\\fsearch(?,abc,1,3)", 3),
    ("\\fsearch(?,abc,1,4)", 0),
    ("\\fsearch([ab]c,zbczbc,1,2)", 5),
    ("\\findex(aa,aaa,1,2)", 2),
    ("\\findex(aa,aaa,1,3)", 0),
    ("\\frsearch(b,bb)", 2),
    ("\\frsearch(b,bb,1)", 2),
    ("\\frsearch(b,bb,2)", 1),
    ("\\frsearch(b,bb,3)", 0),
    ("\\frsearch(b,bb,,2)", 1),
])
def test_search_offset_and_occurrence(run_wermit, tmp_path, call,
                                      expected):
    """Verify the offset and occurrence arguments of the search functions.

    The nth occurrence from the left starts after the start of the
    previous occurrence.  For offset n, \\frsearch() ignores the
    rightmost n - 1 characters.
    """
    script = tmp_path / "t.ksc"
    script.write_text(f"echo R=[{call}]\n")
    result = run_wermit(f"take {script}")
    assert f"R=[{expected}]" in result.stdout, result.stdout


@pytest.mark.parametrize("occurrence", [0, -1])
def test_search_occurrence_below_one_skips_matching(run_wermit, tmp_path,
                                                   occurrence):
    """Verify \\fsearch() skips matching for an occurrence below 1.

    The debug log records each matcher call as "CKMATCH ENTRY".  An
    occurrence below 1 makes no matcher call.  Occurrence 1 calls the
    matcher and confirms that the debug log records "CKMATCH ENTRY".
    """
    log = tmp_path / "debug.log"
    script = tmp_path / "t.ksc"
    script.write_text(
        f"log debug {log}\n"
        f"echo R=[\\fsearch(a,aaaaaaaa,1,{occurrence})]\n"
        "close debug\n"
        f"log debug {tmp_path / 'one.log'}\n"
        "echo O=[\\fsearch(a,aaaaaaaa,1,1)]\n"
        "close debug\n")
    result = run_wermit(f"take {script}")
    assert "R=[0]" in result.stdout, result.stdout
    assert "O=[1]" in result.stdout, result.stdout
    assert b"CKMATCH ENTRY" in (tmp_path / "one.log").read_bytes()
    assert b"CKMATCH ENTRY" not in log.read_bytes()


def _random_pattern(rng, depth=0, maxlen=5):
    """Return a random pattern as a (Kermit pattern, regex) pair.

    Tokens are 'a', 'b', '.', '?', '*', "[ab]", and brace groups.  Brace
    groups nest two deep and can hold empty alternatives.  In the regex,
    '*' is ".*", '?' is ".", and a brace group is an alternation.
    """
    kermit, regex = "", ""
    for _ in range(rng.randint(0, maxlen)):
        r = rng.random()
        if r < 0.35:
            c = rng.choice("ab.")
            kermit += c
            regex += re.escape(c)
        elif r < 0.5:
            kermit += "?"
            regex += "."
        elif r < 0.7:
            kermit += "*"
            regex += ".*"
        elif r < 0.78:
            kermit += "[ab]"
            regex += "[ab]"
        elif depth < 2:
            alts = [_random_pattern(rng, depth + 1, 3)
                    for _ in range(rng.randint(1, 3))]
            kermit += "{" + ",".join(a[0] for a in alts) + "}"
            regex += "(?:" + "|".join(a[1] for a in alts) + ")"
    return kermit, regex


def test_match_random_patterns(run_wermit, tmp_path):
    """Verify IF MATCH and \\fsearch() against a regex reference.

    The patterns come from _random_pattern() with a fixed seed.  The
    strings hold 1 to 7 characters from "ab.".  IF MATCH matches the
    whole string.  \\fsearch() returns 1 plus the first index where the
    regex matches a prefix of the rest of the string, or 0.  Kermit
    strips one level of braces from a function argument, so the script
    wraps each \\fsearch() pattern in braces.
    """
    rng = random.Random(56)
    cases = []
    while len(cases) < 3000:
        pattern, regex = _random_pattern(rng)
        if pattern:
            string = "".join(rng.choice("ab.")
                             for _ in range(rng.randint(1, 7)))
            cases.append((pattern, string, re.compile(regex, re.S)))
    lines = []
    for i, (pattern, string, _) in enumerate(cases):
        lines.append(f"if match {{{string}}} {{{pattern}}} echo M {i}")
        lines.append(f"echo S {i} \\fsearch({{{pattern}}},{string})")
    script = tmp_path / "t.ksc"
    script.write_text("\n".join(lines) + "\n")
    result = run_wermit(f"take {script}", timeout=120)
    matched = set()
    found = {}
    for line in result.stdout.splitlines():
        words = line.split()
        if len(words) == 2 and words[0] == "M":
            matched.add(int(words[1]))
        elif len(words) == 3 and words[0] == "S":
            found[int(words[1])] = int(words[2])
    wrong = []
    for i, (pattern, string, rx) in enumerate(cases):
        want = next((k + 1 for k in range(len(string))
                     if rx.match(string, k)), 0)
        if (i in matched) != bool(rx.fullmatch(string)):
            wrong.append(f"IF MATCH {{{string}}} {{{pattern}}}")
        if found.get(i) != want:
            wrong.append(f"\\fsearch({pattern},{string}) = "
                         f"{found.get(i)} instead of {want}")
    assert not wrong, "\n".join(wrong[:20])


def test_input_pattern_match_text(run_wermit):
    """Verify \\v(inmatch) starts where an INPUT pattern match starts.

    INPUT checks the pattern after each character, so the match ends
    at the 'b'.
    """
    result = run_wermit(
        "set host /pty printf zzabc-xy, if fail exit 1, "
        "input 5 {\\fpattern(?b)}, echo I=[\\v(inmatch)], close")
    assert "I=[ab]" in result.stdout, result.stdout


def test_wildcard_brace_after_inner_dot(run_wermit, tmp_path):
    """Verify "*.{jpg,gif}" matches file names with more than one dot."""
    d = tmp_path / "d"
    d.mkdir()
    for name in ["a.b.jpg", "ab.gif", "c.d.txt"]:
        (d / name).write_text("x")
    script = tmp_path / "t.ksc"
    script.write_text(
        f"cd {d}\n"
        "echo COUNT=[\\ffiles(*.{jpg,gif})]\n")
    result = run_wermit(f"take {script}")
    assert "COUNT=[2]" in result.stdout, result.stdout


@pytest.mark.parametrize("string,pattern,expected", [
    ("bbab..a", "{ab,.}?", False),
    ("abxabc", "ab{c}", False),
    ("xfoo.c", "{foo,bar}.?", False),
    ("foo.c", "{foo,bar}.?", True),
    ("a", "a{,b}", True),
    ("ab", "a{,b}", True),
    ("b", "b**", True),
    ("a", "a*{,a}", True),
    ("..a..", "*.{,a}", True),
    ("x", "*{,}", True),
    ("x", "*{,*b}", True),
    ("a.x.", "*.{,*b}", True),
    ("x", "{,}", False),
    ("ab", "a{,}", False),
    ("ab", "{a,{b,.}}b", True),
    ("bb", "{a,{b,.}}b", True),
    ("cb", "{a,{b,.}}b", False),
    ("bbabb", "{a,{b,.}}**", True),
])
def test_match_brace_in_place(run_wermit, tmp_path, string, pattern,
                              expected):
    """Verify each brace alternative matches at the current position.

    The alternative and the rest of the pattern must match the text
    that follows.  The alternative cannot skip text unless a '*'
    precedes the braces.  An empty alternative matches no text,
    including at the end of the string.  Braces can nest.
    """
    script = tmp_path / "t.ksc"
    script.write_text(
        f"if match {{{string}}} {{{pattern}}} echo M=[1]\n"
        "else echo M=[0]\n")
    result = run_wermit(f"take {script}")
    assert f"M=[{int(expected)}]" in result.stdout, result.stdout

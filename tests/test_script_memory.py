"""Tests for memory errors reachable from script functions and commands.

Each case runs a short script and then echoes a marker.  Out-of-bounds
access shows only under AddressSanitizer.  A normal build checks that
wermit reaches the marker without a signal.
"""
import pytest

LONG = "d" * 5000

CASES = {
    "zjdate": "echo [\\fdayofyear(20240101 12:00:00)]"
              "[\\fdoy(20240101 12:00:00)][\\fjdate(20240101 12:00:00)]",
    "zjdate_bad_month": "echo [\\fdoy(20241301)][\\fdoy(20240001)]",
    "jzdate_long_time": "echo [\\fdoy2date(2024032 12:00:00" + LONG + ")]",
    "kwvalue_no_equals": "echo [\\fkeywordvalue(abc)]",
    "kwvalue_numeric": "echo [\\fkwvalue(1e308,\\255)]",
    "substring_nonnumeric_start": "echo [\\fsubstring(hello world,o)]",
    "lopx_no_separator": "echo [\\flopx(abc)]",
    "lopx_space": "echo [\\flopx(a b)]",
    "lop_zero_count": "echo [\\flop(abc,0,0)]",
    "squeeze_empty": "echo [\\fsqueeze()]",
    "pictureinfo_no_arg": "echo [\\fpictureinfo()]",
    "show_variables": "show variables\necho [\\v(platform)]",
    "fpadd_many_places": "echo [\\ffpadd(1,2,5000)]",
    "fpraise_negative_places": "echo [\\ffpraise(2,7,-2147483649)]",
    "round_huge": "echo [\\fsexpression(round 1e300)]\n(round 1e300)",
    "fileinfo_empty": "echo [\\ffileinfo(,&a)]",
    "mxlook_setq": "(setq (setq 3.5 (let)))",
    "mxlook_decrement": "(-- (+ y (+) y) 1)",
    "rpad_huge_count": "echo [\\frpad(abc,2147483647,1)]",
    "lpad_huge_count": "echo [\\flpad(abc,2147483647,-)]",
    "dirname_long": "echo [\\fdirname(" + LONG + ")]",
    "strcmp_long_length": "echo [\\fstrcmp(a,b,0,1000)]"
                          "[\\fstrcmp(a,b,1,9223372036854775807)]",
    "ipaddress_huge_index":
        "echo [\\fipaddress({a b},2147483647,&a)]",
    "declare_huge_array": "declare \\&a[2147483647]",
    "file_negative_channel": "file open /write \\%o out.txt\n"
                             "file seek \\%c -1\nfile seek -1 0\n"
                             "file flush -1\nfile close -1\n"
                             "file write -1 x\nfile read -1 \\%x\n"
                             "echo [\\f_eof(-1)][\\f_pos(-1)]",
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_script_function_memory(run_wermit, tmp_path, name):
    """Verify a script reaches its end marker without a memory error."""
    script = tmp_path / "t.ksc"
    script.write_text(CASES[name] + "\necho END-MARKER\n")
    result = run_wermit(f"cd {tmp_path}, take {script}", timeout=30)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "END-MARKER" in result.stdout, (result.stdout[-2000:],
                                           result.stderr[-2000:])


@pytest.mark.parametrize("args,sign", [
    ("abc,abc", 0),
    ("abc,abd", -1),
    ("abd,abc", 1),
    ("abc,ABC,0", 0),
    ("abc,ABC,1", 1),
    ("xbc,abc,0,2", 0),
    ("abcx,abcy,0,1,3", 0),
    ("abc,abd,0,-5", -1),
])
def test_strcmp_compares_arguments(run_wermit, tmp_path, args, sign):
    """Verify \\fstrcmp() compares its first two arguments."""
    script = tmp_path / "t.ksc"
    script.write_text(f"echo RESULT=[\\fstrcmp({args})]\n")
    result = run_wermit(f"take {script}")
    value = int(result.stdout.split("RESULT=[")[1].split("]")[0])
    assert (value > 0) - (value < 0) == sign, result.stdout


@pytest.mark.parametrize("func", ["rfiles", "files", "rdirectories"])
def test_file_list_overflow_stops(run_wermit, tmp_path, func):
    """Verify file expansion stops adding names once the list is full.

    SET FILE LISTSIZE makes the name list smaller than the number of
    matches in a directory tree.
    """
    top = tmp_path / "tree"
    for d in range(4):
        sub = top / f"d{d}"
        sub.mkdir(parents=True)
        for i in range(40):
            (sub / f"f{i:02d}.txt").write_text("x")
    for i in range(40):
        (top / f"t{i:02d}.txt").write_text("x")
    script = tmp_path / "t.ksc"
    script.write_text(f"set file listsize 16\n"
                      f"echo [\\f{func}({top}/*)]\n"
                      f"echo [\\f{func}({top}/d0/*)]\n"
                      "echo END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=30)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "END-MARKER" in result.stdout, result.stdout[-2000:]


def test_take_error_message_long_file_name(run_wermit, tmp_path):
    """Verify an error in a TAKE file with a 90-character name.

    newerrmsg() shortens a long command line to fit beside the file
    name.  With a long name the room left is negative and must not
    index before the command buffer.  The underflow shows only under
    AddressSanitizer.
    """
    script = tmp_path / ("t" * 86 + ".ksc")
    script.write_text("nosuchcommand " + "x" * 100 + "\n"
                      "echo END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=30)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "END-MARKER" in result.stdout, result.stdout[-2000:]
    assert "nosuchcommand" in result.stdout + result.stderr


@pytest.mark.parametrize("command", [
    "ask /timeout:1 \\%a {Q? }",
    "show key",
    "getc \\%c {x? }",
    "getc /timeout:1 \\%c {x? }",
])
def test_console_reads_end_at_eof(wermit_path, command):
    """Verify console reads stop when stdin is at end of file.

    Run from cron, stdin is often /dev/null.  These commands must end
    instead of looping and filling the output.
    """
    import subprocess
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         f"set command more-prompting off, {command}, exit"],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=20,
        start_new_session=True)
    assert len(result.stdout) < 2000, result.stdout[:200]


@pytest.mark.parametrize("length", [10, 300, 3000])
def test_while_long_condition(run_wermit, tmp_path, length):
    """Verify WHILE runs with a condition of the given length.

    The condition compares a variable with a string of length bytes.
    The loop body sets the variable to that string, so the body runs
    once.
    """
    word = "w" * length
    script = tmp_path / "w.ksc"
    script.write_text(
        ".\\%n = 0\n"
        ".\\%s = x\n"
        f"while not equal \"\\%s\" \"{word}\" "
        f"{{ .\\%s := {word}, incr \\%n }}\n"
        "echo COUNT=[\\%n] LEN=[\\flen(\\%s)]\n"
        "echo END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=30)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert f"COUNT=[1] LEN=[{length}]" in result.stdout, (
        result.stdout[-2000:])


def test_get_path_too_many_directories(run_wermit, tmp_path):
    """Verify SET SERVER GET-PATH refuses more than 128 directories.

    The 129th name was stored one past the parser's array before the
    count was checked.  The overflow shows only under AddressSanitizer.
    """
    names = []
    for i in range(130):
        (tmp_path / f"d{i:03d}").mkdir()
        names.append(f"d{i:03d}")
    script = tmp_path / "gp.ksc"
    script.write_text(f"cd {tmp_path}\n"
                      "set server get-path " + " ".join(names) + "\n"
                      "echo STATUS=[\\v(status)]\n"
                      "echo END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=30)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "Too many directories" in result.stdout, result.stdout[-500:]
    assert "END-MARKER" in result.stdout, result.stdout[-500:]


@pytest.mark.parametrize("call,want", [
    ("\\fstripb(x,x)", "[x]"), ('\\fstripb(",1)', '["]'),
    ("\\fstripb((ab))", "[ab]"), ("\\fstripb({ab},2)", "[ab]")],
    ids=["one-char-same", "one-char-numeric", "parens", "numeric"])
def test_stripb_short_strings(run_wermit, tmp_path, call, want):
    """Verify \\fstripb() returns a one-character string unchanged.

    One character cannot hold both an opening and a closing bracket.
    Longer strings lose their outer pair.
    """
    script = tmp_path / "t.ksc"
    script.write_text(f"echo [{call}]\necho END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=30)
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert want in result.stdout, result.stdout


def test_aaconvert_same_array_twice(run_wermit, tmp_path):
    """Verify \\faaconvert() refuses one array for names and values.

    Declaring the value array frees the name array when both are the
    same.  The function must return its bad-array error.
    """
    script = tmp_path / "t.ksc"
    script.write_text("define x<one> 1\ndefine x<two> 2\n"
                      "echo [\\faaconvert(x,&a,&a)]\necho END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=30)
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "ARG_BAD_ARRAY" in result.stdout, result.stdout
    assert "END-MARKER" in result.stdout, result.stdout


@pytest.mark.parametrize("order", ["first-exists", "second-exists"])
def test_filecompare_missing_file(run_wermit, tmp_path, order):
    """Verify \\ffilecompare() returns -1 when one file cannot be opened."""
    (tmp_path / "a.txt").write_text("x\n")
    a, b = str(tmp_path / "a.txt"), str(tmp_path / "missing")
    if order == "second-exists":
        a, b = b, a
    result = run_wermit(f"echo [\\ffilecompare({a},{b})], echo END-MARKER",
                        timeout=30)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "[-1]" in result.stdout, result.stdout


def test_file_list_empty_pattern_with_array(run_wermit, tmp_path):
    """Verify a file-list function with an empty pattern ends its list.

    \\fdirectories() with an empty pattern and an array counts no files
    but read a name left from an earlier expansion into its list.  The
    list then had no terminator, and the next call read past it.
    """
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.txt").write_text("x\n")
    script = tmp_path / "t.ksc"
    script.write_text("set take error off\n"
                      "if numeric \\fdirecto(\\%a,&a,abc) echo T\n"
                      "echo [\\fdirectories(*)]\n"
                      "echo [\\fdirectories(*)]\n"
                      "echo END-MARKER\n")
    result = run_wermit(f"cd {tmp_path}, take {script}", timeout=30)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "END-MARKER" in result.stdout, result.stdout

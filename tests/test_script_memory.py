"""Tests for memory errors reachable from script functions and commands.

Each case runs a short script and then echoes a marker.  Out-of-bounds
access shows only under AddressSanitizer.  A normal build checks that
wermit reaches the marker without a signal.
"""
import re

import pytest

from conftest import scaled

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
    "if_declared_long_name": ".x := \\frepeat(a,40)\n"
                             "if declared \\m(x) echo YES",
    "array_subscript_16_chars": "declare \\&a[3]\n"
                                "echo [\\&a[0000000000000001]]",
    "sexp_increment_32_chars":
        "define \\%x 12345678901234567890123456789012\n"
        "(++ \\\\\\\\%x)",
    "function_name_64_chars": "echo [\\f" + "a" * 64 + "(1)]",
    "macro_name_expands_long": ".n := \\frepeat(a,4096)\n"
                               "echo [\\m(\\m(n))]",
    "macro_argument_too_long": ".c := \\frepeat(x,20000)\n"
                               "define mymac { echo \\flen(\\%1) }\n"
                               "mymac \\m(c)\\m(c)",
    "dial_pbx_prefix_long": "set dial country-code 1\n"
                            "set dial area-code 215\n"
                            "set dial pbx-exchange 555\n"
                            "set dial pbx-inside-prefix \\frepeat(9,40)\n"
                            "lookup +1 (215) 5551234\n"
                            "lookup +12155551234",
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
def test_strcmp_compares_arguments(run_wermit, tmp_path, monkeypatch,
                                   args, sign):
    """Verify \\fstrcmp() compares its first two arguments.

    ckstrcmp() compares characters with strcoll().  The C locale gives
    the byte order the expected signs assume.  In en_US.UTF-8 on macOS,
    "a" sorts before "A".
    """
    monkeypatch.setenv("LC_ALL", "C")
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


def test_log_reopen_does_not_leak_descriptors(run_wermit, tmp_path):
    """Verify reopening an existing log file leaves no descriptor open."""
    import os
    if not os.path.isdir("/proc/self/fd"):
        pytest.skip("no /proc/self/fd")
    script = tmp_path / "t.ksc"
    log = tmp_path / "t.log"
    script.write_text(
        "run ls /proc/$PPID/fd | wc -l\n"
        f"for \\%i 1 30 1 {{ log transactions {log} append, "
        "close transactions }\n"
        "run ls /proc/$PPID/fd | wc -l\n")
    result = run_wermit(f"take {script}")
    counts = [int(x) for x in result.stdout.split() if x.isdigit()]
    assert len(counts) == 2, result.stdout
    assert counts[1] <= counts[0] + 1, counts


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
        stdin=subprocess.DEVNULL, capture_output=True, timeout=scaled(20),
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


def _maxrss_kb(wermit_path, cmds):
    """Run wermit with cmds and return its peak resident size in KB.

    The figure includes the forked parent's size before exec(), so
    compare it only with another run from the same process.
    """
    import os
    import subprocess
    proc = subprocess.Popen(
        [wermit_path, "-H", "-Y", "-Q", "-C", cmds],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
    _, status, usage = os.wait4(proc.pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0, status
    # ru_maxrss is in bytes on macOS and kilobytes elsewhere.
    unit = 1024 if os.uname().sysname == "Darwin" else 1
    return usage.ru_maxrss // unit


@pytest.mark.slow
def test_function_empty_last_argument_does_not_leak(wermit_path):
    """Verify a function call whose last argument is empty frees it.

    fneval() drops empty trailing arguments from its count.  A leak of
    one argument buffer per call raises the peak resident size by about
    29 MB over 10,000 calls on Linux.  A run with a non-empty argument
    is the baseline.

    On FreeBSD, ru_maxrss of a forked child sometimes includes the
    parent's resident size.  A wermit that only runs EXIT reports a
    peak of the parent's size plus 14 MB in about one run in four.  The
    excess follows the parent's size and not wermit's work.  The
    smallest of three runs excludes it.  The leak this test detects
    adds to every run.
    """
    loop = "for \\%i 1 10000 1 {{ .x := \\flength({}) }}, exit"
    base = min(_maxrss_kb(wermit_path, loop.format("abc"))
               for _ in range(3))
    empty = min(_maxrss_kb(wermit_path, loop.format("\\%z"))
                for _ in range(3))
    assert empty - base < 15 * 1024, (base, empty)


def test_file_list_overflow_closes_directories(wermit_path, tmp_path):
    """Verify a full file list closes the directories being read.

    traverse() stops reading d0 when the list fills, and Kermit prints
    the overflow message.  With 40 descriptors, a leak of one directory per
    call leaves none to open d0 after about 36 calls, and the message
    stops.
    """
    import resource
    import subprocess
    top = tmp_path / "tree"
    for d in range(2):
        sub = top / f"d{d}"
        sub.mkdir(parents=True)
        for i in range(40):
            (sub / f"f{i:02d}.txt").write_text("x")

    def limit():
        resource.setrlimit(resource.RLIMIT_NOFILE, (40, 40))
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         "set file listsize 16, "
         f"for \\%i 1 200 1 {{ .n := \\frfiles({top}/*) }}, exit"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=scaled(60), preexec_fn=limit)
    out = result.stdout + result.stderr
    assert out.count("Too many files") == 200, out[-500:]


def test_fileinfo_bom_file_closes_it(wermit_path, tmp_path):
    """Verify scanning a file that starts with a BOM closes it.

    \\ffileinfo() runs scanfile().  scanfile() returns early for a BOM.
    With 40 descriptors, a FILE left open per call stops the scan within
    200 calls, and element 9 goes missing.
    """
    import resource
    import subprocess
    bom = tmp_path / "bom.txt"
    bom.write_bytes(b"\xef\xbb\xbfhello\n")

    def limit():
        resource.setrlimit(resource.RLIMIT_NOFILE, (40, 40))
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         f"for \\%i 1 200 1 {{ .n := \\ffileinfo({bom},&a) }}, "
         "echo SCAN=[\\&a[9]], exit"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=scaled(60), preexec_fn=limit)
    assert "SCAN=[text:utf8]" in result.stdout, result.stdout


@pytest.mark.parametrize("cmd", ["copy /fromb64 e.txt d.txt",
                                 "copy /append p.txt p.txt"],
                         ids=["fromb64", "same-file"])
def test_copy_closes_its_files(wermit_path, tmp_path, cmd):
    """Verify COPY /FROMB64 and a refused same-file COPY close files.

    Each command runs 60 times with a limit of 40 descriptors.  A FILE
    left open per command stops the later COPY commands.
    """
    import resource
    import subprocess
    (tmp_path / "p.txt").write_text("hello world\n")
    (tmp_path / "e.txt").write_text("aGVsbG8gd29ybGQK\n")

    def limit():
        resource.setrlimit(resource.RLIMIT_NOFILE, (40, 40))
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         f"for \\%i 1 200 1 {{ {cmd} }}, "
         "copy /tob64 p.txt last.txt, echo LAST=\\v(status), exit"],
        cwd=tmp_path, stdin=subprocess.DEVNULL, capture_output=True,
        text=True, timeout=scaled(60), preexec_fn=limit)
    assert "LAST=0" in result.stdout, result.stdout[-500:]


def test_cvtdate_apache_format_does_not_leak(wermit_path, valgrind):
    """Verify \\fcvtdate() of an Apache log date frees its copy.

    cmcvtdate() copies an Apache log date without its colons.  valgrind
    reports no block lost in cmcvtdate().
    """
    import os
    import re
    import subprocess
    result = subprocess.run(
        [valgrind, "-q", "--leak-check=full", wermit_path,
         "-H", "-Y", "-Q", "-C",
         "for \\%i 1 20 1 { .x := "
         "\\fcvtdate([02/Jan/2024:03:04:05 +0000]) }, "
         "echo X=\\m(x), exit"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=scaled(120), env=dict(os.environ, TZ="UTC"))
    assert "X=20240102 03:04:05" in result.stdout, result.stdout
    records = re.split(r"^==\d+== *$", result.stderr, flags=re.M)
    leaked = [r for r in records
              if "definitely lost" in r and "cmcvtdate" in r]
    assert not leaked, result.stderr


def test_get_path_too_many_directories(run_wermit, tmp_path):
    """Verify SET SERVER GET-PATH refuses more than 128 directories.

    The parser's array holds 128 names.  Writing a 129th name past the
    array shows under AddressSanitizer.
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


@pytest.mark.parametrize("value,want", [
    ("'(qq)", "qq"), ("'abc", "abc"), ("'(a b)", "a b")])
def test_sexp_quoted_variable_value(run_wermit, tmp_path, value, want):
    """Verify an S-expression returns a variable's quoted value.

    A variable whose value starts with a quote evaluates to the value
    after the quote, with one pair of outer parentheses removed.  x is
    one character, so dosexp() takes it without splitting.
    """
    script = tmp_path / "t.ksc"
    script.write_text(f".x := {value}\n.long := {value}\n"
                      "echo X=[\\fsexpression(x)]\n"
                      "echo LONG=[\\fsexpression(long)]\n")
    result = run_wermit(f"take {script}", timeout=30)
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert f"X=[{want}]" in result.stdout, result.stdout
    assert f"LONG=[{want}]" in result.stdout, result.stdout


def test_sexp_operator_string_has_no_debug_output(run_wermit, tmp_path):
    """Verify an S-expression operator that yields a string prints nothing.

    The operator position holds an S-expression whose value is a quoted
    '(string).  dosexp() reports the bad operator and prints no other
    line.
    """
    script = tmp_path / "t.ksc"
    script.write_text("set take error off\n((quote '(xyz)) 2)\n"
                      "echo END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=30)
    assert "END-MARKER" in result.stdout, result.stdout
    assert "XXX" not in result.stdout, result.stdout


def test_sexp_quoted_group_arguments(run_wermit, tmp_path):
    """Verify cksplit() keeps each quoted S-expression group whole.

    A macro called from an S-expression gets each quoted '(...) group as
    one argument.  Each length from 1 to 200 reuses the word buffers of
    the split before it.  The macro must get exactly the group's text.
    """
    script = tmp_path / "t.ksc"
    script.write_text(
        "define m {\n"
        "    if not equal {\\%1} {\\m(s) b} "
        "echo BAD=[\\%1] [\\m(s) b]\n"
        "    return 1\n"
        "}\n"
        "for \\%i 1 200 1 {\n"
        "    .s := \\frepeat(a,\\%i)\n"
        "    (m '(\\m(s) b) '(c d) '(e f))\n"
        "}\n"
        "echo END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=60)
    out = result.stdout + result.stderr
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "END-MARKER" in result.stdout, out[-2000:]
    assert "BAD=" not in result.stdout, result.stdout[-2000:]


def test_sexp_empty_first_expression(run_wermit):
    """Verify an empty first S-expression returns an empty value.

    \\fsexpression() with an empty first argument and a second argument
    evaluates an empty S-expression.  As the first S-expression of the
    session, it runs before the result stack exists.
    """
    result = run_wermit("echo [\\fsexpression(,1)], echo END-MARKER",
                        timeout=30)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "[]" in result.stdout, result.stdout
    assert "END-MARKER" in result.stdout, result.stdout


@pytest.mark.parametrize("limit", [10, 1, 0, -1])
def test_sexp_depth_limit_edges(run_wermit, tmp_path, limit):
    """Verify S-expressions at and past the depth limit stay in bounds.

    The result stack has one entry for each level.  An S-expression
    nested exactly to SET SEXPRESSION DEPTH-LIMIT uses the last level.
    One level deeper reports the limit and uses one more entry.
    """
    d = max(limit, 1)
    script = tmp_path / "t.ksc"
    script.write_text(
        "set take error off\n"
        f"set sexpression depth-limit {limit}\n"
        + "(" * d + "1" + ")" * d + "\n"
        + "(" * (d + 1) + "1" + ")" * (d + 1) + "\n"
        "echo END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=30)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "depth limit exceeded" in result.stdout, result.stdout
    assert "END-MARKER" in result.stdout, result.stdout


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


def test_assign_value_too_long_is_cut(run_wermit, tmp_path):
    """Verify ASSIGN stores a terminated value when it does not fit.

    The value of b expands to 60000 characters, more than line[] holds.
    ASSIGN stores the part that fits.  Under AddressSanitizer, addmac()
    must not read past line[].
    """
    script = tmp_path / "t.ksc"
    script.write_text("set take error off\n"
                      ".a := \\frepeat(a,30000)\n"
                      ".b := \\m(a)\\m(a)\n"
                      "echo ST=\\v(status)\n"
                      "echo END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=30)
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "ST=0" in result.stdout, result.stdout[-500:]
    assert "END-MARKER" in result.stdout, result.stdout[-500:]


def test_assign_counts_each_copied_value(run_wermit, tmp_path):
    """Verify ASSIGN counts every byte of each macro value it copies.

    The value is 32760 characters from one macro and 200 from a
    one-character macro.  The total is more than line[] holds, so ASSIGN
    stores only the part that fits.  SHOW MACRO prints the stored value
    and ends each wrapped line with a hyphen.
    """
    script = tmp_path / "t.ksc"
    script.write_text("set take error off\n"
                      ".c := \\frepeat(c,32760)\n"
                      "define x x\n"
                      ".b := \\m(c)" + "\\m(x)" * 200 + "\n"
                      "show macro b\n"
                      "echo END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=30)
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "END-MARKER" in result.stdout, result.stdout[-500:]
    shown = result.stdout.replace("-\n", "")
    m = re.search(r"b = (c+)(x*)\n", shown)
    assert m, result.stdout[-500:]
    assert len(m.group(1)) == 32760
    assert len(m.group(2)) < 200


def test_show_features_long_program_path(wermit_path):
    """Verify SHOW FEATURES prints a long program path in bounds.

    SHOW FEATURES expands the program's directory and name into a
    2046-character buffer.  argv[0] names no file, so the directory is
    all of argv[0], and the expansion does not fit.
    """
    import os
    import subprocess
    result = subprocess.run(
        ["/" + "a" * 1500, "-H", "-Y", "-Q", "-C",
         "set command more-prompting off, show features, "
         "echo END-MARKER, exit"],
        executable=wermit_path, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=scaled(30),
        env=dict(os.environ))
    assert result.returncode == 0, result.returncode
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "END-MARKER" in result.stdout, result.stdout[-500:]


def test_output_expansion_fills_line(run_wermit, tmp_path):
    """Verify OUTPUT expands a value that fills line[] in bounds.

    OUTPUT copies its text into line[] and expands it into the rest of
    line[].  The loop tries lengths around the space left, so one of
    them fills it exactly.  Under AddressSanitizer, the NUL must not
    land past line[].
    """
    script = tmp_path / "t.ksc"
    script.write_text(
        "set take error off\n"
        "for \\%n 32750 32775 1 { .c := \\frepeat(x,16000)"
        "\\frepeat(x,\\feval(\\%n-16000)), output \\m(c) }\n"
        "echo END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=60)
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "END-MARKER" in result.stdout, result.stdout[-500:]


def test_failed_expansions_keep_depth(run_wermit, tmp_path):
    """Verify failed expansions leave the nesting depth as it was.

    Each ASSIGN of b expands a value too long for line[], and the
    expansion fails.  The ASSIGN of x after it must work every time.
    A circular definition still reaches the depth limit.
    """
    script = tmp_path / "t.ksc"
    script.write_text(
        "set take error off\n"
        ".c := \\frepeat(x,20000)\n"
        ".\\%f = 0\n"
        "for \\%i 1 300 1 { .b := \\m(c)\\m(c), .x := ok\\%i, "
        "if not equal \"\\m(x)\" \"ok\\%i\" incr \\%f }\n"
        "echo FAILS=\\%f\n"
        "define \\%a \\%b\n"
        "define \\%b \\%a\n"
        "echo [\\%a]\n"
        "echo END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=60)
    out = result.stdout + result.stderr
    assert "FAILS=0" in out, out[-1000:]
    assert out.count("circular or too deep") == 1, out[-1000:]
    assert "END-MARKER" in result.stdout, out[-1000:]


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

    The first \\fdirectories() fills the name buffer.  The second and
    third take an empty pattern and an array, so each builds an empty
    list.  Reading past an unterminated list shows under
    AddressSanitizer.
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


def test_array_resize_too_large(run_wermit, tmp_path):
    """Verify ARRAY RESIZE refuses a size whose pointers overflow int.

    The array keeps its size.  Under UBSan, lo+1 must not overflow.
    """
    script = tmp_path / "t.ksc"
    script.write_text("set take error off\ndeclare \\&a[3]\n"
                      "array resize &a 2147483647\n"
                      "echo DIM=\\fdim(&a)\necho END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=30)
    assert "runtime error" not in result.stderr, result.stderr[-2000:]
    assert "Dimension too large" in result.stdout, result.stdout
    assert "DIM=3" in result.stdout, result.stdout


def test_sexp_macro_argument_list_grows(run_wermit, tmp_path):
    """Verify dosexp() passes each macro argument whole as the list grows.

    dosexp() builds the argument list for a macro in a buffer that
    grows by 64 bytes.  Arguments of each length from 1 to 150, with and
    without spaces, cross every growth boundary.
    """
    script = tmp_path / "t.ksc"
    script.write_text(
        "define m {\n"
        "    if not equal {\\%1} {\\m(s)} echo BAD1=[\\%1]\n"
        "    if not equal {\\%2} {\\m(s) b} echo BAD2=[\\%2]\n"
        "    if not equal {\\%3} {c} echo BAD3=[\\%3]\n"
        "    return 1\n"
        "}\n"
        "for \\%i 1 150 1 {\n"
        "    .s := \\frepeat(a,\\%i)\n"
        "    (m '\\m(s) '(\\m(s) b) 'c)\n"
        "}\n"
        "echo END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=60)
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "END-MARKER" in result.stdout, result.stdout[-2000:]
    assert "BAD" not in result.stdout, result.stdout[-2000:]


@pytest.mark.parametrize("limit", [5, 1000])
def test_sexp_depth_limit_set_inside_sexp(run_wermit, tmp_path, limit):
    """Verify SET SEXPRESSION DEPTH-LIMIT inside an S-expression is refused.

    The command frees the result stack, so it fails while an
    S-expression is using the stack and works at top level.
    """
    script = tmp_path / "t.ksc"
    script.write_text(
        "set take error off\n"
        f"define m {{ set sexpression depth-limit {limit}, return 1 }}\n"
        "echo [\\fsexpression(+ 1 (+ 2 (+ 3 (m 4))))]\n"
        "set sexpression depth-limit 20\n"
        "echo ST=\\v(status)\n"
        "echo END-MARKER\n")
    result = run_wermit(f"take {script}", timeout=30)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "[7]" in result.stdout, result.stdout
    assert "ST=0" in result.stdout, result.stdout
    assert "END-MARKER" in result.stdout, result.stdout


def test_sexp_interrupted_resets_depth(wermit_path, tmp_path):
    """Verify Ctrl-C during an S-expression returns the depth to zero.

    wermit runs on a pseudoterminal.  An S-expression calls a macro that
    loops.  Ctrl-C returns to the prompt.  \\v(sdepth) is then 0, and SET
    SEXPRESSION DEPTH-LIMIT works at top level.
    """
    import os
    import pty
    import subprocess
    import time
    from conftest import PtyReader, _make_controlling_tty
    fd, slave = pty.openpty()
    proc = subprocess.Popen(
        [wermit_path, "-H", "-Y", "-Q"],
        stdin=slave, stdout=slave, stderr=slave, cwd=str(tmp_path),
        close_fds=True, preexec_fn=_make_controlling_tty)
    os.close(slave)
    pty_in = PtyReader(fd)

    try:
        pty_in.until(b"C-Kermit>", 15)
        os.write(fd, b"define spin { while true { } }\r")
        os.write(fd, b"(spin)\r")
        time.sleep(1)
        os.write(fd, b"\x03")
        pty_in.until(b"^C", 15)
        pty_in.until(b"C-Kermit>", 15)
        os.write(fd, b"echo DEPTH=\\v(sdepth)\r")
        pty_in.until(b"DEPTH=", 15)
        pty_in.until(b"C-Kermit>", 15)
        os.write(fd, b"set sexpression depth-limit 50\r")
        os.write(fd, b"echo RC=\\v(status)\r")
        pty_in.until(b"RC=", 15)
        pty_in.until(b"C-Kermit>", 15)
        os.write(fd, b"exit\r")
        pty_in.drain(5)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        os.close(fd)
    text = pty_in.out.decode(errors="replace")
    assert "DEPTH=0" in text, text[-1000:]
    assert "Not allowed" not in text, text[-1000:]
    assert "RC=0" in text, text[-1000:]


def test_expansion_interrupted_resets_depth(wermit_path, tmp_path):
    """Verify Ctrl-C during a variable expansion returns its depth to zero.

    wermit runs on a pseudoterminal.  Each element of \\&b[] holds the
    name of the next, so expanding \\&b[1] nests 60 levels.  The last
    element runs a macro that loops.  After Ctrl-C, a second 60-level
    chain in \\&a[] must expand.  The limit is 100 levels, so it fails
    if the first 60 remain counted.
    """
    import os
    import pty
    import subprocess
    import time
    from conftest import PtyReader, _make_controlling_tty
    lines = ["declare \\&a[60]", "declare \\&b[60]",
             "define spin { while true { } }"]
    for i in range(1, 60):
        lines.append(f"define \\&a[{i}] \\&a[{i + 1}]")
        lines.append(f"define \\&b[{i}] \\&b[{i + 1}]")
    lines += ["define \\&a[60] OK", "define \\&b[60] \\fexecute(spin)"]
    script = tmp_path / "chain.ksc"
    script.write_text("\n".join(lines) + "\n")
    fd, slave = pty.openpty()
    proc = subprocess.Popen(
        [wermit_path, "-H", "-Y", "-Q"],
        stdin=slave, stdout=slave, stderr=slave, cwd=str(tmp_path),
        close_fds=True, preexec_fn=_make_controlling_tty)
    os.close(slave)
    pty_in = PtyReader(fd)

    try:
        pty_in.until(b"C-Kermit>", 15)
        os.write(fd, b"take chain.ksc\r")
        os.write(fd, b"echo READY\r")
        pty_in.until(b"\r\nREADY", 15)
        pty_in.until(b"C-Kermit>", 15)
        os.write(fd, b"echo [\\&b[1]]\r")
        time.sleep(1)
        os.write(fd, b"\x03")
        pty_in.until(b"^C", 15)
        pty_in.until(b"C-Kermit>", 15)
        os.write(fd, b"echo VALUE=[\\&a[1]]\r")
        pty_in.until(b"VALUE=[", 15)
        pty_in.until(b"C-Kermit>", 15)
        os.write(fd, b"exit\r")
        pty_in.drain(5)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        os.close(fd)
    text = pty_in.out.decode(errors="replace")
    assert "VALUE=[OK]" in text, text[-1000:]
    assert "too deep" not in text, text[-1000:]


POW_CASES = [("(^ 2 10)", "1024"), ("(^ 3 3)", "27"), ("(^ 2 -1)", "0.5"),
             ("(^ -1 -3)", "-1"), ("(^ 2 62)", "4611686018427387904"),
             ("(^ 2 63)", "9223372036854775000.0"), ("(^ 0 5)", "0"),
             ("(^ 2.5 2)", "6.25"), ("(^ -2 3)", "-8"),
             ("(^ 4 0.5)", "2.0"), ("(^ -1 9223372036854775807)", "-1"),
             ("(^ 7 22)", "3909821048582988049")]


@pytest.mark.parametrize("expr,want", POW_CASES,
                         ids=[e for e, _ in POW_CASES])
def test_sexp_power_results(run_wermit, expr, want):
    """Verify integer powers in S-expressions keep their results."""
    result = run_wermit(f"echo [\\fsexpression({expr})]", timeout=30)
    assert f"[{want}]" in result.stdout, result.stdout


@pytest.mark.parametrize("expr", [
    "(^ 2 9223372036854775807)", "(^ 0.0 9223372036854775807 2)",
    "(^ -9223372036854775808 -9223372036854775808)", "(^ 2 -64)",
    "(^ -1 9223372036854775807)"])
def test_sexp_power_huge_exponent(run_wermit, expr):
    """Verify a huge integer exponent finishes without a trap.

    The integer power squares and multiplies, and falls back to
    floating point on overflow.
    """
    result = run_wermit(f"echo [\\fsexpression({expr})], echo END-MARKER",
                        timeout=20)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "runtime error" not in result.stderr, result.stderr[-2000:]
    assert "END-MARKER" in result.stdout, result.stdout

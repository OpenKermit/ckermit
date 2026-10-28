import subprocess

import pytest
from conftest import assert_ok


def test_sexpression_round(run_wermit):
    """Test \\fsexpression(round ...) with different place counts."""
    result = run_wermit(
        "echo A=[\\fsexpression(round 3.14159 2)], "
        "echo B=[\\fsexpression(round 3.14159 0)], "
        "echo C=[\\fsexpression(round 2.7)]"
    )
    assert_ok(result)
    assert "A=[3.14]" in result.stdout
    assert "B=[3]" in result.stdout
    assert "C=[3]" in result.stdout


def test_fjoin_csv_separator_overflow_reports_error(run_wermit):
    """Test that \\fjoin() in CSV mode reports RESULT_TOO_LONG when the
    separator cannot fit in the result buffer.
    """
    # Sized to fill the 32763-byte result buffer (CMDBL - 1), leaving
    # room for NUL but no space for the comma separator.
    elt1_len = 32762

    cmds = (
        f"declare \\&a[2], "
        f"assign \\&a[1] \\frepeat(x,{elt1_len}), "
        f"echo LEN1=[\\flen(\\&a[1])], "
        f"echo LEN2=[\\flen(\\&a[2])], "
        f"echo RESULT=[\\fjoin(&a[],CSV)]"
    )
    result = run_wermit(cmds, timeout=20)
    assert_ok(result)

    # Verify element 1 fills the buffer and element 2 is empty.
    assert f"LEN1=[{elt1_len}]" in result.stdout
    assert "LEN2=[0]" in result.stdout

    assert "RESULT_TOO_LONG" in result.stdout, (
        "\\fjoin() should report RESULT_TOO_LONG when the CSV "
        "separator can't fit; got: " + result.stdout
    )
    # Ensure the result was not silently truncated without the separator.
    assert f"RESULT=[{'x' * elt1_len}]" not in result.stdout


def test_variable_ref_invalid_byte_no_oob_read(run_wermit, tmp_path):
    """Verify that variable references with high bytes evaluate to empty.

    References such as \\%<byte> and \\fcontents(%<byte>) with invalid
    variable name bytes (such as 0x80 or 0xff) must evaluate as undefined
    variables (empty strings) and not read out of bounds.

    The commands are written to a TAKE file to avoid passing raw non-UTF-8
    bytes through pytest-xdist process communication.
    """
    for n in (0x80, 0xff):
        script = tmp_path / f"highbyte_{n:02x}.cmd"
        script.write_bytes(
            b"echo A=[\\%" + bytes([n]) + b"]\n"
            b"echo B=[\\fcontents(%" + bytes([n]) + b")]\n"
        )
        result = run_wermit(f"take {script}")
        assert_ok(result)
        assert "A=[]" in result.stdout, (
            f"byte 0x{n:02x}: \\%<byte> returned non-empty/leaked "
            f"data: {result.stdout!r}"
        )
        assert "B=[]" in result.stdout, (
            f"byte 0x{n:02x}: \\fcontents(%<byte>) returned "
            f"non-empty/leaked data: {result.stdout!r}"
        )


def test_femail_whitespace_only_arg_no_oob_read(run_wermit):
    """Verify that \\femail() evaluates to empty on whitespace-only input."""
    for arg in (" ", "\t", " " * 20, "\t" * 20, " \t" * 10):
        result = run_wermit(f"echo E=[\\femail({arg})]")
        assert_ok(result)
        assert "E=[]" in result.stdout, (
            f"\\femail({arg!r}) did not evaluate to empty: "
            f"{result.stdout!r}"
        )


def test_radix_conversion_overflow_returns_minus_one(run_wermit):
    """Test \\fradix(), \\fhex2n() and \\foct2n() up to and past 2^63-1.

    The largest convertible value is 2^63-1. Anything larger returns
    -1, including values that are a multiple of 2^64.
    """
    result = run_wermit(
        "echo A=[\\fradix(7FFFFFFFFFFFFFFF,16,10)], "
        "echo B=[\\fradix(8000000000000000,16,10)], "
        "echo C=[\\fradix(FFFFFFFFFFFFFFFF,16,10)], "
        "echo D=[\\fhex2n(10000000000000000)], "
        "echo E=[\\foct2n(777777777777777777777)], "
        "echo F=[\\foct2n(1000000000000000000000)], "
        "echo G=[\\fradix(-777,8,16)]"
    )
    assert_ok(result)
    assert "A=[9223372036854775807]" in result.stdout, result.stdout
    assert "B=[-1]" in result.stdout, result.stdout
    assert "C=[-1]" in result.stdout, result.stdout
    assert "D=[-1]" in result.stdout, result.stdout
    assert "E=[9223372036854775807]" in result.stdout, result.stdout
    assert "F=[-1]" in result.stdout, result.stdout
    assert "G=[-1FF]" in result.stdout, result.stdout


def test_wait_file_event_status(run_wermit, tmp_path):
    """WAIT n FILE succeeds when the event happens and fails on timeout."""
    present = tmp_path / "present.txt"
    present.write_text("x\n")
    absent = tmp_path / "absent.txt"
    result = run_wermit(
        f"wait 1 file deletion {present}, echo A=[\\v(status)], "
        f"wait 1 file creation {absent}, echo B=[\\v(status)], "
        f"wait 1 file creation {present}, echo C=[\\v(status)]",
        timeout=20)
    assert_ok(result)
    assert "A=[1]" in result.stdout, result.stdout
    assert "B=[1]" in result.stdout, result.stdout
    assert "C=[0]" in result.stdout, result.stdout


def test_sexpression_integer_overflow_uses_float(run_wermit, tmp_path):
    """Verify +, - and * fall back to floating point on 64-bit overflow.

    Results that fit in 64 bits stay exact integers.
    """
    cases = {
        "A": ("* 4294967296 4294967296", "18446744073709550000.0"),
        "B": ("+ 9223372036854775807 1", "9223372036854775000.0"),
        "C": ("- -9223372036854775807 2", "-9223372036854775000.0"),
        "D": ("* -4294967296 4294967296", "-18446744073709550000.0"),
        "E": ("* 3037000499 3037000499", "9223372030926249001"),
        "F": ("+ 9007199254740993 0", "9007199254740993"),
        "G": ("- 9223372036854775806 -1", "9223372036854775807"),
        "H": ("* 2 -3 4", "-24"),
    }
    script = tmp_path / "t.ksc"
    script.write_text("".join(f"echo {k}=[\\fsexpression({expr})]\n"
                              for k, (expr, _) in cases.items()))
    result = run_wermit(f"take {script}")
    for k, (expr, want) in cases.items():
        assert f"{k}=[{want}]" in result.stdout, (expr, result.stdout)


def test_division_by_minus_one_does_not_trap(run_wermit, tmp_path):
    """Verify division and modulus by -1 at the most negative value.

    The hardware traps on these, so they are computed explicitly.
    """
    script = tmp_path / "t.ksc"
    script.write_text(
        "echo A=[\\fmod(-2147483648,-1)]\n"
        "echo B=[\\fsexp(/ -9223372036854775808 -1)]\n"
        "echo C=[\\feval((-9223372036854775807-1)%-1)]\n"
        "echo D=[\\feval((-9223372036854775807-1)/-1)]\n"
        "echo E=[\\fsexp(% 7 -1)]\n"
        "echo F=[\\fsexp(/ 7 -1)]\n"
        "echo H=[\\feval(7/-1)]\n"
        "echo END-MARKER\n")
    result = run_wermit(f"take {script}")
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    for want in ["A=[0]", "C=[0]", "E=[0]", "F=[-7]", "H=[-7]",
                 "END-MARKER"]:
        assert want in result.stdout, result.stdout


def test_max_min_mod_random_use_64_bits(run_wermit, tmp_path):
    """Verify \\fmax(), \\fmin(), \\fmod() and \\frandom() use 64 bits."""
    script = tmp_path / "t.ksc"
    script.write_text(
        "echo A=[\\fmax(4294967296,3)] B=[\\fmin(4294967296,3)]\n"
        "echo C=[\\fmod(4294967297,4294967296)] D=[\\fmod(-7,3)]\n"
        "echo E=[\\fmax(-5,-9)] F=[\\fmin(-5,-9)]\n"
        "for \\%i 1 40 1 { echo R=[\\frandom(10000000000)] "
        "N=[\\frandom(-3)] }\n")
    result = run_wermit(f"take {script}")
    for want in ["A=[4294967296]", "B=[3]", "C=[1]", "D=[-1]", "E=[-5]",
                 "F=[-9]"]:
        assert want in result.stdout, result.stdout
    big = [int(x.split("]")[0]) for x in result.stdout.split("R=[")[1:]]
    neg = [int(x.split("]")[0]) for x in result.stdout.split("N=[")[1:]]
    assert len(big) == 40 and all(0 <= v < 10000000000 for v in big)
    assert any(v >= 2 ** 32 for v in big), big
    assert all(-3 < v <= 0 for v in neg), neg


@pytest.mark.parametrize("mjd,want", [
    ("0", "[18581117]"),
    ("-678941", "[00000101]"),
    ("2973483", "[99991231]"),
    ("2973484", "ARG_OUT_OF_RANGE"),
    ("-678942", "ARG_OUT_OF_RANGE"),
    ("99999999999999", "ARG_OUT_OF_RANGE"),
])
def test_mjd2date_range(run_wermit, mjd, want):
    """Verify \\fmjd2date() accepts years 0 through 9999 only."""
    result = run_wermit(f"echo [\\fmjd2date({mjd})]")
    assert want in result.stdout + result.stderr, result.stdout


def test_pathname_of_missing_dir_dotdot_is_root(run_wermit):
    """Verify \\fpathname(/missing/..) is "/" with nothing after it."""
    result = run_wermit("echo [\\fpathname(/nosuchdir_q/..)]")
    assert "[/]" in result.stdout, result.stdout


def test_fullversion_has_no_empty_test_tag(run_wermit):
    """Verify \\v(fullversion) adds a test tag only for a test release."""
    result = run_wermit("echo [\\v(fullversion)] [\\v(test)]")
    full = result.stdout.split("[")[1].split("]")[0]
    if "[0]" in result.stdout:
        assert " " not in full and not full.endswith("."), full


def test_random_seed_reads_no_uninitialized_memory(wermit_path, valgrind):
    """Verify startup and \\frandom() run clean under valgrind."""
    result = subprocess.run(
        [valgrind, "-q", "--error-exitcode=9", wermit_path,
         "-H", "-Y", "-Q", "-C", "echo R=\\frandom(1000), quit"],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert "R=" in result.stdout, result.stdout


def test_random_differs_between_runs(run_wermit):
    """Verify \\frandom() gives different sequences in separate runs."""
    seqs = set()
    for _ in range(3):
        result = run_wermit(
            "for \\%i 1 4 1 { xecho [\\frandom(1000000000)] }, echo")
        assert_ok(result)
        seqs.add(result.stdout.strip())
    assert len(seqs) == 3, seqs


@pytest.mark.parametrize("expr", ["abc", "1+qqq", "2*zz"])
def test_eval_undefined_name_stays_in_bounds(wermit_path, valgrind, expr):
    """Verify \\feval() of an undefined name reads only the expression.

    gettok() skips the bad name and reads on.  At the end of the
    expression it must stop at the final NUL.
    """
    result = subprocess.run(
        [valgrind, "-q", "--error-exitcode=9", wermit_path,
         "-H", "-Y", "-Q", "-C", f"echo [\\feval({expr})], quit"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=120)
    assert result.returncode == 0, result.stderr
    assert "ARG_NOT_NUMERIC" in result.stdout, result.stdout

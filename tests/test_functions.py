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

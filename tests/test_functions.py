from conftest import assert_ok


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

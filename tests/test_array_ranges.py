"""
Tests for ARRAY CLEAR, ARRAY SET and ARRAY COPY ranges (ckuusr.c).

A range may extend past the array's dimension.  Only the elements that
exist are used.  Access past the element list shows only under
AddressSanitizer.
"""

SETUP = [
    "declare \\&a[3]",
    ".\\&a[1] := one",
    ".\\&a[2] := two",
    ".\\&a[3] := three",
]


def _run(run_wermit, cmds):
    """Run SETUP and cmds, and return the CompletedProcess."""
    result = run_wermit(", ".join(SETUP + cmds + ["echo END-MARKER"]))
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "END-MARKER" in result.stdout, result.stdout + result.stderr
    return result


def test_array_clear_past_dimension(run_wermit):
    """Verify ARRAY CLEAR stops at the last element."""
    result = _run(run_wermit, [
        "array clear &a[2:100]",
        "echo A=[\\&a[1]][\\&a[2]][\\&a[3]] DIM=[\\fdim(&a)]",
    ])
    assert "A=[one][][] DIM=[3]" in result.stdout, result.stdout


def test_array_set_past_dimension(run_wermit):
    """Verify ARRAY SET stops at the last element."""
    result = _run(run_wermit, [
        "array set &a[2:100] x",
        "echo A=[\\&a[1]][\\&a[2]][\\&a[3]] DIM=[\\fdim(&a)]",
    ])
    assert "A=[one][x][x] DIM=[3]" in result.stdout, result.stdout


def test_array_copy_past_source_dimension(run_wermit):
    """Verify ARRAY COPY copies only the source elements that exist."""
    result = _run(run_wermit, [
        "array copy &a[2:9] &b",
        "echo B=[\\&b[1]][\\&b[2]] DIM=[\\fdim(&b)]",
    ])
    assert "B=[two][three] DIM=[2]" in result.stdout, result.stdout


def test_array_copy_empty_range(run_wermit):
    """Verify ARRAY COPY of a range past the source copies nothing."""
    result = _run(run_wermit, [
        "array copy &a[5:9] &b",
        "echo B=[\\&b[1]] DIM=[\\fdim(&b)]",
    ])
    assert "B=[] DIM=[1]" in result.stdout, result.stdout

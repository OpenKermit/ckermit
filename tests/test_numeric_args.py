"""
Tests for numeric script function arguments out of the int and
CK_OFF_T ranges (ckatoi() and ckatofs(), ckclib.c).

Each value saturates rather than wrapping.
"""
import pytest


@pytest.mark.parametrize("expr,expected", [
    ("\\fsubstr(abcdef,4294967298,2)", "[]"),
    ("\\fsubstr(abcdef,2,4294967298)", "[bcdef]"),
    ("\\fleft(abcdef,4294967298)", "[abcdef]"),
    ("\\fright(abcdef,4294967297)", "[abcdef]"),
    ("\\feval(9223372036854775807)", "[9223372036854775807]"),
    ("\\feval(9223372036854775808)", "[9223372036854775807]"),
    ("\\feval(100000000000000000000)", "[9223372036854775807]"),
    ("\\feval(-9223372036854775807-1)", "[-9223372036854775808]"),
    ("\\feval(-5)", "[-5]"),
])
def test_large_numeric_argument(run_wermit, expr, expected):
    """Verify a number beyond the argument's range saturates."""
    result = run_wermit(f"echo [{expr}]")
    assert "runtime error" not in result.stderr, result.stderr
    assert expected in result.stdout, result.stdout

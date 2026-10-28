r"""Tests for the end of a doublequoted command field.

A doublequote ends the field unless an odd number of backslashes
precedes it.  So "\\" and "a\\" end at their closing quote, and "a\""
contains an escaped quote.
"""
import pytest


@pytest.mark.parametrize("left,right,expect", [
    (r'"\%c"', r'"\\"', "EQ"),
    (r'"a\\"', r'"a\\"', "EQ"),
    (r'"x"', r'"\\"', "NE"),
    (r'"a\""', r'"a\""', "EQ"),
    (r'"\\\\"', r'"\\\\"', "EQ"),
    (r'"a\\\""', r'"a\\\""', "EQ"),
])
def test_if_equal_doublequoted_backslashes(run_wermit, tmp_path, left,
                                           right, expect):
    """Verify IF EQUAL parses doublequoted fields ending in backslashes."""
    script = tmp_path / "t.ksc"
    script.write_text("assign \\%c \\\\\n"
                      f"if equal {left} {right} {{ echo RESULT=EQ }} "
                      "else { echo RESULT=NE }\n"
                      "echo END-MARKER\n")
    result = run_wermit(f"take {script}")
    assert f"RESULT={expect}" in result.stdout, result.stdout
    assert "Syntax error" not in result.stdout, result.stdout
    assert "END-MARKER" in result.stdout, result.stdout

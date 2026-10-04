"""Tests for TYPE /WIDTH: truncation and tab expansion (dotype())."""
from conftest import assert_ok

LINES = [
    "abcdefghijklmnopqrstuvwxyz0123456789",
    "short",
    "0123456789012345678",
]


def test_type_width_truncates_lines(run_wermit, tmp_path):
    """TYPE /WIDTH:20 shows each line truncated to 20 characters."""
    f = tmp_path / "t.txt"
    f.write_text("\n".join(LINES) + "\n")
    result = run_wermit(f"type /width:20 {f}")
    assert_ok(result)
    assert result.stdout.splitlines() == [s[:20] for s in LINES], (
        repr(result.stdout))


def test_type_width_with_tail(run_wermit, tmp_path):
    """TYPE /WIDTH:20 /TAIL:2 shows the last 2 lines, truncated."""
    f = tmp_path / "t.txt"
    f.write_text("\n".join(LINES) + "\n")
    result = run_wermit(f"type /width:20 /tail:2 {f}")
    assert_ok(result)
    assert result.stdout.splitlines() == [s[:20] for s in LINES[1:]], (
        repr(result.stdout))


def test_type_width_expands_tabs(run_wermit, tmp_path):
    """TYPE /WIDTH expands tabs to 8-column stops, with no stray bytes."""
    f = tmp_path / "t.txt"
    f.write_text("\tA\nab\tB\tC\n")
    result = run_wermit(f"type /width:30 {f}")
    assert_ok(result)
    assert result.stdout.splitlines() == [
        "        A",
        "ab      B       C",
    ], repr(result.stdout)

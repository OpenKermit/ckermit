"""Tests for the default file patterns (ckuusx.c)."""


def _text_patterns(run_wermit):
    """Return the default text patterns that SHOW PATTERNS lists."""
    out = run_wermit("show patterns").stdout
    text = out.split("File text-patterns:", 1)[1]
    return text.split()


def test_ts_is_not_a_text_pattern(run_wermit):
    """Verify *.ts is not a default text pattern.

    MPEG transport stream video uses .ts as well as TypeScript, and
    text mode would convert the video's line ends.
    """
    patterns = _text_patterns(run_wermit)
    assert "*.js" in patterns, patterns
    assert "*.ts" not in patterns, patterns

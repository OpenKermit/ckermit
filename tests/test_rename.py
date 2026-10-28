"""Tests for the RENAME command."""
from conftest import make_deep_dir


def test_rename_replace_too_long_fails(run_wermit, tmp_path):
    """Verify RENAME /REPLACE refuses a new name longer than its buffer.

    Each of the 200 characters of the name is replaced by 100, so the
    new name needs 20,000 bytes.  renameone() holds it in CKMAXPATH
    bytes.  RENAME must fail and leave the file alone.
    """
    old = "a" * 200
    (tmp_path / old).write_text("x")
    repl = "B" * 100
    result = run_wermit(
        f"cd {tmp_path}, rename /replace:{{{{a}}{{{repl}}}}} a*, "
        "echo STATUS=\\v(status)")
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "?New name too long: " + old in result.stdout, result.stdout
    assert "STATUS=1" in result.stdout, result.stdout
    assert (tmp_path / old).exists()


def test_rename_replace_within_limit(run_wermit, tmp_path):
    """Verify RENAME /REPLACE still renames when the new name fits."""
    (tmp_path / "abcabc").write_text("x")
    result = run_wermit(
        f"cd {tmp_path}, rename /replace:{{{{b}}{{XY}}}} abc*, "
        "echo STATUS=\\v(status)")
    assert "STATUS=0" in result.stdout, result.stdout
    assert (tmp_path / "aXYcaXYc").exists()


def test_rename_wildcard_long_directory(run_wermit, tmp_path):
    """Verify RENAME of a wildcard match under a long directory path.

    The directory part is more than half of PATH_MAX.  renameone()
    joins the directory and the file name again after it changes the
    case.  It builds the joined name in a local buffer.
    """
    deep = make_deep_dir(tmp_path)
    (deep / "FILEX").write_text("x")
    result = run_wermit(
        f"rename /lower {deep}/FILE*, echo STATUS=\\v(status)")
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "STATUS=0" in result.stdout, result.stdout
    assert (deep / "filex").exists()

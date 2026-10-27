"""Tests for the CHANGE command (domydir(), ckuus6.c)."""
import os

from conftest import make_deep_dir


def test_change_long_directory_and_pattern(run_wermit, tmp_path):
    """Verify CHANGE with a long pattern in a long directory path.

    CHANGE takes the full path of its file pattern to find the source
    directory.  realpath() fails for a pattern, so zfnqfp() joins the
    current directory and the pattern.  Here that is more than PATH_MAX
    bytes, and chgsourcedir[] holds CKMAXPATH+1.  Writes past it show
    under AddressSanitizer.
    """
    deep = make_deep_dir(tmp_path)
    (deep / "x.txt").write_text("aaa\n")
    pattern = "*" * os.pathconf(str(tmp_path), "PC_PATH_MAX") + ".txt"
    result = run_wermit(
        f"cd {deep}, change {pattern} aaa bbb, echo STATUS=\\v(status)")
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "AddressSanitizer" not in result.stderr, result.stderr[-3000:]
    assert "STATUS=0" in result.stdout, result.stdout
    assert (deep / "x.txt").read_text() == "bbb\n"

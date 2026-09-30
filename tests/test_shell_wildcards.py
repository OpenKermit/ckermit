"""Tests for SET WILDCARD-EXPANSION SHELL."""


def test_shell_expansion_long_path(tmp_path, run_wermit):
    """Verify shell expansion lists a matching path over 255 chars."""
    name = "".join(chr(97 + (i % 26)) for i in range(20))
    path = tmp_path
    for i in range(15):
        path = path / f"{name}{i}"
    path.mkdir(parents=True)
    (path / "file1.txt").write_text("hello world")
    assert len(str(path / "file1.txt")) > 255

    result = run_wermit(
        "set wildcard-expansion shell, "
        f"echo N=[\\ffiles({path}/*.txt)] F=[\\fnextfile()]"
    )
    assert f"N=[1] F=[{path}/file1.txt]" in result.stdout, result.stdout


def test_shell_expansion_overlong_word(tmp_path, run_wermit):
    """Verify an expansion word exceeding the path buffer is skipped.

    The shell expands the pattern to a 5000-character word.
    """
    result = run_wermit(
        f"cd {tmp_path}, set wildcard-expansion shell, "
        "echo N=[\\ffiles(x$(printf %05000d 0)*)]"
    )
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}"
    )
    assert "N=[0]" in result.stdout, result.stdout

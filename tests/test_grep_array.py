"""
Tests for GREP /ARRAY in dogrep() (ckuus6.c).
"""
import pytest


def _grep(run_wermit, tmp_path, grep_cmd, extra=()):
    """Run grep_cmd in tmp_path and return the CompletedProcess."""
    return run_wermit(", ".join([
        f"cd {tmp_path}",
        grep_cmd,
        "echo COUNT=[\\&a[0]] DIM=[\\fdim(&a)]",
        *extra,
        "echo DONE",
    ]), timeout=60)


@pytest.mark.parametrize("switches,expected", [
    ("", ["alpha one", "alpha two"]),
    ("/linenumbers", ["1:alpha one", "3:alpha two"]),
])
def test_grep_array_elements(run_wermit, tmp_path, switches, expected):
    """Verify each element holds the whole line and \\&a[0] the count."""
    (tmp_path / "f.txt").write_text("alpha one\nbeta\nalpha two\n")
    result = _grep(run_wermit, tmp_path,
                   f"grep {switches} /array:&a alpha f.txt",
                   ["echo E1=[\\&a[1]]", "echo E2=[\\&a[2]]"])
    assert "COUNT=[2] DIM=[2]" in result.stdout, result.stdout
    assert f"E1=[{expected[0]}]" in result.stdout, result.stdout
    assert f"E2=[{expected[1]}]" in result.stdout, result.stdout


def test_grep_array_several_files(run_wermit, tmp_path):
    """Verify name:lineno:line elements from several files are whole."""
    (tmp_path / "a.txt").write_text("x\nalpha one\n")
    (tmp_path / "b.txt").write_text("alpha two\n")
    result = _grep(run_wermit, tmp_path,
                   "grep /linenumbers /array:&a alpha *.txt",
                   ["echo E1=[\\&a[1]]", "echo E2=[\\&a[2]]"])
    assert "COUNT=[2]" in result.stdout, result.stdout
    assert "E1=[a.txt:2:alpha one]" in result.stdout, result.stdout
    assert "E2=[b.txt:1:alpha two]" in result.stdout, result.stdout


def test_grep_array_long_line(run_wermit, tmp_path):
    """Verify a matching line longer than 10000 bytes is stored whole."""
    line = "alpha" + "x" * 20000
    (tmp_path / "f.txt").write_text(line + "\n")
    result = _grep(run_wermit, tmp_path,
                   "grep /linenumbers /array:&a alpha f.txt",
                   ["echo LEN=[\\flen(\\&a[1])]"])
    assert "DONE" in result.stdout, result.stdout[-500:] + result.stderr
    assert f"LEN=[{len(line) + 2}]" in result.stdout, result.stdout[-500:]


def test_grep_array_more_than_1000_matches(run_wermit, tmp_path):
    """Verify more than 1000 matching lines all go into the array."""
    (tmp_path / "f.txt").write_text(
        "".join(f"alpha {i}\n" for i in range(2500)))
    result = _grep(run_wermit, tmp_path, "grep /array:&a alpha f.txt",
                   ["echo LAST=[\\&a[2500]]"])
    assert "DONE" in result.stdout, result.stdout[-500:] + result.stderr
    assert "COUNT=[2500] DIM=[2500]" in result.stdout, result.stdout[-500:]
    assert "LAST=[alpha 2499]" in result.stdout, result.stdout[-500:]


def test_grep_array_keeps_macro_arguments(run_wermit, tmp_path):
    """Verify GREP /ARRAY inside a macro leaves its arguments alone."""
    (tmp_path / "f.txt").write_text("alpha\n")
    result = run_wermit(", ".join([
        f"cd {tmp_path}",
        "define grepmacro { grep /array:&a alpha f.txt, "
        "echo ARGS=[\\&_[1]][\\&_[3]][\\&_[5]] }",
        "grepmacro one two three four five",
        "echo DONE",
    ]), timeout=60)
    assert "ARGS=[one][three][five]" in result.stdout, result.stdout


def test_grep_array_nameonly(run_wermit, tmp_path):
    """Verify GREP /NAMEONLY /ARRAY stores each matching file once."""
    for i in range(1010):
        (tmp_path / f"f{i:04d}.txt").write_text("alpha\nalpha\n")
    result = _grep(run_wermit, tmp_path,
                   "set file listsize 2000, "
                   "grep /nameonly /array:&a alpha *.txt",
                   ["echo LAST=[\\&a[1010]]"])
    assert "COUNT=[1010] DIM=[1010]" in result.stdout, result.stdout[-500:]
    assert "LAST=[f1009.txt]" in result.stdout, result.stdout[-500:]


def test_grep_array_through_link(run_wermit, tmp_path):
    """Verify GREP /ARRAY into a linked array sizes the real array."""
    (tmp_path / "f.txt").write_text(
        "".join(f"alpha {i}\n" for i in range(1500)))
    result = run_wermit(", ".join([
        f"cd {tmp_path}",
        "declare \\&r[5]",
        "array link &a &r",
        "grep /array:&a alpha f.txt",
        "echo DIMS=[\\fdim(&a)][\\fdim(&r)] LAST=[\\&r[1500]]",
    ]), timeout=60)
    assert "DIMS=[1500][1500] LAST=[alpha 1499]" in result.stdout, (
        result.stdout[-500:] + result.stderr)


def test_grep_nameonly_closes_files(wermit_path, tmp_path):
    """Verify GREP /NAMEONLY closes each file after its first match.

    With 40 descriptors, a FILE left open per matching file stops the
    search after about 35 of the 100 files.
    """
    import resource
    import subprocess
    for i in range(100):
        (tmp_path / f"f{i:03d}.txt").write_text("alpha\nalpha\n")

    def limit():
        resource.setrlimit(resource.RLIMIT_NOFILE, (40, 40))
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         f"cd {tmp_path}, grep /nameonly /array:&a alpha *.txt, "
         "echo COUNT=[\\&a[0]], exit"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=60, preexec_fn=limit)
    assert "COUNT=[100]" in result.stdout, result.stdout

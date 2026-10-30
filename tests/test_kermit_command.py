"""
Tests for the KERMIT command (ckuusr.c).

The KERMIT command parses its text as command-line options with
cmdlin() and runs any file transfer action they give.
"""
import re


def test_kermit_command_sends_files(tmp_path, foreign_kermit_pty,
                                    wermit_path):
    """Verify KERMIT -s sends each named file, twice in a row."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("first file\n")
    (src / "b.txt").write_text("second file\n")
    for _ in range(2):
        for name in ("a.txt", "b.txt"):
            (tmp_path / name).unlink(missing_ok=True)
        returncode, stdout = foreign_kermit_pty(
            [wermit_path, "-H", "-Y", "-Q", "-r"],
            "set command more-prompting off, set delay 0, "
            "set host {HOST}, kermit -s src/a.txt src/b.txt, "
            "echo S=\\v(status), close, exit",
            tmp_path, timeout=30)
        assert returncode == 0, stdout
        assert "S=0" in stdout, stdout
        assert (tmp_path / "a.txt").read_text() == "first file\n"
        assert (tmp_path / "b.txt").read_text() == "second file\n"


def test_kermit_command_sets_options(run_wermit):
    """Verify KERMIT applies options and later commands still run."""
    result = run_wermit("kermit -e 500, kermit -b 1200, "
                        "echo S=\\v(status), show protocol")
    assert "S=0" in result.stdout, result.stdout
    assert re.search(r"Packet Length:\s+\d+\s+500", result.stdout), \
        result.stdout

"""Tests for the COPY command."""


def test_copy_interpret_wildcard_to_directory(run_wermit, tmp_path):
    """Verify COPY /INTERPRET keeps the destination for every file.

    Each source file goes to the target directory under its name.  The
    expansion of one file's lines must not change where the next file
    goes.
    """
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()
    (src / "a.txt").write_text("hello\n")
    (src / "b.txt").write_text("world\n")
    result = run_wermit(
        f"cd {tmp_path}, copy /interpret src/*.txt out/, "
        "echo STATUS=\\v(status)")
    assert "STATUS=0" in result.stdout, result.stdout
    assert (out / "a.txt").read_text() == "hello\n"
    assert (out / "b.txt").read_text() == "world\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out", "src"]


def test_copy_interpret_keeps_last_line(run_wermit, tmp_path):
    """Verify COPY /INTERPRET copies a last line that has no newline."""
    (tmp_path / "c.txt").write_bytes(b"one\ntwo")
    (tmp_path / "d.txt").write_bytes(b"x\n")
    result = run_wermit(
        f"cd {tmp_path}, copy /interpret c.txt c2.txt, "
        "copy /interpret d.txt d2.txt, echo STATUS=\\v(status)")
    assert "STATUS=0" in result.stdout, result.stdout
    assert (tmp_path / "c2.txt").read_bytes() == b"one\ntwo"
    assert (tmp_path / "d2.txt").read_bytes() == b"x\n"


def test_copy_toscreen_shows_last_line(run_wermit, tmp_path):
    """Verify COPY /TOSCREEN shows a last line that has no newline."""
    (tmp_path / "c.txt").write_bytes(b"one\ntwo")
    result = run_wermit(
        f"cd {tmp_path}, copy /toscreen c.txt, echo [END]")
    assert "one\ntwo\n[END]" in result.stdout, result.stdout


def test_copy_interpret_line_ends(run_wermit, tmp_path):
    """Verify COPY /INTERPRET ends lines only at LF.

    A vertical tab and the CR of a CRLF are data, copied as they are.
    """
    (tmp_path / "vt.txt").write_bytes(b"x\vy\n")
    (tmp_path / "crlf.txt").write_bytes(b"a\r\nb\r\n")
    result = run_wermit(
        f"cd {tmp_path}, copy /interpret vt.txt vt2.txt, "
        "copy /interpret crlf.txt crlf2.txt, echo STATUS=\\v(status)")
    assert "STATUS=0" in result.stdout, result.stdout
    assert (tmp_path / "vt2.txt").read_bytes() == b"x\vy\n"
    assert (tmp_path / "crlf2.txt").read_bytes() == b"a\r\nb\r\n"

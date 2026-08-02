"""
Transfer-level tests for filenames containing an embedded space,
quoted with either {braces} or "doublequotes", covering SEND and GET,
each for a single file and for multiple files named in one command.

See doc/spaces.md for the quoting rules the interactive command
parser supports (both delimiters are accepted for any filename
field, doublequotes gated on the dblquo/SET COMMAND DOUBLEQUOTING
setting which defaults on).
"""
import pytest
from conftest import assert_ok


def _quote(name, style):
    if style == "brace":
        return "{" + name + "}"
    if style == "doublequote":
        return '"' + name + '"'
    raise ValueError(style)


@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_send_single_space_name(tmp_path, wermit_loopback, style):
    """SEND of one file whose name contains a space, for both
    quoting styles."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    name = "file one.txt"
    (src_dir / name).write_text("payload\n")

    result = wermit_loopback(
        dest_dir, "", f"cd {src_dir}, send {_quote(name, style)}")

    assert_ok(result)
    assert (dest_dir / name).read_text() == "payload\n"


@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_send_multiple_space_names(tmp_path, wermit_loopback, style):
    """MSEND of several space-containing names in one command, for
    both quoting styles."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    name1, name2 = "file one.txt", "file two.txt"
    (src_dir / name1).write_text("one\n")
    (src_dir / name2).write_text("two\n")
    q1, q2 = _quote(name1, style), _quote(name2, style)

    result = wermit_loopback(
        dest_dir, "", f"cd {src_dir}, msend {q1} {q2}")

    assert_ok(result)
    assert (dest_dir / name1).read_text() == "one\n"
    assert (dest_dir / name2).read_text() == "two\n"


@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_get_single_space_name(tmp_path, wermit_loopback, style):
    """GET of one file whose name contains a space, for both
    quoting styles."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    name = "file one.txt"
    (src_dir / name).write_text("payload\n")

    result = wermit_loopback(
        src_dir, "", f"cd {dest_dir}, get {_quote(name, style)}")

    assert_ok(result)
    assert (dest_dir / name).read_text() == "payload\n"


@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_get_multiple_space_names(tmp_path, wermit_loopback, style):
    """MGET of several space-containing names in one command, for
    both quoting styles."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    name1, name2 = "file one.txt", "file two.txt"
    (src_dir / name1).write_text("one\n")
    (src_dir / name2).write_text("two\n")
    q1, q2 = _quote(name1, style), _quote(name2, style)

    result = wermit_loopback(
        src_dir, "", f"cd {dest_dir}, mget {q1} {q2}")

    assert_ok(result)
    assert (dest_dir / name1).read_text() == "one\n"
    assert (dest_dir / name2).read_text() == "two\n"

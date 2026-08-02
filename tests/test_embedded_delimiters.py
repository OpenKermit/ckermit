r"""
Transfer-level tests for filenames that themselves contain a literal
{brace} or "doublequote" character (as opposed to tests/test_spaces.py,
which only covers an embedded space). Covers SEND and GET, both
quoting styles for the command line, and, since it costs little
extra, a variant where the name also has an embedded space. Also
covers MGET/MSEND (several individually-quoted names in one command),
which additionally exercise cksplit() to split the names
apart, a second, independent grouping/escape mechanism from single-
name GET/SEND's cmfld()/cmifi().

A balanced {brace} pair needs opposite treatment for GET and SEND.  GET's
cmfld() field parser must have it left unescaped (escaping it works for ordinary
content, but it misreads purely-numeric content like "{123}" as a character-code
escape, so bare is the one to actually use).  SEND's and DIR's cmifi() field
parser must have it escaped, or the field fails to parse.  A literal double
quote character, by contrast, uses the same convention for both: escape it only
when double quotes are also the outer delimiter. Almost all cases below pass;
one real bug in MGET's interaction with cksplit() is pinned down as
xfail(strict=True) rather than worked around.  See
test_mget_multiple_embedded_doublequote_names.

"""
import pytest
from conftest import assert_ok


def _quote_brace_name(name, style, direction):
    """
    Quote a filename that itself contains a literal {balanced} brace
    pair, for the given outer quoting style and transfer direction.

    GET's filespec field and SEND's (and DIR's) filename field
    need opposite treatment (doc/spaces.md's "The
    convention splits by command family"): SEND requires the embedded
    pair to be backslash-escaped or it fails to parse at all; GET
    requires it NOT to be escaped; escaping happens to also work
    for ordinary content, but silently misreads numeric content, so
    bare is the one convention that works unconditionally for GET.
    """
    if direction == "send":
        escaped = name.replace("{", "\\{").replace("}", "\\}")
    else:
        escaped = name
    if style == "brace":
        return "{" + escaped + "}"
    if style == "doublequote":
        return '"' + escaped + '"'
    raise ValueError(style)


def _quote_dquote_name(name, style):
    """
    Quote a filename that itself contains a literal doublequote
    character. Consistent between SEND and GET: no escaping needed
    when braces are the outer delimiter (doublequotes don't affect
    brace tracking); must be escaped (\\") when doublequotes are the
    outer delimiter.
    """
    escaped = name.replace('"', '\\"') if style == "doublequote" else name
    if style == "brace":
        return "{" + escaped + "}"
    if style == "doublequote":
        return '"' + escaped + '"'
    raise ValueError(style)


@pytest.mark.parametrize("with_space", [False, True], ids=["nospace", "space"])
@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_send_embedded_brace_name(
        tmp_path, wermit_loopback, style, with_space):
    """SEND of a file whose name itself contains a {balanced} brace
    pair, escaped for the wire regardless of outer quoting style."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    name = "file {one} two.txt" if with_space else "file{one}.txt"
    (src_dir / name).write_text("payload\n")

    quoted = _quote_brace_name(name, style, "send")
    result = wermit_loopback(dest_dir, "", f"cd {src_dir}, send {quoted}")

    assert_ok(result)
    assert (dest_dir / name).read_text() == "payload\n"


@pytest.mark.parametrize("with_space", [False, True], ids=["nospace", "space"])
@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_get_embedded_brace_name(tmp_path, wermit_loopback, style, with_space):
    """GET of a file whose name itself contains a {balanced} brace
    pair, left unescaped regardless of outer quoting style (the
    opposite of SEND's convention)."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    name = "file {one} two.txt" if with_space else "file{one}.txt"
    (src_dir / name).write_text("payload\n")

    quoted = _quote_brace_name(name, style, "get")
    result = wermit_loopback(src_dir, "", f"cd {dest_dir}, get {quoted}")

    assert_ok(result)
    assert (dest_dir / name).read_text() == "payload\n"


@pytest.mark.parametrize("with_space", [False, True], ids=["nospace", "space"])
@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_send_embedded_doublequote_name(tmp_path, wermit_loopback, style,
                                         with_space):
    """SEND of a file whose name itself contains a literal doublequote
    character."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    name = 'file "one" two.txt' if with_space else 'file"one".txt'
    (src_dir / name).write_text("payload\n")

    quoted = _quote_dquote_name(name, style)
    result = wermit_loopback(dest_dir, "", f"cd {src_dir}, send {quoted}")

    assert_ok(result)
    assert (dest_dir / name).read_text() == "payload\n"


@pytest.mark.parametrize("with_space", [False, True], ids=["nospace", "space"])
@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_get_embedded_doublequote_name(tmp_path, wermit_loopback, style,
                                        with_space):
    """GET of a file whose name itself contains a literal doublequote
    character."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    name = 'file "one" two.txt' if with_space else 'file"one".txt'
    (src_dir / name).write_text("payload\n")

    quoted = _quote_dquote_name(name, style)
    result = wermit_loopback(src_dir, "", f"cd {dest_dir}, get {quoted}")

    assert_ok(result)
    assert (dest_dir / name).read_text() == "payload\n"


# The tests above cover a single name.  MGET/MSEND run cksplit() to
# split several individually-quoted names out of one field, a second,
# independent grouping/escape mechanism from cmfld()/cmifi()'s
# gtword()/setatm().  It handles multiple embedded-brace names
# correctly (both directions), but has a bug with an embedded, escaped
# double quotes.  See test_mget_multiple_embedded_doublequote_names below.

@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_msend_multiple_embedded_brace_names(tmp_path, wermit_loopback, style):
    """MSEND of two names, each containing a {balanced} brace pair,
    in one command."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    name1, name2 = "file{one}.txt", "file {two} b.txt"
    (src_dir / name1).write_text("A\n")
    (src_dir / name2).write_text("B\n")
    q1 = _quote_brace_name(name1, style, "send")
    q2 = _quote_brace_name(name2, style, "send")

    result = wermit_loopback(dest_dir, "", f"cd {src_dir}, msend {q1} {q2}")

    assert_ok(result)
    assert (dest_dir / name1).read_text() == "A\n"
    assert (dest_dir / name2).read_text() == "B\n"


@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_mget_multiple_embedded_brace_names(tmp_path, wermit_loopback, style):
    """MGET of two names, each containing a {balanced} brace pair,
    in one command."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    name1, name2 = "file{one}.txt", "file {two} b.txt"
    (src_dir / name1).write_text("A\n")
    (src_dir / name2).write_text("B\n")
    q1 = _quote_brace_name(name1, style, "get")
    q2 = _quote_brace_name(name2, style, "get")

    result = wermit_loopback(src_dir, "", f"cd {dest_dir}, mget {q1} {q2}")

    assert_ok(result)
    assert (dest_dir / name1).read_text() == "A\n"
    assert (dest_dir / name2).read_text() == "B\n"


@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_msend_multiple_embedded_doublequote_names(
        tmp_path, wermit_loopback, style):
    """MSEND of two names, each containing a literal doublequote
    character, in one command."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    name1, name2 = 'file"one".txt', 'file "two" b.txt'
    (src_dir / name1).write_text("A\n")
    (src_dir / name2).write_text("B\n")
    q1 = _quote_dquote_name(name1, style)
    q2 = _quote_dquote_name(name2, style)

    result = wermit_loopback(dest_dir, "", f"cd {src_dir}, msend {q1} {q2}")

    assert_ok(result)
    assert (dest_dir / name1).read_text() == "A\n"
    assert (dest_dir / name2).read_text() == "B\n"


@pytest.mark.parametrize("style", [
    pytest.param("brace", id="brace"),
    pytest.param("doublequote", id="doublequote", marks=pytest.mark.xfail(
        strict=True,
        reason="MGET's cmtxt() resolves backslash escapes over the "
        "whole multi-name field before cksplit() ever sees it, so an "
        "escaped doublequote needed to embed a literal one inside a "
        "doublequoted name is already gone by the time cksplit() "
        "tries to find where that name ends; see doc/spaces.md")),
])
def test_mget_multiple_embedded_doublequote_names(
        tmp_path, wermit_loopback, style):
    """
    MGET of two names, each containing a literal doublequote character, in one
    command. Known bug: with braces as the outer delimiter, the embedded double
    quote needs no escaping, matching the single-name case, and this works.  But
    with double quote as the outer delimiter, the embedded quote must be
    escaped, and MGET's field-wide xxstring() pass in doxget() resolves that
    escape away before cksplit() runs, so cksplit() does not distinguish the
    embedded quote from the name's real closing delimiter. This applies to any
    name reached via MGET.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    name1, name2 = 'file"one".txt', 'file "two" b.txt'
    (src_dir / name1).write_text("A\n")
    (src_dir / name2).write_text("B\n")
    q1 = _quote_dquote_name(name1, style)
    q2 = _quote_dquote_name(name2, style)

    result = wermit_loopback(src_dir, "", f"cd {dest_dir}, mget {q1} {q2}")

    assert_ok(result)
    assert (dest_dir / name1).read_text() == "A\n"
    assert (dest_dir / name2).read_text() == "B\n"

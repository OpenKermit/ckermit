r"""
Tests that a literal {brace} character in a filename
or other free-text field, for DIR/DELETE/RENAME/COPY/TYPE (local,
cmifi()-based) is always represented by backslash-escaping both
delimiters, "\{" and "\}" (the opposite convention from GET/REMOTE
DELETE/REMOTE RENAME/REMOTE COPY, covered in test_embedded_delimiters.py
and test_remote.py, which need a second wermit process). Everything
here runs against a single local wermit process: DELETE, RENAME,
COPY, TYPE, DIR, ASK, DEFINE, and variable substitution.

Every case was verified directly against the built binary, including
with decoy files present, before being written down as an assertion.
"""
import os
import time
import pytest
from conftest import assert_ok, start_wermit_pty, finish_wermit_pty


def _esc(name, with_space):
    """Backslash-escape both delimiters of a literal {balanced} brace
    pair, the one convention that works everywhere).
    Adds an outer {} wrap when a space also needs protecting; a
    plain space still needs a grouping delimiter, brace-escaping
    or not.md)."""
    escaped = name.replace("{", "\\{").replace("}", "\\}")
    return "{" + escaped + "}" if with_space else escaped


@pytest.mark.parametrize("with_space", [False, True], ids=["nospace", "space"])
def test_local_delete_embedded_brace(tmp_path, run_wermit, with_space):
    """
    DELETE of a file whose name contains a literal {brace} pair,
    with decoy files present that would get caught by an over-broad
    wildcard/alternation match if the escaping weren't precise.
    """
    name = "file {one} two.txt" if with_space else "file{one}.txt"
    (tmp_path / name).write_text("payload\n")
    (tmp_path / "fileone.txt").write_text("decoy 1\n")
    (tmp_path / "fileXXXone.txt").write_text("decoy 2\n")

    result = run_wermit(f"cd {tmp_path}, delete {_esc(name, with_space)}")

    assert_ok(result)
    assert not (tmp_path / name).exists()
    assert (tmp_path / "fileone.txt").exists()
    assert (tmp_path / "fileXXXone.txt").exists()


@pytest.mark.parametrize("with_space", [False, True], ids=["nospace", "space"])
def test_local_dir_embedded_brace(tmp_path, run_wermit, with_space):
    """DIRECTORY listing of a file whose name contains a literal
    {brace} pair matches only that file, not an over-broad decoy."""
    name = "file {one} two.txt" if with_space else "file{one}.txt"
    (tmp_path / name).write_text("payload\n")
    (tmp_path / "fileone.txt").write_text("decoy\n")

    result = run_wermit(f"cd {tmp_path}, dir {_esc(name, with_space)}")

    assert_ok(result)
    assert name in result.stdout
    assert "fileone.txt" not in result.stdout


def test_dir_doublequote_brace_tracking_quirk(tmp_path, run_wermit):
    """
    Regression test for the "braces inside doublequotes are tracked
    unconditionally" quirk.  Verifies setatm()'s (ckucmd.c)
    brace-depth counter runs on every character regardless of whether
    the field is currently grouped by doublequotes rather than
    braces, so a literal, unescaped, balanced {brace} pair inside a
    doublequoted filename throws off doublequote-close detection.
    Pinned down here so that if setatm()'s brace-tracking is ever
    made quote-context-aware, the resulting behavior change (both
    assertions below would then need to flip) is deliberate rather
    than accidental.
    """
    name = "d{bal}ance.txt"
    (tmp_path / name).write_text("payload\n")

    bare = run_wermit(f'cd {tmp_path}, dir "d{{bal}}ance.txt"')
    assert bare.returncode != 0
    assert name not in bare.stdout

    escaped = run_wermit(f'cd {tmp_path}, dir "d\\{{bal\\}}ance.txt"')
    assert_ok(escaped)
    assert name in escaped.stdout


def test_local_copy_embedded_brace(tmp_path, run_wermit):
    """COPY of a file whose name contains a literal {brace} pair to a
    specific new (non-directory) name works, unlike RENAME below.
    COPY does not refuse based on an "is this a wildcard" heuristic."""
    name = "file{one}.txt"
    (tmp_path / name).write_text("payload\n")

    result = run_wermit(f"cd {tmp_path}, copy {_esc(name, False)} copied.txt")

    assert_ok(result)
    assert (tmp_path / name).exists()
    assert (tmp_path / "copied.txt").read_text() == "payload\n"


def test_local_type_embedded_brace(tmp_path, run_wermit):
    """TYPE of a file whose name contains a literal {brace} pair
    prints its contents."""
    name = "file{one}.txt"
    (tmp_path / name).write_text("payload contents\n")

    result = run_wermit(f"cd {tmp_path}, type {_esc(name, False)}")

    assert_ok(result)
    assert "payload contents" in result.stdout


def test_local_rename_into_directory_embedded_brace(tmp_path, run_wermit):
    """
    RENAME of a file whose name contains a literal {brace} pair into
    a directory (keeping the same base name) works. This is the
    workaround for the specific-new-name limitation.
    """
    name = "file{one}.txt"
    (tmp_path / name).write_text("payload\n")
    (tmp_path / "dest").mkdir()

    result = run_wermit(f"cd {tmp_path}, rename {_esc(name, False)} dest")

    assert_ok(result)
    assert not (tmp_path / name).exists()
    assert (tmp_path / "dest" / name).exists()


@pytest.mark.xfail(
    strict=True,
    reason="dorenam()'s fallback iswild(line) check runs against the "
    "already-matched, real filename and can't tell a literal brace "
    "from a wildcard; see doc/spaces.md's known limitations")
def test_local_rename_to_specific_name_embedded_brace(tmp_path, run_wermit):
    """
    RENAME of a file whose name contains a literal {brace} pair to a
    specific new (non-directory) name. Known limitation:
    cmifi()'s wildness computation gets this right (verified via
    debug trace), but dorenam() (ckuus6.c) then re-checks wildness
    with iswild(line), where line is the already-resolved, matched,
    real filename. A real filename can contain a
    brace with nothing to do with wildcard intent, so this always
    reads as wild and overrides cmifi()'s correct answer, refusing
    with "Multiple source files not allowed if target is not a
    directory" even though exactly one file matches. Workaround is
    test_local_rename_into_directory_embedded_brace above.
    """
    name = "file{one}.txt"
    (tmp_path / name).write_text("payload\n")

    result = run_wermit(
        f"cd {tmp_path}, rename {_esc(name, False)} renamed.txt")

    assert_ok(result)
    assert not (tmp_path / name).exists()
    assert (tmp_path / "renamed.txt").exists()


def test_local_delete_numeric_content_embedded_brace(tmp_path, run_wermit):
    """
    Local commands can escape a numeric bracketed segment without any
    problem, unlike GET/REMOTE DELETE/REMOTE RENAME/REMOTE COPY, where
    escaping (as opposed to the recommended bare convention) hits the
    limitation documented in doc/spaces.md and pinned down by
    test_remote.py's
    test_remote_delete_numeric_content_embedded_brace_escaped_fails:
    cmifi()'s conversion-function call is gated by chkvar() finding an
    actual variable/macro reference (\\%, \\v(, \\m() somewhere in the
    field (a deliberate design choice, so plain backslashes in
    ordinary paths aren't misread as escapes). A field with no
    variable reference, like this one, never reaches xxstring()/
    xxesc() at all, so a purely numeric bracketed segment like
    "{123}", which trips up commands that unconditionally run
    the field through xxstring(), works fine here even escaped.
    """
    name = "file{123}.txt"
    (tmp_path / name).write_text("payload\n")
    (tmp_path / "fileone.txt").write_text("decoy\n")

    result = run_wermit(f"cd {tmp_path}, delete {_esc(name, False)}")

    assert_ok(result)
    assert not (tmp_path / name).exists()
    assert (tmp_path / "fileone.txt").exists()


def test_ask_help_example(wermit_path, tmp_path):
    """
    The exact first example from HELP ASK: "ASK \\%n { What is your
    name\\? }". Braces preserve the leading/trailing spaces in the
    prompt, and the backslash before "?" keeps it from being treated
    as the command-line help-request character while the prompt text
    itself is being typed/parsed. Answered over a real pty, since ASK
    reads a live keystroke stream rather than the take-file command
    parser.
    """
    cmd_str = (
        "set command more-prompting off, "
        r"ask \%n { What is your name\? }, "
        r"echo Name is: \%n, "
        "exit 0"
    )
    proc, master = start_wermit_pty(wermit_path, cmd_str, tmp_path)
    time.sleep(0.5)
    os.write(master, b"John Doe\r")
    rc, out = finish_wermit_pty(proc, master, timeout=10)

    assert rc == 0
    assert "What is your name?" in out
    assert "Name is: John Doe" in out


def test_define_with_brace_body(run_wermit):
    """
    DEFINE with a brace-delimited multi-command body, a common
    scripting primitive whose braces are pure command grouping (no
    escaping involved at all), still works.
    """
    result = run_wermit(
        "define my_macro { echo LINE_ONE, echo LINE_TWO }, my_macro")

    assert_ok(result)
    assert "LINE_ONE" in result.stdout
    assert "LINE_TWO" in result.stdout


def test_variable_substitution(run_wermit, tmp_path):
    """
    Variable substitution (\\%a positional/user variable, \\m(macro),
    \\v(builtin variable), and the dot-assignment shorthand) all still
    resolve correctly.
    """
    result = run_wermit(
        f"cd {tmp_path}, "
        "assign x hello, "
        r"echo MACRO: \m(x), "
        r".\%y := 5, "
        r"echo DOTVAR: \%y, "
        r"echo BUILTIN: \v(directory)"
    )

    assert_ok(result)
    assert "MACRO: hello" in result.stdout
    assert "DOTVAR: 5" in result.stdout
    assert f"BUILTIN: {tmp_path}" in result.stdout

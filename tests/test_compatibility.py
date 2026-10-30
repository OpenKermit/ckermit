"""Tests for SET COMPATIBILITY.

Validates SET COMPATIBILITY 9, 10, 11, and DEFAULT, as well as invocation
via kermit9 and kermit10 binary aliases.
"""

import re
import subprocess
from functools import partial

import pytest
from conftest import assert_ok, scaled

# compat_9() calls compat_10().  The keyword tests use 10.  Only
# test_compat_11_and_default_round_trip parses every keyword.
_COMPAT_KEYWORDS = ["10"]

# Server functions enabled in compatibility modes 9 and 10.
_CHANGED_ENABLE_FUNCTIONS = [
    "GET", "SEND", "MAIL", "PRINT", "REMOTE ASSIGN", "REMOTE CD/CWD",
    "REMOTE COPY", "REMOTE DIRECTORY", "REMOTE QUERY", "REMOTE MKDIR",
    "REMOTE RENAME", "REMOTE SET", "REMOTE SPACE", "REMOTE TYPE",
    "REMOTE WHO", "FINISH", "ENABLE",
]

# Server functions remaining disabled in compatibility modes.
_UNCHANGED_ENABLE_FUNCTIONS = [
    "REMOTE DELETE", "REMOTE RMDIR", "BYE", "EXIT",
]


def test_set_compatibility_rejects_unknown_keyword(run_wermit):
    """Verify an unrecognized keyword raises a syntax error."""
    result = run_wermit("set compatibility bogus")
    assert result.returncode != 0
    assert "?" in result.stdout


def test_compat_11_and_default_round_trip(run_wermit):
    """Verify each keyword sets or resets the compatibility settings.

    The first SHOW reports the C-Kermit 11 defaults.
    """
    def round_trip(show):
        result = run_wermit(
            f"{show}, "
            f"set compatibility 9, {show}, "
            f"set compatibility 11, {show}, "
            f"set compatibility 10, {show}, "
            f"set compatibility default, {show}")
        assert_ok(result)
        return result.stdout

    out = round_trip("show file")
    collisions = re.findall(r"File collision:\s+(\S+)", out)
    assert collisions == \
        ["reject", "backup", "reject", "backup", "reject"]

    modes = re.findall(r"Transfer mode:\s+(\S+)", out)
    assert modes == \
        ["manual", "automatic", "manual", "automatic", "manual"]

    confirms = re.findall(r"Receive confirm:\s+(\S+)", out)
    assert confirms == ["on", "off", "on", "off", "on"]

    pathnames = re.findall(r"Receive pathnames:\s+(\S+)", out)
    assert pathnames == ["auto"] * 5

    out = round_trip("show terminal")
    errors = re.findall(r"Autodownload: on, error (\S+)", out)
    assert errors == \
        ["continue", "stop", "continue", "stop", "continue"]

    out = round_trip("show tcp")
    families = re.findall(r"address-family:\s+(\S+)", out)
    assert families == ["auto", "ipv4", "auto", "ipv4", "auto"]


@pytest.mark.parametrize("keyword,collision", [
    ("10", "backup"), ("11", "reject"),
])
def test_compat_survives_set_protocol(run_wermit, keyword, collision):
    """Verify SET PROTOCOL keeps the collision and pathnames settings.

    SET PROTOCOL reloads both from the protocol table.  SET
    COMPATIBILITY must update the table as well as the settings.
    """
    result = run_wermit("set file collision rename, "
                        "set receive pathnames off, "
                        f"set compatibility {keyword}, "
                        "set protocol kermit, show file")
    assert_ok(result)
    assert f"File collision:          {collision}" in result.stdout, (
        result.stdout)
    assert "Receive pathnames:       auto" in result.stdout, result.stdout


@pytest.mark.parametrize("keyword", _COMPAT_KEYWORDS)
def test_compat_sets_enable_functions(run_wermit, keyword):
    """Verify a compatibility mode enables only the changed functions.

    The functions in _CHANGED_ENABLE_FUNCTIONS become Enabled.  The
    ones in _UNCHANGED_ENABLE_FUNCTIONS stay Remote only.  The
    assertion lists every function with another state.
    """
    result = run_wermit(f"set compatibility {keyword}, show server")
    assert_ok(result)
    states = {}
    for line in result.stdout.splitlines():
        for function in (_CHANGED_ENABLE_FUNCTIONS +
                         _UNCHANGED_ENABLE_FUNCTIONS):
            if line.strip().startswith(function):
                states.setdefault(function, line)
    wrong = [f for f in _CHANGED_ENABLE_FUNCTIONS
             if "Enabled" not in states.get(f, "")]
    wrong += [f for f in _UNCHANGED_ENABLE_FUNCTIONS
              if "Remote only" not in states.get(f, "")]
    assert not wrong, (wrong, result.stdout)


# --- Protocol-level check against a real 9.0.302 server ----------------
#
# Test SET COMPATIBILITY 9 against a C-Kermit 9.0.302 server to verify
# file collision behavior during file transfers.

@pytest.fixture
def old_loopback(wermit_loopback, ckermit_old_path):
    """wermit_loopback fixture bound to ckermit-old-9.0.302."""
    return partial(wermit_loopback, server_binary_path=ckermit_old_path)


def test_get_collision_compat_9_restores_backup(tmp_path, old_loopback):
    """Verify SET COMPATIBILITY 9 restores backup file collision mode."""
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    src = server_dir / "dup.txt"

    src.write_text("version 1")
    assert_ok(old_loopback(
        server_dir, "",
        f"set compatibility 9, cd {client_dir}, set delay 0, get dup.txt"))

    src.write_text("version 2, different length")
    assert_ok(old_loopback(
        server_dir, "",
        f"set compatibility 9, cd {client_dir}, set delay 0, get dup.txt"))

    assert (client_dir / "dup.txt").read_text() == \
        "version 2, different length"
    assert (client_dir / "dup.txt.~1~").read_text() == "version 1"


def test_get_collision_default_discards_without_compat(
    tmp_path, old_loopback
):
    """Verify C-Kermit 11 default discards colliding files."""
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    src = server_dir / "dup.txt"

    src.write_text("version 1")
    assert_ok(old_loopback(
        server_dir, "", f"cd {client_dir}, set delay 0, get dup.txt"))

    src.write_text("version 2, different length")
    assert_ok(old_loopback(
        server_dir, "", f"cd {client_dir}, set delay 0, get dup.txt"))

    assert (client_dir / "dup.txt").read_text() == "version 1"
    assert not (client_dir / "dup.txt.~1~").exists()


# --- Invoked as kermit9 / kermit10 --------------------------------------

def _run_as(wermit_path, tmp_path, name, commands):
    """Run wermit via a symlink to test argv[0] behavior."""
    link = tmp_path / name
    link.symlink_to(wermit_path)
    cmd_str = commands.strip()
    if not cmd_str.endswith(", exit") and not cmd_str.endswith(",exit"):
        cmd_str += ", exit"
    return subprocess.run(
        [str(link), "-H", "-Y", "-C",
         f"set command more-prompting off, {cmd_str}"],
        capture_output=True, text=True, timeout=scaled(10))


def test_invoked_as_kermit9_applies_compat_9(wermit_path, tmp_path):
    result = _run_as(wermit_path, tmp_path, "kermit9", "show file")
    assert_ok(result)
    assert "File collision:          backup" in result.stdout
    assert "Transfer mode:           automatic" in result.stdout


def test_invoked_as_kermit10_applies_compat_10(wermit_path, tmp_path):
    result = _run_as(wermit_path, tmp_path, "kermit10", "show file")
    assert_ok(result)
    assert "File collision:          backup" in result.stdout
    assert "Transfer mode:           automatic" in result.stdout


def test_invoked_as_plain_kermit_unaffected(wermit_path, tmp_path):
    result = _run_as(wermit_path, tmp_path, "kermit", "show file")
    assert_ok(result)
    assert "File collision:          reject" in result.stdout
    assert "Transfer mode:           manual" in result.stdout


def test_invoked_as_kermit9_howcalled_stays_kermit(wermit_path, tmp_path):
    """Verify alias invocation leaves program identity unchanged."""
    result = _run_as(wermit_path, tmp_path, "kermit9", r"echo \v(program)")
    assert_ok(result)
    assert "C-Kermit" in result.stdout


@pytest.mark.parametrize("kind", ["absolute", "dotdot"])
def test_compat_receive_confines_incoming_paths(wermit_path, tmp_path,
                                                kind):
    """Verify compatibility modes do not write outside the receive dir.

    Beta.12's default RECEIVE PATHNAMES AUTO confined an absolute
    incoming name.  The compatibility modes keep that.  An absolute
    name is stored under the receive directory.  A name with ".." is
    refused.
    """
    recv_dir = tmp_path / "recv" / "sub"
    send_dir = tmp_path / "send"
    recv_dir.mkdir(parents=True)
    send_dir.mkdir()
    (send_dir / "a.txt").write_text("payload\n")
    link = tmp_path / "kermit10"
    link.symlink_to(wermit_path)
    if kind == "absolute":
        target = tmp_path / "escaped-abs.txt"
        as_name = str(target)
    else:
        target = tmp_path / "escaped-dotdot.txt"
        as_name = "../../escaped-dotdot.txt"
    # The sender starts in recv_dir.  A relative CD keeps the SET HOST
    # command within TTNAMLEN when tmp_path is long.
    result = subprocess.run([
        str(link), "-H", "-Y", "-Q", "-C",
        "set command more-prompting off, set delay 0, "
        f"cd {recv_dir}, "
        f"set host /network-type:pseudoterminal {wermit_path} -H -Y -Q -C "
        "{cd ../../send, set file names literal, set send pathnames on, "
        f"send /as-name:{{{as_name}}} a.txt, quit}}, "
        "receive, close, exit"], capture_output=True, text=True,
        timeout=scaled(30), start_new_session=True)
    assert not target.exists(), result.stdout + result.stderr
    if kind == "absolute":
        confined = recv_dir / str(target).lstrip("/")
        assert confined.read_text() == "payload\n", \
            result.stdout + result.stderr
    else:
        assert "Access denied" in result.stdout, \
            result.stdout + result.stderr


@pytest.mark.parametrize("keyword", ["10", "11"])
def test_compat_does_not_undo_disable_enable(run_wermit, keyword):
    """Verify SET COMPATIBILITY does not re-enable after DISABLE ENABLE.

    DISABLE ENABLE can not be undone, so a later SET COMPATIBILITY must
    not turn on a disabled server function either.
    """
    result = run_wermit("disable enable, disable mkdir, disable mail, "
                        f"set compatibility {keyword}, show server")
    assert_ok(result)
    for name in ("REMOTE MKDIR", "MAIL", "ENABLE"):
        line = re.search(rf"^ *{name} +(\S.*)$", result.stdout, re.M)
        assert line and line.group(1).strip() == "Disabled", \
            (name, result.stdout)


def test_compat_10_restores_enable_without_disable(run_wermit):
    """Verify SET COMPATIBILITY 10 still restores Beta.12 ENABLE values."""
    result = run_wermit("set compatibility 10, show server")
    assert_ok(result)
    for name in ("REMOTE MKDIR", "MAIL", "ENABLE"):
        line = re.search(rf"^ *{name} +(\S.*)$", result.stdout, re.M)
        assert line and line.group(1).strip() == "Enabled", \
            (name, result.stdout)

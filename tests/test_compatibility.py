"""Tests for SET COMPATIBILITY.

Validates SET COMPATIBILITY 9, 10, 11, and DEFAULT, as well as invocation
via kermit9 and kermit10 binary aliases.
"""

import re
import subprocess
from functools import partial

import pytest
from conftest import assert_ok

_COMPAT_KEYWORDS = ["9", "10"]

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


def _show_server_lines(run_wermit, keyword):
    result = run_wermit(f"set compatibility {keyword}, show server")
    assert_ok(result)
    return result.stdout


@pytest.mark.parametrize("keyword", ["9", "10", "11", "default", "DEFAULT"])
def test_set_compatibility_accepts_each_keyword(run_wermit, keyword):
    """Verify each documented keyword parses without error."""
    result = run_wermit(f"set compatibility {keyword}")
    assert_ok(result)


def test_set_compatibility_rejects_unknown_keyword(run_wermit):
    """Verify an unrecognized keyword raises a syntax error."""
    result = run_wermit("set compatibility bogus")
    assert result.returncode != 0
    assert "?" in result.stdout


def test_help_set_compatibility(run_wermit):
    """Verify HELP SET COMPATIBILITY output."""
    result = run_wermit("help set compatibility")
    assert_ok(result)
    assert "SET COMPATIBILITY" in result.stdout
    assert "9.0.302" in result.stdout
    assert "10.0 Beta.12" in result.stdout


def test_compat_defaults_before_any_command(run_wermit):
    """Verify C-Kermit 11 default settings before compatibility mode."""
    result = run_wermit("show file")
    assert_ok(result)
    assert "Transfer mode:           manual" in result.stdout
    assert "Receive pathnames:       auto" in result.stdout
    assert "Receive confirm:         on" in result.stdout
    assert "File collision:          discard" in result.stdout


def test_compat_11_and_default_round_trip(run_wermit):
    """Verify SET COMPATIBILITY 11 and DEFAULT reset settings."""
    result = run_wermit(
        "show file, "
        "set compatibility 9, show file, "
        "set compatibility 11, show file, "
        "set compatibility 10, show file, "
        "set compatibility default, show file")
    assert_ok(result)

    collisions = re.findall(r"File collision:\s+(\S+)", result.stdout)
    assert collisions == \
        ["discard", "backup", "discard", "backup", "discard"]

    modes = re.findall(r"Transfer mode:\s+(\S+)", result.stdout)
    assert modes == \
        ["manual", "automatic", "manual", "automatic", "manual"]

    tcp_result = run_wermit(
        "show tcp, "
        "set compatibility 9, show tcp, "
        "set compatibility 11, show tcp, "
        "set compatibility 10, show tcp, "
        "set compatibility default, show tcp")
    assert_ok(tcp_result)
    families = re.findall(r"address-family:\s+(\S+)", tcp_result.stdout)
    assert families == ["auto", "ipv4", "auto", "ipv4", "auto"]


@pytest.mark.parametrize("keyword", _COMPAT_KEYWORDS)
def test_compat_file_settings(run_wermit, keyword):
    result = run_wermit(f"set compatibility {keyword}, show file")
    assert_ok(result)
    assert "Transfer mode:           automatic" in result.stdout
    assert "Receive pathnames:       absolute" in result.stdout
    assert "Receive confirm:         off" in result.stdout
    assert "File collision:          backup" in result.stdout


@pytest.mark.parametrize("keyword", _COMPAT_KEYWORDS)
def test_compat_autodownload_error(run_wermit, keyword):
    result = run_wermit(f"set compatibility {keyword}, show terminal")
    assert_ok(result)
    assert "Autodownload: on, error stop" in result.stdout


@pytest.mark.parametrize("keyword", _COMPAT_KEYWORDS)
def test_compat_tcp_address_family(run_wermit, keyword):
    result = run_wermit(f"set compatibility {keyword}, show tcp")
    assert_ok(result)
    assert "address-family: ipv4" in result.stdout


@pytest.mark.parametrize("keyword", _COMPAT_KEYWORDS)
@pytest.mark.parametrize("function", _CHANGED_ENABLE_FUNCTIONS)
def test_compat_enables_changed_functions(run_wermit, keyword, function):
    lines = _show_server_lines(run_wermit, keyword)
    for line in lines.splitlines():
        if line.strip().startswith(function):
            assert "Enabled" in line, line
            return
    pytest.fail(f"{function!r} not found in SHOW SERVER output:\n{lines}")


@pytest.mark.parametrize("keyword", _COMPAT_KEYWORDS)
@pytest.mark.parametrize("function", _UNCHANGED_ENABLE_FUNCTIONS)
def test_compat_leaves_unrelated_functions_alone(
    run_wermit, keyword, function
):
    lines = _show_server_lines(run_wermit, keyword)
    for line in lines.splitlines():
        if line.strip().startswith(function):
            assert "Remote only" in line, line
            return
    pytest.fail(f"{function!r} not found in SHOW SERVER output:\n{lines}")


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
        capture_output=True, text=True, timeout=10)


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
    assert "File collision:          discard" in result.stdout
    assert "Transfer mode:           manual" in result.stdout


def test_invoked_as_kermit9_howcalled_stays_kermit(wermit_path, tmp_path):
    """Verify alias invocation leaves program identity unchanged."""
    result = _run_as(wermit_path, tmp_path, "kermit9", r"echo \v(program)")
    assert_ok(result)
    assert "C-Kermit" in result.stdout

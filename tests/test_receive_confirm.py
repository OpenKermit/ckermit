"""Tests for SET RECEIVE CONFIRM interactive prompt.

Executes client/server loopback commands over pseudoterminals to feed
scripted input ("yes", "no", "quit", "go") on stdin.
"""
import curses
import os
import pytest
from conftest import (make_loopback_dirs, start_wermit_pty,
                      finish_wermit_pty, _wait_for_pty_marker)


def _write_server_script(server_dir, commands):
    """Write script to cd into server_dir and execute commands."""
    script = server_dir.parent / f"server_{server_dir.name}.ksc"
    lines = [f"cd {server_dir}"] + [c.strip() for c in commands.split(",")
                                     if c.strip()]
    script.write_text("\n".join(lines) + "\n")
    return script


def _run_client(run_wermit, wermit_path, server_script, client_dir,
                 client_cmds, answers=None, timeout=10):
    """Run client against server_script over pseudoterminal loopback."""
    cmd = [
        "-H", "-Y", "-Q", "-C",
        "set command more-prompting off, set delay 0, "
        f"set host /network-type:pseudoterminal {wermit_path} "
        f"{server_script}, set delay 0, "
        f"cd {client_dir}, {client_cmds}, close, exit"
    ]
    return run_wermit(cmd, input_data=answers, timeout=timeout)


def test_confirm_on_by_default(tmp_path, run_wermit, wermit_path):
    """Verify RECEIVE prompts even without an explicit CONFIRM setting."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "surprise.txt").write_text("payload\n")
    script = _write_server_script(server_dir, "send surprise.txt")

    result = _run_client(run_wermit, wermit_path, script, client_dir,
                         "receive", answers="yes\n")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Accept incoming file" in result.stdout
    assert (client_dir / "surprise.txt").read_text() == "payload\n"


def test_confirm_off_disables_prompting(tmp_path, run_wermit, wermit_path):
    """Verify RECEIVE does not prompt when CONFIRM is explicitly off."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "surprise.txt").write_text("payload\n")
    script = _write_server_script(server_dir, "send surprise.txt")

    result = _run_client(run_wermit, wermit_path, script, client_dir,
                         "set receive confirm off, receive", answers=None)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Accept incoming file" not in result.stdout
    assert (client_dir / "surprise.txt").read_text() == "payload\n"


def test_confirm_on_get_exact_match_no_prompt(tmp_path, run_wermit,
                                               wermit_path):
    """Verify GET of a precise name does not prompt under CONFIRM ON."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "expected.txt").write_text("hello\n")
    script = _write_server_script(server_dir, "server")

    result = _run_client(
        run_wermit, wermit_path, script, client_dir,
        "set receive confirm on, get expected.txt", answers=None)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (client_dir / "expected.txt").read_text() == "hello\n"


def test_confirm_on_get_braced_name_with_space_no_prompt(
        tmp_path, run_wermit, wermit_path):
    """
    A GET of a brace-quoted name containing a space (e.g.
    "get {file one.txt}") does not prompt under CONFIRM ON.
    rq_confirm_start() splits cmarg into the requested name
    via fnsplit() to recognize the incoming file as an exact match.
    """
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "file one.txt").write_text("hello\n")
    script = _write_server_script(server_dir, "server")

    result = _run_client(
        run_wermit, wermit_path, script, client_dir,
        "set receive confirm on, get {file one.txt}", answers=None)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Accept incoming file" not in result.stdout
    assert (client_dir / "file one.txt").read_text() == "hello\n"


def test_confirm_on_get_embedded_brace_name_no_prompt(
        tmp_path, run_wermit, wermit_path):
    """
    A GET of a name with an embedded {brace} and no space
    (as in "get file{one}.txt") does not prompt under CONFIRM ON.
    fnsplit() resolves such a name back to its literal form, which
    looks exactly like ckmatch()'s bare-brace alternation syntax;
    rq_confirm_start() must re-escape it with bresc() before matching,
    or it is wrongly treated as a wildcard and always prompts.
    """
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "file{one}.txt").write_text("hello\n")
    script = _write_server_script(server_dir, "server")

    result = _run_client(
        run_wermit, wermit_path, script, client_dir,
        "set receive confirm on, get file{one}.txt", answers=None)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Accept incoming file" not in result.stdout
    assert (client_dir / "file{one}.txt").read_text() == "hello\n"


def test_confirm_on_mget_braced_names_with_spaces_no_prompt(
        tmp_path, run_wermit, wermit_path):
    """
    An MGET of several brace-quoted names, each containing a space,
    must not prompt for any of them under CONFIRM ON: fnsplit() must
    correctly split cmarg into all of the individually brace-quoted
    names, not just the first, for rq_confirm_start() to recognize
    each incoming file as an exact match.
    """
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "file one.txt").write_text("A\n")
    (server_dir / "file two.txt").write_text("B\n")
    script = _write_server_script(server_dir, "server")

    result = _run_client(
        run_wermit, wermit_path, script, client_dir,
        "set receive confirm on, "
        "mget {file one.txt} {file two.txt}", answers=None)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Accept incoming file" not in result.stdout
    assert (client_dir / "file one.txt").read_text() == "A\n"
    assert (client_dir / "file two.txt").read_text() == "B\n"


def test_confirm_on_receive_prompts_and_yes_accepts(tmp_path, run_wermit,
                                                     wermit_path):
    """Verify RECEIVE prompts under CONFIRM ON and yes accepts file."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "surprise.txt").write_text("payload\n")
    script = _write_server_script(server_dir, "send surprise.txt")

    result = _run_client(run_wermit, wermit_path, script, client_dir,
                         "set receive confirm on, receive", answers="yes\n")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Accept incoming file" in result.stdout
    assert (client_dir / "surprise.txt").read_text() == "payload\n"


def test_confirm_no_skips_one_file_and_continues(tmp_path, run_wermit,
                                                  wermit_path):
    """Verify answering no skips only the current file."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "a.txt").write_text("A\n")
    (server_dir / "b.txt").write_text("B\n")
    script = _write_server_script(server_dir, "send *.txt")

    result = _run_client(run_wermit, wermit_path, script, client_dir,
                         "set receive confirm on, receive",
                         answers="no\nyes\n")

    assert not (client_dir / "a.txt").exists()
    assert (client_dir / "b.txt").read_text() == "B\n"


def test_confirm_quit_aborts_whole_transfer(tmp_path, run_wermit,
                                             wermit_path):
    """Verify answering quit aborts the entire transfer."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "a.txt").write_text("A\n")
    (server_dir / "b.txt").write_text("B\n")
    script = _write_server_script(server_dir, "send *.txt")

    result = _run_client(run_wermit, wermit_path, script, client_dir,
                         "set receive confirm on, receive",
                         answers="quit\n")

    assert result.returncode != 0
    assert not (client_dir / "a.txt").exists()
    assert not (client_dir / "b.txt").exists()
    assert result.stdout.count("Accept incoming file") == 1


def test_confirm_go_accepts_rest_without_asking(tmp_path, run_wermit,
                                                 wermit_path):
    """Verify answering go accepts all remaining files without prompting."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "a.txt").write_text("A\n")
    (server_dir / "b.txt").write_text("B\n")
    script = _write_server_script(server_dir, "send *.txt")

    result = _run_client(run_wermit, wermit_path, script, client_dir,
                         "set receive confirm on, receive", answers="go\n")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (client_dir / "a.txt").read_text() == "A\n"
    assert (client_dir / "b.txt").read_text() == "B\n"
    assert result.stdout.count("Accept incoming file") == 1


def test_confirm_switch_overrides_global_setting(tmp_path, run_wermit,
                                                  wermit_path):
    """Verify /CONFIRM switch overrides global setting."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "surprise.txt").write_text("payload\n")
    script = _write_server_script(server_dir, "send surprise.txt")

    result = _run_client(run_wermit, wermit_path, script, client_dir,
                         "receive /confirm:on", answers="yes\n")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Accept incoming file" in result.stdout
    assert (client_dir / "surprise.txt").read_text() == "payload\n"


def test_confirm_prompt_suspends_fullscreen_display(tmp_path, wermit_path):
    """Verify confirmation prompt suspends and resumes fullscreen display."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "surprise.txt").write_text("payload\n")
    script = _write_server_script(server_dir, "send surprise.txt")

    client_cmd = (
        "set delay 0, "
        f"set host /network-type:pseudoterminal {wermit_path} {script}, "
        "set delay 0, set file display fullscreen, "
        "set receive confirm on, receive, close, exit"
    )

    # Pick a specific terminal and look for its byte sequences, isolating
    # from differences in the test environment.
    curses.setupterm(term="screen")
    rmcup = curses.tigetstr("rmcup")
    smcup = curses.tigetstr("smcup")
    assert rmcup and smcup, (
        "\"screen\" terminfo on this system has no smcup/rmcup; "
        "picked as TERM specifically because it should always have "
        "both, so this needs a different TERM value here instead")

    env_term = os.environ.get("TERM")
    os.environ["TERM"] = "screen"
    try:
        proc, master = start_wermit_pty(wermit_path, client_cmd, client_dir)
        try:
            prefix, found = _wait_for_pty_marker(
                master, b"Accept incoming file", timeout=10)
            assert found, (
                "confirm prompt never appeared: " +
                prefix.decode("utf-8", errors="replace"))
            assert rmcup in prefix, (
                "fullscreen display was not suspended (no rmcup) "
                "before the prompt: " +
                prefix.decode("utf-8", errors="replace"))
            os.write(master, b"yes\r\n")
            returncode, rest = finish_wermit_pty(proc, master, timeout=10)
        finally:
            try:
                os.close(master)
            except OSError:
                pass
    finally:
        if env_term is None:
            os.environ.pop("TERM", None)
        else:
            os.environ["TERM"] = env_term

    output = prefix.decode("utf-8", errors="replace") + rest
    assert returncode == 0, output
    name_pos = rest.find("RECEIVING: surprise.txt")
    assert name_pos != -1, (
        "filename field was not redrawn after the prompt: " + output)
    resume_pos = rest.find(smcup.decode("latin-1"))
    assert resume_pos != -1, (
        "fullscreen display was not resumed (no smcup) after the "
        "prompt: " + output)
    assert name_pos > resume_pos, (
        "filename field appeared before the fullscreen display was "
        "resumed, not as part of its repaint: " + output)
    assert (client_dir / "surprise.txt").read_text() == "payload\n"

"""Regression tests for string and buffer length boundaries.

Tests verify behavior when inputs exceed 8-bit length boundaries
(127 and 255 bytes).
"""
from conftest import make_loopback_dirs


def _distinct_chars(length):
    """Return a string of alternating lowercase letters of the given length.

    Varying characters prevent Kermit repeat-count compression.
    """
    return "".join(chr(97 + (i % 26)) for i in range(length))


def test_send_except_pattern_over_256_rejected(run_wermit):
    """Verify SEND /EXCEPT: rejects patterns longer than 256 characters."""
    pattern = _distinct_chars(300)
    result = run_wermit(f"send /except:{pattern} nonexistent.txt")
    assert "?Pattern too long - 256 max" in result.stdout, result.stdout


def test_take_file_long_nested_path_with_argument(tmp_path, run_wermit):
    """Verify TAKE with arguments runs a script path longer than 255 bytes."""
    name = _distinct_chars(20)
    path = tmp_path
    for i in range(15):
        path = path / f"{name}{i}"
    path.mkdir(parents=True)
    script = path / "script.ksc"
    script.write_text("echo TAKE-WORKED [\\%1]\n")
    assert len(str(script)) > 255, "test setup should exceed 255 chars"

    result = run_wermit(f"take {script} hello")
    assert "TAKE-WORKED [hello]" in result.stdout, result.stdout


def test_remote_login_long_username_does_not_crash(tmp_path, wermit_loopback):
    """Verify REMOTE LOGIN with a username over 255 characters fails cleanly.

    The command is rejected downstream without crashing.
    """
    name = _distinct_chars(300)
    client_cmd = f"remote login {name} a a"
    result = wermit_loopback(tmp_path, client_commands=client_cmd)
    assert result.returncode >= 0, (
        f"wermit crashed (returncode {result.returncode}) instead of "
        f"failing cleanly; stdout: {result.stdout}\nstderr: "
        f"{result.stderr}"
    )
    assert "malloc" not in (result.stdout + result.stderr).lower()


def test_get_as_deep_nonexistent_directory_created(tmp_path, wermit_loopback):
    """Verify GET creates a destination directory path over 255 chars."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "myfile.txt").write_text("hello world")

    name = _distinct_chars(20)
    destdir = client_dir
    for i in range(13):
        destdir = destdir / f"{name}{i}"
    assert len(str(destdir)) + 1 > 255, "test setup should exceed 255 chars"

    client_cmd = f"cd {client_dir}, get myfile.txt {destdir}/"
    result = wermit_loopback(server_dir, "", client_cmd)

    received = destdir / "myfile.txt"
    assert received.exists(), (
        f"destination directory/file was not created; stdout: "
        f"{result.stdout}"
    )
    assert received.read_text() == "hello world"


def test_remote_login_long_username_not_flagged_too_long(tmp_path,
                                                          wermit_loopback):
    """Verify encstr() does not report truncation for a 300-byte username.

    Setting reliable on allows packets large enough to hold the username.
    """
    name = _distinct_chars(300)
    client_cmd = f"set reliable on, remote login {name} a a"
    result = wermit_loopback(tmp_path, client_commands=client_cmd)
    assert "String too long" not in result.stdout, (
        "encstr() reported truncation for a 300-byte username that "
        f"fits comfortably in a negotiated packet; stdout: "
        f"{result.stdout}"
    )


def _read_server_debug_log(server_dir):
    """Return the contents of the server debug log."""
    return (server_dir / "server-debug.log").read_text()


def test_remote_query_long_variable_name_wrapped_correctly(
        tmp_path, wermit_loopback):
    """Verify REMOTE QUERY handles variable names longer than 255 characters.

    The server wraps the variable name in \\m(...) for evaluation.
    Check the server debug log to confirm the full name was looked up.
    """
    name = _distinct_chars(300)
    value = "REMOTE-QUERY-VALUE-MARKER"
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    log_path = server_dir / "server-debug.log"

    result = wermit_loopback(
        server_dir,
        server_setup_cmds=f"log debug {log_path}, .{name} := {value}",
        client_commands=f"set reliable on, remote query user {name}",
    )
    log = _read_server_debug_log(server_dir)
    assert f"vp[{value}]" in log, (
        f"expected the full 300-char variable name to resolve to "
        f"{value!r}; server debug log did not show it (client "
        f"stdout: {result.stdout})"
    )


def test_cmnum_overflow_guard_rejects_huge_set_argument(run_wermit):
    """Verify SET rejects numeric arguments exceeding integer range."""
    result = run_wermit("set receive timeout 99999999999")
    assert (
        "?Magnitude of result too large for integer - 99999999999"
        in result.stdout
    ), result.stdout

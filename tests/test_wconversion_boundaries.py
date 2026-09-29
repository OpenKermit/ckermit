"""Regression tests for string and buffer length boundaries.

Tests verify behavior when inputs exceed 8-bit length boundaries
(127 and 255 bytes).
"""
import os
import socket
import time

import pytest

from conftest import (make_loopback_dirs, start_wermit_pty,
                      finish_wermit_pty, _wait_for_pty_marker)
from test_iksdb import (_build_has_iksdb, _connect_iksd, _close_iksd,
                        iksd_path)  # noqa: F401 (fixture)


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


def test_get_except_pattern_over_256_rejected(run_wermit):
    """Verify GET /EXCEPT: rejects patterns longer than 256 characters."""
    pattern = _distinct_chars(300)
    result = run_wermit(f"get /except:{pattern} nonexistent.txt")
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


def _deep_dir(base, depth=13):
    """Create and return a directory path exceeding 255 characters."""
    name = _distinct_chars(20)
    path = base
    for i in range(depth):
        path = path / f"{name}{i}"
    path.mkdir(parents=True)
    assert len(str(path)) > 255, "test setup should exceed 255 characters"
    return path


def test_get_move_to_long_directory_created(tmp_path, run_wermit):
    """Verify GET /MOVE-TO: creates a directory path over 255 characters.

    The directory is created before checking for an active connection.
    """
    destdir = str(tmp_path)
    while len(destdir) < 440:
        destdir += "/" + _distinct_chars(10)
    destdir += "/" + "x" * (449 - len(destdir))
    assert len(destdir) == 450

    result = run_wermit(f"get /move-to:{destdir} nonexistent.txt")
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}; "
        f"stderr: {result.stderr}"
    )
    assert os.path.isdir(destdir), (
        f"GET /MOVE-TO: did not create the directory; stdout: "
        f"{result.stdout}"
    )


def test_get_as_name_long_path(tmp_path, wermit_loopback):
    """Verify GET /AS-NAME: stores a file under a path over 255 characters."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "myfile.txt").write_text("hello world")
    received = _deep_dir(client_dir) / "renamed.txt"

    client_cmd = (f"cd {client_dir}, set receive confirm off, "
                  f"get /as-name:{received} myfile.txt")
    result = wermit_loopback(server_dir, "", client_cmd)

    assert received.exists(), (
        f"file was not stored under the as-name; stdout: {result.stdout}"
    )
    assert received.read_text() == "hello world"


def test_get_filter_long_command(tmp_path, wermit_loopback):
    """Verify GET /FILTER: runs a filter command over 255 characters."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (server_dir / "myfile.txt").write_text("hello world")
    destdir = _deep_dir(client_dir)

    client_cmd = (f"cd {client_dir}, "
                  f"get /filter:{{cat > {destdir}/\\v(filename)}} "
                  "myfile.txt")
    result = wermit_loopback(server_dir, "", client_cmd)

    received = destdir / "myfile.txt"
    assert received.exists(), (
        f"filter did not write the file; stdout: {result.stdout}"
    )
    assert received.read_text() == "hello world"


def test_send_move_to_long_directory_created(tmp_path, run_wermit):
    """Verify SEND /MOVE-TO: creates a directory path over 255 characters.

    The directory is created before checking for an active connection.
    """
    src = tmp_path / "f.txt"
    src.write_text("hello world")
    destdir = str(tmp_path)
    while len(destdir) < 440:
        destdir += "/" + _distinct_chars(10)
    destdir += "/" + "x" * (449 - len(destdir))
    assert len(destdir) == 450

    result = run_wermit(f"send /move-to:{destdir} {src}")
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}; "
        f"stderr: {result.stderr}"
    )
    assert os.path.isdir(destdir), (
        f"SEND /MOVE-TO: did not create the directory; stdout: "
        f"{result.stdout}"
    )


def test_send_long_source_path_with_as_name(tmp_path, wermit_loopback):
    """Verify SEND with a source path over 255 characters and an as-name."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    src = _deep_dir(client_dir) / "myfile.txt"
    src.write_text("hello world")

    client_cmd = f"send {src} renamed.txt"
    result = wermit_loopback(server_dir, "", client_cmd)

    received = server_dir / "renamed.txt"
    assert received.exists(), (
        f"file not received under the as-name; stdout: {result.stdout}"
    )
    assert received.read_text() == "hello world"


def test_send_filter_long_command(tmp_path, wermit_loopback):
    """Verify SEND /FILTER: runs a filter command over 255 characters."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    srcdir = _deep_dir(client_dir)
    (srcdir / "myfile.txt").write_text("hello world")

    client_cmd = (f"cd {client_dir}, "
                  f"send /filter:{{cd {srcdir} && tr a-z A-Z "
                  "< \\v(filename)} "
                  f"{srcdir}/myfile.txt")
    result = wermit_loopback(server_dir, "", client_cmd)

    received = server_dir / "myfile.txt"
    assert received.exists(), (
        f"file not received; stdout: {result.stdout}"
    )
    assert received.read_text() == "HELLO WORLD"


def test_send_listfile_long_path(tmp_path, wermit_loopback):
    """Verify SEND /LISTFILE: reads a list file path over 255 characters."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (client_dir / "myfile.txt").write_text("hello world")
    listfile = _deep_dir(client_dir) / "list.txt"
    listfile.write_text(f"{client_dir}/myfile.txt\n")

    client_cmd = f"cd {client_dir}, send /listfile:{listfile}"
    result = wermit_loopback(server_dir, "", client_cmd)

    received = server_dir / "myfile.txt"
    assert received.exists(), (
        f"file not received; stdout: {result.stdout}"
    )
    assert received.read_text() == "hello world"


def test_add_send_list_long_name_and_alias(tmp_path, run_wermit):
    """Verify ADD SEND-LIST stores a filename and alias over 255 characters."""
    src = _deep_dir(tmp_path) / "myfile.txt"
    src.write_text("hello world")
    alias = _distinct_chars(300)

    result = run_wermit(f"add send-list {src} text {alias}, "
                        "show send-list")
    assert f"{src}, mode: text, alias: {alias}" in result.stdout, (
        result.stdout
    )


def test_send_mail_long_address_does_not_crash(tmp_path, run_wermit):
    """Verify SEND /MAIL: accepts an address over 255 characters.

    The address is not observable without an active connection.
    Verify wermit does not crash.
    """
    src = tmp_path / "f.txt"
    src.write_text("hello world")
    result = run_wermit(f"send /mail:{_distinct_chars(300)} {src}")
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}; "
        f"stderr: {result.stderr}"
    )


def test_send_print_long_options_does_not_crash(tmp_path, run_wermit):
    """Verify SEND /PRINT: accepts options over 255 characters.

    The options are not observable without an active connection.
    Verify wermit does not crash.
    """
    src = tmp_path / "f.txt"
    src.write_text("hello world")
    result = run_wermit(f"send /print:{_distinct_chars(300)} {src}")
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}; "
        f"stderr: {result.stderr}"
    )


def test_connect_trigger_long_string(tmp_path, wermit_path):
    r"""Verify CONNECT /TRIGGER: matches a string over 255 characters.

    CONNECT requires a terminal, so wermit runs under a pty.
    """
    trigger = _distinct_chars(300)
    cmd = (f"set exit warning off, "
           f"set host /pty sh -c 'sleep 1; echo XX{trigger}YY; sleep 2', "
           f"connect /trigger:{trigger}, "
           "echo TRIG=[\\v(trigger)], exit")
    proc, master = start_wermit_pty(wermit_path, cmd, tmp_path)
    rc, out = finish_wermit_pty(proc, master, timeout=30)
    assert rc == 0, f"wermit exited {rc}; output: {out}"
    assert f"TRIG=[{trigger}]" in out, out


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


def test_remote_login_long_username_truncation_detected(tmp_path,
                                                        wermit_loopback):
    """Verify encstr() detects truncation of a 300-byte username.

    Without RELIABLE, slow-start limits the first packet to about 233
    data bytes, so the username does not fit. encstr() compares the
    encoded position against the full string length. A length
    narrowed to 8 bits (300 becomes 44) would miss the truncation and
    send a partial username.
    """
    name = _distinct_chars(300)
    client_cmd = f"remote login {name} a a"
    result = wermit_loopback(tmp_path, client_commands=client_cmd)
    assert "String too long" in result.stdout, (
        "encstr() did not report truncation for a 300-byte username "
        f"that exceeds the slow-start packet size; stdout: "
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


def test_send_long_filename_rejected_not_truncated(tmp_path,
                                                   wermit_loopback):
    """Verify SEND rejects a filename exceeding negotiated packet size.

    On a connection without RELIABLE enabled, slow-start limits the initial
    packet size to 233 filename bytes. Longer filenames must be rejected
    rather than truncated.
    """
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    name = _distinct_chars(250)
    (client_dir / name).write_text("hello world")

    client_cmd = f"cd {client_dir}, send {name}"
    result = wermit_loopback(server_dir, "", client_cmd)

    assert "Filename too long" in result.stdout, result.stdout
    arrived = list(server_dir.iterdir())
    assert not arrived, (
        f"a file was created on the far end despite the rejection: "
        f"{arrived}\nstdout: {result.stdout}"
    )


def _as_name_256():
    """Return a relative pathname of exactly 256 characters."""
    name = "/".join(_distinct_chars(20) + str(i) for i in range(11))
    name += "/" + "n" * (255 - len(name))
    assert len(name) == 256
    return name


def test_send_as_name_switch_256(tmp_path, wermit_loopback):
    """Verify SEND /AS-NAME: sends a 256-character as-name intact."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (client_dir / "myfile.txt").write_text("hello world")
    asname = _as_name_256()

    client_cmd = (f"cd {client_dir}, set reliable on, "
                  f"send /as-name:{asname} myfile.txt")
    result = wermit_loopback(server_dir, "set receive pathnames relative",
                             client_cmd)

    received = server_dir / asname
    assert received.exists(), (
        f"file not received under the as-name; stdout: {result.stdout}"
    )
    assert received.read_text() == "hello world"


def test_send_as_name_switch_256_does_not_crash(tmp_path, run_wermit):
    """Verify SEND /AS-NAME: accepts a 256-character value.

    The value is not observable without an active connection.
    Verify wermit does not crash.
    """
    src = tmp_path / "f.txt"
    src.write_text("hello world")
    result = run_wermit(f"send /as-name:{_distinct_chars(256)} {src}")
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}; "
        f"stderr: {result.stderr}"
    )


def test_send_trailing_as_name_256(tmp_path, wermit_loopback):
    """Verify SEND with a trailing 256-character as-name."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (client_dir / "myfile.txt").write_text("hello world")
    asname = _as_name_256()

    client_cmd = (f"cd {client_dir}, set reliable on, "
                  f"send myfile.txt {asname}")
    result = wermit_loopback(server_dir, "set receive pathnames relative",
                             client_cmd)

    received = server_dir / asname
    assert received.exists(), (
        f"file not received under the as-name; stdout: {result.stdout}"
    )
    assert received.read_text() == "hello world"


def test_send_long_as_name_rejected(tmp_path, wermit_loopback):
    """Verify SEND rejects an as-name over 256 characters."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (client_dir / "myfile.txt").write_text("hello world")
    name = "/".join(_distinct_chars(20) + str(i) for i in range(13))
    asname = name + "/renamed.txt"
    assert len(asname) > 256

    client_cmd = (f"cd {client_dir}, set reliable on, "
                  f"send /as-name:{asname} myfile.txt")
    result = wermit_loopback(server_dir, "set receive pathnames relative",
                             client_cmd)

    assert "As-name too long" in result.stdout, result.stdout
    arrived = [p for p in server_dir.rglob("*") if p.is_file()]
    assert not arrived, (
        f"a file was created on the far end despite the rejection: "
        f"{arrived}\nstdout: {result.stdout}"
    )


def test_script_expect_trace_survives_long_preamble(tmp_path,
                                                   wermit_loopback):
    """Verify SCRIPT does not overrun its trace buffer on long inputs.

    dorseq() appends received bytes to a 512-byte trace buffer while
    evaluating expect sequences. Sending more non-matching bytes than
    the buffer can hold before the match string verifies the length
    guard prevents an overflow.
    """
    junk = _distinct_chars(600)
    server_setup_cmds = f"output {{{junk}}}, output {{MATCHED}}"
    client_cmd = (
        "script MATCHED, if success echo SCRIPT-OK, "
        "if failure echo SCRIPT-FAIL"
    )
    result = wermit_loopback(tmp_path, server_setup_cmds, client_cmd)

    assert result.returncode >= 0, (
        f"wermit crashed (returncode {result.returncode}) instead of "
        f"completing SCRIPT; stdout: {result.stdout}\nstderr: "
        f"{result.stderr}"
    )
    assert "SCRIPT-OK" in result.stdout, result.stdout


def test_autodownload_ask_prompt_shows_full_path(tmp_path, wermit_path):
    """Verify AUTODOWNLOAD ASK prompt displays paths over 255 characters.

    An incoming transfer during a CONNECT session prompts for confirmation
    when AUTODOWNLOAD ASK is set. Check that the prompt displays the full
    destination path without truncation.
    """
    name = _distinct_chars(20)
    near_dir = tmp_path
    for i in range(13):
        near_dir = near_dir / f"{name}{i}"
    near_dir.mkdir(parents=True)
    assert len(str(near_dir)) > 255, "test setup should exceed 255 chars"

    far_dir = tmp_path / "far"
    far_dir.mkdir()
    (far_dir / "testfile.txt").write_text("autodownload prompt test\n")
    far_ksc = tmp_path / "far.ksc"
    far_ksc.write_text(
        f"set delay 0\ncd {far_dir}\nsend testfile.txt\nexit\n"
    )

    client_cmd = (
        "set terminal autodownload ask, "
        f"set host /network-type:pseudoterminal {wermit_path} {far_ksc}, "
        "connect, close, exit"
    )
    proc, master = start_wermit_pty(wermit_path, client_cmd, near_dir)
    try:
        prefix, found = _wait_for_pty_marker(master, b"Filename [", 15)
        assert found, (
            "autodownload confirmation prompt never appeared: " +
            prefix.decode("utf-8", errors="replace")
        )
        # The pty can deliver the prompt in pieces. Read through the
        # closing bracket so the whole default path is present.
        if b"]" not in prefix.split(b"Filename [", 1)[1]:
            more, found = _wait_for_pty_marker(master, b"]", 15)
            prefix += more
            assert found, (
                "autodownload prompt path never completed: " +
                prefix.decode("utf-8", errors="replace")
            )
        prefix_text = prefix.decode("utf-8", errors="replace")
        expected_path = str(near_dir / "testfile.txt")
        assert expected_path in prefix_text, (
            f"prompt did not show the full destination path "
            f"{expected_path!r}: {prefix_text}"
        )
        os.write(master, b"\r")

        prefix2, found2 = _wait_for_pty_marker(
            master, b"Accept incoming file", 10)
        assert found2, (
            "receive-confirm prompt never appeared: " +
            prefix2.decode("utf-8", errors="replace")
        )
        os.write(master, b"yes\r\n")

        returncode, rest = finish_wermit_pty(proc, master, timeout=15)
    finally:
        try:
            os.close(master)
        except OSError:
            pass

    assert returncode == 0, prefix_text + rest
    received = near_dir / "testfile.txt"
    assert received.exists(), (
        f"file was not received; output: {prefix_text}{rest}"
    )
    assert received.read_text() == "autodownload prompt test\n"


def test_iksd_login_long_username_and_password(
        run_wermit, iksd_path, tmp_path):
    """Verify IKSD handles login credentials over 255 characters.

    IKSD allows three login attempts before exiting with status 1.
    The test sends 270-character credentials and refuses Telnet
    options.
    """
    if not _build_has_iksdb(run_wermit):
        pytest.skip("build has no IKSDB support")

    length = 270
    proc, client, log_fh = _connect_iksd(
        iksd_path, tmp_path / "iksd.db", tmp_path / "iksd.log")
    client.settimeout(0.2)
    buf = b""
    prompts = 0
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                data = client.recv(4096)
            except socket.timeout:
                continue
            except ConnectionResetError:
                break
            if not data:
                break
            i = 0
            while i < len(data):
                # IAC WILL/DO: answer DONT/WONT.
                if (data[i] == 255 and i + 2 < len(data)
                        and data[i + 1] in (251, 253)):
                    reply = 254 if data[i + 1] == 251 else 252
                    client.sendall(bytes([255, reply, data[i + 2]]))
                    i += 3
                    continue
                buf += data[i:i + 1]
                i += 1
            if buf.endswith(b"Username: "):
                client.sendall(b"u" * length + b"\r")
                buf += b"<sent>"
                prompts += 1
            elif buf.endswith(b"Password: "):
                client.sendall(b"p" * length + b"\r")
                buf += b"<sent>"
                prompts += 1
        rc = proc.wait(timeout=10)
    finally:
        _close_iksd(proc, client, log_fh)

    assert rc >= 0, f"iksd died with signal {-rc}; output: {buf!r}"
    assert prompts == 6, f"expected 3 login attempts; output: {buf!r}"
    assert b"u" * length in buf, "username echo missing"


def test_join_csv_long_quoted_element(tmp_path, run_wermit):
    r"""Verify \fjoin() CSV mode quotes an element over 255 characters."""
    element = _distinct_chars(140) + "," + _distinct_chars(140)
    script = tmp_path / "join.ksc"
    script.write_text(
        "declare \\&a[1]\n"
        f"assign \\&a[1] {element}\n"
        "echo RESULT=[\\fjoin(&a[],CSV)]\n"
    )
    result = run_wermit(f"take {script}")
    assert f'RESULT=["{element}"]' in result.stdout, result.stdout


def test_cmnum_overflow_guard_rejects_huge_set_argument(run_wermit):
    """Verify SET rejects numeric arguments exceeding integer range."""
    result = run_wermit("set receive timeout 99999999999")
    assert (
        "?Magnitude of result too large for integer - 99999999999"
        in result.stdout
    ), result.stdout

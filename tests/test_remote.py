import pytest
from conftest import assert_ok


@pytest.fixture(params=["pseudoterminal", "raw-socket", "telnet"])
def loopback_transport(request):
    """Overrides conftest's single-value default so every test in
    this module also runs over a pty, TCP raw, and TCP telnet."""
    return request.param


def test_remote_pwd(tmp_path, wermit_loopback):
    """
    Test the 'remote pwd' command to print the working directory on the server.
    """
    result = wermit_loopback(tmp_path, client_commands="remote pwd")

    assert_ok(result)
    assert str(tmp_path) in result.stdout


def test_remote_cd_and_directory(tmp_path, wermit_loopback):
    """
    Test 'remote cd' to change directories and 'remote directory' to list the new directory on the server.
    """
    sub_dir = tmp_path / "sub_target"
    sub_dir.mkdir()
    (sub_dir / "target_remote_file.txt").touch()

    result = wermit_loopback(tmp_path,
                             client_commands="remote cd sub_target, remote directory")

    assert_ok(result)
    assert "target_remote_file.txt" in result.stdout


def test_remote_mkdir_rmdir(tmp_path, wermit_loopback):
    """
    Test 'remote mkdir' and 'remote rmdir' to create and remove folders on the server.
    """
    target_dir = tmp_path / "unique_remote_dir"
    assert not target_dir.exists()

    # 1. Create directory via remote command
    result_mkdir = wermit_loopback(tmp_path,
                                   client_commands="remote mkdir unique_remote_dir")
    assert_ok(result_mkdir)
    assert target_dir.exists()
    assert target_dir.is_dir()

    # 2. Delete directory via remote command
    result_rmdir = wermit_loopback(tmp_path,
                                   client_commands="remote rmdir unique_remote_dir")
    assert_ok(result_rmdir)
    assert not target_dir.exists()


def test_remote_copy_delete_rename(tmp_path, wermit_loopback):
    """
    Test 'remote copy', 'remote rename', and 'remote delete' commands on the server.
    """
    src_file = tmp_path / "origin.txt"
    src_file.write_text("Remote data copy content.")
    copied_file = tmp_path / "copy.txt"
    renamed_file = tmp_path / "renamed.txt"

    # 1. Perform remote copy
    result_copy = wermit_loopback(tmp_path,
                                  client_commands="remote copy origin.txt copy.txt")
    assert_ok(result_copy)
    assert copied_file.exists()
    assert copied_file.read_text() == "Remote data copy content."

    # 2. Perform remote rename
    result_rename = wermit_loopback(tmp_path,
                                    client_commands="remote rename copy.txt renamed.txt")
    assert_ok(result_rename)
    assert not copied_file.exists()
    assert renamed_file.exists()

    # 3. Perform remote delete
    result_delete = wermit_loopback(tmp_path,
                                    client_commands="remote delete renamed.txt")
    assert_ok(result_delete)
    assert not renamed_file.exists()


@pytest.mark.parametrize("filename_len", [6, 7, 8, 9, 10, 11, 12, 13, 14])
@pytest.mark.parametrize("content", ["", "1234567890"])
def test_remote_delete_boundary_lengths(
        tmp_path, wermit_loopback, filename_len, content):
    """
    Test "remote delete" with different filename lengths and file sizes
    to ensure we cover the boundary cases (packet lengths 92-98)
    without encountering hangs or corruption.
    """
    # Use non-repeating characters to avoid repeat-count compression.
    filename = "".join(chr(97 + i) for i in range(filename_len))
    target_file = tmp_path / filename
    target_file.write_text(content)

    result = wermit_loopback(
        tmp_path, client_commands=f"remote delete {filename}")
    assert_ok(result, f"Client failed for length {filename_len}")
    assert not target_file.exists()


@pytest.mark.parametrize("command_name", ["cd", "mkdir", "copy", "rename", "directory", "get"])
@pytest.mark.parametrize("is_enabled", [False, True])
def test_local_server_remote_commands_disabled_by_default(
        tmp_path, wermit_loopback, command_name, is_enabled):
    """
    Verify that by default, the remote system cannot control the local system
    using remote commands (CD, MKDIR, COPY, RENAME, DIRECTORY, GET) when the
    local system is in server mode (disabled in local mode by default since
    commit 9ee170a8593a6af6f4bf895eb0572065d59f83f1).

    Verify also that we can explicitly enable them using 'enable all'
    on the local system.
    """
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    server_dir = tmp_path / "server"
    server_dir.mkdir()

    # Pre-test setup
    if command_name == "copy":
        (client_dir / "source.txt").write_text("hello")
    elif command_name == "rename":
        (client_dir / "old.txt").write_text("hello")
    elif command_name == "get":
        (client_dir / "target.txt").write_text("hello from client")
    elif command_name == "directory":
        (client_dir / "placeholder.txt").write_text("placeholder")

    status_file = server_dir / \
        f"status_{command_name}_{'enabled' if is_enabled else 'disabled'}.txt"

    # Map command_name to the actual Kermit command sent by the server process
    server_cmd_map = {
        "cd": "remote cd ..",
        "mkdir": "remote mkdir new_dir",
        "copy": "remote copy source.txt dest.txt",
        "rename": "remote rename old.txt new.txt",
        "directory": "remote directory",
        "get": "get target.txt"
    }
    server_cmd = server_cmd_map[command_name]

    # Reverse client-server synchronization:
    # Because the server starts asynchronously before the client enters
    # server mode, they synchronize via a handshake. The server process
    # waits for the client to be ready using "input 5 READY". The client
    # sends "READY" followed by a carriage return (READY\13) right before
    # entering server mode. This prevents the server from sending commands
    # too early, but it is complex and can time out if the PTY stalls.
    server_cmds = "\n".join([
        "input 5 READY",
        server_cmd,
        f"if success !echo SUCCESS > {status_file}",
        f"if failure !echo FAILURE > {status_file}",
        "finish",
        "exit"
    ])

    client_setup_cmd = f"cd {client_dir}"
    if is_enabled:
        client_setup_cmd += ", enable all"

    client_cmd = f"{client_setup_cmd}, output READY\\13, server"
    result = wermit_loopback(server_dir, server_cmds, client_cmd)

    # If commands are enabled (success), the client exits server mode cleanly with code 0
    # after receiving the finish command. If commands are disabled (failure), the client still
    # shuts down cleanly via the finish command, but its final exit code is 8 because
    # it flags the failed/rejected remote command transaction.
    expected_returncode = 0 if is_enabled else 8
    assert result.returncode == expected_returncode, (
        f"Client exited with unexpected code {result.returncode} (expected {expected_returncode}). "
        f"stdout: {result.stdout}"
    )
    assert status_file.exists()
    expected_status = "SUCCESS" if is_enabled else "FAILURE"
    assert status_file.read_text().strip() == expected_status

    # Validate side effects on the client/server filesystems
    if command_name == "mkdir":
        assert (client_dir / "new_dir").exists() == is_enabled
    elif command_name == "copy":
        assert (client_dir / "dest.txt").exists() == is_enabled
    elif command_name == "rename":
        assert (client_dir / "new.txt").exists() == is_enabled
        if is_enabled:
            assert not (client_dir / "old.txt").exists()
        else:
            assert (client_dir / "old.txt").exists()
    elif command_name == "get":
        assert (server_dir / "target.txt").exists() == is_enabled


def _wrap(name, style):
    """Wrap name in the given outer quoting style with no internal
    escaping, for the "just add delimiters" case."""
    if style == "brace":
        return "{" + name + "}"
    if style == "doublequote":
        return '"' + name + '"'
    raise ValueError(style)


@pytest.mark.parametrize("style", ["none", "brace", "doublequote"])
def test_remote_delete_with_space(tmp_path, wermit_loopback, style):
    """
    REMOTE DELETE's filespec field is captured by cmtxt(),
    which reads to the end of the line as one blob rather than
    splitting on unquoted spaces the way cmfld()/cmifi() do. A space
    in the name needs no quoting here, and wrapping it in
    either delimiter style works. Contrast with REMOTE RENAME/REMOTE COPY below.
    """
    d = tmp_path / "d"
    d.mkdir()
    name = "file one.txt"
    (d / name).write_text("payload\n")

    arg = name if style == "none" else _wrap(name, style)
    result = wermit_loopback(d, "", f"remote delete {arg}")

    assert_ok(result)
    assert not (d / name).exists()


@pytest.mark.parametrize("style", ["none", "brace", "doublequote"])
def test_remote_directory_with_space(tmp_path, wermit_loopback, style):
    """
    REMOTE DIRECTORY (RDIR) shares REMOTE DELETE's cmtxt() field
    parser, so the same space-handling applies: no quoting needed,
    and either delimiter style works.
    """
    d = tmp_path / "d"
    d.mkdir()
    name = "file one.txt"
    (d / name).write_text("payload\n")

    arg = name if style == "none" else _wrap(name, style)
    result = wermit_loopback(d, "", f"remote directory {arg}")

    assert_ok(result)
    assert name in result.stdout


@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_remote_rename_with_space(tmp_path, wermit_loopback, style):
    """
    REMOTE RENAME's two filename arguments are each parsed with a
    separate cmfld() call (ckuus7.c), the same field parser GET uses
    elsewhere. Each resolved field is now stripped with brstrip()
    before use, the same as every other cmfld()/cmifi() caller in the
    tree, so a brace- or doublequote-wrapped name works correctly.
    """
    d = tmp_path / "d"
    d.mkdir()
    src = "file one.txt"
    dst = "file two.txt"
    (d / src).write_text("payload\n")

    result = wermit_loopback(
        d, "",
        f"remote rename {_wrap(src, style)} {_wrap(dst, style)}")

    assert_ok(result)
    assert not (d / src).exists()
    assert (d / dst).exists()


@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_remote_copy_with_space(tmp_path, wermit_loopback, style):
    """
    REMOTE COPY shares REMOTE RENAME's exact two-field cmfld()
    mechanism and setgen()/srv_copy() wire encoding, and got the same
    brstrip() fix.
    """
    d = tmp_path / "d"
    d.mkdir()
    src = "file one.txt"
    dst = "file two.txt"
    (d / src).write_text("payload\n")

    result = wermit_loopback(
        d, "",
        f"remote copy {_wrap(src, style)} {_wrap(dst, style)}")

    assert_ok(result)
    assert (d / src).exists()
    assert (d / dst).exists()


@pytest.mark.parametrize("with_space", [False, True], ids=["nospace", "space"])
@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_remote_rename_embedded_brace_name(
        tmp_path, wermit_loopback, style, with_space):
    """
    REMOTE RENAME shares REMOTE DELETE's family convention for an
    embedded balanced {brace} pair: leave it unescaped. Its field is
    parsed with cmfld() (not cmtxt()) but that field also runs
    unconditionally through xxstring(), so the same reasoning applies
    (doc/spaces.md's "The convention splits by command family");
    brstrip() (the fix from test_remote_rename_with_space above)
    already strips a genuine outer wrap before the name is used, no
    further escaping needed.
    """
    d = tmp_path / "d"
    d.mkdir()
    name = "file {one} two.txt" if with_space else "file{one}.txt"
    (d / name).write_text("payload\n")

    arg = _wrap(name, style)
    result = wermit_loopback(d, "", f"remote rename {arg} renamed.txt")

    assert_ok(result)
    assert not (d / name).exists()
    assert (d / "renamed.txt").exists()


@pytest.mark.parametrize("with_space", [False, True], ids=["nospace", "space"])
@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_remote_delete_embedded_brace_name(
        tmp_path, wermit_loopback, style, with_space):
    """
    REMOTE DELETE follows the GET/REMOTE family's convention for an
    embedded balanced {brace} pair: leave it unescaped (the opposite
    of local DIR/SEND/DELETE). This needed a fix. REMOTE DELETE's
    field cmtxt() is run through xxstring() before transmission,
    which doesn't touch a bare brace, but the resolved name's literal
    brace still had no backslash in front of it by the time it
    reached the far end, so the far end's wildcard matcher
    (iswild()/fgen()) misread it as pattern syntax. Fixed by
    re-escaping any brace left in the resolved name
    after stripping outer quotes.
    """
    d = tmp_path / "d"
    d.mkdir()
    name = "file {one} two.txt" if with_space else "file{one}.txt"
    (d / name).write_text("payload\n")

    arg = _wrap(name, style)
    result = wermit_loopback(d, "", f"remote delete {arg}")

    assert_ok(result)
    assert not (d / name).exists()


@pytest.mark.parametrize("with_space", [False, True], ids=["nospace", "space"])
@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_remote_directory_embedded_brace_name(
        tmp_path, wermit_loopback, style, with_space):
    """
    REMOTE DIRECTORY (RDIR) supports embedded brace names, leaving
    the brace pair unescaped.
    """
    d = tmp_path / "d"
    d.mkdir()
    name = "file {one} two.txt" if with_space else "file{one}.txt"
    (d / name).write_text("payload\n")

    arg = _wrap(name, style)
    result = wermit_loopback(d, "", f"remote directory {arg}")

    assert_ok(result)
    assert name in result.stdout


@pytest.mark.parametrize("with_space", [False, True], ids=["nospace", "space"])
@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_remote_delete_embedded_doublequote_name(
        tmp_path, wermit_loopback, style, with_space):
    """
    REMOTE DELETE handles an embedded, balanced pair of double quote
    characters correctly for either outer delimiter.
    The embedded
    quotes must be escaped (\\"), the same convention DIR/SEND use,
    and escaping survives xxstring() intact since it isn't a brace;
    with braces as the outer delimiter, the embedded quotes are left
    unescaped, since doublequotes don't affect brace tracking, again
    matching DIR/SEND.
    """
    d = tmp_path / "d"
    d.mkdir()
    name = 'file "one" two.txt' if with_space else 'file"one".txt'
    (d / name).write_text("payload\n")

    escaped = name.replace('"', '\\"') if style == "doublequote" else name
    arg = _wrap(escaped, style)
    result = wermit_loopback(d, "", f"remote delete {arg}")

    assert_ok(result)
    assert not (d / name).exists()


def test_remote_delete_numeric_content_embedded_brace(
        tmp_path, wermit_loopback):
    """
    REMOTE DELETE's family (GET/REMOTE DELETE/REMOTE RENAME/REMOTE
    COPY) convention, leaving an embedded balanced {brace} pair
    unescaped, has no numeric-content gap, unlike escaping it (see
    test_remote_delete_numeric_content_embedded_brace_escaped_fails
    below). "{123}" round-trips correctly here because no backslash
    is involved, so xxesc() is never asked to interpret it.
    """
    d = tmp_path / "d"
    d.mkdir()
    name = "file{123}.txt"
    (d / name).write_text("payload\n")
    (d / "fileone.txt").write_text("decoy\n")

    result = wermit_loopback(d, "", "remote delete file{123}.txt")

    assert_ok(result)
    assert not (d / name).exists()
    assert (d / "fileone.txt").exists()


@pytest.mark.xfail(
    strict=True,
    reason="xxesc() intentionally reads \\{123\\} as a numeric "
    "escape (character code 123), not literal text; this is exactly "
    "why the recommended convention for this family is to leave the "
    "pair unescaped, see the passing test right above")
def test_remote_delete_numeric_content_embedded_brace_escaped_fails(
        tmp_path, wermit_loopback):
    """
    Escaping a purely numeric bracketed segment (e.g. "{123}") does
    NOT work on any command whose field parser unconditionally runs
    xxstring() (REMOTE DELETE's cmtxt(), same as GET's cmfld()):
    "123" parses as a valid decimal number, so xxesc() converts the
    whole escaped sequence to the single character with that code
    instead of leaving the digits as literal text. This is inherent
    to \\{decimal}/\\{octal}/\\{hex} being an intentional escape
    syntax that shares delimiters with the literal-brace convention;
    there's no way to tell them apart from the escaped text alone.
    Contrast with test_brace_convention.py's
    test_local_delete_numeric_content_embedded_brace, where local
    DELETE's cmifi() only runs xxstring() when a variable reference is
    also present, so escaping this same content works fine there.
    """
    d = tmp_path / "d"
    d.mkdir()
    name = "file{123}.txt"
    (d / name).write_text("payload\n")

    result = wermit_loopback(d, "", r"remote delete file\{123\}.txt")

    assert_ok(result)
    assert not (d / name).exists()

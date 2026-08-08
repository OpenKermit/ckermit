"""Compatibility tests against C-Kermit 9.0.302.

Tests reuse wermit_loopback with server_binary_path set to
ckermit-old-9.0.302. Tests skip automatically if the binary is absent.
C-Kermit 9.0.302 does not support SSL/TLS or IPv6.
"""
from functools import partial

import pytest

from conftest import assert_ok, make_loopback_dirs
from test_transfer import (KERMIT_PACKET_LEN, run_transfer_helper,
                           _run_nul_replay_transfer)
from test_remote import _wrap

MB = 1024 * 1024


@pytest.fixture(params=["pseudoterminal", "raw-socket", "telnet"])
def loopback_transport(request):
    """Loopback transports supported by C-Kermit 9.0.302."""
    return request.param


@pytest.fixture
def old_loopback(wermit_loopback, ckermit_old_path):
    """Return a wermit_loopback fixture bound to C-Kermit 9.0.302.

    C-Kermit 9.0.302 lacks support for packet replay handling with
    unprefixed control characters.
    """
    return partial(wermit_loopback, server_binary_path=ckermit_old_path)


def _xfail_old_ckermit_unprefix_replay(request):
    """Mark test xfail(strict=False) for C-Kermit 9.0.302 unprefix flake."""
    request.node.add_marker(pytest.mark.xfail(
        reason="C-Kermit 9.0.302 packet replay unprefix flake",
        strict=False,
    ))


def _xfail_if_send_and_clear_unprefix(request, direction):
    """Mark send-direction tests xfail under clear_unprefix."""
    if direction == "send" and request.node.callspec.params.get(
            "wermit_loopback"):
        _xfail_old_ckermit_unprefix_replay(request)


# --- Core transfer parity ---------------------------------------------

@pytest.mark.parametrize("direction", ["send", "get"])
@pytest.mark.parametrize("size", [
    pytest.param(0, id="0B"),
    pytest.param(1024, id="1024B"),
    pytest.param(KERMIT_PACKET_LEN - 1, id="pktlen-1"),
    pytest.param(KERMIT_PACKET_LEN, id="pktlen"),
    pytest.param(KERMIT_PACKET_LEN + 1, id="pktlen+1"),
])
def test_transfer_binary(tmp_path, old_loopback, direction, size, request):
    """Binary transfer in both directions across packet boundaries."""
    _xfail_if_send_and_clear_unprefix(request, direction)
    run_transfer_helper(
        tmp_path, old_loopback, direction,
        file_type="binary", file_name="binary_file.dat",
        file_content=b"" if size == 0 else bytes(range(256)) * (
            size // 256 + 1), is_text=False)


@pytest.mark.parametrize("direction", ["send", "get"])
def test_transfer_text(tmp_path, old_loopback, direction, request):
    """Text transfer in both directions with CRLF conversion."""
    _xfail_if_send_and_clear_unprefix(request, direction)
    run_transfer_helper(
        tmp_path, old_loopback, direction,
        file_type="text", file_name="text_file.txt",
        file_content="Line 1: Hello.\nLine 2: Compat test.\n",
        is_text=True)


@pytest.mark.parametrize("direction", ["send", "get"])
def test_transfer_large(tmp_path, old_loopback, direction, request):
    """Binary transfer well beyond a single packet or window."""
    _xfail_if_send_and_clear_unprefix(request, direction)
    size = 3 * MB
    content = (bytes(range(256)) * (size // 256 + 1))[:size]
    run_transfer_helper(
        tmp_path, old_loopback, direction,
        file_type="binary", file_name="large_file.dat",
        file_content=content, is_text=False, timeout=60)


def test_transfer_recursive(tmp_path, old_loopback):
    """Recursive directory transfer against legacy server."""
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    (client_dir / "file1.txt").write_text("file1 content")
    subdir = client_dir / "nested_subdir"
    subdir.mkdir()
    (subdir / "file2.txt").write_text("file2 content")

    server_dir = tmp_path / "server"
    server_dir.mkdir()

    result = old_loopback(
        server_dir, "set file type binary, set delay 0",
        f"set file type binary, set delay 0, cd {client_dir}, "
        "send /recursive *")
    assert_ok(result)

    assert (server_dir / "file1.txt").read_text() == "file1 content"
    assert (server_dir / "nested_subdir" / "file2.txt").read_text() \
        == "file2 content"


# --- REMOTE command parity ---------------------------------------------

def test_remote_pwd(tmp_path, old_loopback):
    result = old_loopback(tmp_path, client_commands="remote pwd")
    assert_ok(result)
    assert str(tmp_path) in result.stdout


def test_remote_cd_and_directory(tmp_path, old_loopback):
    sub_dir = tmp_path / "sub_target"
    sub_dir.mkdir()
    (sub_dir / "target_remote_file.txt").touch()
    result = old_loopback(
        tmp_path,
        client_commands="remote cd sub_target, remote directory")
    assert_ok(result)
    assert "target_remote_file.txt" in result.stdout


def test_remote_mkdir_rmdir(tmp_path, old_loopback):
    target_dir = tmp_path / "unique_remote_dir"
    result_mkdir = old_loopback(
        tmp_path, client_commands="remote mkdir unique_remote_dir")
    assert_ok(result_mkdir)
    assert target_dir.is_dir()

    result_rmdir = old_loopback(
        tmp_path, client_commands="remote rmdir unique_remote_dir")
    assert_ok(result_rmdir)
    assert not target_dir.exists()


def test_remote_copy_delete_rename(tmp_path, old_loopback):
    src_file = tmp_path / "origin.txt"
    src_file.write_text("Remote data copy content.")
    copied_file = tmp_path / "copy.txt"
    renamed_file = tmp_path / "renamed.txt"

    assert_ok(old_loopback(
        tmp_path, client_commands="remote copy origin.txt copy.txt"))
    assert copied_file.read_text() == "Remote data copy content."

    assert_ok(old_loopback(
        tmp_path, client_commands="remote rename copy.txt renamed.txt"))
    assert not copied_file.exists()
    assert renamed_file.exists()

    assert_ok(old_loopback(
        tmp_path, client_commands="remote delete renamed.txt"))
    assert not renamed_file.exists()


@pytest.mark.parametrize("filename_len", [6, 7, 8, 9, 10, 11, 12, 13, 14])
@pytest.mark.parametrize("content", ["", "1234567890"])
def test_remote_delete_boundary_lengths(
        tmp_path, old_loopback, filename_len, content):
    """Delete files with lengths spanning short and extended headers."""
    filename = "".join(chr(97 + i) for i in range(filename_len))
    target_file = tmp_path / filename
    target_file.write_text(content)

    result = old_loopback(
        tmp_path, client_commands=f"remote delete {filename}")
    assert_ok(result, f"Client failed for length {filename_len}")
    assert not target_file.exists()


def test_transfer_unprefixed_nul_replay(tmp_path, old_loopback, request):
    """Binary transfer with embedded NUL bytes under out-of-order replay."""
    # _run_nul_replay_transfer forces set control unprefix all on server.
    _xfail_old_ckermit_unprefix_replay(request)
    _run_nul_replay_transfer(tmp_path, old_loopback)


# --- Known behavior differences from doc/changelog.md ------------------

def test_remote_status_unimplemented_on_old_server(tmp_path, old_loopback):
    """Confirm REMOTE STATUS returns error against legacy server."""
    result = old_loopback(tmp_path, client_commands="remote status")
    assert result.returncode != 0
    assert "Unimplemented REMOTE command" in result.stdout


def test_remote_cdup_against_old_server(tmp_path, old_loopback):
    """Confirm REMOTE CDUP works against legacy server."""
    sub_dir = tmp_path / "sub_target"
    sub_dir.mkdir()
    result = old_loopback(
        tmp_path,
        client_commands="remote cd sub_target, remote cdup, remote pwd")
    assert_ok(result)
    assert str(tmp_path) in result.stdout


@pytest.mark.parametrize("command_name", ["cd", "mkdir", "get"])
def test_cve_2025_68920_restriction_holds_against_old_peer(
        tmp_path, wermit_loopback, ckermit_old_path, command_name):
    """Confirm server mode rejects remote actions from legacy peer."""
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    server_dir = tmp_path / "server"
    server_dir.mkdir()

    if command_name == "get":
        (client_dir / "target.txt").write_text("hello from old ckermit")

    far_end_cmd_map = {
        "cd": "remote cd ..",
        "mkdir": "remote mkdir new_dir",
        "get": "get target.txt",
    }
    status_file = server_dir / f"status_{command_name}.txt"
    far_end_cmds = "\n".join([
        "input 5 READY",
        far_end_cmd_map[command_name],
        f"if success !echo SUCCESS > {status_file}",
        f"if failure !echo FAILURE > {status_file}",
        "finish",
        "exit",
    ])

    near_cmd = f"cd {client_dir}, output READY\\13, server"
    result = wermit_loopback(server_dir, far_end_cmds, near_cmd,
                             server_binary_path=ckermit_old_path)

    # Server mode rejects remote actions, causing peer exit code 8.
    assert result.returncode == 8, (
        f"Unexpected returncode {result.returncode}. "
        f"stdout: {result.stdout}")
    assert status_file.read_text().strip() == "FAILURE"
    if command_name == "mkdir":
        assert not (client_dir / "new_dir").exists()
    elif command_name == "get":
        assert not (server_dir / "target.txt").exists()


def test_file_collision_default_divergence(tmp_path, old_loopback):
    """Verify default file collision backup behavior on legacy peer."""
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    src = client_dir / "dup.txt"

    src.write_text("version 1")
    assert_ok(old_loopback(server_dir, client_commands=f"send {src}"))

    src.write_text("version 2, different length")
    assert_ok(old_loopback(server_dir, client_commands=f"send {src}"))

    assert (server_dir / "dup.txt").read_text() == \
        "version 2, different length"
    assert (server_dir / "dup.txt.~1~").read_text() == "version 1"


# --- Space and brace quoting in REMOTE commands -------------------------
#
# Client command parsing resolves field quoting before sending the
# filespec wire message. Legacy servers receive the unquoted filespec.

@pytest.mark.parametrize("style", ["none", "brace", "doublequote"])
def test_remote_delete_with_space(tmp_path, old_loopback, style):
    d = tmp_path / "d"
    d.mkdir()
    name = "file one.txt"
    (d / name).write_text("payload\n")

    arg = name if style == "none" else _wrap(name, style)
    result = old_loopback(d, "", f"remote delete {arg}")

    assert_ok(result)
    assert not (d / name).exists()


@pytest.mark.parametrize("style", ["none", "brace", "doublequote"])
def test_remote_directory_with_space(tmp_path, old_loopback, style):
    d = tmp_path / "d"
    d.mkdir()
    name = "file one.txt"
    (d / name).write_text("payload\n")

    arg = name if style == "none" else _wrap(name, style)
    result = old_loopback(d, "", f"remote directory {arg}")

    assert_ok(result)
    assert name in result.stdout


@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_remote_rename_with_space(tmp_path, old_loopback, style):
    d = tmp_path / "d"
    d.mkdir()
    src = "file one.txt"
    dst = "file two.txt"
    (d / src).write_text("payload\n")

    result = old_loopback(
        d, "", f"remote rename {_wrap(src, style)} {_wrap(dst, style)}")

    assert_ok(result)
    assert not (d / src).exists()
    assert (d / dst).exists()


@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_remote_copy_with_space(tmp_path, old_loopback, style):
    d = tmp_path / "d"
    d.mkdir()
    src = "file one.txt"
    dst = "file two.txt"
    (d / src).write_text("payload\n")

    result = old_loopback(
        d, "", f"remote copy {_wrap(src, style)} {_wrap(dst, style)}")

    assert_ok(result)
    assert (d / src).exists()
    assert (d / dst).exists()


@pytest.mark.parametrize("with_space", [False, True], ids=["nospace", "space"])
@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_remote_delete_embedded_brace_name(
        tmp_path, old_loopback, style, with_space):
    d = tmp_path / "d"
    d.mkdir()
    name = "file {one} two.txt" if with_space else "file{one}.txt"
    (d / name).write_text("payload\n")

    arg = _wrap(name, style)
    result = old_loopback(d, "", f"remote delete {arg}")

    assert_ok(result)
    assert not (d / name).exists()


@pytest.mark.parametrize("with_space", [False, True], ids=["nospace", "space"])
@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_remote_directory_embedded_brace_name(
        tmp_path, old_loopback, style, with_space):
    d = tmp_path / "d"
    d.mkdir()
    name = "file {one} two.txt" if with_space else "file{one}.txt"
    (d / name).write_text("payload\n")

    arg = _wrap(name, style)
    result = old_loopback(d, "", f"remote directory {arg}")

    assert_ok(result)
    assert name in result.stdout


@pytest.mark.parametrize("with_space", [False, True], ids=["nospace", "space"])
@pytest.mark.parametrize("style", ["brace", "doublequote"])
def test_remote_delete_embedded_doublequote_name(
        tmp_path, old_loopback, style, with_space):
    d = tmp_path / "d"
    d.mkdir()
    name = 'file "one" two.txt' if with_space else 'file"one".txt'
    (d / name).write_text("payload\n")

    escaped = name.replace('"', '\\"') if style == "doublequote" else name
    arg = _wrap(escaped, style)
    result = old_loopback(d, "", f"remote delete {arg}")

    assert_ok(result)
    assert not (d / name).exists()

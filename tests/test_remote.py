import pytest
from conftest import assert_ok


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

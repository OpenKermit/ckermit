import os
import pytest
from pathlib import Path
from conftest import resolve_transfer_paths


def expected_reject_returncode(direction):
    """Return the expected exit code when a transfer is rejected: 2 for send, 0 for get."""
    return 2 if direction == "send" else 0


def run_collision_test(
    tmp_path,
    wermit_loopback,
    direction,

    # e.g., "reject", "backup", "overwrite", "append" etc.  None will result in "default"
    collision_mode,

    existing_content,
    incoming_content,
    file_name="collision_test.txt",
    existing_mtime=None,
    incoming_mtime=None
):
    client_dir = tmp_path / (
        f"client_{direction}_{collision_mode or 'default'}_"
        f"{existing_mtime or 0}_{incoming_mtime or 0}"
    )
    client_dir.mkdir(parents=True, exist_ok=True)
    server_dir = tmp_path / (
        f"server_{direction}_{collision_mode or 'default'}_"
        f"{existing_mtime or 0}_{incoming_mtime or 0}"
    )
    server_dir.mkdir(parents=True, exist_ok=True)

    src_file, dest_file = resolve_transfer_paths(
        client_dir, server_dir, direction, file_name)

    # 1. Create the incoming file on the sender side
    src_file.write_text(incoming_content)
    if incoming_mtime is not None:
        os.utime(src_file, (incoming_mtime, incoming_mtime))

    # 2. Create the existing file on the receiver side
    dest_file.write_text(existing_content)
    if existing_mtime is not None:
        os.utime(dest_file, (existing_mtime, existing_mtime))

    # 3. Setup client and server commands.
    server_cmds = [
        "enable delete",
        "set file type text",
        "set delay 0"
    ]
    client_cmds = [
        "enable delete",
        "set file type text",
        "set delay 0"
    ]

    collision_cmd = (
        f"set file collision {collision_mode}" if collision_mode else ""
    )

    if collision_cmd:
        if direction == "send":
            server_cmds.append(collision_cmd)
        elif direction == "get":
            client_cmds.append(collision_cmd)

    if direction == "send":
        client_cmd = f"{', '.join(client_cmds)}, send {src_file}"
    else:
        client_cmd = f"{', '.join(client_cmds)}, cd {client_dir}, get {file_name}"
    result = wermit_loopback(server_dir, "\n".join(server_cmds), client_cmd)

    return result.returncode, dest_file.parent, dest_file


@pytest.mark.parametrize("direction", ["send", "get"])
@pytest.mark.parametrize("collision_mode", [None, "reject"])
def test_collision_default_and_reject(tmp_path, wermit_loopback, direction, collision_mode):
    """
    Validate that default collision behavior matches REJECT (preserves existing
    file), confirming the fix in commit 9ee170a8593a6af6f4bf895eb0572065d59f83f1,
    and that explicit SET FILE COLLISION REJECT behaves the same.
    """
    retcode, dest_dir, dest_file = run_collision_test(
        tmp_path,
        wermit_loopback,
        direction=direction,
        collision_mode=collision_mode,
        existing_content="EXISTING",
        incoming_content="INCOMING",
    )
    # Existing file is preserved and no extra files created
    assert dest_file.read_text() == "EXISTING"
    assert len([p for p in dest_dir.iterdir() if p != dest_file]) == 0
    # send: server rejects -> client returns 2; get: client rejects -> returns 0
    assert retcode == expected_reject_returncode(direction)


@pytest.mark.parametrize("direction", ["send", "get"])
def test_collision_overwrite(tmp_path, wermit_loopback, direction):
    """
    Validate that SET FILE COLLISION OVERWRITE replaces the existing file.
    """
    retcode, dest_dir, dest_file = run_collision_test(
        tmp_path,
        wermit_loopback,
        direction=direction,
        collision_mode="overwrite",
        existing_content="EXISTING OVERWRITE",
        incoming_content="INCOMING OVERWRITE"
    )
    assert dest_file.read_text() == "INCOMING OVERWRITE"
    other_files = [p.name for p in dest_dir.iterdir() if p != dest_file]
    assert len(other_files) == 0
    assert retcode == 0


@pytest.mark.parametrize("direction", ["send", "get"])
def test_collision_backup(tmp_path, wermit_loopback, direction):
    """
    Validate that SET FILE COLLISION BACKUP renames the existing file to a unique backup name
    (e.g., filename.~1~, filename.~2~), and writes the incoming file under the original name.
    """
    file_name = "collision_test.txt"
    retcode, dest_dir, dest_file = run_collision_test(
        tmp_path,
        wermit_loopback,
        direction=direction,
        collision_mode="backup",
        existing_content="EXISTING BACKUP",
        incoming_content="INCOMING BACKUP",
        file_name=file_name
    )
    assert dest_file.read_text() == "INCOMING BACKUP"
    assert retcode == 0

    # Check that a backup file with suffix .~1~ was created
    backup_file = dest_dir / f"{file_name}.~1~"
    assert backup_file.exists()
    assert backup_file.read_text() == "EXISTING BACKUP"


@pytest.mark.parametrize("direction", ["send", "get"])
def test_collision_backup_multiple(tmp_path, wermit_loopback, direction):
    """
    Validate that backup increments version numbers if previous backup
    files exist.
    """
    file_name = "collision_test.txt"

    # Pre-create a .~1~ backup in the destination directory so the
    # transfer's backup lands at .~2~ rather than .~1~.
    # The destination side is the server for "send" and the client for "get",
    # matching run_collision_test's directory naming convention.
    side = "server" if direction == "send" else "client"
    dest_dir = tmp_path / f"{side}_{direction}_backup_0_0"
    dest_dir.mkdir(parents=True, exist_ok=True)
    backup_file_1 = dest_dir / f"{file_name}.~1~"
    backup_file_1.write_text("OLD BACKUP 1")

    retcode, dest_dir, dest_file = run_collision_test(
        tmp_path, wermit_loopback,
        direction=direction,
        collision_mode="backup",
        existing_content="EXISTING BACKUP ACTIVE",
        incoming_content="INCOMING BACKUP NEW",
        file_name=file_name,
    )

    assert retcode == 0
    assert dest_file.read_text() == "INCOMING BACKUP NEW"
    # The existing active file should have been backed up to .~2~ because
    # .~1~ existed
    backup_file_2 = dest_dir / f"{file_name}.~2~"
    assert backup_file_2.exists()
    assert backup_file_2.read_text() == "EXISTING BACKUP ACTIVE"
    # .~1~ should remain untouched
    assert backup_file_1.read_text() == "OLD BACKUP 1"


@pytest.mark.parametrize("direction", ["send", "get"])
def test_collision_rename(tmp_path, wermit_loopback, direction):
    """
    Validate that SET FILE COLLISION RENAME preserves the existing file as-is,
    and writes the incoming file under a unique name (e.g., filename.~1~).
    """
    file_name = "collision_test.txt"
    retcode, dest_dir, dest_file = run_collision_test(
        tmp_path,
        wermit_loopback,
        direction=direction,
        collision_mode="rename",
        existing_content="EXISTING RENAME",
        incoming_content="INCOMING RENAME",
        file_name=file_name
    )
    # Existing file should remain untouched
    assert dest_file.read_text() == "EXISTING RENAME"
    assert retcode == 0

    # Incoming file should be saved as .~1~
    incoming_renamed = dest_dir / f"{file_name}.~1~"
    assert incoming_renamed.exists()
    assert incoming_renamed.read_text() == "INCOMING RENAME"


@pytest.mark.parametrize("direction", ["send", "get"])
def test_collision_append(tmp_path, wermit_loopback, direction):
    """
    Ensure that SET FILE COLLISION APPEND appends the incoming file content
    to the end of the existing file.
    """
    retcode, dest_dir, dest_file = run_collision_test(
        tmp_path,
        wermit_loopback,
        direction=direction,
        collision_mode="append",
        existing_content="LINE1\n",
        incoming_content="LINE2\n"
    )
    assert dest_file.read_text() == "LINE1\nLINE2\n"
    assert retcode == 0


@pytest.mark.parametrize("direction", ["send", "get"])
def test_collision_update_newer(tmp_path, wermit_loopback, direction):
    """
    Ensure that SET FILE COLLISION UPDATE overwrites the existing file
    if the incoming file is newer.
    """
    # T_existing = 1000000000 (Sun Sep  9 01:46:40 2001 UTC)
    # T_incoming = 1000010000 (incoming is 10000 seconds newer)
    retcode, dest_dir, dest_file = run_collision_test(
        tmp_path,
        wermit_loopback,
        direction=direction,
        collision_mode="update",
        existing_content="EXISTING OLDER",
        incoming_content="INCOMING NEWER",
        existing_mtime=1000000000,
        incoming_mtime=1000010000
    )
    assert dest_file.read_text() == "INCOMING NEWER"
    assert retcode == 0


@pytest.mark.parametrize("direction", ["send", "get"])
def test_collision_update_older_or_same(tmp_path, wermit_loopback, direction):
    """
    Validate that SET FILE COLLISION UPDATE rejects the incoming file
    if the incoming file is older or has the same timestamp.
    """
    # T_existing = 1000000000
    # T_incoming = 999990000 (incoming is 10000 seconds older)
    retcode, dest_dir, dest_file = run_collision_test(
        tmp_path,
        wermit_loopback,
        direction=direction,
        collision_mode="update",
        existing_content="EXISTING NEWER",
        incoming_content="INCOMING OLDER",
        existing_mtime=1000000000,
        incoming_mtime=999990000
    )
    assert dest_file.read_text() == "EXISTING NEWER"
    assert retcode == expected_reject_returncode(direction)

    # Test same timestamp
    retcode2, dest_dir2, dest_file2 = run_collision_test(
        tmp_path,
        wermit_loopback,
        direction=direction,
        collision_mode="update",
        existing_content="EXISTING SAME",
        incoming_content="INCOMING SAME",
        existing_mtime=1000000000,
        incoming_mtime=1000000000
    )
    assert dest_file2.read_text() == "EXISTING SAME"
    assert retcode2 == expected_reject_returncode(direction)

import os
import pytest
from pathlib import Path
import logging
from conftest import assert_ok, make_loopback_dirs, resolve_transfer_paths

logger = logging.getLogger(__name__)


def run_transfer_helper(tmp_path, wermit_loopback, direction,
                        file_type, file_name, file_content, is_text=False):
    """
    Execute loopback file transfer tests in both SEND and GET directions.

    This helper function sets up a temporary workspace directory tree
    containing "client" and "server" subdirectories, writes the specified
    content to the source file, and executes a file transfer between two
    kermit instances.

    Parameters:

    tmp_path (pathlib.Path):
        Pytest fixture providing a temporary directory for the test.
    wermit_loopback (callable):
        A fixture that initializes a wermit loopback
        session, returning an object with run_client and wait_for_server_exit
        methods.
    direction (str):
        The transfer direction. Valid settings:
            - "send": The client sends the file to the server.
            - "get": The client gets the file from the server.
    file_type (str):
        The C-Kermit file transfer type. Valid settings:
            - "binary": Transfers raw bytes without modifications.
            - "text": Transfers text, allowing record format conversion.
    file_name (str):
        The name of the file to create and transfer (e.g., "test.dat").
    file_content (bytes or str):
        The content to write to the source file before transferring.
    is_text (bool, optional):
        If True, writes the file and reads it as text (using unicode
        strings). If False (default), writes and reads raw bytes.
    """
    logger.info("run_transfer_helper: Starting transfer. "
                "Direction: %s, type: %s, file: %s",
                direction, file_type, file_name)

    client_dir, server_dir = make_loopback_dirs(tmp_path)
    src_file, dest_file = resolve_transfer_paths(
        client_dir, server_dir, direction, file_name)

    if is_text:
        src_file.write_text(file_content)
    else:
        src_file.write_bytes(file_content)

    file_size = len(file_content)
    logger.info("run_transfer_helper: Dirs and source file created. "
                "File size: %d bytes.", file_size)

    if direction == "send":
        client_cmd = f"set file type {file_type}, set delay 0, send {src_file}"
    else:
        client_cmd = (f"set file type {file_type}, set delay 0, "
                      f"cd {client_dir}, get {file_name}")
    logger.info("run_transfer_helper: Running loopback transfer in %s",
                server_dir)
    result = wermit_loopback(server_dir, f"set file type {file_type}, set delay 0",
                             client_cmd)

    logger.info("run_transfer_helper: Client exit code: %d", result.returncode)
    logger.debug("run_transfer_helper: Client stdout: %s", result.stdout)
    logger.debug("run_transfer_helper: Client stderr: %s", result.stderr)
    assert_ok(result)

    # Verify exact contents on the destination side
    logger.info("run_transfer_helper: Verifying destination file %s",
                dest_file)
    assert dest_file.exists()
    if is_text:
        content = dest_file.read_text()
    else:
        content = dest_file.read_bytes()
    assert content == file_content


@pytest.mark.parametrize("direction", ["send", "get"])
def test_kermit_transfer_binary(tmp_path, wermit_loopback, direction):
    """
    Test binary file transfer in both SEND and GET directions.
    Verifies that files are byte-identical.

    Passed tmp_path and the wermit_loopback _setup function, as well as the
    parameterized direction.
    """
    logger.info(
        "test_kermit_transfer_binary: Starting test (direction=%s)", direction)
    binary_content = bytes(range(256)) * 4  # 1024 bytes
    run_transfer_helper(
        tmp_path,
        wermit_loopback,
        direction,
        file_type="binary",
        file_name="binary_file.dat",
        file_content=binary_content,
        is_text=False
    )
    logger.info(
        "test_kermit_transfer_binary: Test passed (direction=%s)", direction)


@pytest.mark.parametrize("direction", ["send", "get"])
def test_kermit_transfer_text(tmp_path, wermit_loopback, direction):
    """
    Test text file transfer in both SEND and GET directions.
    """
    logger.info(
        "test_kermit_transfer_text: Starting test (direction=%s)", direction)
    text_content = "Line 1: Hello C-Kermit!\nLine 2: Testing text transfer.\n"
    run_transfer_helper(
        tmp_path,
        wermit_loopback,
        direction,
        file_type="text",
        file_name="text_file.txt",
        file_content=text_content,
        is_text=True
    )
    logger.info(
        "test_kermit_transfer_text: Test passed (direction=%s)", direction)


@pytest.mark.parametrize("direction", ["send", "get"])
def test_kermit_transfer_empty(tmp_path, wermit_loopback, direction):
    """
    Test empty (0-byte) file transfer in both SEND and GET directions.
    """
    logger.info(
        "test_kermit_transfer_empty: Starting test (direction=%s)", direction)
    run_transfer_helper(
        tmp_path,
        wermit_loopback,
        direction,
        file_type="binary",
        file_name="empty_file.dat",
        file_content=b"",
        is_text=False
    )
    logger.info(
        "test_kermit_transfer_empty: Test passed (direction=%s)", direction)


def test_kermit_transfer_recursive(tmp_path, wermit_loopback):
    """
    Test recursive file transfer (SEND /RECURSIVE).
    Verifies that nested files and subdirectories are correctly recreated
    on the server, but completely empty directories are skipped.
    GET /RECURSIVE is not tested as recursive GET is not supported by the
    Kermit protocol.
    """
    logger.info("test_kermit_transfer_recursive: Starting test")
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    (client_dir / "file1.txt").write_text("file1 content")

    subdir = client_dir / "nested_subdir"
    subdir.mkdir()
    (subdir / "file2.txt").write_text("file2 content")

    # Add an empty directory
    empty_subdir = client_dir / "empty_subdir"
    empty_subdir.mkdir()

    server_dir = tmp_path / "server"
    server_dir.mkdir()

    logger.info(
        "test_kermit_transfer_recursive: Running client to "
        "recursively send *")
    result = wermit_loopback(
        server_dir,
        "set file type binary, set delay 0",
        f"set file type binary, set delay 0, cd {client_dir}, send /recursive *")
    assert_ok(result)

    # Verify received files and contents
    logger.info(
        "test_kermit_transfer_recursive: Verifying directory structure "
        "and files...")
    dest_file1 = server_dir / "file1.txt"
    dest_file2 = server_dir / "nested_subdir" / "file2.txt"
    dest_empty_dir = server_dir / "empty_subdir"

    assert dest_file1.exists()
    assert dest_file1.read_text() == "file1 content"

    assert dest_file2.exists()
    assert dest_file2.read_text() == "file2 content"

    # Verify empty folder does NOT exist (Kermit protocol limitation)
    assert not dest_empty_dir.exists()

    # Verify that ONLY the expected files and folders exist on the destination
    expected_paths = {
        Path("file1.txt"),
        Path("nested_subdir"),
        Path("nested_subdir/file2.txt"),
    }
    actual_paths = {p.relative_to(server_dir) for p in server_dir.rglob("*")}
    assert actual_paths == expected_paths


@pytest.mark.parametrize("direction", ["send", "get"])
def test_kermit_transfer_preserves_mtime(tmp_path, wermit_loopback, direction):
    """
    Test that file transfer preserves the last modified timestamp.
    On platforms that track timestamps with sub-second precision, the test
    should check with second-level precision.
    """
    logger.info("test_kermit_transfer_preserves_mtime: Starting test "
                "(direction=%s)", direction)
    client_dir, server_dir = make_loopback_dirs(
        tmp_path, f"client_{direction}_mtime", f"server_{direction}_mtime")
    file_name = "mtime_test.txt"
    src_file, dest_file = resolve_transfer_paths(
        client_dir, server_dir, direction, file_name)

    src_file.write_text("Hello, this is a timestamp preservation test.")

    # Define a target timestamp with sub-second precision:
    # 1700000000.5678 (Sun Nov 14 22:13:20 2023 UTC)
    target_mtime = 1700000000.5678

    # Set both atime and mtime on the source file
    os.utime(src_file, (target_mtime, target_mtime))

    # Double check that the OS actually set it (at least to second-level
    # precision)
    src_stat = src_file.stat()
    set_mtime = src_stat.st_mtime
    logger.info("test_kermit_transfer_preserves_mtime: Source file mtime "
                "set to: %f", set_mtime)
    assert int(set_mtime) == 1700000000

    if direction == "send":
        logger.info("test_kermit_transfer_preserves_mtime: Running client "
                    "to SEND file %s", src_file)
        client_cmd = f"set file type binary, set delay 0, send {src_file}"
    else:
        logger.info("test_kermit_transfer_preserves_mtime: Running client "
                    "to GET file %s", file_name)
        client_cmd = (f"set file type binary, set delay 0, "
                      f"cd {client_dir}, get {file_name}")

    result = wermit_loopback(server_dir, "set file type binary, set delay 0",
                             client_cmd)

    assert_ok(result)

    logger.info(
        "test_kermit_transfer_preserves_mtime: Verifying dest file %s",
        dest_file)
    assert dest_file.exists()

    # Verify that the content matches
    assert dest_file.read_text() == "Hello, this is a timestamp preservation test."

    # Verify the last modified timestamp is preserved to the second.
    # Accepts both sub-second precision being preserved and it being
    # lost/rounded.
    dest_mtime = dest_file.stat().st_mtime
    logger.info("test_kermit_transfer_preserves_mtime: Destination file "
                "mtime is %f. Difference: %f",
                dest_mtime, abs(dest_mtime - set_mtime))
    assert abs(dest_mtime - set_mtime) <= 1.0

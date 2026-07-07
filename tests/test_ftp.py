import os
import threading
import pytest
from pyftpdlib.authorizers import DummyAuthorizer
from conftest import assert_ok
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer


@pytest.fixture
def ftp_server(tmp_path):
    # Setup dummy authorizer
    authorizer = DummyAuthorizer()
    # Add a user with full permissions
    # e: change directory, l: list, r: retrieve, a: append, d: delete,
    # f: rename, m: mkdir, w: write, M: chmod, T: utime
    authorizer.add_user("testuser", "testpass",
                        str(tmp_path), perm="elradfmwMT")

    # Subclass FTPHandler to silence log outputs during pytest runs
    class SilentFTPHandler(FTPHandler):
        def log(self, *args, **kwargs):
            pass

        def log_line(self, *args, **kwargs):
            pass

    # Set passive ports range to avoid port binding conflicts
    # Let pyftpdlib pick ports automatically
    server = FTPServer(("127.0.0.1", 0), SilentFTPHandler)
    server.handler.authorizer = authorizer

    ip, port = server.socket.getsockname()

    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    yield port, tmp_path

    server.close_all()
    thread.join(timeout=2)


def ftp_session(port, *commands):
    return ", ".join([
        f"ftp open 127.0.0.1 {port} /user:testuser /password:testpass",
        *commands,
        "ftp close", "exit"
    ])


def test_ftp_upload_download(ftp_server, run_wermit, tmp_path):
    port, server_dir = ftp_server

    # Create a local file to upload
    local_dir = tmp_path / "local"
    local_dir.mkdir()
    local_file = local_dir / "upload.dat"
    content = b"FTP binary data content " * 100
    local_file.write_bytes(content)

    # 1. Upload file using FTP put
    server_file_name = "server_file.dat"
    result = run_wermit(ftp_session(
        port, f"ftp put {local_file} {server_file_name}"))
    assert_ok(result, "Upload failed")

    # Verify the file was created on the server
    uploaded_file = server_dir / server_file_name
    assert uploaded_file.exists()
    assert uploaded_file.read_bytes() == content

    # 2. Download file using FTP get
    download_file = local_dir / "download.dat"
    result = run_wermit(ftp_session(
        port, f"ftp get {server_file_name} {download_file}"))
    assert_ok(result, "Download failed")

    # Verify the downloaded file matches
    assert download_file.exists()
    assert download_file.read_bytes() == content


def test_ftp_rename_delete(ftp_server, run_wermit, tmp_path):
    port, server_dir = ftp_server

    # Create a file on the server directly
    server_file = server_dir / "temp.dat"
    server_file.write_text("Hello FTP")

    # Rename and delete via FTP client commands
    result = run_wermit(ftp_session(
        port,
        "ftp rename temp.dat renamed_temp.dat",
        "ftp delete renamed_temp.dat",
    ))
    assert_ok(result, "FTP commands failed")

    # Verify the file is deleted on the server
    assert not (server_dir / "temp.dat").exists()
    assert not (server_dir / "renamed_temp.dat").exists()


def test_ftp_default_transfer_mode_manual(ftp_server, run_wermit, tmp_path):
    """
    Verify that by default, the FTP transfer mode is manual (binary)
    and does not automatically convert text files.

    This test verifies the fix in commit
    cdd2e257e8720e2d42a7a41ad504c76a95ef5ade.
    """
    port, server_dir = ftp_server

    # Create a local text file with CRLF line endings
    local_dir = tmp_path / "local"
    local_dir.mkdir(exist_ok=True)
    local_file = local_dir / "crlf_file.txt"
    content = b"Line 1\r\nLine 2\r\n"
    local_file.write_bytes(content)

    # 1. Upload using default transfer mode settings (manual/binary default)
    # The file should be transferred in binary mode (TYPE I).
    server_file_name_default = "default_crlf.txt"
    result = run_wermit(
        "set ftp debug on, " +
        ftp_session(port, f"ftp put {local_file} {server_file_name_default}")
    )
    assert_ok(result, "Default FTP upload failed")

    # Verify that TYPE I (Image/Binary) was sent, and TYPE A was NOT sent
    assert "---> TYPE I" in result.stdout or "---> TYPE L 8" in result.stdout
    assert "---> TYPE A" not in result.stdout

    # Verify the uploaded file exists on the server
    uploaded_file_default = server_dir / server_file_name_default
    assert uploaded_file_default.exists()

    # 2. Upload with transfer mode explicitly set to automatic before open
    # Auto transfer mode will detect the .txt extension and switch type to
    # ASCII (TYPE A).
    server_file_name_auto = "auto_lf.txt"
    result = run_wermit(
        "set transfer mode automatic, set ftp debug on, "
        + ftp_session(port, f"ftp put {local_file} {server_file_name_auto}")
    )
    assert_ok(result, "Auto FTP upload failed")

    # Verify that TYPE A (ASCII) was sent
    assert "---> TYPE A" in result.stdout

    # Verify the uploaded file exists on the server
    uploaded_file_auto = server_dir / server_file_name_auto
    assert uploaded_file_auto.exists()


def test_ftp_preserves_mtime(ftp_server, run_wermit, tmp_path):
    port, server_dir = ftp_server

    # 1. Create a file directly on the FTP server filesystem
    server_file_name = "server_file_mtime.dat"
    server_file = server_dir / server_file_name
    server_file.write_text("FTP timestamp preservation test.")

    # 2. Set modification time on the server file (with sub-second precision)
    target_mtime = 1700000000.5678
    os.utime(server_file, (target_mtime, target_mtime))

    set_mtime = server_file.stat().st_mtime
    assert int(set_mtime) == 1700000000

    # 3. Download the file using FTP get
    local_dir = tmp_path / "local"
    local_dir.mkdir(exist_ok=True)
    download_file = local_dir / "download.dat"

    result = run_wermit(
        "set ftp dates on, " +
        ftp_session(port, f"ftp get {server_file_name} {download_file}")
    )
    assert_ok(result, "Download failed")

    # Verify the downloaded file matches content and has the correct timestamp
    # (second-level precision)
    assert download_file.exists()
    assert download_file.read_text() == "FTP timestamp preservation test."

    download_mtime = download_file.stat().st_mtime
    assert abs(download_mtime - set_mtime) <= 1.0

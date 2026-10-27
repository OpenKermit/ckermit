import calendar
import errno
import os
import subprocess
import threading
import pytest
from pyftpdlib.authorizers import DummyAuthorizer
from conftest import assert_ok
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer


@pytest.fixture
def ftp_server(wermit_ftp_available, tmp_path):
    if not wermit_ftp_available:
        pytest.skip("wermit was built with -DNOFTP (no FTP client)")

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

    def run_server():
        try:
            server.serve_forever()
        except OSError as e:
            # On at least NetBSD, close_all() below
            # closes the kqueue fd from the main thread while this
            # thread may be blocked inside it, causing EBADF.
            # This is an expected shutdown race, not a real failure.
            if e.errno != errno.EBADF:
                raise

    thread = threading.Thread(target=run_server)
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
    #
    server_file_name = "server_file.dat"
    result = run_wermit(ftp_session(
        port, f"ftp put {local_file} {server_file_name}"), timeout=30)
    assert_ok(result, "Upload failed")

    # Verify the file was created on the server
    uploaded_file = server_dir / server_file_name
    assert uploaded_file.exists()
    assert uploaded_file.read_bytes() == content

    # 2. Download file using FTP get
    download_file = local_dir / "download.dat"
    result = run_wermit(ftp_session(
        port, f"ftp get {server_file_name} {download_file}"), timeout=30)
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
    #
    result = run_wermit(ftp_session(
        port,
        "ftp rename temp.dat renamed_temp.dat",
        "ftp delete renamed_temp.dat",
    ), timeout=30)
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
    #
    server_file_name_default = "default_crlf.txt"
    result = run_wermit(
        "set ftp debug on, " +
        ftp_session(port, f"ftp put {local_file} {server_file_name_default}"),
        timeout=30
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
        + ftp_session(port, f"ftp put {local_file} {server_file_name_auto}"),
        timeout=30
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
    #
    local_dir = tmp_path / "local"
    local_dir.mkdir(exist_ok=True)
    download_file = local_dir / "download.dat"

    result = run_wermit(
        "set ftp dates on, " +
        ftp_session(port, f"ftp get {server_file_name} {download_file}"),
        timeout=30
    )
    assert_ok(result, "Download failed")

    # Verify the downloaded file matches content and has the correct timestamp
    # (second-level precision)
    assert download_file.exists()
    assert download_file.read_text() == "FTP timestamp preservation test."

    download_mtime = download_file.stat().st_mtime
    assert abs(download_mtime - set_mtime) <= 1.0


def test_ftp_command_line_put_without_files(wermit_ftp_available,
                                            wermit_path, tmp_path):
    """Command-line FTP PUT with no existing file reports no files to put.

    Invoked as "ftp", the -p option names files to put.
    """
    if not wermit_ftp_available:
        pytest.skip("wermit was built with -DNOFTP (no FTP client)")
    ftp = tmp_path / "ftp"
    ftp.symlink_to(wermit_path)
    result = subprocess.run(
        [str(ftp), "-Y", "-p", str(tmp_path / "nonexistent")],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=30, start_new_session=True)
    output = result.stdout + result.stderr
    assert "No files to put" in output, output


def test_ftp_text_put_larger_than_buffer(ftp_server, run_wermit, tmp_path):
    """Verify a text-mode PUT larger than the 8 KiB send buffer.

    zzsend() flushes the buffer each time it fills.  A store past the
    buffer shows only under AddressSanitizer.
    """
    port, server_dir = ftp_server
    local_dir = tmp_path / "local"
    local_dir.mkdir()
    local_file = local_dir / "text.txt"
    lines = [f"line {i:05d} of the text file" for i in range(700)]
    local_file.write_text("\n".join(lines) + "\n")

    result = run_wermit(ftp_session(
        port, f"ftp put /text {local_file} text.txt"), timeout=30)
    assert_ok(result, "Upload failed")
    uploaded = (server_dir / "text.txt").read_text().splitlines()
    assert uploaded == lines


@pytest.mark.parametrize("name", ["ftphost", "[ftphost]"])
def test_ftp_open_network_directory_name(ftp_server, run_wermit,
                                         tmp_path, name):
    """Verify FTP OPEN of a name from the network directory.

    The name is replaced by the directory entry's address.  The lookup
    runs from the command line, outside any TAKE file.  A double free
    or a store before the TAKE line counters shows only under
    AddressSanitizer, except where the C library aborts.
    """
    port, server_dir = ftp_server
    (server_dir / "hello.txt").write_text("hello\n")
    netdir = tmp_path / "netdir.txt"
    netdir.write_text("ftphost tcp/ip 127.0.0.1\n")

    result = run_wermit(", ".join([
        f"set network directory {netdir}",
        f"ftp open {name} {port} /user:testuser /password:testpass",
        "if success echo OPEN-OK",
        "ftp close",
        "exit",
    ]), timeout=30)
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}")
    assert "OPEN-OK" in result.stdout, result.stdout


@pytest.mark.parametrize("size", [None, "18446744073709551619"],
                         ids=["true-size", "wrapping-size"])
def test_ftp_put_recover_size_reply(wermit_ftp_available, run_wermit,
                                    tmp_path, size):
    """Verify PUT /RECOVER with the server's SIZE reply.

    The remote file holds the first 3 bytes of the local file.  With the
    true size, Kermit appends the rest.  2**64 + 3 does not fit in a
    file offset.  Kermit must treat it as larger than the local file and
    send the whole file.  A wrapped value of 3 would append the rest to
    the wrong remote contents.
    """
    if not wermit_ftp_available:
        pytest.skip("wermit was built with -DNOFTP (no FTP client)")
    root = tmp_path / "root"
    root.mkdir()
    (root / "up.txt").write_bytes(b"hel" if size is None else b"old")
    (tmp_path / "up.txt").write_bytes(b"hello\n")
    authorizer = DummyAuthorizer()
    authorizer.add_user("testuser", "testpass", str(root),
                        perm="elradfmwMT")

    class Handler(FTPHandler):
        def log(self, *args, **kwargs):
            pass

        def log_line(self, *args, **kwargs):
            pass

        def ftp_SIZE(self, path):
            if size is None:
                return FTPHandler.ftp_SIZE(self, path)
            self.respond("213 " + size)

    server = FTPServer(("127.0.0.1", 0), Handler)
    server.handler.authorizer = authorizer
    port = server.socket.getsockname()[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_wermit(ftp_session(
            port, f"ftp put /recover {tmp_path}/up.txt up.txt",
            "echo PUT=\\v(status)"), timeout=30)
    finally:
        server.close_all()
        thread.join(timeout=2)
    assert "PUT=0" in result.stdout, result.stdout + result.stderr
    assert (root / "up.txt").read_bytes() == b"hello\n"


def test_ftp_server_time_offset_keeps_seconds(wermit_ftp_available,
                                              run_wermit, tmp_path,
                                              monkeypatch):
    """Verify SET FTP SERVER-TIME-OFFSET keeps the seconds of MDTM.

    The server reports 2024-01-02 03:04:55 UTC.  With an offset of +1
    hour the downloaded file gets 04:04:55 UTC.
    """
    if not wermit_ftp_available:
        pytest.skip("wermit was built with -DNOFTP (no FTP client)")
    monkeypatch.setenv("TZ", "UTC")
    root = tmp_path / "root"
    root.mkdir()
    (root / "m.txt").write_bytes(b"data\n")
    authorizer = DummyAuthorizer()
    authorizer.add_user("testuser", "testpass", str(root),
                        perm="elradfmwMT")

    class Handler(FTPHandler):
        def log(self, *args, **kwargs):
            pass

        def log_line(self, *args, **kwargs):
            pass

        def ftp_MDTM(self, path):
            self.respond("213 20240102030455")

    server = FTPServer(("127.0.0.1", 0), Handler)
    server.handler.authorizer = authorizer
    port = server.socket.getsockname()[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_wermit(
            "set ftp server-time-offset +1, set ftp dates on, " +
            ftp_session(port, f"ftp get m.txt {tmp_path}/m.txt",
                        "echo GET=\\v(status)"), timeout=30)
    finally:
        server.close_all()
        thread.join(timeout=2)
    assert "GET=0" in result.stdout, result.stdout + result.stderr
    want = calendar.timegm((2024, 1, 2, 4, 4, 55, 0, 0, 0))
    assert os.stat(tmp_path / "m.txt").st_mtime == want


def _limit_file_size():
    """Limit files to 64 KiB.  A larger write fails with EFBIG."""
    import resource
    import signal
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    resource.setrlimit(resource.RLIMIT_FSIZE, (65536, 65536))


@pytest.mark.parametrize("mode", ["binary", "ascii"])
def test_ftp_get_reports_local_write_failure(ftp_server, wermit_path,
                                             tmp_path, mode):
    """Verify FTP GET fails when the local file cannot be written.

    wermit runs with a file size limit of 64 KiB, and the remote file is
    larger.  GET must fail.  SET FILE INCOMPLETE AUTO then deletes the
    partial file of a text transfer.
    """
    port, server_dir = ftp_server
    (server_dir / "big.dat").write_bytes(b"0123456789abcdef\n" * 20000)
    local = tmp_path / "local"
    local.mkdir()
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-C",
         "set command more-prompting off, " + ftp_session(
             port, f"set ftp type {mode}",
             f"ftp get big.dat {local / 'big.dat'}",
             "echo STATUS=\\v(status)")],
        capture_output=True, text=True, timeout=60,
        preexec_fn=_limit_file_size)
    assert "STATUS=1" in result.stdout, result.stdout + result.stderr
    if mode == "ascii":
        assert not (local / "big.dat").exists()

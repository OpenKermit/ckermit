"""Large-file (CK_OFF_T) offset handling past the 4 GiB boundary.

CK_OFF_T is 64 bits on all supported platforms, including 32-bit
Linux builds with _LARGEFILE_SOURCE and _FILE_OFFSET_BITS=64.
These tests verify file size and offset handling past 2^31 and 2^32.
"""
import re
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import pytest

from conftest import assert_ok, make_loopback_dirs

FOUR_GIB = 1 << 32


def _holds_sparse_file(d):
    """Return True if directory d supports sparse files past 4 GiB."""
    probe = d / "sparse-probe"
    try:
        with open(probe, "wb") as f:
            f.seek(FOUR_GIB + 12345)
            f.write(b"\0")
        return probe.stat().st_blocks * 512 < FOUR_GIB
    except OSError:
        return False
    finally:
        probe.unlink(missing_ok=True)


@pytest.fixture
def sparse_dir(tmp_path):
    """Return an empty directory that supports sparse files past 4 GiB.

    NetBSD tmpfs rejects file sizes beyond filesystem capacity with
    ENOSPC, even for sparse files. When tmp_path is on such a
    filesystem, a directory under /var/tmp is used instead.

    The directory is removed on teardown.
    """
    for base in (tmp_path, Path("/var/tmp")):
        try:
            d = Path(tempfile.mkdtemp(prefix="sparse-", dir=base))
        except OSError:
            continue
        if _holds_sparse_file(d):
            break
        shutil.rmtree(d, ignore_errors=True)
    else:
        pytest.skip("no filesystem supports sparse files past 4 GiB")

    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def big_file_dir(sparse_dir):
    """Return directory with a small file and a sparse 4 GiB+ file."""
    d = sparse_dir

    small = d / "small.txt"
    small.write_bytes(b"hello world\n")

    big_size = FOUR_GIB + 12345
    big = d / "big.dat"
    with open(big, "wb") as f:
        f.seek(big_size - 1)
        f.write(b"\0")

    sizes = {small.name: small.stat().st_size, big.name: big_size}
    return d, sizes


def _parse_sizeofs(stdout):
    """Parse SHOW FEATURES sizeofs output into a dictionary.

    prtopt() word-wraps long lines without repeating the prefix.
    Read until the next blank line to capture continuation lines.
    """
    lines = stdout.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.strip().startswith(
            "sizeofs:")),
        None)
    if start is None:
        raise AssertionError(f"no 'sizeofs:' line found in:\n{stdout}")

    chunk = [lines[start].strip()[len("sizeofs:"):]]
    for line in lines[start + 1:]:
        if not line.strip():
            break
        chunk.append(line.strip())

    fields = {}
    for token in " ".join(chunk).split():
        name, sep, value = token.partition("=")
        if sep:
            fields[name] = int(value)
    return fields


def test_show_features_off_t_is_64_bit(run_wermit):
    """CK_OFF_T must be 8 bytes on all platforms.

    On both ILP32 and LP64 systems, long and pointer widths must match.
    """
    result = run_wermit("show features")
    assert_ok(result)
    sizeofs = _parse_sizeofs(result.stdout)

    assert sizeofs["CK_OFF_T"] == 8, (
        "CK_OFF_T should be 64 bits on every supported platform; "
        f"got sizeofs: {sizeofs}"
    )
    assert sizeofs["long"] == sizeofs["char*"], (
        "'long' and a pointer should always be the same width "
        f"(ILP32 or LP64); got sizeofs: {sizeofs}"
    )


def test_show_features_time_t(run_wermit):
    """Verify time_t width matches platform rules.

    Linux builds require an 8-byte time_t, except on 32-bit glibc.
    32-bit glibc defaults to a 32-bit time_t without -D_TIME_BITS=64.
    musl uses 64 bits on all targets.

    FreeBSD requires time_t to match the width of long.
    """
    result = run_wermit("show version, show features")
    assert_ok(result)

    built_for = next(
        (ln.split("Built for:", 1)[1].strip()
         for ln in result.stdout.splitlines() if "Built for:" in ln),
        None)
    assert built_for is not None, (
        f"no 'Built for:' line found in:\n{result.stdout}")

    sizeofs = _parse_sizeofs(result.stdout)

    glibc = re.search(r"\b__GLIBC__\b", result.stdout) is not None

    if "Linux" in built_for and glibc and sizeofs["long"] == 4:
        assert sizeofs["time_t"] in (4, 8), (
            f"unexpected time_t width; got sizeofs: {sizeofs}"
        )
    elif "Linux" in built_for:
        assert sizeofs["time_t"] == 8, (
            "time_t should be 64 bits on this Linux build; "
            f"got sizeofs: {sizeofs}"
        )
    elif "FreeBSD" in built_for:
        assert sizeofs["time_t"] == sizeofs["long"], (
            "on FreeBSD, time_t and long share the same __LP64__ "
            f"gating and should always match; got sizeofs: {sizeofs}"
        )
    else:
        pytest.skip(
            f"time_t width not asserted for this platform "
            f"({built_for})")


def test_fsize_reports_correct_size_past_4gib(run_wermit, big_file_dir):
    r"""\fsize() must report the true size of a file past 4 GiB."""
    d, sizes = big_file_dir
    big = d / "big.dat"

    result = run_wermit(f"echo SIZE=[\\fsize({big})]")
    assert_ok(result)
    assert f"SIZE=[{sizes['big.dat']}]" in result.stdout, result.stdout


def test_dir_reports_correct_size_past_4gib(run_wermit, big_file_dir):
    """DIR must show the correct size for files past 4 GiB."""
    d, sizes = big_file_dir

    result = run_wermit(f"dir {d}")
    assert_ok(result)

    for name, size in sizes.items():
        # Extract the size digits immediately preceding the timestamp.
        # Permissions and size may not have intervening whitespace.
        line = next(
            (ln for ln in result.stdout.splitlines() if name in ln), None)
        assert line is not None, (
            f"no DIR listing line for {name} in:\n{result.stdout}")
        m = re.search(
            r"(\d+)\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", line)
        assert m is not None, f"no size field found in line:\n{line}"
        assert int(m.group(1)) == size, (
            f"DIR reported size {m.group(1)} for {name}, expected {size}\n"
            f"line: {line}"
        )


def test_dir_summary_total_past_4gib(run_wermit, big_file_dir):
    """DIR /SUMMARY must report the correct sum when the total
    exceeds 4 GiB.
    """
    d, sizes = big_file_dir
    total = sum(sizes.values())
    assert total > FOUR_GIB, "test setup should exceed 4 GiB total"

    result = run_wermit(f"dir /summary {d}")
    assert_ok(result)

    m = re.search(r"(\d+)\s+bytes?\b", result.stdout)
    assert m is not None, (
        f"no '<N> byte(s)' total found in:\n{result.stdout}")
    assert int(m.group(1)) == total, (
        f"DIR /SUMMARY reported {m.group(1)} bytes, expected {total}\n"
        f"output: {result.stdout}"
    )


def test_reget_resumes_past_4gib(sparse_dir, wermit_loopback):
    r"""REGET must resume a partial file transfer past 4 GiB.

    The receiver reports the existing length in the ACK attribute
    packet. The sender seeks to that offset before transmitting the
    remaining bytes.
    """
    resume_at = FOUR_GIB + 12345
    marker = b"123456789"
    name = "big.dat"

    client_dir, server_dir = make_loopback_dirs(sparse_dir)

    source = server_dir / name
    with open(source, "wb") as f:
        f.seek(resume_at)
        f.write(marker)
    source_size = resume_at + len(marker)

    partial = client_dir / name
    with open(partial, "wb") as f:
        f.seek(resume_at)
        f.write(marker[:1])            # First marker byte matches source.

    client_cmd = f"set file type binary, cd {client_dir}, reget {name}"
    result = wermit_loopback(
        server_dir, "set file type binary", client_cmd, timeout=30)
    assert_ok(result)

    assert partial.stat().st_size == source_size, (
        f"expected {source_size}, got {partial.stat().st_size}\n"
        f"output: {result.stdout}"
    )
    with open(partial, "rb") as f:
        f.seek(resume_at)
        assert f.read(len(marker)) == marker, result.stdout


def test_fsexpression_arithmetic_past_4gib(run_wermit):
    r"""\fsexpression() arithmetic must not truncate past 4 GiB.

    Verify addition and subtraction with values past 2^32 return
    the exact 64-bit integer result.
    """
    a, b = FOUR_GIB - 10, 20
    result = run_wermit(f"echo SUM=[\\fsexpression(+ {a} {b})]")
    assert_ok(result)
    assert f"SUM=[{a + b}]" in result.stdout, result.stdout

    c, d = FOUR_GIB + 1000, 500
    result = run_wermit(f"echo DIFF=[\\fsexpression(- {c} {d})]")
    assert_ok(result)
    assert f"DIFF=[{c - d}]" in result.stdout, result.stdout


def test_fsexpression_arithmetic_past_2_53(run_wermit):
    r"""\fsexpression() arithmetic must be exact past 2^53.

    Verify addition, subtraction, and exact division with values past
    the 53-bit double precision limit return exact integer results.
    """
    for a, b in [
        (9007199254740994, 1),
        (9007199254740995, 2),
        (9007199254740996, 3),
    ]:
        result = run_wermit(f"echo R=[\\fsexpression(- {a} {b})]")
        assert_ok(result)
        assert "R=[9007199254740993]" in result.stdout, result.stdout

    result = run_wermit("echo R=[\\fsexpression(- 9007199254740993 1)]")
    assert_ok(result)
    assert "R=[9007199254740992]" in result.stdout, result.stdout

    for a, b, expected in [
        (9007199254740992, 3, 9007199254740995),
        (9007199254740991, 2, 9007199254740993),
    ]:
        result = run_wermit(f"echo R=[\\fsexpression(+ {a} {b})]")
        assert_ok(result)
        assert f"R=[{expected}]" in result.stdout, result.stdout

    # An exact division past 2^53 must produce an integer result.
    result = run_wermit(
        "echo R=[\\fsexpression(/ 18014398509481986 2)]"
    )
    assert_ok(result)
    assert "R=[9007199254740993]" in result.stdout, result.stdout

    # An inexact division must produce a floating-point result.
    result = run_wermit("echo R=[\\fsexpression(/ 7 2)]")
    assert_ok(result)
    assert "R=[3.5]" in result.stdout, result.stdout


@pytest.mark.parametrize("size", [3 * 2**30 + 7, FOUR_GIB + 12345])
def test_file_count_bytes_past_2gib(sparse_dir, run_wermit, size):
    r"""FILE COUNT /BYTES must report sizes past 2 GiB exactly.

    Verify both the listing and \v(f_count).
    """
    big = sparse_dir / "big.dat"
    with open(big, "wb") as f:
        f.seek(size - 1)
        f.write(b"\0")

    result = run_wermit(
        f"file open /read \\%c {big}, "
        "file count /bytes /list \\%c, "
        "echo C=[\\v(f_count)], "
        "file close \\%c"
    )
    assert_ok(result)
    assert f" {size} bytes" in result.stdout, result.stdout
    assert f"C=[{size}]" in result.stdout, result.stdout


def test_fsexpression_rounding_past_2_53(run_wermit):
    r"""\fsexpression() rounding and selection must be exact past 2^53.

    A whole-number operand of CEILING, FLOOR, TRUNCATE or ROUND is
    returned unchanged. ABS, MAX and MIN also return exact results.
    """
    for expr, expected in [
        ("ceiling 9007199254740993", "9007199254740993"),
        ("floor -9007199254740993", "-9007199254740993"),
        ("truncate 9007199254740993", "9007199254740993"),
        ("round 9007199254740993", "9007199254740993"),
        ("round 9007199254740993 2", "9007199254740993"),
        ("ceiling 9223372036854775807", "9223372036854775807"),
        ("abs -9007199254740993", "9007199254740993"),
        ("max 9007199254740992 9007199254740993", "9007199254740993"),
        ("min 9007199254740993 9007199254740992", "9007199254740992"),
        # Fractional operands keep floating-point behavior.
        ("ceiling 2.5", "3"),
        ("floor -2.5", "-3"),
        ("truncate -2.5", "-2"),
        ("round 7 2", "7.00"),
        ("round 2.567 2", "2.57"),
    ]:
        result = run_wermit(f"echo R=[\\fsexpression({expr})]")
        assert_ok(result)
        assert f"R=[{expected}]" in result.stdout, (expr, result.stdout)


def _capture_http_headers(server_sock):
    """Accept one connection and return its request headers as text.

    The connection is closed without reading the request body.
    """
    server_sock.settimeout(15)
    conn, _ = server_sock.accept()
    try:
        conn.settimeout(10)
        request = b""
        while b"\r\n\r\n" not in request:
            chunk = conn.recv(4096)
            if not chunk:
                break
            request += chunk
    finally:
        conn.close()
    return request.split(b"\r\n\r\n", 1)[0].decode("latin-1")


@pytest.mark.parametrize("method", ["put", "post"])
@pytest.mark.parametrize("size", [3 * 2**30 + 7, FOUR_GIB + 12345])
def test_http_upload_content_length_past_2gib(
    sparse_dir, spawn_wermit, wermit_http_available, get_free_port,
    method, size,
):
    """HTTP PUT and POST must send the exact Content-length past 2 GiB."""
    if not wermit_http_available:
        pytest.skip("wermit built with NOHTTP")

    big = sparse_dir / "big.dat"
    with open(big, "wb") as f:
        f.seek(size - 1)
        f.write(b"\0")

    port = get_free_port()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", port))
    server_sock.listen(1)
    try:
        proc = spawn_wermit([
            "-H", "-Y", "-C",
            "set command more-prompting off, "
            f"http open 127.0.0.1 {port}, "
            f"http {method} {big} /big.dat, "
            "exit",
        ], cwd=str(sparse_dir))
        headers = _capture_http_headers(server_sock)
    finally:
        server_sock.close()
    proc.kill()
    proc.wait(timeout=10)

    assert headers.startswith(f"{method.upper()} /big.dat "), headers
    assert f"\r\nContent-length: {size}\r\n" in headers + "\r\n", headers


@pytest.mark.parametrize("size", [3 * 2**30, FOUR_GIB + 12345])
def test_ftp_command_line_put_file_past_2gib(sparse_dir, wermit_path, size):
    """Command-line FTP PUT must accept a file of 2 GiB or more.

    Invoked as "ftp" with no host, wermit parses the PUT file list
    and then starts without connecting.
    """
    big = sparse_dir / "big.dat"
    with open(big, "wb") as f:
        f.seek(size - 1)
        f.write(b"\0")
    ftp = sparse_dir / "ftp"
    ftp.symlink_to(wermit_path)

    result = subprocess.run(
        [str(ftp), "-Y", "-p", str(big)],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=30, start_new_session=True)
    output = result.stdout + result.stderr
    assert "No files to" not in output, output
    assert "C-Kermit" in output, output


def test_remote_delete_files_past_2gib(sparse_dir, wermit_loopback):
    """REMOTE DELETE must delete files of 2 GiB or more and count them.

    The server lists each file it deletes and the total bytes freed.
    """
    client_dir, server_dir = make_loopback_dirs(sparse_dir)
    sizes = {"big3.dat": 3 * 2**30, "big4.dat": FOUR_GIB + 12345}
    for name, size in sizes.items():
        with open(server_dir / name, "wb") as f:
            f.seek(size - 1)
            f.write(b"\0")

    result = wermit_loopback(
        server_dir, "", f"cd {client_dir}, remote delete big*.dat",
        timeout=30)
    assert_ok(result)

    for name in sizes:
        assert not (server_dir / name).exists(), result.stdout
    assert f"{sum(sizes.values())} bytes freed" in result.stdout, (
        result.stdout)


def test_delete_summary_bytes_past_2gib(sparse_dir, run_wermit):
    """DELETE /SUMMARY must total file sizes past 2 GiB exactly."""
    sizes = {"big3.dat": 3 * 2**30, "big4.dat": FOUR_GIB + 12345}
    for name, size in sizes.items():
        with open(sparse_dir / name, "wb") as f:
            f.seek(size - 1)
            f.write(b"\0")
    result = run_wermit(f"delete /summary {sparse_dir}/big*.dat")
    assert_ok(result)
    for name in sizes:
        assert not (sparse_dir / name).exists(), result.stdout
    assert f"2 files deleted, {sum(sizes.values())} bytes freed" in (
        result.stdout), result.stdout


def test_wait_file_deletion_size_2_32_minus_1(sparse_dir, run_wermit):
    """WAIT FILE DELETION must not take a 2^32-1 byte file as deleted.

    In 32 bits that size is -1, the value for a file that does not
    exist.
    """
    big = sparse_dir / "big.dat"
    with open(big, "wb") as f:
        f.seek(FOUR_GIB - 2)
        f.write(b"\0")
    result = run_wermit(
        f"wait 1 file deletion {big}, echo STATUS=[\\v(status)]")
    assert "STATUS=[1]" in result.stdout, result.stdout
    assert big.exists()


@pytest.mark.parametrize("size", [3 * 2**30, FOUR_GIB + 12345])
def test_send_option_accepts_file_past_2gib(sparse_dir, wermit_path, size):
    """The -s command-line option must accept a file of 2 GiB or more.

    With no connection, wermit then fails to open the terminal; it
    must not report the file itself as unusable.
    """
    big = sparse_dir / "big.dat"
    with open(big, "wb") as f:
        f.seek(size - 1)
        f.write(b"\0")
    result = subprocess.run(
        [wermit_path, "-Y", "-s", str(big)],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=30, start_new_session=True)
    output = result.stdout + result.stderr
    assert "kermit -s" not in output, output

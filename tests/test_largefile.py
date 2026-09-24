"""Large-file (CK_OFF_T) offset handling past the 4 GiB boundary.

CK_OFF_T is 64 bits on all supported platforms, including 32-bit
Linux builds with _LARGEFILE_SOURCE and _FILE_OFFSET_BITS=64.
These tests verify file size and offset handling past 2^31 and 2^32.
"""
import re

import pytest

from conftest import assert_ok, make_loopback_dirs

FOUR_GIB = 1 << 32


@pytest.fixture
def big_file_dir(tmp_path):
    """Return directory with a small file and a sparse 4 GiB+ file."""
    d = tmp_path / "bigdir"
    d.mkdir()

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

    Linux builds require an 8-byte time_t. FreeBSD requires time_t
    to match the width of long.
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

    if "Linux" in built_for:
        assert sizeofs["time_t"] == 8, (
            "time_t should be 64 bits on every Linux build; "
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


def test_reget_resumes_past_4gib(tmp_path, wermit_loopback):
    r"""REGET must resume a partial file transfer past 4 GiB.

    The receiver reports the existing length in the ACK attribute
    packet. The sender seeks to that offset before transmitting the
    remaining bytes.
    """
    resume_at = FOUR_GIB + 12345
    marker = b"123456789"
    name = "big.dat"

    client_dir, server_dir = make_loopback_dirs(tmp_path)

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

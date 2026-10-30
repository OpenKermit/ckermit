"""
Tests for the IKSD session database (dbinit()/getslot()/initslot() in
ckuusx.c): the on-disk record format, specifically that db_SADDR and
db_CADDR are stored as address text (supporting both IPv4 and IPv6)
behind a version-tagged file header, and that an old-format database
(no header, 32-bit hex addresses) is left unchanged.  db_checkformat()
disables the database for such a file.

These tests invoke wermit directly as an "iksd": argv[0] must be
"iksd" for it to enter server mode, and its network connection is
expected to already be an accepted socket on file descriptors 0/1,
exactly as inetd/xinetd would set it up. dbinit()/getslot()/
initslot() all run immediately after the connection is recognized,
before any login or Telnet negotiation, so a bare TCP connection is
enough; no login is needed.
"""
import os
import socket
import struct
import subprocess
import time

import pytest

from conftest import assert_ok, expected_timeout, scaled

RECL = 4096
HDRL = 16
MAGIC = b"KIKSDB02"

SADDR_OFF, SADDR_LEN = 32, 64
CADDR_OFF, CADDR_LEN = 96, 64
USER_OFF = 1024

# Pre-version-2 record layout (32-bit hex addresses, no file header),
# for building a fixture "old" database.
OLD_SADDR_OFF = 32
OLD_CADDR_OFF = 48
OLD_START_OFF = 65
OLD_LASTU_OFF = 83
OLD_ULEN_OFF = 100
OLD_DLEN_OFF = 104
OLD_ILEN_OFF = 108
OLD_USER_OFF = 1024
OLD_DIR_OFF = 2048
OLD_INFO_OFF = 3072


def _build_has_iksdb(run_wermit):
    result = run_wermit(["--help"], timeout=10)
    assert result.returncode == 0 and result.stdout, (
        f"wermit --help failed: {result!r}")
    return "--dbfile" in result.stdout


def _build_has_address_family(run_wermit):
    result = run_wermit("show tcp")
    assert_ok(result, "SHOW TCP failed")
    return "address-family:" in result.stdout


@pytest.fixture
def iksd_path(tmp_path, wermit_path):
    link = tmp_path / "iksd"
    os.symlink(wermit_path, str(link))
    return str(link)


def _connect_iksd(iksd_path, dbfile, log_path,
                  family=socket.AF_INET, bindaddr="127.0.0.1",
                  extra_args=(), cwd=None, env=None):
    """
    Starts iksd_path as an IKSD with stdin/stdout wired to a freshly
    accepted loopback socket, as inetd would, using the database at
    dbfile. Returns (proc, client_socket, log_file_handle); the
    caller must close all three (see _close_iksd).  extra_args go
    before --dbfile, and cwd is the working directory of the IKSD.
    env is the environment of the IKSD, or None for this process's.
    """
    srv = socket.socket(family, socket.SOCK_STREAM)
    srv.bind((bindaddr, 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    client = socket.create_connection((bindaddr, port), timeout=scaled(5))
    conn, _ = srv.accept()
    srv.close()

    log_fh = open(log_path, "wb")
    proc = subprocess.Popen(
        [iksd_path, "-H", *extra_args, "--dbfile=" + str(dbfile)],
        stdin=conn.fileno(), stdout=conn.fileno(), stderr=log_fh,
        close_fds=True, cwd=cwd, env=env,
    )
    conn.close()                        # child has its own dup now
    return proc, client, log_fh


def _close_iksd(proc, client, log_fh):
    client.close()
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=expected_timeout(3))
        except Exception:
            proc.kill()
    log_fh.close()


def _wait_for_file(path, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return
        time.sleep(0.05)


def _field(data, off, length):
    return data[off:off + length].decode("ascii", "replace").rstrip(" ")


def test_new_database_has_v2_header_and_text_addresses(
        run_wermit, iksd_path, tmp_path):
    if not _build_has_iksdb(run_wermit):
        pytest.skip("build has no IKSDB support")

    dbfile = tmp_path / "iksd.db"
    proc, client, log_fh = _connect_iksd(
        iksd_path, dbfile, tmp_path / "iksd.log")
    try:
        _wait_for_file(dbfile)
        time.sleep(0.3)                 # let initslot() finish writing
        data = dbfile.read_bytes()
        assert data[:8] == MAGIC
        assert len(data) >= HDRL + RECL
        rec = data[HDRL:HDRL + RECL]
        assert _field(rec, SADDR_OFF, SADDR_LEN) == "127.0.0.1"
        assert _field(rec, CADDR_OFF, CADDR_LEN) == "127.0.0.1"
    finally:
        _close_iksd(proc, client, log_fh)


def test_new_database_ipv6_addresses(run_wermit, iksd_path, tmp_path):
    if not _build_has_iksdb(run_wermit):
        pytest.skip("build has no IKSDB support")
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    try:
        probe = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        probe.bind(("::1", 0))
        probe.close()
    except OSError:
        pytest.skip("no IPv6 loopback available in this environment")

    dbfile = tmp_path / "iksd6.db"
    proc, client, log_fh = _connect_iksd(
        iksd_path, dbfile, tmp_path / "iksd6.log",
        family=socket.AF_INET6, bindaddr="::1")
    try:
        _wait_for_file(dbfile)
        time.sleep(0.3)
        data = dbfile.read_bytes()
        assert data[:8] == MAGIC
        rec = data[HDRL:HDRL + RECL]
        assert _field(rec, SADDR_OFF, SADDR_LEN) == "::1"
        assert _field(rec, CADDR_OFF, CADDR_LEN) == "::1"
    finally:
        _close_iksd(proc, client, log_fh)


def _make_old_record(flags=0, pid=0, saddr_ip=0, caddr_ip=0,
                      start="", lastu="", user="", dirn="", info=""):
    rec = bytearray(b" " * RECL)

    def put(off, s):
        b = s.encode()
        rec[off:off + len(b)] = b

    put(0, "%04x" % flags)
    put(16, "%016x" % pid)
    put(OLD_SADDR_OFF, "%016x" % saddr_ip)
    put(OLD_CADDR_OFF, "%016x" % caddr_ip)
    put(OLD_START_OFF, start)
    put(OLD_LASTU_OFF, lastu)
    put(OLD_ULEN_OFF, "%04x" % len(user))
    put(OLD_DLEN_OFF, "%04x" % len(dirn))
    put(OLD_ILEN_OFF, "%04x" % len(info))
    put(OLD_USER_OFF, user)
    put(OLD_DIR_OFF, dirn)
    put(OLD_INFO_OFF, info)
    assert len(rec) == RECL
    return bytes(rec)


def test_old_format_database_is_left_alone(run_wermit, iksd_path, tmp_path):
    """
    An old-format (pre-IPv6, no header) database is not understood
    and not converted; db_checkformat() must leave it byte-for-byte
    untouched and disable the database for this session rather than
    guess at its layout. The connection itself must still work fine
    without a database.
    """
    if not _build_has_iksdb(run_wermit):
        pytest.skip("build has no IKSDB support")

    dbfile = tmp_path / "old.db"
    mypid = os.getpid()
    saddr_ip = struct.unpack("!I", socket.inet_aton("10.0.0.5"))[0]
    caddr_ip = struct.unpack("!I", socket.inet_aton("203.0.113.9"))[0]
    before = _make_old_record(
        flags=1, pid=mypid, saddr_ip=saddr_ip, caddr_ip=caddr_ip,
        start="20260101 12:00:00", lastu="20260101 12:05:00",
        user="alice", dirn="/home/alice", info="SEND")
    dbfile.write_bytes(before)
    assert dbfile.stat().st_size == RECL
    assert before[:8] != MAGIC

    proc, client, log_fh = _connect_iksd(
        iksd_path, dbfile, tmp_path / "old.log")
    try:
        time.sleep(0.5)
        assert proc.poll() is None, "iksd exited/crashed on an old-format db"
        after = dbfile.read_bytes()
        assert after == before, "old-format database was modified"
        # No leftover conversion temp file.
        assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
            ["iksd", "old.db", "old.log"])
    finally:
        _close_iksd(proc, client, log_fh)


def test_already_current_database_not_reconverted(
        run_wermit, iksd_path, tmp_path):
    if not _build_has_iksdb(run_wermit):
        pytest.skip("build has no IKSDB support")

    dbfile = tmp_path / "v2.db"
    proc, client, log_fh = _connect_iksd(
        iksd_path, dbfile, tmp_path / "v2first.log")
    try:
        _wait_for_file(dbfile)
        time.sleep(0.3)
        first = dbfile.read_bytes()
        assert first[:8] == MAGIC
    finally:
        _close_iksd(proc, client, log_fh)

    proc2, client2, log_fh2 = _connect_iksd(
        iksd_path, dbfile, tmp_path / "v2second.log")
    try:
        time.sleep(0.5)
        second = dbfile.read_bytes()
        assert second[:8] == MAGIC
        assert second[:HDRL] == first[:HDRL]
        # Header intact and the file is still a whole number of
        # records -- i.e. it wasn't reconverted (which would corrupt
        # or duplicate the header).
        assert (len(second) - HDRL) % RECL == 0
    finally:
        _close_iksd(proc2, client2, log_fh2)


def test_stale_ipv6_lock_is_removed(run_wermit, iksd_path, tmp_path):
    """Verify an IKSD removes a stale IPv6 lock file.

    The lock file holds "ADDRESS:PID", and the address contains colons.
    rename() replaces the lock file in any case on this system, so the
    debug log shows whether getslot() found the lock stale.
    """
    if not _build_has_iksdb(run_wermit):
        pytest.skip("build has no IKSDB support")
    if not _build_has_address_family(run_wermit):
        pytest.skip("build has no SET TCP ADDRESS-FAMILY (not CK_IPV6)")
    try:
        probe = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        probe.bind(("::1", 0))
        probe.close()
    except OSError:
        pytest.skip("no IPv6 loopback available in this environment")

    dead = subprocess.Popen(["true"])
    dead.wait()
    (tmp_path / "iksd.lck").write_text("::1:%010d\n" % dead.pid)
    dbfile = tmp_path / "iksd6.db"
    proc, client, log_fh = _connect_iksd(
        iksd_path, dbfile, tmp_path / "iksd6.log",
        family=socket.AF_INET6, bindaddr="::1", extra_args=["-d"],
        cwd=tmp_path)
    try:
        _wait_for_file(dbfile, timeout=6)
        assert dbfile.exists() and dbfile.stat().st_size > 0
    finally:
        _close_iksd(proc, client, log_fh)
    log = (tmp_path / "debug.log").read_text(errors="replace")
    assert "getslot PID stale" in log, log[-2000:]

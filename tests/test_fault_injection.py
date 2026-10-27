"""
Tests for failed and short reads and writes, using tests/faultinj.c.

faultinj.c is preloaded into wermit and makes the Nth read(), recv(),
write() or send() call fail, or makes a read return end of file.  These
tests check that wermit reports the error, or ends the operation, and
does not hang or crash.  They need glibc on Linux and a C compiler.
"""
import http.server
import os
import platform
import shutil
import subprocess
import threading
import time

import pytest

from test_iksdb import _build_has_iksdb, _close_iksd, _connect_iksd

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="session")
def faultinj(tmp_path_factory):
    """Build faultinj.so and return its path, or skip."""
    if platform.system() != "Linux" or not shutil.which("cc"):
        pytest.skip("fault injection needs Linux and cc")
    libc = platform.libc_ver()[0]
    if libc != "glibc":
        pytest.skip("fault injection needs glibc")
    lib = tmp_path_factory.mktemp("faultinj") / "faultinj.so"
    subprocess.run(["cc", "-O1", "-shared", "-fPIC", "-o", str(lib),
                    os.path.join(HERE, "faultinj.c"), "-ldl"],
                   check=True)
    return str(lib)


def run_faulted(wermit_path, lib, func, n, cmds, cwd, timeout=30, count=1):
    """Run wermit with calls n to n+count-1 of func failing.

    Return the CompletedProcess.
    """
    env = dict(os.environ, LD_PRELOAD=lib, FAULT_FUNC=func,
               FAULT_N=str(n), FAULT_COUNT=str(count))
    return subprocess.run([wermit_path, "-H", "-Y", "-Q", "-C",
                           cmds + ", exit 0"],
                          cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True,
                          timeout=timeout)


@pytest.mark.parametrize("func", ["read", "write"])
@pytest.mark.parametrize("n", [1, 2, 3])
def test_copy_reports_io_error(wermit_path, faultinj, tmp_path, func, n):
    """Verify COPY fails when a read or write of the file fails."""
    (tmp_path / "f.txt").write_text("line one\nline two\n" * 200)
    result = run_faulted(wermit_path, faultinj, func, n,
                         "copy f.txt g.txt, echo S=\\v(status)", tmp_path)
    assert result.returncode == 0, result.stderr
    assert "S=1" in result.stdout, result.stdout
    assert "Input/Output error" in result.stdout, result.stdout


@pytest.mark.parametrize("n", [1, 2, 3])
def test_copy_short_read_copies_what_was_read(wermit_path, faultinj,
                                              tmp_path, n):
    """Verify COPY stops at an early end of file and keeps the data."""
    data = "line one\nline two\n" * 200
    (tmp_path / "f.txt").write_text(data)
    result = run_faulted(wermit_path, faultinj, "readeof", n,
                         "copy f.txt g.txt, echo S=\\v(status)", tmp_path)
    assert result.returncode == 0, result.stderr
    copied = (tmp_path / "g.txt").read_text()
    assert data.startswith(copied), len(copied)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    """Serve files without logging or tracebacks."""

    def log_message(self, *args):
        pass

    def handle(self):
        try:
            super().handle()
        except OSError:
            pass


def _http_get(wermit_path, lib, tmp_path, func, count):
    """Serve f.txt and GET it with count reads failing from the first."""
    (tmp_path / "f.txt").write_text("hello\n" * 100)

    def handler(*a, **k):
        return _Quiet(*a, directory=str(tmp_path), **k)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        return run_faulted(
            wermit_path, lib, func, 1,
            f"http open 127.0.0.1 {port}, http get /f.txt out.txt, "
            "echo S=\\v(status), http close", tmp_path, count=count)
    finally:
        srv.shutdown()


@pytest.mark.parametrize("func", ["read", "readeof"])
def test_http_get_retries_a_lost_reply(wermit_path, faultinj, tmp_path,
                                       func):
    """Verify HTTP GET reconnects once when the first reply is lost."""
    result = _http_get(wermit_path, faultinj, tmp_path, func, 1)
    assert result.returncode == 0, result.stderr
    assert "S=0" in result.stdout, result.stdout
    assert (tmp_path / "out.txt").read_text() == "hello\n" * 100


@pytest.mark.parametrize("func", ["read", "readeof"])
def test_http_get_fails_when_replies_are_lost(wermit_path, faultinj,
                                              tmp_path, func):
    """Verify HTTP GET fails, without hanging, if both replies are lost."""
    result = _http_get(wermit_path, faultinj, tmp_path, func, 2)
    assert result.returncode == 0, result.stderr
    assert "S=1" in result.stdout, result.stdout


def test_type_short_read_ends_cleanly(wermit_path, faultinj, tmp_path):
    """Verify TYPE ends at an early end of file without error."""
    (tmp_path / "f.txt").write_text("alpha\nbeta\n" * 1000)
    result = run_faulted(wermit_path, faultinj, "readeof", 2,
                         "type f.txt, echo DONE", tmp_path)
    assert result.returncode == 0, result.stderr
    assert "DONE" in result.stdout, result.stdout[-500:]


def test_grep_array_open_failure(wermit_path, faultinj, tmp_path):
    """Verify GREP /ARRAY survives a file that fails to open.

    The parse checks that f.txt is readable.  Failing each open in turn
    makes the open in the search loop fail too.
    """
    (tmp_path / "f.txt").write_text("alpha\n")
    report = tmp_path / "count"
    cmds = "grep /array:&a alpha f.txt, echo COUNT=[\\&a[0]]"
    env = dict(os.environ, LD_PRELOAD=faultinj, FAULT_FUNC="open",
               FAULT_N="0", FAULT_REPORT=str(report))
    subprocess.run([wermit_path, "-H", "-Y", "-Q", "-C", cmds + ", exit 0"],
                   cwd=tmp_path, env=env, stdin=subprocess.DEVNULL,
                   capture_output=True, timeout=30, check=True)
    calls = int(report.read_text().split()[0])
    for n in range(1, calls + 1):
        result = run_faulted(wermit_path, faultinj, "open", n, cmds,
                             tmp_path)
        assert result.returncode == 0, (n, result.stdout, result.stderr)


def _pty_masters(pid):
    """Return the open flags of each pty master descriptor of pid."""
    flags = []
    fddir = f"/proc/{pid}/fd"
    for fd in os.listdir(fddir):
        try:
            target = os.readlink(os.path.join(fddir, fd))
        except OSError:
            continue
        if "ptmx" not in target:
            continue
        with open(f"/proc/{pid}/fdinfo/{fd}") as f:
            for line in f:
                if line.startswith("flags:"):
                    flags.append(int(line.split()[1], 8))
    return flags


@pytest.mark.parametrize("func", ["openpty", "fork"])
def test_ttptycmd_failure_restores_connection(wermit_path, faultinj,
                                              tmp_path, func):
    """Verify a failed openpty() or fork() in ttptycmd() cleans up.

    SET HOST /PTY makes the first call of each.  The second, from the
    Zmodem SEND, fails.  The connection must be blocking again, and
    the pty from a failed fork() must be closed.
    """
    (tmp_path / "f.txt").write_text("hello\n")
    ready = tmp_path / "ready"
    env = dict(os.environ, LD_PRELOAD=faultinj, FAULT_FUNC=func,
               FAULT_N="2")
    proc = subprocess.Popen(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         "set host /pty cat, send /protocol:zmodem f.txt, "
         f"open write {ready}, close write, pause 10, close, exit 0"],
        cwd=tmp_path, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        end = time.monotonic() + 20
        while not ready.exists() and time.monotonic() < end:
            time.sleep(0.1)
        assert ready.exists(), "wermit did not reach the pause"
        masters = _pty_masters(proc.pid)
    finally:
        proc.kill()
        proc.wait()
    assert len(masters) == 1, masters
    assert not masters[0] & os.O_NONBLOCK, oct(masters[0])

def test_iksd_lock_write_failure(run_wermit, wermit_path, faultinj,
                                 tmp_path):
    """Verify the IKSD leaves the database alone when it cannot lock it.

    The failed write is the write of the address and PID into the
    temporary lock file.  The IKSD removes the temporary file, creates
    no lock file and does not create the database.  The Telnet
    negotiation follows the database setup.
    """
    if not _build_has_iksdb(run_wermit):
        pytest.skip("build has no IKSDB support")
    iksd = tmp_path / "iksd"
    os.symlink(wermit_path, str(iksd))
    dbfile = tmp_path / "iksd.db"
    env = dict(os.environ, LD_PRELOAD=faultinj, FAULT_FUNC="write",
               FAULT_N="1")
    proc, client, log_fh = _connect_iksd(
        str(iksd), dbfile, tmp_path / "iksd.log", cwd=tmp_path, env=env)
    try:
        client.settimeout(5)
        assert client.recv(4096).startswith(b"\xff")
        assert not dbfile.exists()
        assert not (tmp_path / "iksd.lck").exists()
        names = [p.name for p in tmp_path.iterdir()]
        assert not [n for n in names if n.startswith("127.0.0.1.")], names
    finally:
        _close_iksd(proc, client, log_fh)


def test_iksd_lock_write_failure_syslog(run_wermit, wermit_path, faultinj,
                                        tmp_path):
    """Verify the IKSD logs a failed lock file write to syslog.

    FAULT_SYSLOG captures the syslog() messages.  Syslog support needs
    a build with -DDOSYSLOG.
    """
    if not _build_has_iksdb(run_wermit):
        pytest.skip("build has no IKSDB support")
    if "NOSYSLOG" in run_wermit("show features").stdout:
        pytest.skip("build has no syslog support (needs -DDOSYSLOG)")
    iksd = tmp_path / "iksd"
    os.symlink(wermit_path, str(iksd))
    dbfile = tmp_path / "iksd.db"
    log = tmp_path / "syslog.txt"
    env = dict(os.environ, LD_PRELOAD=faultinj, FAULT_FUNC="write",
               FAULT_N="1", FAULT_SYSLOG=str(log))
    proc, client, log_fh = _connect_iksd(
        str(iksd), dbfile, tmp_path / "iksd.log", cwd=tmp_path, env=env)
    try:
        client.settimeout(5)
        assert client.recv(4096).startswith(b"\xff")
        text = log.read_text() if log.exists() else ""
        assert ("IKSD database not updated: can't write lockfile "
                + str(tmp_path) + "/127.0.0.1.") in text, text
        assert not dbfile.exists()
    finally:
        _close_iksd(proc, client, log_fh)

def _children(pid):
    """Return the PIDs of the child processes of pid, zombies included."""
    kids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat") as f:
                stat = f.read()
        except OSError:
            continue
        if int(stat.rsplit(")", 1)[1].split()[1]) == pid:
            kids.append(int(entry))
    return kids


def test_pty_sync_failure_runs_nothing(wermit_path, faultinj, tmp_path):
    """Verify SET HOST /PTY runs nothing when its child cannot sync.

    Every write() fails, so the child of do_pty() cannot report through
    the sync pipe.  SET HOST must fail.  The command must not run, the
    pty master must be closed, and the child must be reaped.
    """
    ready = tmp_path / "ready"
    env = dict(os.environ, LD_PRELOAD=faultinj, FAULT_FUNC="write",
               FAULT_N="1", FAULT_COUNT="100000", HOME=str(tmp_path))
    proc = subprocess.Popen(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         "set host /pty sh -c 'touch marker', if success exit 3, "
         f"pause 1, open write {ready}, close write, pause 10, exit 0"],
        cwd=tmp_path, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        end = time.monotonic() + 20
        while (not ready.exists() and proc.poll() is None
               and time.monotonic() < end):
            time.sleep(0.1)
        assert proc.poll() is None, proc.returncode
        assert ready.exists(), "wermit did not reach the pause"
        masters = _pty_masters(proc.pid)
        kids = _children(proc.pid)
    finally:
        proc.kill()
        proc.wait()
    assert not (tmp_path / "marker").exists()
    assert masters == [], masters
    assert kids == [], kids

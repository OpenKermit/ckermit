import os
import pty
import select
import socket
import subprocess
import pytest
from pathlib import Path
import logging
import time

# Set to capture kermit's internal "log debug" trace (zchki()/stat()
# calls, protocol state, etc.) for every wermit_loopback session and
# dump it into the pytest failure report. Off by default because it
# roughly doubles the I/O of every loopback test.
DEBUG_LOOPBACK = bool(os.environ.get("KERMIT_TEST_DEBUG_LOOPBACK"))

# Exit code used by TcpLoopbackSession.run_client's "if failure exit"
# guard to signal that SET HOST itself never connected. Distinct from
# 0 (success) and from wermit's own exit codes for the commands that
# would otherwise have run.
SSL_CONNECT_FAILURE_CODE = 90

# Cap how much debug output gets captured in a log
# message. A hung session can retry in a tight loop and produce an
# large  amount of trace data before its timeout fires. Without a
# cap, one failure report can balloon to hundreds of megabytes.
# Keep the tail, since that is the data closest to the hang or failure.
MAX_LOGGED_CHARS = 50000


def truncated(label, text):
    """Returns text, or its last MAX_LOGGED_CHARS chars with a note of
    how much was omitted, so callers can safely dump traces into a
    logger.info() call regardless of how large they get."""
    if len(text) <= MAX_LOGGED_CHARS:
        return text
    omitted = len(text) - MAX_LOGGED_CHARS
    return (
        f"[{label}: {omitted} chars omitted, showing last "
        f"{MAX_LOGGED_CHARS} chars]\n{text[-MAX_LOGGED_CHARS:]}"
    )


def assert_ok(result, label="Command failed"):
    assert result.returncode == 0, (
        f"{label}: stdout={result.stdout}\nstderr={result.stderr}"
    )


def make_loopback_dirs(tmp_path, client_name="client", server_name="server"):
    """Create and return (client_dir, server_dir) under tmp_path."""
    client_dir = tmp_path / client_name
    server_dir = tmp_path / server_name
    client_dir.mkdir(exist_ok=True)
    server_dir.mkdir(exist_ok=True)
    return client_dir, server_dir


def resolve_transfer_paths(client_dir, server_dir, direction, file_name):
    """Return (src_file, dest_file) for the given transfer direction."""
    if direction == "send":
        return client_dir / file_name, server_dir / file_name
    if direction == "get":
        return server_dir / file_name, client_dir / file_name
    raise ValueError(f"Unknown direction: {direction}")


def take_file_lines(cmds):
    """Split a caller-supplied command string into individual TAKE-file
    lines.  Callers join multiple commands with newlines, with commas
    (as used for -C), or both.

    A TAKE file requires exactly one command per line."""
    lines = []
    for line in cmds.split("\n"):
        for part in line.split(","):
            part = part.strip()
            if part:
                lines.append(part)
    return lines


def pattern_bytes(size):
    """Generate test data, just 0x00 through 0xFF, for transfers of different
    sizes.  Since this data doesn't contain repeating sequences, Kermit's
    RLE won't reduce the packet sizes.  However, escaping may adjust transfer
    sizes."""
    reps = size // 256 + 1
    return (bytes(range(256)) * reps)[:size]


logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def wermit_path():
    """
    Locates the wermit binary relative to the test directory.
    Raises FileNotFoundError if the binary is not built.
    """
    # Relative path from /tests/conftest.py to the root wermit executable
    path = Path(__file__).parent.parent / "wermit"
    if not path.exists():
        raise FileNotFoundError(
            f"wermit binary not found at {path}. Please run 'make' in the root directory first."
        )
    return str(path.absolute())


@pytest.fixture
def run_wermit(wermit_path):
    """
    Synchronously runs a wermit command or script, returning a CompletedProcess.
    Can accept a list of arguments or a string command (executed via -C).
    """
    def _run(args, input_data=None, timeout=10):
        if isinstance(args, str):
            # Automatically skip init file, suppress banner, run inline
            # command with more-prompting off, and append exit to prevent
            # hanging in interactive mode (especially when run with pytest -s)
            cmd_str = args.strip()
            if not (cmd_str.endswith(", exit") or cmd_str.endswith(",exit") or cmd_str == "exit"):
                cmd_str += ", exit"
            cmd = [wermit_path, "-H", "-Y", "-C",
                   f"set command more-prompting off, {cmd_str}"]
        else:
            cmd = [wermit_path] + args

        logger.info("run_wermit: Launching process: %s", " ".join(cmd))
        t_start = time.perf_counter()
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        logger.info("run_wermit: Process completed with exit code %d in %.4f seconds",
                    result.returncode, time.perf_counter() - t_start)
        return result
    return _run


@pytest.fixture(params=[False, True], ids=["default", "clear_unprefix"])
def wermit_loopback(request, wermit_path, run_wermit):
    """
    Sets up and runs a full wermit client-server loopback session using
    pseudoterminals. Returns a callable that accepts a server directory,
    optional server setup commands, and client commands; creates the server
    script, runs the client against it, and returns a CompletedProcess.
    """
    created_files = []
    use_clear_unprefix = request.param

    def _run(server_dir, server_setup_cmds="", client_commands="",
             timeout=10):
        server_ksc = Path(server_dir).parent / \
            f"server_{Path(server_dir).name}.ksc"
        server_log = Path(server_dir).parent / \
            f"server_{Path(server_dir).name}.log"
        client_log = Path(server_dir).parent / \
            f"client_{Path(server_dir).name}.log"

        # Build server script content
        setup_lines = []
        if DEBUG_LOOPBACK:
            setup_lines.append(f"log debug {server_log}")
        setup_lines.append("set command more-prompting off")
        setup_lines.append("set delay 0")
        if use_clear_unprefix:
            setup_lines.append("set clear-channel on")
            setup_lines.append("set control unprefix all")
        setup_lines.append(f"cd {server_dir}")
        if server_setup_cmds:
            setup_lines.extend(take_file_lines(server_setup_cmds))
        setup_lines.append("server")

        logger.info("wermit_loopback: Creating server script %s", server_ksc)
        logger.debug("wermit_loopback: Server script content:\n%s",
                     "\n".join(setup_lines))
        server_ksc.write_text("\n".join(setup_lines) + "\n")
        if server_ksc not in created_files:
            created_files.append(server_ksc)
        if DEBUG_LOOPBACK:
            if server_log not in created_files:
                created_files.append(server_log)
            if client_log not in created_files:
                created_files.append(client_log)

        if isinstance(client_commands, list):
            cmd_str = ", ".join(client_commands)
        else:
            cmd_str = client_commands

        if use_clear_unprefix:
            client_prefix = (
                "set clear-channel on, set control unprefix all, "
            )
        else:
            client_prefix = ""

        client_debug_prefix = f"log debug {client_log}, " if DEBUG_LOOPBACK else ""
        full_client_cmd = [
            "-H", "-Y", "-Q", "-C",
            f"{client_debug_prefix}set command more-prompting off, set delay 0, set host /network-type:pseudoterminal {wermit_path} {server_ksc.absolute()}, set delay 0, {client_prefix}{cmd_str}, close, exit"
        ]
        logger.info(
            "wermit_loopback: Client running command sequence: %s", cmd_str)
        result = run_wermit(full_client_cmd, timeout=timeout)

        if DEBUG_LOOPBACK:
            for label, log_path in (("Server", server_log), ("Client", client_log)):
                if log_path.exists():
                    try:
                        log_content = log_path.read_text(errors='replace')
                        logger.info(
                            "wermit_loopback: %s process debug log:\n%s",
                            label,
                            truncated(f"{label} debug log", log_content))
                    except Exception as e:
                        logger.warning(
                            "wermit_loopback: Failed to read %s log %s: %s",
                            label, log_path, e)

        return result

    yield _run

    # Clean up temporary server scripts
    for path in created_files:
        try:
            if path.exists():
                logger.info("wermit_loopback: Cleaning up script %s", path)
                path.unlink()
        except OSError:
            pass


@pytest.fixture
def get_free_port():
    """
    Finds and returns a free TCP port on localhost for real-socket tests.
    """
    def _get_port():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port
    return _get_port


@pytest.fixture
def spawn_wermit(wermit_path):
    """
    Asynchronously runs a wermit process in the background, optionally
    redirecting its combined stdout/stderr to a caller-provided file
    object. Automatically terminates/kills the process on teardown.
    """
    processes = []

    def _spawn(args, cwd=None, stdout=None):
        cmd = [wermit_path] + args
        logger.info("spawn_wermit: Launching background process: %s",
                    " ".join(cmd))
        proc = subprocess.Popen(
            cmd,
            stdout=stdout if stdout is not None else subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            cwd=cwd
        )
        processes.append(proc)
        return proc

    yield _spawn

    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)


@pytest.fixture
def wermit_tcp_loopback(spawn_wermit, run_wermit, get_free_port):
    """
    Sets up a wermit client-server session over a real TCP/IP loopback
    socket (127.0.0.1), as opposed to the pseudoterminal used by
    wermit_loopback. This is required for SSL/TLS tests: C-Kermit's SSL
    support (ckcnet.c netopen()/tcpsrv_open()) only runs for genuine TCP
    sockets, so the PTY-based fixture never exercises it.

    Returns a callable that starts a server listening on a free port
    (optionally with an /SSL or /TLS protocol-switch and setup commands
    such as certificate configuration) and returns a TcpLoopbackSession
    for driving one or more clients against it.
    """
    created_files = []
    opened_logs = []

    class TcpLoopbackSession:
        def __init__(self, port, server_proc, server_log_path):
            self.port = port
            self.server_proc = server_proc
            self.server_log_path = server_log_path

        def run_client(self, client_commands, protocol=None,
                       setup_cmds="", timeout=10):
            """
            Connects a client to the loopback server and runs the given
            commands. protocol, if given ("ssl" or "tls"), is appended
            as a /SSL or /TLS protocol-switch to SET HOST. setup_cmds
            are run before SET HOST (e.g. to configure client-side
            certificate/verification parameters). Note: unlike
            wermit_loopback, no -Q switch is used, because C-Kermit
            suppresses its "[SSL - OK]"/"[SSL - FAILED]" verbose
            authentication messages whenever -Q (quiet) is in effect.
            """
            if isinstance(client_commands, list):
                cmd_str = ", ".join(client_commands)
            else:
                cmd_str = client_commands

            proto_switch = f" /{protocol}" if protocol else ""
            setup_prefix = f"{setup_cmds}, " if setup_cmds else ""

            full_client_cmd = [
                "-H", "-Y", "-C",
                "set command more-prompting off, "
                "set tcp reverse-dns-lookup off, "
                f"{setup_prefix}"
                f"set host localhost {self.port}{proto_switch}, "
                # Bail out immediately if the connection (e.g. the SSL/TLS
                # handshake) didn't succeed, instead of running the rest
                # of the command list with no connection open. Without
                # this, a command like REMOTE falls back to speaking
                # Kermit protocol over the controlling terminal (there
                # being no open connection), hanging until it exhausts
                # its retries.
                f"if failure exit {SSL_CONNECT_FAILURE_CODE}, "
                f"{cmd_str}, close, exit"
            ]
            logger.info(
                "wermit_tcp_loopback: Client running command sequence: %s",
                cmd_str)
            return run_wermit(full_client_cmd, timeout=timeout)

        def server_output(self):
            """Returns the server's captured stdout/stderr so far."""
            try:
                return self.server_log_path.read_text(errors="replace")
            except OSError:
                return ""

        def wait_for_server_exit(self, timeout=5):
            """Waits for the server process to exit, forcing it to stop
            if it hasn't on its own, and returns its exit code."""
            try:
                self.server_proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.server_proc.terminate()
                try:
                    self.server_proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.server_proc.kill()
                    self.server_proc.wait(timeout=2)
            return self.server_proc.returncode

    def _setup(server_dir, protocol=None, setup_cmds="", ready_timeout=10):
        port = get_free_port()
        server_log_path = Path(server_dir).parent / \
            f"tcp_server_{Path(server_dir).name}.log"

        proto_switch = f" /{protocol}" if protocol else ""
        setup_prefix = f"{setup_cmds}, " if setup_cmds else ""
        server_cmd = [
            "--unbuffered", "-H", "-Y", "-C",
            "set command more-prompting off, "
            "set tcp reverse-dns-lookup off, "
            f"cd {server_dir}, {setup_prefix}"
            f"set host /server * {port}{proto_switch}"
        ]

        logger.info("wermit_tcp_loopback: Starting server on port %d: %s",
                    port, server_cmd)
        server_log_fh = open(server_log_path, "w")
        opened_logs.append(server_log_fh)
        created_files.append(server_log_path)
        proc = spawn_wermit(server_cmd, stdout=server_log_fh)

        deadline = time.monotonic() + ready_timeout
        ready = False
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            server_log_fh.flush()
            content = server_log_path.read_text(errors="replace")
            # "Waiting to Accept" is the only reliable readiness signal:
            # under CK_IPV6, SET HOST * in AUTO mode (the default) binds
            # an IPv4 and an IPv6 socket one after another, each printing
            # its own "Listening" line as it completes, so "Listening"
            # alone can appear well before the *second* socket is
            # actually up. "Waiting to Accept" is printed exactly once,
            # only after every socket SET HOST * is going to open has
            # finished binding and listening.
            if "Waiting to Accept" in content:
                ready = True
                break
            time.sleep(0.05)

        if not ready:
            server_log_fh.flush()
            content = server_log_path.read_text(errors="replace")
            raise RuntimeError(
                "wermit_tcp_loopback: server did not start listening "
                f"(exit={proc.poll()}); log:\n{content}"
            )

        return TcpLoopbackSession(port, proc, server_log_path)

    yield _setup

    for fh in opened_logs:
        try:
            fh.close()
        except OSError:
            pass

    for path in created_files:
        try:
            if logger.isEnabledFor(logging.DEBUG) and path.exists():
                logger.debug(
                    "wermit_tcp_loopback: Server process log:\n%s",
                    path.read_text(errors="replace"))
            if path.exists():
                path.unlink()
        except OSError:
            pass


# The following scaffolding runs a wermit process ("the local side")
# with its own console (stdin/stdout/stderr) attached to a real
# pseudoterminal, since kermit's console handling requires a real tty
# in some code paths (e.g. ttptycmd() in ckutio.c). It's used directly
# by tests that just need to run a wermit command and capture its
# output (e.g. test_zmodem.py's PTY-mode transfers), and it's also the
# building block zmodem_remote uses for its TCP mode, where the
# wermit-under-test must be started (as a TCP listener) before its
# remote peer is spawned, and only collected afterwards.

def _log_debug_file(label, path):
    path = Path(path)
    if not path.exists():
        return
    try:
        text = path.read_text(errors="replace")
        logger.info(
            "%s: wermit debug log:\n%s",
            label, truncated("wermit debug log", text))
    except OSError as e:
        logger.warning(
            "%s: failed to read debug log %s: %s", label, path, e)


def _log_process_snapshot(label):
    """Logs any wermit/sz/rz processes still alive, so a timeout tells
    us whether the hang is in wermit itself or in a child it exec'd.
    This is a system-wide ps -ef filtered by name only, so under
    parallel test runs (or just an unrelated wermit/sz/rz elsewhere on
    the machine) it can easily catch processes that have nothing to do
    with the test that timed out."""
    try:
        ps = subprocess.run(
            ["ps", "-ef"], capture_output=True, text=True, timeout=5)
        relevant = "\n".join(
            line for line in ps.stdout.splitlines()
            if line.startswith("UID")
            or any(name in line for name in ("wermit", " sz", " rz"))
        )
        logger.info(
            "%s: possibly relevant process snapshot:\n%s", label, relevant)
    except Exception as e:
        logger.warning(
            "%s: failed to capture process snapshot: %s", label, e)


def start_wermit_pty(wermit_path, cmd_str, cwd, debug_log=None):
    """
    Starts a wermit process with its stdin/stdout/stderr connected to a
    real pseudoterminal slave, without waiting for it to finish.
    Returns (proc, master).  Pass both to finish_wermit_pty() to
    collect its output and exit code.
    """
    master, slave = pty.openpty()

    debug_prefix = f"log debug {debug_log}, " if debug_log else ""
    cmd = [
        wermit_path, "-H", "-Y", "-C",
        f"{debug_prefix}set command more-prompting off, {cmd_str}"
    ]

    proc = subprocess.Popen(
        cmd,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        cwd=str(cwd),
        close_fds=True
    )

    os.close(slave)
    return proc, master


def finish_wermit_pty(proc, master, timeout=45, debug_log=None):
    """
    Reads a wermit process's pty output (started via start_wermit_pty)
    until it exits or the timeout fires, then returns
    (returncode, stdout).
    """
    output = []
    start_time = time.time()

    while proc.poll() is None:
        if time.time() - start_time > timeout:
            captured = b"".join(output).decode('utf-8', errors='replace')
            logger.error(
                "finish_wermit_pty: wermit (pid %d) timed out after %ds. "
                "pty output captured before timeout:\n%s",
                proc.pid, timeout, truncated("pty output", captured))
            _log_process_snapshot("finish_wermit_pty")
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
            os.close(master)
            if debug_log:
                _log_debug_file("finish_wermit_pty", debug_log)
            raise subprocess.TimeoutExpired(
                proc.args, timeout, output=captured.encode())

        r, _, _ = select.select([master], [], [], 0.1)
        if master in r:
            try:
                data = os.read(master, 4096)
                if not data:
                    break
                output.append(data)
            except OSError:
                break

    # Read any remaining output after process exits
    while True:
        r, _, _ = select.select([master], [], [], 0.05)
        if master in r:
            try:
                data = os.read(master, 4096)
                if not data:
                    break
                output.append(data)
            except OSError:
                break
        else:
            break

    os.close(master)
    proc.wait()

    if debug_log:
        _log_debug_file("finish_wermit_pty", debug_log)

    return proc.returncode, b"".join(output).decode('utf-8', errors='replace')


def run_wermit_pty(wermit_path, cmd_str, cwd, timeout=45, debug_log=None):
    """
    Runs kermit with its stdin, stdout, and stderr connected to a real
    pseudoterminal slave, waiting for it to finish and returning
    (returncode, stdout).

    This is because, by default, when kermit sets up a host connection
    over a pseudoterminal, it runs ckutio.c:ttptycmd(). If kermit's own
    stdin is not a TTY (e.g., standard input is redirected from
    /dev/null or pipes), the original implementation of
    tcgetattr(0, &term) and ioctl(0, TIOCGWINSZ, &twin) would fail,
    printing "tcgetattr: Inappropriate ioctl for device" and aborting.

    Using pty.openpty() ensures that tests execute in a clean, simulated
    terminal environment matching normal shell usage.
    """
    proc, master = start_wermit_pty(wermit_path, cmd_str, cwd, debug_log)
    return finish_wermit_pty(proc, master, timeout=timeout, debug_log=debug_log)


def _wait_for_pty_marker(master, marker, timeout):
    """
    Reads from a pty master until marker (bytes) appears in the
    accumulated output or timeout runs out, returning whatever was
    read (so callers can prepend it to later-captured output).
    """
    buf = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r, _, _ = select.select([master], [], [], 0.1)
        if master in r:
            try:
                data = os.read(master, 4096)
            except OSError:
                break
            if not data:
                break
            buf += data
            if marker in buf:
                break
    return buf


@pytest.fixture(params=["pty", "tcp"], ids=["pty", "tcp"])
def zmodem_remote(request, wermit_path, get_free_port, spawn_wermit):
    """
    Provides a way to run the wermit-under-test (Zmodem tests' "local"
    side) against a real rz/sz "remote", parameterized over two ways
    of reaching it:

    - "pty": the far end of SET HOST /NETWORK-TYPE:PSEUDOTERMINAL is a
      second wermit process, not rz/sz directly. rz/sz's own termios
      handling (see doc/mac.md: rz unconditionally re-enables IXOFF on
      itself via io_mode(), among other things, moments after any
      raw-mode setup the connection itself does) turned out to apply
      directly to whatever pty is hosting it.  When rz/sz is the
      connection target itself, that pty is the exact one the
      wermit-under-test treats as its own connection, not some private
      pty of rz/sz's own. Routing through a second wermit instead (the
      same wermit_loopback fixture's approach, adapted for Zmodem
      instead of Kermit protocol) means rz/sz only ever touches a
      private pty that far-end wermit creates for it via its own
      ttptycmd(), exactly like the "tcp" mode below already ensures.
      This makes the two modes structurally identical in that respect,
      differing only in the outer connection's transport.

      The far-end wermit is exec'd with a script and no explicit SET
      LINE or SET HOST of its own: a wermit invoked this way (as the
      target of another process's SET HOST /NETWORK-TYPE:PSEUDOTERMINAL)
      treats its own controlling tty (the pty slave it was exec'd
      onto) as its connection by default, so SET PROTOCOL ZMODEM
      plus SEND or RECEIVE runs directly over it with nothing else
      needed.

    - "tcp": a second, plain wermit process ("the remote") reaches the
      wermit-under-test over a raw TCP/IP connection.  It doesn't use
      Kermit's SERVER mode.

      To actually run rz/sz, the remote uses SET PROTOCOL ZMODEM plus SEND or
      RECEIVE, which is Kermit's mechanism for redirecting an external protocol
      over the current connection.  It forks rz/sz onto a pty of its own
      choosing and relays that to the connection. This is exactly the same
      mechanism the wermit under test already uses for SEND with a
      non-Kermit protocol, so it needs no special handling on the test's part.
      It's the same as a real remote BBS/modem host execing rz/sz onto the line
      it's already connected to, just automated by Kermit instead of by hand.

      The remote is spawned via spawn_wermit with its console discarded.  Unlike
      the wermit under test, it doesn't need a real tty, and giving it an unread
      pty instead of discarding its output would risk deadlock on large
      transfers once its progress messages fill the pty's kernel buffer with
      nothing draining it.

    Returns a callable:
        zmodem_remote(remote_argv, cmd_str, cwd, timeout=45,
                      debug_log=None)
    where remote_argv is the rz/sz command as a list (e.g.
    ["sz", str(src_file)] or ["rz"]), and cmd_str is the
    wermit-under-test's own command string with a literal "{HOST}"
    placeholder standing in for the "set host" target.

    Returns (returncode, stdout) like run_wermit_pty. The
    callable also exposes zmodem_remote.mode ("pty" or "tcp") so
    callers can pad timeouts for the extra TCP connection setup.
    """
    mode = request.param
    created_files = []

    def _remote_clause(remote_argv):
        """
        Translates remote_argv (["sz", path] to send that file, or
        ["rz"] to receive) into the SET PROTOCOL ZMODEM SEND/RECEIVE
        clause a remote wermit runs to do the same thing via its own
        external-protocol machinery.
        """
        if remote_argv[0] == "sz":
            return f"send {remote_argv[1]}"
        return "receive"

    def _pty_run(remote_argv, cmd_str, cwd, timeout=45, debug_log=None):
        server_ksc = Path(cwd).parent / "zmodem_remote_server.ksc"
        server_ksc.write_text(
            "set command more-prompting off\n"
            "set delay 0\n"
            "set protocol zmodem\n"
            f"{_remote_clause(remote_argv)}\n"
            "exit\n"
        )
        created_files.append(server_ksc)

        full_cmd_str = cmd_str.format(
            HOST="/network-type:pseudoterminal "
                 f"{wermit_path} {server_ksc.absolute()}")
        return run_wermit_pty(
            wermit_path, full_cmd_str, cwd, timeout=timeout,
            debug_log=debug_log)

    def _tcp_run(remote_argv, cmd_str, cwd, timeout=45, debug_log=None):
        port = get_free_port()
        full_cmd_str = cmd_str.format(HOST=f"* {port} /raw-socket")

        # Start the wermit-under-test first: it's the TCP listener, so
        # it must be listening before the remote side tries to
        # connect.
        proc, master = start_wermit_pty(
            wermit_path, full_cmd_str, cwd, debug_log)
        # "Waiting to Accept" (not "Listening") is the only reliable
        # readiness signal here -- see the identical comment in
        # wermit_tcp_loopback's _setup() above for why: under CK_IPV6,
        # SET HOST * in AUTO mode (the default) binds an IPv4 and an
        # IPv6 socket one after another, each printing its own
        # "Listening" line, so waiting for "Listening" can let the
        # client below race ahead and try to connect (to whichever
        # family the resolver prefers, often IPv6) before that
        # socket is actually up yet.
        prefix = _wait_for_pty_marker(master, b"Waiting to Accept",
                                       timeout=10)

        spawn_wermit(
            ["-H", "-Y", "-C",
             "set command more-prompting off, "
             "set tcp reverse-dns-lookup off, "
             "set protocol zmodem, "
             f"set host localhost {port} /raw-socket, "
             f"{_remote_clause(remote_argv)}, close, exit"],
            cwd=str(cwd), stdout=subprocess.DEVNULL)

        returncode, stdout = finish_wermit_pty(
            proc, master, timeout=timeout, debug_log=debug_log)
        return returncode, prefix.decode('utf-8', errors='replace') + stdout

    run = _tcp_run if mode == "tcp" else _pty_run
    run.mode = mode
    yield run

    for path in created_files:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

import os
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

    def _run(server_dir, server_setup_cmds="", client_commands=""):
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
            setup_lines.append(server_setup_cmds)
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
        result = run_wermit(full_client_cmd)

        if DEBUG_LOOPBACK:
            for label, log_path in (("Server", server_log), ("Client", client_log)):
                if log_path.exists():
                    try:
                        log_content = log_path.read_text(errors='replace')
                        logger.info(
                            "wermit_loopback: %s process debug log:\n%s",
                            label, log_content)
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
            if "Listening" in content or "Waiting to Accept" in content:
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

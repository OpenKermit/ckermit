import os
import pty
import select
import shutil
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

# sz/rz (lrzsz) print a  status
# line to their controlling terminal for roughly every 1K
# subpacket.  ttptycmd()
# relays every one of those bytes just like real file data, so this
# purely cosmetic chatter turns into ~20,000 extra small read/write
# round trips, each a scheduling opportunity for another process to
# steal the CPU.  Under high CPU load, this causes failure.
# This is sz/rz's behavior, not a ckermit inefficiency, and
# real interactive users generally want that progress display, so
# this quiets it for tests only rather than changing ckermit's
# shipped SET PROTOCOL ZMODEM default. Params are upload-binary,
# upload-text, send-binary, send-text, receive-binary, receive-text
# (see SET PROTOCOL's help text); upload-* are left blank since
# nothing here relies on kermit's remote-command-on-connect feature.
ZMODEM_QUIET_PROTOCOL_CLAUSE = (
    'set protocol zmodem "" "" "sz -q %s" "sz -q -a %s" "rz -q" "rz -q"'
)

# Exit code used by TcpLoopbackSession.run_client's "if failure exit"
# guard to signal that SET HOST itself never connected. Distinct from
# 0 (success) and from wermit's exit codes for the commands that
# would otherwise have run.
SSL_CONNECT_FAILURE_CODE = 90

# Extra seconds padded onto client-side timeouts for any real-TCP transport
# beyond what a pty needs.  Leaves headroom if necessary for real TCP connection
# setup/teardown.  I'm not convinced this is necessary though.
TCP_TIMEOUT_MARGIN = 15

# /TELNET pulls in two Telnet options by default that a wermit-to- wermit test
# connection doesn't need and that each cost real wall-clock time to negotiate:
#
# - AUTHENTICATION/START-TLS: the server side requests AUTHENTICATION,
#   and SSL is one of the auth types on offer, so the two ends go off
#   and negotiate an SSL-authenticated session instead of the plain
#   Telnet connection these tests mean to exercise.
#
# - KERMIT (option 47, RFC 2840): both ends mutually request it by
#   default, triggering an SB KERMIT SOP sub-negotiation
#   (tn_wait()/tn_siks() in ckctel.c) on top of the ordinary option
#   negotiation. Measured as the dominant cost of a plain "REMOTE PWD"
#   over /TELNET taking ~8s versus ~0.4s for the otherwise-identical
#   /RAW-SOCKET case; refusing it alone brings that down to ~1.6s.
#
# Several other options (TERMINAL-TYPE, NAWS, NEW-ENVIRONMENT, SEND-LOCATION,
# COM-PORT-CONTROL) are also requested by default and each add further small
# delays, but refusing them together with KERMIT was tried and broke
# Zmodem-over-telnet, rz/sz's handshake bytes never reaching the other side.
# Whatever combination of Telnet option state that KERMIT negotiation leaves
# behind evidently matters to the raw 8-bit-clean path Zmodem depends on with no
# Kermit-level framing. Don't add further refusals here without
# confirming zmodem_remote's tcp-telnet tests still pass.
TELNET_MINIMAL_OPTIONS_CLAUSE = (
    "set telopt /client authentication refused, "
    "set telopt /client start-tls refused, "
    "set telopt /client kermit refused, "
    "set telopt /server authentication refused, "
    "set telopt /server start-tls refused, "
    "set telopt /server kermit refused"
)


def telnet_minimal_options_prefix(transport):
    """Returns TELNET_MINIMAL_OPTIONS_CLAUSE as a ", "-suffixed prefix
    ready to prepend to a command string when transport is "telnet"
    (however the caller spells its raw-mode value), or "" otherwise.
    """
    return (f"{TELNET_MINIMAL_OPTIONS_CLAUSE}, "
            if transport == "telnet" else "")


def ssl_server_setup_cmds(ssl_pki):
    """SET AUTHENTICATION SSL commands presenting the "happy path"
    trusted-CA-signed server certificate from the ssl_pki fixture.
    Shared by anything that wants a working /SSL (or /TLS) server side
    without walking through test_ssl.py's negative-path
    certificate variations (untrusted CA, expired, etc.)."""
    return (
        "set authentication ssl rsa-cert-file "
        f"{ssl_pki['server_crt']}, "
        f"set authentication ssl rsa-key-file {ssl_pki['server_key']}"
    )


def ssl_client_setup_cmds(ssl_pki):
    """SET AUTHENTICATION SSL command trusting the CA that signed the
    "happy path" server certificate ssl_server_setup_cmds() presents.
    """
    return f"set authentication ssl verify-file {ssl_pki['ca_crt']}"


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


def tail_text(path, label, max_chars=MAX_LOGGED_CHARS):
    """Returns at most the last max_chars characters of a text file,
    formatted the same way truncated() would, without first reading
    the whole file into memory.

    A session that retries in a tight loop, or a large-file transfer
    with debug logging on, can leave behind a log hundreds of
    megabytes in size. Reading and decoding all of that just to keep
    the last max_chars via truncated() a moment later was slow enough
    on its own to trip pytest's timeout. Seeking near the end keeps
    the amount of data read and decoded bounded regardless of the
    file's actual size.
    """
    path = Path(path)
    size = path.stat().st_size
    # Read a generous byte margin per character: a UTF-8 character can
    # take up to 4 bytes, and the file may also contain raw invalid
    # bytes that each need a single-character replacement.
    read_size = max_chars * 4
    with path.open("rb") as f:
        if size > read_size:
            f.seek(size - read_size)
        text = f.read().decode("utf-8", errors="replace")
    if size <= read_size:
        return text
    text = text[-max_chars:]
    return (
        f"[{label}: {size} byte file, showing last "
        f"{len(text)} chars]\n{text}"
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


# Number of times a TCP-listener spawn is retried, with a freshly probed port,
# after get_free_port() lost the probe-then-release race.  The port it hands
# back was free at the moment of the probe, but nothing reserves it, so under
# heavy parallel test load another process can grab that same port before this
# listener's SET HOST gets to bind it.  Each retry calls get_free_port() again,
# so it isn't the same losing port a second time.
PORT_COLLISION_RETRIES = 3

# ckermit's message when SET HOST's bind() fails, checked in a spawned
# listener's captured output to distinguish a port race failure
# from some other startup failure.
#
PORT_BIND_FAILURE_MARKER = "Unable to bind to socket"


class PortCollisionError(RuntimeError):
    """Raised by _wait_for_tcp_listener when the spawned listener's
    output shows PORT_BIND_FAILURE_MARKER: get_free_port()'s
    probed port was raced by something else before this listener
    could bind it. Callers should retry with a fresh port rather than
    fail the test outright."""


def _wait_for_tcp_listener(proc, log_path, log_fh, label, timeout=10):
    """
    Polls log_path (the captured stdout of a wermit process started
    via spawn_wermit) until "Waiting to Accept" appears, proc exits,
    or timeout runs out. Raises PortCollisionError, or plain
    RuntimeError for anything else, with the captured log, on failure.

    "Waiting to Accept" (not "Listening") is the only reliable
    readiness signal: under CK_IPV6, SET HOST * in AUTO mode (the
    default) binds an IPv4 and an IPv6 socket one after another, each
    printing its "Listening" line as it completes, so "Listening"
    alone can appear well before the *second* socket is actually up.
    "Waiting to Accept" is printed exactly once, only after every
    socket SET HOST * is going to open has finished binding and
    listening.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        log_fh.flush()
        content = log_path.read_text(errors="replace")
        if "Waiting to Accept" in content:
            return
        time.sleep(0.05)

    log_fh.flush()
    content = log_path.read_text(errors="replace")
    if PORT_BIND_FAILURE_MARKER in content:
        raise PortCollisionError(
            f"{label}: port raced by another process; log:\n{content}"
        )
    raise RuntimeError(
        f"{label}: server did not start listening "
        f"(exit={proc.poll()}); log:\n{content}"
    )


def _wait_or_kill(proc, timeout=5):
    """Waits for proc to exit, escalating to terminate() then kill()
    if it doesn't exit by itself. Returns its exit code."""
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
    return proc.returncode


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


@pytest.fixture(params=["pseudoterminal"])
def loopback_transport(request):
    """
    This is the transport that wermit_loopback's client and server use to reach
    each other.  "pseudoterminal", "raw-socket", "telnet" (a loopback TCP
    socket, without or with telnet framing), or "ssl" (a loopback TCP socket
    wrapped in /SSL, with a "happy path" CA-trusted certificate from the ssl_pki
    fixture; skips if openssl isn't on PATH).

    Test modules that need TCP, telnet, or SSL coverage override this fixture
    locally (same name, additional params, in that module only); modules that
    don't stay on pseudoterminal-only, unaffected in test count or behavior.
    """
    return request.param


@pytest.fixture(params=[False, True], ids=["default", "clear_unprefix"])
def wermit_loopback(request, wermit_path, run_wermit, spawn_wermit,
                    get_free_port, loopback_transport):
    """

    Sets up and runs a full wermit client-server loopback session.  Returns a
    callable that accepts a server directory, optional server setup commands,
    and client commands; runs the client against the server, and returns a
    CompletedProcess.

    The connection is provided by loopback_transport.  The far ("server") end
    always runs server_setup_cmds followed by SERVER; a caller whose
    server_setup_cmds itself ends in "exit" (to instead drive an interactive
    script over the connection) simply leaves that trailing SERVER unreached,
    exactly as in a real take file.
    """
    created_files = []
    opened_logs = []
    use_clear_unprefix = request.param
    transport = loopback_transport

    def _run_pseudoterminal(server_dir, setup_lines, cmd_str,
                            client_prefix, client_debug_prefix,
                            server_log, client_log, timeout):
        server_ksc = Path(server_dir).parent / \
            f"server_{Path(server_dir).name}.ksc"
        logger.info(
            "wermit_loopback: Creating server script %s", server_ksc)
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

        full_client_cmd = [
            "-H", "-Y", "-Q", "-C",
            f"{client_debug_prefix}set command more-prompting off, "
            f"set delay 0, set host /network-type:pseudoterminal "
            f"{wermit_path} {server_ksc.absolute()}, set delay 0, "
            f"{client_prefix}{cmd_str}, close, exit"
        ]
        logger.info(
            "wermit_loopback: Client running command sequence: %s",
            cmd_str)
        return run_wermit(full_client_cmd, timeout=timeout)

    def _tcp_switch_and_prefixes(transport):

        """Returns (switch, server_prefix, client_prefix) for a TCP-based
        transport: the SET HOST protocol-switch name, and any commands each side
        must run before SET HOST.  raw-socket needs neither; telnet needs the
        same refusals on both ends; ssl needs asymmetric certificate setup
        pulled from the ssl_pki fixture, fetched lazily so only tests that
        actually pick "ssl" pay for generating it (or get skipped if openssl
        isn't available).
        """

        if transport == "ssl":
            ssl_pki = request.getfixturevalue("ssl_pki")
            return ("ssl", f"{ssl_server_setup_cmds(ssl_pki)}, ",
                    f"{ssl_client_setup_cmds(ssl_pki)}, ")
        prefix = telnet_minimal_options_prefix(transport)
        return transport, prefix, prefix

    def _run_tcp(server_dir, setup_lines, cmd_str, client_prefix,
                client_debug_prefix, server_log, client_log, timeout):
        switch, server_prefix, client_extra_prefix = \
            _tcp_switch_and_prefixes(transport)
        server_stdout_log = Path(server_dir).parent / \
            f"tcp_server_{Path(server_dir).name}.log"
        if server_stdout_log not in created_files:
            created_files.append(server_stdout_log)
        if DEBUG_LOOPBACK:
            if server_log not in created_files:
                created_files.append(server_log)
            if client_log not in created_files:
                created_files.append(client_log)

        server_cmd_str = ", ".join(setup_lines)
        port = None
        for attempt in range(PORT_COLLISION_RETRIES):
            port = get_free_port()
            server_full_cmd = [
                "--unbuffered", "-H", "-Y", "-C",
                f"{server_prefix}set host * {port} /{switch}, "
                f"{server_cmd_str}"
            ]
            logger.info(
                "wermit_loopback: Starting server on port %d: %s",
                port, server_full_cmd)
            server_log_fh = open(server_stdout_log, "w")
            opened_logs.append(server_log_fh)
            proc = spawn_wermit(server_full_cmd, stdout=server_log_fh)
            try:
                _wait_for_tcp_listener(
                    proc, server_stdout_log, server_log_fh,
                    "wermit_loopback")
                break
            except PortCollisionError:
                if attempt == PORT_COLLISION_RETRIES - 1:
                    raise
                logger.info(
                    "wermit_loopback: port %d raced, retrying", port)
                _wait_or_kill(proc, timeout=1)

        full_client_cmd = [
            "-H", "-Y", "-Q", "-C",
            f"{client_debug_prefix}set command more-prompting off, "
            "set delay 0, set tcp reverse-dns-lookup off, "
            f"{client_extra_prefix}set host localhost {port} /{switch}, "
            f"if failure exit {SSL_CONNECT_FAILURE_CODE}, "
            f"set delay 0, {client_prefix}{cmd_str}, close, exit"
        ]
        logger.info(
            "wermit_loopback: Client running command sequence: %s",
            cmd_str)
        result = run_wermit(
            full_client_cmd, timeout=timeout + TCP_TIMEOUT_MARGIN)
        _wait_or_kill(proc)
        return result

    def _run(server_dir, server_setup_cmds="", client_commands="",
             timeout=10):
        # Only ever written to if DEBUG_LOOPBACK enables "log debug"
        # on both sides.  Distinct from _run_tcp's
        # stdout-capture log.
        server_log = Path(server_dir).parent / \
            f"server_{Path(server_dir).name}.log"
        client_log = Path(server_dir).parent / \
            f"client_{Path(server_dir).name}.log"

        # Build the far end's command sequence.
        setup_lines = []
        if DEBUG_LOOPBACK:
            setup_lines.append(f"log debug {server_log}")
        setup_lines.append("set command more-prompting off")
        setup_lines.append("set delay 0")
        if transport != "pseudoterminal":
            setup_lines.append("set tcp reverse-dns-lookup off")
        if use_clear_unprefix:
            setup_lines.append("set clear-channel on")
            setup_lines.append("set control unprefix all")
        setup_lines.append(f"cd {server_dir}")
        if server_setup_cmds:
            setup_lines.extend(take_file_lines(server_setup_cmds))
        setup_lines.append("server")

        if isinstance(client_commands, list):
            cmd_str = ", ".join(client_commands)
        else:
            cmd_str = client_commands

        client_prefix = (
            "set clear-channel on, set control unprefix all, "
            if use_clear_unprefix else ""
        )
        client_debug_prefix = (
            f"log debug {client_log}, " if DEBUG_LOOPBACK else ""
        )

        run = _run_pseudoterminal if transport == "pseudoterminal" \
            else _run_tcp
        result = run(server_dir, setup_lines, cmd_str, client_prefix,
                    client_debug_prefix, server_log, client_log, timeout)

        if DEBUG_LOOPBACK:
            for label, log_path in (("Server", server_log),
                                    ("Client", client_log)):
                if log_path.exists():
                    try:
                        logger.info(
                            "wermit_loopback: %s process debug log:\n%s",
                            label,
                            tail_text(log_path, f"{label} debug log"))
                    except Exception as e:
                        logger.warning(
                            "wermit_loopback: Failed to read %s log %s: %s",
                            label, log_path, e)

        return result

    yield _run

    for fh in opened_logs:
        try:
            fh.close()
        except OSError:
            pass

    # Clean up temporary server scripts/logs. Server processes
    # themselves are torn down by spawn_wermit's teardown.
    for path in created_files:
        try:
            if path.exists():
                logger.info("wermit_loopback: Cleaning up %s", path)
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
def server_dir(tmp_path):
    """A "server" subdirectory under tmp_path for tests that run a
    wermit server (via wermit_tcp_loopback or wermit_loopback) with
    its own cwd separate from the client's."""
    d = tmp_path / "server"
    d.mkdir()
    return d


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
            if it hasn't already, and returns its exit code."""
            return _wait_or_kill(self.server_proc, timeout=timeout)

    def _setup(server_dir, protocol=None, setup_cmds="", ready_timeout=10):
        server_log_path = Path(server_dir).parent / \
            f"tcp_server_{Path(server_dir).name}.log"

        proto_switch = f" /{protocol}" if protocol else ""
        setup_prefix = f"{setup_cmds}, " if setup_cmds else ""

        for attempt in range(PORT_COLLISION_RETRIES):
            port = get_free_port()
            server_cmd = [
                "--unbuffered", "-H", "-Y", "-C",
                "set command more-prompting off, "
                "set tcp reverse-dns-lookup off, "
                f"cd {server_dir}, {setup_prefix}"
                f"set host /server * {port}{proto_switch}"
            ]

            logger.info(
                "wermit_tcp_loopback: Starting server on port %d: %s",
                port, server_cmd)
            server_log_fh = open(server_log_path, "w")
            opened_logs.append(server_log_fh)
            created_files.append(server_log_path)
            proc = spawn_wermit(server_cmd, stdout=server_log_fh)
            try:
                _wait_for_tcp_listener(
                    proc, server_log_path, server_log_fh,
                    "wermit_tcp_loopback", timeout=ready_timeout)
                break
            except PortCollisionError:
                if attempt == PORT_COLLISION_RETRIES - 1:
                    raise
                logger.info(
                    "wermit_tcp_loopback: port %d raced, retrying", port)
                _wait_or_kill(proc, timeout=1)

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
# with its console (stdin/stdout/stderr) attached to a real
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
        logger.info(
            "%s: wermit debug log:\n%s",
            label, tail_text(path, "wermit debug log"))
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


def finish_wermit_pty_pair(proc_a, master_a, proc_b, master_b, timeout=45):
    """
    Like finish_wermit_pty(), but drains two wermit ptys concurrently
    instead of one after the other, returning
    ((returncode_a, stdout_a), (returncode_b, stdout_b)).

    Draining one side to completion before starting the other assumes
    both finish at about the same time.
    """
    entries = {master_a: (proc_a, []), master_b: (proc_b, [])}
    open_masters = set(entries)
    start_time = time.time()

    while open_masters:
        if time.time() - start_time > timeout:
            for master, (proc, output) in entries.items():
                captured = b"".join(output).decode('utf-8', errors='replace')
                logger.error(
                    "finish_wermit_pty_pair: wermit (pid %d) timed out "
                    "after %ds. pty output captured before timeout:\n%s",
                    proc.pid, timeout, truncated("pty output", captured))
            _log_process_snapshot("finish_wermit_pty_pair")
            for proc, _ in entries.values():
                if proc.poll() is None:
                    proc.terminate()
            for proc, _ in entries.values():
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            for master in open_masters:
                os.close(master)
            raise RuntimeError(
                "finish_wermit_pty_pair: timed out after %ds" % timeout)

        r, _, _ = select.select(list(open_masters), [], [], 0.1)
        for master in r:
            proc, output = entries[master]
            try:
                data = os.read(master, 4096)
            except OSError:
                data = b""
            if not data:
                open_masters.discard(master)
                os.close(master)
                continue
            output.append(data)

    for proc, _ in entries.values():
        proc.wait()

    return tuple(
        (proc.returncode, b"".join(output).decode('utf-8', errors='replace'))
        for proc, output in entries.values())


def run_wermit_pty(wermit_path, cmd_str, cwd, timeout=45, debug_log=None):
    """
    Runs kermit with its stdin, stdout, and stderr connected to a real
    pseudoterminal slave, waiting for it to finish and returning
    (returncode, stdout).

    This is because, by default, when kermit sets up a host connection
    over a pseudoterminal, it runs ckutio.c:ttptycmd(). If kermit's
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
    accumulated output or timeout runs out. Returns (buf, found).
    buf is everything read (so callers can prepend it to
    later-captured output), and found is whether marker actually
    appeared before the timeout ran out or the process closed the
    pty.
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
                return buf, True
    return buf, False


def _openssl(*args):
    # stdin is explicitly closed off and a timeout is set so that a
    # misconfigured invocation that might prompt interactivel6 fails fast with a
    # clear "openssl timed out" error tied to this fixture, instead of hanging
    # forever reading from a stdin nothing will ever write to.
    #
    # check=False plus assert_ok (rather than check=True) so a failure
    # shows openssl's actual stdout and stderr.
    result = subprocess.run(["openssl", *args], check=False,
                             capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=30)
    assert_ok(result, label=f"openssl {' '.join(args)}")


def _make_ca(d, name, subj):
    """Self-signed CA: returns (key_path, crt_path)."""
    key = d / f"{name}.key"
    crt = d / f"{name}.crt"
    _openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes",
              "-keyout", str(key), "-out", str(crt), "-days", "2",
              "-subj", subj)
    return key, crt


def _make_leaf(d, name, subj, ca_key, ca_crt, san=None, dates=None):
    """
    Leaf cert signed by the given CA: returns (key_path, crt_path).
    san adds a subjectAltName extension. dates is an optional
    (not_before, not_after) pair of [CC]YYMMDDHHMMSSZ strings, used to
    mint an already-expired certificate.
    """
    key = d / f"{name}.key"
    csr = d / f"{name}.csr"
    crt = d / f"{name}.crt"
    _openssl("req", "-newkey", "rsa:2048", "-nodes",
              "-keyout", str(key), "-out", str(csr), "-subj", subj)
    args = ["x509", "-req", "-in", str(csr), "-CA", str(ca_crt),
            "-CAkey", str(ca_key), "-CAcreateserial", "-out", str(crt)]
    if dates:
        not_before, not_after = dates
        args += ["-not_before", not_before, "-not_after", not_after]
    else:
        args += ["-days", "2"]
    if san:
        ext_cnf = d / f"{name}_ext.cnf"
        ext_cnf.write_text(f"subjectAltName={san}\n")
        args += ["-extfile", str(ext_cnf)]
    _openssl(*args)
    return key, crt


@pytest.fixture(scope="session")
def ssl_pki(tmp_path_factory):
    """
    Generates a small PKI (via the openssl CLI) for exercising direct
    kermit-to-kermit /SSL and /TLS connections:
      - a trusted CA, and a server cert/key signed by it
        (CN=SAN=localhost)
      - a client cert/key signed by the trusted CA, for mutual-TLS tests
      - a second, untrusted CA, and a "localhost" server cert/key signed
        by it instead of the trusted CA, for "wrong CA" negative tests
      - an already-expired server cert/key signed by the trusted CA

    The server certs' CN/SAN is "localhost". Tests must connect to
    that hostname, not an IP address, to avoid C-Kermit's interactive
    hostname-mismatch confirmation prompt.
    """
    if shutil.which("openssl") is None:
        pytest.skip("openssl CLI not found on PATH")
    d = tmp_path_factory.mktemp("ssl_pki")

    ca_key, ca_crt = _make_ca(d, "ca", "/CN=Test CA")
    server_key, server_crt = _make_leaf(
        d, "server", "/CN=localhost", ca_key, ca_crt,
        san="DNS:localhost"
    )
    client_key, client_crt = _make_leaf(
        d, "client", "/CN=test-client", ca_key, ca_crt
    )

    untrusted_ca_key, untrusted_ca_crt = _make_ca(
        d, "untrusted_ca", "/CN=Untrusted CA"
    )
    untrusted_server_key, untrusted_server_crt = _make_leaf(
        d, "untrusted_server", "/CN=localhost",
        untrusted_ca_key, untrusted_ca_crt, san="DNS:localhost"
    )

    expired_key, expired_crt = _make_leaf(
        d, "expired", "/CN=localhost", ca_key, ca_crt,
        san="DNS:localhost",
        dates=("20190101000000Z", "20200101000000Z")
    )

    return {
        "ca_crt": ca_crt,
        "ca_key": ca_key,
        "server_crt": server_crt,
        "server_key": server_key,
        "client_crt": client_crt,
        "client_key": client_key,
        "untrusted_ca_crt": untrusted_ca_crt,
        "untrusted_ca_key": untrusted_ca_key,
        "untrusted_server_crt": untrusted_server_crt,
        "untrusted_server_key": untrusted_server_key,
        "expired_crt": expired_crt,
        "expired_key": expired_key,
    }


@pytest.fixture(params=["pty", "tcp-raw", "tcp-telnet"],
                ids=["pty", "tcp-raw", "tcp-telnet"])
def zmodem_remote(request, wermit_path, get_free_port, spawn_wermit):
    """
    Provides a way to run the wermit-under-test (Zmodem tests' local side)
    against a rz/sz remote, parameterized over three ways of reaching it:

    - "pty": the far end of SET HOST /NETWORK-TYPE:PSEUDOTERMINAL is a second
      wermit process, not rz/sz directly.

      The far-end wermit is exec'd with a script and no explicit SET LINE or SET
      HOST; a wermit invoked this way (as the target of another process's SET
      HOST /NETWORK-TYPE:PSEUDOTERMINAL) treats its controlling tty (the pty
      slave it was exec'd onto) as its connection by default, so SET PROTOCOL
      ZMODEM plus SEND or RECEIVE runs directly over it with nothing else
      needed.

    - "tcp-raw"/"tcp-telnet": a second, plain wermit process (the remote)
      reaches the wermit-under-test over a real TCP/IP connection, using SET
      HOST's /RAW-SOCKET or /TELNET protocol-switch respectively. It doesn't use
      Kermit's SERVER mode.

      This matters for Zmodem in particular because rz/sz's binary data
      (including 0xFF bytes) is piped directly over the connection with no
      Kermit-level framing, so under "tcp-telnet" it depends entirely on the
      Telnet layer's IAC byte-stuffing and BINARY negotiation to survive intact.

      To actually run rz/sz, the remote uses SET PROTOCOL ZMODEM plus SEND or
      RECEIVE, which is Kermit's mechanism for redirecting an external protocol
      over the current connection.  It forks rz/sz onto a pty of its
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
    wermit-under-test's command string with a literal "{HOST}"
    placeholder standing in for the "set host" target.

    Returns (returncode, stdout) like run_wermit_pty. The
    callable also exposes zmodem_remote.mode ("pty" or "tcp") so
    callers can pad timeouts for the extra TCP connection setup.
    """
    param = request.param
    mode = "pty" if param == "pty" else "tcp"
    tcp_transport = None if param == "pty" else param.split("-", 1)[1]
    created_files = []

    def _remote_clause(remote_argv):
        """
        Translates remote_argv (["sz", path] to send that file, or
        ["rz"] to receive) into the SET PROTOCOL ZMODEM SEND/RECEIVE
        clause a remote wermit runs to do the same thing via its
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
            f"{ZMODEM_QUIET_PROTOCOL_CLAUSE}\n"
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
        switch = "raw-socket" if tcp_transport == "raw" else "telnet"
        telnet_prefix = telnet_minimal_options_prefix(tcp_transport)

        for attempt in range(PORT_COLLISION_RETRIES):
            port = get_free_port()
            full_cmd_str = telnet_prefix + cmd_str.format(
                HOST=f"* {port} /{switch}")

            # Start the wermit-under-test first; it's the TCP
            # listener, so it must be listening before the remote
            # side tries to connect.
            proc, master = start_wermit_pty(
                wermit_path, full_cmd_str, cwd, debug_log)
            prefix, ready = _wait_for_pty_marker(
                master, b"Waiting to Accept", timeout=10)
            if ready:
                break

            bind_failed = PORT_BIND_FAILURE_MARKER.encode() in prefix
            os.close(master)
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except (subprocess.TimeoutExpired, OSError):
                proc.kill()
                proc.wait(timeout=2)
            if not bind_failed or attempt == PORT_COLLISION_RETRIES - 1:
                raise RuntimeError(
                    "zmodem_remote: wermit-under-test did not start "
                    "listening; pty output:\n"
                    f"{prefix.decode('utf-8', errors='replace')}")
            logger.info("zmodem_remote: port %d raced, retrying", port)

        spawn_wermit(
            ["-H", "-Y", "-C",
             "set command more-prompting off, "
             "set tcp reverse-dns-lookup off, "
             f"{telnet_prefix}"
             f"{ZMODEM_QUIET_PROTOCOL_CLAUSE}, "
             f"set host localhost {port} /{switch}, "
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

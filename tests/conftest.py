import errno
import fcntl
import os
import pty
import re
import select
import shlex
import shutil
import socket
import subprocess
import termios
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

# A Kermit client sends the far end's start string (KERMIT -X, -R or
# -IR) and then sleeps 400 ms before each transaction.  The far end in
# these tests already runs SERVER or RECEIVE.  So test clients turn
# the start string off.  9.0.302 lacks this command.
PROTOCOL_STARTUP_OFF = "set protocol startup-string off"

# After connecting, each end of a /TELNET or /SSL session waits for
# Telnet negotiation replies.  With nothing outstanding, the wait
# lasts until a 1 s read timeout.  With the wait off, both ends still
# negotiate.  Replies are handled as they arrive among the packets.
TELNET_WAIT_OFF = "set telnet wait-for-negotiations off"

# Extra seconds padded onto client-side timeouts for any real-TCP transport
# beyond what a pty needs.  Leaves headroom if necessary for real TCP connection
# setup/teardown.  I'm not convinced this is necessary though.
TCP_TIMEOUT_MARGIN = 15

# The hang limits in this suite (subprocess timeouts, pty and listener
# waits, and the pytest-timeout limit) are sized for a fast machine.
# scaled() multiplies a limit by the factor in this environment
# variable.  When it is unset, pytest_configure() measures wermit
# against CALIBRATION_REFERENCE and sets it.  xdist workers inherit it.
# Elapsed-time assertions do not use the factor.  Each bound is smaller
# than the stall that it detects.
TIMEOUT_SCALE_ENV = "KERMIT_TEST_TIMEOUT_SCALE"
CALIBRATION_CMD = "for \\%i 1 2000 1 { .x := \\%i }, exit"
CALIBRATION_REFERENCE = 0.055       # seconds on a 2026 x86 machine
TIMEOUT_SCALE_MAX = 20


def calibrate_timeout_scale(wermit):
    """Return the timeout factor for this machine.

    wermit runs CALIBRATION_CMD five times.  Divide the best time by
    CALIBRATION_REFERENCE and clamp the result to the range 1 to
    TIMEOUT_SCALE_MAX.
    """
    best = None
    for _ in range(5):
        start = time.monotonic()
        subprocess.run([wermit, "-H", "-Y", "-C", CALIBRATION_CMD],
                       stdin=subprocess.DEVNULL, capture_output=True,
                       timeout=600)
        took = time.monotonic() - start
        best = took if best is None else min(best, took)
    return min(max(best / CALIBRATION_REFERENCE, 1.0), TIMEOUT_SCALE_MAX)


def timeout_scale():
    """Return the factor from KERMIT_TEST_TIMEOUT_SCALE, or 1."""
    try:
        scale = float(os.environ.get(TIMEOUT_SCALE_ENV, "1"))
    except ValueError:
        return 1.0
    return scale if scale > 0 else 1.0


def scaled(seconds):
    """Return the hang limit seconds multiplied by timeout_scale()."""
    return seconds * timeout_scale()


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """Set the timeout factor and apply it to pytest-timeout.

    This runs after pytest-timeout reads its setting.  A limit given by
    --timeout or PYTEST_TIMEOUT stays as given.
    """
    if TIMEOUT_SCALE_ENV not in os.environ:
        wermit = Path(__file__).parent.parent / "wermit"
        scale = calibrate_timeout_scale(str(wermit)) \
            if wermit.exists() else 1.0
        os.environ[TIMEOUT_SCALE_ENV] = f"{scale:.2f}"
    if (getattr(config, "_env_timeout", None)
            and config.getvalue("timeout") is None
            and "PYTEST_TIMEOUT" not in os.environ):
        config._env_timeout *= timeout_scale()


def pytest_report_header(config):
    """Show the timeout factor in the session header."""
    return f"kermit timeout scale: {timeout_scale():.2f}"


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


TELNET_REFUSE_KERMIT_CLAUSE = (
    "set telopt /client kermit refused, "
    "set telopt /server kermit refused"
)


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


def require_tls_version(ssl_pki, version):
    """Skip the test unless this Python can handshake at version.

    version names an ssl.TLSVersion member such as "TLSv1_1".  Both ends
    allow only that version at security level 0.  LibreSSL 3.8 and later
    have no TLS 1.0 or 1.1 and fail the handshake.
    """
    import ssl
    import threading
    tls_version = getattr(ssl.TLSVersion, version)
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client_ctx.check_hostname = False
    client_ctx.verify_mode = ssl.CERT_NONE
    try:
        server_ctx.load_cert_chain(ssl_pki["server_crt"],
                                   ssl_pki["server_key"])
        for ctx in (server_ctx, client_ctx):
            ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
            ctx.minimum_version = tls_version
            ctx.maximum_version = tls_version
    except (ValueError, ssl.SSLError) as e:
        pytest.skip(f"this Python cannot use only {version}: {e}")
    server_sock, client_sock = socket.socketpair()
    server_sock.settimeout(10)
    client_sock.settimeout(10)
    errors = []

    def serve():
        try:
            with server_ctx.wrap_socket(server_sock,
                                        server_side=True):
                pass
        except (OSError, ssl.SSLError) as e:
            errors.append(e)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        with client_ctx.wrap_socket(client_sock):
            pass
    except (OSError, ssl.SSLError) as e:
        errors.append(e)
    finally:
        client_sock.close()
        thread.join(timeout=10)
        server_sock.close()
    if errors:
        pytest.skip(f"this Python cannot handshake at {version}: "
                    f"{errors[0]}")


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


# Maximum size in bytes for a live debug log capture. Only the trailing
# characters are read by tail_text(); 2MB provides sufficient margin
# while bounding disk usage across parallel test runs.
DEBUG_LOG_CAPTURE_BYTES = 2 * 1024 * 1024


def debug_log_capture_path(debug_log):
    """Return the .tail path written on disk for a logical debug_log path.

    Debug traces are captured through a size-bounded tail during
    execution. Callers inspect this capture path instead of the logical
    path.
    """
    return Path(str(debug_log) + ".tail")


def _debug_log_tmp_path(capture_path):
    """Return the in-progress path debug_log_command() writes to before
    renaming it to its final capture_path."""
    return Path(str(capture_path) + ".partial")


def _track_debug_log_files(created_files, log_path):
    """Register log_path's capture file and in-progress temporary file
    with created_files for cleanup."""
    capture_path = debug_log_capture_path(log_path)
    for path in (capture_path, _debug_log_tmp_path(capture_path)):
        if path not in created_files:
            created_files.append(path)


def debug_log_command(debug_log):
    """Return Kermit commands to start a timestamped debug log piped
    through a size-bounded tail.

    Uses Kermit's "log debug |command" syntax. Enclosing braces prevent
    filename truncation on spaces.

    tail buffers input until EOF, then writes trailing bytes to a
    temporary path before renaming it to the final capture path. The
    atomic rename allows consumers to check for file existence rather
    than polling file size.

    Traps SIGHUP so tail is unaffected by PTY process group
    termination. Does not exec, since the shell must survive tail to
    execute the rename.

    Prefixes with "set debug timestamps on" so each line carries a
    millisecond timestamp.
    """
    capture_path = debug_log_capture_path(debug_log)
    tmp_path = _debug_log_tmp_path(capture_path)
    return (
        "set debug timestamps on, "
        f"log debug {{|trap '' HUP; "
        f"tail -c {DEBUG_LOG_CAPTURE_BYTES} > {tmp_path} && "
        f"mv {tmp_path} {capture_path}}}"
    )


def tail_text(path, label, max_chars=MAX_LOGGED_CHARS):
    """Return at most the last max_chars characters of a file, seeking
    near the end of the file rather than reading it in full."""
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


def make_deep_dir(base):
    """Create and return a directory whose path is about 70% of PATH_MAX.

    Its path is more than half of PATH_MAX, so a buffer of PATH_MAX
    bytes cannot hold it twice.  Each component is 200 bytes.
    """
    path_max = os.pathconf(str(base), "PC_PATH_MAX")
    count = (path_max * 7 // 10 - len(str(base))) // 201
    deep = base.joinpath(*(["d" * 200] * max(count, 1)))
    deep.mkdir(parents=True)
    return deep


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
PORT_COLLISION_RETRIES = 8

# ckermit's message when SET HOST's bind() fails, checked in a spawned
# listener's captured output to distinguish a port race failure
# from some other startup failure.
#
PORT_BIND_FAILURE_MARKER = "Unable to bind to socket"

# ckermit's message when SET HOST * cannot bind the IPv6 socket because the
# port is in use.  The IPv4 socket is already bound, so the server still
# prints "Waiting to Accept", but a client connecting to "localhost" tries ::1
# first and reaches whatever else holds that port.  So this is also treated
# as a port collision.
PORT_BIND6_FAILURE_MARKER = (
    f"Unable to bind IPv6 socket (errno = {errno.EADDRINUSE})"
)


def port_collided(output):
    """Return True if listener output shows the port was taken, on
    either the IPv4 or the IPv6 socket."""
    return (PORT_BIND_FAILURE_MARKER in output
            or PORT_BIND6_FAILURE_MARKER in output)

# ckermit's message when a TCP server's tn_wait() finds the connection it just
# accepted already gone.  Checked server's captured stdout to recognize the
# other half of the same get_free_port() race PORT_BIND_FAILURE_MARKER covers:
# the bind succeeds, but a stray leftover connection from something else lands
# in the listener's single accept() ahead of the real client, which is never
# consumed from the accept() backlog.  See _run_tcp's use of this for the
# resulting client-side timeout.
STRAY_CONNECTION_MARKER = "Connection closed by peer"


class PortCollisionError(RuntimeError):
    """Raised by _wait_for_tcp_listener when the spawned listener's
    output satisfies port_collided(): get_free_port()'s
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
    deadline = time.monotonic() + scaled(timeout)
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        log_fh.flush()
        content = log_path.read_text(errors="replace")
        if "Waiting to Accept" in content:
            break
        time.sleep(0.05)

    log_fh.flush()
    content = log_path.read_text(errors="replace")
    if port_collided(content):
        raise PortCollisionError(
            f"{label}: port raced by another process; log:\n{content}"
        )
    if "Waiting to Accept" in content:
        return
    raise RuntimeError(
        f"{label}: server did not start listening "
        f"(exit={proc.poll()}); log:\n{content}"
    )


def _wait_or_kill(proc, timeout=5):
    """Waits for proc to exit, escalating to terminate() then kill()
    if it doesn't exit by itself. Returns its exit code."""
    try:
        proc.wait(timeout=scaled(timeout))
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=scaled(2))
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=scaled(2))
    return proc.returncode


def retry_on_port_collision(get_free_port, label, attempt):
    """
    Calls attempt(port) with a fresh port from get_free_port() until
    it returns without raising PortCollisionError, at most
    PORT_COLLISION_RETRIES times.  The last PortCollisionError, and
    any other exception, propagates.  attempt must release whatever
    it started before raising PortCollisionError.

    Returns (port, attempt's return value).
    """
    for n in range(PORT_COLLISION_RETRIES):
        port = get_free_port()
        try:
            return port, attempt(port)
        except PortCollisionError:
            if n == PORT_COLLISION_RETRIES - 1:
                raise
            logger.info("%s: port %d raced, retrying", label, port)
    raise AssertionError("unreachable")


def spawn_tcp_listener(spawn_wermit, args, log_path, label,
                       binary_path=None, timeout=10):
    """
    Spawns a wermit TCP listener with its output in log_path and
    waits for it to be ready.  Returns (proc, log_fh); the caller
    closes log_fh.

    On PortCollisionError the listener is stopped and log_fh closed
    before the exception propagates, as retry_on_port_collision()
    requires.
    """
    log_fh = open(log_path, "w")
    proc = spawn_wermit(args, stdout=log_fh, binary_path=binary_path)
    try:
        _wait_for_tcp_listener(proc, log_path, log_fh, label,
                               timeout=timeout)
    except PortCollisionError:
        log_fh.close()
        _wait_or_kill(proc, timeout=1)
        raise
    except BaseException:
        log_fh.close()
        raise
    return proc, log_fh


def start_tcp_listener(spawn_wermit, get_free_port, args_for_port,
                       log_path, label, binary_path=None, timeout=10):
    """
    Spawns a wermit TCP listener on a free port, retrying on port
    collisions.  args_for_port(port) returns the wermit arguments.
    Returns (port, proc, log_fh); the caller closes log_fh.
    """
    port, (proc, log_fh) = retry_on_port_collision(
        get_free_port, label,
        lambda port: spawn_tcp_listener(
            spawn_wermit, args_for_port(port), log_path, label,
            binary_path=binary_path, timeout=timeout))
    return port, proc, log_fh


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


@pytest.fixture(scope="session")
def wermit_sanitized(wermit_path):
    """Return True if wermit was built with AddressSanitizer or UBSan.

    valgrind, address-space limits and LD_PRELOAD libraries do not
    work with a sanitizer runtime.
    """
    with open(wermit_path, "rb") as f:
        data = f.read()
    return b"__asan_init" in data or b"__ubsan_handle" in data


@pytest.fixture
def valgrind(wermit_sanitized):
    """Return the path to valgrind, or skip the test.

    Skips if valgrind is not installed or wermit has a sanitizer.
    """
    import shutil
    path = shutil.which("valgrind")
    if not path:
        pytest.skip("valgrind not installed")
    if wermit_sanitized:
        pytest.skip("valgrind does not run a sanitizer build")
    return path


def _optional_binary_path(name):
    """Return absolute path to a repository-root compatibility binary.

    Skip the test if the binary is not present.
    """
    path = Path(__file__).parent.parent / name
    if not path.exists():
        pytest.skip(f"{name} binary not present at {path}")
    return str(path.absolute())


@pytest.fixture(scope="session")
def gkermit_path():
    """Return path to G-Kermit binary for compatibility tests."""
    return _optional_binary_path("gkermit")


@pytest.fixture(scope="session")
def eksw_path():
    """Return path to E-Kermit binary for compatibility tests."""
    return _optional_binary_path("eksw")


@pytest.fixture(scope="session")
def ckermit_old_path():
    """Return path to C-Kermit 9.0.302 binary for compatibility tests."""
    return _optional_binary_path("ckermit-old-9.0.302")


@pytest.fixture(scope="session")
def wermit_ssl_available(wermit_path):
    """
    True if the wermit binary under test was compiled with SSL/TLS
    support.
    """
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-C",
         "set command more-prompting off, "
         "if not available ssl exit 89, exit 0"],
        capture_output=True, text=True, timeout=scaled(10)
    )
    return result.returncode != 89


@pytest.fixture(scope="session")
def wermit_ftp_available(wermit_path):
    """
    True if the wermit binary under test was compiled with FTP client
    support, i.e. not built with -DNOFTP.

    There is no "IF AVAILABLE FTP" command (AVAILABLE only covers
    authentication types), so this instead greps SHOW FEATURES'
    compiled-options list for the "NOFTP" token that shofea() in
    ckuus5.c prints only when NOFTP was defined at compile time.
    """
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-C",
         "set command more-prompting off, show features, exit"],
        capture_output=True, text=True, timeout=scaled(10)
    )
    return not re.search(r"\bNOFTP\b", result.stdout)


@pytest.fixture(scope="session")
def wermit_http_available(wermit_path):
    """
    True if the wermit binary under test was compiled with HTTP client
    support. Checks SHOW FEATURES output for the NOHTTP token.
    """
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-C",
         "set command more-prompting off, show features, exit"],
        capture_output=True, text=True, timeout=scaled(10)
    )
    return not re.search(r"\bNOHTTP\b", result.stdout)


@pytest.fixture
def run_wermit(wermit_path):
    """
    Synchronously runs a wermit command or script, returning a CompletedProcess.
    Can accept a list of arguments or a string command (executed via -C).

    wermit runs in a new session with no controlling terminal.  Otherwise
    SEND, GET, and similar commands with no connection open /dev/tty and
    exchange packets with the terminal pytest was started from.
    """
    def _run(args, input_data=None, timeout=10, pre_timeout_callback=None):
        """Run wermit and return a CompletedProcess.

        If pre_timeout_callback is specified, invoke it 2 seconds before
        the hard timeout (or immediately if timeout <= 2) to capture live
        state before termination.
        """
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
        timeout = scaled(timeout)
        t_start = time.perf_counter()
        if pre_timeout_callback is None:
            result = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout,
                start_new_session=True
            )
        else:
            proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE if input_data else None,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                start_new_session=True)
            snapshot_at = max(timeout - 2, 0)
            try:
                stdout, stderr = proc.communicate(
                    input=input_data, timeout=snapshot_at)
                result = subprocess.CompletedProcess(
                    cmd, proc.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                pre_timeout_callback()
                try:
                    stdout, stderr = proc.communicate(
                        timeout=timeout - snapshot_at)
                    result = subprocess.CompletedProcess(
                        cmd, proc.returncode, stdout, stderr)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                    raise subprocess.TimeoutExpired(
                        cmd, timeout, output=stdout, stderr=stderr)
        logger.info("run_wermit: Process completed with exit code %d in %.4f seconds",
                    result.returncode, time.perf_counter() - t_start)
        return result
    return _run


@pytest.fixture(params=["pseudoterminal"])
def loopback_transport(request):
    """Return the transport for wermit_loopback's client and server.

    Supported values are "pseudoterminal", "raw-socket", "telnet",
    "ssl", "ssl-telnet", and "tls-telnet".  The SSL and TLS transports
    use a CA-trusted certificate from the ssl_pki fixture and skip if
    openssl is not on PATH.  "ssl-telnet" and "tls-telnet" negotiate
    Telnet at the start of the connection.

    Test modules that need TCP, telnet, or SSL coverage override this
    fixture locally.  Other modules use "pseudoterminal" only.
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

    The returned callable accepts an optional server_binary_path
    parameter, defaulting to wermit_path. Passing another binary
    runs the server side with that executable for compatibility
    testing.

    The returned callable accepts an optional telnet_wait flag
    (default False).  For the telnet and ssl transports, False turns
    off SET TELNET WAIT-FOR-NEGOTIATIONS on both ends.  True keeps the
    default wait.

    The returned callable accepts an optional server_debug_log flag
    (default False). When True, forces the server debug log on
    unconditionally via debug_log_command(), independent of
    KERMIT_TEST_DEBUG_LOOPBACK. Use server_debug_log instead of putting
    a "log debug" command in server_setup_cmds.
    """
    created_files = []
    opened_logs = []
    use_clear_unprefix = request.param
    transport = loopback_transport

    def _run_pseudoterminal(server_dir, setup_lines, cmd_str,
                            client_prefix, client_debug_prefix,
                            server_log, client_log, timeout,
                            server_binary_path, debug_server,
                            telnet_wait):
        server_ksc = Path(server_dir).parent / \
            f"server_{Path(server_dir).name}.ksc"
        logger.info(
            "wermit_loopback: Creating server script %s", server_ksc)
        logger.debug("wermit_loopback: Server script content:\n%s",
                     "\n".join(setup_lines))
        server_ksc.write_text("\n".join(setup_lines) + "\n")
        if server_ksc not in created_files:
            created_files.append(server_ksc)
        if debug_server:
            _track_debug_log_files(created_files, server_log)
        if DEBUG_LOOPBACK:
            _track_debug_log_files(created_files, client_log)

        full_client_cmd = [
            "-H", "-Y", "-Q", "-C",
            f"{client_debug_prefix}set command more-prompting off, "
            f"{PROTOCOL_STARTUP_OFF}, "
            f"set delay 0, set host /network-type:pseudoterminal "
            f"{server_binary_path} {server_ksc.absolute()}, set delay 0, "
            f"{client_prefix}{cmd_str}, close, exit"
        ]
        logger.info(
            "wermit_loopback: Client running command sequence: %s",
            cmd_str)
        return run_wermit(full_client_cmd, timeout=timeout)

    def _tcp_switch_and_prefixes(transport, telnet_wait):

        """Returns (switch, server_prefix, client_prefix) for a TCP-based
        transport: the SET HOST protocol-switch name, and any commands each side
        must run before SET HOST.  raw-socket needs neither; telnet needs the
        same refusals on both ends; ssl needs asymmetric certificate setup
        pulled from the ssl_pki fixture, fetched lazily so only tests that
        actually pick "ssl" pay for generating it (or get skipped if openssl
        isn't available).
        """

        wait = "" if telnet_wait else f"{TELNET_WAIT_OFF}, "
        if transport in ("ssl-telnet", "tls-telnet"):
            # These negotiate Telnet in full.  Keep the wait.
            wait = ""
        if transport in ("ssl", "ssl-telnet", "tls-telnet"):
            ssl_pki = request.getfixturevalue("ssl_pki")
            return (transport,
                    f"{wait}{ssl_server_setup_cmds(ssl_pki)}, ",
                    f"{wait}{ssl_client_setup_cmds(ssl_pki)}, ")
        prefix = telnet_minimal_options_prefix(transport)
        if transport == "telnet":
            prefix = wait + prefix
        return transport, prefix, prefix

    def _run_tcp(server_dir, setup_lines, cmd_str, client_prefix,
                client_debug_prefix, server_log, client_log, timeout,
                server_binary_path, debug_server, telnet_wait):
        switch, server_prefix, client_extra_prefix = \
            _tcp_switch_and_prefixes(transport, telnet_wait)
        server_stdout_log = Path(server_dir).parent / \
            f"tcp_server_{Path(server_dir).name}.log"
        if server_stdout_log not in created_files:
            created_files.append(server_stdout_log)
        if debug_server:
            _track_debug_log_files(created_files, server_log)
        if DEBUG_LOOPBACK:
            _track_debug_log_files(created_files, client_log)

        server_cmd_str = ", ".join(setup_lines)

        def attempt(port):
            server_full_cmd = [
                "--unbuffered", "-H", "-Y", "-C",
                f"{server_prefix}set host * {port} /{switch}, "
                f"{server_cmd_str}"
            ]
            logger.info(
                "wermit_loopback: Starting server on port %d: %s",
                port, server_full_cmd)
            proc, server_log_fh = spawn_tcp_listener(
                spawn_wermit, server_full_cmd, server_stdout_log,
                "wermit_loopback", binary_path=server_binary_path)
            opened_logs.append(server_log_fh)

            full_client_cmd = [
                "-H", "-Y", "-Q", "-C",
                f"{client_debug_prefix}set command more-prompting off, "
                f"{PROTOCOL_STARTUP_OFF}, "
                "set delay 0, set tcp reverse-dns-lookup off, "
                f"{client_extra_prefix}set host localhost {port} "
                f"/{switch}, "
                f"if failure exit {SSL_CONNECT_FAILURE_CODE}, "
                f"set delay 0, {client_prefix}{cmd_str}, close, exit"
            ]
            logger.info(
                "wermit_loopback: Client running command sequence: %s",
                cmd_str)
            try:
                try:
                    return run_wermit(
                        full_client_cmd,
                        timeout=timeout + TCP_TIMEOUT_MARGIN,
                        pre_timeout_callback=lambda: _log_socket_snapshot(
                            "wermit_loopback: client about to time out",
                            port))
                except subprocess.TimeoutExpired as e:
                    # If some other process's connection lands on this
                    # listener's single accept() before this test's
                    # client does, the server gives up immediately.
                    # The client's connect() has already completed at
                    # the TCP level, so it waits for protocol data
                    # until this timeout.  STRAY_CONNECTION_MARKER in
                    # the server's stdout is that server-side give-up.
                    # So it is retried as a port collision.
                    stray = (
                        server_stdout_log.exists() and
                        STRAY_CONNECTION_MARKER in
                        server_stdout_log.read_text(errors="replace"))
                    if not stray:
                        raise
                    raise PortCollisionError(
                        f"wermit_loopback: port {port}'s listener "
                        "accepted a stray connection") from e
            finally:
                # Always drain server stdout. Post-transfer assertions
                # may fail even when the client process exits 0.
                _wait_or_kill(proc)
                if server_stdout_log.exists():
                    try:
                        logger.info(
                            "wermit_loopback: Server stdout log:\n%s",
                            tail_text(
                                server_stdout_log, "Server stdout log"))
                    except OSError as e:
                        logger.warning(
                            "wermit_loopback: Failed to read server "
                            "stdout log %s: %s", server_stdout_log, e)

        _, result = retry_on_port_collision(
            get_free_port, "wermit_loopback", attempt)
        return result

    def _run(server_dir, server_setup_cmds="", client_commands="",
             timeout=10, server_binary_path=None, server_debug_log=False,
             telnet_wait=False):
        # Target paths for debug logs. Written only if DEBUG_LOOPBACK
        # or server_debug_log is enabled. Distinct from _run_tcp stdout logs.
        server_log = Path(server_dir).parent / \
            f"server_{Path(server_dir).name}.log"
        client_log = Path(server_dir).parent / \
            f"client_{Path(server_dir).name}.log"

        # server_debug_log enables the server debug log independently of
        # DEBUG_LOOPBACK using debug_log_command(). Do not embed a "log debug"
        # command in server_setup_cmds; debopn() closes any existing debug log
        # before opening a new one, which can terminate the server process
        # during connection setup.
        debug_server = DEBUG_LOOPBACK or server_debug_log

        # Build the far end's command sequence. Split debug_log_command()
        # into separate commands for TAKE file compatibility in
        # pseudoterminal mode.
        setup_lines = []
        if debug_server:
            setup_lines.extend(take_file_lines(debug_log_command(server_log)))
        setup_lines.append("set command more-prompting off")
        if server_binary_path in (None, wermit_path):
            # The far end acts as a client when server_setup_cmds
            # runs REMOTE commands before SERVER.
            setup_lines.append(PROTOCOL_STARTUP_OFF)
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
            f"{debug_log_command(client_log)}, " if DEBUG_LOOPBACK else ""
        )

        run = _run_pseudoterminal if transport == "pseudoterminal" \
            else _run_tcp
        result = None
        try:
            result = run(server_dir, setup_lines, cmd_str, client_prefix,
                        client_debug_prefix, server_log, client_log, timeout,
                        server_binary_path or wermit_path, debug_server,
                        telnet_wait)
        finally:
            # Dump debug logs on failure or timeout. The server log is
            # dumped if debug_server is True. The client log is dumped if
            # DEBUG_LOOPBACK is True.
            failed = result is None or result.returncode != 0
            logs = []
            if failed and DEBUG_LOOPBACK:
                logs.append(("Client", client_log))
            if failed and debug_server:
                logs.append(("Server", server_log))
            for label, log_path in logs:
                capture_path = debug_log_capture_path(log_path)
                try:
                    if _wait_for_debug_log_ready(capture_path):
                        logger.info(
                            "wermit_loopback: %s process debug "
                            "log:\n%s",
                            label,
                            tail_text(capture_path, f"{label} debug log"))
                    else:
                        logger.warning(
                            "wermit_loopback: %s debug log %s "
                            "never appeared", label, capture_path)
                except Exception as e:
                    logger.warning(
                        "wermit_loopback: Failed to read %s "
                        "log %s: %s", label, capture_path, e)

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

    The port must be free on both 127.0.0.1 and ::1, since SET HOST *
    listens on both and clients resolving "localhost" may try either.
    If IPv6 is unavailable, only 127.0.0.1 is checked.
    """
    def _v6_free(port):
        try:
            s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        except OSError:
            return True
        try:
            s.bind(("::1", port))
        except OSError as e:
            return e.errno != errno.EADDRINUSE
        finally:
            s.close()
        return True

    def _get_port():
        while True:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
            s.close()
            if _v6_free(port):
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

    An optional binary_path parameter overrides wermit_path to spawn
    an alternate Kermit binary.
    """
    processes = []

    def _spawn(args, cwd=None, stdout=None, binary_path=None):
        cmd = [binary_path or wermit_path] + args
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
                proc.wait(timeout=scaled(2))
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=scaled(2))


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
                       setup_cmds="", timeout=10, host="localhost"):
            """
            Connects a client to the loopback server and runs the given
            commands. protocol, if given ("ssl" or "tls"), is appended
            as a /SSL or /TLS protocol-switch to SET HOST. setup_cmds
            are run before SET HOST (e.g. to configure client-side
            certificate/verification parameters). host is the name
            or address given to SET HOST. Note: unlike
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
                f"{PROTOCOL_STARTUP_OFF}, "
                "set tcp reverse-dns-lookup off, "
                f"{setup_prefix}"
                f"set host {host} {self.port}{proto_switch}, "
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
            return run_wermit(
                full_client_cmd, timeout=timeout + TCP_TIMEOUT_MARGIN)

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

        def server_cmd(port):
            cmd = [
                "--unbuffered", "-H", "-Y", "-C",
                "set command more-prompting off, "
                f"{PROTOCOL_STARTUP_OFF}, "
                "set tcp reverse-dns-lookup off, "
                f"cd {server_dir}, {setup_prefix}"
                f"set host /server * {port}{proto_switch}"
            ]
            logger.info(
                "wermit_tcp_loopback: Starting server on port %d: %s",
                port, cmd)
            return cmd

        created_files.append(server_log_path)
        port, proc, server_log_fh = start_tcp_listener(
            spawn_wermit, get_free_port, server_cmd, server_log_path,
            "wermit_tcp_loopback", timeout=ready_timeout)
        opened_logs.append(server_log_fh)

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

def _wait_for_debug_log_ready(path, timeout=2.0, poll=0.05):
    """Wait for a debug log capture file to appear at path.

    Returns True if the file appears before timeout, False otherwise.

    The tail writer runs in a background process spawned by Kermit.
    Because debug_log_command() atomically renames the temporary output
    file to path once complete, existence indicates that the capture is
    finished.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            return True
        time.sleep(poll)
    return path.exists()


def _log_debug_file(label, path):
    path = debug_log_capture_path(path)
    if not _wait_for_debug_log_ready(path):
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


def _log_socket_snapshot(label, port):
    """Log socket and process state for port.

    Runs netstat to record whether the TCP connection reached ESTABLISHED
    or remained in SYN_SENT.

    Also invokes _log_process_snapshot to record running processes.
    """
    try:
        ns = subprocess.run(
            ["netstat", "-an"], capture_output=True, text=True, timeout=5)
        # BSD netstat uses '.' as port delimiter (127.0.0.1.41000); Linux
        # uses ':' (127.0.0.1:41000). Match either delimiter and require a
        # trailing non-digit or end-of-line to avoid prefix matches.
        port_re = re.compile(rf"[.:]{port}(\D|$)")
        relevant = "\n".join(
            line for line in ns.stdout.splitlines() if port_re.search(line)
        )
        logger.info(
            "%s: socket snapshot for port %d:\n%s", label, port, relevant)
    except Exception as e:
        logger.warning(
            "%s: failed to capture socket snapshot: %s", label, e)
    _log_process_snapshot(label)


def _make_controlling_tty():
    """
    Makes the pty slave this process's controlling terminal. Without
    this, the child stays a member of the parent Python process's
    session with no controlling terminal, which on OpenBSD in
    particular silently disables tty-dependent behavior instead of
    erroring: conbgt() (ckutio.c) misreads it as running in the
    background and suppresses prompts entirely, and curses fullscreen
    mode (SET FILE DISPLAY FULLSCREEN) never paints anything.
    """
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


def start_wermit_pty(wermit_path, cmd_str, cwd, debug_log=None):
    """
    Starts a wermit process with its stdin/stdout/stderr connected to a
    real pseudoterminal slave, which is also made its controlling
    terminal (see _make_controlling_tty()), without waiting for it to
    finish. Returns (proc, master).  Pass both to finish_wermit_pty()
    to collect its output and exit code.
    """
    master, slave = pty.openpty()

    debug_prefix = f"{debug_log_command(debug_log)}, " if debug_log else ""
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
        close_fds=True,
        preexec_fn=_make_controlling_tty
    )

    os.close(slave)
    return proc, master


def finish_wermit_pty(proc, master, timeout=45, debug_log=None):
    """
    Reads a wermit process's pty output (started via start_wermit_pty)
    until it exits or the timeout fires, then returns
    (returncode, stdout).
    """
    timeout = scaled(timeout)
    output = []
    start_time = time.time()

    try:
        while proc.poll() is None:
            if time.time() - start_time > timeout:
                captured = b"".join(output).decode('utf-8', errors='replace')
                logger.error(
                    "finish_wermit_pty: wermit (pid %d) timed out after "
                    "%ds. pty output captured before timeout:\n%s",
                    proc.pid, timeout, truncated("pty output", captured))
                _log_process_snapshot("finish_wermit_pty")
                proc.terminate()
                try:
                    proc.wait(timeout=scaled(2))
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=scaled(2))
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

        # Log the debug trace on failure.
        if debug_log and proc.returncode != 0:
            _log_debug_file("finish_wermit_pty", debug_log)

        return (proc.returncode,
                b"".join(output).decode('utf-8', errors='replace'))
    finally:
        # Remove the debug log capture and any incomplete temporary file
        # on exit.
        if debug_log:
            capture_path = debug_log_capture_path(debug_log)
            capture_path.unlink(missing_ok=True)
            _debug_log_tmp_path(capture_path).unlink(missing_ok=True)


def finish_wermit_pty_pair(proc_a, master_a, proc_b, master_b, timeout=45):
    """
    Like finish_wermit_pty(), but drains two wermit ptys concurrently
    instead of one after the other, returning
    ((returncode_a, stdout_a), (returncode_b, stdout_b)).

    Draining one side to completion before starting the other assumes
    both finish at about the same time.
    """
    timeout = scaled(timeout)
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
                    proc.wait(timeout=scaled(2))
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=scaled(2))
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


def _wait_for_pty_raw(master, timeout):
    """Read from master until ISIG is off or timeout runs out.

    CONNECT turns ISIG off.  Keys typed while ISIG is on can be taken
    as signal characters, and the terminal driver then flushes pending
    input.  Return (buf, raw): buf is everything read, and raw is
    whether ISIG went off within timeout.
    """
    buf = b""
    deadline = time.time() + scaled(timeout)
    while time.time() < deadline:
        if not termios.tcgetattr(master)[3] & termios.ISIG:
            return buf, True
        r, _, _ = select.select([master], [], [], 0.05)
        if master in r:
            try:
                data = os.read(master, 4096)
            except OSError:
                break
            if not data:
                break
            buf += data
    return buf, False


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
    deadline = time.time() + scaled(timeout)
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


# The interactive prompt of wermit -H -Y ends with this.
PROMPT = b"C-Kermit>"


def read_pty_until(master, buf, markers, timeout):
    """Read from a pty master onto buf until buf holds one of markers.

    markers is a tuple of bytes.  An empty tuple reads whatever arrives
    within timeout.  The read also ends when timeout runs out or the
    pty closes.  Return buf with the data appended.
    """
    end = time.monotonic() + scaled(timeout)
    while not any(m in buf for m in markers):
        left = end - time.monotonic()
        if left <= 0 or not select.select([master], [], [], left)[0]:
            break
        try:
            data = os.read(master, 65536)
        except OSError:
            break
        if not data:
            break
        buf += data
    return buf


def start_pty_tcp_listener(wermit_path, get_free_port, cmd_for_port, cwd,
                           label, debug_log=None, timeout=10):
    """
    Starts a wermit TCP listener on a pty via start_wermit_pty(),
    using a free port and retrying on port collisions.
    cmd_for_port(port) returns the command string.

    Returns (port, proc, master, prefix).  prefix is the pty output
    read up to "Waiting to Accept", for callers to prepend to the
    output they collect later.
    """
    def attempt(port):
        proc, master = start_wermit_pty(
            wermit_path, cmd_for_port(port), cwd, debug_log)
        prefix, ready = _wait_for_pty_marker(
            master, b"Waiting to Accept", timeout=timeout)
        text = prefix.decode("utf-8", errors="replace")
        collided = port_collided(text)
        if ready and not collided:
            return proc, master, prefix

        os.close(master)
        try:
            proc.terminate()
            proc.wait(timeout=scaled(2))
        except (subprocess.TimeoutExpired, OSError):
            proc.kill()
            proc.wait(timeout=scaled(2))
        if collided:
            raise PortCollisionError(
                f"{label}: port raced by another process; "
                f"pty output:\n{text}")
        raise RuntimeError(
            f"{label}: wermit did not start listening; "
            f"pty output:\n{text}")

    port, (proc, master, prefix) = retry_on_port_collision(
        get_free_port, label, attempt)
    return port, proc, master, prefix


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
                             stdin=subprocess.DEVNULL,
                             timeout=scaled(30))
    assert_ok(result, label=f"openssl {' '.join(args)}")


def _key_args(d, name, key):
    """Return (key_path, openssl req arguments) for a certificate.

    With key, the certificate uses that existing key.  Without it,
    openssl generates a new RSA key at d/name.key.
    """
    if key:
        return key, ["-new", "-key", str(key)]
    path = d / f"{name}.key"
    return path, ["-newkey", "rsa:2048", "-nodes", "-keyout", str(path)]


def _make_ca(d, name, subj, san=None, key=None):
    """Create a self-signed certificate and return (key_path, crt_path).

    san is an optional subjectAltName extension value.  key is an
    existing key to use instead of a new one.
    """
    key, key_args = _key_args(d, name, key)
    crt = d / f"{name}.crt"
    args = ["req", "-x509", *key_args, "-out", str(crt), "-days", "2",
            "-subj", subj]
    if san:
        args += ["-addext", f"subjectAltName={san}"]
    _openssl(*args)
    return key, crt


def _make_leaf(d, name, subj, ca_key, ca_crt, san=None, dates=None,
               key=None):
    """Create a leaf certificate signed by the given CA.

    Return (key_path, crt_path).  san adds a subjectAltName extension.
    dates is an optional (not_before, not_after) pair of
    [CC]YYMMDDHHMMSSZ strings for an expired certificate.  key is an
    existing key to use instead of a new one.
    """
    key, key_args = _key_args(d, name, key)
    csr = d / f"{name}.csr"
    crt = d / f"{name}.crt"
    _openssl("req", *key_args, "-out", str(csr), "-subj", subj)

    ext_cnf = None
    if san:
        ext_cnf = d / f"{name}_ext.cnf"
        ext_cnf.write_text(f"subjectAltName={san}\n")

    if dates:
        crt = _sign_with_dates(d, name, csr, ca_key, ca_crt, dates,
                                ext_cnf)
    else:
        # The serial file goes in d.  Next to a shared CA certificate,
        # concurrent xdist workers would write it at once.
        args = ["x509", "-req", "-in", str(csr), "-CA", str(ca_crt),
                "-CAkey", str(ca_key), "-CAcreateserial",
                "-CAserial", str(d / f"{name}.srl"),
                "-out", str(crt), "-days", "2"]
        if ext_cnf:
            args += ["-extfile", str(ext_cnf)]
        _openssl(*args)
    return key, crt


def _sign_with_dates(d, name, csr, ca_key, ca_crt, dates, ext_cnf):
    """
    Signs csr with an explicit (not_before, not_after) validity
    period, returning the crt path. "openssl x509 -req"'s
    -not_before/-not_after options are too new to rely on in CI
    (added in OpenSSL 3.1; some runners still ship 3.0.x). "openssl
    ca" has taken explicit -startdate/-enddate values since long
    before OpenSSL 3.0, so use that instead. It needs a CA database
    (index.txt/serial), scoped to this call and started empty so
    unique_subject never rejects reusing a subject across leaves.
    """
    crt = d / f"{name}.crt"
    not_before, not_after = dates
    capki = d / f"{name}_capki"
    capki.mkdir()
    index = capki / "index.txt"
    serial = capki / "serial"
    index.write_text("")
    serial.write_text("1000\n")
    ca_cnf = capki / "ca.cnf"
    ca_cnf.write_text(
        "[ca]\n"
        "default_ca = CA_default\n"
        "[CA_default]\n"
        f"database = {index}\n"
        f"serial = {serial}\n"
        f"new_certs_dir = {capki}\n"
        f"certificate = {ca_crt}\n"
        f"private_key = {ca_key}\n"
        "default_md = sha256\n"
        "policy = policy_anything\n"
        "email_in_dn = no\n"
        "unique_subject = no\n"
        "[policy_anything]\n"
        "commonName = supplied\n"
    )
    args = ["ca", "-batch", "-config", str(ca_cnf), "-in", str(csr),
            "-out", str(crt), "-startdate", not_before,
            "-enddate", not_after]
    if ext_cnf:
        args += ["-extfile", str(ext_cnf)]
    _openssl(*args)
    return crt


@pytest.fixture(scope="session")
def ssl_pki(tmp_path_factory, wermit_ssl_available):
    """
    Generates a small PKI (via the openssl CLI) for exercising direct
    kermit-to-kermit /SSL and /TLS connections:
      - a trusted CA, and a server cert/key signed by it
        (CN=SAN=localhost)
      - a client cert/key signed by the trusted CA, for mutual-TLS tests
      - a second, untrusted CA, and a "localhost" server cert/key signed
        by it instead of the trusted CA, for "wrong CA" negative tests
      - an already-expired server cert/key signed by the trusted CA
      - a self-signed "localhost" server cert/key (not signed by either
        CA above), for testing self-signed leaf verification separately
        from the untrusted-CA path
      - a server cert/key signed by the trusted CA whose only
        subjectAltNames are IP addresses, including 127.0.0.1

    The server certs' CN/SAN is "localhost". Tests must connect to
    that hostname, not an IP address, to avoid C-Kermit's interactive
    hostname-mismatch confirmation prompt.

    The PKI has three RSA keys: one per CA, and one that every leaf
    and the self-signed certificate share.  The tests check certificate
    fields and signatures, not key uniqueness.  RSA key generation
    takes about 5 s on a 599 MHz Alpha.  Under xdist the workers share
    one PKI in the run's base directory.  A lock file serializes its
    creation.
    """
    if not wermit_ssl_available:
        pytest.skip("wermit was not built with SSL/TLS support")
    if shutil.which("openssl") is None:
        pytest.skip("openssl CLI not found on PATH")
    root = tmp_path_factory.getbasetemp()
    if os.environ.get("PYTEST_XDIST_WORKER"):
        root = root.parent
    d = root / "ssl_pki"
    with open(root / "ssl_pki.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not (d / "done").exists():
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir()
            _make_pki(d)
            (d / "done").write_text("")
    return _pki_paths(d)


def _pki_paths(d):
    """Return the ssl_pki dictionary for the PKI in directory d."""
    paths = {}
    for name in ("ca", "server", "client", "untrusted_ca",
                 "untrusted_server", "expired", "selfsigned_server",
                 "ip_server"):
        paths[f"{name}_crt"] = d / f"{name}.crt"
        paths[f"{name}_key"] = d / "leaf.key"
    paths["ca_key"] = d / "ca.key"
    paths["untrusted_ca_key"] = d / "untrusted_ca.key"
    return paths


def _make_pki(d):
    """Create the ssl_pki certificates and keys in directory d."""
    ca_key, ca_crt = _make_ca(d, "ca", "/CN=Test CA")
    untrusted_ca_key, untrusted_ca_crt = _make_ca(
        d, "untrusted_ca", "/CN=Untrusted CA")
    leaf_key = d / "leaf.key"
    _openssl("genrsa", "-out", str(leaf_key), "2048")
    _make_leaf(d, "server", "/CN=localhost", ca_key, ca_crt,
               san="DNS:localhost", key=leaf_key)
    _make_leaf(d, "client", "/CN=test-client", ca_key, ca_crt,
               key=leaf_key)
    _make_leaf(d, "untrusted_server", "/CN=localhost",
               untrusted_ca_key, untrusted_ca_crt, san="DNS:localhost",
               key=leaf_key)
    _make_leaf(d, "expired", "/CN=localhost", ca_key, ca_crt,
               san="DNS:localhost",
               dates=("20190101000000Z", "20200101000000Z"), key=leaf_key)
    _make_ca(d, "selfsigned_server", "/CN=localhost", san="DNS:localhost",
             key=leaf_key)
    _make_leaf(d, "ip_server", "/CN=ip-server", ca_key, ca_crt,
               san="IP:192.168.255.254,IP:::1,IP:127.0.0.1", key=leaf_key)


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

        # Start the wermit-under-test first; it's the TCP listener,
        # so it must be listening before the remote side tries to
        # connect.
        port, proc, master, prefix = start_pty_tcp_listener(
            wermit_path, get_free_port,
            lambda port: telnet_prefix + cmd_str.format(
                HOST=f"* {port} /{switch}"),
            cwd, "zmodem_remote", debug_log=debug_log)

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


@pytest.fixture
def foreign_kermit_pty(wermit_path):
    """Run wermit against an external binary over a pseudoterminal.

    Used for compatibility testing with Kermit implementations that run
    over stdin/stdout without SERVER mode support.

    Return a callable with signature:
        foreign_kermit_pty(peer_argv, cmd_str, cwd, timeout=45,
                           debug_log=None)

    peer_argv is the external binary argument list. cmd_str is the
    wermit command string containing a literal "{HOST}" placeholder for
    the SET HOST target. Return tuple (returncode, stdout).

    The "{HOST}" placeholder is replaced via str.replace() rather than
    str.format() to preserve literal braces in Kermit commands.
    """
    def _run(peer_argv, cmd_str, cwd, timeout=45, debug_log=None):
        host = ("/network-type:pseudoterminal "
                + " ".join(shlex.quote(str(a)) for a in peer_argv))
        full_cmd_str = (f"{PROTOCOL_STARTUP_OFF}, "
                        + cmd_str.replace("{HOST}", host))
        return run_wermit_pty(wermit_path, full_cmd_str, cwd,
                              timeout=timeout, debug_log=debug_log)
    return _run


IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240
TTYPE, NEW_ENVIRON, START_TLS = 24, 39, 46


class TlsBioSocket:
    """TLS over a connected socket through memory BIOs.

    The handshake starts in the constructor.  first, when given, goes
    out in the same send as the ClientHello.
    """

    def __init__(self, ctx, sock, first=b""):
        import ssl
        self.raw = sock
        self.inc = ssl.MemoryBIO()
        self.out = ssl.MemoryBIO()
        self.obj = ctx.wrap_bio(self.inc, self.out)
        try:
            self.obj.do_handshake()
            done = True
        except ssl.SSLWantReadError:
            done = False
        self.raw.sendall(first + self.out.read())
        while not done:
            try:
                self.obj.do_handshake()
                done = True
            except ssl.SSLWantReadError:
                # In TLS 1.2 the client's last flight goes out before
                # the server's Finished arrives.  Send it before the
                # read or both sides wait.
                self._flush()
                self._fill()
            self._flush()

    def _flush(self):
        if self.out.pending:
            self.raw.sendall(self.out.read())

    def _fill(self):
        got = self.raw.recv(4096)
        if not got:
            raise ConnectionError("connection closed in TLS")
        self.inc.write(got)

    def sendall(self, b):
        self.obj.write(b)
        self._flush()

    def recv(self, n):
        import ssl
        while True:
            try:
                return self.obj.read(n)
            except ssl.SSLWantReadError:
                self._flush()
                try:
                    self._fill()
                except ConnectionError:
                    return b""
            except ssl.SSLZeroReturnError:
                return b""

    def settimeout(self, t):
        self.raw.settimeout(t)

    def close(self):
        self.raw.close()


class TelnetTlsClient:
    """Telnet client that runs START_TLS with a client certificate.

    It agrees to START_TLS, NEW-ENVIRON and TTYPE and refuses other
    options.  It sends its SB START_TLS FOLLOWS and the ClientHello in
    one send, and sets tls when the handshake completes.  It answers
    SB NEW-ENVIRON SEND with each name in users as a USER variable,
    in order.  It collects the data the server sends outside Telnet
    commands.
    """

    def __init__(self, port, ssl_pki, users):
        import ssl
        self.sock = socket.create_connection(("127.0.0.1", port),
                                             timeout=scaled(15))
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        self.ctx.check_hostname = False
        self.ctx.load_verify_locations(ssl_pki["ca_crt"])
        self.ctx.load_cert_chain(ssl_pki["client_crt"],
                                 ssl_pki["client_key"])
        self.users = users
        self.data = b""
        self.buf = b""
        self.tls = False

    def _send(self, b):
        self.sock.sendall(bytes(b))

    def _sb(self, opt, body):
        self._send([IAC, SB, opt] + list(body) + [IAC, SE])

    def _handle_sb(self, body):
        if not body:
            return
        opt = body[0]
        if opt == START_TLS and body[1:2] == b"\x01":
            self.sock = TlsBioSocket(
                self.ctx, self.sock,
                bytes([IAC, SB, START_TLS, 1, IAC, SE]))
            self.tls = True
        elif opt == NEW_ENVIRON and body[1:2] == b"\x01":
            reply = [0]
            for user in self.users:
                reply += [0] + list(b"USER") + [1] + list(user.encode())
            self._sb(NEW_ENVIRON, reply)
        elif opt == TTYPE and body[1:2] == b"\x01":
            self._sb(TTYPE, [0] + list(b"VT100"))

    def _parse(self):
        """Handle the complete commands in self.buf."""
        b = self.buf
        i = 0
        while i < len(b):
            if b[i] != IAC:
                self.data += b[i:i + 1]
                i += 1
                continue
            if i + 1 >= len(b):
                break
            cmd = b[i + 1]
            if cmd == IAC:
                self.data += b"\xff"
                i += 2
            elif cmd in (DO, DONT, WILL, WONT):
                if i + 2 >= len(b):
                    break
                opt = b[i + 2]
                if cmd == DO:
                    ok = opt in (START_TLS, NEW_ENVIRON, TTYPE)
                    self._send([IAC, WILL if ok else WONT, opt])
                elif cmd == WILL:
                    self._send([IAC, DO if opt in (0, 1, 3) else DONT,
                                opt])
                i += 3
            elif cmd == SB:
                end = b.find(bytes([IAC, SE]), i + 2)
                if end < 0:
                    break
                i, body = end + 2, b[i + 2:end]
                self.buf = b[i:]
                self._handle_sb(body)
                return True
            else:
                i += 2
        self.buf = b[i:]
        return False

    def _wait(self, done, timeout):
        """Read and handle input until done() returns True."""
        deadline = time.monotonic() + scaled(timeout)
        while True:
            # A START_TLS switch must not read past the handshake.
            while self._parse():
                pass
            if done():
                break
            if time.monotonic() > deadline:
                break
            self.sock.settimeout(max(0.1, deadline - time.monotonic()))
            try:
                got = self.sock.recv(4096)
            except OSError:
                break
            if not got:
                break
            self.buf += got

    def expect(self, until, timeout=20):
        """Read until any byte string in until appears in new data.

        Returns the data read since the last call.
        """
        start = len(self.data)
        self._wait(lambda: any(u in self.data[start:] for u in until),
                   timeout)
        return self.data[start:].decode("latin-1")

    def wait_tls(self, timeout=20):
        """Read until the TLS handshake completes.  Returns tls."""
        self._wait(lambda: self.tls, timeout)
        return self.tls

    def send_line(self, text):
        """Send text and a carriage return as Telnet data."""
        self._send(list(text.encode()) + [13, 0])

    def run(self, until, timeout=20):
        """Read until any byte string in until appears, then close."""
        self.expect(until, timeout)
        self.sock.close()
        return self.data.decode("latin-1")

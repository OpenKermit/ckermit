"""
Tests for how ENABLE/DISABLE CD, ENABLE/DISABLE MKDIR, and SET RECEIVE
PATHNAMES interact when a recursive transfer places files with
directory components in their names.  See doc/permissions.md for the
narrative explanation these tests back up.

Three connection types matter here, because ENABLED() (ckcker.h)
decides CD/MKDIR access from both the "local" flag and, for
TCPSOCKET builds, a second "tcp_incoming" flag:

  - "pseudoterminal" (wermit_loopback default): the server is spawned
    as a child process over a pty, exactly like a user who logged in
    some other way and typed "kermit" by hand.  local=0.
  - "raw-socket"/"telnet" (wermit_loopback, transport override): the
    server itself does "SET HOST * port" and accepts the incoming
    connection with the SET HOST-derived listener code
    This sets local=1 *and* tcp_incoming=1,
    and those two cancel out in ENABLED()'s formula, leaving the
    REMOTE bit in control - the same as pty.
  - "adopted" (this module's fixture): the server is handed an
    already-connected socket via -F, the way inetd (or an IKSD-style
    internet service) hands a daemon its client connection.  This
    sets local=1 but *not* tcp_incoming, so the LOCAL bit is what
    controls CD/MKDIR access here - the opposite of the other two
    shapes, and the reason ENABLE CD's default (REMOTE) denies
    embedded pathnames for this connection shape while allowing them
    for the other two.
"""
import os
import socket
import subprocess
import pytest
from conftest import (
    PORT_COLLISION_RETRIES,
    PortCollisionError,
    _wait_for_tcp_listener,
    _wait_or_kill,
    assert_ok,
)


@pytest.fixture(params=["pseudoterminal", "raw-socket", "telnet"])
def loopback_transport(request):
    """Overrides conftest's single-value default so tests in this
    module that use wermit_loopback also run over TCP raw and
    telnet, not just pseudoterminal."""
    return request.param


@pytest.fixture
def adopted_loopback(wermit_path, tmp_path):
    """
    Runs a wermit "server" over a socketpair handed to it via -F, the way inetd
    hands a daemon an already-accepted client connection, instead of the server
    calling SET HOST itself.

    Returns a callable: (server_ini_lines, server_action, client_commands,
    timeout=10) -> (server_result, client_result), where server_ini_lines is a
    list of commands run (via -y) before server_action ("-x" to enter SERVER
    state, or "" to run nothing further and just let the init file's commands do
    the work), and client_commands is a comma/newline-joined command string run
    by the client side.
    """
    def _run(server_ini_lines, server_action, client_commands,
             timeout=10):
        sa, sb = socket.socketpair()
        os.set_inheritable(sa.fileno(), True)
        os.set_inheritable(sb.fileno(), True)

        server_dir = tmp_path / "server"
        server_dir.mkdir(exist_ok=True)
        inifile = tmp_path / "adopted_server.ini"
        inifile.write_text(
            "set command more-prompting off\n"
            f"cd {server_dir}\n" +
            "\n".join(server_ini_lines) + "\n"
        )

        server_args = [wermit_path, "-H", "-y", str(inifile),
                        "-F", str(sb.fileno())]
        if server_action:
            server_args.append(server_action)
        server_proc = subprocess.Popen(
            server_args, pass_fds=(sb.fileno(),),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True, cwd=server_dir,
        )
        sb.close()

        if isinstance(client_commands, list):
            cmd_str = ", ".join(client_commands)
        else:
            cmd_str = client_commands

        client_args = [wermit_path, "-H", "-Y", "-Q",
                        "-F", str(sa.fileno()), "-C", cmd_str]
        try:
            client_result = subprocess.run(
                client_args, pass_fds=(sa.fileno(),),
                capture_output=True, text=True, timeout=timeout,
            )
        finally:
            sa.close()
            try:
                server_stdout, _ = server_proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                server_proc.kill()
                server_stdout, _ = server_proc.communicate()

        class _Result:
            def __init__(self, returncode, stdout):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = ""

        server_result = _Result(server_proc.returncode or 0,
                                 server_stdout)
        return server_result, client_result

    return _run


# ---------------------------------------------------------------------
# Which bit (LOCAL or REMOTE) controls CD/MKDIR access, per connection
# shape, is what the tests below actually prove, end to end, by
# checking whether a directory-carrying filename gets accepted, not
# by asking "local" or "tcp_incoming" directly: an early "IF LOCAL"
# probe run from the -y init file that configures each test's ENABLE
# settings was tried and dropped, since at that point the "adopted"
# fixture's -F connection has not been driven far enough for "local"
# to reflect its final value yet, even though it is correct by the
# time rcvfil()'s CD check runs later during the real transfer that
# follows. The acceptance/rejection pattern below is what that CD
# check actually sees, so it is the reliable signal for these tests.
#
# For a direct look at local/tcp_incoming/inserver themselves,
# post-connection where they do hold their final values, see the
# SHOW SERVER tests instead.
# ---------------------------------------------------------------------

def _write_payload_and_run(adopted_loopback, tmp_path, ini_lines,
                            as_name):
    payload = tmp_path / "sender_payload.txt"
    payload.write_text("payload data")
    server_result, client_result = adopted_loopback(
        ini_lines, "-x",
        [f"cd {tmp_path}", "set file type binary", "set delay 0",
         f"send /as-name:{as_name} sender_payload.txt",
         "close", "exit"],
        timeout=10)
    return server_result, client_result


@pytest.mark.parametrize("cd_setting,expect_accepted", [
    (None, False),              # default is REMOTE; LOCAL governs here
    ("enable cd local", True),
    ("enable cd both", True),
    ("enable cd remote", False),
    ("disable cd", False),
])
def test_cd_enable_state_governs_pathname_acceptance(
        adopted_loopback, tmp_path, cd_setting, expect_accepted):
    ini_lines = ["enable send both", "enable mkdir both"]
    if cd_setting:
        ini_lines.append(cd_setting)

    server_result, client_result = _write_payload_and_run(
        adopted_loopback, tmp_path, ini_lines, "subdir/probe.txt")

    dest = tmp_path / "server" / "subdir" / "probe.txt"
    assert dest.exists() == expect_accepted, (
        f"server stdout: {server_result.stdout}\n"
        f"client stdout: {client_result.stdout}"
    )


def test_mkdir_enable_required_independent_of_cd(adopted_loopback,
                                                  tmp_path):
    """Even with CD fully open, creating the subdirectories a
    recursive transfer needs also requires ENABLE MKDIR; without it,
    the transfer fails with "Directory creation failure" even though
    the filename itself was accepted."""
    ini_lines = ["enable send both", "enable cd both"]
    # Deliberately do NOT enable mkdir.

    server_result, client_result = _write_payload_and_run(
        adopted_loopback, tmp_path, ini_lines, "newsubdir/probe.txt")

    dest = tmp_path / "server" / "newsubdir" / "probe.txt"
    assert not dest.exists()
    assert "Directory creation failure" in client_result.stdout


def test_mkdir_enable_both_allows_recursive_directories(
        adopted_loopback, tmp_path):
    ini_lines = ["enable send both", "enable cd both", "enable mkdir both"]

    server_result, client_result = _write_payload_and_run(
        adopted_loopback, tmp_path, ini_lines, "newsubdir2/probe.txt")

    dest = tmp_path / "server" / "newsubdir2" / "probe.txt"
    assert dest.exists()
    assert dest.read_text() == "payload data"


# ---------------------------------------------------------------------
# RECEIVE PATHNAMES containment: RELATIVE must confine an accepted
# pathname to a descendant of the current directory, neutralizing
# both a leading "/" and any ".." component, on an ordinary client
# receive (no server/CD involvement at all).
# ---------------------------------------------------------------------

def test_receive_pathnames_relative_neutralizes_dotdot(
        tmp_path, wermit_loopback):
    """A crafted /AS-NAME with an embedded ".." must not let the
    file escape the receiving directory. Regression test for the
    hasdotdot() fix."""
    client_dir, server_dir = tmp_path / "client", tmp_path / "server"
    client_dir.mkdir()
    server_dir.mkdir()
    (client_dir / "payload.txt").write_text("payload data")

    # A canary that must NOT be overwritten if "../canary.txt"
    # (relative to server_dir, i.e. tmp_path/canary.txt) escapes.
    canary = tmp_path / "canary.txt"
    canary.write_text("original canary")

    result = wermit_loopback(
        server_dir,
        "set file type binary, set delay 0",
        f"set file type binary, set delay 0, cd {client_dir}, "
        "send /as-name:../canary.txt payload.txt")
    # The transfer is correctly *refused* (non-zero exit, "Access
    # denied"), not merely redirected: that is hasdotdot() doing its
    # job, so this is not a case for assert_ok.
    assert result.returncode != 0
    assert "Access denied" in result.stdout

    assert canary.read_text() == "original canary"
    assert not (server_dir / "canary.txt").exists()


def test_receive_pathnames_off_also_rejects_dotdot(
        tmp_path, wermit_loopback):
    """The "..' rejection is not something RELATIVE alone adds on top
    of OFF's plain stripping; it happens earlier and unconditionally
    (for every mode except ABSOLUTE), so OFF refuses the same crafted
    name rather than silently stripping it down to a safe basename."""
    client_dir, server_dir = tmp_path / "client", tmp_path / "server"
    client_dir.mkdir()
    server_dir.mkdir()
    (client_dir / "payload.txt").write_text("payload data")

    result = wermit_loopback(
        server_dir,
        "set receive pathnames off, set file type binary, set delay 0",
        f"set file type binary, set delay 0, cd {client_dir}, "
        "send /as-name:foo/../bar.txt payload.txt")
    assert result.returncode != 0
    assert "Access denied" in result.stdout
    assert not (server_dir / "bar.txt").exists()


def test_receive_pathnames_off_strips_ordinary_path(
        tmp_path, wermit_loopback):
    """Without a ".." to reject, OFF's actual job -- discarding any
    directory part, "/" included, and keeping only the base filename
    -- still works as documented."""
    client_dir, server_dir = tmp_path / "client", tmp_path / "server"
    client_dir.mkdir()
    server_dir.mkdir()
    (client_dir / "payload.txt").write_text("payload data")

    result = wermit_loopback(
        server_dir,
        "set receive pathnames off, set file type binary, set delay 0",
        f"set file type binary, set delay 0, cd {client_dir}, "
        "send /as-name:subdir/bar.txt payload.txt")
    assert_ok(result)

    assert (server_dir / "bar.txt").exists()
    assert not (server_dir / "subdir").exists()


def test_receive_pathnames_relative_neutralizes_leading_slash(
        tmp_path, wermit_loopback):
    """A crafted /AS-NAME that is absolute must be confined beneath
    the receiving directory, not honored literally."""
    client_dir, server_dir = tmp_path / "client", tmp_path / "server"
    client_dir.mkdir()
    server_dir.mkdir()
    (client_dir / "payload.txt").write_text("payload data")

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    canary = outside_dir / "canary.txt"
    canary.write_text("original canary")

    absolute_name = str(canary)
    assert absolute_name.startswith("/")

    result = wermit_loopback(
        server_dir,
        "set file type binary, set delay 0",
        f"set file type binary, set delay 0, cd {client_dir}, "
        f"send /as-name:{absolute_name} payload.txt")
    assert_ok(result)

    assert canary.read_text() == "original canary"


def test_receive_pathnames_absolute_honors_literal_path(
        tmp_path, wermit_loopback):
    """SET RECEIVE PATHNAMES ABSOLUTE is an explicit opt-in to trust
    the sender's absolute path; confirm it actually takes the literal
    path rather than confining it, using a target that stays safely
    inside tmp_path."""
    client_dir, server_dir = tmp_path / "client", tmp_path / "server"
    client_dir.mkdir()
    server_dir.mkdir()
    (client_dir / "payload.txt").write_text("payload data")

    target_dir = tmp_path / "absolute_target"
    target_dir.mkdir()
    target_file = target_dir / "landed.txt"
    absolute_name = str(target_file)

    result = wermit_loopback(
        server_dir,
        "set receive pathnames absolute, set file type binary, "
        "set delay 0",
        f"set file type binary, set delay 0, cd {client_dir}, "
        f"send /as-name:{absolute_name} payload.txt")
    assert_ok(result)

    assert target_file.exists()
    assert target_file.read_text() == "payload data"


# ---------------------------------------------------------------------
# GET /RECURSIVE: confirm it actually works end to end
# ---------------------------------------------------------------------

def test_get_recursive_descends_into_subdirectories(
        tmp_path, wermit_loopback):
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    nested = server_dir / "nested"
    nested.mkdir()
    (server_dir / "top.txt").write_text("top content")
    (nested / "deep.txt").write_text("deep content")

    client_dir = tmp_path / "client"
    client_dir.mkdir()

    result = wermit_loopback(
        server_dir,
        "set file type binary, set delay 0",
        f"set file type binary, set delay 0, cd {client_dir}, "
        "get /recursive *")
    assert_ok(result)

    got_top = client_dir / "top.txt"
    got_deep = client_dir / "nested" / "deep.txt"
    assert got_top.exists() and got_top.read_text() == "top content"
    assert got_deep.exists() and got_deep.read_text() == "deep content"


# ---------------------------------------------------------------------
# SHOW SERVER's Connection mode/Incoming TCP accept/Governing ENABLE
# bit lines against three of the four connection-shape
# table rows in doc/permissions.md. The fourth row (inserver, an
# actual IKSD) is not exercised here; see the module docstring.
# ---------------------------------------------------------------------

def test_show_server_reports_plain_process_as_remote(wermit_path):
    """A process with no connection at all: local=0, so REMOTE
    governs (this is degenerate compared to the doc's table, which
    starts from a connection having been made one way or another,
    but it is the state every process begins in)."""
    result = subprocess.run(
        [wermit_path, "-Y", "-Q", "-C", "show server"],
        capture_output=True, text=True, timeout=10,
    )
    assert_ok(result)
    assert "Connection mode:      Remote" in result.stdout
    assert "Incoming TCP accept:  No" in result.stdout
    assert "Governing ENABLE bit: REMOTE" in result.stdout
    assert "Internet server:      No" in result.stdout


def test_show_server_reports_set_host_star_as_remote(
        wermit_path, tmp_path, get_free_port, spawn_wermit):
    """Row 2 (a server that itself does SET HOST *, the way this
    project's raw-socket/telnet transports do): local=1 *and*
    tcp_incoming=1, so despite Connection mode reading Local, the
    Governing ENABLE bit is still REMOTE - the "technically local but
    logically remote" case ckcker.h's ENABLED() comment describes."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()

    for attempt in range(PORT_COLLISION_RETRIES):
        port = get_free_port()
        inifile = tmp_path / f"row2_server_{attempt}.ini"
        inifile.write_text(
            "set command more-prompting off\n"
            f"cd {server_dir}\n"
            f"set host * {port} /raw-socket\n"
            "show server\n"
            "close\n"
        )
        server_log = tmp_path / f"row2_server_{attempt}.log"
        server_log_fh = open(server_log, "w")
        server_proc = spawn_wermit(
            ["--unbuffered", "-H", "-y", str(inifile)],
            stdout=server_log_fh
        )
        try:
            _wait_for_tcp_listener(
                server_proc, server_log, server_log_fh, "show_server_row2"
            )
            break
        except PortCollisionError:
            server_log_fh.close()
            _wait_or_kill(server_proc, timeout=1)
            if attempt == PORT_COLLISION_RETRIES - 1:
                raise

    client_result = subprocess.run(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         "set tcp reverse-dns-lookup off, "
         f"set host localhost {port} /raw-socket, close, exit"],
        capture_output=True, text=True, timeout=10,
    )
    assert_ok(client_result)
    _wait_or_kill(server_proc, timeout=10)
    server_log_fh.close()
    server_out = server_log.read_text(errors="replace")

    assert "Connection mode:      Local" in server_out
    assert "Incoming TCP accept:  Yes" in server_out
    assert "Governing ENABLE bit: REMOTE" in server_out

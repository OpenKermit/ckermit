"""
KVM/Linux VSOCK tests (see doc/vsock.md).
"""
import socket
import time

import pytest
from conftest import assert_ok


def _show_features_output(run_wermit):
    result = run_wermit("show features")
    assert_ok(result, "SHOW FEATURES failed")
    return result.stdout


def _build_has_vsock(run_wermit):
    return "vsock" in _show_features_output(run_wermit).lower()


def _vsock_loopback_works():
    """
    Return True if a CID 1 (localhost) VSOCK connection actually succeeds.

    Socket creation alone only proves the af_vsock module is loaded.
    Connecting to CID 1 additionally requires the vsock_loopback
    transport, which some GitHub-hosted Ubuntu runners lack even
    though AF_VSOCK sockets can be created there, so probe the real
    connect path instead of just constructing a socket.
    """
    af_vsock = getattr(socket, "AF_VSOCK", None)
    if af_vsock is None:
        return False
    try:
        srv = socket.socket(af_vsock, socket.SOCK_STREAM)
    except OSError:
        return False
    try:
        srv.bind((socket.VMADDR_CID_ANY, socket.VMADDR_PORT_ANY))
        srv.listen(1)
        port = srv.getsockname()[1]
        try:
            cli = socket.socket(af_vsock, socket.SOCK_STREAM)
        except OSError:
            return False
        try:
            cli.settimeout(2)
            cli.connect((1, port))
        except OSError:
            return False
        finally:
            cli.close()
        return True
    except OSError:
        return False
    finally:
        srv.close()


@pytest.fixture
def vsock_available(run_wermit):
    """
    Skip test unless wermit was built with CK_VSOCK and CID 1 loopback works.
    """
    if not _build_has_vsock(run_wermit):
        pytest.skip("build has no VSOCK support (not CK_VSOCK)")
    if not _vsock_loopback_works():
        pytest.skip("this host does not support VSOCK CID 1 loopback")
    return True


def test_show_features_vsock_line_format(run_wermit):
    output = _show_features_output(run_wermit)
    if not _build_has_vsock(run_wermit):
        pytest.skip("build has no VSOCK support (not CK_VSOCK)")
    assert "KVM/Linux VSOCK support (AF_VSOCK)" in output


def test_set_network_type_vsock_selected(run_wermit):
    if not _build_has_vsock(run_wermit):
        pytest.skip("build has no VSOCK support (not CK_VSOCK)")
    result = run_wermit("set network type vsock, show network")
    assert_ok(result, "SET NETWORK TYPE VSOCK failed")
    assert "VSOCK" in result.stdout
    assert "KVM/Linux VSOCK (AF_VSOCK)" in result.stdout


def test_help_set_host_mentions_vsock(run_wermit):
    if not _build_has_vsock(run_wermit):
        pytest.skip("build has no VSOCK support (not CK_VSOCK)")
    result = run_wermit("help set host")
    assert_ok(result, "HELP SET HOST failed")
    assert "CID:PORT" in result.stdout
    assert "VSOCK loopback" in result.stdout


def test_help_set_host_mentions_vsock_server(run_wermit):
    if not _build_has_vsock(run_wermit):
        pytest.skip("build has no VSOCK support (not CK_VSOCK)")
    result = run_wermit("help set host")
    assert_ok(result, "HELP SET HOST failed")
    assert "listens for an incoming VSOCK" in result.stdout
    assert "port 1649" in result.stdout


def test_help_set_network_mentions_vsock(run_wermit):
    """
    Verify HELP SET NETWORK output includes VSOCK.
    """
    if not _build_has_vsock(run_wermit):
        pytest.skip("build has no VSOCK support (not CK_VSOCK)")
    result = run_wermit("help set network")
    assert_ok(result, "HELP SET NETWORK failed")
    assert "SET NETWORK TYPE VSOCK" in result.stdout


def test_set_host_invalid_vsock_address(run_wermit):
    """
    Verify invalid VSOCK addresses are rejected by SET HOST.
    """
    if not _build_has_vsock(run_wermit):
        pytest.skip("build has no VSOCK support (not CK_VSOCK)")
    for bad in ["bogus", "1", "1:2:3", ":9600", "1:"]:
        result = run_wermit(f"set network type vsock, set host {bad}")
        assert_ok(result, f"wermit should exit cleanly on bad address {bad}")
        assert f"Invalid VSOCK address: {bad}" in result.stderr, bad


def test_set_host_vsock_numeric_cid(run_wermit):
    """
    Verify SET HOST formats the numeric CID and port into the output.
    """
    if not _build_has_vsock(run_wermit):
        pytest.skip("build has no VSOCK support (not CK_VSOCK)")
    result = run_wermit("set network type vsock, set host 1:9999")
    assert_ok(result, "wermit should exit cleanly")
    assert "Trying 1:9999" in result.stdout


@pytest.mark.parametrize("cid_name,expect_cid", [
    ("local", 1),
    ("host", 2),
    ("hypervisor", 0),
    ("any", 4294967295),
    ("LOCAL", 1),           # symbolic names are case-insensitive
])
def test_set_host_vsock_symbolic_cid(run_wermit, cid_name, expect_cid):
    if not _build_has_vsock(run_wermit):
        pytest.skip("build has no VSOCK support (not CK_VSOCK)")
    result = run_wermit(f"set network type vsock, set host {cid_name}:9999")
    assert_ok(result, "wermit should exit cleanly")
    assert f"Trying {expect_cid}:9999" in result.stdout


def test_set_host_vsock_server_invalid_port(run_wermit):
    """
    Verify SET HOST *:port rejects invalid port strings.
    """
    if not _build_has_vsock(run_wermit):
        pytest.skip("build has no VSOCK support (not CK_VSOCK)")
    result = run_wermit("set network type vsock, set host *:bogus")
    assert_ok(result, "wermit should exit cleanly")
    assert "Invalid VSOCK port: bogus" in result.stderr


def test_set_host_vsock_server_accepts_connection(
    run_wermit, spawn_wermit, vsock_available, get_free_port
):
    """
    Test VSOCK server operation by connecting a client to wermit.
    """
    port = get_free_port()
    script = (
        "set command more-prompting off, set network type vsock, "
        f"set host *:{port}, if fail exit 1 ACCEPT-FAILED, "
        "input 5 PING, output PONG\\13, close connection, exit 0 DONE"
    )
    proc = spawn_wermit(["-H", "-Y", "-C", script])

    cli = None
    last_err = None
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            cli = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
            cli.settimeout(1)
            cli.connect((1, port))
            break
        except OSError as e:
            last_err = e
            if cli is not None:
                cli.close()
            cli = None
            time.sleep(0.2)
    assert cli is not None, f"could not connect to VSOCK server: {last_err}"

    cli.sendall(b"PING\r")
    cli.settimeout(5)
    reply = cli.recv(100)
    cli.close()

    out, _ = proc.communicate(timeout=10)
    assert "DONE" in out, out
    assert b"PONG" in reply


def test_set_host_vsock_connect_fails_cleanly(run_wermit, vsock_available):
    """
    Verify SET HOST to an unused VSOCK port fails cleanly.
    """
    result = run_wermit("set network type vsock, set host 1:59999")
    assert_ok(result, "SET HOST 1:59999 should fail cleanly, not crash")
    assert "Trying 1:59999" in result.stdout
    assert "Connected" not in result.stdout

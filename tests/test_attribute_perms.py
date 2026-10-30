"""
Tests for file permissions set from Attribute packets in zstime().

Each test sends a file with SET ATTRIBUTE DATE OFF, so the receiver
applies permissions without a date.
"""
import os
import stat


from conftest import assert_ok


def _send(tmp_path, wermit_loopback, mode, sender_cmds, server_cmds,
          existing_mode=None, server_binary_path=None):
    """Send a file of the given mode.  Return the received file's mode."""
    client_dir = tmp_path / "client"
    server_dir = tmp_path / "server"
    client_dir.mkdir()
    server_dir.mkdir()
    src = client_dir / "perm.txt"
    src.write_bytes(b"permissions\n")
    os.chmod(src, mode)
    dest = server_dir / "perm.txt"
    if existing_mode is not None:
        dest.write_bytes(b"old\n")
        os.chmod(dest, existing_mode)
    result = wermit_loopback(
        server_dir,
        f"set delay 0, {server_cmds}",
        f"set delay 0, set attribute date off, {sender_cmds}, send {src}",
        timeout=60, server_binary_path=server_binary_path)
    assert_ok(result)
    assert dest.read_bytes() == b"permissions\n"
    return stat.S_IMODE(dest.stat().st_mode)


def test_local_permissions_without_date(tmp_path, wermit_loopback):
    """Verify the sender's UNIX mode applies when no date is sent."""
    mode = _send(tmp_path, wermit_loopback, 0o604, "set file type binary",
                 "set file type binary")
    assert mode == 0o604, oct(mode)


def test_inherited_permissions_without_date(tmp_path, wermit_loopback):
    """Verify a backed-up file passes its mode on when no date is sent."""
    mode = _send(tmp_path, wermit_loopback, 0o644,
                 "set attribute protection off",
                 "set file collision backup", existing_mode=0o600)
    assert mode == 0o600, oct(mode)


def test_local_permissions_read_no_uninitialized_data(
        tmp_path, wermit_loopback, wermit_path, valgrind):
    """Verify zstime() reads no uninitialized data under valgrind."""
    vlog = tmp_path / "valgrind.log"
    wrapper = tmp_path / "vg-wermit"
    wrapper.write_text(f"#!/bin/sh\nexec {valgrind} -q "
                       f"--log-file={vlog} {wermit_path} \"$@\"\n")
    os.chmod(wrapper, 0o755)
    mode = _send(tmp_path, wermit_loopback, 0o604, "set file type binary",
                 "set file type binary", server_binary_path=wrapper)
    assert mode == 0o604, oct(mode)
    report = vlog.read_text() if vlog.exists() else ""
    assert "zstime" not in report, report

"""Tests for a sender's RESEND against the receiver's collision rules.

A RESEND asks the receiver to append to an existing file.  The receiver
honors it only after it requested a REGET or GET /RECOVER, or when its FILE
COLLISION setting already permits changing an existing file.
"""
from conftest import make_loopback_dirs


def _run_pair(run_wermit, wermit_path, sender_dir, receiver_dir,
              sender_cmds, receiver_cmds, timeout=30):
    """Run receiver_cmds locally against a sender over a pseudoterminal."""
    cmd = [
        "-H", "-Y", "-Q", "-C",
        "set command more-prompting off, set delay 0, "
        f"cd {receiver_dir}, "
        f"set host /network-type:pseudoterminal {wermit_path} -H -Y -Q -C "
        f"{{cd {sender_dir}, set file type binary, {sender_cmds}, quit}}, "
        f"{receiver_cmds}, echo STATUS=\\v(status), close, exit"
    ]
    return run_wermit(cmd, input_data="n\n", timeout=timeout)


def test_resend_refused_under_default_collision(tmp_path, run_wermit,
                                                wermit_path):
    """Verify a sender's RESEND does not append to an existing file."""
    receiver_dir, sender_dir = make_loopback_dirs(tmp_path)
    (receiver_dir / "target").write_bytes(b"orig\n")
    (sender_dir / "f").write_bytes(b"orig\nappended data\n")

    result = _run_pair(run_wermit, wermit_path, sender_dir, receiver_dir,
                       "resend /as-name:target f", "receive")

    assert (receiver_dir / "target").read_bytes() == b"orig\n", \
        result.stdout + result.stderr
    assert "STATUS=1" in result.stdout, result.stdout


def test_resend_appends_when_collision_overwrite(tmp_path, run_wermit,
                                                 wermit_path):
    """Verify RESEND still appends when the receiver permits changes."""
    receiver_dir, sender_dir = make_loopback_dirs(tmp_path)
    (receiver_dir / "target").write_bytes(b"orig\n")
    (sender_dir / "f").write_bytes(b"orig\nappended data\n")

    result = _run_pair(run_wermit, wermit_path, sender_dir, receiver_dir,
                       "resend /as-name:target f",
                       "set file collision overwrite, receive")

    assert (receiver_dir / "target").read_bytes() == \
        b"orig\nappended data\n", result.stdout + result.stderr
    assert "STATUS=0" in result.stdout, result.stdout


def test_reget_resumes_partial_file(tmp_path, run_wermit, wermit_path):
    """Verify a local REGET resumes a partial file under the defaults."""
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    data = bytes(range(256)) * 64
    (server_dir / "big.bin").write_bytes(data)
    (client_dir / "big.bin").write_bytes(data[:5000])

    result = _run_pair(run_wermit, wermit_path, server_dir, client_dir,
                       "server", "set file type binary, reget big.bin, "
                       "echo REGET=\\v(status), finish")

    assert "REGET=0" in result.stdout, result.stdout + result.stderr
    assert (client_dir / "big.bin").read_bytes() == data

"""
Tests that ENABLE ... LOCAL does not allow the service to a remote
client (ENABLED(), ckcker.h).
"""
import os
import stat
import subprocess


def test_enable_mail_local_refuses_remote_mail(wermit_path, tmp_path):
    """Verify a server with ENABLE MAIL LOCAL refuses SEND /MAIL.

    The server is the remote side of the connection, so a service
    enabled for local use only is disabled for it.  Fake Mail and
    mailx commands record any attempt to send mail.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    marker = tmp_path / "mailed"
    for name in ("Mail", "mailx", "mail"):
        fake = bindir / name
        fake.write_text(f"#!/bin/sh\ncat > /dev/null\ntouch {marker}\n")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    sdir = tmp_path / "s"
    sdir.mkdir()
    cdir = tmp_path / "c"
    cdir.mkdir()
    (cdir / "m.txt").write_text("hello\n")
    srv = tmp_path / "srv.ksc"
    srv.write_text(f"cd {sdir}\nset delay 0\nenable mail local\nserver\n")
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-Q", "-C",
         "set delay 0, set host /network-type:pseudoterminal "
         f"{wermit_path} {srv}, "
         "send /mail:nobody@example.invalid m.txt, "
         "echo M=\\v(status), finish, close, exit 0"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        cwd=cdir, env=env, timeout=60)
    assert "M=1" in result.stdout, result.stdout + result.stderr
    assert not marker.exists()

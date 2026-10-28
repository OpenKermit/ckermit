"""Tests of TCP_NODELAY during Telnet option negotiation.

tn_start() turns Nagle off while it sends options and reads replies.
It then restores the SET TCP NODELAY setting.  With Nagle on, each
small write after the first waits for the peer's delayed ACK (about
40 ms on Linux).
"""

import re

import pytest

from conftest import TELNET_REFUSE_KERMIT_CLAUSE, timeout_scale


def _server(wermit_tcp_loopback, server_dir):
    """Start a /TELNET Kermit server that refuses the Kermit option."""
    return wermit_tcp_loopback(server_dir, protocol="telnet",
                               setup_cmds=TELNET_REFUSE_KERMIT_CLAUSE)


def _client(session, setup, commands):
    """Run a /TELNET client against session with the setup commands.

    Both ends refuse the Kermit option.  The other options take their
    defaults.
    """
    return session.run_client(
        commands, protocol="telnet",
        setup_cmds=f"{TELNET_REFUSE_KERMIT_CLAUSE}, {setup}", timeout=20)


def test_telnet_negotiation_has_no_nagle_stall(server_dir,
                                              wermit_tcp_loopback):
    """Verify Kermit-to-Kermit Telnet negotiation finishes promptly.

    With Nagle on, the exchange held two writes for the peer's
    delayed ACK, about 85 ms in all.  Without it, the exchange takes
    a few milliseconds on loopback.
    """
    if timeout_scale() > 2:
        pytest.skip("elapsed-time bound is for a fast machine")
    session = _server(wermit_tcp_loopback, server_dir)
    result = _client(session, ".t0 := \\v(ftime)",
                     "echo NEG=\\ffpsubtract(\\v(ftime),\\m(t0))")
    session.wait_for_server_exit()
    m = re.search(r"NEG=([0-9.]+)", result.stdout)
    assert m, result.stdout
    assert float(m.group(1)) < 0.04, result.stdout


@pytest.mark.parametrize("setting", ["off", "on"])
def test_telnet_negotiation_restores_nodelay(server_dir,
                                            wermit_tcp_loopback, setting):
    """Verify SET TCP NODELAY survives Telnet negotiation."""
    session = _server(wermit_tcp_loopback, server_dir)
    result = _client(session, f"set tcp nodelay {setting}",
                     "show network")
    session.wait_for_server_exit()
    assert re.search(rf"Nodelay: +{setting}\b", result.stdout), \
        result.stdout

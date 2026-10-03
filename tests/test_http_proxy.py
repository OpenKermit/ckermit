"""
Tests for SET TCP HTTP-PROXY name handling in netopen() and
http_open().
"""
import pytest


@pytest.mark.parametrize("command", [
    "set host 127.0.0.1 9",
    "http open 127.0.0.1 9",
], ids=["set_host", "http_open"])
def test_long_proxy_name_without_port(run_wermit, wermit_http_available,
                                      command):
    """A proxy name that fills the hostname buffer must not overrun it.

    With no port in the proxy name, the default service name is stored
    after the name in the same buffer.
    """
    if command.startswith("http") and not wermit_http_available:
        pytest.skip("wermit built with NOHTTP")
    result = run_wermit(
        f"set tcp http-proxy {'p' * 1100}, {command}, "
        "echo DONE=[\\v(status)]"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DONE=[1]" in result.stdout, result.stdout

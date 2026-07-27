"""
SHOW INTERFACES tests.

Verify SHOW INTERFACES lists network interfaces and IPv4/IPv6 addresses
when CK_GETIFADDRS is defined.
"""
import re

import pytest
from conftest import assert_ok

# The loopback interface name is OS-specific: Linux calls it "lo",
# while FreeBSD, NetBSD, OpenBSD, and macOS call it "lo0".
LOOPBACK_RE = re.compile(r"^lo\d*:", re.MULTILINE)


def _build_has_interfaces(run_wermit):
    result = run_wermit("show interfaces")
    return result.returncode == 0 and "No keywords match" not in result.stdout


def test_show_interfaces_lists_loopback(run_wermit):
    if not _build_has_interfaces(run_wermit):
        pytest.skip("build has no SHOW INTERFACES (not CK_GETIFADDRS)")

    result = run_wermit("show interfaces")
    assert_ok(result, "SHOW INTERFACES failed")
    assert LOOPBACK_RE.search(result.stdout)
    assert "127.0.0.1" in result.stdout


def test_show_interfaces_abbreviates(run_wermit):
    if not _build_has_interfaces(run_wermit):
        pytest.skip("build has no SHOW INTERFACES (not CK_GETIFADDRS)")

    result = run_wermit("show int")
    assert_ok(result, "SHOW INT (abbreviated) failed")
    assert LOOPBACK_RE.search(result.stdout)


def test_show_interfaces_ipv6_gated_on_build(run_wermit):
    """
    Verify IPv6 addresses appear only in IPv6-enabled builds (CK_IPV6).
    """
    if not _build_has_interfaces(run_wermit):
        pytest.skip("build has no SHOW INTERFACES (not CK_GETIFADDRS)")

    tcp_result = run_wermit("show tcp")
    assert_ok(tcp_result, "SHOW TCP failed")
    build_has_ipv6 = "address-family:" in tcp_result.stdout

    result = run_wermit("show interfaces")
    assert_ok(result, "SHOW INTERFACES failed")
    if not build_has_ipv6:
        assert "IPv6" not in result.stdout

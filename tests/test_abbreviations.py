"""Tests that common keyword abbreviations keep their meaning.

Keywords added in C-Kermit 11 share prefixes with older keywords.
Each abbreviation here resolves to the older keyword.
"""
import pytest


@pytest.mark.parametrize("command", [
    "set com height 30",
    "show in",
    "set tcp a 127.0.0.1",
    "set tcp ad 127.0.0.1",
    "set tcp addr 127.0.0.1",
    "set rec co 35",
    "set rec con 35",
    "set send co 35",
])
def test_abbreviation_is_not_ambiguous(run_wermit, command):
    """Verify the abbreviated command parses and succeeds.

    SET RECEIVE CONFIRM refuses 35, so success with "co" or "con"
    shows that CONTROL-PREFIX was chosen.
    """
    result = run_wermit(f"{command}, echo STATUS=\\v(status)")
    assert "Ambiguous" not in result.stdout + result.stderr, result.stdout
    assert "STATUS=0" in result.stdout, result.stdout


@pytest.mark.parametrize("command", ["get", "receive"])
def test_co_switch_means_command(run_wermit, command):
    """Verify /co abbreviates /command.  /command takes no argument."""
    result = run_wermit(f"{command} /co:abc foo")
    assert "does not take an argument" in result.stdout + result.stderr, (
        result.stdout, result.stderr)

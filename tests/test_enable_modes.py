"""Tests for the LOCAL and REMOTE modes of ENABLE and DISABLE.

The mode selects the half of a setting to change.  The other half keeps
its value.  SHOW SERVER reports the result.
"""
import re

import pytest
from conftest import assert_ok


def _cd_state(run_wermit, cmds):
    """Return the SHOW SERVER text for REMOTE CD/CWD after cmds."""
    result = run_wermit(f"{cmds}, show server")
    assert_ok(result)
    m = re.search(r"REMOTE CD/CWD +(\S.*)$", result.stdout, re.M)
    assert m, result.stdout
    return m.group(1).strip()


@pytest.mark.parametrize("cmds,expected", [
    ("echo", "Remote only"),
    ("disable cd remote", "Disabled"),
    ("disable cd local", "Remote only"),
    ("enable cd local", "Enabled"),
    ("enable cd remote", "Remote only"),
    ("disable cd, enable cd local", "Local only"),
    ("disable cd, enable cd remote", "Remote only"),
    ("enable cd, disable cd remote", "Local only"),
    ("enable cd, disable cd local", "Remote only"),
    ("disable cd", "Disabled"),
    ("enable cd", "Enabled"),
])
def test_enable_disable_mode_changes_one_half(run_wermit, cmds, expected):
    """Verify LOCAL and REMOTE change only their half of the setting."""
    assert _cd_state(run_wermit, cmds) == expected


def test_disable_all_remote_keeps_local(run_wermit):
    """Verify DISABLE ALL REMOTE leaves LOCAL settings unchanged."""
    assert _cd_state(run_wermit, "enable all, disable all remote") == \
        "Local only"

"""
Tests for SET PROTOCOL and its external protocol commands.
"""
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("command", [
    "set protocol zmodem {sz %s} {sz -a %s} {rz} {rz}",
    "set protocol kermit {} {} {}",
])
def test_set_protocol_fields_are_initialized(wermit_path, command):
    """Verify SET PROTOCOL with few fields stores no uninitialized bytes.

    SHOW PROTOCOL prints every stored command, so valgrind reports any
    field that SET PROTOCOL left unset.
    """
    valgrind = shutil.which("valgrind")
    if not valgrind:
        pytest.skip("valgrind not installed")
    result = subprocess.run(
        [valgrind, "-q", "--error-exitcode=9", wermit_path,
         "-H", "-Y", "-Q", "-C", f"{command}, show protocol, quit"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=120)
    assert "uninitialised" not in result.stderr, result.stderr
    assert result.returncode == 0, result.stderr


def test_set_protocol_longest_command_twice(run_wermit):
    """Verify SET PROTOCOL keeps a 71-character command as the default.

    The second SET PROTOCOL shows the stored command, in braces, as the
    default for the field.
    """
    long_cmd = "x" * 71
    result = run_wermit(", ".join([
        f"set protocol kermit {long_cmd}",
        "set protocol kermit short",
        "show protocol",
        "echo DONE",
    ]))
    assert "DONE" in result.stdout, result.stdout + result.stderr
    assert "short" in result.stdout, result.stdout
    assert "ERROR: AddressSanitizer" not in result.stderr, result.stderr

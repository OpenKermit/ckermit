"""Tests for SET FLOW-CONTROL on a pseudoterminal serial line.

Each test records the CRTSCTS, IXON, and IXOFF flags of the line in
terminal mode (OUTPUT, as CONNECT uses), inside an external protocol,
and after a transfer (packet mode).
"""
import os
import pty
import subprocess
import termios
import threading
import tty

import pytest

from conftest import open_pty_line, scaled

pytestmark = pytest.mark.skipif(
    not hasattr(termios, "CRTSCTS"), reason="termios has no CRTSCTS")

# Append "crtscts ixon ixoff" as 0/1 values for a tty to the file named
# by FLOWCHECK_OUT.  With an argument, the helper opens that device.
# Without one, it reads stdin.
FLOWCHECK = """\
import os, sys, termios
if len(sys.argv) > 1:
    fd = os.open(sys.argv[1], os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
else:
    fd = 0
a = termios.tcgetattr(fd)
bits = (a[2] & termios.CRTSCTS, a[0] & termios.IXON, a[0] & termios.IXOFF)
with open(os.environ["FLOWCHECK_OUT"], "a") as out:
    out.write(" ".join("1" if b else "0" for b in bits) + "\\n")
"""

# The steps that put the line in terminal mode and in packet mode.
TERMINAL = "output x"
TRANSFER = "send /protocol:zmodem f.txt"


def _pty_keeps_crtscts():
    """Return True if a pty slave on this platform retains CRTSCTS."""
    master, slave = pty.openpty()
    try:
        attrs = termios.tcgetattr(slave)
        attrs[2] |= termios.CRTSCTS
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        return bool(termios.tcgetattr(slave)[2] & termios.CRTSCTS)
    except termios.error:
        return False
    finally:
        os.close(master)
        os.close(slave)


def _drain(master):
    """Read and discard pty output until the slave side closes."""
    while True:
        try:
            if not os.read(master, 4096):
                break
        except OSError:
            break


def _preset(fd, crtscts, ixon, ixoff):
    """Set the CRTSCTS, IXON, and IXOFF flags of the tty fd."""
    attrs = termios.tcgetattr(fd)
    for idx, flag, on in ((2, termios.CRTSCTS, crtscts),
                          (0, termios.IXON, ixon),
                          (0, termios.IXOFF, ixoff)):
        if on:
            attrs[idx] |= flag
        else:
            attrs[idx] &= ~flag
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def _flow_states(wermit_path, tmp_path, flow, steps, preset):
    """Run steps on a pty line with SET FLOW-CONTROL flow.

    preset gives the (crtscts, ixon, ixoff) state of the line before
    wermit opens it.  In steps, CHECK expands to a command that records
    the state of the line.  TRANSFER sends a file with an external
    protocol whose send command records the state of its stdin.
    Return the recorded states in order as (crtscts, ixon, ixoff)
    tuples of booleans.
    """
    if not _pty_keeps_crtscts():
        pytest.skip("pty does not retain CRTSCTS on this platform")
    helper = tmp_path / "flowcheck.py"
    helper.write_text(FLOWCHECK)
    # SET PROTOCOL limits each command to 71 characters.
    wrapper = tmp_path / "fc"
    wrapper.write_text(
        f'#!/bin/sh\nexec "{os.sys.executable}" "{helper}" "$@"\n')
    wrapper.chmod(0o755)
    out = tmp_path / "flow.out"
    (tmp_path / "f.txt").write_text("hello\n")
    master, slave, name = open_pty_line()
    tty.setraw(master)
    # The slave stays open so that the preset survives until wermit
    # opens the line.
    _preset(slave, *preset)
    reader = threading.Thread(target=_drain, args=(master,), daemon=True)
    reader.start()
    cmds = (f"set line {name}, set carrier-watch off, set speed 9600, "
            f"set flow {flow}, "
            "set protocol zmodem {} {./fc} {./fc} {} {}, "
            + steps.replace("CHECK", f"!./fc {name}")
            + ", exit")
    env = dict(os.environ, FLOWCHECK_OUT=str(out))
    try:
        result = subprocess.run(
            [wermit_path, "-H", "-Y", "-Q", "-C", cmds],
            cwd=tmp_path, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=scaled(30))
    finally:
        os.close(slave)
        os.close(master)
    assert out.exists(), result.stdout + result.stderr
    return [tuple(f == "1" for f in line.split())
            for line in out.read_text().splitlines()]


def _check_hardware(states, crtscts):
    """Assert the CRTSCTS flag of every state."""
    assert [s[0] for s in states] == [crtscts] * len(states), states


def _check_software(states, ixon, ixoff):
    """Assert the IXON and IXOFF flags of every state."""
    assert [s[1:] for s in states] == [(ixon, ixoff)] * len(states), states


# Terminal mode, then packet mode: line after OUTPUT, inside the
# external protocol, and after the transfer.
VT_THEN_PKT = f"{TERMINAL}, CHECK, {TRANSFER}, CHECK"
# Packet mode, then terminal mode: inside the external protocol, after
# the transfer, and after OUTPUT.
PKT_THEN_VT = f"{TRANSFER}, CHECK, {TERMINAL}, CHECK"


@pytest.mark.parametrize("steps", [VT_THEN_PKT, PKT_THEN_VT],
                         ids=["vt-then-pkt", "pkt-then-vt"])
def test_rtscts_on_in_all_modes(wermit_path, tmp_path, steps):
    """Verify SET FLOW RTS/CTS sets CRTSCTS and clears IXON/IXOFF.

    The flags hold through each change between terminal mode and
    packet mode.
    """
    states = _flow_states(wermit_path, tmp_path, "rts/cts", steps,
                          (False, True, True))
    _check_hardware(states, True)
    _check_software(states, False, False)


@pytest.mark.parametrize("steps", [VT_THEN_PKT, PKT_THEN_VT],
                         ids=["vt-then-pkt", "pkt-then-vt"])
def test_none_clears_all_flow_control(wermit_path, tmp_path, steps):
    """Verify SET FLOW NONE clears CRTSCTS, IXON, and IXOFF.

    The line starts with all three flags set.
    """
    states = _flow_states(wermit_path, tmp_path, "none", steps,
                          (True, True, True))
    _check_hardware(states, False)
    _check_software(states, False, False)


@pytest.mark.parametrize("steps", [VT_THEN_PKT, PKT_THEN_VT],
                         ids=["vt-then-pkt", "pkt-then-vt"])
def test_xonxoff_in_all_modes(wermit_path, tmp_path, steps):
    """Verify SET FLOW XON/XOFF sets IXON/IXOFF and clears CRTSCTS.

    The line starts with CRTSCTS set and IXON/IXOFF clear.  The flags
    hold in terminal mode, inside the external protocol, and after the
    transfer.
    """
    states = _flow_states(wermit_path, tmp_path, "xon/xoff", steps,
                          (True, False, False))
    _check_hardware(states, False)
    _check_software(states, True, True)


@pytest.mark.parametrize("crtscts, soft",
                         [(True, False), (False, True)],
                         ids=["hard", "soft"])
@pytest.mark.parametrize("steps", [VT_THEN_PKT, PKT_THEN_VT],
                         ids=["vt-then-pkt", "pkt-then-vt"])
def test_keep_preserves_flags(wermit_path, tmp_path, steps, crtscts, soft):
    """Verify SET FLOW KEEP leaves the flags as the line had them.

    CRTSCTS, IXON, and IXOFF keep their initial values in terminal
    mode, inside the external protocol, and after the transfer.
    """
    states = _flow_states(wermit_path, tmp_path, "keep", steps,
                          (crtscts, soft, soft))
    _check_hardware(states, crtscts)
    _check_software(states, soft, soft)


@pytest.mark.parametrize("flow, expect",
                         [("none", (False, False, False)),
                          ("xon/xoff", (False, True, True))],
                         ids=["none", "xon-xoff"])
def test_rtscts_then_other_flow(wermit_path, tmp_path, flow, expect):
    """Verify a change from RTS/CTS to another setting clears CRTSCTS.

    RTS/CTS is in effect for terminal mode and a transfer first.  The
    first state comes from the external protocol in that transfer.
    """
    states = _flow_states(
        wermit_path, tmp_path, "rts/cts",
        f"{TERMINAL}, {TRANSFER}, set flow {flow}, {TERMINAL}, CHECK, "
        f"{TRANSFER}, CHECK",
        (False, False, False))
    assert states == [(True, False, False)] + [expect] * 3


@pytest.mark.parametrize("steps", [VT_THEN_PKT, PKT_THEN_VT],
                         ids=["vt-then-pkt", "pkt-then-vt"])
def test_xonxoff_then_none(wermit_path, tmp_path, steps):
    """Verify a change from XON/XOFF to NONE clears IXON/IXOFF.

    XON/XOFF is in effect for terminal mode and a transfer first.  The
    first state comes from the external protocol in that transfer.
    """
    states = _flow_states(
        wermit_path, tmp_path, "xon/xoff",
        f"{TERMINAL}, {TRANSFER}, set flow none, " + steps,
        (False, False, False))
    assert states == [(False, True, True)] + [(False, False, False)] * 3


def test_automatic_clears_software_in_packet_mode(wermit_path, tmp_path):
    """Verify packet mode clears IXON/IXOFF with SET FLOW AUTOMATIC.

    SET FLOW AUTOMATIC after SET LINE leaves the flow-control setting
    unresolved until the next connection.  The line starts with IXON
    and IXOFF set.
    """
    states = _flow_states(wermit_path, tmp_path, "automatic",
                          f"{TRANSFER}, CHECK", (False, True, True))
    _check_software(states, False, False)


def test_rtscts_kept_after_transmit_binary(wermit_path, tmp_path):
    """Verify CRTSCTS stays on after TRANSMIT /BINARY ends."""
    states = _flow_states(wermit_path, tmp_path, "rts/cts",
                          "set transmit echo off, "
                          "transmit /binary /nowait f.txt, CHECK",
                          (False, False, False))
    assert states == [(True, False, False)]


def test_xonxoff_restored_after_transmit_binary(wermit_path, tmp_path):
    """Verify XON/XOFF is back on when TRANSMIT /BINARY ends.

    TRANSMIT /BINARY uses NONE in place of XON/XOFF while it runs.
    """
    states = _flow_states(wermit_path, tmp_path, "xon/xoff",
                          "set transmit echo off, "
                          "transmit /binary /nowait f.txt, CHECK",
                          (False, False, False))
    assert states == [(False, True, True)]

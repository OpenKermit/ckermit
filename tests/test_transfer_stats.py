"""Tests of the rate and time figures a Kermit transfer reports."""
import re

from conftest import assert_ok, make_loopback_dirs

# GFMINTIME in ckcdeb.h.  The CPS divisor is never less than this.
GFMINTIME = 0.005


def test_transfer_statistics_rate_and_time(tmp_path, wermit_loopback):
    """Verify \\v(cps), \\v(tftime), STATISTICS and the transaction log.

    A short transfer can finish in under GFMINTIME.  The elapsed time
    is then GFMINTIME, and the rate is at most size / GFMINTIME.  Every
    report of the rate shows the same figure.
    """
    size = 1000
    client_dir, server_dir = make_loopback_dirs(tmp_path)
    (client_dir / "f.bin").write_bytes(b"x" * size)
    tlog = tmp_path / "t.log"
    result = wermit_loopback(
        server_dir, "set delay 0",
        f"cd {client_dir}, set delay 0, log transactions {tlog}, "
        "send f.bin, echo CPS=\\v(cps) TFTIME=\\v(tftime), statistics, "
        "close transactions")
    assert_ok(result)
    out = result.stdout.replace("\r", "")
    m = re.search(r"CPS=(-?\d+) TFTIME=(-?\d+)", out)
    assert m, out
    cps, tftime = int(m.group(1)), int(m.group(2))
    m = re.search(r"elapsed time\s+: \S+ \((\d+\.\d+) sec\)", out)
    assert m, out
    elapsed = float(m.group(1))
    m = re.search(r"effective data rate\s+: (\d+) cps", out)
    assert m, out
    assert int(m.group(1)) == cps, out

    assert elapsed >= GFMINTIME, out
    assert abs(tftime - elapsed) <= 0.5 + 0.001, out
    assert 0 < cps <= size / GFMINTIME, out
    assert cps >= size / (elapsed + 0.001) - 1, out

    text = tlog.read_text()
    m = re.search(r"effective data rate\s+: (\d+)", text)
    assert m, text
    assert int(m.group(1)) == cps, text
    m = re.search(r"elapsed time \(seconds\)\s+: (\d+)", text)
    assert m, text
    assert 0 <= elapsed - int(m.group(1)) < 1.001, text

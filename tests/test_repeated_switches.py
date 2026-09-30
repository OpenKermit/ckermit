"""Regression tests for a string-valued switch given twice.

The second occurrence replaces the first. Its error and empty-value
paths must leave no freed or stale value behind.
"""


def _assert_no_crash(result):
    assert result.returncode >= 0, (
        f"wermit died with signal {-result.returncode}; "
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_send_except_repeated_with_too_long_pattern(run_wermit):
    """Verify a rejected second SEND /EXCEPT: does not crash."""
    result = run_wermit(f"send /except:a /except:{'b' * 300} ckcmai.c")
    _assert_no_crash(result)
    assert "?Pattern too long - 256 max" in result.stdout, result.stdout


def test_get_except_repeated_with_too_long_pattern(run_wermit):
    """Verify a rejected second GET /EXCEPT: does not crash."""
    result = run_wermit(f"get /except:a /except:{'b' * 300} x")
    _assert_no_crash(result)
    assert "?Pattern too long - 256 max" in result.stdout, result.stdout


def test_send_move_to_cleared_by_empty_value(tmp_path, run_wermit):
    """Verify an empty second SEND /MOVE-TO: clears the first."""
    src = tmp_path / "f.txt"
    src.write_text("hello world")
    destdir = tmp_path / ("d" * 40)
    result = run_wermit(f"send /move-to:{destdir} /move-to:{{}} {src}")
    _assert_no_crash(result)
    assert not destdir.exists()


def test_send_rename_to_cleared_by_empty_value(tmp_path, run_wermit):
    """Verify an empty second SEND /RENAME-TO: clears the first."""
    src = tmp_path / "f.txt"
    src.write_text("hello world")
    result = run_wermit(f"send /rename-to:{'r' * 40} /rename-to:{{}} {src}")
    _assert_no_crash(result)


def test_get_move_to_cleared_by_empty_value(tmp_path, run_wermit):
    """Verify an empty second GET /MOVE-TO: clears the first."""
    destdir = tmp_path / ("d" * 40)
    result = run_wermit(f"get /move-to:{destdir} /move-to:{{}} x")
    _assert_no_crash(result)
    assert not destdir.exists()

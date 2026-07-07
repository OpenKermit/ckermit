from conftest import assert_ok


def test_wermit_path(wermit_path):
    assert wermit_path is not None
    assert "wermit" in wermit_path


def test_run_wermit_version(run_wermit):
    result = run_wermit("show version, exit")
    assert_ok(result)
    assert "C-Kermit" in result.stdout

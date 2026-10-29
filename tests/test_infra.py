from conftest import assert_ok


def test_run_wermit_version(run_wermit):
    result = run_wermit("show version, exit")
    assert_ok(result)
    assert "C-Kermit" in result.stdout

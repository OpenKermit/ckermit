"""Regression tests for SET/SHOW TERMINAL settings."""


def test_show_terminal_autodownload_reflects_ask(run_wermit):
    """Verify SHOW TERMINAL distinguishes ON, ASK, and OFF autodownload."""
    result = run_wermit(
        "set terminal autodownload ask, show terminal"
    )
    assert "Autodownload: ask, error continue" in result.stdout, (
        result.stdout
    )

    result = run_wermit(
        "set terminal autodownload on, show terminal"
    )
    assert "Autodownload: on, error continue" in result.stdout, (
        result.stdout
    )

    result = run_wermit(
        "set terminal autodownload off, show terminal"
    )
    assert "Autodownload: off" in result.stdout, result.stdout

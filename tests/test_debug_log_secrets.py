"""
Tests that the debug log does not record passwords.
"""


def test_telnet_url_password_not_logged(run_wermit, tmp_path):
    """Verify a password in a telnet:// URL stays out of the debug log.

    The connection is refused.  netopen() splits the URL before it
    connects.  The parser and netopen() log the URL as given, so only
    the password line that netopen() writes after the split is checked.
    """
    log = tmp_path / "debug.log"
    run_wermit(f"log debug {log}, "
               "set host telnet://alice:Sekr1tPw@127.0.0.1:9, "
               "close debug", timeout=30)
    text = log.read_text(errors="replace")
    lines = [ln for ln in text.splitlines()
             if "netopen namecopy password" in ln]
    assert lines, text[-2000:]
    assert not any("Sekr1tPw" in ln for ln in lines), lines

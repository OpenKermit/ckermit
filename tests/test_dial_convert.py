

def test_lookup_skips_unopenable_directory(run_wermit, tmp_path):
    """Verify LOOKUP goes on to the next directory after one it can't open.

    ludial() freed its line buffer when a directory failed to open, then
    read the next directory into the freed buffer and crashed.
    """
    gone = tmp_path / "gone.dat"
    gone.write_text("x 1\n")
    d = tmp_path / "d.dat"
    d.write_text("home             5551212              ;  9600 none\n")
    result = run_wermit(f"set dial directory {gone} {d}, delete {gone}, "
                        "lookup home, echo S=\\v(status)", timeout=30)
    assert result.returncode == 0, result.returncode
    assert "5551212" in result.stdout, result.stdout
    assert "S=0" in result.stdout, result.stdout

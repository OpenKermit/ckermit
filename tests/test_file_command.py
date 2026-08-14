from conftest import assert_ok


def test_file_seek_eof_and_last(tmp_path, run_wermit):
    """Test FILE SEEK with EOF and LAST keywords for byte and line positions."""
    test_file = tmp_path / "seektest.txt"
    test_file.write_text("line1\nline2\nline3\n")
    file_size = test_file.stat().st_size  # 18 bytes: three 6-byte lines
    assert file_size == 18

    cmds = (
        f"file open /read \\%c {test_file}, "
        f"file seek /byte \\%c eof, "
        f"echo BYTEPOS_EOF=[\\F_pos(\\%c)], "
        f"file seek /line \\%c eof, "
        f"echo LINEPOS_EOF=[\\F_line(\\%c)], "
        f"file seek /line \\%c last, "
        f"echo LINEPOS_LAST=[\\F_line(\\%c)], "
        f"file close \\%c"
    )
    result = run_wermit(cmds)
    assert_ok(result)

    assert f"BYTEPOS_EOF=[{file_size}]" in result.stdout
    assert "LINEPOS_EOF=[3]" in result.stdout
    # LAST positions just before the final line, i.e. after 2 lines.
    assert "LINEPOS_LAST=[2]" in result.stdout

import os
import pytest
from conftest import assert_ok


def nonblank_lines(result):
    """Return result.stdout split into stripped, non-empty lines."""
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_directory_basic(tmp_path, run_wermit):
    """
    Test that the default directory listing command successfully displays
    files in a target directory.
    """
    (tmp_path / "file1.txt").touch()
    (tmp_path / "file2.txt").touch()

    result = run_wermit(f"cd {tmp_path}, directory")
    assert_ok(result)
    assert "file1.txt" in result.stdout
    assert "file2.txt" in result.stdout


def test_directory_brief(tmp_path, run_wermit):
    """
    Test the /brief switch, which prints only filenames (usually in a space-separated grid).
    """
    (tmp_path / "brief_a.txt").touch()
    (tmp_path / "brief_b.txt").touch()

    result = run_wermit(f"cd {tmp_path}, directory /brief")
    assert_ok(result)

    # Grid elements are separated by multiple spaces, split to get individual
    # names
    output_words = result.stdout.split()
    assert "brief_a.txt" in output_words
    assert "brief_b.txt" in output_words


def test_directory_verbose(tmp_path, run_wermit):
    """
    Test the /verbose switch, verifying it includes file metadata (like size).
    """
    f = tmp_path / "verbose_file.txt"
    f.write_text("Hello World!")  # 12 bytes

    result = run_wermit(f"cd {tmp_path}, directory /verbose")
    assert_ok(result)
    assert "verbose_file.txt" in result.stdout
    # Parse output line-by-line to verify the size column is specifically "12"
    # for verbose_file.txt
    found = False
    for line in result.stdout.splitlines():
        if "verbose_file.txt" in line:
            parts = line.split()
            # Expecting columns: permissions size date time filename
            if len(parts) >= 5 and parts[1] == "12" and parts[-1] == "verbose_file.txt":
                found = True
                break
    assert found, f"Could not find verbose entry with size 12 for verbose_file.txt in stdout:\n{result.stdout}"


def test_directory_files_and_directories(tmp_path, run_wermit):
    """
    Test /files and /directories switches to ensure correct filtering.
    """
    (tmp_path / "only_file.txt").touch()
    # Name the subdirectory uniquely to avoid matching any part of pytest's
    # tmp_path path
    subdir_name = "unique_test_dir_folder"
    (tmp_path / subdir_name).mkdir()

    # 1. Show only files
    result_files = run_wermit(f"cd {tmp_path}, directory /files /brief")
    assert_ok(result_files)
    files_words = result_files.stdout.split()
    assert "only_file.txt" in files_words
    assert subdir_name not in files_words

    # 2. Show only directories
    result_dirs = run_wermit(f"cd {tmp_path}, directory /directories /brief")
    assert_ok(result_dirs)
    dirs_words = result_dirs.stdout.split()
    assert subdir_name in dirs_words
    assert "only_file.txt" not in dirs_words


def test_directory_recursive(tmp_path, run_wermit):
    """
    Test the /recursive switch to descend into subdirectories.
    """
    subdir = tmp_path / "recursive_subdir"
    subdir.mkdir()
    (subdir / "nested.txt").touch()
    (tmp_path / "top_level.txt").touch()

    result = run_wermit(f"cd {tmp_path}, directory /recursive /brief")
    assert_ok(result)

    output_words = result.stdout.split()
    assert "top_level.txt" in output_words
    # Check that the nested file is listed (either as nested.txt or with the
    # subdir path)
    assert any("nested.txt" in word for word in output_words)


def test_directory_output_redirect(tmp_path, run_wermit):
    """
    Test the /output switch to redirect the listing to a file.
    """
    (tmp_path / "test_ref.txt").touch()
    outfile = tmp_path / "redirected_output.txt"

    result = run_wermit(f"cd {tmp_path}, directory /brief /output:{outfile}")
    assert_ok(result)

    # Verify the output file exists and contains the listed file name
    assert outfile.exists()
    content = outfile.read_text()
    assert "test_ref.txt" in content


def test_directory_array(tmp_path, run_wermit):
    """
    Test the /array:&a switch, which stores listing items into a Kermit array.
    We check the count stored in array[0] and elements stored in array[1] and array[2].
    """
    (tmp_path / "array_item1.txt").touch()
    (tmp_path / "array_item2.txt").touch()

    # Query array details by printing &a[0], &a[1], &a[2]
    # &a[0] should hold the count (2), &a[1] and &a[2] the sorted filenames.
    result = run_wermit(
        f"cd {tmp_path}, directory /array:&a, echo \\&a[0], echo \\&a[1], echo \\&a[2]"
    )
    assert_ok(result)

    output_lines = nonblank_lines(result)

    # Verify index 0 contains the file count, and index 1 and 2 contain the
    # sorted filenames
    assert "2" in output_lines
    assert "array_item1.txt" in output_lines
    assert "array_item2.txt" in output_lines


def test_directory_symlinks(tmp_path, run_wermit):
    """
    Test symlink filtering (/nolinks, /nofollowlinks) using local files and links.
    """
    target = tmp_path / "link_target.txt"
    target.touch()

    link = tmp_path / "link_pointer.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip(
            "Symlinks are not supported on this platform/configuration.")

    # 1. /nolinks: Symlink must NOT be listed
    result_nolinks = run_wermit(f"cd {tmp_path}, directory /nolinks")
    assert_ok(result_nolinks)
    assert "link_target.txt" in result_nolinks.stdout
    assert "link_pointer.txt" not in result_nolinks.stdout

    # 2. /nofollowlinks: Symlink must be listed
    result_nofollow = run_wermit(f"cd {tmp_path}, directory /nofollowlinks")
    assert_ok(result_nofollow)
    assert "link_target.txt" in result_nofollow.stdout
    assert "link_pointer.txt" in result_nofollow.stdout


def test_directory_dotfiles(tmp_path, run_wermit):
    """
    Test /dotfiles and /nodotfiles switches.
    """
    (tmp_path / "normal_file.txt").touch()
    (tmp_path / ".hidden_file.txt").touch()

    # 1. /nodotfiles (default) - .hidden_file.txt should not be listed
    result = run_wermit(f"cd {tmp_path}, directory /brief /nodotfiles")
    assert_ok(result)
    words = result.stdout.split()
    assert "normal_file.txt" in words
    assert ".hidden_file.txt" not in words

    # 2. /dotfiles - .hidden_file.txt should be listed
    result_dot = run_wermit(f"cd {tmp_path}, directory /brief /dotfiles")
    assert_ok(result_dot)
    words_dot = result_dot.stdout.split()
    assert "normal_file.txt" in words_dot
    assert ".hidden_file.txt" in words_dot


def test_directory_backup(tmp_path, run_wermit):
    """
    Test /backup and /nobackupfiles switches.
    """
    (tmp_path / "file1.txt").touch()
    (tmp_path / "file1.txt.~1~").touch()
    (tmp_path / "file1.txt.~2~").touch()

    # 1. /backup (default) - backup files should be listed
    result = run_wermit(f"cd {tmp_path}, directory /brief /backup")
    assert_ok(result)
    words = result.stdout.split()
    assert "file1.txt" in words
    assert "file1.txt.~1~" in words
    assert "file1.txt.~2~" in words

    # 2. /nobackupfiles - backup files should not be listed
    result_no = run_wermit(
        f"cd {tmp_path}, directory /brief /nobackupfiles"
    )
    assert_ok(result_no)
    words_no = result_no.stdout.split()
    assert "file1.txt" in words_no
    assert "file1.txt.~1~" not in words_no
    assert "file1.txt.~2~" not in words_no


def _sorted_indices(result):
    """Return the (filea, fileb, filec) positions among result's array output."""
    lines = nonblank_lines(result)
    return lines.index("filea"), lines.index("fileb"), lines.index("filec")


def test_directory_sorting(tmp_path, run_wermit):
    """
    Test /sort:size, /sort:date, and /reverse switches.
    """
    file_a = tmp_path / "filea"
    file_b = tmp_path / "fileb"
    file_c = tmp_path / "filec"

    # Set sizes: filea=5, fileb=15, filec=10
    file_a.write_text("a" * 5)
    file_b.write_text("b" * 15)
    file_c.write_text("c" * 10)

    # Set mod times (atime, mtime): filea=1000, fileb=3000, filec=2000
    os.utime(file_a, (1000, 1000))
    os.utime(file_b, (3000, 3000))
    os.utime(file_c, (2000, 2000))

    # 1. Test sorting by size (ascending)
    # Expected order: filea (5), filec (10), fileb (15)
    res_size = run_wermit(
        f"cd {tmp_path}, directory /array:&a /sort:size, "
        "echo \\&a[1], echo \\&a[2], echo \\&a[3]"
    )
    assert_ok(res_size)
    idx_a, idx_b, idx_c = _sorted_indices(res_size)
    assert idx_a < idx_c < idx_b

    # 2. Test sorting by size reverse (descending)
    # Expected order: fileb (15), filec (10), filea (5)
    res_size_rev = run_wermit(
        f"cd {tmp_path}, directory /array:&a /sort:size /reverse, "
        "echo \\&a[1], echo \\&a[2], echo \\&a[3]"
    )
    assert_ok(res_size_rev)
    idx_a, idx_b, idx_c = _sorted_indices(res_size_rev)
    assert idx_b < idx_c < idx_a

    # 3. Test sorting by date (ascending)
    # Expected order (mtime): filea (1000), filec (2000), fileb (3000)
    res_date = run_wermit(
        f"cd {tmp_path}, directory /array:&a /sort:date, "
        "echo \\&a[1], echo \\&a[2], echo \\&a[3]"
    )
    assert_ok(res_date)
    idx_a, idx_b, idx_c = _sorted_indices(res_date)
    assert idx_a < idx_c < idx_b

    # 4. Test sorting by date reverse (descending)
    # Expected order: fileb (3000), filec (2000), filea (1000)
    res_date_rev = run_wermit(
        f"cd {tmp_path}, directory /array:&a /sort:date /reverse, "
        "echo \\&a[1], echo \\&a[2], echo \\&a[3]"
    )
    assert_ok(res_date_rev)
    idx_a, idx_b, idx_c = _sorted_indices(res_date_rev)
    assert idx_b < idx_c < idx_a

"""
Tests for conversion of an old-style dialing directory (ddcvt(),
ckuus6.c).
"""
import subprocess

from conftest import scaled


def test_dial_directory_conversion_closes_file(wermit_path, tmp_path,
                                               valgrind):
    """Verify conversion closes the old directory file.

    valgrind --track-fds lists the descriptors open at exit.
    """
    d = tmp_path / "d.dat"
    d.write_text("home 5551212 9600 none\nwork 5553434 2400 even\n")
    result = subprocess.run(
        [valgrind, "-q", "--track-fds=yes", wermit_path,
         "-H", "-Y", "-Q", "-C",
         f"set dial directory {d}, set dial convert-directory on, "
         "lookup home, exit"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        cwd=tmp_path, timeout=scaled(120))
    assert "Converting" in result.stdout, result.stdout
    text = d.read_text()
    assert "home             5551212              ;  9600 none" in text, text
    open_fds = [ln for ln in result.stderr.splitlines()
                if "d.dat" in ln]
    assert not open_fds, result.stderr


def test_lookup_skips_unopenable_directory(run_wermit, tmp_path):
    """Verify LOOKUP goes on to the next directory after one it can't open.

    SET DIAL DIRECTORY accepts only existing files, so the first file
    is deleted after SET DIAL DIRECTORY and before LOOKUP.
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


def test_lookup_long_country_and_area_codes(run_wermit, tmp_path):
    """Verify dncvt() terminates long country and area codes.

    dncvt() collects the digits of each code into a fixed buffer and
    stops at its size.  Reading an unterminated code shows only under
    AddressSanitizer.
    """
    digits = "1234567890" * 3
    for number in (f"+1 ({digits}) 5551234", "+" + "1" * 150):
        result = run_wermit(
            f"cd {tmp_path}, set dial country-code 1, "
            "set dial area-code 212, set dial ld-prefix 1, "
            f"lookup {number}, echo RC=\\v(status)")
        assert result.returncode >= 0, (
            f"wermit died with signal {-result.returncode}")
        assert "AddressSanitizer" not in result.stderr, (
            result.stderr[-3000:])
        assert "RC=0" in result.stdout, result.stdout


def test_lookup_pbx_internal_call_type(run_wermit, tmp_path):
    """Verify a PBX internal number gets the internal call type.

    LOOKUP shows each number's call type in parentheses: 0 internal,
    2 local.  The type of the second number must not land on the
    first, with or without a delimited area code.
    """
    d = tmp_path / "d.dat"
    d.write_text("home +1 (212) 999-1234\nhome +1 (212) 555-1234\n"
                 "work +1 2129991234\nwork +1 2125551234\n")
    result = run_wermit(
        f"set dial directory {d}, set dial country-code 1, "
        "set dial area-code 212, set dial pbx-exchange 555, "
        "set dial pbx-inside-prefix 7, set dial pbx-outside-prefix 9, "
        "set dial sort off, lookup home, lookup work")
    types = [ln.split()[-1] for ln in result.stdout.splitlines()
             if "=>" in ln]
    assert types == ["(2)", "(0)", "(2)", "(0)"], result.stdout

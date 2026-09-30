"""Tests for \\fpictureinfo() JPEG parsing."""
import pytest

SOI = b"\xff\xd8"
EOI = b"\xff\xd9"
# SOF0 frame: length 17, precision 8, height 16, width 32, 3 components.
SOF0 = (b"\xff\xc0\x00\x11\x08\x00\x10\x00\x20\x03"
        b"\x01\x22\x00\x02\x11\x01\x03\x11\x01")
JFIF = b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"


def _picture_info(run_wermit, tmp_path, data):
    """Write data to a .jpg file and return the wermit output."""
    pic = tmp_path / "pic.jpg"
    pic.write_bytes(data)
    script = tmp_path / "pic.ksc"
    script.write_text(
        f"echo R=[\\fpictureinfo({pic},&a)] "
        "W=[\\&a[1]] H=[\\&a[2]]\n"
    )
    return run_wermit(f"take {script}")


def test_pictureinfo_jpeg_dimensions(tmp_path, run_wermit):
    """Verify \\fpictureinfo() reads a JPEG's dimensions."""
    data = SOI + b"\xff\xe0\x00\x10" + JFIF + SOF0 + EOI
    result = _picture_info(run_wermit, tmp_path, data)
    assert "R=[1] W=[32] H=[16]" in result.stdout, result.stdout


@pytest.mark.parametrize("length", [b"\x00\x00", b"\x00\x01"])
def test_pictureinfo_jpeg_invalid_segment_length(tmp_path, run_wermit,
                                                 length):
    """Verify a segment length below 2 does not end the marker search.

    The length includes the two length bytes, so 0 and 1 are invalid.
    The parser continues searching for the next marker.
    """
    data = SOI + b"\xff\xe0" + length + SOF0 + EOI
    result = _picture_info(run_wermit, tmp_path, data)
    assert "R=[1] W=[32] H=[16]" in result.stdout, result.stdout

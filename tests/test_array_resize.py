"""
Tests for ARRAY RESIZE (ckuusr.c).
"""
import re
import resource
import subprocess
import sys

import pytest

from conftest import scaled


def test_array_resize_smaller_frees_elements(wermit_path, valgrind):
    """Verify shrinking an array frees the elements it drops."""
    cmds = ", ".join([
        "set command more-prompting off",
        "declare \\&a[10]",
        "for \\%i 1 10 1 { .\\&a[\\%i] := element \\%i }",
        "array resize &a 3",
        "echo LAST=[\\&a[3]] DIM=[\\fdim(&a)]",
        "quit",
    ])
    result = subprocess.run(
        [valgrind, "-q", "--leak-check=full", wermit_path,
         "-H", "-Y", "-Q", "-C", cmds],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=scaled(120))
    assert "LAST=[element 3] DIM=[3]" in result.stdout, result.stdout
    # valgrind separates loss records with "==pid== " lines.  dodef()
    # stored the elements.  Other leaks are not at issue.
    records = re.split(r"^==\d+== *$", result.stderr, flags=re.M)
    leaked = [r for r in records
              if "definitely lost" in r and "dodef" in r]
    assert not leaked, result.stderr


def test_array_resize_updates_every_link(run_wermit):
    """Verify resizing through one link updates the other links."""
    result = run_wermit(", ".join([
        "declare \\&r[5]",
        ".\\&r[3] := three",
        "array link &a &r",
        "array link &b &r",
        "array resize &a 20",
        ".\\&b[20] := twenty",
        "echo DIMS=[\\fdim(&a)][\\fdim(&b)][\\fdim(&r)]",
        "echo B3=[\\&b[3]] R20=[\\&r[20]]",
    ]))
    assert "DIMS=[20][20][20]" in result.stdout, result.stdout
    assert "B3=[three] R20=[twenty]" in result.stdout, result.stdout


def test_array_resize_out_of_memory(wermit_path, wermit_sanitized):
    """Verify ARRAY RESIZE fails when the element list cannot be had."""
    if wermit_sanitized:
        pytest.skip("a sanitizer build cannot run under RLIMIT_AS")
    if not hasattr(resource, "RLIMIT_AS"):
        pytest.skip("no RLIMIT_AS on this platform")
    gb = 1 << 30

    # Check whether RLIMIT_AS can be lowered and is enforced.  macOS may
    # reject the setrlimit() call.  qemu-user accepts it but enforces
    # nothing.  A 1 GiB allocation must fail under a 1 GiB limit.
    probe = subprocess.run(
        [sys.executable, "-c",
         "import resource, sys\n"
         f"resource.setrlimit(resource.RLIMIT_AS, ({gb}, {gb}))\n"
         "try:\n"
         f"    bytearray({gb})\n"
         "except MemoryError:\n"
         "    sys.exit(0)\n"
         "sys.exit(3)\n"],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=scaled(30))
    if probe.returncode == 3:
        pytest.skip("RLIMIT_AS is not enforced here")
    if probe.returncode != 0:
        pytest.skip("RLIMIT_AS cannot be lowered to 1 GiB here")

    def limit():
        resource.setrlimit(resource.RLIMIT_AS, (gb, gb))
    result = subprocess.run(
        [wermit_path, "-H", "-Y", "-Q", "-C", ", ".join([
            "set command more-prompting off",
            "declare \\&a[5]",
            ".\\&a[2] := two",
            "array resize &a 300000000",
            "echo STATUS=[\\v(status)] A2=[\\&a[2]] DIM=[\\fdim(&a)]",
            "exit 0",
        ])],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=scaled(60), preexec_fn=limit)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "STATUS=[1] A2=[two] DIM=[5]" in result.stdout, result.stdout

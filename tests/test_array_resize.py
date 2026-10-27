"""
Tests for ARRAY RESIZE (ckuusr.c).
"""
import re
import resource
import shutil
import subprocess

import pytest


def test_array_resize_smaller_frees_elements(wermit_path):
    """Verify shrinking an array frees the elements it drops."""
    valgrind = shutil.which("valgrind")
    if not valgrind:
        pytest.skip("valgrind not installed")
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
        timeout=120)
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


def test_array_resize_out_of_memory(wermit_path):
    """Verify ARRAY RESIZE fails when the element list cannot be had."""
    if not hasattr(resource, "RLIMIT_AS"):
        pytest.skip("no RLIMIT_AS on this platform")
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
    except (ValueError, OSError):
        pytest.skip("RLIMIT_AS cannot be set on this platform")
    def limit():
        gib = 1 << 30
        resource.setrlimit(resource.RLIMIT_AS, (gib, gib))
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
        timeout=60, preexec_fn=limit)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "STATUS=[1] A2=[two] DIM=[5]" in result.stdout, result.stdout

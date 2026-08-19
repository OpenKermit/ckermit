from pathlib import Path
from conftest import assert_ok


def script(name):
    path = Path(__file__).parent / "scripts" / name
    assert path.exists(), f"Script not found: {path}"
    return path


def test_script_basic(run_wermit):
    """
    Executes the basic scripting test file and verifies that variables, macros,
    and dot assignments resolve and print correctly, and that the script exits with 0.
    """
    result = run_wermit([str(script("test_basic.ksc")), "-Y"])

    assert_ok(result)
    assert "TEST_BASIC: Macro value is 42" in result.stdout
    assert "TEST_BASIC: Variable value is 100" in result.stdout
    assert "TEST_BASIC: Dot value is 200" in result.stdout


def test_script_args_success(run_wermit):
    """
    Executes test_args.ksc with valid arguments and checks that they are mapped correctly.
    """
    result = run_wermit([str(script("test_args.ksc")),
                        "-Y", "=", "hello", "world"])

    assert_ok(result)
    assert "TEST_ARGS: Arg 1 is hello" in result.stdout
    assert "TEST_ARGS: Arg 2 is world" in result.stdout


def test_script_args_missing(run_wermit):
    """
    Executes test_args.ksc with insufficient arguments and expects a failure exit code.
    """
    result = run_wermit([str(script("test_args.ksc")), "-Y"])
    assert result.returncode != 0
    assert "TEST_ARGS_FAIL" in result.stdout


def test_script_control(run_wermit):
    """
    Executes the test_control.ksc script and asserts that all control flow,
    loops, and jumps resolve correctly, and that the exit code is 0.
    """
    result = run_wermit([str(script("test_control.ksc")), "-Y"])

    assert_ok(result)
    assert "TEST_CONTROL: SUCCESS verified" in result.stdout
    assert "TEST_CONTROL: FAILURE verified" in result.stdout
    assert "TEST_CONTROL: EXIST verified" in result.stdout
    assert "TEST_CONTROL: COMPARISON verified" in result.stdout
    assert "TEST_CONTROL: FOR loop 0" not in result.stdout
    assert "TEST_CONTROL: FOR loop 1" in result.stdout
    assert "TEST_CONTROL: FOR loop 2" in result.stdout
    assert "TEST_CONTROL: FOR loop 3" in result.stdout
    assert "TEST_CONTROL: FOR loop 4" not in result.stdout
    assert "TEST_CONTROL: WHILE loop 0" not in result.stdout
    assert "TEST_CONTROL: WHILE loop 1" in result.stdout
    assert "TEST_CONTROL: WHILE loop 2" in result.stdout
    assert "TEST_CONTROL: WHILE loop 3" in result.stdout
    assert "TEST_CONTROL: WHILE loop 4" not in result.stdout
    assert "TEST_CONTROL: GOTO loop 0" not in result.stdout
    assert "TEST_CONTROL: GOTO loop 1" in result.stdout
    assert "TEST_CONTROL: GOTO loop 2" in result.stdout
    assert "TEST_CONTROL: GOTO loop 3" in result.stdout
    assert "TEST_CONTROL: GOTO loop 4" not in result.stdout
    assert "TEST_CONTROL: GOTO verified" in result.stdout


def test_underscore_macro_name_not_internal(run_wermit):
    """
    Invoking a user-defined macro whose name starts with "_" but isn't one of
    the macro names _while, _forx, _forz, _xif, _switx.

    Regression test for isinternalmacro().  It looped
    "i < sizeof(* tags)", the size of one array element (a char *),
    instead of the array's element count. tags[] has 4 real entries;
    sizeof(char *) is 4 on a 32-bit build, so the loop happened to be
    correct there, but incorrect on 64-bit.
    """
    result = run_wermit("define _mytest1 echo hi, do _mytest1")

    assert result.returncode >= 0, (
        "wermit crashed (signal "
        f"{-result.returncode}) invoking a user macro named "
        f"_mytest1: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert_ok(result)
    assert "hi" in result.stdout

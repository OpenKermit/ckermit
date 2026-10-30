Debian systems need:

apt-get install libssl-dev python3-pyftpdlib python3-pytest python3-pytest-xdist python3-pytest-timeout lrzsz check

Mac systems need:

brew install openssl@3 check lrzsz pkg-config
pip3 install --break-system-packages pytest pytest-xdist pytest-timeout pyftpdlib

On FreeBSD:

pkg install -y check lrzsz python3 py312-pip
pip install pytest pytest-xdist pytest-timeout pyftpdlib

On NetBSD:

pkgin -y install check lrzsz py313-pip
pip3.13 install pytest pytest-xdist pytest-timeout pyftpdlib

Slow Machines:

A hang limit bounds something that is expected to finish, such as a
subprocess or a wait for output.  Each is at least 60 s, so a loaded
host or a VM under emulation does not fail a test that would pass.
The pytest-timeout limit is 600 s.  At startup, conftest.py times a
short wermit loop.  It multiplies the limits by the ratio to a fast
machine, clamped to the range 1 to 20.  The session header shows the
factor:

    kermit timeout scale: 20.00

KERMIT_TEST_TIMEOUT_SCALE overrides the measured factor:

    KERMIT_TEST_TIMEOUT_SCALE=10 pytest -n0

--timeout or PYTEST_TIMEOUT sets the pytest-timeout limit directly
without scaling.  The factor raises only the limits that stop a hung
test.  Tests that check how long an operation took keep their bounds.

On a single-CPU machine, run the suite with -n0.  A 599 MHz Alpha
running NetBSD takes about 48 minutes.

Slow and ZMODEM Tests:

Tests marked slow wait out a timeout or a fixed delay on purpose.
Tests marked zmodem run ZMODEM transfers with lrzsz.  Both take long
on a slow machine.  A default run leaves them out, and the session
header says so.  Run them too with:

    pytest --full

or with KERMIT_TEST_FULL=1 in the environment.  CI runs the full
suite, and so should anyone changing Kermit.  An explicit -m
expression decides by itself, so "pytest -m zmodem" runs only the
ZMODEM tests.

Writing Tests:

A wermit_loopback test runs over a pty, with control prefixing on.  A
test that needs more transports parametrizes loopback_transport with
indirect=True.  A test that transfers control characters applies
CLEAR_UNPREFIX_MODES to run with and without prefixing.

For a sweep of boundary values or keywords, run one session that tries
each value, and report every failing value in the assertion message.
Keep a separate process per value only when the bug needs one, such as
a leak counted at exit or a failure that kills the process.

Use scaled() for a limit on something expected to finish.  It is at
least 60 s.  Use kermit_wait() for an INPUT in a Kermit script that
expects its text.  Use expected_timeout() only for a wait the test
means to run out.  read_pty_until() and PtyReader fail the test when
the text they wait for does not arrive.

Debugging Server-Side Operations:

To enable and print the server-side debug logs (even for successful tests), run pytest with xdist disabled (-n0), capturing disabled (-s), and CLI log level set to DEBUG:

    pytest -s --log-cli-level=DEBUG -n0

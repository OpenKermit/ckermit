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

The hang limits in the suite (subprocess timeouts, waits for output,
and the pytest-timeout limit of 120 s) are sized for a fast machine.
At startup, conftest.py times a short wermit loop.  It multiplies the
limits by the ratio to a fast machine, clamped to the range 1 to 20.
The session header shows the factor:

    kermit timeout scale: 20.00

KERMIT_TEST_TIMEOUT_SCALE overrides the measured factor:

    KERMIT_TEST_TIMEOUT_SCALE=10 pytest -n0

--timeout or PYTEST_TIMEOUT sets the pytest-timeout limit directly
without scaling.  The factor raises only the limits that stop a hung
test.  Tests that check how long an operation took keep their bounds.

On a single-CPU machine, run the suite with -n0.  A 599 MHz Alpha
running NetBSD takes about 48 minutes.

Debugging Server-Side Operations:

To enable and print the server-side debug logs (even for successful tests), run pytest with xdist disabled (-n0), capturing disabled (-s), and CLI log level set to DEBUG:

    pytest -s --log-cli-level=DEBUG -n0

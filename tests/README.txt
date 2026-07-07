Debian systems need:

apt-get install python3-pyftpdlib python3-pytest python3-pytest-xdist lrzsz check

Debugging Server-Side Operations:
To enable and print the server-side debug logs (even for successful tests), run pytest with xdist disabled (-n0), capturing disabled (-s), and CLI log level set to DEBUG:

    pytest -s --log-cli-level=DEBUG -n0

Debian systems need:

apt-get install python3-pyftpdlib python3-pytest python3-pytest-xdist lrzsz check

Mac systems need:

brew install openssl@3 check lrzsz
pip3 install --break-system-packages pytest pytest-xdist pyftpdlib

On FreeBSD:

pkg install -y openssl check lrzsz python3 py312-pip
pip install pytest pytest-xdist pyftpdlib

On NetBSD:

pkgin -y install openssl check lrzsz py313-pip
pip3.13 install pytest pytest-xdist pyftpdlib

Debugging Server-Side Operations:

To enable and print the server-side debug logs (even for successful tests), run pytest with xdist disabled (-n0), capturing disabled (-s), and CLI log level set to DEBUG:

    pytest -s --log-cli-level=DEBUG -n0

"""
Regression tests for ttptycmd()'s Telnet option negotiation handling
(ckutio.c).

ttptycmd() is the relay loop used by external protocol commands (e.g.
SEND under SET PROTOCOL ZMODEM) once the connection is handed off to a
child process on a pty. Telnet option negotiation (IAC
WILL/WONT/DO/DONT/SB) can arrive during this phase and must be answered
so the peer does not time out.

A plain sleep stands in for the external protocol helper (e.g. sz/rz).

An in-process TCP proxy sits between the client and server wermit
instances. It relays traffic transparently, injecting an unsolicited
Telnet command toward the client once negotiation settles and SEND hands
off to ttptycmd(). The proxy captures client replies to verify the
negotiation response.
"""
import os
import socket
import subprocess
import threading
import time

import pytest

from conftest import start_wermit_pty, _wait_for_pty_marker

IAC, WILL, WONT, DO, DONT = 255, 251, 252, 253, 254

# Telnet options tn_ini() (ckctel.c) refuses by default in both
# directions, regardless of what else is negotiated on the
# connection. Using one of these keeps the expected reply fixed
# (WONT/DONT) no matter what other options a given wermit build or
# test environment happens to accept.
REFUSED_OPTION_RCP = 2
REFUSED_OPTION_STATUS = 5


class _InjectingProxy:
    """
    Transparent TCP proxy for exercising ttptycmd()'s Telnet handling.

    Relays bytes unmodified in both directions between whatever
    connects to listen_port and target_port, except: inject_delay
    seconds after relaying starts, it sends inject_bytes toward the
    client exactly once. Bytes the client sends back after that are
    captured and available via reply_after_inject once the session
    ends.
    """

    def __init__(self, listen_port, target_port, inject_delay,
                 inject_bytes, capture_window=1.5):
        self.listen_port = listen_port
        self.target_port = target_port
        self.inject_delay = inject_delay
        self.inject_bytes = inject_bytes
        # How long after injecting to keep capturing the client's
        # replies. Bounded so unrelated negotiation from the
        # connection's eventual teardown (e.g. a "DO LOGOUT"
        # exchanged when either side closes) doesn't get mistaken
        # for a reply to the injected bytes.
        self.capture_window = capture_window
        self._captured = bytearray()
        self._lock = threading.Lock()
        self._injected = False
        self._injected_at = None
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", listen_port))
        self._listener.listen(1)
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def join(self, timeout=10):
        self._thread.join(timeout)

    @property
    def reply_after_inject(self):
        with self._lock:
            return bytes(self._captured)

    def _run(self):
        try:
            client, _ = self._listener.accept()
        except OSError:
            return
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.connect(("127.0.0.1", self.target_port))

        t_c2s = threading.Thread(
            target=self._pump, args=(client, server, False), daemon=True)
        t_s2c = threading.Thread(
            target=self._pump, args=(server, client, True), daemon=True)
        t_c2s.start()
        t_s2c.start()
        t_c2s.join()
        t_s2c.join()
        client.close()
        server.close()
        self._listener.close()

    def _pump(self, src, dst, is_server_to_client):
        start = time.time()
        injected = False
        src.settimeout(0.2)
        while True:
            if (is_server_to_client and not injected
                    and time.time() - start >= self.inject_delay):
                try:
                    dst.sendall(self.inject_bytes)
                except OSError:
                    pass
                with self._lock:
                    self._injected = True
                    self._injected_at = time.time()
                injected = True
            try:
                chunk = src.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            if not is_server_to_client:
                with self._lock:
                    if (self._injected and time.time() - self._injected_at
                            <= self.capture_window):
                        self._captured.extend(chunk)
            try:
                dst.sendall(chunk)
            except OSError:
                break
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def _run_ttptycmd_negotiation_case(
        wermit_path, get_free_port, spawn_wermit, tmp_path,
        inject_bytes, inject_delay=2.0, transfer_delay=4):
    """
    Starts a plain Telnet "server" wermit (CONNECT mode, no external
    protocol involved) on a pty, an _InjectingProxy in front of it,
    and a "client" wermit that connects through the proxy and
    immediately hands the connection to a `sleep` (standing in for
    sz/rz) via SET PROTOCOL + SEND. inject_bytes lands while that
    `sleep` is still running, so only ttptycmd()'s relay loop is
    running on the client side to answer it.

    Returns the proxy's captured reply bytes: whatever the client
    sent back after the injected bytes.
    """
    server_port = get_free_port()
    proxy_port = get_free_port()

    # Both sides need the same telopt refusals and dummy protocol
    # clause, or the client's connect-time negotiation errors out
    # ("?Telnet Option negotiation error") before SEND is reached.
    common_clause = (
        "set telopt /client authentication refused, "
        "set telopt /client start-tls refused, "
        "set telopt /client kermit refused, "
        "set telopt /server authentication refused, "
        "set telopt /server start-tls refused, "
        "set telopt /server kermit refused, "
        'set protocol zmodem "" "" '
        f'"sleep {transfer_delay}" "sleep {transfer_delay}" '
        f'"sleep {transfer_delay}" "sleep {transfer_delay}"'
    )

    server_cmd = (
        f"{common_clause}, "
        "set tcp reverse-dns-lookup off, "
        "set terminal autodownload on, "
        f"set host * {server_port} /telnet, connect, close, exit"
    )
    proc, master = start_wermit_pty(wermit_path, server_cmd, tmp_path)
    try:
        _, ready = _wait_for_pty_marker(
            master, b"Waiting to Accept", timeout=10)
        assert ready, "server wermit never started listening"

        proxy = _InjectingProxy(
            proxy_port, server_port, inject_delay, inject_bytes)
        proxy.start()

        src_file = tmp_path / "src.txt"
        src_file.write_text("hello from test_ttptycmd_telnet\n")

        client = spawn_wermit(
            ["-H", "-Y", "-C",
             "set command more-prompting off, "
             "set tcp reverse-dns-lookup off, "
             f"{common_clause}, "
             f"set host 127.0.0.1 {proxy_port} /telnet, "
             "if failure exit 90, "
             f"send {src_file}, close, exit"],
            cwd=str(tmp_path))

        client.wait(timeout=transfer_delay + inject_delay + 15)
        proxy.join(timeout=10)
    finally:
        # The server's plain CONNECT mode (no autodownload, unlike the
        # real Zmodem fixtures) doesn't reliably notice the client
        # closing the connection, so don't wait on a graceful exit
        # here, just tear it down.
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        try:
            os.close(master)
        except OSError:
            pass

    return proxy.reply_after_inject


@pytest.mark.parametrize("kind,option,expect_reply", [
    pytest.param(
        DO, REFUSED_OPTION_RCP, bytes([IAC, WONT, REFUSED_OPTION_RCP]),
        id="unsolicited-do-gets-wont"),
    pytest.param(
        WILL, REFUSED_OPTION_STATUS,
        bytes([IAC, DONT, REFUSED_OPTION_STATUS]),
        id="unsolicited-will-gets-dont"),
])
def test_ttptycmd_answers_unsolicited_negotiation(
        wermit_path, get_free_port, spawn_wermit, tmp_path,
        kind, option, expect_reply):
    """
    Verify that ttptycmd() answers unsolicited Telnet WILL/DO commands.

    An unsolicited WILL or DO arriving after SEND hands the connection
    to ttptycmd() must produce a negotiation reply instead of being
    silently dropped.
    """
    inject_bytes = bytes([IAC, kind, option])
    reply = _run_ttptycmd_negotiation_case(
        wermit_path, get_free_port, spawn_wermit, tmp_path,
        inject_bytes)
    assert expect_reply in reply, (
        f"expected the client to reply with {expect_reply!r} to "
        f"{inject_bytes!r}, but its reply was {reply!r}"
    )


def test_ttptycmd_doubled_iac_is_not_treated_as_negotiation(
        wermit_path, get_free_port, spawn_wermit, tmp_path):
    """
    Verify that doubled IAC is treated as literal data, not negotiation.

    IAC IAC is Telnet's escape for a literal 0xFF data byte and must
    pass through to the pty without provoking a negotiation response.
    """
    reply = _run_ttptycmd_negotiation_case(
        wermit_path, get_free_port, spawn_wermit, tmp_path,
        bytes([IAC, IAC]))
    assert IAC not in reply, (
        f"a doubled IAC (literal data) should never provoke a Telnet "
        f"reply, but got {reply!r}"
    )

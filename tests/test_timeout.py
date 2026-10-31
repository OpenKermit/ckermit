import socket
import time

import pytest

from conftest import TCP_TIMEOUT_MARGIN

# SET SEND TIMEOUT 2 plus SET RETRY-LIMIT 3 gives an escalating
# per-attempt wait that totals about 20s before ttinl() gives up.
# RUN_TIMEOUT includes margin for slower CI hosts.
RUN_TIMEOUT = 60 + TCP_TIMEOUT_MARGIN
GIVE_UP_BOUND = 45


@pytest.mark.slow
def test_receive_gives_up_on_stalled_peer(run_wermit):
    """Verify RECEIVE times out when connected to a stalled peer.

    The peer accepts the connection via the kernel backlog without calling
    accept() or transmitting data.
    """
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        start = time.perf_counter()
        result = run_wermit(
            "set tcp reverse-dns-lookup off, "
            "set send timeout 2, set retry-limit 3, "
            f"set host 127.0.0.1 {port} /raw-socket, receive, close",
            timeout=RUN_TIMEOUT,
        )
        elapsed = time.perf_counter() - start
    finally:
        listener.close()

    assert elapsed < GIVE_UP_BOUND, (
        f"RECEIVE took {elapsed:.1f}s to give up on stalled peer"
    )
    assert result.returncode != 0
    assert "Too many retries" in result.stdout, result.stdout


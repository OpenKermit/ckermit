import socket
import time

from conftest import TCP_TIMEOUT_MARGIN

# SET SEND TIMEOUT 2 plus SET RETRY-LIMIT 3 gives an escalating
# per-attempt wait that totals about 20s before ttinl() gives up.
# RUN_TIMEOUT includes margin for slower CI hosts.
RUN_TIMEOUT = 60 + TCP_TIMEOUT_MARGIN
GIVE_UP_BOUND = 45


def test_receive_gives_up_on_stalled_peer(run_wermit, get_free_port):
    """
    Test that RECEIVE times out when connected to a stalled peer.

    The peer is a TCP listener that accepts the connection via the
    kernel listen backlog without calling accept(), and never transmits
    data. wermit is run as the receiver with SET SEND TIMEOUT 2 and
    SET RETRY-LIMIT 3. Verify that the process terminates within
    GIVE_UP_BOUND seconds rather than hanging.
    """
    port = get_free_port()
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", port))
    listener.listen(1)
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
        f"receive took {elapsed:.1f}s to give up on a peer that never "
        "sent a byte; a broken deadline mechanism would hang instead "
        "of exiting within this bound"
    )
    assert result.returncode != 0
    assert "Too many retries" in result.stdout, result.stdout


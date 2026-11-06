"""testkit.no_network makes any socket connection fail."""

import socket

import pytest

from rdf_persistence.testkit import no_network  # noqa: F401  (fixture)


def test_a_socket_connect_fails(no_network):  # noqa: F811
    with pytest.raises(RuntimeError, match="network"):
        socket.socket().connect(("127.0.0.1", 9))


def test_create_connection_fails(no_network):  # noqa: F811
    with pytest.raises(RuntimeError, match="network"):
        socket.create_connection(("127.0.0.1", 9))


def test_the_guard_is_gone_after_the_test():
    with pytest.raises(OSError):  # a real refused connection, not the guard
        socket.create_connection(("127.0.0.1", 9), timeout=1)

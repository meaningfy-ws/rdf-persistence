"""``no_network``: a fixture that makes any socket connection fail (PD-16)."""

import socket
from collections.abc import Iterator
from typing import NoReturn

import pytest

BLOCKED = "network access is blocked by the no_network fixture"


def _refuse(*_args: object, **_kwargs: object) -> NoReturn:
    raise RuntimeError(BLOCKED)


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make ``connect``, ``connect_ex`` and ``create_connection`` raise ``RuntimeError``."""
    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    yield

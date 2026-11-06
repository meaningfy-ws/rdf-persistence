"""The base of the HTTP adapters: one client with explicit timeouts, and transport errors mapped to the adapter's own error (PD-28a)."""

import httpx
import pytest

from rdf_persistence.adapters._http import (
    CONNECT_TIMEOUT_SECONDS,
    READ_TIMEOUT_SECONDS,
    HttpAdapter,
)
from rdf_persistence.domain.exceptions import PersistenceError


class ProbeUnavailableError(PersistenceError):
    """The error this test adapter raises when its server cannot be reached."""


class Probe(HttpAdapter):
    service = "Probe"
    unavailable = ProbeUnavailableError


def probe_answering(handler) -> Probe:
    return Probe(base_url="http://probe.test", transport=httpx.MockTransport(handler))


async def test_a_request_goes_through_the_given_transport() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    async with probe_answering(handler) as probe:
        response = await probe.request("GET", "/ping")
    assert response.status_code == 204
    assert str(seen[0].url) == "http://probe.test/ping"


async def test_a_transport_error_becomes_the_adapters_unavailable_error() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    async with probe_answering(refuse) as probe:
        with pytest.raises(ProbeUnavailableError, match="Probe is unreachable"):
            await probe.request("GET", "/ping")


async def test_the_timeouts_are_explicit() -> None:
    async with probe_answering(lambda _r: httpx.Response(200)) as probe:
        timeout = probe.client.timeout
    assert (timeout.connect, timeout.read) == (CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS)
    assert (CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS) == (5.0, 30.0)


async def test_leaving_the_context_closes_the_client() -> None:
    async with probe_answering(lambda _r: httpx.Response(200)) as probe:
        pass
    assert probe.client.is_closed

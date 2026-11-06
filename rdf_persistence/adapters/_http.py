"""The base of the HTTP adapters (PD-28a): one client with explicit timeouts, a transport for test doubles,
and one place that turns a transport error into the adapter's own "unavailable" error.

A request is never retried here; the caller decides.
"""

from http import HTTPMethod
from types import TracebackType
from typing import Any, ClassVar, Self

import httpx
from pydantic import BaseModel

from rdf_persistence.domain.exceptions import PersistenceError

CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 30.0
JSON = "application/json"
CONTENT_TYPE = "Content-Type"
EMPTY_JSON_OBJECT = "{}"


def json_body(body: BaseModel | None) -> dict[str, Any]:
    """The ``request`` arguments that send ``body`` as JSON, leaving out what is unset; ``{}`` when there is none."""
    content = body.model_dump_json(exclude_none=True) if body else EMPTY_JSON_OBJECT
    return {"content": content, "headers": {CONTENT_TYPE: JSON}}


class HttpAdapter:
    """An adapter over one HTTP server.

    A subclass names the server (``service``, for messages) and the error that means it cannot be
    reached (``unavailable``).
    """

    service: ClassVar[str]
    unavailable: ClassVar[type[PersistenceError]]

    def __init__(
        self,
        *,
        base_url: str = "",
        auth: httpx.Auth | None = None,
        headers: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.client = httpx.AsyncClient(
            base_url=base_url,
            auth=auth,
            headers=headers,
            transport=transport,
            timeout=httpx.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS),
        )

    async def request(self, method: HTTPMethod | str, url: str, **kwargs: Any) -> httpx.Response:
        """Send a request; a transport error raises the adapter's ``unavailable`` error."""
        try:
            return await self.client.request(method, url, **kwargs)
        except httpx.HTTPError as error:
            raise self.unavailable(f"{self.service} is unreachable: {error}") from error

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

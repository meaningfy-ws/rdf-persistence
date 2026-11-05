"""The Apache Jena Fuseki implementation of the ``Store`` port."""

import logging
from io import BytesIO
from types import TracebackType
from typing import Self
from urllib.parse import quote

import httpx
from rdflib import Graph, URIRef
from rdflib.query import Result

from rdf_persistence.domain.errors import (
    BadQuery,
    Conflict,
    DatabaseGone,
    NotFound,
    PersistenceError,
    StoreUnavailable,
)

SPARQL_QUERY = "application/sparql-query"
SPARQL_UPDATE = "application/sparql-update"
RESULTS_JSON = "application/sparql-results+json"
TURTLE = "text/turtle"
ADMIN_DATASETS = "/$/datasets"
DATASET_TYPE = "tdb2"
HTTP_BAD_REQUEST, HTTP_NOT_FOUND, HTTP_METHOD_NOT_ALLOWED, HTTP_CONFLICT = 400, 404, 405, 409
HTTP_SERVER_ERROR = 500
BAD_QUERY_MESSAGE = "Fuseki refused the SPARQL text as malformed"
UNREADABLE = "Fuseki answered with something unreadable"

log = logging.getLogger(__name__)


def _dataset_path(name: str, endpoint: str) -> str:
    return f"/{quote(name, safe='')}/{endpoint}"


def _raise_for_status(response: httpx.Response, *, on_missing: type[PersistenceError]) -> None:
    """Map a Fuseki status to the toolkit's errors; ``on_missing`` is raised for 404 and 405."""
    status = response.status_code
    if status >= HTTP_SERVER_ERROR:
        raise StoreUnavailable(f"Fuseki answered {status}")
    if status in (HTTP_NOT_FOUND, HTTP_METHOD_NOT_ALLOWED):
        raise on_missing(f"Fuseki answered {status} for {response.request.url.path}")
    if status == HTTP_CONFLICT:
        raise Conflict(f"Fuseki answered {status} for {response.request.url.path}")
    if status == HTTP_BAD_REQUEST:
        log.debug("Fuseki refused a request with 400: %s", response.text)
        raise BadQuery(BAD_QUERY_MESSAGE)
    if not response.is_success:  # 401, 403, 415, a redirect...: not the caller's to tell apart
        raise StoreUnavailable(f"Fuseki answered {status}")


def _read_result(response: httpx.Response) -> Result:
    if response.headers.get("content-type", "").startswith(RESULTS_JSON):
        return Result.parse(BytesIO(response.content), format="json")
    result = Result("CONSTRUCT")
    result.graph = Graph().parse(data=response.content, format="turtle")
    return result


class FusekiStore:
    """A ``Store`` over Fuseki's SPARQL, Graph Store and admin endpoints, with basic auth."""

    def __init__(
        self,
        url: str,
        user: str,
        password: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=url, auth=httpx.BasicAuth(user, password), transport=transport
        )

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _send(
        self, method: str, path: str, *, on_missing: type[PersistenceError] = DatabaseGone, **kwargs
    ) -> httpx.Response:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.TransportError as error:
            raise StoreUnavailable(f"Fuseki is unreachable: {error}") from error
        _raise_for_status(response, on_missing=on_missing)
        return response

    async def query(self, dataset: str, sparql: str) -> Result:
        response = await self._send(
            "POST",
            _dataset_path(dataset, "query"),
            content=sparql.encode(),
            headers={"Content-Type": SPARQL_QUERY, "Accept": f"{RESULTS_JSON}, {TURTLE};q=0.9"},
        )
        try:
            return _read_result(response)
        except Exception as error:  # rdflib's parsers raise many types; none is the caller's
            raise StoreUnavailable(f"{UNREADABLE}: {type(error).__name__}") from error

    async def update(self, dataset: str, sparql: str) -> None:
        await self._send(
            "POST",
            _dataset_path(dataset, "update"),
            content=sparql.encode(),
            headers={"Content-Type": SPARQL_UPDATE},
        )

    async def put_graph(self, dataset: str, graph_iri: URIRef, graph: Graph) -> None:
        await self._send(
            "PUT",
            _dataset_path(dataset, "data"),
            params={"graph": str(graph_iri)},
            content=graph.serialize(format="turtle").encode(),
            headers={"Content-Type": TURTLE},
        )

    async def create_dataset(self, name: str) -> None:
        await self._send(
            "POST",
            ADMIN_DATASETS,
            data={"dbName": name, "dbType": DATASET_TYPE},
            on_missing=NotFound,
        )

    async def drop_dataset(self, name: str) -> None:
        await self._send("DELETE", f"{ADMIN_DATASETS}/{quote(name, safe='')}", on_missing=NotFound)

    async def list_datasets(self) -> list[str]:
        response = await self._send("GET", ADMIN_DATASETS, on_missing=NotFound)
        try:
            return [entry["ds.name"].lstrip("/") for entry in response.json()["datasets"]]
        except (ValueError, KeyError, TypeError) as error:
            raise StoreUnavailable(f"{UNREADABLE}: {type(error).__name__}") from error

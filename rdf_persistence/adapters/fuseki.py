"""The Apache Jena Fuseki implementation of the ``Store`` port."""

import logging
from http import HTTPMethod, HTTPStatus
from io import BytesIO
from urllib.parse import quote

import httpx
from pydantic import ValidationError
from rdflib import Graph, URIRef
from rdflib.query import Result

from rdf_persistence.adapters._http import CONTENT_TYPE, HttpAdapter
from rdf_persistence.adapters.generated.rp_wire import FusekiDatasetList
from rdf_persistence.domain.exceptions import (
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
ACCEPT = "Accept"
# The endpoints of a dataset, and the administration endpoint of Fuseki.
QUERY_ENDPOINT, UPDATE_ENDPOINT, DATA_ENDPOINT = "query", "update", "data"
ADMIN_DATASETS = "/$/datasets"
# The form fields that create a dataset.
FORM_DB_NAME, FORM_DB_TYPE, DATASET_TYPE = "dbName", "dbType", "tdb2"
GRAPH_PARAM = "graph"
# The names rdflib gives the formats Fuseki speaks.
RDFLIB_JSON, RDFLIB_TURTLE = "json", "turtle"
BAD_QUERY_MESSAGE = "Fuseki refused the SPARQL text as malformed"
UNREADABLE = "Fuseki answered with something unreadable"

log = logging.getLogger(__name__)


def _dataset_path(name: str, endpoint: str) -> str:
    return f"/{quote(name, safe='')}/{endpoint}"


def _raise_for_status(response: httpx.Response, *, on_missing: type[PersistenceError]) -> None:
    """Map a Fuseki status to the toolkit's errors; ``on_missing`` is raised for 404 and 405."""
    status = response.status_code
    if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        raise StoreUnavailable(f"Fuseki answered {status}")
    if status in (HTTPStatus.NOT_FOUND, HTTPStatus.METHOD_NOT_ALLOWED):
        raise on_missing(f"Fuseki answered {status} for {response.request.url.path}")
    if status == HTTPStatus.CONFLICT:
        raise Conflict(f"Fuseki answered {status} for {response.request.url.path}")
    if status == HTTPStatus.BAD_REQUEST:
        log.debug("Fuseki refused a request with 400: %s", response.text)
        raise BadQuery(BAD_QUERY_MESSAGE)
    if not response.is_success:  # 401, 403, 415, a redirect...: not the caller's to tell apart
        raise StoreUnavailable(f"Fuseki answered {status}")


def _read_result(response: httpx.Response) -> Result:
    if response.headers.get("content-type", "").startswith(RESULTS_JSON):
        return Result.parse(BytesIO(response.content), format=RDFLIB_JSON)
    result = Result("CONSTRUCT")
    result.graph = Graph().parse(data=response.content, format=RDFLIB_TURTLE)
    return result


class FusekiStore(HttpAdapter):
    """A ``Store`` over Fuseki's SPARQL, Graph Store and admin endpoints, with basic auth."""

    service = "Fuseki"
    unavailable = StoreUnavailable

    def __init__(
        self,
        url: str,
        user: str,
        password: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(base_url=url, auth=httpx.BasicAuth(user, password), transport=transport)

    async def _send(
        self,
        method: HTTPMethod,
        path: str,
        *,
        on_missing: type[PersistenceError] = DatabaseGone,
        **kwargs,
    ) -> httpx.Response:
        response = await self.request(method, path, **kwargs)
        _raise_for_status(response, on_missing=on_missing)
        return response

    async def query(self, dataset: str, sparql: str) -> Result:
        response = await self._send(
            HTTPMethod.POST,
            _dataset_path(dataset, QUERY_ENDPOINT),
            content=sparql.encode(),
            headers={CONTENT_TYPE: SPARQL_QUERY, ACCEPT: f"{RESULTS_JSON}, {TURTLE};q=0.9"},
        )
        try:
            return _read_result(response)
        except Exception as error:  # rdflib's parsers raise many types; none is the caller's
            raise StoreUnavailable(f"{UNREADABLE}: {type(error).__name__}") from error

    async def update(self, dataset: str, sparql: str) -> None:
        await self._send(
            HTTPMethod.POST,
            _dataset_path(dataset, UPDATE_ENDPOINT),
            content=sparql.encode(),
            headers={CONTENT_TYPE: SPARQL_UPDATE},
        )

    async def put_graph(self, dataset: str, graph_iri: URIRef, graph: Graph) -> None:
        await self._send(
            HTTPMethod.PUT,
            _dataset_path(dataset, DATA_ENDPOINT),
            params={GRAPH_PARAM: str(graph_iri)},
            content=graph.serialize(format=RDFLIB_TURTLE).encode(),
            headers={CONTENT_TYPE: TURTLE},
        )

    async def create_dataset(self, name: str) -> None:
        await self._send(
            HTTPMethod.POST,
            ADMIN_DATASETS,
            data={FORM_DB_NAME: name, FORM_DB_TYPE: DATASET_TYPE},
            on_missing=NotFound,
        )

    async def drop_dataset(self, name: str) -> None:
        await self._send(
            HTTPMethod.DELETE, f"{ADMIN_DATASETS}/{quote(name, safe='')}", on_missing=NotFound
        )

    async def list_datasets(self) -> list[str]:
        response = await self._send(HTTPMethod.GET, ADMIN_DATASETS, on_missing=NotFound)
        try:
            listing = FusekiDatasetList.model_validate_json(response.content)
        except ValidationError as error:
            raise StoreUnavailable(UNREADABLE) from error
        return [entry.ds_name.lstrip("/") for entry in listing.datasets]

"""A ``Store`` over the SPARQL 1.1 Protocol and the Graph Store Protocol, whatever the server.

The base holds what the protocols fix: the query, update and graph PUT requests, their headers and
the mapping of an HTTP status to the toolkit's errors. A subclass names its server (``service``),
the paths of a dataset's endpoints and the operations the protocols leave out: creating, dropping and
listing datasets, and the dataset-level N-Quads.
"""

import logging
from abc import ABC, abstractmethod
from http import HTTPMethod, HTTPStatus
from io import BytesIO
from typing import ClassVar

import httpx
from rdflib import Graph, URIRef
from rdflib.query import Result

from rdf_persistence.core.adapters._http import HttpAdapter
from rdf_persistence.core.domain.exceptions import (
    BadQuery,
    Conflict,
    DatabaseGone,
    PersistenceError,
    StoreUnavailable,
)
from rdf_persistence.core.domain.media import ACCEPT, CONTENT_TYPE, TURTLE
from rdf_persistence.core.services.generated.rp_core_services import LogContext
from rdf_persistence.core.services.telemetry import log_extra

SPARQL_QUERY = "application/sparql-query"
SPARQL_UPDATE = "application/sparql-update"
RESULTS_JSON = "application/sparql-results+json"
GRAPH_PARAM = "graph"

log = logging.getLogger(__name__)


class SparqlProtocolStore(HttpAdapter, ABC):
    """The protocol half of a store; a subclass adds the layout of its server and its admin."""

    db_system_name: ClassVar[str]

    @abstractmethod
    def query_path(self, dataset: str) -> str:
        """The path a SPARQL query on ``dataset`` is posted to."""

    @abstractmethod
    def update_path(self, dataset: str) -> str:
        """The path a SPARQL update on ``dataset`` is posted to."""

    @abstractmethod
    def graph_store_path(self, dataset: str) -> str:
        """The path of ``dataset``'s Graph Store endpoint."""

    @abstractmethod
    async def create_dataset(self, name: str) -> None:
        """Create an empty dataset."""

    @abstractmethod
    async def drop_dataset(self, name: str) -> None:
        """Drop a dataset with everything in it."""

    @abstractmethod
    async def list_datasets(self) -> list[str]:
        """The names of the datasets the server holds."""

    @abstractmethod
    async def export_quads(self, dataset: str) -> bytes:
        """Every quad of ``dataset``, as N-Quads."""

    @abstractmethod
    async def import_quads(self, dataset: str, nquads: bytes) -> None:
        """Add N-Quads to ``dataset``."""

    @property
    def unreadable(self) -> str:
        """The message of an answer that cannot be read."""
        return f"{self.service} answered with something unreadable"

    async def _send(
        self,
        method: HTTPMethod,
        path: str,
        *,
        on_missing: type[PersistenceError] = DatabaseGone,
        **kwargs,
    ) -> httpx.Response:
        response = await self.request(method, path, **kwargs)
        self._raise_for_status(response, on_missing=on_missing)
        return response

    def _raise_for_status(
        self, response: httpx.Response, *, on_missing: type[PersistenceError]
    ) -> None:
        """Map a status to the toolkit's errors; ``on_missing`` is raised for 404 and 405."""
        status = response.status_code
        if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise StoreUnavailable(f"{self.service} answered {status}")
        if status in (HTTPStatus.NOT_FOUND, HTTPStatus.METHOD_NOT_ALLOWED):
            raise on_missing(f"{self.service} answered {status} for {response.request.url.path}")
        if status == HTTPStatus.CONFLICT:
            raise Conflict(f"{self.service} answered {status} for {response.request.url.path}")
        if status == HTTPStatus.BAD_REQUEST:
            log.debug(
                "A SPARQL Protocol store refused a request with 400",
                extra=log_extra(
                    LogContext(
                        step="store-bad-request",
                        db_system_name=self.db_system_name,
                        db_response_status_code="400",
                        response_body=response.text,
                    )
                ),
            )
            raise BadQuery(f"{self.service} refused the SPARQL text as malformed")
        if not response.is_success:  # 401, 403, 415, a redirect...: not the caller's to tell apart
            raise StoreUnavailable(f"{self.service} answered {status}")

    @staticmethod
    def _read_result(response: httpx.Response) -> Result:
        if response.headers.get("content-type", "").startswith(RESULTS_JSON):
            return Result.parse(BytesIO(response.content), format=RESULTS_JSON)
        result = Result("CONSTRUCT")
        result.graph = Graph().parse(data=response.content, format=TURTLE)
        return result

    async def query(self, dataset: str, sparql: str) -> Result:
        response = await self._send(
            HTTPMethod.POST,
            self.query_path(dataset),
            content=sparql.encode(),
            headers={CONTENT_TYPE: SPARQL_QUERY, ACCEPT: f"{RESULTS_JSON}, {TURTLE};q=0.9"},
        )
        try:
            return self._read_result(response)
        except Exception as error:  # rdflib's parsers raise many types; none is the caller's
            raise StoreUnavailable(f"{self.unreadable}: {type(error).__name__}") from error

    async def update(self, dataset: str, sparql: str) -> None:
        await self._send(
            HTTPMethod.POST,
            self.update_path(dataset),
            content=sparql.encode(),
            headers={CONTENT_TYPE: SPARQL_UPDATE},
        )

    async def put_graph(self, dataset: str, graph_iri: URIRef, graph: Graph) -> None:
        await self._send(
            HTTPMethod.PUT,
            self.graph_store_path(dataset),
            params={GRAPH_PARAM: str(graph_iri)},
            content=graph.serialize(format=TURTLE).encode(),
            headers={CONTENT_TYPE: TURTLE},
        )

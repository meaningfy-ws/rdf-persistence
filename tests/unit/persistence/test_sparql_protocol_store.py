"""SparqlProtocolStore: the SPARQL 1.1 Protocol half of a store, through a minimal subclass, with no network.

The subclass names a service ("Toy"), three paths and the admin operations; everything else, the
requests, the headers and the error mapping, is the base's (thematic-structure PD-7).
"""

import logging
from collections.abc import Callable

import httpx
import pytest
from rdflib import Graph, Literal, URIRef

from rdf_persistence.core.domain.exceptions import (
    BadQuery,
    Conflict,
    DatabaseGone,
    StoreUnavailable,
)
from rdf_persistence.persistence.adapters.sparql_protocol import SparqlProtocolStore
from rdf_persistence.testkit import assert_isomorphic
from tests.logs import attributes, records_of

URL = "http://toy.test:7878"
EX = "http://example.org/"
RESULTS_JSON = "application/sparql-results+json"
SELECT_ANSWER = b'{"head":{"vars":["s"]},"results":{"bindings":[]}}'


class ToyStore(SparqlProtocolStore):
    """The smallest store the base accepts: fixed paths, no admin."""

    service = "Toy"
    unavailable = StoreUnavailable
    db_system_name = "toy"

    def query_path(self, dataset: str) -> str:
        return f"/q/{dataset}"

    def update_path(self, dataset: str) -> str:
        return f"/u/{dataset}"

    def graph_store_path(self, dataset: str) -> str:
        return f"/g/{dataset}"

    async def create_dataset(self, name: str) -> None:
        raise NotImplementedError

    async def drop_dataset(self, name: str) -> None:
        raise NotImplementedError

    async def list_datasets(self) -> list[str]:
        raise NotImplementedError

    async def export_quads(self, dataset: str) -> bytes:
        raise NotImplementedError

    async def import_quads(self, dataset: str, nquads: bytes) -> None:
        raise NotImplementedError


class Recorder:
    """A MockTransport handler that records each request and answers with one response."""

    def __init__(self, response: Callable[[httpx.Request], httpx.Response] | httpx.Response):
        self.sent: list[httpx.Request] = []
        self._response = response

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.sent.append(request)
        return self._response(request) if callable(self._response) else self._response


def store_answering(response) -> tuple[ToyStore, Recorder]:
    recorder = Recorder(response)
    return ToyStore(base_url=URL, transport=httpx.MockTransport(recorder)), recorder


def reply(status: int = 200, content: bytes = b"", content_type: str = "text/plain"):
    return httpx.Response(status, content=content, headers={"content-type": content_type})


async def test_a_query_goes_to_the_subclass_path_as_sparql_query_text():  # TC-40
    store, recorder = store_answering(reply(content=SELECT_ANSWER, content_type=RESULTS_JSON))
    await store.query("d", "SELECT ?s WHERE { ?s ?p ?o }")
    request = recorder.sent[0]
    assert request.method == "POST", "a query is posted"
    assert request.url.path == "/q/d", "a query goes to the path the subclass names"
    assert request.headers["content-type"] == "application/sparql-query"
    assert request.headers["accept"] == f"{RESULTS_JSON}, text/turtle;q=0.9", (
        "both answers accepted"
    )
    assert request.content == b"SELECT ?s WHERE { ?s ?p ?o }", "the text is sent unchanged"


async def test_an_update_goes_to_the_subclass_path_as_sparql_update_text():  # TC-40
    store, recorder = store_answering(reply(204))
    await store.update("d", "CLEAR ALL")
    request = recorder.sent[0]
    assert request.method == "POST", "an update is posted"
    assert request.url.path == "/u/d", "an update goes to the path the subclass names"
    assert request.headers["content-type"] == "application/sparql-update"
    assert request.content == b"CLEAR ALL", "the text is sent unchanged"


async def test_a_graph_is_put_to_the_subclass_path_as_turtle_under_a_graph_parameter():  # TC-40
    store, recorder = store_answering(reply(204))
    graph = Graph()
    graph.add((URIRef(f"{EX}a"), URIRef(f"{EX}p"), Literal("v")))
    await store.put_graph("d", URIRef(f"{EX}g?x=1&y"), graph)
    request = recorder.sent[0]
    assert request.method == "PUT", "a graph is replaced with PUT"
    assert request.url.path == "/g/d", "a graph goes to the path the subclass names"
    assert request.url.params["graph"] == f"{EX}g?x=1&y", "the graph IRI is one encoded parameter"
    assert request.headers["content-type"].startswith("text/turtle")
    sent = Graph().parse(data=request.content.decode(), format="turtle")
    assert_isomorphic(sent, graph)  # the body is the graph, as Turtle


DATA_PLANE = {
    "query": lambda s: s.query("d", "ASK {}"),
    "update": lambda s: s.update("d", "CLEAR ALL"),
    "put_graph": lambda s: s.put_graph("d", URIRef(f"{EX}g"), Graph()),
}


@pytest.mark.parametrize("operation", DATA_PLANE)
@pytest.mark.parametrize(
    ("status", "error"),
    [
        (400, BadQuery),
        (404, DatabaseGone),
        (409, Conflict),
        (500, StoreUnavailable),
        (401, StoreUnavailable),
    ],
)
async def test_a_status_maps_to_the_toolkits_error(operation, status, error):  # TC-41
    store, _ = store_answering(reply(status, b"nope"))
    with pytest.raises(error):
        await DATA_PLANE[operation](store)


@pytest.mark.parametrize(
    ("status", "expected"),
    [(500, "Toy answered 500"), (404, "Toy answered 404"), (409, "Toy answered 409")],
)
async def test_an_error_message_names_the_service_of_the_subclass(status, expected):  # TC-41
    store, _ = store_answering(reply(status, b"nope"))
    with pytest.raises(Exception, match=expected) as raised:
        await store.update("d", "CLEAR ALL")
    assert "Fuseki" not in str(raised.value), "the base knows no Fuseki"


async def test_a_refused_query_says_so_in_the_name_of_the_service():  # TC-41
    store, _ = store_answering(reply(400, b"Parse error"))
    with pytest.raises(BadQuery, match="Toy refused the SPARQL text as malformed"):
        await store.query("d", "SELECT broken")


async def test_the_refusal_is_logged_under_the_base_with_the_db_system_of_the_subclass(caplog):
    store, _ = store_answering(reply(400, b"Parse error"))
    with (
        caplog.at_level(
            logging.DEBUG, logger="rdf_persistence.persistence.adapters.sparql_protocol"
        ),
        pytest.raises(BadQuery),
    ):
        await store.query("d", "SELECT broken")
    [record] = records_of(caplog, "store-bad-request")
    assert record.name == "rdf_persistence.persistence.adapters.sparql_protocol"
    assert record.getMessage() == "A SPARQL Protocol store refused a request with 400"
    assert attributes(record)["db.system.name"] == "toy", "the subclass names the system"


async def test_an_unreadable_query_answer_is_unavailable_and_names_the_service():  # TC-41
    store, _ = store_answering(reply(content=b"<html/>", content_type=RESULTS_JSON))
    with pytest.raises(StoreUnavailable, match="Toy answered with something unreadable"):
        await store.query("d", "ASK {}")


def test_a_subclass_without_a_db_system_name_cannot_be_instantiated():
    """The base declares ``db_system_name`` with no value; a 400 must never reach an AttributeError."""

    body = {
        name: member
        for name, member in vars(ToyStore).items()
        if name != "db_system_name" and not name.startswith("__")
    }
    forgetful = type("Forgetful", (SparqlProtocolStore,), body)
    with pytest.raises(TypeError, match="db_system_name"):
        forgetful(base_url=URL)


def test_the_base_cannot_be_instantiated_on_its_own():  # TC-42
    with pytest.raises(TypeError, match="abstract"):
        SparqlProtocolStore(base_url=URL)  # type: ignore[abstract]

"""FusekiStore request building and error mapping, with no network (httpx.MockTransport)."""

import base64
import logging
import urllib.parse
from collections.abc import Callable

import httpx
import pytest
from rdflib import Graph, Literal, URIRef

from rdf_persistence.adapters.fuseki import FusekiStore
from rdf_persistence.domain.exceptions import (
    BadQuery,
    Conflict,
    DatabaseGone,
    NotFound,
    StoreUnavailable,
)
from rdf_persistence.testkit import assert_isomorphic
from tests.logs import attributes, records_of

URL = "http://fuseki.test:3030"
EX = "http://example.org/"
RESULTS_JSON = "application/sparql-results+json"


class Recorder:
    """A MockTransport handler that records each request and answers with one response."""

    def __init__(self, response: Callable[[httpx.Request], httpx.Response] | httpx.Response):
        self.sent: list[httpx.Request] = []
        self._response = response

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.sent.append(request)
        return self._response(request) if callable(self._response) else self._response


def store_answering(response) -> tuple[FusekiStore, Recorder]:
    recorder = Recorder(response)
    return FusekiStore(URL, "u", "p", transport=httpx.MockTransport(recorder)), recorder


def reply(status: int = 200, content: bytes = b"", content_type: str = "text/plain"):
    return httpx.Response(status, content=content, headers={"content-type": content_type})


async def test_select_posts_the_query_and_returns_rows():
    body = (
        b'{"head":{"vars":["s","n"]},"results":{"bindings":[{"s":{"type":"uri","value":"'
        + EX.encode()
        + b'a"},"n":{"type":"literal","value":"5","datatype":"http://www.w3.org/2001/XMLSchema#integer"}}]}}'
    )
    store, recorder = store_answering(reply(content=body, content_type=RESULTS_JSON))
    result = await store.query("books", "SELECT ?s ?n WHERE { ?s ?p ?n }")
    request = recorder.sent[0]
    assert request.method == "POST", "a query is posted"
    assert request.url.path == "/books/query", "a query goes to the dataset's query endpoint"
    assert request.headers["content-type"] == "application/sparql-query", (
        "the query is sent as SPARQL query text"
    )
    assert request.content == b"SELECT ?s ?n WHERE { ?s ?p ?n }", "the query text is sent unchanged"
    rows = list(result)
    assert [(r.s, r.n) for r in rows] == [(URIRef(f"{EX}a"), Literal(5))], (
        "each row carries its bound values"
    )


async def test_ask_returns_the_boolean():
    store, _ = store_answering(
        reply(content=b'{"head":{},"boolean":true}', content_type=RESULTS_JSON)
    )
    result = await store.query("books", "ASK { ?s ?p ?o }")
    assert result.askAnswer is True, "an ask returns its boolean answer"


async def test_construct_returns_a_graph():
    turtle = f"<{EX}a> <{EX}p> <{EX}b> .".encode()
    store, _ = store_answering(reply(content=turtle, content_type="text/turtle"))
    result = await store.query("books", "CONSTRUCT WHERE { ?s ?p ?o }")
    expected = Graph()
    expected.add((URIRef(f"{EX}a"), URIRef(f"{EX}p"), URIRef(f"{EX}b")))
    assert_isomorphic(result.graph, expected)


async def test_requests_carry_basic_auth():
    store, recorder = store_answering(
        reply(content=b'{"head":{},"boolean":false}', content_type=RESULTS_JSON)
    )
    await store.query("books", "ASK {}")
    expected = "Basic " + base64.b64encode(b"u:p").decode()
    assert recorder.sent[0].headers["authorization"] == expected, (
        "requests carry the basic-auth header"
    )


async def test_update_posts_sparql_update():
    store, recorder = store_answering(reply(204))
    await store.update("books", "CLEAR ALL")
    request = recorder.sent[0]
    assert request.method == "POST", "an update is posted"
    assert request.url.path == "/books/update", "an update goes to the dataset's update endpoint"
    assert request.headers["content-type"] == "application/sparql-update", (
        "the update is sent as SPARQL update text"
    )
    assert request.content == b"CLEAR ALL", "the update text is sent unchanged"


async def test_put_graph_sends_turtle_to_the_graph_store_endpoint():
    store, recorder = store_answering(reply(204))
    graph = Graph()
    graph.add((URIRef(f"{EX}a"), URIRef(f"{EX}p"), Literal("v")))
    await store.put_graph("books", URIRef(f"{EX}g?x=1&y"), graph)
    request = recorder.sent[0]
    assert request.method == "PUT", "a graph is replaced with PUT"
    assert request.url.path == "/books/data", "a graph goes to the dataset's graph-store endpoint"
    assert request.url.params["graph"] == f"{EX}g?x=1&y", "the graph IRI is one encoded parameter"
    assert request.headers["content-type"].startswith("text/turtle"), "the graph is sent as Turtle"
    sent = Graph().parse(data=request.content.decode(), format="turtle")
    assert_isomorphic(sent, graph)


async def test_create_dataset_posts_a_tdb2_name():
    store, recorder = store_answering(reply(200))
    await store.create_dataset("books")
    request = recorder.sent[0]
    assert request.method == "POST", "a dataset is created with POST"
    assert request.url.path == "/$/datasets", "a dataset is created at the admin endpoint"
    assert urllib.parse.parse_qs(request.content.decode()) == {
        "dbName": ["books"],
        "dbType": ["tdb2"],
    }, "the dataset is created as a tdb2 database with the given name"


async def test_drop_dataset_deletes_by_name():
    store, recorder = store_answering(reply(200))
    await store.drop_dataset("books")
    assert recorder.sent[0].method == "DELETE", "a dataset is dropped with DELETE"
    assert recorder.sent[0].url.path == "/$/datasets/books", "a dataset is dropped by its name"


async def test_list_datasets_returns_names_without_the_slash():
    body = b'{"datasets":[{"ds.name":"/a","ds.state":true},{"ds.name":"/b","ds.state":true}]}'
    store, recorder = store_answering(reply(content=body, content_type="application/json"))
    assert await store.list_datasets() == ["a", "b"], (
        "datasets are listed by name without the leading slash"
    )
    assert recorder.sent[0].method == "GET", "datasets are listed with GET"
    assert recorder.sent[0].url.path == "/$/datasets", "datasets are listed at the admin endpoint"


async def test_a_dataset_name_cannot_change_the_path():
    store, recorder = store_answering(reply(204))
    await store.update("a/../$/datasets", "CLEAR ALL")
    assert recorder.sent[0].url.raw_path.decode() == "/a%2F..%2F%24%2Fdatasets/update", (
        "a dataset name cannot change the request path"
    )


# (operation, call) pairs: every data-plane operation maps a missing dataset the same way.
DATA_PLANE = {
    "query": lambda s: s.query("d", "ASK {}"),
    "update": lambda s: s.update("d", "CLEAR ALL"),
    "put_graph": lambda s: s.put_graph("d", URIRef(f"{EX}g"), Graph()),
}


@pytest.mark.parametrize("operation", DATA_PLANE)
@pytest.mark.parametrize(
    ("status", "error"),
    # One case per branch of _raise_for_status; 500 stands for the whole `>= 500` class
    # (503 is the same branch), 404 and 405 are the explicit pair.
    [
        (405, DatabaseGone),
        (404, DatabaseGone),
        (400, BadQuery),
        (500, StoreUnavailable),
    ],
)
async def test_data_plane_statuses_map_to_errors(operation, status, error):
    store, _ = store_answering(reply(status, b"nope"))
    with pytest.raises(error):
        await DATA_PLANE[operation](store)


@pytest.mark.parametrize("operation", DATA_PLANE)
# One class: every httpx.TransportError is mapped once in _http; ConnectError stands for it.
@pytest.mark.parametrize("failure", [httpx.ConnectError("refused")])
async def test_an_unreachable_store_is_unavailable(operation, failure):
    def refuse(request):
        raise failure

    store = FusekiStore(URL, "u", "p", transport=httpx.MockTransport(refuse))
    with pytest.raises(StoreUnavailable):
        await DATA_PLANE[operation](store)


@pytest.mark.parametrize("operation", DATA_PLANE)
async def test_an_answer_that_cannot_be_decoded_is_unavailable(operation):
    """A body that claims gzip but is not raises httpx.DecodingError, which is not a transport error."""
    undecodable = httpx.Response(
        200, stream=httpx.ByteStream(b"plain"), headers={"content-encoding": "gzip"}
    )
    store, _ = store_answering(undecodable)
    with pytest.raises(StoreUnavailable):
        await DATA_PLANE[operation](store)


async def test_creating_an_existing_dataset_is_a_conflict():
    store, _ = store_answering(reply(409))
    with pytest.raises(Conflict):
        await store.create_dataset("books")


async def test_dropping_a_missing_dataset_is_not_found():
    store, _ = store_answering(reply(404))
    with pytest.raises(NotFound):
        await store.drop_dataset("books")


@pytest.mark.parametrize("call", ["create_dataset", "drop_dataset", "list_datasets"])
async def test_admin_5xx_is_unavailable(call):
    store, _ = store_answering(reply(502))
    args = () if call == "list_datasets" else ("books",)
    with pytest.raises(StoreUnavailable):
        await getattr(store, call)(*args)


async def test_the_store_closes_its_client():
    store, _ = store_answering(reply(204))
    async with store:
        pass
    with pytest.raises(RuntimeError):
        await store.update("d", "CLEAR ALL")


ADMIN_PLANE = {
    "create_dataset": lambda s: s.create_dataset("d"),
    "drop_dataset": lambda s: s.drop_dataset("d"),
    "list_datasets": lambda s: s.list_datasets(),
}


@pytest.mark.parametrize("operation", [*DATA_PLANE, *ADMIN_PLANE])
# One class: every other non-success status falls to the one `not response.is_success` branch.
@pytest.mark.parametrize("status", [301])
async def test_any_other_unsuccessful_status_is_unavailable(operation, status):
    store, _ = store_answering(reply(status, b"nope"))
    call = {**DATA_PLANE, **ADMIN_PLANE}[operation]
    with pytest.raises(StoreUnavailable, match=str(status)):
        await call(store)


async def test_a_refused_query_carries_a_fixed_message_and_the_body_only_in_the_log(caplog):
    body = b"Parse error: SELECT secret-token-in-the-query"
    store, _ = store_answering(reply(400, body))
    with (
        caplog.at_level(logging.DEBUG, logger="rdf_persistence.adapters.fuseki"),
        pytest.raises(BadQuery) as raised,
    ):
        await store.query("d", "SELECT broken")
    assert "secret-token-in-the-query" not in str(raised.value), "the body is not in the error"
    assert str(raised.value), "but the error says something"
    [record] = records_of(caplog, "store-bad-request")
    assert "secret-token-in-the-query" not in record.getMessage(), "the message is constant"
    assert "secret-token-in-the-query" in str(attributes(record)["rp.store.response_body"]), (
        "the body is in the log, as an attribute"
    )


async def test_a_refused_query_logs_one_debug_record_with_the_status_and_the_body(caplog):  # TC-19
    body = "Parse error: SELECT secret-token-in-the-query"
    store, _ = store_answering(reply(400, body.encode()))
    with (
        caplog.at_level(logging.DEBUG, logger="rdf_persistence.adapters.fuseki"),
        pytest.raises(BadQuery),
    ):
        await store.query("d", "SELECT broken")
    [record] = records_of(caplog, "store-bad-request")
    assert record.levelno == logging.DEBUG, "the body is written at DEBUG only"
    assert record.getMessage() == "Fuseki refused a request with 400"
    assert attributes(record) == {
        "rp.step": "store-bad-request",
        "db.system.name": "fuseki",
        "db.response.status_code": "400",
        "rp.store.response_body": body,
    }
    assert [r for r in caplog.records if r.levelno > logging.DEBUG] == [], "nothing above DEBUG"


BAD_ANSWERS = {
    "json results that are not json": (b"<html>proxy</html>", RESULTS_JSON),
    "json results of no known shape": (b'{"head":{}}', RESULTS_JSON),
    "turtle that is not turtle": (b"<html>proxy</html>", "text/turtle"),
    "an answer of no known type": (b"<html>proxy</html>", "text/html"),
}


@pytest.mark.parametrize(("body", "content_type"), BAD_ANSWERS.values(), ids=BAD_ANSWERS.keys())
async def test_an_unreadable_query_answer_is_unavailable(body, content_type):
    store, _ = store_answering(reply(200, body, content_type))
    with pytest.raises(StoreUnavailable, match="unreadable"):
        await store.query("d", "SELECT * WHERE { ?s ?p ?o }")


@pytest.mark.parametrize("body", [b"not json", b'{"nodatasets":[]}', b'{"datasets":[{"x":1}]}'])
async def test_an_unreadable_dataset_list_is_unavailable(body):
    store, _ = store_answering(reply(200, body, "application/json"))
    with pytest.raises(StoreUnavailable, match="unreadable"):
        await store.list_datasets()

"""Graph loading: parse in a worker thread, refuse what does not parse, write one named graph."""

import io
import json
import threading
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import UUID

import pytest
from rdflib import XSD, Graph, Literal, URIRef
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence import InvalidGraph
from rdf_persistence.domain.exceptions import DatabaseGone, InvalidIri, NotFound, StoreUnavailable
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.loading import _RDFLIB_FORMATS, parse_graph
from rdf_persistence.services.session import Session
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE

TENANT = "https://example.org/libraries/6f1c"
AGGREGATE = f"{TENANT}/books/{UUID(int=1)}"
TITLE = URIRef("http://purl.org/dc/terms/title")
BOOK = URIRef("https://example.org/b")
EXPECTED = Graph()
EXPECTED.add((BOOK, TITLE, Literal("Dune")))
GOOD = {
    RdfFormat.TURTLE: b'<https://example.org/b> <http://purl.org/dc/terms/title> "Dune" .',
    RdfFormat.NTRIPLES: b'<https://example.org/b> <http://purl.org/dc/terms/title> "Dune" .\n',
    RdfFormat.RDFXML: (
        b'<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        b'xmlns:dc="http://purl.org/dc/terms/"><rdf:Description rdf:about="https://example.org/b">'
        b"<dc:title>Dune</dc:title></rdf:Description></rdf:RDF>"
    ),
    RdfFormat.JSONLD: (
        b'{"@id": "https://example.org/b", "http://purl.org/dc/terms/title": "Dune"}'
    ),
}
BROKEN = {
    RdfFormat.TURTLE: b"<https://example.org/b> <http://purl.org/dc/terms/title> ",
    RdfFormat.NTRIPLES: b"this is not a triple\n",
    RdfFormat.RDFXML: b"<rdf:RDF><unclosed>",
    RdfFormat.JSONLD: b'{"@id": ',
}


@pytest.fixture
async def store():
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


@pytest.fixture
async def session(store) -> AsyncIterator[Session]:
    async with fake_session(
        store, tenant_iri=TENANT, principal=Principal(id="https://example.org/people/ada")
    ) as opened:
        yield opened


def test_every_format_has_a_good_and_a_broken_sample():
    assert set(GOOD) == set(BROKEN) == set(RdfFormat), "a row for every format"


@pytest.mark.parametrize("fmt", list(RdfFormat), ids=lambda f: f.value)
async def test_a_good_file_is_written_to_a_new_graph_under_the_aggregate(store, session, fmt):
    loaded = await session.load_graph(AGGREGATE, GOOD[fmt], rdf_format=fmt)
    assert str(loaded).startswith(f"{AGGREGATE}/content/"), "the loaded graph IRI"
    assert store.sent("put_graph") == [str(loaded)], "one graph written, under that IRI"


async def test_the_loaded_triples_are_those_of_the_file(store, session):
    loaded = await session.load_graph(
        AGGREGATE, GOOD[RdfFormat.TURTLE], rdf_format=RdfFormat.TURTLE
    )
    query = fill("CONSTRUCT { ?s ?p ?o } WHERE { GRAPH $g { ?s ?p ?o } }", g=term(loaded))
    held = (await store.query(FAKE_DATABASE, query)).graph
    assert isomorphic(held, EXPECTED), graph_diff(held, EXPECTED)


async def test_each_load_gets_its_own_graph(store, session):
    args = (AGGREGATE, GOOD[RdfFormat.TURTLE])
    first = await session.load_graph(*args, rdf_format=RdfFormat.TURTLE)
    second = await session.load_graph(*args, rdf_format=RdfFormat.TURTLE)
    assert first != second, "a fresh IRI every time"


@pytest.mark.parametrize("fmt", list(RdfFormat), ids=lambda f: f.value)
async def test_a_broken_file_is_refused_with_the_parsers_message_and_nothing_is_sent(
    store, session, fmt
):
    with pytest.raises(InvalidGraph) as raised:
        await session.load_graph(AGGREGATE, BROKEN[fmt], rdf_format=fmt)
    assert str(raised.value), "the parser's message is carried"
    assert store.sent("put_graph") == [], "no graph written"
    assert store.sent("update") == [] and store.sent("query") == [], "the store was not touched"


async def test_parsing_runs_in_a_worker_thread(store, session, monkeypatch):
    seen: list[str] = []
    original = Graph.parse

    def spy(self, *args, **kwargs):
        seen.append(threading.current_thread().name)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Graph, "parse", spy)
    await session.load_graph(AGGREGATE, GOOD[RdfFormat.TURTLE], rdf_format=RdfFormat.TURTLE)
    assert seen and seen[0] != threading.main_thread().name, "not on the event-loop thread"


async def test_an_aggregate_outside_the_tenant_is_refused_before_any_request(session, store):
    with pytest.raises(ValueError, match="not an aggregate IRI of the tenant"):
        await session.load_graph(
            "https://example.org/other/books/1", GOOD[RdfFormat.TURTLE], rdf_format=RdfFormat.TURTLE
        )
    assert store.sent("put_graph") == [], "nothing was written"


def rdflib_message(data: bytes, fmt: RdfFormat) -> str:
    """What rdflib itself says about ``data``."""
    with pytest.raises(Exception) as raised:
        Graph().parse(io.BytesIO(data), format=_RDFLIB_FORMATS[fmt])
    return str(raised.value)


@pytest.mark.parametrize("fmt", list(RdfFormat), ids=lambda f: f.value)
async def test_the_message_of_a_refused_file_is_the_parsers_own(fmt):
    with pytest.raises(InvalidGraph) as raised:
        await parse_graph(BROKEN[fmt], fmt)
    assert str(raised.value) == rdflib_message(BROKEN[fmt], fmt)


async def test_a_format_the_toolkit_does_not_know_is_a_bug_and_not_an_invalid_graph():
    with pytest.raises(KeyError):
        await parse_graph(b"", "not-a-format")  # type: ignore[arg-type]


class _Recorder(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.requests.append(self.path)  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "application/ld+json")
        self.end_headers()
        self.wfile.write(b'{"@context": {"title": "http://purl.org/dc/terms/title"}}')

    def log_message(self, *args):  # silence
        pass


@pytest.fixture
def context_server() -> Iterator[HTTPServer]:
    """A local server that records every request made to it."""
    server = HTTPServer(("127.0.0.1", 0), _Recorder)
    server.requests = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def jsonld(context: object) -> bytes:
    return json.dumps(
        {"@context": context, "@id": "https://example.org/b", "title": "Dune"}
    ).encode()


NON_INLINE = {
    "iri": lambda url: jsonld(url),
    "iri in an array": lambda url: jsonld([{"x": "http://example.org/x"}, url]),
    "file iri": lambda _: jsonld("file:///etc/hostname"),
    "bare path": lambda _: jsonld("/etc/hostname"),
    "relative path": lambda _: jsonld("context.jsonld"),
    "nested in a node": lambda url: json.dumps(
        {
            "@id": "https://example.org/b",
            "http://example.org/p": {"@context": url, "@id": "https://example.org/c"},
        }
    ).encode(),
    "in a graph array": lambda url: json.dumps(
        [{"@context": url, "@id": "https://example.org/b"}]
    ).encode(),
    "scoped in a term": lambda url: jsonld(
        {"title": {"@id": "http://purl.org/dc/terms/title", "@context": url}}
    ),
    "@import": lambda url: jsonld({"@import": url}),
}


@pytest.mark.parametrize("make", NON_INLINE.values(), ids=NON_INLINE.keys())
async def test_a_jsonld_context_that_is_not_inline_is_refused_and_nothing_is_fetched(
    context_server, make
):
    url = f"http://127.0.0.1:{context_server.server_port}/context.jsonld"
    with pytest.raises(InvalidGraph, match="inline"):
        await parse_graph(make(url), RdfFormat.JSONLD)
    assert context_server.requests == [], "the server was never asked"


@pytest.mark.parametrize(
    "context",
    [
        {"title": "http://purl.org/dc/terms/title"},
        [{"title": "http://purl.org/dc/terms/title"}],
        None,
    ],
    ids=["object", "array of objects", "null"],
)
async def test_an_inline_jsonld_context_still_parses(context):
    data = jsonld(context)
    if context is None:
        data = data.replace(b'"title"', b'"http://purl.org/dc/terms/title"')
    graph = await parse_graph(data, RdfFormat.JSONLD)
    assert isomorphic(graph, EXPECTED), graph_diff(graph, EXPECTED)


SECOND = f"{TENANT}/books/{UUID(int=2)}"


async def loaded_for(session, iri):
    """Load the sample Turtle for ``iri`` and commit the aggregate so the graph is registered."""
    loaded = await session.load_graph(iri, GOOD[RdfFormat.TURTLE], rdf_format=RdfFormat.TURTLE)
    await session.add_graph(iri, [], [loaded])
    return loaded


async def test_a_loaded_graph_reads_back_as_the_file_that_was_loaded(session):
    loaded = await loaded_for(session, AGGREGATE)
    read = await session.loaded_graph(AGGREGATE, str(loaded))
    assert isomorphic(read, EXPECTED), graph_diff(read, EXPECTED)


async def test_a_graph_of_another_aggregate_or_an_unknown_one_is_not_found(session):
    await loaded_for(session, AGGREGATE)
    other = await loaded_for(session, SECOND)
    with pytest.raises(NotFound):
        await session.loaded_graph(AGGREGATE, str(other))
    with pytest.raises(NotFound):
        await session.loaded_graph(AGGREGATE, f"{AGGREGATE}/content/{UUID(int=9)}")


async def listed_by_a_new_session(store, iri):
    """The loaded graphs of ``iri`` as a later request, in a session of its own, sees them."""
    async with fake_session(store, tenant_iri=TENANT) as later:
        return await later.loaded_graphs(iri)


async def test_a_later_session_finds_the_loaded_graph_and_reads_it(store, session):
    loaded = await loaded_for(session, AGGREGATE)
    await loaded_for(session, SECOND)
    assert await listed_by_a_new_session(store, AGGREGATE) == [loaded], "only this aggregate's"
    async with fake_session(store, tenant_iri=TENANT) as later:
        (graph_iri,) = await later.loaded_graphs(AGGREGATE)
        read = await later.loaded_graph(AGGREGATE, graph_iri)
    assert isomorphic(read, EXPECTED), graph_diff(read, EXPECTED)


async def test_after_a_replace_only_the_new_loaded_graph_is_listed(store, session):
    await loaded_for(session, AGGREGATE)
    _, _, version = await session.get_graph(AGGREGATE)
    new = await session.load_graph(AGGREGATE, GOOD[RdfFormat.TURTLE], rdf_format=RdfFormat.TURTLE)
    version = await session.replace_graph(AGGREGATE, [], version, [new])
    assert await listed_by_a_new_session(store, AGGREGATE) == [new]
    await session.replace_graph(AGGREGATE, [], version)
    assert await listed_by_a_new_session(store, AGGREGATE) == [new], "None keeps the registered"


async def test_several_loaded_graphs_are_listed_sorted_by_iri(store, session):
    graphs = [
        await session.load_graph(AGGREGATE, GOOD[RdfFormat.TURTLE], rdf_format=RdfFormat.TURTLE)
        for _ in range(3)
    ]
    await session.add_graph(AGGREGATE, [], graphs)
    assert await listed_by_a_new_session(store, AGGREGATE) == sorted(graphs)


async def test_an_aggregate_without_loaded_graphs_lists_none(store, session):
    await session.add_graph(AGGREGATE, [])
    unregistered = await session.load_graph(
        SECOND, GOOD[RdfFormat.TURTLE], rdf_format=RdfFormat.TURTLE
    )
    await session.add_graph(SECOND, [])
    assert await listed_by_a_new_session(store, AGGREGATE) == []
    assert unregistered not in await listed_by_a_new_session(store, SECOND), "loaded, not committed"


async def test_a_removed_or_never_stored_aggregate_is_not_found(session):
    await loaded_for(session, AGGREGATE)
    _, _, version = await session.get_graph(AGGREGATE)
    await session.remove(AGGREGATE, version)
    with pytest.raises(NotFound):
        await session.loaded_graphs(AGGREGATE)
    with pytest.raises(NotFound):
        await session.loaded_graphs(SECOND)


async def test_an_iri_the_policy_does_not_mint_is_refused_before_any_query(store, session):
    before = len(store.sent("query"))
    with pytest.raises(InvalidIri):
        await session.loaded_graphs("https://elsewhere.example/books/1")
    assert len(store.sent("query")) == before, "nothing sent"


async def test_a_dropped_tenant_database_is_reported(store, session):
    await store.drop_dataset(FAKE_DATABASE)
    with pytest.raises(DatabaseGone):
        await session.loaded_graphs(AGGREGATE)


# -- the load marker (live-tenant-sweep PD-2) ---------------------------------------------------

MARKER_TIME = datetime(2026, 11, 10, 9, 30, tzinfo=UTC)
LOADED_AT = URIRef("https://meaningfy.ws/ns/rdf-persistence#loadedAt")
PRINCIPAL = Principal(id="https://example.org/people/ada")


class _OrderedStore(FakeStore):
    """A fake store that also records the order of its writes across operations."""

    def __init__(self) -> None:
        super().__init__()
        self.order: list[str] = []

    async def update(self, dataset, sparql):
        self.order.append("update")
        await super().update(dataset, sparql)

    async def put_graph(self, dataset, graph_iri, graph):
        self.order.append("put_graph")
        await super().put_graph(dataset, graph_iri, graph)


async def _marker_triples(store, loaded) -> list[tuple]:
    registry = DEFAULT_IRIS.registry(TENANT)
    query = fill(
        "SELECT ?p ?o WHERE { GRAPH $registry { $g ?p ?o } }",
        registry=term(registry),
        g=term(loaded),
    )
    return [(row.p, row.o) for row in await store.query(FAKE_DATABASE, query)]


async def _marked(clock=lambda: MARKER_TIME, store=None):
    store = store or _OrderedStore()
    await store.create_dataset(FAKE_DATABASE)
    return store, fake_session(store, tenant_iri=TENANT, principal=PRINCIPAL, clock=clock)


async def test_the_marker_is_written_to_the_registry_before_the_graph_is_put():
    store, opened = await _marked()
    async with opened as session:
        loaded = await session.load_graph(
            AGGREGATE, GOOD[RdfFormat.TURTLE], rdf_format=RdfFormat.TURTLE
        )
    assert store.order == ["update", "put_graph"], "a crash between the two leaves a marker only"
    expected = [(LOADED_AT, Literal(MARKER_TIME))]
    assert await _marker_triples(store, loaded) == expected, "the one marker triple, nothing more"


async def test_the_marker_holds_the_session_clock_as_a_date_time():
    store, opened = await _marked(clock=lambda: MARKER_TIME)
    async with opened as session:
        loaded = await session.load_graph(
            AGGREGATE, GOOD[RdfFormat.TURTLE], rdf_format=RdfFormat.TURTLE
        )
    ((_, stamp),) = await _marker_triples(store, loaded)
    assert stamp.datatype == XSD.dateTime and stamp.toPython() == MARKER_TIME


async def test_a_failed_put_leaves_the_marker():
    store, opened = await _marked()
    store.on("put_graph", StoreUnavailable("down"))
    async with opened as session:
        with pytest.raises(StoreUnavailable):
            await session.load_graph(AGGREGATE, GOOD[RdfFormat.TURTLE], rdf_format=RdfFormat.TURTLE)
    registry = DEFAULT_IRIS.registry(TENANT)
    held = await store.query(
        FAKE_DATABASE,
        fill("ASK { GRAPH $r { ?g $p ?t } }", r=term(registry), p=term(LOADED_AT)),
    )
    assert held.askAnswer, "the marker is there for the sweep to clear"


async def test_a_commit_of_the_loaded_graph_keeps_its_registry_entry_and_listing():
    store, opened = await _marked()
    async with opened as session:
        loaded = await session.load_graph(
            AGGREGATE, GOOD[RdfFormat.TURTLE], rdf_format=RdfFormat.TURTLE
        )
        await session.add_graph(AGGREGATE, [], loaded_graphs=[loaded])
        assert await session.loaded_graphs(AGGREGATE) == [loaded], "still registered and listed"
    properties = {p for p, _ in await _marker_triples(store, loaded)}
    assert v.REGISTRY_OWNED_BY in properties and v.REGISTRY_KIND in properties

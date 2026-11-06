"""Graph loading: parse in a worker thread, refuse what does not parse, write one named graph."""

import io
import json
import threading
from collections.abc import AsyncIterator, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence import InvalidGraph
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services.loading import _RDFLIB_FORMATS, parse_graph
from rdf_persistence.services.session import Session
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE

TENANT = "https://example.org/libraries/6f1c"
AGGREGATE = f"{TENANT}/books/1"
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
    with pytest.raises(ValueError, match="not inside the tenant"):
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

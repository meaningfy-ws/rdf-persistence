"""Graph loading: parse in a worker thread, refuse what does not parse, write one named graph."""

import threading

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence import InvalidGraph
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services.session import Session
from rdf_persistence.testkit import FakeStore

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
    await fake.create_dataset("db")
    return fake


@pytest.fixture
def session(store) -> Session:
    return Session(
        store,
        database="db",
        tenant_iri=TENANT,
        principal=Principal(id="https://example.org/people/ada"),
        clock=lambda: None,
    )


def test_every_format_has_a_good_and_a_broken_sample():
    assert set(GOOD) == set(BROKEN) == set(RdfFormat), "a row for every format"


@pytest.mark.parametrize("fmt", list(RdfFormat), ids=lambda f: f.value)
async def test_a_good_file_is_written_to_a_new_graph_under_the_aggregate(store, session, fmt):
    loaded = await session.load_graph(AGGREGATE, GOOD[fmt], format=fmt)
    assert str(loaded).startswith(f"{AGGREGATE}/content/"), "the loaded graph IRI"
    assert store.sent("put_graph") == [str(loaded)], "one graph written, under that IRI"


async def test_the_loaded_triples_are_those_of_the_file(store, session):
    loaded = await session.load_graph(AGGREGATE, GOOD[RdfFormat.TURTLE], format=RdfFormat.TURTLE)
    query = fill("CONSTRUCT { ?s ?p ?o } WHERE { GRAPH $g { ?s ?p ?o } }", g=term(loaded))
    held = (await store.query("db", query)).graph
    assert isomorphic(held, EXPECTED), graph_diff(held, EXPECTED)


async def test_each_load_gets_its_own_graph(store, session):
    args = (AGGREGATE, GOOD[RdfFormat.TURTLE])
    first = await session.load_graph(*args, format=RdfFormat.TURTLE)
    second = await session.load_graph(*args, format=RdfFormat.TURTLE)
    assert first != second, "a fresh IRI every time"


@pytest.mark.parametrize("fmt", list(RdfFormat), ids=lambda f: f.value)
async def test_a_broken_file_is_refused_with_the_parsers_message_and_nothing_is_sent(
    store, session, fmt
):
    with pytest.raises(InvalidGraph) as raised:
        await session.load_graph(AGGREGATE, BROKEN[fmt], format=fmt)
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
    await session.load_graph(AGGREGATE, GOOD[RdfFormat.TURTLE], format=RdfFormat.TURTLE)
    assert seen and seen[0] != threading.main_thread().name, "not on the event-loop thread"


async def test_an_aggregate_outside_the_tenant_is_refused_before_any_request(session, store):
    with pytest.raises(ValueError, match="not inside the tenant"):
        await session.load_graph(
            "https://example.org/other/books/1", GOOD[RdfFormat.TURTLE], format=RdfFormat.TURTLE
        )
    assert store.sent("put_graph") == [], "nothing was written"

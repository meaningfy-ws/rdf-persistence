"""The one JSON-LD path (PD-6): bodies and loaded files read by the same PyLD call, the same refusals."""

import json
from uuid import UUID

import pytest
from rdflib import Graph, URIRef

from rdf_persistence import InvalidGraph
from rdf_persistence.core.domain.exceptions import InvalidBody
from rdf_persistence.core.domain.media import JSON, JSON_LD
from rdf_persistence.files.domain.generated.rp_files import RdfFormat
from rdf_persistence.persistence.services import jsonld as one_path
from rdf_persistence.persistence.services.jsonld import NO_BASE, triples_of
from rdf_persistence.persistence.services.loading import NOT_INLINE, parse_graph
from rdf_persistence.testkit import (  # noqa: F401  (no_network is a fixture)
    FakeStore,
    assert_isomorphic,
    fake_session,
    no_network,
)
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import BOOK_JSON, TENANT, book_iri, encoded

TITLE = "http://purl.org/dc/terms/title"
BOOK = f"{TENANT}/books/{UUID(int=1)}"
CONTEXT_UNREACHABLE = "http://context.invalid/context.jsonld"
ABSOLUTE = "a JSON-LD document must use absolute IRIs"

# What rdflib's own json-ld parser gave for the good JSON-LD samples of test_loading.py, read on the
# code before the swap: the same single triple whatever the inline context (TC-43).
RDFLIB_GOLDEN = '<https://example.org/b> <http://purl.org/dc/terms/title> "Dune" .\n'
GOOD_SAMPLES = {
    "no context": {"@id": "https://example.org/b", TITLE: "Dune"},
    "object context": {
        "@context": {"title": TITLE},
        "@id": "https://example.org/b",
        "title": "Dune",
    },
    "array context": {
        "@context": [{"title": TITLE}],
        "@id": "https://example.org/b",
        "title": "Dune",
    },
    "null context": {"@context": None, "@id": "https://example.org/b", TITLE: "Dune"},
}


def encoded_file(document: object) -> bytes:
    return json.dumps(document).encode()


@pytest.mark.parametrize("document", GOOD_SAMPLES.values(), ids=GOOD_SAMPLES.keys())
async def test_a_good_file_loads_to_the_triples_rdflib_gave(document):
    golden = Graph().parse(data=RDFLIB_GOLDEN, format="nt")
    graph = await parse_graph(encoded_file(document), RdfFormat.JSONLD)
    assert_isomorphic(graph, golden)


def test_a_document_without_a_graph_keyword_gives_its_triples_as_the_default_graph():
    graph = triples_of({"@graph": [{"@id": "https://example.org/b", TITLE: "Dune"}]})
    assert (URIRef("https://example.org/b"), URIRef(TITLE), None) in graph, (
        "TC-42: a top-level @graph with no @id is the default graph"
    )


async def test_a_loaded_file_with_a_top_level_graph_and_no_id_loads():
    document = {"@graph": [{"@id": "https://example.org/b", TITLE: "Dune"}]}
    graph = await parse_graph(encoded_file(document), RdfFormat.JSONLD)
    assert len(graph) == 1, "TC-42: the triples of the default graph"


NAMED_GRAPH = {"@id": "urn:g", "@graph": [{"@id": "https://example.org/b", TITLE: "Dune"}]}


def test_a_named_graph_is_refused_by_triples_of():
    with pytest.raises(one_path.NamedGraphRefused):
        triples_of(NAMED_GRAPH)


async def test_a_loaded_file_holding_a_named_graph_is_refused_and_nothing_is_sent():
    store = FakeStore()
    await store.create_dataset(FAKE_DATABASE)
    async with fake_session(store, tenant_iri=TENANT) as session:
        with pytest.raises(InvalidGraph, match="a loaded file holds one graph"):
            await session.load_graph(BOOK, encoded_file(NAMED_GRAPH), rdf_format=RdfFormat.JSONLD)
    assert store.sent("put_graph") == [], "TC-40: no graph written"
    assert store.sent("update") == [], "TC-40: the store was not touched"


async def test_a_body_naming_a_graph_is_refused(documents, book_class):
    body = {
        "@context": documents.context,
        "@id": "urn:g",
        "@graph": [{"type": "Book", **BOOK_JSON}],
    }
    with pytest.raises(InvalidBody, match="a body describes one graph"):
        await documents.parse(
            encoded(body), JSON_LD, book_class, book_iri(1), creating=True, tenant=TENANT
        )


RELATIVE = {"@id": "book1", TITLE: "Dune"}


def test_a_relative_iri_without_a_base_is_refused_by_triples_of():
    with pytest.raises(one_path.RelativeIriRefused):
        triples_of(RELATIVE)


async def test_a_loaded_file_with_a_relative_iri_and_no_base_is_refused():
    with pytest.raises(InvalidGraph) as raised:
        await parse_graph(encoded_file(RELATIVE), RdfFormat.JSONLD)
    assert str(raised.value) == ABSOLUTE, "TC-42b: the reason, not lost triples"


async def test_a_loaded_file_with_a_base_of_its_own_resolves_against_it():
    document = {"@context": {"@base": "https://ex.org/"}, **RELATIVE}
    graph = await parse_graph(encoded_file(document), RdfFormat.JSONLD)
    assert (URIRef("https://ex.org/book1"), URIRef(TITLE), None) in graph, (
        "TC-42b: a document's own @base applies"
    )
    assert NO_BASE not in graph.serialize(format="nt"), "the placeholder base never leaks"


@pytest.mark.parametrize("media_type", [JSON, JSON_LD], ids=["json", "json-ld"])
async def test_a_body_with_a_relative_reference_is_refused(documents, book_class, media_type):
    # TC-42c
    body = {**BOOK_JSON, "shelf": "shelves/1"}
    if media_type == JSON_LD:
        body = {"@context": documents.context, "type": "Book", **body}
    with pytest.raises(InvalidBody, match=ABSOLUTE):
        await documents.parse(
            encoded(body), media_type, book_class, book_iri(1), creating=True, tenant=TENANT
        )


NOT_VALID = "a JSON-LD document holds an IRI that is not valid"
OBJECT_OR_ARRAY = "a JSON-LD document is an object or an array"
UNREADABLE = {
    "relative under a null base": {"@context": {"@base": None}, "@id": "a", TITLE: "Dune"},
    "relative type": {"@id": "https://example.org/b", "@type": "rel"},
    "space in a subject": {"@id": "https://ex.org/a b", TITLE: "Dune"},
    "control character": {"@id": "https://ex.org/a\nb", TITLE: "Dune"},
    "space in an object": {"@id": "https://ex.org/a", TITLE: {"@id": "https://ex.org/a b"}},
    "space in a predicate": {"@id": "https://ex.org/a", "https://ex.org/p q": "x"},
}


@pytest.mark.parametrize("document", UNREADABLE.values(), ids=UNREADABLE.keys())
def test_triples_of_refuses_an_iri_that_is_relative_or_not_valid_rather_than_drop_it(document):
    with pytest.raises((one_path.RelativeIriRefused, one_path.InvalidIriRefused)):
        triples_of(document)


@pytest.mark.parametrize("document", [123, True, 1.5, None, "x", ""], ids=repr)
def test_triples_of_refuses_a_document_that_is_not_an_object_or_an_array(document):
    with pytest.raises(one_path.NotADocumentRefused):
        triples_of(document)


@pytest.mark.parametrize(
    "document",
    [UNREADABLE["space in a subject"], UNREADABLE["control character"]],
    ids=["space", "control character"],
)
async def test_a_loaded_file_with_an_iri_that_is_not_valid_is_refused(document):
    with pytest.raises(InvalidGraph) as raised:
        await parse_graph(encoded_file(document), RdfFormat.JSONLD)
    assert str(raised.value) == NOT_VALID, "the reason, not a shorter graph"


async def test_a_loaded_file_with_a_null_base_and_a_relative_iri_is_refused():
    with pytest.raises(InvalidGraph) as raised:
        await parse_graph(encoded_file(UNREADABLE["relative under a null base"]), RdfFormat.JSONLD)
    assert str(raised.value) == ABSOLUTE


@pytest.mark.parametrize("data", [b"123", b"true", b"null"], ids=repr)
async def test_a_loaded_file_that_is_not_an_object_or_an_array_is_refused(data):
    with pytest.raises(InvalidGraph) as raised:
        await parse_graph(data, RdfFormat.JSONLD)
    assert str(raised.value) == OBJECT_OR_ARRAY


async def test_a_body_with_an_iri_that_is_not_valid_is_refused(documents, book_class):
    body = {
        "@context": documents.context,
        "type": "Book",
        **BOOK_JSON,
        "shelf": "https://ex.org/a b",
    }
    with pytest.raises(InvalidBody, match=NOT_VALID):
        await documents.parse(
            encoded(body), JSON_LD, book_class, book_iri(1), creating=True, tenant=TENANT
        )


NON_INLINE = {
    "iri": {"@context": CONTEXT_UNREACHABLE, "@id": "https://example.org/b"},
    "file iri": {"@context": "file:///etc/hostname", "@id": "https://example.org/b"},
    "relative path": {"@context": "context.jsonld", "@id": "https://example.org/b"},
    "@import": {"@context": {"@import": CONTEXT_UNREACHABLE}, "@id": "https://example.org/b"},
}


@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("document", NON_INLINE.values(), ids=NON_INLINE.keys())
def test_a_context_that_is_not_inline_is_refused_by_triples_of_before_any_fetch(document):
    with pytest.raises(one_path.RemoteContextRefused):
        triples_of(document)


@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("document", NON_INLINE.values(), ids=NON_INLINE.keys())
async def test_a_loaded_file_with_a_context_that_is_not_inline_is_refused(document):
    with pytest.raises(InvalidGraph) as raised:
        await parse_graph(encoded_file(document), RdfFormat.JSONLD)
    assert str(raised.value) == NOT_INLINE, "TC-39: the toolkit's refusal, not a fetch failure"

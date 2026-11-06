"""Bodies and representations of an aggregate (PD-14, PD-12): JSON and JSON-LD in, shapes, JSON, JSON-LD and Turtle out."""

import json
from copy import deepcopy

import pytest
from pyld import jsonld
from rdflib import RDF, BNode, Graph, URIRef
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence.domain.exceptions import InvalidBody
from rdf_persistence.domain.iris import graph_iri
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.documents import JSON, JSON_LD, TURTLE, Documents
from tests.toy import TENANT, book_iri, dune, toy_mapper

BOOK = book_iri(1)
GRAPH = graph_iri(BOOK)
BIBO = "http://purl.org/ontology/bibo/"
BOOK_TYPE = URIRef(f"{BIBO}Book")
BOOK_JSON = {
    "label": "Dune",
    "description": "A planet.",
    "genre": "fiction",
    "authors": ["Herbert"],
    "chapters": [{"number": 1, "notes": [{"label": "n", "description": "d", "text": "t"}]}],
}


def encoded(body: object) -> bytes:
    return json.dumps(body).encode()


def with_context(documents: Documents, body: dict) -> dict:
    return {"@context": documents.context, **body}


def assert_same_triples(left: Graph, right: Graph) -> None:
    assert isomorphic(left, right), (
        f"only left: {sorted(graph_diff(left, right)[1])}\nonly right: {sorted(graph_diff(left, right)[2])}"
    )


@pytest.fixture
def stored() -> Graph:
    """The triples of a book as the session reads them, one new set of part IRIs per test."""
    return toy_mapper().to_graph(dune(BOOK))


def graph_of_json(documents: Documents, body: dict) -> Graph:
    nquads = jsonld.to_rdf(with_context(documents, body), {"format": "application/n-quads"})
    return Graph().parse(data=nquads, format="nt")


# --- what is served -------------------------------------------------------------------------


def test_the_aggregate_types_are_the_roots_with_a_path_in_the_tenant_database(documents) -> None:
    assert sorted(documents.aggregates) == ["books", "scans"], (
        "the tenant root and the access record have no generic route"
    )


def test_the_tenant_root_is_the_class_in_the_meta_graph(documents) -> None:
    assert documents.tenant_root.name == "Library", "the toy's tenant root"


# --- reading a body ---------------------------------------------------------------------------


async def test_a_json_body_becomes_the_typed_triples_of_a_node_rooted_at_the_given_iri(
    documents, book_class
) -> None:
    graph = await documents.parse(encoded(BOOK_JSON), JSON, book_class, BOOK, creating=True)
    assert (URIRef(BOOK), RDF.type, BOOK_TYPE) in graph, "the root is typed by the route's class"
    chapters = list(graph.subjects(RDF.type, URIRef(f"{BIBO}Chapter")))
    assert len(chapters) == 1, "an owned part is typed by the range of its slot"


async def test_a_part_without_an_iri_gets_one_under_the_root(documents, book_class) -> None:
    graph = await documents.parse(encoded(BOOK_JSON), JSON, book_class, BOOK, creating=True)
    parts = {s for s in graph.subjects() if s != URIRef(BOOK)}
    assert parts and all(str(p).startswith(f"{BOOK}/parts/") for p in parts), (
        "PD-6: a part without an IRI is minted one"
    )
    assert not any(isinstance(s, BNode) for s in graph.subjects()), "no blank node is left"


async def test_a_json_ld_body_and_the_same_json_body_give_the_same_triples(
    documents, book_class
) -> None:
    given = {
        "id": BOOK,
        **BOOK_JSON,
        "chapters": [{**BOOK_JSON["chapters"][0], "id": f"{BOOK}/parts/c1"}],
    }
    given["chapters"][0]["notes"][0]["id"] = f"{BOOK}/parts/n1"
    as_json = await documents.parse(encoded(given), JSON, book_class, BOOK, creating=False)
    typed = deepcopy(with_context(documents, given))
    typed["type"] = "Book"
    typed["chapters"][0]["type"] = "Chapter"
    typed["chapters"][0]["notes"][0]["type"] = "Note"
    as_ld = await documents.parse(encoded(typed), JSON_LD, book_class, BOOK, creating=False)
    assert_same_triples(as_json, as_ld)


async def test_a_body_may_leave_out_the_id_on_a_replace(documents, book_class) -> None:
    graph = await documents.parse(encoded(BOOK_JSON), JSON, book_class, BOOK, creating=False)
    assert (URIRef(BOOK), RDF.type, BOOK_TYPE) in graph, "the path names the root"


async def test_a_body_may_repeat_the_id_of_the_path_on_a_replace(documents, book_class) -> None:
    graph = await documents.parse(
        encoded({"id": BOOK, **BOOK_JSON}), JSON, book_class, BOOK, creating=False
    )
    assert (URIRef(BOOK), RDF.type, BOOK_TYPE) in graph, "the same id is no change"


async def test_a_replace_with_another_id_is_refused(documents, book_class) -> None:
    with pytest.raises(InvalidBody, match="differs from the path"):
        await documents.parse(
            encoded({"id": book_iri(2), **BOOK_JSON}), JSON, book_class, BOOK, creating=False
        )


async def test_a_create_with_an_id_is_refused(documents, book_class) -> None:
    with pytest.raises(InvalidBody, match="assigns the IRI"):
        await documents.parse(
            encoded({"id": book_iri(2), **BOOK_JSON}), JSON, book_class, BOOK, creating=True
        )


async def test_a_body_typed_as_another_class_is_refused(documents, book_class) -> None:
    body = {"@context": documents.context, "type": "Scan", **BOOK_JSON}
    with pytest.raises(InvalidBody, match="must be a"):
        await documents.parse(encoded(body), JSON_LD, book_class, BOOK, creating=True)


async def test_a_body_that_describes_a_node_outside_the_aggregate_is_refused(
    documents, book_class
) -> None:
    other = {"id": book_iri(9), "label": "Other", "description": "d", "type": "Book"}
    body = {"@context": documents.context, "@graph": [{"type": "Book", **BOOK_JSON}, other]}
    with pytest.raises(InvalidBody):
        await documents.parse(encoded(body), JSON_LD, book_class, BOOK, creating=True)


async def test_a_part_outside_the_aggregate_is_refused(documents, book_class) -> None:
    body = {**BOOK_JSON, "chapters": [{"id": f"{TENANT}/books/elsewhere", "number": 1}]}
    with pytest.raises(InvalidBody, match="inside the aggregate"):
        await documents.parse(encoded(body), JSON, book_class, BOOK, creating=True)


async def test_a_remote_context_is_not_fetched(documents, book_class) -> None:
    body = {"@context": "http://127.0.0.1:9/ctx.jsonld", "type": "Book", "label": "x"}
    with pytest.raises(InvalidBody, match="inline"):
        await documents.parse(encoded(body), JSON_LD, book_class, BOOK, creating=True)


@pytest.mark.parametrize("data", [b"{not json", b"[1, 2]", b'"text"', b""])
async def test_a_body_that_is_not_a_json_object_is_refused(documents, book_class, data) -> None:
    with pytest.raises(InvalidBody):
        await documents.parse(data, JSON, book_class, BOOK, creating=True)


async def test_the_bookkeeping_a_client_sends_is_dropped(documents, book_class) -> None:
    body = {**BOOK_JSON, "created": "2001-01-01T00:00:00Z", "creator": "https://evil.example/u"}
    graph = await documents.parse(encoded(body), JSON, book_class, BOOK, creating=True)
    forged = set(graph.predicates()) & v.BOOKKEEPING_PREDICATES
    assert not forged, f"only the session writes who created a graph and when: {sorted(forged)}"


# --- the shapes ---------------------------------------------------------------------------------


async def test_a_valid_body_passes_the_shapes(documents, book_class) -> None:
    graph = await documents.parse(encoded(BOOK_JSON), JSON, book_class, BOOK, creating=True)
    await documents.validate(graph)


async def test_a_body_without_the_required_description_is_refused_naming_the_slot(
    documents, book_class
) -> None:
    body = {k: v for k, v in BOOK_JSON.items() if k != "description"}
    graph = await documents.parse(encoded(body), JSON, book_class, BOOK, creating=True)
    with pytest.raises(InvalidBody, match="description"):
        await documents.validate(graph)


async def test_an_unknown_field_is_refused(documents, book_class) -> None:
    with pytest.raises(InvalidBody, match="colour"):
        await documents.parse(
            encoded({**BOOK_JSON, "colour": "red"}), JSON, book_class, BOOK, creating=True
        )


async def test_validating_leaves_the_cached_shapes_unchanged(documents, book_class) -> None:
    before = len(documents.shapes)
    graph = await documents.parse(encoded(BOOK_JSON), JSON, book_class, BOOK, creating=True)
    await documents.validate(graph)
    assert len(documents.shapes) == before, "the shapes graph is shared by every request"


# --- the representations ----------------------------------------------------------------------


async def test_the_json_of_an_aggregate_nests_its_parts_and_has_no_context(
    documents, book_class, stored
) -> None:
    body = json.loads(await documents.render(stored, GRAPH, book_class, JSON))
    assert body["id"] == BOOK, "id holds the IRI"
    assert "@context" not in body, "the context comes by the Link header"
    assert sorted(c["number"] for c in body["chapters"]) == [1, 2], (
        "chapters are nested in the book"
    )
    assert body["chapters"][0]["notes"][0]["text"] == "a note", "and notes in their chapter"


async def test_the_json_ld_of_an_aggregate_carries_the_context(
    documents, book_class, stored
) -> None:
    body = json.loads(await documents.render(stored, GRAPH, book_class, JSON_LD))
    assert body["@context"] == documents.context, "a JSON-LD document is self-contained"


async def test_the_three_representations_describe_the_same_triples(
    documents, book_class, stored
) -> None:
    as_json = json.loads(await documents.render(stored, GRAPH, book_class, JSON))
    as_ld = json.loads(await documents.render(stored, GRAPH, book_class, JSON_LD))
    as_turtle = Graph().parse(
        data=await documents.render(stored, GRAPH, book_class, TURTLE), format="turtle"
    )
    assert_same_triples(graph_of_json(documents, as_json), stored)
    assert_same_triples(
        graph_of_json(documents, {k: v for k, v in as_ld.items() if k != "@context"}), stored
    )
    assert_same_triples(as_turtle, stored)


async def test_what_the_service_returns_it_accepts_back(documents, book_class, stored) -> None:
    returned = json.loads(await documents.render(stored, GRAPH, book_class, JSON))
    graph = await documents.parse(encoded(returned), JSON, book_class, BOOK, creating=False)
    assert_same_triples(graph, stored)
    await documents.validate(graph)


async def test_the_bookkeeping_of_the_stored_graph_is_not_shown(
    documents, book_class, stored
) -> None:
    stored.add((GRAPH, URIRef("https://meaningfy.ws/ns/rdf-persistence#version"), URIRef("urn:v")))
    body = await documents.render(stored, GRAPH, book_class, TURTLE)
    assert "graph" not in body, "the version token is the ETag, not content"
    assert "urn:v" not in body, "the version token is the ETag, not content"

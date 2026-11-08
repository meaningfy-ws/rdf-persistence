"""Bodies and representations of an aggregate (PD-14, PD-12): JSON and JSON-LD in, shapes, JSON, JSON-LD and Turtle out."""

import json
import shutil
from copy import deepcopy

import pytest
from pyld import jsonld
from rdflib import RDF, BNode, Graph, Literal, URIRef
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence.domain.exceptions import InvalidBody
from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.domain.iris import Iris, graph_iri
from rdf_persistence.domain.media import JSON, JSON_LD, TURTLE
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import iri_types
from tests.toy import TENANT, TOY_SCHEMA, book_iri, dune, toy_mapper
from tests.unit.services.conftest import GENERATED

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


def _flat_documents() -> Documents:
    """The toy library's parts beside their roots, minted under this tenant (PD-7)."""
    layout = "{base}{tenant_id}/{type}/{id}"
    settings = ServiceSettings(
        base="https://example.org/",
        prefix="acme",
        tenant_segment="libraries",
        creator_role="owner",
        roles_claim="roles",
        iri_policy=IriPolicy(
            tenant_template="{base}libraries/{tenant_id}",
            aggregate_template=layout,
            part_template=layout,
            loaded_graph_template=layout,
            tenant_id=IdSpec(kind=IdKind.RANDOM, length=8),
            object_id=IdSpec(kind=IdKind.RANDOM, length=13),
        ),
    )
    iris = Iris(settings, *iri_types(load_schema(TOY_SCHEMA)))
    return Documents(load_schema(TOY_SCHEMA), GENERATED, iris=iris)


@pytest.fixture(scope="module")
def default_documents() -> Documents:
    return Documents(load_schema(TOY_SCHEMA), GENERATED)


@pytest.fixture(scope="module")
def flat_documents() -> Documents:
    return _flat_documents()


@pytest.fixture(scope="module", params=["default_documents", "flat_documents"])
def documents(request) -> Documents:
    """Every test of a body runs under both IRI policies: parts nested under the root, and beside it."""
    return request.getfixturevalue(request.param)


async def parse(documents: Documents, *args, **kwargs):
    """``Documents.parse`` in the toy tenant, which the flat policy needs to mint a part's IRI."""
    return await documents.parse(*args, tenant=TENANT, **kwargs)


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
    graph, _ = await parse(documents, encoded(BOOK_JSON), JSON, book_class, BOOK, creating=True)
    assert (URIRef(BOOK), RDF.type, BOOK_TYPE) in graph, "the root is typed by the route's class"
    chapters = list(graph.subjects(RDF.type, URIRef(f"{BIBO}Chapter")))
    assert len(chapters) == 1, "an owned part is typed by the range of its slot"


async def minted_parts(documents: Documents, book_class) -> set[URIRef]:
    graph, _ = await parse(documents, encoded(BOOK_JSON), JSON, book_class, BOOK, creating=True)
    assert not any(isinstance(s, BNode) for s in graph.subjects()), "no blank node is left"
    return {s for s in graph.subjects() if s != URIRef(BOOK)}


async def test_a_part_without_an_iri_gets_one_under_its_root_by_the_default_policy(
    default_documents, book_class
) -> None:
    parts = await minted_parts(default_documents, book_class)
    assert parts and all(str(p).startswith(f"{BOOK}/parts/") for p in parts)


async def test_a_part_without_an_iri_gets_one_beside_its_root_by_a_flat_policy(
    flat_documents, book_class
) -> None:
    parts = await minted_parts(flat_documents, book_class)
    assert parts and all(str(p).startswith("https://example.org/") for p in parts)
    assert not any(str(p).startswith(f"{BOOK}/") for p in parts)


async def test_a_json_ld_body_and_the_same_json_body_give_the_same_triples(
    documents, book_class
) -> None:
    given = {
        "id": BOOK,
        **BOOK_JSON,
        "chapters": [deepcopy(BOOK_JSON["chapters"][0]) | {"id": f"{BOOK}/parts/c1"}],
    }
    given["chapters"][0]["notes"][0]["id"] = f"{BOOK}/parts/n1"
    as_json, _ = await parse(documents, encoded(given), JSON, book_class, BOOK, creating=False)
    typed = deepcopy(with_context(documents, given))
    typed["type"] = "Book"
    typed["chapters"][0]["type"] = "Chapter"
    typed["chapters"][0]["notes"][0]["type"] = "Note"
    as_ld, _ = await parse(documents, encoded(typed), JSON_LD, book_class, BOOK, creating=False)
    assert_same_triples(as_json, as_ld)


async def test_a_body_may_leave_out_the_id_on_a_replace(documents, book_class) -> None:
    graph, _ = await parse(documents, encoded(BOOK_JSON), JSON, book_class, BOOK, creating=False)
    assert (URIRef(BOOK), RDF.type, BOOK_TYPE) in graph, "the path names the root"


async def test_a_body_may_repeat_the_id_of_the_path_on_a_replace(documents, book_class) -> None:
    graph, _ = await parse(
        documents, encoded({"id": BOOK, **BOOK_JSON}), JSON, book_class, BOOK, creating=False
    )
    assert (URIRef(BOOK), RDF.type, BOOK_TYPE) in graph, "the same id is no change"


async def test_a_replace_with_another_id_is_refused(documents, book_class) -> None:
    with pytest.raises(InvalidBody, match="differs from the path"):
        await parse(
            documents,
            encoded({"id": book_iri(2), **BOOK_JSON}),
            JSON,
            book_class,
            BOOK,
            creating=False,
        )


async def test_a_create_with_an_id_is_refused(documents, book_class) -> None:
    with pytest.raises(InvalidBody, match="assigns the IRI"):
        await parse(
            documents,
            encoded({"id": book_iri(2), **BOOK_JSON}),
            JSON,
            book_class,
            BOOK,
            creating=True,
        )


async def test_a_body_typed_as_another_class_is_refused(documents, book_class) -> None:
    body = {"@context": documents.context, "type": "Scan", **BOOK_JSON}
    with pytest.raises(InvalidBody, match="must be a"):
        await parse(documents, encoded(body), JSON_LD, book_class, BOOK, creating=True)


async def test_a_body_that_describes_a_node_outside_the_aggregate_is_refused(
    documents, book_class
) -> None:
    other = {"id": book_iri(9), "label": "Other", "description": "d", "type": "Book"}
    body = {"@context": documents.context, "@graph": [{"type": "Book", **BOOK_JSON}, other]}
    with pytest.raises(InvalidBody):
        await parse(documents, encoded(body), JSON_LD, book_class, BOOK, creating=True)


OUTSIDE = f"{TENANT}/books/elsewhere"
OUTSIDE_BODY = {**BOOK_JSON, "chapters": [{"id": OUTSIDE, "number": 1}]}


async def test_a_part_outside_the_aggregate_is_refused_when_parts_are_nested(
    default_documents, book_class
) -> None:
    with pytest.raises(InvalidBody, match="inside the aggregate"):
        await parse(default_documents, encoded(OUTSIDE_BODY), JSON, book_class, BOOK, creating=True)


async def test_a_part_outside_the_aggregate_is_reported_as_named_when_parts_are_flat(
    flat_documents, book_class
) -> None:
    """No IRI says where a flat part belongs, so the caller checks it against what the aggregate stores (PD-7)."""
    _, named = await parse(
        flat_documents, encoded(OUTSIDE_BODY), JSON, book_class, BOOK, creating=True
    )
    assert named == {URIRef(OUTSIDE)}


async def test_a_part_cannot_take_the_iri_of_its_aggregates_graph(documents, book_class) -> None:
    """The graph IRI carries the version and the creator, so a part there would be bookkeeping (PD-12d)."""
    body = {**BOOK_JSON, "chapters": [{"id": str(GRAPH), "number": 1}]}
    with pytest.raises(InvalidBody, match="graph"):
        await parse(documents, encoded(body), JSON, book_class, BOOK, creating=False)


async def test_a_remote_context_is_not_fetched(documents, book_class) -> None:
    body = {"@context": "http://127.0.0.1:9/ctx.jsonld", "type": "Book", "label": "x"}
    with pytest.raises(InvalidBody, match="inline"):
        await parse(documents, encoded(body), JSON_LD, book_class, BOOK, creating=True)


@pytest.mark.parametrize("data", [b"{not json", b"[1, 2]", b'"text"', b""])
async def test_a_body_that_is_not_a_json_object_is_refused(documents, book_class, data) -> None:
    with pytest.raises(InvalidBody):
        await parse(documents, data, JSON, book_class, BOOK, creating=True)


async def test_the_bookkeeping_a_client_sends_is_dropped(documents, book_class) -> None:
    body = {**BOOK_JSON, "created": "2001-01-01T00:00:00Z", "creator": "https://evil.example/u"}
    graph, _ = await parse(documents, encoded(body), JSON, book_class, BOOK, creating=True)
    forged = set(graph.predicates()) & v.BOOKKEEPING_PREDICATES
    assert not forged, f"only the session writes who created a graph and when: {sorted(forged)}"


# --- the shapes ---------------------------------------------------------------------------------


async def test_a_valid_body_passes_the_shapes(documents, book_class) -> None:
    graph, _ = await parse(documents, encoded(BOOK_JSON), JSON, book_class, BOOK, creating=True)
    await documents.validate(graph)


async def test_a_body_without_the_required_description_is_refused_naming_the_slot(
    documents, book_class
) -> None:
    body = {k: v for k, v in BOOK_JSON.items() if k != "description"}
    graph, _ = await parse(documents, encoded(body), JSON, book_class, BOOK, creating=True)
    with pytest.raises(InvalidBody, match="description"):
        await documents.validate(graph)


async def test_an_unknown_field_is_refused(documents, book_class) -> None:
    with pytest.raises(InvalidBody, match="colour"):
        await parse(
            documents,
            encoded({**BOOK_JSON, "colour": "red"}),
            JSON,
            book_class,
            BOOK,
            creating=True,
        )


async def test_validating_leaves_the_cached_shapes_unchanged(documents, book_class) -> None:
    before = len(documents.shapes)
    graph, _ = await parse(documents, encoded(BOOK_JSON), JSON, book_class, BOOK, creating=True)
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
    graph, _ = await parse(documents, encoded(returned), JSON, book_class, BOOK, creating=False)
    assert_same_triples(graph, stored)
    await documents.validate(graph)


async def test_the_bookkeeping_of_the_stored_graph_is_not_shown(
    documents, book_class, stored
) -> None:
    stored.add((GRAPH, URIRef("https://meaningfy.ws/ns/rdf-persistence#version"), URIRef("urn:v")))
    body = await documents.render(stored, GRAPH, book_class, TURTLE)
    assert "graph" not in body, "the version token is the ETag, not content"
    assert "urn:v" not in body, "the version token is the ETag, not content"


# --- the one implementation of a body and of a frame ---------------------------------------------


def test_expanding_a_json_body_gives_the_triples_of_the_typed_node(documents, book_class) -> None:
    graph = documents.expand({"id": BOOK, **BOOK_JSON}, book_class)
    assert (URIRef(BOOK), RDF.type, BOOK_TYPE) in graph, "the class gives the type"
    assert len(set(graph.subjects(RDF.type, None))) == 3, "the book, its chapter and the note"


def test_expanding_refuses_a_key_the_class_has_no_slot_for(documents, book_class) -> None:
    with pytest.raises(InvalidBody, match="colour"):
        documents.expand({**BOOK_JSON, "colour": "red"}, book_class)


def test_framing_gives_back_the_body_that_was_expanded(documents, book_class) -> None:
    graph = documents.expand({"id": BOOK, **BOOK_JSON}, book_class)
    framed = documents.frame(graph, book_class)
    assert framed["label"] == "Dune" and framed["chapters"][0]["notes"][0]["text"] == "t"


def test_the_internal_values_of_the_nodes_a_replacement_keeps_are_kept(documents) -> None:
    key = URIRef("https://meaningfy.ws/ns/rdf-persistence#fileKey")
    gone = URIRef(f"{BOOK}/parts/gone")
    stored = Graph()
    stored.add((URIRef(BOOK), key, Literal("K")))
    stored.add((gone, key, Literal("other")))
    stored.add((URIRef(BOOK), URIRef("urn:public"), Literal("not internal")))
    replacement = [(URIRef(BOOK), RDF.type, BOOK_TYPE)]
    assert documents.internal_values(stored, replacement) == [(URIRef(BOOK), key, Literal("K"))], (
        "only internal statements, only of nodes the replacement describes"
    )


def test_the_internal_values_of_a_part_the_replacement_keeps_are_kept(documents) -> None:
    key = URIRef("https://meaningfy.ws/ns/rdf-persistence#fileKey")
    part = URIRef(f"{BOOK}/parts/kept")
    stored = Graph()
    stored.add((part, key, Literal("K")))
    replacement = [(part, RDF.type, BOOK_TYPE)]
    assert documents.internal_values(stored, replacement) == [(part, key, Literal("K"))], (
        "the internal statement of a part that persists is kept"
    )


def test_a_folder_without_the_frame_of_a_served_type_stops_start_up(tmp_path) -> None:
    folder = tmp_path / "generated"
    shutil.copytree(GENERATED, folder)
    (folder / "Scan.frame.jsonld").unlink()
    broken = Documents(load_schema(TOY_SCHEMA), folder)
    with pytest.raises(FileNotFoundError, match="Scan.frame"):
        broken.require_frames()

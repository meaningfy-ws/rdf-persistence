"""Bodies are strict (PD-14b): no internal slot, no key the class does not have, no stray node, bounded in size."""

import asyncio

import pytest
from rdflib import RDF, Graph, Literal, URIRef

from rdf_persistence.domain.exceptions import InvalidBody, PayloadTooLarge
from rdf_persistence.domain.media import JSON, JSON_LD, TURTLE
from rdf_persistence.services.documents import MAX_NODES
from tests.toy import TENANT, book_iri
from tests.unit.services.test_documents import BOOK, BOOK_JSON, encoded

RP = "https://meaningfy.ws/ns/rdf-persistence#"
FILE_KEY = URIRef(f"{RP}fileKey")
SCAN = book_iri(5).replace("/books/", "/scans/")
SCAN_JSON = {
    "label": "Dune, scanned",
    "description": "A scanned copy.",
    "file_name": "dune.pdf",
    "media_type": "application/pdf",
    "byte_size": 12,
    "sha256": "0" * 64,
}
SECRET = "SECRET-FILE-KEY"


def scan_ld(documents, context: dict | None = None, **extra) -> dict:
    return {
        "@context": [documents.context, {"rp": RP, **(context or {})}],
        "type": "Scan",
        **SCAN_JSON,
        **extra,
    }


async def parsed(documents, cls, body: dict, media_type: str = JSON, iri: str = SCAN):
    return await documents.parse(encoded(body), media_type, cls, iri, creating=True)


# --- internal slots: refused in every key form, at every level ---------------------------------


@pytest.mark.parametrize(
    "key",
    ["file_key", "rp:fileKey", f"{RP}fileKey", "fileKey"],
    ids=["name", "curie", "iri", "camel"],
)
async def test_a_plain_json_body_cannot_set_an_internal_slot_in_any_key_form(
    documents, scan_class, key
) -> None:
    with pytest.raises(InvalidBody):
        await parsed(documents, scan_class, {**SCAN_JSON, key: SECRET})


async def test_the_refusal_of_an_internal_slot_names_the_slot(documents, scan_class) -> None:
    with pytest.raises(InvalidBody, match="file_key"):
        await parsed(documents, scan_class, {**SCAN_JSON, "file_key": SECRET})


@pytest.mark.parametrize(
    "extra",
    [
        {"rp:fileKey": SECRET},
        {f"{RP}fileKey": SECRET},
        {"k": SECRET},
        {"@reverse": {f"{RP}fileKey": {"@id": "urn:x:other"}}},
    ],
    ids=["curie", "iri", "own term", "reverse"],
)
async def test_a_json_ld_body_cannot_set_an_internal_slot_in_any_key_form(
    documents, scan_class, extra
) -> None:
    body = scan_ld(documents, {"k": f"{RP}fileKey"}, **extra)
    with pytest.raises(InvalidBody, match="file_key"):
        await parsed(documents, scan_class, body, JSON_LD)


async def test_a_nested_context_that_renames_a_term_to_an_internal_slot_is_refused(
    documents, scan_class
) -> None:
    body = {**scan_ld(documents), "scan_of": book_iri(1)}
    body["label"] = {"@context": {"label": f"{RP}fileKey"}, "@value": SECRET}
    body["@context"].append({"label": {"@id": f"{RP}fileKey"}})
    with pytest.raises(InvalidBody, match="file_key"):
        await parsed(documents, scan_class, body, JSON_LD)


async def test_an_internal_slot_is_refused_in_an_owned_part(documents, book_class) -> None:
    chapter = {"number": 1, "rp:fileKey": SECRET}
    with pytest.raises(InvalidBody):
        await parsed(documents, book_class, {**BOOK_JSON, "chapters": [chapter]}, iri=BOOK)


async def test_an_internal_slot_is_refused_in_an_owned_part_of_a_json_ld_body(
    documents, book_class
) -> None:
    chapter = {"type": "Chapter", "number": 1, "rp:fileKey": SECRET}
    body = {
        "@context": [documents.context, {"rp": RP}],
        "type": "Book",
        **BOOK_JSON,
        "chapters": [chapter],
    }
    with pytest.raises(InvalidBody, match="file_key"):
        await parsed(documents, book_class, body, JSON_LD, iri=BOOK)


@pytest.mark.parametrize("char", list('<>"{}|^\\`'))
async def test_a_reference_that_is_not_a_valid_iri_is_an_invalid_body(
    documents, scan_class, char
) -> None:
    with pytest.raises(InvalidBody):  # the N-Quads parser refuses some of them first
        await parsed(documents, scan_class, {**SCAN_JSON, "scan_of": f"urn:x:a{char}b"})


# --- plain JSON keys are the class's slot names ----------------------------------------------


@pytest.mark.parametrize(
    "key", ["colour", "@reverse", "@included", "@graph", "@vocab", "@context", "http://x.example/p"]
)
async def test_a_plain_json_key_that_is_not_a_slot_of_the_class_is_refused_in_a_part(
    documents, book_class, key
) -> None:
    chapter = {"number": 1, key: {"@id": "http://x.example/o"}}
    with pytest.raises(InvalidBody, match="chapters|Chapter"):
        await parsed(documents, book_class, {**BOOK_JSON, "chapters": [chapter]}, iri=BOOK)


@pytest.mark.parametrize("key", ["colour", "@reverse", "@included", "@graph", "@vocab"])
async def test_a_plain_json_key_that_is_not_a_slot_of_the_class_is_refused_at_the_root(
    documents, book_class, key
) -> None:
    with pytest.raises(InvalidBody, match="Book"):
        await parsed(documents, book_class, {**BOOK_JSON, key: "x"}, iri=BOOK)


async def test_a_plain_json_reference_is_a_bare_iri_or_an_object_with_only_an_id(
    documents, scan_class
) -> None:
    ok = {**SCAN_JSON, "scan_of": {"@id": book_iri(1)}}
    graph = await parsed(documents, scan_class, ok)
    assert (URIRef(SCAN), None, URIRef(book_iri(1))) in graph, "the reference is kept"
    with pytest.raises(InvalidBody):
        await parsed(documents, scan_class, {**SCAN_JSON, "scan_of": {"@id": book_iri(1), "x": 1}})


# --- only the root and its owned parts, typed -------------------------------------------------


async def test_a_node_smuggled_through_a_reference_slot_is_refused(documents, scan_class) -> None:
    smuggled = {"@id": f"{SCAN}/smuggled", "junk": "anything"}
    with pytest.raises(InvalidBody):
        await parsed(documents, scan_class, {**SCAN_JSON, "scan_of": smuggled})


async def test_a_json_ld_node_smuggled_through_a_reference_slot_is_refused(
    documents, scan_class
) -> None:
    smuggled = {"@id": f"{SCAN}/smuggled", "@type": "Note", "label": "x", "description": "d"}
    with pytest.raises(InvalidBody, match="smuggled"):
        await parsed(documents, scan_class, scan_ld(documents, scan_of=smuggled), JSON_LD)


async def test_the_tenant_root_cannot_plant_an_aggregate_of_the_tenant(documents) -> None:
    planted = {
        "@id": book_iri(7),
        "@type": "Book",
        "label": "Planted",
        "description": "d",
    }
    body = {
        "@context": [documents.context, {"schema": "http://schema.org/"}],
        "type": "Library",
        "label": "Ghent",
        "description": "d",
        "schema:hasPart": planted,
    }
    with pytest.raises(InvalidBody, match="not part of"):
        await documents.parse(encoded(body), JSON_LD, documents.tenant_root, TENANT, creating=False)


async def test_the_tenant_root_cannot_plant_the_access_record(documents) -> None:
    planted = {"@id": f"{TENANT}/access", "@type": "LibraryAccess"}
    body = {
        "@context": [documents.context, {"schema": "http://schema.org/"}],
        "type": "Library",
        "label": "Ghent",
        "description": "d",
        "schema:hasPart": planted,
    }
    with pytest.raises(InvalidBody, match="not part of"):
        await documents.parse(encoded(body), JSON_LD, documents.tenant_root, TENANT, creating=False)


async def test_an_untyped_part_is_refused(documents, book_class) -> None:
    body = {
        "@context": documents.context,
        "type": "Book",
        **BOOK_JSON,
        "chapters": [{"id": f"{BOOK}/parts/c1", "number": 1}],
    }
    with pytest.raises(InvalidBody, match="not part of"):
        await parsed(documents, book_class, body, JSON_LD, iri=BOOK)


async def test_a_part_of_another_class_than_the_slot_ranges_over_is_refused(
    documents, book_class
) -> None:
    body = {
        "@context": documents.context,
        "type": "Book",
        **BOOK_JSON,
        "chapters": [{"id": f"{BOOK}/parts/c1", "type": "Scan", "number": 1}],
    }
    with pytest.raises(InvalidBody, match="not part of"):
        await parsed(documents, book_class, body, JSON_LD, iri=BOOK)


async def test_a_detached_cycle_of_nodes_is_refused(documents, book_class) -> None:
    cycle = [
        {"@id": f"{BOOK}/parts/a", "@type": "Chapter", "chapters": {"@id": f"{BOOK}/parts/b"}},
        {"@id": f"{BOOK}/parts/b", "@type": "Chapter", "chapters": {"@id": f"{BOOK}/parts/a"}},
    ]
    body = {"@context": documents.context, "@graph": [{"type": "Book", **BOOK_JSON}, *cycle]}
    with pytest.raises(InvalidBody):
        await parsed(documents, book_class, body, JSON_LD, iri=BOOK)


# --- an internal value that is stored is never shown ------------------------------------------


@pytest.mark.parametrize("media_type", [JSON, JSON_LD, TURTLE])
async def test_a_stored_internal_value_is_not_in_any_representation(
    documents, scan_class, media_type
) -> None:
    root = URIRef(SCAN)
    stored_graph = Graph()
    for predicate, value in {
        URIRef("http://schema.org/name"): Literal("x"),
        FILE_KEY: Literal(SECRET),
    }.items():
        stored_graph.add((root, predicate, value))
    stored_graph.add((root, RDF.type, URIRef("https://example.org/ns/library#Scan")))
    body = await documents.render(stored_graph, URIRef(f"{SCAN}/graph"), scan_class, media_type)
    assert SECRET not in body, f"{media_type} must not carry the file key"
    assert "fileKey" not in body, f"{media_type} must not carry the internal predicate"


# --- bounded ---------------------------------------------------------------------------------


async def test_a_body_of_too_many_nodes_is_refused_before_it_is_expanded(
    documents, book_class
) -> None:
    chapters = [{"number": n} for n in range(MAX_NODES + 1)]
    async with asyncio.timeout(5):  # a body that is expanded first takes minutes
        with pytest.raises(PayloadTooLarge):
            await parsed(documents, book_class, {**BOOK_JSON, "chapters": chapters}, iri=BOOK)


async def test_a_body_of_too_many_list_items_is_refused(documents, book_class) -> None:
    authors = ["Herbert"] * (MAX_NODES + 1)
    async with asyncio.timeout(5):
        with pytest.raises(PayloadTooLarge):
            await parsed(documents, book_class, {**BOOK_JSON, "authors": authors}, iri=BOOK)


async def test_a_json_ld_body_of_too_many_nodes_is_refused(documents, book_class) -> None:
    nodes = [{"@id": f"{BOOK}/parts/{n}"} for n in range(MAX_NODES + 1)]
    async with asyncio.timeout(5):
        with pytest.raises(PayloadTooLarge):
            await parsed(documents, book_class, {"@graph": nodes}, JSON_LD, iri=BOOK)


async def test_a_body_nested_beyond_what_the_parser_reads_is_refused_not_a_server_error(
    documents, book_class
) -> None:
    data = b"[" * 100_000 + b"]" * 100_000
    with pytest.raises(InvalidBody):
        await documents.parse(data, JSON, book_class, BOOK, creating=True)


# --- a refusal that has its own message keeps it ----------------------------------------------


async def test_a_remote_context_is_refused_with_its_own_message(documents, book_class) -> None:
    body = {"@context": "http://127.0.0.1:9/ctx.jsonld", "type": "Book", "label": "x"}
    with pytest.raises(InvalidBody, match="must be inline"):
        await parsed(documents, book_class, body, JSON_LD, iri=BOOK)

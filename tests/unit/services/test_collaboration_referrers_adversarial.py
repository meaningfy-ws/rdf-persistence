"""Adversarial tests of ``Collaboration.referrers`` and ``ServiceKit.collaboration`` (reverse-references 1.x).

Edge cases, leaks, hostile input, odd stored data, limits. Each test names the spec line or the
design.md item it holds the code to (PD-n, Error matrix, RISK-n). B1 to B4 are stored books of the toy
tenant, S1 and S2 its shelves; ``ada`` is a librarian, ``bob`` a reader who may not read the book a test
hides from him.
"""

import re
from collections.abc import AsyncIterator

import pytest
from rdflib import RDF, Literal, URIRef

from rdf_persistence import Action, CallerAccess, TenantState
from rdf_persistence.domain.exceptions import BadQuery, Forbidden, InvalidIri, NotFound
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.generated.service.rp_service import Authorised, ReferrerList
from rdf_persistence.testkit import fake_session
from tests.fixtures.library.generated.books import Book
from tests.toy import (
    ADA,
    BOB,
    TENANT,
    ban,
    book_iri,
    caller,
    direct,
    dune,
    graph_of,
    held,
    library,
    role,
    shelf_iri,
    toy_mapper,
)
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, principal_of

B1, B2, B3, B4 = (book_iri(n) for n in (1, 2, 3, 4))
S1, S2 = shelf_iri(1), shelf_iri(2)
LIB = "https://example.org/ns/library#"
SHELF_P, SEQUEL_P, ABOUT_P = (URIRef(f"{LIB}{n}") for n in ("shelf", "sequelOf", "about"))
BOOK_CLASS = URIRef("http://purl.org/ontology/bibo/Book")
OTHER_TENANT = "https://example.org/libraries/00000000"
HIDDEN_CLASS_SLOT = re.compile(r"Book|shelf|sequel_of|about")


def refs(found: ReferrerList) -> list[tuple[str, str, str]]:
    return [(r.referrer, r.referrer_class, r.referrer_slot) for r in found.referrers or []]


async def put(session, model) -> None:
    await session.add_graph(model.id, toy_mapper().to_triples(model))


async def put_book(session, iri: str, **slots: str) -> Book:
    book = dune(iri, chapters=1, **slots)
    await put(session, book)
    return book


async def put_raw(session, iri: str, rdf_class: str | None, *links: tuple[URIRef, str]) -> None:
    """An aggregate graph with the given type (none if ``None``) and links, written as triples."""
    typed = [] if rdf_class is None else [(URIRef(iri), RDF.type, URIRef(rdf_class))]
    await session.add_graph(iri, [*typed, *((URIRef(iri), p, URIRef(o)) for p, o in links)])


def as_ada(collaboration, session=None):
    return collaboration(caller(principal=ADA), held(role("librarian")), session)


def as_bob(collaboration, access: CallerAccess):
    return collaboration(caller(principal=BOB), access)


def bob_reading_all_but(hidden: str) -> CallerAccess:
    return held(role("reader", who=BOB), bans=[ban(Action.READ, graph_of(hidden), BOB)])


# --- 1. claims nobody tested -----------------------------------------------------------------


async def test_the_tenant_root_is_never_listed_as_a_referrer(toy_session, collaboration):
    root = library()
    await toy_session.add_graph(
        TENANT, [*toy_mapper().to_triples(root), (URIRef(TENANT), SHELF_P, URIRef(S1))]
    )
    stored, _, _ = await toy_session.get_graph(TENANT)
    assert (URIRef(TENANT), SHELF_P, URIRef(S1)) in stored, "the root really holds the IRI"
    found = await as_ada(collaboration).referrers(S1)
    assert (refs(found), found.hidden_count) == ([], 0), "the root is no aggregate of the registry"


async def test_narrowing_by_slot_does_not_narrow_the_hidden_count(toy_session, collaboration):
    await put_book(toy_session, B1, shelf=S1)
    await put_raw(toy_session, B2, str(BOOK_CLASS), (SEQUEL_P, S1))
    found = await as_bob(collaboration, bob_reading_all_but(B2)).referrers(S1, slot="shelf")
    assert refs(found) == [(B1, "Book", "shelf")], "only the readable referrer of that slot"
    assert found.hidden_count == 1, "b2 refers by another slot and is still counted"
    whole = await as_bob(collaboration, bob_reading_all_but(B2)).referrers(S1)
    assert whole.hidden_count == found.hidden_count, "the same count whatever is asked"


async def test_narrowing_by_class_does_not_narrow_the_hidden_count(toy_session, collaboration):
    await put_book(toy_session, B1, shelf=S1)
    await put_raw(toy_session, S2, f"{LIB}Shelf", (SEQUEL_P, S1))
    found = await as_bob(collaboration, bob_reading_all_but(S2)).referrers(S1, class_name="Book")
    assert refs(found) == [(B1, "Book", "shelf")], "the shelf is not a book"
    assert found.hidden_count == 1, "the hidden shelf is still counted"


async def test_a_book_that_refers_to_itself_is_listed(toy_session, collaboration):
    await put_book(toy_session, B1, sequel_of=B1)
    found = await as_ada(collaboration).referrers(B1)
    assert refs(found) == [(B1, "Book", "sequel_of")], "a self-reference is a reference"


async def test_a_self_referring_book_the_caller_may_not_read_is_hidden_not_named(
    toy_session, collaboration
):
    await put_book(toy_session, B1, sequel_of=B1)
    with pytest.raises(Forbidden):  # the caller may not read b1, the target, either
        await as_bob(collaboration, bob_reading_all_but(B1)).referrers(B1)


# --- 2. leaks --------------------------------------------------------------------------------


def assert_no_trace(found: ReferrerList, hidden: str) -> None:
    text = found.model_dump_json()
    assert hidden not in text, "the hidden IRI is not in the result"
    assert hidden.rsplit("/", 1)[1] not in text, "nor its uuid"
    assert not HIDDEN_CLASS_SLOT.search(text), (
        "no class or slot name in a result that lists nothing"
    )


async def test_a_hidden_referrer_leaves_no_trace_in_a_result_that_lists_nothing(
    toy_session, collaboration
):
    await put_book(toy_session, B2, shelf=S1, sequel_of=S1)
    found = await as_bob(collaboration, bob_reading_all_but(B2)).referrers(S1)
    assert (found.referrers, found.hidden_count) == (None, 1), "counted once, listed never"
    assert_no_trace(found, B2)


async def test_a_hidden_referrer_leaves_no_trace_beside_a_listed_one(toy_session, collaboration):
    await put_book(toy_session, B1, shelf=S1)
    await put_raw(toy_session, B2, f"{LIB}Secret", (URIRef(f"{LIB}hiddenSlot"), S1))
    found = await as_bob(collaboration, bob_reading_all_but(B2)).referrers(S1)
    assert refs(found) == [(B1, "Book", "shelf")], "only what he may read"
    text = found.model_dump_json()
    assert B2 not in text and "Secret" not in text and "hiddenSlot" not in text, (
        "neither IRI, class nor slot of the hidden one"
    )


async def test_a_caller_with_no_access_to_the_tenant_learns_nothing_from_the_error(
    toy_session, collaboration
):
    await put_book(toy_session, B2, shelf=S1)
    stranger = collaboration(caller(principal=BOB), held())
    with pytest.raises(NotFound) as raised:
        await stranger.referrers(S1)
    assert B2 not in str(raised.value) and "Book" not in str(raised.value), (
        "no referrer in the text"
    )


async def test_a_caller_with_no_access_gets_the_same_refusal_whether_or_not_anything_refers(
    toy_session, collaboration
):
    await put_book(toy_session, B2, shelf=S1)
    stranger = collaboration(caller(principal=BOB), held())
    with pytest.raises(NotFound) as used:
        await stranger.referrers(S1)
    with pytest.raises(NotFound) as unused:
        await stranger.referrers(S2)
    assert str(used.value).replace(S1, "x") == str(unused.value).replace(S2, "x"), (
        "the refusal does not tell a used shelf from an unused one"
    )


async def test_a_tenant_level_prohibition_refuses_before_anything_is_read(
    toy_session, collaboration
):
    await put_book(toy_session, B2, shelf=S1)
    access = held(role("reader", who=BOB), bans=[ban(Action.READ, TENANT, BOB)])
    with pytest.raises(Forbidden) as raised:
        await as_bob(collaboration, access).referrers(S1)
    assert B2 not in str(raised.value), "the refusal names no referrer"


async def test_a_referrer_the_caller_reads_only_through_a_direct_grant_is_listed(
    toy_session, collaboration
):
    await put_book(toy_session, B1, shelf=S1)
    await put_book(toy_session, B2, shelf=S1)
    access = held(direct(Action.READ, graph_of(S1), BOB), direct(Action.READ, graph_of(B1), BOB))
    found = await as_bob(collaboration, access).referrers(S1)
    assert refs(found) == [(B1, "Book", "shelf")], "the direct grant on b1 is enough"
    assert found.hidden_count == 1, "b2 has no grant"
    assert B2 not in found.model_dump_json(), "b2 is not named"


async def test_a_direct_grant_on_a_referrer_does_not_make_the_resource_readable(
    toy_session, collaboration
):
    await put_book(toy_session, B1, shelf=S1)
    with pytest.raises(NotFound):
        await as_bob(collaboration, held(direct(Action.READ, graph_of(B1), BOB))).referrers(S1)


# --- 3. hostile input ------------------------------------------------------------------------

INJECTION = f"{S1}> }} ; DROP ALL ; INSERT DATA {{ <urn:x> <urn:y> <"
HOSTILE_IRIS = {
    "sparql fragment": INJECTION,
    "closing angle": f"{S1}>",
    "quote": f'{S1}"',
    "apostrophe": f"{S1}'",
    "newline": f"{S1}\n",
    "newline inside": f"{TENANT}/shelves/\n{S1.rsplit('/', 1)[1]}",
    "space": f"{S1} ",
    "empty": "",
    "graph iri of the shelf": graph_of(S1),
    "another tenant": shelf_iri(1).replace(TENANT, OTHER_TENANT),
    "skolem part of a book": f"{B1}/parts/6f1c0c1e-0000-4000-8000-000000000009",
    "loaded graph": f"{B1}/content/6f1c0c1e-0000-4000-8000-000000000009",
    "a very long uuid": f"{TENANT}/shelves/{'a' * 100_000}",
    "a very long string": "x" * 1_000_000,
    "a literal looking like an iri": '"https://example.org"',
    "a prefixed name": "lib:shelf",
    "a blank node": "_:b0",
    "a path trick": f"{TENANT}/shelves/../books/{S1.rsplit('/', 1)[1]}",
}


@pytest.mark.parametrize("iri", HOSTILE_IRIS.values(), ids=HOSTILE_IRIS.keys())
async def test_an_iri_the_policy_does_not_mint_is_refused_as_invalid(
    toy_session, collaboration, iri
):
    await put_book(toy_session, B1, shelf=S1)
    with pytest.raises(InvalidIri):
        await as_ada(collaboration).referrers(iri)
    assert await toy_session.get_graph(B1), "the store is untouched"
    assert refs(await as_ada(collaboration).referrers(S1)) == [(B1, "Book", "shelf")], (
        "and still answers"
    )


async def test_a_uriref_is_accepted_as_the_iri(toy_session, collaboration):
    await put_book(toy_session, B1, shelf=S1)
    found = await as_ada(collaboration).referrers(URIRef(S1))  # type: ignore[arg-type]
    assert refs(found) == [(B1, "Book", "shelf")], "a URIRef is the str it holds"


async def test_the_tenant_root_iri_has_no_referrers_when_nothing_refers_to_it(
    toy_session, collaboration
):
    await put_book(toy_session, B1, shelf=S1)
    found = await as_ada(collaboration).referrers(TENANT)
    assert (refs(found), found.hidden_count) == ([], 0), (
        "the tenant is a minted IRI nothing refers to"
    )


async def test_an_aggregate_may_refer_to_the_tenant_root(toy_session, collaboration):
    await put_raw(toy_session, B1, str(BOOK_CLASS), (SHELF_P, TENANT))
    found = await as_ada(collaboration).referrers(TENANT)
    assert refs(found) == [(B1, "Book", "shelf")], "the tenant root is a legitimate target"


BAD_NAMES = {
    "sparql fragment": "Book } UNION { ?s ?p ?o",
    "quote": 'Book"',
    "closing angle": "Book>",
    "newline": "Book\n",
    "empty": "",
    "space": " ",
    "a prefixed name": "lib:Book",
    "the full class iri": str(BOOK_CLASS),
    "a very long name": "B" * 100_000,
    "case": "book",
}


@pytest.mark.parametrize("name", BAD_NAMES.values(), ids=BAD_NAMES.keys())
async def test_a_class_name_the_schema_does_not_have_is_a_bad_query(
    toy_session, collaboration, name
):
    await put_book(toy_session, B1, shelf=S1)
    with pytest.raises(BadQuery):
        await as_ada(collaboration).referrers(S1, class_name=name)
    assert refs(await as_ada(collaboration).referrers(S1)) == [(B1, "Book", "shelf")], "untouched"


BAD_SLOTS = {
    **{k: v for k, v in BAD_NAMES.items() if k not in ("case", "the full class iri")},
    "the full slot iri": str(SHELF_P),
    "a class name": "Book",
    "case": "Shelf",
}


@pytest.mark.parametrize("name", BAD_SLOTS.values(), ids=BAD_SLOTS.keys())
async def test_a_slot_name_the_schema_does_not_have_is_a_bad_query(
    toy_session, collaboration, name
):
    await put_book(toy_session, B1, shelf=S1)
    with pytest.raises(BadQuery):
        await as_ada(collaboration).referrers(S1, slot=name)
    assert refs(await as_ada(collaboration).referrers(S1)) == [(B1, "Book", "shelf")], "untouched"


# --- 4. shape of stored data -----------------------------------------------------------------


async def test_a_part_that_refers_names_its_aggregate_and_the_slot_of_the_part(
    toy_session, collaboration
):
    await put_book(toy_session, B1)
    b2 = dune(B2, chapters=2)
    b2.chapters[0].notes[0].about = B1
    b2.chapters[1].notes[0].about = B1
    await put(toy_session, b2)
    found = await as_ada(collaboration).referrers(B1)
    assert refs(found) == [(B2, "Book", "about")], "two notes, one slot, one aggregate: one item"


async def test_the_same_iri_held_by_a_root_slot_and_a_part_slot_is_listed_once_per_slot(
    toy_session, collaboration
):
    await put_book(toy_session, B1)
    b2 = dune(B2, chapters=1, sequel_of=B1)
    b2.chapters[0].notes[0].about = B1
    await put(toy_session, b2)
    mine = await as_ada(collaboration).referrers(B1)
    assert refs(mine) == [(B2, "Book", "about"), (B2, "Book", "sequel_of")], "one item per slot"
    theirs = await as_bob(collaboration, bob_reading_all_but(B2)).referrers(B1)
    assert (theirs.referrers, theirs.hidden_count) == (None, 1), "counted once whatever its slots"


async def test_a_referrer_of_a_class_the_schema_does_not_know_keeps_its_iris(
    toy_session, collaboration
):
    await put_raw(toy_session, B3, f"{LIB}Magazine", (SHELF_P, S1))
    found = await as_ada(collaboration).referrers(S1)
    assert refs(found) == [(B3, f"{LIB}Magazine", str(SHELF_P))], "class and slot stay as stored"
    assert found.hidden_count == 0, "readable like any aggregate"


async def test_a_referrer_of_an_unknown_class_is_hidden_like_any_other(toy_session, collaboration):
    await put_raw(toy_session, B3, f"{LIB}Magazine", (SHELF_P, S1))
    found = await as_bob(collaboration, bob_reading_all_but(B3)).referrers(S1)
    assert (found.referrers, found.hidden_count) == (None, 1), "counted"
    assert B3 not in found.model_dump_json() and "Magazine" not in found.model_dump_json(), (
        "unnamed"
    )


async def test_an_aggregate_with_two_types_names_a_known_slot_by_its_name(
    toy_session, collaboration
):
    await toy_session.add_graph(
        B3,
        [
            (URIRef(B3), RDF.type, BOOK_CLASS),
            (URIRef(B3), RDF.type, URIRef(f"{LIB}Magazine")),
            (URIRef(B3), SHELF_P, URIRef(S1)),
        ],
    )
    found = await as_ada(collaboration).referrers(S1)
    assert refs(found) == [(B3, "Book", "shelf")], "one item: the known type names the slot"


async def test_an_aggregate_with_no_type_is_not_found(toy_session, collaboration):  # RISK-6
    await put_raw(toy_session, B3, None, (SHELF_P, S1))
    found = await as_ada(collaboration).referrers(S1)
    assert (refs(found), found.hidden_count) == ([], 0), "known and accepted: no type, no row"


async def test_a_triple_in_a_graph_loaded_into_an_aggregate_is_not_a_reference(
    toy_session, collaboration
):
    """The spec reads 'across the aggregate graphs': a loaded graph is not one (decision to confirm)."""
    triples = toy_mapper().to_triples(dune(B1, chapters=1))
    version = await toy_session.add_graph(B1, triples)
    loaded = await toy_session.load_graph(
        B1, f"<{B1}/x> <{SHELF_P}> <{S1}> .".encode(), rdf_format=RdfFormat.NTRIPLES
    )
    await toy_session.replace_graph(B1, triples, version, loaded_graphs=[loaded])
    assert await toy_session.loaded_graphs(B1) == [loaded], "the load is registered"
    found = await as_ada(collaboration).referrers(S1)
    assert (refs(found), found.hidden_count) == ([], 0), "a loaded graph does not count"


async def test_a_referrer_whose_only_trace_is_its_bookkeeping_is_not_listed(
    collaboration,
):
    async with fake_session(tenant_iri=TENANT, principal=Principal(id=B1)) as session:
        await put_book(session, B2)  # created by b1: dcterms:creator <b1>
        found = await as_ada(collaboration, session).referrers(B1)
    assert (refs(found), found.hidden_count) == ([], 0), "the creator is about the graph"


async def test_a_literal_equal_to_the_iri_text_is_not_a_reference(toy_session, collaboration):
    await put_book(toy_session, B1, shelf=S2)
    book = dune(B2, chapters=1).model_copy(update={"description": S1, "label": S1})
    book.chapters[0].notes[0].text = S1
    await put(toy_session, book)
    await toy_session.add_graph(
        B3,
        [
            (URIRef(B3), RDF.type, BOOK_CLASS),
            (URIRef(B3), SHELF_P, Literal(S1)),
            (
                URIRef(B3),
                SEQUEL_P,
                Literal(S1, datatype=URIRef("http://www.w3.org/2001/XMLSchema#anyURI")),
            ),
        ],
    )
    found = await as_ada(collaboration).referrers(S1)
    assert (refs(found), found.hidden_count) == ([], 0), "only IRIs refer"


@pytest.mark.slow
async def test_many_referrers_come_back_complete_and_sorted(toy_session, collaboration):
    shelf_refs = {book_iri(n): "shelf" for n in range(10, 310)}
    async with toy_session.transaction() as work:  # one commit; the many writes are not the point
        for iri in shelf_refs:
            await work.add_graph(
                iri, [(URIRef(iri), RDF.type, BOOK_CLASS), (URIRef(iri), SHELF_P, URIRef(S1))]
            )
    found = await as_ada(collaboration).referrers(S1)
    listed = [r for r, _, _ in refs(found)]
    assert listed == sorted(shelf_refs), "all 300, sorted by IRI"
    assert found.hidden_count == 0, "none hidden"


async def test_many_hidden_referrers_are_all_counted(toy_session, collaboration):
    for n in range(10, 60):
        await put_raw(toy_session, book_iri(n), str(BOOK_CLASS), (SHELF_P, S1))
    found = await as_bob(collaboration, held(direct(Action.READ, graph_of(S1), BOB))).referrers(S1)
    assert (found.referrers, found.hidden_count) == (None, 50), "every one counted, none named"


# --- 5. class and slot names -----------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["Chapter", "Note", "Described", "AggregateRoot", "Tracked", "Library"],
    ids=lambda n: n,
)
async def test_a_class_that_is_not_an_aggregate_root_gives_an_empty_result(
    toy_session, collaboration, name
):
    await put_book(toy_session, B1, shelf=S1)
    found = await as_ada(collaboration).referrers(S1, class_name=name)
    assert (refs(found), found.hidden_count) == ([], 0), "no aggregate is typed so"


async def test_a_slot_of_a_part_narrows_to_the_aggregate_that_holds_the_part(
    toy_session, collaboration
):
    b2 = dune(B2, chapters=1)
    b2.chapters[0].notes[0].about = B1
    await put_book(toy_session, B1)
    await put(toy_session, b2)
    found = await as_ada(collaboration).referrers(B1, slot="about", class_name="Book")
    assert refs(found) == [(B2, "Book", "about")], "the part's slot, the root's class"
    note_class = await as_ada(collaboration).referrers(B1, class_name="Note")
    assert refs(note_class) == [], "the class is the referrer's, never the part's"


async def test_a_predicate_the_stored_class_has_no_slot_for_is_named_by_its_iri(
    toy_session, collaboration
):
    """A shelf holding ``sequelOf`` (a slot of Book): the name falls back to the predicate IRI."""
    await put_raw(toy_session, S2, f"{LIB}Shelf", (SEQUEL_P, S1))
    found = await as_ada(collaboration).referrers(S1)
    assert refs(found) == [(S2, "Shelf", str(SEQUEL_P))], (
        "the slot's name is not the Shelf's to give"
    )
    narrowed = await as_ada(collaboration).referrers(S1, slot="sequel_of")
    assert refs(narrowed) == [], "narrowing by name keeps the items named so, and this one is not"


async def test_the_class_of_a_subject_that_is_a_part_does_not_name_the_slot(
    toy_session, collaboration
):
    """The note's ``about`` is named by Note's slots, though the referrer is a Book."""
    b2 = dune(B2, chapters=1)
    b2.chapters[0].notes[0].about = B1
    await put_book(toy_session, B1)
    await put(toy_session, b2)
    found = await as_ada(collaboration).referrers(B1)
    assert [s for _, _, s in refs(found)] == ["about"], "the name, not the lib: IRI"


# --- 6. the kit ------------------------------------------------------------------------------


@pytest.fixture
async def service() -> AsyncIterator[ToyService]:
    toy = ToyService()
    async with toy.app.router.lifespan_context(toy.app):
        yield toy


async def made_tenant(service: ToyService, who: str = "ada") -> tuple[str, str, str]:
    """A tenant made by ``who``, with a shelf-bearing book: ``(tenant id, tenant IRI, shelf IRI)``."""
    async with service.client() as client:
        headers = service.bearer(who)
        made = await client.post("/libraries", json=TENANT_BODY, headers=headers)
        path = made.headers["location"]
        tenant_id = path.rsplit("/", 1)[1]
        tenant = service.kit.tenant_iri(tenant_id)
        shelf = f"{tenant}/shelves/6f1c0c1e-0000-4000-8000-000000000001"
        book = await client.post(
            f"{path}/books", json={**DUNE_BODY, "shelf": shelf}, headers=headers
        )
        assert book.status_code == 201, book.text
    return tenant_id, str(tenant), shelf


def authorised_as(principal: str, tenant: str, *grants, global_roles=None) -> Authorised:
    return Authorised(
        principal=principal,
        caller_access=CallerAccess(
            tenant=tenant, state=TenantState.ACTIVE, grants=list(grants) or None
        ),
        checked_target=tenant,
        global_roles=global_roles,
    )


async def test_a_collaboration_acts_for_the_tenant_of_the_access_only(service):
    _, mine, my_shelf = await made_tenant(service)
    _, theirs, their_shelf = await made_tenant(service, "bob")
    authorised = authorised_as(
        principal_of("ada"), mine, role("librarian", target=mine, who=principal_of("ada"))
    )
    async with service.kit.collaboration(authorised) as collaboration:
        assert len((await collaboration.referrers(my_shelf)).referrers or []) == 1, "its own tenant"
        with pytest.raises(InvalidIri):
            await collaboration.referrers(their_shelf)


async def test_a_collaboration_acts_as_the_authorised_principal_only(service):
    tenant_id, tenant, shelf = await made_tenant(service)
    stranger = authorised_as(principal_of("mallory"), tenant)
    async with service.kit.collaboration(stranger) as collaboration:
        with pytest.raises(NotFound):
            await collaboration.referrers(shelf)
    reader = authorised_as(
        principal_of("rita"), tenant, role("reader", target=tenant, who=principal_of("rita"))
    )
    async with service.kit.collaboration(reader) as collaboration:
        assert (await collaboration.referrers(shelf)).hidden_count == 0, "rita reads the book"


async def test_an_authorised_with_no_global_roles_gets_no_system_access(service):
    _, tenant, shelf = await made_tenant(service)
    nobody = authorised_as(principal_of("mallory"), tenant, global_roles=None)
    async with service.kit.collaboration(nobody) as collaboration:
        with pytest.raises(NotFound):
            await collaboration.referrers(shelf)
    admin = authorised_as(principal_of("mallory"), tenant, global_roles=["admin"])
    async with service.kit.collaboration(admin) as collaboration:
        assert len((await collaboration.referrers(shelf)).referrers or []) == 1, "the role reads"


async def test_an_authorised_with_an_empty_list_of_global_roles_gets_no_system_access(service):
    _, tenant, shelf = await made_tenant(service)
    nobody = authorised_as(principal_of("mallory"), tenant, global_roles=[])
    async with service.kit.collaboration(nobody) as collaboration:
        with pytest.raises(NotFound):
            await collaboration.referrers(shelf)


async def test_a_collaboration_of_a_tenant_that_does_not_exist_is_refused(service):
    ghost = "https://example.org/libraries/6f1c0c1e-0000-4000-8000-0000000000ff"
    authorised = authorised_as(
        principal_of("ada"), ghost, role("librarian", target=ghost, who=principal_of("ada"))
    )
    with pytest.raises((NotFound, InvalidIri, LookupError)) as raised:
        async with service.kit.collaboration(authorised) as collaboration:
            await collaboration.referrers(f"{ghost}/shelves/6f1c0c1e-0000-4000-8000-000000000001")
    assert type(raised.value).__module__.startswith("rdf_persistence"), "a documented error"

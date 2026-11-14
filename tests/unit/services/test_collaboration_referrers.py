"""Collaboration.referrers: who points at a resource, as the caller may read them (PD-3, #78)."""

import pytest
from rdflib import URIRef

from rdf_persistence import Action
from rdf_persistence.domain.exceptions import BadQuery, Forbidden, InvalidIri
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.service.rp_service import Referrer, ReferrerList
from rdf_persistence.services.schema import load_schema
from rdf_persistence.testkit import fake_session
from tests.fixtures.library.generated.books import Book
from tests.toy import (
    ADA,
    BOB,
    TENANT,
    TOY_SCHEMA,
    ban,
    book_iri,
    caller,
    dune,
    graph_of,
    held,
    role,
    shelf_iri,
    toy_mapper,
)

B1, B2, B3, B4 = (book_iri(n) for n in (1, 2, 3, 4))
S1, S2, S9 = shelf_iri(1), shelf_iri(2), shelf_iri(9)


async def put(session, model) -> None:
    await session.add_graph(model.id, toy_mapper().to_triples(model))


async def put_book(session, iri: str, **slots: str) -> Book:
    book = dune(iri, chapters=1, **slots)
    await put(session, book)
    return book


def as_ada(collaboration, session=None):
    return collaboration(caller(principal=ADA), held(role("librarian")), session)


def as_bob(collaboration, hidden: str = B2):
    access = held(role("reader", who=BOB), bans=[ban(Action.READ, graph_of(hidden), BOB)])
    return collaboration(caller(principal=BOB), access)


def refs(found: ReferrerList) -> list[tuple[str, str, str]]:
    return [(r.referrer, r.referrer_class, r.referrer_slot) for r in found.referrers or []]


async def test_a_resource_lists_the_aggregates_that_point_at_it_by_slot(toy_session, collaboration):
    await put_book(toy_session, B1, shelf=S1)
    await put_book(toy_session, B2, shelf=S1)
    await put_book(toy_session, B3, shelf=S2)
    found = await as_ada(collaboration).referrers(S1)
    assert isinstance(found, ReferrerList), "a generated model, not a dict"
    assert all(isinstance(r, Referrer) for r in found.referrers), "each item a generated model"
    assert refs(found) == [(B1, "Book", "shelf"), (B2, "Book", "shelf")], "b3 is on s2"
    assert found.hidden_count == 0, "ada may read both"


async def test_a_referrer_the_caller_may_not_read_is_counted_and_not_named(
    toy_session, collaboration
):
    await put_book(toy_session, B1, shelf=S1)
    await put_book(toy_session, B2, shelf=S1)
    found = await as_bob(collaboration).referrers(S1)
    assert refs(found) == [(B1, "Book", "shelf")], "bob may read only b1"
    assert found.hidden_count == 1, "b2 is counted"
    assert B2 not in found.model_dump_json(), "and never named"


B2_ABOUT, B3_SEQUEL = (B2, "Book", "about"), (B3, "Book", "sequel_of")


@pytest.mark.parametrize(
    ("narrow", "expected"),
    [
        ({"slot": "sequel_of"}, [B3_SEQUEL]),
        ({"slot": "about"}, [B2_ABOUT]),
        ({"slot": "shelf"}, []),
        ({"class_name": "Book"}, [B2_ABOUT, B3_SEQUEL]),
        ({"class_name": "Shelf"}, []),
        ({"class_name": "Book", "slot": "sequel_of"}, [B3_SEQUEL]),
    ],
    ids=[
        "slot kept",
        "slot of a part kept",
        "slot nobody uses",
        "class kept",
        "class nobody has",
        "class and slot",
    ],
)
async def test_a_class_and_a_slot_keep_only_the_referrers_that_match(
    toy_session, collaboration, narrow, expected
):
    await put_book(toy_session, B1)
    await put_book(toy_session, B3, sequel_of=B1)
    b2 = dune(B2, chapters=1)
    b2.chapters[0].notes[0].about = B1
    await put(toy_session, b2)
    found = await as_ada(collaboration).referrers(B1, **narrow)
    assert refs(found) == expected, "the rows of that class and slot, sorted"
    assert found.hidden_count == 0, "ada may read all"


@pytest.mark.parametrize(
    "narrow", [{}, {"slot": "sequel_of"}, {"class_name": "Shelf"}], ids=["none", "slot", "class"]
)
async def test_narrowing_never_changes_the_hidden_count(toy_session, collaboration, narrow):
    await put_book(toy_session, B1, shelf=S1)
    await put_book(toy_session, B2, shelf=S1)
    found = await as_bob(collaboration).referrers(S1, **narrow)
    assert found.hidden_count == 1, "b2 is hidden, whatever the call asks for"
    assert B2 not in found.model_dump_json(), "and never named"


async def test_without_narrowing_a_part_that_refers_names_its_aggregate(toy_session, collaboration):
    await put_book(toy_session, B1)
    await put_book(toy_session, B3, sequel_of=B1)
    b2 = dune(B2, chapters=1)
    b2.chapters[0].notes[0].about = B1
    await put(toy_session, b2)
    found = await as_ada(collaboration).referrers(B1)
    assert refs(found) == [(B2, "Book", "about"), (B3, "Book", "sequel_of")], "sorted by referrer"


async def test_a_referrer_that_refers_by_two_slots_is_listed_twice_and_hidden_once(
    toy_session, collaboration
):
    await put_book(toy_session, B1)
    b4 = dune(B4, chapters=1, sequel_of=B1)
    b4.chapters[0].notes[0].about = B1
    await put(toy_session, b4)
    mine = await as_ada(collaboration).referrers(B1)
    assert refs(mine) == [(B4, "Book", "about"), (B4, "Book", "sequel_of")], "one item per slot"
    theirs = await as_bob(collaboration, hidden=B4).referrers(B1)
    assert refs(theirs) == [], "b4 is hidden"
    assert theirs.hidden_count == 1, "counted once, whatever its slots"


async def test_an_unused_resource_gives_an_empty_result(toy_session, collaboration):
    await put_book(toy_session, B1, shelf=S1)
    found = await as_ada(collaboration).referrers(S9)
    assert refs(found) == [], "nothing refers to s9"
    assert found.hidden_count == 0, "and nothing is hidden"


async def test_an_iri_the_policy_does_not_mint_is_refused(collaboration):
    with pytest.raises(InvalidIri):
        await as_ada(collaboration).referrers("https://elsewhere.org/x")


@pytest.mark.parametrize(
    "narrow", [{"slot": "nope"}, {"class_name": "Nope"}], ids=["unknown slot", "unknown class"]
)
async def test_a_class_or_slot_the_schema_does_not_have_is_a_bad_query(collaboration, narrow):
    with pytest.raises(BadQuery, match="Nope|nope"):
        await as_ada(collaboration).referrers(S1, **narrow)


async def test_a_caller_prohibited_from_reading_the_resource_is_forbidden(
    toy_session, collaboration
):
    await put_book(toy_session, B1, shelf=S1)
    access = held(role("reader", who=BOB), bans=[ban(Action.READ, graph_of(S1), BOB)])
    with pytest.raises(Forbidden):
        await collaboration(caller(principal=BOB), access).referrers(S1)


async def test_the_tracking_statements_of_a_graph_are_not_referrers(collaboration):
    async with fake_session(tenant_iri=TENANT, principal=Principal(id=S1)) as session:
        await put_book(session, B1)  # its graph names s1 as its creator
        found = await as_ada(collaboration, session).referrers(S1)
    assert refs(found) == [], "dcterms:creator is about the graph"
    assert found.hidden_count == 0, "and not a hidden referrer either"


async def test_a_link_is_dropped_only_for_the_class_a_dependent_pair_names(toy_session):
    await put_book(toy_session, B1, shelf=S1)
    view = load_schema(TOY_SCHEMA)
    book = URIRef(view.get_uri(view.get_class("Book"), expand=True))
    note = URIRef(view.get_uri(view.get_class("Note"), expand=True))
    shelf = URIRef(view.get_uri(view.get_slot("shelf"), expand=True))
    assert await toy_session.referrer_rows(S1, dependents=[(book, shelf)]) == [], "a book's shelf"
    kept = await toy_session.referrer_rows(S1, dependents=[(note, shelf)])
    assert [r[0] for r in kept] == [B1], "the same predicate on another class still counts"

"""Nested collections: what a deep read, a plain read, a cascade and collections_of make of a tree (PD-6, PD-8)."""

import pytest

from rdf_persistence import StoredDataInvalid, generated_models
from rdf_persistence.collaboration.services.write_guards import WriteGuards
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.testkit import fake_session
from tests.toy import MODULES, TENANT, TOY_SCHEMA, book_iri, shelf_iri, toy_mapper
from tests.unit.collaboration.test_collaboration_cascade import stored
from tests.unit.collaboration.test_collaboration_collections import a_shelf as plain_shelf
from tests.unit.collaboration.test_collaboration_collections import (
    as_ada,
    as_bob_without,
    put,
    put_book,
)

B0, B1, B2 = (book_iri(n) for n in (10, 11, 12))
L1, L2, L3 = (shelf_iri(n) for n in (11, 12, 13))


def nesting(iri: str, *parts: str):
    return plain_shelf(iri, nests=True, has_part=list(parts) or None)


@pytest.fixture
async def guarded():
    """A session whose writes check collections, the way the kit's sessions do."""
    listings = Listings(load_schema(TOY_SCHEMA))
    guards = WriteGuards(toy_mapper(), generated_models(*MODULES), listings)
    async with fake_session(tenant_iri=TENANT, listings=listings, guards=guards) as session:
        yield session


async def three_levels(session) -> None:
    """L1 holds b0 and L2; L2 holds b1 and L3; L3 holds b2."""
    for iri in (B0, B1, B2):
        await put_book(session, iri)
    await put(session, nesting(L3, B2))
    await put(session, nesting(L2, B1, L3))
    await put(session, nesting(L1, B0, L2))


async def test_a_deep_read_lists_the_items_of_every_level_and_no_sub_collection(
    guarded, collaboration
):
    await three_levels(guarded)
    found = await as_ada(collaboration, guarded).members(L1, deep=True)
    assert found.member_iris == sorted([B0, B1, B2]), "the items of the three levels"
    assert found.hidden_count == 0, "the sub-collections are structure, not hidden"


async def test_a_plain_read_of_a_nesting_collection_lists_its_sub_collections(
    guarded, collaboration
):
    await three_levels(guarded)
    found = await as_ada(collaboration, guarded).members(L1)
    assert found.member_iris == sorted([B0, L2]), "its own members, the sub-shelf among them"


async def test_a_deep_read_counts_an_unreadable_item_of_the_second_level(guarded, collaboration):
    await three_levels(guarded)
    found = await as_bob_without(collaboration, guarded, B1).members(L1, deep=True)
    assert found.member_iris == sorted([B0, B2]), "b1 is not listed, b2 below it still is"
    assert found.hidden_count == 1, "b1 is counted once"


async def test_a_deep_read_counts_an_unreadable_sub_collection_and_does_not_enter_it(
    guarded, collaboration
):
    await three_levels(guarded)
    found = await as_bob_without(collaboration, guarded, L2).members(L1, deep=True)
    assert found.member_iris == [B0], "nothing of what L2 holds is listed"
    assert found.hidden_count == 1, "L2 is counted once"


async def test_an_item_named_at_two_levels_is_listed_and_counted_once(guarded, collaboration):
    for iri in (B1, B2):
        await put_book(guarded, iri)
    await put(guarded, nesting(L2, B1, B2))
    await put(guarded, nesting(L1, B1, L2))
    visible = await as_ada(collaboration, guarded).members(L1, deep=True)
    assert visible.member_iris == sorted([B1, B2]), "b1 is at two levels, listed once"
    hidden = await as_bob_without(collaboration, guarded, B1).members(L1, deep=True)
    assert hidden.hidden_count == 1, "and counted once when unreadable"


async def test_collections_of_a_sub_collection_gives_its_parent(guarded, collaboration):
    await three_levels(guarded)
    found = await as_ada(collaboration, guarded).collections_of(L2)
    assert found.member_iris == [L1], "the shelf that nests it"


async def test_a_cascade_of_a_nesting_shelf_deletes_the_sub_shelf_and_keeps_its_books(
    guarded, collaboration
):
    for iri in (B0, B1):
        await put_book(guarded, iri)
    await put(guarded, nesting(L2, B1))
    await put(guarded, nesting(L1, B0, L2))
    version = (await guarded.get_graph(L1))[2]
    await as_ada(collaboration, guarded).delete_cascade(L1, version)
    assert not any([await stored(guarded, i) for i in (L1, L2, B0)]), (
        "the shelf, its sub-shelf and its book"
    )
    assert await stored(guarded, B1), "the book of the sub-shelf stays"


async def test_a_deep_read_refuses_a_stored_nested_shelf_of_another_member_class(
    toy_session, collaboration
):
    """Written without guards: the nested shelf holds authors, the nesting one holds books."""
    await put(toy_session, plain_shelf(L2, member_class="Author"))
    await put(toy_session, nesting(L1, L2))
    with pytest.raises(StoredDataInvalid, match=L2):
        await as_ada(collaboration, toy_session).members(L1, deep=True)

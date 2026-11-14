"""Collaboration.members and collections_of: what a reference collection holds (PD-7, #79)."""

import pytest
from rdflib import RDF, URIRef

from rdf_persistence import Action, StoredDataInvalid, generated_models
from rdf_persistence.domain.exceptions import Forbidden, InvalidBody, InvalidIri
from rdf_persistence.domain.generated.rp_collections import MembershipRule, SlotEquality
from rdf_persistence.domain.generated.service.rp_service import Filter, ListRequest, MemberList
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.write_guards import WriteGuards
from rdf_persistence.testkit import fake_session
from tests.fixtures.library.generated.books import Genre, Shelf
from tests.toy import (
    ADA,
    BOB,
    MODULES,
    ROLES,
    TENANT,
    TOY_SCHEMA,
    ban,
    book_iri,
    caller,
    dune,
    graph_of,
    held,
    role,
    shelf,
    shelf_iri,
    toy_mapper,
)

B1, B2, B3, B5 = (book_iri(n) for n in (1, 2, 3, 5))
S1, S2 = shelf_iri(1), shelf_iri(2)
A, B = shelf_iri(3), shelf_iri(4)
PARTIAL = TOY_SCHEMA.parent / "partial.yaml"


def poetry(slot: str = "genre", value: str = "poetry") -> MembershipRule:
    return MembershipRule(rule_equalities=[SlotEquality(equals_slot=slot, equals_value=value)])


def a_shelf(iri: str, **slots):
    return shelf(iri).model_copy(update=slots)


async def put(session, model) -> None:
    await session.add_graph(model.id, toy_mapper().to_triples(model))


async def put_book(session, iri: str, genre: Genre = Genre.FICTION) -> None:
    await put(session, dune(iri, chapters=1).model_copy(update={"genre": genre.value}))


@pytest.fixture
async def guarded():
    """A session whose writes check collections, the way the kit's sessions do."""
    listings = Listings(load_schema(TOY_SCHEMA))
    guards = WriteGuards(toy_mapper(), generated_models(*MODULES), listings)
    async with fake_session(tenant_iri=TENANT, listings=listings, guards=guards) as session:
        yield session


def as_ada(collaboration, session):
    return collaboration(caller(principal=ADA), held(role("librarian")), session)


def as_bob(collaboration, session, hidden: str = B2):
    access = held(role("reader", who=BOB), bans=[ban(Action.READ, graph_of(hidden), BOB)])
    return collaboration(caller(principal=BOB), access, session)


async def test_a_rule_alone_makes_the_matching_aggregates_members(guarded, collaboration):  # TC-23
    await put_book(guarded, B5, Genre.POETRY)
    await put_book(guarded, B1)
    await put(guarded, a_shelf(S1, membership_rule=poetry()))
    found = await as_ada(collaboration, guarded).members(S1)
    assert isinstance(found, MemberList), "a generated model, not a dict"
    assert found.member_iris == [B5], "the poetry book, not the fiction one"


async def test_the_explicit_and_the_rule_members_are_joined_and_sorted(
    guarded, collaboration
):  # TC-24
    await put_book(guarded, B1)
    await put_book(guarded, B3, Genre.POETRY)
    await put(guarded, a_shelf(S1, had_member=[B1], membership_rule=poetry()))
    found = await as_ada(collaboration, guarded).members(S1)
    assert found.member_iris == [B1, B3], "explicit b1 and rule b3, sorted"
    assert found.hidden_count == 0, "ada may read both"


async def test_a_member_a_caller_may_not_read_is_counted_and_not_named(
    guarded, collaboration
):  # TC-25
    await put_book(guarded, B1)
    await put_book(guarded, B2)
    await put(guarded, a_shelf(S1, had_member=[B1, B2]))
    found = await as_bob(collaboration, guarded).members(S1)
    assert found.member_iris == [B1], "bob may read only b1"
    assert found.hidden_count == 1, "b2 is counted"
    assert B2 not in found.model_dump_json(), "and never named"


async def test_a_collection_of_a_member_who_matches_both_ways_lists_it_once(guarded, collaboration):
    await put_book(guarded, B3, Genre.POETRY)
    await put(guarded, a_shelf(S1, had_member=[B3], membership_rule=poetry()))
    found = await as_ada(collaboration, guarded).members(S1)
    assert found.member_iris == [B3], "named and matched, listed once"


async def test_a_rule_with_no_equality_means_every_aggregate_of_the_class(guarded, collaboration):
    await put_book(guarded, B1)
    await put_book(guarded, B3, Genre.POETRY)
    await put(guarded, a_shelf(S1, membership_rule=MembershipRule()))
    found = await as_ada(collaboration, guarded).members(S1)
    assert found.member_iris == [B1, B3], "both books, whatever their genre"


async def test_a_deep_read_goes_into_the_members_that_are_collections(
    guarded, collaboration
):  # TC-26
    await put_book(guarded, B1)
    await put(guarded, a_shelf(B, member_class="Book", had_member=[B1]))
    await put(guarded, a_shelf(A, member_class="Shelf", had_member=[B]))
    build = as_ada(collaboration, guarded)
    assert (await build.members(A)).member_iris == [B], "not deep: only the shelf"
    assert (await build.members(A, deep=True)).member_iris == sorted([B, B1]), "deep: and its book"


async def test_a_deep_read_of_collections_that_hold_each_other_ends(
    guarded, collaboration
):  # TC-27
    await put(guarded, a_shelf(A, member_class="Shelf"))
    await put(guarded, a_shelf(B, member_class="Shelf", had_member=[A]))
    stored = await guarded.get_graph(A)
    await guarded.replace_graph(
        A, toy_mapper().to_triples(a_shelf(A, member_class="Shelf", had_member=[B])), stored[2]
    )
    found = await as_ada(collaboration, guarded).members(A, deep=True)
    assert found.member_iris == sorted([A, B]), "each is the other's member, and the read ends"


async def test_a_deep_read_does_not_go_into_a_collection_the_caller_may_not_read(
    guarded, collaboration
):  # TC-28
    await put_book(guarded, B1)
    await put(guarded, a_shelf(B, member_class="Book", had_member=[B1]))
    await put(guarded, a_shelf(A, member_class="Shelf", had_member=[B]))
    found = await as_bob(collaboration, guarded, hidden=B).members(A, deep=True)
    assert found.member_iris is None, "b is hidden, and b1 behind it is not reached"
    assert found.hidden_count == 1, "b is counted"


async def test_a_member_collection_that_is_gone_is_a_leaf_of_a_deep_read(guarded, collaboration):
    await put(guarded, a_shelf(B, member_class="Book"))
    await put(guarded, a_shelf(A, member_class="Shelf", had_member=[B]))
    await guarded.remove(B, (await guarded.get_graph(B))[2])
    found = await as_ada(collaboration, guarded).members(A, deep=True)
    assert found.member_iris == [B], "b is still named, and has no members of its own"


async def test_a_stored_collection_the_schema_no_longer_accepts_is_stored_data_invalid(
    toy_session, collaboration
):  # TC-31
    await put(toy_session, a_shelf(S1, membership_rule=poetry("colour", "red")))  # no guards
    with pytest.raises(StoredDataInvalid, match=S1):
        await as_ada(collaboration, toy_session).members(S1)


async def test_members_of_a_caller_prohibited_from_reading_the_collection_are_forbidden(
    guarded, collaboration
):
    await put(guarded, a_shelf(S1))
    access = held(role("reader", who=BOB), bans=[ban(Action.READ, graph_of(S1), BOB)])
    with pytest.raises(Forbidden):
        await collaboration(caller(principal=BOB), access, guarded).members(S1)


async def test_a_schema_without_the_collection_module_has_no_members_or_collections_of_but_referrers(
    toy_session,
):  # TC-09a, both halves
    view = load_schema(PARTIAL)
    rules = AccessRules(load_role_definitions(ROLES))
    build = Collaboration(
        toy_session,
        view=view,
        rules=rules,
        iris=DEFAULT_IRIS,
        mapper=toy_mapper(),
        models=generated_models(*MODULES),
        listings=Listings(view),
        caller=caller(principal=ADA),
        access=held(role("librarian")),
    )
    with pytest.raises(LookupError, match="rp_collections"):
        await build.members(S1)
    with pytest.raises(LookupError, match="rp_collections"):
        await build.collections_of(B1)
    await put(toy_session, dune(B1, chapters=1).model_copy(update={"shelf": S1}))
    found = await build.referrers(S1)  # the referrers read needs no collection module
    assert [r.referrer for r in found.referrers or []] == [B1], "it works all the same"


async def test_the_collections_that_hold_a_member_are_those_that_list_it_or_match_it(
    guarded, collaboration
):  # TC-29
    await put_book(guarded, B3, Genre.POETRY)
    await put(guarded, a_shelf(S1, had_member=[B3]))
    await put(guarded, a_shelf(S2, membership_rule=poetry()))
    found = await as_ada(collaboration, guarded).collections_of(B3)
    assert isinstance(found, MemberList), "a generated model"
    assert found.member_iris == [S1, S2], "s1 lists it, s2 matches it"
    assert found.hidden_count == 0, "ada may read both"


async def test_a_collection_that_holds_a_member_both_ways_is_counted_once(guarded, collaboration):
    await put_book(guarded, B3, Genre.POETRY)
    await put(guarded, a_shelf(S1, had_member=[B3], membership_rule=poetry()))
    found = await as_bob(collaboration, guarded, hidden=S1).collections_of(B3)
    assert found.member_iris is None, "bob may not read s1"
    assert found.hidden_count == 1, "and it is one collection, not two holders"


async def test_a_rule_that_the_member_does_not_meet_is_not_a_holder(guarded, collaboration):
    await put_book(guarded, B1)
    await put(guarded, a_shelf(S1, membership_rule=poetry()))
    found = await as_ada(collaboration, guarded).collections_of(B1)
    assert found.member_iris is None, "b1 is fiction, the rule asks for poetry"


async def test_a_collection_of_another_member_class_is_not_tested(guarded, collaboration):  # TC-30
    await put_book(guarded, B3, Genre.POETRY)
    await put(guarded, a_shelf(S2, member_class="Shelf", membership_rule=MembershipRule()))
    found = await as_ada(collaboration, guarded).collections_of(B3)
    assert found.member_iris is None, "s2 collects shelves, whatever its rule says"


async def test_a_hidden_holder_is_counted_and_not_named(guarded, collaboration):
    await put_book(guarded, B3, Genre.POETRY)
    await put(guarded, a_shelf(S1, had_member=[B3]))
    await put(guarded, a_shelf(S2, membership_rule=poetry()))
    found = await as_bob(collaboration, guarded, hidden=S2).collections_of(B3)
    assert found.member_iris == [S1], "bob may read only s1"
    assert found.hidden_count == 1, "s2 is counted"
    assert S2 not in found.model_dump_json(), "and never named"


async def test_a_hidden_referrer_that_is_no_collection_is_not_counted(guarded, collaboration):
    await put_book(guarded, B1)
    await put_book(guarded, B2)
    await put(guarded, a_shelf(S1, had_member=[B1]))
    await put(guarded, dune(B3, chapters=1, sequel_of=B1))  # a book that points at b1
    found = await as_bob(collaboration, guarded, hidden=B3).collections_of(B1)
    assert found.member_iris == [S1], "the shelf"
    assert found.hidden_count == 0, "b3 refers to b1 but is not a collection"


async def test_a_member_that_is_not_stored_has_only_its_explicit_holders(guarded, collaboration):
    await put_book(guarded, B1)
    await put(guarded, a_shelf(S1, had_member=[B1]))
    await guarded.remove(B1, (await guarded.get_graph(B1))[2])
    found = await as_ada(collaboration, guarded).collections_of(B1)
    assert found.member_iris == [S1], "the shelf still lists it; no rule is asked about a gone book"


async def test_a_deleted_member_stays_named_and_blocks_the_next_save_until_it_is_taken_out(
    guarded, collaboration
):  # the how-to: no referential integrity
    await put_book(guarded, B1)
    await put_book(guarded, B2)
    await put(guarded, a_shelf(S1, had_member=[B1, B2]))
    await guarded.remove(B1, (await guarded.get_graph(B1))[2])
    build = as_ada(collaboration, guarded)
    assert (await build.members(S1)).member_iris == [B1, B2], "the deleted book is still listed"
    assert (await build.members(S1, deep=True)).member_iris == [B1, B2], "deep reads list it too"
    work = UnitOfWork(guarded, toy_mapper())
    stale = await work.get(Shelf, S1)
    work.add(stale)
    with pytest.raises(InvalidBody, match=B1):
        await work.commit()
    work = UnitOfWork(guarded, toy_mapper())
    fresh = await work.get(Shelf, S1)
    fresh.had_member = [B2]
    work.add(fresh)
    await work.commit()
    assert (await build.members(S1)).member_iris == [B2], "taken out, the shelf is saved"


async def test_a_shelf_is_changed_by_a_replace_and_its_token_deletes_it(guarded, collaboration):
    await put_book(guarded, B1)
    await put_book(guarded, B2)
    await put(guarded, a_shelf(S1, had_member=[B1]))
    work = UnitOfWork(guarded, toy_mapper())
    edited = await work.get(Shelf, S1)
    edited.had_member = [*(edited.had_member or []), B2]
    work.add(edited)
    await work.commit()
    work = UnitOfWork(guarded, toy_mapper())
    await work.get(Shelf, S1)
    await as_ada(collaboration, guarded).delete_cascade(S1, work.version(S1))
    assert not await guarded.heads([S1, B1, B2]), "the shelf and both books are gone"


async def test_a_shelf_of_shelves_with_an_empty_rule_holds_itself(guarded, collaboration):
    await put(guarded, a_shelf(S1, member_class="Shelf", membership_rule=MembershipRule()))
    await put(guarded, a_shelf(S2))
    build = as_ada(collaboration, guarded)
    assert (await build.members(S1)).member_iris == [S1, S2], "every shelf, itself included"
    await build.delete_cascade(S1, (await guarded.get_graph(S1))[2])
    assert not await guarded.heads([S1, S2]), "the cascade deletes both, itself once"


def genre_plan(value: str):
    listings = Listings(load_schema(TOY_SCHEMA))
    return listings.plan(
        listings.served_root("Book"), ListRequest(filters=[Filter(slot="genre", value=value)])
    )


async def test_the_matching_of_one_aggregate_is_asked_of_the_store(toy_session):
    await put_book(toy_session, B3, Genre.POETRY)
    verse, prose = genre_plan("poetry"), genre_plan("fiction")
    assert await toy_session.matches(B3, verse.target, verse.conditions or []), "b3 is poetry"
    assert not await toy_session.matches(B3, prose.target, prose.conditions or []), "not fiction"
    assert not await toy_session.matches(B2, verse.target, verse.conditions or []), (
        "b2 is not stored"
    )


def as_bob_without(collaboration, session, *hidden: str):
    bans = [ban(Action.READ, graph_of(h), BOB) for h in hidden]
    return collaboration(caller(principal=BOB), held(role("reader", who=BOB), bans=bans), session)


async def test_a_rule_does_not_count_what_its_author_may_not_read(guarded, collaboration):
    await put_book(guarded, B3, Genre.POETRY)
    await put_book(guarded, B5, Genre.POETRY)
    await put(guarded, a_shelf(S1, membership_rule=poetry()))
    found = await as_bob_without(collaboration, guarded, B5).members(S1)
    assert found.member_iris == [B3], "the poetry book bob may read"
    assert found.hidden_count == 0, "the one he may not read is dropped, not counted"


async def test_a_hidden_named_member_is_counted_and_a_hidden_rule_member_is_not(
    guarded, collaboration
):
    for iri in (B1, B2):
        await put_book(guarded, iri)
    await put_book(guarded, B3, Genre.POETRY)
    await put(guarded, a_shelf(S1, had_member=[B1, B2], membership_rule=poetry()))
    found = await as_bob_without(collaboration, guarded, B2, B3).members(S1)
    assert found.member_iris == [B1], "bob may read b1 only"
    assert found.hidden_count == 1, "b2 is named, so counted; b3 only matches, so it is not"


async def test_a_deep_read_does_not_count_a_hidden_rule_member_of_a_nested_collection(
    guarded, collaboration
):
    await put_book(guarded, B3, Genre.POETRY)
    await put(guarded, a_shelf(B, member_class="Book", membership_rule=poetry()))
    await put(guarded, a_shelf(A, member_class="Shelf", had_member=[B]))
    found = await as_bob_without(collaboration, guarded, B3).members(A, deep=True)
    assert found.member_iris == [B], "the nested shelf"
    assert found.hidden_count == 0, "b3 matches b's rule and is hidden: not counted"


async def test_a_collection_that_is_not_an_aggregate_of_the_tenant_is_an_invalid_iri(
    guarded, collaboration
):
    with pytest.raises(InvalidIri):
        await as_ada(collaboration, guarded).members("https://elsewhere.org/shelf")


async def test_a_deep_read_refuses_a_stored_member_class_that_is_no_served_root(
    toy_session, collaboration
):
    """A collection written without guards, naming a class a cascade must never delete."""
    await put(toy_session, a_shelf(S1, member_class="LibraryAccess"))
    with pytest.raises(StoredDataInvalid, match=S1):
        await as_ada(collaboration, toy_session).members(S1, deep=True)


async def test_a_plain_read_lists_what_a_collection_of_no_served_class_names(
    toy_session, collaboration
):
    await put(toy_session, a_shelf(S1, member_class="LibraryAccess"))
    found = await as_ada(collaboration, toy_session).members(S1)
    assert found.member_iris is None, "it names none"


async def test_an_unknown_member_class_is_stored_data_invalid_not_an_attribute_error(
    toy_session, collaboration
):
    await put(toy_session, a_shelf(S1, member_class="NoSuchClass"))
    with pytest.raises(StoredDataInvalid, match=S1):
        await as_ada(collaboration, toy_session).members(S1, deep=True)


async def test_a_deep_read_names_the_nested_collection_whose_rule_is_bad(
    toy_session, collaboration
):
    await put(toy_session, a_shelf(B, member_class="Book", membership_rule=poetry("colour", "red")))
    await put(toy_session, a_shelf(A, member_class="Shelf", had_member=[B]))
    with pytest.raises(StoredDataInvalid) as refused:
        await as_ada(collaboration, toy_session).members(A, deep=True)
    assert B in str(refused.value), "b is the broken one"
    assert A not in str(refused.value), "not the shelf the caller asked about"


async def test_a_collection_is_decoded_from_its_own_graph_only(toy_session, collaboration):
    """a holds a fiction rule and, inside its graph, the triples of a collection b with another rule."""
    await put_book(toy_session, B3, Genre.POETRY)
    foreign = toy_mapper().to_triples(a_shelf(B, membership_rule=poetry("genre", "fiction")))
    own = toy_mapper().to_triples(a_shelf(A, membership_rule=poetry("genre", "fiction")))
    await toy_session.add_graph(A, [*own, *foreign])
    found = await as_ada(collaboration, toy_session).collections_of(B3)
    assert found.member_iris is None, "b is no holder: its triples in a's graph make no collection"
    await put(toy_session, a_shelf(B, membership_rule=poetry()))
    found = await as_ada(collaboration, toy_session).collections_of(B3)
    assert found.member_iris == [B], "the real b holds b3; a's foreign copy does not corrupt it"


async def test_a_referrer_by_had_member_that_is_no_collection_is_not_a_holder(
    toy_session, collaboration
):
    await put_book(toy_session, B1)
    stray = [
        (URIRef(B2), RDF.type, URIRef("http://purl.org/ontology/bibo/Book")),
        (URIRef(B2), v.HAD_MEMBER, URIRef(B1)),
    ]
    await toy_session.add_graph(B2, stray)
    found = await as_ada(collaboration, toy_session).collections_of(B1)
    assert found.member_iris is None, "a book that names b1 as a member is no collection"
    assert found.hidden_count == 0, "and is not counted"


async def test_a_member_that_is_no_longer_a_collection_is_a_leaf_of_a_deep_read(
    guarded, collaboration
):
    await put(guarded, a_shelf(B, member_class="Book"))
    await put(guarded, a_shelf(A, member_class="Shelf", had_member=[B]))
    stored_b = (await guarded.get_graph(B))[2]
    await guarded.remove(B, stored_b)
    await put_book(guarded, B)  # the IRI of a shelf now holds a book
    found = await as_ada(collaboration, guarded).members(A, deep=True)
    assert found.member_iris == [B], "the shelf it names; what is stored there is no collection"

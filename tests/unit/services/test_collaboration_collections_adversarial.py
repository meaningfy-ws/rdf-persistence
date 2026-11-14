"""Adversarial tests of stage 2, reference collections (rp-reference-collections, PD-5 to PD-8, PD-15, PD-25).

The cascade delete first (a new invariant on the write path, all or nothing under concurrent writers),
then the write guard, the reads, and ``Session.heads`` / ``matches`` / ``_require_match``. Each test
names the spec line, design item or decision it holds the code to. B1 to B9 are books of the toy
tenant, S1 and A, B its shelves; ``ada`` is a librarian, ``bob`` a reader. "Another writer" is a second
session on the same fake store, made to act at a stated moment (``before``).
"""

from contextlib import asynccontextmanager, suppress
from uuid import UUID

import pytest
from pydantic import ValidationError
from rdflib import RDF, BNode, Literal, URIRef

from rdf_persistence import Action, StoredDataInvalid, generated_models
from rdf_persistence.domain.exceptions import (
    BadQuery,
    CommitTooLarge,
    Conflict,
    Forbidden,
    InvalidBody,
    InvalidIri,
    NotFound,
    PersistenceError,
    SparqlError,
    StoreUnavailable,
)
from rdf_persistence.domain.generated.rp_collections import MembershipRule, SlotEquality
from rdf_persistence.domain.generated.service.rp_service import Filter, ListRequest, MemberList
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.domain.sparql import term
from rdf_persistence.services import collaboration as collaboration_module
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import DEFAULT_MAX_ROOTS, UnitOfWork
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.write_guards import WriteGuards
from rdf_persistence.testkit import FakeStore, fake_session
from tests.fixtures.library.generated.books import Genre, Shelf
from tests.toy import (
    ADA,
    BOB,
    MODULES,
    TENANT,
    TOY_SCHEMA,
    access,
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
from tests.unit.services.test_collaboration_cascade import (
    HEADS,
    a_shelf,
    before,
    gone,
    poetry,
    put,
    put_book,
    regenre,
    stored,
    version,
)

B1, B2, B3, B4, B5, B6, B9 = (book_iri(n) for n in (1, 2, 3, 4, 5, 6, 9))
S1, S2, A, B, C = (
    shelf_iri(n) for n in (51, 52, 53, 54, 55)
)  # no UUID of a book is one of a shelf
OTHER_TENANT = "https://example.org/libraries/00000000"
MARKER_LEFT = "ASK { GRAPH $registry { ?m a $marker } }"
LIB = "https://example.org/ns/library#"
SCAN_CLASS = URIRef(f"{LIB}Scan")
BOOK_CLASS = URIRef("http://purl.org/ontology/bibo/Book")
SHELF_CLASS = URIRef(f"{LIB}Shelf")
EVIL = 'x" } . ?s ?p ?o } ; DROP ALL ; # \n\r\t\\ \u0000 <a> {'


def uuid_of(iri: str) -> str:
    return iri.rsplit("/", 1)[1]


def everything_said(error: BaseException) -> str:
    """Every text an error carries: its message, repr, arguments and the ``iris`` of a conflict."""
    return " ".join([str(error), repr(error), *map(str, error.args), *getattr(error, "iris", ())])


# -- sessions and writers -----------------------------------------------------------------------


def guards() -> WriteGuards:
    return WriteGuards(toy_mapper(), generated_models(*MODULES), Listings(load_schema(TOY_SCHEMA)))


@pytest.fixture
async def guarded():
    """A session whose writes check collections, the way the kit's sessions do."""
    listings = Listings(load_schema(TOY_SCHEMA))
    async with fake_session(tenant_iri=TENANT, listings=listings, guards=guards()) as session:
        yield session


@asynccontextmanager
async def second_writer(store: FakeStore):
    """Another guarded session on the same store."""
    listings = Listings(load_schema(TOY_SCHEMA))
    async with fake_session(store, tenant_iri=TENANT, listings=listings, guards=guards()) as other:
        yield other


def as_ada(collaboration, session):
    return collaboration(caller(principal=ADA), held(role("librarian")), session)


def as_bob(collaboration, session, *hidden: str):
    bans = [ban(Action.READ, graph_of(h), BOB) for h in hidden]
    return collaboration(caller(principal=BOB), held(role("reader", who=BOB), bans=bans), session)


async def cascade_of(collaboration, store: FakeStore, iri: str, ver: str) -> None:
    """Another writer runs a whole cascade of ``iri`` as ada."""
    async with second_writer(store) as other:
        await as_ada(collaboration, other).delete_cascade(iri, ver)


async def shelve(session, *books: str, rule: MembershipRule | None = None, shelf: str = S1) -> str:
    """Store a poetry book for each of ``books`` and a shelf naming them (and with ``rule``); its version."""
    for iri in books:
        await put_book(session, iri, Genre.POETRY)
    await put(session, a_shelf(shelf, had_member=list(books) or None, membership_rule=rule))
    return await version(session, shelf)


async def heads_of(session, iris) -> dict[str, str]:
    return {str(h.head_iri): str(h.head_version) for h in await session.heads(list(iris))}


async def marker_left(session) -> bool:
    return await session._ask(
        MARKER_LEFT, registry=term(DEFAULT_IRIS.registry(TENANT)), marker=term(v.COMMIT_MARKER)
    )


def drifted(old: dict[str, str], now: dict[str, str], *changed: str) -> list[str]:
    """The IRIs of ``old`` not stored at their old version now, apart from those another writer ``changed``."""
    return [i for i, ver in old.items() if i not in changed and now.get(i) != ver]


# -- 1. the cascade is all or nothing -----------------------------------------------------------


async def test_a_forbidden_cascade_leaves_everything_and_no_marker(guarded, collaboration):
    ver = await shelve(guarded, B1, B2)
    old = await heads_of(guarded, [S1, B1, B2])
    access_ = held(role("reader"), direct(Action.DELETE, graph_of(S1)))
    with pytest.raises(Forbidden):
        await collaboration(caller(), access_, guarded).delete_cascade(S1, ver)
    assert drifted(old, await heads_of(guarded, old)) == [], "the shelf and the books are as before"
    assert not await marker_left(guarded), "no commit marker"


async def test_a_conflicting_cascade_leaves_everything_and_no_marker(guarded, collaboration):
    await shelve(guarded, B1, B2)
    old = await heads_of(guarded, [S1, B1, B2])
    with pytest.raises(Conflict) as refused:
        await as_ada(collaboration, guarded).delete_cascade(S1, "stale")
    assert refused.value.iris == (S1,), "the collection is the one named"
    assert drifted(old, await heads_of(guarded, old)) == [], "all stored at their old version"
    assert not await marker_left(guarded), "no commit marker"


async def test_a_cascade_too_large_leaves_everything_and_no_marker(toy_session, collaboration):
    members = [book_iri(n) for n in range(1, DEFAULT_MAX_ROOTS + 1)]
    await put(toy_session, a_shelf(S1, had_member=members))
    old = await heads_of(toy_session, [S1])
    with pytest.raises(CommitTooLarge):
        await as_ada(collaboration, toy_session).delete_cascade(S1, old[S1])
    assert drifted(old, await heads_of(toy_session, old)) == [], "the shelf is as before"
    assert not await marker_left(toy_session), "no commit marker"


async def test_a_store_failure_on_the_update_leaves_everything_and_no_marker(
    guarded, collaboration
):
    ver = await shelve(guarded, B1, B2)
    old = await heads_of(guarded, [S1, B1, B2])
    guarded._store.on("update", StoreUnavailable("the store went away"))
    with pytest.raises(StoreUnavailable):
        await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert drifted(old, await heads_of(guarded, old)) == [], "nothing was deleted"
    assert not await marker_left(guarded), "no commit marker"


async def test_a_store_failure_on_a_read_leaves_everything(guarded, collaboration):
    ver = await shelve(guarded, B1, B2)
    old = await heads_of(guarded, [S1, B1, B2])
    guarded._store.on("query", StoreUnavailable("down"), after=2)
    with pytest.raises(StoreUnavailable):
        await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert drifted(old, await heads_of(guarded, old)) == [], "nothing was deleted"


async def test_a_named_member_removed_before_the_heads_is_skipped(guarded, collaboration):
    ver = await shelve(guarded, B1, B2)
    before(guarded._store, "query", lambda: gone(guarded._store, B2), when=HEADS)
    await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert not await stored(guarded, S1) and not await stored(guarded, B1), "the rest is deleted"


async def test_a_named_member_replaced_before_the_heads_is_deleted_at_its_new_version(
    guarded, collaboration
):  # pinned: the version is read at the heads, so a replace before them is not a conflict
    ver = await shelve(guarded, B1, B2)
    before(guarded._store, "query", lambda: regenre(guarded._store, B2, Genre.FICTION), when=HEADS)
    await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert not await stored(guarded, S1) and not await stored(guarded, B2), "it went with the shelf"


async def test_a_named_member_removed_and_added_again_before_the_heads_is_deleted(
    guarded, collaboration
):  # pinned, as the replace before the heads
    ver = await shelve(guarded, B1, B2)

    async def again():
        await gone(guarded._store, B2)
        async with second_writer(guarded._store) as other:
            await put_book(other, B2, Genre.FICTION)

    before(guarded._store, "query", again, when=HEADS)
    await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert not await stored(guarded, B2), "the new B2 is deleted with the shelf"


async def test_a_named_member_removed_after_the_heads_is_a_conflict_not_a_skip(
    guarded, collaboration
):  # TC-36, Error matrix: a member changed since resolved; its removal is a change
    ver = await shelve(guarded, B1, B2)
    old = await heads_of(guarded, [S1, B1])
    before(guarded._store, "update", lambda: gone(guarded._store, B2))
    with pytest.raises(Conflict) as refused:
        await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert refused.value.iris == (B2,), "the removed member is named"
    assert drifted(old, await heads_of(guarded, old)) == [], "the shelf and b1 stay"


async def test_a_named_member_removed_and_added_again_after_the_heads_is_a_conflict(
    guarded, collaboration
):
    ver = await shelve(guarded, B1, B2)
    old = await heads_of(guarded, [S1, B1])

    async def again():
        await gone(guarded._store, B2)
        async with second_writer(guarded._store) as other:
            await put_book(other, B2, Genre.POETRY)

    before(guarded._store, "update", again)
    with pytest.raises(Conflict) as refused:
        await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert refused.value.iris == (B2,), "its version is not the one that was read"
    assert drifted(old, await heads_of(guarded, old)) == [], "nothing else was deleted"
    assert await stored(guarded, B2), "the new B2 is not deleted"


@pytest.mark.parametrize(
    "members",
    [[B1], [B1, B2, B3], [B2]],
    ids=["a-member-added", "a-member-dropped", "all-replaced"],
)
async def test_the_collection_replaced_after_it_was_read_is_a_conflict(
    guarded, collaboration, members
):  # PD-8 step 5: the collection is removed at the caller's version
    ver = await shelve(guarded, B1, B2)
    await put_book(guarded, B3, Genre.POETRY)
    old = await heads_of(guarded, [B1, B2, B3])

    async def replaced():
        async with second_writer(guarded._store) as other:
            replacement = toy_mapper().to_triples(a_shelf(S1, had_member=members))
            await other.replace_graph(S1, replacement, await version(other, S1))

    before(guarded._store, "update", replaced)
    with pytest.raises(Conflict) as refused:
        await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert refused.value.iris == (S1,), "the collection is named"
    assert drifted(old, await heads_of(guarded, old)) == [], "no member was deleted"
    assert await stored(guarded, S1), "and the new collection is stored"


async def test_a_rule_member_regenred_back_and_forth_is_a_conflict_though_it_still_matches(
    guarded, collaboration
):  # Error matrix: a member changed since resolved
    ver = await shelve(guarded, B3, rule=poetry())

    async def back_and_forth():
        await regenre(guarded._store, B3, Genre.FICTION)
        await regenre(guarded._store, B3, Genre.POETRY)

    before(guarded._store, "update", back_and_forth)
    with pytest.raises(Conflict) as refused:
        await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert refused.value.iris == (B3,), "its version changed"
    assert await stored(guarded, S1) and await stored(guarded, B3), "nothing is deleted"


async def test_a_rule_member_regenred_back_and_forth_before_the_heads_is_deleted(
    guarded, collaboration
):  # pinned: the heads read the latest version and the member still matches
    ver = await shelve(guarded, B3, rule=poetry())

    async def back_and_forth():
        await regenre(guarded._store, B3, Genre.FICTION)
        await regenre(guarded._store, B3, Genre.POETRY)

    before(guarded._store, "query", back_and_forth, when=HEADS)
    await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert not await stored(guarded, B3), "it matched at the heads and at the send"


async def test_a_rule_member_removed_after_its_remove_was_collected_is_a_conflict(
    guarded, collaboration
):
    ver = await shelve(guarded, B3, rule=poetry())
    before(guarded._store, "update", lambda: gone(guarded._store, B3))
    with pytest.raises(Conflict) as refused:
        await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert refused.value.iris == (B3,), "the removed member is named"
    assert await stored(guarded, S1), "the shelf stays"


async def test_a_rule_member_removed_before_the_heads_is_skipped(guarded, collaboration):
    ver = await shelve(guarded, B3, B5, rule=poetry())
    before(guarded._store, "query", lambda: gone(guarded._store, B5), when=HEADS)
    await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert not await stored(guarded, S1) and not await stored(guarded, B3), "the rest is deleted"


async def test_a_new_rule_match_during_the_cascade_is_not_deleted(guarded, collaboration):
    ver = await shelve(guarded, B3, rule=poetry())

    async def another_poetry_book():
        async with second_writer(guarded._store) as other:
            await put_book(other, B6, Genre.POETRY)

    before(guarded._store, "update", another_poetry_book)
    await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert not await stored(guarded, S1) and not await stored(guarded, B3), "resolved ones go"
    assert await stored(guarded, B6), "the new match survives (Error matrix: resolved at the call)"


async def test_two_cascades_of_one_collection_both_succeed_and_leave_everything_gone_and_no_marker(
    guarded, collaboration
):  # PD-27: a removes-only commit whose roots another writer removed is a success (atomic-commit PD-17e)
    ver = await shelve(guarded, B1, B2)
    before(guarded._store, "update", lambda: cascade_of(collaboration, guarded._store, S1, ver))
    await as_ada(collaboration, guarded).delete_cascade(S1, ver)  # the loser reports no error
    assert not any([await stored(guarded, i) for i in (S1, B1, B2)]), "the winner deleted all"
    assert not await marker_left(guarded), "no commit marker"


async def test_a_cascade_racing_a_plain_delete_of_the_collection_is_a_conflict(
    guarded, collaboration
):
    ver = await shelve(guarded, B1, B2)
    before(guarded._store, "update", lambda: gone(guarded._store, S1))
    with pytest.raises(Conflict) as refused:
        await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert refused.value.iris == (S1,), "the collection went"
    assert await stored(guarded, B1) and await stored(guarded, B2), "the members stay"


async def test_a_cascade_whose_every_member_is_already_gone_deletes_the_collection(
    guarded, collaboration
):
    ver = await shelve(guarded, B1, B2)
    await gone(guarded._store, B1)
    await gone(guarded._store, B2)
    await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert not await stored(guarded, S1), "the collection is deleted"


async def test_a_cascade_whose_every_member_goes_between_the_read_and_the_heads(
    guarded, collaboration
):
    ver = await shelve(guarded, B1, B2)

    async def all_gone():
        await gone(guarded._store, B1)
        await gone(guarded._store, B2)

    before(guarded._store, "query", all_gone, when=HEADS)
    await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert not await stored(guarded, S1), "the collection is deleted"


# -- 2. the cascade: who may --------------------------------------------------------------------


def leaks(error: BaseException, *iris: str) -> list[str]:
    """The IRIs and UUIDs of ``iris`` found anywhere in what ``error`` carries."""
    text = everything_said(error)
    return [i for i in iris if i in text or uuid_of(i) in text]


async def test_a_caller_who_may_delete_the_collection_and_no_member_is_told_the_readable_ones(
    guarded, collaboration
):
    ver = await shelve(guarded, B1, B2)
    access_ = held(role("reader"), direct(Action.DELETE, graph_of(S1)))
    with pytest.raises(Forbidden) as refused:
        await collaboration(caller(), access_, guarded).delete_cascade(S1, ver)
    assert B1 in str(refused.value) and B2 in str(refused.value), (
        "both are named: they are readable"
    )
    assert await stored(guarded, S1), "nothing is deleted"


async def test_members_the_caller_may_not_read_are_counted_and_never_named_anywhere(
    guarded, collaboration
):
    ver = await shelve(guarded, B1, B2, B3)
    access_ = held(
        role("reader"),
        direct(Action.DELETE, graph_of(S1)),
        bans=[ban(Action.READ, graph_of(B1)), ban(Action.READ, graph_of(B3))],
    )
    with pytest.raises(Forbidden) as refused:
        await collaboration(caller(), access_, guarded).delete_cascade(S1, ver)
    assert leaks(refused.value, B1, B3) == [], "no IRI or UUID of a hidden member, in any text"
    assert "2 not readable" in str(refused.value), "they are counted"
    assert B2 in str(refused.value), "the readable refused one is named"


async def test_a_caller_with_no_right_on_any_member_and_no_read_names_nothing(
    guarded, collaboration
):
    ver = await shelve(guarded, B1, B2)
    access_ = held(
        role("reader"),
        direct(Action.DELETE, graph_of(S1)),
        bans=[ban(Action.READ, graph_of(B1)), ban(Action.READ, graph_of(B2))],
    )
    with pytest.raises(Forbidden) as refused:
        await collaboration(caller(), access_, guarded).delete_cascade(S1, ver)
    assert leaks(refused.value, B1, B2) == [], "nothing of the members"
    assert "2 not readable" in str(refused.value), "only the count"


async def test_a_caller_with_delete_on_every_member_only_through_direct_grants_cascades(
    guarded, collaboration
):
    ver = await shelve(guarded, B1, B2)
    grants = [direct(Action.DELETE, graph_of(i)) for i in (S1, B1, B2)]
    await collaboration(caller(), held(role("reader"), *grants), guarded).delete_cascade(S1, ver)
    assert not any([await stored(guarded, i) for i in (S1, B1, B2)]), "all deleted"


async def test_a_direct_delete_grant_on_the_members_only_does_not_allow_the_collection(
    guarded, collaboration
):
    ver = await shelve(guarded, B1)
    access_ = held(role("reader"), direct(Action.DELETE, graph_of(B1)))
    with pytest.raises(Forbidden) as refused:
        await collaboration(caller(), access_, guarded).delete_cascade(S1, ver)
    assert leaks(refused.value, B1) == [], "the refusal is about the collection and names no member"
    assert await stored(guarded, B1), "nothing is deleted"


async def test_a_tenant_level_prohibition_of_delete_refuses_the_cascade(guarded, collaboration):
    ver = await shelve(guarded, B1, B2)
    access_ = held(role("librarian"), bans=[ban(Action.DELETE, TENANT)])
    with pytest.raises(Forbidden) as refused:
        await collaboration(caller(), access_, guarded).delete_cascade(S1, ver)
    assert leaks(refused.value, B1, B2) == [], "no member is named"
    assert all([await stored(guarded, i) for i in (S1, B1, B2)]), "nothing is deleted"


async def test_a_prohibition_of_delete_on_one_member_refuses_the_cascade_even_for_a_librarian(
    guarded, collaboration
):
    ver = await shelve(guarded, B1, B2)
    access_ = held(role("librarian"), bans=[ban(Action.DELETE, graph_of(B2))])
    with pytest.raises(Forbidden) as refused:
        await collaboration(caller(), access_, guarded).delete_cascade(S1, ver)
    assert B2 in str(refused.value), "b2 is readable and refused: named"
    assert await stored(guarded, B1) and await stored(guarded, S1), "nothing is deleted"


async def test_a_caller_who_sees_nothing_of_the_collection_is_told_it_is_not_found(
    guarded, collaboration
):
    ver = await shelve(guarded, B1)
    with pytest.raises(NotFound) as refused:
        await collaboration(caller(), held(), guarded).delete_cascade(S1, ver)
    assert leaks(refused.value, B1) == [], "nothing of the members"
    assert await stored(guarded, S1), "the collection is stored"


async def test_a_caller_prohibited_from_reading_the_collection_learns_nothing_of_the_members(
    guarded, collaboration
):
    ver = await shelve(guarded, B1)
    access_ = held(role("librarian"), bans=[ban(Action.READ, graph_of(S1))])
    with pytest.raises(PersistenceError) as refused:
        await collaboration(caller(), access_, guarded).delete_cascade(S1, ver)
    assert isinstance(refused.value, (Forbidden, NotFound)), "a refusal of access"
    assert leaks(refused.value, B1) == [], "nothing of the members"
    assert await stored(guarded, S1) and await stored(guarded, B1), "nothing is deleted"


# -- 3. the cascade: odd shapes -----------------------------------------------------------------


async def test_a_collection_that_names_the_tenant_root_does_not_delete_it(
    toy_session, collaboration
):  # no guard: a stored collection is not trusted to hold only aggregates of its member class
    await put(toy_session, library())
    await put(toy_session, a_shelf(S1, had_member=[TENANT]))
    with suppress(PersistenceError):  # a refusal or a skip are both fine
        await as_ada(collaboration, toy_session).delete_cascade(S1, await version(toy_session, S1))
    assert await toy_session.get_graph(TENANT), "the tenant root is stored"


async def test_a_collection_that_names_the_access_record_does_not_delete_it(
    toy_session, collaboration
):  # the record is registered as an aggregate, and a librarian may delete it
    record = access()
    await put(toy_session, record)
    await put(toy_session, a_shelf(S1, had_member=[record.id]))
    ver = await version(toy_session, S1)
    with pytest.raises(StoredDataInvalid, match=S1) as refused:  # PD-27 item 1
        await as_ada(collaboration, toy_session).delete_cascade(S1, ver)
    assert record.id not in everything_said(refused.value), "the member is not named"
    assert await stored(toy_session, record.id), "the tenant's access record is stored"
    assert await stored(toy_session, S1), "the shelf is kept: nothing is deleted"


@pytest.mark.parametrize(
    "member",
    [
        pytest.param(graph_of(B1), id="a-graph-iri"),
        pytest.param(book_iri(7).replace(TENANT, OTHER_TENANT), id="another-tenant"),
        pytest.param("https://example.org/.well-known/genid/abc", id="a-skolem-iri"),
        pytest.param(f"{B1}/parts/{UUID(int=5)}", id="a-part-iri"),
    ],
)
async def test_a_member_that_is_no_aggregate_of_the_tenant_refuses_without_deleting(
    toy_session, collaboration, member
):  # written without guards
    await put_book(toy_session, B1)
    await put(toy_session, a_shelf(S1, had_member=[B1, member]))
    old = await heads_of(toy_session, [S1, B1])
    with pytest.raises(PersistenceError):
        await as_ada(collaboration, toy_session).delete_cascade(S1, old[S1])
    assert drifted(old, await heads_of(toy_session, old)) == [], "the shelf and b1 are kept"
    assert not await marker_left(toy_session), "no commit marker"


async def test_a_member_listed_twice_is_deleted_once(toy_session, collaboration):
    await put_book(toy_session, B1)
    await put(toy_session, a_shelf(S1, had_member=[B1, B1]))
    await as_ada(collaboration, toy_session).delete_cascade(S1, await version(toy_session, S1))
    assert not await stored(toy_session, S1) and not await stored(toy_session, B1), "both gone"


async def test_a_member_that_is_both_named_and_matched_is_deleted_and_not_guarded_twice(
    guarded, collaboration
):
    ver = await shelve(guarded, B3, rule=poetry())
    await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert not await stored(guarded, B3), "deleted once"


async def test_a_member_both_named_and_matched_that_is_regenred_after_the_heads_is_a_conflict(
    guarded, collaboration
):
    ver = await shelve(guarded, B3, rule=poetry())
    before(guarded._store, "update", lambda: regenre(guarded._store, B3, Genre.FICTION))
    with pytest.raises(Conflict) as refused:
        await as_ada(collaboration, guarded).delete_cascade(S1, ver)
    assert refused.value.iris == (B3,), "its version changed"


async def test_a_member_of_another_class_named_by_an_unguarded_collection_is_refused_and_stays(
    toy_session, collaboration
):  # PD-27 item 1: a Scan under a shelf of books
    scan_iri = f"{TENANT}/scans/{UUID(int=1)}"
    await toy_session.add_graph(scan_iri, [(URIRef(scan_iri), RDF.type, SCAN_CLASS)])
    await put(toy_session, a_shelf(S1, had_member=[scan_iri]))
    ver = await version(toy_session, S1)
    with pytest.raises(StoredDataInvalid, match=S1) as refused:
        await as_ada(collaboration, toy_session).delete_cascade(S1, ver)
    assert scan_iri not in everything_said(refused.value), "the member is not named"
    assert await stored(toy_session, scan_iri), "a Scan is not a member of a shelf of books"
    assert await stored(toy_session, S1), "the shelf is kept: nothing is deleted"


async def test_a_collection_listing_itself_among_collections_is_deleted_once_with_its_peer(
    toy_session, collaboration
):
    await put(toy_session, a_shelf(A, member_class="Shelf", had_member=[S1]))
    await put(toy_session, a_shelf(S1, member_class="Shelf", had_member=[S1, A]))
    await as_ada(collaboration, toy_session).delete_cascade(S1, await version(toy_session, S1))
    assert not await stored(toy_session, S1) and not await stored(toy_session, A), "both gone"


async def test_a_nested_collection_that_lists_the_outer_does_not_loop_or_delete_more(
    guarded, collaboration
):
    await put_book(guarded, B1)
    await put(guarded, a_shelf(A, member_class="Book", had_member=[B1]))
    await put(guarded, a_shelf(S1, member_class="Shelf", had_member=[A]))
    stored_a = await guarded.get_graph(A)
    reverse = toy_mapper().to_triples(a_shelf(A, member_class="Shelf", had_member=[S1]))
    await guarded.replace_graph(A, reverse, stored_a[2])
    await as_ada(collaboration, guarded).delete_cascade(S1, await version(guarded, S1))
    assert not await stored(guarded, S1) and not await stored(guarded, A), "both shelves go"
    assert await stored(guarded, B1), "the book that a replaced shelf no longer names stays"


async def books_through_one_transaction(session, count: int) -> list[str]:
    """``count`` stored books (all fiction), in one request; ``Transaction`` itself has no root limit."""
    iris = [book_iri(n) for n in range(1, count + 1)]
    async with session.transaction() as transaction:
        for iri in iris:
            await transaction.add_graph(iri, toy_mapper().to_triples(dune(iri, chapters=0)))
    return iris


LIMIT = 6  # the limit the three tests below lower the cascade's to: the fake store is slow at 500


@pytest.fixture
def small_limit(monkeypatch):
    """The cascade counts against ``services.collaboration.DEFAULT_MAX_ROOTS``; the fake store takes minutes at 500."""
    monkeypatch.setattr(collaboration_module, "DEFAULT_MAX_ROOTS", LIMIT)


async def test_rule_members_that_make_the_collection_and_members_exactly_the_limit_are_deleted(
    toy_session, collaboration, small_limit
):
    iris = await books_through_one_transaction(toy_session, LIMIT - 1)
    await put(toy_session, a_shelf(S1, membership_rule=MembershipRule()))
    await as_ada(collaboration, toy_session).delete_cascade(S1, await version(toy_session, S1))
    assert not await stored(toy_session, S1), "the shelf is gone"
    assert await heads_of(toy_session, iris) == {}, "and the books with it"


async def test_rule_members_one_over_the_limit_are_refused_and_nothing_is_deleted(
    toy_session, collaboration, small_limit
):
    iris = await books_through_one_transaction(toy_session, LIMIT)
    await put(toy_session, a_shelf(S1, membership_rule=MembershipRule()))
    with pytest.raises(CommitTooLarge, match=str(LIMIT)):
        await as_ada(collaboration, toy_session).delete_cascade(S1, await version(toy_session, S1))
    assert await stored(toy_session, S1), "the shelf is stored"
    assert len(await heads_of(toy_session, iris)) == LIMIT, "every book is stored"
    assert not await marker_left(toy_session), "no commit marker"


async def test_named_and_rule_members_count_once_each_against_the_limit(
    toy_session, collaboration, small_limit
):
    iris = await books_through_one_transaction(toy_session, LIMIT - 1)
    await put(toy_session, a_shelf(S1, had_member=iris[:3], membership_rule=MembershipRule()))
    await as_ada(collaboration, toy_session).delete_cascade(S1, await version(toy_session, S1))
    assert not await stored(toy_session, S1), "the same books named and matched count once"


async def test_a_rule_member_that_is_the_collection_itself_is_not_counted_twice(
    toy_session, collaboration, small_limit
):  # a shelf of shelves whose rule matches every shelf, itself included
    await put(toy_session, a_shelf(A, member_class="Shelf"))
    await put(toy_session, a_shelf(B, member_class="Shelf"))
    await put(toy_session, a_shelf(S1, member_class="Shelf", membership_rule=MembershipRule()))
    await as_ada(collaboration, toy_session).delete_cascade(S1, await version(toy_session, S1))
    assert not any([await stored(toy_session, i) for i in (S1, A, B)]), "all three are gone"


async def test_a_cascade_of_something_that_is_not_a_collection_is_bad_query(guarded, collaboration):
    await put_book(guarded, B1)
    with pytest.raises(BadQuery):
        await as_ada(collaboration, guarded).delete_cascade(B1, await version(guarded, B1))
    assert await stored(guarded, B1), "the book is stored"


async def test_a_cascade_of_a_missing_collection_is_not_found(guarded, collaboration):
    with pytest.raises(NotFound):
        await as_ada(collaboration, guarded).delete_cascade(S2, "anything")


@pytest.mark.parametrize(
    "collection",
    [
        pytest.param(shelf_iri(7).replace(TENANT, OTHER_TENANT), id="another-tenant"),
        pytest.param("not an iri", id="malformed"),
        pytest.param("", id="empty"),
        pytest.param(S1 + "> } ; DROP ALL ; <", id="sparql-in-the-iri"),
        pytest.param(TENANT, id="the-tenant-root"),
    ],
)
async def test_a_collection_iri_that_is_not_one_of_the_tenant_deletes_nothing(
    guarded, collaboration, collection
):
    ver = await shelve(guarded, B1)
    with pytest.raises(PersistenceError):
        await as_ada(collaboration, guarded).delete_cascade(collection, ver)
    assert await stored(guarded, S1) and await stored(guarded, B1), "nothing is deleted"


@pytest.mark.parametrize(
    "if_version",
    [
        pytest.param("", id="empty"),
        pytest.param("x" * 100_000, id="absurdly-long"),
        pytest.param(EVIL, id="sparql-metacharacters"),
        pytest.param("\u0000", id="nul"),
    ],
)
async def test_an_if_version_that_is_not_the_version_is_a_conflict_and_deletes_nothing(
    guarded, collaboration, if_version
):
    await shelve(guarded, B1)
    with pytest.raises(Conflict):
        await as_ada(collaboration, guarded).delete_cascade(S1, if_version)
    assert await stored(guarded, S1) and await stored(guarded, B1), "nothing is deleted"
    assert await stored(guarded, B1), "and no injected statement ran"


# -- 4. the write guard -------------------------------------------------------------------------


def bad_shelf(iri: str = S1, **slots) -> Shelf:
    """A shelf of books that names a shelf, which a guard refuses."""
    return a_shelf(iri, had_member=[S2], **slots)


async def other_shelf(session) -> None:
    await put(session, a_shelf(S2))


async def through_transaction_add(session, model) -> None:
    async with session.transaction() as transaction:
        await transaction.add_graph(model.id, toy_mapper().to_triples(model))


async def through_unit_of_work_add(session, model) -> None:
    work = UnitOfWork(session, toy_mapper())
    work.add(model)
    await work.commit()


async def through_session_add(session, model) -> None:
    await session.add_graph(model.id, toy_mapper().to_triples(model))


@pytest.mark.parametrize(
    "write",
    [through_session_add, through_transaction_add, through_unit_of_work_add],
    ids=["session-add", "transaction-add", "unit-of-work-add"],
)
async def test_every_write_path_refuses_a_collection_of_the_wrong_class(guarded, write):
    await other_shelf(guarded)
    with pytest.raises(InvalidBody, match=S2):
        await write(guarded, bad_shelf())
    assert not await stored(guarded, S1), "nothing is stored"
    assert not await marker_left(guarded), "no commit marker"


async def replace_by_session(session, model, ver) -> None:
    await session.replace_graph(model.id, toy_mapper().to_triples(model), ver)


async def replace_by_transaction(session, model, ver) -> None:
    async with session.transaction() as transaction:
        await transaction.replace_graph(model.id, toy_mapper().to_triples(model), ver)


async def replace_by_unit_of_work(session, model, ver) -> None:
    work = UnitOfWork(session, toy_mapper())
    await work.get(Shelf, model.id)
    work.add(model)
    await work.commit()


@pytest.mark.parametrize(
    "replace",
    [replace_by_session, replace_by_transaction, replace_by_unit_of_work],
    ids=["session-replace", "transaction-replace", "unit-of-work-replace"],
)
async def test_every_write_path_refuses_a_replace_that_turns_a_valid_collection_invalid(
    guarded, replace
):
    await put_book(guarded, B1)
    await other_shelf(guarded)
    await put(guarded, a_shelf(S1, had_member=[B1]))
    ver = await version(guarded, S1)
    with pytest.raises(InvalidBody, match=S2):
        await replace(guarded, bad_shelf(), ver)
    assert await version(guarded, S1) == ver, "the stored collection is as it was"


async def test_a_replace_that_drops_the_member_class_into_a_part_class_is_refused(guarded):
    await put(guarded, a_shelf(S1))
    ver = await version(guarded, S1)
    with pytest.raises(InvalidBody, match="Chapter"):
        await replace_by_session(guarded, a_shelf(S1, member_class="Chapter"), ver)
    assert await version(guarded, S1) == ver, "the stored collection is as it was"


@pytest.mark.parametrize(
    "member_class",
    ["ReferenceCollection", "Described", "AggregateRoot", "Chapter", "Note", "Tracked", "NoSuch"],
)
async def test_a_member_class_that_is_not_a_served_root_is_refused(guarded, member_class):
    with pytest.raises(InvalidBody, match=member_class):
        await through_session_add(guarded, a_shelf(S1, member_class=member_class))
    assert not await stored(guarded, S1), "nothing is stored"


async def test_a_collection_of_its_own_class_is_saved_with_collections_in_it(guarded):
    await other_shelf(guarded)
    await through_session_add(guarded, a_shelf(S1, member_class="Shelf", had_member=[S2]))
    assert await stored(guarded, S1), "a shelf of shelves"


async def test_a_collection_that_names_itself_is_refused_until_it_is_stored(guarded):  # D-6
    with pytest.raises(InvalidBody, match=S1):
        await through_session_add(guarded, a_shelf(S1, member_class="Shelf", had_member=[S1]))
    assert not await stored(guarded, S1), "nothing is stored"


async def test_a_collection_that_names_itself_on_replace_is_saved(guarded):
    await put(guarded, a_shelf(S1, member_class="Shelf"))
    await replace_by_session(
        guarded, a_shelf(S1, member_class="Shelf", had_member=[S1]), await version(guarded, S1)
    )
    assert await stored(guarded, S1), "it is stored, and now names itself"


async def test_a_root_typed_with_a_collection_class_and_another_is_guarded_as_a_collection(guarded):
    await other_shelf(guarded)
    triples = [*toy_mapper().to_triples(bad_shelf()), (URIRef(S1), RDF.type, BOOK_CLASS)]
    with pytest.raises(InvalidBody, match=S2):
        await guarded.add_graph(S1, triples)
    assert not await stored(guarded, S1), "nothing is stored"


async def test_a_root_typed_with_the_other_class_first_is_guarded_all_the_same(guarded):
    await other_shelf(guarded)
    triples = [(URIRef(S1), RDF.type, BOOK_CLASS), *toy_mapper().to_triples(bad_shelf())]
    with pytest.raises(InvalidBody, match=S2):
        await guarded.add_graph(S1, triples)
    assert not await stored(guarded, S1), "nothing is stored"


def shelf_triples(**slots):
    return toy_mapper().to_triples(a_shelf(S1, **slots))


def without(triples, predicate: str):
    return [t for t in triples if str(t[1]) != predicate]


MEMBER_CLASS_P = "https://meaningfy.ws/ns/rdf-persistence#memberClass"
HAD_MEMBER_P = "http://www.w3.org/ns/prov#hadMember"
RULE_P = str(v.MEMBERSHIP_RULE)


def undecodable():
    base = shelf_triples()
    return [
        pytest.param(without(base, MEMBER_CLASS_P), id="no-member-class"),
    ]


@pytest.mark.parametrize("triples", undecodable())
async def test_a_collection_whose_triples_do_not_decode_is_refused_with_a_toolkit_error(
    guarded, triples
):
    with pytest.raises(InvalidBody) as refused:  # PD-27 item 2
        await guarded.add_graph(S1, triples)
    assert not isinstance(refused.value, ValidationError), "not a bare pydantic error"
    assert not await stored(guarded, S1), "nothing is stored"


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param((URIRef(RULE_P), Literal("a rule")), id="rule-literal"),
        pytest.param((URIRef(MEMBER_CLASS_P), Literal("Chapter")), id="two-member-classes"),
    ],
)
async def test_raw_triples_the_mapper_never_writes_are_stored_by_the_guard(guarded, extra):
    """PD-27, rejected: the guard checks the decoded model, and the generic API checks the shape first."""
    await guarded.add_graph(S1, [*shelf_triples(), (URIRef(S1), *extra)])
    assert await stored(guarded, S1), "a literal rule or a second member class is stored as given"


async def test_members_given_as_literals_are_refused_and_nothing_is_stored(guarded):
    triples = [*shelf_triples(), (URIRef(S1), URIRef(HAD_MEMBER_P), Literal("just text"))]
    with pytest.raises(PersistenceError):
        await guarded.add_graph(S1, triples)
    assert not await stored(guarded, S1), "nothing is stored"


async def test_a_member_that_is_a_blank_node_is_refused_and_nothing_is_stored(guarded):
    triples = [*shelf_triples(), (URIRef(S1), URIRef(HAD_MEMBER_P), BNode("b"))]
    with pytest.raises(PersistenceError):
        await guarded.add_graph(S1, triples)
    assert not await stored(guarded, S1), "nothing is stored"


async def test_a_member_of_another_tenant_is_an_invalid_iri(guarded):
    other = book_iri(1).replace(TENANT, OTHER_TENANT)
    with pytest.raises(InvalidIri, match=OTHER_TENANT):
        await through_session_add(guarded, a_shelf(S1, had_member=[other]))
    assert not await stored(guarded, S1), "nothing is stored"


async def test_a_member_of_this_tenant_that_exists_only_in_another_database_is_not_stored(guarded):
    async with fake_session(FakeStore(), tenant_iri=TENANT) as elsewhere:
        await put_book(elsewhere, B1)
    with pytest.raises(InvalidBody, match=B1):
        await through_session_add(guarded, a_shelf(S1, had_member=[B1]))
    assert not await stored(guarded, S1), "the guard asks this tenant's database only"


@pytest.mark.slow
async def test_hundreds_of_members_cost_one_heads_query(guarded):
    iris = await books_through_one_transaction(guarded, 300)
    queries = len(guarded._store.sent("query"))
    await through_session_add(guarded, a_shelf(S1, had_member=iris))
    heads_queries = [q for q in guarded._store.sent("query")[queries:] if HEADS in q]
    assert len(heads_queries) == 1, "one heads query for the 300 members"


async def test_a_refused_collection_in_a_transaction_with_valid_changes_writes_nothing(guarded):
    await other_shelf(guarded)
    sent = len(guarded._store.sent("update"))
    with pytest.raises(InvalidBody, match=S2):
        async with guarded.transaction() as transaction:
            await transaction.add_graph(B1, toy_mapper().to_triples(dune(B1, chapters=0)))
            await transaction.add_graph(S1, toy_mapper().to_triples(bad_shelf()))
    assert not await stored(guarded, B1), "the valid book of the transaction is not stored"
    assert len(guarded._store.sent("update")) == sent, "no request was sent"


async def test_a_refused_collection_first_in_a_transaction_writes_nothing(guarded):
    await other_shelf(guarded)
    with pytest.raises(InvalidBody, match=S2):
        async with guarded.transaction() as transaction:
            await transaction.add_graph(S1, toy_mapper().to_triples(bad_shelf()))
            await transaction.add_graph(B1, toy_mapper().to_triples(dune(B1, chapters=0)))
    assert not await stored(guarded, B1), "the valid book is not stored"


async def test_a_refused_collection_the_caller_catches_in_a_transaction_can_be_corrected(guarded):
    await other_shelf(guarded)
    async with guarded.transaction() as transaction:
        with pytest.raises(InvalidBody):
            await transaction.add_graph(S1, toy_mapper().to_triples(bad_shelf()))
        await transaction.add_graph(S1, toy_mapper().to_triples(a_shelf(S1)))
    assert await stored(guarded, S1), "the corrected shelf is stored"


async def test_a_guarded_session_costs_a_book_write_no_extra_query_even_in_a_transaction():
    counts = []
    for guard in (None, guards()):
        store = FakeStore()
        async with fake_session(store, tenant_iri=TENANT, guards=guard) as session:
            await books_through_one_transaction(session, 5)
        counts.append(len(store.sent("query")))
    assert counts[0] == counts[1], "no query more"


async def test_a_collection_with_no_member_and_no_rule_costs_no_heads_query(guarded):
    await through_session_add(guarded, a_shelf(S1))
    assert not [q for q in guarded._store.sent("query") if HEADS in q], "no members, no heads read"


# -- 5. the reads -------------------------------------------------------------------------------


def said_in(found: MemberList, *iris: str) -> list[str]:
    text = found.model_dump_json()
    return [i for i in iris if i in text or uuid_of(i) in text]


async def test_members_names_nothing_of_a_hidden_member_in_any_field(guarded, collaboration):
    await shelve(guarded, B1, B2)
    found = await as_bob(collaboration, guarded, B2).members(S1)
    assert said_in(found, B2) == [], "no IRI or UUID of b2"
    assert found.hidden_count == 1, "it is counted"


async def test_a_hidden_member_both_named_and_matched_is_counted_once(guarded, collaboration):
    await shelve(guarded, B2, rule=poetry())
    found = await as_bob(collaboration, guarded, B2).members(S1)
    assert found.hidden_count == 1, "one IRI, counted once"


async def test_a_hidden_member_reached_by_two_collections_of_a_deep_read_is_counted_once(
    guarded, collaboration
):
    await put_book(guarded, B1)
    await put_book(guarded, B2)
    await put(guarded, a_shelf(A, member_class="Book", had_member=[B1, B2]))
    await put(guarded, a_shelf(B, member_class="Book", had_member=[B2]))
    await put(guarded, a_shelf(S1, member_class="Shelf", had_member=[A, B]))
    found = await as_bob(collaboration, guarded, B2).members(S1, deep=True)
    assert found.member_iris == sorted([A, B, B1]), "the readable ones"
    assert found.hidden_count == 1, "b2 once, though two shelves hold it"


async def test_a_diamond_of_collections_lists_the_shared_members_once(guarded, collaboration):
    await put_book(guarded, B1)
    await put(guarded, a_shelf(C, member_class="Book", had_member=[B1]))
    await put(guarded, a_shelf(A, member_class="Shelf", had_member=[C]))
    await put(guarded, a_shelf(B, member_class="Shelf", had_member=[C]))
    await put(guarded, a_shelf(S1, member_class="Shelf", had_member=[A, B]))
    found = await as_ada(collaboration, guarded).members(S1, deep=True)
    assert found.member_iris == sorted([A, B, C, B1]), "c and b1 once each"


async def test_a_deep_read_through_a_collection_that_lists_itself_ends(guarded, collaboration):
    await put_book(guarded, B1)
    await put(guarded, a_shelf(A, member_class="Book", had_member=[B1]))
    await put(guarded, a_shelf(S1, member_class="Shelf"))
    stored_s = await guarded.get_graph(S1)
    triples = toy_mapper().to_triples(a_shelf(S1, member_class="Shelf", had_member=[S1, A]))
    await guarded.replace_graph(S1, triples, stored_s[2])
    found = await as_ada(collaboration, guarded).members(S1, deep=True)
    assert found.member_iris == sorted([S1, A, B1]), "itself, its shelf and the book"


async def test_a_long_chain_of_collections_is_read_to_the_end(guarded, collaboration):
    shelves = [shelf_iri(100 + n) for n in range(30)]
    await put_book(guarded, B1)
    await put(guarded, a_shelf(shelves[-1], member_class="Book", had_member=[B1]))
    for outer, inner in reversed(list(zip(shelves, shelves[1:], strict=False))):
        await put(guarded, a_shelf(outer, member_class="Shelf", had_member=[inner]))
    found = await as_ada(collaboration, guarded).members(shelves[0], deep=True)
    assert found.member_iris == sorted([*shelves[1:], B1]), "every level, and the book"


async def test_a_deep_read_of_a_collection_of_books_does_not_open_a_book(guarded, collaboration):
    await shelve(guarded, B1)
    found = await as_ada(collaboration, guarded).members(S1, deep=True)
    assert found.member_iris == [B1], "a book is a leaf"


@pytest.mark.parametrize(
    "value",
    [EVIL, "'", '"', "\n", "}", "\\", "x\u0000y", "<http://a>", "?s", "a" * 5000],
    ids=[
        "evil",
        "apostrophe",
        "quote",
        "newline",
        "brace",
        "backslash",
        "nul",
        "iri",
        "var",
        "long",
    ],
)
async def test_a_rule_value_with_metacharacters_matches_only_what_equals_it(
    toy_session, collaboration, value
):  # stored without guards; PD-7: the conditions are the ones find uses
    await put(toy_session, dune(B1, chapters=0, isbn=value))
    await put_book(toy_session, B2)
    rule = MembershipRule(rule_equalities=[SlotEquality(equals_slot="isbn", equals_value=value)])
    await put(toy_session, a_shelf(S1, membership_rule=rule))
    found = await as_ada(collaboration, toy_session).members(S1)
    assert found.member_iris == [B1], "the book whose isbn is exactly that text, and no other"
    assert await stored(toy_session, B2) and await stored(toy_session, S1), "nothing was dropped"


async def test_a_rule_value_that_is_not_a_value_of_its_slot_is_stored_data_invalid(
    toy_session, collaboration
):
    rule = MembershipRule(rule_equalities=[SlotEquality(equals_slot="genre", equals_value=EVIL)])
    await put(toy_session, a_shelf(S1, membership_rule=rule))
    with pytest.raises(StoredDataInvalid, match=S1):
        await as_ada(collaboration, toy_session).members(S1)


@pytest.mark.parametrize("slot", [EVIL, "genre> } ; DROP ALL ; <", "", "chapters", "id"])
async def test_a_rule_slot_the_listing_does_not_accept_is_stored_data_invalid(
    toy_session, collaboration, slot
):
    rule = MembershipRule(rule_equalities=[SlotEquality(equals_slot=slot, equals_value="x")])
    await put(toy_session, a_shelf(S1, membership_rule=rule))
    with pytest.raises(StoredDataInvalid, match=S1):
        await as_ada(collaboration, toy_session).members(S1)


async def test_a_stored_member_class_that_is_no_longer_served_is_stored_data_invalid(
    toy_session, collaboration
):
    await put(toy_session, a_shelf(S1, member_class="Chapter", membership_rule=poetry()))
    with pytest.raises(StoredDataInvalid, match=S1):
        await as_ada(collaboration, toy_session).members(S1)


async def test_members_of_a_non_collection_is_bad_query(guarded, collaboration):
    await put_book(guarded, B1)
    with pytest.raises(BadQuery):
        await as_ada(collaboration, guarded).members(B1)


async def test_members_of_a_missing_iri_is_not_found(guarded, collaboration):
    with pytest.raises(NotFound):
        await as_ada(collaboration, guarded).members(S2)


async def test_members_of_the_tenant_root_is_not_a_crash(toy_session, collaboration):
    await put(toy_session, library())
    with pytest.raises(BadQuery):
        await as_ada(collaboration, toy_session).members(TENANT)


@pytest.mark.parametrize("iri", ["not an iri", "", S1 + "> } ; DROP ALL ; <", OTHER_TENANT])
async def test_members_of_an_iri_that_is_not_one_of_the_tenant_is_a_toolkit_error(
    guarded, collaboration, iri
):
    with pytest.raises(PersistenceError):
        await as_ada(collaboration, guarded).members(iri)


async def test_an_aggregate_with_a_rule_triple_but_no_collection_class_does_not_break_collections_of(
    toy_session, collaboration
):  # PD-7: one CONSTRUCT of every graph whose root has rp:membershipRule
    await put_book(toy_session, B1, Genre.POETRY)
    await put(toy_session, a_shelf(S1, membership_rule=poetry()))
    stray = [(URIRef(B2), RDF.type, BOOK_CLASS), (URIRef(B2), URIRef(RULE_P), BNode("r"))]
    await toy_session.add_graph(B2, stray)
    found = await as_ada(collaboration, toy_session).collections_of(B1)
    assert found.member_iris == [S1], "a stray triple on a book hides no real collection"


async def test_a_bad_rule_of_one_collection_of_the_class_fails_collections_of_for_everyone(
    toy_session, collaboration
):  # pinned, a robustness finding: S2's rule breaks the question about B1 for every caller
    await put_book(toy_session, B1, Genre.POETRY)
    await put(toy_session, a_shelf(S1, membership_rule=poetry()))
    bad = MembershipRule(rule_equalities=[SlotEquality(equals_slot="colour", equals_value="red")])
    await put(toy_session, a_shelf(S2, membership_rule=bad))
    with pytest.raises(StoredDataInvalid, match=S2):
        await as_ada(collaboration, toy_session).collections_of(B1)


async def test_a_bad_collection_the_caller_may_not_read_is_not_named_when_collections_of_fails(
    toy_session, collaboration
):  # PD-27 item 4
    await put_book(toy_session, B1, Genre.POETRY)
    bad = MembershipRule(rule_equalities=[SlotEquality(equals_slot="colour", equals_value="red")])
    await put(toy_session, a_shelf(S2, membership_rule=bad))
    with pytest.raises(StoredDataInvalid) as refused:
        await as_bob(collaboration, toy_session, S2).collections_of(B1)
    assert S2 not in everything_said(refused.value), "the hidden collection is not named"
    assert "one collection of the tenant cannot be read" in str(refused.value)


async def test_an_undecodable_rule_collection_of_another_class_does_not_fail_collections_of(
    toy_session, collaboration
):
    await put_book(toy_session, B1, Genre.POETRY)
    bad = MembershipRule(rule_equalities=[SlotEquality(equals_slot="colour", equals_value="red")])
    await put(toy_session, a_shelf(S2, member_class="Scan", membership_rule=bad))
    found = await as_ada(collaboration, toy_session).collections_of(B1)
    assert found.member_iris is None, "a shelf of scans cannot hold a book"


async def test_collections_of_an_aggregate_with_two_types_lists_the_collections_of_both(
    toy_session, collaboration
):
    iri = book_iri(8)
    await toy_session.add_graph(
        iri, [(URIRef(iri), RDF.type, BOOK_CLASS), (URIRef(iri), RDF.type, SCAN_CLASS)]
    )
    await put(toy_session, a_shelf(S1, member_class="Book", membership_rule=MembershipRule()))
    await put(toy_session, a_shelf(S2, member_class="Scan", membership_rule=MembershipRule()))
    found = await as_ada(collaboration, toy_session).collections_of(iri)
    assert found.member_iris == [S1, S2], "it is a book and a scan"


async def test_collections_of_names_nothing_of_a_hidden_holder(guarded, collaboration):
    await shelve(guarded, B1)
    await put(guarded, a_shelf(S2, had_member=[B1]))
    found = await as_bob(collaboration, guarded, S2).collections_of(B1)
    assert found.member_iris == [S1], "bob may read s1 only"
    assert said_in(found, S2) == [], "no IRI or UUID of s2"
    assert found.hidden_count == 1, "s2 is counted"


async def test_a_collection_holding_by_name_and_by_rule_is_one_hidden_holder(
    guarded, collaboration
):
    await shelve(guarded, B3, rule=poetry())
    found = await as_bob(collaboration, guarded, S1).collections_of(B3)
    assert found.hidden_count == 1, "the same collection, counted once"


async def test_collections_of_a_hidden_aggregate_is_refused_without_a_leak(guarded, collaboration):
    await shelve(guarded, B2)
    with pytest.raises((Forbidden, NotFound)) as refused:
        await as_bob(collaboration, guarded, B2).collections_of(B2)
    assert leaks(refused.value, S1) == [], "no collection is named"


@pytest.mark.parametrize("iri", ["not an iri", "", OTHER_TENANT, graph_of(B1), f"{B1}/parts/x"])
async def test_collections_of_an_iri_that_is_not_an_aggregate_is_invalid_iri(
    guarded, collaboration, iri
):
    with pytest.raises(InvalidIri):
        await as_ada(collaboration, guarded).collections_of(iri)


async def test_collections_of_a_missing_aggregate_is_an_empty_list(guarded, collaboration):
    # pinned: like referrers, only access is checked, not existence
    found = await as_ada(collaboration, guarded).collections_of(B9)
    assert found.member_iris is None and found.hidden_count == 0, "no holder, none hidden"


# -- 6. Session.heads, matches and Transaction._require_match -----------------------------------


@pytest.mark.parametrize(
    "hostile",
    [EVIL, "> } ; DROP ALL ; <", "a b", "", "\n", "http://a/b> ?x <c"],
    ids=["evil", "break-out", "space", "empty", "newline", "inject"],
)
async def test_heads_of_a_hostile_iri_raises_a_sparql_error_and_runs_nothing(guarded, hostile):
    await put_book(guarded, B1)
    with pytest.raises(SparqlError):
        await guarded.heads([B1, hostile])
    assert await stored(guarded, B1), "nothing was dropped"


async def test_heads_names_a_repeated_iri_once(guarded):
    await put_book(guarded, B1)
    found = await guarded.heads([B1, B1, B1])
    assert [h.head_iri for h in found] == [B1], "one head"


async def test_heads_of_an_aggregate_with_two_types_lists_both_types(guarded):
    iri = book_iri(8)
    await guarded.add_graph(
        iri, [(URIRef(iri), RDF.type, BOOK_CLASS), (URIRef(iri), RDF.type, SCAN_CLASS)]
    )
    found = await guarded.heads([iri])
    assert found[0].head_types == sorted([str(BOOK_CLASS), str(SCAN_CLASS)]), "both, sorted"


async def test_heads_has_the_access_record_but_not_the_tenant_root(toy_session):
    # pinned: the tenant root is not an Aggregate entry of the registry, the access record is
    await put(toy_session, library())
    await put(toy_session, access())
    found = await toy_session.heads([TENANT, f"{TENANT}/access"])
    assert [h.head_iri for h in found] == [f"{TENANT}/access"], "only the access record"


async def test_heads_of_a_graph_iri_a_part_and_a_loose_iri_are_none(guarded):
    await put_book(guarded, B1)
    asked = [graph_of(B1), f"{B1}/parts/{UUID(int=1)}", "https://example.org/x"]
    assert await guarded.heads(asked) == [], "none is a registered aggregate"


@pytest.mark.slow
async def test_heads_of_hundreds_of_iris_is_one_query(guarded):
    iris = await books_through_one_transaction(guarded, 400)
    queries = len(guarded._store.sent("query"))
    found = await guarded.heads(iris)
    assert len(found) == 400, "all are found"
    assert len(guarded._store.sent("query")) == queries + 1, "in one query"


async def test_heads_in_iri_order_whatever_the_order_asked(guarded):
    for iri in (B3, B1, B2):
        await put_book(guarded, iri)
    found = await guarded.heads([B3, B1, B2])
    assert [h.head_iri for h in found] == [B1, B2, B3], "sorted by IRI"


async def test_heads_with_no_iris_sends_no_query(guarded):
    queries = len(guarded._store.sent("query"))
    assert await guarded.heads([]) == [], "none"
    assert len(guarded._store.sent("query")) == queries, "and no query"


def book_conditions(genre: str = "poetry"):
    view = load_schema(TOY_SCHEMA)
    listings = Listings(view)
    plan = listings.plan(
        listings.served_root("Book"),
        ListRequest(filters=[Filter(slot="genre", value=genre)] if genre else None),
    )
    return plan.target, plan.conditions or []


async def test_matches_is_exact_about_the_class(guarded):
    await put(guarded, a_shelf(S1))
    ancestor = str(load_schema(TOY_SCHEMA).get_uri("ReferenceCollection", expand=True))
    assert not await guarded.matches(S1, ancestor, []), "a shelf is not exactly a collection mixin"
    assert await guarded.matches(S1, str(SHELF_CLASS), []), "but it is exactly a shelf"


@pytest.mark.parametrize(
    ("genre", "asked", "expected"),
    [
        (Genre.POETRY, "poetry", True),
        (Genre.FICTION, "poetry", False),
        (Genre.POETRY, "", True),
    ],
    ids=["holds", "differs", "no-condition"],
)
async def test_matches_holds_every_condition_or_none(guarded, genre, asked, expected):
    await put_book(guarded, B1, genre)
    target, conditions = book_conditions(asked)
    assert await guarded.matches(B1, target, conditions) is expected, "the same test as find"


async def test_matches_of_a_missing_aggregate_is_false(guarded):
    target, conditions = book_conditions()
    assert not await guarded.matches(B9, target, conditions), "nothing to match"


@pytest.mark.parametrize("iri", ["not an iri", "", OTHER_TENANT, graph_of(B1), TENANT + "/x"])
async def test_matches_of_an_iri_the_policy_does_not_mint_is_invalid_iri(guarded, iri):
    target, conditions = book_conditions()
    with pytest.raises(InvalidIri):
        await guarded.matches(iri, target, conditions)


@pytest.mark.parametrize("hostile", [EVIL, "> } ; DROP ALL ; <", "", "a b"])
async def test_matches_of_a_hostile_class_iri_raises_a_sparql_error(guarded, hostile):
    await put_book(guarded, B1)
    with pytest.raises(SparqlError):
        await guarded.matches(B1, hostile, [])
    assert await stored(guarded, B1), "nothing was dropped"


async def test_matches_with_the_class_of_a_subclass_instance_is_exact(guarded):
    await put(guarded, a_shelf(S1))
    assert not await guarded.matches(S1, str(BOOK_CLASS), []), "a shelf is not a book"


async def test_require_match_with_no_condition_guards_only_the_class(guarded):
    await put_book(guarded, B1)
    await put_book(guarded, B2)
    async with guarded.transaction() as transaction:
        await transaction.remove(B1, await version(guarded, B1))
        transaction._require_match(B2, str(BOOK_CLASS), [])
    assert not await stored(guarded, B1), "it commits when B2 is a book"


async def test_require_match_with_a_wrong_class_fails_the_commit_and_names_no_one(guarded):
    await put_book(guarded, B1)
    await put(guarded, a_shelf(S1))
    with pytest.raises(Conflict) as refused:
        async with guarded.transaction() as transaction:
            await transaction.remove(B1, await version(guarded, B1))
            transaction._require_match(S1, str(BOOK_CLASS), [])
    assert refused.value.iris == (), "a match guard names no one (PD-15)"
    assert await stored(guarded, B1), "b1 is stored"


async def test_the_same_iri_matched_twice_is_guarded_twice_without_joining(guarded):
    await put_book(guarded, B1, Genre.POETRY)
    await put_book(guarded, B2)
    target, conditions = book_conditions()
    async with guarded.transaction() as transaction:
        await transaction.remove(B2, await version(guarded, B2))
        transaction._require_match(B1, target, conditions)
        transaction._require_match(B1, target, conditions)
    assert not await stored(guarded, B2), "both guards hold: it commits"


async def test_two_match_guards_where_one_fails_fail_the_commit(guarded):
    await put_book(guarded, B1, Genre.POETRY)
    await put_book(guarded, B2)
    await put_book(guarded, B3)
    target, conditions = book_conditions()
    with pytest.raises(Conflict):
        async with guarded.transaction() as transaction:
            await transaction.remove(B3, await version(guarded, B3))
            transaction._require_match(B1, target, conditions)
            transaction._require_match(B2, target, conditions)
    assert await stored(guarded, B3), "all or nothing"


async def test_a_match_guard_on_an_iri_with_a_change_in_the_transaction(guarded):
    await put_book(guarded, B1, Genre.POETRY)
    target, conditions = book_conditions()
    async with guarded.transaction() as transaction:
        await transaction.remove(B1, await version(guarded, B1))
        transaction._require_match(B1, target, conditions)
    assert not await stored(guarded, B1), "the guard is read before the removal is applied"


async def test_a_match_guard_on_an_iri_with_no_change_races_with_a_regenre(guarded):
    await put_book(guarded, B1)
    await put_book(guarded, B2, Genre.POETRY)
    target, conditions = book_conditions()
    before(guarded._store, "update", lambda: regenre(guarded._store, B2, Genre.FICTION))
    with pytest.raises(Conflict) as refused:
        async with guarded.transaction() as transaction:
            await transaction.remove(B1, await version(guarded, B1))
            transaction._require_match(B2, target, conditions)
    assert refused.value.iris == (), "no root of the transaction changed: no one is named"
    assert await stored(guarded, B1), "b1 is stored"


async def test_a_match_guard_after_the_transaction_ended_is_refused(guarded):
    await put_book(guarded, B1)
    async with guarded.transaction() as transaction:
        pass
    with pytest.raises(RuntimeError):
        transaction._require_match(B1, str(BOOK_CLASS), [])


async def test_a_match_guard_of_an_iri_the_policy_does_not_mint_is_invalid_iri(guarded):
    with pytest.raises(InvalidIri):
        async with guarded.transaction() as transaction:
            transaction._require_match("not an iri", str(BOOK_CLASS), [])


async def test_a_match_guard_alone_sends_nothing(guarded):
    await put_book(guarded, B1)
    sent = len(guarded._store.sent("update"))
    async with guarded.transaction() as transaction:
        transaction._require_match(B1, str(BOOK_CLASS), [])
    assert len(guarded._store.sent("update")) == sent, "a guard without a change is no request"

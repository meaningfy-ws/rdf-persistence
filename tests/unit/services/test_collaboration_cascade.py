"""Collaboration.delete_cascade: delete a collection and its members, all or nothing (PD-8, #79).

"Another writer" is a second session on the same fake store, made to act at a stated moment by
wrapping one operation of the store: ``before`` runs it once, just before the first matching call.
"""

import pytest

from rdf_persistence import Action, StoredDataInvalid, generated_models
from rdf_persistence.domain.exceptions import (
    CommitTooLarge,
    Conflict,
    Forbidden,
    InvalidBody,
    InvalidIri,
)
from rdf_persistence.domain.generated.rp_collections import MembershipRule, SlotEquality
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import DEFAULT_MAX_ROOTS, UnitOfWork
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.write_guards import WriteGuards
from rdf_persistence.testkit import FakeStore, fake_session
from tests.fixtures.library.generated.books import Genre
from tests.toy import (
    ADA,
    MODULES,
    ROLES,
    TENANT,
    TOY_SCHEMA,
    ban,
    book_iri,
    caller,
    direct,
    dune,
    graph_of,
    held,
    library,
    role,
    shelf,
    shelf_iri,
    toy_mapper,
)
from tests.toy import access as access_record

B1, B2, B3, B4, B9 = (book_iri(n) for n in (1, 2, 3, 4, 9))
S1, A = shelf_iri(1), shelf_iri(3)
HEADS = "VALUES ?m"  # the text of the query that reads the heads of the members


def poetry() -> MembershipRule:
    return MembershipRule(
        rule_equalities=[SlotEquality(equals_slot="genre", equals_value="poetry")]
    )


def a_shelf(iri: str, **slots):
    return shelf(iri).model_copy(update=slots)


async def put(session, model) -> str:
    return await session.add_graph(model.id, toy_mapper().to_triples(model))


async def put_book(session, iri: str, genre: Genre = Genre.FICTION) -> None:
    await put(session, dune(iri, chapters=1).model_copy(update={"genre": genre.value}))


async def stored(session, iri: str) -> bool:
    return bool(await session.heads([iri]))


async def version(session, iri: str) -> str:
    return (await session.get_graph(iri))[2]


@pytest.fixture
async def guarded():
    """A session whose writes check collections, the way the kit's sessions do."""
    listings = Listings(load_schema(TOY_SCHEMA))
    guards = WriteGuards(toy_mapper(), generated_models(*MODULES), listings)
    async with fake_session(tenant_iri=TENANT, listings=listings, guards=guards) as session:
        yield session


def as_ada(collaboration, session):
    return collaboration(caller(principal=ADA), held(role("librarian")), session)


async def regenre(store: FakeStore, iri: str, genre: Genre) -> None:
    """Another writer replaces the book ``iri`` with one of ``genre``."""
    async with fake_session(store, tenant_iri=TENANT) as other:
        model = dune(iri, chapters=1).model_copy(update={"genre": genre.value})
        await other.replace_graph(iri, toy_mapper().to_triples(model), await version(other, iri))


async def gone(store: FakeStore, iri: str) -> None:
    """Another writer removes the aggregate ``iri``."""
    async with fake_session(store, tenant_iri=TENANT) as other:
        await other.remove(iri, await version(other, iri))


def before(store: FakeStore, operation: str, action, when: str = "") -> None:
    """Await ``action()`` once, just before the first call of ``operation`` whose text holds ``when``."""
    original = getattr(store, operation)
    done = False

    async def wrapped(dataset, text):
        nonlocal done
        if not done and when in text:
            done = True
            await action()
        return await original(dataset, text)

    setattr(store, operation, wrapped)


async def test_a_plain_delete_keeps_the_members(guarded):  # TC-33
    await put_book(guarded, B1)
    await put_book(guarded, B2)
    await put(guarded, a_shelf(S1, had_member=[B1, B2]))
    await guarded.remove(S1, await version(guarded, S1))
    assert not await stored(guarded, S1), "the shelf is gone"
    assert await stored(guarded, B1), "b1 stays"
    assert await stored(guarded, B2), "and b2"


async def test_a_cascade_deletes_the_collection_and_all_its_members_in_one_request(
    guarded, collaboration
):  # TC-34
    await put_book(guarded, B1)
    await put_book(guarded, B2)
    await put_book(guarded, B3, Genre.POETRY)
    await put(guarded, a_shelf(S1, had_member=[B1], membership_rule=poetry()))
    sent = len(guarded._store.sent("update"))
    await as_ada(collaboration, guarded).delete_cascade(S1, await version(guarded, S1))
    assert len(guarded._store.sent("update")) == sent + 1, "one update request"
    assert not any([await stored(guarded, i) for i in (S1, B1, B3)]), "s1, b1 and b3 are gone"
    assert await stored(guarded, B2), "a fiction book that nothing names stays"


async def test_a_member_the_caller_may_not_delete_refuses_the_cascade_and_is_named(
    guarded, collaboration
):  # TC-35
    await put_book(guarded, B1)
    await put_book(guarded, B2)
    await put(guarded, a_shelf(S1, had_member=[B1, B2]))
    access = held(
        role("reader"), direct(Action.DELETE, graph_of(S1)), direct(Action.DELETE, graph_of(B1))
    )
    with pytest.raises(Forbidden) as refused:
        await collaboration(caller(), access, guarded).delete_cascade(
            S1, await version(guarded, S1)
        )
    assert B2 in str(refused.value), "b2 is refused and named"
    assert B1 not in str(refused.value), "b1 may be deleted: not named"
    assert await stored(guarded, S1), "the shelf is kept"
    assert await stored(guarded, B1), "and b1: nothing is deleted"


async def test_a_refused_member_the_caller_may_not_read_is_counted_and_not_named(
    guarded, collaboration
):
    for iri in (B1, B2, B3):
        await put_book(guarded, iri)
    await put(guarded, a_shelf(S1, had_member=[B1, B2, B3]))
    access = held(
        role("reader"),
        direct(Action.DELETE, graph_of(S1)),
        direct(Action.DELETE, graph_of(B1)),
        bans=[ban(Action.READ, graph_of(B3))],
    )
    with pytest.raises(Forbidden) as refused:
        await collaboration(caller(), access, guarded).delete_cascade(
            S1, await version(guarded, S1)
        )
    assert B2 in str(refused.value), "b2 is refused and readable: named"
    assert B3 not in str(refused.value), "b3 is refused and hidden: never named"
    assert "1 not readable" in str(refused.value), "but counted"


async def test_a_member_changed_between_the_resolve_and_the_send_is_a_conflict(
    guarded, collaboration
):  # TC-36
    await put_book(guarded, B1)
    await put_book(guarded, B2)
    await put(guarded, a_shelf(S1, had_member=[B1, B2]))
    before(guarded._store, "update", lambda: regenre(guarded._store, B2, Genre.POETRY))
    with pytest.raises(Conflict) as refused:
        await as_ada(collaboration, guarded).delete_cascade(S1, await version(guarded, S1))
    assert refused.value.iris == (B2,), "the changed member is named"
    assert all([await stored(guarded, i) for i in (S1, B1, B2)]), "nothing is deleted"


async def test_a_rule_member_regenred_after_the_heads_is_a_conflict(
    guarded, collaboration
):  # TC-36a
    await put_book(guarded, B3, Genre.POETRY)
    await put(guarded, a_shelf(S1, membership_rule=poetry()))
    before(guarded._store, "update", lambda: regenre(guarded._store, B3, Genre.FICTION))
    with pytest.raises(Conflict) as refused:
        await as_ada(collaboration, guarded).delete_cascade(S1, await version(guarded, S1))
    assert refused.value.iris == (B3,), "its version changed, which the remove's guard names"
    assert await stored(guarded, S1), "the shelf is kept"
    assert await stored(guarded, B3), "and b3: nothing is deleted"


async def test_a_rule_member_regenred_before_the_heads_fails_the_match_guard(
    guarded, collaboration
):  # TC-36b
    await put_book(guarded, B3, Genre.POETRY)
    await put(guarded, a_shelf(S1, membership_rule=poetry()))
    before(guarded._store, "query", lambda: regenre(guarded._store, B3, Genre.FICTION), when=HEADS)
    with pytest.raises(Conflict) as refused:
        await as_ada(collaboration, guarded).delete_cascade(S1, await version(guarded, S1))
    assert refused.value.iris == (), "the heads read the new version: only the rule no longer holds"
    assert await stored(guarded, S1), "the shelf is kept"
    assert await stored(guarded, B3), "and b3: nothing is deleted"


async def test_more_members_than_one_commit_holds_is_refused_before_any_other_read(
    toy_session, collaboration
):  # TC-36c
    members = [book_iri(n) for n in range(1, DEFAULT_MAX_ROOTS + 1)]
    await put(toy_session, a_shelf(S1, had_member=members))  # no guards: the books are not stored
    with pytest.raises(CommitTooLarge, match=str(DEFAULT_MAX_ROOTS)):
        await as_ada(collaboration, toy_session).delete_cascade(S1, await version(toy_session, S1))
    assert not [q for q in toy_session._store.sent("query") if HEADS in q], "no heads were read"
    assert await stored(toy_session, S1), "the shelf is kept"


async def test_a_collection_that_lists_itself_is_deleted_once(toy_session, collaboration):  # TC-37
    await put_book(toy_session, B1)
    await put(toy_session, a_shelf(S1, had_member=[S1, B1]))  # no guards: a shelf holds books
    await as_ada(collaboration, toy_session).delete_cascade(S1, await version(toy_session, S1))
    assert not await stored(toy_session, S1), "the shelf is gone"
    assert not await stored(toy_session, B1), "and its book"


async def test_a_member_that_is_a_collection_is_deleted_and_its_own_members_stay(
    guarded, collaboration
):  # TC-38
    await put_book(guarded, B1)
    await put(guarded, a_shelf(A, member_class="Book", had_member=[B1]))
    await put(guarded, a_shelf(S1, member_class="Shelf", had_member=[A]))
    await as_ada(collaboration, guarded).delete_cascade(S1, await version(guarded, S1))
    assert not await stored(guarded, S1), "the outer shelf is gone"
    assert not await stored(guarded, A), "and the shelf it holds"
    assert await stored(guarded, B1), "not deep"


async def test_a_stale_version_of_the_collection_is_a_conflict(guarded, collaboration):  # TC-39
    await put_book(guarded, B1)
    await put(guarded, a_shelf(S1, had_member=[B1]))
    with pytest.raises(Conflict):
        await as_ada(collaboration, guarded).delete_cascade(S1, "not-the-version")
    assert await stored(guarded, S1), "the shelf is kept"
    assert await stored(guarded, B1), "and its book: nothing is deleted"


async def test_a_member_that_is_already_gone_is_skipped(guarded, collaboration):  # TC-40
    await put_book(guarded, B1)
    await put_book(guarded, B9)
    await put(guarded, a_shelf(S1, had_member=[B1, B9]))
    await guarded.remove(B9, await version(guarded, B9))
    await as_ada(collaboration, guarded).delete_cascade(S1, await version(guarded, S1))
    assert not await stored(guarded, S1), "the shelf is gone"
    assert not await stored(guarded, B1), "and the book that was still there"


async def test_a_member_that_goes_after_the_heads_is_skipped_too(guarded, collaboration):
    await put_book(guarded, B1)
    await put_book(guarded, B4)
    await put(guarded, a_shelf(S1, had_member=[B1, B4]))
    current = await version(guarded, S1)
    before(guarded._store, "query", lambda: gone(guarded._store, B4), when=graph_of(B4))
    await as_ada(collaboration, guarded).delete_cascade(S1, current)
    assert not await stored(guarded, S1), "the shelf is gone"
    assert not await stored(guarded, B1), "and the book that was still there"


def reads_only_and_deletes_the_shelf(*hidden: str):
    """A caller who may delete the shelf alone and read everything but ``hidden``."""
    return held(
        role("reader"),
        direct(Action.DELETE, graph_of(S1)),
        bans=[ban(Action.READ, graph_of(h)) for h in hidden],
    )


async def test_a_cascade_leaves_the_rule_members_the_caller_may_not_read_and_says_nothing(
    guarded, collaboration
):
    """The author of a rule must not learn, even from a refusal, that something hidden matches it."""
    hidden = [book_iri(n) for n in (11, 12, 13)]
    for iri in hidden:
        await put_book(guarded, iri, Genre.POETRY)
    await put(guarded, a_shelf(S1, membership_rule=poetry()))
    access = reads_only_and_deletes_the_shelf(*hidden)
    await collaboration(caller(), access, guarded).delete_cascade(S1, await version(guarded, S1))
    assert not await stored(guarded, S1), "the shelf is deleted: no refusal tells of hidden matches"
    left = [iri for iri in hidden if await stored(guarded, iri)]
    assert left == hidden, "the books the caller may not read are no members for it: they stay"


async def test_a_cascade_refusal_names_readable_members_and_counts_only_the_named_hidden_ones(
    guarded, collaboration
):
    for iri in (B1, B2):
        await put_book(guarded, iri)
    await put_book(guarded, B3, Genre.POETRY)
    await put_book(guarded, B4, Genre.POETRY)
    await put(guarded, a_shelf(S1, had_member=[B1, B2], membership_rule=poetry()))
    access = reads_only_and_deletes_the_shelf(B2, B4)
    with pytest.raises(Forbidden) as refused:
        await collaboration(caller(), access, guarded).delete_cascade(
            S1, await version(guarded, S1)
        )
    said = str(refused.value)
    assert B1 in said, "b1 is refused and readable"
    assert B3 in said, "b3 matches the rule, is refused and readable"
    assert "1 not readable" in said, "b2 is named by the collection: counted"
    assert B2 not in said, "and not named"
    assert B4 not in said, "b4 only matches the rule: not named"
    assert "2 not readable" not in said, "nor counted: it is no member for this caller"


async def test_the_room_check_gives_the_limit_and_no_member_count(toy_session, collaboration):
    members = [book_iri(n) for n in range(1, DEFAULT_MAX_ROOTS + 8)]
    await put(toy_session, a_shelf(S1, had_member=members))  # no guards: the books are not stored
    with pytest.raises(CommitTooLarge) as refused:
        await as_ada(collaboration, toy_session).delete_cascade(S1, await version(toy_session, S1))
    assert str(DEFAULT_MAX_ROOTS) in str(refused.value), "the limit"
    assert str(len(members)) not in str(refused.value), "not how many members there are"


async def test_a_stored_member_class_that_is_no_served_root_refuses_the_cascade(
    toy_session, collaboration
):
    """A collection written without guards: its member class is the access class, it names the record."""
    record = access_record()
    await put(toy_session, record)
    await put(toy_session, a_shelf(S1, member_class="LibraryAccess", had_member=[record.id]))
    with pytest.raises(StoredDataInvalid, match=S1):
        await as_ada(collaboration, toy_session).delete_cascade(S1, await version(toy_session, S1))
    assert await stored(toy_session, record.id), "the access record is kept"
    assert await stored(toy_session, S1), "and the shelf"


async def test_an_unknown_stored_member_class_refuses_the_cascade(toy_session, collaboration):
    await put(toy_session, a_shelf(S1, member_class="NoSuchClass"))
    with pytest.raises(StoredDataInvalid, match=S1):
        await as_ada(collaboration, toy_session).delete_cascade(S1, await version(toy_session, S1))
    assert await stored(toy_session, S1), "nothing is deleted"


async def test_the_tenant_root_is_never_cascaded(toy_session, collaboration):
    await put(toy_session, library())
    with pytest.raises(InvalidIri):
        await as_ada(collaboration, toy_session).delete_cascade(TENANT, "any")
    assert await toy_session.get_graph(TENANT), "the tenant root is kept"


async def test_a_collection_that_is_not_an_aggregate_of_the_tenant_is_an_invalid_iri(
    toy_session, collaboration
):
    with pytest.raises(InvalidIri):
        await as_ada(collaboration, toy_session).delete_cascade("https://elsewhere.org/s", "any")


async def test_a_shelf_and_its_new_books_in_one_commit_is_refused(guarded):  # D-6
    work = UnitOfWork(guarded, toy_mapper())
    work.add(dune(B1, chapters=1))
    work.add(a_shelf(S1, had_member=[B1]))
    with pytest.raises(InvalidBody, match=B1):
        await work.commit()
    assert not await stored(guarded, S1), "the shelf is not stored"
    assert not await stored(guarded, B1), "nor is the book: all or nothing"


async def test_a_cascade_on_a_schema_without_the_module_is_a_lookup_error(toy_session):
    view = load_schema(TOY_SCHEMA.parent / "partial.yaml")
    build = Collaboration(
        toy_session,
        view=view,
        rules=AccessRules(load_role_definitions(ROLES)),
        iris=DEFAULT_IRIS,
        mapper=toy_mapper(),
        models=generated_models(*MODULES),
        listings=Listings(view),
        caller=caller(principal=ADA),
        access=held(role("librarian")),
    )
    with pytest.raises(LookupError, match="rp_collections"):
        await build.delete_cascade(S1, "any")

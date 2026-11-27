"""The write guard's rule on assignees (workflow-assignees D-2, T2, T3): only an assignment or a clearing transition changes them.

The toy ``Book`` follows the assignable review workflow of ``assignees_world``. A stored book is seeded through
a transaction that calls ``_allow_assignees``, as ``assign`` will; each row of the guard table of D-2 is one
case of ``GUARD``, a positive and a negative one.
"""

import pytest
from rdflib import RDF, RDFS, Literal, URIRef

from rdf_persistence import Action, generated_models
from rdf_persistence.collaboration.services.collaboration import Collaboration
from rdf_persistence.collaboration.services.workflows import Workflows
from rdf_persistence.collaboration.services.write_guards import WriteGuards
from rdf_persistence.core.domain.exceptions import Conflict, Forbidden, InvalidBody, NotFound
from rdf_persistence.iris.services.iris import DEFAULT_IRIS
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.mapper import UnitOfWork
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import (
    ADA,
    BOB,
    BOOK_CLASS,
    MODULES,
    TENANT,
    ban,
    book_iri,
    caller,
    dune,
    held,
    role,
    toy_mapper,
)
from tests.unit.collaboration.assignees_world import write_world
from tests.unit.collaboration.collaboration_data import REVIEW, VIEW, version_of

B = book_iri(1)
P1, P2 = "https://example.org/people/p1", "https://example.org/people/p2"
NONE = frozenset()
ONE = frozenset({P1})
TWO = frozenset({P1, P2})
OTHER = frozenset({P2})


@pytest.fixture
def guards(tmp_path) -> WriteGuards:
    world = write_world(tmp_path)
    return WriteGuards(toy_mapper(), generated_models(*MODULES), Listings(VIEW), world.workflows)


def a_book(assignees=NONE):
    """The book B naming ``assignees`` (none: the slot unset, as an application that knows nothing of them writes it)."""
    return dune(B).model_copy(update={"assigned_to": sorted(assignees) or None})


async def assignees_of(session, iri: str = B) -> frozenset[str]:
    held = await session.root_values(iri, [v.WORKFLOW_ASSIGNEES])
    return frozenset(str(o) for o in held[v.WORKFLOW_ASSIGNEES])


async def replace(session, book, *, allowing: frozenset[str] | None = None) -> None:
    """Replace the stored book; ``allowing`` is what only an assignment or a clearing transition does."""
    version = await version_of(session, str(book.id))
    async with session.transaction() as t:
        if allowing is not None:
            t._allow_assignees(str(book.id), allowing)
        await t.replace_graph(str(book.id), toy_mapper().to_triples(book), version)


async def add(session, book) -> None:
    work = UnitOfWork(session, toy_mapper())
    work.add(book)
    await work.commit()


async def seeded(session, stored: frozenset[str]) -> None:
    """The book B stored holding ``stored``, put there the way an assignment will (an add holds none)."""
    await add(session, a_book())
    if stored:
        await replace(session, a_book(stored), allowing=stored)
    assert await assignees_of(session) == stored, "the book holds what the test seeded"


# (id, stored, allowed, written, result): the replace rows of D-2; result is the set held afterwards, or None for Forbidden
GUARD = [
    ("allowed-set-written-as-is", NONE, ONE, ONE, ONE),
    ("allowed-set-more-is-refused", NONE, ONE, TWO, None),
    ("allowed-set-less-is-refused", ONE, TWO, ONE, None),
    ("allowed-empty-set-written-clears", ONE, NONE, NONE, NONE),
    ("allowed-empty-set-with-one-written-is-refused", ONE, NONE, ONE, None),
    ("allowed-set-omitted-is-refused", ONE, ONE, NONE, None),
    ("nothing-allowed-omitted-puts-the-stored-back", ONE, None, NONE, ONE),
    ("nothing-allowed-omitted-and-none-stored-stays-none", NONE, None, NONE, NONE),
    ("nothing-allowed-the-stored-set-is-written-as-is", TWO, None, TWO, TWO),
    ("nothing-allowed-another-set-is-refused", ONE, None, OTHER, None),
    ("nothing-allowed-more-than-stored-is-refused", ONE, None, TWO, None),
    ("nothing-allowed-some-on-a-book-with-none-is-refused", NONE, None, ONE, None),
]


@pytest.mark.parametrize(
    ("stored", "allowed", "written", "result"),
    [g[1:] for g in GUARD],
    ids=[g[0] for g in GUARD],
)
async def test_a_replace_changes_the_assignees_only_as_the_transaction_allows(
    guards, stored, allowed, written, result
):  # T3
    async with fake_session(tenant_iri=TENANT, guards=guards) as session:
        await seeded(session, stored)
        if result is None:
            with pytest.raises(Forbidden, match="assignee"):
                await replace(session, a_book(written), allowing=allowed)
            assert await assignees_of(session) == stored, "a refusal stores nothing"
        else:
            await replace(session, a_book(written), allowing=allowed)
            assert await assignees_of(session) == result, "the assignees are as the rule says"


async def test_a_replace_that_omits_the_assignees_keeps_the_rest_of_the_write(guards):  # T3
    async with fake_session(tenant_iri=TENANT, guards=guards) as session:
        await seeded(session, ONE)
        await replace(session, a_book().model_copy(update={"label": "Dune II"}))
        stored = await UnitOfWork(session, toy_mapper()).get(type(a_book()), B)
        assert stored.label == "Dune II", "the rest of the write is applied"
        assert await assignees_of(session) == ONE, "and the assignees are kept"


async def test_an_allowance_is_for_one_book_only(guards):  # T3
    other = book_iri(2)
    async with fake_session(tenant_iri=TENANT, guards=guards) as session:
        await add(session, a_book())
        await add(session, dune(other))
        version = await version_of(session, other)
        async with session.transaction() as t:
            t._allow_assignees(B, ONE)
            with pytest.raises(Forbidden, match="assignee"):
                await t.replace_graph(
                    other,
                    toy_mapper().to_triples(dune(other).model_copy(update={"assigned_to": [P1]})),
                    version,
                )
        assert await assignees_of(session, other) == NONE, "another book takes none"


async def test_a_transaction_that_has_ended_takes_no_allowance(guards):
    async with fake_session(tenant_iri=TENANT, guards=guards) as session:
        async with session.transaction() as t:
            pass
        with pytest.raises(RuntimeError, match="ended"):
            t._allow_assignees(B, ONE)


# (id, written, result): the add rows of D-2
ADD = [
    ("a-new-book-has-no-assignee", NONE, NONE),
    ("an-add-naming-an-assignee-is-refused", ONE, None),
]


@pytest.mark.parametrize(("written", "result"), [a[1:] for a in ADD], ids=[a[0] for a in ADD])
async def test_an_add_holds_no_assignee(guards, written, result):  # T2
    async with fake_session(tenant_iri=TENANT, guards=guards) as session:
        if result is None:
            with pytest.raises(Forbidden, match="assignee"):
                await add(session, a_book(written))
            with pytest.raises(NotFound):
                await session.get_graph(B)
        else:
            await add(session, a_book(written))
            assert await assignees_of(session) == result, "the new book holds none"


async def test_an_add_names_no_assignee_even_when_the_transaction_allows_a_set(guards):  # T2
    async with fake_session(tenant_iri=TENANT, guards=guards) as session:
        with pytest.raises(Forbidden, match="assignee"):
            async with session.transaction() as t:
                t._allow_assignees(B, ONE)
                await t.add_graph(B, toy_mapper().to_triples(a_book(ONE)))


def untyped(*assignees: str):
    """The triples of a root with no class: it follows no workflow, so its ``assigned_to`` is its own."""
    root = URIRef(B)
    return [
        (root, RDFS.label, Literal("an untyped root")),
        *((root, v.WORKFLOW_ASSIGNEES, URIRef(p)) for p in assignees),
    ]


# (id, held by the untyped root, written by the replace, refused)
TAKING = [
    ("takes-the-class-holding-assignees", ONE, NONE, True),
    ("takes-the-class-writing-assignees", NONE, ONE, True),
    ("takes-the-class-with-none-held-or-written", NONE, NONE, False),
]


@pytest.mark.parametrize(
    ("held", "written", "refused"), [t[1:] for t in TAKING], ids=[t[0] for t in TAKING]
)
async def test_a_root_of_no_workflow_class_takes_one_holding_and_writing_no_assignee(
    guards, held, written, refused
):  # T3, D-2 last row
    async with fake_session(tenant_iri=TENANT, guards=guards) as session:
        await session.add_graph(B, untyped(*held))
        assert await assignees_of(session) == held, "the application's own assignees are written"
        version = await version_of(session, B)
        triples = toy_mapper().to_triples(a_book(written))
        assert (URIRef(B), RDF.type, URIRef(BOOK_CLASS)) in triples, (
            "the replace gives it the book class"
        )
        if refused:
            with pytest.raises(Forbidden, match="assignee"):
                await session.replace_graph(B, triples, version)
            assert await assignees_of(session) == held, "a refusal stores nothing"
        else:
            await session.replace_graph(B, triples, version)
            assert await assignees_of(session) == NONE, "the book holds none"


async def test_a_root_of_no_workflow_class_keeps_its_own_assignees(guards):  # D-2, last sentence
    async with fake_session(tenant_iri=TENANT, guards=guards) as session:
        await session.add_graph(B, untyped(P1))
        version = await version_of(session, B)
        await session.replace_graph(B, untyped(P1, P2), version)
        assert await assignees_of(session) == TWO, "an unguarded root writes what it says"


# -- Assignments (D-3, D-4): T4 to T11 and T13 ------------------------------------------------------

RITA = "https://example.org/people/rita"  # holds ``reviewer`` only
NOBODY = "https://example.org/people/nobody"  # no grant at all
OUTSIDER = "not-an-absolute-iri"
LIBRARIAN, REVIEWER, READER, STRANGER = "librarian", "reviewer", "reader", "stranger"


def access_for(who: str):
    """What the tenant's access record says of ``who``, by the way the test names the caller."""
    return {
        LIBRARIAN: held(role("librarian", who=ADA)),
        REVIEWER: held(role("reviewer", who=RITA)),
        READER: held(role("reader", who=BOB)),
        STRANGER: held(),
    }[who]


PRINCIPAL_OF = {LIBRARIAN: ADA, REVIEWER: RITA, READER: BOB, STRANGER: NOBODY}
# who may read the book, for ``access_of``: the principals the toolkit is asked about
READERS = {
    P1: held(role("reader", who=P1)),
    P2: held(role("reader", who=P2)),
    RITA: held(role("reviewer", who=RITA)),
    ADA: held(role("librarian", who=ADA)),
    NOBODY: held(),
}


async def reads(principal: str):
    """The ``access_of`` of the tests: the stored access of the few principals they know."""
    return READERS[principal]


@pytest.fixture
def world(tmp_path):
    return write_world(tmp_path)


@pytest.fixture
async def open_session(world):
    """The session, over a store of its own, with the guard of the assignable workflow."""
    store = FakeStore()
    await store.create_dataset(FAKE_DATABASE)
    guards = WriteGuards(toy_mapper(), generated_models(*MODULES), Listings(VIEW), world.workflows)
    async with fake_session(store, tenant_iri=TENANT, guards=guards) as session:
        yield session


def assigner(world, session, who: str, *, bans=None, access_of=reads, workflow=True):
    """A ``Collaboration`` for the caller named ``who``; ``workflow=False`` leaves the toy book under none."""
    return Collaboration(
        session,
        view=VIEW,
        rules=world.rules,
        iris=DEFAULT_IRIS,
        mapper=toy_mapper(),
        models=generated_models(*MODULES),
        listings=Listings(VIEW),
        workflows=(world.workflows if workflow is True else workflow or None),
        caller=caller(principal=PRINCIPAL_OF[who]),
        access=access_for(who).model_copy(update={"prohibitions": bans}),
        access_of=access_of,
    )


async def in_review(world, session, stored: frozenset[str] = NONE) -> str:
    """The book B in ``in_review``, holding ``stored``; returns its version."""
    await add(session, a_book())
    lib = assigner(world, session, LIBRARIAN)
    await lib.transition(B, "in_review", if_version=await version_of(session, B))
    if stored:
        await replace(session, a_book(stored), allowing=stored)
    return await version_of(session, B)


async def recorded(session) -> list:
    """The ``Assignment`` activities that used B, as the provenance graph holds them."""
    return sorted(await session.activities(v.ASSIGNMENT, v.USED, URIRef(B)))


# (id, caller, stored, wanted, added, removed): an assignment that is allowed, and what it records (T4, T5)
ALLOWED = [
    ("an-editor-assigns-two-people", LIBRARIAN, NONE, TWO, TWO, NONE),
    ("an-editor-replaces-one-by-another", LIBRARIAN, ONE, OTHER, OTHER, ONE),
    ("an-editor-clears-the-assignees", LIBRARIAN, TWO, NONE, NONE, TWO),
    ("a-reviewer-takes-the-work", REVIEWER, ONE, frozenset({P1, RITA}), frozenset({RITA}), NONE),
    ("a-reviewer-drops-it-again", REVIEWER, frozenset({P1, RITA}), ONE, NONE, frozenset({RITA})),
]


@pytest.mark.parametrize(
    ("who", "stored", "wanted", "added", "removed"),
    [a[1:] for a in ALLOWED],
    ids=[a[0] for a in ALLOWED],
)
async def test_an_allowed_assignment_stores_the_set_and_records_what_changed(
    world, open_session, who, stored, wanted, added, removed
):  # T4, T5
    session = open_session
    held_version = await in_review(world, session, stored)
    who_ = assigner(world, session, who)
    new = await who_.assign(B, sorted(wanted), if_version=held_version)
    assert new == await version_of(session, B), "the version returned is the stored one"
    assert new != held_version, "and it is a new one"
    assert await assignees_of(session) == wanted, "the book holds the set asked for"
    [record] = await who_.assignments(B)
    assert (record.assigned_principals, record.released_principals) == (
        sorted(added) or None,
        sorted(removed) or None,
    ), "the record names who was added and who was released"
    assert record.used_resource == B, "of the book"


async def test_an_assignee_drops_itself_where_no_edge_leaves(world, open_session):  # T5
    session = open_session
    await add(session, a_book())
    lib = assigner(world, session, LIBRARIAN)
    await lib.transition(B, "in_review", if_version=await version_of(session, B))
    await lib.transition(B, "accepted", if_version=await version_of(session, B))
    await replace(session, a_book(frozenset({BOB})), allowing=frozenset({BOB}))
    reader = assigner(world, session, READER)  # no modify, no edge leaves accepted
    await reader.assign(B, [], if_version=await version_of(session, B))
    assert await assignees_of(session) == NONE, "the assignee dropped itself"


# (id, caller, stored, wanted, error): refusals of D-3 steps 5 to 9 (T6, T8, T9)
REFUSED = [
    ("a-reviewer-assigns-someone-else", REVIEWER, ONE, TWO, Forbidden),
    ("a-reader-with-no-edge-role-takes-it", READER, NONE, frozenset({BOB}), Forbidden),
    ("a-reviewer-drops-someone-else", REVIEWER, TWO, ONE, Forbidden),
    ("a-principal-that-is-no-absolute-iri", LIBRARIAN, NONE, frozenset({OUTSIDER}), InvalidBody),
    ("an-added-principal-that-may-not-read", LIBRARIAN, NONE, frozenset({NOBODY}), InvalidBody),
    (
        "an-added-principal-unknown-to-the-reader",
        LIBRARIAN,
        ONE,
        frozenset({P1, NOBODY}),
        InvalidBody,
    ),
]


@pytest.mark.parametrize(
    ("who", "stored", "wanted", "error"), [r[1:] for r in REFUSED], ids=[r[0] for r in REFUSED]
)
async def test_a_refused_assignment_changes_nothing_and_records_nothing(
    world, open_session, who, stored, wanted, error
):  # T6, T9
    session = open_session
    held_version = await in_review(world, session, stored)
    with pytest.raises(error):
        await assigner(world, session, who).assign(B, sorted(wanted), if_version=held_version)
    assert await assignees_of(session) == stored, "a refusal stores nothing"
    assert await recorded(session) == [], "and records nothing"
    assert await version_of(session, B) == held_version, "the version is the one held"


async def test_an_outsider_is_named_when_refused(world, open_session):  # T9
    session = open_session
    held_version = await in_review(world, session)
    with pytest.raises(InvalidBody, match=NOBODY):
        await assigner(world, session, LIBRARIAN).assign(B, [NOBODY], if_version=held_version)


async def test_an_assignee_may_be_added_only_by_a_wired_reader(world, open_session):  # D-4
    session = open_session
    held_version = await in_review(world, session)
    lib = assigner(world, session, LIBRARIAN, access_of=None)
    with pytest.raises(LookupError, match="access reader"):
        await lib.assign(B, [P1], if_version=held_version)
    await lib.assign(B, [], if_version=held_version)  # nothing added: no reader is needed
    # the caller adding itself needs no reader either
    rev = assigner(world, session, REVIEWER, access_of=None)
    await rev.assign(B, [RITA], if_version=await version_of(session, B))
    assert await assignees_of(session) == frozenset({RITA}), "the reviewer took the work"


async def test_a_stale_version_conflicts_before_every_other_refusal(world, open_session):  # T7
    session = open_session
    held_version = await in_review(world, session)
    reviewer = assigner(world, session, REVIEWER)
    for wanted in ([P1], [OUTSIDER], [NOBODY]):  # each would be refused for another reason
        with pytest.raises(Conflict):
            await reviewer.assign(B, wanted, if_version=held_version + "-old")
    assert await assignees_of(session) == NONE, "nothing was stored"


# (id, wanted, error): a workflow that is not assignable refuses a set and accepts the empty one (T8)
NOT_ASSIGNABLE = [("a-set-is-refused", [P1], InvalidBody), ("the-empty-set-is-accepted", [], None)]


@pytest.mark.parametrize(
    ("wanted", "error"), [n[1:] for n in NOT_ASSIGNABLE], ids=[n[0] for n in NOT_ASSIGNABLE]
)
async def test_a_workflow_that_is_not_assignable_refuses_a_set_and_takes_the_empty_one(
    world, open_session, wanted, error
):  # T8
    session = open_session
    await add(session, a_book())
    lib = assigner(world, session, LIBRARIAN, workflow=Workflows([REVIEW], VIEW, world.rules))
    version_ = await version_of(session, B)
    if error is not None:
        with pytest.raises(error):
            await lib.assign(B, wanted, if_version=version_)
    else:
        assert await lib.assign(B, wanted, if_version=version_) == version_, "nothing to change"


async def test_a_book_under_no_workflow_refuses_every_assignment(
    world, open_session
):  # error matrix
    session = open_session
    await add(session, a_book())
    lib = assigner(world, session, LIBRARIAN, workflow=False)
    for wanted in ([], [P1]):
        with pytest.raises(InvalidBody, match="workflow"):
            await lib.assign(B, wanted, if_version=await version_of(session, B))


async def test_a_prohibition_of_modify_blocks_every_assignment_even_the_own(
    world, open_session
):  # T10
    session = open_session
    held_version = await in_review(world, session)
    bans = [ban(Action.MODIFY, TENANT, RITA)]
    reviewer = assigner(world, session, REVIEWER, bans=bans)
    with pytest.raises(Forbidden, match="modify"):
        await reviewer.assign(B, [RITA], if_version=held_version)
    assert await assignees_of(session) == NONE, "the reviewer did not take the work"


async def test_the_same_set_returns_the_version_held_and_records_nothing(
    world, open_session
):  # T11
    session = open_session
    held_version = await in_review(world, session, TWO)
    lib = assigner(world, session, LIBRARIAN)
    assert await lib.assign(B, sorted(TWO), if_version=held_version) == held_version, "held"
    assert await version_of(session, B) == held_version, "nothing was stored"
    assert await recorded(session) == [], "and no record was made"


async def test_an_assignment_is_refused_to_one_who_cannot_see_the_book(
    world, open_session
):  # step 2
    session = open_session
    held_version = await in_review(world, session)
    with pytest.raises(NotFound):
        await assigner(world, session, STRANGER).assign(B, [P1], if_version=held_version)


async def test_the_history_of_assignments_is_oldest_first_and_kept_after_a_delete(
    world, open_session
):  # T13
    session = open_session
    held_version = await in_review(world, session)
    lib = assigner(world, session, LIBRARIAN)
    second = await lib.assign(B, [P1], if_version=held_version)
    await lib.assign(B, [P2], if_version=second)
    first, last = await lib.assignments(B)
    assert (first.assigned_principals, first.released_principals) == ([P1], None), "the first"
    assert (last.assigned_principals, last.released_principals) == ([P2], [P1]), "the second"
    assert first.used_resource == B, "of the book"
    assert first.was_associated_with, "by the session's principal"
    assert (first.started_at_time, first.id) <= (last.started_at_time, last.id), "oldest first"
    await session.remove(B, await version_of(session, B))
    with pytest.raises(NotFound):
        await lib.assignments(B)
    assert len(await recorded(session)) == 2, "the records stay in the provenance graph"

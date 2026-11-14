"""Collaboration.transition and .transitions: the one write that changes a state (PD-15, PD-20 to PD-22, #81).

The toy ``Book`` follows the workflow ``review`` (draft, in_review, accepted); ``librarian`` makes every
transition. Ada is a librarian, bob a reader, unless a test says otherwise. The session is guarded
and drops the records with their aggregate, the way the kit opens one. "Another writer" is a second
session on the same fake store, made to act at a stated moment by wrapping one operation of it.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from rdflib import URIRef

from rdf_persistence import Action, generated_models
from rdf_persistence.domain.exceptions import (
    Conflict,
    Forbidden,
    InvalidBody,
    InvalidIri,
    NotFound,
)
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_discussion import Motivation
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.discussion import dependents as discussion_dependents
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.session import Session
from rdf_persistence.services.transitions import dependents as transition_dependents
from rdf_persistence.services.workflows import Workflows, load_workflow, state_iri
from rdf_persistence.services.write_guards import WriteGuards
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import (
    ADA,
    BOB,
    MODULES,
    REVIEW_WORKFLOW,
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
    role,
    shelf,
    shelf_iri,
    toy_mapper,
)

B1, B2 = book_iri(1), book_iri(2)
S1 = shelf_iri(1)
VIEW = load_schema(TOY_SCHEMA)
T0 = datetime(2026, 11, 14, 9, tzinfo=UTC)
REVIEW = load_workflow(REVIEW_WORKFLOW)
DRAFT, IN_REVIEW, ACCEPTED = (state_iri(REVIEW, s) for s in ("draft", "in_review", "accepted"))
RETIRED = state_iri(REVIEW, "retired")  # a state the file does not list


@pytest.fixture(scope="module")
def rules(tmp_path_factory: pytest.TempPathFactory) -> AccessRules:
    """The toy roles, and a ``librarian`` that can also be granted on one aggregate."""
    path = tmp_path_factory.mktemp("roles") / "roles.yaml"
    path.write_text(
        ROLES.read_text() + "- {role: librarian, level: aggregate, actions: [read, modify]}\n"
    )
    return AccessRules(load_role_definitions(path))


@pytest.fixture
def now() -> dict[str, datetime]:
    """The time the session's clock tells; a test moves it."""
    return {"t": T0}


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


def combined(view=VIEW):
    return discussion_dependents(view) + transition_dependents(view)


@asynccontextmanager
async def opened(
    store: FakeStore, now: dict[str, datetime], who: str, rules: AccessRules, *, guarded=True
) -> AsyncIterator[Session]:
    """A session the way the kit opens one: write guards with the workflows, the records dropped with their aggregate."""
    listings = Listings(VIEW)
    guards = WriteGuards(
        toy_mapper(), generated_models(*MODULES), listings, Workflows([REVIEW], VIEW, rules)
    )
    async with fake_session(
        store,
        tenant_iri=TENANT,
        principal=Principal(id=who),
        clock=lambda: now["t"],
        listings=listings,
        guards=guards if guarded else None,
        dependents=combined() if guarded else (),
    ) as session:
        yield session


@pytest.fixture
async def session(store, now, rules) -> AsyncIterator[Session]:
    async with opened(store, now, ADA, rules) as ada:
        yield ada


@pytest.fixture
async def plain(store, now, rules) -> AsyncIterator[Session]:
    """A session with no workflow guard: what wrote the books before their class named a workflow."""
    async with opened(store, now, ADA, rules, guarded=False) as unguarded:
        yield unguarded


def collab(rules: AccessRules, session: Session, who: str, *grants, bans=None, view=VIEW):
    return Collaboration(
        session,
        view=view,
        rules=rules,
        iris=DEFAULT_IRIS,
        mapper=toy_mapper(),
        models=generated_models(*MODULES),
        listings=Listings(view),
        workflows=Workflows([REVIEW], view, rules),
        caller=caller(principal=who),
        access=held(*grants, bans=bans),
    )


@pytest.fixture
def ada(rules, session) -> Collaboration:
    return collab(rules, session, ADA, role("librarian"))


@pytest.fixture
def bob(rules, session) -> Collaboration:
    return collab(rules, session, BOB, role("reader", who=BOB))


async def put(session: Session, model) -> None:
    await session.add_graph(model.id, toy_mapper().to_triples(model))


@pytest.fixture
async def books(session: Session) -> None:
    for iri in (B1, B2):
        await put(session, dune(iri, chapters=1))


async def version(session: Session, iri: str) -> str:
    return (await session.get_graph(iri))[2]


async def status_of(session: Session, iri: str) -> list[str]:
    return sorted(
        map(str, (await session.root_values(iri, [v.WORKFLOW_STATUS]))[v.WORKFLOW_STATUS])
    )


async def records_of(session: Session, iri: str) -> list[str]:
    return sorted(await session.graphs_with(v.USED, URIRef(iri)))


async def comments_on(session: Session, iri: str) -> list[str]:
    return sorted(await session.graphs_with(v.HAS_TARGET, URIRef(iri)))


async def go(who: Collaboration, session: Session, to: str, iri: str = B1, **more) -> str:
    return await who.transition(iri, to, if_version=await version(session, iri), **more)


def before(store: FakeStore, operation: str, action) -> None:
    """Await ``action()`` once, just before the next call of ``operation``."""
    original = getattr(store, operation)
    done = False

    async def wrapped(dataset, text):
        nonlocal done
        if not done:
            done = True
            await action()
        return await original(dataset, text)

    setattr(store, operation, wrapped)


async def test_a_librarian_moves_a_book_and_gets_the_new_version(session, ada, books):  # TC-82
    first = await version(session, B1)
    new = await go(ada, session, "in_review")
    assert await status_of(session, B1) == [IN_REVIEW], "the state is the new one"
    assert new == await version(session, B1), "the version returned is the stored one"
    assert new != first, "and it is a new one"


@pytest.mark.parametrize(
    ("to", "said"),
    [("accepted", r"draft.*accepted"), ("nonsense", r"'nonsense' is an unknown state")],
    ids=["a-state-with-no-edge-from-here", "no-state-of-the-workflow"],
)
async def test_a_move_the_workflow_has_not_is_a_conflict_naming_both_states(
    session, ada, books, to, said
):  # TC-83; PD-32 item 6: a `to` that is no state says so
    with pytest.raises(Conflict, match=said):
        await go(ada, session, to)
    assert await status_of(session, B1) == [DRAFT], "b1 stays in draft"


async def test_a_reader_may_not_make_the_move_and_nothing_changes(session, bob, books):  # TC-84
    with pytest.raises(Forbidden):
        await go(bob, session, "in_review")
    assert await status_of(session, B1) == [DRAFT], "b1 stays in draft"
    assert await records_of(session, B1) == [], "and no record was written"


@pytest.mark.parametrize("text", [None, "  "])
async def test_a_move_that_needs_a_comment_refuses_none_and_blank(
    session, ada, books, text
):  # TC-85
    await go(ada, session, "in_review")
    with pytest.raises(InvalidBody):
        await go(ada, session, "draft", comment=text)
    assert await status_of(session, B1) == [IN_REVIEW], "b1 stays in review"
    assert len(await records_of(session, B1)) == 1, "only the first move has a record"


async def test_a_stale_version_is_a_conflict_with_no_record_and_no_comment(
    session, ada, books
):  # TC-86
    with pytest.raises(Conflict):
        await ada.transition(B1, "in_review", if_version="stale", comment="ready")
    assert await status_of(session, B1) == [DRAFT], "b1 stays in draft"
    assert await records_of(session, B1) == [], "no record"
    assert await comments_on(session, B1) == [], "no comment"


async def test_each_move_is_recorded_with_its_agent_time_and_comment(
    store, now, rules, books
):  # TC-87
    async with opened(store, now, ADA, rules) as s1, opened(store, now, BOB, rules) as s2:
        p1 = collab(rules, s1, ADA, role("librarian"))
        p2 = collab(rules, s2, BOB, role("librarian", who=BOB))
        await go(p1, s1, "in_review", comment="ready")
        now["t"] = T0 + timedelta(minutes=1)
        await go(p2, s2, "accepted")
        first, second = await p1.transitions(B1)
        [ready] = await p1.thread(B1)
    assert (first.was_associated_with, second.was_associated_with) == ([ADA], [BOB]), "the agents"
    assert (first.started_at_time, second.started_at_time) == (T0, T0 + timedelta(minutes=1)), (
        "the times are the session's clock"
    )
    assert (first.used_resource, first.from_state_iri, first.to_state_iri) == (
        B1,
        DRAFT,
        IN_REVIEW,
    ), "the first move is of b1, from draft to in review"
    assert (second.from_state_iri, second.to_state_iri) == (IN_REVIEW, ACCEPTED), "the states"
    assert first.transition_comment == ready.id, "the first names the comment of the thread"
    assert ready.body_value == "ready", "which holds the text"
    assert second.transition_comment is None, "the second has none"


async def test_a_prohibition_of_modify_freezes_the_book_for_transitions(
    rules, session, books
):  # TC-87a
    frozen = collab(rules, session, ADA, role("librarian"), bans=[ban(Action.MODIFY, graph_of(B1))])
    with pytest.raises(Forbidden):
        await go(frozen, session, "in_review")
    assert await status_of(session, B1) == [DRAFT], "b1 stays in draft"
    assert await records_of(session, B1) == [], "and no record was written"


async def test_a_move_with_a_comment_posts_it_in_the_thread_in_one_request(
    store, session, ada, bob, books
):  # TC-88
    await go(ada, session, "in_review")
    updates = len(store.sent("update"))
    await go(ada, session, "accepted", comment="fine")
    assert len(store.sent("update")) == updates + 1, (
        "the state, the record and the comment: one request"
    )
    *_, fine = await bob.thread(B1)  # bob only reads: the comment has no audience
    assert fine.body_value == "fine", "the comment ends the thread"
    assert fine.creator == ADA, "by ada"
    assert (fine.from_state_iri, fine.to_state_iri) == (IN_REVIEW, ACCEPTED), "with both states"
    assert fine.comment_audience is None, "for everyone who reads"
    assert fine.has_target == B1, "on b1"
    assert fine.motivated_by == Motivation.COMMENTING, "a remark, not a reply"


async def test_a_plain_replace_leaves_the_records_alone(session, ada, books):  # TC-89
    await go(ada, session, "in_review", comment="ready")
    kept = await ada.transitions(B1)
    edited = dune(B1, chapters=1)
    edited.label = "Dune again"
    await session.replace_graph(B1, toy_mapper().to_triples(edited), await version(session, B1))
    assert await ada.transitions(B1) == kept, "the records are as they were"
    assert await status_of(session, B1) == [IN_REVIEW], "and so is the state"


async def test_removing_the_book_removes_its_records_and_comments(session, ada, books):  # TC-90
    await go(ada, session, "in_review", comment="ready")
    await session.remove(B1, await version(session, B1))
    assert await records_of(session, B1) == [], "no record"
    assert await comments_on(session, B1) == [], "no comment"


async def test_a_book_stored_before_its_class_named_the_workflow_starts_from_the_initial_state(
    session, ada, plain
):  # TC-91
    await put(plain, dune(B1, chapters=1))
    assert await status_of(session, B1) == [], "it has no state"
    await go(ada, session, "in_review")
    assert await status_of(session, B1) == [IN_REVIEW], "the first transition gives it a state"
    [record] = await ada.transitions(B1)
    assert record.from_state_iri == DRAFT, "the move was from the initial state"


async def test_a_state_the_file_no_longer_lists_is_stored_as_it_is_and_no_move_leaves_it(
    session, ada, plain
):  # TC-92
    await put(plain, dune(B1, chapters=1, workflow_status=RETIRED))
    for to in ("in_review", "draft"):
        with pytest.raises(Conflict, match="retired"):
            await go(ada, session, to)
    edited = dune(B1, chapters=1)
    edited.label = "Dune again"
    await session.replace_graph(B1, toy_mapper().to_triples(edited), await version(session, B1))
    assert await status_of(session, B1) == [RETIRED], "a label replace passes and keeps the state"


async def test_a_grant_on_one_book_lets_the_caller_move_that_book_only(
    rules, session, books
):  # TC-93
    one = collab(rules, session, ADA, role("librarian", target=graph_of(B1)))
    await go(one, session, "in_review")
    assert await status_of(session, B1) == [IN_REVIEW], "b1 moved"
    with pytest.raises(NotFound):
        await go(one, session, "in_review", B2)
    assert await status_of(session, B2) == [DRAFT], "b2 did not"


async def test_a_shelf_is_under_no_workflow(session, ada):  # TC-94
    await put(session, shelf(S1))
    with pytest.raises(InvalidBody, match="workflow"):
        await go(ada, session, "in_review", S1)


async def test_two_moves_from_one_version_store_the_first_and_refuse_the_second(
    store, now, rules, session, ada, books
):  # TC-95
    stale = await version(session, B1)
    async with opened(store, now, BOB, rules) as other:
        rival = collab(rules, other, BOB, role("librarian", who=BOB))

        async def rival_moves():
            await rival.transition(B1, "in_review", if_version=stale)

        before(store, "update", rival_moves)
        with pytest.raises(Conflict):
            await ada.transition(B1, "in_review", if_version=stale, comment="mine")
    assert await status_of(session, B1) == [IN_REVIEW], "the first stored"
    [record] = await ada.transitions(B1)
    assert record.was_associated_with == [BOB], "it is the rival's"
    assert await comments_on(session, B1) == [], "the loser left no comment"


async def test_the_records_are_not_referrers_of_the_book(session, ada, books):  # TC-96
    await go(ada, session, "in_review")
    assert (await ada.referrers(B1)).referrers is None, "no record is listed"


async def test_a_record_takes_no_comment(rules, session, ada, books):
    await go(ada, session, "in_review")
    [record] = await ada.transitions(B1)
    may_annotate = collab(rules, session, ADA, role("librarian"), direct(Action.ANNOTATE))
    with pytest.raises(InvalidIri):
        await may_annotate.comment(record.id, "a remark")
    assert await comments_on(session, record.id) == [], "nothing was stored"


async def test_a_schema_without_the_module_has_no_transitions(rules, session, books):
    view = load_schema(Path(TOY_SCHEMA).parent / "partial.yaml")
    bare = collab(rules, session, ADA, role("librarian"), view=view)
    with pytest.raises(LookupError, match="rp_workflow"):
        await bare.transition(B1, "in_review", if_version="x")
    with pytest.raises(LookupError, match="rp_workflow"):
        await bare.transitions(B1)
    assert transition_dependents(view) == (), "and it has no records to drop"

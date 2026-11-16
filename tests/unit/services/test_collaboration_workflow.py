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
from rdflib import RDF, XSD, Graph, URIRef

from rdf_persistence import Action, generated_models
from rdf_persistence.domain.exceptions import (
    Conflict,
    Forbidden,
    InvalidBody,
    NotFound,
)
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_discussion import Motivation
from rdf_persistence.domain.generated.rp_workflow import Transition
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.discussion import dependents as discussion_dependents
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.session import Session
from rdf_persistence.services.workflows import Workflows
from rdf_persistence.services.write_guards import WriteGuards
from rdf_persistence.testkit import FakeStore, assert_isomorphic, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
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
    direct,
    dune,
    graph_of,
    held,
    role,
    shelf,
    shelf_iri,
    toy_mapper,
)
from tests.unit.services.collaboration_data import (
    ACCEPTED,
    DRAFT,
    IN_REVIEW,
    RETIRED,
    REVIEW,
)

B1, B2 = book_iri(1), book_iri(2)
S1 = shelf_iri(1)
PROVENANCE = URIRef(DEFAULT_IRIS.provenance(TENANT))
BOOK_CLASS = "http://purl.org/ontology/bibo/Book"
COMMENT_CLASS = str(v.ANNOTATION)
VIEW = load_schema(TOY_SCHEMA)
T0 = datetime(2026, 11, 14, 9, tzinfo=UTC)


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
    """What a remove drops with its aggregate: the comments (a transition's activity stays, PD-11)."""
    return discussion_dependents(view)


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
    """The IRIs of the transition activities that used ``iri``, as the provenance graph holds them."""
    return sorted(await session.activities(v.TRANSITION, v.USED, URIRef(iri)))


async def provenance_of(store: FakeStore) -> Graph:
    """The tenant's whole provenance graph."""
    text = f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{PROVENANCE}> {{ ?s ?p ?o }} }}"
    return (await store.query(FAKE_DATABASE, text)).graph or Graph()


def parts_of(graph: Graph, activity: str, link: URIRef) -> set[tuple[str, str]]:
    """The ``(entity, class)`` of each generation or invalidation (by ``link``) of ``activity``."""
    return {
        (str(graph.value(p, v.ENTITY)), str(graph.value(p, v.ENTITY_CLASS)))
        for p in graph.objects(URIRef(activity), link)
    }


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


async def move_twice(store, now, rules, session, ada, books) -> None:
    """ada moves b1 to in review with a comment, then accepts it a minute later."""
    await go(ada, session, "in_review", comment="ready")
    now["t"] = T0 + timedelta(minutes=1)
    await go(ada, session, "accepted")


async def test_a_transition_is_one_activity_that_used_the_book(store, session, ada, books):  # TC-41
    await go(ada, session, "in_review", comment="ready")
    graph = await provenance_of(store)
    [record] = graph.subjects(RDF.type, v.TRANSITION)
    [ready] = await comments_on(session, B1)
    assert (record, v.USED, URIRef(B1)) in graph, "it used b1"
    assert (record, v.FROM_STATE, URIRef(DRAFT)) in graph, "from draft"
    assert (record, v.TO_STATE, URIRef(IN_REVIEW)) in graph, "to in review"
    assert (record, v.TRANSITION_COMMENT, URIRef(ready)) in graph, "with the comment it posted"
    assert (record, RDF.type, v.ACTIVITY) in graph, "and it is an activity"
    new_book = {(B1, BOOK_CLASS)}
    assert parts_of(graph, str(record), v.HAS_GENERATION) == new_book | {(ready, COMMENT_CLASS)}, (
        "it generated a version of b1 and the comment"
    )
    assert parts_of(graph, str(record), v.HAS_INVALIDATION) == new_book, (
        "it invalidated b1's old one"
    )
    for payload in ("to_state", "expected_version", "body_value"):
        assert (record, v.predicate(payload), None) not in graph, f"no {payload}"


async def test_a_transition_has_no_aggregate_of_its_own(store, session, ada, books):  # TC-42
    await go(ada, session, "in_review", comment="ready")
    graphs = {
        str(r.g)
        for r in await store.query(FAKE_DATABASE, "SELECT DISTINCT ?g { GRAPH ?g { ?s ?p ?o } }")
    }
    assert not [g for g in graphs if "rp-transitions" in g], "no graph of a record"
    [record] = await records_of(session, B1)
    owned = f"ASK {{ GRAPH ?r {{ ?g <{v.REGISTRY_OWNED_BY}> <{record}> }} }}"
    assert not (await store.query(FAKE_DATABASE, owned)).askAnswer, "no registry entry of a record"


async def test_removing_the_book_keeps_its_transitions_and_removes_its_comments(
    store, now, rules, session, ada, books
):  # TC-44
    await move_twice(store, now, rules, session, ada, books)
    old = await records_of(session, B1)
    await session.remove(B1, await version(session, B1))
    assert await records_of(session, B1) == old, "the two transitions are still stored"
    graph = await provenance_of(store)
    assert len(list(graph.subjects(RDF.type, v.REMOVE))) == 1, "and the remove is a third activity"
    assert await comments_on(session, B1) == [], "the comment is gone"


async def test_the_transitions_of_a_removed_book_are_not_found(
    store, now, rules, session, ada, books
):  # TC-45
    await move_twice(store, now, rules, session, ada, books)
    await session.remove(B1, await version(session, B1))
    with pytest.raises(NotFound):
        await ada.transitions(B1)


async def test_a_book_added_again_shows_the_old_history(
    store, now, rules, session, ada, books
):  # TC-46: the old test asserted none
    await move_twice(store, now, rules, session, ada, books)
    before_remove = await ada.transitions(B1)
    await session.remove(B1, await version(session, B1))
    await put(session, dune(B1, chapters=1))
    assert await ada.transitions(B1) == before_remove, "the two old transitions"


@pytest.mark.parametrize("how", ["stale", "role"])
async def test_a_refused_transition_leaves_no_activity(
    store, session, ada, bob, books, how
):  # TC-48
    seen = await provenance_of(store)
    if how == "stale":
        with pytest.raises(Conflict):
            await ada.transition(B1, "in_review", if_version="stale", comment="ready")
    else:
        with pytest.raises(Forbidden):
            await go(bob, session, "in_review")
    assert_isomorphic(await provenance_of(store), seen)
    assert await records_of(session, B1) == [], "no transition"


async def test_a_transition_typed_activity_that_did_not_replace_the_book_is_not_returned(
    session, ada, books
):  # D-6 b: an activity that used b1 but generated none of it is no move of b1
    command = Transition(
        id="urn:uuid:5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c04e",
        used_resource=B1,
        from_state_iri=DRAFT,
        to_state_iri=IN_REVIEW,
    )
    async with session.transaction(served=toy_mapper().served(command)) as transaction:
        await transaction.replace_graph(
            B2, toy_mapper().to_triples(dune(B2)), await version(session, B2)
        )
    assert await ada.transitions(B1) == [], "b1 was not replaced by it"


async def test_a_move_with_a_comment_shows_only_the_parts_about_the_book(session, ada, books):
    await go(ada, session, "in_review", comment="ready")
    [found] = await ada.transitions(B1)
    assert [g.entity for g in found.generations] == [B1], "the comment's generation is dropped"
    assert [i.entity for i in found.invalidations] == [B1], "and so is any other invalidation"
    [ready] = await comments_on(session, B1)
    assert found.transition_comment == ready, "though the comment is still named"


async def test_a_transition_of_a_subclass_comes_back_as_a_transition(
    store, session, ada, books
):  # TC-49
    kind = f"{v.TRANSITION.rsplit('#', 1)[0]}#ApproveBook"  # a class the schema does not know
    foreign = "urn:uuid:5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c049"
    await store.update(
        FAKE_DATABASE,
        f"INSERT DATA {{ GRAPH <{PROVENANCE}> {{ <{foreign}> a <{v.TRANSITION}>, <{kind}>, <{v.ACTIVITY}> ; "
        f"<{v.USED}> <{B1}> ; <{v.HAS_GENERATION}> <{foreign}/part> . <{foreign}/part> a <{v.GENERATION}> ; "
        f'<{v.PART_ACTIVITY}> <{foreign}> ; <{v.AT_TIME}> "2026-01-01T00:00:00Z"^^<{XSD.dateTime}> ; '
        f'<{v.ENTITY}> <{B1}> ; <{v.ENTITY_VERSION}> "v" }} }}',
    )
    [found] = await ada.transitions(B1)
    assert type(found) is Transition, "the found activity is a transition"
    assert found.id == foreign, "the found transition keeps its id"
    assert found.used_resource == B1, "the found transition keeps its used resource"


async def test_a_value_the_caller_set_for_a_computed_slot_is_overwritten(
    store, session, ada, books
):  # TC-49a
    forged = Transition(
        id="urn:uuid:5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c04a",
        used_resource=B1,
        from_state_iri=ACCEPTED,
        to_state_iri=ACCEPTED,
    )
    await ada._transitions.transition(  # what a bus handler calls, with its command
        B1,
        "in_review",
        if_version=await version(session, B1),
        command=forged,
    )
    graph = await provenance_of(store)
    assert list(graph.objects(URIRef(forged.id), v.FROM_STATE)) == [URIRef(DRAFT)], "computed, once"
    assert list(graph.objects(URIRef(forged.id), v.TO_STATE)) == [URIRef(IN_REVIEW)], "and so is to"


async def test_a_command_naming_another_aggregate_is_stored_against_the_moved_one(
    store, session, ada, books
):  # beside TC-49a: the aggregate is the one moved, not the one the command names
    forged = Transition(
        id="urn:uuid:5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c04d",
        used_resource=B2,
        from_state_iri=ACCEPTED,
        to_state_iri=ACCEPTED,
    )
    await ada._transitions.transition(
        B1, "in_review", if_version=await version(session, B1), command=forged
    )
    graph = await provenance_of(store)
    assert list(graph.objects(URIRef(forged.id), v.USED)) == [URIRef(B1)], "the moved aggregate"


def test_the_toolkit_fills_eight_slots_and_the_session_five_of_them():  # TC-49b
    computed = {"from_state_iri", "to_state_iri", "transition_comment"}
    assert {*v.SESSION_FILLED, *computed} == v.TOOLKIT_FILLED, "the five and the three, no more"
    assert set(v.SESSION_FILLED) < v.TOOLKIT_FILLED, "the session's five are a subset"


def test_a_served_transition_drops_the_payload_and_keeps_the_computed_slots():  # TC-49c
    command = Transition(
        id="urn:uuid:5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c04c",
        used_resource=B1,
        to_state="in_review",
        expected_version="v1",
        body_value="x",
        from_state_iri=DRAFT,
    )
    served = toy_mapper().served(command)
    predicates = {p for _, p, _ in served.triples}
    assert predicates == {v.USED, v.FROM_STATE}, "the statements of what the toolkit fills"
    payload = (
        served.activity.to_state,
        served.activity.expected_version,
        served.activity.body_value,
    )
    assert payload == (None, None, None), "the activity has no payload"
    assert served.types == [v.TRANSITION, v.ACTIVITY], "the served transition keeps its types"


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


async def test_the_records_are_not_referrers_of_the_book(session, ada, books):  # TC-96, TC-47
    await go(ada, session, "in_review", comment="ready")
    assert (await ada.referrers(B1)).referrers is None, "neither the move nor its comment is listed"


async def test_a_record_takes_no_comment(rules, session, ada, books):
    await go(ada, session, "in_review")
    [record] = await ada.transitions(B1)
    may_annotate = collab(rules, session, ADA, role("librarian"), direct(Action.ANNOTATE))
    with pytest.raises(
        NotFound
    ):  # an activity of the provenance graph is no aggregate of the tenant
        await may_annotate.comment(record.id, "a remark")
    assert await comments_on(session, record.id) == [], "nothing was stored"


async def test_a_schema_without_the_module_has_no_transitions(rules, session, books):
    view = load_schema(Path(TOY_SCHEMA).parent / "partial.yaml")
    bare = collab(rules, session, ADA, role("librarian"), view=view)
    with pytest.raises(LookupError, match="rp_workflow"):
        await bare.transition(B1, "in_review", if_version="x")
    with pytest.raises(LookupError, match="rp_workflow"):
        await bare.transitions(B1)

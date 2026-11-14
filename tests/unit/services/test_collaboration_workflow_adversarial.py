"""Adversarial tests of stage 4, workflow (rp-workflow, PD-15 to PD-22, PD-25, PD-28 item 1, PD-30, D-9, D-10, RISK-4, Q-2).

First the one rule the stage exists for (only a transition changes the state of an aggregate, through
every write path), then who may make a transition and what a refusal tells, which transitions exist,
the transaction under concurrent writers, the records, and the workflow files and the hard rule. Each
test names the spec line, design item or decision it holds the code to; "pinned" marks behaviour no
document decides. B1 and B2 are books of the toy tenant, S1 a shelf; ``ada`` is a librarian and ``bob``
a reader. "Another writer" is a second session on the same fake store, made to act at a stated moment
(``before``).
"""

import contextlib
import inspect
import shutil
from datetime import timedelta
from pathlib import Path

import pytest
import yaml
from rdflib import RDF, XSD, BNode, Literal, URIRef

from rdf_persistence import Action, UnitOfWork, generated_models
from rdf_persistence.domain.exceptions import (
    Conflict,
    Forbidden,
    InvalidBody,
    InvalidIri,
    InvalidWorkflow,
    NotFound,
    StoredDataInvalid,
    StoreUnavailable,
)
from rdf_persistence.domain.generated.rp_access import Grant
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_workflow import TransitionRecord, WorkflowTransition
from rdf_persistence.domain.generated.service.rp_service import CallerAccess, TenantState
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.domain.sparql import Triple, fill, term
from rdf_persistence.entrypoints.kit import ServiceKit
from rdf_persistence.generation.checks.hard import hard_problems
from rdf_persistence.generation.generated.rp_generation import HardRule
from rdf_persistence.generation.problems import format_problem
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.session import Session, Transaction
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.services.transitions import Transitions
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
    toy_mapper,
)
from tests.toy_service import DUNE_BODY, ToyService, principal_of
from tests.unit.entrypoints.scene import Scene
from tests.unit.services import test_collaboration_workflow as built
from tests.unit.services.test_collaboration_cascade import before
from tests.unit.services.test_collaboration_collections_adversarial import (
    everything_said,
    marker_left,
)
from tests.unit.services.test_collaboration_workflow import (
    ACCEPTED,
    B1,
    B2,
    DRAFT,
    IN_REVIEW,
    RETIRED,
    REVIEW,
    S1,
    T0,
    VIEW,
    comments_on,
    go,
    opened,
    put,
    records_of,
    status_of,
    version,
)

# the fixtures of the builder's tests, shared: pytest finds a fixture by the name it is bound to here
ada, bob, books, now, plain, session, store = (
    built.ada,
    built.bob,
    built.books,
    built.now,
    built.plain,
    built.session,
    built.store,
)

LIB = "https://example.org/ns/library#"
SHELF_CLASS = URIRef(f"{LIB}Shelf")
BOOK_CLASS = URIRef("http://purl.org/ontology/bibo/Book")
OTHER_FLOW = "https://example.org/ns/library/workflows/other/accepted"
EVIL = 'x" } . ?s ?p ?o } ; DROP ALL ; # \n\r\t\\ <a> {'
COUNT = "SELECT (COUNT(DISTINCT ?g) AS ?n) WHERE { GRAPH $registry { ?g $p_kind ?k } }"
EXTRA_ROLES = (
    "- {role: librarian, level: aggregate, actions: [read, modify]}\n"
    "- {role: editor, level: aggregate, actions: [read]}\n"
)


# -- fixtures and builders ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def rules(tmp_path_factory: pytest.TempPathFactory) -> AccessRules:
    """The toy roles, a ``librarian`` and an ``editor`` that can be granted on one aggregate."""
    path = tmp_path_factory.mktemp("roles") / "roles.yaml"
    path.write_text(ROLES.read_text() + EXTRA_ROLES)
    return AccessRules(load_role_definitions(path))


def move(from_state: str, to_state: str, *roles: str, comment: bool = False) -> WorkflowTransition:
    return WorkflowTransition(
        from_state=from_state,
        to_state=to_state,
        transition_roles=list(roles or ["librarian"]),
        comment_required=comment,
    )


def flow(*moves: WorkflowTransition):
    """The review workflow with only ``moves`` as transitions."""
    return REVIEW.model_copy(update={"workflow_transitions": list(moves)})


def make(
    rules: AccessRules,
    session: Session,
    who: str,
    grants: list[Grant],
    *,
    bans=None,
    global_roles: tuple[str, ...] = (),
    workflow=REVIEW,
    state: TenantState = TenantState.ACTIVE,
) -> Collaboration:
    """A collaboration of ``who`` over ``session`` with the given grants, bans and token roles."""
    return Collaboration(
        session,
        view=VIEW,
        rules=rules,
        iris=DEFAULT_IRIS,
        mapper=toy_mapper(),
        models=session._write_guards._models,
        listings=Listings(VIEW),
        workflows=Workflows([workflow], VIEW, rules),
        caller=caller(*global_roles, principal=who),
        access=held(*grants, bans=bans, state=state),
    )


def typed(iri: str, *states, types: tuple[URIRef, ...] | None = None) -> list[Triple]:
    """The triples of a valid book, its status replaced by ``states`` (none: no status), its root type by ``types``."""
    root = URIRef(iri)
    kept = [
        t
        for t in toy_mapper().to_triples(dune(iri, chapters=1))
        if not (
            t[0] == root and (t[1] == v.WORKFLOW_STATUS or (t[1] == RDF.type and types is not None))
        )
    ]
    typing = [(root, RDF.type, t) for t in types or ()]
    named = [
        (root, v.WORKFLOW_STATUS, s if isinstance(s, (URIRef, Literal, BNode)) else URIRef(s))
        for s in states
    ]
    return [*kept, *typing, *named]


async def add_by_session(session: Session, iri: str, triples: list[Triple]) -> None:
    await session.add_graph(iri, triples)


async def add_by_transaction(session: Session, iri: str, triples: list[Triple]) -> None:
    async with session.transaction() as transaction:
        await transaction.add_graph(iri, triples)


async def replace_by_session(session: Session, iri: str, triples: list[Triple]) -> None:
    await session.replace_graph(iri, triples, await version(session, iri))


async def replace_by_transaction(session: Session, iri: str, triples: list[Triple]) -> None:
    held_version = await version(session, iri)
    async with session.transaction() as transaction:
        await transaction.replace_graph(iri, triples, held_version)


ADDS = [add_by_session, add_by_transaction]
REPLACES = [replace_by_session, replace_by_transaction]


def named(function) -> str:
    return function.__name__


async def aggregates(store: FakeStore) -> int:
    text = fill(COUNT, registry=term(DEFAULT_IRIS.registry(TENANT)), p_kind=term(v.REGISTRY_KIND))
    return int(next(iter(await store.query(FAKE_DATABASE, text))).n)


async def snapshot(session: Session, store: FakeStore, iri: str = B1):
    """What a refused write must leave as it was: the state, the version, the records, the thread, the count, the marker."""
    return (
        await status_of(session, iri),
        await version(session, iri),
        await records_of(session, iri),
        await comments_on(session, iri),
        await aggregates(store),
        await marker_left(session),
    )


# -- 1. the state can only be changed by a transition (spec "toolkit owns the state", PD-19) -----

BAD_STATES = [
    pytest.param([ACCEPTED], id="another-state"),
    pytest.param([DRAFT, ACCEPTED], id="two-states"),
    pytest.param([OTHER_FLOW], id="a-state-of-another-workflow"),
    pytest.param([Literal(ACCEPTED)], id="a-literal"),
    pytest.param([Literal(DRAFT)], id="the-initial-state-as-a-literal"),
    pytest.param([f"{DRAFT}/"], id="the-initial-state-with-a-trailing-slash"),
    pytest.param([DRAFT.replace("https:", "http:")], id="the-initial-state-in_another-scheme"),
    pytest.param([DRAFT, f"{DRAFT}/"], id="the-initial-state-in-two-spellings"),
    pytest.param([BNode("state")], id="a-blank-node"),
]


@pytest.mark.parametrize("states", BAD_STATES)
@pytest.mark.parametrize("add", ADDS, ids=named)
async def test_a_new_book_takes_no_state_but_the_initial_one_through_any_add(session, add, states):
    with pytest.raises(Forbidden):
        await add(session, B1, typed(B1, *states))
    with pytest.raises(NotFound):
        await session.get_graph(B1)


@pytest.mark.parametrize("states", BAD_STATES)
@pytest.mark.parametrize("replace", REPLACES, ids=named)
async def test_a_stored_book_takes_no_other_state_through_any_replace(
    store, session, books, replace, states
):
    seen = await snapshot(session, store)
    with pytest.raises(Forbidden):
        await replace(session, B1, typed(B1, *states))
    assert await snapshot(session, store) == seen, "state, version and the rest are as they were"


@pytest.mark.parametrize("state", [ACCEPTED, IN_REVIEW, OTHER_FLOW, f"{DRAFT}/"])
async def test_the_unit_of_work_cannot_set_a_state_on_a_new_or_a_stored_book(session, books, state):
    work = UnitOfWork(session, toy_mapper())
    work.add(dune(book_iri(7), chapters=1).model_copy(update={"workflow_status": state}))
    with pytest.raises(Forbidden):
        await work.commit()
    edit = UnitOfWork(session, toy_mapper())
    stored = await edit.get(type(dune(B1)), B1)
    edit.add(stored.model_copy(update={"workflow_status": state}))
    with pytest.raises(Forbidden):
        await edit.commit()
    assert await status_of(session, B1) == [DRAFT], "the stored book stays in draft"
    with pytest.raises(NotFound):
        await session.get_graph(book_iri(7))


async def test_a_status_on_a_part_is_no_state_of_the_book(session, ada, books):  # pinned
    chapter = next(o for s, p, o in typed(B1) if s == URIRef(B1) and p == URIRef(f"{LIB}chapter"))
    sneaked = [*typed(B1), (chapter, v.WORKFLOW_STATUS, URIRef(ACCEPTED))]
    with contextlib.suppress(Forbidden):  # refusing it is as good
        await replace_by_session(session, B1, sneaked)
    assert await status_of(session, B1) == [DRAFT], "the state of the root is not that of a part"
    await go(ada, session, "in_review")
    [record] = await ada.transitions(B1)
    assert record.from_state_iri == DRAFT, "the move starts from the state of the root"


@pytest.mark.parametrize("replace", REPLACES, ids=named)
async def test_a_replace_without_a_status_keeps_the_state_a_transition_gave(
    session, ada, books, replace
):
    await go(ada, session, "in_review")
    await replace(session, B1, typed(B1))
    assert await status_of(session, B1) == [IN_REVIEW], "the status is kept, not dropped"


TYPE_CHANGES = [
    pytest.param((), id="the-type-dropped"),
    pytest.param((SHELF_CLASS,), id="a-shelf-type"),
    pytest.param((v.TRANSITION_RECORD,), id="a-record-type"),
    pytest.param((v.ANNOTATION,), id="an-annotation-type"),
]


@pytest.mark.parametrize("types", TYPE_CHANGES)
@pytest.mark.parametrize("replace", REPLACES, ids=named)
async def test_a_replace_that_changes_the_type_cannot_write_a_state(
    store, session, books, replace, types
):
    """PD-32 item 1: the workflow is that of the STORED class, and an aggregate under a workflow
    keeps a class under it. Dropping the type, or a record or annotation type, is refused by that
    rule; a shelf type is refused first by the collection check, as these triples are no shelf."""
    seen = await snapshot(session, store)
    with pytest.raises((Forbidden, InvalidBody)):
        await replace(session, B1, typed(B1, ACCEPTED, types=types))
    assert await snapshot(session, store) == seen, "the book is as it was"


@pytest.mark.parametrize("replace", REPLACES, ids=named)
async def test_a_writer_cannot_strip_the_type_write_a_state_and_restore_the_type(
    store, session, books, replace
):
    """The suspected hole: the type goes, any state is written, the type comes back, review is skipped."""
    seen = await snapshot(session, store)
    for step in (typed(B1, ACCEPTED, types=()), typed(B1, ACCEPTED)):
        try:
            await replace(session, B1, step)
        except (Forbidden, InvalidBody):
            break
    assert await status_of(session, B1) == [DRAFT], "no transition moved it, so it is in draft"
    assert (await snapshot(session, store))[2:4] == seen[2:4], "and nothing was recorded"


@pytest.mark.parametrize("types", [(v.ANNOTATION,), ()], ids=["an-annotation-type", "no-type"])
@pytest.mark.parametrize("replace", REPLACES, ids=named)
async def test_the_three_write_path_is_closed_at_its_first_step(
    store, session, ada, books, replace, types
):
    """PD-32 item 1: retype to a class under no workflow (the state was kept), write again (no workflow:
    the state was dropped), retype back (no state, so the initial one). The first step is refused now.

    Shown through a session and its transactions. The generic routes cannot show it on the toy: a
    route fixes the class of its body, and the toy serves no superclass without a workflow above a
    class with one; the rule is the one below the routes (``Aggregates`` writes through a session)."""
    await go(ada, session, "in_review")
    seen = await snapshot(session, store)
    with pytest.raises(Forbidden, match="keeps a class under it"):
        await replace(session, B1, typed(B1, types=types))
    assert await snapshot(session, store) == seen, "the book is as the transition left it"
    assert await status_of(session, B1) == [IN_REVIEW], "still in review, not back in draft"


@pytest.mark.parametrize("add", ADDS, ids=named)
async def test_an_application_own_status_on_a_class_under_no_workflow_is_written(session, add):
    """PD-32 item 1 (turns round PD-31): a shelf follows no workflow, so its adms:status is the application's."""
    own, another = (URIRef(f"https://example.org/own/{name}") for name in ("open", "closed"))
    root = URIRef(S1)
    triples = toy_mapper().to_triples(shelf(S1))
    await add(session, S1, [*triples, (root, v.WORKFLOW_STATUS, own)])
    assert await status_of(session, S1) == [str(own)], "written on add"
    await replace_by_session(session, S1, [*triples, (root, v.WORKFLOW_STATUS, another)])
    assert await status_of(session, S1) == [str(another)], "and on replace"
    await replace_by_session(session, S1, list(triples))
    assert await status_of(session, S1) == [], "a replace without it drops it, as any slot"


@pytest.mark.parametrize("add", ADDS, ids=named)
async def test_a_root_added_without_a_class_in_a_state_cannot_become_a_book_holding_it(
    session, add
):
    """PD-32 item 1: an untyped root is no book, so its state is its own (written as given); taking
    the class of a workflow while holding a state is refused, so it never becomes a book in accepted."""
    await add(session, B1, typed(B1, ACCEPTED, types=()))
    with pytest.raises(Forbidden, match="holds no state"):
        await replace_by_session(session, B1, typed(B1, ACCEPTED))
    held = await session.root_values(B1, [RDF.type, v.WORKFLOW_STATUS])
    assert held[RDF.type] == set(), "the root still has no class"
    assert {str(s) for s in held[v.WORKFLOW_STATUS]} == {ACCEPTED}, "and its own state, as written"


async def test_a_book_typed_with_the_workflow_class_and_another_takes_no_state(session):
    with pytest.raises(Forbidden):
        await add_by_session(session, B1, typed(B1, ACCEPTED, types=(v.ANNOTATION, BOOK_CLASS)))
    with pytest.raises(NotFound):
        await session.get_graph(B1)


async def test_removing_a_book_and_adding_it_again_starts_in_the_initial_state(session, ada, books):
    await go(ada, session, "in_review", comment="ready")
    await session.remove(B1, await version(session, B1))
    with pytest.raises(Forbidden):
        await add_by_session(session, B1, typed(B1, IN_REVIEW))
    await add_by_session(session, B1, typed(B1))
    assert await status_of(session, B1) == [DRAFT], "the re-add starts in the initial state"
    assert await ada.transitions(B1) == [], "with none of the old records"
    assert await ada.thread(B1) == [], "and none of the old comments"


async def test_a_cascade_then_an_add_starts_in_the_initial_state(rules, session, ada, books):
    await go(ada, session, "in_review", comment="ready")
    await put(session, shelf(S1).model_copy(update={"had_member": [B1]}))
    await ada.delete_cascade(S1, await version(session, S1))
    with pytest.raises(Forbidden):
        await add_by_session(session, B1, typed(B1, ACCEPTED))
    await add_by_session(session, B1, typed(B1))
    assert await status_of(session, B1) == [DRAFT], "the re-add starts in the initial state"
    assert await records_of(session, B1) == [], "no record of the old book"
    assert await comments_on(session, B1) == [], "no comment of the old book"


PUBLIC_OWNERS = [Collaboration, UnitOfWork, Session, Transaction, Transitions, ServiceKit, Tenancy]


def public_calls():
    for owner in PUBLIC_OWNERS:
        for name, member in inspect.getmembers(owner, callable):
            if not name.startswith("_") and (
                inspect.isfunction(member) or inspect.ismethod(member)
            ):
                yield pytest.param(member, id=f"{owner.__name__}.{name}")


@pytest.mark.parametrize("call", list(public_calls()))
def test_no_public_callable_takes_a_state_allowance(call):  # TC-80a
    names = set(inspect.signature(call).parameters) - {"self"}
    assert not {n for n in names if "state" in n or "allow" in n or "status" in n}, (
        f"{names} lets a caller set a state"
    )


async def test_an_allowance_for_one_book_lets_no_other_book_change_state(store, session, books):
    seen = await snapshot(session, store, B2)
    with pytest.raises(Forbidden):
        async with session.transaction() as transaction:
            transaction._allow_state(B1, ACCEPTED)
            await transaction.replace_graph(B1, typed(B1, ACCEPTED), await version(session, B1))
            await transaction.replace_graph(B2, typed(B2, ACCEPTED), await version(session, B2))
    assert await status_of(session, B1) == [DRAFT], (
        "the allowed book did not move either: all or nothing"
    )
    assert await snapshot(session, store, B2) == seen, "the other book is as it was"


async def test_an_allowance_for_one_book_lets_no_other_book_be_added_in_a_state(session, books):
    async with session.transaction() as transaction:
        transaction._allow_state(B1, ACCEPTED)
        with pytest.raises(Forbidden):
            await transaction.add_graph(book_iri(9), typed(book_iri(9), ACCEPTED))


async def test_an_allowance_does_not_let_the_book_hold_two_states(session, books):
    with pytest.raises(Forbidden):
        async with session.transaction() as transaction:
            transaction._allow_state(B1, ACCEPTED)
            await transaction.replace_graph(
                B1, typed(B1, ACCEPTED, IN_REVIEW), await version(session, B1)
            )
    assert await status_of(session, B1) == [DRAFT], "the book is as it was"


@pytest.fixture
async def toy():
    service = ToyService()
    async with service.app.router.lifespan_context(service.app), service.client() as http:
        yield await Scene.set_up(service, http)


API_STATES = ["accepted", ACCEPTED, f"{DRAFT}/", DRAFT.upper(), DRAFT.replace("https:", "http:")]


@pytest.mark.parametrize("state", API_STATES)
async def test_the_generic_put_cannot_set_a_state(toy, state):
    scene = toy
    response = await scene.http.put(
        scene.book,
        json={**DUNE_BODY, "workflow_status": state},
        headers=scene.headers("ada", **{"If-Match": scene.book_etag}),
    )
    assert response.status_code in (403, 422), response.text
    stored = await scene.http.get(scene.book, headers=scene.headers("ada"))
    assert (stored.json()["workflow_status"], stored.headers["etag"]) == (DRAFT, scene.book_etag), (
        "the book is in draft and unchanged"
    )


@pytest.mark.parametrize("extra", [{"type": "Shelf"}, {"@type": "lib:Shelf"}, {"rdf:type": "x"}])
async def test_the_generic_put_cannot_change_the_type_of_a_book(toy, extra):
    scene = toy
    response = await scene.http.put(
        scene.book,
        json={**DUNE_BODY, "workflow_status": ACCEPTED, **extra},
        headers=scene.headers("ada", **{"If-Match": scene.book_etag}),
    )
    assert response.status_code in (400, 403, 422), response.text
    stored = await scene.http.get(scene.book, headers=scene.headers("ada"))
    assert stored.json()["workflow_status"] == DRAFT, "the book is in draft"


# -- 1e. finding aggregates by state (PD-32 item 9: the how-to says only what this test shows) ----


async def test_session_find_filters_the_books_of_a_state(session, ada, books):
    await go(ada, session, "in_review")
    book = type(dune(B1))
    assert await session.find(book, workflow_status=IN_REVIEW) == [B1], "b1 moved"
    assert await session.find(book, workflow_status=DRAFT) == [B2], "b2 did not"
    assert await session.find(book, workflow_status=ACCEPTED) == [], "none is accepted"


# -- 1d. a `to` that is no state of the workflow (PD-32 item 6) ---------------------------------


@pytest.mark.parametrize("to", ["archived", "DRAFT", "", ACCEPTED, DRAFT, " draft"])
async def test_a_target_that_is_no_state_name_of_the_workflow_is_a_conflict_saying_so(
    session, ada, books, to
):
    with pytest.raises(Conflict, match="unknown state") as refused:
        await go(ada, session, to)
    assert "review" in str(refused.value), "it names the workflow"
    assert await status_of(session, B1) == [DRAFT], "the book stays in draft"


async def test_a_state_of_the_workflow_with_no_edge_from_here_is_still_a_missing_transition(
    session, ada, books
):
    with pytest.raises(Conflict, match="no transition from") as refused:
        await go(ada, session, "accepted")
    assert "unknown state" not in str(refused.value), "accepted is a state"


# -- 1c. a Prohibition of annotate refuses a transition's comment (PD-32 item 3) ----------------

SILENCED = [
    pytest.param([ban(Action.ANNOTATE, graph_of(B1))], id="ban-on-the-aggregate"),
    pytest.param([ban(Action.ANNOTATE)], id="ban-on-the-tenant"),
]


@pytest.mark.parametrize("bans", SILENCED)
async def test_a_transition_with_a_comment_by_a_caller_prohibited_annotate_is_forbidden(
    store, rules, session, books, bans
):
    silenced = make(rules, session, ADA, [role("librarian")], bans=bans)
    seen = await snapshot(session, store)
    with pytest.raises(Forbidden, match="annotate"):
        await silenced.transition(
            B1, "in_review", if_version=await version(session, B1), comment="ready"
        )
    assert await snapshot(session, store) == seen, "no state, no record, no comment"


@pytest.mark.parametrize("bans", SILENCED)
@pytest.mark.parametrize("comment", [None, "", "   "], ids=["none", "empty", "blank"])
async def test_a_transition_without_a_comment_by_a_caller_prohibited_annotate_passes(
    rules, session, books, bans, comment
):
    silenced = make(rules, session, ADA, [role("librarian")], bans=bans)
    await silenced.transition(
        B1, "in_review", if_version=await version(session, B1), comment=comment
    )
    assert await status_of(session, B1) == [IN_REVIEW], "the book moved"
    assert await comments_on(session, B1) == [], "with no comment in the thread"


# -- 1b. a stale write is a conflict, not a refusal of the state (PD-32 item 2) -----------------


async def replace_stale(
    session: Session, iri: str, triples: list[Triple], read: str, *, by
) -> None:
    if by == "session":
        await session.replace_graph(iri, triples, read)
        return
    async with session.transaction() as transaction:
        await transaction.replace_graph(iri, triples, read)


@pytest.mark.parametrize("by", ["session", "transaction"])
async def test_a_replace_of_the_body_read_before_a_transition_is_a_conflict_not_a_refusal(
    store, session, ada, books, by
):
    """The reviewer's scenario: read in draft; another writer moves it to in_review; the body read
    (in draft) is written back. It would change the state, but the client only read an older one."""
    read = await version(session, B1)
    await go(ada, session, "in_review")
    seen = await snapshot(session, store)
    with pytest.raises(Conflict, match="changed by someone else since it was read") as refused:
        await replace_stale(session, B1, typed(B1, DRAFT), read, by=by)
    assert refused.value.iris == (B1,), "the conflict names the aggregate"
    assert not isinstance(refused.value, Forbidden), "it is no refusal of the state"
    assert await snapshot(session, store) == seen, "nothing changed"


@pytest.mark.parametrize("by", ["session", "transaction"])
async def test_a_stale_replace_the_guards_do_not_refuse_is_still_refused_by_the_commit(
    store, session, ada, books, by
):
    read = await version(session, B1)
    await go(ada, session, "in_review")
    seen = await snapshot(session, store)
    with pytest.raises(Conflict, match="changed by someone else since it was read"):
        await replace_stale(
            session, B1, typed(B1), read, by=by
        )  # no state written: the stored one is kept
    assert await snapshot(session, store) == seen, "nothing changed"


@pytest.mark.parametrize("by", ["session", "transaction"])
async def test_a_replace_at_the_current_version_that_changes_the_state_is_still_forbidden(
    session, books, by
):
    with pytest.raises(Forbidden):
        await replace_stale(session, B1, typed(B1, ACCEPTED), await version(session, B1), by=by)
    assert await status_of(session, B1) == [DRAFT], "the book stays in draft"


async def test_a_stale_transition_is_a_conflict_about_the_version_not_about_the_edge(
    session, ada, books
):
    read = await version(session, B1)
    await go(ada, session, "in_review")
    # from in_review there is no edge to in_review: before, this said so; now the version is first
    with pytest.raises(Conflict, match="changed by someone else since it was read") as refused:
        await ada.transition(B1, "in_review", if_version=read)
    assert refused.value.iris == (B1,), "it names the aggregate"
    assert await status_of(session, B1) == [IN_REVIEW], "the book is as the other writer left it"
    assert len(await ada.transitions(B1)) == 1, "no second record"


async def test_a_stale_transition_by_a_reader_is_a_conflict_before_the_role_check(
    session, ada, bob, books
):
    read = await version(session, B1)
    await go(ada, session, "in_review")
    with pytest.raises(Conflict, match="changed by someone else"):
        await bob.transition(B1, "accepted", if_version=read)


async def test_a_transition_at_the_current_version_with_no_edge_is_still_about_the_edge(
    session, ada, books
):
    with pytest.raises(Conflict, match="no transition from") as refused:
        await ada.transition(B1, "accepted", if_version=await version(session, B1))
    assert "changed by someone else" not in str(refused.value), "the version is current"


async def test_the_generic_put_of_a_body_read_before_a_transition_is_a_409(toy):
    scene = toy
    tenant_id = scene.tenant.rsplit("/", 1)[1]
    authorised = await scene.service.kit.require(
        scene.headers("ada")["Authorization"], tenant_id, Action.READ
    )
    async with scene.service.kit.collaboration(authorised) as collaboration:
        await collaboration.transition(
            scene.book_iri, "in_review", if_version=scene.book_etag.strip('"')
        )
    response = await scene.http.put(
        scene.book,
        json={**DUNE_BODY, "workflow_status": DRAFT},
        headers=scene.headers("ada", **{"If-Match": scene.book_etag}),
    )
    assert response.status_code == 409, response.text
    stored = await scene.http.get(scene.book, headers=scene.headers("ada"))
    assert stored.json()["workflow_status"] == IN_REVIEW, "the book is where the transition left it"


async def test_the_generic_post_cannot_create_a_book_with_two_states(toy):
    scene = toy
    listed = f"{scene.tenant}/books"
    total = (await scene.http.get(listed, headers=scene.headers("ada"))).json()["total"]
    response = await scene.http.post(
        listed,
        json={**DUNE_BODY, "workflow_status": [DRAFT, ACCEPTED]},
        headers=scene.headers("ada"),
    )
    assert response.status_code in (403, 422), response.text
    after = (await scene.http.get(listed, headers=scene.headers("ada"))).json()["total"]
    assert after == total, "nothing was stored"


# -- 2. who may make a transition (spec "only defined and permitted", Q-2, PD-20, PD-30 item 3) ---

LIBRARIAN_ON_B1 = role("librarian", target=graph_of(B1))
# (id, grants, bans, token roles, what happens)
WHO = [
    pytest.param([role("librarian")], None, (), None, id="role-on-the-tenant"),
    pytest.param([LIBRARIAN_ON_B1], None, (), None, id="role-on-the-aggregate-only"),
    pytest.param(
        [role("librarian", target=graph_of(B2))], None, (), NotFound, id="role-on-another-aggregate"
    ),
    pytest.param([direct(Action.MODIFY)], None, (), Forbidden, id="modify-without-the-role"),
    pytest.param([direct(Action.ANNOTATE)], None, (), Forbidden, id="annotate-without-the-role"),
    pytest.param(
        [role("librarian")],
        [ban(Action.MODIFY, graph_of(B1))],
        (),
        Forbidden,
        id="role-and-modify-banned-on-the-aggregate",
    ),
    pytest.param(
        [role("librarian")],
        [ban(Action.MODIFY)],
        (),
        Forbidden,
        id="role-and-modify-banned-on-the-tenant",
    ),
    pytest.param(
        [role("librarian")],
        [ban(Action.READ, graph_of(B1))],
        (),
        Forbidden,
        id="role-and-read-banned-on-the-aggregate",
    ),
    pytest.param(
        [role("librarian")],
        [ban(Action.READ)],
        (),
        Forbidden,
        id="role-and-read-banned-on-the-tenant",
    ),
    pytest.param(
        [role("librarian")],
        [ban(Action.DELETE, graph_of(B1))],
        (),
        None,
        id="role-and-delete-banned",
    ),
    pytest.param(
        [role("librarian")],
        [ban(Action.ANNOTATE, graph_of(B1))],
        (),
        None,
        id="role-and-annotate-banned",
    ),
    pytest.param(
        [role("librarian")], [ban(Action.MODIFY, who=BOB)], (), None, id="modify-banned-for-another"
    ),
    pytest.param([], None, (), NotFound, id="no-grant-at-all"),
    pytest.param(
        [role("librarian", who=BOB)], None, (), NotFound, id="the-role-of-another-principal"
    ),
    pytest.param(
        [direct(Action.READ)],
        None,
        ("librarian",),
        Forbidden,
        id="token-role-not-defined-at-system-level",
    ),
]


@pytest.mark.parametrize(("grants", "bans", "tokens", "outcome"), WHO)
async def test_only_the_edge_roles_and_no_ban_of_modify_or_read_let_a_caller_move_a_book(
    rules, session, books, grants, bans, tokens, outcome
):
    who = make(rules, session, ADA, grants, bans=bans, global_roles=tokens)
    if outcome is None:
        await go(who, session, "in_review")
        assert await status_of(session, B1) == [IN_REVIEW], "moved"
        return
    with pytest.raises(outcome):
        await go(who, session, "in_review")
    assert await status_of(session, B1) == [DRAFT], "b1 stays in draft"
    assert await records_of(session, B1) == [], "and no record was written"


async def test_a_token_role_defined_at_system_level_counts_for_an_edge(rules, session, books):
    admin = flow(move("draft", "in_review", "admin"))
    who = make(rules, session, ADA, [direct(Action.READ)], global_roles=("admin",), workflow=admin)
    await go(who, session, "in_review")
    assert await status_of(session, B1) == [IN_REVIEW], "the system-level token role moved it"


async def test_a_token_role_the_edge_does_not_name_does_not_count(rules, session, books):
    admin = flow(move("draft", "in_review", "librarian"))
    who = make(rules, session, ADA, [direct(Action.READ)], global_roles=("admin",), workflow=admin)
    with pytest.raises(Forbidden):
        await go(who, session, "in_review")


@pytest.mark.parametrize(
    "grant", [role("editor", target=graph_of(B1)), role("librarian")], ids=["editor", "librarian"]
)
async def test_one_role_of_an_edge_with_several_is_enough(rules, session, books, grant):
    several = flow(move("draft", "in_review", "editor", "librarian"))
    await go(make(rules, session, ADA, [grant], workflow=several), session, "in_review")
    assert await status_of(session, B1) == [IN_REVIEW], "moved by one of the roles"


async def test_a_role_granted_on_the_aggregate_of_an_edge_with_several_roles_only_may_not_read_more(
    rules, session, books
):
    several = flow(move("draft", "in_review", "editor", "librarian"))
    who = make(rules, session, ADA, [role("editor", target=graph_of(B1))], workflow=several)
    with pytest.raises(NotFound):
        await go(who, session, "in_review", B2)


def reader_of(rules, session):
    return make(rules, session, BOB, [role("reader", who=BOB)])


async def test_a_reader_is_told_the_roles_the_edge_asks_for(rules, session, books):
    """Pinned: the refusal of a caller who may read but holds no role names the roles of the edge."""
    with pytest.raises(Forbidden) as refused:
        await go(reader_of(rules, session), session, "in_review")
    assert "librarian" in str(refused.value), "the roles of the edge are in the text"


async def test_a_reader_tells_an_existing_edge_from_a_missing_one_by_the_kind_of_refusal(
    rules, session, books
):
    """Pinned: no edge is a Conflict, an edge without the role a Forbidden, so a reader can probe the edges."""
    who = reader_of(rules, session)
    with pytest.raises(Forbidden):
        await go(who, session, "in_review")
    with pytest.raises(Conflict):
        await go(who, session, "accepted")


async def test_a_conflict_for_a_reader_names_the_state_and_nothing_else_of_the_workflow(
    rules, session, books
):
    with pytest.raises(Conflict) as refused:
        await go(reader_of(rules, session), session, "accepted")
    said = everything_said(refused.value)
    assert DRAFT in said, "the current state is readable like any slot"
    assert "in_review" not in said, "the other edges and states are not listed"
    assert "librarian" not in said, "nor the roles"


async def test_a_caller_who_may_not_read_learns_nothing_of_the_book_from_a_refusal(
    rules, session, books
):
    for target in (B1, book_iri(9)):  # a stored book in draft, and one that is not stored
        stranger = make(rules, session, BOB, [])
        with pytest.raises(NotFound) as refused:
            await stranger.transition(target, "in_review", if_version="x")
        said = str(refused.value).replace(target, "<iri>")
        assert said == "nothing of <iri> is visible to the caller", (
            "the same refusal for a stored and a missing book"
        )
        for secret in ("draft", "review", "librarian", "version"):
            assert secret not in said, f"{secret!r} is not in {said!r}"


async def test_a_caller_banned_from_reading_gets_the_same_refusal_for_a_stored_and_a_missing_book(
    rules, session, books
):
    texts = []
    for target in (B1, book_iri(9)):
        banned = make(rules, session, ADA, [role("librarian")], bans=[ban(Action.READ)])
        with pytest.raises(Forbidden) as refused:
            await banned.transition(target, "in_review", if_version="x")
        texts.append(everything_said(refused.value).replace(target, "<iri>"))
    assert texts[0] == texts[1], "a ban says the same of a book that is there and one that is not"


async def test_a_tenant_being_deleted_is_not_found(rules, session, books):
    who = make(rules, session, ADA, [role("librarian")], state=TenantState.DELETING)
    with pytest.raises(NotFound):
        await go(who, session, "in_review")
    assert await status_of(session, B1) == [DRAFT], "b1 stays in draft"


# -- 3. which transitions exist (PD-20, PD-22, spec "only defined and permitted") ----------------

NO_SUCH_STATE = [
    "archived",
    "",
    " ",
    "in_review ",
    "in_review\n",
    "IN_REVIEW",
    "in_review/../draft",
    "../in_review",
    EVIL,
    "in_review' } ; DROP ALL ; #",
    IN_REVIEW,
    "draft",
    "retired",
]


@pytest.mark.parametrize("to", NO_SUCH_STATE)
async def test_a_target_that_is_no_state_name_is_a_conflict_and_changes_nothing(
    store, session, ada, books, to
):
    seen = await snapshot(session, store)
    with pytest.raises(Conflict):
        await go(ada, session, to)
    assert await snapshot(session, store) == seen, "nothing changed"


async def test_a_workflow_with_a_self_edge_moves_a_book_to_the_state_it_is_in(
    rules, session, books
):  # pinned
    loop = flow(move("draft", "draft"))
    who = make(rules, session, ADA, [role("librarian")], workflow=loop)
    first = await version(session, B1)
    new = await go(who, session, "draft")
    [record] = await who.transitions(B1)
    assert (record.from_state_iri, record.to_state_iri) == (DRAFT, DRAFT), "a record of the loop"
    assert new != first, "the book has a new version"


@pytest.mark.parametrize("to", ["in_review", "draft", "accepted", "retired"])
async def test_every_move_from_a_stored_state_the_file_no_longer_lists_is_a_conflict(
    session, ada, plain, to
):
    await put(plain, dune(B1, chapters=1, workflow_status=RETIRED))
    with pytest.raises(Conflict, match="retired"):
        await go(ada, session, to)
    assert await status_of(session, B1) == [RETIRED], "the stored state is kept"


async def test_a_book_with_two_stored_states_is_not_moved_from_either_of_them(
    session, ada, plain
):  # PD-31 item 7: stored data the toolkit would not write
    await put(plain, dune(B1, chapters=1))
    await replace_by_session(plain, B1, typed(B1, DRAFT, IN_REVIEW))
    for to in ("in_review", "accepted"):  # draft to in_review exists, in_review to accepted too
        with pytest.raises(StoredDataInvalid, match="books"):  # names the aggregate
            await go(ada, session, to)
    assert await status_of(session, B1) == sorted([DRAFT, IN_REVIEW]), "nothing changed"


async def test_a_transition_of_a_class_that_inherits_the_workflow_finds_it(tmp_path, rules):
    folder = copy_schema(tmp_path)
    edit(folder, "books.yaml", "  Shelf:\n", NOVEL)
    view = load_schema(folder / "library.yaml")
    workflows = Workflows([REVIEW], view, rules)
    assert workflows.for_class("Novel") is REVIEW, "the subclass follows the workflow of Book"
    assert workflows.for_iri(f"{LIB}Novel") is REVIEW, "by its IRI too"


async def test_a_book_of_a_subclass_takes_no_state_through_a_plain_write(tmp_path, rules):
    folder = copy_schema(tmp_path)
    edit(folder, "books.yaml", "  Shelf:\n", NOVEL)
    workflows = Workflows([REVIEW], load_schema(folder / "library.yaml"), rules)
    novel = URIRef(book_iri(5))
    triples = [
        (novel, RDF.type, URIRef(f"{LIB}Novel")),
        (novel, v.WORKFLOW_STATUS, URIRef(ACCEPTED)),
    ]
    async with fake_session(tenant_iri=TENANT) as session:
        with pytest.raises(Forbidden):
            await workflows.keep_state(session, str(novel), triples, None, None)


async def test_a_subclass_inherits_the_workflow_through_a_guarded_session_and_a_transition(
    tmp_path, rules, store, now
):  # PD-32 item 8, L2 W5. The toy has no generated Novel model: the raw triples stand for it.
    folder = copy_schema(tmp_path)
    edit(folder, "books.yaml", "  Shelf:\n", NOVEL)
    view = load_schema(folder / "library.yaml")
    flows = Workflows([REVIEW], view, rules)
    guards = WriteGuards(toy_mapper(), generated_models(*MODULES), Listings(view), flows)
    novel = book_iri(5)
    own = [(URIRef(novel), RDF.type, URIRef(f"{LIB}Novel"))]
    async with fake_session(
        store,
        tenant_iri=TENANT,
        principal=Principal(id=ADA),
        clock=lambda: now["t"],
        guards=guards,
        dependents=built.combined(view),
    ) as session:
        await session.add_graph(novel, own)
        assert await status_of(session, novel) == [DRAFT], "the novel starts in the initial state"
        with pytest.raises(Forbidden):
            await session.replace_graph(
                novel,
                [*own, (URIRef(novel), v.WORKFLOW_STATUS, URIRef(ACCEPTED))],
                await version(session, novel),
            )
        who = built.collab(rules, session, ADA, role("librarian"), view=view)
        await who.transition(novel, "in_review", if_version=await version(session, novel))
        assert await status_of(session, novel) == [IN_REVIEW], "the transition found the workflow"
        [record] = await who.transitions(novel)
        assert (record.from_state_iri, record.to_state_iri) == (DRAFT, IN_REVIEW), "and recorded it"


@pytest.mark.parametrize("target", [TENANT, "https://example.org/elsewhere", EVIL, ""])
async def test_the_tenant_and_a_foreign_iri_are_documented_errors_for_transition(
    rules, session, ada, books, target
):
    with pytest.raises((NotFound, InvalidBody, InvalidIri)):
        await ada.transition(target, "in_review", if_version="x")
    assert await status_of(session, B1) == [DRAFT], "nothing changed"


async def test_a_comment_and_a_record_are_under_no_workflow(session, ada, books):
    await go(ada, session, "in_review", comment="ready")
    [record] = await ada.transitions(B1)
    for target in (record.id, record.transition_comment):
        with pytest.raises(InvalidBody, match="workflow"):
            await ada.transition(target, "in_review", if_version=await version(session, target))
    assert len(await ada.transitions(B1)) == 1, "no second record"
    assert len(await ada.thread(B1)) == 1, "no second comment"


async def test_the_records_of_a_comment_or_a_record_are_none(session, ada, books):
    await go(ada, session, "in_review", comment="ready")
    [record] = await ada.transitions(B1)
    assert await ada.transitions(record.id) == [], "a record has no moves"
    assert await ada.transitions(record.transition_comment) == [], "nor a comment"


# -- 4. the transaction under refusals and concurrent writers (PD-15, PD-20, spec "nothing SHALL change")


async def refuse_for_a_stale_version(ada, session):
    with pytest.raises(Conflict):
        await ada.transition(B1, "in_review", if_version="stale", comment="ready")


async def refuse_for_a_missing_role(rules, session):
    with pytest.raises(Forbidden):
        await go(reader_of(rules, session), session, "in_review", comment="ready")


async def refuse_for_a_missing_edge(ada, session):
    with pytest.raises(Conflict):
        await go(ada, session, "accepted", comment="ready")


async def refuse_for_a_missing_comment(ada, session):
    await go(ada, session, "in_review")
    with pytest.raises(InvalidBody):
        await go(ada, session, "draft")


async def refuse_for_a_failed_store(ada, session):
    session._store.on("update", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await go(ada, session, "in_review", comment="ready")


REFUSALS = [
    pytest.param(lambda r, a, s: refuse_for_a_stale_version(a, s), id="stale-version"),
    pytest.param(lambda r, a, s: refuse_for_a_missing_role(r, s), id="missing-role"),
    pytest.param(lambda r, a, s: refuse_for_a_missing_edge(a, s), id="missing-edge"),
    pytest.param(lambda r, a, s: refuse_for_a_missing_comment(a, s), id="missing-comment"),
    pytest.param(lambda r, a, s: refuse_for_a_failed_store(a, s), id="store-failure"),
]


@pytest.mark.parametrize("refuse", REFUSALS)
async def test_after_a_refused_transition_nothing_is_left(
    store, rules, session, ada, books, refuse
):
    before_it = await snapshot(session, store)
    await refuse(rules, ada, session)
    after_it = await snapshot(session, store)
    if after_it[0] == [IN_REVIEW]:  # the refusal came after a first move: compare to that one
        assert (len(after_it[2]), after_it[5]) == (1, False), "one record and no marker"
        return
    assert after_it == before_it, "state, version, records, thread, count and marker are as before"


async def test_two_moves_from_one_version_keep_the_winners_comment_only(
    store, now, rules, session, ada, books
):
    stale = await version(session, B1)
    async with opened(store, now, BOB, rules) as other:
        rival = make(rules, other, BOB, [role("librarian", who=BOB)])

        async def rival_moves():
            await rival.transition(B1, "in_review", if_version=stale, comment="first")

        before(store, "update", rival_moves)
        with pytest.raises(Conflict):
            await ada.transition(B1, "in_review", if_version=stale, comment="second")
    assert [c.body_value for c in await ada.thread(B1)] == ["first"], "the thread has the winner's"
    assert len(await records_of(session, B1)) == 1, "exactly one record"
    assert await aggregates(store) == 4, "two books, one record and one comment"
    assert not await marker_left(session), "no marker"


async def test_a_transition_racing_a_plain_replace_loses_and_leaves_nothing(
    store, now, rules, session, ada, books
):
    stale = await version(session, B1)
    async with opened(store, now, BOB, rules) as other:

        async def rival_edits():
            edited = dune(B1, chapters=1)
            edited.label = "Dune again"
            await other.replace_graph(B1, toy_mapper().to_triples(edited), stale)

        before(store, "update", rival_edits)
        with pytest.raises(Conflict):
            await ada.transition(B1, "in_review", if_version=stale, comment="ready")
    assert await status_of(session, B1) == [DRAFT], "still in draft"
    assert (await records_of(session, B1), await comments_on(session, B1)) == ([], []), "nothing"
    assert not await marker_left(session), "no marker"


async def test_a_transition_racing_a_remove_leaves_no_orphan_record_or_comment(
    store, now, rules, session, ada, books
):
    await session.remove(B2, await version(session, B2))
    stale = await version(session, B1)
    async with opened(store, now, BOB, rules) as other:

        async def rival_removes():
            await other.remove(B1, stale)

        before(store, "update", rival_removes)
        with pytest.raises(Conflict):
            await ada.transition(B1, "in_review", if_version=stale, comment="ready")
    assert await aggregates(store) == 0, "no book, no record, no comment"
    assert not await marker_left(session), "no marker"


async def test_a_transition_racing_a_cascade_that_holds_the_book_leaves_no_orphan(
    store, now, rules, session, ada, books
):
    await session.remove(B2, await version(session, B2))
    await put(session, shelf(S1).model_copy(update={"had_member": [B1]}))
    stale = await version(session, B1)
    async with opened(store, now, BOB, rules) as other:
        rival = make(rules, other, BOB, [role("librarian", who=BOB)])

        async def rival_cascades():
            await rival.delete_cascade(S1, await version(other, S1))

        before(store, "update", rival_cascades)
        with pytest.raises(Conflict):
            await ada.transition(B1, "in_review", if_version=stale, comment="ready")
    assert await aggregates(store) == 0, "no shelf, book, record or comment"
    assert not await marker_left(session), "no marker"


async def test_a_comment_posted_while_a_transition_runs_stays_in_the_thread(
    store, now, rules, session, ada, books
):
    stale = await version(session, B1)
    async with opened(store, now, BOB, rules) as other:
        remarker = make(rules, other, BOB, [direct(Action.ANNOTATE, who=BOB)])

        async def remark():
            await remarker.comment(B1, "meanwhile")

        before(store, "update", remark)
        await ada.transition(B1, "in_review", if_version=stale, comment="ready")
    assert sorted(c.body_value for c in await ada.thread(B1)) == ["meanwhile", "ready"], (
        "both comments are in the thread"
    )
    assert len(await records_of(session, B1)) == 1, "one record"


@pytest.mark.parametrize("text", ["", "  ", "\n\t "])
async def test_a_blank_comment_on_a_move_that_needs_none_stores_no_blank_comment(
    session, ada, books, text
):
    await go(ada, session, "in_review", comment=text)
    blank = [c for c in await ada.thread(B1) if not c.body_value.strip()]
    assert blank == [], "the thread of a book holds no comment without text"


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("x" * 20_000, id="long"),
        pytest.param(EVIL, id="sparql-fragments"),
        pytest.param("line one\r\nline two\n\n\ttabbed \\ \"quoted\" 'single'", id="newlines"),
        pytest.param("naïve ☃ 日本語 \U0001f600", id="unicode"),
    ],
)
async def test_a_comment_is_stored_and_read_back_exactly_and_touches_nothing_else(
    store, session, ada, books, text
):
    await go(ada, session, "in_review", comment=text)
    [posted] = await ada.thread(B1)
    assert posted.body_value == text, "the text is exactly what was given"
    assert await aggregates(store) == 4, "two books, one record, one comment"


# -- 5. the records (spec "recorded as provenance", PD-21, D-9 item 4) ---------------------------


async def test_the_records_are_oldest_first_whatever_the_order_they_were_made_in(
    now, session, ada, books
):
    await go(ada, session, "in_review")
    now["t"] = T0 - timedelta(hours=1)
    await go(ada, session, "accepted")
    times = [r.started_at_time for r in await ada.transitions(B1)]
    assert times == sorted(times), "ordered by time, not by when they were stored"
    assert times[0] < times[1], "the earlier time first"


async def test_records_of_one_time_are_ordered_by_iri(session, ada, books):
    await go(ada, session, "in_review")
    await go(ada, session, "draft", comment="back")
    await go(ada, session, "in_review")
    ids = [r.id for r in await ada.transitions(B1)]
    assert len(ids) == 3, "three records"
    assert ids == sorted(ids), "the clock stood still, so the IRIs order them"


async def test_the_records_of_a_book_are_its_own(session, ada, books):
    await go(ada, session, "in_review")
    await go(ada, session, "in_review", B2)
    await go(ada, session, "accepted", B2)
    assert (len(await ada.transitions(B1)), len(await ada.transitions(B2))) == (1, 2), (
        "one move of b1, two of b2"
    )
    assert {r.used_resource for r in await ada.transitions(B2)} == {B2}, "only the moves of b2"


async def test_the_agent_of_a_record_is_the_principal_of_the_session(rules, session, books):
    other_caller = make(rules, session, BOB, [role("librarian", who=BOB)])
    await go(other_caller, session, "in_review")
    [record] = await other_caller.transitions(B1)
    assert record.was_associated_with == [ADA], (
        "the session's principal, not the caller's name"
    )  # pinned


@pytest.mark.parametrize("policy", ["default", "flat"])
async def test_no_generic_route_reads_replaces_or_deletes_a_record(policy):
    from rdf_persistence.domain.generated.service.rp_service import IriPolicy

    flat = IriPolicy(aggregate_template="{tenant}/{id}") if policy == "flat" else None
    service = ToyService(iri_policy=flat)
    async with service.app.router.lifespan_context(service.app), service.client() as http:
        scene = await Scene.set_up(service, http)
        record, version_of_record = await a_record(service, scene)
        headers = {**scene.headers("ada"), "If-Match": f'"{version_of_record}"'}
        answers = [
            (
                await http.get(f"{scene.tenant}/{path}/{record}", headers=scene.headers("ada"))
            ).status_code
            for path in ("books", "shelves", "rp-transitions")
        ]
        answers += [
            (
                await http.put(f"{scene.tenant}/books/{record}", json=DUNE_BODY, headers=headers)
            ).status_code,
            (await http.delete(f"{scene.tenant}/books/{record}", headers=headers)).status_code,
        ]
        assert answers == [404] * 5, f"every route answers 404: {answers}"
        async with service.kit.session(scene.tenant_iri, principal_of("ada")) as session:
            _, _, kept = await session.get_graph(scene.record_iri)
        assert kept == version_of_record, "the record is as it was"


async def a_record(service: ToyService, scene: Scene) -> tuple[str, str]:
    """One move of the scene's book made the way the kit makes it: ``(the record's id in a path, its version)``."""
    kit, who = service.kit, principal_of("ada")
    grant = Grant(assignee=who, target=scene.tenant_iri, role="librarian")
    access = CallerAccess(tenant=scene.tenant_iri, state=TenantState.ACTIVE, grants=[grant])
    async with kit.session(scene.tenant_iri, who) as session:
        moves = Collaboration(
            session,
            view=kit.view,
            rules=kit.rules,
            iris=kit.iris,
            mapper=kit.mapper,
            models=kit.models,
            listings=kit.listings,
            workflows=kit.workflows,
            caller=caller(principal=who),
            access=access,
        )
        await moves.transition(
            scene.book_iri, "in_review", if_version=(await session.get_graph(scene.book_iri))[2]
        )
        [record] = await moves.transitions(scene.book_iri)
        scene.record_iri = record.id
        return record.id.rsplit("/", 1)[1], (await session.get_graph(record.id))[2]


async def test_the_generic_delete_of_a_book_removes_its_records_and_comments(toy):
    scene = toy
    await a_record(scene.service, scene)
    gone = await scene.http.delete(
        scene.book,
        headers=scene.headers(
            "ada",
            **{
                "If-Match": (
                    await scene.http.get(scene.book, headers=scene.headers("ada"))
                ).headers["etag"]
            },
        ),
    )
    assert gone.status_code == 204, gone.text
    async with scene.service.kit.session(scene.tenant_iri, principal_of("ada")) as session:
        assert await session.graphs_with(v.USED, URIRef(scene.book_iri)) == {}, "no record is left"


@pytest.mark.parametrize("path", ["session", "transaction", "unit-of-work", "cascade"])
async def test_removing_a_book_removes_its_records_and_comments_through_every_path(
    store, session, ada, books, path
):
    await go(ada, session, "in_review", comment="ready")
    await session.remove(B2, await version(session, B2))
    stored = await version(session, B1)
    if path == "session":
        await session.remove(B1, stored)
    elif path == "transaction":
        async with session.transaction() as transaction:
            await transaction.remove(B1, stored)
    elif path == "unit-of-work":
        work = UnitOfWork(session, toy_mapper())
        work.remove(await work.get(type(dune(B1)), B1))
        await work.commit()
    else:
        await put(session, shelf(S1).model_copy(update={"had_member": [B1]}))
        await ada.delete_cascade(S1, await version(session, S1))
    assert await aggregates(store) == 0, "no book, record, comment or shelf is left"


async def test_a_record_is_no_member_class_and_no_member_of_a_collection(session, ada, books):
    await go(ada, session, "in_review")
    [record] = await ada.transitions(B1)
    for slots in ({"member_class": "TransitionRecord"}, {"had_member": [record.id]}):
        with pytest.raises(InvalidBody):
            await put(session, shelf(S1).model_copy(update=slots))
    assert not await session.heads([S1]), "no shelf was stored"


async def test_what_the_referrers_of_the_comment_of_a_move_show(session, ada, bob, books):  # pinned
    await go(ada, session, "in_review", comment="ready")
    [record] = await ada.transitions(B1)
    comment = record.transition_comment
    for who in (ada, bob):
        shown = await who.referrers(comment)
        listed = [r.referrer for r in shown.referrers or []]
        assert listed == [record.id], f"the record that names the comment is its referrer: {listed}"


@pytest.mark.parametrize("extra", [[], [("p", "x")]], ids=["bare", "with-a-stray-triple"])
async def test_a_foreign_aggregate_typed_as_a_record_does_not_break_the_listing(
    plain, ada, session, books, extra
):
    await go(ada, session, "in_review")
    foreign = str(DEFAULT_IRIS.mint_aggregate(TENANT, "rp-transition", "rp-transitions"))
    triples = [
        (URIRef(foreign), RDF.type, v.TRANSITION_RECORD),
        (URIRef(foreign), v.USED, URIRef(B1)),
    ]
    triples += [(URIRef(foreign), URIRef(f"{LIB}{p}"), Literal(o)) for p, o in extra]
    await plain.add_graph(foreign, triples)
    records = await ada.transitions(B1)
    assert [r.id for r in records] != [], "the genuine record is listed"
    assert foreign not in {r.id for r in records}, "the malformed one is skipped"


@pytest.mark.parametrize(
    "stamp",
    ["2026-11-14T08:00:00", "not a time"],
    ids=["a-time-with-no-zone", "not-a-time"],
)
async def test_a_foreign_record_with_an_odd_time_does_not_break_the_listing(
    plain, ada, session, books, stamp
):
    await go(ada, session, "in_review")
    foreign = str(DEFAULT_IRIS.mint_aggregate(TENANT, "rp-transition", "rp-transitions"))
    record = TransitionRecord(
        id=foreign,
        used_resource=B1,
        from_state_iri=DRAFT,
        to_state_iri=IN_REVIEW,
        started_at_time=T0,
    )
    started = v.predicate("started_at_time")
    triples = [
        (s, p, Literal(stamp, datatype=XSD.dateTime) if p == started else o)
        for s, p, o in toy_mapper().to_triples(record)
    ]
    await plain.add_graph(foreign, triples)
    listed = await ada.transitions(B1)
    assert any(isinstance(r, TransitionRecord) for r in listed), (
        "a list, with no undocumented error"
    )


async def test_a_foreign_record_that_names_the_book_goes_with_it(store, plain, session, ada, books):
    """Pinned: a malformed record typed as one and naming the book is dropped with the book, as a record is."""
    foreign = str(DEFAULT_IRIS.mint_aggregate(TENANT, "rp-transition", "rp-transitions"))
    await plain.add_graph(
        foreign,
        [(URIRef(foreign), RDF.type, v.TRANSITION_RECORD), (URIRef(foreign), v.USED, URIRef(B1))],
    )
    await session.remove(B1, await version(session, B1))
    assert not await session.heads([foreign]), "the foreign record went with the book"


async def test_an_aggregate_of_another_class_that_names_the_book_with_prov_used_stays(
    plain, session, ada, books
):
    await put(plain, shelf(S1))
    await plain.replace_graph(
        S1,
        [*toy_mapper().to_triples(shelf(S1)), (URIRef(S1), v.USED, URIRef(B1))],
        await version(plain, S1),
    )
    await session.remove(B1, await version(session, B1))
    assert await session.heads([S1]), "the shelf stays: only a record's link is dropped"


async def test_an_aggregate_of_another_class_that_links_to_the_book_with_prov_used_is_a_referrer(
    plain, ada, session, books
):  # PD-32 item 8, L2 W6
    await put(plain, shelf(S1))
    await plain.replace_graph(
        S1,
        [*toy_mapper().to_triples(shelf(S1)), (URIRef(S1), v.USED, URIRef(B1))],
        await version(plain, S1),
    )
    shown = await ada.referrers(B1)
    listed = {r.referrer: (r.referrer_class, r.referrer_slot) for r in shown.referrers or []}
    assert S1 in listed, f"the shelf is listed among the referrers of the book: {listed}"
    assert listed[S1][0] == "Shelf", f"as a shelf: {listed[S1]}"
    assert "used" in listed[S1][1], f"by the link it uses: {listed[S1]}"


# -- 6. workflow files, the kit and the hard rule (PD-17, PD-18, D-10, RISK-4) -------------------

BASE = {
    "id": "https://example.org/w/flow",
    "workflow_name": "flow",
    "workflow_states": ["a", "b"],
    "initial_state": "a",
    "workflow_transitions": [
        {"from_state": "a", "to_state": "b", "transition_roles": ["librarian"]}
    ],
}


def written(tmp_path: Path, **changes) -> Path:
    path = tmp_path / "flow.workflow.yaml"
    path.write_text(yaml.safe_dump({**BASE, **changes}))
    return path


def text_file(tmp_path: Path, text: str | bytes) -> Path:
    path = tmp_path / "flow.workflow.yaml"
    path.write_bytes(text if isinstance(text, bytes) else text.encode())
    return path


MOVE = {"from_state": "a", "to_state": "b", "transition_roles": ["librarian"]}
REFUSED_FILES = [
    pytest.param({"workflow_states": "a"}, id="states-a-string"),
    pytest.param(
        {"workflow_states": ["a/b"], "initial_state": "a/b", "workflow_transitions": []},
        id="a-state-with-a-slash",
    ),
    pytest.param(
        {"workflow_states": ["../x"], "initial_state": "../x", "workflow_transitions": []},
        id="a-state-that-climbs",
    ),
    pytest.param(
        {"workflow_states": ["A"], "initial_state": "A", "workflow_transitions": []},
        id="an-upper-case-state",
    ),
    pytest.param(
        {"workflow_states": ["a\n"], "initial_state": "a\n", "workflow_transitions": []},
        id="a-state-with-a-newline",
    ),
    pytest.param(
        {"workflow_states": [""], "initial_state": "", "workflow_transitions": []},
        id="an-empty-state",
    ),
    pytest.param({"workflow_states": ["a", "b", "a b"]}, id="a-state-with-a-space"),
    pytest.param({"workflow_transitions": {"a": "b"}}, id="transitions-a-mapping"),
    pytest.param(
        {"workflow_transitions": [{**MOVE, "transition_roles": "librarian"}]}, id="roles-a-string"
    ),
    pytest.param({"workflow_transitions": [{**MOVE, "transition_roles": None}]}, id="roles-none"),
    pytest.param(
        {"workflow_transitions": [{**MOVE, "comment_required": "maybe"}]},
        id="comment-required-maybe",
    ),
    pytest.param(
        {"workflow_transitions": [{**MOVE, "colour": "red"}]}, id="an-unknown-key-on-a-transition"
    ),
    pytest.param({"colour": "red"}, id="an-unknown-key"),
    pytest.param({"workflow_transition": [MOVE]}, id="a-misspelled-key"),
    pytest.param({"initial_state": 5}, id="initial-state-an-int"),
    pytest.param({"initial_state": None}, id="initial-state-none"),
    pytest.param({"workflow_name": "Flow"}, id="name-in-capitals"),
    pytest.param({"workflow_name": "a/b"}, id="name-with-a-slash"),
    pytest.param({"workflow_name": ""}, id="name-empty"),
    pytest.param({"id": None}, id="id-none"),
]


@pytest.mark.parametrize("changes", REFUSED_FILES)
def test_a_hostile_workflow_file_is_refused_naming_the_file(tmp_path, changes):
    path = written(tmp_path, **changes)
    with pytest.raises(InvalidWorkflow) as refused:
        load_workflow(path)
    assert str(path) in str(refused.value), "the message names the file"


RAW_FILES = [
    pytest.param("", id="empty"),
    pytest.param("# only a comment\n", id="only-a-comment"),
    pytest.param("---\n---\n", id="two-documents"),
    pytest.param("[]", id="an-empty-list"),
    pytest.param("just text", id="a-string"),
    pytest.param("id: &a [*a]\nworkflow_states: &b [*b]\n", id="a-recursive-alias"),
    pytest.param("id: !!python/object/apply:os.getcwd []\n", id="a-python-tag"),
    pytest.param(b"\xff\xfe\x00bad bytes", id="not-utf8"),
    pytest.param("id: a\x00b\n", id="a-nul-byte"),
    pytest.param("{" * 5000, id="deeply-nested-flow"),
]


@pytest.mark.parametrize("content", RAW_FILES)
def test_a_file_that_is_no_workflow_in_any_way_is_refused_naming_the_file(tmp_path, content):
    path = text_file(tmp_path, content)
    with pytest.raises(InvalidWorkflow) as refused:
        load_workflow(path)
    assert str(path) in str(refused.value), "the message names the file"


def test_a_directory_given_as_the_path_is_refused_naming_it(tmp_path):
    with pytest.raises(InvalidWorkflow, match=str(tmp_path)):
        load_workflow(tmp_path)


def test_a_workflow_file_with_yaml_anchors_is_read(tmp_path):
    text = (
        "id: https://example.org/w/flow\nworkflow_name: flow\nworkflow_states: [a, b]\n"
        "initial_state: a\nworkflow_transitions:\n"
        "  - {from_state: a, to_state: b, transition_roles: &r [librarian]}\n"
        "  - {from_state: b, to_state: a, transition_roles: *r}\n"
    )
    assert len(load_workflow(text_file(tmp_path, text)).workflow_transitions) == 2, "both edges"


ACCEPTED_FILES = [
    pytest.param({"workflow_transitions": [{**MOVE, "to_state": "a"}]}, id="a-self-edge"),
    pytest.param({"workflow_transitions": None}, id="no-transitions"),
]


@pytest.mark.parametrize("changes", ACCEPTED_FILES)
def test_pinned_a_file_the_model_does_not_refuse_is_loaded(tmp_path, changes):
    """Pinned: a file the model and PD-31 accept is loaded."""
    assert load_workflow(written(tmp_path, **changes)).workflow_name == "flow", "it is loaded"


REFUSED_BY_THE_LOADER = [  # PD-31 item 5, decided: these were pinned as loading
    pytest.param({"workflow_states": ["a", "a", "b"]}, "a", id="a-state-listed-twice"),
    pytest.param({"id": "https://example.org/w/flow/"}, "id", id="an-id-with-a-trailing-slash"),
    pytest.param(
        {"workflow_transitions": [{**MOVE, "transition_roles": []}]},
        "transition_roles",
        id="an-edge-with-no-roles",
    ),
]


@pytest.mark.parametrize(("changes", "element"), REFUSED_BY_THE_LOADER)
def test_a_file_with_a_repeated_state_a_slash_id_or_an_empty_role_list_is_refused(
    tmp_path, changes, element
):
    path = written(tmp_path, **changes)
    with pytest.raises(InvalidWorkflow) as refused:
        load_workflow(path)
    assert str(path) in str(refused.value), "the message names the file"
    assert element in str(refused.value), "and the element"


def test_a_huge_states_list_loads_and_is_checked_quickly(tmp_path, rules):
    names = [f"s{n}" for n in range(3000)]
    moves = [
        {"from_state": a, "to_state": b, "transition_roles": ["librarian"]}
        for a, b in zip(names, names[1:], strict=False)
    ]
    workflow = load_workflow(
        written(tmp_path, workflow_states=names, initial_state="s0", workflow_transitions=moves)
    )
    assert len(workflow.workflow_states) == 3000, "all the states"
    assert Workflows([workflow, REVIEW], VIEW, rules).for_class("Book") is REVIEW, (
        "the file of the book is the review one"
    )


BAD_IDS = [
    "",
    "flow",
    "has space",
    "https://example.org/w>",
    "https://example.org/w<",
    'https://example.org/w"',
    "https://example.org/w\n",
    "https://example.org/w\t",
]


@pytest.mark.parametrize("workflow_id", BAD_IDS)
def test_a_workflow_id_that_is_no_iri_is_refused_naming_the_file(tmp_path, workflow_id):
    """A state is the id, a slash and its name: an id that is no IRI makes states that are none."""
    path = written(tmp_path, id=workflow_id)
    with pytest.raises(InvalidWorkflow) as refused:
        load_workflow(path)
    assert str(path) in str(refused.value), "the message names the file"


def test_two_workflows_with_one_id_and_two_names_are_refused(rules):
    """Their states would be one scheme's concepts: the IRI of a state names no one workflow."""
    twin = REVIEW.model_copy(update={"workflow_name": "twin"})
    with pytest.raises(InvalidWorkflow, match="twin|review"):
        Workflows([REVIEW, twin], VIEW, rules)


def test_the_state_iri_of_a_name_with_the_workflow_id_is_unique_per_name():
    assert state_iri(REVIEW, "draft") != state_iri(REVIEW, "in_review"), "one IRI per name"


def test_a_kit_given_an_inconsistent_file_names_the_file(tmp_path):
    path = tmp_path / "ghost.workflow.yaml"
    path.write_text(REVIEW_WORKFLOW.read_text().replace("[librarian]", "[ghost]", 1))
    with pytest.raises(InvalidWorkflow) as refused:
        ToyService(workflows=(path,))
    assert str(path) in str(refused.value), "the file is named, not only the workflow"


def test_a_kit_given_one_file_twice_refuses_to_start_naming_the_workflow():
    with pytest.raises(InvalidWorkflow, match="review"):
        ToyService(workflows=(REVIEW_WORKFLOW, REVIEW_WORKFLOW))


def test_pinned_a_kit_given_a_file_no_class_uses_starts(tmp_path):
    extra = tmp_path / "unused.workflow.yaml"
    extra.write_text(
        REVIEW_WORKFLOW.read_text()
        .replace("workflow_name: review", "workflow_name: unused")
        .replace("workflows/review", "workflows/unused")
    )
    service = ToyService(workflows=(REVIEW_WORKFLOW, extra))
    assert service.kit.workflows.for_class("Book").workflow_name == "review", (
        "the book keeps its own"
    )


NOVEL = """  Novel:
    title: Novel
    description: A book of fiction.
    is_a: Book
    class_uri: lib:Novel
    annotations:
      rp_path: novels
  Shelf:
"""
MIXIN = """  Flagged:
    title: Flagged
    description: A mixin that names a workflow.
    mixin: true
    annotations:
      workflow: review
  Shelf:
"""
ABSTRACT_ROOT = """  Item:
    title: Item
    description: A base of the items.
    abstract: true
    class_uri: lib:Item
    mixins: [AggregateRoot, Described, Tracked, UnderWorkflow]
    annotations:
      rp_path: items
      database: tenant
      workflow: review
  Novel:
    title: Novel
    description: A concrete item.
    is_a: Item
    class_uri: lib:Novel
    annotations:
      rp_path: novels
      database: tenant
  Shelf:
"""
OVERRIDE = "      workflow: other\n"


def copy_schema(tmp_path: Path) -> Path:
    folder = tmp_path / "library"
    shutil.copytree(
        TOY_SCHEMA.parent, folder, ignore=shutil.ignore_patterns("__pycache__", "generated")
    )
    return folder


def edit(folder: Path, module: str, old: str, new: str) -> None:
    text = (folder / module).read_text(encoding="utf-8")
    assert old in text, f"{old!r} is not in {module}"
    (folder / module).write_text(text.replace(old, new, 1), encoding="utf-8")


def workflow_problems(folder: Path) -> list[str]:
    found = (format_problem(p) for p in hard_problems(load_schema(folder / "library.yaml"), folder))
    return [p for p in found if f"[{HardRule.WORKFLOW.value}]" in p]


def test_a_mixin_that_names_a_workflow_is_a_hard_problem(tmp_path):
    folder = copy_schema(tmp_path)
    edit(folder, "books.yaml", "  Shelf:\n", MIXIN)
    assert any("Flagged" in p for p in workflow_problems(folder)), "the mixin is named"


def test_an_abstract_root_with_a_workflow_and_a_concrete_subclass_is_no_problem(tmp_path, rules):
    folder = copy_schema(tmp_path)
    edit(folder, "books.yaml", "  Shelf:\n", ABSTRACT_ROOT)
    assert workflow_problems(folder) == [], "D-10 item 4: the base may name it"
    workflows = Workflows([REVIEW], load_schema(folder / "library.yaml"), rules)
    assert workflows.for_class("Novel") is REVIEW, "the concrete class inherits it"


def test_pinned_a_subclass_that_names_another_workflow_follows_that_one(tmp_path, rules):
    folder = copy_schema(tmp_path)
    edit(
        folder,
        "books.yaml",
        "  Shelf:\n",
        NOVEL.replace("      rp_path: novels\n", "      rp_path: novels\n" + OVERRIDE),
    )
    assert workflow_problems(folder) == [], "the hard rule has nothing to say about it"
    view = load_schema(folder / "library.yaml")
    other = REVIEW.model_copy(
        update={"workflow_name": "other", "id": "https://example.org/w/other"}
    )
    workflows = Workflows([REVIEW, other], view, rules)
    assert workflows.for_class("Novel") is other, "its own annotation wins over its parent's"
    assert workflows.for_class("Book") is REVIEW, "the parent keeps its own"


def test_a_subclass_that_names_a_workflow_no_file_defines_refuses_the_kit(tmp_path, rules):
    folder = copy_schema(tmp_path)
    edit(
        folder,
        "books.yaml",
        "  Shelf:\n",
        NOVEL.replace("      rp_path: novels\n", "      rp_path: novels\n" + OVERRIDE),
    )
    with pytest.raises(InvalidWorkflow, match="Novel"):
        Workflows([REVIEW], load_schema(folder / "library.yaml"), rules)

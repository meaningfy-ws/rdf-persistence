"""WriteGuards: the collection rule on the write path (PD-6, TC-15 to TC-20, TC-22)."""

import inspect

import pytest
from linkml_runtime.linkml_model import SchemaDefinition
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import RDF, URIRef

from rdf_persistence import (
    AccessRules,
    Forbidden,
    InvalidBody,
    InvalidIri,
    NotFound,
    generated_models,
    load_role_definitions,
)
from rdf_persistence.domain.generated.rp_annotations import Tracked
from rdf_persistence.domain.generated.rp_collections import MembershipRule, SlotEquality
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.reference_collections import member_class_iris
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.session import Session, Transaction
from rdf_persistence.services.workflows import Workflows, load_workflow, state_iri
from rdf_persistence.services.write_guards import WriteGuards
from rdf_persistence.testkit import FakeStore, fake_session
from tests.fixtures.library.generated.books import Book
from tests.toy import (
    MODULES,
    REVIEW_WORKFLOW,
    ROLES,
    TENANT,
    TOY_SCHEMA,
    book_iri,
    dune,
    shelf,
    shelf_iri,
    toy_mapper,
)
from tests.unit.services.test_collaboration_workflow_adversarial import copy_schema, edit

ELSEWHERE = "https://elsewhere.org/b"
REVIEW = load_workflow(REVIEW_WORKFLOW)
DRAFT, IN_REVIEW, ACCEPTED = (state_iri(REVIEW, s) for s in ("draft", "in_review", "accepted"))


def guards(*, workflows: bool = False) -> WriteGuards:
    view = load_schema(TOY_SCHEMA)
    kept = (
        Workflows([REVIEW], view, AccessRules(load_role_definitions(ROLES))) if workflows else None
    )
    return WriteGuards(toy_mapper(), generated_models(*MODULES), Listings(view), kept)


def rule(slot: str, value: str) -> MembershipRule:
    return MembershipRule(rule_equalities=[SlotEquality(equals_slot=slot, equals_value=value)])


def a_shelf(n: int = 1, **slots):
    return shelf(shelf_iri(n)).model_copy(update=slots)


async def save(session, *objects) -> None:
    work = UnitOfWork(session, toy_mapper())
    for obj in objects:
        work.add(obj)
    await work.commit()


async def version_of(session, iri: str) -> str:
    return (await session.get_graph(iri))[2]


async def test_a_collection_of_stored_books_is_saved_and_its_members_are_untouched():  # TC-15
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, dune(book_iri(1)), dune(book_iri(2)))
        before = [await version_of(session, book_iri(n)) for n in (1, 2)]
        await save(session, a_shelf(had_member=[book_iri(1), book_iri(2)]))
        assert await version_of(session, shelf_iri(1)), "the shelf is stored"
        assert before == [await version_of(session, book_iri(n)) for n in (1, 2)], "books untouched"


BAD_BODY = [
    pytest.param({"had_member": [shelf_iri(2)]}, shelf_iri(2), id="TC-16-another-class"),
    pytest.param({"had_member": [book_iri(99)]}, book_iri(99), id="TC-17-never-stored"),
    pytest.param({"member_class": "Chapter"}, "Chapter", id="TC-19-not-a-served-root"),
    pytest.param({"member_class": "Comment"}, "Comment", id="D-7-a-comment-is-no-member-class"),
    pytest.param({"membership_rule": rule("colour", "red")}, "colour", id="TC-20-unknown-slot"),
    pytest.param({"membership_rule": rule("genre", "haiku")}, "haiku", id="TC-20-bad-value"),
]


@pytest.mark.parametrize(("slots", "named"), BAD_BODY)
async def test_a_collection_that_breaks_a_rule_is_refused_naming_it_and_not_stored(slots, named):
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, a_shelf(2))  # a shelf, not a book
        with pytest.raises(InvalidBody, match=named):
            await save(session, a_shelf(**slots))
        with pytest.raises(NotFound):
            await session.get_graph(shelf_iri(1))


async def test_every_member_that_is_not_of_the_class_is_named():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, dune(book_iri(1)), a_shelf(2))
        with pytest.raises(InvalidBody) as refused:
            await save(session, a_shelf(had_member=[book_iri(1), shelf_iri(2), book_iri(99)]))
        assert shelf_iri(2) in str(refused.value), "the shelf is not a book"
        assert book_iri(99) in str(refused.value), "b99 was never stored"
        assert book_iri(1) not in str(refused.value), "b1 is a member of the class"


async def test_a_member_the_tenant_does_not_mint_is_an_invalid_iri():  # TC-18
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        with pytest.raises(InvalidIri, match=ELSEWHERE):
            await save(session, a_shelf(had_member=[ELSEWHERE]))
        with pytest.raises(NotFound):
            await session.get_graph(shelf_iri(1))


@pytest.mark.parametrize(
    "slots",
    [
        {"membership_rule": rule("genre", "poetry")},
        {"membership_rule": MembershipRule()},
        {"member_class": "Shelf", "had_member": [shelf_iri(2)]},
    ],
    ids=["rule", "empty-rule", "collection-of-collections"],
)
async def test_a_valid_rule_or_collection_of_collections_is_saved(slots):
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, a_shelf(2))
        await save(session, a_shelf(**slots))
        assert await version_of(session, shelf_iri(1)), "the shelf is stored"


async def test_a_session_without_guards_checks_nothing():  # TC-22
    async with fake_session(tenant_iri=TENANT) as session:
        await save(session, a_shelf(2))
        await save(session, a_shelf(had_member=[shelf_iri(2)]))
        assert await version_of(session, shelf_iri(1)), "the shelf of shelves is stored"


async def test_a_replace_of_a_collection_is_guarded_like_an_add():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, dune(book_iri(1)), a_shelf(2))
        await save(session, a_shelf(had_member=[book_iri(1)]))
        kept = await version_of(session, shelf_iri(1))
        work = UnitOfWork(session, toy_mapper())
        stored = await work.get(type(a_shelf()), shelf_iri(1))
        work.add(stored.model_copy(update={"had_member": [shelf_iri(2)]}))
        with pytest.raises(InvalidBody, match=shelf_iri(2)):
            await work.commit()
        assert await version_of(session, shelf_iri(1)) == kept, "the shelf is as it was"


async def test_a_book_through_a_guarded_session_costs_no_extra_query():
    queries = []
    for guarded in (None, guards()):
        store = FakeStore()
        async with fake_session(store, tenant_iri=TENANT, guards=guarded) as session:
            await save(session, dune(book_iri(1)))
        queries.append(len(store.sent("query")))
    assert queries[0] == queries[1], "the same number of queries with and without guards"


async def test_the_guard_leaves_a_non_collection_untouched():
    triples = list(toy_mapper().to_triples(dune(book_iri(1))))
    async with fake_session(tenant_iri=TENANT) as session:
        prepared = await guards().prepare(session, book_iri(1), triples, None, None)
        assert prepared == triples, "the triples of a book are written as they are"


def test_the_classes_of_a_member_class_are_it_and_its_descendants():  # PD-27: no root subclass in the toy
    view = load_schema(TOY_SCHEMA)
    lib = "https://example.org/ns/library#"
    assert member_class_iris(view, "Shelf") == {f"{lib}Shelf"}, "a class with no subclass"
    assert f"{lib}LibraryAccess" in member_class_iris(view, "TenantAccess"), (
        "a subclass is accepted"
    )


# The workflow rule (PD-19): only a transition changes the state of an aggregate.


def a_book(status: str | None = None, **slots) -> Book:
    return dune(book_iri(1)).model_copy(update={"workflow_status": status, **slots})


async def status_of(session, iri: str = book_iri(1)) -> str | None:
    return (await UnitOfWork(session, toy_mapper()).get(Book, iri)).workflow_status


async def replace_as(session, book: Book, *, allowing: str | None = None) -> None:
    """Replace the stored book by ``book`` in one transaction; ``allowing`` is what only a transition does."""
    version = await version_of(session, str(book.id))
    async with session.transaction() as t:
        if allowing is not None:
            t._allow_state(str(book.id), allowing)
        await t.replace_graph(str(book.id), toy_mapper().to_triples(book), version)


async def test_a_book_added_without_a_status_starts_in_the_initial_state():  # TC-76
    async with fake_session(tenant_iri=TENANT, guards=guards(workflows=True)) as session:
        await save(session, a_book())
        assert await status_of(session) == DRAFT, "the initial state is set"


async def test_a_book_added_in_the_initial_state_is_kept_there():
    async with fake_session(tenant_iri=TENANT, guards=guards(workflows=True)) as session:
        await save(session, a_book(DRAFT))
        assert await status_of(session) == DRAFT, "the initial state passes"


async def test_a_book_added_in_another_state_is_refused_and_not_stored():  # TC-77
    async with fake_session(tenant_iri=TENANT, guards=guards(workflows=True)) as session:
        with pytest.raises(Forbidden, match="only by a transition"):
            await save(session, a_book(ACCEPTED))
        with pytest.raises(NotFound):
            await session.get_graph(book_iri(1))


async def test_a_replace_in_another_state_is_refused_and_the_book_stays():  # TC-78
    async with fake_session(tenant_iri=TENANT, guards=guards(workflows=True)) as session:
        await save(session, a_book())
        with pytest.raises(Forbidden, match="only by a transition"):
            await save_over(session, workflow_status=ACCEPTED)
        assert await status_of(session) == DRAFT, "the book stays in draft"


async def save_over(session, **slots) -> None:
    """Replace the stored book by itself with ``slots`` changed, through the unit of work."""
    work = UnitOfWork(session, toy_mapper())
    work.add((await work.get(Book, book_iri(1))).model_copy(update=slots))
    await work.commit()


async def test_a_replace_without_a_status_keeps_the_stored_one():  # TC-79
    async with fake_session(tenant_iri=TENANT, guards=guards(workflows=True)) as session:
        await save(session, a_book())
        await save_over(session, label="Dune II", workflow_status=None)
        assert await status_of(session) == DRAFT, "the stored state is kept"
        stored = await UnitOfWork(session, toy_mapper()).get(Book, book_iri(1))
        assert stored.label == "Dune II", "the rest of the write is applied"


async def test_a_replace_that_repeats_the_stored_state_passes():
    async with fake_session(tenant_iri=TENANT, guards=guards(workflows=True)) as session:
        await save(session, a_book())
        await save_over(session, label="Dune II")
        assert await status_of(session) == DRAFT, "the state is unchanged"


async def test_a_transaction_that_allows_the_state_may_set_it():  # TC-80
    async with fake_session(tenant_iri=TENANT, guards=guards(workflows=True)) as session:
        await save(session, a_book())
        await replace_as(session, a_book(ACCEPTED), allowing=ACCEPTED)
        assert await status_of(session) == ACCEPTED, "the allowed state is set"


async def test_a_transaction_allows_one_state_for_one_book_only():
    async with fake_session(tenant_iri=TENANT, guards=guards(workflows=True)) as session:
        await save(session, a_book())
        with pytest.raises(Forbidden):
            await replace_as(session, a_book(ACCEPTED), allowing=IN_REVIEW)
        assert await status_of(session) == DRAFT, "another state than the allowed one is refused"


async def test_a_transaction_without_the_allowance_refuses_a_state_change():  # TC-80a
    async with fake_session(tenant_iri=TENANT, guards=guards(workflows=True)) as session:
        await save(session, a_book())
        with pytest.raises(Forbidden):
            await replace_as(session, a_book(ACCEPTED))
        assert await status_of(session) == DRAFT, "the book stays in draft"


async def test_a_transaction_that_has_ended_takes_no_allowance():
    async with fake_session(tenant_iri=TENANT, guards=guards(workflows=True)) as session:
        async with session.transaction() as t:
            pass
        with pytest.raises(RuntimeError, match="ended"):
            t._allow_state(book_iri(1), ACCEPTED)


PUBLIC_CALLS = [
    Session.transaction,
    Session.add_graph,
    Session.replace_graph,
    Transaction.add_graph,
    Transaction.replace_graph,
    UnitOfWork.commit,
    UnitOfWork.add,
]


@pytest.mark.parametrize("call", PUBLIC_CALLS, ids=lambda c: c.__qualname__)
def test_no_public_argument_allows_a_state(call):  # TC-80a
    names = set(inspect.signature(call).parameters)
    assert not {n for n in names if "state" in n or "allow" in n}, f"{names} lets a caller set one"


async def test_a_stored_book_with_no_state_stays_without_one_until_a_transition():  # PD-22
    store = FakeStore()
    async with fake_session(store, tenant_iri=TENANT) as plain:
        await save(plain, a_book())  # stored before its class named the workflow
    async with fake_session(store, tenant_iri=TENANT, guards=guards(workflows=True)) as session:
        await save_over(session, label="Dune II")
        assert await status_of(session) is None, "absent stays absent"
        with pytest.raises(Forbidden):
            await save_over(session, workflow_status=ACCEPTED)
        await replace_as(session, a_book(IN_REVIEW, label="Dune II"), allowing=IN_REVIEW)
        assert await status_of(session) == IN_REVIEW, "the first transition sets a state"


async def test_a_stored_state_the_workflow_no_longer_lists_stays_readable_and_writable():  # PD-22
    gone = state_iri(REVIEW, "archived")
    store = FakeStore()
    async with fake_session(store, tenant_iri=TENANT) as plain:
        await save(plain, a_book(gone))
    async with fake_session(store, tenant_iri=TENANT, guards=guards(workflows=True)) as session:
        await save_over(session, label="Dune II")
        assert await status_of(session) == gone, "the stored state is read as stored"
        await save_over(session, label="Dune III", workflow_status=gone)
        assert await status_of(session) == gone, "and repeated, it passes"


async def queries_of(guarded: WriteGuards, *objects, then=None) -> int:
    store = FakeStore()
    async with fake_session(store, tenant_iri=TENANT, guards=guarded) as session:
        await save(session, *objects)
        if then:
            await then(session)
    return len(store.sent("query"))


async def rename_shelf(session) -> None:
    work = UnitOfWork(session, toy_mapper())
    work.add((await work.get(type(a_shelf()), shelf_iri(1))).model_copy(update={"label": "New"}))
    await work.commit()


# TC-81. PD-31 item 1: the workflow of a replace is that of the stored root, so a replace of any
# class costs one read in a service with workflows. Before, a shelf cost none (the class of the
# written triples decided); an add cost none and a book's replace one, as now.
async def test_a_replace_of_any_class_costs_one_more_read_when_workflows_are_configured():
    plain = await queries_of(guards(), a_shelf(), then=rename_shelf)
    flowing = await queries_of(guards(workflows=True), a_shelf(), then=rename_shelf)
    assert flowing == plain + 1, "a shelf is read once more, for its stored types and state"


async def test_an_add_costs_no_extra_query_and_a_book_replace_one_small_select():
    assert await queries_of(guards(workflows=True), a_book()) == await queries_of(
        guards(), a_book()
    ), "an add reads nothing more"
    plain = await queries_of(guards(), a_book(), then=lambda s: save_over(s, label="x"))
    flowing = await queries_of(
        guards(workflows=True), a_book(), then=lambda s: save_over(s, label="x")
    )
    assert flowing == plain + 1, "a replace reads the stored types and state once"


async def test_a_service_with_no_workflow_loaded_costs_no_extra_query():
    rules = AccessRules(load_role_definitions(ROLES))
    nothing = Workflows([], SchemaView(SchemaDefinition(id="https://x.org/s", name="s")), rules)
    empty = WriteGuards(
        toy_mapper(), generated_models(*MODULES), Listings(load_schema(TOY_SCHEMA)), nothing
    )
    unguarded = await queries_of(guards(), a_shelf(), then=rename_shelf)
    assert await queries_of(empty, a_shelf(), then=rename_shelf) == unguarded, (
        "workflows that no class follows read nothing more than guards with none"
    )


# The class rule of the workflow guard (PD-32 item 1). S is the workflow of the stored root's
# types, N that of the written ones. One row per cell of the decision table: the stored types and
# states, the written types and states, the one state the transaction allows, and what comes of it.

LIB = "https://example.org/ns/library#"
BOOK, NOVEL_CLASS, SHELF = (
    URIRef("http://purl.org/ontology/bibo/Book"),
    URIRef(f"{LIB}Novel"),
    URIRef(f"{LIB}Shelf"),
)
ROOT = book_iri(1)
OWN = "https://example.org/own/state"  # an application's own value of adms:status
OTHER_DRAFT = "https://example.org/w/other/draft"
FORBIDDEN = "forbidden"
NOVEL = (
    "  Novel:\n    title: Novel\n    description: A novel.\n    is_a: Book\n"
    "    class_uri: lib:Novel\n    annotations:\n      rp_path: novels\n"
    "      workflow: other\n  Shelf:\n"
)


@pytest.fixture(scope="module")
def flows(tmp_path_factory: pytest.TempPathFactory) -> Workflows:
    """``Book`` follows ``review``; ``Novel`` (a subclass) names ``other``; ``Shelf`` follows none."""
    folder = copy_schema(tmp_path_factory.mktemp("schema"))
    edit(folder, "books.yaml", "  Shelf:\n", NOVEL)
    other = REVIEW.model_copy(
        update={"workflow_name": "other", "id": "https://example.org/w/other"}
    )
    rules = AccessRules(load_role_definitions(ROLES))
    return Workflows([REVIEW, other], load_schema(folder / "library.yaml"), rules)


def triples_of(types: tuple[URIRef, ...], states: tuple[str, ...]) -> list:
    root = URIRef(ROOT)
    return [(root, RDF.type, t) for t in types] + [
        (root, v.WORKFLOW_STATUS, URIRef(s)) for s in states
    ]


def states_of(triples: list) -> set[str]:
    return {str(o) for _, p, o in triples if p == v.WORKFLOW_STATUS}


def no_status(triples: list) -> list:
    return [t for t in triples if t[1] != v.WORKFLOW_STATUS]


# add: (written types, written states, the states written or FORBIDDEN)
ADD_ROWS = [
    pytest.param((), (), set(), id="no-class-no-state-as-it-is"),
    pytest.param((), (OWN,), {OWN}, id="no-class-own-state-is-the-applications"),
    pytest.param((SHELF,), (OWN,), {OWN}, id="shelf-own-state-is-the-applications"),
    pytest.param((BOOK,), (), {DRAFT}, id="book-no-state-gets-the-initial-one"),
    pytest.param((BOOK,), (DRAFT,), {DRAFT}, id="book-initial-state-kept"),
    pytest.param((BOOK,), (ACCEPTED,), FORBIDDEN, id="book-another-state"),
    pytest.param((BOOK, SHELF), (ACCEPTED,), FORBIDDEN, id="book-and-shelf-another-state"),
    pytest.param((BOOK, NOVEL_CLASS), (), FORBIDDEN, id="two-workflows"),
    pytest.param((NOVEL_CLASS,), (), {OTHER_DRAFT}, id="novel-follows-its-own-workflow"),
]


@pytest.mark.parametrize(("written", "states", "expected"), ADD_ROWS)
async def test_the_decision_table_of_an_add(flows, written, states, expected):
    triples = triples_of(written, states)
    async with fake_session(tenant_iri=TENANT) as session:
        if expected == FORBIDDEN:
            with pytest.raises(Forbidden):
                await flows.keep_state(session, ROOT, triples, None, None)
            return
        result = await flows.keep_state(session, ROOT, triples, None, None)
    assert states_of(result) == expected, "the states written"
    assert no_status(result) == no_status(triples), "nothing else is touched"


# replace: (stored types, stored states, written types, written states, allowed, states written)
REPLACE_ROWS = [
    pytest.param((SHELF,), (), (SHELF,), (), None, set(), id="S-none-N-none-as-it-is"),
    pytest.param((SHELF,), (OWN,), (SHELF,), (), None, set(), id="S-none-N-none-own-state-dropped"),
    pytest.param((SHELF,), (), (SHELF,), (OWN,), None, {OWN}, id="S-none-N-none-own-state"),
    pytest.param((), (), (), (OWN,), None, {OWN}, id="no-class-either-side-own-state"),
    pytest.param((BOOK,), (DRAFT,), (), (), None, FORBIDDEN, id="S-wf-class-dropped"),
    pytest.param((BOOK,), (DRAFT,), (SHELF,), (ACCEPTED,), None, FORBIDDEN, id="S-wf-N-none"),
    pytest.param((BOOK,), (DRAFT,), (NOVEL_CLASS,), (), None, FORBIDDEN, id="S-wf-N-another-wf"),
    pytest.param((BOOK,), (DRAFT,), (BOOK, NOVEL_CLASS), (), None, FORBIDDEN, id="N-two-wf"),
    pytest.param((BOOK, NOVEL_CLASS), (DRAFT,), (BOOK,), (), None, FORBIDDEN, id="S-two-wf"),
    pytest.param((BOOK,), (DRAFT,), (BOOK,), (), None, {DRAFT}, id="no-state-written-kept"),
    pytest.param((BOOK,), (DRAFT,), (BOOK,), (DRAFT,), None, {DRAFT}, id="stored-state-passes"),
    pytest.param((BOOK,), (DRAFT,), (BOOK,), (ACCEPTED,), None, FORBIDDEN, id="another-state"),
    pytest.param((BOOK,), (DRAFT,), (BOOK,), (ACCEPTED,), ACCEPTED, {ACCEPTED}, id="allowed"),
    pytest.param((BOOK,), (DRAFT,), (BOOK,), (ACCEPTED,), IN_REVIEW, FORBIDDEN, id="allowed-other"),
    pytest.param((BOOK,), (), (BOOK,), (), None, set(), id="none-stays-none"),
    pytest.param((BOOK,), (), (BOOK,), (ACCEPTED,), None, FORBIDDEN, id="none-stored-writes"),
    pytest.param((BOOK,), (), (BOOK,), (ACCEPTED,), ACCEPTED, {ACCEPTED}, id="first-transition"),
    pytest.param((SHELF,), (OWN,), (BOOK,), (), None, FORBIDDEN, id="S-none-holds-state-N-wf"),
    pytest.param((SHELF,), (), (BOOK,), (), None, set(), id="S-none-N-wf-no-state-yet"),
    pytest.param((SHELF,), (), (BOOK,), (DRAFT,), None, FORBIDDEN, id="S-none-N-wf-writes-state"),
    pytest.param((), (), (BOOK,), (), None, set(), id="no-class-stored-N-wf-no-state-yet"),
]


@pytest.mark.parametrize(
    ("stored", "held", "written", "states", "allowed", "expected"), REPLACE_ROWS
)
async def test_the_decision_table_of_a_replace(
    flows, stored, held, written, states, allowed, expected
):
    triples = triples_of(written, states)
    async with fake_session(tenant_iri=TENANT) as session:
        await session.add_graph(ROOT, triples_of(stored, held))
        if expected == FORBIDDEN:
            with pytest.raises(Forbidden):
                await flows.keep_state(session, ROOT, triples, Tracked(), allowed)
            return
        result = await flows.keep_state(session, ROOT, triples, Tracked(), allowed)
    assert states_of(result) == expected, "the states written"
    assert no_status(result) == no_status(triples), "nothing else is touched"

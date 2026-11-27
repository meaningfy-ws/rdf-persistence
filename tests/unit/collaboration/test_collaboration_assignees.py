"""The write guard's rule on assignees (workflow-assignees D-2, T2, T3): only an assignment or a clearing transition changes them.

The toy ``Book`` follows the assignable review workflow of ``assignees_world``. A stored book is seeded through
a transaction that calls ``_allow_assignees``, as ``assign`` will; each row of the guard table of D-2 is one
case of ``GUARD``, a positive and a negative one.
"""

import pytest
from rdflib import RDF, RDFS, Literal, URIRef

from rdf_persistence import generated_models
from rdf_persistence.collaboration.services.write_guards import WriteGuards
from rdf_persistence.core.domain.exceptions import Forbidden, NotFound
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.mapper import UnitOfWork
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.testkit import fake_session
from tests.toy import BOOK_CLASS, MODULES, TENANT, book_iri, dune, toy_mapper
from tests.unit.collaboration.assignees_world import write_world
from tests.unit.collaboration.collaboration_data import VIEW, version_of

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

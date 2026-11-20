"""A removal that something still refers to is refused on a real Fuseki (delete-refuses-referenced RISK-2).

IT-1: the guard holds against a concurrent removal of the referrer. IT-2: E1 and E7. IT-3: E8, E9 and
matrix row 14. ``A1`` is an author (the toy's refusing class), ``B1`` a book that names it with
``written_by``, ``S1`` a shelf, a reference collection that names its members with ``has_part``.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from rdflib import URIRef

from rdf_persistence import CallerAccess, VerifiedCaller, generated_models
from rdf_persistence.access.services.access import AccessRules, load_role_definitions
from rdf_persistence.collaboration.services.collaboration import Collaboration
from rdf_persistence.collaboration.services.discussion import dependents
from rdf_persistence.collaboration.services.referenced_removals import ReferencedRemovals
from rdf_persistence.collaboration.services.workflows import Workflows, load_workflow
from rdf_persistence.collaboration.services.write_guards import WriteGuards
from rdf_persistence.core.domain.exceptions import Conflict, InUse
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.iris.services.iris import DEFAULT_IRIS
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.session import Session, open_session
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.schema.services.schema import load_schema
from tests.fixtures.library.domain.generated.books import Author
from tests.toy import (
    ADA,
    BOB,
    MODULES,
    REVIEW_WORKFLOW,
    ROLES,
    TENANT,
    TOY_SCHEMA,
    book_iri,
    caller,
    dune,
    held,
    role,
    shelf,
    shelf_iri,
    toy_mapper,
)

ROUNDS = 20
A1 = f"{TENANT}/authors/{UUID(int=1)}"
A2 = f"{TENANT}/authors/{UUID(int=2)}"
B1 = book_iri(1)
S1 = shelf_iri(1)
WRITTEN_BY = URIRef("https://example.org/ns/library#writtenBy")
REVIEW = load_workflow(REVIEW_WORKFLOW)


@pytest.fixture
async def database(store) -> AsyncIterator[str]:
    """A fresh dataset for the test, dropped after it."""
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


@pytest.fixture(scope="module")
def rules(tmp_path_factory: pytest.TempPathFactory) -> AccessRules:
    """The toy roles and a ``reviewer`` that reads and annotates."""
    path = tmp_path_factory.mktemp("roles") / "roles.yaml"
    path.write_text(
        ROLES.read_text() + "- {role: reviewer, level: tenant, actions: [read, annotate]}\n"
    )
    return AccessRules(load_role_definitions(path))


def opened(store, database: str, rules: AccessRules, who: str = ADA):
    """A session the way the kit opens one, with the refusal of removals the schema asks for."""
    view = load_schema(TOY_SCHEMA)
    listings = Listings(view)
    guards = WriteGuards(
        toy_mapper(), generated_models(*MODULES), listings, Workflows([REVIEW], view, rules)
    )
    return open_session(
        store,
        database=database,
        tenant_iri=TENANT,
        principal=Principal(id=who),
        listings=listings,
        guards=guards,
        dependents=dependents(view),
        removals=ReferencedRemovals(view, LimitSettings()),
    )


@pytest.fixture
async def session(store, database, rules) -> AsyncIterator[Session]:
    async with opened(store, database, rules) as ada:
        yield ada


def collaboration(
    session: Session, rules: AccessRules, who: VerifiedCaller, access: CallerAccess
) -> Collaboration:
    view = load_schema(TOY_SCHEMA)
    return Collaboration(
        session,
        view=view,
        rules=rules,
        iris=DEFAULT_IRIS,
        mapper=toy_mapper(),
        models=generated_models(*MODULES),
        listings=Listings(view),
        workflows=Workflows([REVIEW], view, rules),
        caller=who,
        access=access,
    )


@pytest.fixture
def as_ada(session, rules) -> Collaboration:
    return collaboration(session, rules, caller(principal=ADA), held(role("librarian")))


async def put(session: Session, model) -> str:
    return await session.add_graph(model.id, toy_mapper().to_triples(model))


async def put_author(session: Session, iri: str = A1) -> str:
    return await put(session, Author(id=iri, label="Herbert"))


async def put_book(session: Session, iri: str = B1, **slots: str) -> str:
    return await put(session, dune(iri, chapters=1, **slots))


async def version_of(session: Session, iri: str) -> str:
    return (await session.get_graph(iri))[2]


async def stored(session: Session, iri: str) -> bool:
    return bool(await session.heads([iri]))


async def test_it1_a_referrer_removed_at_the_same_time_never_leaves_a_dangling_reference(
    store, database, rules, session
):
    for n in range(ROUNDS):
        author, book = f"{TENANT}/authors/{UUID(int=1000 + n)}", book_iri(1000 + n)
        await put_author(session, author)
        await put_book(session, book, written_by=author)
        versions = [await version_of(session, author), await version_of(session, book)]
        async with (
            opened(store, database, rules, "https://example.org/people/ben") as theirs,
            opened(store, database, rules) as mine,
        ):
            outcomes = await asyncio.gather(
                mine.remove(author, versions[0]),
                theirs.remove(book, versions[1]),
                return_exceptions=True,
            )

        for outcome in outcomes:  # done, refused as in use, or lost the race: nothing else
            assert outcome is None or isinstance(outcome, Conflict), f"round {n}: {outcome!r}"
        assert not (not await stored(session, author) and await stored(session, book)), (
            f"round {n}: the author is gone while the book that names it stays"
        )


async def test_e1_a_removal_of_a_referenced_author_is_refused_naming_the_book(session):
    await put_author(session)
    await put_book(session, written_by=A1)
    with pytest.raises(InUse) as refused:
        await session.remove(A1, await version_of(session, A1))
    assert refused.value.iris == (A1,), "names the refused root"
    assert refused.value.referrers == ((B1, "Book", "written_by"),), "names the book and its slot"
    assert (refused.value.more_count, refused.value.hidden_count) == (0, 0)
    assert await stored(session, A1), "the author stays"


async def test_e7_a_cascade_deletes_a_collection_of_authors_and_its_members(session, as_ada):
    await put_author(session, A1)
    await put(session, shelf(S1).model_copy(update={"member_class": "Author", "has_part": [A1]}))
    await as_ada.delete_cascade(S1, await version_of(session, S1))
    assert not await stored(session, S1), "the shelf is gone"
    assert not await stored(session, A1), "its own link does not keep the author"


async def test_e8_a_collection_that_names_the_author_refuses_its_plain_removal(session):
    await put_author(session)
    await put(session, shelf(S1).model_copy(update={"member_class": "Author", "has_part": [A1]}))
    with pytest.raises(InUse) as refused:
        await session.remove(A1, await version_of(session, A1))
    assert [(r, c) for r, c, _ in refused.value.referrers] == [(S1, "Shelf")], "the shelf is named"
    assert await stored(session, A1), "the author stays"


async def test_e9_a_comment_on_the_author_goes_with_it(session, rules):
    await put_author(session)
    reviewer = collaboration(
        session,
        rules,
        caller(principal=BOB),
        held(role("reader", who=BOB), role("reviewer", who=BOB)),
    )
    comment = await reviewer.comment(A1, "a note on the author")
    await session.remove(A1, await version_of(session, A1))
    assert not await stored(session, A1), "the author is removed"
    assert not await stored(session, comment), "the comment went with it"
    assert not await session.graphs_with(v.HAS_TARGET, URIRef(A1)), "nothing targets it"


async def test_matrix_14_a_part_referring_to_its_own_root_is_no_referrer(session):
    part = URIRef(f"{A1}/parts/1")
    triples = toy_mapper().to_triples(Author(id=A1, label="Herbert"))
    version = await session.add_graph(A1, [*triples, (part, WRITTEN_BY, URIRef(A1))])
    await session.remove(A1, version)
    assert not await stored(session, A1), "its own part does not refuse the removal"


async def test_another_author_stays_when_one_is_refused(session):
    """The refusal is of the referenced root only: an unreferenced author is removed."""
    await put_author(session, A1)
    await put_author(session, A2)
    await put_book(session, written_by=A1)
    await session.remove(A2, await version_of(session, A2))
    assert not await stored(session, A2), "the author nothing refers to is removed"
    assert await stored(session, A1), "the referenced author stays"

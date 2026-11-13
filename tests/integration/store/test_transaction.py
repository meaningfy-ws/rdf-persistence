"""``Session.transaction`` against a real Fuseki: several aggregate writes in one request (atomic-commit 1.4).

A and B are stored books, C a new one; "another session" is a second session on the same dataset.
"""

import asyncio
import time
import uuid
from collections.abc import AsyncIterator

import pytest
from rdflib import URIRef

from rdf_persistence.adapters.fuseki import FusekiStore
from rdf_persistence.domain.exceptions import Conflict, NotFound
from rdf_persistence.domain.iris import DEFAULT_IRIS, graph_iri
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import Session
from tests.fixtures.library.generated.books import Book
from tests.integration.store.test_session import BEN, TENANT, TITLE, book, session_for, title
from tests.toy import dune, toy_mapper

A, B, C = book(1), book(2), book(3)
ENTRY = "ASK { GRAPH $registry { $graph ?p ?o } }"
ANY_MARKER = "ASK { GRAPH $registry { ?m a $marker } }"
CONCURRENT = 20


async def ask(store, database, text: str, **terms) -> bool:
    return bool((await store.query(database, fill(text, **terms))).askAnswer)


async def has_entry(store, database, root: str) -> bool:
    return await ask(
        store,
        database,
        ENTRY,
        registry=term(DEFAULT_IRIS.registry(TENANT)),
        graph=term(graph_iri(root)),
    )


async def a_marker_is_left(store, database) -> bool:
    return await ask(
        store,
        database,
        ANY_MARKER,
        registry=term(DEFAULT_IRIS.registry(TENANT)),
        marker=term(v.COMMIT_MARKER),
    )


async def stored(session: Session, root: str) -> bool:
    try:
        await session.get_graph(root)
    except NotFound:
        return False
    return True


async def stored_title(session: Session, root: str) -> str:
    graph, _, _ = await session.get_graph(root)
    return str(graph.value(URIRef(root), TITLE))


@pytest.fixture
async def store(fuseki) -> AsyncIterator[FusekiStore]:
    async with FusekiStore(fuseki.url, fuseki.user, fuseki.password) as client:
        yield client


@pytest.fixture
async def database(store: FusekiStore) -> AsyncIterator[str]:
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


@pytest.fixture
async def session(store, database) -> Session:
    return session_for(store, database)


@pytest.fixture
async def seeded(session) -> dict[str, str]:
    """A and B stored, at the returned versions."""
    return {root: await session.add_graph(root, title(root, "first")) for root in (A, B)}


async def test_it01_replace_add_and_remove_commit_together(store, database, session, seeded):
    async with session.transaction() as t:
        a2 = await t.replace_graph(A, title(A, "second"), seeded[A])
        c1 = await t.add_graph(C, title(C, "new"))
        assert await t.remove(B, seeded[B]) is None
    assert (await session.get_graph(A))[2] == a2, "A holds the replace's token"
    assert (await session.get_graph(C))[2] == c1, "C holds the add's token"
    assert await stored_title(session, A) == "second", "A was replaced"
    assert not await stored(session, B), "B was removed"
    assert await has_entry(store, database, C), "the added root is registered"
    assert not await has_entry(store, database, B), "the removed root is unregistered"
    assert not await a_marker_is_left(store, database), "the marker was released"


async def test_it02_a_replaced_root_changed_meanwhile_refuses_everything(
    store, database, session, seeded
):
    other = session_for(store, database, principal=BEN)
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            await t.add_graph(C, title(C, "new"))
            await t.remove(B, seeded[B])
            await other.replace_graph(A, title(A, "theirs"), seeded[A])
    assert refused.value.iris == (A,)
    assert await stored_title(session, A) == "theirs"
    assert not await stored(session, C)
    assert await stored(session, B)
    assert not await a_marker_is_left(store, database)


async def test_it04_of_twenty_concurrent_transactions_exactly_one_commits(
    store, database, session, seeded
):
    new_books = [book(100 + n) for n in range(CONCURRENT)]

    async def attempt(own: str) -> BaseException | None:
        mine = session_for(store, database)
        try:
            async with mine.transaction() as t:
                await t.replace_graph(A, title(A, own), seeded[A])
                await t.add_graph(own, title(own, "new"))
        except Conflict as refused:
            return refused
        return None

    outcomes = await asyncio.gather(*(attempt(own) for own in new_books))
    assert sum(outcome is None for outcome in outcomes) == 1, "exactly one transaction wins"
    assert all(isinstance(o, Conflict) for o in outcomes if o is not None)
    present = [own for own in new_books if await stored(session, own)]
    assert len(present) == 1, "exactly one new book is stored"
    assert await stored_title(session, A) == present[0], "and it is the winner's replacement"
    assert not await a_marker_is_left(store, database)


async def test_it03_a_unit_of_work_that_changes_a_and_adds_b_refuses_both_when_b_changed_meanwhile(
    store, database, session
):
    for root in (A, B):
        seed = UnitOfWork(session, toy_mapper())
        seed.add(dune(root))
        await seed.commit()
    mine = UnitOfWork(session, toy_mapper())
    book_a, book_b = await mine.get(Book, A), await mine.get(Book, B)
    other = UnitOfWork(session_for(store, database, principal=BEN), toy_mapper())
    theirs = await other.get(Book, B)
    theirs.label = "theirs"
    other.add(theirs)
    await other.commit()
    book_a.label = "mine"
    book_b.label = "mine"
    mine.add(book_a)
    mine.add(book_b)
    with pytest.raises(Conflict) as refused:
        await mine.commit()
    assert refused.value.iris == (B,), "only the changed book is named"
    label_a = (await UnitOfWork(session, toy_mapper()).get(Book, A)).label
    assert label_a == dune(A).label, "A is unchanged in the store"
    label_b = (await UnitOfWork(session, toy_mapper()).get(Book, B)).label
    assert label_b == "theirs", "B keeps the other edit"
    assert not await a_marker_is_left(store, database), "the marker was released"


COUNT_ENTRIES = "SELECT (COUNT(DISTINCT ?g) AS ?n) WHERE { GRAPH $registry { ?g $kind ?k } }"


@pytest.mark.slow
async def test_it06_a_commit_of_the_default_limit_of_new_books_is_one_update_within_30_s(
    store, database, session, capsys
):
    """PD-10, PD-11, RISK-2: 500 books, each with two chapters and their notes, in one commit."""
    updates: list[int] = []
    send = store.update

    async def counted(dataset: str, sparql: str) -> None:
        updates.append(len(sparql))
        await send(dataset, sparql)

    store.update = counted  # type: ignore[method-assign]
    unit = UnitOfWork(session, toy_mapper())
    for n in range(500):
        unit.add(dune(book(1000 + n)))
    started = time.perf_counter()
    await unit.commit()
    seconds = time.perf_counter() - started
    with capsys.disabled():
        print(
            f"\nIT-06: 500 books committed in {seconds:.1f} s; updates {len(updates)}, bytes {updates}"
        )
    counted_entries = await store.query(
        database,
        fill(
            COUNT_ENTRIES, registry=term(DEFAULT_IRIS.registry(TENANT)), kind=term(v.REGISTRY_KIND)
        ),
    )
    assert int(next(iter(counted_entries)).n) == 500, "all 500 books are registered"
    assert len(updates) == 1, f"one update request, got {updates}"
    assert seconds < 30, f"500 books took {seconds:.1f} s (PD-10 allows 30 s)"
    assert not await a_marker_is_left(store, database), "the marker was released"

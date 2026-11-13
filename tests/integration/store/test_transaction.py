"""``Session.transaction`` against a real Fuseki: several aggregate writes in one request (atomic-commit 1.4).

A and B are stored books, C a new one; "another session" is a second session on the same dataset.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
from rdflib import URIRef

from rdf_persistence.adapters.fuseki import FusekiStore
from rdf_persistence.domain.exceptions import Conflict, NotFound
from rdf_persistence.domain.iris import DEFAULT_IRIS, graph_iri
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.session import Session
from tests.integration.store.test_session import BEN, TENANT, TITLE, book, session_for, title

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
    assert (await session.get_graph(A))[2] == a2
    assert (await session.get_graph(C))[2] == c1
    assert await stored_title(session, A) == "second"
    assert not await stored(session, B)
    assert await has_entry(store, database, C) and not await has_entry(store, database, B)
    assert not await a_marker_is_left(store, database)


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

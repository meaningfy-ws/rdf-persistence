"""Wall-clock budgets of the session on a real Fuseki (moved from the integration tests, rule 12)."""

import time
import uuid
from collections.abc import AsyncIterator

import pytest
from rdflib import Literal, URIRef

from rdf_persistence import FusekiStore
from rdf_persistence.domain.iris import loaded_graph_iri
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import Session
from tests.integration.store.sessions import (
    TITLE,
    book,
    graph_of,
    keyed_book,
    session_for,
    session_of,
)
from tests.toy import dune, toy_mapper

REPLACE_REMOVE_SECONDS = 2.0  # the cartesian form took tens of seconds
COMMIT_SECONDS = 30  # PD-10
KEYED_ADD_SECONDS = 0.5
BOOKS, BATCH, ROUNDS = 1000, 100, 20


@pytest.fixture
async def database(store: FusekiStore) -> AsyncIterator[str]:
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


@pytest.mark.parametrize("call", ["replace", "remove"])
async def test_replace_and_remove_cost_the_size_of_the_graphs_not_their_product(
    store, database, call
):
    """50 aggregate triples and a loaded graph of 2000: the cartesian form took tens of seconds."""
    session = session_for(store, database)
    loaded = loaded_graph_iri(book(1))
    root = URIRef(book(1))
    await store.put_graph(
        database, loaded, graph_of([(root, TITLE, Literal(i)) for i in range(2000)])
    )
    triples = [(root, TITLE, Literal(f"title {i}")) for i in range(50)]
    version = await session.add_graph(book(1), triples, [loaded])
    started = time.perf_counter()
    if call == "replace":
        await session.replace_graph(book(1), triples, version)
    else:
        await session.remove(book(1), version)
    seconds = time.perf_counter() - started
    assert seconds < REPLACE_REMOVE_SECONDS, f"{call} took {seconds:.1f} s"


async def test_a_commit_of_the_default_limit_of_new_books_stays_within_30_s(store, database):
    """PD-10, RISK-2: 500 books, each with two chapters and their notes, in one commit."""
    session = session_for(store, database)
    unit = UnitOfWork(session, toy_mapper())
    for n in range(500):
        unit.add(dune(book(1000 + n)))
    started = time.perf_counter()
    await unit.commit()
    seconds = time.perf_counter() - started
    assert seconds < COMMIT_SECONDS, f"500 books took {seconds:.1f} s (PD-10 allows 30 s)"


async def mean_seconds(adds) -> float:
    """The mean wall time of awaiting each coroutine of ``adds`` in turn."""
    spent = []
    for add in adds:
        start = time.perf_counter()
        await add
        spent.append(time.perf_counter() - start)
    return sum(spent) / len(spent)


async def test_a_keyed_add_stays_under_half_a_second_in_a_tenant_of_a_thousand_books(
    store, database
):
    session: Session = session_of(store, database)
    unkeyed = session_of(store, database, keys=())
    for first in range(0, BOOKS, BATCH):  # 10 transactions of 100 books, unkeyed: only the load
        async with unkeyed.transaction() as load:
            for n in range(first, first + BATCH):
                iri = book(10_000 + n)
                await load.add_graph(iri, keyed_book(iri, f"load-{n}"))
    keyed = await mean_seconds(
        session.add_graph(iri, keyed_book(iri, f"new-{n}"))
        for n, iri in enumerate(book(20_000 + n) for n in range(ROUNDS))
    )
    assert keyed < KEYED_ADD_SECONDS, f"mean keyed add {keyed:.3f} s over {ROUNDS} adds"

"""What the drop of the dependents of a removed aggregate costs on Fuseki when there is none (PD-30 item 6).

A tenant of 5 000 stored books and no comment: the median time of removing one book, in a session
without dependents, and in one with them under the order of the old template (the registry first)
and the new one (the link first). The figures are printed, not asserted: a timing is no test.
"""

import statistics
import time
import uuid
from collections.abc import AsyncIterator

import pytest

from rdf_persistence import generated_models
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.services import session as session_module
from rdf_persistence.services.discussion import dependents
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.session import Session, open_session
from rdf_persistence.services.write_guards import WriteGuards
from tests.toy import ADA, MODULES, TENANT, TOY_SCHEMA, book_iri, dune, toy_mapper

BOOKS = 5000
REMOVES = 5
MARKED = session_module._MARKED
DELETE = "DELETE { GRAPH ?d { ?s ?p ?o } GRAPH $registry { ?d ?ep ?eo } }"
REGISTRY = "GRAPH $registry { ?d $p_kind $aggregate ; $p_owned_by ?c }"
UNION = "{ GRAPH ?d { ?s ?p ?o } } UNION { GRAPH $registry { ?d ?ep ?eo } }"
REGISTRY_FIRST = (
    f"{DELETE} WHERE {{ {MARKED} {REGISTRY} VALUES (?type ?link) {{ $pairs }} "
    f"GRAPH ?d {{ ?c a ?type ; ?link $root }} {UNION} }}"
)
LINK_FIRST = (
    f"{DELETE} WHERE {{ {MARKED} VALUES (?type ?link) {{ $pairs }} "
    f"GRAPH ?d {{ ?c ?link $root ; a ?type }} {REGISTRY} {UNION} }}"
)


@pytest.fixture
async def database(store) -> AsyncIterator[str]:
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


async def opened(store, database: str, pairs, stack):
    listings = Listings(load_schema(TOY_SCHEMA))
    return await stack.enter_async_context(
        open_session(
            store,
            database=database,
            tenant_iri=TENANT,
            principal=Principal(id=ADA),
            listings=listings,
            guards=WriteGuards(toy_mapper(), generated_models(*MODULES), listings),
            dependents=pairs,
        )
    )


async def median_remove(session: Session, books: list[str]) -> float:
    times = []
    for iri in books:
        version = (await session.get_graph(iri))[2]
        started = time.perf_counter()
        await session.remove(iri, version)
        times.append(time.perf_counter() - started)
    return statistics.median(times)


@pytest.mark.slow
async def test_removing_a_book_of_a_tenant_without_comments_with_and_without_the_drop(
    store, database, monkeypatch
):
    from contextlib import AsyncExitStack

    async with AsyncExitStack() as stack:
        plain = await opened(store, database, (), stack)
        with_pairs = await opened(store, database, dependents(load_schema(TOY_SCHEMA)), stack)
        books = [book_iri(n) for n in range(1, BOOKS + 1)]
        for start in range(0, BOOKS, 100):
            work = UnitOfWork(plain, toy_mapper())
            for iri in books[start : start + 100]:
                work.add(dune(iri, chapters=0))
            await work.commit()
        first = [books[n] for n in range(0, REMOVES)]
        second = [books[n] for n in range(REMOVES, 2 * REMOVES)]
        third = [books[n] for n in range(2 * REMOVES, 3 * REMOVES)]
        without = await median_remove(plain, first)
        monkeypatch.setattr(session_module, "_DROP_DEPENDENTS", REGISTRY_FIRST)
        old = await median_remove(with_pairs, second)
        monkeypatch.setattr(session_module, "_DROP_DEPENDENTS", LINK_FIRST)
        new = await median_remove(with_pairs, third)
    print(
        f"median remove of one of {BOOKS} books, no comment: without the drop {without:.3f} s, "
        f"registry first {old:.3f} s, link first {new:.3f} s"
    )

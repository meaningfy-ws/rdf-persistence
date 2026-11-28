"""Dependent aggregates on a real Fuseki (dependent-aggregates RISK-1, A-13, PD-3 to PD-7).

The guards of a part's write and of a whole's delete are right only if the store applies one update
request at a time. IT-D1 is the cascade itself. IT-D2 and IT-D3 run writers concurrently (the outcome
varies; the invariant must not). IT-D4 and IT-D5 force the two interleavings that matter: a part added
after the delete's discovery, and the whole deleted after the part's check. Each would pass on a store
that ignored the guard only if the interleaving never happened, which the pause makes certain.
"""

import asyncio
import uuid
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, AsyncExitStack

import pytest
from rdflib import RDF, URIRef

from rdf_persistence.core.domain.exceptions import Conflict, NotFound
from rdf_persistence.core.domain.generated.rp_core import DependenceLink, Principal
from rdf_persistence.files.domain.generated.rp_files import RdfFormat
from rdf_persistence.persistence.adapters.fuseki import FusekiStore
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.persistence.services.session import Session, open_session
from tests.integration.store.pausing_store import PausingStore
from tests.toy import TENANT
from tests.unit.persistence.dependent_helpers import (
    A1,
    LIB,
    LINK,
    R1,
    R2,
    R3,
    RESULT,
    audit,
    iri,
    is_stored,
    names,
    result,
)

ROUNDS = 20
FINDING, OF_RESULT = (URIRef(LIB + name) for name in ("Finding", "of_result"))
LINK_F = DependenceLink(
    part_classes=[str(FINDING)], pointer=str(OF_RESULT), whole_classes=[str(RESULT)]
)
LINKS = (LINK, LINK_F)
F1 = iri("findings", 1)
LOADED = b"<https://example.org/a> <https://example.org/b> <https://example.org/c> ."


@pytest.fixture
async def database(store: FusekiStore) -> AsyncIterator[str]:
    """A fresh dataset for the test, dropped after it."""
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


def opened(store, database: str, who: str = "ada") -> AbstractAsyncContextManager[Session]:
    """A session of the toy tenant whose schema links a result to its audit and a finding to its result."""
    return open_session(
        store,
        database=database,
        tenant_iri=TENANT,
        principal=Principal(id=f"https://example.org/people/{who}"),
        dependence=LINKS,
        limits=LimitSettings(max_roots=50),
    )


@pytest.fixture
async def session(store, database) -> AsyncIterator[Session]:
    async with opened(store, database) as ada:
        yield ada


def finding(root: str, whole: str) -> list:
    return [(URIRef(root), RDF.type, FINDING), (URIRef(root), OF_RESULT, URIRef(whole))]


async def version_of(session: Session, root: str) -> str:
    return (await session.get_graph(root))[2]


async def mentioned(store, database: str, root: str) -> bool:
    """Whether any graph of the dataset, registry included, still has ``root`` as a subject."""
    answer = await store.query(database, f"ASK {{ GRAPH ?g {{ <{root}> ?p ?o }} }}")
    return bool(answer.askAnswer)


async def test_it_d1_removing_a_whole_removes_three_levels_and_a_loaded_graph(
    store, database, session
):
    other, other_result = iri("audits", 2), iri("results", 4)
    a1 = await session.add_graph(A1, audit(A1))
    loaded = await session.load_graph(R1, LOADED, rdf_format=RdfFormat.TURTLE)
    await session.add_graph(R1, result(R1, A1), [loaded])
    await session.add_graph(R2, result(R2, A1))
    await session.add_graph(F1, finding(F1, R1))
    await session.add_graph(other, audit(other))
    await session.add_graph(other_result, result(other_result, other))

    await session.remove(A1, a1)

    for root in (A1, R1, R2, F1):
        assert not await mentioned(store, database, root), f"{root} is gone, registry entry too"
    held = await store.query(database, f"ASK {{ GRAPH <{loaded}> {{ ?s ?p ?o }} }}")
    assert not held.askAnswer, "the loaded graph of a part went with it"
    assert await is_stored(session, other), "an unrelated whole stays"
    assert await is_stored(session, other_result), "an unrelated part stays"


@pytest.mark.slow
async def test_it_d2_concurrent_part_writes_and_the_whole_delete_leave_no_part_without_its_whole(
    store, database, session
):
    counts: Counter[str] = Counter()
    for n in range(ROUNDS):
        whole, kept = iri("audits", 100 + n), iri("results", 100 + n)
        parts = [iri("results", 200 + 3 * n + k) for k in range(3)]
        version = await session.add_graph(whole, audit(whole))
        await session.add_graph(kept, result(kept, whole))
        async with AsyncExitStack() as stack:
            each = [await stack.enter_async_context(opened(store, database)) for _ in range(4)]
            outcomes = await asyncio.gather(
                each[0].remove(whole, version),
                *(s.add_graph(p, result(p, whole)) for s, p in zip(each[1:], parts, strict=True)),
                return_exceptions=True,
            )
        removal, *writes = outcomes
        for outcome in outcomes:
            assert outcome is None or isinstance(outcome, str | Conflict | NotFound), (
                f"round {n}: an outcome no guard explains: {outcome!r}"
            )
        counts[type(removal).__name__] += 1
        summary = f"round {n}, delete {removal!r}, writes {writes!r}"
        if removal is None:
            assert not await is_stored(session, whole), f"{summary}: removed yet stored"
        else:
            assert await is_stored(session, whole), f"{summary}: refused yet gone"
        for part in (kept, *parts):
            if await is_stored(session, part):
                assert await is_stored(session, whole), f"{summary}: {part} has no whole"
    print(f"IT-D2 delete outcomes over {ROUNDS} rounds: {dict(counts)}")


async def test_it_d3_two_parts_written_in_parallel_both_succeed_and_leave_the_whole_as_it_was(
    store, database, session
):
    for n in range(5):
        whole = iri("audits", 300 + n)
        version = await session.add_graph(whole, audit(whole))
        first, second = iri("results", 300 + 2 * n), iri("results", 301 + 2 * n)
        async with opened(store, database) as one, opened(store, database, "ben") as two:
            await asyncio.gather(
                one.add_graph(first, result(first, whole)),
                two.add_graph(second, result(second, whole)),
            )
        assert await version_of(session, whole) == version, f"round {n}: the whole's version moved"
        assert await is_stored(session, first), f"round {n}: the first part is stored"
        assert await is_stored(session, second), f"round {n}: the second part is stored"


async def test_it_d4_a_part_added_after_the_deletes_discovery_makes_the_delete_a_conflict(
    store, database, session
):
    a1 = await session.add_graph(A1, audit(A1))
    await session.add_graph(R1, result(R1, A1))
    await session.add_graph(R2, result(R2, A1))
    pausing = PausingStore(store)
    async with opened(pausing, database) as deleter:
        work = asyncio.ensure_future(deleter.remove(A1, a1))
        await pausing.paused(work)  # discovered R1 and R2, update not sent
        await session.add_graph(R3, result(R3, A1))
        pausing.release()
        (outcome,) = await asyncio.gather(work, return_exceptions=True)

    assert isinstance(outcome, Conflict), f"the delete is a conflict: {outcome!r}"
    assert outcome.iris == (A1,), f"it names the whole: {outcome.iris!r}"
    for root in (A1, R1, R2, R3):
        assert await is_stored(session, root), f"nothing was removed: {root}"


async def test_it_d5_a_whole_deleted_after_the_parts_check_makes_the_part_not_found(
    store, database, session
):
    a1 = await session.add_graph(A1, audit(A1))
    pausing = PausingStore(store)
    async with opened(pausing, database) as writer:
        work = asyncio.ensure_future(writer.add_graph(R3, result(R3, A1)))
        await pausing.paused(work)  # the whole was asked for and found, update not sent
        await session.remove(A1, a1)
        pausing.release()
        (outcome,) = await asyncio.gather(work, return_exceptions=True)

    assert isinstance(outcome, NotFound), f"the part is not found: {outcome!r}"
    assert names(outcome, A1), f"it names the whole: {outcome!s}"
    assert not await mentioned(store, database, R3), "no graph of the part was written"

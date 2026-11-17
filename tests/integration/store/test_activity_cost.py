"""What recording one activity per commit costs on Fuseki (message-bus PD-12, TC-50).

A tenant whose provenance graph already holds 20 000 activities, preloaded with bulk ``INSERT DATA``
updates through the store (not through commits). One book is replaced 200 times in a session that
does not record, then 200 times in one that does; the mean time per commit of each block is
printed. The figures are printed, not asserted: a timing is no test.
"""

import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_provenance import Generation, Invalidation, Replace
from rdf_persistence.domain.sparql import fill, term, triples_block
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.iris import DEFAULT_IRIS
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.provenance import ID_PREFIX, activity_triples
from rdf_persistence.services.session import Session, open_session
from tests.toy import ADA, TENANT, book_iri, dune, toy_mapper

PRELOADED = 20_000
PER_UPDATE = 2_000
REPLACES = 200
PROVENANCE = DEFAULT_IRIS.provenance(TENANT)
INSERT = "INSERT DATA { GRAPH $provenance { $triples } }"
COUNT = "SELECT (COUNT(DISTINCT ?a) AS ?n) WHERE { GRAPH $provenance { ?a a $activity } }"


@pytest.fixture
async def database(store) -> AsyncIterator[str]:
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


def an_activity(n: int) -> Replace:
    """One replace in the shape the session records: a generation and an invalidation."""
    id = f"{ID_PREFIX}{uuid.uuid4()}"
    at = datetime(2026, 11, 14, 12, n % 60, tzinfo=UTC)
    part = {"activity": id, "at_time": at, "entity": book_iri(n), "entity_version": f"v{n}"}
    return Replace(
        id=id,
        started_at_time=at,
        ended_at_time=at,
        was_associated_with=[ADA],
        generations=[Generation(**part)],
        invalidations=[Invalidation(**part)],
    )


async def preload(store, database: str) -> None:
    for start in range(0, PRELOADED, PER_UPDATE):
        triples = [
            t
            for n in range(start, start + PER_UPDATE)
            for t in activity_triples(an_activity(n), [v.REPLACE, v.ACTIVITY])
        ]
        await store.update(
            database,
            fill(INSERT, provenance=term(PROVENANCE), triples=triples_block(triples)),
        )


async def activities(store, database: str) -> int:
    rows = await store.query(
        database, fill(COUNT, provenance=term(PROVENANCE), activity=term(v.ACTIVITY))
    )
    return int(next(iter(rows)).n)


async def replace_block(session: Session, root: str) -> float:
    """The mean seconds per commit of ``REPLACES`` sequential replaces of the book at ``root``."""
    started = time.perf_counter()
    for n in range(REPLACES):
        unit = UnitOfWork(session, toy_mapper())
        stored = await unit.get(type(dune(root)), root)
        stored.label = f"edit {n}"
        unit.add(stored)
        await unit.commit()
    return (time.perf_counter() - started) / REPLACES


@pytest.mark.slow
async def test_a_commit_that_records_its_activity_costs_what_beside_one_that_does_not(
    store, database, capsys
):
    root = book_iri(1)
    started = time.perf_counter()
    await preload(store, database)
    preloaded_in = time.perf_counter() - started
    async with (
        open_session(
            store, database=database, tenant_iri=TENANT, principal=Principal(id=ADA)
        ) as recorded,
        open_session(
            store,
            database=database,
            tenant_iri=TENANT,
            principal=Principal(id=ADA),
            record_activities=False,
        ) as unrecorded,
    ):
        seed = UnitOfWork(unrecorded, toy_mapper())
        seed.add(dune(root))
        await seed.commit()
        assert await activities(store, database) == PRELOADED, "the preload holds 20 000 activities"
        # Unrecorded first: the provenance graph stays at 20 000 for it, then grows by 200 for
        # the recorded block, the worse case for the recorded commits.
        plain = await replace_block(unrecorded, root)
        before = await activities(store, database)
        with_activity = await replace_block(recorded, root)
        after = await activities(store, database)
    with capsys.disabled():
        print(
            f"\nTC-50: {REPLACES} replaces over {PRELOADED} activities (preload {preloaded_in:.1f} s); "
            f"recorded {with_activity * 1000:.1f} ms per commit, unrecorded {plain * 1000:.1f} ms, "
            f"difference {(with_activity - plain) * 1000:.1f} ms, ratio {with_activity / plain:.2f}"
        )
    assert before == PRELOADED, "the unrecorded block added no activity"
    assert after - before == REPLACES, "the recorded block added one activity per commit"

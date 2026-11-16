"""``Session.relayed_since``: the activities relayed at or after a named one, for a resume (aggregate-events 3.1; PD-12)."""

from datetime import UTC, datetime, timedelta

import pytest
from rdflib import RDF, URIRef

from rdf_persistence.domain.exceptions import DatabaseGone
from rdf_persistence.services import vocabulary as v
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.unit.services.test_pending_mark import PLUMBING, three_commits
from tests.unit.services.test_session_activity import PROVENANCE, X, activities, opened

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
WEEK = timedelta(days=7)
XSD_DATE_TIME = "http://www.w3.org/2001/XMLSchema#dateTime"


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


async def relay_marks(store: FakeStore, marks: dict[str, str]) -> None:
    """Replace each activity's pending mark by a ``relayedAt`` written as given (a lexical form, or a literal)."""
    for iri, mark in marks.items():
        value = mark if mark.startswith('"') else f'"{mark}"^^<{XSD_DATE_TIME}>'
        await store.update(
            FAKE_DATABASE,
            f"DELETE WHERE {{ GRAPH <{PROVENANCE}> {{ <{iri}> <{v.PENDING_SINCE}> ?o }} }};"
            f"INSERT DATA {{ GRAPH <{PROVENANCE}> {{ <{iri}> <{v.RELAYED_AT}> {value} }} }}",
        )


async def three_ids(store: FakeStore, session) -> tuple[str, str, str]:
    await three_commits(session)
    a, b, c = sorted(a.id for a in await activities(store))
    return a, b, c


async def test_the_activities_relayed_after_the_named_one_come_ordered_by_time_then_iri(store):
    async with opened(store) as session:
        a, b, c = await three_ids(store, session)
        await relay_marks(
            store,
            {a: "2026-11-15T10:00:00Z", c: "2026-11-15T10:00:01Z", b: "2026-11-15T10:00:01Z"},
        )
        found = await session.relayed_since(a, WEEK, NOW)
    assert found is not None
    assert [iri for iri, _ in found] == [b, c], "the named one excluded; time, then IRI"
    assert all((URIRef(i), RDF.type, v.ACTIVITY) in g for i, g in found), "each with its activity"
    assert [t for _, g in found for p in PLUMBING for t in g.triples((None, p, None))] == [], (
        "without the plumbing predicates"
    )


async def test_an_activity_relayed_at_the_same_time_as_the_named_one_is_included(store):
    async with opened(store) as session:
        a, b, c = await three_ids(store, session)
        await relay_marks(
            store,
            {a: "2026-11-15T10:00:00Z", b: "2026-11-15T10:00:00Z", c: "2026-11-14T10:00:00Z"},
        )
        found = await session.relayed_since(a, WEEK, NOW)
    assert found is not None
    assert [iri for iri, _ in found] == [b], "later or the same instant; never earlier"


async def test_an_activity_applied_early_but_relayed_late_is_found(store):  # TC-37a
    async with opened(store) as session:
        a, b, c = await three_ids(store, session)  # the order of the IRIs is not the order applied
        await relay_marks(store, {c: "2026-11-15T10:00:00Z", a: "2026-11-15T10:05:00Z"})
        found = await session.relayed_since(c, WEEK, NOW)
    assert found is not None
    assert [iri for iri, _ in found] == [a], "the one relayed after the named one, whenever applied"


@pytest.mark.parametrize(
    "case, mark",
    [
        ("unknown", None),
        ("never relayed", "pending"),
        ("older than the window", "2026-11-08T11:59:59Z"),
        ("relayed at a bad mark", '"yesterday"'),
        ("relayed without a zone", "2026-11-15T10:00:00"),
    ],
)
async def test_the_named_activity_that_cannot_anchor_a_resume_gives_none(
    store, case, mark
):  # TC-38
    async with opened(store) as session:
        a, b, _ = await three_ids(store, session)
        if mark not in (None, "pending"):
            await relay_marks(store, {a: mark})
        named = X if mark is None else a
        assert await session.relayed_since(named, WEEK, NOW) is None, case


async def test_the_window_edge_is_inside(store):
    async with opened(store) as session:
        a, b, _ = await three_ids(store, session)
        await relay_marks(store, {a: "2026-11-09T12:00:00Z", b: "2026-11-15T10:00:00Z"})
        found = await session.relayed_since(a, WEEK, NOW)
    assert found is not None and [iri for iri, _ in found] == [b], "exactly seven days ago counts"


async def test_a_bad_mark_never_fails_the_read_and_sorts_after_every_valid_one(store):
    async with opened(store) as session:
        a, b, c = await three_ids(store, session)
        await relay_marks(
            store, {a: "2026-11-15T10:00:00Z", b: '"later"', c: "2026-11-15T10:00:02Z"}
        )
        found = await session.relayed_since(a, WEEK, NOW)
    assert found is not None
    ids = [iri for iri, _ in found]  # a store may compare "later" with a time or drop it
    assert ids[0] == c and set(ids) <= {b, c}, "the valid one first; the bad one, if any, last"


async def test_a_database_that_is_gone_raises_database_gone(store):
    async with opened(store) as session:
        await store.drop_dataset(FAKE_DATABASE)
        with pytest.raises(DatabaseGone):
            await session.relayed_since(X, WEEK, NOW)

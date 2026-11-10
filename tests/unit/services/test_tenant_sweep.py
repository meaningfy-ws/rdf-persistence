"""The sweep of a live tenant over the fakes (live-tenant-sweep PD-1 to PD-9, PD-11, the worked example).

The world is the design's: a book B committed with loaded graph G1; G2 loaded for B two hours ago and
never committed; G3 loaded five minutes ago; a scan S stored with blob k1; blob k2 left behind three
hours ago; blob k3 uploaded a minute ago. Time is a clock the tests move; nothing sleeps.
"""

import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from rdflib import Graph, Literal, URIRef

from rdf_persistence.domain.exceptions import Conflict, NotFound, StoreUnavailable, TenantGone
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.generated.rp_tenancy import TenantSweepReport
from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.domain.iris import Iris
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import iri_types
from rdf_persistence.services.session import open_session
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.services.tenant_sweep import sweep_tenant
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, SETTINGS, TOY_SCHEMA, library_slots, toy_mapper

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
CREATOR = Principal(id=ADA)
FILE_KEY = URIRef("https://meaningfy.ws/ns/rdf-persistence#fileKey")
LOADED_AT = URIRef("https://meaningfy.ws/ns/rdf-persistence#loadedAt")
OWNED_BY = URIRef("https://meaningfy.ws/ns/rdf-persistence#ownedBy")
TURTLE = b'<https://example.org/b> <http://purl.org/dc/terms/title> "Dune" .'
HOUR = timedelta(hours=1)
ALL_QUADS = "SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } }"


class Events(FakeStore):
    """A fake store that records its queries with the bucket listings, in one order."""

    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self.events = events
        self.after: tuple[str, object] | None = (
            None  # (text in a query, coroutine function to run before it)
        )

    async def query(self, dataset, sparql):
        self.events.append(sparql)
        if self.after is not None and self.after[0] in sparql:
            _, act = self.after
            self.after = None
            await act()
        return await super().query(dataset, sparql)


class EventFiles(FakeFileStore):
    def __init__(self, events: list[str], clock) -> None:
        super().__init__(clock)
        self.events = events

    async def list_blobs(self, bucket):
        self.events.append("list_blobs")
        return await super().list_blobs(bucket)


async def make_world(iris: Iris, settings: ServiceSettings) -> SimpleNamespace:
    """A tenant over the fakes, with helpers that act at a chosen age."""
    events: list[str] = []
    stamp = SimpleNamespace(at=NOW)
    store, files = Events(events), EventFiles(events, lambda: stamp.at)
    tenancy = Tenancy(
        store,
        files,
        settings,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        iris=iris,
    )
    await tenancy.ensure_system_database()
    tenant = (await tenancy.create("Ghent", library_slots(), CREATOR)).id
    access, _ = await tenancy.get(tenant)
    world = SimpleNamespace(
        events=events,
        store=store,
        files=files,
        tenancy=tenancy,
        iris=iris,
        tenant=tenant,
        database=access.database_name,
        stamp=stamp,
    )

    def session(age: timedelta = timedelta()):
        return open_session(
            store,
            database=world.database,
            tenant_iri=tenant,
            principal=CREATOR,
            clock=lambda: NOW - age,
            iris=iris,
        )

    async def load(aggregate: str, age: timedelta) -> URIRef:
        async with session(age) as opened:
            return await opened.load_graph(aggregate, TURTLE, rdf_format=RdfFormat.TURTLE)

    async def commit(aggregate: str, loaded: list[URIRef] = (), keys: list[str] = ()) -> str:
        triples = [(URIRef(aggregate), FILE_KEY, Literal(k)) for k in keys]
        async with session() as opened:
            return await opened.add_graph(aggregate, triples, loaded_graphs=list(loaded))

    async def blob(key: str, age: timedelta) -> None:
        world.stamp.at = NOW - age
        await files.put(world.database, key, b"bytes")
        world.stamp.at = NOW

    async def snapshot() -> tuple[frozenset, list[str]]:
        rows = await store.query(world.database, ALL_QUADS)
        quads = frozenset(tuple(map(str, row)) for row in rows)
        return quads, [b.file_key for b in await files.list_blobs(world.database)]

    async def sweep(**keywords) -> TenantSweepReport:
        return await sweep_tenant(
            tenancy, store, files, iris, world.tenant, clock=lambda: NOW, **keywords
        )

    async def holds(graph: URIRef) -> bool:
        asked = await store.query(world.database, f"ASK {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}")
        return bool(asked.askAnswer)

    async def marked(graph: URIRef) -> bool:
        text = fill(
            "ASK { GRAPH $r { $g $p ?t } }",
            r=term(iris.registry(tenant)),
            g=term(graph),
            p=term(LOADED_AT),
        )
        return bool((await store.query(world.database, text)).askAnswer)

    world.session, world.load, world.commit, world.blob = session, load, commit, blob
    world.snapshot, world.sweep, world.holds, world.marked = snapshot, sweep, holds, marked
    return world


def book(world: SimpleNamespace, n: int, folder: str = "books") -> str:
    return f"{world.tenant}/{folder}/{UUID(int=n)}"


@pytest.fixture
async def world() -> SimpleNamespace:
    """The worked example: B+G1 committed, G2 old and uncommitted, G3 young, S+k1, k2 old, k3 young."""
    made = await make_world(Iris(SETTINGS), SETTINGS)
    made.book, made.scan = book(made, 1), book(made, 2, "scans")
    made.g1 = await made.load(made.book, 3 * HOUR)
    await made.commit(made.book, [made.g1])
    made.g2 = await made.load(made.book, 2 * HOUR)
    made.g3 = await made.load(made.book, timedelta(minutes=5))
    await made.commit(made.scan, keys=["k1"])
    await made.blob("k1", 3 * HOUR)
    await made.blob("k2", 3 * HOUR)
    await made.blob("k3", timedelta(minutes=1))
    return made


# -- the worked example ------------------------------------------------------------------------


async def test_a_dry_run_reports_the_orphans_and_changes_nothing(world):
    before = await world.snapshot()
    report = await world.sweep()
    assert report == TenantSweepReport(
        tenant=world.tenant,
        older_than_seconds=3600,
        loaded_graphs=[str(world.g2)],
        blobs=["k2"],
        removed_loaded_graphs=False,
        removed_blobs=False,
        skipped_blobs=[],
    )
    assert await world.snapshot() == before, "graphs, markers and blobs are as they were"


async def test_removing_loaded_graphs_leaves_the_blobs(world):
    report = await world.sweep(remove=True)
    assert not await world.holds(world.g2), "the orphan is gone"
    assert [await world.holds(g) for g in (world.g1, world.g3)] == [True, True]
    assert (report.removed_loaded_graphs, report.removed_blobs) == (True, False)
    assert [b.file_key for b in await world.files.list_blobs(world.database)] == ["k1", "k2", "k3"]


async def test_removing_blobs_leaves_the_loaded_graphs(world):
    report = await world.sweep(remove_blobs=True)
    assert [b.file_key for b in await world.files.list_blobs(world.database)] == ["k1", "k3"]
    assert await world.holds(world.g2), "the orphan graph stays"
    assert (report.removed_loaded_graphs, report.removed_blobs) == (False, True)


async def test_removing_both_keeps_what_a_commit_names_or_will_name(world):
    report = await world.sweep(remove=True, remove_blobs=True)
    assert report.loaded_graphs == [str(world.g2)] and report.blobs == ["k2"]
    assert not await world.holds(world.g2)
    assert [await world.holds(g) for g in (world.g1, world.g3)] == [True, True]
    assert [b.file_key for b in await world.files.list_blobs(world.database)] == ["k1", "k3"]
    async with world.session() as opened:
        await opened.replace_graph(world.book, [], await _version(opened, world.book), [world.g3])
        assert await opened.loaded_graphs(world.book) == [world.g3], "G3's commit succeeds"


async def _version(opened, aggregate: str) -> str:
    return (await opened.get_graph(aggregate))[2]


async def test_the_grace_period_is_the_one_asked_for(world):
    report = await world.sweep(older_than=timedelta(minutes=2))
    assert report.older_than_seconds == 120
    assert report.loaded_graphs == sorted([str(world.g2), str(world.g3)])
    assert report.blobs == ["k2"], "k3 is a minute old"


async def test_a_sweep_twice_removes_nothing_the_second_time(world):
    await world.sweep(remove=True, remove_blobs=True)
    again = await world.sweep(remove=True, remove_blobs=True)
    assert again.loaded_graphs == [] and again.blobs == []


# -- what is never a candidate -----------------------------------------------------------------


async def test_a_blob_named_by_any_graph_of_the_tenant_is_kept(world):
    await world.blob("k4", 3 * HOUR)
    await world.commit(book(world, 3, "scans"), keys=["k4"])
    report = await world.sweep(remove_blobs=True)
    assert report.blobs == ["k2"]
    assert "k4" in [b.file_key for b in await world.files.list_blobs(world.database)]


async def test_the_tenant_graphs_and_aggregates_are_never_candidates(world):
    before = await world.snapshot()
    report = await world.sweep(remove=True, remove_blobs=True)
    after = await world.snapshot()
    removed = before[0] - after[0]
    registry = str(world.iris.registry(world.tenant))
    assert {g for g, *_ in removed if g != registry} == {str(world.g2)}, "only the orphan's graph"
    assert {p for g, _, p, _ in removed if g == registry} == {str(LOADED_AT)}, "and markers"
    assert str(world.iris.meta(world.tenant)) in {g for g, *_ in after[0]}
    assert str(world.iris.registry(world.tenant)) in {g for g, *_ in after[0]}
    assert report.loaded_graphs == [str(world.g2)]


async def test_the_tenant_roots_loaded_graph_is_never_a_candidate(world):
    root_graph = await world.load(world.tenant, 5 * HOUR)
    report = await world.sweep(remove=True)
    assert str(root_graph) not in (report.loaded_graphs or [])
    assert await world.holds(root_graph), "its graph is untouched"


async def test_another_tenants_graphs_and_blobs_are_untouched(world):
    other = (await world.tenancy.create("Bruges", library_slots(), CREATOR)).id
    access, _ = await world.tenancy.get(other)
    async with open_session(
        world.store,
        database=access.database_name,
        tenant_iri=other,
        principal=CREATOR,
        clock=lambda: NOW - 5 * HOUR,
        iris=world.iris,
    ) as opened:
        theirs = await opened.load_graph(
            f"{other}/books/{UUID(int=9)}", TURTLE, rdf_format=RdfFormat.TURTLE
        )
    world.stamp.at = NOW - 5 * HOUR
    await world.files.put(access.database_name, "theirs", b"x")
    await world.sweep(remove=True, remove_blobs=True)
    asked = await world.store.query(
        access.database_name, f"ASK {{ GRAPH <{theirs}> {{ ?s ?p ?o }} }}"
    )
    assert asked.askAnswer
    assert [b.file_key for b in await world.files.list_blobs(access.database_name)] == ["theirs"]


async def test_a_graph_with_no_marker_counts_as_old(world):
    unmarked = world.iris.mint_loaded_graph(world.tenant, world.book)
    graph = Graph()
    graph.add((URIRef("https://example.org/b"), URIRef("https://example.org/p"), Literal("x")))
    await world.store.put_graph(world.database, unmarked, graph)
    report = await world.sweep()
    assert str(unmarked) in report.loaded_graphs


async def test_a_commit_between_the_read_and_the_delete_keeps_the_graph(world):
    async def commit_g2():
        async with world.session() as opened:
            await opened.replace_graph(
                world.book, [], await _version(opened, world.book), [world.g1, world.g2]
            )

    world.store.after = (
        str(FILE_KEY),
        commit_g2,
    )  # after the owners were read, before the blobs' keys
    report = await world.sweep(remove=True)
    assert report.loaded_graphs == [str(world.g2)], "the sweep had judged it an orphan"
    assert await world.holds(world.g2), "the guarded delete saw the new registry entry"
    async with world.session() as opened:
        assert world.g2 in await opened.loaded_graphs(world.book)


# -- the markers (PD-6) ------------------------------------------------------------------------


async def test_the_marker_of_a_graph_a_commit_owns_goes_only_with_remove(world):
    assert await world.marked(world.g1)
    await world.sweep()
    assert await world.marked(world.g1), "a dry run deletes no marker"
    await world.sweep(remove=True)
    assert not await world.marked(world.g1), "the commit made it useless"
    async with world.session() as opened:
        assert world.g1 in await opened.loaded_graphs(world.book), "its registry entry survives"


async def test_the_marker_of_a_removed_orphan_goes_with_it(world):
    await world.sweep(remove=True)
    assert not await world.marked(world.g2)
    assert await world.marked(world.g3), "a young load keeps its marker"


async def test_an_old_marker_whose_graph_was_never_put_is_removed(world):
    world.store.on("put_graph", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await world.load(world.book, 2 * HOUR)
    (stale,) = [m for m in await _markers(world) if m not in (world.g1, world.g2, world.g3)]
    await world.sweep()
    assert await world.marked(stale)
    await world.sweep(remove=True)
    assert not await world.marked(stale)


async def test_a_young_marker_whose_graph_is_not_there_yet_is_kept(world):
    world.store.on("put_graph", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await world.load(world.book, timedelta(minutes=5))
    (young,) = [m for m in await _markers(world) if m not in (world.g1, world.g2, world.g3)]
    await world.sweep(remove=True)
    assert await world.marked(young), "the load may still be on its way to the PUT"


async def _markers(world) -> list[URIRef]:
    text = fill(
        "SELECT ?g WHERE { GRAPH $r { ?g $p ?t } }",
        r=term(world.iris.registry(world.tenant)),
        p=term(LOADED_AT),
    )
    return [URIRef(row.g) for row in await world.store.query(world.database, text)]


# -- a policy whose loaded-graph template has no {root} (N1) -----------------------------------

FLAT = "{base}{tenant_id}/{type}/{id}"
BOOK_TYPE = "book"


async def test_under_a_template_without_root_an_old_orphan_is_still_found():
    settings = ServiceSettings(
        base="http://mwb.meaningfy.ws/",
        prefix="mwb",
        tenant_segment="projects",
        creator_role="librarian",
        roles_claim="roles",
        deployment="k3f9a2x",
        iri_policy=IriPolicy(
            tenant_template="{base}project/{tenant_id}",
            aggregate_template=FLAT,
            part_template=FLAT,
            loaded_graph_template=FLAT,
            tenant_id=IdSpec(kind=IdKind.RANDOM, length=7),
            object_id=IdSpec(kind=IdKind.RANDOM, length=13),
        ),
    )
    iris = Iris(settings, *iri_types(load_schema(TOY_SCHEMA)))
    world = await make_world(iris, settings)
    aggregate = str(iris.mint_aggregate(world.tenant, BOOK_TYPE, "books"))
    orphan = await world.load(aggregate, 2 * HOUR)
    kept = await world.load(aggregate, 3 * HOUR)
    await world.commit(aggregate, [kept])
    assert iris.loaded_graph_root(str(orphan)) is None
    report = await world.sweep(remove=True)
    assert report.loaded_graphs == [str(orphan)]
    assert not await world.holds(orphan) and await world.holds(kept)


# -- the order of the reads (PD-7) --------------------------------------------------------------


def _position(events: list[str], needle: str) -> int:
    return next(i for i, e in enumerate(events) if needle in e)


async def test_graphs_are_listed_before_their_owners_and_blobs_before_their_keys(world):
    world.events.clear()
    await world.sweep()
    events = world.events
    assert _position(events, "DISTINCT ?g") < _position(events, str(OWNED_BY))
    assert _position(events, "list_blobs") < _position(events, str(FILE_KEY))


# -- a blob the object store refuses (PD-9), the logs, the refusals (PD-11) ---------------------


async def test_a_blob_the_store_refuses_is_skipped_and_the_sweep_goes_on(world, caplog):
    await world.blob("k5", 3 * HOUR)
    world.files.on("delete", ValueError("a key the adapter refuses"))
    with caplog.at_level(logging.INFO):
        report = await world.sweep(remove_blobs=True)
    assert report.blobs == ["k2", "k5"] and report.skipped_blobs == ["k2"]
    keys = [b.file_key for b in await world.files.list_blobs(world.database)]
    assert "k5" not in keys and "k2" in keys
    assert any(r.__dict__.get("step") == "sweep-blob-skipped" for r in caplog.records)


async def test_each_removal_is_logged_with_its_step(world, caplog):
    with caplog.at_level(logging.INFO, logger="rdf_persistence.services.tenant_sweep"):
        await world.sweep(remove=True, remove_blobs=True)
    steps = [(r.__dict__.get("step"), r.__dict__.get("resource")) for r in caplog.records]
    assert steps == [("sweep-loaded-graph", str(world.g2)), ("sweep-blob", "k2")]


async def test_a_dry_run_logs_no_removal(world, caplog):
    with caplog.at_level(logging.INFO, logger="rdf_persistence.services.tenant_sweep"):
        await world.sweep()
    assert caplog.records == []


async def test_a_tenant_that_is_not_there_is_not_found(world):
    with pytest.raises(NotFound):
        await sweep_tenant(
            world.tenancy,
            world.store,
            world.files,
            world.iris,
            f"{world.tenant}0x",
            clock=lambda: NOW,
        )


async def test_a_tenant_being_deleted_is_refused_and_nothing_is_read(world):
    _, version = await world.tenancy.get(world.tenant)
    world.store.on("drop_dataset", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await world.tenancy.delete(world.tenant, version)
    with pytest.raises(Conflict):
        await world.sweep(remove=True, remove_blobs=True)
    assert world.files.sent("list_blobs") == [], "no blob was looked at"
    assert not any("DISTINCT" in e for e in world.events), "no graph was looked at"


async def test_a_missing_bucket_stops_the_sweep_before_any_removal(world):
    await world.files.delete_bucket(world.database)
    with pytest.raises(TenantGone):
        await world.sweep(remove=True, remove_blobs=True)
    assert await world.holds(world.g2), "no graph was removed either"

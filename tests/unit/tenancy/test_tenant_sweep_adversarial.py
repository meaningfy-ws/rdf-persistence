"""Attacks on the live-tenant sweep: try to make it delete what it must keep (live-tenant-sweep PD-2 to PD-9).

Each test asserts the safe behaviour the design promises. The world is the worked example of
``test_tenant_sweep``: B+G1 committed, G2 old and uncommitted, G3 young, S+k1, k2 old, k3 young.
"""

import asyncio
from datetime import timedelta
from uuid import UUID

import pytest
from rdflib import XSD, Graph, Literal, URIRef

from rdf_persistence.core.domain.exceptions import DatabaseGone, StoreUnavailable
from rdf_persistence.core.domain.sparql import term
from tests.toy import library_slots
from tests.unit.tenancy import test_tenant_sweep as worked
from tests.unit.tenancy.test_tenant_sweep import (
    ALL_QUADS,
    CREATOR,
    FILE_KEY,
    HOUR,
    LOADED_AT,
    NOW,
    OWNED_BY,
    book,
)

world = worked.world  # the worked-example fixture
SUBJECT, PREDICATE = URIRef("https://example.org/s"), URIRef("https://example.org/p")


async def plant(world, graph: URIRef, marker: Literal | None = None, extra=()) -> URIRef:
    """Put ``graph`` with one triple (and ``extra``) into the tenant database; mark its load if asked."""
    content = Graph()
    content.add((SUBJECT, PREDICATE, Literal("x")))
    for triple in extra:
        content.add(triple)
    await world.store.put_graph(world.database, graph, content)
    if marker is not None:
        await mark(world, graph, marker)
    return graph


async def mark(world, graph: URIRef, marker: Literal) -> None:
    triple = f"{term(graph)} {term(LOADED_AT)} {marker.n3()}"
    registry = term(world.iris.registry(world.tenant))
    await world.store.update(world.database, f"INSERT DATA {{ GRAPH {registry} {{ {triple} }} }}")


def at(age: timedelta) -> Literal:
    return Literal(NOW - age)


async def quads(world) -> frozenset:
    return frozenset(
        tuple(map(str, row)) for row in await world.store.query(world.database, ALL_QUADS)
    )


async def blob_keys(world) -> list[str]:
    return [b.file_key for b in await world.files.list_blobs(world.database)]


# -- (b) what is never a loaded graph ---------------------------------------------------------


async def test_a_graph_that_reads_as_another_tenants_loaded_graph_is_kept(world):
    other = (await world.tenancy.create("Bruges", library_slots(), CREATOR)).id
    foreign = world.iris.mint_loaded_graph(other, f"{other}/books/{UUID(int=9)}")
    await plant(world, foreign, at(5 * HOUR))
    report = await world.sweep(remove=True)
    assert str(foreign) not in report.loaded_graphs, (
        "the other tenant's look-alike graph is not reported"
    )
    assert await world.holds(foreign), "that graph is still in the store"


@pytest.mark.parametrize("which", ["not-a-uuid", "meta"])
async def test_a_loaded_graph_of_something_that_is_no_aggregate_is_kept(world, which):
    roots = {
        "not-a-uuid": f"{world.tenant}/books/not-a-uuid",
        "meta": str(world.iris.meta(world.tenant)),
    }
    graph = world.iris.mint_loaded_graph(world.tenant, roots[which])
    await plant(world, graph, at(5 * HOUR))
    report = await world.sweep(remove=True)
    assert str(graph) not in report.loaded_graphs, (
        "the graph of something that is no aggregate is not reported"
    )
    assert await world.holds(graph), "that graph is still in the store"


async def test_old_markers_on_the_tenants_own_graphs_do_not_make_them_candidates(world):
    own = [
        world.iris.meta(world.tenant),
        world.iris.registry(world.tenant),
        URIRef(f"{world.book}/graph"),
        URIRef(world.book),
        URIRef(world.tenant),
        world.iris.access(world.tenant),
    ]
    for graph in own:
        await mark(world, graph, at(9 * HOUR))
    before = await quads(world)
    report = await world.sweep(remove=True, remove_blobs=True)
    removed = before - await quads(world)
    registry = str(world.iris.registry(world.tenant))
    assert {g for g, *_ in removed if g != registry} == {str(world.g2)}, (
        "only the stale graph is removed, not the ones with old markers"
    )
    assert report.loaded_graphs == [str(world.g2)], "only the stale graph is reported"


# -- (f) odd markers and keys ------------------------------------------------------------------

UNREADABLE = {
    "naive": Literal("2026-11-10T09:00:00", datatype=XSD.dateTime),
    "ill-typed": Literal("not a time", datatype=XSD.dateTime),
}


# design RF-1: such a marker counts as none. Equivalence classes: a datetime with no zone (naive), a value
# that is no datetime (ill-typed; a date-only, a plain and a number literal are the same)
@pytest.mark.parametrize("kind", UNREADABLE)
@pytest.mark.parametrize("remove", [False, True])
async def test_a_marker_another_tool_wrote_badly_does_not_crash_the_sweep(world, kind, remove):
    odd = await plant(
        world, world.iris.mint_loaded_graph(world.tenant, world.book), UNREADABLE[kind]
    )
    report = await world.sweep(remove=remove)
    assert str(world.g2) in report.loaded_graphs, (
        "the stale graph is reported despite the badly written marker"
    )
    assert await world.holds(world.g1), "the first kept graph is still in the store"
    assert await world.holds(world.g3), "the second kept graph is still in the store"
    assert await world.holds(odd) or remove, "a dry run removes nothing"


async def test_two_markers_for_one_graph_count_as_young_when_either_is_young(world):
    graph = await plant(world, world.iris.mint_loaded_graph(world.tenant, world.book), at(5 * HOUR))
    await mark(world, graph, at(timedelta(minutes=1)))
    report = await world.sweep(remove=True)
    assert str(graph) not in report.loaded_graphs, "the graph with a young marker is not reported"
    assert await world.holds(graph), "that graph is still in the store"


async def test_a_two_hour_old_marker_written_with_an_offset_is_old(world):
    graph = await plant(world, world.iris.mint_loaded_graph(world.tenant, world.book))
    await mark(world, graph, Literal("2026-11-10T12:30:00+05:00", datatype=XSD.dateTime))
    assert str(graph) in (await world.sweep()).loaded_graphs, "07:30Z is four and a half hours old"
    other = await plant(world, world.iris.mint_loaded_graph(world.tenant, world.book))
    await mark(world, other, Literal("2026-11-10T17:30:00+05:00", datatype=XSD.dateTime))
    assert str(other) not in (await world.sweep()).loaded_graphs, "12:30Z is a half hour old"


async def test_what_is_exactly_as_old_as_the_grace_period_is_kept(world):
    graph = await plant(world, world.iris.mint_loaded_graph(world.tenant, world.book), at(HOUR))
    await world.blob("edge", HOUR)
    report = await world.sweep(older_than=HOUR, remove=True, remove_blobs=True)
    assert str(graph) not in report.loaded_graphs, (
        "the graph as old as the grace period is not reported"
    )
    assert "edge" not in report.blobs, "its blob is not reported"
    assert await world.holds(graph), "that graph is still in the store"
    assert "edge" in await blob_keys(world), "its blob is still in the store"


async def test_with_no_grace_period_what_was_just_written_is_kept(world):
    now_graph = await plant(
        world, world.iris.mint_loaded_graph(world.tenant, world.book), at(timedelta())
    )
    await world.blob("now", timedelta())
    report = await world.sweep(older_than=timedelta(), remove=True, remove_blobs=True)
    assert str(now_graph) not in report.loaded_graphs, "what was just written is not reported"
    assert "now" not in report.blobs, "its blob is not reported"
    assert str(world.g3) in report.loaded_graphs, "a minute-old orphan is old enough then"


# Keys with a control character are left out: the one blob-key rule (``checked_blob_key``) refuses them, as Garage does.
ODD_KEYS = ['a"b', "a'b", "a b", "é☃", "a\\b", "}{ ; DROP ALL", "<x>"]


@pytest.mark.parametrize("key", ODD_KEYS)
async def test_blob_keys_with_odd_characters_are_matched_exactly(world, key):
    await world.blob(key, 3 * HOUR)
    await world.blob(key + "-orphan", 3 * HOUR)
    await world.commit(book(world, 7, "scans"), keys=[key])
    report = await world.sweep(remove_blobs=True)
    assert report.blobs == sorted(["k2", key + "-orphan"]), (
        "the report lists the orphan blobs, matched exactly"
    )
    assert report.skipped_blobs == [], "no blob is skipped"
    assert key in await blob_keys(world), "the blob with odd characters is kept"
    assert key + "-orphan" not in await blob_keys(world), "its look-alike orphan is deleted"


async def test_a_key_named_as_an_iri_is_kept(world):
    await world.blob("urn:key:iri", 3 * HOUR)
    await world.store.put_graph(
        world.database,
        URIRef(f"{world.book}/graph2"),
        _one((SUBJECT, FILE_KEY, URIRef("urn:key:iri"))),
    )
    report = await world.sweep(remove_blobs=True)
    assert "urn:key:iri" not in report.blobs, "a key named as an IRI is not reported"
    assert "urn:key:iri" in await blob_keys(world), "that blob is still in the store"


def _one(triple) -> Graph:
    graph = Graph()
    graph.add(triple)
    return graph


async def test_a_blob_named_only_inside_a_loaded_graph_is_kept_even_as_that_graph_goes(world):
    await world.blob("inside", 3 * HOUR)
    inside = await plant(
        world,
        world.iris.mint_loaded_graph(world.tenant, world.book),
        at(5 * HOUR),
        extra=[(SUBJECT, FILE_KEY, Literal("inside"))],
    )
    report = await world.sweep(remove=True, remove_blobs=True)
    assert str(inside) in report.loaded_graphs, "the graph that goes is reported"
    assert "inside" not in report.blobs, "its blob is not reported"
    assert not await world.holds(inside), "the graph is gone"
    assert "inside" in await blob_keys(world), "its blob is still in the store"
    assert "inside" in (await world.sweep(remove_blobs=True)).blobs, "next run: no graph names it"


# -- (a) interleavings --------------------------------------------------------------------------


async def test_a_commit_that_names_a_blob_between_the_listing_and_the_key_read_keeps_it(world):
    async def name_k2():
        await world.commit(book(world, 8, "scans"), keys=["k2"])

    world.store.after = (str(FILE_KEY), name_k2)
    report = await world.sweep(remove_blobs=True)
    assert "k2" not in report.blobs, "a blob named by a late commit is not reported"
    assert "k2" in await blob_keys(world), "that blob is still in the store"


async def test_a_commit_between_the_listing_and_the_owner_read_makes_the_graph_owned(world):
    async def commit_g2():
        async with world.session() as opened:
            version = (await opened.get_graph(world.book))[2]
            await opened.replace_graph(world.book, [], version, [world.g1, world.g2])

    world.store.after = (str(OWNED_BY), commit_g2)
    report = await world.sweep(remove=True)
    assert str(world.g2) not in report.loaded_graphs, (
        "a graph owned by a late commit is not reported"
    )
    assert await world.holds(world.g2), "that graph is still in the store"


async def test_a_graph_loaded_after_the_listing_is_never_judged(world):
    late: list[URIRef] = []

    async def load_late():
        late.append(await world.load(world.book, 5 * HOUR))

    world.store.after = (str(OWNED_BY), load_late)
    report = await world.sweep(remove=True)
    assert str(late[0]) not in report.loaded_graphs, (
        "a graph loaded after the listing is not reported"
    )
    assert await world.holds(late[0]), "that graph is still in the store"


async def test_two_sweeps_at_once_remove_each_orphan_once_and_keep_the_rest(world):
    first, second = await asyncio.gather(
        world.sweep(remove=True, remove_blobs=True), world.sweep(remove=True, remove_blobs=True)
    )
    assert first.loaded_graphs == [str(world.g2)], "the first sweep reports the stale graph"
    assert second.loaded_graphs in ([str(world.g2)], []), (
        "the second sweep reports the stale graph or nothing, never another"
    )
    assert [await world.holds(g) for g in (world.g1, world.g2, world.g3)] == [True, False, True], (
        "only the stale graph is gone"
    )
    assert await blob_keys(world) == ["k1", "k3"], "only the stale blobs are gone"


# -- (d) (c) (e) what is touched and what is said ----------------------------------------------


async def test_a_dry_run_sends_no_update_and_no_delete(world):
    updates, deletes = len(world.store.sent("update")), len(world.files.sent("delete"))
    report = await world.sweep()
    assert len(world.store.sent("update")) == updates, "a dry run sent no update"
    assert len(world.files.sent("delete")) == deletes, "a dry run sent no delete"
    assert report.loaded_graphs, "the dry run still reports the stale graphs"
    assert report.blobs, "the dry run still reports the stale blobs"
    assert report.skipped_blobs == [], "the dry run skipped no blob"


async def test_removing_graphs_alone_deletes_no_blob_and_removing_blobs_alone_updates_nothing(
    world,
):
    await world.sweep(remove=True)
    assert world.files.sent("delete") == [], "removing graphs alone deletes no blob"
    updates = len(world.store.sent("update"))
    await world.sweep(remove_blobs=True)
    assert len(world.store.sent("update")) == updates, "removing blobs alone sends no update"


async def test_the_sweep_reads_and_deletes_only_in_the_tenants_bucket(world):
    other = (await world.tenancy.create("Bruges", library_slots(), CREATOR)).id
    theirs = (await world.tenancy.get(other))[0].database_name
    world.stamp.at = NOW - 5 * HOUR
    await world.files.put(theirs, "k2", b"same key, other tenant")
    await world.sweep(remove=True, remove_blobs=True)
    assert world.files.sent("list_blobs")[-1] == world.database, (
        "the blobs are listed in the tenant's own bucket"
    )
    assert all(sent.startswith(f"{world.database}/") for sent in world.files.sent("delete")), (
        "every delete stays in the tenant's own bucket"
    )
    assert await world.files.get(theirs, "k2") == b"same key, other tenant", (
        "the other tenant's blob with the same key is untouched"
    )


async def test_a_remove_blobs_report_says_nothing_was_skipped_when_nothing_was(world):
    report = await world.sweep(remove=True)
    assert report.removed_blobs is False, "the report says no blob was removed"
    assert report.skipped_blobs == [], "the report says no blob was skipped"
    assert report.blobs == ["k2"], "the report names the one stale blob"
    assert await blob_keys(world) == ["k1", "k2", "k3"], (
        "without the remove flag no blob is deleted"
    )


# -- (f) failures mid-sweep ---------------------------------------------------------------------


async def test_a_gone_database_stops_the_sweep_before_any_blob_is_deleted(world):
    await world.store.drop_dataset(world.database)
    with pytest.raises(DatabaseGone):
        await world.sweep(remove=True, remove_blobs=True)
    assert world.files.sent("delete") == [], "no blob is deleted once the database is gone"
    assert await blob_keys(world) == ["k1", "k2", "k3"], "every blob is still there"


async def test_a_failing_graph_delete_leaves_the_rest_for_the_next_run(world):
    second = await plant(
        world, world.iris.mint_loaded_graph(world.tenant, world.book), at(4 * HOUR)
    )
    world.store.on("update", StoreUnavailable("down"), after=1)
    with pytest.raises(StoreUnavailable):
        await world.sweep(remove=True, remove_blobs=True)
    assert await blob_keys(world) == ["k1", "k2", "k3"], "no blob went before the graphs finished"
    await world.sweep(remove=True, remove_blobs=True)
    assert [await world.holds(g) for g in (world.g2, second, world.g1, world.g3)] == [
        False,
        False,
        True,
        True,
    ], "the failing delete leaves the later graphs in place"
    assert await blob_keys(world) == ["k1", "k3"], "the blobs are untouched"


async def test_a_failing_blob_delete_stops_the_sweep_and_a_second_run_finishes(world):
    await world.blob("k5", 3 * HOUR)
    world.files.on("delete", StoreUnavailable("down"), after=1)
    with pytest.raises(StoreUnavailable):
        await world.sweep(remove=True, remove_blobs=True)
    assert not await world.holds(world.g2), "the graph that remained is removed"
    assert await world.holds(world.g1), "the untouched graph is still in the store"
    report = await world.sweep(remove=True, remove_blobs=True)
    assert report.blobs == ["k5"], "the report names the blob left for the next run"
    assert await blob_keys(world) == ["k1", "k3"], "the blobs that were not stale remain"

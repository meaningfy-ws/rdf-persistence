"""Attacks on the live-tenant sweep: try to make it delete what it must keep (live-tenant-sweep PD-2 to PD-9).

Each test asserts the safe behaviour the design promises. The world is the worked example of
``test_tenant_sweep``: B+G1 committed, G2 old and uncommitted, G3 young, S+k1, k2 old, k3 young.
"""

import asyncio
from datetime import timedelta
from uuid import UUID

import pytest
from rdflib import XSD, Graph, Literal, URIRef

from rdf_persistence.domain.exceptions import DatabaseGone, StoreUnavailable
from rdf_persistence.domain.sparql import term
from tests.toy import library_slots
from tests.unit.services import test_tenant_sweep as worked
from tests.unit.services.test_tenant_sweep import (
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
    assert str(foreign) not in report.loaded_graphs
    assert await world.holds(foreign)


@pytest.mark.parametrize("which", ["not-a-uuid", "meta"])
async def test_a_loaded_graph_of_something_that_is_no_aggregate_is_kept(world, which):
    roots = {
        "not-a-uuid": f"{world.tenant}/books/not-a-uuid",
        "meta": str(world.iris.meta(world.tenant)),
    }
    graph = world.iris.mint_loaded_graph(world.tenant, roots[which])
    await plant(world, graph, at(5 * HOUR))
    report = await world.sweep(remove=True)
    assert str(graph) not in report.loaded_graphs
    assert await world.holds(graph)


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
    assert {g for g, *_ in removed if g != registry} == {str(world.g2)}
    assert report.loaded_graphs == [str(world.g2)]


# -- (f) odd markers and keys ------------------------------------------------------------------

UNREADABLE = {
    "naive": Literal("2026-11-10T09:00:00", datatype=XSD.dateTime),
    "ill-typed": Literal("not a time", datatype=XSD.dateTime),
    "date-only": Literal("2026-11-10", datatype=XSD.date),
    "plain": Literal("yesterday"),
    "number": Literal(3),
}


@pytest.mark.parametrize("kind", UNREADABLE)  # design RF-1: such a marker counts as none
@pytest.mark.parametrize("remove", [False, True])
async def test_a_marker_another_tool_wrote_badly_does_not_crash_the_sweep(world, kind, remove):
    odd = await plant(
        world, world.iris.mint_loaded_graph(world.tenant, world.book), UNREADABLE[kind]
    )
    report = await world.sweep(remove=remove)
    assert str(world.g2) in report.loaded_graphs
    assert await world.holds(world.g1) and await world.holds(world.g3)
    assert await world.holds(odd) or remove, "a dry run removes nothing"


async def test_two_markers_for_one_graph_count_as_young_when_either_is_young(world):
    graph = await plant(world, world.iris.mint_loaded_graph(world.tenant, world.book), at(5 * HOUR))
    await mark(world, graph, at(timedelta(minutes=1)))
    report = await world.sweep(remove=True)
    assert str(graph) not in report.loaded_graphs
    assert await world.holds(graph)


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
    assert str(graph) not in report.loaded_graphs and "edge" not in report.blobs
    assert await world.holds(graph) and "edge" in await blob_keys(world)


async def test_with_no_grace_period_what_was_just_written_is_kept(world):
    now_graph = await plant(
        world, world.iris.mint_loaded_graph(world.tenant, world.book), at(timedelta())
    )
    await world.blob("now", timedelta())
    report = await world.sweep(older_than=timedelta(), remove=True, remove_blobs=True)
    assert str(now_graph) not in report.loaded_graphs and "now" not in report.blobs
    assert str(world.g3) in report.loaded_graphs, "a minute-old orphan is old enough then"


ODD_KEYS = ['a"b', "a'b", "a b", "é☃", "a\nb", "a\\b", "}{ ; DROP ALL", "<x>", "k\u0000z"]


@pytest.mark.parametrize("key", ODD_KEYS)
async def test_blob_keys_with_odd_characters_are_matched_exactly(world, key):
    await world.blob(key, 3 * HOUR)
    await world.blob(key + "-orphan", 3 * HOUR)
    await world.commit(book(world, 7, "scans"), keys=[key])
    report = await world.sweep(remove_blobs=True)
    assert report.blobs == sorted(["k2", key + "-orphan"]) and report.skipped_blobs == []
    assert key in await blob_keys(world) and key + "-orphan" not in await blob_keys(world)


@pytest.mark.parametrize(
    "named",
    [
        URIRef("urn:key:iri"),
        Literal("urn:key:iri", lang="en"),
        Literal("urn:key:iri", datatype=XSD.token),
    ],
)
async def test_a_key_named_as_an_iri_or_a_tagged_literal_is_kept(world, named):
    await world.blob("urn:key:iri", 3 * HOUR)
    await world.store.put_graph(
        world.database, URIRef(f"{world.book}/graph2"), _one((SUBJECT, FILE_KEY, named))
    )
    report = await world.sweep(remove_blobs=True)
    assert "urn:key:iri" not in report.blobs and "urn:key:iri" in await blob_keys(world)


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
    assert str(inside) in report.loaded_graphs and "inside" not in report.blobs
    assert not await world.holds(inside) and "inside" in await blob_keys(world)
    assert "inside" in (await world.sweep(remove_blobs=True)).blobs, "next run: no graph names it"


# -- (a) interleavings --------------------------------------------------------------------------


async def test_a_commit_that_names_a_blob_between_the_listing_and_the_key_read_keeps_it(world):
    async def name_k2():
        await world.commit(book(world, 8, "scans"), keys=["k2"])

    world.store.after = (str(FILE_KEY), name_k2)
    report = await world.sweep(remove_blobs=True)
    assert "k2" not in report.blobs and "k2" in await blob_keys(world)


async def test_a_commit_between_the_listing_and_the_owner_read_makes_the_graph_owned(world):
    async def commit_g2():
        async with world.session() as opened:
            version = (await opened.get_graph(world.book))[2]
            await opened.replace_graph(world.book, [], version, [world.g1, world.g2])

    world.store.after = (str(OWNED_BY), commit_g2)
    report = await world.sweep(remove=True)
    assert str(world.g2) not in report.loaded_graphs
    assert await world.holds(world.g2)


async def test_a_graph_loaded_after_the_listing_is_never_judged(world):
    late: list[URIRef] = []

    async def load_late():
        late.append(await world.load(world.book, 5 * HOUR))

    world.store.after = (str(OWNED_BY), load_late)
    report = await world.sweep(remove=True)
    assert str(late[0]) not in report.loaded_graphs
    assert await world.holds(late[0])


async def test_two_sweeps_at_once_remove_each_orphan_once_and_keep_the_rest(world):
    first, second = await asyncio.gather(
        world.sweep(remove=True, remove_blobs=True), world.sweep(remove=True, remove_blobs=True)
    )
    assert first.loaded_graphs == [str(world.g2)]
    assert second.loaded_graphs in ([str(world.g2)], [])
    assert [await world.holds(g) for g in (world.g1, world.g2, world.g3)] == [True, False, True]
    assert await blob_keys(world) == ["k1", "k3"]


# -- (d) (c) (e) what is touched and what is said ----------------------------------------------


async def test_a_dry_run_sends_no_update_and_no_delete(world):
    updates, deletes = len(world.store.sent("update")), len(world.files.sent("delete"))
    report = await world.sweep()
    assert (len(world.store.sent("update")), len(world.files.sent("delete"))) == (updates, deletes)
    assert report.loaded_graphs and report.blobs and report.skipped_blobs == []


async def test_removing_graphs_alone_deletes_no_blob_and_removing_blobs_alone_updates_nothing(
    world,
):
    await world.sweep(remove=True)
    assert world.files.sent("delete") == []
    updates = len(world.store.sent("update"))
    await world.sweep(remove_blobs=True)
    assert len(world.store.sent("update")) == updates


async def test_the_sweep_reads_and_deletes_only_in_the_tenants_bucket(world):
    other = (await world.tenancy.create("Bruges", library_slots(), CREATOR)).id
    theirs = (await world.tenancy.get(other))[0].database_name
    world.stamp.at = NOW - 5 * HOUR
    await world.files.put(theirs, "k2", b"same key, other tenant")
    await world.sweep(remove=True, remove_blobs=True)
    assert world.files.sent("list_blobs")[-1] == world.database
    assert all(sent.startswith(f"{world.database}/") for sent in world.files.sent("delete"))
    assert await world.files.get(theirs, "k2") == b"same key, other tenant"


async def test_a_remove_blobs_report_says_nothing_was_skipped_when_nothing_was(world):
    report = await world.sweep(remove=True)
    assert (report.removed_blobs, report.skipped_blobs, report.blobs) == (False, [], ["k2"])
    assert await blob_keys(world) == ["k1", "k2", "k3"]


# -- (f) failures mid-sweep ---------------------------------------------------------------------


async def test_a_gone_database_stops_the_sweep_before_any_blob_is_deleted(world):
    await world.store.drop_dataset(world.database)
    with pytest.raises(DatabaseGone):
        await world.sweep(remove=True, remove_blobs=True)
    assert world.files.sent("delete") == []
    assert await blob_keys(world) == ["k1", "k2", "k3"]


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
    ]
    assert await blob_keys(world) == ["k1", "k3"]


async def test_a_failing_blob_delete_stops_the_sweep_and_a_second_run_finishes(world):
    await world.blob("k5", 3 * HOUR)
    world.files.on("delete", StoreUnavailable("down"), after=1)
    with pytest.raises(StoreUnavailable):
        await world.sweep(remove=True, remove_blobs=True)
    assert not await world.holds(world.g2) and await world.holds(world.g1)
    report = await world.sweep(remove=True, remove_blobs=True)
    assert report.blobs == ["k5"]
    assert await blob_keys(world) == ["k1", "k3"]

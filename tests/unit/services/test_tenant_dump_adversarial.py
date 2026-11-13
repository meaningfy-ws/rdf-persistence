"""Hostile archives, failures at each step and round trips of dump and restore (tenant-dump-restore, adversarial).

Written after task 3.1 to break it; the TC-10 to TC-27 cases of ``test_tenant_dump.py`` are not repeated. A test
named ``..._design_silent`` pins a guarantee the design does not state; its docstring says what it expects and why.
"""

import asyncio
import gzip
import io
import tarfile
import zlib
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from rdflib import Dataset, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS

from rdf_persistence.domain.exceptions import (
    InvalidBody,
    NotFound,
    PersistenceError,
    StoreUnavailable,
)
from rdf_persistence.domain.generated.service.rp_service import IriPolicy, TenantDump
from rdf_persistence.domain.media import N_QUADS
from rdf_persistence.domain.tenant_move import rewrite
from rdf_persistence.services.sweep import sweep
from rdf_persistence.services.tenant_dump import dump
from tests.toy import SETTINGS
from tests.unit.services.test_tenant_dump import (
    BLOB_BYTES,
    END,
    GRAPHS,
    MANIFEST,
    VIEW,
    at_version,
    dumped,
    edited,
    iris_of,
    manifest_of,
    moved,
    pack,
    populated,
    read_book,
    refused,
    restored,
    state_of,
    unpack,
)
from tests.unit.services.test_tenant_sweep import make_world

BLOCK = 512


def FROZEN() -> datetime:  # noqa: N802
    return datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def world() -> SimpleNamespace:
    return await populated(await make_world(iris_of(SETTINGS), SETTINGS))


def raw_tar(
    *members: tuple[str, bytes] | tuple[str, bytes, int], end: bool = True, marker: bool = True
) -> bytes:
    """A gzipped tar written block by block, so a header may lie: ``(name, payload)`` or ``(name, payload, declared size)``.

    A name is encoded as latin-1 so a test can plant a byte that is not UTF-8. ``marker`` adds the dump's ``end``
    member; ``end`` adds the tar's two zero blocks.
    """
    out = io.BytesIO()
    for name, payload, *declared in (*members, *([(END, b"")] if marker else [])):
        info = tarfile.TarInfo(name)
        info.size = declared[0] if declared else len(payload)
        out.write(info.tobuf(tarfile.GNU_FORMAT, "latin-1", "surrogateescape"))
        out.write(payload + b"\0" * (-len(payload) % BLOCK))
    if end:
        out.write(b"\0" * 2 * BLOCK)
    return gzip.compress(out.getvalue())


async def head_of(world: SimpleNamespace) -> list[tuple[str, bytes]]:
    """The manifest and the graphs of a dump of the world."""
    return unpack(await dumped(world))[:2]


# -- hostile blob members: a blob is a regular file named blobs/<key> -------------------------------


@pytest.mark.parametrize(
    "name", ["blobs/", "blobs", "/etc/passwd", "../blobs/x", "manifest.json", "graphs.nq"]
)
async def test_a_member_whose_name_is_not_a_blob_name_is_refused_and_leaves_nothing(world, name):
    before = await state_of(world)
    with pytest.raises(InvalidBody):
        await restored(world, pack(*await head_of(world), ("blobs/ok", b"x"), (name, b"x")))
    assert await state_of(world) == before


@pytest.mark.parametrize("key", ["../x", "a/../../x"])
async def test_a_blob_key_that_climbs_out_of_the_bucket_is_refused_design_silent(world, key):
    """Design PD-3 says 'a regular file under blobs/'. ``blobs/../x`` is under ``blobs/`` as text only: an
    object store that maps keys to paths would write outside the bucket. Expected: refused. (A key with ``//``
    or a leading ``/`` is a legal object key a dump can hold, so it is not tested as hostile.)"""
    before = await state_of(world)
    with pytest.raises(InvalidBody):
        await restored(world, pack(*await head_of(world), (f"blobs/{key}", b"x")))
    assert await state_of(world) == before


async def test_two_blobs_with_one_key_are_refused_design_silent(world):
    """A real dump never repeats a key; a second ``blobs/a`` would silently replace the first. Expected: refused."""
    before = await state_of(world)
    with pytest.raises(InvalidBody):
        await restored(
            world, pack(*await head_of(world), ("blobs/a", b"first"), ("blobs/a", b"second"))
        )
    assert await state_of(world) == before


@pytest.mark.parametrize(
    "kind", [tarfile.LNKTYPE, tarfile.SYMTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE]
)
async def test_a_blob_member_that_is_a_link_or_a_device_is_refused(world, kind):
    before = await state_of(world)
    archive = pack(*await head_of(world), ("blobs/a", b"first"), ("blobs/l", b"", kind))
    with pytest.raises(InvalidBody):
        await restored(world, archive)
    assert await state_of(world) == before


async def test_a_second_manifest_in_place_of_the_graphs_is_refused(world):
    manifest, _ = await head_of(world)
    before = await state_of(world)
    with pytest.raises(InvalidBody):
        await restored(world, pack(manifest, manifest))
    assert await state_of(world) == before


async def test_an_archive_with_only_a_manifest_is_refused(world):
    before = await state_of(world)
    with pytest.raises(InvalidBody):
        await restored(world, pack((MANIFEST, (await head_of(world))[0][1])))
    assert await state_of(world) == before


async def test_a_blob_whose_header_declares_more_bytes_than_the_archive_holds_leaves_nothing(world):
    manifest, graphs = await head_of(world)
    archive = raw_tar(
        manifest, graphs, ("blobs/a", b"x" * 10), ("blobs/big", b"short", 10_000), end=False
    )
    before = await state_of(world)
    with pytest.raises(InvalidBody):
        await restored(world, archive)
    assert await state_of(world) == before


async def test_a_gzip_cut_inside_a_blob_leaves_nothing(world):
    manifest, graphs = await head_of(world)
    payload = (
        bytes(range(256)) * 4000
    )  # about a megabyte; gzip cannot shrink a repeated ramp enough to hide the cut
    full = raw_tar(manifest, graphs, ("blobs/a", payload))
    before = await state_of(world)
    with pytest.raises(InvalidBody):
        await restored(world, full[: len(full) * 2 // 3])
    assert await state_of(world) == before


async def test_a_blob_name_that_is_not_utf8_is_refused_design_silent(world):
    """The tar name ``blobs/\\xff`` is not UTF-8; the object store would fail to encode the key, with an error
    that is not ``InvalidBody``. Expected: ``InvalidBody`` (the archive is hostile), nothing left."""
    manifest, graphs = await head_of(world)
    before = await state_of(world)
    with pytest.raises(InvalidBody):
        await restored(world, raw_tar(manifest, graphs, ("blobs/\xff", b"x")))
    assert await state_of(world) == before


async def test_a_graphs_member_that_is_not_utf8_or_not_n_quads_is_refused(world):
    manifest, _ = await head_of(world)
    for junk in (b"\xff\xfe\x00 not a quad", b"<a> <b> .\n", b"\x00" * 64):
        assert "N-Quads" in await refused(world, pack(manifest, (GRAPHS, junk)))


# -- hostile quads: what the graphs may name -----------------------------------------------------------


def other_tenant(world: SimpleNamespace) -> str:
    return str(world.iris.mint_tenant())


def quad(subject: str, obj: str, graph: str) -> bytes:
    return f"<{subject}> <{DCTERMS.relation}> <{obj}> <{graph}> .\n".encode()


async def test_a_quad_in_the_graph_of_another_tenants_aggregate_is_refused(world):
    other = other_tenant(world)
    graph = f"{world.iris.mint_aggregate(other, 'book', 'books')}/graph"
    reason = await refused(
        world,
        edited(await dumped(world), GRAPHS, lambda nq: nq + quad(world.book, world.book, graph)),
    )
    assert graph in reason


@pytest.mark.parametrize("which", ["meta", "registry", "tenant", "access"])
async def test_a_quad_in_another_tenants_system_graph_is_refused(world, which):
    other = other_tenant(world)
    graph = {
        "meta": str(world.iris.meta(other)),
        "registry": str(world.iris.registry(other)),
        "tenant": other,
        "access": f"{world.iris.access(other)}/graph",
    }[which]
    await refused(
        world, edited(await dumped(world), GRAPHS, lambda nq: nq + quad(other, other, graph))
    )


async def test_the_source_tenants_access_record_graph_is_refused_if_a_dump_holds_it(world):
    """The access record lives in the system database; a dump that names its graph must not write it."""
    access = f"{world.iris.access(world.tenant)}/graph"
    await refused(
        world,
        edited(
            await dumped(world),
            GRAPHS,
            lambda nq: nq + quad(str(world.iris.access(world.tenant)), world.tenant, access),
        ),
    )


async def test_a_reference_to_another_tenants_aggregate_is_never_rewritten_to_the_new_tenant(world):
    """Design PD-5 checks graph names only. A subject or object naming another tenant's aggregate inside a legal
    graph is either refused or kept verbatim; it must never be moved into the new tenant's space."""
    foreign = str(world.iris.mint_aggregate(other_tenant(world), "book", "books"))
    data = edited(
        await dumped(world),
        GRAPHS,
        lambda nq: nq + quad(world.book, foreign, f"{world.iris.meta(world.tenant)}"),
    )
    try:
        new = (await restored(world, data)).id
    except InvalidBody:
        return
    record, _ = await world.tenancy.get(new)
    exported = (await world.store.export_quads(record.database_name)).decode()
    assert f"<{foreign}>" in exported, "kept verbatim"
    assert world.iris.tenant_id_of(new) not in foreign


async def test_a_dump_that_claims_another_source_tenant_than_its_quads_come_from_is_refused(world):
    """The manifest names tenant X (consistent with itself) while the quads are the world's tenant's: nothing is
    moved, so every graph is foreign to the new tenant."""
    claimed = other_tenant(world)

    def claim(payload: bytes) -> bytes:
        return (
            TenantDump.model_validate_json(payload)
            .model_copy(
                update={
                    "source_tenant": claimed,
                    "source_tenant_id": world.iris.tenant_id_of(claimed),
                }
            )
            .model_dump_json()
            .encode()
        )

    await refused(world, edited(await dumped(world), MANIFEST, claim))


# -- manifest -----------------------------------------------------------------------------------------


def with_manifest(data: bytes, **changes) -> bytes:
    return edited(
        data,
        MANIFEST,
        lambda payload: (
            TenantDump.model_validate_json(payload)
            .model_copy(update=changes)
            .model_dump_json()
            .encode()
        ),
    )


@pytest.mark.parametrize(
    "source",
    [
        "{base}libraries/books",  # a path word as the tenant id
        "{base}libraries/libraries",
        "{base}libraries/",
        "{base}",
        "not an iri",
    ],
)
async def test_a_source_tenant_that_is_not_a_tenant_iri_or_is_a_reserved_word_is_refused(
    world, source
):
    data = with_manifest(
        await dumped(world),
        source_tenant=source.format(base=SETTINGS.base),
        source_tenant_id="books",
    )
    await refused(world, data)


async def test_a_source_tenant_id_that_does_not_belong_to_the_source_tenant_is_refused(world):
    other_id = world.iris.tenant_id_of(other_tenant(world))
    assert other_id in await refused(
        world, with_manifest(await dumped(world), source_tenant_id=other_id)
    )


@pytest.mark.parametrize("empty", ["", " "])
async def test_an_empty_source_tenant_id_is_refused_and_does_not_rewrite_everything(world, empty):
    await refused(world, with_manifest(await dumped(world), source_tenant_id=empty))


async def test_extra_manifest_fields_are_refused_or_ignored_never_a_crash(world):
    def add(payload: bytes) -> bytes:
        return payload[:-1] + b', "surprise": {"nested": [1, 2]}}'

    data = edited(await dumped(world), MANIFEST, add)
    try:
        summary = await restored(world, data)
    except InvalidBody:
        return
    assert summary.label == "Ghent"


@pytest.mark.parametrize(
    "text", [b'{"format_version": "1"}', b"[]", b"null", b'"x"', b"{" * 5000, b"\xff\xfe"]
)
async def test_a_manifest_of_the_wrong_shape_is_refused(world, text):
    await refused(world, edited(await dumped(world), MANIFEST, lambda _: text))


async def test_a_format_version_given_as_the_string_one_is_refused_or_read_as_one(world):
    def stringly(payload: bytes) -> bytes:
        return payload.replace(b'"format_version":1', b'"format_version":"1"')

    data = edited(await dumped(world), MANIFEST, stringly)
    assert b'"format_version":"1"' in dict(unpack(data))[MANIFEST], "the edit took"
    try:
        summary = await restored(world, data)
    except InvalidBody:
        return
    assert summary.id != world.tenant


async def test_a_schema_without_version_round_trips_and_refuses_a_schema_that_has_one(world):
    bare = at_version(None)  # type: ignore[arg-type]
    out = io.BytesIO()
    await dump(world.tenancy, world.store, world.files, world.iris, bare, world.tenant, out)
    assert manifest_of(out.getvalue()).schema_version is None
    assert (await restored(world, out.getvalue(), view=bare)).id != world.tenant
    assert "1.0.0" in await refused(world, out.getvalue(), view=at_version("1.0.0"))


async def test_an_empty_schema_version_is_not_a_missing_one(world):
    """RISK-4: version '' in the dump against none in the service. The two must not be taken as one."""
    out = io.BytesIO()
    await dump(
        world.tenancy, world.store, world.files, world.iris, at_version(""), world.tenant, out
    )
    await refused(world, out.getvalue(), view=at_version(None))  # type: ignore[arg-type]


# -- write order and cleanup --------------------------------------------------------------------------


async def test_a_failing_create_bucket_leaves_nothing_and_raises_the_original_error(world):
    data = await dumped(world)
    before = await state_of(world)
    world.files.on("create_bucket", StoreUnavailable("no bucket for you"))
    with pytest.raises(StoreUnavailable, match="no bucket for you"):
        await restored(world, data)
    assert await state_of(world) == before


async def test_a_failing_second_blob_put_drops_the_database_and_the_bucket(world):
    await world.files.put(world.database, "k2", b"second")
    await world.files.put(world.database, "k3", b"third")
    data = await dumped(world)
    before = await state_of(world)
    world.files.on("put", StoreUnavailable("the object store broke"), after=1)
    with pytest.raises(StoreUnavailable, match="the object store broke"):
        await restored(world, data)
    assert len(world.files.sent("put")) == 3 + 2, (
        "three to set up, two tried: the third was never put"
    )
    assert await state_of(world) == before


async def test_a_bucket_gone_before_the_record_fails_the_restore_cleanly(world):
    data = await dumped(world)
    before = await state_of(world)
    put = world.files.put

    async def put_then_lose_the_bucket(bucket: str, key: str, payload: bytes) -> None:
        await put(bucket, key, payload)
        if bucket != world.database:
            await world.files.delete_bucket(bucket)

    world.files.put = put_then_lose_the_bucket  # type: ignore[method-assign]
    with pytest.raises(PersistenceError, match="vanished"):
        await restored(world, data)
    assert await state_of(world) == before


async def test_a_database_gone_in_an_archive_without_blobs_is_still_noticed():
    """With no blob the vanished check is reached straight after the import."""
    world = await make_world(iris_of(SETTINGS), SETTINGS)
    data = await dumped(world)
    before = await state_of(world)
    import_quads = world.store.import_quads

    async def import_then_lose_the_database(name: str, nquads: bytes) -> None:
        await import_quads(name, nquads)
        await world.store.drop_dataset(name)

    world.store.import_quads = import_then_lose_the_database  # type: ignore[method-assign]
    with pytest.raises(PersistenceError, match="vanished"):
        await restored(world, data)
    assert await state_of(world) == before


async def test_a_cancelled_restore_writes_no_record_and_the_sweep_drops_what_it_left(world):
    data = await dumped(world)
    before = await state_of(world)
    world.files.on("put", asyncio.CancelledError(), after=0)  # type: ignore[arg-type]
    with pytest.raises(asyncio.CancelledError):
        await restored(world, data)
    databases, buckets, tenants = await state_of(world)
    assert tenants == before[2], "no access record: the tenant does not exist"
    await sweep(world.tenancy, world.store, world.files, SETTINGS)
    assert await state_of(world) == before, "the start-up sweep finished the cleanup"


async def test_a_blob_failure_late_in_a_big_archive_leaves_nothing(world):
    for n in range(25):
        await world.files.put(world.database, f"blob-{n:02d}", bytes([n]) * 100)
    data = await dumped(world)
    before = await state_of(world)
    world.files.on("put", StoreUnavailable("late failure"), after=20)
    with pytest.raises(StoreUnavailable):
        await restored(world, data)
    assert await state_of(world) == before


# -- dump ------------------------------------------------------------------------------------------------


async def test_a_failing_export_raises_unchanged_and_writes_nothing_to_out(world):
    world.store.on("export_quads", StoreUnavailable("the store is down"))
    out = io.BytesIO()
    with pytest.raises(StoreUnavailable, match="the store is down"):
        await dump(world.tenancy, world.store, world.files, world.iris, VIEW, world.tenant, out)
    assert out.getvalue() == b""


async def test_a_failing_listing_raises_unchanged_and_writes_nothing_to_out(world):
    world.files.on("list_blobs", StoreUnavailable("no listing"))
    out = io.BytesIO()
    with pytest.raises(StoreUnavailable, match="no listing"):
        await dump(world.tenancy, world.store, world.files, world.iris, VIEW, world.tenant, out)
    assert out.getvalue() == b""


async def test_a_blob_read_that_fails_otherwise_is_raised_and_the_partial_archive_never_restores(
    world,
):
    await world.files.put(world.database, "k2", b"second")
    world.files.on("get", StoreUnavailable("read failed"), after=1)
    out = io.BytesIO()
    with pytest.raises(StoreUnavailable, match="read failed"):
        await dump(world.tenancy, world.store, world.files, world.iris, VIEW, world.tenant, out)
    await refused(world, out.getvalue())


async def test_an_archive_cut_after_a_whole_blob_is_refused_not_restored_without_the_rest(world):
    """A transfer cut at a member boundary (no tar end blocks, no gzip end) restores a tenant that silently lacks
    the blobs after the cut. Expected: ``InvalidBody``. Design silent (PD-3 names only a broken stream)."""
    head = await head_of(world)
    raw = io.BytesIO()
    for name, payload in (*head, ("blobs/k1", BLOB_BYTES)):
        info = tarfile.TarInfo(name)
        info.size = len(payload)
        raw.write(info.tobuf(tarfile.GNU_FORMAT, "utf-8", "surrogateescape"))
        raw.write(payload + b"\0" * (-len(payload) % BLOCK))
    packer = zlib.compressobj(wbits=31)
    cut = packer.compress(raw.getvalue()) + packer.flush(zlib.Z_SYNC_FLUSH)  # no end marker
    await refused(world, cut)


async def test_every_blob_gone_still_dumps_the_manifest_and_the_graphs(world):
    world.files.on("get", NotFound("gone"), times=5)
    data = await dumped(world)
    assert [n for n, _ in unpack(data)] == [MANIFEST, GRAPHS, END], "no blob member"
    assert (await restored(world, data)).label == "Ghent", "and it restores"


KEYS = {
    "slashes": "a/b/c.txt",
    "unicode": "été/日本語 ✓.bin",
    "spaces": "with space and %20 and ?query=1&x#frag",
    "long": "k" * 300,
    "long-path": "/".join(["segment-of-some-length"] * 20),
    "dots": "..hidden",
}


@pytest.mark.parametrize("key", list(KEYS.values()), ids=list(KEYS))
async def test_a_blob_key_survives_a_dump_and_a_restore(world, key):
    await world.files.put(world.database, key, key.encode())
    new = (await restored(world, await dumped(world))).id
    record, _ = await world.tenancy.get(new)
    assert await world.files.get(record.database_name, key) == key.encode(), "the blob's bytes"


@pytest.mark.parametrize("key", ["line\nbreak", "tab\there", "del\x7f"], ids=repr)
async def test_a_blob_key_with_a_control_character_is_refused_by_the_one_key_rule(world, key):
    """Garage refuses such a key (``checked_blob_key``); the archive of a store that held one is refused whole."""
    before = await state_of(world)
    with pytest.raises(InvalidBody, match="key"):
        await restored(world, pack(*await head_of(world), (f"blobs/{key}", b"x")))
    assert await state_of(world) == before, "database and bucket dropped, no record"


async def test_a_blob_of_zero_bytes_and_one_of_every_byte_value_survive(world):
    await world.files.put(world.database, "empty", b"")
    new = (await restored(world, await dumped(world))).id
    record, _ = await world.tenancy.get(new)
    assert await world.files.get(record.database_name, "empty") == b""
    assert await world.files.get(record.database_name, "k1") == BLOB_BYTES
    assert {b.file_key for b in await world.files.list_blobs(record.database_name)} == {
        "empty",
        "k1",
    }


async def test_a_dump_is_deterministic_in_its_members_for_the_same_clock(world):
    first, second = io.BytesIO(), io.BytesIO()
    for out in (first, second):
        await dump(
            world.tenancy,
            world.store,
            world.files,
            world.iris,
            VIEW,
            world.tenant,
            out,
            clock=FROZEN,
        )
    assert [n for n, _ in unpack(first.getvalue())] == [n for n, _ in unpack(second.getvalue())]
    assert manifest_of(first.getvalue()) == manifest_of(second.getvalue())


# -- round trips ----------------------------------------------------------------------------------------


def named_graphs(nquads: bytes) -> dict[str, object]:
    dataset = Dataset()
    dataset.parse(data=nquads, format=N_QUADS)
    return {str(g.identifier): g for g in dataset.graphs() if len(g)}


async def test_a_second_dump_of_a_restored_tenant_names_the_new_tenant_and_holds_the_same_graphs(
    world,
):
    first = await dumped(world)
    new = (await restored(world, first)).id
    second = await dumped(world, new)
    one, two = manifest_of(first), manifest_of(second)
    assert (two.source_tenant, one.source_tenant) == (new, world.tenant)
    assert two.source_tenant_id == world.iris.tenant_id_of(new)
    assert (two.label, two.iri_policy, two.schema_id) == (one.label, one.iri_policy, one.schema_id)
    old_id, new_id = world.iris.tenant_id_of(world.tenant), world.iris.tenant_id_of(new)
    mapped = dict(unpack(first))[GRAPHS].replace(old_id.encode(), new_id.encode())
    expected, got = named_graphs(mapped), named_graphs(dict(unpack(second))[GRAPHS])
    assert expected.keys() == got.keys()
    assert all(isomorphic(expected[name], got[name]) for name in got)
    assert [n for n, _ in unpack(second)] == [n for n, _ in unpack(first)]
    assert dict(unpack(second))["blobs/k1"] == BLOB_BYTES


async def test_restoring_one_archive_twice_gives_two_tenants_that_share_no_iri(world):
    data = await dumped(world)
    one, two = (await restored(world, data)).id, (await restored(world, data)).id
    assert len({world.tenant, one, two}) == 3
    exported = []
    for tenant in (world.tenant, one, two):
        record, _ = await world.tenancy.get(tenant)
        dataset = Dataset()
        dataset.parse(data=await world.store.export_quads(record.database_name), format=N_QUADS)
        # the toolkit's own IRIs: those under the base (a loaded document's own IRIs are the consumer's data)
        exported.append(
            {
                str(t)
                for q in dataset.quads()
                for t in (q[0], q[3])
                if str(t).startswith(SETTINGS.base)
            }
        )
    assert not (exported[0] & exported[1]) and not (exported[0] & exported[2])
    assert not (exported[1] & exported[2])
    assert len({(await world.tenancy.get(t))[0].database_name for t in (one, two)}) == 2
    for tenant in (one, two):
        assert (await read_book(world, tenant, moved(world, world.book, tenant))).label == "Dune"


async def test_a_restore_under_a_policy_that_puts_the_id_before_a_dash_round_trips():
    settings = SETTINGS.model_copy(
        update={
            "iri_policy": IriPolicy(
                aggregate_template="{base}{tenant_id}-{id}",
                part_template="{base}{tenant_id}-{id}",
                loaded_graph_template="{base}{tenant_id}-{id}",
            )
        }
    )
    world = await populated(await make_world(iris_of(settings), settings))
    new = (await restored(world, await dumped(world))).id
    book = moved(world, world.book, new)
    assert world.iris.is_aggregate(new, book)
    assert (await read_book(world, new, book)).label == "Dune"
    assert not world.iris.is_aggregate(world.tenant, book)


# -- rewrite --------------------------------------------------------------------------------------------

IDS = st.from_regex(r"[a-z0-9]{1,6}", fullmatch=True)
SEPARATORS = st.sampled_from(["/", "-", ".", ":", "?", "#"])
BASE = "https://ex.org/"


@st.composite
def iri_texts(draw) -> str:
    words = draw(st.lists(IDS, min_size=1, max_size=5))
    text = words[0]
    for word in words[1:]:
        text += draw(SEPARATORS) + word
    return BASE + text


def dataset_with(iri: str, other: str) -> Dataset:
    dataset = Dataset()
    graph = dataset.graph(URIRef(iri))
    graph.add((URIRef(iri), DCTERMS.relation, URIRef(other)))
    graph.add((URIRef(iri), DCTERMS.title, Literal(f"about {other} and {iri}")))
    return dataset


def quads_of(dataset: Dataset) -> set[tuple]:
    return set(dataset.quads())


@settings(
    max_examples=150, suppress_health_check=[HealthCheck.too_slow], deadline=None, derandomize=True
)
@given(iri=iri_texts(), other=iri_texts(), old=IDS, new=IDS)
def test_rewrite_changes_nothing_when_the_ids_are_equal_and_never_touches_literals(
    iri, other, old, new
):
    source = dataset_with(iri, other)
    assert quads_of(rewrite(source, BASE, old, old)) == quads_of(source), "equal ids: no change"
    for _, predicate, obj, _ in rewrite(source, BASE, old, new).quads():
        assert predicate in (DCTERMS.relation, DCTERMS.title), "predicates are never moved"
        if predicate == DCTERMS.title:
            assert str(obj) == f"about {other} and {iri}", "a literal is never moved"


@settings(
    max_examples=200, suppress_health_check=[HealthCheck.too_slow], deadline=None, derandomize=True
)
@given(iri=iri_texts(), other=iri_texts(), old=IDS, new=IDS)
def test_rewrite_to_a_new_id_and_back_restores_the_dataset_when_the_new_id_is_not_there(
    iri, other, old, new
):
    assume(old != new and new not in iri and new not in other)
    source = dataset_with(iri, other)
    there = rewrite(source, BASE, old, new)
    assert quads_of(rewrite(there, BASE, new, old)) == quads_of(source), "there and back again"


@pytest.mark.parametrize(("old", "new"), [("ab", "abc"), ("abc", "ab"), ("a", "a0"), ("1", "10")])
def test_an_old_id_that_is_a_prefix_of_the_new_one_or_the_reverse_is_matched_whole(old, new):
    longer = max(old, new, key=len)
    iri = f"{BASE}t/{old}/x/{longer}z/{old}-{old}.{old}?q={old}#{old}"
    quads = list(rewrite(dataset_with(iri, iri), BASE, old, new).quads())
    ((s, _, o, g),) = [q for q in quads if q[1] == DCTERMS.relation]
    expected = f"{BASE}t/{new}/x/{longer}z/{new}-{new}.{new}?q={new}#{new}"
    assert {str(s), str(g)} == {expected}, "subject and graph"
    assert str(o) == expected, "object"


async def test_an_id_in_a_query_or_a_fragment_moves_with_the_path_design_silent(world):
    """PD-4 rewrites every delimited token after ``base``: ``?`` and ``#`` are delimiters, so the id in a query
    or fragment of a tenant IRI moves too. Pinned so a change of that rule is deliberate."""
    old = world.iris.tenant_id_of(world.tenant)
    iri = f"{world.tenant}/books/x?owner={old}#{old}"
    quads = rewrite(dataset_with(iri, iri), SETTINGS.base, old, "newid").quads()
    ((s, _, _, _),) = [q for q in quads if q[1] == DCTERMS.relation]
    assert str(s) == f"{SETTINGS.base}libraries/newid/books/x?owner=newid#newid", (
        "path, query, fragment"
    )

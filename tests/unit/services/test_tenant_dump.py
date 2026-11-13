"""Dump and restore of a tenant over the fakes (tenant-dump-restore PD-3, PD-5, PD-6, PD-7; TC-10 to TC-27).

The world is the sweep test's tenant ``T`` (Ghent) with a book ``B``, a graph ``g`` loaded for ``B``, a graph
``r`` loaded for the root, and a scan ``S`` with one blob. Every test names its TC id.
"""

import copy
import io
import logging
import tarfile
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from rdflib import URIRef
from rdflib.compare import isomorphic

from rdf_persistence.domain.exceptions import (
    Conflict,
    InvalidBody,
    NotFound,
    PersistenceError,
    StoreUnavailable,
)
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.generated.service.rp_service import (
    GrantSet,
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
    TenantDump,
)
from rdf_persistence.domain.iris import Iris
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import iri_types
from rdf_persistence.services.sweep import sweep
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.services.tenant_dump import dump, restore
from tests.fixtures.library.generated.books import Book
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, BOB, SETTINGS, TOY_SCHEMA, dune, role, toy_mapper
from tests.unit.services.test_tenant_sweep import (
    BOOK_TYPE,
    FLAT,
    TURTLE,
    make_world,
)

VIEW = load_schema(TOY_SCHEMA)
RESTORER = Principal(id=BOB)
SCAN_TYPE = "scan"
MANIFEST, GRAPHS = "manifest.json", "graphs.nq"
BLOB_BYTES = bytes(range(256))
FLAT_SETTINGS = ServiceSettings(
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
        object_id=IdSpec(kind=IdKind.RANDOM, length=12),
    ),
)


def iris_of(settings: ServiceSettings) -> Iris:
    return Iris(settings, *iri_types(VIEW))


async def populated(world: SimpleNamespace, title: str | None = None) -> SimpleNamespace:
    """``world`` with the book B, the loads g (for B) and r (for the root), and the scan S with its blob."""
    iris, tenant = world.iris, world.tenant
    world.book = str(iris.mint_aggregate(tenant, BOOK_TYPE, "books"))
    world.scan = str(iris.mint_aggregate(tenant, SCAN_TYPE, "scans"))
    async with world.session() as opened:
        world.g = await opened.load_graph(world.book, TURTLE, rdf_format=RdfFormat.TURTLE)
        world.r = await opened.load_graph(tenant, TURTLE, rdf_format=RdfFormat.TURTLE)
        book = dune(world.book).model_copy(update={"label": title or "Dune"})
        await opened.add_graph(world.book, toy_mapper().to_triples(book), loaded_graphs=[world.g])
        graph, _, version = await opened.get_graph(tenant)
        await opened.replace_graph(tenant, list(graph), version, loaded_graphs=[world.r])
    await world.commit(world.scan, keys=["k1"])
    await world.files.put(world.database, "k1", BLOB_BYTES)
    return world


async def dumped(world: SimpleNamespace, tenant: str | None = None) -> bytes:
    out = io.BytesIO()
    await dump(
        world.tenancy, world.store, world.files, world.iris, VIEW, tenant or world.tenant, out
    )
    return out.getvalue()


async def restored(
    world: SimpleNamespace, data: bytes, *, tenancy: Tenancy | None = None, view=VIEW
):
    return await restore(tenancy or world.tenancy, world.iris, view, io.BytesIO(data), RESTORER)


def unpack(data: bytes) -> list[tuple[str, bytes]]:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        return [(m.name, tar.extractfile(m).read()) for m in tar.getmembers()]  # type: ignore[union-attr]


def pack(*entries: tuple[str, bytes] | tuple[str, bytes, bytes]) -> bytes:
    """A tar.gz of ``(name, payload)`` regular files; a third item names another member type (a link, a directory)."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, payload, *kind in entries:
            info = tarfile.TarInfo(name)
            if kind:
                info.type = kind[0]
                info.linkname = "elsewhere"
                tar.addfile(info)
            else:
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def edited(data: bytes, name: str, change) -> bytes:
    """``data`` with the payload of member ``name`` replaced by ``change(payload)``."""
    return pack(*[(n, change(p) if n == name else p) for n, p in unpack(data)])


def manifest_of(data: bytes) -> TenantDump:
    return TenantDump.model_validate_json(dict(unpack(data))[MANIFEST])


async def state_of(world: SimpleNamespace) -> tuple:
    """Everything a restore may create: the databases, the buckets and the tenants with a record."""
    return (
        sorted(await world.store.list_datasets()),
        await world.files.list_buckets(""),
        [t.id for t in await world.tenancy.tenants()],
    )


async def read_book(
    world: SimpleNamespace, tenant: str, iri: str, who: Principal = RESTORER
) -> Book:
    async with world.tenancy.tenant_session(tenant, who) as opened:
        return await UnitOfWork(opened, toy_mapper()).get(Book, iri)


def moved(world: SimpleNamespace, old: str, new_tenant: str) -> str:
    """``old`` with the source tenant's id spelled as the new tenant's id."""
    return old.replace(world.iris.tenant_id_of(world.tenant), world.iris.tenant_id_of(new_tenant))


@pytest.fixture
async def world() -> SimpleNamespace:
    return await populated(await make_world(iris_of(SETTINGS), SETTINGS))


# -- TC-10, TC-13: a restored tenant answers like the original -----------------------------------


async def assert_answers_like_the_original(world: SimpleNamespace, summary) -> None:
    new = summary.id
    assert new != world.tenant, "a new tenant"
    assert summary.label == "Ghent", "the original's label"
    original = await read_book(world, world.tenant, world.book, Principal(id=ADA))
    restored_book = await read_book(world, new, moved(world, world.book, new))
    assert restored_book.id == moved(world, world.book, new), (
        "an IRI that carries the new tenant id"
    )
    assert restored_book.model_dump(exclude={"id", "chapters"}) == original.model_dump(
        exclude={"id", "chapters"}
    ), "the same slot values"
    assert [c.number for c in restored_book.chapters] == [c.number for c in original.chapters]
    book_new = moved(world, world.book, new)
    async with world.tenancy.tenant_session(new, RESTORER) as opened, world.session() as old:
        for owner, load in ((world.book, world.g), (world.tenant, world.r)):
            owner_new = moved(world, owner, new)
            assert await opened.loaded_graphs(owner_new) == [URIRef(moved(world, str(load), new))]
            copied = await opened.loaded_graph(owner_new, moved(world, str(load), new))
            assert isomorphic(copied, await old.loaded_graph(owner, str(load))), "the same triples"
    assert book_new == restored_book.id
    record, _ = await world.tenancy.get(new)
    assert await world.files.get(record.database_name, "k1") == BLOB_BYTES, "the blob byte for byte"


async def test_tc10_a_restored_tenant_answers_like_the_original(world):
    summary = await restored(world, await dumped(world))
    await assert_answers_like_the_original(world, summary)


async def test_tc13_a_restored_tenant_answers_like_the_original_under_the_flat_policy():
    flat = await populated(await make_world(iris_of(FLAT_SETTINGS), FLAT_SETTINGS))
    summary = await restored(flat, await dumped(flat))
    await assert_answers_like_the_original(flat, summary)
    new = summary.id
    for iri in (
        moved(flat, flat.book, new),
        moved(flat, str(flat.g), new),
        moved(flat, str(flat.r), new),
    ):
        assert flat.iris.is_aggregate(new, iri) or flat.iris.is_loaded_graph(new, iri), iri


async def test_tc11_the_restored_tenant_accepts_a_replace_and_the_original_is_unchanged(world):
    new = (await restored(world, await dumped(world))).id
    iri = moved(world, world.book, new)
    async with world.tenancy.tenant_session(new, RESTORER) as opened:
        work = UnitOfWork(opened, toy_mapper())
        book = await work.get(Book, iri)
        book.label = "Dune Messiah"
        work.add(book)
        await work.commit()
    assert (await read_book(world, new, iri)).label == "Dune Messiah"
    assert (await read_book(world, world.tenant, world.book, Principal(id=ADA))).label == "Dune"


async def test_tc12_only_the_restorer_is_granted_the_creator_role(world):
    _, version = await world.tenancy.get(world.tenant)
    grants = GrantSet(
        grants=[role("librarian", world.tenant, who) for who in (ADA, "urn:x:c", "urn:x:d")]
    )
    await world.tenancy.set_grants(world.tenant, grants, version, Principal(id=ADA))
    new = (await restored(world, await dumped(world))).id
    record, _ = await world.tenancy.get(new)
    assert [(g.assignee, g.role, g.target) for g in record.grants] == [(BOB, "librarian", new)]
    assert record.state == TenantState.ACTIVE
    assert not record.prohibitions


async def test_tc14_a_literal_holding_the_source_tenants_iri_is_kept():
    world = await make_world(iris_of(SETTINGS), SETTINGS)
    await populated(world, title=world.tenant)
    new = (await restored(world, await dumped(world))).id
    book = await read_book(world, new, moved(world, world.book, new))
    assert book.label == world.tenant, "the literal is the source tenant's IRI, not the new one"


# -- TC-15, TC-16: what a dump needs ----------------------------------------------------------------


async def test_tc15_a_tenant_being_deleted_is_a_conflict_and_writes_nothing(world):
    world.files.on("delete_bucket", StoreUnavailable("the object store is down"))
    _, version = await world.tenancy.get(world.tenant)
    with pytest.raises(StoreUnavailable):
        await world.tenancy.delete(world.tenant, version)
    out = io.BytesIO()
    with pytest.raises(Conflict):
        await dump(world.tenancy, world.store, world.files, world.iris, VIEW, world.tenant, out)
    assert out.getvalue() == b"", "nothing written"


async def test_tc15_an_unknown_tenant_is_not_found_and_writes_nothing(world):
    out = io.BytesIO()
    unknown = str(world.iris.mint_tenant())
    with pytest.raises(NotFound):
        await dump(world.tenancy, world.store, world.files, world.iris, VIEW, unknown, out)
    assert out.getvalue() == b"", "nothing written"


async def test_tc16_a_blob_gone_before_its_read_is_skipped_and_logged(world, caplog):
    await world.files.put(world.database, "k2", b"second")
    world.files.on("get", NotFound("deleted meanwhile"))  # the first read, of k1
    with caplog.at_level(logging.WARNING, logger="rdf_persistence.services.tenant_dump"):
        data = await dumped(world)
    assert [n for n, _ in unpack(data)] == [MANIFEST, GRAPHS, "blobs/k2"], "k1 is not in the dump"
    steps = [(r.__dict__.get("step"), r.__dict__.get("resource")) for r in caplog.records]
    assert steps == [("dump-blob-gone", "k1")]


async def test_a_dump_holds_the_manifest_the_graphs_and_the_blobs_in_that_order(world):
    data = await dumped(world)
    assert [n for n, _ in unpack(data)] == [MANIFEST, GRAPHS, "blobs/k1"]
    manifest = manifest_of(data)
    assert manifest.format_version == 1
    assert manifest.source_tenant == world.tenant
    assert manifest.source_tenant_id == world.iris.tenant_id_of(world.tenant)
    assert manifest.label == "Ghent"
    assert manifest.iri_policy == world.iris.effective_policy
    assert manifest.schema_id == VIEW.schema.id
    assert manifest.created_at.tzinfo is not None and manifest.created_at <= datetime.now(UTC)


# -- TC-17 to TC-21: a restore refuses a dump it cannot trust ----------------------------------------


async def refused(world: SimpleNamespace, data: bytes, **keywords) -> str:
    """The reason of the ``InvalidBody`` a restore of ``data`` raises; nothing has been created."""
    before = await state_of(world)
    with pytest.raises(InvalidBody) as caught:
        await restored(world, data, **keywords)
    assert await state_of(world) == before, "no database, bucket or record created"
    return str(caught.value)


def at_version(version: str):
    other = copy.deepcopy(VIEW)
    other.schema.version = version
    return other


async def test_tc17_another_schema_version_is_refused_naming_both(world):
    out = io.BytesIO()
    await dump(
        world.tenancy, world.store, world.files, world.iris, at_version("1.0.0"), world.tenant, out
    )
    reason = await refused(world, out.getvalue(), view=at_version("1.1.0"))
    assert "1.0.0" in reason and "1.1.0" in reason


async def test_tc17_another_schema_id_is_refused(world):
    other = copy.deepcopy(VIEW)
    other.schema.id = "https://example.org/other-schema"
    assert "https://example.org/other-schema" in await refused(
        world, await dumped(world), view=other
    )


async def test_a_format_version_other_than_one_is_refused_naming_it(world):
    def bump(payload: bytes) -> bytes:
        return (
            TenantDump.model_validate_json(payload)
            .model_copy(update={"format_version": 2})
            .model_dump_json()
            .encode()
        )

    assert "2" in await refused(world, edited(await dumped(world), MANIFEST, bump))


async def test_a_manifest_that_is_not_a_tenant_dump_is_refused(world):
    assert await refused(
        world, edited(await dumped(world), MANIFEST, lambda _: b'{"format_version": 1}')
    )
    assert await refused(world, edited(await dumped(world), MANIFEST, lambda _: b"not json"))


async def test_tc18_another_iri_policy_is_refused_naming_the_field():
    settings = FLAT_SETTINGS.model_copy(
        update={
            "iri_policy": FLAT_SETTINGS.iri_policy.model_copy(
                update={"object_id": IdSpec(kind=IdKind.RANDOM, length=12)}
            )
        }
    )
    world = await populated(await make_world(iris_of(settings), settings))

    def thirteen(payload: bytes) -> bytes:
        manifest = TenantDump.model_validate_json(payload)
        manifest.iri_policy.object_id.length = 13
        return manifest.model_dump_json().encode()

    assert "object_id.length" in await refused(
        world, edited(await dumped(world), MANIFEST, thirteen)
    )


async def test_a_policy_that_glues_the_tenant_id_to_a_letter_is_refused_naming_the_template():
    glued = ServiceSettings(
        base=SETTINGS.base,
        prefix=SETTINGS.prefix,
        tenant_segment=SETTINGS.tenant_segment,
        creator_role=SETTINGS.creator_role,
        roles_claim=SETTINGS.roles_claim,
        iri_policy=IriPolicy(tenant_template="{base}libraries/t{tenant_id}"),
    )
    world = await populated(await make_world(iris_of(glued), glued))
    assert "tenant_template" in await refused(world, await dumped(world))


async def test_tc19_a_quad_in_a_foreign_graph_is_refused_naming_it(world):
    foreign = b"<http://elsewhere.example/s> <http://elsewhere.example/p> <http://elsewhere.example/o> <http://elsewhere.example/g> .\n"
    reason = await refused(world, edited(await dumped(world), GRAPHS, lambda nq: nq + foreign))
    assert "http://elsewhere.example/g" in reason


async def test_tc19_a_quad_in_the_default_graph_is_refused(world):
    default = b"<http://elsewhere.example/s> <http://elsewhere.example/p> <http://elsewhere.example/o> .\n"
    assert "default graph" in await refused(
        world, edited(await dumped(world), GRAPHS, lambda nq: nq + default)
    )


async def test_a_dump_without_a_root_is_refused(world):
    def without_root(nq: bytes) -> bytes:
        return b"".join(
            line
            for line in nq.splitlines(keepends=True)
            if f"<{world.tenant}> ".encode() not in line
        )

    assert await refused(world, edited(await dumped(world), GRAPHS, without_root))


async def test_tc20_a_root_validator_that_refuses_stops_the_restore():
    seen = []

    def refuse(old, new, who):
        seen.append((old, who))
        raise InvalidBody("no more libraries")

    world = await populated(await make_world(iris_of(SETTINGS), SETTINGS))
    strict = Tenancy(
        world.store,
        world.files,
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        iris=world.iris,
        root_validators=[refuse],
    )
    assert "no more libraries" in await refused(world, await dumped(world), tenancy=strict)
    assert seen == [(None, RESTORER)], "old is None and who is the restorer"


@pytest.mark.parametrize(
    "damage",
    [
        lambda data: pack(*reversed(unpack(data)[:2]), *unpack(data)[2:]),
        lambda data: pack((MANIFEST, b"", tarfile.SYMTYPE), *unpack(data)[1:]),
        lambda data: pack(unpack(data)[0], (GRAPHS, b"", tarfile.SYMTYPE), *unpack(data)[2:]),
        lambda data: pack(unpack(data)[0], ("other.nq", unpack(data)[1][1]), *unpack(data)[2:]),
        lambda data: b"this is not gzip",
        lambda data: b"",
        lambda data: data[: len(data) // 3],
    ],
    ids=[
        "manifest-not-first",
        "manifest-link",
        "graphs-link",
        "graphs-misnamed",
        "not-gzip",
        "empty",
        "truncated",
    ],
)
async def test_tc21_an_archive_that_is_not_a_dump_is_refused(world, damage):
    await refused(world, damage(await dumped(world)))


# -- TC-22, TC-23, TC-26, TC-27: a restore that fails leaves no tenant -----------------------------------


async def test_tc22_a_failed_import_raises_and_leaves_no_database_bucket_or_record(world):
    data = await dumped(world)
    before = await state_of(world)
    world.store.on("import_quads", StoreUnavailable("the store failed"))
    with pytest.raises(StoreUnavailable, match="the store failed"):
        await restored(world, data)
    assert await state_of(world) == before


async def test_tc23_a_cleanup_that_fails_too_is_logged_and_the_sweep_finishes_it(world, caplog):
    data = await dumped(world)
    world.store.on("import_quads", StoreUnavailable("the import failed"))
    world.store.on("drop_dataset", StoreUnavailable("the drop failed"))
    with (
        caplog.at_level(logging.WARNING, logger="rdf_persistence.services.tenancy"),
        pytest.raises(StoreUnavailable, match="the import failed"),
    ):
        await restored(world, data)
    assert "restore-cleanup" in [r.__dict__.get("step") for r in caplog.records]
    assert len(await world.store.list_datasets()) == 3, "system, source and the leftover database"
    assert await world.files.list_buckets("") == [world.database], "the bucket was still dropped"
    await sweep(world.tenancy, world.store, world.files, SETTINGS)
    assert len(await world.store.list_datasets()) == 2, (
        "the sweep drops the database no record names"
    )


async def test_tc26_a_database_dropped_before_the_record_fails_the_restore_cleanly(world):
    data = await dumped(world)
    before = await state_of(world)
    put = world.files.put

    async def put_then_sweep(bucket: str, key: str, payload: bytes) -> None:
        await put(bucket, key, payload)
        if (
            bucket != world.database
        ):  # the new bucket: a start-up sweep elsewhere drops the new database
            await world.store.drop_dataset(bucket)

    world.files.put = put_then_sweep  # type: ignore[method-assign]
    with pytest.raises(PersistenceError, match="vanished"):
        await restored(world, data)
    assert await state_of(world) == before, "no record, and the bucket is gone"


async def test_tc27_a_member_that_is_not_a_blob_fails_after_the_blobs_before_it_and_leaves_nothing(
    world,
):
    members = unpack(await dumped(world))[:2]
    before = await state_of(world)
    archive = pack(*members, ("blobs/a", b"first"), ("notes.txt", b"not a blob"))
    with pytest.raises(InvalidBody):
        await restored(world, archive)
    assert world.files.sent("put")[-1].endswith("/a"), "blobs/a was put before the refusal"
    assert await state_of(world) == before


async def test_tc27_a_blob_member_that_is_a_directory_fails_and_leaves_nothing(world):
    members = unpack(await dumped(world))[:2]
    before = await state_of(world)
    with pytest.raises(InvalidBody):
        await restored(
            world, pack(*members, ("blobs/a", b"first"), ("blobs/dir", b"", tarfile.DIRTYPE))
        )
    assert await state_of(world) == before


# -- TC-24, TC-25 -----------------------------------------------------------------------------------


async def test_tc24_a_tenant_with_its_root_only_dumps_and_restores():
    world = await make_world(iris_of(SETTINGS), SETTINGS)
    data = await dumped(world)
    assert [n for n, _ in unpack(data)] == [MANIFEST, GRAPHS], "no blob"
    new = (await restored(world, data)).id
    record, _ = await world.tenancy.get(new)
    assert record.label == "Ghent" and await world.files.list_blobs(record.database_name) == []


async def test_tc25_the_restored_tenant_takes_the_roots_label_not_the_manifests():
    world = await make_world(iris_of(SETTINGS), SETTINGS)
    async with world.tenancy.tenant_session(world.tenant, Principal(id=ADA)) as opened:
        work = UnitOfWork(opened, toy_mapper())
        root = await work.get(Library, world.tenant)
        root.label = "New"  # the rename was cut after the root and before the record
        work.add(root)
        await work.commit()
    data = await dumped(world)
    assert manifest_of(data).label == "Ghent", "the record still says Ghent"
    summary = await restored(world, data)
    record, _ = await world.tenancy.get(summary.id)
    async with world.tenancy.tenant_session(summary.id, RESTORER) as opened:
        root = await UnitOfWork(opened, toy_mapper()).get(Library, summary.id)
    assert (summary.label, record.label, root.label) == ("New", "New", "New")

"""Dump and restore of a tenant over the fakes (tenant-dump-restore PD-3, PD-5, PD-6, PD-7; TC-10 to TC-27).

The world is the sweep test's tenant ``T`` (Ghent) with a book ``B``, a graph ``g`` loaded for ``B``, a graph
``r`` loaded for the root, and a scan ``S`` with one blob. Every test names its TC id.
"""

import copy
import gzip
import io
import logging
import tarfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import SKOS

from rdf_persistence.domain.exceptions import (
    Conflict,
    InvalidBody,
    NotFound,
    PersistenceError,
    StoreNotWired,
    StoreUnavailable,
)
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.layout import stamps_graph_iri
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.generated.service.rp_service import (
    GrantSet,
    IdKind,
    IdSpec,
    IriPolicy,
    MigrationStep,
    ServiceSettings,
    TenantDump,
)
from rdf_persistence.services.iris import Iris
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.migrations import SchemaChain
from rdf_persistence.services.migrations import chain_of as chain_of_schema
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import iri_types
from rdf_persistence.services.session import Clock, utc_now
from rdf_persistence.services.sweep import sweep
from rdf_persistence.services.tenancy import DEFAULT_STORE, Tenancy
from rdf_persistence.services.tenant_dump import dump, restore
from rdf_persistence.services.vocabulary import TOOLKIT_MIGRATIONS, metamodel
from rdf_persistence.testkit import FakeStore, assert_isomorphic
from tests.fixtures.library.generated.books import Book
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import (
    ADA,
    BOB,
    SETTINGS,
    TOY_MIGRATIONS,
    TOY_SCHEMA,
    dune,
    library,
    role,
    template,
    toy_mapper,
)
from tests.unit.services.migration_helpers import chain_of, migration, rename
from tests.unit.services.test_tenant_sweep import (
    BOOK_TYPE,
    FLAT,
    TURTLE,
)
from tests.unit.services.test_tenant_sweep import make_world as sweep_world

VIEW = load_schema(TOY_SCHEMA)
RUNNING = copy.deepcopy(
    VIEW
)  # the schema of a service that runs version 2 (the ``chains`` fixture)
RUNNING.schema.version = "2"
TOOLKIT_SCHEMA = metamodel().schema.id
TOOLKIT_VERSION = metamodel().schema.version  # the version the toolkit runs, whatever it moves to
LIBRARY_SCHEMA = "https://example.org/ns/library"
BASE_STAMPS = (
    (TOOLKIT_SCHEMA, TOOLKIT_VERSION),
    (LIBRARY_SCHEMA, "1"),
)  # what the toy kit stamps a tenant with
# the chains of the toy kit: both schemas have the one version "1" (no migration file)
TOY_CHAINS = [
    chain_of_schema(metamodel(), TOOLKIT_MIGRATIONS),
    chain_of_schema(VIEW, TOY_MIGRATIONS),
]
RESTORER = Principal(id=BOB)
SCAN_TYPE = "scan"
MANIFEST, GRAPHS, END = "manifest.json", "graphs.nq", "end"
BLOB_BYTES = bytes(range(256))
MAX_BYTES = 1 << 30  # the default of ``max_restore_bytes``
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


async def make_world(
    iris: Iris, settings: ServiceSettings, stamps: Sequence[tuple[str, str]] = BASE_STAMPS
) -> SimpleNamespace:
    """The sweep test's world, its tenant stamped as the toy kit stamps one (a dump of an unstamped tenant has no version)."""
    return await sweep_world(iris, settings, stamps)


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


async def dumped(
    world: SimpleNamespace, tenant: str | None = None, view=VIEW, clock: Clock = utc_now
) -> bytes:
    out = io.BytesIO()
    await dump(
        world.tenancy,
        world.store,
        world.files,
        world.iris,
        view,
        tenant or world.tenant,
        out,
        clock=clock,
    )
    return out.getvalue()


async def restored(
    world: SimpleNamespace,
    data: bytes,
    *,
    tenancy: Tenancy | None = None,
    view=VIEW,
    max_bytes: int = MAX_BYTES,
    chains: Sequence[SchemaChain] = TOY_CHAINS,
    store: str = DEFAULT_STORE,
):
    return await restore(
        tenancy or world.tenancy,
        world.iris,
        view,
        io.BytesIO(data),
        RESTORER,
        max_bytes=max_bytes,
        chains=chains,
        store=store,
    )


def unpack(data: bytes) -> list[tuple[str, bytes]]:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        return [(m.name, tar.extractfile(m).read()) for m in tar.getmembers()]  # type: ignore[union-attr]


def pack(*entries: tuple[str, bytes] | tuple[str, bytes, bytes], end: bool = True) -> bytes:
    """A tar.gz of ``(name, payload)`` regular files; a third item names another member type (a link, a directory).

    The ``end`` marker member is added last unless ``end`` is false or the entries already end with it.
    """
    if end and not (entries and entries[-1][0] == END):
        entries = (*entries, (END, b""))
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


# -- schema-migrations TC-34, TC-35: the stamps travel with a dump -------------------------------

STAMPS = ((TOOLKIT_SCHEMA, TOOLKIT_VERSION), (LIBRARY_SCHEMA, "2"))
ALL_STAMPS = "SELECT ?s ?v WHERE {{ GRAPH <{graph}> {{ ?s ?p ?v }} }}"


async def stamps_held(world: SimpleNamespace, tenant: str) -> dict[str, str]:
    database = (await world.tenancy.get(tenant))[0].database_name
    graph = stamps_graph_iri(SETTINGS.base)
    rows = await world.store.query(database, ALL_STAMPS.format(graph=graph))
    return {str(row.s): str(row.v) for row in rows}  # type: ignore[union-attr]


async def test_tc34_a_stamped_tenant_dumps_and_restores_at_the_same_version(chains):
    world = await populated(await make_world(iris_of(SETTINGS), SETTINGS, stamps=STAMPS))
    assert await stamps_held(world, world.tenant) == dict(STAMPS), "create stamped the tenant"
    summary = await restored(world, await dumped(world, view=RUNNING), view=RUNNING, chains=chains)
    assert await stamps_held(world, summary.id) == dict(STAMPS), (
        "the restored tenant holds the stamps"
    )


async def test_tc35_a_tenant_set_aside_can_still_be_dumped(world):
    world.tenancy.set_aside([world.tenant])
    assert await dumped(world), "the dump is made"


# -- schema-migrations PD-24.1: a restore takes exactly the stamps the service runs --------------------

STAMPS_GRAPH = stamps_graph_iri(SETTINGS.base)


def stamp_line(schema: str, version: str, predicate: str = str(v.DATA_SCHEMA_VERSION)) -> str:
    return f'<{schema}> <{predicate}> "{version}" <{STAMPS_GRAPH}> .\n'


def with_stamps(data: bytes, *statements: str) -> bytes:
    """``data`` whose stamps graph holds exactly the N-Quads ``statements``."""
    marker = f"<{STAMPS_GRAPH}> .".encode()

    def change(nq: bytes) -> bytes:
        kept = [line for line in nq.splitlines(keepends=True) if marker not in line]
        return b"".join([*kept, *(s.encode() for s in statements)])

    return edited(data, GRAPHS, change)


@pytest.fixture
async def stamped() -> SimpleNamespace:
    return await populated(await make_world(iris_of(SETTINGS), SETTINGS, stamps=STAMPS))


async def test_a_dump_with_the_stamps_the_service_runs_is_restored_with_exactly_them(
    stamped, chains
):
    data = with_stamps(
        await dumped(stamped, view=RUNNING),
        stamp_line(TOOLKIT_SCHEMA, TOOLKIT_VERSION),
        stamp_line(LIBRARY_SCHEMA, "2"),
    )
    summary = await restored(stamped, data, view=RUNNING, chains=chains)
    assert await stamps_held(stamped, summary.id) == dict(STAMPS), "the restored tenant holds them"


@pytest.mark.parametrize(
    ("statements", "named"),
    [
        ([("TOOLKIT", TOOLKIT_VERSION)], [LIBRARY_SCHEMA, "missing"]),
        ([("TOOLKIT", TOOLKIT_VERSION), ("LIBRARY", "1")], ["'1'", "'2'"]),
        ([("TOOLKIT", TOOLKIT_VERSION), ("LIBRARY", "2"), ("LIBRARY", "3")], ["'3'", "'2'"]),
        (
            [("TOOLKIT", TOOLKIT_VERSION), ("LIBRARY", "2"), ("urn:schema:other", "1")],
            ["urn:schema:other"],
        ),
        (
            [("TOOLKIT", TOOLKIT_VERSION), ("LIBRARY", "2"), ("LIBRARY", "x", "urn:p")],
            ["urn:p", "not a stamp"],
        ),
    ],
    ids=[
        "a stamp missing",
        "another version",
        "a doubled stamp",
        "a foreign schema",
        "not a stamp",
    ],
)
async def test_a_dump_whose_stamps_graph_differs_is_refused_before_anything_is_created(
    stamped, chains, statements, named
):
    ids = {"TOOLKIT": TOOLKIT_SCHEMA, "LIBRARY": LIBRARY_SCHEMA}
    lines = [stamp_line(ids.get(schema, schema), *rest) for schema, *rest in statements]
    data = with_stamps(await dumped(stamped, view=RUNNING), *lines)
    reason = await refused(stamped, data, view=RUNNING, chains=chains)
    for text in named:
        assert text in reason, f"the reason names {text}"


def stamp_graph_with(tenancy_data: bytes, library_stamp: str) -> Dataset:
    """The quads of a dump of the toy tenant, its library stamp replaced by the N-Quads text ``library_stamp``."""
    data = with_stamps(tenancy_data, stamp_line(TOOLKIT_SCHEMA, TOOLKIT_VERSION), library_stamp)
    parsed = Dataset()
    parsed.parse(data=dict(unpack(data))[GRAPHS], format="nquads")
    return parsed


@pytest.mark.parametrize(
    "literal",
    [
        '"1"@en',
        '"1"^^<http://www.w3.org/2001/XMLSchema#string>',
        '"1"^^<http://www.w3.org/2001/XMLSchema#integer>',
    ],
    ids=["a language tag", "xsd:string", "another datatype"],
)
async def test_tenancy_restore_refuses_a_stamp_that_is_not_a_plain_literal(world, literal):
    """PD-25.1: the runner's guard is a plain literal, so a tagged or typed stamp could never match it again."""
    line = f"<{LIBRARY_SCHEMA}> <{v.DATA_SCHEMA_VERSION}> {literal} <{STAMPS_GRAPH}> .\n"
    parsed = stamp_graph_with(await dumped(world), line)
    before = await state_of(world)
    with pytest.raises(InvalidBody, match="not a stamp"):
        await world.tenancy.restore(
            parsed, world.iris.tenant_id_of(world.tenant), iter(()), RESTORER
        )
    assert await state_of(world) == before, "checked before any create"


async def test_a_tenancy_that_configures_no_stamp_refuses_a_dump_that_has_one(world):
    plain = Tenancy(
        world.store, world.files, SETTINGS, mapper=toy_mapper(), root_class=Library,
        access_class=LibraryAccess, iris=world.iris,
    )  # fmt: skip
    parsed = stamp_graph_with(await dumped(world), stamp_line(LIBRARY_SCHEMA, "1"))
    with pytest.raises(InvalidBody, match=LIBRARY_SCHEMA):
        await plain.restore(parsed, world.iris.tenant_id_of(world.tenant), iter(()), RESTORER)


async def test_a_tenant_with_no_stamp_dumps_with_no_version_and_that_dump_is_refused_on_restore():
    """PD-25.7: an unstamped database follows the first version (PD-10), but a dump does not guess it (PD-15)."""
    unstamped = await populated(await make_world(iris_of(SETTINGS), SETTINGS, stamps=()))
    data = await dumped(unstamped)
    assert manifest_of(data).schema_version is None, "no stamp, no version: not the running one"
    reason = await refused(unstamped, data)
    assert "None" in reason, "the reason names the missing version"
    assert "'1'" in reason, "and the versions the chain has"


async def test_a_manifest_version_that_is_not_the_dumps_own_stamp_is_refused_naming_both(
    stamped, chains
):
    def older(payload: bytes) -> bytes:
        found = TenantDump.model_validate_json(payload)
        return found.model_copy(update={"schema_version": "1"}).model_dump_json().encode()

    data = edited(await dumped(stamped, view=RUNNING), MANIFEST, older)
    reason = await refused(stamped, data, view=RUNNING, chains=chains)
    assert "'1'" in reason, "the manifest's version is named"
    assert "'2'" in reason, "the stamp's version is named"


# -- schema-migrations TC-50 to TC-53: a dump carries its version, a restore migrates an older one ------

OLD_DESCRIPTION = URIRef("https://example.org/ns/library#oldDescription")
OLD_CITY = URIRef("https://example.org/ns/library#oldCity")
OWNER = Principal(id=ADA)


def predicate_of(model, text: str) -> URIRef:
    """The predicate under which the mapper stores the literal ``text`` of ``model``."""
    return next(p for _, p, o in toy_mapper().to_triples(model) if o == Literal(text))


BOOK_DESCRIPTION = predicate_of(dune("urn:book"), "A planet.")
CITY = predicate_of(library(), "Ghent")


@pytest.fixture
def chains(tmp_path: Path) -> list[SchemaChain]:
    """The toolkit's chain ``[1]`` and the library's ``[1, 2]``: ``1__2`` moves a book's description and the root's city."""
    steps = [
        rename(OLD_DESCRIPTION, BOOK_DESCRIPTION),
        rename(OLD_CITY, CITY),
    ]
    return [
        (TOOLKIT_SCHEMA, chain_of(tmp_path / "rp", TOOLKIT_SCHEMA, current=TOOLKIT_VERSION)),
        (
            LIBRARY_SCHEMA,
            chain_of(
                tmp_path / "lib",
                LIBRARY_SCHEMA,
                migration(LIBRARY_SCHEMA, "1", "2", *steps),
                current="2",
            ),
        ),
    ]


async def move_predicate(world: SimpleNamespace, subject: str, old: URIRef, new: URIRef) -> None:
    """Store what ``subject`` holds under ``old`` as it was stored before the schema changed to ``new``."""
    await world.store.update(
        world.database,
        f"DELETE {{ GRAPH ?g {{ <{subject}> <{old}> ?o }} }} INSERT {{ GRAPH ?g {{ <{subject}> <{new}> ?o }} }} "
        f"WHERE {{ GRAPH ?g {{ <{subject}> <{old}> ?o }} }}",
    )
    kept = await world.store.query(
        world.database, f"SELECT ?o WHERE {{ GRAPH ?g {{ <{subject}> <{old}> ?o }} }}"
    )
    assert not list(kept), f"{subject} holds nothing under {old}: the fixture is aged"


@pytest.fixture
async def aged() -> SimpleNamespace:
    """A tenant stamped ``1`` whose book and root hold their description and city as version 1 stored them."""
    world = await populated(
        await make_world(
            iris_of(SETTINGS),
            SETTINGS,
            stamps=((TOOLKIT_SCHEMA, TOOLKIT_VERSION), (LIBRARY_SCHEMA, "1")),
        )
    )
    await move_predicate(world, world.book, BOOK_DESCRIPTION, OLD_DESCRIPTION)
    await move_predicate(world, world.tenant, CITY, OLD_CITY)
    world.running = Tenancy(
        world.store, world.files, SETTINGS, mapper=toy_mapper(), root_class=Library,
        access_class=LibraryAccess, iris=world.iris, stamps=STAMPS,
    )  # fmt: skip
    return world


async def token_of(world: SimpleNamespace, tenant: str, iri: str, who: Principal) -> str:
    async with world.tenancy.tenant_session(tenant, who) as opened:
        return (await opened.get_graph(iri))[2]


async def test_tc50_a_dump_carries_the_version_its_data_follows(aged):
    manifest = manifest_of(await dumped(aged, view=RUNNING))
    assert manifest.schema_version == "1", "the tenant's stamp, not the version the service runs"


async def test_tc51_an_older_dump_is_migrated_and_restored_at_the_running_version(aged, chains):
    data = await dumped(aged, view=RUNNING)
    summary = await restored(aged, data, tenancy=aged.running, view=RUNNING, chains=chains)
    assert await stamps_held(aged, summary.id) == dict(STAMPS), "the new tenant is at version 2"
    book = await read_book(aged, summary.id, moved(aged, aged.book, summary.id))
    assert book.description == "A planet.", "the book's description is in its current shape"
    async with aged.tenancy.tenant_session(summary.id, RESTORER) as opened:
        root = await UnitOfWork(opened, toy_mapper()).get(Library, summary.id)
    assert root.city == "Ghent", "the root is vetted and stored in its current shape"
    assert summary.label == "Ghent", "the tenant's label is the root's"


async def test_tc51_the_restored_graphs_get_new_version_tokens(aged, chains):
    data = await dumped(aged, view=RUNNING)
    summary = await restored(aged, data, tenancy=aged.running, view=RUNNING, chains=chains)
    new_book = moved(aged, aged.book, summary.id)
    before = await token_of(aged, aged.tenant, aged.book, OWNER)
    assert await token_of(aged, summary.id, new_book, RESTORER) != before, (
        "a migration with steps renews every token"
    )


async def test_a_dump_at_the_running_version_restores_exactly_as_before(stamped, chains):
    data = await dumped(stamped, view=RUNNING)
    assert manifest_of(data).schema_version == "2", "the tenant is at the running version"
    summary = await restored(stamped, data, view=RUNNING, chains=chains)
    new_book = moved(stamped, stamped.book, summary.id)
    before = await token_of(stamped, stamped.tenant, stamped.book, OWNER)
    assert await token_of(stamped, summary.id, new_book, RESTORER) == before, (
        "no update was applied: the token is the dumped one"
    )


@pytest.mark.parametrize(
    ("version", "named"),
    [(None, "None"), ("9", "'9'")],
    ids=["no version", "a version the chain does not have"],
)
async def test_tc52_a_manifest_with_no_version_or_an_unknown_one_is_refused(
    aged, chains, version, named
):
    def change(payload: bytes) -> bytes:
        found = TenantDump.model_validate_json(payload)
        return found.model_copy(update={"schema_version": version}).model_dump_json().encode()

    data = edited(await dumped(aged, view=RUNNING), MANIFEST, change)
    reason = await refused(aged, data, tenancy=aged.running, view=RUNNING, chains=chains)
    assert named in reason, "the reason names the version the dump carries"
    assert "'1', '2'" in reason, "the reason names the chain's versions"


async def test_tc52_a_manifest_of_another_schema_is_refused(aged, chains):
    other = copy.deepcopy(RUNNING)
    other.schema.id = "https://example.org/other-schema"
    data = await dumped(aged, view=other)
    reason = await refused(aged, data, tenancy=aged.running, view=RUNNING, chains=chains)
    assert "https://example.org/other-schema" in reason, "the reason names the dump's schema"


@pytest.mark.parametrize(
    ("statements", "named"),
    [
        ([], ["missing"]),
        ([(TOOLKIT_SCHEMA, "9"), (LIBRARY_SCHEMA, "1")], [TOOLKIT_SCHEMA, "'9'"]),
    ],
    ids=["no stamps graph", "a toolkit stamp the chain does not know"],
)
async def test_tc52_a_dump_whose_stamps_are_not_versions_of_the_chains_is_refused(
    aged, chains, statements, named
):
    lines = [stamp_line(schema, version) for schema, version in statements]
    data = with_stamps(await dumped(aged, view=RUNNING), *lines)
    reason = await refused(aged, data, tenancy=aged.running, view=RUNNING, chains=chains)
    for text in named:
        assert text in reason, f"the reason names {text}"


async def test_tc53_a_migration_that_fails_on_the_dump_is_refused_and_creates_nothing(
    aged, tmp_path
):
    failing = MigrationStep(
        title="a pattern rdflib cannot run",
        where_pattern=f'?s <{OLD_CITY}> ?o . FILTER(REGEX(?o, "["))',
        delete_pattern=f"?s <{OLD_CITY}> ?o .",
        insert_pattern=f"?s <{CITY}> ?o .",
    )
    bad = [
        (TOOLKIT_SCHEMA, chain_of(tmp_path / "rp", TOOLKIT_SCHEMA, current=TOOLKIT_VERSION)),
        (
            LIBRARY_SCHEMA,
            chain_of(
                tmp_path / "lib",
                LIBRARY_SCHEMA,
                migration(LIBRARY_SCHEMA, "1", "2", failing),
                current="2",
            ),
        ),
    ]
    data = await dumped(aged, view=RUNNING)
    reason = await refused(aged, data, tenancy=aged.running, view=RUNNING, chains=bad)
    assert f"1__2 of {LIBRARY_SCHEMA}" in reason, "the reason names the migration"


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
    assert [c.number for c in restored_book.chapters] == [c.number for c in original.chapters], (
        "the same parts"
    )
    book_new = moved(world, world.book, new)
    async with world.tenancy.tenant_session(new, RESTORER) as opened, world.session() as old:
        for owner, load in ((world.book, world.g), (world.tenant, world.r)):
            owner_new = moved(world, owner, new)
            assert await opened.loaded_graphs(owner_new) == [
                URIRef(moved(world, str(load), new))
            ], "the same load, under the new id"
            copied = await opened.loaded_graph(owner_new, moved(world, str(load), new))
            assert_isomorphic(copied, await old.loaded_graph(owner, str(load)))
    assert book_new == restored_book.id, "the book is where the rewrite put it"
    record, _ = await world.tenancy.get(new)
    assert await world.files.get(record.database_name, "k1") == BLOB_BYTES, "the blob byte for byte"


async def test_tc10_a_restored_tenant_answers_like_the_original(world):
    summary = await restored(world, await dumped(world))
    await assert_answers_like_the_original(world, summary)


async def test_tc13_a_restored_tenant_answers_like_the_original_under_the_flat_policy():
    flat = await populated(await make_world(iris_of(FLAT_SETTINGS), FLAT_SETTINGS))
    summary = await restored(flat, await dumped(flat))
    await assert_answers_like_the_original(flat, summary)


async def test_tc13_the_flat_policy_accepts_the_restored_aggregate_and_loaded_graphs():
    flat = await populated(await make_world(iris_of(FLAT_SETTINGS), FLAT_SETTINGS))
    new = (await restored(flat, await dumped(flat))).id
    assert flat.iris.is_aggregate(new, moved(flat, flat.book, new)), "the book is an aggregate"
    for load in (flat.g, flat.r):
        assert flat.iris.is_loaded_graph(new, moved(flat, str(load), new)), (
            f"{load} is a loaded graph of the new tenant"
        )


async def test_tc11_the_restored_tenant_accepts_a_replace_and_the_original_is_unchanged(world):
    new = (await restored(world, await dumped(world))).id
    iri = moved(world, world.book, new)
    async with world.tenancy.tenant_session(new, RESTORER) as opened:
        work = UnitOfWork(opened, toy_mapper())
        book = await work.get(Book, iri)
        book.label = "Dune Messiah"
        work.add(book)
        await work.commit()
    assert (await read_book(world, new, iri)).label == "Dune Messiah", (
        "the restored tenant holds the replaced label"
    )
    assert (await read_book(world, world.tenant, world.book, Principal(id=ADA))).label == "Dune", (
        "the original tenant is unchanged"
    )


async def test_tc12_only_the_restorer_is_granted_the_creator_role(world):
    _, version = await world.tenancy.get(world.tenant)
    grants = GrantSet(
        grants=[role("librarian", world.tenant, who) for who in (ADA, "urn:x:c", "urn:x:d")]
    )
    await world.tenancy.set_grants(world.tenant, grants, version, Principal(id=ADA))
    new = (await restored(world, await dumped(world))).id
    record, _ = await world.tenancy.get(new)
    assert [(g.assignee, g.role, g.target) for g in record.grants] == [(BOB, "librarian", new)], (
        "the restorer alone"
    )
    assert record.state == TenantState.ACTIVE, "active"
    assert not record.prohibitions, "no prohibition"


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
    assert [n for n, _ in unpack(data)] == [MANIFEST, GRAPHS, "blobs/k2", END], (
        "k1 is not in the dump"
    )
    steps = [(r.__dict__.get("step"), r.__dict__.get("resource")) for r in caplog.records]
    assert steps == [("dump-blob-gone", "k1")], "the missing blob is logged and skipped"


async def test_a_dump_holds_the_manifest_the_graphs_the_blobs_and_the_end_marker_in_that_order(
    world,
):
    data = await dumped(world)
    assert [n for n, _ in unpack(data)] == [MANIFEST, GRAPHS, "blobs/k1", END], "the member order"
    assert dict(unpack(data))[END] == b"", "the end marker is empty"


async def test_a_dump_manifest_names_the_source_the_policy_and_the_schema(world):
    taken = datetime(2026, 11, 16, 9, 30, tzinfo=UTC)
    manifest = manifest_of(await dumped(world, clock=lambda: taken))
    assert manifest.format_version == 1, "format version"
    assert manifest.source_tenant == world.tenant, "source tenant"
    assert manifest.source_tenant_id == world.iris.tenant_id_of(world.tenant), "source tenant id"
    assert manifest.label == "Ghent", "the record's label"
    assert manifest.iri_policy == world.iris.effective_policy, "the effective policy"
    assert manifest.schema_id == VIEW.schema.id, "the schema id"
    assert manifest.created_at == taken, "the manifest carries the clock's reading"


async def test_a_dump_changes_nothing_in_the_tenant(world):
    before = (await world.store.export_quads(world.database), await state_of(world))
    blobs = await world.files.list_blobs(world.database)
    await dumped(world)
    assert await world.store.export_quads(world.database) == before[0], "the graphs"
    assert await state_of(world) == before[1], "the databases, buckets and tenants"
    assert await world.files.list_blobs(world.database) == blobs, "the blobs"


async def test_a_dump_and_a_restore_each_log_one_line_without_content(world, caplog):
    with caplog.at_level(logging.INFO, logger="rdf_persistence.services.tenant_dump"):
        data = await dumped(world)
        new = (await restored(world, data)).id
    lines = [r for r in caplog.records if r.__dict__.get("step") in ("dump", "restore")]
    assert [(r.__dict__["step"], r.__dict__["tenant"]) for r in lines] == [
        ("dump", world.tenant),
        ("restore", new),
    ], "one dump line for the source, one restore line for the new tenant"
    assert lines[0].__dict__["blobs"] == 1, "the dump line counts the blobs"
    assert lines[1].__dict__["source"] == world.tenant, "the restore line names the source"
    text = " ".join(r.getMessage() for r in lines)
    assert "Dune" not in text, "no graph or blob content in the log"
    assert "k1" not in text, "no graph or blob content in the log"


# -- TC-17 to TC-21: a restore refuses a dump it cannot trust ----------------------------------------


async def refused(world: SimpleNamespace, data: bytes, **keywords) -> str:
    """The reason of the ``InvalidBody`` a restore of ``data`` raises; nothing has been created."""
    before = await state_of(world)
    with pytest.raises(InvalidBody) as caught:
        await restored(world, data, **keywords)
    assert await state_of(world) == before, "no database, bucket or record created"
    return str(caught.value)


def at_version(version: str):
    """The toy schema at another ``version``; a dump and a restore read the schema id from it, not the version."""
    other = copy.deepcopy(VIEW)
    other.schema.version = version
    return other


async def test_tc17_another_schema_version_is_refused_naming_both(world):
    def other_version(payload: bytes) -> bytes:
        found = TenantDump.model_validate_json(payload)
        return found.model_copy(update={"schema_version": "1.0.0"}).model_dump_json().encode()

    reason = await refused(world, edited(await dumped(world), MANIFEST, other_version))
    assert "1.0.0" in reason, "the dump's version"
    assert "'1'" in reason, "the version the service has"


async def test_tc17_another_schema_id_is_refused(world):
    other = copy.deepcopy(VIEW)
    other.schema.id = "https://example.org/other-schema"
    assert "https://example.org/other-schema" in await refused(
        world, await dumped(world), view=other
    ), "the reason names the service's schema id"


async def test_a_format_version_other_than_one_is_refused_naming_it(world):
    def bump(payload: bytes) -> bytes:
        return (
            TenantDump.model_validate_json(payload)
            .model_copy(update={"format_version": 2})
            .model_dump_json()
            .encode()
        )

    assert "2" in await refused(world, edited(await dumped(world), MANIFEST, bump)), (
        "the refusal names the format version"
    )


@pytest.mark.parametrize(
    "text", [b'{"format_version": 1}', b"not json"], ids=["fields-missing", "not-json"]
)
async def test_a_manifest_that_is_not_a_tenant_dump_is_refused(world, text):
    reason = await refused(world, edited(await dumped(world), MANIFEST, lambda _: text))
    assert MANIFEST in reason, "the reason names the manifest"


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
    ), "the reason names the differing field"


async def test_tc50_a_dump_whose_manifest_lacks_the_application_template_restores_on_the_default_policy(
    world,
):
    def as_an_older_service_wrote_it(payload: bytes) -> bytes:
        manifest = TenantDump.model_validate_json(payload)
        return manifest.model_dump_json(exclude={"iri_policy": {"application_template"}}).encode()

    data = edited(await dumped(world), MANIFEST, as_an_older_service_wrote_it)
    assert "application_template" not in dict(unpack(data))[MANIFEST].decode(), "the old shape"
    summary = await restored(world, data)
    assert summary.id != world.tenant, "restored as a new tenant"


async def test_a_dump_whose_manifest_lacks_the_provenance_template_restores_on_the_default_policy(
    world,
):
    def as_an_older_service_wrote_it(payload: bytes) -> bytes:
        manifest = TenantDump.model_validate_json(payload)
        return manifest.model_dump_json(exclude={"iri_policy": {"provenance_template"}}).encode()

    data = edited(await dumped(world), MANIFEST, as_an_older_service_wrote_it)
    assert "provenance_template" not in dict(unpack(data))[MANIFEST].decode(), "the old shape"
    summary = await restored(world, data)
    assert summary.id != world.tenant, "restored as a new tenant"


async def test_tc50_a_manifest_that_names_another_application_template_is_still_refused(world):
    def renamed(payload: bytes) -> bytes:
        manifest = TenantDump.model_validate_json(payload)
        manifest.iri_policy.application_template = "{base}application"
        return manifest.model_dump_json().encode()

    reason = await refused(world, edited(await dumped(world), MANIFEST, renamed))
    assert "application_template" in reason, "the reason names the differing field"


async def test_tc49_a_triple_in_a_tenant_graph_that_names_an_application_aggregate_survives_a_restore(
    world,
):
    template = str(world.iris.mint_aggregate(str(world.iris.application), "template", "templates"))
    book = str(world.iris.mint_aggregate(world.tenant, BOOK_TYPE, "books"))
    cites = (URIRef(book), SKOS.related, URIRef(template))
    async with world.session() as opened:
        await opened.add_graph(book, [*toy_mapper().to_triples(dune(book)), cites])
    new = (await restored(world, await dumped(world))).id
    async with world.tenancy.tenant_session(new, RESTORER) as opened:
        graph, _, _ = await opened.get_graph(moved(world, book, new))
    assert list(graph.objects(URIRef(moved(world, book, new)), SKOS.related)) == [
        URIRef(template)
    ], "the restored book names the same application aggregate"


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
    assert "tenant_template" in await refused(world, await dumped(world)), (
        "the refusal names the tenant template"
    )


async def test_tc19_a_quad_in_a_foreign_graph_is_refused_naming_it(world):
    foreign = b"<http://elsewhere.example/s> <http://elsewhere.example/p> <http://elsewhere.example/o> <http://elsewhere.example/g> .\n"
    reason = await refused(world, edited(await dumped(world), GRAPHS, lambda nq: nq + foreign))
    assert "http://elsewhere.example/g" in reason, "the reason names the foreign graph"


async def test_tc19_a_quad_in_the_default_graph_is_refused(world):
    default = b"<http://elsewhere.example/s> <http://elsewhere.example/p> <http://elsewhere.example/o> .\n"
    assert "default graph" in await refused(
        world, edited(await dumped(world), GRAPHS, lambda nq: nq + default)
    ), "the reason names the default graph"


async def test_a_dump_without_a_root_is_refused(world):
    def without_root(nq: bytes) -> bytes:
        return b"".join(
            line
            for line in nq.splitlines(keepends=True)
            if f"<{world.tenant}> ".encode() not in line
        )

    assert "root" in await refused(world, edited(await dumped(world), GRAPHS, without_root)), (
        "the reason names the root"
    )


async def test_a_root_that_does_not_decode_is_refused(world):
    """The root is there but cannot be read as a tenant root: its required label is gone."""

    def unlabelled(nq: bytes) -> bytes:
        label = f"<{world.tenant}> <{SKOS.prefLabel}> ".encode()
        return b"".join(line for line in nq.splitlines(keepends=True) if not line.startswith(label))

    assert "root" in await refused(world, edited(await dumped(world), GRAPHS, unlabelled)), (
        "the reason names the root"
    )


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
        stamps=BASE_STAMPS,
        root_validators=[refuse],
    )
    assert "no more libraries" in await refused(world, await dumped(world), tenancy=strict), (
        "the refusal carries the validator's message"
    )
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
    assert await state_of(world) == before, "no database, bucket or record is left"


async def test_tc23_a_cleanup_that_fails_too_is_logged_and_the_sweep_finishes_it(world, caplog):
    data = await dumped(world)
    world.store.on("import_quads", StoreUnavailable("the import failed"))
    world.store.on("drop_dataset", StoreUnavailable("the drop failed"))
    with (
        caplog.at_level(logging.WARNING, logger="rdf_persistence.services.tenancy"),
        pytest.raises(StoreUnavailable, match="the import failed"),
    ):
        await restored(world, data)
    cleanup = [r for r in caplog.records if r.__dict__.get("step") == "restore-cleanup"]
    assert [r.__dict__["resource"] for r in cleanup] == [cleanup[0].__dict__["resource"]], (
        "one failed drop was logged, naming the database"
    )
    leftover = cleanup[0].__dict__["resource"]
    datasets = set(await world.store.list_datasets())
    assert leftover in datasets, "the logged database is still there"
    assert leftover != world.database, "and it is the new one, not the source"
    assert len(datasets) == 3, "system, source and the leftover database"
    assert await world.files.list_buckets("") == [world.database], "the bucket was still dropped"
    await sweep(world.tenancy, world.store, world.files, SETTINGS)
    assert set(await world.store.list_datasets()) == datasets - {leftover}, (
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
    assert await state_of(world) == before, "and then dropped with the rest"


async def test_tc27_a_blob_member_that_is_a_directory_fails_and_leaves_nothing(world):
    members = unpack(await dumped(world))[:2]
    before = await state_of(world)
    with pytest.raises(InvalidBody):
        await restored(
            world, pack(*members, ("blobs/a", b"first"), ("blobs/dir", b"", tarfile.DIRTYPE))
        )
    assert await state_of(world) == before, "nothing is left"


# -- TC-24, TC-25 -----------------------------------------------------------------------------------


async def test_tc24_a_tenant_with_its_root_only_dumps_and_restores():
    world = await make_world(iris_of(SETTINGS), SETTINGS)
    data = await dumped(world)
    assert [n for n, _ in unpack(data)] == [MANIFEST, GRAPHS, END], "no blob"
    new = (await restored(world, data)).id
    record, _ = await world.tenancy.get(new)
    assert record.label == "Ghent", "the label"
    assert await world.files.list_blobs(record.database_name) == [], "an empty bucket"


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
    assert summary.label == "New", "the summary takes the root's label"
    assert record.label == "New", "the access record takes the root's label"
    assert root.label == "New", "the root keeps its label"


# -- PD-13: the decompression budget, the end marker, the record write ------------------------------------


def charge_of(payload: bytes) -> int:
    """What a restore charges for one member (PD-14): its header block plus its size padded to a block."""
    return tarfile.BLOCKSIZE + -(-len(payload) // tarfile.BLOCKSIZE) * tarfile.BLOCKSIZE


def charged(data: bytes) -> int:
    """What a restore charges for the whole of ``data``."""
    return sum(charge_of(payload) for _, payload in unpack(data))


async def test_a_budget_that_holds_every_member_and_its_block_restores_and_one_byte_less_refuses(
    world,
):
    data = await dumped(world)
    assert (await restored(world, data, max_bytes=charged(data))).id != world.tenant, "fits"
    assert "bytes" in await refused(world, data, max_bytes=charged(data) - 1), "one byte short"


async def test_many_small_blobs_are_charged_with_their_padding(world):
    members = unpack(await dumped(world))[:2]
    data = pack(*members, *((f"blobs/b{i}", b"x") for i in range(50)))
    assert (await restored(world, data, max_bytes=charged(data))).id != world.tenant, "fits"
    assert "bytes" in await refused(world, data, max_bytes=charged(data) - 1), "one byte short"


async def test_a_budget_the_graphs_overflow_is_refused_before_anything_is_created(world):
    data = await dumped(world)
    head = charge_of(unpack(data)[0][1])  # the manifest alone
    await refused(world, data, max_bytes=head)  # refused() asserts that nothing was created


async def test_a_blob_that_overflows_the_budget_is_refused_and_leaves_nothing(world):
    members = unpack(await dumped(world))[:2]
    archive = pack(*members, ("blobs/big", b"\0" * 200_000))  # about 200 bytes once gzipped
    before = await state_of(world)
    budget = charged(pack(*members, ("blobs/small", b"x")))
    with pytest.raises(InvalidBody, match="bytes"):
        await restored(world, archive, max_bytes=budget)
    assert not [k for k in world.files.sent("put") if k.endswith("/big")], "the blob was never read"
    assert await state_of(world) == before, "database and bucket dropped, no record"


async def test_a_manifest_larger_than_its_cap_is_refused_whatever_the_budget(world):
    def padded(payload: bytes) -> bytes:
        manifest = TenantDump.model_validate_json(payload)
        return manifest.model_copy(update={"label": "x" * 70_000}).model_dump_json().encode()

    reason = await refused(world, edited(await dumped(world), MANIFEST, padded))
    assert MANIFEST in reason, "the reason names the manifest and its cap"
    assert "64" in reason, "the reason names the manifest and its cap"


async def test_the_gzip_stream_after_the_end_marker_is_bounded_by_the_budget(world):
    data = await dumped(world)
    members = unpack(data)
    tail = gzip.compress(  # the tar of the dump, then a long run of zero bytes under the same gzip
        gzip.decompress(pack(*members)) + b"\0" * 5_000_000
    )
    await refused(world, tail, max_bytes=charged(data) + 100_000)


def with_header_on_the_manifest(data: bytes, header: dict[str, str], fmt: int) -> bytes:
    """The archive ``data`` with ``header`` as the extended header of its first member (the manifest)."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", format=fmt) as tar:
        for index, (name, payload) in enumerate(unpack(data)):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            if index == 0:
                info.pax_headers = header
            tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


async def test_a_pax_header_larger_than_the_budget_is_refused_and_creates_nothing(world):
    data = await dumped(
        world
    )  # about 2 MB of header, a few KB once gzipped; the budget is far smaller
    hostile = with_header_on_the_manifest(data, {"comment": "x" * 2_000_000}, tarfile.PAX_FORMAT)
    reason = await refused(world, hostile, max_bytes=charged(data) + 100_000)
    assert "bytes" in reason, "the reason says it is the size"


async def test_a_header_inside_the_budget_does_not_stop_a_restore(world):
    data = await dumped(world)
    small = with_header_on_the_manifest(data, {"comment": "x" * 1_000}, tarfile.PAX_FORMAT)
    assert (await restored(world, small, max_bytes=charged(data) + 10_000)).id != world.tenant, (
        "the restore within the budget makes a new tenant"
    )


async def test_a_dump_of_a_tenant_with_no_blob_still_ends_with_an_empty_regular_end_member():
    world = await make_world(iris_of(SETTINGS), SETTINGS)
    out = io.BytesIO()
    await dump(world.tenancy, world.store, world.files, world.iris, VIEW, world.tenant, out)
    with tarfile.open(fileobj=io.BytesIO(out.getvalue()), mode="r:gz") as tar:
        last = tar.getmembers()[-1]
    assert (last.name, last.isfile(), last.size) == (END, True, 0), "an empty regular file end"


async def test_a_gnu_long_name_header_over_the_budget_is_refused_and_creates_nothing(world):
    data = await dumped(world)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        for name, payload in unpack(data):
            info = tarfile.TarInfo("blobs/" + "n" * 2_000_000 if name == "blobs/k1" else name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    reason = await refused(world, buffer.getvalue(), max_bytes=charged(data) + 100_000)
    assert "bytes" in reason, "the reason says it is the size"


@pytest.mark.parametrize(
    "damage",
    [
        lambda head: pack(*head, ("blobs/a", b"x"), end=False),
        lambda head: pack(*head, end=False),
        lambda head: pack(*head, (END, b"not empty")),
        lambda head: pack(*head, (END, b"", tarfile.SYMTYPE)),
        lambda head: pack(*head, (END, b""), ("blobs/after", b"x"), end=False),
        lambda head: pack(*head, (END, b""), (END, b""), end=False),
    ],
    ids=[
        "blobs-without-end",
        "no-blobs-without-end",
        "end-not-empty",
        "end-a-link",
        "blob-after-end",
        "two-ends",
    ],
)
async def test_an_archive_whose_blobs_are_not_followed_by_exactly_one_empty_end_is_refused(
    world, damage
):
    head = unpack(await dumped(world))[:2]
    before = await state_of(world)
    with pytest.raises(InvalidBody):
        await restored(world, damage(head))
    assert await state_of(world) == before, "database and bucket dropped, no record"


async def test_a_failed_record_write_leaves_orphans_for_the_sweep_and_no_record(world):
    data = await dumped(world)
    before = await state_of(world)
    world.store.on("update", StoreUnavailable("the system database is down"), times=50)
    with pytest.raises(StoreUnavailable, match="system database"):
        await restored(world, data)
    databases, buckets, tenants = await state_of(world)
    assert tenants == before[2], "no access record"
    assert len(databases) == len(before[0]) + 1, "the new database is left to the sweep"
    assert len(buckets) == len(before[1]) + 1, "and so is the new bucket"
    await sweep(world.tenancy, world.store, world.files, SETTINGS)
    assert await state_of(world) == before, "the start-up sweep drops both"


async def test_tenancy_restore_vets_the_graphs_itself_and_creates_nothing_for_a_foreign_one(world):
    foreign = Dataset()
    foreign.graph(URIRef("http://elsewhere.example/g")).add(
        (URIRef("urn:x:s"), URIRef("urn:x:p"), URIRef("urn:x:o"))
    )
    before = await state_of(world)
    with pytest.raises(InvalidBody, match="http://elsewhere.example/g"):
        await world.tenancy.restore(
            foreign, world.iris.tenant_id_of(world.tenant), iter(()), RESTORER
        )
    assert await state_of(world) == before, "checked before any create"


async def test_a_dump_that_holds_an_application_class_is_refused_and_creates_nothing(world):
    """D-6 b: a ``Template`` put into the tenant's database directly must not be restored there."""
    template_iri = str(world.iris.mint_aggregate(world.tenant, "template", "templates"))
    async with world.session() as opened:  # no refused types: the way a stray graph gets there
        await opened.add_graph(template_iri, toy_mapper().to_triples(template(template_iri)))
    data = await dumped(world)
    before = await state_of(world)
    with pytest.raises(InvalidBody, match="the dump holds an object of the application class"):
        await restored(world, data)
    assert await state_of(world) == before, "no database, bucket or access record was created"


async def test_a_manifest_that_names_the_application_as_its_source_tenant_is_refused(world):
    """The application is no tenant, so a dump cannot claim to come from it."""
    application = str(world.iris.application)

    def from_the_application(payload: bytes) -> bytes:
        manifest = TenantDump.model_validate_json(payload)
        manifest.source_tenant, manifest.source_tenant_id = application, "app"
        return manifest.model_dump_json().encode()

    reason = await refused(world, edited(await dumped(world), MANIFEST, from_the_application))
    assert application in reason, "the reason names the application IRI"


# -- tenant-stores PD-7: a restore on a store beside ``default`` ---------------------------------------

CLIENT_A = "client-a"


class VanishingStore(FakeStore):
    """A store whose database disappears once the quads are imported: a sweep elsewhere dropped it."""

    async def import_quads(self, dataset: str, data: bytes) -> None:
        await super().import_quads(dataset, data)
        await self.drop_dataset(dataset)


def beside(world: SimpleNamespace, other: FakeStore, iris: Iris | None = None) -> Tenancy:
    """A tenancy over the world's default store and files, with ``other`` wired as ``client-a``."""
    return Tenancy(
        world.store,
        world.files,
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        iris=iris or world.iris,
        stamps=BASE_STAMPS,
        stores={CLIENT_A: other},
    )


async def test_tc19_a_dump_restored_on_another_store_makes_its_tenant_there(world):
    other = FakeStore()
    tenancy = beside(world, other)
    on_default = sorted(await world.store.list_datasets())

    summary = await restored(world, await dumped(world), tenancy=tenancy, store=CLIENT_A)

    record, _ = await tenancy.get(summary.id)
    assert summary.id != world.tenant, "a new IRI"
    assert record.store_name == CLIENT_A, "the restored tenant is made on the other store"
    assert await other.list_datasets() == [record.database_name], "the database is on client-a"
    assert sorted(await world.store.list_datasets()) == on_default, "default gained none"


async def test_tc20_a_restore_that_fails_on_another_store_drops_the_database_there(world):
    other = FakeStore()
    other.on("import_quads", StoreUnavailable("down"))
    tenancy = beside(world, other)
    data = await dumped(world)
    before = await state_of(world)

    with pytest.raises(StoreUnavailable, match="down"):
        await restored(world, data, tenancy=tenancy, store=CLIENT_A)

    assert await other.list_datasets() == [], "dropped from client-a"
    assert await state_of(world) == before, "nothing on default, no bucket, no record"


async def test_tc39_the_vanished_check_reads_the_store_of_the_restore(world):
    other = VanishingStore()
    tenancy = beside(world, other)
    data = await dumped(world)
    before = (len(world.store.sent("list_datasets")), len(other.sent("list_datasets")))

    with pytest.raises(PersistenceError, match="vanished"):
        await restored(world, data, tenancy=tenancy, store=CLIENT_A)

    after = (len(world.store.sent("list_datasets")), len(other.sent("list_datasets")))
    assert after == (before[0] + 1, before[1] + 2), (
        "default: the id draw; client-a: the draw and the check"
    )


async def test_tc19_the_restored_book_reads_back_through_a_session_on_the_new_tenant(world):
    tenancy = beside(world, FakeStore())
    summary = await restored(world, await dumped(world), tenancy=tenancy, store=CLIENT_A)

    async with tenancy.tenant_session(summary.id, RESTORER) as opened:
        book = await UnitOfWork(opened, toy_mapper()).get(
            Book, moved(world, world.book, summary.id)
        )

    assert book.label == "Dune", "the book is on the new tenant's store"


async def test_a_restore_on_a_store_that_is_not_wired_is_refused_naming_it_and_makes_nothing(world):
    data = await dumped(world)
    before = await state_of(world)

    with pytest.raises(StoreNotWired, match="client-b"):
        await restored(world, data, store="client-b")

    assert await state_of(world) == before, "no database, bucket or record, on any store"


async def test_pd14_a_restore_that_conflicts_on_the_bucket_keeps_the_other_tenants_bucket_and_files(
    world,
):
    other = FakeStore()
    drawn = str(UUID(int=7))
    iris = Iris(SETTINGS, *iri_types(VIEW), id_source=lambda spec: drawn)
    tenancy = beside(
        world, other, iris
    )  # the tenant it draws is known: the winner's bucket is named
    name = iris.resource_name(str(iris.mint_tenant()))
    data = await dumped(world)
    await world.files.create_bucket(name)  # the winner's, made between this draw and its create
    await world.files.put(name, "scan.pdf", b"%PDF")

    with pytest.raises(Conflict):
        await restored(world, data, tenancy=tenancy, store=CLIENT_A)

    assert await other.list_datasets() == [], "the database it made is dropped from client-a"
    assert await world.files.get(name, "scan.pdf") == b"%PDF", "the winner's bucket and file stay"
    assert world.files.sent("delete_bucket") == [], "no bucket drop was sent"

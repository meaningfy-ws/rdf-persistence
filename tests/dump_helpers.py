"""The helpers of the dump and restore tests: a populated, stamped tenant and the dump archive's pieces.

The dump, restore, pending-mark, session-activity and event tests use them, from more than one
theme and tier, so they sit at the root of ``tests/``.
"""

import copy
import io
import tarfile
from collections.abc import Sequence
from types import SimpleNamespace

import pytest
from rdflib import Literal, URIRef

from rdf_persistence.core.domain.exceptions import InvalidBody
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.files.domain.generated.rp_files import RdfFormat
from rdf_persistence.iris.domain.layout import stamps_graph_iri
from rdf_persistence.iris.services.generated.rp_iris_services import ServiceSettings
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.migrations.services.migrations import SchemaChain
from rdf_persistence.migrations.services.migrations import chain_of as chain_of_schema
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.persistence.services.mapper import UnitOfWork
from rdf_persistence.persistence.services.session import Clock, utc_now
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import iri_types
from rdf_persistence.schema.services.vocabulary import TOOLKIT_MIGRATIONS, metamodel
from rdf_persistence.tenancy.services.generated.rp_tenancy_services import TenantDump
from rdf_persistence.tenancy.services.tenancy import DEFAULT_STORE, Tenancy
from rdf_persistence.tenancy.services.tenant_dump import dump, restore
from tests.fixtures.library.domain.generated.books import Book
from tests.tenancy_world import BOOK_TYPE, TURTLE
from tests.tenancy_world import make_world as sweep_world
from tests.toy import ADA, BOB, SETTINGS, TOY_MIGRATIONS, TOY_SCHEMA, dune, library, toy_mapper

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
STAMPS = ((TOOLKIT_SCHEMA, TOOLKIT_VERSION), (LIBRARY_SCHEMA, "2"))
ALL_STAMPS = "SELECT ?s ?v WHERE {{ GRAPH <{graph}> {{ ?s ?p ?v }} }}"
STAMPS_GRAPH = stamps_graph_iri(SETTINGS.base)
OLD_DESCRIPTION = URIRef("https://example.org/ns/library#oldDescription")
OLD_CITY = URIRef("https://example.org/ns/library#oldCity")
OWNER = Principal(id=ADA)


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
    limits: LimitSettings | None = None,
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
        limits=limits,
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


async def stamps_held(world: SimpleNamespace, tenant: str) -> dict[str, str]:
    database = (await world.tenancy.get(tenant))[0].database_name
    graph = stamps_graph_iri(SETTINGS.base)
    rows = await world.store.query(database, ALL_STAMPS.format(graph=graph))
    return {str(row.s): str(row.v) for row in rows}  # type: ignore[union-attr]


def stamp_line(schema: str, version: str, predicate: str = str(v.DATA_SCHEMA_VERSION)) -> str:
    return f'<{schema}> <{predicate}> "{version}" <{STAMPS_GRAPH}> .\n'


def with_stamps(data: bytes, *statements: str) -> bytes:
    """``data`` whose stamps graph holds exactly the N-Quads ``statements``."""
    marker = f"<{STAMPS_GRAPH}> .".encode()

    def change(nq: bytes) -> bytes:
        kept = [line for line in nq.splitlines(keepends=True) if marker not in line]
        return b"".join([*kept, *(s.encode() for s in statements)])

    return edited(data, GRAPHS, change)


def predicate_of(model, text: str) -> URIRef:
    """The predicate under which the mapper stores the literal ``text`` of ``model``."""
    return next(p for _, p, o in toy_mapper().to_triples(model) if o == Literal(text))


BOOK_DESCRIPTION = predicate_of(dune("urn:book"), "A planet.")
CITY = predicate_of(library(), "Ghent")


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


async def token_of(world: SimpleNamespace, tenant: str, iri: str, who: Principal) -> str:
    async with world.tenancy.tenant_session(tenant, who) as opened:
        return (await opened.get_graph(iri))[2]


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

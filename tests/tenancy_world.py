"""A tenant over the fakes, with helpers that act at a chosen age: the world of the sweep tests.

The tenant sweep, the dump, the migration and the session-activity tests all build on it, from
more than one theme and tier, so it sits at the root of ``tests/``.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

from rdflib import Literal, URIRef

from rdf_persistence.access.domain.generated.rp_tenancy import TenantSweepReport
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.core.domain.sparql import fill, term
from rdf_persistence.files.domain.generated.rp_files import RdfFormat
from rdf_persistence.iris.services.generated.rp_iris_services import ServiceSettings
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.persistence.services.session import open_session
from rdf_persistence.tenancy.services.tenancy import Tenancy
from rdf_persistence.tenancy.services.tenant_sweep import sweep_tenant
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.domain.generated.library import Library
from tests.fixtures.library.domain.generated.library_access import LibraryAccess
from tests.toy import ADA, library_slots, toy_mapper, toy_rules

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
CREATOR = Principal(id=ADA)
FILE_KEY = URIRef("https://meaningfy.ws/ns/rdf-persistence#fileKey")
LOADED_AT = URIRef("https://meaningfy.ws/ns/rdf-persistence#loadedAt")
OWNED_BY = URIRef("https://meaningfy.ws/ns/rdf-persistence#ownedBy")
TURTLE = b'<https://example.org/b> <http://purl.org/dc/terms/title> "Dune" .'
HOUR = timedelta(hours=1)
ALL_QUADS = "SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } }"
FLAT = "{base}{tenant_id}/{type}/{id}"
BOOK_TYPE = "book"


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


async def make_world(
    iris: Iris, settings: ServiceSettings, stamps: Sequence[tuple[str, str]] = ()
) -> SimpleNamespace:
    """A tenant over the fakes, with helpers that act at a chosen age; ``stamps`` as ``Tenancy`` takes them."""
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
        rules=toy_rules(),
        iris=iris,
        stamps=stamps,
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

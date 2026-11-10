"""The live-tenant sweep and the removal with blobs against real Fuseki and Garage (live-tenant-sweep 5.2).

The graphs and blobs are real; time is the sweep's injected clock, set ahead of the real one, so
nothing waits. A blob is stamped by the object store's clock, so the young-blob case stays in the
unit tests; here an old marker and a young marker are told apart by their own times.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from rdflib import URIRef

from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.iris import Iris
from rdf_persistence.services.file_removal import remove_with_files
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import open_session
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.services.tenant_sweep import sweep_tenant
from tests.fixtures.library.generated.scans import Scan
from tests.toy import SETTINGS, library_slots, toy_mapper
from tests.toy_service import SCAN_BODY
from tests.unit.services.test_tenant_sweep import CREATOR, TURTLE

HOUR = timedelta(hours=1)


class Shelf:
    """A tenant on the real stores, with helpers that write at a chosen time."""

    def __init__(self, tenancy: Tenancy, store, files, tenant: str, database: str) -> None:
        self.tenancy, self.store, self.files = tenancy, store, files
        self.tenant, self.database = tenant, database
        self.iris = Iris(SETTINGS.model_copy(update={"prefix": SETTINGS.prefix}))

    def session(self, at: datetime):
        return open_session(
            self.store,
            database=self.database,
            tenant_iri=self.tenant,
            principal=CREATOR,
            clock=lambda: at,
            iris=self.iris,
        )

    def new(self, folder: str) -> str:
        return f"{self.tenant}/{folder}/{uuid4()}"

    async def load(self, aggregate: str, at: datetime) -> URIRef:
        async with self.session(at) as opened:
            return await opened.load_graph(aggregate, TURTLE, rdf_format=RdfFormat.TURTLE)

    async def commit_book(self, aggregate: str, loaded: list[URIRef]) -> None:
        async with self.session(datetime.now(UTC)) as opened:
            await opened.add_graph(aggregate, [], loaded_graphs=loaded)

    async def commit_scan(self, key: str) -> tuple[str, str]:
        """Store a scan naming ``key`` through the mapper; its IRI and version."""
        iri = self.new("scans")
        async with self.tenancy.tenant_session(self.tenant, CREATOR) as opened:
            work = UnitOfWork(opened, toy_mapper())
            work.add(Scan.model_validate({**SCAN_BODY, "id": iri, "file_key": key}))
            await work.commit()
            return iri, (await opened.get_graph(iri))[2]

    async def blob(self, key: str) -> None:
        await self.files.put(self.database, key, b"bytes")

    async def blobs(self) -> list[str]:
        return [b.file_key for b in await self.files.list_blobs(self.database)]

    async def holds(self, graph: URIRef) -> bool:
        asked = await self.store.query(self.database, f"ASK {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}")
        return bool(asked.askAnswer)


@pytest.fixture
async def shelf(tenancy, store, files) -> Shelf:
    tenant = (await tenancy.create("Ghent", library_slots(), CREATOR)).id
    access, _ = await tenancy.get(tenant)
    return Shelf(tenancy, store, files, tenant, access.database_name)


async def test_the_sweep_gives_the_worked_examples_outcome_on_real_stores(shelf):
    now = datetime.now(UTC)
    book = shelf.new("books")
    g1, g2 = await shelf.load(book, now), await shelf.load(book, now)
    g3 = await shelf.load(book, now + 90 * timedelta(minutes=1))  # young at the sweep's clock
    await shelf.commit_book(book, [g1])
    await shelf.commit_scan("k1")  # its file_key is what keeps the blob (a plain literal read back)
    await shelf.blob("k1")
    await shelf.blob("k2")
    clock = lambda: now + 2 * HOUR  # noqa: E731  the cutoff is then now + 1 h: the blobs are old
    sweep = lambda **kw: sweep_tenant(  # noqa: E731
        shelf.tenancy, shelf.store, shelf.files, shelf.iris, shelf.tenant, clock=clock, **kw
    )

    dry = await sweep()
    assert (dry.loaded_graphs, dry.blobs) == ([str(g2)], ["k2"]), "found"
    assert not (dry.removed_loaded_graphs or dry.removed_blobs)
    assert await shelf.blobs() == ["k1", "k2"], "a dry run changes nothing"

    graphs_only = await sweep(remove=True)
    assert graphs_only.removed_loaded_graphs and not graphs_only.removed_blobs
    assert not await shelf.holds(g2), "the orphan graph goes with remove"
    assert await shelf.blobs() == ["k1", "k2"], "but the blobs stay without remove_blobs"

    both = await sweep(remove=True, remove_blobs=True)
    assert both.removed_blobs and both.blobs == ["k2"]
    assert await shelf.blobs() == ["k1"], "the orphan blob goes; the named blob stays"
    assert await shelf.holds(g1) and await shelf.holds(g3), "committed and young graphs stay"


async def test_removing_with_files_deletes_only_the_keys_no_other_aggregate_names(shelf):
    own, own_version = await shelf.commit_scan("own")
    (shared, shared_version), _ = (
        await shelf.commit_scan("shared"),
        await shelf.commit_scan("shared"),
    )
    for key in ("own", "shared"):
        await shelf.blob(key)
    remove = lambda iri, version: remove_with_files(  # noqa: E731
        shelf.tenancy, shelf.files, shelf.tenant, CREATOR, iri, version
    )

    await remove(own, own_version)
    assert await shelf.blobs() == ["shared"], "the blob only the removed scan named is gone"
    await remove(shared, shared_version)
    assert await shelf.blobs() == ["shared"], "a key another scan still names stays"

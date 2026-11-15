"""The kit wires the stores a service serves beside ``default`` (tenant-stores PD-3, PD-9, PD-10).

``D`` is the default ``FakeStore``, ``A`` the store wired as ``client-a``. Every test names its TC id.
"""

import io
from datetime import timedelta
from types import SimpleNamespace

import pytest

from rdf_persistence.domain.exceptions import DatabaseGone, NotFound, StoreNotWired
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.services.store import ToolkitStore
from rdf_persistence.services.tenancy import DEFAULT_STORE
from rdf_persistence.testkit import FakeStore
from tests.toy import library_slots
from tests.toy_service import DUNE_BODY, ToyService, principal_of

CLIENT_A = "client-a"
ADA = Principal(id=principal_of("ada"))
TURTLE = b'<https://example.org/b> <http://purl.org/dc/terms/title> "Dune" .'


@pytest.fixture
async def world():
    """A service with ``client-a`` wired, a tenant on ``A`` and a book in it, and a client."""
    d, a = FakeStore(), FakeStore()
    service = ToyService(store=d, stores={CLIENT_A: a})
    async with service.app.router.lifespan_context(service.app):
        summary = await service.kit.tenancy.create("Ghent", library_slots(), ADA, store=CLIENT_A)
        async with service.client() as http:
            headers = service.bearer("ada")
            path = f"/libraries/{summary.id.rsplit('/', 1)[1]}"
            book = await http.post(f"{path}/books", json=DUNE_BODY, headers=headers)
            assert book.status_code == 201, book.text
            yield SimpleNamespace(
                d=d,
                a=a,
                service=service,
                http=http,
                headers=headers,
                tenant=summary.id,
                path=path,
                book=book.headers["location"],
            )


async def test_tc29_a_book_of_a_tenant_on_a_wired_store_is_read_from_that_store(world) -> None:
    response = await world.http.get(world.book, headers=world.headers)
    record, _ = await world.service.kit.tenancy.get(world.tenant)
    assert response.status_code == 200, "the book is served"
    assert record.database_name in await world.a.list_datasets(), "the database is on A"
    assert record.database_name not in await world.d.list_datasets(), "and not on D"


async def test_tc30_the_generic_post_creates_the_tenant_on_default(world) -> None:
    from tests.toy_service import TENANT_BODY

    made = await world.http.post("/libraries", json=TENANT_BODY, headers=world.headers)
    tenant = world.service.kit.tenant_iri(made.headers["location"].rsplit("/", 1)[1])
    record, _ = await world.service.kit.tenancy.get(tenant)
    assert made.status_code == 201, "the tenant is created"
    assert record.database_name in await world.d.list_datasets(), "its database is on D (DEC-1)"


async def test_tc31_store_of_a_tenant_is_the_toolkit_store_around_its_store(world) -> None:
    store = await world.service.kit.store_of(world.tenant)
    assert isinstance(store, ToolkitStore), "a ToolkitStore"
    assert store is world.service.kit.tenancy.stores()[CLIENT_A], "the one wired for client-a"
    assert store is not world.service.kit.store, "not the default store"


async def test_tc31_store_of_an_unknown_tenant_is_not_found(world) -> None:
    with pytest.raises(NotFound):
        await world.service.kit.store_of(
            world.service.kit.tenant_iri("0" * 8 + "-0000-4000-8000-" + "0" * 12)
        )


async def test_tc32_a_dump_of_a_tenant_on_a_store_restores_on_default(world) -> None:
    kit = world.service.kit
    archive = io.BytesIO()
    await kit.dump_tenant(world.tenant, archive)
    archive.seek(0)
    summary = await kit.restore_tenant(archive, ADA.id, store=DEFAULT_STORE)
    record, _ = await kit.tenancy.get(summary.id)
    copy = f"/libraries/{summary.id.rsplit('/', 1)[1]}/books"
    listed = await world.http.get(copy, headers=world.headers)
    assert record.database_name in await world.d.list_datasets(), "the copy is on D"
    assert listed.status_code == 200, "the copy is served"
    assert len(listed.json()["items"]) == 1, "its book reads back"


_A, _D = FakeStore(), FakeStore()


@pytest.mark.parametrize(
    ("wiring", "match"),
    [
        pytest.param({"stores": {"default": _A}}, "'default'", id="named-default"),
        pytest.param({"stores": {"a": _A, "b": _A}}, "'b'.*'a'", id="one-object-twice"),
        pytest.param({"store": _D, "stores": {"a": _D}}, "'a'.*'default'", id="the-default-again"),
    ],
)
def test_tc33_a_store_wired_wrongly_is_refused_before_the_app_is_returned(wiring, match) -> None:
    with pytest.raises(ValueError, match=match):
        ToyService(**wiring)


async def test_tc36_the_sweep_of_a_tenant_off_default_finds_its_orphan_on_its_store(world) -> None:
    kit = world.service.kit
    aggregate = str(kit.iris.mint_aggregate(world.tenant, "book", "books"))
    async with kit.session(world.tenant, ADA.id) as session:
        orphan = await session.load_graph(aggregate, TURTLE, rdf_format=RdfFormat.TURTLE)
    report = await kit.sweep_tenant(world.tenant, older_than=timedelta(0))
    assert report.loaded_graphs == [str(orphan)], "the orphan loaded on client-a is found there"


async def test_tc37_restore_on_an_unwired_store_is_refused_before_src_is_read(world) -> None:
    class Unread(io.RawIOBase):
        def readable(self) -> bool:
            return True

        def readinto(self, buffer) -> int:
            pytest.fail("the archive was read")

    d_before, a_before = await world.d.list_datasets(), await world.a.list_datasets()
    with pytest.raises(StoreNotWired, match="client-z"):
        await world.service.kit.restore_tenant(
            io.BufferedReader(Unread()), ADA.id, store="client-z"
        )
    assert await world.d.list_datasets() == d_before, "nothing is created on D"
    assert await world.a.list_datasets() == a_before, "nothing is created on A"


async def test_tc34_start_up_refuses_a_record_that_names_an_unwired_store(world) -> None:
    bare = ToyService(store=world.d)  # the same system database, client-a not wired
    with pytest.raises(StoreNotWired, match=CLIENT_A):
        async with bare.app.router.lifespan_context(bare.app):
            pytest.fail("the app must not start")


async def test_tc35_no_body_shows_the_store_name(world) -> None:
    got = await world.http.get(f"{world.path}/grants", headers=world.headers)
    put = await world.http.put(
        f"{world.path}/grants",
        content=got.content,
        headers={
            **world.headers,
            "If-Match": got.headers["etag"],
            "Content-Type": "application/json",
        },
    )
    listed = await world.http.get("/libraries", headers=world.headers)
    for name, response in (("GET", got), ("PUT", put), ("list", listed)):
        assert response.status_code == 200, f"{name} answers"
        assert "storeName" not in response.text, f"{name} body has no storeName"
        assert CLIENT_A not in response.text, f"{name} body does not name the store"


async def test_a_tenant_whose_store_is_wired_to_an_empty_store_is_gone_not_empty(world) -> None:
    other = ToyService(store=world.d, stores={CLIENT_A: FakeStore()})
    async with other.client() as http:
        response = await http.get(world.book, headers=other.bearer("ada"))
    with pytest.raises(DatabaseGone):
        async with other.kit.session(world.tenant, ADA.id) as session:
            await session.get_graph(world.tenant)
    assert response.status_code == 404, "over HTTP a missing database is a 404, not an empty result"

"""Session.find: the IRIs of the tenant's aggregates of a class whose slots equal given values (PD-6, #60)."""

from uuid import UUID

import pytest

from rdf_persistence.domain.exceptions import BadQuery
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.schema import load_schema
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_TENANT
from tests.fixtures.library.generated.books import Book, Genre
from tests.fixtures.library.generated.scans import Scan
from tests.toy import TOY_SCHEMA, toy_mapper

OTHER_TENANT = "https://example.org/libraries/other"


@pytest.fixture(scope="module")
def listings() -> Listings:
    return Listings(load_schema(TOY_SCHEMA))


def scan_iri(n: int, tenant: str = FAKE_TENANT) -> str:
    return str(DEFAULT_IRIS.aggregate(tenant, "scan", "scans", str(UUID(int=n))))


def book_iri(n: int) -> str:
    return str(DEFAULT_IRIS.aggregate(FAKE_TENANT, "book", "books", str(UUID(int=n))))


async def put_scan(session, n: int, file_name: str, tenant: str = FAKE_TENANT) -> str:
    iri = scan_iri(n, tenant)
    model = Scan(id=iri, label=f"scan {n}", file_name=file_name)
    await session.add_graph(iri, toy_mapper().to_triples(model))
    return iri


async def put_book(session, n: int, authors: list[str], label: str = "A book") -> str:
    iri = book_iri(n)
    model = Book(id=iri, label=label, description="d", genre=Genre.FICTION, authors=authors)
    await session.add_graph(iri, toy_mapper().to_triples(model))
    return iri


async def test_find_without_listings_says_how_to_get_them():  # T-21
    async with fake_session() as session:
        with pytest.raises(RuntimeError, match="find needs a session opened with listings"):
            await session.find(Scan, file_name="a")


async def test_find_returns_exactly_the_aggregate_with_the_value(listings):  # T-16
    async with fake_session(listings=listings) as session:
        first = await put_scan(session, 1, "a")
        await put_scan(session, 2, "b")
        assert await session.find(Scan, file_name="a") == [first]


async def test_find_leaves_out_other_tenants_and_other_classes(listings):  # T-17
    store = FakeStore()
    async with fake_session(store, tenant_iri=OTHER_TENANT, listings=listings) as elsewhere:
        await put_scan(elsewhere, 3, "a", OTHER_TENANT)
    async with fake_session(store, listings=listings) as session:
        await put_book(session, 4, ["X"], label="a")
        mine = await put_scan(session, 1, "a")
        assert await session.find(Scan, file_name="a") == [mine]


async def test_find_by_an_unknown_slot_is_a_bad_query_naming_slot_and_class(listings):  # T-18
    async with fake_session(listings=listings) as session:
        with pytest.raises(BadQuery, match=r"Scan has no slot 'colour'"):
            await session.find(Scan, colour="red")


async def test_find_by_several_values_of_a_slot_needs_them_all(listings):  # T-19
    async with fake_session(listings=listings) as session:
        both = await put_book(session, 1, ["X", "Y"])
        await put_book(session, 2, ["X"])
        await put_book(session, 3, ["Y", "Z"])
        assert await session.find(Book, authors=["X", "Y"]) == [both]


async def test_find_pages_until_every_match_is_collected(listings):  # T-20
    async with fake_session(listings=listings) as session:
        expected = [await put_scan(session, n, "same") for n in range(1, 202)]
        found = await session.find(Scan, file_name="same")
        assert found == sorted(expected)


async def test_find_refuses_a_class_that_is_not_an_aggregate_root(listings):
    from tests.fixtures.library.generated.books import Chapter

    async with fake_session(listings=listings) as session:
        with pytest.raises(ValueError, match="Chapter is not an aggregate root with a path"):
            await session.find(Chapter, number=1)

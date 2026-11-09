"""Session.find: the IRIs of the tenant's aggregates of a class whose slots equal given values (PD-6, #60)."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from linkml_runtime.linkml_model.annotations import Annotation

from rdf_persistence import Action
from rdf_persistence.domain.exceptions import BadQuery
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.listing import PAGE, Listings
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.session import _filters
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_TENANT
from tests.fixtures.library.generated.books import Book, Genre
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.fixtures.library.generated.scans import Scan
from tests.toy import ADA, ROLES, TOY_SCHEMA, ban, caller, graph_of, held, role, toy_mapper

OTHER_TENANT = "https://example.org/libraries/other"


@pytest.fixture(scope="module")
def listings() -> Listings:
    return Listings(load_schema(TOY_SCHEMA))


def scan_iri(n: int, tenant: str = FAKE_TENANT) -> str:
    return str(DEFAULT_IRIS.aggregate(tenant, "scan", "scans", str(UUID(int=n))))


def book_iri(n: int) -> str:
    return str(DEFAULT_IRIS.aggregate(FAKE_TENANT, "book", "books", str(UUID(int=n))))


async def put_scan(
    session, n: int, file_name: str, tenant: str = FAKE_TENANT, label: str | None = None, **more
) -> str:
    iri = scan_iri(n, tenant)
    model = Scan(id=iri, label=label or f"scan {n}", file_name=file_name, **more)
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
        mine = await put_scan(session, 1, "x", label="a")
        assert await session.find(Scan, label="a") == [mine]


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


@pytest.mark.slow
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


async def test_find_by_a_datetime_uses_the_rdf_lexical_form():  # R2-1
    when = datetime(2026, 11, 9, 8, 30, tzinfo=UTC)
    async with fake_session(listings=Listings(load_schema(TOY_SCHEMA))) as session:
        first = await put_scan(session, 1, "a", uploaded=when)
        await put_scan(session, 2, "a")
        assert await session.find(Scan, uploaded=when) == [first]


@pytest.mark.parametrize(
    ("value", "text"),
    [(True, "true"), (False, "false"), (Genre.FICTION, Genre.FICTION.value), (3, "3")],
)
def test_a_filter_value_is_its_rdf_lexical_form(value, text):  # R2-1
    assert [f.value for f in _filters({"slot": value})] == [text]


async def test_find_refuses_an_empty_list_instead_of_dropping_the_filter(listings):  # R2-7
    async with fake_session(listings=listings) as session:
        await put_book(session, 1, ["X"])
        with pytest.raises(ValueError, match="authors"):
            await session.find(Book, authors=[])


async def test_find_refuses_a_root_kept_in_the_system_database():  # R2-2
    view = load_schema(TOY_SCHEMA)
    access = view.get_class("LibraryAccess")
    for tag, value in {"rp_path": "accesses", "database": "system"}.items():
        access.annotations[tag] = Annotation(tag, value)  # a path, yet in the system database
    async with fake_session(listings=Listings(view)) as session:
        with pytest.raises(ValueError, match="LibraryAccess is not an aggregate root with a path"):
            await session.find(LibraryAccess)


async def test_find_refuses_a_class_that_is_not_in_the_schema(listings):  # R2-2
    class Stranger(Scan):
        pass

    async with fake_session(listings=listings) as session:
        with pytest.raises(ValueError, match="Stranger is not an aggregate root with a path"):
            await session.find(Stranger)


async def test_find_returns_an_aggregate_the_principal_may_not_read(listings):  # PD-6
    async with fake_session(listings=listings) as session:
        iri = await put_scan(session, 1, "a")
        rules = AccessRules(load_role_definitions(ROLES))
        banned = held(role("reader"), bans=[ban(Action.READ, graph_of(iri))])
        assert rules.hidden_graphs(caller(principal=ADA), banned) == [graph_of(iri)]
        assert await session.find(Scan, file_name="a") == [iri], "the session ignores prohibitions"


async def test_find_by_a_value_of_an_unknown_type_is_a_bad_query(listings):
    async with fake_session(listings=listings) as session:
        with pytest.raises(BadQuery):
            await session.find(Scan, byte_size="many")


def test_a_page_is_the_largest_the_list_request_accepts():  # R2-3
    from rdf_persistence.domain.generated.service.rp_service import ListRequest

    assert ListRequest(limit=PAGE).limit == PAGE
    with pytest.raises(ValueError):
        ListRequest(limit=PAGE + 1)

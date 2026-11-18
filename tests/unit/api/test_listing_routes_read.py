"""Read-only listings over the router and the fakes: one store shared by the whole class (PD-3).

The tests here never write; the five that do stay in ``test_listing_routes.py`` with a store of
their own. The class shares one service, one client and one shelf, so the schema, the app and the
five books are built once. Class decorators, not a module ``pytestmark`` (pytest.ini forbids it).
"""

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from rdf_persistence import GrantSet, Page
from rdf_persistence.core.domain.media import JSON, JSON_LD, TURTLE
from tests.toy_service import ToyService, assert_problem
from tests.unit.api.listing_shelf import BOOKS, PROBLEM_BAD_QUERY, Shelf, unordered

CLASS_LOOP = "class"


async def granted_by(shelf: Shelf) -> GrantSet:
    """The grants of the shelf's tenant as the router serves them now."""
    answer = await shelf.http.get(f"{shelf.tenant}/grants", headers=shelf.headers())
    assert answer.status_code == 200, answer.text
    return GrantSet.model_validate(answer.json())


@pytest.mark.xdist_group("listing_read")
@pytest.mark.asyncio(loop_scope=CLASS_LOOP)
class TestReadOnlyListing:
    @pytest_asyncio.fixture(scope="class", loop_scope=CLASS_LOOP)
    async def service(self) -> AsyncIterator[ToyService]:
        toy = ToyService()
        async with toy.app.router.lifespan_context(toy.app):
            yield toy

    @pytest_asyncio.fixture(scope="class", loop_scope=CLASS_LOOP)
    async def client(self, service: ToyService) -> AsyncIterator[httpx.AsyncClient]:
        async with service.client() as http:
            yield http

    @pytest_asyncio.fixture(scope="class", loop_scope=CLASS_LOOP)
    async def shelf(self, service: ToyService, client: httpx.AsyncClient) -> AsyncIterator[Shelf]:
        shelf = await Shelf.set_up(service, client)
        granted = await granted_by(shelf)
        yield shelf
        # the class shares one store: no test of the class may have written to it
        tenants = (await client.get("/libraries", headers=shelf.headers())).json()
        assert tenants["total"] == 1, "a test of the class added a tenant"
        assert await granted_by(shelf) == granted, "a test of the class changed the grants"
        assert sorted(await shelf.labels()) == sorted(label for label, *_ in BOOKS), (
            "a test of the class changed the five books"
        )

    # --- the page -----------------------------------------------------------------------------------

    async def test_a_page_holds_the_third_and_fourth_books_by_iri_with_the_total(
        self, shelf: Shelf
    ) -> None:
        response = await shelf.page_of("limit=2&offset=2")
        page = Page.model_validate(response.json())
        everything = shelf.by_iri(*shelf.books)
        assert response.status_code == 200, response.text
        assert [i["label"] for i in page.items] == everything[2:4], (
            "the third and fourth by IRI order"
        )
        assert (page.total, page.limit, page.offset) == (5, 2, 2), (
            "the total counts the whole listing"
        )

    async def test_without_parameters_the_page_starts_at_zero_with_fifty_places(
        self, shelf: Shelf
    ) -> None:
        page = Page.model_validate((await shelf.page_of()).json())
        assert page.limit == 50, "the default page size is 50"
        assert page.offset == 0, "the default offset is 0"
        assert page.total == 5, "the total counts every book"
        assert [i["label"] for i in page.items] == shelf.by_iri(*shelf.books), "ordered by IRI"

    async def test_an_offset_past_the_end_is_an_empty_page_that_still_counts(
        self, shelf: Shelf
    ) -> None:
        page = Page.model_validate((await shelf.page_of("offset=9")).json())
        assert page.items == [], "a page past the end has no items"
        assert page.total == 5, "the total still counts every book"

    async def test_an_item_is_what_a_read_of_the_same_book_returns(self, shelf: Shelf) -> None:
        page = (await shelf.page_of("limit=1")).json()
        item = page["items"][0]
        read = await shelf.http.get(
            item["id"].replace(shelf.tenant_iri, shelf.tenant), headers=shelf.headers()
        )
        assert unordered(item) == unordered(read.json()), "framed the same way, parts nested"

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("sort=label", ["Beloved", "Candide", "Dune", "Emma", "Ulysses"]),
            ("sort=-label", ["Ulysses", "Emma", "Dune", "Candide", "Beloved"]),
            ("sort=-published&limit=2", ["Beloved", "Dune"]),
            ("sort=published&limit=2", ["Candide", "Emma"]),
            ("genre=nonfiction&sort=label", ["Candide", "Emma"]),
            ("genre=fiction&authors=Herbert&sort=label", ["Dune", "Ulysses"]),
            ("authors=Herbert&authors=Joyce", ["Ulysses"]),
            ("published=1922-02-02", ["Ulysses"]),
            ("label=Dune&genre=nonfiction", []),
            ("label=No+such+book", []),
        ],
    )
    async def test_filters_and_a_sort_key_select_and_order_the_page(
        self, shelf, query, expected
    ) -> None:
        assert await shelf.labels(query) == expected, (
            "the filters and the sort key give the expected labels"
        )

    async def test_the_total_of_a_filtered_listing_counts_the_matches_only(
        self, shelf: Shelf
    ) -> None:
        page = Page.model_validate((await shelf.page_of("genre=fiction&limit=1")).json())
        assert len(page.items) == 1, "the limit caps the page at one item"
        assert page.total == 3, "the total counts every match, not just the page"

    # --- representations ----------------------------------------------------------------------------

    async def test_json_items_come_without_context_and_the_link_header_leads_to_it(
        self, shelf: Shelf
    ) -> None:
        response = await shelf.page_of("limit=1")
        assert response.headers["content-type"].startswith(JSON), (
            "the plain JSON listing has a JSON content type"
        )
        assert "context.jsonld" in response.headers["link"], "as for a read"
        assert "@context" not in response.json()["items"][0], "the JSON items carry no context"

    async def test_json_ld_items_carry_their_context(self, shelf: Shelf) -> None:
        response = await shelf.page_of("limit=2", **{"Accept": JSON_LD})
        items = response.json()["items"]
        assert response.headers["content-type"].startswith(JSON_LD), (
            "the JSON-LD listing has a JSON-LD content type"
        )
        assert all("@context" in item for item in items), "each item is a document on its own"

    async def test_a_listing_cannot_be_turtle(self, shelf: Shelf) -> None:
        response = await shelf.page_of(**{"Accept": TURTLE})
        problem = assert_problem(response, 406, "not-acceptable")  # a listing is not a document
        assert problem.title == "Not acceptable", "the fixed title"

    # --- a bad query --------------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "query",
        [
            "colour=red",
            "creator=https://example.org/people/ada",
            "chapters=1",
            "genre=horror",
            "published=yesterday",
            "limit=0",
            "limit=201",
            "limit=ten",
            "limit=1&limit=2",
            "offset=-1",
            "offset=1.5",
            "sort=colour",
            "sort=chapters",
            "sort=label&sort=isbn",
            "sort=",
        ],
    )
    async def test_a_bad_query_is_a_400_problem_and_changes_nothing(self, shelf, query) -> None:
        response = await shelf.page_of(query)
        problem = assert_problem(response, 400, "bad-query")
        assert problem.title == PROBLEM_BAD_QUERY, "the fixed title"
        assert len(await shelf.labels()) == 5, "the store is unchanged"

    async def test_a_hostile_filter_value_is_just_a_value(self, shelf: Shelf) -> None:
        response = await shelf.page_of("label=%22%7D+%3B+DROP+ALL+%3B+%23")
        assert response.status_code == 200, response.text
        assert response.json()["items"] == [], "the hostile value matches no item"
        assert response.json()["total"] == 0, "the hostile value matches nothing"
        assert len(await shelf.labels()) == 5, "the store is unchanged"

    # --- who sees what ------------------------------------------------------------------------------

    async def test_a_reader_lists_and_an_outsider_does_not_see_the_tenant(
        self, shelf: Shelf
    ) -> None:
        assert len(await shelf.labels(who="rita")) == 5, "the reader lists all five books"
        assert (await shelf.page_of(who="omar")).status_code == 404, (
            "an outsider gets 404 for the tenant"
        )

    async def test_a_global_reader_lists_the_books_of_any_tenant(self, shelf: Shelf) -> None:
        response = await shelf.http.get(shelf.path, headers=shelf.headers("root", "admin"))
        assert response.json()["total"] == 5, "the global reader sees the five books of the tenant"

    async def test_a_listing_without_a_token_is_a_401(self, shelf: Shelf) -> None:
        assert (await shelf.http.get(shelf.path)).status_code == 401, (
            "a listing without a token is refused with 401"
        )

    async def test_a_listing_of_a_tenant_that_does_not_exist_is_a_404(self, shelf: Shelf) -> None:
        response = await shelf.http.get(
            "/libraries/00000000-0000-4000-8000-000000000000/books", headers=shelf.headers()
        )
        assert response.status_code == 404, "a listing of a missing tenant is 404"

    # --- the tenants --------------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "query", ["limit=0", "limit=201", "offset=-1", "limit=x", "sort=label", "label=Ghent"]
    )
    async def test_the_tenant_listing_takes_only_limit_and_offset(
        self, shelf, client, query
    ) -> None:
        response = await client.get(f"/libraries?{query}", headers=shelf.headers())
        problem = assert_problem(response, 400, "bad-query")
        assert problem.title == PROBLEM_BAD_QUERY, "the fixed title"

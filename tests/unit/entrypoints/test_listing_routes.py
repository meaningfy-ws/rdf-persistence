"""Listings over the router and the fakes: pages, filters, sort, who sees what (task 5.4, PD-9, PD-15)."""

from collections.abc import AsyncIterator

import httpx
import pytest

from rdf_persistence import GrantSet, Page, Problem
from rdf_persistence.domain.generated.rp_access import Action, Grant, Prohibition
from rdf_persistence.entrypoints.problems import PROBLEM_MEDIA_TYPE
from rdf_persistence.services.documents import JSON, JSON_LD, TURTLE
from tests.toy_service import ToyService, principal_of
from tests.unit.entrypoints.scene import BOOK, TENANT_BODY

PROBLEM_BAD_QUERY = "Bad query"
BOOKS = [
    ("Dune", "fiction", "1965-08-01", ["Herbert"]),
    ("Emma", "nonfiction", "1815-12-23", ["Austen"]),
    ("Ulysses", "fiction", "1922-02-02", ["Joyce", "Herbert"]),
    ("Candide", "nonfiction", None, []),
    ("Beloved", "fiction", "1987-09-02", ["Morrison"]),
]


@pytest.fixture
async def service() -> AsyncIterator[ToyService]:
    toy = ToyService()
    async with toy.app.router.lifespan_context(toy.app):
        yield toy


@pytest.fixture
async def client(service: ToyService) -> AsyncIterator[httpx.AsyncClient]:
    async with service.client() as http:
        yield http


class Shelf:
    """A tenant of ``ada`` with five books, a reader ``rita`` and a stranger ``omar``."""

    def __init__(self, service: ToyService, http: httpx.AsyncClient) -> None:
        self.service, self.http = service, http
        self.tenant = ""
        self.tenant_iri = ""
        self.books: dict[str, str] = {}  # label -> IRI

    def headers(self, who: str = "ada", *roles: str) -> dict[str, str]:
        return self.service.bearer(who, *roles)

    @property
    def path(self) -> str:
        return f"{self.tenant}/books"

    async def page_of(self, query: str = "", who: str = "ada", **headers: str) -> httpx.Response:
        return await self.http.get(f"{self.path}?{query}", headers={**self.headers(who), **headers})

    async def labels(self, query: str = "", who: str = "ada") -> list[str]:
        page = (await self.page_of(query, who)).json()
        return [item["label"] for item in page["items"]]

    async def grant(self, *grants: Grant, prohibitions: list[Prohibition] | None = None) -> None:
        current = await self.http.get(f"{self.tenant}/grants", headers=self.headers())
        body = GrantSet.model_validate(current.json())
        updated = GrantSet(
            grants=[*(body.grants or []), *grants],
            prohibitions=[*(body.prohibitions or []), *(prohibitions or [])] or None,
        )
        put = await self.http.put(
            f"{self.tenant}/grants",
            content=updated.model_dump_json(exclude_none=True),
            headers={**self.headers(), "If-Match": current.headers["etag"], "Content-Type": JSON},
        )
        assert put.status_code == 200, put.text

    @classmethod
    async def set_up(cls, service: ToyService, http: httpx.AsyncClient) -> "Shelf":
        shelf = cls(service, http)
        made = await http.post("/libraries", json=TENANT_BODY, headers=shelf.headers())
        shelf.tenant, shelf.tenant_iri = made.headers["location"], made.json()["id"]
        for label, genre, published, authors in BOOKS:
            body = {**BOOK, "label": label, "genre": genre, "authors": authors}
            if published:
                body["published"] = published
            created = await http.post(shelf.path, json=body, headers=shelf.headers())
            assert created.status_code == 201, created.text
            shelf.books[label] = created.json()["id"]
        await shelf.grant(
            Grant(assignee=principal_of("rita"), target=shelf.tenant_iri, role="reader")
        )
        return shelf

    def by_iri(self, *labels: str) -> list[str]:
        return sorted(labels, key=lambda label: self.books[label])


@pytest.fixture
async def shelf(service: ToyService, client: httpx.AsyncClient) -> Shelf:
    return await Shelf.set_up(service, client)


def problem_of(response: httpx.Response) -> Problem:
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE, response.text
    return Problem.model_validate(response.json())


# --- the page -----------------------------------------------------------------------------------


async def test_a_page_holds_the_third_and_fourth_books_by_iri_with_the_total(shelf) -> None:
    response = await shelf.page_of("limit=2&offset=2")
    page = Page.model_validate(response.json())
    everything = shelf.by_iri(*shelf.books)
    assert response.status_code == 200, response.text
    assert [i["label"] for i in page.items] == everything[2:4], "the third and fourth by IRI order"
    assert (page.total, page.limit, page.offset) == (5, 2, 2), "the total counts the whole listing"


async def test_without_parameters_the_page_starts_at_zero_with_fifty_places(shelf) -> None:
    page = Page.model_validate((await shelf.page_of()).json())
    assert (page.limit, page.offset, page.total) == (50, 0, 5)
    assert [i["label"] for i in page.items] == shelf.by_iri(*shelf.books), "ordered by IRI"


async def test_an_offset_past_the_end_is_an_empty_page_that_still_counts(shelf) -> None:
    page = Page.model_validate((await shelf.page_of("offset=9")).json())
    assert (page.items, page.total) == ([], 5)


async def test_an_item_is_what_a_read_of_the_same_book_returns(shelf) -> None:
    page = (await shelf.page_of("limit=1")).json()
    item = page["items"][0]
    read = await shelf.http.get(
        item["id"].replace(shelf.tenant_iri, shelf.tenant), headers=shelf.headers()
    )
    assert item == read.json(), "framed the same way, parts nested"


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
async def test_filters_and_a_sort_key_select_and_order_the_page(shelf, query, expected) -> None:
    assert await shelf.labels(query) == expected


async def test_the_total_of_a_filtered_listing_counts_the_matches_only(shelf) -> None:
    page = Page.model_validate((await shelf.page_of("genre=fiction&limit=1")).json())
    assert (len(page.items), page.total) == (1, 3)


async def test_a_listing_never_shows_the_books_of_another_tenant(shelf, client, service) -> None:
    other = await client.post("/libraries", json=TENANT_BODY, headers=shelf.headers("bob"))
    await client.post(f"{other.headers['location']}/books", json=BOOK, headers=shelf.headers("bob"))
    assert len(await shelf.labels()) == 5
    theirs = await client.get(f"{other.headers['location']}/books", headers=shelf.headers("bob"))
    assert theirs.json()["total"] == 1


# --- representations ----------------------------------------------------------------------------


async def test_json_items_come_without_context_and_the_link_header_leads_to_it(shelf) -> None:
    response = await shelf.page_of("limit=1")
    assert response.headers["content-type"].startswith(JSON)
    assert "context.jsonld" in response.headers["link"], "as for a read"
    assert "@context" not in response.json()["items"][0]


async def test_json_ld_items_carry_their_context(shelf) -> None:
    response = await shelf.page_of("limit=2", **{"Accept": JSON_LD})
    items = response.json()["items"]
    assert response.headers["content-type"].startswith(JSON_LD)
    assert all("@context" in item for item in items), "each item is a document on its own"


async def test_a_listing_cannot_be_turtle(shelf) -> None:
    response = await shelf.page_of(**{"Accept": TURTLE})
    assert response.status_code == 406
    assert problem_of(response).title == "Not acceptable"


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
async def test_a_bad_query_is_a_400_problem_and_changes_nothing(shelf, query) -> None:
    response = await shelf.page_of(query)
    assert response.status_code == 400, response.text
    assert problem_of(response).title == PROBLEM_BAD_QUERY
    assert len(await shelf.labels()) == 5


async def test_a_hostile_filter_value_is_just_a_value(shelf) -> None:
    response = await shelf.page_of("label=%22%7D+%3B+DROP+ALL+%3B+%23")
    assert response.status_code == 200, response.text
    assert (response.json()["items"], response.json()["total"]) == ([], 0)
    assert len(await shelf.labels()) == 5, "the store is unchanged"


# --- who sees what ------------------------------------------------------------------------------


async def test_a_reader_lists_and_an_outsider_does_not_see_the_tenant(shelf) -> None:
    assert len(await shelf.labels(who="rita")) == 5
    assert (await shelf.page_of(who="omar")).status_code == 404


async def test_a_global_reader_lists_the_books_of_any_tenant(shelf) -> None:
    response = await shelf.http.get(shelf.path, headers=shelf.headers("root", "admin"))
    assert response.json()["total"] == 5


async def test_a_permission_on_one_book_alone_does_not_list_books(shelf) -> None:
    book = shelf.books["Dune"]
    await shelf.grant(
        Grant(assignee=principal_of("bea"), target=f"{book}/graph", action=Action.MODIFY)
    )
    own = await shelf.http.get(
        shelf.path + "/" + book.rsplit("/", 1)[1], headers=shelf.headers("bea")
    )
    listing = await shelf.page_of(who="bea")
    assert own.status_code == 200, "she can read the book she may modify"
    assert listing.status_code == 404, "but a listing needs read on the tenant"


async def test_a_book_the_caller_is_prohibited_from_reading_is_not_listed_or_counted(shelf) -> None:
    hidden = shelf.books["Emma"]
    await shelf.grant(
        prohibitions=[
            Prohibition(assignee=principal_of("rita"), target=f"{hidden}/graph", action=Action.READ)
        ]
    )
    page = Page.model_validate((await shelf.page_of("limit=2", who="rita")).json())
    assert "Emma" not in [i["label"] for i in page.items]
    assert page.total == 4, "the total leaves it out as well"
    assert len(await shelf.labels(who="ada")) == 5, "the librarian is not prohibited"


async def test_a_prohibition_of_modify_leaves_the_book_in_the_listing(shelf) -> None:
    book = shelf.books["Emma"]
    await shelf.grant(
        prohibitions=[
            Prohibition(assignee=principal_of("rita"), target=f"{book}/graph", action=Action.MODIFY)
        ]
    )
    assert len(await shelf.labels(who="rita")) == 5


async def test_a_listing_without_a_token_is_a_401(shelf) -> None:
    assert (await shelf.http.get(shelf.path)).status_code == 401


async def test_a_listing_of_a_tenant_that_does_not_exist_is_a_404(shelf) -> None:
    response = await shelf.http.get(
        "/libraries/00000000-0000-4000-8000-000000000000/books", headers=shelf.headers()
    )
    assert response.status_code == 404


# --- the tenants --------------------------------------------------------------------------------


async def test_the_tenant_listing_is_paged_by_iri_like_any_other(shelf, client) -> None:
    for name in ("Two", "Three"):
        await client.post(
            "/libraries", json={**TENANT_BODY, "label": name}, headers=shelf.headers()
        )
    everyone = (await client.get("/libraries", headers=shelf.headers())).json()
    ids = [t["id"] for t in everyone["items"]]
    page = Page.model_validate(
        (await client.get("/libraries?limit=2&offset=1", headers=shelf.headers())).json()
    )
    assert ids == sorted(ids), "ordered by IRI"
    assert (page.total, page.limit, page.offset) == (3, 2, 1)
    assert [t["id"] for t in page.items] == ids[1:3]


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=201", "offset=-1", "limit=x", "sort=label", "label=Ghent"]
)
async def test_the_tenant_listing_takes_only_limit_and_offset(shelf, client, query) -> None:
    response = await client.get(f"/libraries?{query}", headers=shelf.headers())
    assert response.status_code == 400, response.text
    assert problem_of(response).title == PROBLEM_BAD_QUERY

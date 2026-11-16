"""Listings over the router and the fakes: the cases that write (task 5.4, PD-9, PD-15).

The read-only cases share one store in ``test_listing_routes_read.py`` (PD-3); the five here
change the store, so each gets a shelf of its own.
"""

import json

import httpx
import pytest

from rdf_persistence import GrantSet, Page
from rdf_persistence.domain.generated.rp_access import Action, Grant, Prohibition
from rdf_persistence.domain.media import JSON
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, principal_of

PROBLEM_BAD_QUERY = "Bad query"
BOOKS = [
    ("Dune", "fiction", "1965-08-01", ["Herbert"]),
    ("Emma", "nonfiction", "1815-12-23", ["Austen"]),
    ("Ulysses", "fiction", "1922-02-02", ["Joyce", "Herbert"]),
    ("Candide", "nonfiction", None, []),
    ("Beloved", "fiction", "1987-09-02", ["Morrison"]),
]


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
            body = {**DUNE_BODY, "label": label, "genre": genre, "authors": authors}
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


def _unordered(value: object) -> object:
    """Make a document comparable regardless of the order of multivalued slots."""
    if isinstance(value, dict):
        return {key: _unordered(item) for key, item in value.items()}
    if isinstance(value, list):
        return sorted(
            (_unordered(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True)
        )
    return value


async def test_a_listing_never_shows_the_books_of_another_tenant(shelf, client, service) -> None:
    other = await client.post("/libraries", json=TENANT_BODY, headers=shelf.headers("bob"))
    await client.post(
        f"{other.headers['location']}/books", json=DUNE_BODY, headers=shelf.headers("bob")
    )
    assert len(await shelf.labels()) == 5
    theirs = await client.get(f"{other.headers['location']}/books", headers=shelf.headers("bob"))
    assert theirs.json()["total"] == 1


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

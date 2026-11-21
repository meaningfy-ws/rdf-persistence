"""The shelf both listing test files build on: a tenant with five books, a reader and a stranger."""

import json
from datetime import date

import httpx

from rdf_persistence import GrantSet
from rdf_persistence.access.domain.generated.rp_access import Grant, Prohibition
from rdf_persistence.core.domain.media import JSON
from tests.fixtures.library.domain.generated.books import Genre
from tests.toy_service import (
    ADA,
    RITA,
    TENANT_BODY,
    ToyService,
    body_of,
    dune_book,
    principal_of,
)

PROBLEM_BAD_QUERY = "Bad query"
BOOKS = [
    ("Dune", Genre.FICTION, date(1965, 8, 1), ["Herbert"]),
    ("Emma", Genre.NONFICTION, date(1815, 12, 23), ["Austen"]),
    ("Ulysses", Genre.FICTION, date(1922, 2, 2), ["Joyce", "Herbert"]),
    ("Candide", Genre.NONFICTION, None, []),
    ("Beloved", Genre.FICTION, date(1987, 9, 2), ["Morrison"]),
]


class Shelf:
    """A tenant of ``ada`` with five books, a reader ``rita`` and a stranger ``omar``."""

    def __init__(self, service: ToyService, http: httpx.AsyncClient) -> None:
        self.service, self.http = service, http
        self.tenant = ""
        self.tenant_iri = ""
        self.books: dict[str, str] = {}  # label -> IRI

    def headers(self, who: str = ADA, *roles: str) -> dict[str, str]:
        return self.service.bearer(who, *roles)

    @property
    def path(self) -> str:
        return f"{self.tenant}/books"

    async def page_of(self, query: str = "", who: str = ADA, **headers: str) -> httpx.Response:
        return await self.http.get(f"{self.path}?{query}", headers={**self.headers(who), **headers})

    async def labels(self, query: str = "", who: str = ADA) -> list[str]:
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
            book = dune_book(label).model_copy(update={"genre": genre, "authors": authors})
            if published:
                book.published = published
            created = await http.post(shelf.path, json=body_of(book), headers=shelf.headers())
            assert created.status_code == 201, created.text
            shelf.books[label] = created.json()["id"]
        await shelf.grant(
            Grant(assignee=principal_of(RITA), target=shelf.tenant_iri, role="reader")
        )
        return shelf

    def by_iri(self, *labels: str) -> list[str]:
        return sorted(labels, key=lambda label: self.books[label])


def unordered(value: object) -> object:
    """Make a document comparable regardless of the order of multivalued slots."""
    if isinstance(value, dict):
        return {key: unordered(item) for key, item in value.items()}
    if isinstance(value, list):
        return sorted(
            (unordered(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True)
        )
    return value

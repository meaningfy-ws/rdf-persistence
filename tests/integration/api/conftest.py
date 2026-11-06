"""The toy library served over the API against Fuseki: one service per test, with a prefix of its own.

The prefix names the system database and every tenant database, so tests never see each other's data;
everything a test made is dropped afterwards.
"""

from collections.abc import AsyncIterator

import httpx
import pytest

from rdf_persistence import FusekiStore
from tests.toy_service import ToyService, unique_prefix

TENANT_BODY = {"label": "Ghent", "root": {"description": "Books for all.", "city": "Ghent"}}
BOOK = {
    "label": "Dune",
    "description": "A planet.",
    "genre": "fiction",
    "authors": ["Herbert"],
    "chapters": [{"number": 1, "notes": [{"label": "n", "description": "d", "text": "t"}]}],
}


async def drop_databases(store: FusekiStore, prefix: str) -> None:
    for name in await store.list_datasets():
        if name.startswith(f"{prefix}-"):
            await store.drop_dataset(name)


@pytest.fixture
def prefix() -> str:
    return unique_prefix()


@pytest.fixture
async def toy(store: FusekiStore, prefix: str) -> AsyncIterator[ToyService]:
    service = ToyService(store, prefix=prefix)
    async with service.app.router.lifespan_context(service.app):
        yield service
    await drop_databases(store, prefix)


@pytest.fixture
async def client(toy: ToyService) -> AsyncIterator[httpx.AsyncClient]:
    async with toy.client() as http:
        yield http


async def make_book(toy: ToyService, http: httpx.AsyncClient, who: str = "ada") -> httpx.Response:
    """A tenant made by ``who``, and a book in it: the answer to the book's creation."""
    tenant = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer(who))
    assert tenant.status_code == 201, tenant.text
    book = await http.post(
        f"{tenant.headers['location']}/books", json=BOOK, headers=toy.bearer(who)
    )
    assert book.status_code == 201, book.text
    return book

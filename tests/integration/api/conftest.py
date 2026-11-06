"""The toy library served over the API against Fuseki: one service per test, with a prefix of its own.

The prefix names the system database and every tenant database, so tests never see each other's data;
everything a test made is dropped afterwards.
"""

from collections.abc import AsyncIterator

import httpx
import pytest

from rdf_persistence import FusekiStore
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, drop_databases, unique_prefix


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


async def make_tenant(toy: ToyService, http: httpx.AsyncClient, who: str = "ada") -> str:
    """A tenant made by ``who``: the path of its collection of routes."""
    tenant = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer(who))
    assert tenant.status_code == 201, tenant.text
    return str(tenant.headers["location"])


async def make_book(toy: ToyService, http: httpx.AsyncClient, who: str = "ada") -> httpx.Response:
    """A tenant made by ``who``, and a book in it: the answer to the book's creation."""
    tenant = await make_tenant(toy, http, who)
    book = await http.post(f"{tenant}/books", json=DUNE_BODY, headers=toy.bearer(who))
    assert book.status_code == 201, book.text
    return book

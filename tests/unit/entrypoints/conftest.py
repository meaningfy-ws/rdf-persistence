"""The router's unit tests run against fakes and in-process requests: any socket connection is a failure."""

from collections.abc import AsyncIterator

import httpx
import pytest

from rdf_persistence.testkit import no_network  # noqa: F401  (fixture)
from tests.toy_service import ToyService
from tests.unit.entrypoints.scene import Scene


@pytest.fixture(autouse=True)
def _offline(no_network: None) -> None:  # noqa: F811
    """Block the network for every test of this folder."""


@pytest.fixture
async def service() -> AsyncIterator[ToyService]:
    toy = ToyService()
    async with toy.app.router.lifespan_context(toy.app):
        yield toy


@pytest.fixture
async def client(service: ToyService) -> AsyncIterator[httpx.AsyncClient]:
    async with service.client() as http:
        yield http


@pytest.fixture
async def scene(service: ToyService, client: httpx.AsyncClient) -> Scene:
    return await Scene.set_up(service, client)

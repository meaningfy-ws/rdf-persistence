"""Load the container fixtures for the store budgets; they run against a real Fuseki."""

from collections.abc import AsyncIterator

import pytest

from rdf_persistence import FusekiStore
from tests.conftest import load_container_plugin


def pytest_configure(config: pytest.Config) -> None:
    """Register the container fixtures plugin (needs the extra ``rdf-persistence[testkit]``)."""
    load_container_plugin(config)


@pytest.fixture
async def store(fuseki) -> AsyncIterator[FusekiStore]:
    """A client of the session's Fuseki container."""
    async with FusekiStore(fuseki.url, fuseki.user, fuseki.password) as client:
        yield client

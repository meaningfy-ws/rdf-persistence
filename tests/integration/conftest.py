"""Load the container fixtures for the integration tests; the unit lane never imports testcontainers."""

from collections.abc import AsyncIterator

import pytest

from rdf_persistence import FusekiStore, ToolkitSettings
from tests.conftest import load_container_plugin


def pytest_configure(config: pytest.Config) -> None:
    """Register the container fixtures plugin (needs the extra ``rdf-persistence[testkit]``)."""
    load_container_plugin(config)


@pytest.fixture(scope="session")
def toolkit() -> ToolkitSettings:
    """The toolkit's settings, once per session: every adapter of the lane takes its group from here.

    A test that needs another value replaces the group on a copy, never an ad-hoc mapping.
    """
    return ToolkitSettings()


@pytest.fixture
async def store(fuseki, toolkit: ToolkitSettings) -> AsyncIterator[FusekiStore]:
    """A client of the session's Fuseki container."""
    async with FusekiStore(fuseki.url, fuseki.user, fuseki.password, http=toolkit.http) as client:
        yield client

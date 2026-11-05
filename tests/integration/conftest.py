"""Load the container fixtures for the integration tests; the unit lane never imports testcontainers."""

import pytest

from tests.conftest import load_container_plugin


def pytest_configure(config: pytest.Config) -> None:
    """Register the container fixtures plugin (needs the extra ``rdf-persistence[testkit]``)."""
    load_container_plugin(config)

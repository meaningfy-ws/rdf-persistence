"""Load the container fixtures for the generator's e2e tests.

Any session that collects this folder registers the plugin, so the unit lanes and
``make test-generator`` ignore ``tests/generator/e2e`` (Makefile ``GENERATOR_E2E``); only
``make test-containers`` and ``make test-e2e`` collect it.
"""

import pytest

from tests.conftest import load_container_plugin


def pytest_configure(config: pytest.Config) -> None:
    """Register the container fixtures plugin (needs the extra ``rdf-persistence[testkit]``)."""
    load_container_plugin(config)

"""A pytest plugin that releases memory between tests and test modules (PD-9).

Opt in from the root conftest: ``pytest_plugins = ["rdf_persistence.testkit.memory_plugin"]``.
``TEST_RELEASE=off`` disables it.
"""

import os
from collections.abc import Generator

import pytest

from rdf_persistence.testkit.memory import after_test, clear_caches, release_memory


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(
    item: pytest.Item, nextitem: pytest.Item | None
) -> Generator[None, None, None]:
    """Work after pytest's own teardown has finalised the fixtures."""
    yield
    after_test(
        item,
        nextitem,
        clear=clear_caches,
        release=release_memory,
        environ=os.environ,  # noqa: TID251 -- a pytest switch of the test process, not service config
    )

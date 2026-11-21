"""Root test configuration for rdf_persistence.

WHY THIS HOOK EXISTS
--------------------
Test-type markers (``unit``, ``feature``, ``e2e``, ``integration``) and the
container markers (``store``, ``files``, ``identity``; named in ``rdf_persistence.testkit.markers``) are stamped
onto every collected test **by file path**, not by per-file ``pytestmark``.

The natural-looking shortcut — putting ``pytestmark = pytest.mark.unit`` in a
``conftest.py`` — is **silently ignored** by pytest: a ``conftest.py`` is loaded
as a *plugin*, not as a *test module*, so module-level ``pytestmark`` never runs.
The supported way to tag a whole tree is the ``pytest_collection_modifyitems``
collection hook below. It is the single source of truth for marker assignment,
so no test file needs to decorate itself and the ``-m`` filters in the Makefile
(``test-unit`` -> ``pytest -m unit`` etc.) stay correct as new tests are added.

The test-type markers are registered in ``pytest.ini``; the container markers are registered by
the fixtures plugin (``--strict-markers`` is on, so an unregistered marker is an error).

``slow`` is the exception: it is not stamped by path. Put ``@pytest.mark.slow`` on the test itself
(see ``develop/testing.adoc``).
"""

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from rdf_persistence.testkit.markers import EVENTS, FILES, IDENTITY, STORE, register_markers

# Path constants — single source of truth for the test directory structure.
TESTS_ROOT_DIR = Path(__file__).parent

# CI runs the same examples every time (checklist 8); locally Hypothesis explores. Registered and
# loaded at import of this root conftest, so every xdist worker has them.
settings.register_profile(
    "ci", derandomize=True, max_examples=20, deadline=None, suppress_health_check=list(HealthCheck)
)
settings.register_profile(
    "default", max_examples=40, deadline=None, suppress_health_check=list(HealthCheck)
)
settings.load_profile(
    os.environ.get("HYPOTHESIS_PROFILE", "ci" if os.environ.get("CI") else "default")
)

# Freshness of the generated code (PD-26) is checked at the start of every session; pytester runs
# the plugin's own tests.
pytest_plugins = ["pytester", "rdf_persistence_generation.testkit.freshness"]

# The container fixtures plugin (PD-16). Only tests/integration/, tests/e2e/, tests/perf/store/ and
# tests/generator/e2e/ load it, so the unit lanes, which ignore those folders (the Makefile's
# UNIT_LANE and GENERATOR_E2E), run without testcontainers. pytest allows `pytest_plugins` only
# in the rootdir conftest, so those four conftests call `load_container_plugin` from
# `pytest_configure`.
CONTAINER_PLUGIN = "rdf_persistence.testkit.containers.fixtures"


def pytest_configure(config: pytest.Config) -> None:
    """Register the container markers for every lane, including the unit lane."""
    register_markers(config)


def load_container_plugin(config: pytest.Config) -> None:
    """Register the container fixtures plugin once, however many conftests ask for it."""
    config.pluginmanager.import_plugin(CONTAINER_PLUGIN)


@dataclass(frozen=True)
class DirectoryMarkers:
    """A directory below tests/ and every marker it implies."""

    directory: str
    markers: tuple[str, ...]


# The first row whose directory starts the relative path wins (PD-16), so a row never needs
# to exclude another.
_MARKERS_BY_DIR = (
    DirectoryMarkers("generator/unit/", ("unit",)),
    DirectoryMarkers("generator/feature/", ("feature",)),
    DirectoryMarkers("generator/integration/", ("integration",)),
    # install_service needs a store, a file store and an identity provider, as the library's e2e/ row
    DirectoryMarkers("generator/e2e/", ("e2e", STORE, FILES, IDENTITY)),
    DirectoryMarkers("unit/", ("unit",)),
    DirectoryMarkers("feature/", ("feature",)),
    DirectoryMarkers("integration/store/", ("integration", STORE)),
    DirectoryMarkers("integration/api/", ("integration", STORE)),
    DirectoryMarkers("integration/tenancy/", ("integration", STORE, FILES)),
    DirectoryMarkers("integration/files/", ("integration", FILES)),
    DirectoryMarkers("integration/identity/", ("integration", IDENTITY)),
    DirectoryMarkers("integration/adapters/", ("integration", EVENTS)),
    DirectoryMarkers("integration/network/", ("integration",)),
    DirectoryMarkers("e2e/", ("e2e", STORE, FILES, IDENTITY)),
    DirectoryMarkers("perf/store/", ("perf", STORE)),
    DirectoryMarkers("perf/", ("perf",)),
)


def markers_for_path(path: str) -> tuple[str, ...]:
    """Return every marker implied by the directory a test file lives in.

    Only the part of the path below ``tests/`` is matched, so a checkout under a directory
    that happens to be called ``unit`` does not change the result.

    Args:
        path: The test file's path.

    Returns:
        The markers of the matching row of the path table, or ``()`` if none matches.
    """
    try:
        relative = Path(path).relative_to(TESTS_ROOT_DIR).as_posix()
    except ValueError:
        return ()
    for row in _MARKERS_BY_DIR:
        if relative.startswith(row.directory):
            return row.markers
    return ()


def pytest_collection_modifyitems(items: list) -> None:
    """Stamp each collected test with every marker of its directory's row.

    pytest does not honour ``pytestmark`` defined in a ``conftest.py`` (conftest
    is a plugin, not a test module). This collection hook is the correct place
    to apply markers so that ``-m unit``, ``-m store`` and the like filter
    correctly with zero per-file decoration.

    Args:
        items: The list of collected test items, mutated in place.
    """
    for item in items:
        for marker in markers_for_path(str(item.fspath)):
            item.add_marker(getattr(pytest.mark, marker))


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
# Put fixtures used across more than one test tree here. The container fixtures
# come from the testkit plugin above.


@pytest.fixture(scope="session")
def _span_exporter() -> InMemorySpanExporter:
    """The one exporter of the process: the global provider is set once, and xdist workers are processes."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


@pytest.fixture
def spans(_span_exporter: InMemorySpanExporter) -> Callable[[], tuple[ReadableSpan, ...]]:
    """A callable over the spans finished since the test began; call it after the code under test."""
    _span_exporter.clear()
    return lambda: tuple(_span_exporter.get_finished_spans())

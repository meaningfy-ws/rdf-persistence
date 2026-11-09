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

from dataclasses import dataclass
from pathlib import Path

import pytest

from rdf_persistence.testkit.markers import FILES, IDENTITY, STORE, register_markers

# Path constants — single source of truth for the test directory structure.
TESTS_ROOT_DIR = Path(__file__).parent
TEST_DATA_DIR = TESTS_ROOT_DIR / "test_data"

# Freshness of the generated code (PD-26) is checked at the start of every session; pytester runs
# the plugin's own tests.
pytest_plugins = ["pytester", "rdf_persistence.testkit.freshness"]

# The container fixtures plugin (PD-16). Only tests/integration/ and tests/e2e/ load it, so the
# unit lane runs without testcontainers. pytest allows `pytest_plugins` only in the rootdir
# conftest, so those two conftests call `load_container_plugin` from `pytest_configure`.
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
    DirectoryMarkers("unit/", ("unit",)),
    DirectoryMarkers("feature/", ("feature",)),
    DirectoryMarkers("integration/store/", ("integration", STORE)),
    DirectoryMarkers("integration/api/", ("integration", STORE)),
    DirectoryMarkers("integration/tenancy/", ("integration", STORE, FILES)),
    DirectoryMarkers("integration/files/", ("integration", FILES)),
    DirectoryMarkers("integration/identity/", ("integration", IDENTITY)),
    DirectoryMarkers("e2e/", ("e2e", STORE, FILES, IDENTITY)),
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


def load_text_file(relative_path: str) -> str:
    """Load text content from the ``test_data`` directory.

    Args:
        relative_path: Path relative to ``test_data/``, e.g. ``"samples/a.json"``.

    Returns:
        The full file content as a UTF-8 string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    file_path = TEST_DATA_DIR / relative_path
    if not file_path.exists():
        raise FileNotFoundError(f"Test data file not found: {file_path}")
    return file_path.read_text(encoding="utf-8")

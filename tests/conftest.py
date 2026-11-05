"""Root test configuration for rdf_persistence.

WHY THIS HOOK EXISTS
--------------------
Test-type markers (``unit``, ``feature``, ``e2e``, ``integration``) and the
container markers (``store``, ``files``, ``identity``) are stamped
onto every collected test **by file path**, not by per-file ``pytestmark``.

The natural-looking shortcut — putting ``pytestmark = pytest.mark.unit`` in a
``conftest.py`` — is **silently ignored** by pytest: a ``conftest.py`` is loaded
as a *plugin*, not as a *test module*, so module-level ``pytestmark`` never runs.
The supported way to tag a whole tree is the ``pytest_collection_modifyitems``
collection hook below. It is the single source of truth for marker assignment,
so no test file needs to decorate itself and the ``-m`` filters in the Makefile
(``test-unit`` -> ``pytest -m unit`` etc.) stay correct as new tests are added.

Markers must also be registered in ``pytest.ini`` under ``[pytest] markers``
(with ``--strict-markers`` on) or pytest will error on an unknown marker.
"""

from pathlib import Path

import pytest

# Path constants — single source of truth for the test directory structure.
TESTS_ROOT_DIR = Path(__file__).parent
TEST_DATA_DIR = TESTS_ROOT_DIR / "test_data"

# The container fixtures (PD-16): they start only the containers a test's markers need.
pytest_plugins = ["rdf_persistence.testkit.containers.fixtures"]

# Map a directory to every marker it implies (PD-16). The first row whose
# directory occurs in the test path wins, so a row never needs to exclude another.
_MARKERS_BY_DIR = {
    "/unit/": ("unit",),
    "/feature/": ("feature",),
    "/integration/store/": ("integration", "store"),
    "/integration/api/": ("integration", "store"),
    "/integration/tenancy/": ("integration", "store", "files"),
    "/integration/files/": ("integration", "files"),
    "/integration/identity/": ("integration", "identity"),
    "/e2e/": ("e2e", "store", "files", "identity"),
}


def markers_for_path(path: str) -> tuple[str, ...]:
    """Return every marker implied by the directory a test file lives in.

    Args:
        path: The test file's path.

    Returns:
        The markers of the matching row of the path table, or ``()`` if none matches.
    """
    posix = Path(path).as_posix()
    for directory, markers in _MARKERS_BY_DIR.items():
        if directory in posix:
            return markers
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

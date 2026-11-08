"""The path table of ``tests/conftest.py`` stamps every marker of a directory's row (PD-16)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import conftest
from tests.conftest import TESTS_ROOT_DIR, markers_for_path, pytest_collection_modifyitems

ROOT = TESTS_ROOT_DIR.as_posix()


@pytest.mark.parametrize(
    ("directory", "expected"),
    [
        ("unit", {"unit"}),
        ("feature", {"feature"}),
        ("integration/store", {"integration", "store"}),
        ("integration/api", {"integration", "store"}),
        ("integration/tenancy", {"integration", "store", "files"}),
        ("integration/files", {"integration", "files"}),
        ("integration/identity", {"integration", "identity"}),
        ("e2e", {"e2e", "store", "files", "identity"}),
        ("perf", {"perf"}),
    ],
)
def test_directory_row_gives_every_marker(directory: str, expected: set[str]) -> None:
    assert set(markers_for_path(f"{ROOT}/{directory}/test_x.py")) == expected


def test_path_outside_the_table_gets_no_marker() -> None:
    assert markers_for_path(f"{ROOT}/test_x.py") == ()


def test_checkout_under_a_directory_named_like_a_row_is_not_matched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(conftest, "TESTS_ROOT_DIR", Path("/work/unit/repo/tests"))
    assert markers_for_path("/work/unit/repo/tests/test_x.py") == ()
    assert set(markers_for_path("/work/unit/repo/tests/integration/files/test_x.py")) == {
        "integration",
        "files",
    }


def test_path_outside_the_tests_tree_gets_no_marker() -> None:
    assert markers_for_path("/elsewhere/unit/test_x.py") == ()


def test_hook_adds_each_marker_to_the_item() -> None:
    added: list[str] = []
    item = SimpleNamespace(
        fspath=f"{ROOT}/integration/tenancy/test_x.py",
        add_marker=lambda marker: added.append(marker.name),
    )
    pytest_collection_modifyitems([item])
    assert added == ["integration", "store", "files"]

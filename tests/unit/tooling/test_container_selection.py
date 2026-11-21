"""The generator's test pyramid is stamped by folder like the library's (generator-package PD-9)."""

import pytest

from tests.conftest import TESTS_ROOT_DIR, markers_for_path

ROOT = TESTS_ROOT_DIR.as_posix()


@pytest.mark.parametrize(
    ("directory", "expected"),
    [
        ("generator/unit", {"unit"}),
        ("generator/feature", {"feature"}),
        ("generator/integration", {"integration"}),
        ("generator/e2e", {"e2e", "store", "files", "identity"}),
    ],
)
def test_a_generator_folder_stamps_its_test_type_and_containers(
    directory: str, expected: set[str]
) -> None:
    """TC-25: ``integration`` has no container marker; ``e2e`` has the three of ``install_service``."""
    assert set(markers_for_path(f"{ROOT}/{directory}/x.py")) == expected, (
        f"{directory} stamps other markers than its row"
    )

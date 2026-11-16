"""Every developer and CI lane leaves the quarantined tests out (rule 14, PD-9)."""

import re

import pytest

from tests.conftest import TESTS_ROOT_DIR

MAKEFILE = (TESTS_ROOT_DIR.parent / "Makefile").read_text(encoding="utf-8")
SELECTION = re.compile(r'-m "([^"]+)"')
MAX_RECIPE_LINES = 15
LANES = [
    "test",
    "test-unit",
    "test-feature",
    "test-fast",
    "test-changed",
    "coverage-report",
    "profile-tests",
    "test-containers",
    "test-e2e",
]


def recipe_of(target: str) -> list[str]:
    """The tab-indented lines under ``target:``, up to the next blank line."""
    lines = MAKEFILE.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{target}:"))
    recipe = []
    for line in lines[start + 1 :]:
        if not line.startswith("\t"):
            break
        recipe.append(line)
    return recipe


@pytest.mark.parametrize("lane", LANES)
def test_lane_selection_excludes_quarantine(lane: str) -> None:
    selections = SELECTION.findall("\n".join(recipe_of(lane)))
    assert selections, f"{lane} has no -m selection"
    for selection in selections:
        assert selection.endswith(" and not quarantine"), f"{lane}: {selection!r}"
        if " or " in selection:
            assert selection.startswith("("), f"{lane} needs parentheses: {selection!r}"


@pytest.mark.parametrize("target", [*LANES, "mutation"])
def test_recipe_stays_within_the_line_budget(target: str) -> None:
    assert len(recipe_of(target)) <= MAX_RECIPE_LINES, f"{target} recipe is too long"


def test_quarantine_marker_is_registered() -> None:
    ini = (TESTS_ROOT_DIR.parent / "pytest.ini").read_text(encoding="utf-8")
    assert "quarantine:" in ini, "pytest.ini does not register the quarantine marker"

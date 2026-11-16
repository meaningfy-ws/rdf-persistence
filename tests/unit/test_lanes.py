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
    "test-perf",
]
PARALLEL_LANES = ["test", "test-unit", "test-feature", "test-fast", "profile-tests"]
WORKERS = re.compile(r"-n \S+")
VARIABLE = re.compile(r"^(\w+)\s*\??=\s*(.*)$", re.MULTILINE)
REFERENCE = re.compile(r"\$\((\w+)\)")
DIST_LOADGROUP = "--dist loadgroup"


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


def expanded(text: str) -> str:
    """``text`` with each ``$(NAME)`` that the Makefile defines as a plain variable replaced."""
    variables = dict(VARIABLE.findall(MAKEFILE))
    previous = None
    while text != previous:
        previous = text
        text = REFERENCE.sub(lambda m: variables.get(m.group(1), m.group(0)), text)
    return text


def test_expanded_replaces_a_defined_variable_and_leaves_an_unknown_one() -> None:
    assert expanded("-m $(NOT_QUARANTINE) $(UNKNOWN_NAME)").startswith("-m and not quarantine"), (
        "a defined variable is replaced"
    )
    assert expanded("$(UNKNOWN_NAME)") == "$(UNKNOWN_NAME)", "an unknown variable is left alone"


@pytest.mark.parametrize("lane", LANES)
def test_lane_selection_excludes_quarantine(lane: str) -> None:
    selections = SELECTION.findall(expanded("\n".join(recipe_of(lane))))
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


@pytest.mark.parametrize("lane", PARALLEL_LANES)
def test_every_parallel_lane_distributes_by_group(lane: str) -> None:
    recipe = "\n".join(recipe_of(lane))

    assert WORKERS.search(expanded(recipe)), f"{lane} no longer runs in parallel: update the list"
    assert DIST_LOADGROUP in expanded(recipe), f"{lane}: -n without --dist loadgroup"
    assert "$(PARALLEL)" in recipe, f"{lane} spells the worker flags out instead of $(PARALLEL)"
    assert not WORKERS.search(recipe), f"{lane} carries its own -n"


def test_a_lane_that_names_workers_is_in_the_parallel_list() -> None:
    named = [
        lane
        for lane in LANES
        if lane != "test-changed" and WORKERS.search(expanded("\n".join(recipe_of(lane))))
    ]

    assert sorted(named) == sorted(PARALLEL_LANES), "a lane runs in parallel but is not checked"


def test_the_perf_lane_selects_perf_tests_not_in_quarantine() -> None:
    selections = SELECTION.findall(expanded("\n".join(recipe_of("test-perf"))))

    assert selections == ["perf and not quarantine"], "test-perf must select perf, not quarantine"


def test_the_refresh_map_target_runs_the_refresher() -> None:
    assert any("tests.audit.refresh_map" in line for line in recipe_of("refresh-map")), (
        "make refresh-map must run tests/audit/refresh_map.py"
    )

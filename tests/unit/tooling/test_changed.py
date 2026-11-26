"""The changed-files mapper picks the test folders of a change (test-lanes PD-1 to PD-5)."""

from collections.abc import Callable
from pathlib import Path

import pytest

from rdf_persistence.testkit import changed_tests
from rdf_persistence.testkit.generated.rp_testkit import ChangedSelection
from tests import changed
from tests.changed import LAYOUT, OUTSIDE_THEMES, THEMES

REPO = Path(__file__).resolve().parents[3]
CONTAINER_TEST = "tests/integration/api/test_routes.py"
PACKAGE_TESTS = ["tests/unit/package/"]
ROOT_FILE = "tests/unit/test_root_level.py"  # none is left in tests/unit/; a future one
OTHER_ROOT_FILE = "tests/unit/test_other_root_level.py"
LOADGROUP = ["--dist", "loadgroup"]
# The shared arguments of design PD-5, spelled out here so a drift in the module shows.
IGNORES = [
    "--ignore=tests/integration",
    "--ignore=tests/e2e",
    "--ignore=tests/perf",
    "--ignore=tests/generator/e2e",
]
MARKERS = ["-m", "(unit or feature) and not quarantine"]
SEED_HINT = "no test selection data in this worktree: the lead runs make test-seed"
CORE_FILE = "rdf_persistence/core/domain/sparql.py"
SHARED = "shared test infrastructure or schema"


def _folder_run(paths, workers):
    """F of PD-5: the selected paths, the shared arguments, the workers."""
    return [*paths, *IGNORES, *MARKERS, "-n", str(workers), *LOADGROUP]


def _testmon_run(workers=4, generator=True):
    """T of PD-5."""
    folders = ["tests/unit", "tests/feature", *(["tests/generator"] if generator else [])]
    return [
        *folders,
        *IGNORES,
        *MARKERS,
        "--testmon",
        "--testmon-nocollect",
        "--testmon-forceselect",
        "-n",
        str(workers),
        *LOADGROUP,
    ]


def plan(changed_paths, has_data, existing, workers=4):
    """The planner of the testkit with this repository's classifier and layout."""
    return changed_tests.plan(changed_paths, has_data, existing, workers, changed, LAYOUT)


def _arguments(paths, workers=4):
    """The argument lists of the invocations planned for `paths` without selection data."""
    return [i.arguments for i in plan(paths, False, lambda _: True, workers).invocations]


SELECTS = [
    (1, "openspec/changes/x/design.md", []),
    (1, ".claude/settings.json", []),
    (1, "temp/notes.txt", []),
    (1, "README.md", []),
    (2, "docs/modules/ROOT/pages/index.adoc", ["tests/unit/tooling/test_check_docs.py"]),
    (7, ROOT_FILE, [ROOT_FILE]),
    (8, "tests/unit/tooling/test_markers.py", ["tests/unit/tooling/"]),
    (8, "tests/unit/package/test_public_api.py", ["tests/unit/package/"]),
    (8, "tests/unit/core/test_exceptions.py", ["tests/unit/core/"]),
    (8, "tests/unit/api/helpers.py", ["tests/unit/api/"]),
    (8, "tests/unit/api/test_router.py", ["tests/unit/api/"]),
    (9, "tests/feature/steps/test_steps.py", ["tests/feature/"]),
    (10, "rdf_persistence/api/services/example.py", ["tests/unit/api/"]),
    (10, "rdf_persistence/iris/domain/layout.py", ["tests/unit/iris/"]),
    (10, "rdf_persistence/testkit/containers/fuseki.py", ["tests/unit/testkit/"]),
    (11, "rdf_persistence/__init__.py", PACKAGE_TESTS),
]
FALLS_BACK = [
    (3, "pytest.ini"),
    (3, "pyproject.toml"),
    (3, "uv.lock"),
    (3, "Makefile"),
    (3, ".coveragerc"),
    (3, "tests/conftest.py"),
    (3, "tests/toy_service.py"),
    (3, "tests/changed.py"),
    (3, "tests/fixtures/library/pyproject.toml"),
    (3, "tests/unit/__init__.py"),
    (3, "rdf_persistence/model/library.yaml"),
    (5, "tests/e2e/world.py"),
    (5, "tests/integration/conftest.py"),
    (12, ".github/workflows/ci.yml"),
    (12, ".importlinter"),
    (12, "mypy.ini"),
    (12, "tests/unit/conftest.py"),
    (12, "tests/unit/helpers.py"),
]
NAMED_NOT_RUN = [
    (4, CONTAINER_TEST, "make test-containers"),
    (4, "tests/e2e/test_flow.py", "make test-containers"),
    (6, "tests/perf/test_budget.py", "make test-perf"),
]


def select(paths, existing):
    """The testkit's selection with this repository's classifier."""
    return changed_tests.select(paths, existing, changed)


def _select(paths: list[str], existing: Callable[[str], bool] = lambda _: True) -> ChangedSelection:
    return select(paths, existing)


def test_the_rows_cover_the_twelve_mapping_rules():
    rules = {row[0] for table in (SELECTS, FALLS_BACK, NAMED_NOT_RUN) for row in table}

    assert rules == set(range(1, 13)), "a mapping rule of the design has no row"


@pytest.mark.parametrize(
    "changed",
    [
        "rdf_persistence_generation/manifest.py",
        "rdf_persistence_generation/extensions/shacl.py",
        "tests/generator/unit/test_manifest.py",
    ],
)
def test_a_changed_generator_file_selects_the_generator_tests(changed):
    """TC-26: the generator's code and its tests map to ``tests/generator/``, not to a fallback."""
    selection = _select([changed])

    assert selection.paths == ["tests/generator/"], f"{changed} must select the generator pyramid"
    assert not selection.fallback_reasons, f"{changed} must not fall back"


def test_the_folders_of_the_package_are_the_themes_and_the_testkit():
    """Every package folder is a theme the mapper knows or the testkit (PD-11, TC-70)."""
    folders = {p.parent.name for p in (REPO / "rdf_persistence").glob("*/__init__.py")}

    assert folders == OUTSIDE_THEMES | THEMES, "a folder is neither a theme nor the testkit"
    assert not OUTSIDE_THEMES & THEMES, "a name cannot be the testkit and a theme"


def test_the_themes_are_the_thirteen_of_the_design():
    """thematic-structure PD-1: the themes of the module map."""
    expected = {
        "core",
        "iris",
        "schema",
        "files",
        "provenance",
        "persistence",
        "migrations",
        "access",
        "tenancy",
        "events",
        "collaboration",
        "messaging",
        "api",
    }

    assert set(THEMES) == expected, "the set of themes"


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        ("rdf_persistence/tenancy/services/sweep.py", ["tests/unit/tenancy/"]),
        ("rdf_persistence/api/entrypoints/router.py", ["tests/unit/api/"]),
        ("rdf_persistence/persistence/adapters/fuseki.py", ["tests/unit/persistence/"]),
        ("rdf_persistence/files/__init__.py", ["tests/unit/files/"]),
        ("tests/unit/tenancy/test_sweep.py", ["tests/unit/tenancy/"]),
    ],
)
def test_a_changed_theme_file_selects_the_tests_of_its_theme(changed, expected):
    """TC-22: ``rdf_persistence/<theme>/<layer>/x.py`` maps to ``tests/unit/<theme>/``, no fallback."""
    selection = _select([changed])

    assert selection.paths == expected, f"{changed} must select its theme's folder"
    assert not selection.fallback_reasons, f"{changed} must not fall back"


def test_a_changed_theme_file_whose_test_folder_does_not_exist_falls_back_with_a_reason():
    """A theme folder that is gone or never made must not leave an empty selection that exits 0."""
    selection = select(["rdf_persistence/tenancy/services/sweep.py"], lambda path: False)

    assert selection.paths == [], "nothing to run by path"
    assert "rdf_persistence/tenancy/services/sweep.py" in selection.fallback_reasons[0]
    assert "tests/unit/tenancy/" in selection.fallback_reasons[0], "the reason names the folder"
    assert "make test-fast" in selection.fallback_reasons[0], "the reason names the lane"


def test_two_changed_themes_select_both_folders():
    selection = _select(
        ["rdf_persistence/tenancy/services/sweep.py", "rdf_persistence/events/adapters/x.py"]
    )

    assert selection.paths == ["tests/unit/events/", "tests/unit/tenancy/"], "both, sorted"


@pytest.mark.parametrize(
    "changed",
    [
        "rdf_persistence/core/domain/sparql.py",
        "rdf_persistence/core/services/telemetry.py",
        "rdf_persistence/core/__init__.py",
    ],
)
def test_a_changed_core_file_falls_back_to_the_fast_suite(changed):
    """TC-23: ``core`` is imported by every theme, so a change to it runs ``make test-fast``."""
    selection = _select([changed])

    assert selection.paths == [], "core selects no folder of its own"
    assert changed in selection.fallback_reasons[0], "the reason names the path"
    assert "make test-fast" in selection.fallback_reasons[0], "the reason names the lane"


def test_the_theme_rule_and_the_generator_rule_are_kept():
    """A theme's folder and the generator's folder both map, side by side (PD-11)."""
    selection = _select(
        ["rdf_persistence/api/services/example.py", "rdf_persistence_generation/manifest.py"]
    )

    assert selection.paths == ["tests/generator/", "tests/unit/api/"], "theme and generator"


@pytest.mark.parametrize(
    "changed",
    [
        "rdf_persistence/domain/example.py",
        "rdf_persistence/adapters/example.py",
        "rdf_persistence/__init__.py",
    ],
)
def test_a_change_outside_a_theme_and_the_testkit_selects_the_package_tests_only(changed):
    """8.1: the two shims are gone, so a folder that is no theme has no tests of its own (PD-11)."""
    selection = _select([changed])

    assert selection.paths == PACKAGE_TESTS, changed
    assert _arguments([changed]) == [_folder_run(PACKAGE_TESTS, 4)], "a folder runs in parallel"
    assert not selection.fallback_reasons, f"{changed} must not fall back"


def test_a_changed_tooling_test_file_selects_the_tooling_folder_in_parallel():
    selection = _select(["tests/unit/tooling/test_markers.py"])

    assert selection.paths == ["tests/unit/tooling/"], "the folder, not the file"
    assert _arguments(["tests/unit/tooling/test_markers.py"]) == [
        _folder_run(("tests/unit/tooling/",), 4)
    ], "a folder runs in parallel"


def test_a_changed_root_level_test_file_selects_that_file_on_one_process():
    selection = _select([ROOT_FILE])

    assert selection.paths == [ROOT_FILE], "that file only"
    assert _arguments([ROOT_FILE]) == [_folder_run((ROOT_FILE,), 0)], "one process"


@pytest.mark.parametrize(("rule", "changed", "expected"), SELECTS)
def test_a_changed_path_selects_what_its_rule_says(rule, changed, expected):
    selection = _select([changed])

    assert selection.paths == expected, f"rule {rule}: {changed}"
    assert not selection.fallback_reasons, f"rule {rule}: {changed} must not fall back"


@pytest.mark.parametrize(("rule", "changed"), FALLS_BACK)
def test_shared_infrastructure_and_unmapped_files_fall_back(rule, changed):
    selection = _select([changed])

    assert selection.fallback_reasons, f"rule {rule}: {changed} must fall back"
    assert changed in selection.fallback_reasons[0], "the reason names the path"


@pytest.mark.parametrize(("rule", "changed", "make_target"), NAMED_NOT_RUN)
def test_container_and_perf_tests_are_named_not_run(rule, changed, make_target):
    selection = _select([changed])

    assert selection.paths == [], f"rule {rule}: nothing runs"
    assert selection.hints == [f"{changed}: run {make_target}"], f"rule {rule}: the hint"


def test_the_worked_example_selects_one_folder_and_hints_at_the_container_test():
    changed = [
        "rdf_persistence/api/services/example.py",
        "tests/unit/api/test_replace_internal_values.py",
        "openspec/changes/x/design.md",
        CONTAINER_TEST,
    ]

    selection = _select(changed)

    assert selection.paths == ["tests/unit/api/"], "one folder, not two"
    assert selection.hints == [f"{CONTAINER_TEST}: run make test-containers"], "the container hint"
    assert _arguments(changed) == [_folder_run(("tests/unit/api/",), 4)], "the arguments"


def test_a_changed_container_test_alone_gives_no_arguments():
    selection = _select([CONTAINER_TEST])

    assert _arguments([CONTAINER_TEST]) == [], "no paths, so no invocation"
    assert selection.hints, "the container test is still named"


def test_a_lone_deleted_test_file_gives_no_arguments():
    selection = _select([ROOT_FILE], existing=lambda _: False)

    assert selection.paths == [], "a deleted file selects nothing"
    assert plan([ROOT_FILE], False, lambda _: False).invocations == [], "no invocation"


def test_nothing_changed_selects_nothing():
    selection = _select([])

    assert selection == ChangedSelection(paths=[], hints=[], fallback_reasons=[]), "an empty one"


def test_a_selected_file_inside_a_selected_folder_is_dropped():
    selection = _select(["rdf_persistence/api/services/a.py", "tests/unit/api/test_a.py"])

    assert selection.paths == ["tests/unit/api/"], "the file lies in the folder"


def test_a_file_outside_the_selected_folder_is_kept_and_paths_are_sorted():
    selection = _select(
        [
            ROOT_FILE,
            "rdf_persistence/api/services/a.py",
            OTHER_ROOT_FILE,
        ]
    )

    assert selection.paths == [
        "tests/unit/api/",
        OTHER_ROOT_FILE,
        ROOT_FILE,
    ], "sorted, the file outside the folder kept"


def test_a_move_between_themes_selects_both_folders():
    selection = _select(
        ["rdf_persistence/api/services/a.py", "rdf_persistence/persistence/adapters/a.py"]
    )

    assert selection.paths == ["tests/unit/api/", "tests/unit/persistence/"], "both folders"


def test_fallback_wins_over_selected_paths():
    selection = _select(["rdf_persistence/api/services/a.py", "Makefile", "tests/conftest.py"])

    assert len(selection.fallback_reasons) == 2, "one reason per fallback path"


def _missing_library_app(path: str) -> bool:
    return path != "tests/library_app.py"  # absent on this branch, as on review-floors-s1


# (changed, has_data, existing, invocations, hints, fallback reasons): the worked examples of PD-5.
WORKED_EXAMPLES = [
    pytest.param([CORE_FILE], True, None, [_testmon_run()], [], [], id="1-core-with-data"),
    pytest.param(
        [CORE_FILE],
        False,
        None,
        [],
        [SEED_HINT],
        [f"{CORE_FILE}: core is imported by every theme; run make test-fast"],
        id="2-core-without-data",
    ),
    pytest.param(
        ["tests/library_app.py", "tests/e2e/world.py"],
        True,
        _missing_library_app,
        [_testmon_run()],
        [],
        [],
        id="3-helpers-with-data",
    ),
    pytest.param(
        ["tests/library_app.py", "tests/e2e/world.py"],
        False,
        _missing_library_app,
        [],
        [SEED_HINT],
        [
            f"tests/library_app.py: {SHARED}",
            "tests/e2e/world.py: helper imported by unit tests",
        ],
        id="4-helpers-without-data",
    ),
    pytest.param(
        ["rdf_persistence/persistence/services/session.py", "docs/x.adoc"],
        True,
        None,
        [
            _testmon_run(),
            _folder_run(("tests/unit/tooling/test_check_docs.py",), 0),
        ],
        [],
        [],
        id="5-code-and-docs-with-data",
    ),
    pytest.param(
        ["rdf_persistence_generation/lock_step.py"],
        True,
        None,
        [_testmon_run(generator=False), _folder_run(("tests/generator/",), 4)],
        [],
        [],
        id="6-generator-with-data",
    ),
    pytest.param(
        ["tests/fixtures/library/domain/generated/core.py"],
        True,
        None,
        [],
        [],
        [f"tests/fixtures/library/domain/generated/core.py: {SHARED}"],
        id="7-fixture-with-data",
    ),
    pytest.param(
        ["rdf_persistence/model/core.yaml"],
        True,
        None,
        [],
        [],
        [f"rdf_persistence/model/core.yaml: {SHARED}"],
        id="8-model-yaml-with-data",
    ),
    pytest.param(["uv.lock"], True, None, [], [], [f"uv.lock: {SHARED}"], id="9-lock-with-data"),
    pytest.param(
        ["tests/integration/store/test_fuseki_store.py"],
        True,
        None,
        [],
        ["tests/integration/store/test_fuseki_store.py: run make test-containers"],
        [],
        id="10-container-test-with-data",
    ),
    pytest.param([], True, None, [], [], [], id="11-nothing-with-data"),
    pytest.param([], False, None, [], [], [], id="11-nothing-without-data"),
]


@pytest.mark.parametrize(
    ("changed_paths", "has_data", "existing", "invocations", "hints", "reasons"), WORKED_EXAMPLES
)
def test_the_plan_of_a_worked_example(
    changed_paths, has_data, existing, invocations, hints, reasons
):
    got = plan(changed_paths, has_data, existing or (lambda _: True))

    assert [i.arguments for i in got.invocations] == invocations, "the invocations, in order"
    assert got.hints == hints, "the hints"
    assert got.fallback_reasons == reasons, "the fallback reasons"


@pytest.mark.parametrize("has_data", [True, False])
def test_a_plan_called_twice_is_the_same(has_data):
    paths = ["rdf_persistence/api/services/a.py", "docs/x.adoc", "rdf_persistence_generation/m.py"]

    assert plan(paths, has_data, lambda _: True) == plan(paths, has_data, lambda _: True), (
        "no state between calls"
    )


def test_the_workers_of_the_plan_are_a_parameter():
    got = plan(["rdf_persistence/api/services/a.py"], True, lambda _: True, 7)

    assert got.invocations[0].arguments == _testmon_run(workers=7), "T takes the count"


def test_without_data_a_folder_runs_on_the_workers_and_a_file_on_none():
    folder = _arguments(["rdf_persistence/api/services/a.py"], 6)
    file = _arguments([ROOT_FILE], 6)

    assert folder == [_folder_run(("tests/unit/api/",), 6)], "a folder takes the count"
    assert file == [_folder_run((ROOT_FILE,), 0)], "files only run on one process"

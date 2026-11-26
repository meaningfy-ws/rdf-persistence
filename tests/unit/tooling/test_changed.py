"""The changed-files mapper picks the test folders of a change (test-lanes PD-1 to PD-5)."""

import subprocess
import sys
import threading
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path

import pytest

from tests import changed
from tests.changed import (
    FALLBACK_EXIT,
    OUTSIDE_THEMES,
    THEMES,
    GitError,
    Selection,
    changed_files,
    plan,
    select,
)
from tests.testmon_data import DAMAGED_MESSAGE, PACKAGES_MESSAGE, Outcome, worktree_lock

REPO = Path(__file__).resolve().parents[3]
CONTAINER_TEST = "tests/integration/api/test_routes.py"
PACKAGE_TESTS = ("tests/unit/package/",)
ROOT_FILE = "tests/unit/test_root_level.py"  # none is left in tests/unit/; a future one
OTHER_ROOT_FILE = "tests/unit/test_other_root_level.py"
LOADGROUP = ("--dist", "loadgroup")
# The shared arguments of design PD-5, spelled out here so a drift in the module shows.
IGNORES = (
    "--ignore=tests/integration",
    "--ignore=tests/e2e",
    "--ignore=tests/perf",
    "--ignore=tests/generator/e2e",
)
MARKERS = ("-m", "(unit or feature) and not quarantine")
SEED_HINT = "no test selection data in this worktree: the lead runs make test-seed"
CORE_FILE = "rdf_persistence/core/domain/sparql.py"
SHARED = "shared test infrastructure or schema"


def _folder_run(paths, workers):
    """F of PD-5: the selected paths, the shared arguments, the workers."""
    return (*paths, *IGNORES, *MARKERS, "-n", str(workers), *LOADGROUP)


def _testmon_run(workers=4, generator=True):
    """T of PD-5."""
    folders = ("tests/unit", "tests/feature", *(("tests/generator",) if generator else ()))
    return (
        *folders,
        *IGNORES,
        *MARKERS,
        "--testmon",
        "--testmon-nocollect",
        "--testmon-forceselect",
        "-n",
        str(workers),
        *LOADGROUP,
    )


def _arguments(paths, workers=4):
    """The argument lists of the invocations planned for `paths` without selection data."""
    return [i.arguments for i in plan(paths, False, lambda _: True, workers).invocations]


SELECTS = [
    (1, "openspec/changes/x/design.md", ()),
    (1, ".claude/settings.json", ()),
    (1, "temp/notes.txt", ()),
    (1, "README.md", ()),
    (2, "docs/modules/ROOT/pages/index.adoc", ("tests/unit/tooling/test_check_docs.py",)),
    (7, ROOT_FILE, (ROOT_FILE,)),
    (8, "tests/unit/tooling/test_markers.py", ("tests/unit/tooling/",)),
    (8, "tests/unit/package/test_public_api.py", ("tests/unit/package/",)),
    (8, "tests/unit/core/test_exceptions.py", ("tests/unit/core/",)),
    (8, "tests/unit/api/helpers.py", ("tests/unit/api/",)),
    (8, "tests/unit/api/test_router.py", ("tests/unit/api/",)),
    (9, "tests/feature/steps/test_steps.py", ("tests/feature/",)),
    (10, "rdf_persistence/api/services/example.py", ("tests/unit/api/",)),
    (10, "rdf_persistence/iris/domain/layout.py", ("tests/unit/iris/",)),
    (10, "rdf_persistence/testkit/containers/fuseki.py", ("tests/unit/testkit/",)),
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


def _select(paths: list[str], existing: Callable[[str], bool] = lambda _: True) -> Selection:
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

    assert selection.paths == ("tests/generator/",), f"{changed} must select the generator pyramid"
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
        ("rdf_persistence/tenancy/services/sweep.py", ("tests/unit/tenancy/",)),
        ("rdf_persistence/api/entrypoints/router.py", ("tests/unit/api/",)),
        ("rdf_persistence/persistence/adapters/fuseki.py", ("tests/unit/persistence/",)),
        ("rdf_persistence/files/__init__.py", ("tests/unit/files/",)),
        ("tests/unit/tenancy/test_sweep.py", ("tests/unit/tenancy/",)),
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

    assert selection.paths == (), "nothing to run by path"
    assert "rdf_persistence/tenancy/services/sweep.py" in selection.fallback_reasons[0]
    assert "tests/unit/tenancy/" in selection.fallback_reasons[0], "the reason names the folder"
    assert "make test-fast" in selection.fallback_reasons[0], "the reason names the lane"


def test_two_changed_themes_select_both_folders():
    selection = _select(
        ["rdf_persistence/tenancy/services/sweep.py", "rdf_persistence/events/adapters/x.py"]
    )

    assert selection.paths == ("tests/unit/events/", "tests/unit/tenancy/"), "both, sorted"


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

    assert selection.paths == (), "core selects no folder of its own"
    assert changed in selection.fallback_reasons[0], "the reason names the path"
    assert "make test-fast" in selection.fallback_reasons[0], "the reason names the lane"


def test_main_exits_with_the_fallback_status_when_core_changed(monkeypatch, capsys):
    """TC-23 through ``main``: exit 75, which the Makefile turns into ``make test-fast``."""
    got, out = _run_main(monkeypatch, capsys, ["rdf_persistence/core/domain/sparql.py"])

    assert got == 75, "exit status for a change in core"
    assert out.out == "", "nothing is printed on stdout"
    assert "rdf_persistence/core/domain/sparql.py" in out.err, "stderr names the file"


def test_the_theme_rule_and_the_generator_rule_are_kept():
    """A theme's folder and the generator's folder both map, side by side (PD-11)."""
    selection = _select(
        ["rdf_persistence/api/services/example.py", "rdf_persistence_generation/manifest.py"]
    )

    assert selection.paths == ("tests/generator/", "tests/unit/api/"), "theme and generator"


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

    assert selection.paths == ("tests/unit/tooling/",), "the folder, not the file"
    assert _arguments(["tests/unit/tooling/test_markers.py"]) == [
        _folder_run(("tests/unit/tooling/",), 4)
    ], "a folder runs in parallel"


def test_a_changed_root_level_test_file_selects_that_file_on_one_process():
    selection = _select([ROOT_FILE])

    assert selection.paths == (ROOT_FILE,), "that file only"
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

    assert selection.paths == (), f"rule {rule}: nothing runs"
    assert selection.hints == (f"{changed}: run {make_target}",), f"rule {rule}: the hint"


def test_the_worked_example_selects_one_folder_and_hints_at_the_container_test():
    changed = [
        "rdf_persistence/api/services/example.py",
        "tests/unit/api/test_replace_internal_values.py",
        "openspec/changes/x/design.md",
        CONTAINER_TEST,
    ]

    selection = _select(changed)

    assert selection.paths == ("tests/unit/api/",), "one folder, not two"
    assert selection.hints == (f"{CONTAINER_TEST}: run make test-containers",), "the container hint"
    assert _arguments(changed) == [_folder_run(("tests/unit/api/",), 4)], "the arguments"


def test_a_changed_container_test_alone_gives_no_arguments():
    selection = _select([CONTAINER_TEST])

    assert _arguments([CONTAINER_TEST]) == [], "no paths, so no invocation"
    assert selection.hints, "the container test is still named"


def test_a_lone_deleted_test_file_gives_no_arguments():
    selection = _select([ROOT_FILE], existing=lambda _: False)

    assert selection.paths == (), "a deleted file selects nothing"
    assert plan([ROOT_FILE], False, lambda _: False).invocations == (), "no invocation"


def test_nothing_changed_selects_nothing():
    selection = _select([])

    assert selection == Selection(paths=(), hints=(), fallback_reasons=()), "an empty selection"


def test_a_selected_file_inside_a_selected_folder_is_dropped():
    selection = _select(["rdf_persistence/api/services/a.py", "tests/unit/api/test_a.py"])

    assert selection.paths == ("tests/unit/api/",), "the file lies in the folder"


def test_a_file_outside_the_selected_folder_is_kept_and_paths_are_sorted():
    selection = _select(
        [
            ROOT_FILE,
            "rdf_persistence/api/services/a.py",
            OTHER_ROOT_FILE,
        ]
    )

    assert selection.paths == (
        "tests/unit/api/",
        OTHER_ROOT_FILE,
        ROOT_FILE,
    ), "sorted, the file outside the folder kept"


def test_a_move_between_themes_selects_both_folders():
    selection = _select(
        ["rdf_persistence/api/services/a.py", "rdf_persistence/persistence/adapters/a.py"]
    )

    assert selection.paths == ("tests/unit/api/", "tests/unit/persistence/"), "both folders"


def test_fallback_wins_over_selected_paths():
    selection = _select(["rdf_persistence/api/services/a.py", "Makefile", "tests/conftest.py"])

    assert len(selection.fallback_reasons) == 2, "one reason per fallback path"


def _missing_library_app(path: str) -> bool:
    return path != "tests/library_app.py"  # absent on this branch, as on review-floors-s1


# (changed, has_data, existing, invocations, hints, fallback reasons): the worked examples of PD-5.
WORKED_EXAMPLES = [
    pytest.param([CORE_FILE], True, None, [_testmon_run()], (), (), id="1-core-with-data"),
    pytest.param(
        [CORE_FILE],
        False,
        None,
        [],
        (SEED_HINT,),
        (f"{CORE_FILE}: core is imported by every theme; run make test-fast",),
        id="2-core-without-data",
    ),
    pytest.param(
        ["tests/library_app.py", "tests/e2e/world.py"],
        True,
        _missing_library_app,
        [_testmon_run()],
        (),
        (),
        id="3-helpers-with-data",
    ),
    pytest.param(
        ["tests/library_app.py", "tests/e2e/world.py"],
        False,
        _missing_library_app,
        [],
        (SEED_HINT,),
        (
            f"tests/library_app.py: {SHARED}",
            "tests/e2e/world.py: helper imported by unit tests",
        ),
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
        (),
        (),
        id="5-code-and-docs-with-data",
    ),
    pytest.param(
        ["rdf_persistence_generation/lock_step.py"],
        True,
        None,
        [_testmon_run(generator=False), _folder_run(("tests/generator/",), 4)],
        (),
        (),
        id="6-generator-with-data",
    ),
    pytest.param(
        ["tests/fixtures/library/domain/generated/core.py"],
        True,
        None,
        [],
        (),
        (f"tests/fixtures/library/domain/generated/core.py: {SHARED}",),
        id="7-fixture-with-data",
    ),
    pytest.param(
        ["rdf_persistence/model/core.yaml"],
        True,
        None,
        [],
        (),
        (f"rdf_persistence/model/core.yaml: {SHARED}",),
        id="8-model-yaml-with-data",
    ),
    pytest.param(["uv.lock"], True, None, [], (), (f"uv.lock: {SHARED}",), id="9-lock-with-data"),
    pytest.param(
        ["tests/integration/store/test_fuseki_store.py"],
        True,
        None,
        [],
        ("tests/integration/store/test_fuseki_store.py: run make test-containers",),
        (),
        id="10-container-test-with-data",
    ),
    pytest.param([], True, None, [], (), (), id="11-nothing-with-data"),
    pytest.param([], False, None, [], (), (), id="11-nothing-without-data"),
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


def _git(repo: Path, *args: str) -> None:
    cmd = ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args]
    subprocess.run(cmd, cwd=repo, check=True, capture_output=True)


def _write(repo: Path, rel: str, text: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text)


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)


@pytest.fixture
def feature_repo(tmp_path, monkeypatch):
    """A repo whose develop holds four files and whose feature branch has one commit on it."""
    _git(tmp_path, "init", "-b", "develop")
    for name in ("kept.py", "edited.py", "deleted.py", "moved.py"):
        _write(tmp_path, name, name)
    _commit_all(tmp_path, "base")
    _git(tmp_path, "checkout", "-b", "feature/x")
    _write(tmp_path, "committed.py", "c")
    _commit_all(tmp_path, "feature")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_the_listing_holds_committed_uncommitted_untracked_deleted_and_both_sides_of_a_rename(
    feature_repo,
):
    _write(feature_repo, "edited.py", "changed")
    _write(feature_repo, "untracked.py", "u")
    (feature_repo / "deleted.py").unlink()
    (feature_repo / "moved.py").rename(feature_repo / "moved_to.py")

    listed = changed_files("develop")

    assert sorted(listed) == [
        "committed.py",
        "deleted.py",
        "edited.py",
        "moved.py",
        "moved_to.py",
        "untracked.py",
    ], "committed, uncommitted, untracked, deleted and both sides of the rename"


def test_the_listing_is_empty_on_the_base_branch_with_a_clean_tree(feature_repo):
    _git(feature_repo, "checkout", "develop")

    assert changed_files("develop") == [], "nothing differs from the base"


def test_an_unknown_base_is_a_git_error_that_names_it(feature_repo):
    with pytest.raises(GitError, match="nosuchbase"):
        changed_files("nosuchbase")


class Runner:
    """The injected pytest runner: records each argument list, answers the codes it was given."""

    def __init__(self, *codes: int):
        self.codes = list(codes)
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, arguments):
        self.calls.append(tuple(arguments))
        return self.codes.pop(0) if self.codes else 0


def _no_lock(root):
    return nullcontext()


def _run_main(
    monkeypatch, capsys, listing, runner=None, outcome=Outcome.NO_DATA, lock=_no_lock, env=None
):
    monkeypatch.chdir(REPO)
    monkeypatch.delenv("PYTEST_N", raising=False)
    monkeypatch.delenv("PYTEST_CHANGED_N", raising=False)
    monkeypatch.delenv("BASE", raising=False)  # make test-changed BASE=<branch> exports it
    for name, value in (env or {}).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(changed, "_git", lambda *args: f"{REPO}\n")

    def listed(base):
        if isinstance(listing, Exception):
            raise listing
        return listing

    monkeypatch.setattr(changed, "changed_files", listed)
    code = changed.main(runner or Runner(), lambda root: outcome, lock)
    return code, capsys.readouterr()


@pytest.mark.parametrize(
    ("listing", "code", "stdout_empty", "stderr_part"),
    [
        (["openspec/changes/x/design.md"], 0, True, "nothing to run against develop"),
        (["Makefile"], 75, True, "Makefile"),
        (GitError("the base is missing"), 75, True, "the base is missing"),
        (["tests/unit/tooling/test_markers.py"], 0, True, ""),
    ],
)
def test_main_exits_with_the_status_its_listing_calls_for(
    monkeypatch, capsys, listing, code, stdout_empty, stderr_part
):
    got, out = _run_main(monkeypatch, capsys, listing)

    assert got == code, f"exit status for {listing!r}"
    assert (out.out == "") is stdout_empty, f"stdout for {listing!r}: {out.out!r}"
    assert stderr_part in out.err, f"stderr for {listing!r}: {out.err!r}"


VISIBLE = "rdf_persistence/iris/domain/layout.py"  # testmon-visible: T with data
FOLDER_ONLY = "docs/modules/ROOT/pages/index.adoc"  # a folder rule: F only
TWO_RUNS = [VISIBLE, FOLDER_ONLY]


def test_the_fallback_exit_is_75():
    assert FALLBACK_EXIT == 75, "75 is the Makefile's signal to run make test-fast"


@pytest.mark.parametrize(
    ("pytest_exit", "expected"),
    [(0, 0), (1, 1), (2, 2), (3, 2), (4, 4), (5, 0), (70, 1), (-9, 1)],
)
def test_main_maps_the_exit_status_of_pytest(monkeypatch, capsys, pytest_exit, expected):
    """PD-4: 5 (nothing collected) is a pass, 3 (internal error) becomes 2, 75 stays the fallback's."""
    runner = Runner(pytest_exit)

    got, _ = _run_main(monkeypatch, capsys, [FOLDER_ONLY], runner)

    assert got == expected, f"pytest exit {pytest_exit}"
    assert len(runner.calls) == 1, "the one planned run was made"


def test_main_says_so_when_testmon_selects_no_test(monkeypatch, capsys):
    got, out = _run_main(monkeypatch, capsys, [VISIBLE], Runner(5), Outcome.SOUND)

    assert got == 0, "no test selected is a pass"
    assert "testmon selected no test" in out.err, "and it is said"


def test_main_stops_at_the_first_failing_invocation(monkeypatch, capsys):
    runner = Runner(1, 0)

    got, _ = _run_main(monkeypatch, capsys, TWO_RUNS, runner, Outcome.SOUND)

    assert got == 1, "the failure of the first run is the status"
    assert len(runner.calls) == 1, "the second run is not made"


def test_main_runs_every_invocation_in_order_when_all_pass(monkeypatch, capsys):
    runner = Runner(0, 0)

    got, _ = _run_main(monkeypatch, capsys, TWO_RUNS, runner, Outcome.SOUND)

    assert got == 0, "all passed"
    assert [("--testmon" in call) for call in runner.calls] == [True, False], "T then F"


def test_main_passes_the_plans_argument_lists_to_the_runner(monkeypatch, capsys):
    runner = Runner()

    _run_main(monkeypatch, capsys, [VISIBLE], runner, Outcome.SOUND)

    assert runner.calls == [_testmon_run()], "T of PD-5 with the default workers"


def test_pytest_changed_n_sets_the_workers_and_pytest_n_is_ignored(monkeypatch, capsys):
    runner = Runner()

    _run_main(
        monkeypatch,
        capsys,
        [VISIBLE],
        runner,
        Outcome.SOUND,
        env={"PYTEST_CHANGED_N": "6", "PYTEST_N": "2"},
    )

    assert runner.calls == [_testmon_run(workers=6)], "PYTEST_CHANGED_N wins, PYTEST_N is ignored"


@pytest.mark.parametrize(
    ("outcome", "message", "seed_hint"),
    [
        (Outcome.SOUND, "", False),
        (Outcome.NO_DATA, "", True),
        (Outcome.DAMAGED, DAMAGED_MESSAGE, True),
        (Outcome.PACKAGES_CHANGED, PACKAGES_MESSAGE, True),
    ],
)
def test_the_selection_data_outcome_decides_the_plan_and_its_message(
    monkeypatch, capsys, outcome, message, seed_hint
):
    runner = Runner()

    _, out = _run_main(monkeypatch, capsys, [VISIBLE], runner, outcome)

    with_data = "--testmon" in runner.calls[0]
    assert with_data is (outcome is Outcome.SOUND), f"testmon is used only on sound data: {outcome}"
    assert message in out.err, f"the message of {outcome} is printed"
    assert (SEED_HINT in out.err) is seed_hint, f"the seed hint for {outcome}"


def test_a_hint_goes_to_stderr_and_is_not_a_fallback(monkeypatch, capsys):
    runner = Runner()

    got, out = _run_main(monkeypatch, capsys, [CONTAINER_TEST], runner, Outcome.SOUND)

    assert got == 0, "a container test only hints"
    assert "make test-containers" in out.err, "the hint is on stderr"
    assert runner.calls == [], "nothing is run"


def test_a_fallback_reason_runs_nothing(monkeypatch, capsys):
    runner = Runner()

    got, _ = _run_main(monkeypatch, capsys, ["Makefile", VISIBLE], runner, Outcome.SOUND)

    assert got == 75, "run make test-fast"
    assert runner.calls == [], "the runner is not called"


def test_a_fallback_still_prints_the_hints_first(monkeypatch, capsys):
    """PD-5: the seed hint comes before the reasons, and the exit stays 75."""
    runner = Runner()

    got, out = _run_main(monkeypatch, capsys, ["Makefile", VISIBLE], runner, Outcome.NO_DATA)

    assert got == 75, "run make test-fast"
    assert SEED_HINT in out.err, "the hint is printed with a fallback"
    assert "Makefile" in out.err, "the reason is printed"
    assert out.err.index(SEED_HINT) < out.err.index("Makefile"), "hints before reasons"
    assert runner.calls == [], "nothing is run"


@pytest.mark.parametrize("value", ["abc", "0", "-1", "2.5", " ", "1e2"])
def test_a_bad_worker_count_is_a_usage_error(monkeypatch, capsys, value):
    """PD-9: before any git call, the message on stderr, exit 2."""
    runner = Runner()
    git_calls: list[tuple[str, ...]] = []
    monkeypatch.setenv("PYTEST_CHANGED_N", value)
    monkeypatch.setattr(changed, "_git", lambda *args: git_calls.append(args) or f"{REPO}\n")

    got = changed.main(runner, lambda root: Outcome.SOUND, _no_lock)

    err = capsys.readouterr().err
    assert got == 2, f"exit status for {value!r}"
    assert f"PYTEST_CHANGED_N must be a positive integer, got '{value}'" in err, "the message"
    assert git_calls == [], "git is not called"
    assert runner.calls == [], "nothing is run"


@pytest.mark.parametrize("value", ["1", "6", "16"])
def test_a_good_worker_count_is_taken(monkeypatch, capsys, value):
    runner = Runner()

    _run_main(
        monkeypatch, capsys, [VISIBLE], runner, Outcome.SOUND, env={"PYTEST_CHANGED_N": value}
    )

    assert runner.calls == [_testmon_run(workers=int(value))], f"{value} workers"


HOLD_EXCLUSIVE = """
import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT)
fcntl.flock(fd, fcntl.LOCK_EX)
print("ready", flush=True)
sys.stdin.read()
"""


def test_main_waits_for_an_exclusive_holder_before_the_testmon_run(monkeypatch, capsys, tmp_path):
    """PD-6: the swap holds the lock exclusive; T runs only once it is gone."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(changed, "_git", lambda *args: f"{tmp_path}\n")
    monkeypatch.setattr(changed, "changed_files", lambda base: [VISIBLE])
    waiting = threading.Event()
    runner = Runner()
    results: list[int] = []

    def shared_and_signalling(root):
        return worktree_lock(root, exclusive=False, on_wait=waiting.set)

    holder = subprocess.Popen(
        [sys.executable, "-c", HOLD_EXCLUSIVE, str(tmp_path / ".testmondata.lock")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    builder = threading.Thread(
        target=lambda: results.append(
            changed.main(runner, lambda root: Outcome.SOUND, shared_and_signalling)
        )
    )
    try:
        assert holder.stdout.readline().strip() == "ready", "the holder has the lock exclusive"
        builder.start()
        assert waiting.wait(timeout=30), "main reports that it waits for the lock"
        assert runner.calls == [], "T is not run while the lock is held exclusive"
        holder.kill()
        holder.wait()
        builder.join(timeout=30)
        assert not builder.is_alive(), "main goes on once the holder is gone"
    finally:
        holder.kill()
        holder.wait()
    assert results == [0], "main finished with its pass"
    assert runner.calls == [_testmon_run()], "T ran after the wait"


def test_the_folder_run_does_not_take_the_lock(monkeypatch, capsys):
    taken: list[Path] = []

    def recording_lock(root):
        taken.append(root)
        return nullcontext()

    _run_main(monkeypatch, capsys, [FOLDER_ONLY], Runner(), Outcome.SOUND, recording_lock)

    assert taken == [], "F reads no selection data"


def test_the_testmon_run_takes_the_lock_of_the_repository_root(monkeypatch, capsys):
    taken: list[Path] = []

    def recording_lock(root):
        taken.append(root)
        return nullcontext()

    _run_main(monkeypatch, capsys, [VISIBLE], Runner(), Outcome.SOUND, recording_lock)

    assert taken == [REPO], "T holds the shared lock of the root"

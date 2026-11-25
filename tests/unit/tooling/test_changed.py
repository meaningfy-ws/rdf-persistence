"""The changed-files mapper picks the test folders of a change (test-lanes PD-1 to PD-5)."""

import subprocess
from collections.abc import Callable
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
    pytest_arguments,
    select,
)

REPO = Path(__file__).resolve().parents[3]
CONTAINER_TEST = "tests/integration/api/test_routes.py"
PACKAGE_TESTS = ("tests/unit/package/",)
ROOT_FILE = "tests/unit/test_root_level.py"  # none is left in tests/unit/; a future one
OTHER_ROOT_FILE = "tests/unit/test_other_root_level.py"
LOADGROUP = ("--dist", "loadgroup")

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
    """TC-23 through ``main``: exit 3, which the Makefile turns into ``make test-fast``."""
    got, out = _run_main(monkeypatch, capsys, ["rdf_persistence/core/domain/sparql.py"])

    assert got == FALLBACK_EXIT, "exit status for a change in core"
    assert out.out == "", "no pytest arguments are printed"
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
    assert pytest_arguments(selection.paths, None) == [
        *PACKAGE_TESTS,
        "-n",
        "auto",
        *LOADGROUP,
    ], "a folder runs in parallel"
    assert not selection.fallback_reasons, f"{changed} must not fall back"


def test_a_changed_tooling_test_file_selects_the_tooling_folder_in_parallel():
    selection = _select(["tests/unit/tooling/test_markers.py"])

    assert selection.paths == ("tests/unit/tooling/",), "the folder, not the file"
    assert pytest_arguments(selection.paths, None) == [
        "tests/unit/tooling/",
        "-n",
        "auto",
        *LOADGROUP,
    ], "a folder runs in parallel"


def test_a_changed_root_level_test_file_selects_that_file_on_one_process():
    selection = _select([ROOT_FILE])

    assert selection.paths == (ROOT_FILE,), "that file only"
    assert pytest_arguments(selection.paths, None) == [ROOT_FILE, "-n", "0", *LOADGROUP], (
        "one process"
    )


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
    assert pytest_arguments(selection.paths, None) == [
        "tests/unit/api/",
        "-n",
        "auto",
        *LOADGROUP,
    ], "the arguments"


def test_a_changed_container_test_alone_gives_no_arguments():
    selection = _select([CONTAINER_TEST])

    assert pytest_arguments(selection.paths, None) == [], "no paths, so no arguments"
    assert selection.hints, "the container test is still named"


def test_a_lone_deleted_test_file_gives_no_arguments():
    selection = _select([ROOT_FILE], existing=lambda _: False)

    assert selection.paths == (), "a deleted file selects nothing"
    assert pytest_arguments(selection.paths, None) == [], "no paths, so no arguments"


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


@pytest.mark.parametrize(
    ("paths", "expected_n"),
    [
        ((ROOT_FILE,), "0"),
        ((OTHER_ROOT_FILE, ROOT_FILE), "0"),
        (("tests/unit/api/",), "auto"),
        (("tests/feature/",), "auto"),
        (("tests/unit/api/", "tests/unit/persistence/"), "auto"),
        (("tests/unit/api/", ROOT_FILE), "auto"),
    ],
)
def test_one_process_is_chosen_for_files_only(paths, expected_n):
    assert pytest_arguments(paths, None) == [*paths, "-n", expected_n, *LOADGROUP], (
        f"workers for {paths}"
    )


def test_pytest_n_overrides_the_choice_of_workers():
    assert pytest_arguments(("tests/unit/api/",), "4") == [
        "tests/unit/api/",
        "-n",
        "4",
        *LOADGROUP,
    ], "PYTEST_N wins"


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


def _run_main(monkeypatch, capsys, listing):
    monkeypatch.chdir(REPO)
    monkeypatch.delenv("PYTEST_N", raising=False)
    monkeypatch.delenv("BASE", raising=False)  # make test-changed BASE=<branch> exports it
    monkeypatch.setattr(changed, "_git", lambda *args: f"{REPO}\n")

    def listed(base):
        if isinstance(listing, Exception):
            raise listing
        return listing

    monkeypatch.setattr(changed, "changed_files", listed)
    code = changed.main()
    return code, capsys.readouterr()


@pytest.mark.parametrize(
    ("listing", "code", "stdout_empty", "stderr_part"),
    [
        (["openspec/changes/x/design.md"], 0, True, "nothing to run against develop"),
        (["Makefile"], 3, True, "Makefile"),
        (GitError("the base is missing"), 3, True, "the base is missing"),
        (["tests/unit/tooling/test_markers.py"], 0, False, ""),
    ],
)
def test_main_exits_with_the_status_its_listing_calls_for(
    monkeypatch, capsys, listing, code, stdout_empty, stderr_part
):
    got, out = _run_main(monkeypatch, capsys, listing)

    assert got == code, f"exit status for {listing!r}"
    assert (out.out == "") is stdout_empty, f"stdout for {listing!r}: {out.out!r}"
    assert stderr_part in out.err, f"stderr for {listing!r}: {out.err!r}"

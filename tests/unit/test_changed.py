"""The changed-files mapper picks the test folders of a change (test-lanes PD-1 to PD-5)."""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from tests import changed
from tests.changed import (
    LAYERS,
    GitError,
    Selection,
    changed_files,
    pytest_arguments,
    root_unit_tests,
    select,
)

REPO = Path(__file__).resolve().parents[2]
CONTAINER_TEST = "tests/integration/api/test_routes.py"
ROOT_TESTS = ("tests/unit/test_a.py", "tests/unit/test_b.py")

SELECTS = [
    (1, "openspec/changes/x/design.md", ()),
    (1, ".claude/settings.json", ()),
    (1, "temp/notes.txt", ()),
    (1, "README.md", ()),
    (2, "docs/modules/ROOT/pages/index.adoc", ("tests/unit/test_check_docs.py",)),
    (7, "tests/unit/test_public_api.py", ("tests/unit/test_public_api.py",)),
    (8, "tests/unit/domain/test_exceptions.py", ("tests/unit/domain/",)),
    (8, "tests/unit/services/helpers.py", ("tests/unit/services/",)),
    (8, "tests/unit/entrypoints/test_router.py", ("tests/unit/entrypoints/",)),
    (9, "tests/feature/steps/test_steps.py", ("tests/feature/",)),
    (10, "rdf_persistence/services/artifacts.py", ("tests/unit/services/",)),
    (10, "rdf_persistence/domain/generated/models.py", ("tests/unit/domain/",)),
    (10, "rdf_persistence/testkit/containers/fuseki.py", ("tests/unit/testkit/",)),
    (11, "rdf_persistence/__init__.py", ROOT_TESTS),
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
    (5, "tests/e2e/library_app.py"),
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
    return select(paths, existing, ROOT_TESTS)


def test_the_rows_cover_the_twelve_mapping_rules():
    rules = {row[0] for table in (SELECTS, FALLS_BACK, NAMED_NOT_RUN) for row in table}

    assert rules == set(range(1, 13)), "a mapping rule of the design has no row"


def test_the_layers_are_the_layer_folders_of_the_package():
    folders = {p.parent.name for p in (REPO / "rdf_persistence").glob("*/__init__.py")}

    assert folders == LAYERS, "the mapper's layers differ from the package's layer folders"


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


def test_the_root_level_unit_test_files_are_the_real_ones(monkeypatch):
    monkeypatch.chdir(REPO)

    listed = root_unit_tests()

    assert "tests/unit/test_changed.py" in listed, "the listing holds real files"
    assert listed == sorted(listed), "the listing is sorted"


def test_the_worked_example_selects_one_folder_and_hints_at_the_container_test():
    changed = [
        "rdf_persistence/services/artifacts.py",
        "tests/unit/services/test_replace_internal_values.py",
        "openspec/changes/x/design.md",
        CONTAINER_TEST,
    ]

    selection = _select(changed)

    assert selection.paths == ("tests/unit/services/",), "one folder, not two"
    assert selection.hints == (f"{CONTAINER_TEST}: run make test-containers",), "the container hint"
    assert pytest_arguments(selection.paths, None) == ["tests/unit/services/", "-n", "auto"], (
        "the arguments"
    )


def test_a_changed_container_test_alone_gives_no_arguments():
    selection = _select([CONTAINER_TEST])

    assert pytest_arguments(selection.paths, None) == [], "no paths, so no arguments"
    assert selection.hints, "the container test is still named"


def test_a_lone_deleted_test_file_gives_no_arguments():
    selection = _select(["tests/unit/test_public_api.py"], existing=lambda _: False)

    assert selection.paths == (), "a deleted file selects nothing"
    assert pytest_arguments(selection.paths, None) == [], "no paths, so no arguments"


def test_nothing_changed_selects_nothing():
    selection = _select([])

    assert selection == Selection(paths=(), hints=(), fallback_reasons=()), "an empty selection"


def test_a_selected_file_inside_a_selected_folder_is_dropped():
    selection = _select(["rdf_persistence/services/a.py", "tests/unit/services/test_a.py"])

    assert selection.paths == ("tests/unit/services/",), "the file lies in the folder"


def test_a_file_outside_the_selected_folder_is_kept_and_paths_are_sorted():
    selection = _select(
        [
            "tests/unit/test_public_api.py",
            "rdf_persistence/domain/a.py",
            "tests/unit/test_markers.py",
        ]
    )

    assert selection.paths == (
        "tests/unit/domain/",
        "tests/unit/test_markers.py",
        "tests/unit/test_public_api.py",
    ), "sorted, the file outside the folder kept"


def test_a_move_between_layers_selects_both_folders():
    selection = _select(["rdf_persistence/services/a.py", "rdf_persistence/adapters/a.py"])

    assert selection.paths == ("tests/unit/adapters/", "tests/unit/services/"), "both folders"


def test_fallback_wins_over_selected_paths():
    selection = _select(["rdf_persistence/services/a.py", "Makefile", "tests/conftest.py"])

    assert len(selection.fallback_reasons) == 2, "one reason per fallback path"


@pytest.mark.parametrize(
    ("paths", "expected_n"),
    [
        (("tests/unit/test_public_api.py",), "0"),
        (("tests/unit/test_markers.py", "tests/unit/test_public_api.py"), "0"),
        (("tests/unit/domain/",), "0"),
        (("tests/unit/services/",), "auto"),
        (("tests/feature/",), "auto"),
        (("tests/unit/domain/", "tests/unit/services/"), "auto"),
        (("tests/unit/domain/", "tests/unit/test_markers.py"), "auto"),
    ],
)
def test_one_process_is_chosen_for_files_only_or_the_domain_folder_only(paths, expected_n):
    assert pytest_arguments(paths, None) == [*paths, "-n", expected_n], f"workers for {paths}"


def test_pytest_n_overrides_the_choice_of_workers():
    assert pytest_arguments(("tests/unit/services/",), "4") == [
        "tests/unit/services/",
        "-n",
        "4",
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
        (["tests/unit/test_markers.py"], 0, False, ""),
    ],
)
def test_main_exits_with_the_status_its_listing_calls_for(
    monkeypatch, capsys, listing, code, stdout_empty, stderr_part
):
    got, out = _run_main(monkeypatch, capsys, listing)

    assert got == code, f"exit status for {listing!r}"
    assert (out.out == "") is stdout_empty, f"stdout for {listing!r}: {out.out!r}"
    assert stderr_part in out.err, f"stderr for {listing!r}: {out.err!r}"

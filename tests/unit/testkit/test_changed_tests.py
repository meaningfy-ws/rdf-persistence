"""The generic changed-tests planner, against a small fake classifier (test-control-testkit TC-11)."""

import importlib
import subprocess
import sys
import threading
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path, PurePosixPath

import pytest

from rdf_persistence.testkit import changed_tests
from rdf_persistence.testkit.changed_tests import (
    FALLBACK_EXIT,
    NO_DATA_HINT,
    NO_TESTS_EXIT,
    GitError,
    changed_files,
    exit_status,
    plan,
    select,
)
from rdf_persistence.testkit.generated.rp_testkit import (
    ChangedSelection,
    ChangedTestsLayout,
)
from rdf_persistence.testkit.generated.rp_testkit import (
    SelectionDataOutcome as Outcome,
)
from rdf_persistence.testkit.selection_data import DAMAGED_MESSAGE, PACKAGES_MESSAGE, worktree_lock

SEED_HINT = "no test selection data in this worktree: run make test-seed"
APP_FOLDER = "tests/unit/app/"
EXTRA_FOLDER = "tests/extra/"
ROOT_FILE = "tests/unit/test_root_level.py"
OTHER_ROOT_FILE = "tests/unit/test_other_root_level.py"
CONTAINER_TEST = "tests/integration/test_it.py"
APP_FILE = "src/app/x.py"
EXTRA_FILE = "extras/gen/y.py"
DOC_FILE = "docs/page.adoc"
LAYOUT = ChangedTestsLayout(
    testmon_folders=["tests/unit", "tests/feature"],
    extra_testmon_folder="tests/extra",
    extra_selected_by=["extras"],
    ignores=["--ignore=tests/e2e", "--ignore=tests/perf"],
    markers=["-m", "unit and not quarantine"],
    default_workers=4,
)
NO_EXTRA = ChangedTestsLayout(
    testmon_folders=["tests/unit"],
    extra_selected_by=[],
    ignores=[],
    markers=["-m", "unit"],
    default_workers=2,
)


def _selection(
    paths: list[str] | None = None, hints: list[str] | None = None, reasons: list[str] | None = None
) -> ChangedSelection:
    return ChangedSelection(paths=paths or [], hints=hints or [], fallback_reasons=reasons or [])


class FakeClassifier:
    """A project's classifier: the rules a consumer would write, in seven lines."""

    def classify(self, path: str) -> ChangedSelection:
        name = PurePosixPath(path).name
        if path.startswith("src/app/"):
            return _selection([APP_FOLDER])
        if path.startswith("extras/"):
            return _selection([EXTRA_FOLDER])
        if path.startswith("tests/unit/") and name.startswith("test_"):
            return _selection([path])
        if path.startswith("tests/integration/"):
            return _selection(hints=[f"{path}: run make test-containers"])
        if path.startswith("docs/"):
            return _selection(["tests/unit/test_docs.py"])
        if path.startswith(("notes/", ".testmondata")) or path in {"kept.py", "committed.py"}:
            return _selection()
        return _selection(reasons=[f"{path}: shared test infrastructure"])

    def is_testmon_visible(self, path: str) -> bool:
        return path.endswith(".py") and path.startswith(("src/", "extras/", "tests/unit/"))


CLASSIFIER = FakeClassifier()


def _folder_run(paths, workers, layout=LAYOUT):
    """The folder run: the selected paths, the layout's arguments, the workers."""
    return [*paths, *layout.ignores, *layout.markers, "-n", str(workers), "--dist", "loadgroup"]


def _testmon_run(workers=4, extra=True, layout=LAYOUT):
    folders = [*layout.testmon_folders, *([layout.extra_testmon_folder] if extra else [])]
    testmon = ["--testmon", "--testmon-nocollect", "--testmon-forceselect"]
    return [*folders, *layout.ignores, *layout.markers, *testmon] + [
        "-n",
        str(workers),
        "--dist",
        "loadgroup",
    ]


def _select(paths, existing: Callable[[str], bool] = lambda _: True) -> ChangedSelection:
    return select(paths, existing, CLASSIFIER)


def _plan(paths, has_data=False, existing=lambda _: True, workers=4, layout=LAYOUT):
    return plan(paths, has_data, existing, workers, CLASSIFIER, layout)


def _arguments(paths, workers=4):
    return [i.arguments for i in _plan(paths, False, workers=workers).invocations]


@pytest.mark.parametrize(
    ("changed", "paths", "hints", "reasons"),
    [
        (["notes/a.txt"], [], [], []),
        ([APP_FILE], [APP_FOLDER], [], []),
        ([ROOT_FILE], [ROOT_FILE], [], []),
        ([DOC_FILE], ["tests/unit/test_docs.py"], [], []),
        (["Makefile"], [], [], ["Makefile: shared test infrastructure"]),
        ([CONTAINER_TEST], [], [f"{CONTAINER_TEST}: run make test-containers"], []),
        ([], [], [], []),
        ([APP_FILE, "tests/unit/app/test_a.py"], [APP_FOLDER], [], []),
        ([ROOT_FILE, APP_FILE, OTHER_ROOT_FILE], [APP_FOLDER, OTHER_ROOT_FILE, ROOT_FILE], [], []),
    ],
    ids=[
        "no-rule-selects-nothing",
        "folder",
        "file",
        "docs-file",
        "fallback",
        "hint",
        "nothing",
        "file-inside-a-folder-dropped",
        "sorted-with-file-kept",
    ],
)
def test_select_follows_the_classifier(changed, paths, hints, reasons):
    got = _select(changed)

    assert got == _selection(paths, hints, reasons), f"the selection of {changed}"


def test_a_missing_folder_falls_back_with_a_reason_that_names_it():
    got = select([APP_FILE], lambda path: False, CLASSIFIER)

    assert got.paths == [], "nothing to run by path"
    assert APP_FILE in got.fallback_reasons[0], "the reason names the path"
    assert APP_FOLDER in got.fallback_reasons[0], "the reason names the folder"
    assert "make test-fast" in got.fallback_reasons[0], "the reason names the lane"


def test_a_missing_file_is_dropped_without_a_reason():
    got = select([ROOT_FILE], lambda path: False, CLASSIFIER)

    assert got == _selection(), "a deleted file selects nothing"


def test_a_fallback_reason_is_kept_per_path():
    got = _select([APP_FILE, "Makefile", "uv.lock"])

    assert len(got.fallback_reasons) == 2, "one reason per fallback path"


def test_select_collects_strings_so_models_never_need_hashing():
    got = _select([APP_FILE, APP_FILE, "src/app/z.py"])

    assert got.paths == [APP_FOLDER], "the same folder from three files is one"


def test_a_selection_has_the_fields_of_the_generated_model():
    assert isinstance(_select([APP_FILE]), ChangedSelection), "the generated model, not a dataclass"


def test_a_folder_runs_in_parallel():
    assert _arguments([APP_FILE]) == [_folder_run([APP_FOLDER], 4)], "the workers of the call"


def test_a_file_runs_on_one_process():
    assert _arguments([ROOT_FILE], 6) == [_folder_run([ROOT_FILE], 0)], "one process for files"


def test_a_folder_takes_the_worker_count():
    assert _arguments([APP_FILE], 6) == [_folder_run([APP_FOLDER], 6)], "the count is a parameter"


def test_a_project_classifier_runs_its_folder_with_the_layout_and_hints_at_the_seed():
    """The rp-testkit scenario: src/app/x.py changed, no selection data."""
    got = _plan([APP_FILE])

    assert [i.arguments for i in got.invocations] == [_folder_run([APP_FOLDER], 4)], "layout's args"
    assert got.hints == [SEED_HINT], "the hint says to run make test-seed"
    assert got.fallback_reasons == [], "no fallback"


def test_the_seed_hint_is_the_published_constant():
    assert NO_DATA_HINT == SEED_HINT, "the hint of stage 1"


WORKED_EXAMPLES = [
    pytest.param([APP_FILE], True, [_testmon_run()], [], [], id="visible-with-data"),
    pytest.param(
        ["Makefile", APP_FILE],
        False,
        [],
        [SEED_HINT],
        ["Makefile: shared test infrastructure"],
        id="fallback-without-data",
    ),
    pytest.param(
        ["Makefile", APP_FILE],
        True,
        [],
        [],
        ["Makefile: shared test infrastructure"],
        id="fallback-with-data",
    ),
    pytest.param(
        [APP_FILE, DOC_FILE],
        True,
        [_testmon_run(), _folder_run(["tests/unit/test_docs.py"], 0)],
        [],
        [],
        id="code-and-docs-with-data",
    ),
    pytest.param(
        [EXTRA_FILE],
        True,
        [_testmon_run(extra=False), _folder_run([EXTRA_FOLDER], 4)],
        [],
        [],
        id="extra-root-with-data",
    ),
    pytest.param(
        [CONTAINER_TEST],
        True,
        [],
        [f"{CONTAINER_TEST}: run make test-containers"],
        [],
        id="container-test-with-data",
    ),
    pytest.param(
        ["notes/a.py"],
        True,
        [],
        [],
        [],
        id="no-rule-with-data",
    ),
    pytest.param([], True, [], [], [], id="nothing-with-data"),
    pytest.param([], False, [], [], [], id="nothing-without-data"),
]


@pytest.mark.parametrize(
    ("changed", "has_data", "invocations", "hints", "reasons"), WORKED_EXAMPLES
)
def test_the_plan_of_a_worked_example(changed, has_data, invocations, hints, reasons):
    got = _plan(changed, has_data)

    assert [i.arguments for i in got.invocations] == invocations, "the invocations, in order"
    assert got.hints == hints, "the hints"
    assert got.fallback_reasons == reasons, "the fallback reasons"


def test_a_plan_without_an_extra_folder_never_adds_one():
    got = _plan([APP_FILE], True, layout=NO_EXTRA)

    assert [i.arguments for i in got.invocations] == [_testmon_run(layout=NO_EXTRA, extra=False)], (
        "the testmon folders of the layout only"
    )


def test_the_workers_of_the_plan_are_a_parameter():
    got = _plan([APP_FILE], True, workers=7)

    assert got.invocations[0].arguments == _testmon_run(workers=7), (
        "the testmon run takes the count"
    )


@pytest.mark.parametrize("has_data", [True, False])
def test_a_plan_called_twice_is_the_same(has_data):
    paths = [APP_FILE, DOC_FILE, EXTRA_FILE]

    assert _plan(paths, has_data) == _plan(paths, has_data), "no state between calls"


def test_a_lone_deleted_test_file_gives_no_invocation():
    assert _plan([ROOT_FILE], False, existing=lambda _: False).invocations == [], "no run"


def test_the_fallback_exit_is_75():
    assert FALLBACK_EXIT == 75, "75 is the Makefile's signal to run make test-fast"


@pytest.mark.parametrize(
    ("pytest_exit", "expected"),
    [(0, 0), (1, 1), (2, 2), (3, 2), (4, 4), (NO_TESTS_EXIT, 0), (70, 1), (-9, 1)],
)
def test_the_exit_status_of_pytest_maps_to_ours(pytest_exit, expected):
    assert exit_status(pytest_exit) == expected, f"pytest exit {pytest_exit}"


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
    for folder_test in ("tests/unit/app/test_a.py", "tests/unit/test_docs.py", "tests/extra/t.py"):
        _write(tmp_path, folder_test, "")  # the folders the fake classifier selects
    _commit_all(tmp_path, "base")
    _git(tmp_path, "checkout", "-b", "feature/x")
    _write(tmp_path, "committed.py", "c")
    _commit_all(tmp_path, "feature")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BASE", raising=False)
    monkeypatch.delenv("PYTEST_CHANGED_N", raising=False)
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


@pytest.mark.parametrize(
    "name",
    ["src/app/café.py", "src/app/two words.py", "src/app/tab\there.py"],
    ids=["non-ascii", "space", "tab"],
)
def test_a_path_git_would_quote_is_listed_as_it_is(feature_repo, name):
    _write(feature_repo, name, "x")  # untracked
    _write(feature_repo, "edited.py", "changed")  # tracked

    listed = changed_files("develop")

    assert name in listed, f"{name!r} is listed unquoted"
    assert "edited.py" in listed, "a tracked change is still listed"


def test_the_listing_is_empty_on_the_base_branch_with_a_clean_tree(feature_repo):
    _git(feature_repo, "checkout", "develop")

    assert changed_files("develop") == [], "nothing differs from the base"


def test_an_unknown_base_is_a_git_error_that_names_it(feature_repo):
    with pytest.raises(GitError, match="nosuchbase"):
        changed_files("nosuchbase")


def test_pytest_runs_as_a_module_of_the_running_interpreter(monkeypatch):
    seen: list[list[str]] = []

    def fake_run(argv, **kwargs):
        seen.append(list(argv))
        return subprocess.CompletedProcess(argv, 7)

    monkeypatch.setattr(changed_tests.subprocess, "run", fake_run)  # X3

    got = changed_tests._run_pytest(["tests/unit", "-n", "0"])

    assert seen == [[sys.executable, "-m", "pytest", "tests/unit", "-n", "0"]], "the argv"
    assert got == 7, "pytest's code is returned"


PUBLIC_NAMES = {
    "changed_tests": {
        "Classifier",
        "select",
        "plan",
        "changed_files",
        "main",
        "GitError",
        "UsageError",
        "FALLBACK_EXIT",
    },
    "selection_data": {
        "check",
        "swap",
        "seed",
        "worktree_lock",
        "current_packages",
        "main",
        "CHECK_EXIT",
        "MESSAGES",
    },
    "run_queue": {"workers", "main"},
}


@pytest.mark.parametrize("module", sorted(PUBLIC_NAMES))
def test_each_module_declares_the_public_names_of_pd_14(module):
    imported = importlib.import_module(f"rdf_persistence.testkit.{module}")

    assert set(imported.__all__) == PUBLIC_NAMES[module], f"{module}.__all__ is PD-14's list"
    assert len(imported.__all__) == len(PUBLIC_NAMES[module]), "no name twice"


class Runner:
    """The injected pytest runner: records each argument list, answers the codes it was given."""

    def __init__(self, *codes: int):
        self.codes = list(codes)
        self.calls: list[list[str]] = []

    def __call__(self, arguments):
        self.calls.append(list(arguments))
        return self.codes.pop(0) if self.codes else 0


def _no_lock(root):
    return nullcontext()


class RecordingLock:
    """A lock that records the roots it was taken for."""

    def __init__(self) -> None:
        self.taken: list[Path] = []

    def __call__(self, root):
        self.taken.append(root)
        return nullcontext()


def _main(runner=None, outcome=Outcome.NO_DATA, lock=_no_lock, layout=LAYOUT) -> int:
    return changed_tests.main(
        CLASSIFIER, layout, run=runner or Runner(), data_state=lambda root: outcome, lock=lock
    )


def _changed(repo: Path, *files: str) -> None:
    """The files a change leaves untracked in the feature repo."""
    for name in files:
        _write(repo, name, "x")


@pytest.mark.parametrize(
    ("files", "code", "stderr_part"),
    [
        (["notes/a.txt"], 0, "nothing to run against develop"),
        (["Makefile"], 75, "Makefile"),
        ([APP_FILE], 0, ""),
    ],
    ids=["nothing-to-run", "fallback", "a-run"],
)
def test_main_exits_with_the_status_its_listing_calls_for(
    feature_repo, capsys, files, code, stderr_part
):
    _changed(feature_repo, *files)

    got = _main()

    out = capsys.readouterr()
    assert got == code, f"exit status for {files}"
    assert out.out == "", "nothing is printed on stdout"
    assert stderr_part in out.err, f"stderr for {files}: {out.err!r}"


def test_an_unknown_base_makes_main_exit_75_naming_the_base(feature_repo, monkeypatch, capsys):
    monkeypatch.setenv("BASE", "nosuchbase")

    got = _main()

    assert got == FALLBACK_EXIT, "a git failure runs make test-fast"
    assert "nosuchbase" in capsys.readouterr().err, "the base is named"


def test_outside_a_checkout_main_exits_75(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))

    got = _main()

    assert got == FALLBACK_EXIT, "no checkout means make test-fast"
    assert "running make test-fast" in capsys.readouterr().err, "and it is said"


@pytest.mark.parametrize(
    ("pytest_exit", "expected"), [(0, 0), (1, 1), (2, 2), (3, 2), (4, 4), (5, 0), (70, 1), (-9, 1)]
)
def test_main_maps_the_exit_status_of_pytest(feature_repo, pytest_exit, expected):
    _changed(feature_repo, APP_FILE)
    runner = Runner(pytest_exit)

    got = _main(runner)

    assert got == expected, f"pytest exit {pytest_exit}"
    assert len(runner.calls) == 1, "the one planned run was made"


def test_main_says_so_when_testmon_selects_no_test(feature_repo, capsys):
    _changed(feature_repo, APP_FILE)

    got = _main(Runner(5), Outcome.SOUND)

    assert got == 0, "no test selected is a pass"
    assert "testmon selected no test" in capsys.readouterr().err, "and it is said"


def test_main_says_so_when_no_test_is_collected(feature_repo, capsys):
    _changed(feature_repo, ROOT_FILE)

    got = _main(Runner(5))

    assert got == 0, "no test collected is a pass"
    assert "no test collected" in capsys.readouterr().err, "and it is said"


def test_main_stops_at_the_first_failing_invocation(feature_repo):
    _changed(feature_repo, APP_FILE, DOC_FILE)
    runner = Runner(1, 0)

    got = _main(runner, Outcome.SOUND)

    assert got == 1, "the failure of the first run is the status"
    assert len(runner.calls) == 1, "the second run is not made"


def test_main_runs_every_invocation_in_order_when_all_pass(feature_repo):
    _changed(feature_repo, APP_FILE, DOC_FILE)
    runner = Runner(0, 0)

    got = _main(runner, Outcome.SOUND)

    assert got == 0, "all passed"
    assert [("--testmon" in call) for call in runner.calls] == [True, False], (
        "testmon, then folders"
    )


def test_main_passes_the_plans_argument_lists_to_the_runner(feature_repo):
    _changed(feature_repo, APP_FILE)
    runner = Runner()

    _main(runner, Outcome.SOUND)

    assert runner.calls == [_testmon_run()], "the testmon run with the layout's default workers"


def test_the_layouts_default_workers_apply_when_none_is_set(feature_repo):
    _changed(feature_repo, APP_FILE)
    runner = Runner()

    _main(runner, Outcome.SOUND, layout=NO_EXTRA)

    assert runner.calls == [_testmon_run(2, extra=False, layout=NO_EXTRA)], "2, the layout's count"


def test_pytest_changed_n_sets_the_workers_and_pytest_n_is_ignored(feature_repo, monkeypatch):
    _changed(feature_repo, APP_FILE)
    monkeypatch.setenv("PYTEST_CHANGED_N", "6")
    monkeypatch.setenv("PYTEST_N", "2")
    runner = Runner()

    _main(runner, Outcome.SOUND)

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
    feature_repo, capsys, outcome, message, seed_hint
):
    _changed(feature_repo, APP_FILE)
    runner = Runner()

    _main(runner, outcome)

    err = capsys.readouterr().err
    assert ("--testmon" in runner.calls[0]) is (outcome is Outcome.SOUND), f"testmon on {outcome}"
    assert message in err, f"the message of {outcome} is printed"
    assert (SEED_HINT in err) is seed_hint, f"the seed hint for {outcome}"


def test_a_hint_goes_to_stderr_and_is_not_a_fallback(feature_repo, capsys):
    _changed(feature_repo, CONTAINER_TEST)
    runner = Runner()

    got = _main(runner, Outcome.SOUND)

    assert got == 0, "a container test only hints"
    assert "make test-containers" in capsys.readouterr().err, "the hint is on stderr"
    assert runner.calls == [], "nothing is run"


def test_a_fallback_reason_runs_nothing(feature_repo):
    _changed(feature_repo, "Makefile", APP_FILE)
    runner = Runner()

    got = _main(runner, Outcome.SOUND)

    assert got == FALLBACK_EXIT, "run make test-fast"
    assert runner.calls == [], "the runner is not called"


def test_a_fallback_still_prints_the_hints_first(feature_repo, capsys):
    """PD-5: the seed hint comes before the reasons, and the exit stays 75."""
    _changed(feature_repo, "Makefile", APP_FILE)
    runner = Runner()

    got = _main(runner, Outcome.NO_DATA)

    err = capsys.readouterr().err
    assert got == FALLBACK_EXIT, "run make test-fast"
    assert err.index(SEED_HINT) < err.index("Makefile"), "hints before reasons"
    assert runner.calls == [], "nothing is run"


@pytest.mark.parametrize("value", ["abc", "0", "-1", "2.5", " ", "1e2"])
def test_a_bad_worker_count_is_a_usage_error_before_any_git_call(
    tmp_path, monkeypatch, capsys, value
):
    """PD-9: outside a checkout a git call would give 75, so exit 2 shows git was not called."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    monkeypatch.setenv("PYTEST_CHANGED_N", value)
    runner = Runner()

    got = _main(runner, Outcome.SOUND)

    assert got == 2, f"exit status for {value!r}"
    assert f"PYTEST_CHANGED_N must be a positive integer, got '{value}'" in capsys.readouterr().err
    assert runner.calls == [], "nothing is run"


@pytest.mark.parametrize("value", ["1", "6", "16"])
def test_a_good_worker_count_is_taken(feature_repo, monkeypatch, value):
    _changed(feature_repo, APP_FILE)
    monkeypatch.setenv("PYTEST_CHANGED_N", value)
    runner = Runner()

    _main(runner, Outcome.SOUND)

    assert runner.calls == [_testmon_run(workers=int(value))], f"{value} workers"


HOLD_EXCLUSIVE = """
import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT)
fcntl.flock(fd, fcntl.LOCK_EX)
print("ready", flush=True)
sys.stdin.read()
"""


def test_main_waits_for_an_exclusive_holder_before_the_testmon_run(feature_repo):
    """PD-6: the swap holds the lock exclusive; the testmon run starts only once it is gone."""
    import sys

    _changed(feature_repo, APP_FILE)
    waiting = threading.Event()
    runner = Runner()
    results: list[int] = []

    def shared_and_signalling(root):
        return worktree_lock(root, exclusive=False, on_wait=waiting.set)

    holder = subprocess.Popen(
        [sys.executable, "-c", HOLD_EXCLUSIVE, str(feature_repo / ".testmondata.lock")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    builder = threading.Thread(
        target=lambda: results.append(_main(runner, Outcome.SOUND, shared_and_signalling))
    )
    try:
        assert holder.stdout.readline().strip() == "ready", "the holder has the lock exclusive"
        builder.start()
        assert waiting.wait(timeout=30), "main reports that it waits for the lock"
        assert runner.calls == [], "the run does not start while the lock is held exclusive"
        holder.kill()
        holder.wait()
        builder.join(timeout=30)
        assert not builder.is_alive(), "main goes on once the holder is gone"
    finally:
        holder.kill()
        holder.wait()
    assert results == [0], "main finished with its pass"
    assert runner.calls == [_testmon_run()], "the testmon run came after the wait"


def test_the_folder_run_does_not_take_the_lock(feature_repo):
    _changed(feature_repo, DOC_FILE)
    lock = RecordingLock()

    _main(Runner(), Outcome.SOUND, lock)

    assert lock.taken == [], "a folder run reads no selection data"


def test_the_testmon_run_takes_the_lock_of_the_repository_root(feature_repo):
    _changed(feature_repo, APP_FILE)
    lock = RecordingLock()

    _main(Runner(), Outcome.SOUND, lock)

    assert lock.taken == [feature_repo.resolve()], (
        "the testmon run holds the shared lock of the root"
    )

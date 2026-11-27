"""Every developer and CI lane leaves the quarantined tests out (rule 14, PD-9)."""

import os
import re
import subprocess

import pytest

from rdf_persistence.testkit.run_queue import workers
from tests.changed import IGNORES
from tests.conftest import TESTS_ROOT_DIR

MAKEFILE = (TESTS_ROOT_DIR.parent / "Makefile").read_text(encoding="utf-8")
SELECTION = re.compile(r'-m "([^"]+)"')
MAX_RECIPE_LINES = 15
# `test` is no lane of its own: it runs the three below (test_the_test_target_runs_the_three_lanes).
AGGREGATE_LANE = "test"
THREE_LANES = ["test-unit", "test-feature", "test-generator"]
LANES = [
    "test-unit",
    "test-unit-ci",
    "test-durations",
    "test-feature",
    "test-generator",
    "test-fast",
    "test-seed",
    "coverage-report",
    "profile-tests",
    "test-containers",
    "test-e2e",
    "test-perf",
]
# `test-changed` is no lane of this list: tests/changed.py plans and runs its pytest (PD-4), the
# marker filter and ignores are its constants, pinned below and in test_changed.py.
PARALLEL_LANES = [
    "test-unit",
    "test-unit-ci",
    "test-durations",
    "test-feature",
    "test-generator",
    "test-fast",
    "test-seed",
    "profile-tests",
]
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


@pytest.mark.parametrize("target", [*LANES, "test-changed", "mutation"])
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
    named = [lane for lane in LANES if WORKERS.search(expanded("\n".join(recipe_of(lane))))]

    assert sorted(named) == sorted(PARALLEL_LANES), "a lane runs in parallel but is not checked"


def test_the_test_target_runs_the_three_lanes() -> None:
    """generator-package PD-10: ``make test`` is the library's unit and feature lanes and the generator's."""
    recipe = expanded("\n".join(recipe_of(AGGREGATE_LANE)))

    assert " ".join(THREE_LANES) in recipe, "make test no longer runs the three lanes"
    assert not SELECTION.findall(recipe), "make test selects tests itself instead of its lanes"


def test_the_library_lanes_leave_the_generators_tests_to_their_own_lane() -> None:
    """generator-package PD-10, TC-29, TC-30: the pyramids are measured apart."""
    recipes = {lane: expanded("\n".join(recipe_of(lane))) for lane in LANES}

    for lane in ("test-unit", "test-unit-ci", "test-feature", "test-durations"):
        assert re.search(r"--ignore=.*?/tests/generator\s", recipes[lane] + " "), (
            f"{lane} collects tests/generator"
        )
        assert re.search(r"--cov=rdf_persistence\s", recipes[lane]) or lane == "test-durations", (
            f"{lane} does not measure the library"
        )
        assert "--cov=rdf_persistence_generation" not in recipes[lane], (
            f"{lane} measures the generator"
        )
    generator = recipes["test-generator"]
    assert re.search(r"--cov=rdf_persistence_generation\s", generator), (
        "it must measure the generator"
    )
    assert "--cov=rdf_persistence " not in generator, "test-generator measures the library"
    assert re.search(r"GENERATOR_COV_FLAGS\s*=(?:.*\\\n)*.*--cov-fail-under=80", MAKEFILE), (
        "the generator's coverage flags have no 80 % floor"
    )
    assert re.search(r"pytest .*?/tests/generator\s", generator), (
        "it must run tests/generator alone"
    )


def test_the_generator_lane_runs_its_unit_feature_and_integration_tiers_only() -> None:
    """generator-package DEC-9, PD-10, TC-56: no e2e tier, no container, and the slow tsc test runs."""
    recipe = expanded("\n".join(recipe_of("test-generator")))
    selection = " ".join(SELECTION.findall(recipe))
    tiers = set(re.findall(r"\b(unit|feature|integration|e2e|slow)\b", selection))

    assert tiers == {"unit", "feature", "integration"}, f"the generator lane selects {selection!r}"
    assert "not slow" not in selection, "the generator lane must keep the slow tsc test"
    assert "docker" not in recipe.lower(), "the generator lane starts no container"


GENERATOR_E2E_IGNORE = re.compile(
    r"--ignore=(?:(?!--).)*?/tests/generator/e2e(?:\s|$)"
)  # $(shell pwd) holds a space
LANES_WITHOUT_CONTAINERS = [
    "test-unit",
    "test-unit-ci",
    "test-durations",
    "test-feature",
    "test-generator",
    "test-fast",
    "test-seed",
    "coverage-report",
    "profile-tests",
]


@pytest.mark.parametrize("lane", LANES_WITHOUT_CONTAINERS)
def test_the_lanes_without_containers_ignore_the_generators_e2e_folder(lane: str) -> None:
    """D-27 L2 W1+W2: its conftest registers the container plugin whenever a session collects it."""
    recipe = expanded("\n".join(recipe_of(lane)))

    assert GENERATOR_E2E_IGNORE.search(recipe + " "), f"{lane} collects tests/generator/e2e"


@pytest.mark.parametrize("lane", ["test-containers", "test-e2e"])
def test_the_container_lanes_still_collect_the_generators_e2e_folder(lane: str) -> None:
    recipe = expanded("\n".join(recipe_of(lane)))

    assert not GENERATOR_E2E_IGNORE.search(recipe + " "), f"{lane} ignores tests/generator/e2e"


def test_the_ci_generator_job_sets_up_node_before_it_runs_the_lane() -> None:
    """generator-package DEC-9, TC-55: the integration tier runs tsc, which needs Node 20."""
    job = _ci_job("test-generator")

    assert "uses: actions/setup-node@v4" in job, "the generator job has no Node"
    assert re.search(r'node-version:\s*"?20"?', job), "the generator job must set up Node 20"
    assert "run: make test-generator" in job, "the generator job must run its lane"
    assert job.index("actions/setup-node") < job.index("run: make test-generator"), (
        "Node must be set up before the lane runs"
    )


def test_the_durations_lane_replaces_the_file_instead_of_merging_into_it() -> None:
    """generator-package D-14: keys of moved tests must not survive a refresh."""
    recipe = expanded("\n".join(recipe_of("test-durations")))

    assert "--store-durations" in recipe, "test-durations no longer stores durations"
    assert "--clean-durations" in recipe, "test-durations merges into .test_durations"


def test_the_perf_lane_selects_perf_tests_not_in_quarantine() -> None:
    selections = SELECTION.findall(expanded("\n".join(recipe_of("test-perf"))))

    assert selections == ["perf and not quarantine"], "test-perf must select perf, not quarantine"


def test_only_the_ci_unit_lane_leaves_the_slow_tests_out() -> None:
    def selection(lane: str) -> str:
        return " ".join(SELECTION.findall(expanded("\n".join(recipe_of(lane)))))

    assert "and not slow" in selection("test-unit-ci"), "CI must not run the slow tests"
    for lane in ("test-unit", "test-seed"):
        assert "slow" not in selection(lane), f"{lane} must keep running the slow tests"


def test_the_nightly_unit_jobs_run_the_ci_unit_lane_in_shards_and_combine_their_coverage() -> None:
    ci = _workflow("nightly.yaml")

    assert "run: make test-unit-ci GROUP=${{ matrix.group }}" in ci, "a CI shard runs one group"
    assert "run: make coverage-combine" in ci, "a CI job must combine the shards' coverage"


QUEUED_LANES = [*PARALLEL_LANES, "test-containers"]
QUEUE_PREFIX = "TEST_QUEUE_LABEL=$@ $(PYTEST) "
PYTEST_FROM_ENVIRONMENT = ("CI", "PYTEST_N", "PYTEST_WORKER_MB")
QUEUED_PYTEST = "uv run python -m rdf_persistence.testkit.run_queue -- pytest"
PLAIN_PYTEST = "uv run pytest"


def make_prints(text: str, **added: str) -> str:
    """What ``make`` echoes for ``text`` in a child environment holding only ``added`` of the three knobs."""
    environment = {k: v for k, v in os.environ.items() if k not in PYTEST_FROM_ENVIRONMENT}
    environment.update(added)
    result = subprocess.run(
        ["make", "--no-print-directory", "--eval", f'pn:;@echo "{text}"', "pn"],
        cwd=TESTS_ROOT_DIR.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.mark.parametrize("lane", QUEUED_LANES)
def test_every_queued_recipe_line_runs_pytest_through_the_queue(lane: str) -> None:
    """agent-test-control PD-2: the lanes that run workers, and the container lane, wait their turn."""
    lines = [line for line in recipe_of(lane) if "pytest" in expanded(line) and "echo" not in line]

    assert lines, f"{lane} has no pytest line"
    for line in lines:
        queued = QUEUE_PREFIX in line or QUEUE_PREFIX.replace("$(PYTEST)", "$(SEED_RUN)") in line
        assert queued, f"{lane} does not run through the queue: {line.strip()}"
        assert "uv run pytest" not in line, f"{lane} still spells uv run pytest: {line.strip()}"


def test_a_lane_that_runs_workers_is_one_that_queues() -> None:
    holders = [lane for lane in LANES if "$(PARALLEL)" in "\n".join(recipe_of(lane))]

    assert sorted(holders) == sorted(PARALLEL_LANES), "a lane holds $(PARALLEL) but is not queued"


def test_no_recipe_wraps_make_in_the_queue() -> None:
    wrapping = [
        line.strip() for line in MAKEFILE.splitlines() if "$(MAKE)" in line and "$(PYTEST)" in line
    ]

    assert not wrapping, f"a recipe queues a make: {wrapping}"


def test_test_changed_neither_queues_nor_reads_the_worker_count() -> None:
    recipe = "\n".join(recipe_of("test-changed"))

    assert "$(PYTEST)" not in recipe, "test-changed queues"
    assert "PYTEST_N" not in recipe, "test-changed reads PYTEST_N"


def test_test_changed_runs_the_module_and_falls_back_on_75_only() -> None:
    """agent-test-control PD-4: 75 means make test-fast; every other status is the module's own."""
    recipe = "\n".join(recipe_of("test-changed"))

    assert "uv run --no-sync python -m tests.changed" in recipe, "test-changed runs the module"
    assert re.search(r"-eq 75\b.*\$\(MAKE\) --no-print-directory test-fast", recipe), (
        "75 runs make test-fast"
    )
    assert "-eq 3" not in recipe, "3 is no fallback status any more"
    assert "exit $$status" in recipe, "any other non-zero status is the target's"


def test_test_changed_runs_the_module_without_syncing() -> None:
    """PD-6: the fallback ``$(MAKE) test-fast`` inherits UV_NO_SYNC, so no step of the target syncs."""
    recipe = "\n".join(recipe_of("test-changed"))

    assert "uv run --no-sync python -m tests.changed" in recipe, "the module runs with --no-sync"
    assert "test-changed: export UV_NO_SYNC = 1\n" in MAKEFILE, "the fallback must not sync either"


def test_test_changed_leaves_the_pytest_arguments_to_the_module() -> None:
    recipe = expanded("\n".join(recipe_of("test-changed")))

    for forbidden in ("pytest", "--ignore", '-m "', "-n "):
        assert forbidden not in recipe.replace("tests.changed", ""), (
            f"test-changed spells {forbidden!r}: tests/changed.py plans it"
        )


def test_test_changed_help_names_the_worker_variable_it_reads() -> None:
    line = next(x for x in MAKEFILE.splitlines() if x.startswith("test-changed:"))

    assert "PYTEST_CHANGED_N" in line, "the help names PYTEST_CHANGED_N"
    assert "PYTEST_N" not in line.replace("PYTEST_CHANGED_N", ""), "the help names PYTEST_N"


def test_the_ignores_of_the_changed_module_are_those_of_the_unit_lane() -> None:
    """agent-test-control PD-5: the Makefile is the source of truth, the module repeats it."""
    unit_lane = dict(VARIABLE.findall(MAKEFILE))["UNIT_LANE"]
    generator_e2e = dict(VARIABLE.findall(MAKEFILE))["GENERATOR_E2E"]
    text = unit_lane.replace("$(GENERATOR_E2E)", generator_e2e).replace("$(TEST_PATH)", "tests")

    assert tuple(re.findall(r"--ignore=\S+", text)) == IGNORES, "IGNORES drifted from UNIT_LANE"


def _seed_recipe() -> str:
    return "\n".join(recipe_of("test-seed"))


def test_the_whole_seed_cycle_runs_inside_the_queue() -> None:
    """PD-7: clean, run and swap are one queued command (selection_data seed), not recipe shell."""
    recipe = _seed_recipe()
    line = next(x for x in recipe_of("test-seed") if "--testmon" in x)

    assert "$(SEED_RUN) python -m rdf_persistence.testkit.selection_data seed -- pytest " in line, (
        "the seed cycle is the queued testmon_data seed command"
    )
    assert "TEST_QUEUE_LABEL=$@ $(SEED_RUN)" in line, "the queue label is set"
    assert "rm -f" not in recipe, "the clean runs inside the queue, not before it"
    assert "swap" not in recipe, "the swap runs inside the queue, not after it"
    assert "SEED_RUN = uv run python -m rdf_persistence.testkit.run_queue --\n" in MAKEFILE, (
        "locally the seed queues"
    )
    assert "SEED_RUN = uv run\n" in MAKEFILE, "on CI the seed runs unqueued"


def test_the_seed_writes_its_own_data_file() -> None:
    assert "test-seed: export TESTMON_DATAFILE = .testmondata.seed\n" in MAKEFILE, (
        "the seed run records into .testmondata.seed, which the swap then moves"
    )


def test_the_seed_run_is_queued_selects_slow_tests_and_follows_the_test_order() -> None:
    line = next(x for x in recipe_of("test-seed") if "--testmon" in x)

    for part in (
        "--testmon --testmon-forceselect",
        "$(UNIT_LANE)",
        "$(PARALLEL)",
        "-p no:randomly",
        '-m "(unit or feature) $(NOT_QUARANTINE)"',
    ):
        assert part in line, f"the seed run lacks {part!r}"
    assert "--testmon-nocollect" not in line, "the seed collects"
    assert "--cov" not in line, "the seed measures no coverage"


def test_without_ci_the_queue_runs_pytest_and_the_workers_are_left_to_it() -> None:
    printed = make_prints("[$(PYTEST_N)] [$(PYTEST)] [$(PARALLEL)]")

    assert printed == f"[] [{QUEUED_PYTEST}] [-n @workers --dist loadgroup]", printed


def test_on_ci_pytest_runs_unqueued_with_the_workers_counted_by_make() -> None:
    printed = make_prints("$(PYTEST_N)|$(PYTEST)|$(PARALLEL)", CI="1")
    count, pytest_command, parallel = printed.split("|")

    assert pytest_command == PLAIN_PYTEST, f"CI queues: {pytest_command!r}"
    assert 1 <= int(count) <= workers(os.cpu_count(), None, 1), "the count is not workers()"
    assert parallel == f"-n {count} --dist loadgroup", parallel


def test_on_ci_the_worker_count_is_quiet_and_lazy() -> None:
    """PD-8: a recursive variable, so a target that never runs pytest never counts; errors go away."""
    assert re.search(
        r"^PYTEST_N \?= \$\(shell uv run --no-sync python -m rdf_persistence\.testkit\.run_queue --workers 2>/dev/null\)$",
        MAKEFILE,
        re.MULTILINE,
    ), "PYTEST_N is lazy and quiet"
    assert "PYTEST_N :=" not in MAKEFILE, "the count is taken at parse time"


def test_on_ci_without_a_count_pytest_gets_auto() -> None:
    """PD-8: when the count is empty (no uv, as in lint-only jobs), xdist decides."""
    environment = {k: v for k, v in os.environ.items() if k not in PYTEST_FROM_ENVIRONMENT}
    environment.update(CI="1", PYTEST_N="")
    result = subprocess.run(
        ["make", "-n", "test-unit", "CI=1", "PYTEST_N="],
        cwd=TESTS_ROOT_DIR.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "-n auto --dist loadgroup" in result.stdout, "an empty count means -n auto"


@pytest.mark.parametrize("added", [{}, {"CI": "1"}])
def test_a_given_worker_count_replaces_the_token(added: dict[str, str]) -> None:
    printed = make_prints("$(PARALLEL)", PYTEST_N="3", **added)

    assert printed == "-n 3 --dist loadgroup", printed


def _workflow(file: str) -> str:
    return (TESTS_ROOT_DIR.parent / ".github" / "workflows" / file).read_text(encoding="utf-8")


def _jobs(workflow: str) -> list[str]:
    body = workflow.split("\njobs:\n", 1)[1]
    return re.findall(r"^  ([\w-]+):$", body, re.MULTILINE)


def _triggers(workflow: str) -> list[str]:
    on = re.search(r"^on:\n(.*?)(?=^\S)", workflow, re.DOTALL | re.MULTILINE)
    assert on, "the workflow has no on: block"
    return re.findall(r"^  ([\w-]+):", on.group(1), re.MULTILINE)


def test_the_pr_gate_runs_the_static_checks_and_the_feature_tests_only() -> None:
    """ci-minimal-gate DEC-2: no unit or generator tests on a PR."""
    ci = _workflow("ci.yaml")

    assert _jobs(ci) == ["style", "types", "architecture", "spec-docs-generation", "feature"]
    assert "make test-unit" not in ci, "the PR gate runs no unit lane"
    assert "make test-generator" not in ci, "the PR gate runs no generator tests"


def test_the_pr_gate_runs_on_pull_requests_only() -> None:
    """ci-minimal-gate DEC-1: the merge into develop does not run the gate again."""
    assert _triggers(_workflow("ci.yaml")) == ["pull_request"]


def test_the_full_suite_runs_nightly_and_by_hand() -> None:
    """ci-minimal-gate DEC-3: the unit shards, the generator and Sonar run on a schedule."""
    nightly = _workflow("nightly.yaml")

    assert sorted(_triggers(nightly)) == ["schedule", "workflow_dispatch"]
    assert sorted(_jobs(nightly)) == ["sonar", "test-generator", "unit", "unit-shard"]


def _ci_job(name: str) -> str:
    ci = _workflow("nightly.yaml")
    match = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  \S|\Z)", ci, re.DOTALL | re.MULTILINE)
    assert match, f"nightly.yaml has no job {name}"
    return match.group(1)


def _needs(job: str) -> list[str]:
    header = _ci_job(job).split("steps:")[0]
    match = re.search(r"^    needs:\s*\[([^\]]*)\]", header, re.MULTILINE)
    return [name.strip() for name in match.group(1).split(",")] if match else []


def test_the_generator_job_hands_its_coverage_to_the_job_that_scans() -> None:
    """D-15, D-19: the scan job downloads the generator's report by the name it is uploaded under."""
    upload = _ci_job("test-generator")
    scan = _ci_job("sonar")

    assert "actions/upload-artifact@v4" in upload, "test-generator must upload its coverage"
    assert "name: generator-coverage" in upload, "the artifact must carry the name the scan reads"
    assert "coverage-generator.xml" in upload, "the generator's coverage report is uploaded"
    assert "name: generator-coverage" in scan, "the scan job downloads the generator's report"
    assert "name: coverage-report" in scan, "the scan job downloads the library's combined report"
    assert sorted(_needs("sonar")) == ["test-generator", "unit"], "the scan waits for both lanes"


def test_a_generator_failure_leaves_the_unit_job_green_and_the_reverse() -> None:
    """D-19: the unit job's result depends on the shards alone, and the shards do not read the generator."""
    assert _needs("unit") == ["unit-shard"], "unit must need only the shards"
    assert _needs("test-generator") == [], "the generator job must not wait for the library's jobs"
    assert "unit-shard-*" not in _ci_job("test-generator"), "no artifact named for the shards"


def test_the_scan_job_keeps_its_gate_and_runs_whatever_the_lanes_did() -> None:
    scan = _ci_job("sonar")

    assert "vars.SONAR_ENABLED == 'true'" in scan, "the scan runs only when enabled"
    assert "SonarSource/sonarqube-scan-action" in scan, "the scan lives in the sonar job"
    assert "SonarSource/sonarqube-scan-action" not in _ci_job("unit"), "unit no longer scans"


def test_sonar_reads_the_library_and_the_generator_coverage() -> None:
    """D-15: both reports are listed, so the generator's lines stop counting as uncovered."""
    sonar = (TESTS_ROOT_DIR.parent / "sonar-project.properties").read_text(encoding="utf-8")

    assert "sonar.python.coverage.reportPaths=coverage.xml,coverage-generator.xml" in sonar, (
        "sonar must list coverage.xml and coverage-generator.xml"
    )


def test_a_shard_runs_one_balanced_group_without_the_floor() -> None:
    shard = expanded(" ".join(recipe_of("test-unit-ci"))).replace("$(GROUP)", "3")

    assert "--splits $(SPLITS)" not in shard, "SPLITS is expanded"
    assert "--group 3" in shard, "GROUP picks one of the splits"
    assert "--cov-fail-under=0" in shard, "one shard alone cannot reach the floor"


def test_the_ci_matrix_has_one_job_per_split() -> None:
    ci = _workflow("nightly.yaml")
    splits = int(dict(VARIABLE.findall(MAKEFILE))["SPLITS"])

    assert f"group: {list(range(1, splits + 1))}" in ci, "the matrix must list every split"


def test_the_combined_coverage_keeps_the_80_percent_floor() -> None:
    assert any("--fail-under=80" in line for line in recipe_of("coverage-combine")), (
        "make coverage-combine must check the 80 % floor"
    )


def test_the_refresh_map_target_runs_the_refresher() -> None:
    assert any("tests.audit.refresh_map" in line for line in recipe_of("refresh-map")), (
        "make refresh-map must run tests/audit/refresh_map.py"
    )


GOLDEN_RESET = "test_the_toy_typescript_equals_the_golden_files"


def test_refresh_golden_leaves_the_served_baselines_of_the_move_alone() -> None:
    """TC-07's goldens guard the thematic move: an everyday refresh must not rewrite them."""
    recipe = "\n".join(recipe_of("refresh-golden"))
    assert "test_openapi_served" not in recipe, "the served OpenAPI golden is refreshed apart"
    assert f"not {GOLDEN_RESET}" in recipe, "the toy TypeScript golden is refreshed apart"


def test_refresh_snapshot_leaves_the_public_surface_baseline_of_the_move_alone() -> None:
    """TC-03's baseline guards the thematic move: the refresh every model change runs must not rewrite it."""
    recipe = "\n".join(recipe_of("refresh-snapshot"))
    assert "test_public_surface" not in recipe, "the public-surface baseline is refreshed apart"
    assert "RP_REFRESH_SNAPSHOT" in recipe, "the model-shape snapshot is still rewritten here"


def test_the_public_surface_has_a_refresh_target_of_its_own() -> None:
    recipe = "\n".join(recipe_of("refresh-surface"))
    assert "test_public_surface" in recipe, "the public-surface snapshot is rewritten here"
    assert "RP_REFRESH_SNAPSHOT" in recipe, "the refresh switch is set here"
    assert "baseline" in MAKEFILE.split("refresh-surface:")[1].splitlines()[0], (
        "the help string says it resets the move's baseline"
    )


def test_the_served_golden_has_a_refresh_target_of_its_own() -> None:
    recipe = "\n".join(recipe_of("refresh-served-golden"))
    assert "test_openapi_served" in recipe, "the served OpenAPI golden is rewritten here"
    assert GOLDEN_RESET in recipe, "the toy TypeScript golden is rewritten here"
    assert "baseline" in MAKEFILE.split("refresh-served-golden:")[1].splitlines()[0], (
        "the help string says it resets the move's baseline"
    )

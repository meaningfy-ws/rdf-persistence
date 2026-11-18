"""Every developer and CI lane leaves the quarantined tests out (rule 14, PD-9)."""

import re

import pytest

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
    "test-changed",
    "coverage-report",
    "profile-tests",
    "test-containers",
    "test-e2e",
    "test-perf",
]
PARALLEL_LANES = [
    "test-unit",
    "test-unit-ci",
    "test-durations",
    "test-feature",
    "test-generator",
    "test-fast",
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
    "test-changed",
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
    for lane in ("test-unit", "test-changed"):
        assert "slow" not in selection(lane), f"{lane} must keep running the slow tests"


def test_the_ci_unit_jobs_run_the_ci_unit_lane_in_shards_and_combine_their_coverage() -> None:
    ci = (TESTS_ROOT_DIR.parent / ".github" / "workflows" / "ci.yaml").read_text(encoding="utf-8")

    assert "run: make test-unit-ci GROUP=${{ matrix.group }}" in ci, "a CI shard runs one group"
    assert "run: make coverage-combine" in ci, "a CI job must combine the shards' coverage"


def _ci_job(name: str) -> str:
    ci = (TESTS_ROOT_DIR.parent / ".github" / "workflows" / "ci.yaml").read_text(encoding="utf-8")
    match = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  \S|\Z)", ci, re.DOTALL | re.MULTILINE)
    assert match, f"ci.yaml has no job {name}"
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
    ci = (TESTS_ROOT_DIR.parent / ".github" / "workflows" / "ci.yaml").read_text(encoding="utf-8")
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

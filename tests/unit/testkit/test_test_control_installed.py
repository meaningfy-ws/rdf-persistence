"""The test-control modules run by name from outside the repository (test-control-testkit PD-12 a, TC-8)."""

import os
import subprocess
import sys
from pathlib import Path


def _run_module(module: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-m", module, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_run_queue_prints_a_worker_count_by_module_name(tmp_path: Path) -> None:
    done = _run_module("rdf_persistence.testkit.run_queue", ["--workers"], tmp_path)

    assert done.returncode == 0, f"the module runs by name: {done.stderr}"
    assert int(done.stdout.strip()) > 0, f"a positive worker count: {done.stdout!r}"


def test_selection_data_check_reports_no_data_by_module_name(tmp_path: Path) -> None:
    done = _run_module("rdf_persistence.testkit.selection_data", ["check"], tmp_path)

    assert done.returncode == 5, f"an empty folder has no data (exit 5): {done.stderr}"


def test_changed_tests_with_a_bad_worker_count_exits_2_by_module_name(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, "-I", "-m", "rdf_persistence.testkit.changed_tests"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
        env={**os.environ, "PYTEST_CHANGED_N": "abc"},
    )

    assert done.returncode == 2, f"a bad PYTEST_CHANGED_N is a usage error: {done.stderr}"
    assert "PYTEST_CHANGED_N must be a positive integer, got 'abc'" in done.stderr, "the message"


def test_changed_tests_run_as_main_without_a_classifier_prints_a_usage_line(tmp_path: Path) -> None:
    done = _run_module("rdf_persistence.testkit.changed_tests", [], tmp_path)

    assert done.returncode == 2, f"no classifier is a usage error: {done.stderr}"
    assert "usage" in done.stderr.lower(), f"a usage line is printed: {done.stderr!r}"

"""The path table of ``tests/conftest.py`` stamps every marker of a directory's row (PD-16)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import conftest
from tests.conftest import TESTS_ROOT_DIR, markers_for_path, pytest_collection_modifyitems

ROOT = TESTS_ROOT_DIR.as_posix()


@pytest.mark.parametrize(
    ("directory", "expected"),
    [
        ("unit", {"unit"}),
        ("feature", {"feature"}),
        ("integration/store", {"integration", "store"}),
        ("integration/api", {"integration", "store"}),
        ("integration/tenancy", {"integration", "store", "files"}),
        ("integration/files", {"integration", "files"}),
        ("integration/identity", {"integration", "identity"}),
        ("integration/network", {"integration"}),
        ("e2e", {"e2e", "store", "files", "identity"}),
        ("perf", {"perf"}),
    ],
)
def test_directory_row_gives_every_marker(directory: str, expected: set[str]) -> None:
    assert set(markers_for_path(f"{ROOT}/{directory}/test_x.py")) == expected, (
        "a directory row gives its markers"
    )


def test_path_outside_the_table_gets_no_marker() -> None:
    assert markers_for_path(f"{ROOT}/test_x.py") == (), "a path outside the table gets no marker"


def test_checkout_under_a_directory_named_like_a_row_is_not_matched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(conftest, "TESTS_ROOT_DIR", Path("/work/unit/repo/tests"))
    assert markers_for_path("/work/unit/repo/tests/test_x.py") == (), (
        "a directory named like a row above the checkout gets no marker"
    )
    assert set(markers_for_path("/work/unit/repo/tests/integration/files/test_x.py")) == {
        "integration",
        "files",
    }, "only the real rows of the path give markers"


def test_path_outside_the_tests_tree_gets_no_marker() -> None:
    assert markers_for_path("/elsewhere/unit/test_x.py") == (), (
        "a path outside the tests tree gets no marker"
    )


def test_hook_adds_each_marker_to_the_item() -> None:
    added: list[str] = []
    item = SimpleNamespace(
        fspath=f"{ROOT}/integration/tenancy/test_x.py",
        add_marker=lambda marker: added.append(marker.name),
    )
    pytest_collection_modifyitems([item])
    assert added == ["integration", "store", "files"], "the hook adds each marker to the item"


def test_the_slow_marker_is_registered_and_not_slow_deselects_it(pytester: pytest.Pytester) -> None:
    """Under the repo's own pytest.ini (--strict-markers), `slow` is known and `-m` leaves it out."""
    ini = (TESTS_ROOT_DIR.parent / "pytest.ini").read_text(encoding="utf-8")
    pytester.makefile(".ini", pytest=ini)
    pytester.makepyfile(
        test_x="import pytest\n\n@pytest.mark.slow\ndef test_slow():\n    pass\n\n"
        "def test_fast():\n    pass\n"
    )
    result = pytester.runpytest("--strict-markers", "-m", "not slow", "-p", "no:randomly")
    result.assert_outcomes(passed=1, deselected=1)


def _ini() -> str:
    return (TESTS_ROOT_DIR.parent / "pytest.ini").read_text(encoding="utf-8")


def test_a_test_past_its_timeout_fails_naming_itself_and_the_next_test_runs(
    pytester: pytest.Pytester,
) -> None:
    """Under the repo's pytest.ini (signal method), a hung test fails in its worker and the next
    test runs."""
    pytester.makefile(".ini", pytest=_ini())
    pytester.makepyfile(
        test_x="import time\nimport pytest\n\n"
        "@pytest.mark.timeout(1)\ndef test_hangs():\n    time.sleep(30)\n\n"
        "def test_after():\n    pass\n"
    )
    result = pytester.runpytest_subprocess("-n", "1", "-p", "no:randomly", "-p", "no:cacheprovider")
    outcomes = result.parseoutcomes()
    assert outcomes.get("failed") == 1, f"the hung test must fail once: {outcomes}"
    assert outcomes.get("passed") == 1, f"the next test must still run: {outcomes}"
    result.stdout.fnmatch_lines(["*FAILED*test_hangs*"])


def test_a_serial_run_fails_the_test_past_its_timeout_naming_it_and_the_next_test_runs(
    pytester: pytest.Pytester,
) -> None:
    """Without xdist the signal method still fails only the hung test."""
    pytester.makefile(".ini", pytest=_ini())
    pytester.makepyfile(
        test_x="import time\n\n"
        "def test_hangs():\n    time.sleep(30)\n\n"
        "def test_after():\n    pass\n"
    )
    result = pytester.runpytest_subprocess(
        "-p", "no:xdist", "--timeout=1", "-p", "no:randomly", "-p", "no:cacheprovider"
    )
    outcomes = result.parseoutcomes()
    assert outcomes.get("failed") == 1, f"the hung test must fail once: {outcomes}"
    assert outcomes.get("passed") == 1, f"the next test must still run: {outcomes}"
    result.stdout.fnmatch_lines(["*FAILED*test_hangs*"])


def test_a_test_past_its_timeout_does_not_replace_the_xdist_worker(
    pytester: pytest.Pytester,
) -> None:
    """A crashed worker under `--dist loadgroup` never gets its queued tests back: the worker
    must survive a timeout."""
    pytester.makefile(".ini", pytest=_ini())
    pytester.makepyfile(
        test_x="import time\nimport pytest\n\n"
        "@pytest.mark.timeout(1)\ndef test_hangs():\n    time.sleep(30)\n\n"
        "def test_a():\n    pass\n\ndef test_b():\n    pass\n\ndef test_c():\n    pass\n"
    )
    result = pytester.runpytest_subprocess(
        "-n", "2", "--dist", "loadgroup", "-p", "no:randomly", "-p", "no:cacheprovider"
    )
    outcomes = result.parseoutcomes()
    assert outcomes.get("failed") == 1, f"only the hung test fails: {outcomes}"
    assert outcomes.get("passed") == 3, f"every other test ran: {outcomes}"
    output = result.stdout.str() + result.stderr.str()
    assert "replacing crashed worker" not in output, f"the worker was replaced: {output}"


def test_the_hypothesis_profile_is_derandomized_under_ci(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The root conftest loads the `ci` profile at import, so every xdist worker has it."""
    monkeypatch.setenv("CI", "1")
    monkeypatch.delenv("HYPOTHESIS_PROFILE", raising=False)
    monkeypatch.setenv("PYTHONPATH", str(TESTS_ROOT_DIR.parent))
    pytester.makeconftest("import tests.conftest  # noqa: F401\n")
    pytester.makepyfile(
        test_x="from hypothesis import settings\n\n"
        "def test_derandomized():\n"
        "    assert settings.default.derandomize, 'the profile is not derandomized'\n"
        "    assert settings.default.max_examples == 20, 'the repo ci profile is not loaded'\n"
    )
    result = pytester.runpytest_subprocess("-p", "no:randomly", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=1)

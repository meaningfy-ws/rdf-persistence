"""The pytest plugin that stops a session on stale or hand-edited generated output (PD-26)."""

from pathlib import Path

import pytest

from rdf_persistence.generation.cli import main

from .test_generate_cli import PYPROJECT, SCHEMA

CONFTEST = 'pytest_plugins = ["rdf_persistence.testkit.freshness"]\n'
TEST = "def test_it():\n    assert True\n"
INI = "[pytest]\nrp_generate_projects =\n    pyproject.toml\n    other/pyproject.toml\n"


def make_project(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (folder / "m.yaml").write_text(SCHEMA, encoding="utf-8")
    assert main(["--project", str(folder / "pyproject.toml")]) == 0, "the project must generate"
    return folder


@pytest.fixture
def session(pytester: pytest.Pytester) -> pytest.Pytester:
    """A rootdir with a generated project, the plugin enabled and one passing test."""
    make_project(pytester.path)
    pytester.makeconftest(CONFTEST)
    pytester.makepyfile(test_it=TEST)
    return pytester


def test_a_fresh_project_lets_the_tests_run(session: pytest.Pytester) -> None:
    session.runpytest().assert_outcomes(passed=1)


def test_a_schema_changed_without_regenerating_stops_the_session_before_any_test(
    session: pytest.Pytester,
) -> None:
    schema = session.path / "m.yaml"
    schema.write_text(SCHEMA + "# changed\n", encoding="utf-8")
    result = session.runpytest()
    assert result.ret == 1, "the session did not stop with exit code 1"
    result.stdout.fnmatch_lines(["*m.yaml*", "*make generate*"])
    assert "test_it" not in result.stdout.str(), "a test ran in a stale session"


def test_a_hand_edited_generated_file_stops_the_session_and_is_named(
    session: pytest.Pytester,
) -> None:
    output = session.path / "app/generated/m.py"
    output.write_text(output.read_text() + "# by hand\n", encoding="utf-8")
    result = session.runpytest()
    assert result.ret == 1, "the session did not stop with exit code 1"
    result.stdout.fnmatch_lines(["*app/generated/m.py*"])


def test_every_listed_project_is_checked(session: pytest.Pytester) -> None:
    other = make_project(session.path / "other")
    (other / "m.yaml").write_text(SCHEMA + "# changed\n", encoding="utf-8")
    session.makeini(INI)
    result = session.runpytest()
    assert result.ret == 1, "a stale second project did not stop the session"
    result.stdout.fnmatch_lines(["*other*m.yaml*"])


def test_a_listed_project_without_targets_stops_the_session(session: pytest.Pytester) -> None:
    session.makeini(INI)
    result = session.runpytest()
    assert result.ret == 1, "a listed project that cannot be read did not stop the session"
    assert "other/pyproject.toml: no [tool.rp-generate]" in result.stdout.str(), (
        "the unreadable project is not named"
    )

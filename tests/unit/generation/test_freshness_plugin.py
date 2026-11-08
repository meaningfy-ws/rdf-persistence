"""The pytest plugin that stops a session on stale or hand-edited generated output (PD-26)."""

from pathlib import Path

import pytest

from rdf_persistence.generation.cli import main

from .test_freshness import DEFAULT_HINT, NAMED
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
    result.stdout.fnmatch_lines(["*m.yaml*", f"*{DEFAULT_HINT}*"])
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


def stop_text(session: pytest.Pytester) -> str:
    result = session.runpytest()
    assert result.ret == 1, "the session did not stop"
    return result.stdout.str()


def test_an_entry_names_its_own_command_in_the_hint(session: pytest.Pytester) -> None:
    (session.path / "pyproject.toml").write_text(PYPROJECT + NAMED, encoding="utf-8")
    assert main(["--project", str(session.path / "pyproject.toml")]) == 0
    (session.path / "m.yaml").write_text(SCHEMA + "# changed\n", encoding="utf-8")
    text = stop_text(session)
    assert "run `make generate-models` to regenerate, then commit the result" in text, "the entry's command is not named"
    assert "`rp-generate`" not in text, "the default is named beside the entry's command"


def test_several_stale_projects_print_one_hint_naming_each_command_once(
    session: pytest.Pytester,
) -> None:
    other = make_project(session.path / "other")
    (other / "pyproject.toml").write_text(PYPROJECT + NAMED, encoding="utf-8")
    assert main(["--project", str(other / "pyproject.toml")]) == 0
    for folder in (session.path, other):
        (folder / "m.yaml").write_text(SCHEMA + "# changed\n", encoding="utf-8")
    session.makeini(INI)
    text = stop_text(session)
    assert text.count("to regenerate, then commit the result") == 1, "not exactly one hint"
    assert "run `rp-generate` or `make generate-models` to regenerate, then commit the result" in text, "a command is missing"


def test_a_configuration_error_stops_the_session_without_a_hint(session: pytest.Pytester) -> None:
    (session.path / "pyproject.toml").write_text(PYPROJECT + "colour = 'red'\n", encoding="utf-8")
    text = stop_text(session)
    assert "colour" in text, "the unknown key is not named"
    assert "to regenerate" not in text, "a configuration error suggests regenerating"


def test_a_stale_project_and_a_configuration_error_hint_only_the_stale_command(
    session: pytest.Pytester,
) -> None:
    other = make_project(session.path / "other")
    (other / "pyproject.toml").write_text(PYPROJECT + "colour = 'red'\n", encoding="utf-8")
    (session.path / "m.yaml").write_text(SCHEMA + "# changed\n", encoding="utf-8")
    session.makeini(INI)
    text = stop_text(session)
    assert "colour" in text, "the configuration error is not named"
    assert text.count("to regenerate") == 1, "not exactly one hint"
    assert DEFAULT_HINT in text, "the stale project's command is not hinted"


def test_a_configuration_error_beside_a_fresh_project_stops_the_session_without_a_hint(
    session: pytest.Pytester,
) -> None:
    other = make_project(session.path / "other")
    (other / "pyproject.toml").write_text(PYPROJECT + "colour = 'red'\n", encoding="utf-8")
    session.makeini(INI)
    text = stop_text(session)
    assert "colour" in text, "the configuration error is not named"
    assert "to regenerate" not in text, "a fresh project and an error suggest regenerating"


def test_a_non_string_command_stops_the_session_naming_the_toml_key(
    session: pytest.Pytester,
) -> None:
    (session.path / "pyproject.toml").write_text(PYPROJECT + "regenerate-command = 3\n", "utf-8")
    text = stop_text(session)
    assert "regenerate-command" in text, "the TOML key is not named"
    assert "to regenerate" not in text, "a configuration error suggests regenerating"

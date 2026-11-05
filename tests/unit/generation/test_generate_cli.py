"""rp-generate: exit codes, the lint gate, atomic output and --check (PD-2, PD-18)."""

import sys
from pathlib import Path

import pytest

from rdf_persistence import generation
from rdf_persistence.generation import steps
from rdf_persistence.generation.cli import build_parser, main
from rdf_persistence.generation.config import read_targets
from rdf_persistence.generation.pipeline import Run, Step, StepError, generate

PYPROJECT = """
[tool.rp-generate]
schema = "m.yaml"
package = "app.generated"
"""

SCHEMA = """
id: https://example.org/ns/m
name: m
title: Module
description: A module for the tests.
prefixes:
  tst: https://example.org/ns/m#
  linkml: https://w3id.org/linkml/
default_prefix: tst
default_range: string
imports:
  - linkml:types
classes:
  Thing:
    title: Thing
    description: A thing.
    attributes:
      label:
        description: Its label.
"""

OUTPUT = Path("app/generated/m.py")


def project(tmp_path: Path, schema: str = SCHEMA, pyproject: str = PYPROJECT) -> Path:
    (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (tmp_path / "m.yaml").write_text(schema, encoding="utf-8")
    return tmp_path / "pyproject.toml"


def tree(root: Path) -> dict[Path, bytes]:
    return {p.relative_to(root): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_a_run_writes_the_classes_to_the_package_folder(tmp_path: Path) -> None:
    assert main(["--project", str(project(tmp_path))]) == 0, "the run failed"
    assert "class Thing(ConfiguredBaseModel)" in (tmp_path / OUTPUT).read_text(), "no class written"


def test_a_run_leaves_no_staging_folder_behind(tmp_path: Path) -> None:
    main(["--project", str(project(tmp_path))])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["app", "m.yaml", "pyproject.toml"]


def test_a_missing_extra_exits_2_naming_the_extra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in [
        m for m in sys.modules if m.startswith("linkml.")
    ]:  # a cached submodule would import
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "linkml", None)
    monkeypatch.delitem(sys.modules, "rdf_persistence.generation.steps")
    monkeypatch.delattr(generation, "steps")  # a from-import would find the attribute
    assert main(["--project", str(project(tmp_path))]) == 2, "wrong exit code"
    assert "install rdf-persistence[generate]" in capsys.readouterr().err, "no install hint"
    assert not (tmp_path / "app").exists(), "something was written"


def test_a_bad_configuration_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--project", str(tmp_path / "pyproject.toml")]) == 2, "wrong exit code"
    assert "no [tool.rp-generate]" in capsys.readouterr().err, "the problem was not named"


@pytest.mark.parametrize(
    ("rule", "break_schema", "element"),
    [
        ("recommended", lambda s: s.replace("    description: A thing.\n", ""), "Class 'Thing'"),
        ("standard_naming", lambda s: s.replace("Thing:", "thing_one:"), "'thing_one'"),
        (
            "canonical_prefixes",
            lambda s: s.replace("  linkml:", "  dct: http://purl.org/dc/terms/\n  linkml:"),
            "'dct'",
        ),
    ],
    ids=["recommended", "standard_naming", "canonical_prefixes"],
)
def test_a_raised_lint_rule_fails_the_run_and_names_the_element(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], rule: str, break_schema, element: str
) -> None:
    pyproject = project(tmp_path)
    (tmp_path / "m.yaml").write_text(break_schema(SCHEMA), encoding="utf-8")
    assert main(["--project", str(pyproject)]) == 1, f"{rule} did not fail the run"
    error = capsys.readouterr().err
    assert rule in error, f"the rule {rule} is not named"
    assert element in error, f"{element} is not named"


def test_every_raised_rule_has_a_row_in_the_table() -> None:
    assert set(steps.raised_rules()) == {"recommended", "standard_naming", "canonical_prefixes"}, (
        "the raised rules changed: give the new rule a row in the lint test table"
    )


def test_a_lint_problem_in_an_imported_module_fails_the_run(tmp_path: Path, capsys) -> None:
    pyproject = project(tmp_path, SCHEMA.replace("  - linkml:types", "  - linkml:types\n  - part"))
    (tmp_path / "part.yaml").write_text(
        SCHEMA.replace("name: m", "name: part")
        .replace("Thing:", "Part:")
        .replace("    description: A thing.\n", ""),
        encoding="utf-8",
    )
    assert main(["--project", str(pyproject)]) == 1, "the module's problem was ignored"
    assert "Class 'Part'" in capsys.readouterr().err, "the module's class is not named"


def test_a_failed_lint_leaves_the_previous_output_byte_identical(tmp_path: Path) -> None:
    pyproject = project(tmp_path)
    assert main(["--project", str(pyproject)]) == 0
    before = tree(tmp_path)
    (tmp_path / "m.yaml").write_text(SCHEMA.replace("Thing:", "thing_one:"), encoding="utf-8")
    broken = tree(tmp_path)
    assert main(["--project", str(pyproject)]) == 1
    assert tree(tmp_path) == broken, "a failed run changed a file"
    assert broken[OUTPUT] == before[OUTPUT], "the previous output was touched"


def write_then(outcome: Step) -> tuple[Step, ...]:
    def write(run: Run) -> None:
        run.staged(Path("app/generated/new.py")).write_text("new", encoding="utf-8")

    return (Step("write", write, writes=True), outcome)


def test_a_failure_after_a_write_moves_nothing_into_place(tmp_path: Path) -> None:

    pyproject = project(tmp_path)
    old = tmp_path / "app/generated/old.py"
    old.parent.mkdir(parents=True)
    old.write_text("old", encoding="utf-8")

    def fail(run: Run) -> None:
        raise StepError(["boom"])

    targets = read_targets(pyproject, build_parser().parse_args([]))
    problems = generate(targets, tmp_path, write_then(Step("fail", fail)), check=False)
    assert problems == ["m.yaml: fail: boom"], "the failure was not reported"
    assert tree(tmp_path / "app") == {Path("generated/old.py"): b"old"}, (
        "output moved before success"
    )


def test_a_successful_pipeline_moves_every_staged_file(tmp_path: Path) -> None:

    pyproject = project(tmp_path)
    ok = Step("ok", lambda run: None)
    targets = read_targets(pyproject, build_parser().parse_args([]))
    assert generate(targets, tmp_path, write_then(ok), check=False) == []
    assert (tmp_path / "app/generated/new.py").read_text() == "new", (
        "the staged file did not arrive"
    )


def test_check_writes_nothing(tmp_path: Path) -> None:
    pyproject = project(tmp_path)
    before = tree(tmp_path)
    assert main(["--project", str(pyproject), "--check"]) == 0, "a clean schema failed --check"
    assert tree(tmp_path) == before, "--check wrote files"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["m.yaml", "pyproject.toml"]


def test_check_fails_on_a_lint_problem(tmp_path: Path) -> None:
    pyproject = project(tmp_path, SCHEMA.replace("Thing:", "thing_one:"))
    assert main(["--project", str(pyproject), "--check"]) == 1, "--check ignored the lint"

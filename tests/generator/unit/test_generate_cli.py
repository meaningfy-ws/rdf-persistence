"""rp-generate: exit codes, the lint gate, atomic output and --check (PD-2, PD-18)."""

import importlib
import sys
from pathlib import Path

import linkml.linter.linter as linkml_linter
import pytest
from linkml_runtime.utils.schemaview import SchemaView

import rdf_persistence_generation as generation
from rdf_persistence.schema.services.schema import metamodel_importmap
from rdf_persistence_generation import steps
from rdf_persistence_generation.cli import build_parser, main
from rdf_persistence_generation.config import read_targets
from rdf_persistence_generation.exceptions import StepError
from rdf_persistence_generation.generated.rp_generation import CheckProblem
from rdf_persistence_generation.pipeline import Run, Step, generate
from tests.generator.unit.golden import SCHEMA, project

OUTPUT = Path("app/domain/generated/m.py")
PROJECT_FILES = ["app", "m.yaml", "migrations", "pyproject.toml"]  # what a run leaves in the folder


def tree(root: Path) -> dict[Path, bytes]:
    return {p.relative_to(root): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_a_run_writes_the_classes_to_the_package_folder(tmp_path: Path) -> None:
    assert main(["--project", str(project(tmp_path))]) == 0, "the run failed"
    assert "class Thing(Described, AggregateRoot)" in (tmp_path / OUTPUT).read_text(), (
        "no class written"
    )


def test_a_run_leaves_no_staging_folder_behind(tmp_path: Path) -> None:
    main(["--project", str(project(tmp_path))])
    assert sorted(p.name for p in tmp_path.iterdir()) == PROJECT_FILES, (
        "only the project files remain after a run"
    )


@pytest.fixture
def without_linkml(monkeypatch: pytest.MonkeyPatch) -> None:
    """``linkml`` cannot be imported and the pipeline's steps are not loaded."""
    for name in [
        m for m in sys.modules if m.startswith("linkml.")
    ]:  # a cached submodule would import
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "linkml", None)
    monkeypatch.delitem(sys.modules, "rdf_persistence_generation.steps")
    monkeypatch.delattr(generation, "steps")  # a from-import would find the attribute


@pytest.mark.usefixtures("without_linkml")
def test_a_missing_extra_exits_2_naming_the_extra(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--project", str(project(tmp_path))]) == 2, "wrong exit code"
    assert "install rdf-persistence[generate]" in capsys.readouterr().err, "no install hint"
    assert not (tmp_path / "app").exists(), "something was written"


@pytest.mark.usefixtures("without_linkml")
def test_listing_the_python_folders_needs_no_linkml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The flag writes nothing, so it works without the ``generate`` extra (issue #164)."""
    monkeypatch.chdir(tmp_path)
    assert main(["--project", str(project(tmp_path)), "--list-python-folders"]) == 0, (
        "the listing failed without linkml"
    )
    captured = capsys.readouterr()
    assert captured.out.split() == ["app/domain/generated"], captured.out
    assert "install rdf-persistence" not in captured.err, "the install hint was printed"
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
    assert main(["--project", str(pyproject)]) == 0, "the first run succeeds"
    before = tree(tmp_path)
    (tmp_path / "m.yaml").write_text(SCHEMA.replace("Thing:", "thing_one:"), encoding="utf-8")
    broken = tree(tmp_path)
    assert main(["--project", str(pyproject)]) == 1, "the run with a failed lint fails"
    assert tree(tmp_path) == broken, "a failed run changed a file"
    assert broken[OUTPUT] == before[OUTPUT], "the previous output was touched"


def write_then(outcome: Step) -> tuple[Step, ...]:
    def write(run: Run) -> None:
        run.staged(Path("app/domain/generated/new.py")).write_text("new", encoding="utf-8")

    return (Step("write", write, writes=True), outcome)


def test_a_failure_after_a_write_moves_nothing_into_place(tmp_path: Path) -> None:

    pyproject = project(tmp_path)
    old = tmp_path / "app/domain/generated/old.py"
    old.parent.mkdir(parents=True)
    old.write_text("old", encoding="utf-8")

    def fail(run: Run) -> None:
        raise StepError([CheckProblem(message="boom")])

    targets = read_targets(pyproject, build_parser().parse_args([]))
    problems = generate(targets, tmp_path, write_then(Step("fail", fail)), check=False)
    assert problems == [CheckProblem(schema_file="m.yaml", step="fail", message="boom")], (
        "the failure was not reported"
    )
    assert tree(tmp_path / "app") == {Path("domain/generated/old.py"): b"old"}, (
        "output moved before success"
    )


def test_a_successful_pipeline_moves_every_staged_file(tmp_path: Path) -> None:

    pyproject = project(tmp_path)
    ok = Step("ok", lambda run: None)
    targets = read_targets(pyproject, build_parser().parse_args([]))
    assert generate(targets, tmp_path, write_then(ok), check=False) == [], (
        "a successful pipeline reports no problems"
    )
    assert (tmp_path / "app/domain/generated/new.py").read_text() == "new", (
        "the staged file did not arrive"
    )


def test_check_writes_nothing(tmp_path: Path) -> None:
    pyproject = project(tmp_path)
    assert main(["--project", str(pyproject)]) == 0, "the project must generate"
    before = tree(tmp_path)
    assert main(["--project", str(pyproject), "--check"]) == 0, "a fresh project failed --check"
    assert tree(tmp_path) == before, "--check wrote files"
    assert sorted(p.name for p in tmp_path.iterdir()) == PROJECT_FILES, (
        "a check leaves only the project files"
    )


def test_check_fails_on_a_lint_problem(tmp_path: Path) -> None:
    pyproject = project(tmp_path, SCHEMA.replace("Thing:", "thing_one:"))
    assert main(["--project", str(pyproject), "--check"]) == 1, "--check ignored the lint"


def test_the_linter_patch_targets_a_name_linkml_still_has() -> None:
    """The lint step patches the SchemaView ``Linter`` looks up in its module (PD-22); if a linkml
    upgrade moves it, this fails by name instead of the lint silently losing the metamodel map."""
    module_name, _, attribute = steps.LINTER_SCHEMA_VIEW.rpartition(".")
    assert module_name == "linkml.linter.linter", "the patched module changed"
    assert attribute == "SchemaView", "the patched name changed"
    assert getattr(importlib.import_module(module_name), attribute) is SchemaView, (
        "linkml's Linter no longer builds its own SchemaView by that name"
    )


def test_inside_the_patch_the_linter_opens_schemas_through_the_metamodel_map() -> None:
    with steps.metamodel_aware_linter():
        view = linkml_linter.SchemaView("rdf_persistence/model/rp.yaml")
    assert view.importmap == metamodel_importmap(), "the linter would not find the metamodel"
    assert linkml_linter.SchemaView is SchemaView, "the patch was not undone"

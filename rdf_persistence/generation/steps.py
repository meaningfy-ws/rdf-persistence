"""The steps of the pipeline. Imports LinkML's generators, so it needs the ``generate`` extra (PD-2)."""

from collections.abc import Iterator
from functools import partial
from pathlib import Path
from unittest import mock

import yaml
from linkml.linter.linter import Linter
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.checks.boundary import boundary_problems
from rdf_persistence.generation.checks.hard import hard_problems
from rdf_persistence.generation.checks.rules import rules_problems
from rdf_persistence.generation.extensions.jsonld_context import CONTEXT_STEP
from rdf_persistence.generation.extensions.mermaid import DIAGRAMS_STEP
from rdf_persistence.generation.extensions.pydantic_split import render_modules
from rdf_persistence.generation.extensions.shacl import render_shapes
from rdf_persistence.generation.extensions.typescript import TYPESCRIPT_STEP
from rdf_persistence.generation.outputs import stage
from rdf_persistence.generation.pipeline import Run, Step, StepError
from rdf_persistence.services.schema import metamodel_importmap

LINT_CONFIG = Path(__file__).with_name("lint.yaml")


def raised_rules() -> tuple[str, ...]:
    """The lint rules the toolkit makes errors (the keys of ``lint.yaml``'s ``rules``)."""
    rules = yaml.safe_load(LINT_CONFIG.read_text(encoding="utf-8"))["rules"]
    return tuple(rule for rule, config in rules.items() if config["level"] == "error")


def _lint_files(run: Run) -> list[Path]:
    """The root schema and every module of its import closure kept beside it (not the metamodel's)."""
    folder = run.schema_path.parent
    modules = (
        Path(schema.source_file).resolve()
        for schema in run.view.schema_map.values()
        if schema.source_file
    )
    return [
        run.schema_path,
        *sorted(m for m in modules if m.parent == folder and m != run.schema_path),
    ]


def _lint_problems(path: Path) -> Iterator[str]:
    config = yaml.safe_load(LINT_CONFIG.read_text(encoding="utf-8"))
    # shortcut: the linter builds its own SchemaView, so give it the metamodel import map (PD-22);
    # upgrade when linkml's Linter accepts a SchemaView.
    with mock.patch(
        "linkml.linter.linter.SchemaView", partial(SchemaView, importmap=metamodel_importmap())
    ):
        for problem in Linter(config).lint(str(path)):
            if str(problem.level) != "error":
                continue  # warnings are not the toolkit's rules
            yield f"[{problem.rule_name}] {problem.message} ({Path(str(problem.schema_source)).name})"


def lint(run: Run) -> None:
    """Lint the schema and its modules with the raised rules; any problem fails the step."""
    problems = dict.fromkeys(p for path in _lint_files(run) for p in _lint_problems(path))
    if problems:
        raise StepError(list(problems))


def boundary_check(run: Run) -> None:
    """Fail on a part no root owns, a reference to a non-root, or a domain module importing another kind."""
    problems = boundary_problems(run.view, run.schema_path.parent)
    if problems:
        raise StepError(problems)


def hard_check(run: Run) -> None:
    """Fail on a missing IRI, title, description or meaning, a missing path or mixin, a bad annotation."""
    problems = hard_problems(run.view, run.schema_path.parent)
    if problems:
        raise StepError(problems)


def rules_check(run: Run) -> None:
    """Fail on a class that declares ``rules``, which v1 does not support (PD-24)."""
    problems = rules_problems(run.view)
    if problems:
        raise StepError(problems)


def python_classes(run: Run) -> None:
    """Generate one Python module per schema module with the split gen-pydantic (PD-19, PD-24)."""
    try:
        modules = render_modules(run.schema_path)
    except Exception as error:  # the generator raises whatever the schema makes it raise
        raise StepError([str(error)]) from error
    stage(run, run.python_dir, modules)


def shapes(run: Run) -> None:
    """Generate the closed SHACL shapes next to the Python output (PD-24)."""
    try:
        shapes_file = render_shapes(run.schema_path)
    except Exception as error:  # the generator raises whatever the schema makes it raise
        raise StepError([str(error)]) from error
    stage(run, run.python_dir, [shapes_file])


# One line per step; a later task adds its step here.
STEPS = (
    Step("lint", lint),
    Step("boundary check", boundary_check),
    Step("hard check", hard_check),
    Step("rules check", rules_check),
    Step("python", python_classes, writes=True),
    Step("shapes", shapes, writes=True),
    CONTEXT_STEP,
    TYPESCRIPT_STEP,
    DIAGRAMS_STEP,
)

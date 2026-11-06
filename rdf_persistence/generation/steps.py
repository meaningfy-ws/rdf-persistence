"""The steps of the pipeline. Imports LinkML's generators, so it needs the ``generate`` extra (PD-2)."""

import functools
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from unittest import mock

import yaml
from linkml.linter.config.datamodel.config import RuleLevel
from linkml.linter.linter import Linter
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation import components
from rdf_persistence.generation.checks.boundary import boundary_problems
from rdf_persistence.generation.checks.hard import hard_problems
from rdf_persistence.generation.checks.rules import rules_problems
from rdf_persistence.generation.extensions import (
    jsonld_context,
    mermaid,
    pydantic_split,
    shacl,
    typescript,
)
from rdf_persistence.generation.generated.rp_generation import CheckProblem
from rdf_persistence.generation.pipeline import Run, check_step, render_step
from rdf_persistence.services.schema import metamodel_importmap
from rdf_persistence.services.schema_structure import own_schemas

LINT_CONFIG = Path(__file__).with_name("lint.yaml")
# The name Linter looks its SchemaView up by; a test pins it so a linkml upgrade cannot break the patch silently.
LINTER_SCHEMA_VIEW = "linkml.linter.linter.SchemaView"


@functools.cache
def _lint_config() -> dict:
    """The raw ``lint.yaml``, which is the shape ``Linter`` takes."""
    config: dict = yaml.safe_load(LINT_CONFIG.read_text(encoding="utf-8"))
    return config


def raised_rules() -> tuple[str, ...]:
    """The lint rules the toolkit makes errors (the keys of ``lint.yaml``'s ``rules``)."""
    rules = _lint_config()["rules"]
    return tuple(
        rule for rule, config in rules.items() if RuleLevel(config["level"]) == RuleLevel.error
    )


def _lint_files(run: Run) -> list[Path]:
    """The root schema and every module of its import closure kept beside it (not the metamodel's)."""
    modules = {
        Path(str(schema.source_file)).resolve()
        for schema in own_schemas(run.view, run.schema_path.parent)
    }
    return [run.schema_path, *sorted(modules - {run.schema_path.resolve()})]


@contextmanager
def metamodel_aware_linter() -> Iterator[None]:
    """Within it, ``Linter`` opens schemas through the metamodel import map (PD-22).

    shortcut: the linter builds its own SchemaView, so it is patched; upgrade when linkml's Linter
    accepts a SchemaView.
    """
    with mock.patch(LINTER_SCHEMA_VIEW, partial(SchemaView, importmap=metamodel_importmap())):
        yield


def _lint_problems(path: Path) -> Iterator[CheckProblem]:
    with metamodel_aware_linter():
        for problem in Linter(_lint_config()).lint(str(path)):
            if problem.level != RuleLevel.error:
                continue  # warnings are not the toolkit's rules
            yield CheckProblem(
                rule=problem.rule_name,
                element=Path(str(problem.schema_source)).name,
                message=problem.message,
            )


def lint_problems(run: Run) -> list[CheckProblem]:
    """Lint the schema and its modules with the raised rules; a problem repeated by two files is listed once."""
    found = (p for path in _lint_files(run) for p in _lint_problems(path))
    return list({p.model_dump_json(): p for p in found}.values())


def _rules_problems(run: Run) -> list[CheckProblem]:
    return rules_problems(run.view)


def _boundary_problems(run: Run) -> list[CheckProblem]:
    return boundary_problems(run.view, run.schema_path.parent)


def _hard_problems(run: Run) -> list[CheckProblem]:
    return hard_problems(run.view, run.schema_path.parent)


def _python_folder(run: Run) -> Path:
    return run.python_dir


def _components_folder(run: Run) -> Path | None:
    return run.python_dir if run.target.openapi else None


def _typescript_folder(run: Run) -> Path | None:
    return Path(run.target.typescript) if run.target.typescript else None


def _diagrams_folder(run: Run) -> Path | None:
    return Path(run.target.diagrams) if run.target.diagrams else None


LINT_STEP = check_step("lint", lint_problems)
BOUNDARY_STEP = check_step("boundary check", _boundary_problems)
HARD_STEP = check_step("hard check", _hard_problems)
RULES_STEP = check_step("rules check", _rules_problems)
PYTHON_STEP = render_step("python", pydantic_split.render, _python_folder)
SHAPES_STEP = render_step("shapes", shacl.render, _python_folder)
CONTEXT_STEP = render_step("context", jsonld_context.render, _python_folder)
COMPONENTS_STEP = render_step("openapi components", components.render, _components_folder)
TYPESCRIPT_STEP = render_step("typescript", typescript.render, _typescript_folder)
DIAGRAMS_STEP = render_step("diagrams", mermaid.render, _diagrams_folder)

# One step per line, in order; a later task adds its step here.
STEPS = (
    LINT_STEP,
    BOUNDARY_STEP,
    HARD_STEP,
    RULES_STEP,
    PYTHON_STEP,
    SHAPES_STEP,
    CONTEXT_STEP,
    COMPONENTS_STEP,
    TYPESCRIPT_STEP,
    DIAGRAMS_STEP,
)

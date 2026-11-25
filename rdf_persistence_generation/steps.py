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

from rdf_persistence.schema.services.schema import load_schema, metamodel_importmap
from rdf_persistence.schema.services.schema_structure import (
    is_toolkit_schema,
    own_schemas,
    root_classes,
)
from rdf_persistence_generation import components
from rdf_persistence_generation.checks.boundary import (
    boundary_problems,
    derived_kind,
    kind_folder_problems,
    mixed_kind_problems,
)
from rdf_persistence_generation.checks.hard import hard_problems, stored_schema_problems
from rdf_persistence_generation.checks.python_package import python_package_problems
from rdf_persistence_generation.checks.rules import rules_problems
from rdf_persistence_generation.config import (
    METAMODEL_ROOT,
    PYPROJECT,
    migrations_folder,
    read_targets,
    toolkit_roots,
)
from rdf_persistence_generation.extensions import (
    jsonld_context,
    mermaid,
    pydantic_split,
    shacl,
    typescript,
)
from rdf_persistence_generation.generated.rp_generation import CheckProblem
from rdf_persistence_generation.lock_step import lock_problems, write_lock
from rdf_persistence_generation.pipeline import (
    Run,
    Step,
    check_step,
    render_step,
    schema_faults,
    stage,
)

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
    folder = run.schema_path.parent
    mixed = mixed_kind_problems(
        run.view, folder
    )  # a mixed target gets no folder problem: its hint would mislead
    return [
        *boundary_problems(run.view, folder),
        *(
            mixed
            or kind_folder_problems(
                folder, run.target.package, derived_kind(run.view, folder), run.view
            )
        ),
    ]


def _toolkit_packages(run: Run) -> tuple[str, ...]:
    """The packages of the toolkit's own targets, from its ``pyproject.toml``; none on an application's run (PD-3)."""
    project = run.base / PYPROJECT
    if (
        not is_toolkit_schema(run.schema_path.parent, roots=toolkit_roots())
        or not project.is_file()
    ):
        return ()
    return tuple(target.package for target in read_targets(project))


def _root_names(view: SchemaView, folder: Path) -> set[str]:
    return {cls.name for cls in root_classes(view, folder)}


def _metamodel_root_names(run: Run) -> set[str]:
    """The root classes checked on ``rp.yaml``'s target: those of its closure, found through the toolkit's targets."""
    for target in read_targets(run.base / PYPROJECT):
        if Path(target.schema_file).name == METAMODEL_ROOT:
            path = run.base / target.schema_file
            return _root_names(load_schema(path), path.parent)
    return set()


def _stores_its_roots_here(run: Run) -> bool:
    """Whether the stored-schema rules apply to this target: all but a toolkit target whose roots ``rp.yaml`` checks (PD-4, D-5).

    On the toolkit's run, ``rp.yaml`` holds every domain module, so its target answers for every
    root class and writes the one lock; a theme target declares no ``migrations``. A toolkit target
    with a root of its own, or one that sets ``migrations`` (its version is checked, D-10), keeps
    the rules.
    """
    folder = run.schema_path.parent
    if (
        not is_toolkit_schema(folder, roots=toolkit_roots())
        or run.schema_path.name == METAMODEL_ROOT
    ):
        return True
    if migrations_folder(run.target):
        return True
    roots = _root_names(run.view, folder)
    return not roots or not roots <= _metamodel_root_names(run)


def _hard_problems(run: Run) -> list[CheckProblem]:
    folder = run.schema_path.parent
    stored = (
        stored_schema_problems(run.view, folder, migrations_folder(run.target))
        if _stores_its_roots_here(run)
        else []
    )
    return [
        *hard_problems(run.view, folder),
        *stored,
        *python_package_problems(run.view, folder, run.target.package, _toolkit_packages(run)),
    ]


def _python_folder(run: Run) -> Path:
    return run.python_dir


def _components_folder(run: Run) -> Path | None:
    return run.python_dir if run.target.openapi else None


def _typescript_folder(run: Run) -> Path | None:
    return Path(run.target.typescript) if run.target.typescript else None


def _typescript_owners(run: Run) -> dict[str, Path]:
    """The folder of each other target of the project that writes TypeScript, by its package (PD-1).

    A flags-only run has no ``pyproject.toml`` and so no owner: every module is copied.
    """
    project = run.base / PYPROJECT
    if not project.is_file():
        return {}
    return {
        target.package: Path(target.typescript)
        for target in read_targets(project)
        if target.typescript and target.package != run.target.package
    }


def _write_typescript(run: Run) -> None:
    """Stage the TypeScript types, importing the modules another target of the project writes (PD-2)."""
    folder = _typescript_folder(run)
    if folder is None:
        return
    with schema_faults():
        files = typescript.render(run.schema_path, folder=folder, owners=_typescript_owners(run))
    stage(run, folder, files)


def _diagrams_folder(run: Run) -> Path | None:
    return Path(run.target.diagrams) if run.target.diagrams else None


LINT_STEP = check_step("lint", lint_problems)
BOUNDARY_STEP = check_step("boundary check", _boundary_problems)
HARD_STEP = check_step("hard check", _hard_problems)
RULES_STEP = check_step("rules check", _rules_problems)
LOCK_CHECK_STEP = check_step("lock check", lock_problems)
PYTHON_STEP = render_step("python", pydantic_split.render, _python_folder)
SHAPES_STEP = render_step("shapes", shacl.render, _python_folder)
CONTEXT_STEP = render_step("context", jsonld_context.render, _python_folder)
COMPONENTS_STEP = render_step("openapi components", components.render, _components_folder)
TYPESCRIPT_STEP = Step("typescript", _write_typescript, writes=True)
DIAGRAMS_STEP = render_step("diagrams", mermaid.render, _diagrams_folder)
# Last, so a draft is never written by a run whose earlier steps of the target failed.
LOCK_STEP = Step("lock", write_lock, writes=True)

# One step per line, in order; a later task adds its step here.
STEPS = (
    LINT_STEP,
    BOUNDARY_STEP,
    HARD_STEP,
    RULES_STEP,
    LOCK_CHECK_STEP,
    PYTHON_STEP,
    SHAPES_STEP,
    CONTEXT_STEP,
    COMPONENTS_STEP,
    TYPESCRIPT_STEP,
    DIAGRAMS_STEP,
    LOCK_STEP,
)

"""The steps of the pipeline. Imports LinkML's generators, so it needs the ``generate`` extra (PD-2)."""

from collections.abc import Iterator
from functools import partial
from pathlib import Path
from unittest import mock

import yaml
from linkml.generators.pydanticgen import PydanticGenerator
from linkml.generators.pydanticgen.pydanticgen import MetadataMode
from linkml.linter.linter import Linter
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.pipeline import Run, Step, StepError
from rdf_persistence.services.schema import metamodel_importmap

LINT_CONFIG = Path(__file__).with_name("lint.yaml")
TEMPLATE_DIR = Path(__file__).with_name("templates") / "pydantic"


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


def python_classes(run: Run) -> None:
    """Generate the schema's classes with gen-pydantic and the toolkit's base template (PD-19, PD-24)."""
    try:
        generator = PydanticGenerator(
            str(run.schema_path),
            importmap=metamodel_importmap(),
            template_dir=TEMPLATE_DIR,
            metadata_mode=MetadataMode.NONE,
            emit_metadata=False,
        )
        source = generator.serialize()
    except Exception as error:  # the generator raises whatever the schema makes it raise
        raise StepError([str(error)]) from error
    run.staged(run.python_dir / f"{run.schema_path.stem}.py").write_text(source, encoding="utf-8")


# One line per step; a later task adds its step here.
STEPS = (
    Step("lint", lint),
    Step("python", python_classes, writes=True),
)

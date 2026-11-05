"""Run the generation steps over each target, writing to a staging folder moved into place on success."""

import os
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.generated.rp_generation import GenerationTarget
from rdf_persistence.services.schema import load_schema

STAGING_PREFIX = ".rp-generate-"


class StepError(Exception):
    """A step found problems; each is one line to show the developer."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


@dataclass
class Run:
    """What a step works on: one target, its loaded schema and the staging folder to write into."""

    target: GenerationTarget
    base: Path
    staging: Path
    view: SchemaView

    @property
    def schema_path(self) -> Path:
        return self.base / self.target.schema_file

    @property
    def python_dir(self) -> Path:
        """The Python output folder, relative to ``base``."""
        return Path(self.target.python or self.target.package.replace(".", "/"))

    def staged(self, relative: Path) -> Path:
        """The staging path of the output file ``relative`` to ``base``; its folder exists."""
        path = self.staging / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


@dataclass(frozen=True)
class Step:
    """One stage of the pipeline; a ``writes`` step produces output, so ``--check`` skips it."""

    name: str
    run: Callable[[Run], None]
    writes: bool = False


def _run_target(
    target: GenerationTarget, base: Path, staging: Path, steps: Sequence[Step]
) -> list[str]:
    try:
        view = load_schema(base / target.schema_file)
        view.imports_closure()
    except Exception as error:  # the loader raises whatever the YAML or an import raises
        return [f"{target.schema_file}: load: {error}"]
    run = Run(target, base, staging, view)
    for step in steps:
        try:
            step.run(run)
        except StepError as failed:
            return [f"{target.schema_file}: {step.name}: {problem}" for problem in failed.problems]
    return []


def _move_into_place(staging: Path, base: Path) -> None:
    for staged in sorted(p for p in staging.rglob("*") if p.is_file()):
        destination = base / staged.relative_to(staging)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, destination)


def generate(
    targets: Sequence[GenerationTarget], base: Path, steps: Sequence[Step], *, check: bool
) -> list[str]:
    """Run ``steps`` over every target; move all output into place only if nothing failed.

    Args:
        targets: The targets, in order; paths are relative to ``base``.
        base: The folder of the ``pyproject.toml``.
        steps: The pipeline, in order.
        check: Run only the steps that write nothing, and move nothing.

    Returns:
        The problems found, one line each; empty when the run succeeded.
    """
    selected = [step for step in steps if not (check and step.writes)]
    with tempfile.TemporaryDirectory(dir=base, prefix=STAGING_PREFIX) as folder:
        staging = Path(folder)
        problems = [p for target in targets for p in _run_target(target, base, staging, selected)]
        if not problems and not check:
            _move_into_place(staging, base)
    return problems

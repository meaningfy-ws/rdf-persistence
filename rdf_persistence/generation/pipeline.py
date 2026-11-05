"""Run the generation steps over each target, writing to a staging folder moved into place on success."""

import os
import tempfile
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation import manifest
from rdf_persistence.generation.config import python_folder
from rdf_persistence.generation.exceptions import SchemaGenerationError, StepError
from rdf_persistence.generation.generated.rp_generation import (
    CheckProblem,
    GeneratedFile,
    GenerationTarget,
    ManifestEntry,
)
from rdf_persistence.services.schema import LOAD_ERRORS, load_schema

STAGING_PREFIX = ".rp-generate-"


@contextmanager
def schema_faults() -> Iterator[None]:
    """Report a ``SchemaGenerationError`` raised inside the block as a ``StepError``; any other exception is a bug and passes.

    Load errors are reported only where the schema is loaded (``_run_target``), never around a step.
    """
    try:
        yield
    except SchemaGenerationError as error:
        raise StepError([CheckProblem(message=str(error))]) from error


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
        return python_folder(self.target)

    def staged(self, relative: Path) -> Path:
        """The staging path of the output file ``relative`` to ``base``; its folder exists.

        Raises:
            StepError: When the path would leave the staging folder.
        """
        path = self.staging / relative
        if not path.resolve().is_relative_to(self.staging.resolve()):
            raise StepError(
                [CheckProblem(element=str(relative), message="outside the staging folder")]
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


@dataclass(frozen=True)
class Step:
    """One stage of the pipeline; a ``writes`` step produces output, so ``--check`` skips it."""

    name: str
    run: Callable[[Run], None]
    writes: bool = False


def stage(run: Run, folder: Path, files: Iterable[GeneratedFile]) -> None:
    """Write ``files`` into ``folder`` (relative to the run's ``base``) in the staging area.

    Raises:
        StepError: When a name, which may come from the schema, is not a plain file name.
    """
    for file in files:
        if file.name in ("", ".", "..") or "/" in file.name or "\\" in file.name:
            problem = CheckProblem(
                element=repr(file.name), message="an output name must be a plain file name"
            )
            raise StepError([problem])
        run.staged(folder / file.name).write_text(file.text, encoding="utf-8")


def check_step(name: str, find: Callable[[Run], list[CheckProblem]]) -> Step:
    """A step that writes nothing and fails with whatever ``find`` returns."""

    def check(run: Run) -> None:
        if problems := find(run):
            raise StepError(problems)

    return Step(name, check)


def render_step(
    name: str,
    render: Callable[[Path], list[GeneratedFile]],
    folder_of: Callable[[Run], Path | None],
) -> Step:
    """A step that stages what ``render`` makes from the target's schema into ``folder_of(run)``.

    A schema fault in ``render`` is a step failure; ``folder_of`` returning ``None`` means the
    target asks for none of this step's output.
    """

    def write(run: Run) -> None:
        folder = folder_of(run)
        if folder is None:
            return
        with schema_faults():
            files = render(run.schema_path)
        stage(run, folder, files)

    return Step(name, write, writes=True)


def _run_target(
    target: GenerationTarget, base: Path, staging: Path, steps: Sequence[Step]
) -> list[CheckProblem]:
    try:
        view = load_schema(base / target.schema_file)
        view.imports_closure()
    except LOAD_ERRORS as error:
        return [CheckProblem(schema_file=target.schema_file, step="load", message=str(error))]
    run = Run(target, base, staging, view)
    for step in steps:
        try:
            step.run(run)
        except StepError as failed:
            return [
                problem.model_copy(update={"schema_file": target.schema_file, "step": step.name})
                for problem in failed.problems
            ]
    return []


def _move_into_place(staging: Path, base: Path) -> list[Path]:
    """Move every staged file to its place under ``base``; return the places."""
    moved = []
    for staged in sorted(p for p in staging.rglob("*") if p.is_file()):
        destination = base / staged.relative_to(staging)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, destination)
        moved.append(destination)
    return moved


def _remove_stale(entry: ManifestEntry, base: Path) -> CheckProblem | None:
    """Delete the file a previous run wrote and this one does not; return why it was kept, if it was.

    The manifest is data on disk, so nothing in it is trusted: a file goes only if it lies under
    ``base`` after links are followed and still has the hash the previous run recorded.
    """
    file = base / entry.path
    if not file.resolve().is_relative_to(base.resolve()):
        return CheckProblem(message=f"kept {entry.path}: it resolves outside the project")
    if not file.is_file():
        return None
    if manifest.sha256_of(file) != entry.sha256:
        return CheckProblem(
            message=f"kept {entry.path}: it changed since it was generated; delete it if it is stale"
        )
    file.unlink()
    return None


def _publish(target: GenerationTarget, base: Path, staging: Path) -> list[CheckProblem]:
    """Move ``target``'s output into place, delete what its previous run wrote and no longer does, write the manifest.

    Returns:
        One line for each stale file that was kept, and why.
    """
    previous = manifest.read_manifest(target, base)
    written = _move_into_place(staging, base)
    kept = {manifest.recorded_path(f, base) for f in written}
    stale = [e for e in (previous.outputs or [] if previous else []) if e.path not in kept]
    problems = [p for e in stale if (p := _remove_stale(e, base))]
    manifest.write_manifest(target, base, manifest.build_manifest(target, base, written))
    return problems


def _run_targets(
    targets: Sequence[GenerationTarget], base: Path, stagings: Sequence[Path], steps: Sequence[Step]
) -> list[CheckProblem]:
    results = (
        _run_target(target, base, staging, steps)
        for target, staging in zip(targets, stagings, strict=True)
    )
    return [problem for result in results for problem in result]


def _publish_all(
    targets: Sequence[GenerationTarget], base: Path, stagings: Sequence[Path]
) -> list[CheckProblem]:
    kept = (
        _publish(target, base, staging) for target, staging in zip(targets, stagings, strict=True)
    )
    return [problem for result in kept for problem in result]


def _unusable_manifests(targets: Sequence[GenerationTarget], base: Path) -> list[CheckProblem]:
    return [p for t in targets if (p := manifest.unreadable_manifest(t, base))]


def generate(
    targets: Sequence[GenerationTarget], base: Path, steps: Sequence[Step], *, check: bool
) -> list[CheckProblem]:
    """Run ``steps`` over every target; move all output into place only if nothing failed.

    A run writes one manifest per target and deletes only the files the target's previous manifest
    listed (PD-26).

    Args:
        targets: The targets, in order; paths are relative to ``base``.
        base: The folder of the ``pyproject.toml``.
        steps: The pipeline, in order.
        check: Run only the steps that write nothing, and move nothing.

    Returns:
        The problems found, one line each; empty when the run succeeded. A stale file kept after
        the move is a problem too, though the new output is already in place.
    """
    if not check and (unusable := _unusable_manifests(targets, base)):
        return unusable
    selected = [step for step in steps if not (check and step.writes)]
    with tempfile.TemporaryDirectory(dir=base, prefix=STAGING_PREFIX) as folder:
        stagings = [Path(folder) / str(index) for index, _ in enumerate(targets)]
        problems = _run_targets(targets, base, stagings, selected)
        if not problems and not check:
            problems = _publish_all(targets, base, stagings)
    return problems

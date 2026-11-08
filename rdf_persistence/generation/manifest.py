"""The generation manifest and the freshness comparison (PD-26). Needs only ``linkml-runtime``."""

import hashlib
import os
from collections.abc import Iterable, Iterator
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pydantic import ValidationError

from rdf_persistence.generation.config import python_folder
from rdf_persistence.generation.generated.rp_generation import (
    CheckProblem,
    GenerationManifest,
    GenerationTarget,
    ManifestEntry,
)
from rdf_persistence.services.schema import LOAD_ERRORS, PACKAGE, PACKAGE_DIR, load_schema

MANIFEST_NAME = "rp-manifest.json"
DEFAULT_REGENERATE = "rp-generate"
GENERATION_DIR = PACKAGE_DIR / "generation"
GENERATED_DIR = GENERATION_DIR / "generated"
TEMPLATES_DIR = GENERATION_DIR / "templates"
SERVICES_DIR = PACKAGE_DIR / "services"
SCHEMA_READERS = "schema*.py"  # the modules that decide how a schema is read (PD-26)
LINKML_TYPES_PREFIX = "linkml:"


def linkml_version() -> str | None:
    """The installed ``linkml`` version, or ``None`` without the ``generate`` extra."""
    try:
        return version("linkml")
    except PackageNotFoundError:
        return None


def sha256_of(path: Path) -> str:
    """The SHA-256 of the file's raw bytes, in hexadecimal."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_path(target: GenerationTarget, base: Path) -> Path:
    """Where the manifest of ``target`` lives: its Python folder."""
    return base / python_folder(target) / MANIFEST_NAME


def recorded_path(file: Path, base: Path) -> str:
    """The POSIX path recorded for ``file``: ``rdf_persistence/...`` inside the package, else from ``base``."""
    file = file.resolve()
    if file.is_relative_to(PACKAGE_DIR):
        return f"{PACKAGE}/{file.relative_to(PACKAGE_DIR).as_posix()}"
    return Path(os.path.relpath(file, base.resolve())).as_posix()


def _toolkit_files() -> Iterator[Path]:
    yield from SERVICES_DIR.glob(SCHEMA_READERS)
    for module in GENERATION_DIR.rglob("*.py"):
        if not module.is_relative_to(GENERATED_DIR):
            yield module
    yield from (p for p in TEMPLATES_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def _schema_files(target: GenerationTarget, base: Path) -> Iterator[Path]:
    view = load_schema(base / target.schema_file)
    for name in view.imports_closure():
        schema = view.schema_map.get(name)
        if schema is not None and schema.source_file and not name.startswith(LINKML_TYPES_PREFIX):
            yield Path(schema.source_file)


def _entries(files: Iterable[Path], base: Path) -> list[ManifestEntry]:
    by_path = {recorded_path(f, base): f for f in files}
    return [ManifestEntry(path=p, sha256=sha256_of(by_path[p])) for p in sorted(by_path)]


def current_inputs(target: GenerationTarget, base: Path) -> list[ManifestEntry]:
    """The inputs of ``target`` as they are now, sorted by path."""
    return _entries([*_schema_files(target, base), *_toolkit_files()], base)


def build_manifest(
    target: GenerationTarget, base: Path, outputs: Iterable[Path]
) -> GenerationManifest:
    """The manifest of a run that wrote ``outputs`` (absolute paths; never the manifest itself)."""
    return GenerationManifest(
        linkml=linkml_version() or "",
        inputs=current_inputs(target, base),
        outputs=_entries(outputs, base),
    )


def write_manifest(target: GenerationTarget, base: Path, manifest: GenerationManifest) -> None:
    manifest_path(target, base).write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )


def read_manifest(target: GenerationTarget, base: Path) -> GenerationManifest | None:
    """The manifest of ``target``'s previous run; ``None`` when absent or unreadable."""
    path = manifest_path(target, base)
    try:
        return GenerationManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError):
        return None


def unreadable_manifest(target: GenerationTarget, base: Path) -> CheckProblem | None:
    """Why the manifest of ``target``'s previous run cannot be trusted; ``None`` when absent or valid."""
    path = manifest_path(target, base)
    if not path.is_file():
        return None
    try:
        GenerationManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError as error:
        return CheckProblem(
            element=recorded_path(path, base),
            message=f"cannot be read ({error}); fix it or delete it",
        )
    except ValidationError as error:
        fields = sorted({".".join(str(part) for part in e["loc"]) for e in error.errors()})
        return CheckProblem(
            element=recorded_path(path, base),
            message=f"invalid {', '.join(fields)}; delete it and run again",
        )
    return None


def _input_problems(
    target: GenerationTarget, base: Path, recorded: GenerationManifest
) -> Iterator[CheckProblem]:
    try:
        now = {e.path: e.sha256 for e in current_inputs(target, base)}
    except LOAD_ERRORS as error:
        yield CheckProblem(message=f"stale input: {target.schema_file} cannot be read: {error}")
        return
    before = {e.path: e.sha256 for e in recorded.inputs or []}
    for path in sorted(before.keys() | now.keys()):
        if before.get(path) != now.get(path):
            state = "removed" if path not in now else "new" if path not in before else "changed"
            yield CheckProblem(message=f"stale input: {path} ({state})")


def _output_problems(base: Path, recorded: GenerationManifest) -> Iterator[CheckProblem]:
    for entry in recorded.outputs or []:
        file = base / entry.path
        if not file.is_file():
            yield CheckProblem(message=f"missing output: {entry.path}")
        elif sha256_of(file) != entry.sha256:
            yield CheckProblem(message=f"edited by hand: {entry.path}")


def _target_problems(target: GenerationTarget, base: Path) -> Iterator[CheckProblem]:
    recorded = read_manifest(target, base)
    if recorded is None:
        yield CheckProblem(
            message=f"no readable manifest: {recorded_path(manifest_path(target, base), base)}"
        )
        return
    installed = linkml_version()
    if installed is not None and installed != recorded.linkml:
        yield CheckProblem(
            message=f"stale: generated with linkml {recorded.linkml}, installed is {installed}"
        )
    yield from _input_problems(target, base, recorded)
    yield from _output_problems(base, recorded)


def stale_targets(
    targets: Iterable[GenerationTarget], base: Path
) -> list[tuple[GenerationTarget, list[CheckProblem]]]:
    """Each target with a stale, edited or missing file, with one problem line per such file."""
    pairs = ((target, list(_target_problems(target, base))) for target in targets)
    return [(target, problems) for target, problems in pairs if problems]


def freshness_problems(targets: Iterable[GenerationTarget], base: Path) -> list[CheckProblem]:
    """Compare every target's manifest with the files now; one line per stale, edited or missing file."""
    return [problem for _, problems in stale_targets(targets, base) for problem in problems]


def fix_hint(stale: Iterable[GenerationTarget]) -> str:
    """The hint that ends a failed check: the command of each stale target, once, in order."""
    commands = dict.fromkeys(t.regenerate_command or DEFAULT_REGENERATE for t in stale)
    return f"run {' or '.join(f'`{c}`' for c in commands)} to regenerate, then commit the result"

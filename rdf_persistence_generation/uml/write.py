"""Writing the converted schemas and the report beside them (PD-22, I-2).

The files are dumped into a temporary folder inside ``out`` and moved into place, the report
last (PD-3). The only file deleted is the previous report. A ``<root>_*.yaml`` this run did not
write, and a staging folder a killed run left, are reported as ``stale-file``, never deleted. The other files the conversion draws (PD-8) are staged with them and
checked by the library's loader before anything is moved (PD-4); a file it refuses moves nothing.
"""

import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from linkml_runtime.dumpers import yaml_dumper
from linkml_runtime.linkml_model.meta import SchemaDefinition

from rdf_persistence.access.services.access import load_role_definitions
from rdf_persistence.collaboration.services.workflows import load_workflow
from rdf_persistence.core.domain.exceptions import InvalidRoleDefinition, InvalidWorkflow
from rdf_persistence_generation.exceptions import OutputError, StagedFileRefused
from rdf_persistence_generation.generated.rp_generation import ReportKind, ReportLine
from rdf_persistence_generation.uml.roles import ROLES_SUFFIX
from rdf_persistence_generation.uml.workflows import WORKFLOWS_FOLDER, WORKFLOWS_SUFFIX

REPORT_SUFFIX = ".uml-report.txt"
SCHEMA_SUFFIX = ".yaml"
STAGING_PREFIX = ".uml-write-"
FIELD_SEPARATOR = "\t"


def report_text(report: Sequence[ReportLine]) -> str:
    """One ``<kind>\\t<element>\\t<message>`` line per item, sorted, kinds with ``-`` for ``_``."""
    lines = sorted(
        FIELD_SEPARATOR.join(
            (ReportKind(line.report_kind).value.replace("_", "-"), line.element, line.message)
        )
        for line in report
    )
    return "".join(f"{line}\n" for line in lines)


def _stale_in(out: Path, pattern: str, written: set[str]) -> list[ReportLine]:
    """The files matching ``pattern`` that this run did not write, named by their path relative to ``out``."""
    found = (
        file.relative_to(out).as_posix() for file in sorted(out.glob(pattern)) if file.is_file()
    )
    return [
        ReportLine(
            report_kind=ReportKind.STALE_FILE,
            element=name,
            message="kept: this run did not write it",
        )
        for name in found
        if name not in written
    ]


def _stale_files(
    out: Path, root_name: str, written: set[str], files: Mapping[str, str]
) -> list[ReportLine]:
    """The schemas this run did not write; the roles and workflow files only when this run draws one (PD-4)."""
    stale = _stale_in(out, f"{root_name}_*{SCHEMA_SUFFIX}", written)
    if any(name.endswith(ROLES_SUFFIX) for name in files):
        stale += _stale_in(out, f"*{ROLES_SUFFIX}", set(files))
    if any(name.endswith(WORKFLOWS_SUFFIX) for name in files):
        stale += _stale_in(out, f"{WORKFLOWS_FOLDER}*{WORKFLOWS_SUFFIX}", set(files))
    return stale


def _check_staged(staging: Path, files: Mapping[str, str]) -> None:
    """Read each staged file with the library's loader; a refusal is the conversion's miss (PD-4)."""
    for name in sorted(files):
        try:
            _load(staging / name)
        except (InvalidRoleDefinition, InvalidWorkflow) as error:
            raise StagedFileRefused(str(error)) from error


def _load(path: Path) -> None:
    if path.name.endswith(ROLES_SUFFIX):
        load_role_definitions(path)
    elif path.name.endswith(WORKFLOWS_SUFFIX):
        load_workflow(path)


def _stage(staging: Path, files: Mapping[str, str]) -> None:
    for name, text in files.items():
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def _left_staging(out: Path) -> list[ReportLine]:
    """The staging folders a killed run left in ``out``: reported, never deleted (another run may own one)."""
    return [
        ReportLine(
            report_kind=ReportKind.STALE_FILE,
            element=folder.name,
            message="left by an interrupted run; delete it",
        )
        for folder in sorted(out.glob(f"{STAGING_PREFIX}*"))
        if folder.is_dir()
    ]


def _move(staging: Path, out: Path, report_name: str, move: Callable[[Path, Path], None]) -> None:
    """Move every staged file into ``out`` in path order, the report last.

    A folder in ``out`` may hold the consumer's other files, so files move one by one. An
    ``OSError`` is re-raised naming the target, as the real move names the staged source.
    """
    staged_files = sorted(file for file in staging.rglob("*") if file.is_file())
    report = [file for file in staged_files if file.name == report_name and file.parent == staging]
    others = [file for file in staged_files if file not in report]
    for staged in [*others, *report]:
        target = out / staged.relative_to(staging)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            move(staged, target)
        except OSError as error:
            raise OSError(error.errno, error.strerror, str(target)) from error


def write(  # noqa: PLR0913 - the injected move (PD-3) is the sixth input; the others are the run's
    schemas: Sequence[SchemaDefinition],
    report: Sequence[ReportLine],
    out: Path,
    root_name: str,
    files: Mapping[str, str] | None = None,
    move: Callable[[Path, Path], None] = os.replace,
) -> list[ReportLine]:
    """Write each schema as ``<out>/<name>.yaml`` and the report; return the report lines added.

    Args:
        schemas: The converted schemas; each is written under its ``name``.
        report: The conversion's report lines.
        out: The output folder, created if missing.
        root_name: The root module's name: the report is ``<root_name>.uml-report.txt`` and the
            files ``<root_name>_*.yaml`` this run did not write are reported, not deleted.
        files: The other files, a path relative to ``out`` to its text (PD-8); a ``*.roles.yaml``
            or ``workflows/*.workflow.yaml`` is read with the library's loader before anything is
            moved, and the files are moved one by one, so a folder in ``out`` keeps its other files.

    Returns:
        The lines this function added to the report (``stale-file``), already in the written file.

    Raises:
        StagedFileRefused: The loader refuses a staged file; nothing was moved.
        OutputError: A disk or folder error anywhere; ``path`` is the file it named, else ``out``.
            The staging folder is removed; the old report is deleted before the moves and the
            new one moved last, so an interrupted write leaves no report in ``out``.

    The staging folder is made inside ``out`` (the same filesystem as the targets). A folder a
    killed run left there is reported as ``stale-file``, never deleted.
    """
    files = files or {}
    names = {f"{schema.name}{SCHEMA_SUFFIX}" for schema in schemas}
    report_name = f"{root_name}{REPORT_SUFFIX}"
    try:
        out.mkdir(parents=True, exist_ok=True)
        added = [*_stale_files(out, root_name, names, files), *_left_staging(out)]
        with tempfile.TemporaryDirectory(dir=out, prefix=STAGING_PREFIX) as folder:
            staging = Path(folder)
            for schema in schemas:
                yaml_dumper.dump(schema, str(staging / f"{schema.name}{SCHEMA_SUFFIX}"))
            _stage(staging, files)
            _check_staged(staging, files)
            (staging / report_name).write_text(report_text([*report, *added]), encoding="utf-8")
            (out / report_name).unlink(missing_ok=True)
            _move(staging, out, report_name, move)
    except OSError as error:
        raise OutputError(
            Path(error.filename) if error.filename else out, error.strerror or str(error)
        ) from error
    return added

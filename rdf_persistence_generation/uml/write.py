"""Writing the converted schemas and the report beside them (PD-22, I-2).

The files are dumped into a temporary folder beside ``out`` and moved into place with
``os.replace``. Nothing in ``out`` is deleted: a ``<root>_*.yaml`` this run did not write is
reported as ``stale-file``. The other files the conversion draws (PD-8) are staged with them and
checked by the library's loader before anything is moved (PD-4); a file it refuses moves nothing.
"""

import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from linkml_runtime.dumpers import yaml_dumper
from linkml_runtime.linkml_model.meta import SchemaDefinition

from rdf_persistence.access.services.access import load_role_definitions
from rdf_persistence.collaboration.services.workflows import load_workflow
from rdf_persistence.core.domain.exceptions import InvalidRoleDefinition, InvalidWorkflow
from rdf_persistence_generation.exceptions import StagedFileRefused
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


def _move(staging: Path, out: Path) -> None:
    """Move every staged file into ``out``, one by one: a folder in ``out`` may hold the consumer's other files."""
    for staged in sorted(file for file in staging.rglob("*") if file.is_file()):
        target = out / staged.relative_to(staging)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, target)


def write(
    schemas: Sequence[SchemaDefinition],
    report: Sequence[ReportLine],
    out: Path,
    root_name: str,
    files: Mapping[str, str] | None = None,
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
    """
    out.mkdir(parents=True, exist_ok=True)
    files = files or {}
    names = {f"{schema.name}{SCHEMA_SUFFIX}" for schema in schemas}
    added = _stale_files(out, root_name, names, files)
    with tempfile.TemporaryDirectory(dir=out.parent, prefix=STAGING_PREFIX) as folder:
        staging = Path(folder)
        for schema in schemas:
            yaml_dumper.dump(schema, str(staging / f"{schema.name}{SCHEMA_SUFFIX}"))
        _stage(staging, files)
        _check_staged(staging, files)
        (staging / f"{root_name}{REPORT_SUFFIX}").write_text(
            report_text([*report, *added]), encoding="utf-8"
        )
        _move(staging, out)
    return added

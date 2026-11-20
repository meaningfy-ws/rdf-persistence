"""Writing the converted schemas and the report beside them (PD-22, I-2).

The files are dumped into a temporary folder beside ``out`` and moved into place with
``os.replace``. Nothing in ``out`` is deleted: a ``<root>_*.yaml`` this run did not write is
reported as ``stale-file``.
"""

import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

from linkml_runtime.dumpers import yaml_dumper
from linkml_runtime.linkml_model.meta import SchemaDefinition

from rdf_persistence_generation.generated.rp_generation import ReportKind, ReportLine

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


def _stale_files(out: Path, root_name: str, written: set[str]) -> list[ReportLine]:
    pattern = f"{root_name}_*{SCHEMA_SUFFIX}"
    return [
        ReportLine(
            report_kind=ReportKind.STALE_FILE,
            element=file.name,
            message="kept: this run did not write it",
        )
        for file in sorted(out.glob(pattern))
        if file.is_file() and file.name not in written
    ]


def write(
    schemas: Sequence[SchemaDefinition],
    report: Sequence[ReportLine],
    out: Path,
    root_name: str,
) -> list[ReportLine]:
    """Write each schema as ``<out>/<name>.yaml`` and the report; return the report lines added.

    Args:
        schemas: The converted schemas; each is written under its ``name``.
        report: The conversion's report lines.
        out: The output folder, created if missing.
        root_name: The root module's name: the report is ``<root_name>.uml-report.txt`` and the
            files ``<root_name>_*.yaml`` this run did not write are reported, not deleted.

    Returns:
        The lines this function added to the report (``stale-file``), already in the written file.
    """
    out.mkdir(parents=True, exist_ok=True)
    names = {f"{schema.name}{SCHEMA_SUFFIX}" for schema in schemas}
    added = _stale_files(out, root_name, names)
    with tempfile.TemporaryDirectory(dir=out.parent, prefix=STAGING_PREFIX) as folder:
        staging = Path(folder)
        for schema in schemas:
            yaml_dumper.dump(schema, str(staging / f"{schema.name}{SCHEMA_SUFFIX}"))
        (staging / f"{root_name}{REPORT_SUFFIX}").write_text(
            report_text([*report, *added]), encoding="utf-8"
        )
        for staged in sorted(staging.iterdir()):
            os.replace(staged, out / staged.name)
    return added

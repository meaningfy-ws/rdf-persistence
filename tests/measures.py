"""The measures fixture, generated afresh: a decimal, a float and a double slot (langstring-support DEC-8).

No generated package is kept in the repository; a test generates the schema into its own folder.
"""

import shutil
from pathlib import Path

from rdf_persistence_generation.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "measures"
SCHEMA = "measures.yaml"
GENERATED = Path("domain") / "generated"
MEASURE = "https://example.org/measures/1"


def generate_measures(folder: Path, schema_text: str | None = None) -> tuple[Path, Path]:
    """Copy the fixture into ``folder`` and generate it there; returns the schema file and the generated folder.

    ``schema_text``, when given, replaces the fixture's schema in the copy: a test's own inline schema.
    """
    shutil.copytree(FIXTURE, folder, dirs_exist_ok=True)
    if schema_text is not None:
        (folder / SCHEMA).write_text(schema_text)
    assert main(["--project", str(folder / "pyproject.toml")]) == 0, "the fixture must generate"
    return folder / SCHEMA, folder / GENERATED

"""What the migration-file tests share: the library schema's id, the planted files and the steps written to them.

Not collected as tests; the tests of the chain, of the files and of their attacks import from here.
"""

from pathlib import Path

import pytest
import yaml

from rdf_persistence.core.domain.exceptions import InvalidMigration
from rdf_persistence.iris.domain.layout import stamps_graph_iri
from rdf_persistence.migrations.services.generated.rp_migrations_services import (
    Migration,
    MigrationStep,
)
from rdf_persistence.migrations.services.migrations import load_chain

BASE = "https://example.org/"
STAMPS = stamps_graph_iri(BASE)
SCHEMA = "https://example.org/ns/library"
SHELF = "<https://example.org/ns/library#shelf>"
PLACE = "<https://example.org/ns/library#place>"
FILE = "1__2.yaml"


def put(folder: Path, from_version: str, to_version: str, *, name: str | None = None, **fields):
    data = {"schema_id": SCHEMA, "from_version": from_version, "to_version": to_version, **fields}
    path = folder / (name or f"{from_version}__{to_version}.yaml")
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def refused(folder: Path, current: str) -> str:
    with pytest.raises(InvalidMigration) as error:
        load_chain(folder, SCHEMA, current)
    return str(error.value)


def step(title: str = "rename shelf", **fields: str | None) -> MigrationStep:
    return MigrationStep(title=title, **fields)


def rename() -> MigrationStep:
    return step(
        where_pattern=f"?s {SHELF} ?o .",
        delete_pattern=f"?s {SHELF} ?o .",
        insert_pattern=f"?s {PLACE} ?o .",
    )


def migration(*steps: MigrationStep) -> Migration:
    return Migration(schema_id=SCHEMA, from_version="1", to_version="2", steps=list(steps) or None)


def write(folder: Path, content: Migration | str) -> Path:
    path = folder / FILE
    text = (
        content
        if isinstance(content, str)
        else yaml.safe_dump(content.model_dump(exclude_none=True))
    )
    path.write_text(text, encoding="utf-8")
    return path

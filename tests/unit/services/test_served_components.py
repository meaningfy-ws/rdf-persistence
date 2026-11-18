"""The component schemas of the served targets, merged in the order of ``SERVED_SCHEMAS`` (PD-10)."""

import json
from pathlib import Path

import pytest

from rdf_persistence.services.artifacts import COMPONENTS_FILE, SCHEMAS
from rdf_persistence.services.components import (
    DuplicateComponentError,
    component_schemas,
    merge_components,
    served_folders,
)
from rdf_persistence.services.schema import PACKAGE_DIR, SERVED_SCHEMAS, SERVICE_SCHEMA


def folder_with(root: Path, name: str, *classes: str) -> Path:
    """A generated folder whose components file declares ``classes``."""
    folder = root / name
    folder.mkdir()
    document = {SCHEMAS: {cls: {"type": "object", "title": cls} for cls in classes}}
    (folder / COMPONENTS_FILE).write_text(json.dumps(document), encoding="utf-8")
    return folder


def test_two_files_with_disjoint_names_merge_in_served_order(tmp_path: Path) -> None:  # TC-20
    first = folder_with(tmp_path, "first", "Zeta", "Alpha")
    second = folder_with(tmp_path, "second", "Mid")
    assert list(merge_components([first, second])) == ["Zeta", "Alpha", "Mid"], (
        "the names of the first served target come before those of the second"
    )
    assert list(merge_components([second, first])) == ["Mid", "Zeta", "Alpha"], (
        "the order is the one of the folders given"
    )


def test_a_name_in_two_files_is_an_error_naming_it_and_both_files(tmp_path: Path) -> None:  # TC-21
    first = folder_with(tmp_path, "first", "Page", "Alpha")
    second = folder_with(tmp_path, "second", "Beta", "Page")
    with pytest.raises(DuplicateComponentError) as raised:
        merge_components([first, second])
    message = str(raised.value)
    assert "Page" in message, "the error names the component"
    assert str(first / COMPONENTS_FILE) in message, "the error names the first file"
    assert str(second / COMPONENTS_FILE) in message, "the error names the second file"


def test_the_application_folder_may_redeclare_a_served_class(tmp_path: Path) -> None:
    served = folder_with(tmp_path, "served", "Page")
    application = folder_with(tmp_path, "application", "Page", "Book")
    schemas = component_schemas([served], application, ["Book", "Page"])
    assert list(schemas) == ["Book", "Page"], "the metamodel's classes are in both and are one"


def test_the_served_folders_follow_the_served_schemas() -> None:
    assert SERVED_SCHEMAS == (SERVICE_SCHEMA,), "only the service schema is served for now"
    assert served_folders() == (PACKAGE_DIR / "services" / "generated" / "service",), (
        "the folder is the package the schema declares"
    )
    assert all((folder / COMPONENTS_FILE).is_file() for folder in served_folders())

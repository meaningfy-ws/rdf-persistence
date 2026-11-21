"""Which served schema publishes a class: scratch schemas, in orders the real set never has (PD-10).

``SERVED_SCHEMAS`` of the generator's ``components`` module is replaced by scratch schemas, so the rule
"a class two served schemas declare stays in both files, and the merge refuses it" and the rule "a served
schema listed before one it imports is an error" are tried on small cases.
"""

import json
from pathlib import Path

import pytest

from rdf_persistence.api.services.components import DuplicateComponentError, merge_components
from rdf_persistence.core.services.artifacts import COMPONENTS_FILE, SCHEMAS
from rdf_persistence_generation import components
from rdf_persistence_generation.exceptions import SchemaGenerationError

HEADER = """id: https://example.org/{name}
name: {name}
prefixes:
  linkml: https://w3id.org/linkml/
  ex: https://example.org/
default_prefix: ex
default_range: string
imports:
  - linkml:types
{imports}"""


def schema(root: Path, name: str, classes: tuple[str, ...], imports: tuple[str, ...] = ()) -> Path:
    """A scratch schema ``name`` whose classes each have one string slot; ``imports`` are sibling modules."""
    extra = "".join(f"  - ./{module}\n" for module in imports)
    body = HEADER.format(name=name, imports=extra)
    body += "slots:\n" + "".join(f"  {cls.lower()}_label:\n    range: string\n" for cls in classes)
    body += "classes:\n" + "".join(
        f"  {cls}:\n    slots:\n      - {cls.lower()}_label\n" for cls in classes
    )
    path = root / f"{name}.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def published(path: Path) -> set[str]:
    [file] = components.render(path)
    return set(json.loads(file.text)[SCHEMAS])


def write_folders(root: Path, paths: list[Path]) -> list[Path]:
    folders = []
    for path in paths:
        folder = root / f"out_{path.stem}"
        folder.mkdir()
        [file] = components.render(path)
        (folder / COMPONENTS_FILE).write_text(file.text, encoding="utf-8")
        folders.append(folder)
    return folders


def test_a_class_declared_by_two_served_schemas_stays_in_both_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    first = schema(tmp_path, "first", ("Dup", "A"))
    second = schema(tmp_path, "second", ("Dup", "B"))
    monkeypatch.setattr(components, "SERVED_SCHEMAS", (first, second))  # X1
    assert published(first) == {"Dup", "A"}
    assert published(second) == {"Dup", "B"}


def test_a_class_declared_by_two_served_schemas_makes_the_merge_raise_naming_both_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    first = schema(tmp_path, "first", ("Dup", "A"))
    second = schema(tmp_path, "second", ("Dup", "B"))
    monkeypatch.setattr(components, "SERVED_SCHEMAS", (first, second))  # X1
    folders = write_folders(tmp_path, [first, second])
    with pytest.raises(DuplicateComponentError, match=r"(?s)Dup.*out_first.*out_second"):
        merge_components(folders)


def test_a_served_schema_listed_before_the_one_it_imports_is_an_error_naming_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The order the SERVED_SCHEMAS comment forbids ("a schema comes before the ones that import it")."""
    low = schema(tmp_path, "low", ("Low",))
    high = schema(tmp_path, "high", ("High",), imports=("low",))
    monkeypatch.setattr(components, "SERVED_SCHEMAS", (high, low))  # X1
    with pytest.raises(SchemaGenerationError, match=r"(?s)high.*low"):
        components.render(high)

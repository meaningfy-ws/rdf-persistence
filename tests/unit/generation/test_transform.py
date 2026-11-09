"""PD-11: the generated toy classes carry the defaults applied before the generators (the transform is tested in services)."""

import ast
import importlib.util
from pathlib import Path

import pytest

from rdf_persistence.generation.cli import main
from rdf_persistence.services.components import read_components
from rdf_persistence.testkit.model_shape import model_schema_diff

from .test_generate_cli import SCHEMA, project

INHERITED_ROOT = SCHEMA.replace(
    """  Thing:
    title: Thing
    description: A thing.
    mixins: [AggregateRoot, Described]
    annotations:
      rp_path: things
""",
    """  Item:
    title: Item
    description: An abstract root.
    abstract: true
    mixins: [AggregateRoot, Described]
  Thing:
    title: Thing
    description: A thing served.
    is_a: Item
    annotations:
      rp_path: things
""",
)


def test_a_root_inheriting_from_an_abstract_root_builds_without_a_description(
    tmp_path: Path,
) -> None:
    assert INHERITED_ROOT != SCHEMA, "the planted schema must differ"
    assert main(["--project", str(project(tmp_path, INHERITED_ROOT))]) == 0, "the run failed"
    spec = importlib.util.spec_from_file_location("inherited_root", tmp_path / "app/generated/m.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    thing = module.Thing(id="https://example.org/t/1", label="t")
    assert thing.description is None, "the #59 reproduction: a root needs no description"
    components = read_components(tmp_path / "app/generated")
    for name in ("Item", "Thing"):
        assert set(components[name]["required"]) == {"id", "label"}, f"{name} in the JSON Schema"
    models = [module.Item, module.Thing]
    assert model_schema_diff(components, models) == [], "Python and JSON Schema agree"


@pytest.mark.slow
def test_the_generated_toy_classes_reflect_the_transform(toy_copy: Path) -> None:
    assert main(["--project", str(toy_copy / "pyproject.toml")]) == 0, "the toy must generate"
    tree = ast.parse((toy_copy / "generated" / "books.py").read_text(encoding="utf-8"))
    fields = {
        (cls.name, stmt.target.id): ast.unparse(stmt.annotation)
        for cls in tree.body
        if isinstance(cls, ast.ClassDef)
        for stmt in cls.body
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
    }
    assert fields[("Chapter", "label")] == "Optional[str]", (
        "an unlabelled class must have an optional label"
    )
    assert fields[("Note", "label")] == "str", "a labelled class must keep a required label"
    assert fields[("Book", "description")] == "Optional[str]", (
        "a root's description is optional (PD-1)"
    )
    assert fields[("Chapter", "description")] == "Optional[str]", (
        "an owned class must not require a description"
    )

"""PD-11: the generated toy classes carry the defaults applied before the generators (the transform is tested in services)."""

import ast
from pathlib import Path

from rdf_persistence.generation.cli import main


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
    assert fields[("Book", "description")] == "str", "a root must require its description"
    assert fields[("Chapter", "description")] == "Optional[str]", (
        "an owned class must not require a description"
    )

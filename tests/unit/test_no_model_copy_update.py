"""A model is rebuilt with ``replaced``, which validates; ``model_copy(update=...)`` does not (PD-8)."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "rdf_persistence"
LAYERS = ("domain", "services")
SCHEMA_KEYED = {"services/mapper.py"}  # keyed by the schema, generic by design (keep.md)


def update_copies(path: Path) -> list[int]:
    """The lines of ``<x>.model_copy(update=...)`` calls in ``path``."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "model_copy"
        and any(keyword.arg == "update" for keyword in node.keywords)
    ]


def test_model_copy_with_update_remains_only_in_the_schema_keyed_mapper() -> None:  # TC-30
    found = {
        str(path.relative_to(ROOT)): lines
        for layer in LAYERS
        for path in sorted((ROOT / layer).rglob("*.py"))
        if (lines := update_copies(path))
    }
    assert set(found) == SCHEMA_KEYED, f"model_copy(update=) outside the mapper: {found}"

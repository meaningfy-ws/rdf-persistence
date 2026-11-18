"""Every generator call of a toolkit-schema function passes ``roots=`` (PD-5, TC-14a).

Without it the library's default applies, and the generator's own schema would get a consumer's
defaults and class-level rules. The scan reads the syntax tree with ``ast``, so a call by name or
through a module attribute is found, and a ``roots`` in a comment or a string is not one.
"""

import ast
from pathlib import Path

from rdf_persistence_generation.config import GENERATOR_DIR

FUNCTIONS = frozenset({"is_toolkit_schema", "apply_defaults", "generation_view"})
KEYWORD = "roots"


def _called_name(call: ast.Call) -> str | None:
    function = call.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return None


def calls_without_roots(folder: Path) -> list[str]:
    """The ``file:line`` and name of each call under ``folder`` that does not pass ``roots=``."""
    found: list[str] = []
    for path in sorted(folder.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _called_name(node) not in FUNCTIONS:
                continue
            if all(keyword.arg != KEYWORD for keyword in node.keywords):
                found.append(f"{path}:{node.lineno}: {_called_name(node)}")
    return sorted(found)


def test_every_generator_call_of_a_toolkit_schema_function_passes_roots() -> None:
    assert not calls_without_roots(GENERATOR_DIR), "a call without roots= (PD-5)"


def test_a_call_without_roots_is_named_by_file_and_line(tmp_path: Path) -> None:
    """Adversarial: the planted call is found, the one with ``roots=`` is not."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "ok = is_toolkit_schema(folder, roots=ROOTS)\n"
        "\n"
        "bad = generation_view(path)\n"
        "worse = apply_defaults(view, folder)\n",
        encoding="utf-8",
    )

    found = calls_without_roots(tmp_path)

    assert [f.split(": ")[0] for f in found] == [f"{planted}:3", f"{planted}:4"], found


def test_a_call_through_a_module_attribute_without_roots_is_named(tmp_path: Path) -> None:
    planted = tmp_path / "attribute.py"
    planted.write_text(
        "import schema\n"
        "\n"
        "bad = schema.generation_view(path)\n"
        "ok = schema.apply_defaults(view, roots=ROOTS)\n",
        encoding="utf-8",
    )

    found = calls_without_roots(tmp_path)

    assert [f.split(": ")[0] for f in found] == [f"{planted}:3"], found


def test_roots_in_a_comment_does_not_count(tmp_path: Path) -> None:
    planted = tmp_path / "comment.py"
    planted.write_text(
        "bad = is_toolkit_schema(folder)  # roots=ROOTS\n"
        'worse = apply_defaults(view, "roots=ROOTS")\n',
        encoding="utf-8",
    )

    found = calls_without_roots(tmp_path)

    assert [f.split(": ")[0] for f in found] == [f"{planted}:1", f"{planted}:2"], found


def test_a_folder_without_the_calls_has_no_problem(tmp_path: Path) -> None:
    (tmp_path / "other.py").write_text("print(len([1]))\n", encoding="utf-8")

    assert calls_without_roots(tmp_path) == []

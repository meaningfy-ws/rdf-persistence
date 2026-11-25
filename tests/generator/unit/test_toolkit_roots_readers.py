"""Only ``toolkit_roots()`` reads ``TOOLKIT_ROOTS``, so a test patches one constant (PD-7, 192-e).

The scan reads the syntax tree with ``ast``: a name, an attribute and an imported name (an ``as``
alias included) are found, and the word in a comment or a string is not.
"""

import ast
from pathlib import Path

from rdf_persistence_generation.config import GENERATOR_DIR

NAME = "TOOLKIT_ROOTS"
HOME = "config.py"


def _names_it(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == NAME
    if isinstance(node, ast.Attribute):
        return node.attr == NAME
    if isinstance(node, ast.alias):
        return node.name == NAME
    return False


def readers(folder: Path) -> list[str]:
    """The ``file:line`` of each use of ``TOOLKIT_ROOTS`` under ``folder`` outside ``config.py``."""
    found: list[str] = []
    for path in sorted(folder.rglob("*.py")):
        if path.name == HOME and path.parent == folder:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found += [f"{path}:{node.lineno}" for node in ast.walk(tree) if _names_it(node)]
    return sorted(found)


def test_only_the_accessor_reads_toolkit_roots() -> None:
    assert not readers(GENERATOR_DIR), "a module besides config.py names TOOLKIT_ROOTS (PD-7)"


def test_an_import_with_an_alias_is_a_reader(tmp_path: Path) -> None:
    """Adversarial: the planted alias import and its use are found."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "from rdf_persistence_generation.config import TOOLKIT_ROOTS as ROOTS\n\nvalue = ROOTS\n",
        encoding="utf-8",
    )

    assert readers(tmp_path) == [f"{planted}:1"], "the alias import is named, its use is not"


def test_a_module_attribute_and_a_plain_name_are_readers(tmp_path: Path) -> None:
    planted = tmp_path / "attribute.py"
    planted.write_text(
        "import config\n\nfirst = config.TOOLKIT_ROOTS\nsecond = TOOLKIT_ROOTS\n",
        encoding="utf-8",
    )

    assert readers(tmp_path) == [f"{planted}:3", f"{planted}:4"], "both uses are named"


def test_the_word_in_a_comment_or_a_string_is_not_a_reader(tmp_path: Path) -> None:
    (tmp_path / "quiet.py").write_text(
        '# TOOLKIT_ROOTS\ntext = "TOOLKIT_ROOTS"\n', encoding="utf-8"
    )

    assert readers(tmp_path) == [], "a comment and a string are not reads"


def test_the_defining_module_is_not_a_reader(tmp_path: Path) -> None:
    (tmp_path / HOME).write_text("TOOLKIT_ROOTS = ()\n", encoding="utf-8")

    assert readers(tmp_path) == [], "config.py defines and reads it"

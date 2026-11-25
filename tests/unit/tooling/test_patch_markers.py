"""Every patch of toolkit code in a unit test names its kind (272-a, PD-20).

``testing.adoc`` rule 3 allows five kinds of ``monkeypatch.setattr`` or ``delattr`` on toolkit
code, each marked with a trailing ``# X1`` to ``# X5`` comment. The guard reads the AST of every
unit test file, takes the comments from ``tokenize`` (the AST has none), and names file and line
of each toolkit patch with no marker. A call that spans lines passes with the marker on its first
or its last line.

The target is toolkit code when the first argument is a string starting ``rdf_persistence`` or a
name (or an attribute chain on a name) bound in the file by an import from ``rdf_persistence`` or
``rdf_persistence_generation``, ``as`` names included. The guard reads names, not types: a patch
of a toolkit instance (a fixture's object, such as ``toy.documents``) is beyond it.
"""

import ast
import io
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEST_FOLDERS = ["tests/unit", "tests/generator/unit"]
TOOLKIT_PACKAGES = ("rdf_persistence", "rdf_persistence_generation")
PATCHES = {"setattr", "delattr"}
MARKER = re.compile(r"#\s*X[1-5]\b")


def _is_toolkit_module(name: str) -> bool:
    return any(name == package or name.startswith(package + ".") for package in TOOLKIT_PACKAGES)


def toolkit_names(tree: ast.AST) -> set[str]:
    """The names an import from the toolkit binds in this file, ``as`` names included."""
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_toolkit_module(alias.name):
                    bound.add(alias.asname or alias.name.split(".")[0])
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
            and _is_toolkit_module(node.module)
        ):
            bound.update(alias.asname or alias.name for alias in node.names)
    return bound


def _root_name(node: ast.expr) -> str | None:
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _targets_toolkit(first: ast.expr, bound: set[str]) -> bool:
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value.startswith("rdf_persistence")
    return _root_name(first) in bound


def _comment_lines(source: str) -> dict[int, str]:
    return {
        token.start[0]: token.string
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    }


def unmarked_patches(source: str) -> list[int]:
    """Lines of the ``monkeypatch.setattr/delattr`` calls on toolkit code with no ``# X1``-``# X5``."""
    tree = ast.parse(source)
    bound = toolkit_names(tree)
    comments = _comment_lines(source)
    found = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in PATCHES
            and _root_name(node.func.value) == "monkeypatch"
            and node.args
            and _targets_toolkit(node.args[0], bound)
        ):
            continue
        ends = node.end_lineno or node.lineno
        marked = any(MARKER.search(comments.get(line, "")) for line in {node.lineno, ends})
        if not marked:
            found.append(node.lineno)
    return sorted(found)


def test_every_patch_of_toolkit_code_names_its_kind() -> None:
    """Found: toolkit patches with no ``# X1``-``# X5`` marker, rule 3 of ``testing.adoc``."""
    hits = []
    for folder in TEST_FOLDERS:
        for path in sorted((ROOT / folder).rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            hits += [f"{path.relative_to(ROOT).as_posix()}:{n}" for n in unmarked_patches(source)]

    assert hits == [], f"{len(hits)} toolkit patches carry no X1-X5 marker: {hits}"


def test_the_marker_check_sees_an_aliased_import() -> None:
    """Error matrix: a patch through ``import rdf_persistence.x as m`` is found, a marked one is not."""
    source = (
        "import rdf_persistence.x as m\n"
        "from rdf_persistence_generation import y as z\n"
        "def test_a(monkeypatch):\n"
        "    monkeypatch.setattr(m, 'a', 1)\n"
        "    monkeypatch.setattr(z.inner, 'b', 2)\n"
        "    monkeypatch.setattr(m, 'c', 3)  # X1\n"
        "    monkeypatch.setattr(\n"
        "        m, 'd', 4\n"
        "    )  # X2\n"
        "    monkeypatch.setattr('rdf_persistence.q.r', 5)\n"
        "    monkeypatch.setattr(other, 'e', 6)\n"
    )

    assert unmarked_patches(source) == [4, 5, 10], (
        "the guard misses an aliased import, a string target, or flags a marked or foreign patch"
    )

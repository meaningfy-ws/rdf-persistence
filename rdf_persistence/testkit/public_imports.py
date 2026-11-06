"""``assert_public_imports``: a consumer's end-to-end test uses the toolkit's public names only (PD-20).

Parses the file with ``ast``; standard library only.
"""

import ast
import importlib.util
from collections.abc import Iterator
from pathlib import Path

PACKAGE = "rdf_persistence"
PUBLIC_SUBPACKAGE = "testkit"


def _submodules() -> frozenset[str]:
    """The names of the package's subpackages and modules, from the installed folder."""
    spec = importlib.util.find_spec(PACKAGE)
    folders = [Path(p) for p in (spec and spec.submodule_search_locations or ())]
    entries = (entry for folder in folders for entry in folder.iterdir())
    return frozenset(entry.stem for entry in entries if _is_module(entry)) - {"__init__"}


def _is_module(entry: Path) -> bool:
    return (entry.is_dir() and entry.name != "__pycache__") or entry.suffix == ".py"


def _imported_names(node: ast.stmt) -> Iterator[str]:
    """The dotted module names an import statement reaches into."""
    if isinstance(node, ast.Import):
        yield from (alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        yield from _from_names(node)


def _from_names(node: ast.ImportFrom) -> Iterator[str]:
    if node.level == 0 and node.module:
        yield node.module
        yield from (f"{node.module}.{alias.name}" for alias in node.names)


def _is_private(name: str, submodules: frozenset[str]) -> bool:
    parts = name.split(".")
    if parts[0] != PACKAGE or len(parts) == 1:
        return False
    return parts[1] != PUBLIC_SUBPACKAGE and parts[1] in submodules


def _private_imports(source: Path, submodules: frozenset[str]) -> set[str]:
    """One ``file:line imports name`` text per private import in ``source``."""
    tree = ast.parse(source.read_text(), filename=str(source))
    imports = (node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom))
    return {
        f"{source.name}:{node.lineno} imports {name}"
        for node in imports
        for name in _imported_names(node)
        if _is_private(name, submodules)
    }


def assert_public_imports(path: str | Path) -> None:
    """Raise one ``AssertionError`` listing each import of ``rdf_persistence.<sub>`` other than ``testkit``.

    ``from rdf_persistence import X`` is public when ``X`` is a name of the package, and refused
    when ``X`` is one of its subpackages (``services``, ``adapters``, ...).
    """
    found = sorted(_private_imports(Path(path), _submodules()))
    assert not found, "a consumer test may use only the public names:\n" + "\n".join(found)

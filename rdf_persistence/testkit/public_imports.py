"""``assert_public_imports``: a consumer's end-to-end test uses the toolkit's public names only (PD-20).

Parses the file with ``ast``; standard library and the testkit's own import reader only.
"""

import ast
import importlib.util
from collections.abc import Iterator
from pathlib import Path

from rdf_persistence.testkit.guards import from_import_names

PACKAGE = "rdf_persistence"
PUBLIC_SUBPACKAGE = "testkit"
TESTKIT = f"{PACKAGE}.{PUBLIC_SUBPACKAGE}"
# The one module of the testkit a test file names: pytest loads the container fixtures by its path.
PLUGIN_MODULE = "containers"


def _submodules(package: str) -> frozenset[str]:
    """The names of the subpackages and modules of ``package``, from the installed folder."""
    spec = importlib.util.find_spec(package)
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
        yield from from_import_names(node, "").values()


def _is_private(name: str, submodules: frozenset[str], testkit_modules: frozenset[str]) -> bool:
    """True for a module of the toolkit other than the package, its ``testkit``, and the plugin path.

    A name that is no module (a class imported from the package) is public.
    """
    parts = name.split(".")
    if parts[0] != PACKAGE or len(parts) == 1:
        return False
    if parts[1] == PUBLIC_SUBPACKAGE:
        return len(parts) > 2 and parts[2] in testkit_modules and parts[2] != PLUGIN_MODULE
    return parts[1] in submodules


def _private_imports(
    source: Path, submodules: frozenset[str], testkit_modules: frozenset[str]
) -> set[str]:
    """One ``file:line imports name`` text per private import in ``source``."""
    tree = ast.parse(source.read_text(), filename=str(source))
    imports = (node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom))
    return {
        f"{source.name}:{node.lineno} imports {name}"
        for node in imports
        for name in _imported_names(node)
        if _is_private(name, submodules, testkit_modules)
    }


def assert_public_imports(path: str | Path) -> None:
    """Raise one ``AssertionError`` listing each import of a module of the toolkit.

    Only ``rdf_persistence`` and ``rdf_persistence.testkit`` themselves are public, and the path of
    the container fixtures, ``rdf_persistence.testkit.containers``. ``from rdf_persistence import X``
    is public when ``X`` is a name of the package, and refused when ``X`` is one of its subpackages
    (``services``, ``adapters``, ...); the same holds for ``from rdf_persistence.testkit import X``.
    """
    found = sorted(_private_imports(Path(path), _submodules(PACKAGE), _submodules(TESTKIT)))
    assert not found, "a consumer test may use only the public names:\n" + "\n".join(found)

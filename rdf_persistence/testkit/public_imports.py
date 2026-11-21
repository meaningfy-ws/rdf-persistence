"""``assert_public_imports``: a consumer's end-to-end test uses the toolkit's public names only (PD-20).

Parses the file with ``ast``; standard library and the testkit's own import reader only.
"""

import ast
import importlib.util
from collections.abc import Iterator
from functools import cache
from pathlib import Path

from rdf_persistence.testkit.guards import from_import_names

PUBLIC_SUBPACKAGE = "testkit"
# Each package of the toolkit a consumer imports -> the one module of its testkit a test file names
# by path (pytest loads it as a plugin): the container fixtures, the freshness check.
PLUGIN_MODULES = {"rdf_persistence": "containers", "rdf_persistence_generation": "freshness"}
BYTECODE_DIR = "__pycache__"
SOURCE_SUFFIX = ".py"
# In <package>.testkit.<module>, the dotted-name part that names the module.
TESTKIT_MODULE_INDEX = 2


@cache
def _submodules(package: str, subpackage: str = "") -> frozenset[str]:
    """The names of the modules of ``package`` (or of its ``subpackage``), from the installed folder.

    Only the top-level package is located, so nothing is imported: the library never imports the
    generator.
    """
    spec = importlib.util.find_spec(package)
    folders = [Path(p, subpackage) for p in (spec and spec.submodule_search_locations or ())]
    entries = (entry for folder in folders if folder.is_dir() for entry in folder.iterdir())
    return frozenset(entry.stem for entry in entries if _is_module(entry)) - {"__init__"}


def _is_module(entry: Path) -> bool:
    return (entry.is_dir() and entry.name != BYTECODE_DIR) or entry.suffix == SOURCE_SUFFIX


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


def _is_private(name: str) -> bool:
    """True for a module of the toolkit other than a package, its ``testkit``, and the plugin path.

    A name that is no module (a class imported from the package) is public.
    """
    parts = name.split(".")
    package = parts[0]
    if package not in PLUGIN_MODULES or len(parts) == 1:
        return False
    if parts[1] == PUBLIC_SUBPACKAGE:
        module = parts[TESTKIT_MODULE_INDEX] if len(parts) > TESTKIT_MODULE_INDEX else None
        testkit_modules = _submodules(package, PUBLIC_SUBPACKAGE)
        return module in testkit_modules and module != PLUGIN_MODULES[package]
    return parts[1] in _submodules(package)


def _private_imports(source: Path) -> set[str]:
    """One ``file:line imports name`` text per private import in ``source``."""
    tree = ast.parse(source.read_text(), filename=str(source))
    imports = (node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom))
    return {
        f"{source.name}:{node.lineno} imports {name}"
        for node in imports
        for name in _imported_names(node)
        if _is_private(name)
    }


def assert_public_imports(path: str | Path) -> None:
    """Raise one ``AssertionError`` listing each import of a module of the toolkit.

    Only ``rdf_persistence``, ``rdf_persistence_generation`` and their ``testkit`` packages are
    public, and the plugin paths ``rdf_persistence.testkit.containers`` and
    ``rdf_persistence_generation.testkit.freshness``. ``from rdf_persistence import X`` is public
    when ``X`` is a name of the package, and refused when ``X`` is one of its subpackages
    (``services``, ``adapters``, ...); the same holds for each package's ``testkit``.
    """
    found = sorted(_private_imports(Path(path)))
    assert not found, "a consumer test may use only the public names:\n" + "\n".join(found)

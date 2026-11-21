"""The toy library, freshly generated under another package name and imported, for the generator's e2e."""

import importlib
import shutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

from rdf_persistence_generation.cli import main as generate

TOY = Path(__file__).parents[2] / "fixtures" / "library"
PACKAGE = "toy_e2e"


@contextmanager
def generated_toy(tmp_path: Path) -> Iterator[ModuleType]:
    """The toy copied to ``tmp_path/toy_e2e``, generated as ``toy_e2e.generated`` and imported.

    ``tmp_path`` is on ``sys.path`` and ``toy_e2e`` in ``sys.modules`` only inside the block.
    """
    folder = tmp_path / PACKAGE
    shutil.copytree(TOY, folder, ignore=shutil.ignore_patterns("__pycache__", "generated"))
    exit_code = generate(
        ["--project", str(folder / "pyproject.toml"), "--package", f"{PACKAGE}.domain.generated"]
    )
    assert exit_code == 0, "the toy copy did not generate"
    sys.path.insert(0, str(tmp_path))
    importlib.invalidate_caches()
    try:
        yield importlib.import_module(f"{PACKAGE}.domain.generated")
    finally:
        sys.path.remove(str(tmp_path))
        for name in [n for n in sys.modules if n == PACKAGE or n.startswith(f"{PACKAGE}.")]:
            del sys.modules[name]
        importlib.invalidate_caches()

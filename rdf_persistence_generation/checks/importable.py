"""The generated Python imports and type-checks (#242, #243): checked on what the targets wrote.

Generation can succeed and still write a module that fails to import (an impossible MRO, a
shadowed name, a cycle between modules) or does not type-check, so the written code is imported
and type-checked, never trusted. Both run in a subprocess, which leaves this process's
``sys.modules`` alone and sees the files as they now are.
"""

import importlib.util
import os
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

from rdf_persistence_generation.config import python_folder
from rdf_persistence_generation.generated.rp_generation import CheckProblem, GenerationTarget

IMPORT_STEP = "import check"
TYPE_STEP = "type check"
MYPY_CONFIG = Path(__file__).parents[1] / "mypy-generated.ini"
MYPY_MISSING = "mypy is not installed: install rdf-persistence[generate]"
MYPY_ERROR = ": error: "
INIT = "__init__.py"
# Puts the first argument's paths first on sys.path, then imports each module the others name;
# prints one tab-separated line per failure.
IMPORT_SCRIPT = """\
import importlib, os, sys
sys.path[:0] = sys.argv[1].split(os.pathsep)
for name in sys.argv[2:]:
    try:
        importlib.import_module(name)
    except Exception as error:
        print(name, f"{type(error).__name__}: {error}".replace("\\n", " "), sep="\\t")
"""


def _modules(target: GenerationTarget, base: Path) -> list[str]:
    """The dotted names of the Python modules in the target's folder (not its subfolders: other targets')."""
    folder = base / python_folder(target)
    return [
        f"{target.package}.{file.stem}" for file in sorted(folder.glob("*.py")) if file.name != INIT
    ]


def _import_root(target: GenerationTarget, base: Path) -> Path | None:
    """The folder the target's package is imported from: its Python folder less one level per package part.

    ``None`` when the folder's names do not spell the package; the caller's path must then find it.
    """
    folder = (base / python_folder(target)).resolve()
    parts = target.package.split(".")
    if folder.parts[-len(parts) :] != tuple(parts):
        return None
    return folder.parents[len(parts) - 1]


def _roots(targets: Iterable[GenerationTarget], base: Path) -> list[str]:
    found = {str(root) for target in targets if (root := _import_root(target, base))}
    return sorted(found)


def _search_path(roots: Sequence[str]) -> str:
    """The import roots, then this process's own path, as one ``os.pathsep``-joined argument."""
    return os.pathsep.join([*roots, *(entry or os.getcwd() for entry in sys.path)])


def import_problems(targets: Sequence[GenerationTarget], base: Path) -> list[CheckProblem]:
    """One problem per generated module that fails to import, naming it and the exception."""
    schema_of = {
        module: target.schema_file for target in targets for module in _modules(target, base)
    }
    if not schema_of:
        return []
    result = subprocess.run(
        [sys.executable, "-c", IMPORT_SCRIPT, _search_path(_roots(targets, base)), *schema_of],
        capture_output=True,
        text=True,
        check=False,
    )
    problems = []
    for line in result.stdout.splitlines():
        module, _, error = line.partition("\t")
        problems.append(
            CheckProblem(
                schema_file=schema_of.get(module), step=IMPORT_STEP, element=module, message=error
            )
        )
    if result.returncode and not problems:
        problems.append(CheckProblem(step=IMPORT_STEP, message=result.stderr.strip()))
    return problems


def _outermost(targets: Sequence[GenerationTarget], base: Path) -> list[str]:
    """The targets' packages that hold modules, less those inside another: mypy checks a package's subpackages too."""
    packages = sorted({t.package for t in targets if _modules(t, base)})
    return [p for p in packages if not any(p.startswith(f"{other}.") for other in packages)]


def _mypy(targets: Sequence[GenerationTarget], base: Path) -> subprocess.CompletedProcess[str]:
    """mypy over the targets' packages, run with ``mypy-generated.ini``.

    ponytail: mypy finds the packages from its working folder (``mypy_path = .``), the first
    import root; targets imported from two different folders would need MYPYPATH, so far none do.
    """
    roots = _roots(targets, base)
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--config-file", str(MYPY_CONFIG), "--no-error-summary"]
        + [arg for package in _outermost(targets, base) for arg in ("-p", package)],
        cwd=roots[0] if roots else base,
        capture_output=True,
        text=True,
        check=False,
    )


def type_problems(targets: Sequence[GenerationTarget], base: Path) -> list[CheckProblem]:
    """One problem per mypy error over the targets' packages, naming the file and the line."""
    if not any(_modules(target, base) for target in targets):
        return []
    if importlib.util.find_spec("mypy") is None:
        return [CheckProblem(step=TYPE_STEP, message=MYPY_MISSING)]
    result = _mypy(targets, base)
    errors = [line for line in result.stdout.splitlines() if MYPY_ERROR in line]
    problems = [
        CheckProblem(step=TYPE_STEP, element=place, message=message)
        for place, _, message in (line.partition(MYPY_ERROR) for line in errors)
    ]
    if result.returncode and not problems:
        problems.append(
            CheckProblem(step=TYPE_STEP, message=(result.stdout + result.stderr).strip())
        )
    return problems

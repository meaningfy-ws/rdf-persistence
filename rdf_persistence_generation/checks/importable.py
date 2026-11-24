"""The generated Python imports and type-checks (#242, #243): checked on what the targets wrote.

Generation can succeed and still write a module that fails to import (an impossible MRO, a
shadowed name, a cycle between modules) or does not type-check, so the written code is imported
and type-checked, never trusted. Both run in a subprocess, which leaves this process's
``sys.modules`` alone and sees the files as they now are; neither writes into the project.
"""

import hashlib
import importlib.util
import json
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
MYPY_CACHES = "rp-generate-mypy"  # in the user's cache folder, one per project
INIT = "__init__.py"
# argv: the search path to put first, a JSON object {package: folder}, the modules to import.
# A package the path does not find in its folder is loaded from the folder, so a target whose
# folder names do not spell its package is still checked; then each module is imported, and
# each failure printed as one tab-separated line.
IMPORT_SCRIPT = """\
import importlib, importlib.util, json, os, sys
sys.path[:0] = sys.argv[1].split(os.pathsep)
for package, folder in json.loads(sys.argv[2]).items():
    try:
        found = importlib.util.find_spec(package)
    except ImportError:
        found = None
    if found is None or folder not in (found.submodule_search_locations or []):
        spec = importlib.util.spec_from_file_location(
            package, os.path.join(folder, "__init__.py"), submodule_search_locations=[folder]
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[package] = module
        spec.loader.exec_module(module)
for name in sys.argv[3:]:
    try:
        importlib.import_module(name)
    except Exception as error:
        print(name, f"{type(error).__name__}: {error}".replace("\\n", " "), sep="\\t")
"""


def _folder(target: GenerationTarget, base: Path) -> Path:
    return (base / python_folder(target)).resolve()


def _modules(target: GenerationTarget, base: Path) -> list[str]:
    """The dotted names of the Python modules in the target's folder (not its subfolders: other targets')."""
    return [
        f"{target.package}.{file.stem}"
        for file in sorted(_folder(target, base).glob("*.py"))
        if file.name != INIT
    ]


def _import_root(target: GenerationTarget, base: Path) -> Path | None:
    """The folder the target's package is imported from: its Python folder less one level per package part.

    ``None`` when the folder's names do not spell the package.
    """
    folder = _folder(target, base)
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


def _checked(targets: Sequence[GenerationTarget], base: Path) -> list[GenerationTarget]:
    """The targets that wrote Python modules, outer packages first."""
    return sorted((t for t in targets if _modules(t, base)), key=lambda t: t.package)


def import_problems(targets: Sequence[GenerationTarget], base: Path) -> list[CheckProblem]:
    """One problem per generated module that fails to import, naming it and the exception."""
    checked = _checked(targets, base)
    schema_of = {module: t.schema_file for t in checked for module in _modules(t, base)}
    if not schema_of:
        return []
    folders = json.dumps({t.package: str(_folder(t, base)) for t in checked})
    result = subprocess.run(
        # -B: no __pycache__ in the generated folders, which a run's output must not gain
        [sys.executable, "-B", "-c", IMPORT_SCRIPT, _search_path(_roots(checked, base)), folders]
        + list(schema_of),
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


def _mypy_targets(checked: Sequence[GenerationTarget], base: Path) -> list[str]:
    """mypy's arguments: ``-p`` for each outermost package found by its import root, the folder of each other.

    mypy checks a package's subpackages too, so a package inside another listed one is left out.
    """
    rooted = [t.package for t in checked if _import_root(t, base)]
    outermost = [p for p in rooted if not any(p.startswith(f"{other}.") for other in rooted)]
    listed = [_folder(t, base) for t in checked if not _import_root(t, base)]
    folders = _outermost_folders(listed)
    return [*(arg for package in outermost for arg in ("-p", package)), *folders]


def _outermost_folders(listed: Sequence[Path]) -> list[str]:
    """The folders not inside another listed one: a value target's under its domain target's is checked with it."""
    unique = list(dict.fromkeys(listed))
    return [str(f) for f in unique if not any(other in f.parents for other in unique)]


def _cache_dir(base: Path) -> Path:
    """mypy's cache for the project: in the user's own cache folder, so a check writes nothing into
    the project, and no other user of a shared temporary folder can plant a cache that hides errors."""
    import platformdirs  # lazy: linkml brings it with the `generate` extra, which this check needs

    key = hashlib.sha256(str(base.resolve()).encode()).hexdigest()[:16]
    return platformdirs.user_cache_path(MYPY_CACHES) / key


def _mypy(checked: Sequence[GenerationTarget], base: Path) -> subprocess.CompletedProcess[str]:
    """mypy over the targets' packages, run with ``mypy-generated.ini``.

    ponytail: mypy finds the packages from its working folder (``mypy_path = .``), the first
    import root; targets imported from two different folders would need MYPYPATH, so far none do.
    """
    roots = _roots(checked, base)
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--config-file", str(MYPY_CONFIG), "--no-error-summary"]
        + ["--cache-dir", str(_cache_dir(base)), *_mypy_targets(checked, base)],
        cwd=roots[0] if roots else base,
        capture_output=True,
        text=True,
        check=False,
    )


def type_problems(targets: Sequence[GenerationTarget], base: Path) -> list[CheckProblem]:
    """One problem per mypy error over the targets' packages, naming the file and the line."""
    checked = _checked(targets, base)
    if not checked:
        return []
    if importlib.util.find_spec("mypy") is None:
        return [CheckProblem(step=TYPE_STEP, message=MYPY_MISSING)]
    result = _mypy(checked, base)
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

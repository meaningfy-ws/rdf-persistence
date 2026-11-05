"""Guards against hand-written models, shapes, contexts and API schemas (PD-28).

Models are declared in LinkML and generated. ``assert_models_generated`` fails when a hand-written
model sits in ``domain``, ``services`` or ``entrypoints``, or when a generated artefact sits outside
a ``generated`` folder. Standard library only.
"""

import ast
import importlib.util
from collections.abc import Iterable, Iterator
from fnmatch import fnmatch
from pathlib import Path
from typing import NamedTuple

GENERATED = "generated"
SCANNED_LAYERS = ("domain", "services", "entrypoints")
DEFAULT_ALLOW = ("rdf_persistence/domain/base.py:RpModel",)

# Fully qualified names that make a class a hand-written model.
FORBIDDEN_BASES = frozenset(
    {
        "pydantic.BaseModel",
        "pydantic.main.BaseModel",
        "pydantic.v1.BaseModel",
        "rdf_persistence.domain.base.RpModel",
        "enum.Enum",
        "enum.StrEnum",
        "enum.IntEnum",
        "typing.TypedDict",
        "typing.NamedTuple",
        "typing_extensions.TypedDict",
        "typing_extensions.NamedTuple",
    }
)
FORBIDDEN_DECORATORS = frozenset({"dataclasses.dataclass", "pydantic.dataclasses.dataclass"})

FORBIDDEN_FILE_PATTERNS = (
    "*.shacl.ttl",
    "*shapes*.ttl",
    "*.context.jsonld",
    "*.frame.jsonld",
    "*.schema.json",
    "openapi*.json",
    "openapi*.yaml",
    "*.ts",
)
ALLOWED_FILE_PATTERNS = ("*.test.ts", "*.spec.ts")


class Violation(NamedTuple):
    where: str
    what: str

    def __str__(self) -> str:
        return f"{self.where}: {self.what}"


def assert_models_generated(
    package: str | Path,
    *,
    roots: Iterable[Path],
    allow: Iterable[str] = (),
    exempt: Iterable[Path] = (),
) -> None:
    """Raise one ``AssertionError`` listing every violation, or return None.

    ``package``: the package root directory, or an import name resolved without importing it.
    ``roots``: folders scanned by the file guard.
    ``allow``: ``"<posix path relative to the package's parent>:<ClassName>"`` entries added to the
    default exception (``rdf_persistence/domain/base.py:RpModel``).
    ``exempt``: folders the file guard skips (instance data, request bodies).
    """
    package_dir = _package_dir(package)
    allowed = frozenset((*DEFAULT_ALLOW, *allow))
    violations = [*_model_violations(package_dir, allowed), *_file_violations(roots, tuple(exempt))]
    if violations:
        raise AssertionError(
            "Hand-written models or generated artefacts found:\n" + "\n".join(map(str, violations))
        )


def _package_dir(package: str | Path) -> Path:
    if isinstance(package, Path):
        return package
    spec = importlib.util.find_spec(package)
    if spec is None or not spec.submodule_search_locations:
        raise ValueError(f"cannot locate package {package!r}")
    return Path(next(iter(spec.submodule_search_locations)))


# --- model guard -------------------------------------------------------------------------------


def _model_violations(package_dir: Path, allowed: frozenset[str]) -> Iterator[Violation]:
    exports = _top_level_exports(package_dir)
    for layer in SCANNED_LAYERS:
        for path in sorted((package_dir / layer).rglob("*.py")):
            relative = path.relative_to(package_dir.parent)
            if GENERATED in relative.parts:
                continue
            yield from _module_violations(path, relative, allowed, exports)


def _top_level_exports(package_dir: Path) -> dict[str, str]:
    """Names the package's ``__init__`` re-exports, read with ``ast`` (no import)."""
    init = package_dir / "__init__.py"
    if not init.is_file():
        return {}
    tree = ast.parse(init.read_text(encoding="utf-8"), filename=str(init))
    return {
        f"{package_dir.name}.{n}": full
        for n, full in _import_names(tree, package_dir.name, is_package=True).items()
    }


def _module_violations(
    path: Path, relative: Path, allowed: frozenset[str], exports: dict[str, str]
) -> Iterator[Violation]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = _import_names(tree, _module_name(relative), is_package=path.name == "__init__.py")
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or f"{relative.as_posix()}:{node.name}" in allowed:
            continue
        reason = _reason(node, names, exports)
        if reason:
            yield Violation(f"{relative.as_posix()}:{node.lineno}", f"class {node.name} {reason}")


def _reason(node: ast.ClassDef, names: dict[str, str], exports: dict[str, str]) -> str | None:
    for base in node.bases:
        resolved = _resolve(base, names)
        resolved = exports.get(resolved or "", resolved)
        if resolved in FORBIDDEN_BASES:
            return f"derives from {resolved}; declare it in LinkML"
        if resolved and GENERATED in resolved.split("."):
            return f"extends the generated class {resolved}; declare it in LinkML"
    for decorator in node.decorator_list:
        if (resolved := _resolve(decorator, names)) in FORBIDDEN_DECORATORS:
            return f"is decorated with {resolved}; declare it in LinkML"
    return None


def _module_name(relative: Path) -> str:
    parts = list(relative.with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _import_names(tree: ast.Module, module: str, *, is_package: bool) -> dict[str, str]:
    """Map each name bound by an import to the dotted name it stands for."""
    # shortcut: imports inside functions are included, scoping is ignored; upgrade if it misfires.
    names: dict[str, str] = {}
    package = module if is_package else module.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    names[alias.asname] = alias.name
                else:
                    top = alias.name.split(".")[0]
                    names[top] = top
        elif isinstance(node, ast.ImportFrom):
            source = _from_source(node, package)
            for alias in node.names:
                names[alias.asname or alias.name] = (
                    f"{source}.{alias.name}" if source else alias.name
                )
    return names


def _from_source(node: ast.ImportFrom, package: str) -> str:
    if not node.level:
        return node.module or ""
    anchor = package.split(".")[: len(package.split(".")) - (node.level - 1)]
    return ".".join([*anchor, *([node.module] if node.module else [])])


def _resolve(node: ast.expr, names: dict[str, str]) -> str | None:
    """Dotted name of a base or decorator expression, through the module's imports."""
    if isinstance(node, ast.Call | ast.Subscript):
        return _resolve(node.func if isinstance(node, ast.Call) else node.value, names)
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    head = names.get(node.id, node.id)
    return ".".join([head, *reversed(parts)])


# --- file guard --------------------------------------------------------------------------------


def _file_violations(roots: Iterable[Path], exempt: tuple[Path, ...]) -> Iterator[Violation]:
    for root in roots:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            if GENERATED in path.relative_to(root).parts or any(
                path.is_relative_to(e) for e in exempt
            ):
                continue
            if _is_forbidden_file(path.name):
                yield Violation(path.as_posix(), "generated artefact outside a generated/ folder")


def _is_forbidden_file(name: str) -> bool:
    return any(fnmatch(name, p) for p in FORBIDDEN_FILE_PATTERNS) and not any(
        fnmatch(name, p) for p in ALLOWED_FILE_PATTERNS
    )

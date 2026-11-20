"""Packages and modules (R-1, PD-5, PD-14 as D-5 amends it): where a package sits, what its module is
called and which packages that import each other are written as one module.

Pure functions over package paths; a path is the tuple of package names below the subtree package.
"""

import re
from collections.abc import Mapping

from rdf_persistence_generation.generated.rp_generation import UmlModel, UmlPackage, UmlSettings
from rdf_persistence_generation.uml.context import PackagePath

MAIN = "main"
PATH_SEPARATOR = "/"
SEGMENT_SEPARATOR = "__"
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

ModulePath = tuple[str, ...]


def _chain(package_id: int, by_id: Mapping[int, UmlPackage]) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[int] = set()
    current: UmlPackage | None = by_id.get(package_id)
    while current is not None and current.package_id not in seen:
        seen.add(current.package_id)
        names.append(current.name)
        current = by_id.get(current.parent_id) if current.parent_id is not None else None
    return tuple(reversed(names))


def _is_within(path: str, base: str) -> bool:
    """Whether ``path`` is ``base``, below it, or (``base`` being a tail of a path) below its tail: as the reader reads it."""
    return f"/{base}/" in f"/{path}/"


def _is_excluded(full: tuple[str, ...], below: tuple[str, ...], excluded: list[str]) -> bool:
    texts = (PATH_SEPARATOR.join(full), PATH_SEPARATOR.join(below))
    return any(_is_within(text, path) for path in excluded for text in texts if text)


def _subtree_root(
    converted: Mapping[int, UmlPackage], fulls: Mapping[int, tuple[str, ...]]
) -> tuple[str, ...] | None:
    """The path of the subtree package: the converted package whose parent is not converted.

    The reader lists the subtree package first and none of its ancestors, so the root is found by
    its place in the list, not by matching the ``--package`` text, which may be a name or a path.
    """
    tops = sorted(
        fulls[package_id]
        for package_id, package in converted.items()
        if package.parent_id not in converted
    )
    return tops[0] if tops else None


def package_paths(model: UmlModel, settings: UmlSettings) -> dict[int, PackagePath]:
    """The packages of the subtree, each with its path below the subtree package and its exclusion.

    The outside packages (D-17) are laid out with the converted ones, so a path under an
    ``--exclude-package`` is told from one that is simply outside the subtree.
    """
    by_id = _all_packages(model)
    fulls = {package_id: _chain(package_id, by_id) for package_id in by_id}
    root = _subtree_root({p.package_id: p for p in model.uml_packages or []}, fulls)
    excluded = list(settings.exclude_packages or [])
    return {
        package_id: _path_below(full, root, by_id[package_id].note, excluded)
        for package_id, full in fulls.items()
        if root is not None and full[: len(root)] == root
    }


def _all_packages(model: UmlModel) -> dict[int, UmlPackage]:
    packages = [*(model.uml_packages or []), *(model.uml_outside_packages or [])]
    return {package.package_id: package for package in packages}


def _path_below(
    full: tuple[str, ...], root: tuple[str, ...] | None, note: str | None, excluded: list[str]
) -> PackagePath:
    below = full[len(root or ()) :]
    return PackagePath(below, _is_excluded(full, below, excluded), note)


def segment_name(segment: str) -> str:
    """A package name in module form: lower case, each run of other characters one underscore."""
    return _NON_ALNUM.sub("_", segment.lower())


def module_name(root_name: str, path: ModulePath) -> str:
    """``app_library__rare_books`` for ``(library, rare-books)``; the subtree package itself is ``app_main``."""
    tail = SEGMENT_SEPARATOR.join(segment_name(segment) for segment in path) or MAIN
    return f"{root_name}_{tail}"


def _visit(
    node: ModulePath,
    edges: Mapping[ModulePath, set[ModulePath]],
    state: "_Tarjan",
) -> None:
    state.index[node] = state.low[node] = state.counter
    state.counter += 1
    state.stack.append(node)
    state.on_stack.add(node)
    for successor in sorted(edges.get(node, ())):
        if successor not in state.index:
            _visit(successor, edges, state)
            state.low[node] = min(state.low[node], state.low[successor])
        elif successor in state.on_stack:
            state.low[node] = min(state.low[node], state.index[successor])
    if state.low[node] == state.index[node]:
        state.components.append(_pop_component(node, state))


def _pop_component(node: ModulePath, state: "_Tarjan") -> list[ModulePath]:
    component: list[ModulePath] = []
    while True:
        member = state.stack.pop()
        state.on_stack.discard(member)
        component.append(member)
        if member == node:
            return sorted(component)


class _Tarjan:
    """The bookkeeping of one strongly-connected-components search."""

    def __init__(self) -> None:
        self.index: dict[ModulePath, int] = {}
        self.low: dict[ModulePath, int] = {}
        self.stack: list[ModulePath] = []
        self.on_stack: set[ModulePath] = set()
        self.components: list[list[ModulePath]] = []
        self.counter = 0


def cycle_components(
    nodes: list[ModulePath], edges: Mapping[ModulePath, set[ModulePath]]
) -> list[list[ModulePath]]:
    """The groups of two or more modules that import each other, each in path order, groups in path order."""
    state = _Tarjan()
    for node in sorted(nodes):
        if node not in state.index:
            _visit(node, edges, state)
    return sorted(component for component in state.components if len(component) > 1)

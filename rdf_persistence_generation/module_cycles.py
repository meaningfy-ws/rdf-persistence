"""Import cycles among the modules a target generates, and the names a module of a cycle may defer (PD-1 to PD-4).

Pure functions over the text of rendered modules; the standard library and the generated models, never ``linkml``. A node is a
module; an edge ``a -> b`` is a relative ``from .b import ...`` in ``a``. In a module of a cycle, an
imported name of another module of the same cycle is *needed at load* when it is read outside an
annotation, the import itself and a function or lambda body; otherwise it is *deferred*.
"""

import ast
from collections.abc import Hashable, Iterable, Mapping
from typing import Protocol, Self

from rdf_persistence_generation.exceptions import SchemaGenerationError
from rdf_persistence_generation.generated.rp_generation import (
    CycleAnalysis,
    ModuleCycle,
    ModuleDeferral,
)


class _Sortable(Hashable, Protocol):
    def __lt__(self, other: Self, /) -> bool: ...


def _visit[Node: _Sortable](
    node: Node, edges: Mapping[Node, set[Node]], state: "_Tarjan[Node]"
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


def _pop_component[Node: _Sortable](node: Node, state: "_Tarjan[Node]") -> list[Node]:
    component: list[Node] = []
    while True:
        member = state.stack.pop()
        state.on_stack.discard(member)
        component.append(member)
        if member == node:
            return sorted(component)


class _Tarjan[N: _Sortable]:
    """The bookkeeping of one strongly-connected-components search."""

    def __init__(self) -> None:
        self.index: dict[N, int] = {}
        self.low: dict[N, int] = {}
        self.stack: list[N] = []
        self.on_stack: set[N] = set()
        self.components: list[list[N]] = []
        self.counter = 0


def cycle_components[Node: _Sortable](
    nodes: list[Node], edges: Mapping[Node, set[Node]]
) -> list[list[Node]]:
    """The groups of two or more nodes that reach each other, each sorted, the groups sorted."""
    state: _Tarjan[Node] = _Tarjan()
    for node in sorted(nodes):
        if node not in state.index:
            _visit(node, edges, state)
    return sorted(component for component in state.components if len(component) > 1)


def modules_in_cycles(analysis: CycleAnalysis) -> frozenset[str]:
    """Every module that belongs to a cycle."""
    return frozenset(name for cycle in analysis.cycles or [] for name in cycle.modules)


def deferred_by_module(analysis: CycleAnalysis) -> dict[str, dict[str, tuple[str, ...]]]:
    """Per module of a cycle, its deferred names grouped by source module; a module with none has no entry."""
    grouped: dict[str, dict[str, tuple[str, ...]]] = {}
    for deferral in analysis.deferrals or []:
        grouped.setdefault(deferral.module, {})[deferral.source_module] = tuple(deferral.names)
    return grouped


class _LoadNames(ast.NodeVisitor):
    """The names read when the module runs: not in annotations, imports, or function and lambda bodies."""

    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.names.add(node.id)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        return None

    def visit_Import(self, node: ast.Import) -> None:
        return None

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit(node.target)
        if node.value is not None:
            self.visit(node.value)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for expression in (*node.decorator_list, *node.args.defaults):
            self.visit(expression)
        for default in node.args.kw_defaults:
            if default is not None:
                self.visit(default)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for expression in (
            *node.args.defaults,
            *(d for d in node.args.kw_defaults if d is not None),
        ):
            self.visit(expression)


def _load_names(tree: ast.Module) -> set[str]:
    visitor = _LoadNames()
    visitor.visit(tree)
    return visitor.names


def _relative_imports(tree: ast.Module, known: Iterable[str]) -> dict[str, list[ast.alias]]:
    """The names each known sibling module is imported for by ``from .<module> import ...``."""
    known_modules = set(known)
    imports: dict[str, list[ast.alias]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module in known_modules:
            imports.setdefault(node.module, []).extend(node.names)
    return imports


# A module as read: the names it imports from each sibling module, and the names it reads at load.
_Module = tuple[Mapping[str, list[ast.alias]], frozenset[str]]


def _needs_at_load(module: _Module, source: str) -> list[str]:
    imports, needed = module
    return sorted(
        alias.name for alias in imports.get(source, ()) if (alias.asname or alias.name) in needed
    )


def analyse(texts: Mapping[str, str]) -> CycleAnalysis:
    """The cycles among the modules, the names each defers, or ``SchemaGenerationError`` on a load cycle (PD-3)."""
    modules = {name: _read(text, texts) for name, text in texts.items()}
    edges = {
        name: {source for source in imports if source != name}
        for name, (imports, _) in modules.items()
    }
    cycles = tuple(tuple(component) for component in cycle_components(list(modules), edges))
    _refuse_load_cycles(cycles, modules)
    return CycleAnalysis(
        cycles=[ModuleCycle(modules=list(cycle)) for cycle in cycles],
        deferrals=_deferred(cycles, edges, modules),
    )


def _deferred(
    cycles: tuple[tuple[str, ...], ...],
    edges: Mapping[str, set[str]],
    modules: Mapping[str, _Module],
) -> list[ModuleDeferral]:
    """For each module of a cycle and each other module of it, the names imported and not needed at load."""
    deferrals: list[ModuleDeferral] = []
    for name, sources in sorted(_cycle_sources(cycles, edges).items()):
        for source in sources:
            names = _deferred_names(modules[name], source)
            if names:
                deferrals.append(ModuleDeferral(module=name, source_module=source, names=names))
    return deferrals


def _read(text: str, known: Iterable[str]) -> _Module:
    tree = ast.parse(text)
    return _relative_imports(tree, known), frozenset(_load_names(tree))


def _cycle_sources(
    cycles: tuple[tuple[str, ...], ...], edges: Mapping[str, set[str]]
) -> dict[str, list[str]]:
    return {name: sorted(edges[name] & set(cycle)) for cycle in cycles for name in cycle}


def _deferred_names(module: _Module, source: str) -> list[str]:
    needed = set(_needs_at_load(module, source))
    return sorted({alias.name for alias in module[0][source]} - needed)


def _refuse_load_cycles(
    cycles: tuple[tuple[str, ...], ...], modules: Mapping[str, _Module]
) -> None:
    problems: list[str] = []
    for cycle in cycles:
        needed = _load_needs(cycle, modules)
        load_edges: dict[str, set[str]] = {}
        for name, source in needed:
            load_edges.setdefault(name, set()).add(source)
        problems.extend(
            _refusal(component, needed)
            for component in cycle_components(list(load_edges), load_edges)
        )
    if problems:
        raise SchemaGenerationError("; ".join(problems))


def _load_needs(
    cycle: tuple[str, ...], modules: Mapping[str, _Module]
) -> dict[tuple[str, str], list[str]]:
    """For each pair (module, source) of one cycle, the ``source.Name`` the module needs at load."""
    needs = {
        (name, source): [f"{source}.{n}" for n in _needs_at_load(modules[name], source)]
        for name in cycle
        for source in cycle
        if source != name
    }
    return {pair: names for pair, names in needs.items() if names}


def _refusal(component: list[str], needed: Mapping[tuple[str, str], list[str]]) -> str:
    names = sorted(
        text
        for (name, source), texts in needed.items()
        if name in component and source in component
        for text in texts
    )
    return (
        f"{', '.join(component)} import each other and need {', '.join(names)} while they load "
        "(a parent class, a default instance or a union): put these classes in one module, "
        "or break the cycle"
    )

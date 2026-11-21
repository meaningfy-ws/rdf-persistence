"""The walk of the cycle check of nested collections (nested-collections PD-4), in memory.

The caller reads the tenant's nesting skeleton once, ``{collection: members}``; the walk follows it
from the nested members a save adds and says what it reached and whether it came back to the saved
collection. It has no recursion, so the depth of a tree costs nothing.
"""

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Cycle:
    """A way back to the saved collection: it enters at ``closing``, through ``between`` others."""

    closing: str
    between: int


@dataclass(frozen=True)
class Walk:
    """What a walk reached (never the saved collection) and the cycle it found, if any."""

    reached: frozenset[str]
    cycle: Cycle | None


def walk_from(root: str, new: Iterable[str], skeleton: Mapping[str, Collection[str]]) -> Walk:
    """Follow ``skeleton`` from each of the ``new`` members of ``root``, depth first.

    A node not in ``skeleton`` is reached and not entered. Reaching ``root`` is a cycle.
    """
    reached: set[str] = set()
    for start in new:
        stack = [(start, start, 0)]  # (node, the new member it was reached from, depth)
        while stack:
            node, origin, depth = stack.pop()
            if node == root:
                return Walk(frozenset(reached), Cycle(origin, max(depth - 1, 0)))
            if node in reached:
                continue
            reached.add(node)
            stack.extend((member, origin, depth + 1) for member in skeleton.get(node, ()))
    return Walk(frozenset(reached), None)

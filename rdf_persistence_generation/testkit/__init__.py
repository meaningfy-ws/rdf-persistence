"""Test helpers of the generator: the freshness plugin and the conformance suite.

This package imports nothing heavy: the conformance, round-trip and strategy modules, which load
``pyshacl`` or ``hypothesis``, are loaded on first use of one of their names. The freshness plugin
is enabled with ``pytest_plugins = ["rdf_persistence_generation.testkit.freshness"]``.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # what the lazy names are, for type checkers and editors
    from rdf_persistence_generation.testkit.conformance import Conformance
    from rdf_persistence_generation.testkit.conformance import run as conformance_problems
    from rdf_persistence_generation.testkit.roundtrip import round_trip
    from rdf_persistence_generation.testkit.strategies import aggregate

# public name -> (module, attribute)
_LAZY_NAMES = {
    "Conformance": ("rdf_persistence_generation.testkit.conformance", "Conformance"),
    "conformance_problems": ("rdf_persistence_generation.testkit.conformance", "run"),
    "round_trip": ("rdf_persistence_generation.testkit.roundtrip", "round_trip"),
    "aggregate": ("rdf_persistence_generation.testkit.strategies", "aggregate"),
}


def __getattr__(name: str) -> Any:
    """Load a conformance, round-trip or strategy helper on first use, then keep it."""
    if name not in _LAZY_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module, attribute = _LAZY_NAMES[name]
    value = getattr(import_module(module), attribute)
    globals()[name] = value
    return value


__all__ = ["Conformance", "aggregate", "conformance_problems", "round_trip"]

"""Deprecated: this module moved to ``rdf_persistence_generation.testkit.strategies``.

The names are re-exported until the shim will be removed in 0.6.0, the minor release after the one
that ships generator-package (0.5.0). Like the module it forwards to, it needs ``hypothesis``.
"""

import warnings

from rdf_persistence_generation.testkit.strategies import (
    IRI_BASE,
    IRIS,
    MAX_DEPTH,
    MAX_ITEMS,
    TEXT,
    TYPE_VALUES,
    aggregate,
)

warnings.warn(
    "rdf_persistence.testkit.strategies moved to rdf_persistence_generation.testkit.strategies; "
    "the old path will be removed in 0.6.0",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["IRIS", "IRI_BASE", "MAX_DEPTH", "MAX_ITEMS", "TEXT", "TYPE_VALUES", "aggregate"]

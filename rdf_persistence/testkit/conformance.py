"""Deprecated: this module moved to ``rdf_persistence_generation.testkit.conformance``.

The names are re-exported until the shim will be removed in 0.6.0, the minor release after the one
that ships generator-package (0.5.0).
"""

import warnings

from rdf_persistence_generation.testkit.conformance import (
    Conformance,
    coverage_problems,
    generated_classes,
    load_cases,
    run,
    used_kinds,
    verdict_problems,
)

warnings.warn(
    "rdf_persistence.testkit.conformance moved to rdf_persistence_generation.testkit.conformance; "
    "the old path will be removed in 0.6.0",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "Conformance",
    "coverage_problems",
    "generated_classes",
    "load_cases",
    "run",
    "used_kinds",
    "verdict_problems",
]

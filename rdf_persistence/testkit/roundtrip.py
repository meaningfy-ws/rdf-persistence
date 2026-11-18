"""Deprecated: this module moved to ``rdf_persistence_generation.testkit.roundtrip``.

The names are re-exported until the shim will be removed in 0.6.0, the minor release after the one
that ships generator-package (0.5.0).
"""

import warnings

from rdf_persistence_generation.testkit.roundtrip import (
    FRAMING_KEYS,
    assert_isomorphic,
    internal_values,
    public_projection,
    round_trip,
    without_framing,
)

warnings.warn(
    "rdf_persistence.testkit.roundtrip moved to rdf_persistence_generation.testkit.roundtrip; "
    "the old path will be removed in 0.6.0",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "FRAMING_KEYS",
    "assert_isomorphic",
    "internal_values",
    "public_projection",
    "round_trip",
    "without_framing",
]

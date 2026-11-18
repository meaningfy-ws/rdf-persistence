"""Deprecated: this module moved to ``rdf_persistence.core.domain.base``.

``RpModel`` is the same class; the old path keeps working, through the re-export here, until the shim
is removed in the minor release after the one that ships the thematic layout (thematic-structure
PD-8, PD-13). Generated code of a consumer is brought up to date by ``rp-generate``.
"""

import warnings

from rdf_persistence.core.domain.base import RpModel

warnings.warn(
    "rdf_persistence.domain.base moved to rdf_persistence.core.domain.base; "
    "the old path will be removed in the minor release after the one that ships the move",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["RpModel"]

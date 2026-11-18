"""Deprecated: this module moved to ``rdf_persistence_generation.testkit.freshness``.

Enable the plugin with ``pytest_plugins = ["rdf_persistence_generation.testkit.freshness"]``. The
old path keeps working, through the two hooks re-exported here, until the shim will be removed in
0.6.0, the minor release after the one that ships generator-package (0.5.0).
"""

import warnings

from rdf_persistence_generation.testkit.freshness import (
    DEFAULT_PROJECT,
    PROJECTS_OPTION,
    pytest_addoption,
    pytest_sessionstart,
)

warnings.warn(
    "rdf_persistence.testkit.freshness moved to rdf_persistence_generation.testkit.freshness; "
    "the old path will be removed in 0.6.0",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["DEFAULT_PROJECT", "PROJECTS_OPTION", "pytest_addoption", "pytest_sessionstart"]

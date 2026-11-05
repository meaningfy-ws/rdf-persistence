"""Test helpers shipped with the toolkit.

This package imports nothing heavy. The container fixtures live in
``rdf_persistence.testkit.containers`` and need the extra ``rdf-persistence[testkit]``.
"""

from rdf_persistence.testkit.fakes import FakeStore
from rdf_persistence.testkit.network import no_network

__all__ = ["FakeStore", "no_network"]

"""The four generator testkit shims are gone (generator-package PD-3, D-12; issue #165).

The library's testkit keeps no path to the freshness plugin, the conformance suite, the round-trip
check or the strategies: they live in ``rdf_persistence_generation.testkit``.
"""

import importlib

import pytest

import rdf_persistence.testkit as testkit

REMOVED_MODULES = ("freshness", "conformance", "roundtrip", "strategies")
REMOVED_NAMES = ("Conformance", "conformance_problems", "round_trip", "aggregate")


@pytest.mark.parametrize("module", REMOVED_MODULES)
def test_importing_a_removed_shim_path_raises_module_not_found(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"rdf_persistence.testkit.{module}")


@pytest.mark.parametrize("name", REMOVED_NAMES)
def test_a_removed_lazy_name_is_no_longer_exported(name: str) -> None:
    assert name not in testkit.__all__, "the name is still exported"
    with pytest.raises(AttributeError):
        getattr(testkit, name)


def test_assert_isomorphic_stays_in_the_library_testkit() -> None:
    """D-10: the graph comparison lives in ``rdf_persistence.testkit.graphs``."""
    from rdf_persistence.testkit import assert_isomorphic
    from rdf_persistence.testkit.graphs import assert_isomorphic as graphs_one

    assert assert_isomorphic is graphs_one, "the public name is the graphs module's function"

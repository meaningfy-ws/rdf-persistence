"""The module functions that only delegated to ``DEFAULT_IRIS`` are gone (thematic-structure PD-5, 8.1)."""

import pytest

from rdf_persistence.iris.services import iris

REMOVED = (
    "_default_iris",
    "mint_tenant_iri",
    "tenant_iri",
    "aggregate_iri",
    "is_aggregate_iri",
    "is_aggregate_graph_iri",
    "is_loaded_graph_of",
    "mint_part_iri",
    "loaded_graph_iri",
    "tenant_resource_name",
    "principal_iri",
    "mint_aggregate_iri",
)


@pytest.mark.parametrize("name", REMOVED)
def test_a_removed_wrapper_is_no_longer_in_the_iris_module(name: str) -> None:  # TC-31
    assert not hasattr(iris, name), f"{name} still stands in rdf_persistence.iris.services.iris"

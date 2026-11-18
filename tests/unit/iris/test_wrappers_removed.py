"""The eleven module functions that only delegated to ``DEFAULT_IRIS`` are gone (thematic-structure PD-5).

``mint_aggregate_iri`` stays, public and warning, until stage 8 removes it.
"""

import re
import warnings

import pytest
from rdflib import URIRef

import rdf_persistence
from rdf_persistence.iris.services import iris
from rdf_persistence.iris.services.iris import DEFAULT_IRIS

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
)
TENANT = "https://example.org/library/tenants/12345678-1234-4234-8234-123456789abc"


@pytest.mark.parametrize("name", REMOVED)
def test_a_removed_wrapper_is_no_longer_in_the_iris_module(name: str) -> None:  # TC-31
    assert not hasattr(iris, name), f"{name} still stands in rdf_persistence.iris.services.iris"


def test_mint_aggregate_iri_warns_naming_its_replacement() -> None:  # TC-32
    with pytest.warns(DeprecationWarning, match=re.escape("Iris.mint_aggregate")):
        iris.mint_aggregate_iri(TENANT, "books")


def test_mint_aggregate_iri_warns_at_the_line_of_its_caller() -> None:  # TC-32
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        iris.mint_aggregate_iri(TENANT, "books")
    assert caught[0].filename == __file__, "the warning points at the caller, not at iris.py"


def test_mint_aggregate_iri_has_the_shape_of_the_default_policy() -> None:  # TC-32
    with pytest.warns(DeprecationWarning):
        minted = iris.mint_aggregate_iri(TENANT, "books")
    expected = DEFAULT_IRIS.mint_aggregate(TENANT, cls_type="", rp_path="books")
    shape = re.compile(rf"{re.escape(TENANT)}/books/[0-9a-f-]{{36}}")
    assert isinstance(minted, URIRef), "the result is an IRI"
    assert shape.fullmatch(str(minted)), "tenant, path, a UUID"
    assert shape.fullmatch(str(expected)), "the policy mints the same shape"


def test_the_public_name_is_the_warning_function() -> None:  # TC-32
    assert rdf_persistence.mint_aggregate_iri is iris.mint_aggregate_iri, "one object"

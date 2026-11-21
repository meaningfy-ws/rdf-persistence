"""The two deprecation shims and ``mint_aggregate_iri`` are gone (thematic-structure 8.1, D-26).

They shipped in no release, so there was no deprecation period: the move and the removal are one release.
"""

import importlib

import pytest

import rdf_persistence


@pytest.mark.parametrize(
    "path",
    [
        "rdf_persistence.domain.base",
        "rdf_persistence.domain",
        "rdf_persistence.adapters.fuseki",
        "rdf_persistence.adapters",
    ],
)
def test_a_removed_shim_path_cannot_be_imported(path: str) -> None:  # TC-80
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(path)


def test_mint_aggregate_iri_is_no_longer_a_public_name() -> None:  # TC-81
    with pytest.raises(AttributeError):
        _ = rdf_persistence.mint_aggregate_iri
    assert "mint_aggregate_iri" not in rdf_persistence.__all__, "it is not exported either"


def test_mint_aggregate_iri_is_no_longer_in_the_iris_module() -> None:  # TC-81
    from rdf_persistence.iris.services import iris

    assert not hasattr(iris, "mint_aggregate_iri"), "the replacement is Iris.mint_aggregate"

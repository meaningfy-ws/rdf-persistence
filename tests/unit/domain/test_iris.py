"""IRI derivation and minting, and the names of PD-6a."""

import re
import uuid

import pytest
from rdflib import URIRef

from rdf_persistence.domain.iris import (
    access_iri,
    graph_iri,
    loaded_graph_iri,
    meta_graph_iri,
    mint_aggregate_iri,
    mint_part_iri,
    mint_tenant_iri,
    registry_graph_iri,
    system_database_name,
    tenant_name_prefix,
    tenant_resource_name,
)

BASE = "https://example.org/library/"
UUID_RE = "[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
TENANT = URIRef(f"{BASE}libraries/12345678-1234-4234-8234-123456789abc")


def test_graph_iri_appends_graph():
    root = f"{BASE}libraries/t/books/b"
    assert graph_iri(root) == URIRef(f"{root}/graph")
    assert graph_iri(root) != URIRef(root), "never the root IRI itself"


def test_mint_tenant_iri_has_the_base_segment_and_a_uuid():
    iri = mint_tenant_iri(BASE, "libraries")
    assert re.fullmatch(f"{re.escape(BASE)}libraries/{UUID_RE}", iri), iri
    assert mint_tenant_iri(BASE, "libraries") != iri, "each mint is fresh"


def test_mint_aggregate_iri_sits_under_the_tenant():
    iri = mint_aggregate_iri(TENANT, "books")
    assert re.fullmatch(f"{re.escape(TENANT)}/books/{UUID_RE}", iri), iri


def test_loaded_graph_iri_sits_under_the_aggregate():
    aggregate = mint_aggregate_iri(TENANT, "books")
    assert re.fullmatch(f"{re.escape(aggregate)}/content/{UUID_RE}", loaded_graph_iri(aggregate))


def test_meta_registry_and_access_iris():
    assert meta_graph_iri(TENANT) == URIRef(f"{TENANT}/meta")
    assert registry_graph_iri(TENANT) == URIRef(f"{TENANT}/registry")
    assert access_iri(TENANT) == URIRef(f"{TENANT}/access")
    assert graph_iri(access_iri(TENANT)) == URIRef(f"{TENANT}/access/graph")


@pytest.mark.parametrize("segment", ["", "a/b", "a b", "a>b", "../x", "a?b", "a#b"])
def test_a_segment_that_is_not_a_path_segment_is_refused(segment):
    with pytest.raises(ValueError, match="segment"):
        mint_aggregate_iri(TENANT, segment)
    with pytest.raises(ValueError, match="segment"):
        mint_tenant_iri(BASE, segment)


def test_names_follow_pd_6a():
    assert system_database_name("lib") == "lib-system"
    assert tenant_name_prefix("lib") == "lib-t-"
    assert tenant_resource_name("lib", TENANT) == "lib-t-12345678123442348234123456789abc"


def test_tenant_name_starts_with_the_sweep_prefix_and_fits_a_bucket_name():
    name = tenant_resource_name("a" * 20, mint_tenant_iri(BASE, "libraries"))
    assert name.startswith(tenant_name_prefix("a" * 20))
    assert re.fullmatch("[a-z0-9-]{3,63}", name), name


@pytest.mark.parametrize("prefix", ["", "Lib", "a" * 21, "li b", "lib_x", "-lib"])
def test_a_prefix_outside_pd_6a_is_refused(prefix):
    with pytest.raises(ValueError, match="prefix"):
        system_database_name(prefix)
    with pytest.raises(ValueError, match="prefix"):
        tenant_name_prefix(prefix)


def test_tenant_name_needs_a_uuid_last_segment():
    with pytest.raises(ValueError, match="tenant IRI"):
        tenant_resource_name("lib", URIRef(f"{BASE}libraries/not-a-uuid"))


def test_minted_ids_are_uuid4():
    last = mint_tenant_iri(BASE, "libraries").rsplit("/", 1)[1]
    assert uuid.UUID(last).version == 4


def test_mint_part_iri_sits_under_the_root_and_is_fresh():
    root = f"{BASE}libraries/t/books/b"
    iri = mint_part_iri(root)
    assert re.fullmatch(f"{re.escape(root)}/parts/{UUID_RE}", iri), iri
    assert mint_part_iri(root) != iri, "each mint is fresh"

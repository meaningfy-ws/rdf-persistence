"""IRI derivation and minting, and the names of PD-6a."""

import re
import uuid

import pytest
from rdflib import URIRef

from rdf_persistence.domain.exceptions import InvalidIri
from rdf_persistence.domain.iris import (
    access_iri,
    graph_iri,
    is_aggregate_graph_iri,
    is_aggregate_iri,
    is_inside_tenant,
    is_loaded_graph_of,
    loaded_graph_iri,
    meta_graph_iri,
    mint_aggregate_iri,
    mint_part_iri,
    mint_tenant_iri,
    principal_iri,
    registry_graph_iri,
    skolem_iri,
    system_database_name,
    tenant_iri_of_access,
    tenant_name_prefix,
    tenant_resource_name,
    toolkit_principal_iri,
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
    with pytest.raises(InvalidIri, match="segment"):
        mint_aggregate_iri(TENANT, segment)
    with pytest.raises(InvalidIri, match="segment"):
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
    with pytest.raises(InvalidIri, match="prefix"):
        system_database_name(prefix)
    with pytest.raises(InvalidIri, match="prefix"):
        tenant_name_prefix(prefix)


def test_tenant_name_needs_a_uuid_last_segment():
    with pytest.raises(InvalidIri, match="tenant IRI"):
        tenant_resource_name("lib", URIRef(f"{BASE}libraries/not-a-uuid"))


def test_minted_ids_are_uuid4():
    last = mint_tenant_iri(BASE, "libraries").rsplit("/", 1)[1]
    assert uuid.UUID(last).version == 4


def test_mint_part_iri_sits_under_the_root_and_is_fresh():
    root = f"{BASE}libraries/t/books/b"
    iri = mint_part_iri(root)
    assert re.fullmatch(f"{re.escape(root)}/parts/{UUID_RE}", iri), iri
    assert mint_part_iri(root) != iri, "each mint is fresh"


def test_the_tenant_of_an_access_record_is_the_iri_it_hangs_under():
    assert tenant_iri_of_access(access_iri(TENANT)) == TENANT


def test_an_iri_that_is_not_an_access_record_has_no_tenant():
    with pytest.raises(InvalidIri, match="access record"):
        tenant_iri_of_access(f"{TENANT}/books/1")


@pytest.mark.parametrize(
    "last",
    [
        "12345678123442348234123456789ABC",  # no hyphens
        "12345678-1234-4234-8234-123456789ABC",  # upper case
        "{12345678-1234-4234-8234-123456789abc}",
        "urn:uuid:12345678-1234-4234-8234-123456789abc",
        "12345678123442348234123456789abc",
    ],
)
def test_tenant_name_needs_a_canonical_uuid(last):
    with pytest.raises(InvalidIri, match="tenant IRI"):
        tenant_resource_name("lib", f"{BASE}libraries/{last}")


def test_an_iri_rule_breach_is_an_invalid_iri_and_still_a_value_error():
    assert issubclass(InvalidIri, ValueError), "callers that catch ValueError keep working"


def test_a_skolem_iri_lives_under_its_graph_and_is_fresh_each_time():
    graph = graph_iri(f"{TENANT}/books/1")
    first = skolem_iri(graph)
    assert first.startswith(f"{graph}/.well-known/genid/"), "under the graph, in the genid space"
    assert skolem_iri(graph) != first, "each mint is fresh"


def test_the_toolkit_principal_is_toolkit_under_the_base():
    assert toolkit_principal_iri(BASE) == URIRef(f"{BASE}toolkit")


@pytest.mark.parametrize(
    ("iri", "inside"),
    [
        (f"{TENANT}/books/1", True),
        (f"{TENANT}/access", True),
        (str(TENANT), False),  # the tenant itself is not inside itself
        (f"{TENANT}x/books/1", False),  # a longer sibling
        ("https://example.org/other/books/1", False),
    ],
)
def test_an_iri_is_inside_a_tenant_only_below_its_path(iri, inside):
    assert is_inside_tenant(str(TENANT), iri) is inside, iri


AGGREGATE = f"{TENANT}/books/{uuid.uuid4()}"


@pytest.mark.parametrize(
    ("iri", "accepted"),
    [
        (AGGREGATE, True),
        (str(TENANT), True),  # the tenant's root object
        (f"{TENANT}/access", True),  # the access record has a fixed IRI
        (f"{TENANT}/books/1", False),  # not a UUID
        (f"{TENANT}/books/{str(uuid.uuid4()).upper()}", False),  # not canonical
        (f"{TENANT}/books/{uuid.uuid4().hex}", False),  # no hyphens
        (f"{AGGREGATE}/content/x", False),  # a path below an aggregate
        (f"{AGGREGATE}/graph", False),
        (f"{TENANT}/Books/{uuid.uuid4()}", False),  # not a path segment
        (f"{TENANT}/books/{uuid.uuid4()}/", False),
        (f"{TENANT}x/books/{uuid.uuid4()}", False),  # a longer sibling
    ],
)
def test_an_aggregate_iri_is_the_minted_form_or_the_tenant_root(iri, accepted):
    assert is_aggregate_iri(str(TENANT), iri) is accepted, iri


@pytest.mark.parametrize(
    ("iri", "accepted"),
    [
        (str(graph_iri(str(mint_aggregate_iri(TENANT, "books")))), True),
        (str(graph_iri(str(access_iri(TENANT)))), True),
        (str(graph_iri(str(TENANT))), False),  # the tenant root has no aggregate graph of its own
        (str(mint_aggregate_iri(TENANT, "books")), False),  # the root, not its graph
        (f"{TENANT}/books/x/graph", False),
        (f"{BASE}libraries/{uuid.uuid4()}/books/{uuid.uuid4()}/graph", False),
    ],
)
def test_an_aggregate_graph_iri_is_the_graph_of_a_tenants_aggregate(iri, accepted):
    assert is_aggregate_graph_iri(str(TENANT), iri) is accepted, iri


def test_every_minted_aggregate_iri_is_an_aggregate_iri():
    assert is_aggregate_iri(str(TENANT), str(mint_aggregate_iri(TENANT, "books")))


@pytest.mark.parametrize(
    ("graph", "loaded"),
    [
        (str(loaded_graph_iri(AGGREGATE)), True),
        (f"{AGGREGATE}/content/{uuid.uuid4()}/more", False),
        (f"{AGGREGATE}/content/x", False),  # not a UUID
        (f"{AGGREGATE}/content/{uuid.uuid4().hex}", False),
        (f"{AGGREGATE}/content/{str(uuid.uuid4()).upper()}", False),
        (f"{AGGREGATE}/content", False),
        (f"{AGGREGATE}0/content/{uuid.uuid4()}", False),  # a sibling sharing the prefix text
        (f"{TENANT}/books/{uuid.uuid4()}/content/{uuid.uuid4()}", False),  # another aggregate's
    ],
)
def test_a_loaded_graph_is_the_minted_form_under_its_aggregate(graph, loaded):
    assert is_loaded_graph_of(AGGREGATE, graph) is loaded, graph


@pytest.mark.parametrize(
    ("issuer", "subject", "expected"),
    [
        ("https://id.example.org", "42", "https://id.example.org/users/42"),
        ("https://id.example.org/", "42", "https://id.example.org/users/42"),
        ("https://id.example.org", "a/../b c", "https://id.example.org/users/a%2F..%2Fb%20c"),
    ],
)
def test_principal_iri_keeps_the_subject_in_one_segment(issuer, subject, expected) -> None:
    assert str(principal_iri(issuer, subject)) == expected, "the principal IRI is wrong"

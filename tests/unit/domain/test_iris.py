"""IRI derivation and minting, and the names of PD-6a."""

import re
import uuid

import pytest
from rdflib import URIRef

from rdf_persistence.domain.exceptions import InvalidIri, NotFound
from rdf_persistence.domain.iris import (
    DEFAULT_IRIS,
    aggregate_iri,
    graph_iri,
    is_aggregate_graph_iri,
    is_aggregate_iri,
    is_canonical_uuid,
    is_inside_tenant,
    is_loaded_graph_of,
    loaded_graph_iri,
    mint_aggregate_iri,
    mint_part_iri,
    mint_tenant_iri,
    principal_iri,
    root_of_graph,
    skolem_iri,
    system_database_name,
    tenant_iri,
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


def test_root_of_graph_is_the_inverse_of_graph_iri():
    root = f"{BASE}libraries/t/books/b"
    assert root_of_graph(graph_iri(root)) == URIRef(root)


@pytest.mark.parametrize(
    "iri", [f"{BASE}libraries/t/books/b", f"{BASE}libraries/t/books/b/graphs", "/graph"]
)
def test_root_of_graph_refuses_what_is_not_a_graph_iri(iri):
    with pytest.raises(InvalidIri):
        root_of_graph(URIRef(iri))


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
    assert DEFAULT_IRIS.meta(TENANT) == URIRef(f"{TENANT}/meta")
    assert DEFAULT_IRIS.registry(TENANT) == URIRef(f"{TENANT}/registry")
    assert DEFAULT_IRIS.access(TENANT) == URIRef(f"{TENANT}/access")
    assert graph_iri(DEFAULT_IRIS.access(TENANT)) == URIRef(f"{TENANT}/access/graph")


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
    # the shim answers for the default policy, whose base is DEFAULT_IRIS's (PD-12n)
    tenant = URIRef(f"{DEFAULT_IRIS.settings.base}tenants/12345678-1234-4234-8234-123456789abc")
    assert DEFAULT_IRIS.tenant_of_access(DEFAULT_IRIS.access(tenant)) == tenant


def test_an_iri_that_is_not_an_access_record_has_no_tenant():
    with pytest.raises(InvalidIri, match="access record"):
        DEFAULT_IRIS.tenant_of_access(f"{TENANT}/books/1")


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


# Fixed, so every xdist worker collects the same parameter ids.
AGGREGATE_ID = "898b0b0d-e7b5-4c3d-99e3-db49565d00aa"
OTHER_ID = "9e72d652-503c-4b1a-97a4-14c9253c17dd"
AGGREGATE = f"{TENANT}/books/{AGGREGATE_ID}"


@pytest.mark.parametrize(
    ("iri", "accepted"),
    [
        (AGGREGATE, True),
        (str(TENANT), True),  # the tenant's root object
        (f"{TENANT}/access", True),  # the access record has a fixed IRI
        (f"{TENANT}/books/1", False),  # not a UUID
        (f"{TENANT}/books/{OTHER_ID.upper()}", False),  # not canonical
        (f"{TENANT}/books/{OTHER_ID.replace('-', '')}", False),  # no hyphens
        (f"{AGGREGATE}/content/x", False),  # a path below an aggregate
        (f"{AGGREGATE}/graph", False),
        (f"{TENANT}/Books/{OTHER_ID}", False),  # not a path segment
        (f"{TENANT}/books/{OTHER_ID}/", False),
        (f"{TENANT}x/books/{OTHER_ID}", False),  # a longer sibling
    ],
)
def test_an_aggregate_iri_is_the_minted_form_or_the_tenant_root(iri, accepted):
    assert is_aggregate_iri(str(TENANT), iri) is accepted, iri


@pytest.mark.parametrize(
    ("iri", "accepted"),
    [
        pytest.param(
            str(graph_iri(str(mint_aggregate_iri(TENANT, "books")))), True, id="a minted graph"
        ),
        (
            str(graph_iri(str(DEFAULT_IRIS.access(TENANT)))),
            False,
        ),  # the access record is not an aggregate
        (str(graph_iri(str(TENANT))), False),  # the tenant root has no aggregate graph of its own
        pytest.param(str(mint_aggregate_iri(TENANT, "books")), False, id="the root, not its graph"),
        (f"{TENANT}/books/x/graph", False),
        (f"{BASE}libraries/{OTHER_ID}/books/{OTHER_ID}/graph", False),
    ],
)
def test_an_aggregate_graph_iri_is_the_graph_of_a_tenants_aggregate(iri, accepted):
    assert is_aggregate_graph_iri(str(TENANT), iri) is accepted, iri


def test_every_minted_aggregate_iri_is_an_aggregate_iri():
    assert is_aggregate_iri(str(TENANT), str(mint_aggregate_iri(TENANT, "books")))


@pytest.mark.parametrize(
    ("graph", "loaded"),
    [
        pytest.param(str(loaded_graph_iri(AGGREGATE)), True, id="a minted loaded graph"),
        (f"{AGGREGATE}/content/{OTHER_ID}/more", False),
        (f"{AGGREGATE}/content/x", False),  # not a UUID
        (f"{AGGREGATE}/content/{OTHER_ID.replace('-', '')}", False),
        (f"{AGGREGATE}/content/{OTHER_ID.upper()}", False),
        (f"{AGGREGATE}/content", False),
        (f"{AGGREGATE}0/content/{OTHER_ID}", False),  # a sibling sharing the prefix text
        (f"{TENANT}/books/{OTHER_ID}/content/{OTHER_ID}", False),  # another aggregate's
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


# --- the IRIs of a path (PD-14b): one rule, validating ------------------------------------------

UUID_A = "12345678-1234-4234-8234-123456789abc"


@pytest.mark.parametrize(
    ("text", "canonical"),
    [
        (UUID_A, True),
        (UUID_A.upper(), False),
        (UUID_A.replace("-", ""), False),
        ("books", False),
        ("", False),
    ],
)
def test_only_a_lower_case_hyphenated_uuid_is_canonical(text, canonical):
    assert is_canonical_uuid(text) is canonical


def test_a_tenant_iri_is_the_base_the_segment_and_the_id():
    assert tenant_iri(BASE, "libraries", UUID_A) == URIRef(f"{BASE}libraries/{UUID_A}")


@pytest.mark.parametrize("tenant_id", ["nope", UUID_A.upper(), f"{UUID_A}/books", "..", ""])
def test_a_tenant_id_that_is_not_a_canonical_uuid_is_not_found(tenant_id):
    with pytest.raises(NotFound):
        tenant_iri(BASE, "libraries", tenant_id)


def test_a_tenant_segment_that_breaks_the_rule_is_an_invalid_iri():
    with pytest.raises(InvalidIri):
        tenant_iri(BASE, "Libraries/..", UUID_A)


def test_an_aggregate_iri_is_the_tenant_the_path_and_the_id():
    tenant = f"{BASE}libraries/{UUID_A}"
    assert aggregate_iri(tenant, "books", UUID_A) == URIRef(f"{tenant}/books/{UUID_A}")
    assert is_aggregate_iri(tenant, aggregate_iri(tenant, "books", UUID_A)), (
        "what it builds is what is accepted"
    )


@pytest.mark.parametrize("aggregate_id", ["nope", "..", f"{UUID_A}/graph", UUID_A.upper(), ""])
def test_an_aggregate_id_that_is_not_a_canonical_uuid_is_not_found(aggregate_id):
    with pytest.raises(NotFound):
        aggregate_iri(f"{BASE}libraries/{UUID_A}", "books", aggregate_id)

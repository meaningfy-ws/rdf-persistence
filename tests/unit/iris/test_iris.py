"""IRI derivation and minting, and the names of PD-6a."""

import re
import string
import uuid

import pytest
from pydantic import ValidationError
from rdflib import URIRef

from rdf_persistence.core.domain.exceptions import InvalidIri, NotFound
from rdf_persistence.iris.domain.layout import (
    graph_iri,
    system_database_name,
    tenant_name_prefix,
)
from rdf_persistence.iris.services.generated.rp_iris_services import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.iris.services.generated.templates.rp_iris_templates import (
    IriParts,
    IriTemplateVariables,
)
from rdf_persistence.iris.services.iris import (
    DEFAULT_IRIS,
    Iris,
    effective_policy,
    iri_template_variables,
)

BASE = "https://example.org/library/"
UUID_RE = "[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
TENANT = URIRef(f"{BASE}libraries/12345678-1234-4234-8234-123456789abc")


def iris_under(base: str, segment: str, prefix: str = "rp") -> Iris:
    """The default policy under ``base`` and the tenant ``segment``, naming databases by ``prefix``.

    What the module functions removed in thematic-structure PD-5 built for each call.
    """
    return Iris(DEFAULT_IRIS.settings.replaced(base=base, tenant_segment=segment, prefix=prefix))


LIBRARIES = iris_under(BASE, "libraries", "lib")


def test_mint_tenant_iri_has_the_base_segment_and_a_uuid():
    iri = LIBRARIES.mint_tenant()
    assert re.fullmatch(f"{re.escape(BASE)}libraries/{UUID_RE}", iri), iri
    assert LIBRARIES.mint_tenant() != iri, "each mint is fresh"


def test_mint_aggregate_iri_sits_under_the_tenant():
    iri = DEFAULT_IRIS.mint_aggregate(TENANT, cls_type="", rp_path="books")
    assert re.fullmatch(f"{re.escape(TENANT)}/books/{UUID_RE}", iri), iri


def test_loaded_graph_iri_sits_under_the_aggregate():
    aggregate = DEFAULT_IRIS.mint_aggregate(TENANT, cls_type="", rp_path="books")
    assert re.fullmatch(
        f"{re.escape(aggregate)}/content/{UUID_RE}",
        DEFAULT_IRIS.mint_loaded_graph(tenant="", root=aggregate),
    ), "a loaded graph sits under its aggregate with a uuid"


def test_meta_registry_and_access_iris():
    assert DEFAULT_IRIS.meta(TENANT) == URIRef(f"{TENANT}/meta"), (
        "the meta graph hangs under the tenant"
    )
    assert DEFAULT_IRIS.registry(TENANT) == URIRef(f"{TENANT}/registry"), (
        "the registry graph hangs under the tenant"
    )
    assert DEFAULT_IRIS.access(TENANT) == URIRef(f"{TENANT}/access"), (
        "the access record hangs under the tenant"
    )
    assert graph_iri(DEFAULT_IRIS.access(TENANT)) == URIRef(f"{TENANT}/access/graph"), (
        "the access record's graph is its slash graph"
    )


@pytest.mark.parametrize("segment", ["", "a/b", "a b", "a>b", "../x", "a?b", "a#b"])
def test_a_segment_that_is_not_a_path_segment_is_refused(segment):
    with pytest.raises(InvalidIri, match="segment"):
        DEFAULT_IRIS.mint_aggregate(TENANT, cls_type="", rp_path=segment)
    # the tenant segment is a setting now: the settings model refuses it before an Iris is built
    with pytest.raises(ValidationError, match="tenant_segment"):
        iris_under(BASE, segment)


def test_names_follow_pd_6a():
    assert system_database_name("lib") == "lib-system", (
        "the system database is named after the deployment"
    )
    assert tenant_name_prefix("lib") == "lib-t-", (
        "the tenant prefix is the deployment plus the tenant marker"
    )
    assert LIBRARIES.resource_name(TENANT) == "lib-t-12345678123442348234123456789abc", (
        "a tenant resource is the prefix plus its id in hex"
    )


def test_tenant_name_starts_with_the_sweep_prefix_and_fits_a_bucket_name():
    longest = iris_under(BASE, "libraries", "a" * 20)
    name = longest.resource_name(longest.mint_tenant())
    assert name.startswith(tenant_name_prefix("a" * 20)), (
        "a tenant resource name starts with the sweep prefix"
    )
    assert re.fullmatch("[a-z0-9-]{3,63}", name), name


def test_tenant_name_needs_a_uuid_last_segment():
    with pytest.raises(InvalidIri, match="tenant IRI"):
        LIBRARIES.resource_name(URIRef(f"{BASE}libraries/not-a-uuid"))


def test_minted_ids_are_uuid4():
    last = LIBRARIES.mint_tenant().rsplit("/", 1)[1]
    assert uuid.UUID(last).version == 4, "a minted id is a version 4 uuid"


def test_mint_part_iri_sits_under_the_root_and_is_fresh():
    root = f"{BASE}libraries/t/books/b"
    iri = DEFAULT_IRIS.mint_part(tenant="", root=root, cls_type="")
    assert re.fullmatch(f"{re.escape(root)}/parts/{UUID_RE}", iri), iri
    assert DEFAULT_IRIS.mint_part(tenant="", root=root, cls_type="") != iri, "each mint is fresh"


def test_the_tenant_of_an_access_record_is_the_iri_it_hangs_under():
    # the shim answers for the default policy, whose base is DEFAULT_IRIS's (PD-12n)
    tenant = URIRef(f"{DEFAULT_IRIS.settings.base}tenants/12345678-1234-4234-8234-123456789abc")
    assert DEFAULT_IRIS.tenant_of_access(DEFAULT_IRIS.access(tenant)) == tenant, (
        "the tenant is recovered from its access record"
    )


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
        LIBRARIES.resource_name(f"{BASE}libraries/{last}")


def test_an_iri_rule_breach_is_an_invalid_iri_and_still_a_value_error():
    assert issubclass(InvalidIri, ValueError), "callers that catch ValueError keep working"


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
    assert DEFAULT_IRIS.is_aggregate(str(TENANT), iri) is accepted, iri


@pytest.mark.parametrize(
    ("iri", "accepted"),
    [
        pytest.param(
            str(graph_iri(str(DEFAULT_IRIS.mint_aggregate(TENANT, cls_type="", rp_path="books")))),
            True,
            id="a minted graph",
        ),
        (
            str(graph_iri(str(DEFAULT_IRIS.access(TENANT)))),
            False,
        ),  # the access record is not an aggregate
        (str(graph_iri(str(TENANT))), False),  # the tenant root has no aggregate graph of its own
        pytest.param(
            str(DEFAULT_IRIS.mint_aggregate(TENANT, cls_type="", rp_path="books")),
            False,
            id="the root, not its graph",
        ),
        (f"{TENANT}/books/x/graph", False),
        (f"{BASE}libraries/{OTHER_ID}/books/{OTHER_ID}/graph", False),
    ],
)
def test_an_aggregate_graph_iri_is_the_graph_of_a_tenants_aggregate(iri, accepted):
    assert DEFAULT_IRIS.is_aggregate_graph(str(TENANT), iri) is accepted, iri


def test_every_minted_aggregate_iri_is_an_aggregate_iri():
    assert DEFAULT_IRIS.is_aggregate(
        str(TENANT), str(DEFAULT_IRIS.mint_aggregate(TENANT, cls_type="", rp_path="books"))
    ), "a minted aggregate IRI is recognised as an aggregate of its tenant"


@pytest.mark.parametrize(
    ("graph", "loaded"),
    [
        pytest.param(
            str(DEFAULT_IRIS.mint_loaded_graph(tenant="", root=AGGREGATE)),
            True,
            id="a minted loaded graph",
        ),
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
    assert DEFAULT_IRIS.is_loaded_graph(None, graph, AGGREGATE) is loaded, graph


@pytest.mark.parametrize(
    ("issuer", "subject", "expected"),
    [
        ("https://id.example.org", "42", "https://id.example.org/users/42"),
        ("https://id.example.org/", "42", "https://id.example.org/users/42"),
        ("https://id.example.org", "a/../b c", "https://id.example.org/users/a%2F..%2Fb%20c"),
    ],
)
def test_principal_iri_keeps_the_subject_in_one_segment(issuer, subject, expected) -> None:
    assert str(DEFAULT_IRIS.principal(issuer, subject)) == expected, "the principal IRI is wrong"


# --- the IRIs of a path (PD-14b): one rule, validating ------------------------------------------

UUID_A = "12345678-1234-4234-8234-123456789abc"


def test_a_tenant_iri_is_the_base_the_segment_and_the_id():
    assert LIBRARIES.tenant(UUID_A) == URIRef(f"{BASE}libraries/{UUID_A}"), (
        "a tenant IRI is the base, the segment and the id"
    )


@pytest.mark.parametrize("tenant_id", ["nope", UUID_A.upper(), f"{UUID_A}/books", "..", ""])
def test_a_tenant_id_that_is_not_a_canonical_uuid_is_not_found(tenant_id):
    with pytest.raises(NotFound):
        LIBRARIES.tenant(tenant_id)


def test_a_tenant_segment_that_breaks_the_rule_is_refused_by_the_settings():
    with pytest.raises(ValidationError, match="tenant_segment"):
        iris_under(BASE, "Libraries/..")


def test_an_aggregate_iri_is_the_tenant_the_path_and_the_id():
    tenant = f"{BASE}libraries/{UUID_A}"
    assert DEFAULT_IRIS.aggregate(tenant, cls_type="", rp_path="books", object_id=UUID_A) == URIRef(
        f"{tenant}/books/{UUID_A}"
    ), "an aggregate IRI is the tenant, the path and the id"
    assert DEFAULT_IRIS.is_aggregate(
        tenant, DEFAULT_IRIS.aggregate(tenant, cls_type="", rp_path="books", object_id=UUID_A)
    ), "what it builds is what is accepted"


@pytest.mark.parametrize("aggregate_id", ["nope", "..", f"{UUID_A}/graph", UUID_A.upper(), ""])
def test_an_aggregate_id_that_is_not_a_canonical_uuid_is_not_found(aggregate_id):
    with pytest.raises(NotFound):
        DEFAULT_IRIS.aggregate(
            f"{BASE}libraries/{UUID_A}", cls_type="", rp_path="books", object_id=aggregate_id
        )


def _settings(deployment: str | None = None) -> ServiceSettings:
    return ServiceSettings(
        base="https://ex.org/",
        deployment=deployment,
        prefix="lib",
        tenant_segment="t",
        creator_role="owner",
        roles_claim="roles",
    )


def test_tc22_one_helper_gives_the_template_variables_to_both_sites():
    """TC-22: a missing deployment is the empty string, and the policy and ``Iris`` read the same variables."""
    settings = _settings()
    variables = iri_template_variables(settings)
    assert variables == IriTemplateVariables(
        base="https://ex.org/", deployment="", tenant_segment="t"
    )
    assert Iris(settings)._fixed == variables, "Iris reads the helper's variables"
    assert effective_policy(None, settings).tenant_template == "https://ex.org/t/{tenant_id}", (
        "the policy writes the helper's variables into its templates"
    )


def test_tc22_a_deployment_is_kept_as_it_is():
    """TC-22: a set deployment is a variable of its own."""
    assert iri_template_variables(_settings("blue")).deployment == "blue"


def test_tc23_the_id_of_a_tenant_iri_is_the_id():
    """TC-23: ``tenant_id_of`` reads the id out of what the tenant template mints."""
    assert Iris(_settings()).tenant_id_of(f"https://ex.org/t/{UUID_A}") == UUID_A


def _letter_tenants() -> Iris:
    """An ``Iris`` whose tenant ids are five letters, so the id slot can spell a reserved word."""
    policy = IriPolicy(
        tenant_id=IdSpec(kind=IdKind.RANDOM, length=5, alphabet=string.ascii_lowercase)
    )
    settings = _settings().replaced(iri_policy=policy)
    return Iris(settings, root_types=frozenset({"books"}))


@pytest.mark.parametrize("word", ["books", "graph", "parts"])
def test_tc23_a_reserved_word_in_the_place_of_the_id_is_refused(word):
    """TC-23: a reserved word (a root type or a layout word) that fits the id spec is no tenant id."""
    with pytest.raises(InvalidIri):
        _letter_tenants().tenant_id_of(f"https://ex.org/t/{word}")


def test_tc23_a_word_of_the_same_shape_that_is_not_reserved_is_the_id():
    """TC-23: the refusal is the reserved word's, not the shape's."""
    assert _letter_tenants().tenant_id_of("https://ex.org/t/shelf") == "shelf"


def test_tc24_a_group_the_model_does_not_name_is_refused():
    """TC-24: ``IriParts`` has no room for a regex group it does not name."""
    assert IriParts.model_validate({"tenant_id": "x"}).tenant_id == "x"
    with pytest.raises(ValidationError):
        IriParts.model_validate({"tenant_id": "x", "unknown": "y"})

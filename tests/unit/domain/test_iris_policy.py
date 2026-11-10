"""``Iris``: IRIs minted and matched by the templates of the IRI policy (PD-3 to PD-6, PD-10, PD-11)."""

import re
from collections.abc import Callable, Iterator

import pytest
from rdflib import URIRef

from rdf_persistence.domain.exceptions import InvalidIri, NotFound
from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.domain.iris import Iris

BASE = "http://mwb.meaningfy.ws/"
TENANT = f"{BASE}project/p4x8k2m"
ROOT_TYPES = frozenset({"ontology-file"})
OWNED_TYPES = frozenset({"term"})
UUID_RE = "[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
FLAT = "{base}{tenant_id}/{type}/{id}"


def _settings(policy: IriPolicy | None = None, **more: str) -> ServiceSettings:
    return ServiceSettings(
        base=BASE,
        prefix="mwb",
        tenant_segment="projects",
        creator_role="owner",
        roles_claim="roles",
        iri_policy=policy,
        **more,
    )


def _consumer_policy(**more: object) -> IriPolicy:
    return IriPolicy(
        tenant_template="{base}project/{tenant_id}",
        aggregate_template=FLAT,
        part_template=FLAT,
        loaded_graph_template=FLAT,
        tenant_id=IdSpec(kind=IdKind.RANDOM, length=7),
        object_id=IdSpec(kind=IdKind.RANDOM, length=13),
        **more,
    )


def _scripted(*ids: str) -> Callable[[IdSpec | None], str]:
    drawn: Iterator[str] = iter(ids)
    return lambda spec: next(drawn)


@pytest.fixture
def default() -> Iris:
    return Iris(_settings())


@pytest.fixture
def consumer() -> Iris:
    return Iris(_settings(_consumer_policy(), deployment="k3f9a2x"), ROOT_TYPES, OWNED_TYPES)


# --- without a policy: today's shapes -----------------------------------------------------------

DEFAULT_TENANT = f"{BASE}projects/12345678-1234-4234-8234-123456789abc"


def test_a_default_policy_mints_todays_shapes(default):
    tenant = default.mint_tenant()
    assert re.fullmatch(f"{re.escape(BASE)}projects/{UUID_RE}", tenant), tenant
    root = default.mint_aggregate(tenant, "", "files")
    assert re.fullmatch(f"{re.escape(tenant)}/files/{UUID_RE}", root), root
    assert re.fullmatch(f"{re.escape(root)}/parts/{UUID_RE}", default.mint_part(tenant, root, ""))
    assert re.fullmatch(
        f"{re.escape(root)}/content/{UUID_RE}", default.mint_loaded_graph(tenant, root)
    )


def test_a_default_policy_names_the_tenant_graphs_and_resource_as_today(default):
    assert default.access(DEFAULT_TENANT) == URIRef(f"{DEFAULT_TENANT}/access")
    assert default.meta(DEFAULT_TENANT) == URIRef(f"{DEFAULT_TENANT}/meta")
    assert default.registry(DEFAULT_TENANT) == URIRef(f"{DEFAULT_TENANT}/registry")
    assert default.resource_name(DEFAULT_TENANT) == "mwb-t-12345678123442348234123456789abc"


def test_a_default_policy_accepts_the_tenant_its_access_record_and_minted_roots(default):
    root = default.mint_aggregate(DEFAULT_TENANT, "", "files")
    assert default.is_aggregate(DEFAULT_TENANT, DEFAULT_TENANT), "the tenant root"
    assert default.is_aggregate(DEFAULT_TENANT, f"{DEFAULT_TENANT}/access"), "its access record"
    assert default.is_aggregate(DEFAULT_TENANT, root), "a minted root"
    assert not default.is_aggregate(DEFAULT_TENANT, f"{DEFAULT_TENANT}/files/1"), "not a uuid"


def test_a_principal_is_the_issuer_and_the_subject_in_one_segment(default):
    assert default.principal("https://id.example.org/", "a/b c") == URIRef(
        "https://id.example.org/users/a%2Fb%20c"
    )


# --- the consumer's policy (proposal table) -----------------------------------------------------


def test_the_consumers_tenant_is_the_project_path_and_a_short_id(consumer):
    assert re.fullmatch(f"{re.escape(BASE)}project/[a-z0-9]{{7}}", consumer.mint_tenant())
    assert consumer.tenant("p4x8k2m") == URIRef(TENANT)
    assert consumer.tenant_id_of(TENANT) == "p4x8k2m"


def test_a_flat_object_is_not_nested_under_another(consumer):
    ids = _scripted("a8f3k29dm4x1q", "b8f3k29dm4x1q", "c8f3k29dm4x1q")
    iris = Iris(consumer.settings, ROOT_TYPES, OWNED_TYPES, ids)
    root = iris.mint_aggregate(TENANT, "ontology-file", "files")
    part = iris.mint_part(TENANT, root, "term")
    loaded = iris.mint_loaded_graph(TENANT, root)
    assert root == URIRef(f"{BASE}p4x8k2m/ontology-file/a8f3k29dm4x1q")
    assert part == URIRef(f"{BASE}p4x8k2m/term/b8f3k29dm4x1q")
    assert loaded == URIRef(f"{BASE}p4x8k2m/content/c8f3k29dm4x1q")


def test_parts_are_nested_under_their_root_only_when_the_part_template_starts_with_it(
    default, consumer
):
    assert default.nested_parts, "today's parts are {root}/parts/{id}"
    assert not consumer.nested_parts, "the consumer's parts are beside their root"


def test_the_api_path_does_not_enter_the_iri(consumer):
    first = consumer.mint_aggregate(TENANT, "ontology-file", "files")
    second = consumer.mint_aggregate(TENANT, "ontology-file", "ontology-files")
    assert first.split("/")[-2] == second.split("/")[-2] == "ontology-file"


def test_ids_have_the_configured_length_and_alphabet(consumer):
    last = consumer.mint_aggregate(TENANT, "ontology-file", "files").rsplit("/", 1)[1]
    assert re.fullmatch("[a-z0-9]{13}", last), last


def test_a_reserved_id_is_drawn_again():
    iris = Iris(
        _settings(_consumer_policy(), deployment="k3f9a2x"),
        id_source=_scripted("project", "p4x8k2m"),
    )
    assert iris.mint_tenant() == URIRef(TENANT), "the literal word 'project' is never an id"


@pytest.mark.parametrize("reserved", ["content", "ontology-file", "term", "k3f9a2x", "parts"])
def test_a_type_the_deployment_or_a_layout_word_is_never_an_id(reserved):
    iris = Iris(
        _settings(_consumer_policy(), deployment="k3f9a2x"),
        ROOT_TYPES,
        OWNED_TYPES,
        _scripted(reserved, "a8f3k29dm4x1q"),
    )
    assert iris.mint_aggregate(TENANT, "ontology-file", "files").endswith("/a8f3k29dm4x1q")


# --- only what the policy would mint is accepted ------------------------------------------------


@pytest.mark.parametrize(
    ("iri", "accepted"),
    [
        (f"{BASE}p4x8k2m/ontology-file/a8f3k29dm4x1q", True),
        (TENANT, True),  # the tenant root
        (f"{TENANT}/access", True),  # the access record, here the default template
        (f"{BASE}p4x8k2m/files/1", False),  # a hand-made IRI
        (f"{BASE}p4x8k2m/term/a8f3k29dm4x1q", False),  # a part's type
        (f"{BASE}p4x8k2m/content/a8f3k29dm4x1q", False),  # a loaded graph's type
        (f"{BASE}p4x8k2m/unknown/a8f3k29dm4x1q", False),
        (f"{BASE}other00/ontology-file/a8f3k29dm4x1q", False),  # another tenant
        (f"{BASE}p4x8k2m/ontology-file/A8F3K29DM4X1Q", False),
        (f"{BASE}p4x8k2m/ontology-file/a8f3k29dm4x1", False),  # too short
        (f"{BASE}p4x8k2m/ontology-file/a8f3k29dm4x1q/graph", False),
    ],
)
def test_an_aggregate_is_only_what_the_policy_mints(consumer, iri, accepted):
    assert consumer.is_aggregate(TENANT, iri) is accepted, iri


@pytest.mark.parametrize(
    ("iri", "accepted"),
    [
        (f"{BASE}p4x8k2m/content/z0q7c1m2n8b4v", True),
        (f"{BASE}p4x8k2m/ontology-file/z0q7c1m2n8b4v", False),
        (f"{BASE}other00/content/z0q7c1m2n8b4v", False),
    ],
)
def test_a_loaded_graph_is_only_what_the_policy_mints(consumer, iri, accepted):
    assert consumer.is_loaded_graph(TENANT, iri) is accepted, iri


def test_a_nested_loaded_graph_belongs_to_the_named_root(default):
    root = default.mint_aggregate(DEFAULT_TENANT, "", "files")
    graph = default.mint_loaded_graph(DEFAULT_TENANT, root)
    assert default.is_loaded_graph(DEFAULT_TENANT, graph)
    assert default.is_loaded_graph(DEFAULT_TENANT, graph, root)
    assert not default.is_loaded_graph(
        DEFAULT_TENANT, graph, default.mint_aggregate(DEFAULT_TENANT, "", "files")
    ), "another aggregate's graph"


@pytest.mark.parametrize(
    ("suffix", "accepted"),
    [
        ("ontology-file/a8f3k29dm4x1q/graph", True),
        ("ontology-file/a8f3k29dm4x1q", False),  # the root, not its graph
        ("term/a8f3k29dm4x1q/graph", False),
    ],
)
def test_an_aggregate_graph_is_the_graph_of_a_tenants_aggregate(consumer, suffix, accepted):
    assert consumer.is_aggregate_graph(TENANT, f"{BASE}p4x8k2m/{suffix}") is accepted


def test_the_tenant_root_has_no_aggregate_graph_of_its_own(consumer):
    assert not consumer.is_aggregate_graph(TENANT, f"{TENANT}/graph")


# --- path ids and malformed IRIs ----------------------------------------------------------------


@pytest.mark.parametrize("tenant_id", ["P4X8K2M", "p4x8k2", "p4x8k2m0", "p4x8k2/", ""])
def test_a_tenant_path_id_of_the_wrong_form_is_not_found(consumer, tenant_id):
    with pytest.raises(NotFound):
        consumer.tenant(tenant_id)


def test_an_aggregate_path_id_of_the_wrong_form_is_not_found(consumer):
    with pytest.raises(NotFound):
        consumer.aggregate(TENANT, "ontology-file", "files", "a8f3k29dm4x1q0")


def test_an_aggregate_path_id_of_the_right_form_gives_its_iri(consumer):
    assert consumer.aggregate(TENANT, "ontology-file", "files", "a8f3k29dm4x1q") == URIRef(
        f"{BASE}p4x8k2m/ontology-file/a8f3k29dm4x1q"
    )


@pytest.mark.parametrize("iri", [f"{BASE}project/P4X8K2M", f"{BASE}projects/p4x8k2m", "nope", ""])
def test_a_tenant_iri_the_policy_cannot_mint_is_invalid(consumer, iri):
    with pytest.raises(InvalidIri, match="tenant IRI"):
        consumer.tenant_id_of(iri)


def test_a_type_the_schema_does_not_know_cannot_be_minted(consumer):
    with pytest.raises(InvalidIri, match="type"):
        consumer.mint_aggregate(TENANT, "term", "files")  # a part's type
    with pytest.raises(InvalidIri, match="type"):
        consumer.mint_part(TENANT, f"{BASE}p4x8k2m/ontology-file/a8f3k29dm4x1q", "ontology-file")


def test_an_rp_path_that_is_not_a_segment_is_invalid(consumer):
    with pytest.raises(InvalidIri, match="segment"):
        consumer.mint_aggregate(TENANT, "ontology-file", "a/b")


# --- access record, resource names, settings checks ---------------------------------------------


def test_the_tenant_of_an_access_record_comes_back_through_the_templates():
    policy = _consumer_policy(access_template="{base}{deployment}/project/{tenant_id}")
    iris = Iris(_settings(policy, deployment="k3f9a2x"))
    access = iris.access(TENANT)
    assert access == URIRef(f"{BASE}k3f9a2x/project/p4x8k2m")
    assert iris.tenant_of_access(access) == URIRef(TENANT)


def test_the_tenant_of_a_default_access_record_is_the_iri_above_it(default):
    assert default.tenant_of_access(f"{DEFAULT_TENANT}/access") == URIRef(DEFAULT_TENANT)


@pytest.mark.parametrize(
    "iri", [f"{DEFAULT_TENANT}/books/1", "/access", "nope", f"{DEFAULT_TENANT}/content/access"]
)
def test_an_iri_that_is_not_an_access_record_has_no_tenant(default, iri):
    with pytest.raises(InvalidIri, match="access record"):
        default.tenant_of_access(iri)


def test_a_short_tenant_id_names_the_database_and_bucket(consumer):
    assert consumer.resource_name(TENANT) == "mwb-t-p4x8k2m"


def test_a_uuid_tenant_id_names_them_by_its_hex(default):
    assert default.resource_name(DEFAULT_TENANT) == "mwb-t-12345678123442348234123456789abc"


@pytest.mark.parametrize(
    ("policy", "settings_more", "named"),
    [
        (IriPolicy(tenant_template="{base}{deployment}/{tenant_id}"), {}, "tenant_template"),
        (
            IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM)),
            {},
            "object_id",
        ),
    ],
)
def test_settings_the_schema_cannot_refuse_alone_are_refused_when_iris_is_built(
    policy, settings_more, named
):
    with pytest.raises(InvalidIri, match=named):
        Iris(_settings(policy, **settings_more))


def test_a_uriref_and_a_str_of_one_iri_are_checked_alike(consumer):
    iri = f"{BASE}p4x8k2m/ontology-file/a8f3k29dm4x1q"
    assert consumer.is_aggregate(URIRef(TENANT), URIRef(iri)), "URIRef arguments"
    assert consumer.is_aggregate(TENANT, iri), "str arguments"
    assert consumer.is_aggregate(URIRef(TENANT), URIRef(TENANT)), "the tenant root as URIRefs"


def test_the_patterns_are_compiled_once_per_iris(consumer):
    assert consumer._aggregate_re is consumer._aggregate_re, "a cached pattern"


def test_an_iris_is_frozen(consumer):
    with pytest.raises(AttributeError, match="frozen"):
        consumer.root_types = frozenset()


# --- a loaded graph of the tenant root (tenant-root-loads) --------------------------------------


def test_a_template_without_a_root_variable_still_mints_a_loaded_graph_for_the_root(consumer):
    loaded = consumer.mint_loaded_graph(TENANT, TENANT)
    assert consumer.is_loaded_graph(TENANT, loaded), "still a loaded graph"

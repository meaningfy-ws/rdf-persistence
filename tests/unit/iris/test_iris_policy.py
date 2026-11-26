"""``Iris``: IRIs minted and matched by the templates of the IRI policy (PD-3 to PD-6, PD-10, PD-11)."""

import re
from collections.abc import Callable, Iterator

import pytest
from rdflib import URIRef

from rdf_persistence import UnitOfWork
from rdf_persistence.core.domain.exceptions import InvalidIri, NotFound
from rdf_persistence.iris.services.generated.rp_iris_services import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.provenance.services.provenance import is_activity_id
from rdf_persistence.testkit import fake_session
from rdf_persistence.testkit.fakes import FAKE_TENANT
from tests.toy import TENANT as TOY_TENANT
from tests.toy import book_iri, dune, toy_mapper

BASE = "https://example.org/"
TENANT = f"{BASE}library/p4x8k2m"
ROOT_TYPES = frozenset({"ontology-file"})
OWNED_TYPES = frozenset({"term"})
UUID_RE = "[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
FLAT = "{base}{tenant_id}/{type}/{id}"


def _settings(policy: IriPolicy | None = None, **more: str) -> ServiceSettings:
    return ServiceSettings(
        base=BASE,
        prefix="lib",
        tenant_segment="projects",
        creator_role="owner",
        roles_claim="roles",
        iri_policy=policy,
        **more,
    )


def _example_policy(**more: object) -> IriPolicy:
    return IriPolicy(
        tenant_template="{base}library/{tenant_id}",
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
    return Iris(_settings(_example_policy(), deployment="k3f9a2x"), ROOT_TYPES, OWNED_TYPES)


# --- without a policy: today's shapes -----------------------------------------------------------

DEFAULT_TENANT = f"{BASE}projects/12345678-1234-4234-8234-123456789abc"


def test_a_default_policy_mints_todays_shapes(default):
    tenant = default.mint_tenant()
    assert re.fullmatch(f"{re.escape(BASE)}projects/{UUID_RE}", tenant), tenant
    root = default.mint_aggregate(tenant, "", "files")
    assert re.fullmatch(f"{re.escape(tenant)}/files/{UUID_RE}", root), root
    assert re.fullmatch(
        f"{re.escape(root)}/parts/{UUID_RE}", default.mint_part(tenant, root, "")
    ), "the default part IRI is the root plus parts plus a uuid"
    assert re.fullmatch(
        f"{re.escape(root)}/content/{UUID_RE}", default.mint_loaded_graph(tenant, root)
    ), "the default loaded graph IRI is the root plus content plus a uuid"


def test_a_default_policy_names_the_tenant_graphs_and_resource_as_today(default):
    assert default.access(DEFAULT_TENANT) == URIRef(f"{DEFAULT_TENANT}/access"), (
        "the default access record hangs under the tenant"
    )
    assert default.meta(DEFAULT_TENANT) == URIRef(f"{DEFAULT_TENANT}/meta"), (
        "the default meta graph hangs under the tenant"
    )
    assert default.registry(DEFAULT_TENANT) == URIRef(f"{DEFAULT_TENANT}/registry"), (
        "the default registry graph hangs under the tenant"
    )
    assert default.resource_name(DEFAULT_TENANT) == "lib-t-12345678123442348234123456789abc", (
        "the default resource name is the deployment, tenant marker and hex id"
    )


def test_the_provenance_graph_is_minted_and_is_not_an_aggregate_or_a_loaded_graph(default):
    """message-bus PD-5, TC-05."""
    graph = default.provenance(DEFAULT_TENANT)
    assert graph == URIRef(f"{DEFAULT_TENANT}/provenance"), "the default template"
    assert not default.is_aggregate(DEFAULT_TENANT, str(graph)), "not an aggregate"
    assert not default.is_aggregate_graph(DEFAULT_TENANT, str(graph)), "not an aggregate graph"
    assert not default.is_loaded_graph(DEFAULT_TENANT, str(graph)), "not a loaded graph"


def test_a_provenance_template_equal_to_the_registry_template_is_refused():
    """TC-06."""
    with pytest.raises(InvalidIri, match="provenance"):
        Iris(_settings(IriPolicy(provenance_template="{tenant}/registry")))


def test_a_provenance_template_of_its_own_is_accepted():
    iris = Iris(_settings(IriPolicy(provenance_template="{tenant}/prov")))
    assert iris.provenance(DEFAULT_TENANT) == URIRef(f"{DEFAULT_TENANT}/prov"), (
        "the configured template"
    )


def test_a_default_policy_accepts_the_tenant_its_access_record_and_minted_roots(default):
    root = default.mint_aggregate(DEFAULT_TENANT, "", "files")
    assert default.is_aggregate(DEFAULT_TENANT, DEFAULT_TENANT), "the tenant root"
    assert default.is_aggregate(DEFAULT_TENANT, f"{DEFAULT_TENANT}/access"), "its access record"
    assert default.is_aggregate(DEFAULT_TENANT, root), "a minted root"
    assert not default.is_aggregate(DEFAULT_TENANT, f"{DEFAULT_TENANT}/files/1"), "not a uuid"


def test_a_principal_is_the_issuer_and_the_subject_in_one_segment(default):
    assert default.principal("https://id.example.org/", "a/b c") == URIRef(
        "https://id.example.org/users/a%2Fb%20c"
    ), "a principal is the issuer and an encoded subject in one segment"


# --- the example policy (proposal table) -----------------------------------------------------


def test_the_consumers_tenant_is_the_project_path_and_a_short_id(consumer):
    assert re.fullmatch(f"{re.escape(BASE)}library/[a-z0-9]{{7}}", consumer.mint_tenant()), (
        "the consumer's minted tenant is the project path and a short id"
    )
    assert consumer.tenant("p4x8k2m") == URIRef(TENANT), (
        "the consumer's tenant IRI is the project path and its id"
    )
    assert consumer.tenant_id_of(TENANT) == "p4x8k2m", (
        "the tenant id is read back from the tenant IRI"
    )


def test_a_flat_object_is_not_nested_under_another(consumer):
    ids = _scripted("a8f3k29dm4x1q", "b8f3k29dm4x1q", "c8f3k29dm4x1q")
    iris = Iris(consumer.settings, ROOT_TYPES, OWNED_TYPES, ids)
    root = iris.mint_aggregate(TENANT, "ontology-file", "files")
    part = iris.mint_part(TENANT, root, "term")
    loaded = iris.mint_loaded_graph(TENANT, root)
    assert root == URIRef(f"{BASE}p4x8k2m/ontology-file/a8f3k29dm4x1q"), (
        "a flat root is not nested under another object"
    )
    assert part == URIRef(f"{BASE}p4x8k2m/term/b8f3k29dm4x1q"), (
        "a flat part is not nested under another object"
    )
    assert loaded == URIRef(f"{BASE}p4x8k2m/content/c8f3k29dm4x1q"), (
        "a flat loaded graph is not nested under another object"
    )


def test_parts_are_nested_under_their_root_only_when_the_part_template_starts_with_it(
    default, consumer
):
    assert default.nested_parts, "today's parts are {root}/parts/{id}"
    assert not consumer.nested_parts, "the consumer's parts are beside their root"


def test_the_api_path_does_not_enter_the_iri(consumer):
    first = consumer.mint_aggregate(TENANT, "ontology-file", "files")
    second = consumer.mint_aggregate(TENANT, "ontology-file", "ontology-files")
    assert first.split("/")[-2] == second.split("/")[-2] == "ontology-file", (
        "the API path does not enter the aggregate IRI"
    )


def test_ids_have_the_configured_length_and_alphabet(consumer):
    last = consumer.mint_aggregate(TENANT, "ontology-file", "files").rsplit("/", 1)[1]
    assert re.fullmatch("[a-z0-9]{13}", last), last


def test_a_reserved_id_is_drawn_again():
    iris = Iris(
        _settings(_example_policy(), deployment="k3f9a2x"),
        id_source=_scripted("library", "p4x8k2m"),
    )
    assert iris.mint_tenant() == URIRef(TENANT), "the literal word 'library' is never an id"


@pytest.mark.parametrize("reserved", ["content", "ontology-file", "term", "k3f9a2x", "parts"])
def test_a_type_the_deployment_or_a_layout_word_is_never_an_id(reserved):
    iris = Iris(
        _settings(_example_policy(), deployment="k3f9a2x"),
        ROOT_TYPES,
        OWNED_TYPES,
        _scripted(reserved, "a8f3k29dm4x1q"),
    )
    assert iris.mint_aggregate(TENANT, "ontology-file", "files").endswith("/a8f3k29dm4x1q"), (
        "a type the deployment or a layout word names is never an id"
    )


def test_the_default_activity_template_reserves_no_word():
    iris = Iris(_settings(IriPolicy(tenant_id=IdSpec(kind=IdKind.RANDOM, length=4))))
    assert iris.tenant("uuid").endswith("/uuid"), "'uuid' is a tenant id under the default"
    assert not {"urn", "uuid"} & iris._reserved, "the default activity template reserves no word"


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
    assert default.is_loaded_graph(DEFAULT_TENANT, graph), (
        "a nested loaded graph belongs to its tenant"
    )
    assert default.is_loaded_graph(DEFAULT_TENANT, graph, root), (
        "a nested loaded graph belongs to the named root"
    )
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
    assert consumer.is_aggregate_graph(TENANT, f"{BASE}p4x8k2m/{suffix}") is accepted, (
        "an aggregate graph is accepted exactly when the suffix is a tenant aggregate's graph"
    )


def test_the_tenant_root_has_no_aggregate_graph_of_its_own(consumer):
    assert not consumer.is_aggregate_graph(TENANT, f"{TENANT}/graph"), (
        "the tenant root has no aggregate graph of its own"
    )


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
    ), "a path id of the right form gives the aggregate IRI"


@pytest.mark.parametrize("iri", [f"{BASE}library/P4X8K2M", f"{BASE}libraries/p4x8k2m", "nope", ""])
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
    policy = _example_policy(access_template="{base}{deployment}/library/{tenant_id}")
    iris = Iris(_settings(policy, deployment="k3f9a2x"))
    access = iris.access(TENANT)
    assert access == URIRef(f"{BASE}k3f9a2x/library/p4x8k2m"), (
        "the access record is built through the templates"
    )
    assert iris.tenant_of_access(access) == URIRef(TENANT), (
        "the tenant comes back from the access record through the templates"
    )


def test_the_tenant_of_a_default_access_record_is_the_iri_above_it(default):
    assert default.tenant_of_access(f"{DEFAULT_TENANT}/access") == URIRef(DEFAULT_TENANT), (
        "the tenant comes back from a default access record"
    )


@pytest.mark.parametrize(
    "iri", [f"{DEFAULT_TENANT}/books/1", "/access", "nope", f"{DEFAULT_TENANT}/content/access"]
)
def test_an_iri_that_is_not_an_access_record_has_no_tenant(default, iri):
    with pytest.raises(InvalidIri, match="access record"):
        default.tenant_of_access(iri)


def test_a_short_tenant_id_names_the_database_and_bucket(consumer):
    assert consumer.resource_name(TENANT) == "lib-t-p4x8k2m", (
        "a short tenant id names the database and bucket"
    )


def test_a_uuid_tenant_id_names_them_by_its_hex(default):
    assert default.resource_name(DEFAULT_TENANT) == "lib-t-12345678123442348234123456789abc", (
        "a uuid tenant id names them by its hex"
    )


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


def test_an_iris_is_frozen(consumer):
    with pytest.raises(AttributeError, match="frozen"):
        consumer.root_types = frozenset()


def test_changing_the_settings_after_building_changes_nothing_that_is_minted():
    """Fails if ``Iris`` keeps a shallow copy of the settings: the caller's nested policy would leak in."""
    mine = _settings(_example_policy(), deployment="k3f9a2x")
    iris = Iris(mine, ROOT_TYPES, OWNED_TYPES)
    mine.iri_policy.aggregate_template = "{tenant}/changed/{id}"
    assert iris.mint_aggregate(TENANT, "ontology-file", "files").startswith(
        f"{BASE}p4x8k2m/ontology-file/"
    ), "the policy the caller changed afterwards is not the one that mints"


# --- what the part template writes, and what a principal is ---------------------------------------


def test_a_default_part_template_needs_no_type():
    assert not Iris(_settings()).part_needs_type(), "the default part IRI has no type in it"


def test_a_part_template_that_writes_the_type_needs_one():
    policy = IriPolicy(part_template="{root}/parts/{type}/{id}")
    assert Iris(_settings(policy), ROOT_TYPES, OWNED_TYPES).part_needs_type(), (
        "a part template with {type} needs the class's type"
    )


def test_a_principal_is_written_by_the_template_with_the_base():
    iris = Iris(_settings(IriPolicy(principal_template="{base}people/{sub}")))
    assert iris.principal("https://id.example.org", "a b") == URIRef(f"{BASE}people/a%20b"), (
        "the settings' base is written into the principal template"
    )


def test_the_slashes_at_the_end_of_an_issuer_are_dropped_and_no_other_character():
    principal = Iris(_settings()).principal("https://id.example.org/tenantX//", "s")
    assert principal == URIRef("https://id.example.org/tenantX/users/s"), (
        "only the trailing slashes of the issuer go"
    )


def test_a_variable_written_twice_in_a_template_must_read_the_same_twice():
    """Fails if a repeated variable is not a backreference (the second one would match any id)."""
    iris = Iris(
        _settings(_example_policy(access_template="{base}acc/{tenant_id}/{tenant_id}")),
    )
    assert iris.tenant_of_access(f"{BASE}acc/p4x8k2m/p4x8k2m") == URIRef(TENANT), (
        "the same id twice is the access record of that tenant"
    )
    with pytest.raises(InvalidIri):
        iris.tenant_of_access(f"{BASE}acc/p4x8k2m/q4x8k2m")


def test_what_is_minted_for_a_tenant_is_its_aggregate_whatever_the_tenant_spells(default):
    """Fails if ``.`` in a pattern stops at a line break."""
    tenant = f"{DEFAULT_TENANT}\nx"
    root = default.mint_aggregate(tenant, "", "files")
    assert default.is_aggregate(tenant, root), "an aggregate minted for a tenant is its own"


# --- what no policy lets through --------------------------------------------------------------------


def test_with_no_root_types_nothing_is_an_aggregate():
    """Fails if an empty set of types matches the empty type (a ``(?:)`` alternation)."""
    iris = Iris(_settings(_example_policy(), deployment="k3f9a2x"))
    assert not iris.is_aggregate(TENANT, f"{BASE}p4x8k2m//a8f3k29dm4x1q"), (
        "an aggregate IRI with no type is not one when the schema has no root types"
    )


def test_a_tenant_id_of_the_wrong_form_names_itself_in_the_refusal():
    with pytest.raises(NotFound) as refused:
        Iris(_settings()).tenant("not an id")
    assert "not an id" in str(refused.value), "the refusal names the id it refuses"


def test_an_aggregate_id_of_the_wrong_form_names_itself_in_the_refusal(consumer):
    with pytest.raises(NotFound) as refused:
        consumer.aggregate(TENANT, "ontology-file", "files", "not an id")
    assert "not an id" in str(refused.value), "the refusal names the id it refuses"


def test_no_id_that_is_not_reserved_is_refused_after_many_draws():
    iris = Iris(_settings(_example_policy()), id_source=lambda spec: "library")
    with pytest.raises(InvalidIri) as refused:
        iris.mint_tenant()
    assert "reserved" in str(refused.value), "the refusal says why no id came"


def test_an_access_record_of_a_reserved_tenant_id_names_itself_in_the_refusal():
    iris = Iris(
        _settings(_example_policy(access_template="{base}acc/{tenant_id}"), deployment="k3f9a2x")
    )
    iri = f"{BASE}acc/k3f9a2x"
    with pytest.raises(InvalidIri) as refused:
        iris.tenant_of_access(iri)
    assert iri in str(refused.value), "the refusal names the IRI it refuses"


# --- a loaded graph of the tenant root (tenant-root-loads) --------------------------------------


def test_a_template_without_a_root_variable_still_mints_a_loaded_graph_for_the_root(consumer):
    loaded = consumer.mint_loaded_graph(TENANT, TENANT)
    assert consumer.is_loaded_graph(TENANT, loaded), "still a loaded graph"


# --- the activity template (activity-iri-policy PD-2, PD-3) -------------------------------------

UUID = "7a1e1d6e-2f0b-4c57-9a52-2f2f5d1f6a10"
OTHER_TENANT = f"{BASE}projects/87654321-4321-4321-8321-cba987654321"
PLACED = "{tenant}/activity/{id}"


def _placing(template: str = PLACED, **policy: object) -> Iris:
    return Iris(
        _settings(IriPolicy(activity_template=template, **policy)), frozenset({"book"}), OWNED_TYPES
    )


def test_an_activity_iri_follows_the_activity_template():
    iris, placed = _placing(), f"{DEFAULT_TENANT}/activity/{UUID}"
    assert iris.activity(DEFAULT_TENANT, UUID) == URIRef(placed), "the template's IRI"
    assert iris.is_activity(DEFAULT_TENANT, placed), "the placed IRI is the tenant's activity"
    assert not iris.is_activity(OTHER_TENANT, placed), "not another tenant's"
    assert iris.is_activity(None, placed), "no tenant given: any tenant's"
    assert not iris.is_activity(DEFAULT_TENANT, f"urn:uuid:{UUID}"), (
        "the provisional id is not placed"
    )
    assert not iris.is_activity(DEFAULT_TENANT, f"{DEFAULT_TENANT}/activity/{UUID.upper()}"), (
        "a non-canonical UUID is no activity"
    )
    assert iris.activity_uuid(placed) == UUID, "the UUID of the placed form"
    assert iris.activity_uuid(f"urn:uuid:{UUID}") == UUID, "the UUID of the provisional form"
    assert iris.activity_uuid(f"{OTHER_TENANT}/activity/{UUID}") == UUID, (
        "a {tenant} template reads any tenant: callers check is_activity(tenant, iri) first"
    )


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(f"urn:uuid:{UUID}", id="provisional"),
        pytest.param(f"urn:uuid:{UUID.upper()}", id="upper-case"),
        pytest.param(f"urn:uuid:{UUID.replace('-', '')}", id="no-hyphens"),
        pytest.param(f"{DEFAULT_TENANT}/activity/{UUID}", id="placed-shape"),
        pytest.param(f"{DEFAULT_TENANT}/books/{UUID}", id="an-aggregate"),
        pytest.param("", id="empty"),
    ],
)
def test_under_the_default_policy_an_activity_is_what_is_activity_id_accepts(default, text):
    assert default.is_activity(DEFAULT_TENANT, text) == is_activity_id(text), (
        "the default accepts what is_activity_id accepts"
    )


def test_under_the_default_policy_an_activity_is_the_urn_uuid(default):
    assert default.activity(DEFAULT_TENANT, UUID) == URIRef(f"urn:uuid:{UUID}"), "as today"
    assert default.activity_uuid(f"urn:uuid:{UUID}") == UUID, "its UUID"


@pytest.mark.parametrize(
    "text", [f"urn:uuid:{UUID.upper()}", f"{DEFAULT_TENANT}/activity/{UUID}", "x"]
)
def test_an_id_that_is_no_activity_iri_has_no_uuid(text, default):
    with pytest.raises(ValueError, match="activity"):
        default.activity_uuid(text)


def test_an_activity_is_minted_from_a_canonical_uuid_only(default):
    with pytest.raises(ValueError, match="UUID"):
        default.activity(DEFAULT_TENANT, UUID.upper())


def test_the_application_has_activities_under_a_tenant_id_template():
    iris = _placing("{base}{tenant_id}/activity/{id}")
    app = str(iris.application)
    assert iris.activity(app, UUID) == URIRef(f"{BASE}app/activity/{UUID}"), "app stands for the id"
    assert iris.is_activity(app, f"{BASE}app/activity/{UUID}"), "read back as the application's"


def test_a_tenant_the_policy_cannot_parse_mints_an_activity_without_tenant_id():
    default, placed = _placing("urn:uuid:{id}"), _placing()
    assert default.activity(FAKE_TENANT, UUID) == URIRef(f"urn:uuid:{UUID}"), "as today"
    assert placed.activity(FAKE_TENANT, UUID) == URIRef(f"{FAKE_TENANT}/activity/{UUID}"), (
        "a {tenant} template never parses the tenant"
    )
    with pytest.raises(InvalidIri, match="tenant"):
        _placing("{base}{tenant_id}/activity/{id}").activity(FAKE_TENANT, UUID)


async def test_a_commit_through_the_fake_session_under_the_default_policy_records_urn_uuid():
    seen: list[str] = []

    async def on_commit(activity, session) -> None:
        seen.append(str(activity.id))

    async with fake_session(tenant_iri=TOY_TENANT, on_commit=on_commit) as session:
        work = UnitOfWork(session, toy_mapper())
        work.add(dune(book_iri(1)))
        await work.commit()
    assert len(seen) == 1, f"one activity: {seen}"
    assert is_activity_id(seen[0]), f"a urn:uuid: activity, as today: {seen}"


def test_an_activity_iri_is_no_aggregate_or_loaded_graph():
    iris, default = _placing(), Iris(_settings(), frozenset({"book"}), OWNED_TYPES)
    activity, aggregate = f"{DEFAULT_TENANT}/activity/{UUID}", f"{DEFAULT_TENANT}/books/{UUID}"
    assert not iris.is_aggregate(DEFAULT_TENANT, activity), "an activity is no aggregate"
    assert iris.is_aggregate(DEFAULT_TENANT, aggregate), "an aggregate still is"
    assert not iris.is_aggregate_graph(DEFAULT_TENANT, f"{activity}/graph"), "nor has a graph"
    assert iris.is_aggregate_graph(DEFAULT_TENANT, f"{aggregate}/graph"), "an aggregate's graph is"
    assert iris.aggregate_id_of(activity) is None, "no aggregate address"
    assert iris.aggregate_id_of(aggregate) == UUID, "an aggregate's id"
    assert default.is_aggregate(DEFAULT_TENANT, activity), "under the default, as today"
    assert default.is_aggregate_graph(DEFAULT_TENANT, f"{activity}/graph"), "as today"
    assert default.aggregate_id_of(activity) == UUID, "as today"


def test_an_activity_iri_is_no_loaded_graph():
    loaded = f"{DEFAULT_TENANT}/content/{UUID}"
    policy = {"loaded_graph_template": "{tenant}/{type}/{id}"}
    placed = _placing("{tenant}/content/{id}", **policy)
    plain = Iris(_settings(IriPolicy(**policy)), frozenset({"book"}), OWNED_TYPES)
    assert plain.is_loaded_graph(DEFAULT_TENANT, loaded), "a loaded graph under the default"
    assert not placed.is_loaded_graph(DEFAULT_TENANT, loaded), "an activity there is none"


@pytest.mark.parametrize(
    ("roots", "policy", "refused"),
    [
        pytest.param([("book", "activity")], {}, True, id="inside-the-activity-segment"),
        pytest.param([("book", "books")], {}, False, id="another-segment"),
        pytest.param(
            [("book", "activity")],
            {"object_id": IdSpec(kind=IdKind.RANDOM, length=13)},
            False,
            id="random-ids-never-read-as-a-uuid",
        ),
    ],
)
def test_a_root_minted_inside_the_activity_template_is_refused(roots, policy, refused):
    iris = _placing(**policy)
    if refused:
        with pytest.raises(InvalidIri, match="book") as caught:
            iris.require_roots_apart(roots)
        assert "activity_template" in str(caught.value), "names the slot"
    else:
        iris.require_roots_apart(roots)


def test_the_default_activity_template_checks_no_root():
    Iris(_settings()).require_roots_apart([("book", "activity")])

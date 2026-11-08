"""Adversarial tests of iri-policy stage 2: the start-up guard (PD-9, PD-13), custom access, meta and
registry templates, and the principal template. A test that exposes a real defect is a strict xfail."""

from urllib.parse import unquote

import pytest
from rdflib import Graph, Literal, URIRef

from rdf_persistence.adapters.jwks import JwksTokenVerifier
from rdf_persistence.domain.exceptions import (
    DatabaseGone,
    InvalidIri,
    IriPolicyChanged,
    PersistenceError,
)
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.service.rp_service import IdKind, IdSpec, IriPolicy
from rdf_persistence.domain.iris import DEFAULT_ALPHABET, POLICY_SEGMENT, Iris
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.iri_policy_guard import guard_iri_policy
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, SETTINGS, library_slots, toy_mapper

SYSTEM = "lib-system"
RECORD_GRAPH = URIRef(f"{SETTINGS.base}{POLICY_SEGMENT}")
THIRTEEN = IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM, length=13))


def settings_of(policy: IriPolicy | None, **more):
    return SETTINGS.model_copy(update={"iri_policy": policy, **more})


def new_tenancy(store: FakeStore) -> Tenancy:
    return Tenancy(
        store,
        FakeFileStore(),
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
    )


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
async def tenancy(store) -> Tenancy:
    made = new_tenancy(store)
    await made.ensure_system_database()
    return made


async def plant(store: FakeStore, *texts: str, subject: URIRef = RECORD_GRAPH) -> None:
    """Write raw statements into the policy graph, as a foreign or older writer would."""
    record = Graph()
    for text in texts:
        record.add((subject, v.IRI_POLICY, Literal(text)))
    await store.put_graph(SYSTEM, RECORD_GRAPH, record)


# --- (1) the guard: what is stored is not what the guard wrote ------------------------------------


@pytest.mark.parametrize("text", ["not json", '{"bogus": 1}', "[]", ""])
async def test_a_corrupt_or_foreign_record_is_refused_with_a_toolkit_error(store, tenancy, text):
    await plant(store, text)
    with pytest.raises(PersistenceError):
        await guard_iri_policy(store, tenancy, settings_of(None))


async def test_a_corrupt_record_never_starts_the_service(store, tenancy):
    await plant(store, "not json")
    with pytest.raises(Exception):  # noqa: B017 - any refusal; the class is the xfail above
        await guard_iri_policy(store, tenancy, settings_of(None))
    assert len(store.sent("put_graph")) == 1, "the planted record is not overwritten"


async def test_a_statement_about_another_subject_is_no_record_and_is_replaced(store, tenancy):
    await plant(store, THIRTEEN.model_dump_json(), subject=URIRef("urn:other"))
    await guard_iri_policy(store, tenancy, settings_of(None))
    assert len(store.sent("update")) == 1, "the default policy is recorded beside it"


async def test_two_records_that_disagree_refuse_whichever_policy_is_configured(store, tenancy):
    default = settings_of(None)
    other = settings_of(THIRTEEN)
    await guard_iri_policy(store, tenancy, default)  # records the effective default
    stored = store._dataset(SYSTEM).graph(RECORD_GRAPH)
    stored.add((RECORD_GRAPH, v.IRI_POLICY, Literal(THIRTEEN.model_dump_json())))
    for configured in (default, other):
        with pytest.raises(IriPolicyChanged):
            await guard_iri_policy(store, tenancy, configured)


async def test_an_older_record_without_id_specs_is_the_default_policy(store, tenancy):
    await plant(store, "{}")
    await guard_iri_policy(store, tenancy, settings_of(None))


async def test_an_older_record_is_still_refused_for_a_policy_that_really_differs(store, tenancy):
    await plant(store, "{}")
    with pytest.raises(IriPolicyChanged, match="object_id"):
        await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))


@pytest.mark.parametrize("slot", ["tenant_template", "access_template", "principal_template"])
async def test_a_template_set_to_none_is_the_default_template(store, tenancy, slot):
    await guard_iri_policy(store, tenancy, settings_of(None))
    await guard_iri_policy(store, tenancy, settings_of(IriPolicy(**{slot: None})))


async def test_an_unset_alphabet_is_the_default_alphabet(store, tenancy):
    unset = IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM, length=13, alphabet=None))
    spelled = IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM, length=13, alphabet=DEFAULT_ALPHABET))
    await guard_iri_policy(store, tenancy, settings_of(unset))
    await guard_iri_policy(store, tenancy, settings_of(spelled))


async def test_the_same_alphabet_in_another_order_is_a_changed_alphabet(store, tenancy):
    first = IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM, length=8, alphabet="abc123"))
    second = IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM, length=8, alphabet="321cba"))
    await guard_iri_policy(store, tenancy, settings_of(first))
    with pytest.raises(IriPolicyChanged, match=r"object_id\.alphabet"):
        await guard_iri_policy(store, tenancy, settings_of(second))


async def test_a_changed_deployment_slug_under_a_deployment_template_is_refused(store, tenancy):
    policy = IriPolicy(tenant_template="{base}{deployment}/{tenant_id}")
    await guard_iri_policy(store, tenancy, settings_of(policy, deployment="dep1"))
    with pytest.raises(IriPolicyChanged):
        await guard_iri_policy(store, tenancy, settings_of(policy, deployment="dep2"))


async def test_a_deployment_slug_the_policy_does_not_use_may_change(store, tenancy):
    await guard_iri_policy(store, tenancy, settings_of(None, deployment="dep1"))
    await guard_iri_policy(store, tenancy, settings_of(None, deployment="dep2"))


async def test_an_empty_system_database_with_no_dataset_fails_loudly_and_records_nothing(store):
    with pytest.raises(DatabaseGone):
        await guard_iri_policy(store, new_tenancy(store), settings_of(None))
    assert store.sent("update") == []


async def test_an_empty_system_database_records_the_policy_once(store, tenancy):
    await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))
    await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))
    assert len(store.sent("update")) == 1, "a restart does not rewrite the record"


async def test_a_refused_start_leaves_the_recorded_policy_in_place(store, tenancy):
    await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))
    with pytest.raises(IriPolicyChanged):
        await guard_iri_policy(store, tenancy, settings_of(None))
    await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))


async def test_a_refused_start_over_data_names_every_field_and_records_nothing(store, tenancy):
    await tenancy.create("Ghent", library_slots(), Principal(id=ADA))
    changed = IriPolicy(
        meta_template="{tenant}/m",
        principal_template="{issuer}/p/{sub}",
        tenant_id=IdSpec(kind=IdKind.RANDOM, length=8),
    )
    with pytest.raises(IriPolicyChanged) as caught:
        await guard_iri_policy(store, tenancy, settings_of(changed))
    for field in ("meta_template", "principal_template", "tenant_id.kind", "tenant_id.length"):
        assert field in str(caught.value)
    assert not [t for t in store.sent("update") if POLICY_SEGMENT in t]


# --- (2) custom access, meta and registry templates -----------------------------------------------


def iris_of(**templates) -> Iris:
    return Iris(settings_of(IriPolicy(**templates), deployment="dep1"))


@pytest.mark.parametrize(
    "access",
    [
        "{base}{deployment}/access/{tenant_id}",
        "{tenant}/{deployment}/access",
        "{base}access-{tenant_id}",
        "{tenant}/a/b/c/access",
    ],
)
def test_a_custom_access_record_round_trips_to_its_tenant(access):
    iris = iris_of(access_template=access)
    tenant = iris.mint_tenant()
    assert iris.tenant_of_access(str(iris.access(tenant))) == tenant


@pytest.mark.parametrize("other", ["meta", "registry", "access/access", "", "x"])
def test_the_default_access_template_does_not_read_a_sibling_graph_as_a_record(other):
    iris = iris_of()
    tenant = iris.mint_tenant()
    with pytest.raises(InvalidIri):
        iris.tenant_of_access(f"{tenant}/{other}")


def test_an_access_record_of_a_template_under_deployment_is_not_found_under_another_slug():
    one = iris_of(access_template="{base}{deployment}/access/{tenant_id}")
    two = Iris(
        settings_of(
            IriPolicy(access_template="{base}{deployment}/access/{tenant_id}"), deployment="dep2"
        )
    )
    record = one.access(one.mint_tenant())
    with pytest.raises(InvalidIri):
        two.tenant_of_access(str(record))


def test_tenant_of_access_raises_only_invalid_iri_for_a_reserved_word_id():
    spec = IdSpec(kind=IdKind.RANDOM, length=6, alphabet="acesx")
    iris = Iris(settings_of(IriPolicy(tenant_id=spec, access_template="{base}a/{tenant_id}")))
    with pytest.raises(InvalidIri):
        iris.tenant_of_access(f"{SETTINGS.base}a/access")


@pytest.mark.parametrize(
    "templates",
    [
        {"access_template": "{tenant}/meta"},
        {"meta_template": "{tenant}/registry"},
        {"registry_template": "{tenant}/access"},
        {"access_template": "{tenant}"},
    ],
)
def test_two_kinds_of_iri_of_one_tenant_may_not_coincide(templates):
    with pytest.raises(InvalidIri):
        iris = iris_of(**templates)
        tenant = iris.mint_tenant()
        assert len({iris.access(tenant), iris.meta(tenant), iris.registry(tenant), tenant}) == 4
        raise InvalidIri("distinct")  # reached only if they are distinct, which they are not here


def test_distinct_default_templates_mint_distinct_iris():
    iris = iris_of()
    tenant = iris.mint_tenant()
    assert len({iris.access(tenant), iris.meta(tenant), iris.registry(tenant), tenant}) == 4


def test_a_meta_graph_is_not_an_aggregate_under_default_templates():
    iris = iris_of()
    tenant = iris.mint_tenant()
    assert not iris.is_aggregate(str(tenant), str(iris.meta(tenant)))
    assert not iris.is_aggregate(str(tenant), str(iris.registry(tenant)))


# --- (3) the principal template -------------------------------------------------------------------

ISSUER = "https://issuer.example"


@pytest.mark.parametrize(
    "sub",
    [
        "a/b",
        "a b",
        "%2F",
        "%",
        "é",
        "日本",
        "😀",
        "a?b#c",
        "a\nb",
        "a\x00b",
        "{sub}",
        "{issuer}",
        "a:b",
        "@",
        "a;b",
    ],
)
def test_an_odd_subject_stays_in_one_segment_and_decodes_back(sub):
    iri = str(Iris(SETTINGS).principal(ISSUER, sub))
    tail = iri.removeprefix(f"{ISSUER}/users/")
    assert "/" not in tail and "?" not in tail and "#" not in tail
    assert unquote(tail) == sub


@pytest.mark.parametrize("issuer", [ISSUER, ISSUER + "/", ISSUER + "//", ISSUER + "/realms/a/"])
def test_a_trailing_slash_on_the_issuer_never_doubles_the_separator(issuer):
    iri = str(Iris(SETTINGS).principal(issuer, "u1"))
    assert iri == f"{issuer.rstrip('/')}/users/u1"
    assert "//users" not in iri


def test_an_issuer_with_and_without_a_trailing_slash_name_one_principal():
    iris = Iris(SETTINGS)
    assert iris.principal(ISSUER, "u1") == iris.principal(ISSUER + "/", "u1")


def test_a_subject_and_its_encoding_stay_two_principals_even_with_a_custom_template():
    iris = Iris(settings_of(IriPolicy(principal_template="{base}people/{sub}")))
    assert iris.principal(ISSUER, "a/b") != iris.principal(ISSUER, "a%2Fb")
    assert str(iris.principal(ISSUER, "a/b")) == f"{SETTINGS.base}people/a%2Fb"


def test_a_template_without_the_issuer_gives_one_principal_for_two_issuers():
    iris = Iris(settings_of(IriPolicy(principal_template="{base}people/{sub}")))
    assert iris.principal("https://a.example", "u1") == iris.principal("https://b.example", "u1")


def test_an_issuer_with_braces_is_written_in_verbatim_not_formatted_again():
    iri = str(Iris(SETTINGS).principal("https://x.example/{sub}", "u1"))
    assert iri == "https://x.example/{sub}/users/u1"


@pytest.mark.parametrize("issuer", [ISSUER, ISSUER + "/"])
def test_the_verifier_mints_the_principal_by_the_policy_of_its_iris(issuer):
    iris = Iris(settings_of(IriPolicy(principal_template="{issuer}/u/{sub}")))
    verifier = JwksTokenVerifier(issuer, "aud", "roles", iris=iris)
    assert verifier._principal("a/b") == f"{ISSUER}/u/a%2Fb"

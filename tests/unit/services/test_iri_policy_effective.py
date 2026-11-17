"""``Iris.effective_policy`` and ``policy_differences``: what the start-up guard compares (PD-14b)."""

from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.services.iris import (
    DEFAULT_ALPHABET,
    Iris,
    policy_differences,
    policy_record_iri,
    stamps_graph_iri,
)

SETTINGS = ServiceSettings(
    base="https://example.org/library/",
    prefix="lib",
    tenant_segment="libraries",
    creator_role="librarian",
    roles_claim="urn:zitadel:iam:org:project:42:roles",
)


def effective(policy: IriPolicy | None, **more) -> IriPolicy:
    return Iris(SETTINGS.model_copy(update={"iri_policy": policy, **more})).effective_policy


def test_the_settings_are_written_into_the_templates():
    policy = effective(None)
    assert policy.tenant_template == f"{SETTINGS.base}{SETTINGS.tenant_segment}/{{tenant_id}}", (
        "the base and tenant segment are written into the tenant template"
    )


def test_a_deployment_in_a_template_is_written_in():
    policy = effective(
        IriPolicy(tenant_template="{base}{deployment}/{tenant_id}"), deployment="dep1"
    )
    assert policy.tenant_template == f"{SETTINGS.base}dep1/{{tenant_id}}", (
        "the deployment is written into the tenant template"
    )


def test_unset_and_empty_parts_get_their_defaults():
    unset = effective(None)
    assert unset == effective(IriPolicy(access_template=None)), (
        "unset parts get the same policy as defaults"
    )
    assert unset.tenant_id == IdSpec(kind=IdKind.UUID4), "an unset tenant id is a uuid4"
    assert unset.object_id == IdSpec(kind=IdKind.UUID4), "an unset object id is a uuid4"


def test_a_random_id_without_an_alphabet_has_the_default_one():
    spec = IdSpec(kind=IdKind.RANDOM, length=13, alphabet=None)
    assert effective(IriPolicy(object_id=spec)).object_id.alphabet == DEFAULT_ALPHABET, (
        "a random id without an alphabet gets the default alphabet"
    )


def test_differences_are_dotted_field_names():
    one = effective(IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM, length=8)))
    other = effective(
        IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM, length=9), meta_template="{tenant}/m")
    )
    assert policy_differences(one, other) == ["meta_template", "object_id.length"], (
        "differences are named by dotted field paths"
    )


# One base: every base is one equivalence class (the IRI is the base plus a fixed segment).
BASE = "https://a.example/"


def test_the_record_iri_is_under_the_toolkit_segment():
    assert str(policy_record_iri(BASE)) == f"{BASE}toolkit/iri-policy", (
        "the policy record sits under the toolkit segment"
    )


def test_the_stamps_graph_is_under_the_toolkit_segment():
    assert str(stamps_graph_iri(BASE)) == f"{BASE}toolkit/schema-stamps", (
        "the schema stamps graph sits under the toolkit segment"
    )

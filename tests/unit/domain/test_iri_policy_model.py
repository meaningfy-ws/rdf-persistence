"""``IdSpec``, ``IriPolicy`` and the ``ServiceSettings`` fields of the IRI policy (iri-policy task 1.1, PD-1, PD-2)."""

import re

import pytest
from pydantic import ValidationError

from rdf_persistence.domain.exceptions import InvalidIri
from rdf_persistence.domain.generated.service.rp_service import IdSpec, IriPolicy, ServiceSettings
from rdf_persistence.domain.iris import check_iri_policy

DEFAULTS = {
    "tenant_template": "{base}{tenant_segment}/{tenant_id}",
    "access_template": "{tenant}/access",
    "meta_template": "{tenant}/meta",
    "registry_template": "{tenant}/registry",
    "aggregate_template": "{tenant}/{rp_path}/{id}",
    "part_template": "{root}/parts/{id}",
    "loaded_graph_template": "{root}/content/{id}",
    "principal_template": "{issuer}/users/{sub}",
}
FLAT = "{base}{tenant_id}/{type}/{id}"
ID_13 = IdSpec(kind="random", length=13)


def mwb2_policy(**changes: object) -> IriPolicy:
    """The consumer's policy of the proposal's table."""
    fields = {
        "tenant_template": "{base}project/{tenant_id}",
        "access_template": "{base}{deployment}/project/{tenant_id}",
        "meta_template": "{base}{tenant_id}/meta",
        "registry_template": "{base}{tenant_id}/registry",
        "aggregate_template": FLAT,
        "part_template": FLAT,
        "loaded_graph_template": FLAT,
        "principal_template": "{base}{deployment}/user/{sub}",
        "tenant_id": IdSpec(kind="random", length=7),
        "object_id": ID_13,
    }
    return IriPolicy(**{**fields, **changes})


def settings(**changes: object) -> ServiceSettings:
    fields = {
        "base": "http://mwb.meaningfy.ws/",
        "prefix": "mwb",
        "tenant_segment": "projects",
        "creator_role": "owner",
        "roles_claim": "urn:zitadel:iam:org:project:42:roles",
    }
    return ServiceSettings(**{**fields, **changes})


@pytest.mark.parametrize(("slot", "template"), DEFAULTS.items())
def test_the_default_policy_has_todays_template(slot: str, template: str) -> None:
    assert getattr(IriPolicy(), slot) == template, f"default of {slot}"


@pytest.mark.parametrize("slot", ["tenant_id", "object_id"])
def test_an_absent_id_spec_is_the_default_uuid4(slot: str) -> None:
    assert getattr(IriPolicy(), slot) is None, f"{slot} is set by default; absent means uuid4"


def test_the_default_alphabet_is_lower_case_letters_and_digits() -> None:
    assert IdSpec(kind="uuid4").alphabet == "0123456789abcdefghijklmnopqrstuvwxyz"


def test_settings_without_a_policy_hold_none_and_no_deployment() -> None:
    made = settings()
    assert (made.iri_policy, made.deployment) == (None, None), "absent means default"


def test_the_consumers_policy_is_accepted() -> None:
    made = settings(iri_policy=mwb2_policy(), deployment="k3f9a2x")
    assert check_iri_policy(made) is None, "the policy of the proposal was refused"


@pytest.mark.parametrize("length", [3, 33, 0, -1])
def test_a_random_id_length_outside_4_to_32_is_refused(length: int) -> None:
    with pytest.raises(ValidationError, match="length"):
        IdSpec(kind="random", length=length)


@pytest.mark.parametrize("length", [4, 13, 32])
def test_a_random_id_length_from_4_to_32_is_accepted(length: int) -> None:
    assert IdSpec(kind="random", length=length).length == length


def test_a_random_id_without_a_length_is_refused() -> None:
    made = settings(iri_policy=IriPolicy(object_id=IdSpec(kind="random")))
    with pytest.raises(InvalidIri, match="object_id.*length"):
        check_iri_policy(made)


@pytest.mark.parametrize("alphabet", ["ABC", "ab-c", "ab c", "é", ""])
def test_an_alphabet_outside_lower_case_letters_and_digits_is_refused(alphabet: str) -> None:
    with pytest.raises(ValidationError, match="alphabet"):
        IdSpec(kind="random", length=7, alphabet=alphabet)


def test_an_unknown_id_kind_is_refused() -> None:
    with pytest.raises(ValidationError, match="kind"):
        IdSpec(kind="snowflake")


@pytest.mark.parametrize("deployment", ["k3f9a2x", "a", "a" * 32])
def test_a_lower_case_deployment_of_at_most_32_characters_is_accepted(deployment: str) -> None:
    assert settings(deployment=deployment).deployment == deployment


@pytest.mark.parametrize("deployment", ["", "K3F", "a-b", "a" * 33])
def test_any_other_deployment_is_refused(deployment: str) -> None:
    with pytest.raises(ValidationError, match="deployment"):
        settings(deployment=deployment)


def test_a_template_without_its_id_is_refused_naming_the_aggregate_template() -> None:
    with pytest.raises(ValidationError, match="aggregate_template"):
        mwb2_policy(aggregate_template="{base}{tenant_id}/{type}")


@pytest.mark.parametrize(
    "slot",
    [
        "tenant_template",
        "aggregate_template",
        "part_template",
        "loaded_graph_template",
        "principal_template",
    ],
)
def test_an_id_template_that_does_not_end_in_its_id_is_refused(slot: str) -> None:
    with pytest.raises(ValidationError, match=slot):
        IriPolicy(**{slot: "{base}{tenant_id}/x/"})


@pytest.mark.parametrize(
    ("slot", "template"),
    [
        ("tenant_template", "{base}t/{tenant_id}"),
        ("aggregate_template", "{base}{tenant_id}/{type}/{id}"),
        ("part_template", "{root}/{type}/{id}"),
        ("loaded_graph_template", "{root}/content/{id}"),
        ("principal_template", "{issuer}/user/{sub}"),
        ("access_template", "{base}{deployment}/{tenant_id}"),
        ("meta_template", "{tenant}/meta"),
        ("registry_template", "{base}{tenant_id}/registry"),
    ],
)
def test_a_template_with_allowed_variables_is_accepted(slot: str, template: str) -> None:
    assert getattr(IriPolicy(**{slot: template}), slot) == template


@pytest.mark.parametrize("slot", ["access_template", "meta_template", "registry_template"])
def test_a_tenant_graph_template_without_the_tenant_is_refused(slot: str) -> None:
    with pytest.raises(ValidationError, match=slot):
        IriPolicy(**{slot: "{base}access"})


@pytest.mark.parametrize(
    ("slot", "template"),
    [
        ("tenant_template", "{base}{type}/{tenant_id}"),
        ("tenant_template", "{base}{tenant}/{tenant_id}"),
        ("access_template", "{tenant}/{id}"),
        ("meta_template", "{root}/{tenant_id}"),
        ("aggregate_template", "{issuer}/{id}"),
        ("aggregate_template", "{base}{unknown}/{id}"),
        ("part_template", "{tenant}/{rp_path}/{id}"),
        ("loaded_graph_template", "{tenant}/{sub}/{id}"),
        ("principal_template", "{base}{tenant_id}/{sub}"),
    ],
)
def test_a_variable_not_allowed_for_its_kind_is_refused(slot: str, template: str) -> None:
    with pytest.raises(ValidationError, match=slot):
        IriPolicy(**{slot: template})


@pytest.mark.parametrize("character", ["A", "_", "?", "#", " ", "%", "~"])
def test_a_literal_character_outside_the_allowed_set_is_refused(character: str) -> None:
    with pytest.raises(ValidationError, match="tenant_template"):
        IriPolicy(tenant_template="{base}pro" + character + "ject/{tenant_id}")


def test_a_deployment_variable_without_a_deployment_is_refused_naming_it() -> None:
    made = settings(iri_policy=mwb2_policy())
    with pytest.raises(InvalidIri, match="deployment"):
        check_iri_policy(made)


def test_a_policy_without_a_deployment_variable_needs_no_deployment() -> None:
    assert check_iri_policy(settings(iri_policy=IriPolicy())) is None


def test_no_policy_needs_no_check() -> None:
    assert check_iri_policy(settings()) is None


@pytest.mark.parametrize("slot", ["part_template", "loaded_graph_template"])
def test_the_default_part_and_loaded_graph_templates_need_neither_type_tenant_nor_base(slot):
    """The module functions mint them with no tenant and no class (PD-12j)."""
    variables = set(re.findall(r"\{[a-z_]+\}", getattr(IriPolicy(), slot)))
    assert variables == {"{root}", "{id}"}


# app-level-data task 1.1 (PD-1): the application template


def test_the_default_application_template_is_base_app() -> None:
    assert IriPolicy().application_template == "{base}app"


@pytest.mark.parametrize("template", ["{base}{deployment}/app", "{base}{tenant_segment}-app"])
def test_an_application_template_of_the_allowed_placeholders_is_accepted(template: str) -> None:
    assert IriPolicy(application_template=template).application_template == template


@pytest.mark.parametrize("template", ["{base}{tenant_id}", "{base}App", "", "{tenant}/app"])
def test_an_application_template_outside_the_pattern_is_refused(template: str) -> None:
    with pytest.raises(ValidationError, match="application_template"):
        IriPolicy(application_template=template)


def test_a_recorded_policy_without_the_field_holds_the_default_and_the_effective_one_parses() -> (
    None
):
    recorded = IriPolicy.model_validate_json('{"tenant_template": "{base}t/{tenant_id}"}')
    effective = IriPolicy.model_validate_json('{"application_template": "https://ex.org/app"}')
    assert (recorded.application_template, effective.application_template) == (
        "{base}app",
        "https://ex.org/app",
    )

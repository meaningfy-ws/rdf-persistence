"""``Iris.effective_policy`` and ``policy_differences``: what the start-up guard compares (PD-14b)."""

import pytest

from rdf_persistence.domain.generated.service.rp_service import IdKind, IdSpec, IriPolicy
from rdf_persistence.domain.iris import (
    DEFAULT_ALPHABET,
    Iris,
    policy_differences,
    policy_record_iri,
)
from tests.toy import SETTINGS


def effective(policy: IriPolicy | None, **more) -> IriPolicy:
    return Iris(SETTINGS.model_copy(update={"iri_policy": policy, **more})).effective_policy


def test_the_settings_are_written_into_the_templates():
    policy = effective(None)
    assert policy.tenant_template == f"{SETTINGS.base}{SETTINGS.tenant_segment}/{{tenant_id}}"


def test_a_deployment_in_a_template_is_written_in():
    policy = effective(
        IriPolicy(tenant_template="{base}{deployment}/{tenant_id}"), deployment="dep1"
    )
    assert policy.tenant_template == f"{SETTINGS.base}dep1/{{tenant_id}}"


def test_unset_and_empty_parts_get_their_defaults():
    unset = effective(None)
    assert unset == effective(IriPolicy(access_template=None))
    assert unset.tenant_id == IdSpec(kind=IdKind.UUID4)
    assert unset.object_id == IdSpec(kind=IdKind.UUID4)


def test_a_random_id_without_an_alphabet_has_the_default_one():
    spec = IdSpec(kind=IdKind.RANDOM, length=13, alphabet=None)
    assert effective(IriPolicy(object_id=spec)).object_id.alphabet == DEFAULT_ALPHABET


def test_differences_are_dotted_field_names():
    one = effective(IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM, length=8)))
    other = effective(
        IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM, length=9), meta_template="{tenant}/m")
    )
    assert policy_differences(one, other) == ["meta_template", "object_id.length"]


@pytest.mark.parametrize("base", ["https://a.example/", "https://b.example/"])
def test_the_record_iri_is_under_the_toolkit_segment(base):
    assert str(policy_record_iri(base)) == f"{base}toolkit/iri-policy"

"""``Iris`` refuses an activity template a restore could not move or that could collide (activity-iri-policy PD-3a)."""

import pytest

from rdf_persistence.core.domain.exceptions import InvalidIri
from rdf_persistence.iris.services.generated.rp_iris_services import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.iris.services.iris import Iris

BASE = "https://example.org/"
UUID = "7a1e1d6e-2f0b-4c57-9a52-2f2f5d1f6a10"
SHORT = IdSpec(kind=IdKind.RANDOM, length=4, alphabet="048u")


def _settings(**policy: object) -> ServiceSettings:
    return ServiceSettings(
        base=BASE,
        prefix="lib",
        tenant_segment="projects",
        creator_role="owner",
        roles_claim="roles",
        iri_policy=IriPolicy(**policy),
    )


@pytest.mark.parametrize(
    ("policy", "why"),
    [
        pytest.param({"activity_template": "activity/{tenant_id}/{id}"}, "scheme", id="no-scheme"),
        pytest.param(
            {"activity_template": "urn:x:{tenant_id}:{id}"}, "base", id="outside-the-base"
        ),
        pytest.param({"activity_template": "{tenant}{id}"}, "glue", id="tenant-glued-to-id"),
        pytest.param(
            {"activity_template": "{base}{tenant_id}{id}"}, "glue", id="tenant-id-glued-to-id"
        ),
        pytest.param(
            {"activity_template": "{tenant}/{id}", "aggregate_template": "{tenant}/{id}"},
            "aggregate",
            id="the-aggregate-template-is-the-activity-template",
        ),
    ],
)
def test_an_activity_template_a_restore_could_not_move_or_that_collides_is_refused(policy, why):
    with pytest.raises(InvalidIri, match="activity_template") as caught:
        Iris(_settings(**policy))
    assert why in str(caught.value), f"the reason ({why}) is named: {caught.value}"


@pytest.mark.parametrize(
    "policy",
    [
        pytest.param({"activity_template": "{tenant}/activity/{id}"}, id="under-the-tenant"),
        pytest.param({"activity_template": "{base}{tenant_id}/activity/{id}"}, id="tenant-id"),
        pytest.param(
            {
                "activity_template": "{tenant}/{id}",
                "aggregate_template": "{tenant}/{id}",
                "object_id": IdSpec(kind=IdKind.RANDOM, length=13),
            },
            id="random-object-ids-never-read-as-a-uuid",
        ),
    ],
)
def test_an_activity_template_that_moves_with_its_tenant_is_accepted(policy):
    Iris(_settings(**policy))


def test_the_application_is_read_in_a_tenant_id_activity_template():
    iris = Iris(_settings(activity_template="{base}{tenant_id}/activity/{id}"))
    placed = f"{BASE}app/activity/{UUID}"
    assert iris.is_activity(str(iris.application), placed), "an activity of the application"
    assert not iris.is_aggregate(str(iris.application), placed), "no aggregate of it"


def test_the_default_activity_template_is_accepted_under_any_tenant_alphabet():
    for _ in range(50):
        Iris(_settings(tenant_id=SHORT))

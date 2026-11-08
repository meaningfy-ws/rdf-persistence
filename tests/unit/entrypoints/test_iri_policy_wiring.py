"""The kit builds one ``Iris`` and the routes map path ids through it (iri-policy task 3.4, PD-3a, PD-3c).

A path id of the wrong form is a 404 before the store is asked, under the default policy (a UUID)
and under the consumer's (seven lowercase characters, flat objects beside the tenant).
"""

import pytest

from rdf_persistence import AccessRules, load_role_definitions
from rdf_persistence.domain.exceptions import IriPolicyChanged, NotFound
from rdf_persistence.domain.iris import DEFAULT_IRIS, Iris
from tests.toy import ROLES
from tests.toy_service import CONSUMER_POLICY, TENANT_BODY, ToyService

CONSUMER_BASE = "https://example.org/library/"


@pytest.fixture
async def consumer():
    toy = ToyService(iri_policy=CONSUMER_POLICY)
    async with toy.app.router.lifespan_context(toy.app):
        yield toy


async def test_a_wrong_form_tenant_id_is_a_404_and_the_store_is_untouched_by_default(
    service, client
) -> None:
    asked = len(service.store.sent("query"))
    response = await client.get("/libraries/P4X8K2M", headers=service.bearer("ada"))
    assert response.status_code == 404
    assert len(service.store.sent("query")) == asked, "no query went to the store"


async def test_a_wrong_form_aggregate_id_is_a_404_and_the_store_is_untouched_by_default(
    service, client
) -> None:
    tenant = await client.post("/libraries", json=TENANT_BODY, headers=service.bearer("ada"))
    asked = len(service.store.sent("query"))
    response = await client.get(
        f"{tenant.headers['location']}/books/not-a-uuid", headers=service.bearer("ada")
    )
    assert response.status_code == 404
    assert len(service.store.sent("query")) == asked, "no query went to the store"


@pytest.mark.parametrize(
    "tenant_id", ["P4X8K2M", "p4x8k2", "p4x8k2mm", "6f1c0c1e-0000-4000-8000-000000000000"]
)
async def test_a_wrong_form_tenant_id_is_a_404_under_the_consumers_policy(
    consumer, tenant_id
) -> None:
    async with consumer.client() as http:
        asked = len(consumer.store.sent("query"))
        response = await http.get(f"/libraries/{tenant_id}", headers=consumer.bearer("ada"))
    assert response.status_code == 404
    assert len(consumer.store.sent("query")) == asked, "no query went to the store"


async def test_a_wrong_form_aggregate_id_is_a_404_under_the_consumers_policy(consumer) -> None:
    async with consumer.client() as http:
        made = await http.post("/libraries", json=TENANT_BODY, headers=consumer.bearer("ada"))
        asked = len(consumer.store.sent("query"))
        response = await http.get(
            f"{made.headers['location']}/books/NOT-AN-ID", headers=consumer.bearer("ada")
        )
    assert response.status_code == 404
    assert len(consumer.store.sent("query")) == asked, "no query went to the store"


async def test_the_kit_hands_one_policy_to_every_service_it_wires(consumer) -> None:
    kit = consumer.kit
    assert kit.iris.settings.iri_policy == CONSUMER_POLICY
    assert str(kit.tenant_iri("p4x8k2m")) == f"{CONSUMER_BASE}project/p4x8k2m"
    assert kit.rules._iris is kit.iris, (
        "the rules the consumer built are rebound to the kit's policy"
    )
    held = {
        "documents": kit.documents._iris,
        "tenancy": kit.tenancy._iris,
        "aggregates": kit.aggregates._iris,
    }
    assert all(iris is kit.iris for iris in held.values()), held


async def test_a_wrong_form_id_to_require_aggregate_is_not_found(consumer) -> None:
    with pytest.raises(NotFound):
        await consumer.kit.require_aggregate(
            consumer.bearer("ada")["Authorization"],
            "p4x8k2m",
            "books",
            "NOT-AN-ID",
            "read",  # type: ignore[arg-type]
        )


def test_with_iris_keeps_the_permits_and_changes_the_policy() -> None:
    rules = AccessRules(load_role_definitions(ROLES))
    other = Iris(DEFAULT_IRIS.settings.model_copy(update={"base": "https://other.invalid/"}))
    rebound = rules.with_iris(other)
    assert rebound is not rules
    assert rebound._iris is other and rules._iris is DEFAULT_IRIS, "the original is unchanged"
    assert rebound._permits == rules._permits


async def test_start_up_refuses_a_changed_policy_over_the_same_store() -> None:
    first = ToyService(iri_policy=CONSUMER_POLICY)
    async with first.app.router.lifespan_context(first.app):
        pass
    second = ToyService(first.store, first.files, iri_policy=None)
    with pytest.raises(IriPolicyChanged, match="tenant_template"):
        async with second.app.router.lifespan_context(second.app):
            pass

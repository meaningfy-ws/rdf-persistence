"""``ServiceKit.require``: the consumer's own routes get the token check and the access check of the toolkit's (PD-14b)."""

import pytest

from rdf_persistence import Authorised, GrantSet
from rdf_persistence.domain.exceptions import Forbidden, InvalidToken, NotFound
from rdf_persistence.domain.generated.rp_access import Action, Prohibition
from rdf_persistence.domain.iris import graph_iri
from rdf_persistence.domain.media import JSON
from tests.toy_service import principal_of, store_scan
from tests.unit.entrypoints.scene import Scene


def authorization(scene: Scene, who: str) -> str:
    return scene.headers(who)["Authorization"]


def tenant_id(scene: Scene) -> str:
    return scene.tenant_iri.rsplit("/", 1)[-1]


async def test_a_caller_with_the_action_gets_its_access_to_the_tenant(scene) -> None:
    access = await scene.service.kit.require(
        authorization(scene, "ada"), tenant_id(scene), Action.MODIFY
    )
    assert isinstance(access, Authorised), "the model the routes use"
    assert access.caller_access.tenant == scene.tenant_iri, "the tenant of the path"
    assert access.checked_target == scene.tenant_iri, "a tenant check is made on the tenant"
    assert access.principal == principal_of("ada"), "the caller, for a domain service"


async def test_a_request_without_a_bearer_token_is_refused(scene) -> None:
    with pytest.raises(InvalidToken):
        await scene.service.kit.require(None, tenant_id(scene), Action.READ)
    with pytest.raises(InvalidToken):
        await scene.service.kit.require("Basic YWRhOnB3", tenant_id(scene), Action.READ)


async def test_a_caller_who_cannot_see_the_tenant_gets_a_not_found(scene) -> None:
    with pytest.raises(NotFound):
        await scene.service.kit.require(authorization(scene, "omar"), tenant_id(scene), Action.READ)


async def test_a_caller_who_may_read_but_not_modify_is_forbidden(scene) -> None:
    kit = scene.service.kit
    with pytest.raises(Forbidden):
        await kit.require(authorization(scene, "rita"), tenant_id(scene), Action.MODIFY)


async def test_an_id_that_is_no_tenant_id_is_a_not_found(scene) -> None:
    with pytest.raises(NotFound):
        await scene.service.kit.require(authorization(scene, "ada"), "nope", Action.READ)


async def scanned(scene: Scene) -> tuple[str, str]:
    scan = await store_scan(scene.service.kit, scene.tenant_iri, principal_of("ada"))
    return scan.id, scan.id.rsplit("/", 1)[-1]


async def test_an_aggregate_is_checked_and_its_iri_is_the_one_to_act_on(scene) -> None:
    iri, scan_id = await scanned(scene)
    checked = await scene.service.kit.require_aggregate(
        authorization(scene, "rita"), tenant_id(scene), "scans", scan_id, Action.READ
    )
    assert checked.checked_target == iri, "the aggregate the check was made on"
    assert checked.caller_access.tenant == scene.tenant_iri, "and the access to its tenant"
    assert checked.principal == principal_of("rita"), "and the caller's principal"


async def test_a_prohibition_on_the_aggregate_applies(scene) -> None:
    iri, scan_id = await scanned(scene)
    held = GrantSet.model_validate(
        (await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))).json()
    )
    ban = Prohibition(assignee=principal_of("rita"), target=str(graph_iri(iri)), action=Action.READ)
    body = GrantSet(grants=held.grants, prohibitions=[ban]).model_dump_json(exclude_none=True)
    put = await scene.http.put(
        f"{scene.tenant}/grants",
        content=body,
        headers=scene.headers("ada", **{"If-Match": scene.access_etag, "Content-Type": JSON}),
    )
    assert put.status_code == 200, put.text
    with pytest.raises(Forbidden):
        await scene.service.kit.require_aggregate(
            authorization(scene, "rita"), tenant_id(scene), "scans", scan_id, Action.READ
        )


async def test_an_aggregate_id_that_is_no_uuid_is_a_not_found_before_the_store_is_asked(
    scene,
) -> None:
    store = scene.service.store
    asked = len(store.sent("query"))
    with pytest.raises(NotFound):
        await scene.service.kit.require_aggregate(
            authorization(scene, "ada"), tenant_id(scene), "scans", "../graph", Action.READ
        )
    assert len(store.sent("query")) == asked, "no query"

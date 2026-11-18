"""Tenant delete by a system role, attacked through the routes: which actions authorise it."""

from rdf_persistence.core.domain.generated.rp_access import Action, RoleDefinition, RoleLevel
from rdf_persistence.services.access import AccessRules, load_role_definitions
from tests.toy import ROLES


async def test_a_system_admin_with_read_only_cannot_delete_a_tenant(scene) -> None:
    response = await scene.http.delete(
        scene.tenant, headers=scene.headers("root", "admin", **{"If-Match": scene.access_etag})
    )
    assert response.status_code == 403, "the shipped system `admin` role only reads"


async def test_a_system_role_with_administer_deletes_a_tenant_without_a_grant(scene) -> None:
    root_role = RoleDefinition(
        role="superuser", level=RoleLevel.SYSTEM, actions=[Action.READ, Action.ADMINISTER]
    )
    scene.service.kit.rules = AccessRules([*load_role_definitions(ROLES), root_role]).with_iris(
        scene.service.kit.iris
    )
    response = await scene.http.delete(
        scene.tenant,
        headers=scene.headers("root", "superuser", **{"If-Match": scene.access_etag}),
    )
    assert response.status_code == 204, response.text


async def test_a_system_role_with_delete_only_cannot_delete_a_tenant(scene) -> None:
    role = RoleDefinition(
        role="janitor", level=RoleLevel.SYSTEM, actions=[Action.READ, Action.DELETE]
    )
    scene.service.kit.rules = AccessRules([*load_role_definitions(ROLES), role]).with_iris(
        scene.service.kit.iris
    )
    response = await scene.http.delete(
        scene.tenant, headers=scene.headers("root", "janitor", **{"If-Match": scene.access_etag})
    )
    assert response.status_code == 403, "delete alone does not delete the tenant"
    assert (await scene.http.get(scene.tenant, headers=scene.headers("ada"))).status_code == 200, (
        "the tenant still reads"
    )

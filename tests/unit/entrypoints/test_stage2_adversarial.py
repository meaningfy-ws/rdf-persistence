"""Stage 2 of mwb2-adoption-fixes, attacked at the route: validators on tenant writes (PD-7)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from rdf_persistence import InvalidBody, Page
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.iris import tenant_resource_name
from rdf_persistence.domain.media import JSON
from tests.toy_service import ToyService, principal_of
from tests.unit.entrypoints.scene import PROBLEMS, Scene, problem_of


@asynccontextmanager
async def _scene_validated(**validators) -> AsyncIterator[Scene]:
    toy = ToyService(**validators)
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        yield await Scene.set_up(toy, http)


def _invalid_model(old, new, who) -> None:
    if old is not None:  # the scene's own creation runs root validators too
        Page.model_validate({"items": "x"})  # pydantic's ValidationError


def _refuse(old, new, who) -> None:
    if old is not None:
        raise InvalidBody("no")


async def _rename(scene: Scene, label: str) -> httpx.Response:
    return await scene.http.put(
        f"{scene.tenant}/label",
        json={"label": label},
        headers=scene.headers("ada", **{"If-Match": scene.access_etag}),
    )


async def _put_root(scene: Scene, city: str) -> httpx.Response:
    body = {"label": "Ghent", "description": "Books for all.", "city": city}
    return await scene.http.put(
        scene.tenant, json=body, headers=scene.headers("ada", **{"If-Match": scene.root_etag})
    )


async def _etags(scene: Scene) -> tuple[str, str]:
    grants = await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))
    root = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    return grants.headers["etag"], root.headers["etag"]


async def test_a_pydantic_error_from_a_root_validator_on_rename_is_a_422_and_nothing_moves() -> (
    None
):
    async with _scene_validated(root_validators=[_invalid_model]) as scene:
        before = await _etags(scene)
        response = await _rename(scene, "B")
        assert response.status_code == 422, response.text
        assert await _etags(scene) == before, "neither the record nor the root moved"


async def test_a_refusal_on_rename_is_a_422_and_the_label_stays() -> None:
    async with _scene_validated(root_validators=[_refuse]) as scene:
        before = await _etags(scene)
        response = await _rename(scene, "B")
        assert (response.status_code, problem_of(response).type) == (
            422,
            f"{PROBLEMS}invalid-body",
        ), response.text
        root = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
        assert (root.json()["label"], await _etags(scene)) == ("Ghent", before), "all as before"


async def test_a_toolkit_validation_error_on_rename_is_still_a_422_with_validators_installed() -> (
    None
):
    async with _scene_validated(root_validators=[lambda *_: None]) as scene:
        response = await _rename(scene, "")
        assert response.status_code == 422, response.text


async def test_a_root_put_to_an_unknown_tenant_is_a_404_with_validators_installed() -> None:
    async with _scene_validated(root_validators=[_refuse]) as scene:
        response = await scene.http.put(
            "/libraries/00000000-0000-4000-8000-000000000000",
            json={"label": "Ghent", "description": "d", "city": "Ghent"},
            headers=scene.headers("ada", **{"If-Match": scene.root_etag}),
        )
        assert response.status_code in (403, 404), response.text


async def test_a_root_put_with_a_stale_etag_and_a_refusing_validator_still_reports_one_problem() -> (
    None
):
    async with _scene_validated(root_validators=[_refuse]) as scene:
        response = await _put_root(scene, "Bruges")
        assert response.status_code == 422, "the validator refuses before the version is compared"
        stale = await scene.http.put(
            scene.tenant,
            json={"label": "Ghent", "description": "d", "city": "Bruges"},
            headers=scene.headers("ada", **{"If-Match": '"stale"'}),
        )
        assert stale.status_code == 422, stale.text


async def test_a_pydantic_error_from_a_validator_on_a_root_put_is_a_422_and_the_root_keeps_its_etag() -> (
    None
):
    async with _scene_validated(root_validators=[_invalid_model]) as scene:
        before = await _etags(scene)
        response = await _put_root(scene, "Bruges")
        assert response.status_code == 422, response.text
        assert await _etags(scene) == before, "nothing written"


async def _outcome_of_a_root_put_on_a_deleting_tenant(**validators) -> str:
    """What the root replace answers when the tenant is half way through its deletion."""
    async with _scene_validated(**validators) as scene:
        kit = scene.service.kit
        record, version = await kit.tenancy.get(scene.tenant_iri)
        record.state = TenantState.DELETING
        toolkit = kit.tenancy._toolkit
        system = kit.tenancy.system_database
        await kit.tenancy._replace_root(system, scene.tenant_iri, toolkit, record, version)
        prefix = scene.service.settings.prefix
        await scene.service.store.drop_dataset(tenant_resource_name(prefix, scene.tenant_iri))
        body = b'{"label": "Ghent", "description": "Books for all.", "city": "Bruges"}'
        try:
            await kit.aggregates.replace(
                scene.tenant_iri,
                Principal(id=principal_of("ada")),
                kit.documents.tenant_root,
                scene.tenant_iri,
                body,
                JSON,
                scene.root_etag.strip('"'),
            )
        except Exception as error:
            return type(error).__name__
        return "replaced"


async def test_a_root_put_on_a_deleting_tenant_answers_the_same_with_and_without_validators() -> (
    None
):
    plain = await _outcome_of_a_root_put_on_a_deleting_tenant()
    watched = await _outcome_of_a_root_put_on_a_deleting_tenant(root_validators=[lambda *_: None])
    assert watched == plain, f"validators change the outcome: {plain} without, {watched} with"

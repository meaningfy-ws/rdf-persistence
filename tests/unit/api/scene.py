"""The scene of the router's tests: a tenant with a book, a reader and an outsider, over the toy service."""

import httpx

from rdf_persistence import GrantSet, Problem
from rdf_persistence.access.domain.generated.rp_access import (
    Action,
    Grant,
    Prohibition,
    RoleDefinition,
    RoleLevel,
)
from rdf_persistence.access.services.access import AccessRules, load_role_definitions
from rdf_persistence.core.domain.media import JSON, PROBLEM_JSON
from tests.toy import ROLES, SETTINGS
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, principal_of

PROBLEMS = f"{SETTINGS.base}problems/"
NIL = "00000000-0000-4000-8000-00000000000"


class Scene:
    """A tenant made by ``ada`` (a librarian), with a book in it, a reader ``rita`` and an outsider ``omar``."""

    def __init__(self, service: ToyService, http: httpx.AsyncClient) -> None:
        self.service, self.http = service, http
        self.tenant = ""
        self.tenant_iri = ""
        self.book = ""
        self.book_iri = ""
        self.book_etag = ""
        self.access_etag = ""
        self.root_etag = ""

    def headers(self, who: str, *roles: str, **extra: str) -> dict[str, str]:
        return {**self.service.bearer(who, *roles), **extra}

    async def set_grants(self, grants: GrantSet) -> str:
        """Replace the tenant's grants as ada under the current access ETag; answers the new ETag, which the caller keeps."""
        response = await self.http.put(
            f"{self.tenant}/grants",
            content=grants.model_dump_json(exclude_none=True),
            headers=self.headers("ada", **{"If-Match": self.access_etag, "Content-Type": JSON}),
        )
        assert response.status_code == 200, response.text
        return response.headers["etag"]

    @classmethod
    async def set_up(cls, service: ToyService, http: httpx.AsyncClient) -> "Scene":
        scene = cls(service, http)
        made = await http.post("/libraries", json=TENANT_BODY, headers=scene.headers("ada"))
        assert made.status_code == 201, made.text  # say why, if the tenant was not made
        scene.tenant, scene.tenant_iri = made.headers["location"], made.json()["id"]
        book = await http.post(
            f"{scene.tenant}/books", json=DUNE_BODY, headers=scene.headers("ada")
        )
        scene.book, scene.book_etag = book.headers["location"], book.headers["etag"]
        scene.book_iri = book.json()["id"]
        grants = await http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))
        scene.access_etag = grants.headers["etag"]
        body = GrantSet.model_validate(grants.json())
        reader = Grant(assignee=principal_of("rita"), target=scene.tenant_iri, role="reader")
        scene.access_etag = await scene.set_grants(GrantSet(grants=[*(body.grants or []), reader]))
        root = await http.get(scene.tenant, headers=scene.headers("ada"))
        scene.root_etag = root.headers["etag"]
        return scene


def problem_of(response: httpx.Response) -> Problem:
    assert response.headers["content-type"] == PROBLEM_JSON, response.text
    return Problem.model_validate(response.json())


async def ada_and_mia_are_members(scene: Scene) -> str:
    """Add a ``member`` role (read, modify, delete) to the rules and make mia one; the new access ETag."""
    member = RoleDefinition(
        role="member",
        level=RoleLevel.TENANT,
        actions=[Action.READ, Action.MODIFY, Action.DELETE],
    )
    scene.service.kit.rules = AccessRules([*load_role_definitions(ROLES), member]).with_iris(
        scene.service.kit.iris
    )
    return await scene.set_grants(
        GrantSet(
            grants=[
                Grant(assignee=principal_of("ada"), target=scene.tenant_iri, role="librarian"),
                Grant(assignee=principal_of("mia"), target=scene.tenant_iri, role="member"),
            ]
        )
    )


async def everyone_has_a_role(scene: Scene, *prohibitions: Prohibition) -> None:
    """ada a librarian, mia a member (read, modify, delete), rita a reader; ``prohibitions`` on top."""
    scene.access_etag = await ada_and_mia_are_members(scene)
    grants = [
        Grant(assignee=principal_of("ada"), target=scene.tenant_iri, role="librarian"),
        Grant(assignee=principal_of("mia"), target=scene.tenant_iri, role="member"),
        Grant(assignee=principal_of("rita"), target=scene.tenant_iri, role="reader"),
    ]
    await scene.set_grants(GrantSet(grants=grants, prohibitions=list(prohibitions) or None))

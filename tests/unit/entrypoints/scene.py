"""The scene of the router's tests: a tenant with a book, a reader and an outsider, over the toy service."""

import httpx

from rdf_persistence import GrantSet, Problem
from rdf_persistence.domain.generated.rp_access import Grant
from rdf_persistence.domain.media import JSON, PROBLEM_JSON
from tests.toy import SETTINGS
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

    @classmethod
    async def set_up(cls, service: ToyService, http: httpx.AsyncClient) -> "Scene":
        scene = cls(service, http)
        made = await http.post("/libraries", json=TENANT_BODY, headers=scene.headers("ada"))
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
        replaced = await http.put(
            f"{scene.tenant}/grants",
            content=GrantSet(grants=[*(body.grants or []), reader]).model_dump_json(
                exclude_none=True
            ),
            headers=scene.headers("ada", **{"If-Match": scene.access_etag, "Content-Type": JSON}),
        )
        assert replaced.status_code == 200, replaced.text
        scene.access_etag = replaced.headers["etag"]
        root = await http.get(scene.tenant, headers=scene.headers("ada"))
        scene.root_etag = root.headers["etag"]
        return scene


def problem_of(response: httpx.Response) -> Problem:
    assert response.headers["content-type"] == PROBLEM_JSON, response.text
    return Problem.model_validate(response.json())

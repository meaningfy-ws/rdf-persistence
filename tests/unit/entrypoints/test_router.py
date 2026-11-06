"""The generic router over the fakes: tenant routes, aggregate routes, and who may do what (tasks 5.2, 5.3, PD-9, PD-13)."""

import json
import re
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID

import httpx
import pytest
from pyld import jsonld
from rdflib import Graph
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence import GrantSet, Page, Problem, TenantSummary
from rdf_persistence.domain.generated.rp_access import Action, Grant, Prohibition
from rdf_persistence.domain.iris import graph_iri
from rdf_persistence.entrypoints.problems import PROBLEM_MEDIA_TYPE
from rdf_persistence.services.documents import JSON, JSON_LD, TURTLE
from tests.toy import SETTINGS
from tests.toy_service import ToyService, principal_of

PROBLEMS = f"{SETTINGS.base}problems/"
TENANT_BODY = {"label": "Ghent", "root": {"description": "Books for all.", "city": "Ghent"}}
BOOK = {
    "label": "Dune",
    "description": "A planet.",
    "genre": "fiction",
    "authors": ["Herbert"],
    "chapters": [{"number": 1, "notes": [{"label": "n", "description": "d", "text": "t"}]}],
}
NIL = "00000000-0000-4000-8000-00000000000"


@pytest.fixture
async def service() -> AsyncIterator[ToyService]:
    toy = ToyService()
    async with toy.app.router.lifespan_context(toy.app):
        yield toy


@pytest.fixture
async def client(service: ToyService) -> AsyncIterator[httpx.AsyncClient]:
    async with service.client() as http:
        yield http


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
        book = await http.post(f"{scene.tenant}/books", json=BOOK, headers=scene.headers("ada"))
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


@pytest.fixture
async def scene(service: ToyService, client: httpx.AsyncClient) -> Scene:
    return await Scene.set_up(service, client)


def problem_of(response: httpx.Response) -> Problem:
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE, response.text
    return Problem.model_validate(response.json())


# --- tenants ------------------------------------------------------------------------------------


async def test_a_valid_token_is_all_it_takes_to_create_a_tenant(service, client) -> None:
    response = await client.post("/libraries", json=TENANT_BODY, headers=service.bearer("anyone"))
    summary = TenantSummary.model_validate(response.json())
    assert response.status_code == 201, response.text
    assert (summary.label, summary.state) == ("Ghent", "active"), "the summary of the new tenant"
    assert response.headers["location"] == f"/libraries/{summary.id.rsplit('/', 1)[1]}", (
        "its location"
    )


async def test_the_creator_is_a_librarian_of_the_new_tenant(scene) -> None:
    response = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert response.status_code == 200, "the root object"
    assert response.json()["city"] == "Ghent", "the root object"


async def test_a_tenant_body_that_fails_the_class_is_a_422_naming_the_slot(service, client) -> None:
    body = {"label": "Ghent", "root": {"city": 5}}
    response = await client.post("/libraries", json=body, headers=service.bearer("ada"))
    assert response.status_code == 422, response.text
    assert "city" in (problem_of(response).detail or ""), "the slot is named"


@pytest.mark.parametrize(
    "root",
    [
        {"description": "d", "id": "https://evil.example/t"},
        {"description": "d", "colour": "red"},
        "text",
        None,
    ],
    ids=["client-iri", "unknown-slot", "not-an-object", "null"],
)
async def test_a_tenant_root_the_service_cannot_take_is_a_422(service, client, root) -> None:
    response = await client.post(
        "/libraries", json={"label": "G", "root": root}, headers=service.bearer("ada")
    )
    assert (response.status_code, problem_of(response).type) == (422, f"{PROBLEMS}invalid-body"), (
        root
    )


async def test_a_refused_tenant_leaves_no_database_behind(service, client) -> None:
    before = await service.store.list_datasets()
    await client.post("/libraries", json={"label": "", "root": {}}, headers=service.bearer("ada"))
    assert await service.store.list_datasets() == before, (
        "validation comes before anything is created"
    )


async def test_a_tenant_body_must_be_json(service, client) -> None:
    response = await client.post(
        "/libraries",
        content="label: x",
        headers={**service.bearer("ada"), "Content-Type": "text/yaml"},
    )
    assert response.status_code == 415, "status"


async def test_the_listing_shows_a_caller_the_tenants_it_has_a_grant_in(scene) -> None:
    mine = Page.model_validate(
        (await scene.http.get("/libraries", headers=scene.headers("ada"))).json()
    )
    other = Page.model_validate(
        (await scene.http.get("/libraries", headers=scene.headers("omar"))).json()
    )
    assert [i["label"] for i in mine.items] == ["Ghent"], "the creator sees it"
    assert mine.total == 1, "the creator sees it"
    assert other.items == [], "an outsider sees nothing"
    assert other.total == 0, "an outsider sees nothing"


async def test_a_global_reader_lists_every_tenant(scene) -> None:
    page = Page.model_validate(
        (await scene.http.get("/libraries", headers=scene.headers("root", "admin"))).json()
    )
    assert page.total == 1, "the global admin reads all"


async def test_the_label_is_replaced_under_if_match_and_the_version_moves(scene) -> None:
    response = await scene.http.put(
        f"{scene.tenant}/label",
        json={"label": "Bruges"},
        headers=scene.headers("ada", **{"If-Match": scene.access_etag}),
    )
    assert response.status_code == 200, response.text
    assert response.json()["label"] == "Bruges", response.text
    assert response.headers["etag"] != scene.access_etag, "a new version"
    listing = Page.model_validate(
        (await scene.http.get("/libraries", headers=scene.headers("ada"))).json()
    )
    assert listing.items[0]["label"] == "Bruges", "the listing shows it"


async def test_a_label_that_fails_the_pattern_is_a_422(scene) -> None:
    response = await scene.http.put(
        f"{scene.tenant}/label",
        json={"label": " x"},
        headers=scene.headers("ada", **{"If-Match": scene.access_etag}),
    )
    assert response.status_code == 422, "the label of every boundary has the same pattern"


async def test_the_grants_are_read_with_the_etag_of_the_access_record(scene) -> None:
    response = await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))
    grants = GrantSet.model_validate(response.json())
    assert {g.assignee for g in grants.grants or []} == {
        principal_of("ada"),
        principal_of("rita"),
    }, "the creator's and the reader's"
    assert response.headers["etag"] == scene.access_etag, "the record's version"


async def test_a_grant_set_replaces_the_grants(scene) -> None:
    grants = GrantSet(
        grants=[Grant(assignee=principal_of("ada"), target=scene.tenant_iri, role="librarian")],
        prohibitions=[
            Prohibition(assignee=principal_of("ada"), target=scene.tenant_iri, action=Action.DELETE)
        ],
    )
    response = await scene.http.put(
        f"{scene.tenant}/grants",
        content=grants.model_dump_json(exclude_none=True),
        headers=scene.headers("ada", **{"If-Match": scene.access_etag, "Content-Type": JSON}),
    )
    assert response.status_code == 200, response.text
    gone = await scene.http.get(scene.book, headers=scene.headers("rita"))
    assert gone.status_code == 404, "the reader's grant is gone, so is her view of the tenant"
    refused = await scene.http.delete(
        scene.tenant, headers=scene.headers("ada", **{"If-Match": response.headers["etag"]})
    )
    assert refused.status_code == 403, "the new prohibition forbids deleting"


@pytest.mark.parametrize(
    "grant",
    [
        {"assignee": "https://example.org/people/x", "target": "TENANT", "role": "wizard"},
        {"assignee": "not an iri", "target": "TENANT", "role": "reader"},
        {
            "assignee": "https://example.org/people/x",
            "target": "https://elsewhere.example/t",
            "role": "reader",
        },
        {
            "assignee": "https://example.org/people/x",
            "target": "TENANT",
            "role": "reader",
            "action": "read",
        },
    ],
    ids=["unknown-role", "assignee-not-an-iri", "foreign-target", "role-and-action"],
)
async def test_a_grant_set_the_check_could_not_honour_is_a_422_and_changes_nothing(
    scene, grant
) -> None:
    grant = {k: (scene.tenant_iri if v == "TENANT" else v) for k, v in grant.items()}
    response = await scene.http.put(
        f"{scene.tenant}/grants",
        json={"grants": [grant]},
        headers=scene.headers("ada", **{"If-Match": scene.access_etag}),
    )
    assert (response.status_code, problem_of(response).type) == (422, f"{PROBLEMS}invalid-body"), (
        response.text
    )
    unchanged = await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))
    assert unchanged.headers["etag"] == scene.access_etag, "the access record is unchanged"


async def test_a_grant_set_with_a_duplicate_key_is_a_422(scene) -> None:
    grant = {"assignee": principal_of("rita"), "target": scene.tenant_iri, "role": "reader"}
    response = await scene.http.put(
        f"{scene.tenant}/grants",
        json={"grants": [grant, grant]},
        headers=scene.headers("ada", **{"If-Match": scene.access_etag}),
    )
    assert response.status_code == 422, "two grants with one key"


async def test_deleting_a_tenant_drops_it_and_everything_in_it(scene) -> None:
    response = await scene.http.delete(
        scene.tenant, headers=scene.headers("ada", **{"If-Match": scene.access_etag})
    )
    assert response.status_code == 204, response.text
    assert (await scene.http.get(scene.book, headers=scene.headers("ada"))).status_code == 404, (
        "the book"
    )
    assert (await scene.http.get(scene.tenant, headers=scene.headers("ada"))).status_code == 404, (
        "the tenant"
    )
    assert await scene.service.files.list_buckets("lib-t-") == [], "and its bucket"


async def test_deleting_a_tenant_needs_if_match_and_the_current_version(scene) -> None:
    missing = await scene.http.delete(scene.tenant, headers=scene.headers("ada"))
    stale = await scene.http.delete(
        scene.tenant, headers=scene.headers("ada", **{"If-Match": '"old"'})
    )
    assert (missing.status_code, stale.status_code) == (428, 409), "428 without, 409 when stale"


async def test_the_tenant_root_is_replaced_under_if_match(scene) -> None:
    body = {"label": "Ghent", "description": "New description.", "city": "Bruges"}
    response = await scene.http.put(
        scene.tenant, json=body, headers=scene.headers("ada", **{"If-Match": scene.root_etag})
    )
    assert response.status_code == 200, response.text
    assert response.json()["city"] == "Bruges", response.text
    assert response.headers["etag"] != scene.root_etag, "a new version"


async def test_the_tenant_root_cannot_change_its_id(scene) -> None:
    body = {"id": f"{SETTINGS.base}libraries/{NIL}1", "label": "G", "description": "d", "city": "x"}
    response = await scene.http.put(
        scene.tenant, json=body, headers=scene.headers("ada", **{"If-Match": scene.root_etag})
    )
    assert response.status_code == 422, "the id is the tenant's"


# --- aggregates ---------------------------------------------------------------------------------


async def test_a_created_book_has_a_minted_iri_a_location_and_a_version(scene) -> None:
    response = await scene.http.post(
        f"{scene.tenant}/books", json=BOOK, headers=scene.headers("ada")
    )
    book = response.json()
    assert response.status_code == 201, response.text
    assert book["id"].startswith(f"{SETTINGS.base}libraries/"), "the IRI is minted under the tenant"
    assert book["id"].rsplit("/", 2)[-2] == "books", "below the type's path"
    UUID(book["id"].rsplit("/", 1)[1])
    assert response.headers["location"] == f"{scene.tenant}/books/{book['id'].rsplit('/', 1)[1]}", (
        "location"
    )
    assert response.headers["etag"], "version"


async def test_a_book_sent_with_an_iri_on_create_is_refused(scene) -> None:
    body = {**BOOK, "id": f"{SETTINGS.base}libraries/{NIL}1/books/{NIL}2"}
    response = await scene.http.post(
        f"{scene.tenant}/books", json=body, headers=scene.headers("ada")
    )
    assert (response.status_code, problem_of(response).type) == (422, f"{PROBLEMS}invalid-body"), (
        "refused"
    )


async def test_a_read_returns_what_was_created(scene) -> None:
    response = await scene.http.get(scene.book, headers=scene.headers("ada"))
    book = response.json()
    assert (book["label"], book["genre"], book["authors"]) == ("Dune", "fiction", ["Herbert"]), (
        "slots"
    )
    assert book["chapters"][0]["notes"][0]["text"] == "t", "owned parts are nested"
    assert response.headers["etag"] == scene.book_etag, "the version of the create"


async def test_a_read_of_a_book_that_does_not_exist_is_a_404_problem(scene) -> None:
    response = await scene.http.get(f"{scene.tenant}/books/{NIL}9", headers=scene.headers("ada"))
    assert (response.status_code, problem_of(response).type) == (404, f"{PROBLEMS}not-found"), (
        "missing"
    )


async def test_a_replace_changes_the_book_and_moves_its_version(scene) -> None:
    changed = {**BOOK, "label": "Dune Messiah"}
    response = await scene.http.put(
        scene.book, json=changed, headers=scene.headers("ada", **{"If-Match": scene.book_etag})
    )
    assert response.status_code == 200, response.text
    assert response.json()["label"] == "Dune Messiah", response.text
    assert response.headers["etag"] != scene.book_etag, "a new version"
    assert (await scene.http.get(scene.book, headers=scene.headers("ada"))).json()[
        "label"
    ] == "Dune Messiah", "stored"


async def test_a_replace_may_repeat_the_id_of_the_book(scene) -> None:
    current = (await scene.http.get(scene.book, headers=scene.headers("ada"))).json()
    response = await scene.http.put(
        scene.book, json=current, headers=scene.headers("ada", **{"If-Match": scene.book_etag})
    )
    assert response.status_code == 200, "what a read returns, a replace takes back"


async def test_a_replace_with_another_id_is_refused_and_changes_nothing(scene) -> None:
    other_id = f"{scene.tenant_iri}/books/{NIL}7"
    response = await scene.http.put(
        scene.book,
        json={**BOOK, "id": other_id},
        headers=scene.headers("ada", **{"If-Match": scene.book_etag}),
    )
    assert (response.status_code, problem_of(response).type) == (422, f"{PROBLEMS}invalid-body"), (
        "refused"
    )
    assert (await scene.http.get(scene.book, headers=scene.headers("ada"))).headers[
        "etag"
    ] == scene.book_etag, "unchanged"


async def test_a_replace_of_a_book_that_does_not_exist_does_not_create_it(scene) -> None:
    missing = f"{scene.tenant}/books/{NIL}9"
    response = await scene.http.put(
        missing, json=BOOK, headers=scene.headers("ada", **{"If-Match": '"x"'})
    )
    assert response.status_code == 404, "a PUT replaces; it does not create (IRIs are minted)"


@pytest.mark.parametrize(
    "body",
    [
        {k: v for k, v in BOOK.items() if k != "description"},
        {**BOOK, "colour": "red"},
        {**BOOK, "genre": "cookery"},
        {**BOOK, "chapters": [{"number": "one"}]},
    ],
    ids=["missing-description", "unknown-slot", "unknown-enum-value", "wrong-datatype"],
)
async def test_a_book_that_fails_its_shape_is_a_422_and_writes_nothing(scene, body) -> None:
    writes = len(scene.service.store.sent("update"))
    response = await scene.http.post(
        f"{scene.tenant}/books", json=body, headers=scene.headers("ada")
    )
    assert (response.status_code, problem_of(response).type) == (422, f"{PROBLEMS}invalid-body"), (
        response.text
    )
    assert len(scene.service.store.sent("update")) == writes, "validation comes before the store"


async def test_a_body_that_is_not_json_is_a_422(scene) -> None:
    response = await scene.http.post(
        f"{scene.tenant}/books",
        content="{oops",
        headers=scene.headers("ada", **{"Content-Type": JSON}),
    )
    assert response.status_code == 422, "the parse error is the caller's"


async def test_a_delete_removes_the_book(scene) -> None:
    response = await scene.http.delete(
        scene.book, headers=scene.headers("ada", **{"If-Match": scene.book_etag})
    )
    assert response.status_code == 204, "no content"
    assert response.content == b"", "no content"
    assert (await scene.http.get(scene.book, headers=scene.headers("ada"))).status_code == 404, (
        "gone"
    )


async def test_an_unknown_aggregate_type_is_a_404(scene) -> None:
    response = await scene.http.post(
        f"{scene.tenant}/shelves", json=BOOK, headers=scene.headers("ada")
    )
    assert response.status_code == 404, (
        "the model has no such type, so the router has no such route"
    )


async def test_the_scan_type_is_served_beside_the_book(scene) -> None:
    response = await scene.http.get(f"{scene.tenant}/scans/{NIL}1", headers=scene.headers("ada"))
    assert response.status_code == 404, "the route exists; the scan does not"


async def test_the_access_record_has_no_generic_route(scene) -> None:
    for path in (f"{scene.tenant}/access", f"{scene.tenant}/access/{NIL}1"):
        assert (await scene.http.get(path, headers=scene.headers("ada"))).status_code == 404, path


# --- representations (task 5.3) -----------------------------------------------------------------


async def test_plain_json_points_at_the_context_by_a_link_header(scene) -> None:
    response = await scene.http.get(scene.book, headers=scene.headers("ada"))
    link = response.headers["link"]
    assert response.headers["content-type"] == JSON, "plain JSON by default"
    assert re.fullmatch(
        r'<http://test/context\.jsonld>; rel="http://www\.w3\.org/ns/json-ld#context"', link
    ), link
    assert "@context" not in response.json(), "the context is linked, not inlined"


async def test_the_linked_context_is_served_without_a_token(scene) -> None:
    response = await scene.http.get("/context.jsonld")
    assert response.status_code == 200, "JSON-LD"
    assert response.headers["content-type"] == JSON_LD, "JSON-LD"
    assert response.json()["@context"] == scene.service.kit.documents.context, (
        "the generated context"
    )


async def test_json_ld_is_served_on_request_with_its_context(scene) -> None:
    response = await scene.http.get(scene.book, headers=scene.headers("ada", Accept=JSON_LD))
    assert response.headers["content-type"] == JSON_LD, "media type"
    assert response.json()["@context"], "self-contained"
    assert "link" not in response.headers, "the context is inline"


async def test_turtle_is_served_on_request(scene) -> None:
    response = await scene.http.get(scene.book, headers=scene.headers("ada", Accept=TURTLE))
    graph = Graph().parse(data=response.text, format="turtle")
    assert response.headers["content-type"].startswith(TURTLE) and len(graph) > 5, (
        "the book as triples"
    )


async def test_the_json_ld_of_a_book_is_accepted_back_as_a_replace(scene) -> None:
    current = (
        await scene.http.get(scene.book, headers=scene.headers("ada", Accept=JSON_LD))
    ).json()
    response = await scene.http.put(
        scene.book,
        content=json.dumps({**current, "label": "Via JSON-LD"}),
        headers=scene.headers("ada", **{"If-Match": scene.book_etag, "Content-Type": JSON_LD}),
    )
    assert response.status_code == 200, response.text
    assert response.json()["label"] == "Via JSON-LD", response.text


async def test_a_representation_the_service_does_not_make_is_a_406_before_anything_is_written(
    scene,
) -> None:
    writes = len(scene.service.store.sent("update"))
    response = await scene.http.post(
        f"{scene.tenant}/books", json=BOOK, headers=scene.headers("ada", Accept="text/html")
    )
    assert (response.status_code, problem_of(response).type) == (
        406,
        f"{PROBLEMS}not-acceptable",
    ), "406"
    assert len(scene.service.store.sent("update")) == writes, (
        "no book was created that the client cannot read"
    )


@pytest.mark.parametrize("content_type", [TURTLE, "text/plain", "application/xml"])
async def test_a_body_in_another_format_is_a_415(scene, content_type) -> None:
    response = await scene.http.post(
        f"{scene.tenant}/books",
        content="x",
        headers=scene.headers("ada", **{"Content-Type": content_type}),
    )
    assert (response.status_code, problem_of(response).type) == (
        415,
        f"{PROBLEMS}unsupported-media-type",
    ), "415"


# --- who may do what: the table of PD-9, through the routes ---------------------------------------

Request = tuple[str, str, dict[str, Any]]
ROUTES: dict[str, Callable[[Scene], Request]] = {
    "read a book": lambda s: ("GET", s.book, {}),
    "create a book": lambda s: ("POST", f"{s.tenant}/books", {"json": BOOK}),
    "replace a book": lambda s: ("PUT", s.book, {"json": BOOK, "etag": s.book_etag}),
    "delete a book": lambda s: ("DELETE", s.book, {"etag": s.book_etag}),
    "read the grants": lambda s: ("GET", f"{s.tenant}/grants", {}),
    "replace the grants": lambda s: (
        "PUT",
        f"{s.tenant}/grants",
        {"json": {}, "etag": s.access_etag},
    ),
    "rename the tenant": lambda s: (
        "PUT",
        f"{s.tenant}/label",
        {"json": {"label": "X"}, "etag": s.access_etag},
    ),
    "read the root": lambda s: ("GET", s.tenant, {}),
    "replace the root": lambda s: (
        "PUT",
        s.tenant,
        {"json": {"label": "G", "description": "d", "city": "c"}, "etag": s.root_etag},
    ),
    "delete the tenant": lambda s: ("DELETE", s.tenant, {"etag": s.access_etag}),
}
# the status each caller gets from each route, as PD-9's matrix says; the admin is a global role
MATRIX: dict[str, dict[str, int]] = {
    "librarian": {
        "read a book": 200,
        "create a book": 201,
        "replace a book": 200,
        "delete a book": 204,
        "read the grants": 200,
        "replace the grants": 200,
        "rename the tenant": 200,
        "read the root": 200,
        "replace the root": 200,
        "delete the tenant": 204,
    },
    "reader": {
        "read a book": 200,
        "create a book": 403,
        "replace a book": 403,
        "delete a book": 403,
        "read the grants": 403,
        "replace the grants": 403,
        "rename the tenant": 403,
        "read the root": 200,
        "replace the root": 403,
        "delete the tenant": 403,
    },
    "outsider": {name: 404 for name in ROUTES},
    "admin": {
        "read a book": 200,
        "create a book": 403,
        "replace a book": 403,
        "delete a book": 403,
        "read the grants": 403,
        "replace the grants": 403,
        "rename the tenant": 403,
        "read the root": 200,
        "replace the root": 403,
        "delete the tenant": 403,
    },
}
WHO = {
    "librarian": ("ada", ()),
    "reader": ("rita", ()),
    "outsider": ("omar", ()),
    "admin": ("root", ("admin",)),
}
CASES = [(who, route, status) for who, row in MATRIX.items() for route, status in row.items()]


def test_the_matrix_has_a_cell_for_every_route_and_caller() -> None:
    assert {tuple(sorted(row)) for row in MATRIX.values()} == {tuple(sorted(ROUTES))}, (
        "every caller, every route"
    )


@pytest.mark.parametrize(("who", "route", "status"), CASES, ids=[f"{w}: {r}" for w, r, _ in CASES])
async def test_each_route_asks_for_its_action(scene, who, route, status) -> None:
    method, path, options = ROUTES[route](scene)
    sub, roles = WHO[who]
    headers = scene.headers(
        sub, *roles, **({"If-Match": options["etag"]} if "etag" in options else {})
    )
    response = await scene.http.request(method, path, headers=headers, json=options.get("json"))
    assert response.status_code == status, f"{who} on '{route}': {response.text}"


async def test_a_prohibition_beats_a_role(scene) -> None:
    grants = GrantSet(
        grants=[Grant(assignee=principal_of("ada"), target=scene.tenant_iri, role="librarian")],
        prohibitions=[
            Prohibition(
                assignee=principal_of("ada"),
                target=str(graph_iri(scene.book_iri)),
                action=Action.MODIFY,
            )
        ],
    )
    response = await scene.http.put(
        f"{scene.tenant}/grants",
        content=grants.model_dump_json(exclude_none=True),
        headers=scene.headers("ada", **{"If-Match": scene.access_etag, "Content-Type": JSON}),
    )
    assert response.status_code == 200, response.text
    refused = await scene.http.put(
        scene.book, json=BOOK, headers=scene.headers("ada", **{"If-Match": scene.book_etag})
    )
    assert refused.status_code == 403, "the librarian is prohibited from modifying"


# --- the three representations of one book describe the same triples --------------------------------


async def test_the_three_representations_of_a_book_are_the_same_triples(scene) -> None:
    context = scene.service.kit.documents.context

    def triples(response: httpx.Response, media_type: str) -> Graph:
        if media_type == TURTLE:
            return Graph().parse(data=response.text, format="turtle")
        body = {
            "@context": context,
            **{k: v for k, v in response.json().items() if k != "@context"},
        }
        return Graph().parse(
            data=jsonld.to_rdf(body, {"format": "application/n-quads"}), format="nt"
        )

    graphs = {}
    for media_type in (JSON, JSON_LD, TURTLE):
        response = await scene.http.get(scene.book, headers=scene.headers("ada", Accept=media_type))
        graphs[media_type] = triples(response, media_type)
    for media_type in (JSON_LD, TURTLE):
        assert isomorphic(graphs[JSON], graphs[media_type]), (
            f"JSON and {media_type} differ: {sorted(graph_diff(graphs[JSON], graphs[media_type])[1])}"
        )

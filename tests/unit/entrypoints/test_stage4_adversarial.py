"""Stage 4 of mwb2-adoption-fixes, attacked at the route: what a read says the caller may do (PD-10)."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from rdf_persistence import GrantSet, Page, TenantSummary
from rdf_persistence.domain.exceptions import StoreUnavailable
from rdf_persistence.domain.generated.rp_access import Action, Grant, Prohibition
from rdf_persistence.domain.iris import graph_iri
from rdf_persistence.domain.media import JSON, JSON_LD, TURTLE
from rdf_persistence.entrypoints.negotiation import ALLOWED_ACTIONS, RECORD_ETAG
from rdf_persistence.services.access import ACTIONS
from tests.toy_service import DUNE_BODY, principal_of
from tests.unit.entrypoints.scene import Scene
from tests.unit.entrypoints.test_router import _everyone_has_a_role

ROOT_BODY = {"label": "Ghent", "description": "d", "city": "c"}
# who -> (subject, global roles); mia is the member [read, modify, delete] of _everyone_has_a_role
WHO: dict[str, tuple[str, tuple[str, ...]]] = {
    "ada": ("ada", ()),
    "mia": ("mia", ()),
    "rita": ("rita", ()),
    "admin": ("root", ("admin",)),
}
ALL = [a.value for a in ACTIONS]
# annotate has no route to probe: a comment is posted through the discussion service, not the API
ROUTED = [a for a in ALL if a != Action.ANNOTATE.value]


def _as(scene: Scene, who: str, **extra: str) -> dict[str, str]:
    subject, roles = WHO[who]
    return scene.headers(subject, *roles, **extra)


async def _listed(response: httpx.Response) -> list[str]:
    assert response.status_code == 200, response.text
    header = response.headers.get(ALLOWED_ACTIONS)
    assert header is not None, "a successful read carries the header"
    return [part.strip() for part in header.split(",") if part.strip()]


async def _fresh_access_etag(scene: Scene) -> str:
    """The access record's version, from the root read (the grants route needs administer)."""
    root = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    return root.headers[RECORD_ETAG]


async def _probe(scene: Scene, who: str, target: str, action: str) -> int:
    """Try ``action`` for real; on the tenant, delete means deleting a book (the tenant needs administer)."""
    h = _as(scene, who)
    if action == "read":
        return (await scene.http.get(target, headers=h)).status_code
    if action == "modify":
        if target == scene.book:
            etag, body = scene.book_etag, DUNE_BODY
        else:
            etag, body = scene.root_etag, ROOT_BODY
        h = _as(scene, who, **{"If-Match": etag})
        return (await scene.http.put(target, json=body, headers=h)).status_code
    if action == "delete":
        h = _as(scene, who, **{"If-Match": scene.book_etag})
        return (await scene.http.delete(scene.book, headers=h)).status_code
    h = _as(scene, who, **{"If-Match": await _fresh_access_etag(scene)})
    return (await scene.http.put(f"{scene.tenant}/grants", json={}, headers=h)).status_code


def _ban(
    who: str, target: Callable[[Scene], str], action: Action
) -> Callable[[Scene], Prohibition]:
    return lambda s: Prohibition(assignee=principal_of(who), target=target(s), action=action)


def _tenant(s: Scene) -> str:
    return s.tenant_iri


def _book(s: Scene) -> str:
    return str(graph_iri(s.book_iri))


NO_BAN: list[Callable[[Scene], Prohibition]] = []
CASES: dict[str, tuple[str, list[Callable[[Scene], Prohibition]]]] = {
    "ada": ("ada", NO_BAN),
    "mia": ("mia", NO_BAN),
    "rita": ("rita", NO_BAN),
    "admin": ("admin", NO_BAN),
    "mia-no-modify-tenant": ("mia", [_ban("mia", _tenant, Action.MODIFY)]),
    "mia-no-modify-book": ("mia", [_ban("mia", _book, Action.MODIFY)]),
    "mia-no-delete-book": ("mia", [_ban("mia", _book, Action.DELETE)]),
    "ada-no-administer": ("ada", [_ban("ada", _tenant, Action.ADMINISTER)]),
    "ada-no-delete-tenant": ("ada", [_ban("ada", _tenant, Action.DELETE)]),
}


async def _set_up(scene: Scene, case: str) -> str:
    who, bans = CASES[case]
    await _everyone_has_a_role(scene, *(ban(scene) for ban in bans))
    return who


@pytest.mark.parametrize("action", ROUTED)
@pytest.mark.parametrize("case", list(CASES))
@pytest.mark.parametrize("on", ["book", "tenant"])
async def test_a_listed_action_is_allowed_and_an_unlisted_one_is_refused(
    scene, case, on, action
) -> None:
    who = await _set_up(scene, case)
    target = scene.book if on == "book" else scene.tenant
    if (on, action) in {("tenant", "delete"), ("book", "administer")}:
        pytest.skip("R4-1: tenant delete is the test below; no aggregate route needs administer")
    listed = await _listed(await scene.http.get(target, headers=_as(scene, who)))
    status = await _probe(scene, who, target, action)
    expected_ok = action in listed
    assert (status < 300) == expected_ok, (
        f"{case} on {on}: header {listed}; {action} answered {status}"
    )


@pytest.mark.parametrize("who", ["ada", "mia", "rita", "admin"])
async def test_deleting_the_tenant_is_allowed_exactly_when_the_tenant_read_lists_delete(
    scene, who
) -> None:
    await _everyone_has_a_role(scene)
    listed = await _listed(await scene.http.get(scene.tenant, headers=_as(scene, who)))
    etag = await _fresh_access_etag(scene)
    refused = await scene.http.delete(scene.tenant, headers=_as(scene, who, **{"If-Match": etag}))
    assert ("delete" in listed) == (refused.status_code == 204), (
        f"{who}: tenant read lists {listed} but DELETE of the tenant answered {refused.status_code}"
    )


async def test_the_actions_come_in_the_documented_order(scene) -> None:
    await _everyone_has_a_role(scene)
    listed = await _listed(await scene.http.get(scene.tenant, headers=_as(scene, "ada")))
    assert listed == ROUTED, (
        "read, modify, delete, administer; the librarian role names no annotate"
    )


async def test_the_header_never_repeats_or_invents_an_action(scene) -> None:
    await _everyone_has_a_role(scene)
    for who in WHO:
        listed = await _listed(await scene.http.get(scene.tenant, headers=_as(scene, who)))
        assert len(set(listed)) == len(listed), f"{who}: no repeat in {listed}"
        assert set(listed) <= set(ALL), f"{who}: only known actions in {listed}"


async def test_a_direct_modify_grant_lists_read_and_modify_and_both_work(scene) -> None:
    grants = GrantSet(
        grants=[
            Grant(assignee=principal_of("ada"), target=scene.tenant_iri, role="librarian"),
            Grant(assignee=principal_of("mia"), target=scene.tenant_iri, action=Action.MODIFY),
        ]
    )
    await scene.set_grants(grants)
    listed = await _listed(await scene.http.get(scene.tenant, headers=_as(scene, "mia")))
    assert listed == ["read", "modify"], "modify implies read"
    assert await _probe(scene, "mia", scene.tenant, "modify") == 200, "modify works"
    assert await _probe(scene, "mia", scene.tenant, "read") == 200, "read works"


async def test_a_grant_on_one_book_only_shows_the_book_and_hides_the_tenant(scene) -> None:
    grants = GrantSet(
        grants=[
            Grant(assignee=principal_of("ada"), target=scene.tenant_iri, role="librarian"),
            Grant(assignee=principal_of("mia"), target=_book(scene), action=Action.MODIFY),
        ]
    )
    await scene.set_grants(grants)
    book = await scene.http.get(scene.book, headers=_as(scene, "mia"))
    assert await _listed(book) == ["read", "modify"], "the book read lists the aggregate grant"
    tenant = await scene.http.get(scene.tenant, headers=_as(scene, "mia"))
    assert tenant.status_code == 404, "the tenant read is refused"
    assert ALLOWED_ACTIONS not in tenant.headers, "and carries no header"
    listing = Page.model_validate(
        (await scene.http.get("/libraries", headers=_as(scene, "mia"))).json()
    )
    assert listing.items == [], "the listing agrees with the tenant read: nothing"


async def test_a_prohibition_aimed_at_another_book_leaves_this_book_alone(scene) -> None:
    other = await scene.http.post(
        f"{scene.tenant}/books", json=DUNE_BODY, headers=scene.headers("ada")
    )
    other_graph = str(graph_iri(other.json()["id"]))
    await _everyone_has_a_role(
        scene, Prohibition(assignee=principal_of("mia"), target=other_graph, action=Action.MODIFY)
    )
    mine = await scene.http.get(scene.book, headers=_as(scene, "mia"))
    assert await _listed(mine) == ["read", "modify", "delete"], "this book is unaffected"
    theirs = await scene.http.get(other.headers["location"], headers=_as(scene, "mia"))
    assert await _listed(theirs) == ["read", "delete"], "the other book lost modify"
    assert await _probe(scene, "mia", scene.book, "modify") == 200, "and modify works on this one"


async def test_a_prohibition_of_read_on_the_tenant_refuses_the_read_and_the_listing_hides_it(
    scene,
) -> None:
    await _everyone_has_a_role(scene, _ban("mia", _tenant, Action.READ)(scene))
    refused = await scene.http.get(scene.tenant, headers=_as(scene, "mia"))
    assert refused.status_code == 403, "refused"
    assert ALLOWED_ACTIONS not in refused.headers, "no header on a refusal"
    page = Page.model_validate(
        (await scene.http.get("/libraries", headers=_as(scene, "mia"))).json()
    )
    assert page.items == [], "hidden from the listing"


async def _summary(scene: Scene, who: str, accept: str) -> tuple[TenantSummary, Any]:
    response = await scene.http.get("/libraries", headers=_as(scene, who, Accept=accept))
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    "case", ["ada", "mia", "rita", "admin", "mia-no-modify-tenant", "ada-no-administer"]
)
async def test_the_listing_item_equals_the_tenant_read_header(scene, case) -> None:
    who = await _set_up(scene, case)
    header = await _listed(await scene.http.get(scene.tenant, headers=_as(scene, who)))
    page = Page.model_validate((await scene.http.get("/libraries", headers=_as(scene, who))).json())
    [item] = [TenantSummary.model_validate(i) for i in page.items]
    assert [str(a) for a in item.allowed_actions or []] == header, f"{case}: same list"
    assert [str(a) for a in item.allowed_actions or []] == [a for a in ALL if a in header], (
        f"{case}: documented order"
    )


async def test_the_tenant_listing_answers_the_same_items_whatever_the_accept(scene) -> None:
    await _everyone_has_a_role(scene)
    bodies = []
    for accept in (JSON, JSON_LD):
        response = await scene.http.get("/libraries", headers=_as(scene, "mia", Accept=accept))
        assert response.status_code == 200, response.text
        bodies.append(response.json())
    assert bodies[0] == bodies[1], "the listing has one representation, with allowed_actions in it"
    assert bodies[0]["items"][0]["allowed_actions"] == ["read", "modify"], "mia"


async def test_a_tenant_being_deleted_is_gone_from_the_listing_and_the_read(
    service, client
) -> None:
    scene = await Scene.set_up(service, client)
    service.store.on("drop_dataset", StoreUnavailable("down"))
    etag = await _fresh_access_etag(scene)
    stuck = await client.delete(scene.tenant, headers=scene.headers("ada", **{"If-Match": etag}))
    assert stuck.status_code == 503, stuck.text
    read = await client.get(scene.tenant, headers=scene.headers("ada"))
    assert (read.status_code, ALLOWED_ACTIONS in read.headers) == (404, False), "deleting is gone"
    page = Page.model_validate(
        (await client.get("/libraries", headers=scene.headers("ada"))).json()
    )
    assert page.items == [], "and out of the listing"


@pytest.mark.parametrize("accept", [JSON, JSON_LD, TURTLE])
@pytest.mark.parametrize("on", ["book", "tenant"])
async def test_every_representation_of_a_read_carries_the_header(scene, accept, on) -> None:
    await _everyone_has_a_role(scene)
    target = scene.book if on == "book" else scene.tenant
    response = await scene.http.get(target, headers=_as(scene, "mia", Accept=accept))
    assert response.status_code == 200, response.text
    expected = "read, modify, delete" if on == "book" else "read, modify"
    assert response.headers.get(ALLOWED_ACTIONS) == expected, f"{on} as {accept}"


@pytest.mark.parametrize("on", ["book", "tenant"])
async def test_a_conditional_read_keeps_the_header_if_the_service_answers_304(scene, on) -> None:
    target = scene.book if on == "book" else scene.tenant
    etag = scene.book_etag if on == "book" else scene.root_etag
    response = await scene.http.get(target, headers=_as(scene, "ada", **{"If-None-Match": etag}))
    if response.status_code == 304:
        assert ALLOWED_ACTIONS in response.headers, "a 304 is still a read"
    else:
        assert response.status_code == 200, "conditional reads are not supported: plain 200"
        assert ALLOWED_ACTIONS in response.headers, "the full read carries it"


@pytest.mark.parametrize("on", ["book", "tenant"])
async def test_head_is_not_routed_so_it_cannot_leak_a_header(scene, on) -> None:
    target = scene.book if on == "book" else scene.tenant
    response = await scene.http.head(target, headers=_as(scene, "ada"))
    assert response.status_code == 405, "HEAD is not routed"
    assert ALLOWED_ACTIONS not in response.headers, "no header on the 405"


@pytest.mark.parametrize("on", ["book", "tenant"])
@pytest.mark.parametrize(
    ("who", "accept", "status"),
    [
        ("omar", JSON, 404),
        ("rita", "text/yaml", 406),
        ("nobody", JSON, 401),
    ],
)
async def test_error_responses_carry_no_header(scene, on, who, accept, status) -> None:
    target = scene.book if on == "book" else scene.tenant
    headers = {"Accept": accept} if who == "nobody" else scene.headers(who, Accept=accept)
    response = await scene.http.get(target, headers=headers)
    assert response.status_code == status, response.text
    assert ALLOWED_ACTIONS not in response.headers, f"{status} carries no header"


async def test_a_missing_book_and_a_foreign_book_carry_no_header(scene) -> None:
    gone = await scene.http.get(
        f"{scene.tenant}/books/00000000-0000-4000-8000-000000000000", headers=_as(scene, "ada")
    )
    assert gone.status_code == 404, "no such book"
    assert ALLOWED_ACTIONS not in gone.headers, "no header on a 404"


async def test_write_responses_and_the_book_listing_carry_no_header(scene) -> None:
    put = await scene.http.put(
        scene.book, json=DUNE_BODY, headers=_as(scene, "ada", **{"If-Match": scene.book_etag})
    )
    assert put.status_code == 200, put.text
    assert ALLOWED_ACTIONS not in put.headers, "a PUT is not a read"
    listing = await scene.http.get(f"{scene.tenant}/books", headers=_as(scene, "ada"))
    assert ALLOWED_ACTIONS not in listing.headers, "a collection listing is not a read of one"
    grants = await scene.http.get(f"{scene.tenant}/grants", headers=_as(scene, "ada"))
    assert ALLOWED_ACTIONS not in grants.headers, "nor are the grants"


async def test_create_and_rename_leave_allowed_actions_out_of_the_json(service, client) -> None:
    from tests.toy_service import TENANT_BODY

    made = await client.post("/libraries", json=TENANT_BODY, headers=service.bearer("ada"))
    assert "allowed_actions" not in made.json(), "create omits the slot instead of sending null"
    assert ALLOWED_ACTIONS not in made.headers, "no header on create"
    scene = await Scene.set_up(service, client)
    renamed = await client.put(
        f"{scene.tenant}/label",
        json={"label": "Bruges"},
        headers=scene.headers("ada", **{"If-Match": scene.access_etag}),
    )
    assert renamed.status_code == 200, renamed.text
    assert "allowed_actions" not in renamed.json(), "rename omits the slot too"


def test_the_header_is_documented_on_exactly_the_two_reads(service) -> None:
    document = service.app.openapi()
    found = {
        (path, method, status)
        for path, item in document["paths"].items()
        for method, operation in item.items()
        for status, response in operation["responses"].items()
        if ALLOWED_ACTIONS in (response.get("headers") or {})
    }
    assert found == {
        ("/libraries/{t}", "get", "200"),
        ("/libraries/{t}/books/{aggregate_id}", "get", "200"),
        ("/libraries/{t}/scans/{aggregate_id}", "get", "200"),
        ("/libraries/{t}/shelves/{aggregate_id}", "get", "200"),
    }, f"documented on {sorted(found)}"


def test_tenant_summary_documents_allowed_actions_as_the_action_enum(service) -> None:
    schemas = service.app.openapi()["components"]["schemas"]
    slot = schemas["TenantSummary"]["properties"]["allowed_actions"]
    assert slot["items"] == {"$ref": "#/components/schemas/Action"}, slot
    assert slot["type"] == "array", "a list"
    assert "allowed_actions" not in schemas["TenantSummary"].get("required", []), "optional"
    assert schemas["Action"]["enum"] == ["read", "modify", "delete", "administer", "annotate"], (
        "the five, annotate last (PD-9)"
    )
    # the pages document their items as TenantSummary on the tenant listing
    assert "Action" in schemas, "the enum is a component"

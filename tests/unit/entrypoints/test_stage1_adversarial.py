"""Stage 1 of mwb2-adoption-fixes, attacked through the routes: rename, root PUT, Record-ETag, tenant delete, id_source."""

import uuid

import pytest

from rdf_persistence import GrantSet
from rdf_persistence.domain.generated.rp_access import Action, Grant, RoleDefinition, RoleLevel
from rdf_persistence.domain.media import JSON, TURTLE
from rdf_persistence.entrypoints.negotiation import RECORD_ETAG
from rdf_persistence.services.access import AccessRules, load_role_definitions
from tests.toy import ROLES
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, principal_of
from tests.unit.entrypoints.test_router import _put_root, _rename

ROOT = {"description": "Books for all.", "city": "Ghent"}


async def test_a_rename_without_if_match_is_428_and_writes_nothing(scene) -> None:
    response = await scene.http.put(
        f"{scene.tenant}/label", json={"label": "B"}, headers=scene.headers("ada")
    )
    assert response.status_code == 428, "a rename needs If-Match"
    root = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert root.json()["label"] == "Ghent", "the root is untouched"


async def test_a_rename_of_an_unknown_tenant_is_404_and_creates_nothing(scene) -> None:
    before = await scene.service.store.list_datasets()
    response = await scene.http.put(
        f"{scene.tenant}x/label",
        json={"label": "B"},
        headers=scene.headers("ada", **{"If-Match": scene.access_etag}),
    )
    assert response.status_code in (403, 404), "an unknown tenant is refused, not made"
    assert await scene.service.store.list_datasets() == before, "no database was created"


@pytest.mark.parametrize("label", ["", "   "])
async def test_an_invalid_label_is_422_and_the_root_keeps_its_label(scene, label) -> None:
    response = await _rename(scene, label, scene.access_etag)
    assert response.status_code == 422, response.text
    root = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert root.json()["label"] == "Ghent", "the root keeps its label"


async def test_a_root_put_with_no_label_is_refused(scene) -> None:
    response = await scene.http.put(
        scene.tenant, json=ROOT, headers=scene.headers("ada", **{"If-Match": scene.root_etag})
    )
    assert response.status_code == 422, response.text


async def test_a_root_put_with_two_labels_is_refused(scene) -> None:
    response = await scene.http.put(
        scene.tenant,
        json={**ROOT, "label": ["Ghent", "Gent"]},
        headers=scene.headers("ada", **{"If-Match": scene.root_etag}),
    )
    assert response.status_code == 422, response.text
    root = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert root.json()["label"] == "Ghent", "the root keeps its label"


async def test_a_root_put_with_a_stale_if_match_conflicts_even_with_the_right_label(scene) -> None:
    first = await _put_root(scene, "Ghent", scene.root_etag)
    assert first.status_code == 200, "the first PUT is fresh"
    stale = await _put_root(scene, "Ghent", scene.root_etag)
    assert stale.status_code == 409, "the second PUT used a spent ETag"


async def test_a_root_put_with_a_wrong_label_and_a_stale_if_match_is_refused_without_a_write(
    scene,
) -> None:
    assert (await _put_root(scene, "Ghent", scene.root_etag)).status_code == 200, (
        "the first PUT is fresh"
    )
    refused = await _put_root(scene, "Other", scene.root_etag)
    assert refused.status_code in (409, 422), "the second PUT is refused"
    root = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert root.json()["label"] == "Ghent", "the root keeps its label"


async def test_a_book_may_keep_a_label_unlike_its_tenants(scene) -> None:
    book = await scene.http.get(scene.book, headers=scene.headers("ada"))
    changed = {**DUNE_BODY, "id": book.json()["id"], "label": "Dune Messiah"}
    for key in ("chapters",):
        changed[key] = book.json()[key]
    response = await scene.http.put(
        scene.book, json=changed, headers=scene.headers("ada", **{"If-Match": scene.book_etag})
    )
    assert response.status_code == 200, "the label rule is the tenant root's only"


async def test_a_root_put_in_another_tenant_checks_that_tenants_record(scene) -> None:
    other = await scene.http.post("/libraries", json=TENANT_BODY, headers=scene.headers("ada"))
    other_root = await scene.http.get(other.headers["location"], headers=scene.headers("ada"))
    renamed = await scene.http.put(
        f"{other.headers['location']}/label",
        json={"label": "Bruges"},
        headers=scene.headers(
            "ada",
            **{
                "If-Match": (
                    await scene.http.get(
                        f"{other.headers['location']}/grants", headers=scene.headers("ada")
                    )
                ).headers["etag"]
            },
        ),
    )
    assert renamed.status_code == 200, "the other tenant was renamed"
    # the first tenant still wants "Ghent": the other's rename must not leak across tenants
    assert (await _put_root(scene, "Ghent", scene.root_etag)).status_code == 200, (
        "the other tenant's rename did not reach this one"
    )
    assert other_root.status_code == 200, "the other tenant still reads"


# --- Record-ETag --------------------------------------------------------------------------------


async def test_the_record_etag_moves_when_the_grants_are_replaced(scene) -> None:
    before = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    grants = GrantSet.model_validate(
        (await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))).json()
    )
    extra = Grant(assignee=principal_of("zoe"), target=scene.tenant_iri, role="reader")
    put = await scene.http.put(
        f"{scene.tenant}/grants",
        content=GrantSet(grants=[*(grants.grants or []), extra]).model_dump_json(exclude_none=True),
        headers=scene.headers("ada", **{"If-Match": scene.access_etag, "Content-Type": JSON}),
    )
    after = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert put.status_code == 200, "the grants were replaced"
    assert after.headers[RECORD_ETAG] == put.headers["etag"], (
        "the root read shows the grants' new version"
    )
    assert after.headers[RECORD_ETAG] != before.headers[RECORD_ETAG], "the record version moved"
    assert after.headers["etag"] == before.headers["etag"], "the root's own ETag did not move"


async def test_the_record_etag_moves_after_a_rename(scene) -> None:
    before = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    renamed = await _rename(scene, "B", before.headers[RECORD_ETAG])
    after = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert after.headers[RECORD_ETAG] == renamed.headers["etag"], (
        "the root read shows the rename's version"
    )
    assert after.headers[RECORD_ETAG] != before.headers[RECORD_ETAG], "the record version moved"


@pytest.mark.parametrize("who", ["omar"])
async def test_a_refused_root_read_carries_no_record_etag(scene, who) -> None:
    response = await scene.http.get(scene.tenant, headers=scene.headers(who))
    assert response.status_code in (403, 404), "the read is refused"
    assert RECORD_ETAG not in response.headers, "a refused read leaks no record version"


async def test_an_unknown_tenant_read_carries_no_record_etag(scene) -> None:
    response = await scene.http.get(f"{scene.tenant}x", headers=scene.headers("ada"))
    assert response.status_code in (403, 404), "the read is refused"
    assert RECORD_ETAG not in response.headers, "a refused read leaks no record version"


async def test_a_prohibited_read_carries_no_record_etag(scene) -> None:
    grants = GrantSet(
        grants=[Grant(assignee=principal_of("ada"), target=scene.tenant_iri, role="librarian")],
        prohibitions=[
            {"assignee": principal_of("ada"), "target": scene.tenant_iri, "action": Action.READ}
        ],
    )
    put = await scene.http.put(
        f"{scene.tenant}/grants",
        content=grants.model_dump_json(exclude_none=True),
        headers=scene.headers("ada", **{"If-Match": scene.access_etag, "Content-Type": JSON}),
    )
    assert put.status_code == 200, put.text
    response = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert response.status_code in (403, 404), "the read is refused"
    assert RECORD_ETAG not in response.headers, "a refused read leaks no record version"


async def test_a_conditional_get_still_carries_the_record_etag(scene) -> None:
    first = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    again = await scene.http.get(
        scene.tenant, headers=scene.headers("ada", **{"If-None-Match": first.headers["etag"]})
    )
    if again.status_code == 304:
        assert RECORD_ETAG in again.headers, "a 304 carries the header too"
    else:
        assert again.headers[RECORD_ETAG] == first.headers[RECORD_ETAG], (
            "the record version is the same as on the first read"
        )


async def test_a_turtle_root_read_carries_the_record_etag(scene) -> None:
    response = await scene.http.get(scene.tenant, headers=scene.headers("ada", Accept=TURTLE))
    assert response.status_code == 200, "the Turtle read succeeds"
    assert RECORD_ETAG in response.headers, "Turtle carries it too"


def test_the_openapi_documents_the_record_etag_on_the_root_read_only(service) -> None:
    spec = service.app.openapi()
    paths = {p: item for p, item in spec["paths"].items() if "libraries" in p}
    root = paths["/libraries/{t}"]["get"]["responses"]["200"]["headers"]
    assert RECORD_ETAG in root, "the root read documents the header"
    for path, item in paths.items():
        for method, op in item.items():
            if (path, method) == ("/libraries/{t}", "get"):
                continue
            ok = op.get("responses", {}).get("200", {}).get("headers", {})
            assert RECORD_ETAG not in ok, f"{method.upper()} {path}"


# --- tenant delete by a system role ---------------------------------------------------------------


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


# --- id_source ------------------------------------------------------------------------------------


async def test_a_tenant_id_that_clashes_many_times_is_redrawn_until_a_fresh_one() -> None:
    first, fresh = str(uuid.uuid4()), str(uuid.uuid4())
    draws = iter([first] * 5 + [fresh])  # one for the first create, four clashes, then fresh
    toy = ToyService(id_source=lambda _spec: next(draws))
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        one = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
        two = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
    assert (one.status_code, two.status_code) == (201, 201), two.text
    assert two.headers["location"].endswith(f"/{fresh}"), "the clash was redrawn"


async def test_a_tenant_id_source_that_only_clashes_ends_in_a_problem_not_a_hang() -> None:
    # MAX_TENANT_CLASH_DRAWS (5) draws all clash: the service gives up with a 5xx, never loops
    same = str(uuid.uuid4())
    toy = ToyService(id_source=lambda _spec: same)
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        one = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
        two = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
        again = await http.get(one.headers["location"], headers=toy.bearer("ada"))
    assert one.status_code == 201, "the first create succeeded"
    assert two.status_code >= 400, "a second tenant cannot take the first one's id"
    assert again.status_code == 200, "and the first is unharmed"


async def test_an_aggregate_id_that_clashes_with_a_stored_one_is_not_a_server_error() -> None:
    """Shows today: only tenant ids are redrawn (PD-5); a second book given the first's id is a 5xx."""
    drawn: list[str] = []
    replay: list[str] = []

    def source(_spec) -> str:
        value = replay.pop(0) if replay else str(uuid.uuid4())
        drawn.append(value)
        return value

    toy = ToyService(id_source=source)
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        headers = toy.bearer("ada")
        made = await http.post("/libraries", json=TENANT_BODY, headers=headers)
        tenant = made.headers["location"]
        mark = len(drawn)
        one = await http.post(f"{tenant}/books", json=DUNE_BODY, headers=headers)
        replay.extend(drawn[mark : mark + 1])  # the second book's first draw is the first book's id
        two = await http.post(f"{tenant}/books", json=DUNE_BODY, headers=headers)
        again = await http.get(one.headers["location"], headers=headers)
    assert one.status_code == 201, "the first create succeeded"
    assert two.status_code < 500, f"a clashing aggregate id gave {two.status_code}: {two.text}"
    assert again.status_code == 200, "and the first book is unharmed"

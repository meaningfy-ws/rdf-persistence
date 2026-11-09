"""The generic router over the fakes: tenant routes, aggregate routes, and who may do what (tasks 5.2, 5.3, PD-9, PD-13)."""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from pyld import jsonld
from rdflib import Graph
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence import Forbidden, GrantSet, InvalidBody, Page, TenantSummary
from rdf_persistence.domain.generated.rp_access import (
    Action,
    Grant,
    Prohibition,
    RoleDefinition,
    RoleLevel,
)
from rdf_persistence.domain.iris import graph_iri
from rdf_persistence.domain.media import JSON, JSON_LD, TURTLE
from rdf_persistence.entrypoints.negotiation import ALLOWED_ACTIONS, RECORD_ETAG
from rdf_persistence.services import vocabulary
from rdf_persistence.services.access import AccessRules, load_role_definitions
from tests.toy import ROLES, SETTINGS, keep_a_librarian
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, principal_of
from tests.unit.entrypoints.scene import NIL, PROBLEMS, Scene, problem_of

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


async def test_a_tenant_root_with_another_label_is_a_422_and_creates_nothing(
    service, client
) -> None:
    before = await service.store.list_datasets()
    response = await client.post(
        "/libraries",
        json={"label": "Ghent", "root": {"description": "d", "label": "Bruges"}},
        headers=service.bearer("ada"),
    )
    assert (response.status_code, problem_of(response).type) == (
        422,
        f"{PROBLEMS}invalid-body",
    ), response.text
    assert await service.store.list_datasets() == before, "nothing was created"


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
            Prohibition(
                assignee=principal_of("ada"), target=scene.tenant_iri, action=Action.ADMINISTER
            )
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
    assert refused.status_code == 403, "the new prohibition forbids deleting the tenant"


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


async def _ada_is_prohibited(scene: Scene, action: Action) -> str:
    """Replace the grants: ada stays a librarian, barred from ``action`` on the tenant; the new ETag."""
    grants = GrantSet(
        grants=[Grant(assignee=principal_of("ada"), target=scene.tenant_iri, role="librarian")],
        prohibitions=[
            Prohibition(assignee=principal_of("ada"), target=scene.tenant_iri, action=action)
        ],
    )
    return await scene.set_grants(grants)


async def _ada_and_mia_are_members(scene: Scene) -> str:
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


async def test_a_member_may_delete_a_book_but_not_the_tenant(scene) -> None:  # T-2
    etag = await _ada_and_mia_are_members(scene)
    refused = await scene.http.delete(
        scene.tenant, headers=scene.headers("mia", **{"If-Match": etag})
    )
    assert refused.status_code == 403, "delete alone does not delete the tenant"
    datasets = await scene.service.store.list_datasets()
    assert [d for d in datasets if d.startswith("lib-t-")] != [], "the dataset is still there"
    assert len(await scene.service.files.list_buckets("lib-t-")) == 1, "so is the bucket"
    book = await scene.http.delete(
        scene.book, headers=scene.headers("mia", **{"If-Match": scene.book_etag})
    )
    assert book.status_code == 204, "but a member deletes a book"
    gone = await scene.http.get(scene.book, headers=scene.headers("ada"))
    assert gone.status_code == 404, "the book is gone"
    kept = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert kept.status_code == 200, "and the tenant still reads"


async def test_a_prohibition_of_administer_keeps_the_tenant(scene) -> None:  # T-3
    etag = await _ada_is_prohibited(scene, Action.ADMINISTER)
    refused = await scene.http.delete(
        scene.tenant, headers=scene.headers("ada", **{"If-Match": etag})
    )
    assert refused.status_code == 403, "administer is what deleting the tenant needs"


async def test_a_prohibition_of_delete_leaves_the_tenant_deletable(scene) -> None:  # T-5
    etag = await _ada_is_prohibited(scene, Action.DELETE)
    book = await scene.http.delete(
        scene.book, headers=scene.headers("ada", **{"If-Match": scene.book_etag})
    )
    deleted = await scene.http.delete(
        scene.tenant, headers=scene.headers("ada", **{"If-Match": etag})
    )
    assert (book.status_code, deleted.status_code) == (403, 204), "delete guards books, not tenant"


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


async def _rename(scene: Scene, label: str, etag: str) -> httpx.Response:
    return await scene.http.put(
        f"{scene.tenant}/label",
        json={"label": label},
        headers=scene.headers("ada", **{"If-Match": etag}),
    )


async def _put_root(scene: Scene, label: str, etag: str) -> httpx.Response:
    body = {"label": label, "description": "Books for all.", "city": "Ghent"}
    return await scene.http.put(
        scene.tenant, json=body, headers=scene.headers("ada", **{"If-Match": etag})
    )


async def test_a_tenant_has_one_label_whichever_route_changes_it(scene) -> None:  # T-10
    renamed = await _rename(scene, "B", scene.access_etag)
    assert renamed.status_code == 200, renamed.text
    root = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert root.json()["label"] == "B", "the rename reached the root"
    refused = await _put_root(scene, "C", root.headers["etag"])
    assert (refused.status_code, problem_of(refused).type) == (422, f"{PROBLEMS}invalid-body"), (
        "the body repeats a label the record does not have"
    )
    assert "label route" in (problem_of(refused).detail or ""), "it names the label route"
    unchanged = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert unchanged.json()["label"] == "B", "the refused PUT wrote nothing"
    same = await _put_root(scene, "B", root.headers["etag"])
    assert same.status_code == 200, "a root PUT that keeps the record's label is fine"
    stale = await _rename(scene, "D", scene.access_etag)
    assert stale.status_code == 409, "the old record version is stale"
    after = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert after.json()["label"] == "B", "the stale rename left the root"


async def test_a_drifted_root_label_is_refused_until_a_rename_repairs_it(scene) -> None:  # T-11
    label = vocabulary.predicate("label")
    await scene.service.store.update(
        scene.service.kit.iris.resource_name(scene.tenant_iri),
        f"DELETE {{ GRAPH ?g {{ <{scene.tenant_iri}> <{label}> ?o }} }} "
        f'INSERT {{ GRAPH ?g {{ <{scene.tenant_iri}> <{label}> "Drifted" }} }} '
        f"WHERE {{ GRAPH ?g {{ <{scene.tenant_iri}> <{label}> ?o }} }}",
    )
    root = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert root.json()["label"] == "Drifted", "the root drifted from the record"
    refused = await _put_root(scene, "Drifted", root.headers["etag"])
    assert refused.status_code == 422, "the body repeats a label the record does not have"
    assert (await _rename(scene, "Ghent", scene.access_etag)).status_code == 200, (
        "the rename was accepted"
    )
    repaired = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert repaired.json()["label"] == "Ghent", "a rename repairs the root"
    assert (await _put_root(scene, "Ghent", repaired.headers["etag"])).status_code == 200, (
        "the root PUT with the record's label is accepted"
    )


async def test_the_root_read_carries_the_version_a_modifier_renames_with(scene) -> None:  # T-18
    await _ada_and_mia_are_members(scene)
    root = await scene.http.get(scene.tenant, headers=scene.headers("mia"))
    record_etag = root.headers[RECORD_ETAG]
    stale = await scene.http.put(
        f"{scene.tenant}/label",
        json={"label": "Bruges"},
        headers=scene.headers("mia", **{"If-Match": scene.access_etag}),
    )
    assert stale.status_code == 409, "the version from before the grants moved is stale"
    renamed = await scene.http.put(
        f"{scene.tenant}/label",
        json={"label": "Bruges"},
        headers=scene.headers("mia", **{"If-Match": record_etag}),
    )
    assert renamed.status_code == 200, renamed.text


async def test_the_record_etag_of_the_root_equals_the_etag_of_the_grants(scene) -> None:  # T-19
    root = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    grants = await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))
    assert root.headers[RECORD_ETAG] == grants.headers["etag"], "it is the grants' version"
    assert root.headers[RECORD_ETAG] != root.headers["etag"], "it is not the root's version"


async def test_the_tenant_root_cannot_change_its_id(scene) -> None:
    body = {"id": f"{SETTINGS.base}libraries/{NIL}1", "label": "G", "description": "d", "city": "x"}
    response = await scene.http.put(
        scene.tenant, json=body, headers=scene.headers("ada", **{"If-Match": scene.root_etag})
    )
    assert response.status_code == 422, "the id is the tenant's"


# --- aggregates ---------------------------------------------------------------------------------


async def test_a_created_book_has_a_minted_iri_a_location_and_a_version(scene) -> None:
    response = await scene.http.post(
        f"{scene.tenant}/books", json=DUNE_BODY, headers=scene.headers("ada")
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
    body = {**DUNE_BODY, "id": f"{SETTINGS.base}libraries/{NIL}1/books/{NIL}2"}
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
    changed = {**DUNE_BODY, "label": "Dune Messiah"}
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
        json={**DUNE_BODY, "id": other_id},
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
        missing, json=DUNE_BODY, headers=scene.headers("ada", **{"If-Match": '"x"'})
    )
    assert response.status_code == 404, "a PUT replaces; it does not create (IRIs are minted)"


@pytest.mark.parametrize(
    "body",
    [
        {k: v for k, v in DUNE_BODY.items() if k != "description"},
        {**DUNE_BODY, "colour": "red"},
        {**DUNE_BODY, "genre": "cookery"},
        {**DUNE_BODY, "chapters": [{"number": "one"}]},
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
        f"{scene.tenant}/shelves", json=DUNE_BODY, headers=scene.headers("ada")
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
    assert link == f'<{SETTINGS.base}context.jsonld>; rel="http://www.w3.org/ns/json-ld#context"', (
        "built from the service's base"
    )
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
        f"{scene.tenant}/books", json=DUNE_BODY, headers=scene.headers("ada", Accept="text/html")
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
    "create a book": lambda s: ("POST", f"{s.tenant}/books", {"json": DUNE_BODY}),
    "replace a book": lambda s: ("PUT", s.book, {"json": DUNE_BODY, "etag": s.book_etag}),
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
        {"json": {"label": "Ghent", "description": "d", "city": "c"}, "etag": s.root_etag},
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
        scene.book, json=DUNE_BODY, headers=scene.headers("ada", **{"If-Match": scene.book_etag})
    )
    assert refused.status_code == 403, "the librarian is prohibited from modifying"


# --- reads tell the caller what it may do (PD-10) ---------------------------------------------------


async def _everyone_has_a_role(scene: Scene, *prohibitions: Prohibition) -> None:
    """ada a librarian, mia a member (read, modify, delete), rita a reader; ``prohibitions`` on top."""
    scene.access_etag = await _ada_and_mia_are_members(scene)
    grants = [
        Grant(assignee=principal_of("ada"), target=scene.tenant_iri, role="librarian"),
        Grant(assignee=principal_of("mia"), target=scene.tenant_iri, role="member"),
        Grant(assignee=principal_of("rita"), target=scene.tenant_iri, role="reader"),
    ]
    await scene.set_grants(GrantSet(grants=grants, prohibitions=list(prohibitions) or None))


@pytest.mark.parametrize(
    ("who", "allowed"),
    [
        ("ada", "read, modify, delete, administer"),  # the toy's librarian
        ("mia", "read, modify, delete"),  # the member role built in the test
        ("rita", "read"),  # the toy's reader
    ],
)
async def test_the_tenant_read_lists_what_the_caller_may_do(scene, who, allowed) -> None:  # T-29
    await _everyone_has_a_role(scene)
    response = await scene.http.get(scene.tenant, headers=scene.headers(who))
    assert response.status_code == 200, response.text
    assert response.headers.get(ALLOWED_ACTIONS) == allowed, f"{who} on the tenant"


async def test_the_aggregate_read_lists_what_the_caller_may_do(scene) -> None:  # T-29
    await _everyone_has_a_role(scene)
    response = await scene.http.get(scene.book, headers=scene.headers("mia"))
    assert response.headers.get(ALLOWED_ACTIONS) == "read, modify, delete", "the member on a book"


async def test_a_refused_read_carries_no_allowed_actions(scene) -> None:  # T-30
    book_graph = str(graph_iri(scene.book_iri))
    await _everyone_has_a_role(
        scene,
        Prohibition(assignee=principal_of("rita"), target=book_graph, action=Action.READ),
    )
    refused = await scene.http.get(scene.book, headers=scene.headers("rita"))
    assert refused.status_code == 403, "the reader is refused as before"
    assert ALLOWED_ACTIONS not in refused.headers, "a refusal says nothing of what is allowed"


async def test_a_prohibition_takes_its_action_off_the_list(scene) -> None:  # T-30
    book_graph = str(graph_iri(scene.book_iri))
    await _everyone_has_a_role(
        scene,
        Prohibition(assignee=principal_of("mia"), target=book_graph, action=Action.DELETE),
    )
    book = await scene.http.get(scene.book, headers=scene.headers("mia"))
    assert book.headers.get(ALLOWED_ACTIONS) == "read, modify", "delete is prohibited on this book"
    tenant = await scene.http.get(scene.tenant, headers=scene.headers("mia"))
    assert tenant.headers.get(ALLOWED_ACTIONS) == "read, modify, delete", "the tenant is unaffected"


async def test_the_listing_items_carry_what_the_tenant_read_answers(scene) -> None:  # T-31
    await _everyone_has_a_role(scene)
    for who in ("ada", "mia", "rita"):
        headers = scene.headers(who)
        header = (await scene.http.get(scene.tenant, headers=headers)).headers.get(ALLOWED_ACTIONS)
        page = Page.model_validate((await scene.http.get("/libraries", headers=headers)).json())
        [item] = [
            t for t in map(TenantSummary.model_validate, page.items) if t.id == scene.tenant_iri
        ]
        listed = ", ".join(item.allowed_actions or [])
        assert listed == header, f"{who}: the listing says what the read says"


async def test_a_created_tenant_summary_leaves_allowed_actions_empty(service, client) -> None:
    response = await client.post("/libraries", json=TENANT_BODY, headers=service.bearer("ada"))
    assert TenantSummary.model_validate(response.json()).allowed_actions is None, "create"


# --- the three representations of one book describe the same triples --------------------------------


async def test_the_three_representations_of_a_book_are_the_same_triples(scene) -> None:
    context = scene.service.kit.documents.context

    def triples(response: httpx.Response, media_type: str) -> Graph:
        if media_type == TURTLE:
            return Graph().parse(data=response.text, format="turtle")
        body = response.json()  # JSON-LD is read as served, with its own context
        if media_type == JSON:  # plain JSON is JSON-LD with the context its Link header names
            body = {"@context": context, **body}
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


# --- consumer validators on tenant writes (mwb2-adoption-fixes PD-7, DEC-6) ---------------------


@asynccontextmanager
async def _scene_validated(**validators) -> AsyncIterator[Scene]:
    """A scene over a toy service whose validators are ``validators``."""
    toy = ToyService(**validators)
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        yield await Scene.set_up(toy, http)


async def _empty_grants(scene: Scene) -> httpx.Response:
    return await scene.http.put(
        f"{scene.tenant}/grants",
        json={},
        headers=scene.headers("ada", **{"If-Match": scene.access_etag}),
    )


async def test_a_refusing_grant_validator_is_a_422_and_the_record_keeps_its_etag() -> None:  # T-20
    async with _scene_validated(grant_validators=[keep_a_librarian]) as scene:
        refused = await _empty_grants(scene)
        assert (refused.status_code, problem_of(refused).type) == (
            422,
            f"{PROBLEMS}invalid-body",
        ), refused.text
        assert "at least one librarian" in (problem_of(refused).detail or ""), "its message"
        grants = await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))
        assert grants.headers["etag"] == scene.access_etag, "the record did not move"


def _bug(old, new, who) -> None:
    if not new.grants:  # the scene's own set-up writes grants
        raise RuntimeError("bug")


def _not_valid(old, new, who) -> None:
    if not new.grants:
        Page.model_validate({"items": "x"})  # raises pydantic's ValidationError


async def test_a_validator_bug_is_a_500_and_a_pydantic_error_a_422_and_nothing_is_written() -> (
    None
):  # T-23
    async with _scene_validated(grant_validators=[_bug]) as scene:
        broken = await _empty_grants(scene)
        assert (broken.status_code, problem_of(broken).type) == (
            500,
            f"{PROBLEMS}internal-error",
        ), broken.text
        grants = await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))
        assert grants.headers["etag"] == scene.access_etag, "nothing written after the bug"
    async with _scene_validated(grant_validators=[_not_valid]) as scene:
        invalid = await _empty_grants(scene)
        assert (invalid.status_code, problem_of(invalid).type) == (
            422,
            f"{PROBLEMS}invalid-body",
        ), invalid.text
        grants = await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))
        assert grants.headers["etag"] == scene.access_etag, "nothing written after the 422"


def _no_root_city_bruges(old, new, who) -> None:
    if new.city == "Bruges":
        raise InvalidBody("no Bruges")


async def test_a_refusing_root_validator_on_a_root_put_leaves_the_root_unchanged() -> None:  # T-22
    async with _scene_validated(root_validators=[_no_root_city_bruges]) as scene:
        body = {"label": "Ghent", "description": "Books for all.", "city": "Bruges"}
        refused = await scene.http.put(
            scene.tenant, json=body, headers=scene.headers("ada", **{"If-Match": scene.root_etag})
        )
        assert (refused.status_code, problem_of(refused).type) == (
            422,
            f"{PROBLEMS}invalid-body",
        ), refused.text
        assert problem_of(refused).detail == "no Bruges", "the validator's own message"
        root = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
        assert (root.json()["city"], root.headers["etag"]) == ("Ghent", scene.root_etag), (
            "the root is as it was"
        )
        allowed = await _put_root(scene, "Ghent", scene.root_etag)
        assert allowed.status_code == 200, "a body the validator accepts is stored"


async def test_a_root_validator_on_a_root_put_sees_the_stored_root_and_the_body() -> None:  # T-22
    seen: list[tuple] = []
    async with _scene_validated(root_validators=[lambda *args: seen.append(args)]) as scene:
        seen.clear()  # the tenant's creation ran it
        body = {"label": "Ghent", "description": "Books for all.", "city": "Bruges"}
        await scene.http.put(
            scene.tenant, json=body, headers=scene.headers("ada", **{"If-Match": scene.root_etag})
        )
        old, new, who = seen[0]
        assert (old.city, new.city, who.id) == ("Ghent", "Bruges", principal_of("ada")), (
            "old is the stored root, new the decoded body"
        )


def _returns_false(old, new, who) -> bool | None:
    return False if not new.grants else None


def _forbids(old, new, who) -> None:
    if not new.grants:
        raise Forbidden("no")


def _http_403(old, new, who) -> None:
    if not new.grants:
        raise HTTPException(status_code=403)


async def test_a_validator_that_returns_a_value_or_raises_forbidden_is_a_500_and_nothing_is_written() -> (
    None
):  # R2-2, R2-3
    for validator in (_returns_false, _forbids, _http_403):
        async with _scene_validated(grant_validators=[validator]) as scene:
            broken = await _empty_grants(scene)
            assert (broken.status_code, problem_of(broken).type) == (
                500,
                f"{PROBLEMS}internal-error",
            ), broken.text
            grants = await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))
            assert grants.headers["etag"] == scene.access_etag, "nothing written"


async def test_a_refusal_on_create_is_a_422_with_its_detail_and_no_tenant_is_listed() -> None:
    def refuse(old, new, who) -> None:
        raise InvalidBody("no such library")

    toy = ToyService(root_validators=[refuse])
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        headers = toy.bearer("ada")
        refused = await http.post("/libraries", json=TENANT_BODY, headers=headers)
        assert (refused.status_code, problem_of(refused).type) == (
            422,
            f"{PROBLEMS}invalid-body",
        ), refused.text
        assert problem_of(refused).detail == "no such library", "the validator's own message"
        listed = await http.get("/libraries", headers=headers)
        assert listed.json()["items"] == [], "no tenant was made"

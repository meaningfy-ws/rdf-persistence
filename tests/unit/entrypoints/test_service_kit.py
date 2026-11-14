"""The service kit (task 5.1): the token and access dependencies, problem handlers, versions, start-up."""

import io
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from rdflib import RDF, Literal, URIRef

from rdf_persistence import GrantSet, Problem
from rdf_persistence.domain.exceptions import (
    Forbidden,
    InvalidBody,
    InvalidRoleDefinition,
    NotFound,
)
from rdf_persistence.domain.generated.rp_access import Action, Grant
from rdf_persistence.domain.media import PROBLEM_JSON
from rdf_persistence.entrypoints.router import build_router
from rdf_persistence.entrypoints.service import install_service
from rdf_persistence.services.vocabulary import ANNOTATION, HAS_TARGET
from rdf_persistence.testkit import FakeStore
from tests.fixtures.library import generated
from tests.toy import ROLES, SETTINGS, TOY_SCHEMA
from tests.toy_service import CONSUMER_POLICY, DUNE_BODY, TENANT_BODY, ToyService, principal_of

PROBLEMS = f"{SETTINGS.base}problems/"
FILE_KEY = URIRef("https://meaningfy.ws/ns/rdf-persistence#fileKey")
A_UUID = "6f1c0c1e-0000-4000-8000-000000000001"


async def made(client: httpx.AsyncClient, headers: dict[str, str]) -> tuple[str, str, str]:
    """A tenant, and a book in it: ``(tenant path, book path, book ETag)``."""
    tenant = await client.post("/libraries", json=TENANT_BODY, headers=headers)
    path = tenant.headers["location"]
    book = await client.post(f"{path}/books", json=DUNE_BODY, headers=headers)
    return path, book.headers["location"], book.headers["etag"]


# --- the token dependency: a 401 is a problem and no handler runs -------------------------------


async def test_an_expired_token_is_a_401_problem_and_no_handler_runs(service, client) -> None:
    token = service.signer.issue(sub="ada", expires_in=-60)
    queries_before = len(service.store.sent("query"))
    response = await client.get(
        f"/libraries/{A_UUID}/books/{A_UUID}", headers={"Authorization": f"Bearer {token}"}
    )
    problem = Problem.model_validate(response.json())
    assert response.status_code == 401, "status"
    assert response.headers["content-type"] == PROBLEM_JSON, "a problem, not bare text"
    assert problem.type == f"{PROBLEMS}invalid-token", "the problem type"
    assert response.headers["www-authenticate"] == "Bearer", "RFC 6750"
    assert len(service.store.sent("query")) == queries_before, (
        "neither the access check nor the route ran"
    )


@pytest.mark.parametrize(
    "authorization",
    [None, "", "Bearer", "Bearer ", "Basic YWRhOnB3", "Token abc", "Bearer not.a.jwt"],
    ids=["absent", "empty", "no-token", "blank-token", "basic", "other-scheme", "garbage"],
)
async def test_a_request_without_a_valid_bearer_token_is_a_401(
    service, client, authorization
) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}
    response = await client.get(f"/libraries/{A_UUID}", headers=headers)
    assert response.status_code == 401, f"Authorization: {authorization!r}"
    assert response.headers["content-type"] == PROBLEM_JSON, "problem media type"


async def test_a_token_for_another_audience_is_a_401(service, client) -> None:
    token = service.signer.issue(sub="ada", audience="someone-else")
    response = await client.get(
        f"/libraries/{A_UUID}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401, "the verifier refuses it"


async def test_an_unreachable_provider_is_a_503_problem_that_names_no_address(
    service, client
) -> None:
    service.signer.unreachable = True
    response = await client.get(f"/libraries/{A_UUID}", headers=service.bearer("ada"))
    assert (response.status_code, response.json()["type"]) == (503, f"{PROBLEMS}unavailable"), (
        "an outage of the provider is not the caller's fault"
    )


async def test_every_route_but_the_context_refuses_a_request_without_a_token(
    service, client
) -> None:
    routes = [
        r
        for r in build_router(service.kit).routes
        if isinstance(r, APIRoute) and r.name != "context"
    ]
    assert len(routes) >= 12, "the tenant routes and the routes of both aggregate types"
    for route in routes:
        path = re.sub(r"\{[^}]+\}", A_UUID, route.path)
        for method in route.methods:
            response = await client.request(method, path)
            assert response.status_code == 401, f"{method} {route.path} answered without a token"


# --- the access dependency ---------------------------------------------------------------------


async def test_a_caller_with_no_grant_in_a_tenant_gets_a_404_not_a_403(service, client) -> None:
    path, book, _ = await made(client, service.bearer("ada"))
    response = await client.get(book, headers=service.bearer("omar"))
    assert (response.status_code, response.json()["type"]) == (404, f"{PROBLEMS}not-found"), (
        "a tenant the caller has no grant in does not exist for it"
    )


async def test_a_path_that_is_not_a_tenant_id_is_a_404(service, client) -> None:
    response = await client.get("/libraries/not-a-uuid", headers=service.bearer("ada"))
    assert response.status_code == 404, "no tenant has that id"


async def test_the_text_of_a_404_does_not_tell_a_tenant_that_exists_from_one_that_does_not(
    service, client
) -> None:
    path, _, _ = await made(client, service.bearer("ada"))
    hidden = await client.get(path, headers=service.bearer("omar"))
    absent = await client.get(f"/libraries/{A_UUID}", headers=service.bearer("omar"))
    assert hidden.json() == absent.json(), "an outsider cannot probe which tenants exist"


# --- versions: ETag, If-Match, 428, 409 -------------------------------------------------------


async def test_a_read_answers_the_version_as_a_quoted_etag(service, client) -> None:
    _, book, created = await made(client, service.bearer("ada"))
    etag = (await client.get(book, headers=service.bearer("ada"))).headers["etag"]
    assert etag == created, "the version the create answered"
    assert re.fullmatch(r'"[0-9a-f-]{36}"', etag), "a quoted version token"


async def test_an_update_without_if_match_is_a_428_problem_and_changes_nothing(
    service, client
) -> None:
    _, book, etag = await made(client, service.bearer("ada"))
    updates = len(service.store.sent("update"))
    response = await client.put(book, json=DUNE_BODY, headers=service.bearer("ada"))
    assert response.status_code == 428, "status"
    assert response.json()["type"] == f"{PROBLEMS}precondition-required", "problem type"
    assert len(service.store.sent("update")) == updates, "nothing was written"
    assert (await client.get(book, headers=service.bearer("ada"))).headers["etag"] == etag, (
        "unchanged"
    )


async def test_a_delete_without_if_match_is_a_428(service, client) -> None:
    _, book, _ = await made(client, service.bearer("ada"))
    assert (await client.delete(book, headers=service.bearer("ada"))).status_code == 428, "status"


async def test_a_stale_if_match_is_a_409_problem(service, client) -> None:
    _, book, etag = await made(client, service.bearer("ada"))
    headers = {**service.bearer("ada"), "If-Match": etag}
    assert (await client.put(book, json=DUNE_BODY, headers=headers)).status_code == 200, "first"
    stale = await client.put(book, json={**DUNE_BODY, "label": "Late"}, headers=headers)
    assert (stale.status_code, stale.json()["type"]) == (409, f"{PROBLEMS}conflict"), "second"
    assert stale.headers["content-type"] == PROBLEM_JSON, "problem media type"


# --- problem handlers cover the consumer's own routes too --------------------------------------


async def test_a_route_the_consumer_writes_gets_the_same_problem_answers(service, client) -> None:
    @service.app.get("/mine")
    async def mine() -> None:
        raise NotFound("no such thing")

    response = await client.get("/mine")
    assert (response.status_code, response.json()["type"]) == (404, f"{PROBLEMS}not-found"), (
        "install_service registers the handlers on the whole app"
    )


# --- start-up ------------------------------------------------------------------------------------


class LoggedStore(FakeStore):
    """A fake store that remembers the order of the operations sent to it."""

    def __init__(self) -> None:
        super().__init__()
        self.log: list[tuple[str, str]] = []

    def _enter(self, operation: str, payload: str) -> None:
        self.log.append((operation, payload))
        super()._enter(operation, payload)


ORPHAN = "lib-t-" + "a" * 32


async def test_start_up_creates_the_system_database_and_then_sweeps() -> None:
    store = LoggedStore()
    toy = ToyService(store)
    await store.create_dataset(ORPHAN)
    store.log.clear()
    async with toy.app.router.lifespan_context(toy.app):
        pass
    operations = [name for name, _ in store.log]
    assert ("create_dataset", "lib-system") in store.log, "the system database is created"
    assert operations.index("create_dataset") < operations.index("query"), (
        "the sweep reads the access records only after the system database exists"
    )
    assert ORPHAN in await store.list_datasets(), (
        "no record on file: the sweep keeps what it cannot judge"
    )


async def test_start_up_sweeps_the_orphans_of_a_crashed_creation() -> None:
    store = LoggedStore()
    first = ToyService(store)
    async with first.app.router.lifespan_context(first.app), first.client() as http:
        await made(http, first.bearer("ada"))  # a tenant on record, so the sweep may judge the rest
    await store.create_dataset(ORPHAN)
    second = ToyService(store, first.files)
    async with second.app.router.lifespan_context(second.app):
        pass
    assert ORPHAN not in await store.list_datasets(), "the orphan database was dropped"


def installed(app: FastAPI, toy: ToyService, **changes) -> FastAPI:
    """``app`` with the toy service installed on it, sharing ``toy``'s ports unless ``changes`` says otherwise."""
    wiring = {
        "schema": TOY_SCHEMA,
        "generated": generated,
        "store": toy.store,
        "files": toy.files,
        "identity": toy.kit.identity,
        "verifier": toy.kit.verifier,
        "rules": toy.kit.rules,
        "settings": toy.settings,
    }
    install_service(app, **{**wiring, **changes})
    return app


async def test_the_apps_own_lifespan_runs_inside_the_start_up() -> None:
    events: list[str] = []

    @asynccontextmanager
    async def mine(_: FastAPI) -> AsyncIterator[None]:
        events.append("start")
        yield
        events.append("stop")

    toy = ToyService()
    app = installed(FastAPI(lifespan=mine), toy)
    async with app.router.lifespan_context(app):
        assert "lib-system" in await toy.store.list_datasets(), "the system database exists"
        assert events == ["start"], "the app's own start-up ran"
    assert events == ["start", "stop"], "and its shut-down"


def test_an_invalid_role_definitions_file_refuses_to_start_naming_the_entry(tmp_path) -> None:
    bad = tmp_path / "roles.yaml"
    bad.write_text(
        "- {role: admin, level: system, actions: [read]}\n- {role: broken, level: nowhere}\n"
    )
    with pytest.raises(InvalidRoleDefinition, match="entry 2.*broken"):
        installed(FastAPI(), ToyService(), rules=bad)


async def test_a_role_definitions_path_is_loaded_into_the_rules() -> None:
    toy = ToyService()
    app = installed(FastAPI(), toy, rules=ROLES)
    async with app.router.lifespan_context(app), toy.client() as http:
        path, book, _ = await made(http, toy.bearer("ada"))
        assert (await http.get(book, headers=toy.bearer("ada"))).status_code == 200, (
            "the rules built from the file let the librarian read"
        )


async def test_the_prefix_mounts_every_route_below_it() -> None:
    toy = ToyService()
    app = installed(FastAPI(), toy, prefix="/api/v1")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        mounted = await http.get("/api/v1/context.jsonld")
        bare = await http.get("/context.jsonld")
    assert (mounted.status_code, bare.status_code) == (200, 404), "only the prefixed path serves"


# --- bucket_of: the public accessor of a consumer's own routes -----------------------------------


async def test_bucket_of_a_tenant_is_its_stored_database_name(service, client) -> None:
    path, _, _ = await made(client, service.bearer("ada"))
    iri = service.kit.tenant_iri(path.rsplit("/", 1)[1])
    record, _ = await service.kit.tenancy.get(iri)
    assert await service.kit.bucket_of(iri) == record.database_name, (
        "the bucket is the database name"
    )


async def test_bucket_of_an_unknown_tenant_is_not_found(service) -> None:
    with pytest.raises(NotFound):
        await service.kit.bucket_of(service.kit.tenant_iri(A_UUID))


# --- id_source: a test chooses the ids the service draws (PD-5, DEC-7) ----------------------------


async def test_a_tenant_id_that_clashes_is_redrawn_and_the_first_tenant_is_unchanged() -> None:
    first, fresh = str(uuid.uuid4()), str(uuid.uuid4())
    draws = iter([first, first, fresh])
    toy = ToyService(id_source=lambda _spec: next(draws))
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        headers = toy.bearer("ada")
        one = await http.post("/libraries", json=TENANT_BODY, headers=headers)
        two = await http.post(
            "/libraries", json={**TENANT_BODY, "label": "Bruges"}, headers=headers
        )
        again = await http.get(one.headers["location"], headers=headers)
    assert one.headers["location"].endswith(f"/{first}"), "the first create took the first draw"
    assert two.headers["location"].endswith(f"/{fresh}"), "the clash was redrawn"
    assert again.status_code == 200, "the first tenant is unchanged"
    assert again.json()["label"] == TENANT_BODY["label"], "and keeps its label"


async def test_without_an_id_source_two_creates_draw_different_ids_of_the_policy_length() -> None:
    toy = ToyService(iri_policy=CONSUMER_POLICY)
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        locations = [
            (await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada")))
            .headers["location"]
            .rsplit("/", 1)[-1]
            for _ in range(2)
        ]
    assert locations[0] != locations[1], "drawn, not fixed"
    length = CONSUMER_POLICY.tenant_id.length
    assert [len(i) for i in locations] == [length, length], "the policy's tenant id length"


# --- the sweep of a live tenant (live-tenant-sweep task 3.2) -------------------------------------


async def test_the_kit_sweeps_a_tenant_with_its_own_store_files_and_iris(service, client) -> None:
    headers = {"Authorization": f"Bearer {service.signer.issue(sub='ada')}"}
    path = (await client.post("/libraries", json=TENANT_BODY, headers=headers)).headers["location"]
    tenant = service.kit.tenant_iri(path.rsplit("/", 1)[1])
    bucket = await service.kit.bucket_of(tenant)
    await service.files.put(bucket, "left-behind", b"bytes")

    report = await service.kit.sweep_tenant(tenant, older_than=timedelta(seconds=-1))

    assert report.tenant == tenant and report.older_than_seconds == -1
    assert report.blobs == ["left-behind"], "found through the kit's own file store"
    assert report.removed_loaded_graphs is False, "a dry run, as by default"
    await service.kit.sweep_tenant(tenant, remove_blobs=True, older_than=timedelta(seconds=-1))
    assert await service.files.list_blobs(bucket) == [], "the keywords reach the sweep"


# --- dump and restore of a tenant (tenant-dump-restore PD-8) -------------------------------------


async def test_the_kit_dumps_a_tenant_and_restores_it_for_another_principal(
    service, client
) -> None:
    headers = {"Authorization": f"Bearer {service.signer.issue(sub='ada')}"}
    path = (await client.post("/libraries", json=TENANT_BODY, headers=headers)).headers["location"]
    tenant = service.kit.tenant_iri(path.rsplit("/", 1)[1])
    await service.files.put(await service.kit.bucket_of(tenant), "k1", b"scan bytes")
    archive = io.BytesIO()

    manifest = await service.kit.dump_tenant(tenant, archive)
    summary = await service.kit.restore_tenant(
        io.BytesIO(archive.getvalue()), "https://example.org/people/bob"
    )

    assert manifest.source_tenant == tenant, "the manifest names the tenant it came from"
    assert summary.id != tenant and summary.label == manifest.label, "a new tenant with the label"
    record, _ = await service.kit.tenancy.get(summary.id)
    assert [g.assignee for g in record.grants] == ["https://example.org/people/bob"], (
        "the restorer only"
    )
    assert await service.files.get(record.database_name, "k1") == b"scan bytes", (
        "the blob came along"
    )


async def test_the_kit_restores_no_more_than_the_settings_max_restore_bytes(
    service, client, monkeypatch
) -> None:
    headers = {"Authorization": f"Bearer {service.signer.issue(sub='ada')}"}
    path = (await client.post("/libraries", json=TENANT_BODY, headers=headers)).headers["location"]
    tenant = service.kit.tenant_iri(path.rsplit("/", 1)[1])
    archive = io.BytesIO()
    await service.kit.dump_tenant(tenant, archive)
    assert service.kit.max_restore_bytes == 1024**3, "the settings' default reaches the kit"
    monkeypatch.setattr(service.kit, "max_restore_bytes", 1024)

    with pytest.raises(InvalidBody, match="bytes"):
        await service.kit.restore_tenant(
            io.BytesIO(archive.getvalue()), "https://example.org/people/bob"
        )


# --- removal of a file aggregate with its blobs (live-tenant-sweep task 4.1) ---------------------


async def test_the_kit_removes_an_aggregate_with_its_blobs(service, client) -> None:
    headers = {"Authorization": f"Bearer {service.signer.issue(sub='ada')}"}
    path = (await client.post("/libraries", json=TENANT_BODY, headers=headers)).headers["location"]
    tenant = service.kit.tenant_iri(path.rsplit("/", 1)[1])
    bucket = await service.kit.bucket_of(tenant)
    scan = f"{tenant}/scans/{uuid.UUID(int=1)}"
    async with service.kit.session(tenant, "ada") as session:
        version = await session.add_graph(scan, [(URIRef(scan), FILE_KEY, Literal("k1"))])
    await service.files.put(bucket, "k1", b"bytes")

    await service.kit.remove_with_files(tenant, "ada", scan, version)

    assert await service.files.list_blobs(bucket) == [], "the kit's own file store lost the blob"
    async with service.kit.session(tenant, "ada") as session:
        with pytest.raises(NotFound):
            await session.get_graph(scan)


async def test_a_collaboration_opens_for_the_authorised_caller_with_its_global_roles(
    service, client
) -> None:
    headers = service.bearer("ada", "admin")
    tenant = await client.post("/libraries", json=TENANT_BODY, headers=headers)
    path = tenant.headers["location"]
    tenant_id = path.rsplit("/", 1)[1]
    shelf = f"{service.kit.tenant_iri(tenant_id)}/shelves/{A_UUID}"
    book = await client.post(f"{path}/books", json={**DUNE_BODY, "shelf": shelf}, headers=headers)
    authorised = await service.kit.require(headers["Authorization"], tenant_id, Action.READ)
    async with service.kit.collaboration(authorised) as collaboration:
        found = await collaboration.referrers(shelf)
    assert [(r.referrer, r.referrer_slot) for r in found.referrers or []] == [
        (book.json()["id"], "shelf")
    ], "the tenant of the caller's access, read as its principal"
    assert authorised.global_roles == ["admin"], "the roles the collaboration is rebuilt from"


async def test_the_kit_sessions_drop_the_comments_of_a_removed_aggregate(service, client) -> None:
    headers = service.bearer("ada")
    path = (await client.post("/libraries", json=TENANT_BODY, headers=headers)).headers["location"]
    tenant = service.kit.tenant_iri(path.rsplit("/", 1)[1])
    book = (await client.post(f"{path}/books", json=DUNE_BODY, headers=headers)).json()["id"]
    comment = str(service.kit.iris.mint_aggregate(tenant, "rp-comment", "rp-comments"))
    ours = [(URIRef(comment), RDF.type, ANNOTATION), (URIRef(comment), HAS_TARGET, URIRef(book))]
    async with service.kit.session(tenant, "ada") as session:
        await session.add_graph(comment, ours)
        await session.remove(book, (await session.get_graph(book))[2])
        with pytest.raises(NotFound):
            await session.get_graph(comment)


async def test_a_collaboration_opens_on_the_answer_of_require_aggregate(service, client) -> None:
    headers = service.bearer("ada")
    path = (await client.post("/libraries", json=TENANT_BODY, headers=headers)).headers["location"]
    tenant_id = path.rsplit("/", 1)[1]
    shelf = f"{service.kit.tenant_iri(tenant_id)}/shelves/{A_UUID}"
    book = await client.post(f"{path}/books", json={**DUNE_BODY, "shelf": shelf}, headers=headers)
    checked = await service.kit.require_aggregate(
        headers["Authorization"], tenant_id, "shelves", A_UUID, Action.READ
    )
    async with service.kit.collaboration(checked) as collaboration:
        found = await collaboration.referrers(checked.checked_target)
    assert [(r.referrer, r.referrer_slot) for r in found.referrers or []] == [
        (book.json()["id"], "shelf")
    ], "the aggregate that was checked is the one asked about"


async def allow_annotating(scene, *who: str) -> None:
    """Grant each of ``who`` the action ``annotate`` on the tenant, beside the grants it has."""
    grants = GrantSet.model_validate(
        (await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))).json()
    )
    added = [
        Grant(assignee=principal_of(sub), target=scene.tenant_iri, action=Action.ANNOTATE)
        for sub in who
    ]
    scene.access_etag = await scene.set_grants(GrantSet(grants=[*(grants.grants or []), *added]))


async def comment_as(scene, sub: str, text: str) -> str:
    """``sub`` comments on the scene's book through a collaboration the kit opens for its token."""
    tenant_id = scene.tenant.rsplit("/", 1)[1]
    authorised = await scene.service.kit.require(
        scene.headers(sub)["Authorization"], tenant_id, Action.READ
    )
    async with scene.service.kit.collaboration(authorised) as collaboration:
        return await collaboration.comment(scene.book_iri, text)


async def test_each_caller_who_comments_through_the_kit_is_the_author_of_its_comment(scene) -> None:
    await allow_annotating(scene, "ada", "rita")
    by_ada = await comment_as(scene, "ada", "from ada")
    by_rita = await comment_as(scene, "rita", "from rita")
    tenant_id = scene.tenant.rsplit("/", 1)[1]
    authorised = await scene.service.kit.require(
        scene.headers("ada")["Authorization"], tenant_id, Action.READ
    )
    async with scene.service.kit.collaboration(authorised) as collaboration:
        thread = await collaboration.thread(scene.book_iri)
    assert {c.id: c.creator for c in thread} == {
        by_ada: principal_of("ada"),
        by_rita: principal_of("rita"),
    }, "each comment is tracked to the caller whose collaboration posted it"


async def test_the_generic_delete_of_a_book_drops_the_comments_on_it(scene) -> None:
    await allow_annotating(scene, "ada")
    comment = await comment_as(scene, "ada", "a remark")
    deleted = await scene.http.delete(
        scene.book, headers=scene.headers("ada", **{"If-Match": scene.book_etag})
    )
    assert deleted.status_code == 204, "the comment did not change the book's version"
    async with scene.service.kit.session(scene.tenant_iri, "ada") as session:
        with pytest.raises(NotFound):
            await session.get_graph(comment)


async def test_a_reviewer_who_comments_is_still_refused_the_modify_of_the_book(scene) -> None:
    """The rp-access scenario through the generic route: annotate implies read and nothing else."""
    await allow_annotating(scene, "rita")
    await comment_as(scene, "rita", "a remark")
    refused = await scene.http.put(
        scene.book, json=DUNE_BODY, headers=scene.headers("rita", **{"If-Match": scene.book_etag})
    )
    assert refused.status_code == 403, "a comment is no right to write"
    tenant_id = scene.tenant.rsplit("/", 1)[1]
    book_id = scene.book.rsplit("/", 1)[1]
    with pytest.raises(Forbidden):
        await scene.service.kit.require_aggregate(
            scene.headers("rita")["Authorization"], tenant_id, "books", book_id, Action.MODIFY
        )

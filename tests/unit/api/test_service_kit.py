"""The service kit: the token and access dependencies, problem handlers, versions, start-up."""

import asyncio
import io
import re
import shutil
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi import FastAPI
from fastapi.routing import APIRoute
from rdflib import RDF, Literal, URIRef

from rdf_persistence import GrantSet, Problem, bootstrap
from rdf_persistence.access.domain.generated.rp_access import Action, Grant
from rdf_persistence.access.services.generated.rp_access_services import VerifiedCaller
from rdf_persistence.api.entrypoints.generated.settings.rp_api_settings import (
    SseSettings,
    ToolkitSettings,
)
from rdf_persistence.api.entrypoints.router import build_router
from rdf_persistence.collaboration.domain.generated.rp_workflow import Transition
from rdf_persistence.core.domain.exceptions import (
    CommitTooLarge,
    Forbidden,
    InvalidBody,
    InvalidRoleDefinition,
    InvalidWorkflow,
    NotFound,
)
from rdf_persistence.core.domain.media import PROBLEM_JSON
from rdf_persistence.events.services.event_hub import CLOSED
from rdf_persistence.events.services.generated.settings.rp_events_settings import EventSettings
from rdf_persistence.iris.services.iris import DEFAULT_IRIS
from rdf_persistence.migrations.services.generated.rp_migrations_services import Migration
from rdf_persistence.migrations.services.migrations import stamps
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.persistence.services.mapper import UnitOfWork
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity, Replace
from rdf_persistence.schema.services.vocabulary import ANNOTATION, HAS_TARGET, metamodel
from rdf_persistence.testkit import FakeStore, RecordingObserver, open_event_stream
from tests.scene import Scene
from tests.toy import (
    REVIEW_WORKFLOW,
    ROLES,
    SETTINGS,
    TOY_SCHEMA,
    book_iri,
    dune,
)
from tests.toy_service import (
    A_UUID,
    DUNE_BODY,
    EXAMPLE_POLICY,
    TENANT_BODY,
    ToyService,
    assert_problem,
    installed,
    made,
    principal_of,
)
from tests.unit.activity_helpers import activities

PROBLEMS = f"{SETTINGS.base}problems/"
FILE_KEY = URIRef("https://meaningfy.ws/ns/rdf-persistence#fileKey")
LIBRARY_SCHEMA = "https://example.org/ns/library"
TOOLKIT_SCHEMA = "https://meaningfy.ws/ns/rdf-persistence"


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


# Classes: no credential (absent), no token after the scheme, a scheme that is not
# Bearer, a token the verifier refuses.
@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer", "Basic YWRhOnB3", "Bearer not.a.jwt"],
    ids=["absent", "no-token", "basic", "garbage"],
)
async def test_a_request_without_a_valid_bearer_token_is_a_401(
    service, client, authorization
) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}
    response = await client.get(f"/libraries/{A_UUID}", headers=headers)
    assert response.status_code == 401, f"Authorization: {authorization!r}"
    assert response.headers["content-type"] == PROBLEM_JSON, "problem media type"


async def test_a_valid_token_under_another_scheme_is_a_401(service, client) -> None:
    token = service.signer.issue(sub="ada")
    response = await client.get(f"/libraries/{A_UUID}", headers={"Authorization": f"Basic {token}"})
    assert response.status_code == 401, "the scheme, not the token, is what is refused"


class AcceptsAnyToken:
    """A verifier that takes every string for a valid token, so only the gate can refuse one."""

    iris = DEFAULT_IRIS

    async def verify(self, token: str) -> VerifiedCaller:
        return VerifiedCaller(principal="ada")


async def test_an_empty_bearer_token_is_a_401_even_when_the_verifier_takes_any_string() -> None:
    toy = ToyService()
    app = installed(FastAPI(), toy, verifier=AcceptsAnyToken())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        empty = await http.get(f"/libraries/{A_UUID}", headers={"Authorization": "Bearer "})
        control = await http.get(f"/libraries/{A_UUID}", headers={"Authorization": "Bearer x"})
    assert empty.status_code == 401, "the gate refuses an empty token before the verifier"
    assert control.status_code != 401, "the stub does accept a token, so the 401 is the gate's"


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


def test_a_relative_roles_path_is_opened_from_the_working_directory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "roles.yaml").write_text(ROLES.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    installed(FastAPI(), ToyService(), rules=Path("roles.yaml"))  # no error: the file was found
    monkeypatch.chdir(tmp_path.parent)
    with pytest.raises(InvalidRoleDefinition, match="roles.yaml"):
        installed(FastAPI(), ToyService(), rules=Path("roles.yaml"))


def test_a_relative_workflow_path_is_opened_from_the_working_directory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "review.workflow.yaml").write_text(
        REVIEW_WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    service = ToyService(workflows=(Path("review.workflow.yaml"),))
    assert service.kit.workflows.for_class("Book") is not None, "the file was read"
    monkeypatch.chdir(tmp_path.parent)
    with pytest.raises(InvalidWorkflow, match="review.workflow.yaml"):
        ToyService(workflows=(Path("review.workflow.yaml"),))


@pytest.mark.parametrize("given", ["folder", "glob"])
def test_a_folder_or_a_glob_in_workflows_is_no_workflow_file(tmp_path, given: str) -> None:
    (tmp_path / "review.workflow.yaml").write_text(
        REVIEW_WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8"
    )
    path = tmp_path if given == "folder" else tmp_path / "*.workflow.yaml"
    with pytest.raises(InvalidWorkflow, match="cannot read the workflow"):
        ToyService(workflows=(path,))


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
    toy = ToyService(iri_policy=EXAMPLE_POLICY)
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        locations = [
            (await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada")))
            .headers["location"]
            .rsplit("/", 1)[-1]
            for _ in range(2)
        ]
    assert locations[0] != locations[1], "drawn, not fixed"
    length = EXAMPLE_POLICY.tenant_id.length
    assert [len(i) for i in locations] == [length, length], "the policy's tenant id length"


# --- the sweep of a live tenant (live-tenant-sweep) -------------------------------------


async def test_the_kit_sweeps_a_tenant_with_its_own_store_files_and_iris(service, client) -> None:
    headers = {"Authorization": f"Bearer {service.signer.issue(sub='ada')}"}
    path = (await client.post("/libraries", json=TENANT_BODY, headers=headers)).headers["location"]
    tenant = service.kit.tenant_iri(path.rsplit("/", 1)[1])
    bucket = await service.kit.bucket_of(tenant)
    await service.files.put(bucket, "left-behind", b"bytes")

    report = await service.kit.sweep_tenant(tenant, older_than=timedelta(seconds=-1))

    assert report.tenant == tenant, "the report names the swept tenant"
    assert report.older_than_seconds == -1, "the report keeps the age limit it was asked for"
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
    assert summary.id != tenant, "a new tenant with the label"
    assert summary.label == manifest.label, "a new tenant with the label"
    record, _ = await service.kit.tenancy.get(summary.id)
    assert [g.assignee for g in record.grants] == ["https://example.org/people/bob"], (
        "the restorer only"
    )
    assert await service.files.get(record.database_name, "k1") == b"scan bytes", (
        "the blob came along"
    )


async def test_the_kit_restores_no_more_than_the_settings_max_restore_bytes(
    service, client
) -> None:
    headers = {"Authorization": f"Bearer {service.signer.issue(sub='ada')}"}
    path = (await client.post("/libraries", json=TENANT_BODY, headers=headers)).headers["location"]
    tenant = service.kit.tenant_iri(path.rsplit("/", 1)[1])
    archive = io.BytesIO()
    await service.kit.dump_tenant(tenant, archive)
    assert service.kit.max_restore_bytes == 1024**3, "the settings' default reaches the kit"
    limited = ToyService(max_restore_bytes=1024)

    assert limited.kit.max_restore_bytes == 1024, "the setting reaches the kit"
    with pytest.raises(InvalidBody, match="bytes"):
        await limited.kit.restore_tenant(
            io.BytesIO(archive.getvalue()), "https://example.org/people/bob"
        )


# --- removal of a file aggregate with its blobs (live-tenant-sweep) ---------------------


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


async def test_a_transition_through_the_kit_records_the_caller_as_its_agent(scene) -> None:
    tenant_id = scene.tenant.rsplit("/", 1)[1]
    authorised = await scene.service.kit.require(
        scene.headers("ada")["Authorization"], tenant_id, Action.READ
    )
    async with scene.service.kit.session(scene.tenant_iri, "ada") as session:
        version = (await session.get_graph(scene.book_iri))[2]
    async with scene.service.kit.collaboration(authorised) as collaboration:
        await collaboration.transition(
            scene.book_iri, "in_review", if_version=version, comment="ready"
        )
        [record] = await collaboration.transitions(scene.book_iri)
        [ready] = await collaboration.thread(scene.book_iri)
    assert record.was_associated_with == [principal_of("ada")], "the caller is the agent"
    assert record.transition_comment == ready.id, "the record names the comment of the thread"
    assert record.to_state_iri.endswith("/in_review"), "the book moved to review"


async def test_the_kit_restores_a_dump_of_an_older_version_and_migrates_it(
    service, client, tmp_path
) -> None:
    """PD-25.10: the dump is of the schema at version 1; the kit that restores it runs version 2 and has its migration."""
    headers = {"Authorization": f"Bearer {service.signer.issue(sub='ada')}"}
    path = (await client.post("/libraries", json=TENANT_BODY, headers=headers)).headers["location"]
    tenant = service.kit.tenant_iri(path.rsplit("/", 1)[1])
    archive = io.BytesIO()
    await service.kit.dump_tenant(tenant, archive)

    schema_folder, migrations = tmp_path / "library", tmp_path / "migrations"
    shutil.copytree(
        TOY_SCHEMA.parent,
        schema_folder,
        ignore=shutil.ignore_patterns("generated", "golden", "web"),
    )
    library = schema_folder / TOY_SCHEMA.name
    library.write_text(
        library.read_text("utf-8").replace('version: "1"', 'version: "2"', 1), "utf-8"
    )
    migrations.mkdir()
    step = Migration(schema_id=LIBRARY_SCHEMA, from_version="1", to_version="2")
    (migrations / "1__2.yaml").write_text(
        yaml.safe_dump(step.model_dump(exclude_none=True)), "utf-8"
    )
    newer = ToyService(service.store, service.files, schema=library, migrations=migrations)

    summary = await newer.kit.restore_tenant(
        io.BytesIO(archive.getvalue()), "https://example.org/people/bob"
    )

    record, _ = await newer.kit.tenancy.get(summary.id)
    held = await stamps(newer.store, record.database_name, newer.kit.tenancy.stamps_graph)
    assert held[LIBRARY_SCHEMA] == "2", "the restored tenant is at the version the kit runs"
    assert held[TOOLKIT_SCHEMA] == metamodel().schema.version, (
        "and the toolkit's stamp is unchanged"
    )


def observed(scene) -> RecordingObserver:
    """An observer of every activity, on a bus the kit now publishes to (message-bus PD-17)."""
    seen = RecordingObserver()
    kit = scene.service.kit
    kit.bus = bootstrap(observers={Activity: [seen]}, mapper=kit.mapper)
    return seen


async def replace_the_book(scene) -> None:
    response = await scene.http.put(
        scene.book,
        json={**DUNE_BODY, "label": "Dune Messiah"},
        headers=scene.headers("ada", **{"If-Match": scene.book_etag}),
    )
    assert response.status_code == 200, response.text


async def test_a_generic_replace_reaches_the_observers_of_the_kits_bus(scene) -> None:  # TC-81
    seen = observed(scene)
    before = scene.book_etag.strip('"')

    await replace_the_book(scene)

    async with scene.service.kit.session(scene.tenant_iri, "ada") as session:
        after = (await session.get_graph(scene.book_iri))[2]
    [replace] = seen.of(Replace)
    assert replace.was_associated_with == [principal_of("ada")], "associated with the caller"
    assert [(g.entity, g.entity_version) for g in replace.generations or []] == [
        (scene.book_iri, after)
    ], "it generated the new version of the book"
    assert [(i.entity, i.entity_version) for i in replace.invalidations or []] == [
        (scene.book_iri, before)
    ], "and invalidated the version the caller read"


async def test_a_kit_with_no_bus_records_and_publishes_nothing(scene) -> None:  # TC-82
    """Recording still happens without a bus; "publishes nothing" follows from having no bus to publish to."""
    assert scene.service.kit.bus is None, "a kit starts with no bus"

    await replace_the_book(scene)

    stored = await activities(
        scene.service.store,
        DEFAULT_IRIS.provenance(scene.tenant_iri),
        scene.service.kit.iris.resource_name(scene.tenant_iri),
    )
    assert [type(a) for a in stored if type(a) is Replace] == [Replace], "the commit is recorded"


async def test_a_direct_transition_reaches_the_transition_observers(scene) -> None:  # TC-83
    kit = scene.service.kit
    seen = RecordingObserver()
    kit.bus = bootstrap(observers={Transition: [seen]}, mapper=kit.mapper)
    authorised = await kit.require(
        scene.headers("ada")["Authorization"], scene.tenant.rsplit("/", 1)[1], Action.READ
    )
    async with kit.session(scene.tenant_iri, "ada") as session:
        version = (await session.get_graph(scene.book_iri))[2]

    async with kit.collaboration(authorised) as collaboration:
        await collaboration.transition(scene.book_iri, "in_review", if_version=version)

    [move] = seen.of(Transition)
    assert move.to_state_iri.endswith("/in_review"), "the observer got the move"
    assert move.was_associated_with == [principal_of("ada")], "made by the caller"


# --- the toolkit settings reach what the kit builds (technical-models PD-7) --------------------------


@asynccontextmanager
async def served(toolkit: ToolkitSettings) -> AsyncIterator[ToyService]:
    toy = ToyService(toolkit=toolkit)
    async with toy.app.router.lifespan_context(toy.app):
        yield toy


async def test_a_roots_limit_of_the_toolkit_settings_reaches_the_units_of_work() -> None:  # TC-35
    toolkit = ToolkitSettings(limits=LimitSettings(max_roots=2))
    async with served(toolkit) as toy, toy.client() as http:
        tenant = (await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))).json()
        async with toy.kit.session(tenant["id"], "ada") as session:
            work = UnitOfWork(session, toy.kit.mapper)
            for n in (1, 2, 3):
                work.add(dune(book_iri(n)))
            with pytest.raises(CommitTooLarge):
                await work.commit()


async def test_a_keep_alive_of_the_toolkit_settings_reaches_the_events_route() -> None:  # TC-36
    toolkit = ToolkitSettings(sse=SseSettings(keep_alive_seconds=0.05, max_lifetime_seconds=0.001))
    async with served(toolkit) as toy, toy.client() as http:
        scene = await Scene.set_up(toy, http)
        # deliver the set-up activity now: the only wake left for the stream is the keep-alive
        await toy.kit.relay.run_once()
        opened = await open_event_stream(
            toy.app,
            f"{scene.tenant}/rp-events",
            headers=scene.headers("rita"),
            events=1,
            timeout=3.0,  # the stream ends at its first wake, 0.05 s; with 15 s it would raise
        )
    assert opened.status == 200, "the route was reached: a refusal would also leave no events"
    assert opened.headers["content-type"].startswith("text/event-stream"), "it is an event stream"
    assert opened.events == [], "the stream ended at its first wake, before any event"


async def test_a_node_limit_of_the_toolkit_settings_reaches_the_documents() -> None:  # TC-37
    toolkit = ToolkitSettings(limits=LimitSettings(max_document_nodes=3))
    async with served(toolkit) as toy, toy.client() as http:
        headers = toy.bearer("ada")
        path = (await http.post("/libraries", json=TENANT_BODY, headers=headers)).headers[
            "location"
        ]
        chapters = [{"number": n} for n in range(4)]
        response = await http.post(
            f"{path}/books", json={**DUNE_BODY, "chapters": chapters}, headers=headers
        )
        assert_problem(response, 413, "payload-too-large")


async def test_a_queue_size_of_the_toolkit_settings_reaches_the_hub() -> None:  # TC-38
    toolkit = ToolkitSettings(events=EventSettings(hub_queue_size=1))
    async with served(toolkit) as toy, toy.kit.hub.subscribe("tenant") as queue:
        for n in (1, 2):
            toy.kit.hub.offer("tenant", Activity(id=f"urn:uuid:{n}"))
        assert await asyncio.wait_for(queue.get(), 1) is CLOSED, "the second one overflowed it"


def test_a_kit_given_no_toolkit_settings_holds_a_fresh_default_instance() -> None:
    first, second = ToyService().kit, ToyService().kit
    assert first.toolkit == ToolkitSettings(), "the defaults"
    assert first.toolkit is not second.toolkit, "a fresh instance, shared by no two kits"
    assert first.mapper.max_roots == LimitSettings().max_roots, "the roots limit"

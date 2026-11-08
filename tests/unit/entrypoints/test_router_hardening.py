"""What the stage 5 review found, as requests (PD-14b): strict bodies, bounded bodies, every error a problem."""

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from rdf_persistence import Page
from rdf_persistence.domain.exceptions import BadQuery, SparqlError
from rdf_persistence.domain.iris import graph_iri, system_database_name, tenant_resource_name
from rdf_persistence.domain.media import JSON, JSON_LD, TURTLE
from rdf_persistence.services import vocabulary as v
from tests.toy import SETTINGS
from tests.toy_service import DUNE_BODY, SCAN_BODY, TENANT_BODY, ToyService
from tests.unit.entrypoints.scene import PROBLEMS, Scene, problem_of

RP = "https://meaningfy.ws/ns/rdf-persistence#"
ODRL = "http://www.w3.org/ns/odrl/2/"
SECRET = "SECRET-FILE-KEY"
SMALL = 4096
LD_HEADER = {"Content-Type": JSON_LD}


async def slug_of(response: httpx.Response, status: int) -> str:
    assert response.status_code == status, response.text
    return problem_of(response).type.removeprefix(PROBLEMS)


# --- internal slots ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["file_key", "rp:fileKey", f"{RP}fileKey"])
async def test_a_json_scan_cannot_set_the_file_key_in_any_key_form(scene, key) -> None:
    response = await scene.http.post(
        f"{scene.tenant}/scans", json={**SCAN_BODY, key: SECRET}, headers=scene.headers("ada")
    )
    assert await slug_of(response, 422) == "invalid-body", response.text
    assert "file_key" in response.json()["detail"], "the slot is named"


async def test_a_json_ld_scan_cannot_set_the_file_key(scene) -> None:
    body = {
        "@context": [scene.service.kit.documents.context, {"rp": RP}],
        "type": "Scan",
        **SCAN_BODY,
        "rp:fileKey": SECRET,
    }
    response = await scene.http.post(
        f"{scene.tenant}/scans", json=body, headers=scene.headers("ada", **LD_HEADER)
    )
    assert await slug_of(response, 422) == "invalid-body", response.text
    assert "file_key" in response.json()["detail"], "the slot is named"


@pytest.mark.parametrize("media_type", [JSON, JSON_LD, TURTLE])
async def test_a_stored_file_key_is_in_no_representation_and_no_listing(scene, media_type) -> None:
    made = await scene.http.post(
        f"{scene.tenant}/scans", json=SCAN_BODY, headers=scene.headers("ada")
    )
    location, iri = made.headers["location"], made.json()["id"]
    database = tenant_resource_name(SETTINGS.prefix, scene.tenant_iri)
    await scene.service.store.update(
        database,
        f'INSERT DATA {{ GRAPH <{iri}/graph> {{ <{iri}> <{RP}fileKey> "{SECRET}" }} }}',
    )
    one = await scene.http.get(location, headers=scene.headers("ada", Accept=media_type))
    assert one.status_code == 200, one.text
    assert SECRET not in one.text, f"{media_type} shows the key"
    assert "fileKey" not in one.text, f"{media_type} shows the predicate"
    listing = await scene.http.get(f"{scene.tenant}/scans", headers=scene.headers("ada"))
    assert SECRET not in listing.text, "and neither does a listing"


async def stores_file_key(scene, iri: str) -> bool:
    database = tenant_resource_name(SETTINGS.prefix, scene.tenant_iri)
    ask = f'ASK {{ GRAPH <{graph_iri(iri)}> {{ <{iri}> <{RP}fileKey> "{SECRET}" }} }}'
    return bool((await scene.service.store.query(database, ask)).askAnswer)


async def test_a_replace_keeps_the_internal_values_the_service_stored(scene) -> None:
    made = await scene.http.post(
        f"{scene.tenant}/scans", json=SCAN_BODY, headers=scene.headers("ada")
    )
    location, iri, etag = made.headers["location"], made.json()["id"], made.headers["etag"]
    database = tenant_resource_name(SETTINGS.prefix, scene.tenant_iri)
    await scene.service.store.update(
        database,
        f'INSERT DATA {{ GRAPH <{graph_iri(iri)}> {{ <{iri}> <{RP}fileKey> "{SECRET}" }} }}',
    )
    replaced = await scene.http.put(
        location,
        json={**SCAN_BODY, "label": "Dune, rescanned"},
        headers=scene.headers("ada", **{"If-Match": etag}),
    )
    assert replaced.status_code == 200, replaced.text
    assert SECRET not in replaced.text, "and it is still shown to no one"
    assert await stores_file_key(scene, iri), "the client cannot set the key, so a replace keeps it"


# --- nodes the aggregate does not own ---------------------------------------------------------


async def test_a_node_smuggled_through_a_reference_is_a_422_and_nothing_is_stored(scene) -> None:
    made = await scene.http.post(
        f"{scene.tenant}/scans", json=SCAN_BODY, headers=scene.headers("ada")
    )
    location, iri, etag = made.headers["location"], made.json()["id"], made.headers["etag"]
    smuggled = {"@id": f"{iri}/smuggled", "junk": "anything"}
    response = await scene.http.put(
        location,
        json={**SCAN_BODY, "scan_of": smuggled},
        headers=scene.headers("ada", **{"If-Match": etag}),
    )
    assert await slug_of(response, 422) == "invalid-body", response.text
    turtle = await scene.http.get(location, headers=scene.headers("ada", Accept=TURTLE))
    assert "smuggled" not in turtle.text, "nothing of it was written"


async def test_the_tenant_root_cannot_plant_an_aggregate_in_the_meta_graph(scene) -> None:
    root = await scene.http.get(scene.tenant, headers=scene.headers("ada", Accept=JSON_LD))
    planted = {
        "@id": f"{scene.tenant_iri}/books/{uuid4()}",
        "@type": "Book",
        "label": "Planted",
        "description": "d",
    }
    body = {**root.json(), "http://schema.org/hasPart": planted}
    response = await scene.http.put(
        scene.tenant,
        content=json.dumps(body),
        headers=scene.headers("ada", **{"If-Match": scene.root_etag}, **LD_HEADER),
    )
    assert await slug_of(response, 422) == "invalid-body", response.text


# --- bounded bodies ---------------------------------------------------------------------------


@pytest.fixture
async def small() -> AsyncIterator[ToyService]:
    toy = ToyService(max_body_bytes=SMALL)
    async with toy.app.router.lifespan_context(toy.app):
        yield toy


async def test_a_declared_length_over_the_bound_is_a_413_before_the_body_is_read(small) -> None:
    async with small.client() as http:
        made = await http.post("/libraries", json=TENANT_BODY, headers=small.bearer("ada"))
        path = made.headers["location"]
        response = await http.post(
            f"{path}/books",
            content=b"{}",
            headers={**small.bearer("ada"), "Content-Type": JSON, "Content-Length": str(SMALL + 1)},
        )
    assert await slug_of(response, 413) == "payload-too-large", response.text


async def test_a_streamed_body_stops_at_the_bound(small) -> None:
    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(SMALL):  # no Content-Length: the body is counted as it arrives
            yield b" " * 8

    async with small.client() as http:
        made = await http.post("/libraries", json=TENANT_BODY, headers=small.bearer("ada"))
        response = await http.post(
            f"{made.headers['location']}/books",
            content=chunks(),
            headers={**small.bearer("ada"), "Content-Type": JSON},
        )
    assert await slug_of(response, 413) == "payload-too-large", response.text


async def test_a_body_within_the_bound_is_taken(small) -> None:
    async with small.client() as http:
        made = await http.post("/libraries", json=TENANT_BODY, headers=small.bearer("ada"))
        response = await http.post(
            f"{made.headers['location']}/books", json=DUNE_BODY, headers=small.bearer("ada")
        )
    assert response.status_code == 201, response.text


async def test_a_model_body_over_the_bound_is_a_413_too(small) -> None:
    async with small.client() as http:
        response = await http.post(
            "/libraries",
            json={**TENANT_BODY, "label": "x" * SMALL},
            headers=small.bearer("ada"),
        )
    assert await slug_of(response, 413) == "payload-too-large", response.text


async def test_a_body_of_too_many_objects_is_a_413(scene) -> None:
    chapters = [{"number": n} for n in range(10_001)]
    async with asyncio.timeout(5):  # a body that is expanded first takes minutes
        response = await scene.http.post(
            f"{scene.tenant}/books",
            json={**DUNE_BODY, "chapters": chapters},
            headers=scene.headers("ada"),
        )
    assert await slug_of(response, 413) == "payload-too-large", response.text


# --- every error is a problem -----------------------------------------------------------------


async def test_a_method_the_route_lacks_is_a_405_problem_with_the_allowed_methods(scene) -> None:
    response = await scene.http.patch(scene.book, json={}, headers=scene.headers("ada"))
    assert await slug_of(response, 405) == "method-not-allowed", response.text
    assert "GET" in response.headers["allow"], "the Allow header survives"


async def test_an_http_exception_of_a_consumer_route_is_a_problem(service, client) -> None:
    @service.app.get("/teapot")
    async def teapot() -> None:
        raise HTTPException(status_code=418, detail="secret detail")

    response = await client.get("/teapot")
    assert response.status_code == 418, response.text
    assert response.headers["content-type"] == "application/problem+json", "a problem"
    assert "secret detail" not in response.text, "no detail for what the caller cannot fix"


async def test_an_unexpected_error_is_a_500_problem_without_detail(service, client) -> None:
    @service.app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret detail")

    response = await client.get("/boom")
    assert response.status_code == 500, response.text
    assert response.headers["content-type"] == "application/problem+json", "a problem"
    assert "secret detail" not in response.text, "no detail for a fault of the service"


# --- the Link header ----------------------------------------------------------------------------


async def test_the_link_header_does_not_follow_the_host_header(scene) -> None:
    response = await scene.http.get(scene.book, headers=scene.headers("ada", Host="evil.example"))
    link = response.headers["link"]
    assert "evil.example" not in link, link
    assert link.startswith(f"<{SETTINGS.base}context.jsonld>"), "built from the service's base"


async def test_the_link_header_of_a_listing_does_not_follow_the_host_header(scene) -> None:
    response = await scene.http.get(
        f"{scene.tenant}/books", headers=scene.headers("ada", Host="evil.example")
    )
    assert "evil.example" not in response.headers["link"], response.headers["link"]


async def test_the_link_header_includes_the_prefix_the_service_is_mounted_under() -> None:
    toy = ToyService(mount="/v1")
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        made = await http.post("/v1/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
        book = await http.post(
            f"{made.headers['location']}/books", json=DUNE_BODY, headers=toy.bearer("ada")
        )
        link = book.headers["link"]
        context = await http.get("/v1/context.jsonld")
    assert link.startswith(f"<{SETTINGS.base}v1/context.jsonld>"), link
    assert context.status_code == 200, "and the route is where the link says"


# --- server faults are not the caller's ---------------------------------------------------------


async def test_a_sparql_error_from_a_template_is_a_500_without_detail(scene) -> None:
    scene.service.store.on("query", SparqlError("secret detail of a template"), after=0)
    response = await scene.http.get(scene.book, headers=scene.headers("ada"))
    assert await slug_of(response, 500) == "internal-error", response.text
    assert "secret" not in response.text, "no detail"


async def test_a_query_the_store_refuses_is_a_500_without_detail(scene) -> None:
    """The toolkit wrote every query it sends, so a store that finds one malformed is the service's fault."""
    scene.service.store.on("query", BadQuery("secret syntax error at line 3"), after=0)
    response = await scene.http.get(scene.book, headers=scene.headers("ada"))
    assert await slug_of(response, 500) == "internal-error", response.text
    assert "secret" not in response.text, "no detail"


async def test_a_record_the_service_cannot_decode_is_a_500_without_detail(scene) -> None:
    access = f"{scene.tenant_iri}/access"
    await scene.service.store.update(
        system_database_name(SETTINGS.prefix),
        f"INSERT DATA {{ GRAPH <{access}/graph> {{ <{access}> <{v.GRANTS}> [ <{ODRL}target> <{scene.tenant_iri}> ] }} }}",
    )
    response = await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))
    assert await slug_of(response, 500) == "internal-error", response.text
    assert "assignee" not in response.text, "no detail of the stored data"


# --- the IRIs of a path -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "aggregate_id",
    [
        "nope",
        pytest.param("898B0B0D-E7B5-4C3D-99E3-DB49565D00AA", id="upper-case-uuid"),
        "00000000",
        "a" * 200,
    ],
)
async def test_an_aggregate_id_that_is_no_uuid_is_a_404_before_any_store_call(
    scene, aggregate_id
) -> None:
    store = scene.service.store
    before = {op: len(store.sent(op)) for op in ("query", "update", "put_graph")}
    response = await scene.http.get(
        f"{scene.tenant}/books/{aggregate_id}", headers=scene.headers("ada")
    )
    assert await slug_of(response, 404) == "not-found", response.text
    assert before == {op: len(store.sent(op)) for op in before}, "the store was not asked"


async def test_a_tenant_id_that_is_no_uuid_is_a_404_before_any_store_call(scene) -> None:
    store = scene.service.store
    before = len(store.sent("query"))
    response = await scene.http.get("/libraries/nope/books", headers=scene.headers("ada"))
    assert await slug_of(response, 404) == "not-found", response.text
    assert before == len(store.sent("query")), "the store was not asked"


async def test_a_create_naming_an_iri_in_the_tenant_is_refused_and_nothing_is_there(scene) -> None:
    chosen = str(uuid4())
    response = await scene.http.post(
        f"{scene.tenant}/books",
        json={**DUNE_BODY, "id": f"{scene.tenant_iri}/books/{chosen}"},
        headers=scene.headers("ada"),
    )
    assert await slug_of(response, 422) == "invalid-body", response.text
    there = await scene.http.get(f"{scene.tenant}/books/{chosen}", headers=scene.headers("ada"))
    assert there.status_code == 404, "the chosen IRI was not used"


# --- the tenant listing asks the store a fixed number of questions -------------------------------


async def queries_of_a_listing(scene: Scene, tenants: int) -> int:
    for _ in range(tenants):
        made = await scene.http.post("/libraries", json=TENANT_BODY, headers=scene.headers("ada"))
        assert made.status_code == 201, made.text
    store = scene.service.store
    before = len(store.sent("query"))
    page = Page.model_validate(
        (await scene.http.get("/libraries", headers=scene.headers("ada"))).json()
    )
    assert page.total >= tenants, "the caller sees what it made"
    return len(store.sent("query")) - before


async def test_listing_tenants_costs_the_same_queries_however_many_there_are(scene) -> None:
    few = await queries_of_a_listing(scene, 1)
    many = await queries_of_a_listing(scene, 4)
    assert few == many, f"{few} queries for few tenants, {many} for many"
    assert many == 1, "one query loads the records"

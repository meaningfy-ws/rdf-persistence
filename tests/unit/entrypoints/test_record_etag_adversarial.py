"""The Record-ETag header, attacked through the routes: when it moves, when a refusal must not carry it."""

import pytest

from rdf_persistence import GrantSet
from rdf_persistence.domain.generated.rp_access import Action, Grant
from rdf_persistence.domain.media import JSON, TURTLE
from rdf_persistence.entrypoints.negotiation import RECORD_ETAG
from tests.toy_service import principal_of
from tests.unit.entrypoints.test_router import _rename


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

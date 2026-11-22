"""A tenant root that owns a part: the service mints the part's IRI on create and on the root's PUT (#276)."""

from tests.toy_service import TENANT_BODY

CHARTER = {"label": "Charter", "description": "Read freely."}


async def test_a_tenant_whose_root_owns_a_part_is_created_with_the_part_iri_minted(scene) -> None:
    body = {**TENANT_BODY, "root": {**TENANT_BODY["root"], "charter": CHARTER}}
    made = await scene.http.post("/libraries", json=body, headers=scene.headers("ada"))
    assert made.status_code == 201, made.text
    root = await scene.http.get(made.headers["location"], headers=scene.headers("ada"))
    charter = root.json()["charter"]
    assert charter["label"] == "Charter", "the part is stored with the root"
    assert charter["id"].startswith(made.json()["id"] + "/parts/"), (
        "the part template minted its IRI"
    )


async def test_a_root_put_with_a_new_part_mints_its_iri(scene) -> None:
    body = {"label": "Ghent", "description": "Books for all.", "city": "Ghent", "charter": CHARTER}
    put = await scene.http.put(
        scene.tenant, json=body, headers=scene.headers("ada", **{"If-Match": scene.root_etag})
    )
    assert put.status_code == 200, put.text
    root = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
    assert root.json()["charter"]["id"].startswith(scene.tenant_iri + "/parts/"), "minted"


async def test_a_tenant_create_refuses_a_part_iri_from_the_body(scene) -> None:
    part = {**CHARTER, "id": "http://example.org/elsewhere/charter"}
    body = {**TENANT_BODY, "root": {**TENANT_BODY["root"], "charter": part}}
    made = await scene.http.post("/libraries", json=body, headers=scene.headers("ada"))
    assert made.status_code == 422, "a client does not choose a part's IRI: the IRI policy does"

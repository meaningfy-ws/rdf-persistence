"""A tenant's one label, attacked through the routes: rename, root PUT, the label a book may keep."""

import pytest

from tests.toy_service import DUNE_BODY, TENANT_BODY
from tests.unit.api.tenant_requests import put_root, rename

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


# Class: a blank label ("" stands for "   ", which the same validator refuses).
@pytest.mark.parametrize("label", [""])
async def test_an_invalid_label_is_422_and_the_root_keeps_its_label(scene, label) -> None:
    response = await rename(scene, label, scene.access_etag)
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
    first = await put_root(scene, "Ghent", scene.root_etag)
    assert first.status_code == 200, "the first PUT is fresh"
    stale = await put_root(scene, "Ghent", scene.root_etag)
    assert stale.status_code == 409, "the second PUT used a spent ETag"


async def test_a_root_put_with_a_wrong_label_and_a_stale_if_match_is_refused_without_a_write(
    scene,
) -> None:
    assert (await put_root(scene, "Ghent", scene.root_etag)).status_code == 200, (
        "the first PUT is fresh"
    )
    refused = await put_root(scene, "Other", scene.root_etag)
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
    assert (await put_root(scene, "Ghent", scene.root_etag)).status_code == 200, (
        "the other tenant's rename did not reach this one"
    )
    assert other_root.status_code == 200, "the other tenant still reads"

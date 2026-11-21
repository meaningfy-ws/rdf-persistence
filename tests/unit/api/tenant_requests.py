"""The two requests that change a tenant's label, shared by the router tests that attack the one-label rule."""

import httpx

from tests.scene import Scene


async def rename(scene: Scene, label: str, etag: str) -> httpx.Response:
    """``PUT <tenant>/label`` as ada, with ``etag`` as the access record's version."""
    return await scene.http.put(
        f"{scene.tenant}/label",
        json={"label": label},
        headers=scene.headers("ada", **{"If-Match": etag}),
    )


async def put_root(scene: Scene, label: str, etag: str) -> httpx.Response:
    """``PUT <tenant>`` as ada, with ``label`` in the body and ``etag`` as the root's version."""
    body = {"label": label, "description": "Books for all.", "city": "Ghent"}
    return await scene.http.put(
        scene.tenant, json=body, headers=scene.headers("ada", **{"If-Match": etag})
    )

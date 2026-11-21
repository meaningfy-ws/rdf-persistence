"""The generic routes and the kit against comments (rp-discussion): no route for them, and a removal drops them."""

from rdflib import Literal, URIRef

from rdf_persistence.schema.services import vocabulary as v
from tests.scene import PROBLEMS, problem_of
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService
from tests.unit.collaboration.collaboration_data import OA, RP, SECRET, annotation, stored


async def test_the_kit_remove_with_files_drops_the_comments():
    toy = ToyService()
    async with toy.app.router.lifespan_context(toy.app), toy.client() as client:
        headers = toy.bearer("ada")
        path = (await client.post("/libraries", json=TENANT_BODY, headers=headers)).headers[
            "location"
        ]
        tenant = toy.kit.tenant_iri(path.rsplit("/", 1)[1])
        first = (await client.post(f"{path}/books", json=DUNE_BODY, headers=headers)).json()["id"]
        second = (await client.post(f"{path}/books", json=DUNE_BODY, headers=headers)).json()["id"]
        on_first, on_second = (
            str(toy.kit.iris.mint_aggregate(tenant, "rp-comment", "rp-comments")) for _ in range(2)
        )
        async with toy.kit.session(tenant, "ada") as session:
            for comment, target in ((on_first, first), (on_second, second)):
                await session.add_graph(
                    comment, annotation(comment, (v.HAS_TARGET, URIRef(target)))
                )
            old = (await session.get_graph(first))[2]
        await toy.kit.remove_with_files(tenant, "ada", first, old)
        async with toy.kit.session(tenant, "ada") as session:
            assert await stored(session, on_first, on_second) == [on_second], (
                "the comment on the removed aggregate is gone, the other stays"
            )


async def test_the_generic_router_has_no_route_for_comments_whatever_the_method():
    toy = ToyService()
    async with toy.app.router.lifespan_context(toy.app), toy.client() as client:
        headers = toy.bearer("ada")
        path = (await client.post("/libraries", json=TENANT_BODY, headers=headers)).headers[
            "location"
        ]
        tenant = toy.kit.tenant_iri(path.rsplit("/", 1)[1])
        book = (await client.post(f"{path}/books", json=DUNE_BODY, headers=headers)).json()["id"]
        comment = str(toy.kit.iris.mint_aggregate(tenant, "rp-comment", "rp-comments"))
        async with toy.kit.session(tenant, "ada") as session:
            await session.add_graph(
                comment,
                annotation(
                    comment,
                    (v.HAS_TARGET, URIRef(book)),
                    (OA.bodyValue, Literal(SECRET)),
                    (RP.audience, Literal("librarian")),
                ),
            )
        paths = [route.path for route in toy.app.routes if hasattr(route, "path")]
        assert not [p for p in paths if "rp-comments" in p], "no route names the comments path"
        uuid = comment.rsplit("/", 1)[1]
        seen = {}
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
            for url in (f"{path}/rp-comments", f"{path}/rp-comments/{uuid}"):
                response = await client.request(method, url, headers=headers, json={})
                seen[(method, url)] = response
        refusals = {404: f"{PROBLEMS}not-found", 405: f"{PROBLEMS}method-not-allowed"}
        wrong = {
            k: (r.status_code, None if k[0] == "HEAD" else problem_of(r).type)
            for k, r in seen.items()
            if r.status_code not in refusals
            or (k[0] != "HEAD" and problem_of(r).type != refusals[r.status_code])
        }
        assert wrong == {}, "no method on a comment path answers other than not found"
        assert not [k for k, r in seen.items() if SECRET in r.text], "the text is not served"

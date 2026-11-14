"""A generic aggregate route answers only for an aggregate of its own class (PD-30 item 1).

Under an IRI policy whose aggregate template names neither the type nor the path (``{tenant}/{id}``),
a comment and a book of the same id have one IRI, so the route of the books could read, replace or
delete a comment, and the route of the books could be asked about a shelf. The route refuses both
with 404, as it refuses a missing aggregate, and changes nothing.
"""

from collections.abc import AsyncIterator

import httpx
import pytest
from rdflib import RDF, URIRef

from rdf_persistence.domain.generated.service.rp_service import IriPolicy
from rdf_persistence.services.vocabulary import ANNOTATION, HAS_TARGET
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService

FLAT_POLICY = IriPolicy(aggregate_template="{tenant}/{id}")
JSON_LD = "application/ld+json"
TURTLE = "text/turtle"
SHELF_BODY = {"label": "Shelf", "description": "A shelf.", "member_class": "Book"}


@pytest.fixture
async def flat() -> AsyncIterator[ToyService]:
    toy = ToyService(iri_policy=FLAT_POLICY)
    async with toy.app.router.lifespan_context(toy.app):
        yield toy


async def stored_comment(toy: ToyService, tenant: str, target: str) -> tuple[str, str]:
    """A comment on ``target``, written the way the toolkit writes one: ``(its id in a path, its version)``."""
    comment = str(toy.kit.iris.mint_aggregate(tenant, "rp-comment", "rp-comments"))
    triples = [
        (URIRef(comment), RDF.type, ANNOTATION),
        (URIRef(comment), HAS_TARGET, URIRef(target)),
    ]
    async with toy.kit.session(tenant, "ada") as session:
        version = await session.add_graph(comment, triples)
    return comment.rsplit("/", 1)[1], version


async def tenant_of(toy: ToyService, http: httpx.AsyncClient) -> tuple[str, str]:
    """``(tenant path, tenant iri)`` of a new tenant."""
    made = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
    path = made.headers["location"]
    return path, str(toy.kit.tenant_iri(path.rsplit("/", 1)[1]))


@pytest.mark.parametrize("media_type", [JSON_LD, TURTLE])
async def test_a_comment_is_not_read_through_the_route_of_the_books(flat, media_type) -> None:
    async with flat.client() as http:
        path, tenant = await tenant_of(flat, http)
        book = (await http.post(f"{path}/books", json=DUNE_BODY, headers=flat.bearer("ada"))).json()
        comment, _ = await stored_comment(flat, tenant, book["id"])
        response = await http.get(
            f"{path}/books/{comment}", headers={**flat.bearer("ada"), "Accept": media_type}
        )
    assert response.status_code == 404, "no route of the books answers for a comment"


async def test_a_comment_is_neither_replaced_nor_deleted_through_the_route_of_the_books(
    flat,
) -> None:
    async with flat.client() as http:
        path, tenant = await tenant_of(flat, http)
        book = (await http.post(f"{path}/books", json=DUNE_BODY, headers=flat.bearer("ada"))).json()
        comment, version = await stored_comment(flat, tenant, book["id"])
        headers = {**flat.bearer("ada"), "If-Match": f'"{version}"'}
        replaced = await http.put(f"{path}/books/{comment}", json=DUNE_BODY, headers=headers)
        deleted = await http.delete(f"{path}/books/{comment}", headers=headers)
    assert (replaced.status_code, deleted.status_code) == (404, 404), "both refused as missing"
    async with flat.kit.session(tenant, "ada") as session:
        _, _, kept = await session.get_graph(f"{tenant}/{comment}")
    assert kept == version, "the comment is as it was"


async def test_a_shelf_is_not_answered_by_the_route_of_the_books(flat) -> None:
    async with flat.client() as http:
        path, _ = await tenant_of(flat, http)
        shelf = await http.post(f"{path}/shelves", json=SHELF_BODY, headers=flat.bearer("ada"))
        shelf_id = shelf.json()["id"].rsplit("/", 1)[1]
        headers = {**flat.bearer("ada"), "If-Match": shelf.headers["etag"]}
        read = await http.get(f"{path}/books/{shelf_id}", headers=flat.bearer("ada"))
        deleted = await http.delete(f"{path}/books/{shelf_id}", headers=headers)
        still = await http.get(f"{path}/shelves/{shelf_id}", headers=flat.bearer("ada"))
    assert (read.status_code, deleted.status_code) == (404, 404), "a shelf is no book"
    assert still.status_code == 200, "the shelf was not deleted"


@pytest.mark.parametrize("policy", [None, FLAT_POLICY], ids=["default", "flat"])
async def test_a_book_is_still_read_replaced_and_deleted_through_its_own_route(policy) -> None:
    toy = ToyService(iri_policy=policy)
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        path, _ = await tenant_of(toy, http)
        book = await http.post(f"{path}/books", json=DUNE_BODY, headers=toy.bearer("ada"))
        at = book.headers["location"]
        read = await http.get(at, headers=toy.bearer("ada"))
        replaced = await http.put(
            at, json=DUNE_BODY, headers={**toy.bearer("ada"), "If-Match": book.headers["etag"]}
        )
        deleted = await http.delete(
            at, headers={**toy.bearer("ada"), "If-Match": replaced.headers["etag"]}
        )
    assert [read.status_code, replaced.status_code, deleted.status_code] == [200, 200, 204]

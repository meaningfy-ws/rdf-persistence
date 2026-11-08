"""The end-to-end proof (task 5.7): the toy library served over Fuseki, Garage and Zitadel.

Real JWT access tokens of the machine users (JWT-profile grant) are verified against the Zitadel
container's keys. Only public names are used (``assert_public_imports`` checks this very file).
"""

import hashlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from rdflib import Graph
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence import Grant, GrantSet, Page, TenantCreate, TenantSummary
from rdf_persistence.testkit import TokenRefusedError, access_token, assert_public_imports
from tests.e2e.world import World, running_world
from tests.fixtures.library.generated.books import Book, Chapter, Genre, Note
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.scans import Scan
from tests.toy_service import body_of

JSON, JSON_LD, TURTLE = "application/json", "application/ld+json", "text/turtle"
LIBRARIAN, READER, OUTSIDER, ADMIN = "librarian", "reader", "outsider", "admin"
SCAN_BYTES = b"%PDF-1.7 a scanned copy of Dune"
SCAN_MEDIA_TYPE = "application/pdf"


def dune(label: str = "Dune") -> Book:
    note = Note.model_construct(label="Spice", description="The spice must flow.", text="Arrakis")
    chapter = Chapter.model_construct(number=1, notes=[note])
    return Book.model_construct(
        label=label,
        description="A planet.",
        genre=Genre.FICTION,
        authors=["Herbert"],
        chapters=[chapter],
    )


@pytest.fixture
async def world(fuseki, garage, zitadel_project) -> AsyncIterator[World]:
    async with running_world(fuseki, garage, zitadel_project) as running:
        yield running


@dataclass(frozen=True)
class Shelf:
    """A library the librarian made, with the reader granted ``reader``, and one book in it."""

    tenant: str
    path: str
    book: str
    book_iri: str
    etag: str


async def grants_of(world: World, tenant: str) -> tuple[GrantSet, str]:
    answer = await world.http.get(f"{tenant}/grants", headers=world.callers.as_(LIBRARIAN))
    assert answer.status_code == 200, answer.text
    return GrantSet.model_validate(answer.json()), answer.headers["etag"]


@pytest.fixture
async def shelf(world: World) -> Shelf:
    http, callers = world.http, world.callers
    root = body_of(Library.model_construct(description="Books for all.", city="Ghent"))
    created = await http.post(
        "/libraries",
        json=TenantCreate(label="Ghent", root=root).model_dump(mode="json"),
        headers=callers.as_(LIBRARIAN),
    )
    assert created.status_code == 201, created.text
    tenant_iri = TenantSummary.model_validate(created.json()).id
    path = created.headers["location"]
    granted, etag = await grants_of(world, path)
    readers = GrantSet(
        grants=[
            *(granted.grants or []),
            Grant(assignee=callers.principals[READER], target=tenant_iri, role=READER),
        ]
    )
    put = await http.put(
        f"{path}/grants",
        json=readers.model_dump(mode="json", exclude_none=True),
        headers=callers.as_(LIBRARIAN, **{"If-Match": etag}),
    )
    assert put.status_code == 200, put.text
    book = await http.post(f"{path}/books", json=body_of(dune()), headers=callers.as_(LIBRARIAN))
    assert book.status_code == 201, book.text
    return Shelf(
        tenant_iri, path, book.headers["location"], book.json()["id"], book.headers["etag"]
    )


async def triples(world: World, shelf: Shelf, who: str, media_type: str) -> Graph:
    """The book as ``who`` reads it in ``media_type``, parsed to RDF."""
    answer = await world.http.get(shelf.book, headers=world.callers.as_(who, Accept=media_type))
    assert answer.status_code == 200, f"{media_type}: {answer.text}"
    if media_type == TURTLE:
        return Graph().parse(data=answer.text, format="turtle")
    if media_type == JSON:  # plain JSON is JSON-LD with the context the Link header names
        context_url = answer.headers["link"].split(">")[0].lstrip("<")
        assert context_url.endswith("/context.jsonld"), "the Link names the generated context"
        context = (await world.http.get("/context.jsonld")).json()["@context"]
        document = {"@context": context, **answer.json()}
    else:
        document = answer.json()
    return Graph().parse(data=json.dumps(document), format="json-ld")


def assert_same_triples(left: Graph, right: Graph, what: str) -> None:
    only_left, only_right = graph_diff(left, right)[1:]
    assert isomorphic(left, right), (
        f"{what}: only left {sorted(only_left)}; only right {sorted(only_right)}"
    )


def test_this_file_and_the_composition_root_use_only_public_names() -> None:
    assert_public_imports(__file__)
    assert_public_imports(Path(__file__).with_name("library_app.py"))


async def test_the_book_is_the_same_three_ways(world, shelf) -> None:
    as_json = await triples(world, shelf, LIBRARIAN, JSON)
    assert_same_triples(as_json, await triples(world, shelf, LIBRARIAN, JSON_LD), "JSON vs JSON-LD")
    assert_same_triples(as_json, await triples(world, shelf, LIBRARIAN, TURTLE), "JSON vs Turtle")


async def test_a_reader_reads_the_book_the_librarian_made(world, shelf) -> None:
    reader = await triples(world, shelf, READER, TURTLE)
    assert_same_triples(
        reader, await triples(world, shelf, LIBRARIAN, TURTLE), "reader vs librarian"
    )


async def test_a_reader_may_not_modify_and_the_book_is_unchanged(world, shelf) -> None:
    before = await triples(world, shelf, LIBRARIAN, TURTLE)
    refused = await world.http.put(
        shelf.book,
        json=body_of(dune("Defaced")),
        headers=world.callers.as_(READER, **{"If-Match": shelf.etag}),
    )
    assert refused.status_code == 403, refused.text
    assert refused.headers["content-type"] == "application/problem+json", "a problem response"
    reread = await world.http.get(shelf.book, headers=world.callers.as_(LIBRARIAN))
    assert reread.headers["etag"] == shelf.etag, "the version is unchanged"
    assert_same_triples(before, await triples(world, shelf, LIBRARIAN, TURTLE), "after the refusal")


async def test_a_reader_may_not_delete_the_book(world, shelf) -> None:
    refused = await world.http.delete(
        shelf.book, headers=world.callers.as_(READER, **{"If-Match": shelf.etag})
    )
    assert refused.status_code == 403, refused.text


async def test_an_outsider_finds_neither_the_library_nor_its_book(world, shelf) -> None:
    for url in (shelf.path, shelf.book):
        answer = await world.http.get(url, headers=world.callers.as_(OUTSIDER))
        assert answer.status_code == 404, f"{url}: {answer.text}"


async def test_a_global_admin_reads_but_cannot_modify(world, shelf) -> None:
    read = await world.http.get(shelf.book, headers=world.callers.as_(ADMIN))
    assert read.status_code == 200, read.text
    refused = await world.http.put(
        shelf.book,
        json=body_of(dune("Defaced")),
        headers=world.callers.as_(ADMIN, **{"If-Match": shelf.etag}),
    )
    assert refused.status_code == 403, refused.text


async def test_a_stale_replace_is_409_and_the_current_etag_replaces(world, shelf) -> None:
    http, librarian = world.http, world.callers.as_(LIBRARIAN, **{"If-Match": shelf.etag})
    first = await http.put(shelf.book, json=body_of(dune("First")), headers=librarian)
    stale = await http.put(shelf.book, json=body_of(dune("Second")), headers=librarian)
    assert first.status_code == 200, first.text
    assert first.headers["etag"] != shelf.etag, "a new version"
    assert stale.status_code == 409, stale.text
    current = world.callers.as_(LIBRARIAN, **{"If-Match": first.headers["etag"]})
    third = await http.put(shelf.book, json=body_of(dune("Third")), headers=current)
    assert third.status_code == 200, third.text
    assert third.headers["etag"] not in (shelf.etag, first.headers["etag"]), "and another version"


async def test_a_scan_file_is_kept_in_the_tenants_bucket_and_referenced(world, shelf) -> None:
    http, callers = world.http, world.callers
    scan = Scan.model_construct(
        label="Dune, scanned",
        description="A scanned copy.",
        scan_of=shelf.book_iri,
        file_name="dune.pdf",
        media_type=SCAN_MEDIA_TYPE,
        byte_size=len(SCAN_BYTES),
        sha256=hashlib.sha256(SCAN_BYTES).hexdigest(),
    )
    created = await http.post(
        f"{shelf.path}/scans", json=body_of(scan), headers=callers.as_(LIBRARIAN)
    )
    assert created.status_code == 201, created.text
    name = created.headers["location"].rsplit("/", 1)[-1]
    file_url = f"{shelf.path}/scan-files/{name}"
    stored = await http.put(file_url, content=SCAN_BYTES, headers=callers.as_(LIBRARIAN))
    assert stored.status_code == 204, stored.text
    as_reader = await http.get(file_url, headers=callers.as_(READER))
    assert as_reader.content == SCAN_BYTES, "the reader gets the exact bytes"
    assert (await http.put(file_url, content=b"x", headers=callers.as_(READER))).status_code == 403
    assert (await http.get(file_url, headers=callers.as_(OUTSIDER))).status_code == 404
    (bucket,) = await world.files.list_buckets(f"{world.prefix}-")
    assert await world.files.get(bucket, name) == SCAN_BYTES, "and the bucket holds them"


async def test_a_disabled_service_account_is_refused_its_next_token(world) -> None:
    account = next(u for u in world.project.machine_users if u.name == READER)
    await world.identity.disable(account.user_id)
    try:
        with pytest.raises(TokenRefusedError):
            access_token(world.project, account)
    finally:
        await world.identity.enable(account.user_id)
    assert access_token(world.project, account), "enabled again, it is granted a token"


async def test_a_page_of_books(world, shelf) -> None:
    http, headers = world.http, world.callers.as_(LIBRARIAN)
    ids = [shelf.book_iri]
    for label in ("Emma", "Ulysses", "Kim"):
        added = await http.post(f"{shelf.path}/books", json=body_of(dune(label)), headers=headers)
        assert added.status_code == 201, added.text
        ids.append(added.json()["id"])
    answer = await http.get(f"{shelf.path}/books?limit=2&offset=2", headers=headers)
    assert answer.status_code == 200, answer.text
    page = Page.model_validate(answer.json())
    assert [item["id"] for item in page.items] == sorted(ids)[2:4], "third and fourth by IRI"
    assert (page.total, page.limit, page.offset) == (4, 2, 2), "the position in the whole listing"


async def test_deleting_the_book_and_the_library_removes_the_database_and_the_bucket(
    world, shelf
) -> None:
    http, callers, prefix = world.http, world.callers, f"{world.prefix}-"

    async def own_databases() -> list[str]:
        return [n for n in await world.store.list_datasets() if n.startswith(prefix)]

    assert len(await own_databases()) == 2, "the system database and the tenant's"
    assert len(await world.files.list_buckets(prefix)) == 1, "the tenant's bucket"

    gone = await http.delete(shelf.book, headers=callers.as_(LIBRARIAN, **{"If-Match": shelf.etag}))
    assert gone.status_code == 204, gone.text
    assert (await http.get(shelf.book, headers=callers.as_(LIBRARIAN))).status_code == 404

    _, record_etag = await grants_of(world, shelf.path)
    dropped = await http.delete(
        shelf.path, headers=callers.as_(LIBRARIAN, **{"If-Match": record_etag})
    )
    assert dropped.status_code == 204, dropped.text
    assert (await http.get(shelf.path, headers=callers.as_(READER))).status_code == 404
    assert len(await own_databases()) == 1, "only the system database remains"
    assert await world.files.list_buckets(prefix) == [], "the bucket is gone"

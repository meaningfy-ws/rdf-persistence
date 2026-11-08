"""The toy library served under the consumer's IRI policy against the real store (iri-policy 4.1).

Every IRI, path id and resource name follows the policy through create, read, list, replace, a
loaded graph and delete. Only public names are used (``assert_public_imports`` checks this file).
"""

import re
from collections.abc import AsyncIterator

import pytest

from rdf_persistence import RdfFormat, TenantCreate, TenantSummary
from rdf_persistence.testkit import assert_public_imports
from tests.e2e.test_library import LIBRARIAN, dune
from tests.e2e.world import World, running_world
from tests.fixtures.library.generated.library import Library
from tests.toy_service import CONSUMER_POLICY, body_of

BASE = "http://mwb.meaningfy.ws/"
DEPLOYMENT = "k3f9a2x"
ID = r"[a-z0-9]"
TURTLE = b'<http://mwb.meaningfy.ws/b> <http://purl.org/dc/terms/title> "Dune" .\n'


@pytest.fixture
async def world(fuseki, garage, zitadel_project) -> AsyncIterator[World]:
    async with running_world(
        fuseki,
        garage,
        zitadel_project,
        base=BASE,
        deployment=DEPLOYMENT,
        iri_policy=CONSUMER_POLICY,
    ) as running:
        yield running


def test_this_file_uses_only_public_names() -> None:
    assert_public_imports(__file__)


async def test_a_library_and_a_book_live_and_die_under_the_policy(world: World) -> None:
    http, headers = world.http, world.callers.as_(LIBRARIAN)
    root = body_of(Library.model_construct(description="Books for all.", city="Ghent"))
    created = await http.post(
        "/libraries",
        json=TenantCreate(label="Ghent", root=root).model_dump(mode="json"),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    tenant = TenantSummary.model_validate(created.json()).id
    assert re.fullmatch(f"{re.escape(BASE)}project/{ID}{{7}}", tenant)
    tenant_id = tenant[-7:]
    path = created.headers["location"]
    assert path == f"/libraries/{tenant_id}"

    name = f"{world.prefix}-t-{tenant_id}"
    assert name in await world.store.list_datasets(), "the tenant's database is named by its id"
    assert await world.files.list_buckets(f"{world.prefix}-") == [name], "and so is its bucket"

    added = await http.post(f"{path}/books", json=body_of(dune()), headers=headers)
    assert added.status_code == 201, added.text
    book = added.json()
    flat = f"{re.escape(BASE)}{tenant_id}/%s/{ID}{{13}}"
    assert re.fullmatch(flat % "book", book["id"])
    assert re.fullmatch(flat % "chapter", book["chapters"][0]["id"])
    book_path = added.headers["location"]
    assert book_path == f"{path}/books/{book['id'][-13:]}"

    read = await http.get(book_path, headers=headers)
    assert read.status_code == 200, read.text
    assert read.json()["id"] == book["id"]
    listing = await http.get(f"{path}/books", headers=headers)
    assert [item["id"] for item in listing.json()["items"]] == [book["id"]]

    replaced = await http.put(
        book_path,
        json={**read.json(), "label": "Dune Messiah"},
        headers={**headers, "If-Match": read.headers["etag"]},
    )
    assert replaced.status_code == 200, replaced.text
    assert (await http.get(book_path, headers=headers)).json()["label"] == "Dune Messiah"

    principal = world.callers.principals[LIBRARIAN]
    async with world.kit.session(tenant, principal) as session:
        loaded = await session.load_graph(book["id"], TURTLE, rdf_format=RdfFormat.TURTLE)
        graph, _, version = await session.get_graph(book["id"])
        await session.replace_graph(book["id"], graph, version, loaded_graphs=[loaded])
    assert re.fullmatch(flat % "content", str(loaded)), "a loaded graph is flat beside its book"
    held = f"ASK {{ GRAPH <{loaded}> {{ ?s ?p ?o }} }}"
    assert (await world.store.query(name, held)).askAnswer, "and holds the file's triples"

    etag = (await http.get(book_path, headers=headers)).headers["etag"]
    gone = await http.delete(book_path, headers={**headers, "If-Match": etag})
    assert gone.status_code == 204, gone.text
    assert (await http.get(book_path, headers=headers)).status_code == 404
    assert not (await world.store.query(name, held)).askAnswer, "the loaded graph goes with it"

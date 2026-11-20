"""TC-9: ``DELETE`` of a refusing class answers 409 ``in-use`` while another aggregate refers to it (E1 to E4, E8, E9).

A1 is an author (its class refuses deletion), B0 to B2 are books; ``ada`` is the tenant's creator, who
reads every aggregate unless a test bans her from one.
"""

import httpx
import pytest
from rdflib import URIRef

from rdf_persistence import Action, GrantSet
from rdf_persistence.access.domain.generated.rp_access import Prohibition
from rdf_persistence.api.entrypoints.generated.rp_api_entrypoints import InUseProblem
from rdf_persistence.core.domain.exceptions import InUse
from rdf_persistence.core.domain.media import JSON
from rdf_persistence.schema.services import vocabulary as v
from tests.toy import graph_of
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, assert_problem, principal_of
from tests.unit.api.scene import PROBLEMS
from tests.unit.collaboration.collaboration_data import annotation

AUTHOR_BODY = {"label": "Herbert", "description": "An author."}


class Library:
    """A tenant of ``ada`` with one author A1, and what the test adds to it."""

    def __init__(self, service: ToyService, http: httpx.AsyncClient) -> None:
        self.service, self.http = service, http
        self.headers = service.bearer("ada")
        self.path = ""
        self.tenant = ""
        self.author = ""

    async def set_up(self) -> "Library":
        made = await self.http.post("/libraries", json=TENANT_BODY, headers=self.headers)
        self.path = made.headers["location"]
        self.tenant = str(self.service.kit.tenant_iri(self.path.rsplit("/", 1)[1]))
        self.author = await self.post("authors", AUTHOR_BODY)
        return self

    async def post(self, collection: str, body: dict) -> str:
        made = await self.http.post(f"{self.path}/{collection}", json=body, headers=self.headers)
        assert made.status_code == 201, made.text
        return made.json()["id"]

    async def book(self, **slots: str) -> str:
        return await self.post("books", {**DUNE_BODY, **slots})

    async def ban_reading(self, iri: str) -> None:
        current = await self.http.get(f"{self.path}/grants", headers=self.headers)
        held = GrantSet.model_validate(current.json())
        ban = Prohibition(assignee=principal_of("ada"), target=graph_of(iri), action=Action.READ)
        put = await self.http.put(
            f"{self.path}/grants",
            content=GrantSet(grants=held.grants, prohibitions=[ban]).model_dump_json(
                exclude_none=True
            ),
            headers={**self.headers, "If-Match": current.headers["etag"], "Content-Type": JSON},
        )
        assert put.status_code == 200, put.text

    async def delete(self, iri: str, if_match: str | None = None) -> httpx.Response:
        url = f"{self.path}/{iri.rsplit('/', 2)[1]}/{iri.rsplit('/', 1)[1]}"
        if if_match is None:
            if_match = (await self.http.get(url, headers=self.headers)).headers["etag"]
        return await self.http.delete(url, headers={**self.headers, "If-Match": if_match})

    async def exists(self, iri: str) -> bool:
        url = f"{self.path}/{iri.rsplit('/', 2)[1]}/{iri.rsplit('/', 1)[1]}"
        return (await self.http.get(url, headers=self.headers)).status_code == 200


async def library(service: ToyService, client: httpx.AsyncClient) -> Library:
    return await Library(service, client).set_up()


def in_use(response: httpx.Response) -> InUseProblem:
    """The 409 body, which must be an ``in-use`` problem and validate as an ``InUseProblem``."""
    assert response.status_code == 409, response.text
    body = InUseProblem.model_validate(response.json())
    assert body.type == f"{PROBLEMS}in-use", f"the problem type: {body.type}"
    return body


def named(body: InUseProblem) -> list[tuple[str, str, str]]:
    return [(r.referrer, r.referrer_class, r.referrer_slot) for r in body.referrers or []]


async def test_a_book_that_refers_to_the_author_refuses_its_deletion(service, client):  # E1
    lib = await library(service, client)
    b1 = await lib.book(written_by=lib.author)

    refused = await lib.delete(lib.author)

    body = in_use(refused)
    assert named(body) == [(b1, "Book", "written_by")], "the readable referrer is named"
    assert (body.more_count, body.hidden_count) == (0, 0), "nothing is cut or hidden"
    assert await lib.exists(lib.author), "the author is still there"


async def test_a_referrer_the_caller_may_not_read_is_counted_not_named(service, client):  # E2
    lib = await library(service, client)
    b2 = await lib.book(written_by=lib.author)
    await lib.ban_reading(b2)

    refused = await lib.delete(lib.author)

    body = in_use(refused)
    assert named(body) == [], "the hidden referrer is not named"
    assert (body.more_count, body.hidden_count) == (0, 1), "it is counted"
    assert b2 not in refused.text, "its IRI does not leak"
    assert await lib.exists(lib.author), "the author is still there"


async def test_an_author_nothing_refers_to_is_deleted(service, client):  # E3
    lib = await library(service, client)

    removed = await lib.delete(lib.author)

    assert removed.status_code == 204, removed.text
    assert not await lib.exists(lib.author), "the author is gone"


async def test_a_book_another_book_is_the_sequel_of_is_still_deleted(service, client):  # E4
    lib = await library(service, client)
    b0 = await lib.book()
    await lib.book(sequel_of=b0)

    removed = await lib.delete(b0)

    assert removed.status_code == 204, removed.text
    assert not await lib.exists(b0), "a class that does not refuse is deleted as before"


async def test_a_shelf_naming_the_author_refuses_its_deletion(service, client):  # E8
    lib = await library(service, client)
    shelf = await lib.post(
        "shelves", {**AUTHOR_BODY, "member_class": "Author", "has_part": [lib.author]}
    )

    refused = await lib.delete(lib.author)

    body = in_use(refused)
    assert named(body) == [(shelf, "Shelf", "has_part")], "the collection link counts"


async def test_a_comment_on_the_author_goes_with_it(service, client):  # E9
    lib = await library(service, client)
    comment = str(service.kit.iris.mint_aggregate(lib.tenant, "rp-comment", "rp-comments"))
    async with service.kit.session(lib.tenant, principal_of("ada")) as session:
        await session.add_graph(comment, annotation(comment, (v.HAS_TARGET, URIRef(lib.author))))

    removed = await lib.delete(lib.author)

    assert removed.status_code == 204, removed.text
    async with service.kit.session(lib.tenant, principal_of("ada")) as session:
        assert not await session.heads([comment]), "the comment went with the author"


async def test_a_stale_version_is_a_conflict_not_in_use_even_with_a_referrer(service, client):
    lib = await library(service, client)
    await lib.book(written_by=lib.author)

    refused = await lib.delete(lib.author, if_match='"stale"')

    assert_problem(refused, 409, "conflict")


async def _kit_remove(service, lib: Library, **options) -> None:
    async with service.kit.session(lib.tenant, principal_of("ada")) as session:
        version = (await session.get_graph(lib.author))[2]
    await service.kit.remove_with_files(lib.tenant, "ada", lib.author, version, **options)


async def test_the_kit_removal_without_readable_refuses_with_an_unfiltered_error(service, client):
    # D-10: the handler answers such an error naming nobody (test_problems)
    lib = await library(service, client)
    await lib.book(written_by=lib.author)

    with pytest.raises(InUse) as refused:
        await _kit_remove(service, lib)

    assert refused.value.filtered is False, "no readable callable judged the referrers"
    assert await lib.exists(lib.author), "the author is still there"


async def test_the_kit_removal_with_readable_names_only_what_it_lets_through(service, client):
    # D-10
    lib = await library(service, client)
    seen = await lib.book(written_by=lib.author)
    unseen = await lib.book(written_by=lib.author)

    async def readable(_root, rows) -> set[str]:
        return {row[0] for row in rows} - {unseen}

    with pytest.raises(InUse) as refused:
        await _kit_remove(service, lib, readable=readable)

    assert refused.value.filtered is True, "the readable callable judged the referrers"
    assert [r[0] for r in refused.value.referrers] == [seen], "the readable one is named"
    assert refused.value.hidden_count == 1, "the other is only counted"

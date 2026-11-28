"""Aggregate validators through the service (aggregate-validators PD-2, PD-4, PD-8; A-1 to A-7)."""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest

from rdf_persistence import Action, InvalidBody, Refused, UnitOfWork
from rdf_persistence.collaboration.services.aggregate_validators import (
    AggregateReader,
    AggregateValidator,
    DeleteValidator,
)
from tests.fixtures.library.domain.generated.books import Shelf
from tests.scene import PROBLEMS, Scene, ban_reading, problem_of
from tests.toy import toy_mapper
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService

REFUSED = "a shelf holds one book at most"
SHELF_BODY = {"label": "Shelf", "description": "A shelf.", "member_class": "Book"}


def at_most_one_member(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
    if len(new.has_part or []) > 1:
        raise InvalidBody(REFUSED)


async def members_of_one_class(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
    """Refuse a shelf naming two members whose classes, as the reader gives them, are equal."""
    classes = [await reader.classes_of(member) for member in new.has_part or []]
    if len(classes) > 1 and len(set(classes)) == 1 and classes[0]:
        raise InvalidBody("the members are of one class")


class Seen:
    """A rule on books that keeps what the reader says of the shelf a book stands on."""

    def __init__(self) -> None:
        self.answers: list[frozenset[str]] = []

    async def __call__(self, old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        if new.shelf:
            self.answers.append(await reader.classes_of(new.shelf))


@asynccontextmanager
async def scene_with(
    aggregate_validators: Mapping[str, Sequence[AggregateValidator]] = {},
    delete_validators: Mapping[str, Sequence[DeleteValidator]] = {},
) -> AsyncIterator[Scene]:
    toy = ToyService(aggregate_validators=aggregate_validators, delete_validators=delete_validators)
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        yield await Scene.set_up(toy, http)


async def post(scene: Scene, collection: str, body: dict) -> httpx.Response:
    return await scene.http.post(
        f"{scene.tenant}/{collection}", json=body, headers=scene.headers("ada")
    )


async def shelf_listing(scene: Scene) -> list[str]:
    page = await scene.http.get(f"{scene.tenant}/shelves", headers=scene.headers("ada"))
    return [item["id"] for item in page.json()["items"]]


async def two_books(scene: Scene) -> list[str]:
    made = [await post(scene, "books", dict(DUNE_BODY)) for _ in range(2)]
    assert [m.status_code for m in made] == [201, 201], [m.text for m in made]
    return [m.json()["id"] for m in made]


async def test_a_refused_create_is_a_422_with_the_message_and_nothing_is_listed() -> None:  # A-1
    async with scene_with({"Shelf": [at_most_one_member]}) as scene:
        books = await two_books(scene)
        response = await post(scene, "shelves", {**SHELF_BODY, "has_part": books})
        assert (response.status_code, problem_of(response).type) == (
            422,
            f"{PROBLEMS}invalid-body",
        ), response.text
        assert REFUSED in response.text, "the rule's message is the answer's"
        assert await shelf_listing(scene) == [], "nothing was written"


async def test_a_refused_replace_is_a_422_and_the_stored_version_stays() -> None:  # A-2
    async with scene_with({"Shelf": [at_most_one_member]}) as scene:
        books = await two_books(scene)
        made = await post(scene, "shelves", {**SHELF_BODY, "has_part": books[:1]})
        assert made.status_code == 201, made.text
        url, etag = made.headers["location"], made.headers["etag"]
        response = await scene.http.put(
            url,
            json={**SHELF_BODY, "has_part": books},
            headers=scene.headers("ada", **{"If-Match": etag}),
        )
        assert response.status_code == 422, response.text
        assert REFUSED in response.text
        after = await scene.http.get(url, headers=scene.headers("ada"))
        assert after.headers["etag"] == etag, "the stored version is unchanged"


async def test_an_async_rule_reads_the_class_of_a_referenced_aggregate() -> None:  # A-3
    async with scene_with({"Shelf": [members_of_one_class]}) as scene:
        books = await two_books(scene)
        response = await post(scene, "shelves", {**SHELF_BODY, "has_part": books})
        assert response.status_code == 422, response.text
        assert "one class" in response.text
        one = await post(scene, "shelves", {**SHELF_BODY, "has_part": books[:1]})
        assert one.status_code == 201, "one member passes the same rule"


async def test_a_reference_the_writer_may_not_read_is_unknown_to_the_rule() -> None:  # A-4
    seen = Seen()
    async with scene_with({"Book": [seen]}) as scene:
        shelf = (await post(scene, "shelves", SHELF_BODY)).json()["id"]
        await post(scene, "books", {**DUNE_BODY, "shelf": shelf})
        assert seen.answers == [frozenset({"Shelf"})], "a reader of the shelf sees its class"
        await ban_reading(scene, shelf)
        await post(scene, "books", {**DUNE_BODY, "shelf": shelf})
        assert seen.answers[-1] == frozenset(), "the writer may not read the shelf"


async def test_a_unit_of_work_commit_is_refused_with_invalid_body_and_writes_nothing() -> None:
    async with scene_with({"Shelf": [at_most_one_member]}) as scene:  # A-5
        books = await two_books(scene)
        shelf = Shelf(
            id=f"{scene.tenant_iri}/shelves/00000000-0000-4000-8000-000000000001",
            label="Shelf",
            description="A shelf.",
            member_class="Book",
            has_part=books,
        )
        async with scene.service.kit.session(scene.tenant_iri, "ada") as session:
            work = UnitOfWork(session, toy_mapper())
            work.add(shelf)
            with pytest.raises(InvalidBody, match=REFUSED):
                await work.commit()
        assert await shelf_listing(scene) == []


async def test_a_transition_through_the_kit_has_its_reader_judged_by_the_caller() -> None:
    seen = Seen()  # A-5
    async with scene_with({"Book": [seen]}) as scene:
        shelf = (await post(scene, "shelves", SHELF_BODY)).json()["id"]
        book = (await post(scene, "books", {**DUNE_BODY, "shelf": shelf})).json()["id"]
        seen.answers.clear()
        await ban_reading(scene, shelf)
        tenant_id = scene.tenant.rsplit("/", 1)[1]
        authorised = await scene.service.kit.require(
            scene.headers("ada")["Authorization"], tenant_id, Action.READ
        )
        async with scene.service.kit.session(scene.tenant_iri, "ada") as session:
            version = (await session.get_graph(book))[2]
        async with scene.service.kit.collaboration(authorised) as collaboration:
            await collaboration.transition(book, "in_review", if_version=version)
        assert seen.answers == [frozenset()], "the rule ran on the move and the caller may not read"


async def refuses_a_forbidden_shelf(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
    shelf = await reader.aggregate(new.shelf) if new.shelf else None
    if shelf is not None and shelf.label == "forbidden":
        raise InvalidBody("the shelf is forbidden")


async def test_a_rule_reads_the_aggregate_a_book_names_through_the_generic_route() -> None:  # T1
    async with scene_with({"Book": [refuses_a_forbidden_shelf]}) as scene:
        bad = (await post(scene, "shelves", {**SHELF_BODY, "label": "forbidden"})).json()["id"]
        good = (await post(scene, "shelves", SHELF_BODY)).json()["id"]
        refused = await post(scene, "books", {**DUNE_BODY, "shelf": bad})
        assert refused.status_code == 422, refused.text
        assert "the shelf is forbidden" in refused.text, "the rule's message is the answer's"
        accepted = await post(scene, "books", {**DUNE_BODY, "shelf": good})
        assert accepted.status_code == 201, accepted.text


async def test_a_shelf_the_caller_may_not_read_is_none_to_the_rule_not_a_refusal() -> None:  # T2
    async with scene_with({"Book": [refuses_a_forbidden_shelf]}) as scene:
        bad = (await post(scene, "shelves", {**SHELF_BODY, "label": "forbidden"})).json()["id"]
        await ban_reading(scene, bad)
        response = await post(scene, "books", {**DUNE_BODY, "shelf": bad})
        assert response.status_code == 201, "the hidden shelf reads as a missing one"


def test_a_class_name_that_is_not_a_root_stops_the_start_up_naming_it() -> None:  # A-6
    with pytest.raises(ValueError, match="Chapter"):
        ToyService(aggregate_validators={"Chapter": [at_most_one_member]})


async def test_without_validators_a_shelf_is_written_as_before() -> None:  # A-7
    toy = ToyService()
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        scene = await Scene.set_up(toy, http)
        books = await two_books(scene)
        made = await post(scene, "shelves", {**SHELF_BODY, "has_part": books})
        assert made.status_code == 201, made.text


async def test_a_rename_hands_the_callers_reader_to_the_rule_of_the_tenant_root() -> None:
    answers: list[frozenset[str]] = []
    book_iri = ""

    async def looks_at_the_book(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        if old is not None:  # the scene's own creation runs the rule too
            answers.append(await reader.classes_of(book_iri))

    async with scene_with({"Library": [looks_at_the_book]}) as scene:
        book_iri = scene.book_iri
        await ban_reading(scene, book_iri)
        rename = await scene.http.put(
            f"{scene.tenant}/label",
            json={"label": "Bruges"},
            headers=scene.headers("ada", **{"If-Match": scene.access_etag}),
        )
        assert rename.status_code == 200, rename.text
        assert answers == [frozenset()], "the caller may not read the book"


async def test_a_rule_on_the_tenant_root_class_refuses_a_root_put_with_a_422() -> None:  # A-7
    def no_bruges(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        if new.city == "Bruges":
            raise InvalidBody("not Bruges")

    async with scene_with({"Library": [no_bruges]}) as scene:
        body = {"label": "Ghent", "description": "Books for all.", "city": "Bruges"}
        headers = scene.headers("ada", **{"If-Match": scene.root_etag})
        response = await scene.http.put(scene.tenant, json=body, headers=headers)
        assert response.status_code == 422, response.text
        assert "not Bruges" in response.text
        root = await scene.http.get(scene.tenant, headers=scene.headers("ada"))
        assert root.headers["etag"] == scene.root_etag, "the root is as it was"


async def test_a_rule_refusing_the_tenant_root_on_create_is_a_422_and_leaves_nothing() -> None:
    # S4, D-10: the create drops the database and the bucket it made
    def refuses_a_create(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        if old is None:
            raise InvalidBody("no new libraries")

    toy = ToyService(aggregate_validators={"Library": [refuses_a_create]})
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        databases = await toy.store.list_datasets()
        buckets = await toy.files.list_buckets("")
        response = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
        assert (response.status_code, problem_of(response).type) == (
            422,
            f"{PROBLEMS}invalid-body",
        ), response.text
        assert "no new libraries" in response.text, "the rule's message is the answer's"
        assert "location" not in response.headers, "no tenant is announced"
        assert await toy.store.list_datasets() == databases, "the database was dropped"
        assert await toy.files.list_buckets("") == buckets, "the bucket was dropped"
        listing = await http.get("/libraries", headers=toy.bearer("ada"))
        assert listing.json()["items"] == [], "no tenant is served"


# Delete rules through the generic route (aggregate-guards D-5 to D-8: T8, T9, T13, T15)

ON_LOAN = "on loan"  # the toy book has no status: its description stands for one


def not_while_on_loan(old: Any, who: Any, reader: AggregateReader) -> None:
    if old.description == ON_LOAN:
        raise Refused(f"{old.id} is on loan; return it before deleting it")


async def delete(scene: Scene, url: str, etag: str) -> httpx.Response:
    return await scene.http.delete(url, headers=scene.headers("ada", **{"If-Match": etag}))


@pytest.mark.parametrize(
    ("description", "status"),
    [(ON_LOAN, 409), ("shelved", 204)],
    ids=["on-loan-refused", "shelved-removed"],
)  # T8, T9
async def test_a_delete_rule_answers_a_409_and_keeps_the_book(
    description: str, status: int
) -> None:
    async with scene_with(delete_validators={"Book": [not_while_on_loan]}) as scene:
        made = await post(scene, "books", {**DUNE_BODY, "description": description})
        assert made.status_code == 201, made.text
        url, etag = made.headers["location"], made.headers["etag"]
        response = await delete(scene, url, etag)
        assert response.status_code == status, response.text
        after = await scene.http.get(url, headers=scene.headers("ada"))
        if status == 409:
            problem = problem_of(response)
            assert problem.type == f"{PROBLEMS}refused", "a refused problem"
            assert "is on loan; return it before deleting it" in (problem.detail or ""), (
                "the rule's message is the problem's detail"
            )
            stale = await delete(scene, url, '"stale"')
            assert problem_of(stale).type == f"{PROBLEMS}conflict", "a version conflict"
            assert problem_of(stale).detail is None, "a version conflict sends no text"
            assert (after.status_code, after.headers["etag"]) == (200, etag), "stored, unchanged"
        else:
            assert after.status_code == 404, "the book is gone"


@pytest.mark.parametrize("readable", [True, False], ids=["readable", "hidden"])  # T15, E2
async def test_a_delete_rule_reads_only_what_the_caller_may_read(readable: bool) -> None:
    seen: list[bool] = []

    async def looks_at_the_shelf(old: Any, who: Any, reader: AggregateReader) -> None:
        seen.append(await reader.aggregate(old.shelf) is not None)

    async with scene_with(delete_validators={"Book": [looks_at_the_shelf]}) as scene:
        shelf = (await post(scene, "shelves", SHELF_BODY)).json()["id"]
        made = await post(scene, "books", {**DUNE_BODY, "shelf": shelf})
        if not readable:
            await ban_reading(scene, shelf)
        response = await delete(scene, made.headers["location"], made.headers["etag"])
        assert response.status_code == 204, response.text
        assert seen == [readable], "the shelf is seen only if the caller may read it"


@pytest.mark.parametrize("readable", [True, False], ids=["readable", "hidden"])  # T15, R2-W1
async def test_a_delete_rule_reached_through_remove_with_files_reads_only_what_the_caller_may_read(
    readable: bool,
) -> None:
    seen: list[bool] = []

    async def looks_at_the_shelf(old: Any, who: Any, reader: AggregateReader) -> None:
        seen.append(await reader.aggregate(old.shelf) is not None)

    async with scene_with(delete_validators={"Book": [looks_at_the_shelf]}) as scene:
        shelf = (await post(scene, "shelves", SHELF_BODY)).json()["id"]
        book = (await post(scene, "books", {**DUNE_BODY, "shelf": shelf})).json()["id"]
        async with scene.service.kit.session(scene.tenant_iri, "ada") as session:
            version = (await session.get_graph(book))[2]
        await scene.service.kit.remove_with_files(
            scene.tenant_iri, "ada", book, version, may_read=lambda iri: readable
        )
        assert seen == [readable], "the shelf is seen only if the caller may read it"


def test_a_delete_rule_key_that_is_not_a_root_stops_the_start_up_naming_it() -> None:  # T13
    with pytest.raises(ValueError, match="Chapter"):
        ToyService(delete_validators={"Chapter": [not_while_on_loan]})

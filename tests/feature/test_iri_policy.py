"""Steps of ``iri_policy.feature``: the toy library served end to end with the fakes (iri-policy 3.4)."""

import asyncio
import re

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from rdf_persistence.core.domain.media import JSON
from tests.toy_service import DUNE_BODY, EXAMPLE_POLICY, TENANT_BODY, ToyService

scenarios("iri_policy.feature")

BASE = "https://example.org/library/"
ID = r"[a-z0-9]"


class Run:
    """One service and what the scenario has seen of it so far."""

    def __init__(self) -> None:
        self.toy = ToyService(iri_policy=EXAMPLE_POLICY)
        asyncio.run(self.toy.kit.tenancy.ensure_system_database())
        self.headers = self.toy.bearer("ada")
        self.last: httpx.Response | None = None
        self.tenant: httpx.Response | None = None
        self.book: httpx.Response | None = None

    def call(self, method: str, url: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            async with self.toy.client() as http:
                return await http.request(method, url, headers=self.headers, **kwargs)

        self.last = asyncio.run(send())
        return self.last

    @property
    def book_path(self) -> str:
        assert self.book is not None, "the book was created"
        return self.book.headers["location"]


@pytest.fixture
def run() -> Run:
    return Run()


@given("the library service runs under the example policy")
def _service(run: Run) -> None:
    assert run.toy.kit.iris.settings.iri_policy == EXAMPLE_POLICY, (
        "the service runs under the example policy"
    )


@when("Ada creates a library")
def _create_library(run: Run) -> None:
    run.tenant = run.call("POST", "/libraries", json=TENANT_BODY)
    assert run.tenant.status_code == 201, run.tenant.text


@then(parsers.parse('the library IRI is under "{segment}" and ends in a 7-character id'))
def _library_iri(run: Run, segment: str) -> None:
    assert run.tenant is not None, "the library was created"
    assert re.fullmatch(f"{re.escape(BASE)}{segment}{ID}{{7}}", run.tenant.json()["id"]), (
        "the library IRI is the library path and a short id"
    )


@then("its Location path ends in that id")
def _library_location(run: Run) -> None:
    assert run.tenant is not None, "the library was created"
    assert run.tenant.headers["location"] == "/libraries/" + run.tenant.json()["id"][-7:], (
        "the library's location is its short id"
    )


@when("Ada adds a book with a chapter to it")
def _add_book(run: Run) -> None:
    assert run.tenant is not None, "the library was created"
    run.book = run.call("POST", f"{run.tenant.headers['location']}/books", json=DUNE_BODY)
    assert run.book.status_code == 201, run.book.text


def _tenant_id(run: Run) -> str:
    assert run.tenant is not None, "the library was created"
    return run.tenant.json()["id"][-7:]


@then(parsers.parse('the book IRI is flat beside the library id under "{kind}"'))
def _book_iri(run: Run, kind: str) -> None:
    assert run.book is not None, "the book was created"
    assert re.fullmatch(
        f"{re.escape(BASE)}{_tenant_id(run)}/{kind}/{ID}{{13}}", run.book.json()["id"]
    ), "the book IRI has the flat shape of the policy"


@then(parsers.parse('the chapter IRI is flat beside the library id under "{kind}"'))
def _chapter_iri(run: Run, kind: str) -> None:
    assert run.book is not None, "the book was created"
    chapter = run.book.json()["chapters"][0]["id"]
    assert re.fullmatch(f"{re.escape(BASE)}{_tenant_id(run)}/{kind}/{ID}{{13}}", chapter), (
        "the chapter IRI has the flat shape of the policy"
    )


@then("the book Location path ends in the book id")
def _book_location(run: Run) -> None:
    assert run.book is not None, "the book was created"
    assert run.book_path == f"/libraries/{_tenant_id(run)}/books/{run.book.json()['id'][-13:]}", (
        "the book's location is the library and its short id"
    )


@then("reading the book answers its IRI and its chapter")
def _read_book(run: Run) -> None:
    assert run.book is not None, "the book was created"
    body = run.call("GET", run.book_path).json()
    assert body["id"] == run.book.json()["id"], "the book read back has the same IRI"
    assert [c["id"] for c in body["chapters"]] == [c["id"] for c in run.book.json()["chapters"]], (
        "the book read back has the same chapters"
    )


@then("listing the books answers the book")
def _list_books(run: Run) -> None:
    assert run.book is not None, "the book was created"
    listing = run.call("GET", run.book_path.rsplit("/", 1)[0]).json()
    assert [item["id"] for item in listing["items"]] == [run.book.json()["id"]], (
        "the listing holds the created book"
    )


@when("Ada replaces the book with a new label")
def _replace_book(run: Run) -> None:
    current = run.call("GET", run.book_path)
    body = {**current.json(), "label": "Dune Messiah"}
    run.headers = {**run.headers, "If-Match": current.headers["etag"], "Content-Type": JSON}
    replaced = run.call("PUT", run.book_path, json=body)
    assert replaced.status_code == 200, replaced.text
    run.headers = {k: v for k, v in run.headers.items() if k not in ("If-Match", "Content-Type")}


@then("reading the book answers the new label")
def _read_new_label(run: Run) -> None:
    assert run.call("GET", run.book_path).json()["label"] == "Dune Messiah", (
        "the new label is read back"
    )


@when("Ada deletes the book")
def _delete_book(run: Run) -> None:
    etag = run.call("GET", run.book_path).headers["etag"]
    run.headers = {**run.headers, "If-Match": etag}
    assert run.call("DELETE", run.book_path).status_code == 204, (
        "the delete is answered with no content"
    )
    run.headers = {k: v for k, v in run.headers.items() if k != "If-Match"}


@then("reading the book answers 404")
def _book_gone(run: Run) -> None:
    assert run.call("GET", run.book_path).status_code == 404, "the deleted book is gone"


@when(parsers.parse('Ada reads "{path}"'))
def _read(run: Run, path: str) -> None:
    run.call("GET", path)


@then(parsers.parse("the answer is {status:d}"))
def _answer(run: Run, status: int) -> None:
    assert run.last is not None, "a call was answered"
    assert run.last.status_code == status, "the answer has the expected status"

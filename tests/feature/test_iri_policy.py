"""Steps of ``iri_policy.feature``: the toy library served end to end with the fakes (iri-policy 3.4)."""

import asyncio
import re

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from rdf_persistence.domain.media import JSON
from tests.toy_service import CONSUMER_POLICY, DUNE_BODY, TENANT_BODY, ToyService

scenarios("iri_policy.feature")

BASE = "https://example.org/library/"
ID = r"[a-z0-9]"


class Run:
    """One service and what the scenario has seen of it so far."""

    def __init__(self) -> None:
        self.toy = ToyService(iri_policy=CONSUMER_POLICY)
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
        assert self.book is not None
        return self.book.headers["location"]


@pytest.fixture
def run() -> Run:
    return Run()


@given("the library service runs under the project policy")
def _service(run: Run) -> None:
    assert run.toy.kit.iris.settings.iri_policy == CONSUMER_POLICY


@when("Ada creates a library")
def _create_library(run: Run) -> None:
    run.tenant = run.call("POST", "/libraries", json=TENANT_BODY)
    assert run.tenant.status_code == 201, run.tenant.text


@then(parsers.parse('the library IRI is under "{segment}" and ends in a 7-character id'))
def _library_iri(run: Run, segment: str) -> None:
    assert run.tenant is not None
    assert re.fullmatch(f"{re.escape(BASE)}{segment}{ID}{{7}}", run.tenant.json()["id"])


@then("its Location path ends in that id")
def _library_location(run: Run) -> None:
    assert run.tenant is not None
    assert run.tenant.headers["location"] == "/libraries/" + run.tenant.json()["id"][-7:]


@when("Ada adds a book with a chapter to it")
def _add_book(run: Run) -> None:
    assert run.tenant is not None
    run.book = run.call("POST", f"{run.tenant.headers['location']}/books", json=DUNE_BODY)
    assert run.book.status_code == 201, run.book.text


def _tenant_id(run: Run) -> str:
    assert run.tenant is not None
    return run.tenant.json()["id"][-7:]


@then(parsers.parse('the book IRI is flat beside the library id under "{kind}"'))
def _book_iri(run: Run, kind: str) -> None:
    assert run.book is not None
    assert re.fullmatch(
        f"{re.escape(BASE)}{_tenant_id(run)}/{kind}/{ID}{{13}}", run.book.json()["id"]
    )


@then(parsers.parse('the chapter IRI is flat beside the library id under "{kind}"'))
def _chapter_iri(run: Run, kind: str) -> None:
    assert run.book is not None
    chapter = run.book.json()["chapters"][0]["id"]
    assert re.fullmatch(f"{re.escape(BASE)}{_tenant_id(run)}/{kind}/{ID}{{13}}", chapter)


@then("the book Location path ends in the book id")
def _book_location(run: Run) -> None:
    assert run.book is not None
    assert run.book_path == f"/libraries/{_tenant_id(run)}/books/{run.book.json()['id'][-13:]}"


@then("reading the book answers its IRI and its chapter")
def _read_book(run: Run) -> None:
    assert run.book is not None
    body = run.call("GET", run.book_path).json()
    assert body["id"] == run.book.json()["id"]
    assert [c["id"] for c in body["chapters"]] == [c["id"] for c in run.book.json()["chapters"]]


@then("listing the books answers the book")
def _list_books(run: Run) -> None:
    assert run.book is not None
    listing = run.call("GET", run.book_path.rsplit("/", 1)[0]).json()
    assert [item["id"] for item in listing["items"]] == [run.book.json()["id"]]


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
    assert run.call("GET", run.book_path).json()["label"] == "Dune Messiah"


@when("Ada deletes the book")
def _delete_book(run: Run) -> None:
    etag = run.call("GET", run.book_path).headers["etag"]
    run.headers = {**run.headers, "If-Match": etag}
    assert run.call("DELETE", run.book_path).status_code == 204
    run.headers = {k: v for k, v in run.headers.items() if k != "If-Match"}


@then("reading the book answers 404")
def _book_gone(run: Run) -> None:
    assert run.call("GET", run.book_path).status_code == 404


@when(parsers.parse('Ada reads "{path}"'))
def _read(run: Run, path: str) -> None:
    run.call("GET", path)


@then(parsers.parse("the answer is {status:d}"))
def _answer(run: Run, status: int) -> None:
    assert run.last is not None and run.last.status_code == status

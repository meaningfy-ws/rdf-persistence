"""Steps of ``consumer_write_rules.feature``: the toy service's held-isbn rule, over the generic API and over the testkit's reader
(consumer-write-rules 2.4; TC-9, TC-12, worked examples 1 and 2).

Scenarios 1 to 3 run the toy service on the fakes through its HTTP routes; scenario 4 calls the rule over a ``FakeAggregateReader``.
"""

import asyncio
from collections.abc import Awaitable
from contextlib import AsyncExitStack
from typing import Any

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from rdf_persistence import Action, GrantSet, RuleRefusal, aggregate_rules
from rdf_persistence.access.domain.generated.rp_access import Prohibition
from rdf_persistence.core.domain.media import JSON
from rdf_persistence.testkit import FakeAggregateReader
from tests.fixtures.library.domain.generated.books import Book
from tests.fixtures.library.services.generated.library_problems import HeldKeyProblem
from tests.scene import Scene
from tests.toy import book_iri, dune, graph_of
from tests.toy_service import (
    DUNE_BODY,
    HELD,
    TENANT_BODY,
    ToyService,
    held_isbn,
    principal_of,
)

scenarios("consumer_write_rules.feature")


class Run:
    """One toy service with the rule, a scene on it, and what the scenario has done so far."""

    def __init__(self) -> None:
        self.runner = asyncio.Runner()
        self.stack = AsyncExitStack()
        self.toy = ToyService(
            aggregate_validators=dict([aggregate_rules(Book, held_isbn)]),
            refusal_problems=(HeldKeyProblem,),
        )
        self.scene: Scene
        self.stored = ""
        self.answer: httpx.Response
        self.other_tenant = ""
        self.other_book = ""
        self.reader: FakeAggregateReader
        self.refusal: RuleRefusal | None = None

    def go[T](self, work: Awaitable[T]) -> T:
        return self.runner.run(work)  # type: ignore[arg-type]

    async def start(self) -> None:
        await self.stack.enter_async_context(self.toy.app.router.lifespan_context(self.toy.app))
        http = await self.stack.enter_async_context(self.toy.client())
        self.scene = await Scene.set_up(self.toy, http)

    async def create(self, isbn: str, tenant: str | None = None) -> httpx.Response:
        return await self.scene.http.post(
            f"{tenant or self.scene.tenant}/books",
            json={**DUNE_BODY, "isbn": isbn},
            headers=self.scene.headers("ada"),
        )

    async def books_in(self, tenant: str) -> list[Any]:
        listed = await self.scene.http.get(f"{tenant}/books", headers=self.scene.headers("ada"))
        assert listed.status_code == 200, listed.text
        return listed.json()["items"]

    async def ban_reading(self, iri: str) -> None:
        scene = self.scene
        grants = await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))
        held = GrantSet.model_validate(grants.json())
        ban = Prohibition(assignee=principal_of("ada"), target=graph_of(iri), action=Action.READ)
        put = await scene.http.put(
            f"{scene.tenant}/grants",
            content=GrantSet(grants=held.grants, prohibitions=[ban]).model_dump_json(
                exclude_none=True
            ),
            headers=scene.headers(
                "ada", **{"If-Match": grants.headers["etag"], "Content-Type": JSON}
            ),
        )
        assert put.status_code == 200, put.text

    def close(self) -> None:
        self.go(self.stack.aclose())
        self.runner.close()


@pytest.fixture
def run():
    current = Run()
    yield current
    current.close()


@given("the toy service with the held-isbn rule and HeldKeyProblem registered")
def _service(run: Run) -> None:
    run.go(run.start())


@given("a tenant where the writer may write books")
def _tenant(run: Run) -> None:
    assert run.scene.tenant, "the scene made a tenant, whose librarian is the writer"


@given(parsers.parse('a stored book with isbn "{isbn}"'))
def _stored(run: Run, isbn: str) -> None:
    made = run.go(run.create(isbn))
    assert made.status_code == 201, made.text
    run.stored = made.json()["id"]


@given(parsers.parse('a stored book with isbn "{isbn}" that the writer may not read'))
def _stored_unreadable(run: Run, isbn: str) -> None:
    _stored(run, isbn)
    run.go(run.ban_reading(run.stored))


@given(parsers.parse('a book with isbn "{isbn}" stored only in another tenant'))
def _stored_elsewhere(run: Run, isbn: str) -> None:
    other = run.go(
        run.scene.http.post("/libraries", json=TENANT_BODY, headers=run.scene.headers("ada"))
    )
    assert other.status_code == 201, other.text
    run.other_tenant = other.headers["location"]
    made = run.go(run.create(isbn, run.other_tenant))
    assert made.status_code == 201, made.text
    run.other_book = made.json()["id"]


@when(parsers.re(r'the writer creates (?:another|a) book with isbn "(?P<isbn>[^"]*)"'))
def _writer_creates(run: Run, isbn: str) -> None:
    run.answer = run.go(run.create(isbn))


@then("the answer is 409 with the problem type of HeldKeyProblem")
def _held_problem(run: Run) -> None:
    assert run.answer.status_code == 409, run.answer.text
    assert HeldKeyProblem.model_validate(run.answer.json()).type == HELD, "the consumer's problem"


@then("the problem's holder is the stored book")
def _holder(run: Run) -> None:
    assert run.answer.json()["holder"] == run.stored, "the holder the rule found"


@then("no second book is stored")
def _no_second(run: Run) -> None:
    held = [book["id"] for book in run.go(run.books_in(run.scene.tenant))]
    assert held.count(run.stored) == 1, "the stored book is still there"
    assert len(held) == 2, f"the scene's own book and the stored one, no more: {held}"


@then("the rule finds no holder and the book is created")
def _created(run: Run) -> None:
    assert run.answer.status_code == 201, run.answer.text
    assert run.other_book not in run.answer.text, "the other tenant's book is not named"


@then("the rule finds no holder")
def _no_holder(run: Run) -> None:
    assert run.stored not in run.answer.text, "the unreadable book is nowhere in the answer"
    assert run.answer.json().get("type") != HELD, "the held-isbn rule did not refuse"


@then("the answer is the key-conflict problem, which names no holder")
def _key_conflict(run: Run) -> None:
    assert run.answer.status_code == 409, run.answer.text
    problem = run.answer.json()
    assert problem["type"].endswith("problems/key-conflict"), f"the problem type: {problem['type']}"
    assert "holder" not in problem, "the toolkit's problem names no holder"


@given(
    parsers.parse(
        'a fake reader seeded with two books with isbn "{isbn}", one unreadable by the writer'
    )
)
def _fake_reader(run: Run, isbn: str) -> None:
    seeded = [dune(book_iri(1), chapters=0, isbn=isbn), dune(book_iri(2), chapters=0, isbn=isbn)]
    run.reader = FakeAggregateReader(seeded, roots=[Book], unreadable=[book_iri(2)])


@when(parsers.parse('the held-isbn rule is called for a new book with isbn "{isbn}"'))
def _rule_called(run: Run, isbn: str) -> None:
    new = dune(book_iri(3), chapters=0, isbn=isbn)
    try:
        run.go(held_isbn(None, new, principal_of("ada"), run.reader))  # type: ignore[arg-type]
    except RuleRefusal as refusal:
        run.refusal = refusal


@then("it refuses naming only the readable book")
def _names_readable(run: Run) -> None:
    assert run.refusal is not None, "the rule refused"
    problem = run.refusal.problem
    assert isinstance(problem, HeldKeyProblem), f"the consumer's problem: {problem!r}"
    assert problem.holder == book_iri(1), "the readable book, and only it"


@then(parsers.parse('the fake reader recorded one find call for Book with isbn "{isbn}"'))
def _one_find(run: Run, isbn: str) -> None:
    assert run.reader.calls == [("find", (Book,), {"isbn": isbn})], "one find, as the rule made it"

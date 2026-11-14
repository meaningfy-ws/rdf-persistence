"""Steps of ``schema_migrations.feature``: the toy library served with the fakes (schema-migrations 2.3, TC-34, TC-37)."""

import asyncio

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.migration_runner import stamps
from rdf_persistence.testkit import FakeStore
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService

scenarios("schema_migrations.feature")

LIBRARY_SCHEMA = "https://example.org/ns/library"
TOOLKIT_SCHEMA = "https://meaningfy.ws/ns/rdf-persistence"


class Run:
    """The store the scenario shares across service starts, and what it has seen so far."""

    def __init__(self) -> None:
        self.store = FakeStore()
        self.toy = ToyService(self.store)
        self.libraries: dict[str, tuple[str, str]] = {}  # owner to (library path, book path)
        self.last: httpx.Response | None = None
        self.held: dict[str, str] = {}

    def run(self, work):
        return asyncio.run(work)

    async def _send(self, method: str, url: str, owner: str, **kwargs) -> httpx.Response:
        async with self.toy.client() as http:
            return await http.request(method, url, headers=self.toy.bearer(owner), **kwargs)

    def call(self, method: str, url: str, owner: str, **kwargs) -> httpx.Response:
        self.last = self.run(self._send(method, url, owner, **kwargs))
        return self.last

    def create_library(self, owner: str) -> str:
        async def start_and_create() -> httpx.Response:
            async with self.toy.app.router.lifespan_context(self.toy.app):
                return await self._send("POST", "/libraries", owner, json=TENANT_BODY)

        created = self.run(start_and_create())
        assert created.status_code == 201, created.text
        return created.headers["location"]


@pytest.fixture
def run() -> Run:
    return Run()


@given(parsers.parse("the library service runs the library schema at version {version}"))
def _service(run: Run, version: str) -> None:
    assert run.toy.kit.chains[-1][1][0][-1] == version


@when("Ada creates a library")
def _ada_creates(run: Run) -> None:
    run.libraries["ada"] = (run.create_library("ada"), "")


@then(parsers.parse("the library records version {version} of the library schema"))
def _records_library(run: Run, version: str) -> None:
    tenant = run.libraries["ada"][0].rsplit("/", 1)[-1]
    database = run.toy.kit.tenancy.database_of(run.toy.kit.tenant_iri(tenant))
    run.held = run.run(stamps(run.store, database, run.toy.kit.tenancy.stamps_graph))
    assert run.held[LIBRARY_SCHEMA] == version


@then(parsers.parse("the library records version {version} of the toolkit's own schema"))
def _records_toolkit(run: Run, version: str) -> None:
    assert run.held[TOOLKIT_SCHEMA] == version


def _holds_a_book(run: Run, owner: str) -> None:
    path = run.create_library(owner)
    book = run.call("POST", f"{path}/books", owner, json=DUNE_BODY)
    assert book.status_code == 201, book.text
    run.libraries[owner] = (path, book.headers["location"])


@given("Ada's library holds a book")
def _ada_book(run: Run) -> None:
    _holds_a_book(run, "ada")


@given("Bob's library holds a book")
def _bob_book(run: Run) -> None:
    _holds_a_book(run, "bob")


@given("Ada's library follows a version of the schema that the service does not know")
def _ada_behind(run: Run) -> None:
    tenant = run.libraries["ada"][0].rsplit("/", 1)[-1]
    graph = run.toy.kit.tenancy.stamps_graph
    database = run.toy.kit.tenancy.database_of(run.toy.kit.tenant_iri(tenant))
    replace = (
        f"DELETE {{ GRAPH <{graph}> {{ <{LIBRARY_SCHEMA}> <{v.DATA_SCHEMA_VERSION}> ?old }} }} "
        f'INSERT {{ GRAPH <{graph}> {{ <{LIBRARY_SCHEMA}> <{v.DATA_SCHEMA_VERSION}> "9" }} }} '
        f"WHERE {{ GRAPH <{graph}> {{ <{LIBRARY_SCHEMA}> <{v.DATA_SCHEMA_VERSION}> ?old }} }}"
    )
    run.run(run.store.update(database, replace))


@when("the service starts")
def _starts(run: Run) -> None:
    run.toy = ToyService(run.store)  # a new instance over the same store, as after a deploy

    async def start() -> None:
        async with run.toy.app.router.lifespan_context(run.toy.app):
            pass  # the migrations run at start-up; the set of tenants set aside outlives it

    run.run(start())


def _asks(run: Run, owner: str) -> None:
    run.call("GET", run.libraries[owner][1], owner)


@when("Ada asks for the book of her library")
def _ada_asks(run: Run) -> None:
    _asks(run, "ada")


@when("Bob asks for the book of his library")
def _bob_asks(run: Run) -> None:
    _asks(run, "bob")


@then(parsers.parse('the answer is {status:d} with the problem "{problem}"'))
def _answer_problem(run: Run, status: int, problem: str) -> None:
    assert run.last is not None
    assert run.last.status_code == status, run.last.text
    assert run.last.json()["type"].endswith(f"/{problem}"), run.last.text


@then(parsers.parse("the answer is {status:d}"))
def _answer(run: Run, status: int) -> None:
    assert run.last is not None
    assert run.last.status_code == status, run.last.text

"""Steps of ``observability.feature``: the toy service over ``FakeStore``, its spans and its log records.

Scenario to requirement of ``rp-observability``: the first three scenarios are "Store calls are traced
with database conventions", the next two "The toolkit's own work is traced", the last four "Log records
carry a constant message and conventional attributes". The store's system is ``rdflib`` here, the
fake's; the Fuseki spelling is the container lane's. The other three scenarios of the spec are not
projected (see the comment of the feature file).
"""

import asyncio
import logging
from contextlib import AsyncExitStack
from types import SimpleNamespace

import httpx
import pytest
from opentelemetry.trace import StatusCode
from pytest_bdd import given, parsers, scenarios, then, when

from rdf_persistence import bootstrap
from rdf_persistence.core.domain.exceptions import StoreUnavailable
from rdf_persistence.core.domain.generated.rp_provenance import Activity, Replace
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.generated.service.rp_service import EventEnvelope
from rdf_persistence.services.generated.settings.rp_settings import LimitSettings
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.messagebus import Work, command
from rdf_persistence.testkit import FakeStore, RecordingObserver
from tests.logs import attributes, records_of
from tests.toy import dune, toy_mapper
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, principal_of

scenarios("observability.feature")

RP = "https://meaningfy.ws/ns/rdf-persistence"
KIT_LOGGER = "rdf_persistence.entrypoints.kit"


class FailingUpdates(FakeStore):
    """A fake store whose updates to the named databases fail."""

    def __init__(self) -> None:
        super().__init__()
        self.refused: set[str] = set()

    async def update(self, dataset: str, sparql: str) -> None:
        if dataset in self.refused:
            raise StoreUnavailable("down")
        await super().update(dataset, sparql)


class Run:
    """One scenario: a toy service over a fake store and what the steps have seen."""

    def __init__(self, spans) -> None:
        self.spans = spans
        self.loop = asyncio.new_event_loop()
        self.stack = AsyncExitStack()
        self.store = FailingUpdates()
        self.toy = ToyService(self.store)
        self.tenants: list[str] = []
        self.book_iri = ""
        self.error: BaseException | None = None
        self.limit = 100
        self.replacement: Replace | None = None

    def run(self, work):
        return self.loop.run_until_complete(work)

    def close(self) -> None:
        self.run(self.stack.aclose())
        self.loop.close()

    @property
    def kit(self):
        return self.toy.kit

    def start(self, toy: ToyService | None = None) -> None:
        self.toy = toy or self.toy
        self.run(self.stack.enter_async_context(self.toy.app.router.lifespan_context(self.toy.app)))

    async def call(self, method: str, url: str, **kwargs) -> httpx.Response:
        async with self.toy.client() as http:
            headers = {**self.toy.bearer("ada"), **kwargs.pop("headers", {})}
            return await http.request(method, url, headers=headers, **kwargs)

    def tenant(self) -> str:
        """Make a tenant through the API; answer its IRI."""

        async def make() -> str:
            made = await self.call("POST", "/libraries", json=TENANT_BODY)
            assert made.status_code == 201, made.text
            return made.headers["location"]

        path = self.run(make())
        self.tenants.append(self.kit.tenant_iri(path.rsplit("/", 1)[-1]))
        return self.tenants[-1]

    def commit_book(self, label: str | None = None, tenant: str | None = None) -> str:
        tenant = tenant or self.tenants[-1]
        iri = str(self.kit.iris.mint_aggregate(tenant, "book", "books"))
        book = dune(iri) if label is None else dune(iri).model_copy(update={"label": label})

        async def commit() -> None:
            async with self.kit.session(tenant, principal_of("ada")) as session:
                work = UnitOfWork(session, toy_mapper())
                work.add(book)
                await work.commit()

        self.run(commit())
        self.book_iri = iri
        return iri

    def named(self, name: str):
        return [s for s in self.spans() if s.name == name]


@pytest.fixture
def run(spans):
    scenario = Run(spans)
    yield scenario
    scenario.close()


def child_of(span, parent) -> bool:
    return span.parent is not None and span.parent.span_id == parent.context.span_id


# -- Given: the running service ------------------------------------------------------------------


@given("a running library service with a tenant")
def _service_with_tenant(run: Run) -> None:
    run.start()
    run.tenant()


@given("a running library service with a tenant holding a book")
def _service_with_book(run: Run) -> None:
    run.start()
    run.commit_book(tenant=run.tenant())


@given("a running library service with two tenants that each hold a book")
def _service_with_two(run: Run) -> None:
    run.start()
    for _ in range(2):
        run.commit_book(tenant=run.tenant())


@given("a store that does not answer")
def _store_down(run: Run) -> None:
    run.store.on("query", StoreUnavailable("down"), times=1000)


@given("an observer of every activity")
def _observer(run: Run) -> None:
    run.kit.bus = bootstrap(observers={Activity: [RecordingObserver()]}, mapper=run.kit.mapper)


# -- When and Then: traces -----------------------------------------------------------------------


@when("a book is committed in the tenant")
def _commit(run: Run) -> None:
    run.commit_book()


@when(parsers.parse('a book titled "{text}" is committed in the tenant'))
def _commit_titled(run: Run, text: str) -> None:
    run.commit_book(text)


@when("the book is read")
def _read(run: Run) -> None:
    async def read() -> None:
        async with run.kit.session(run.tenants[-1], principal_of("ada")) as session:
            await session.get_graph(run.book_iri)

    try:
        run.run(read())
    except Exception as error:  # noqa: BLE001 -- the failure is the outcome the Then steps assert on
        run.error = error


@when("the relay runs one round")
def _round(run: Run) -> None:
    run.run(run.kit.relay.run_once())


@then("an update of the store names the store's system and the tenant's database")
def _update_named(run: Run) -> None:
    database = run.kit.tenancy.database_of(run.tenants[-1])
    found = [
        s
        for s in run.named("update")
        if s.attributes.get("db.namespace") == database
        and s.attributes.get("db.system.name") == "rdflib"
    ]
    assert found, f"no update span of {database} in {[s.name for s in run.spans()]}"


@then("that update is a child of the commit")
def _update_child(run: Run) -> None:
    commits = run.named("rp.session.commit")
    assert commits, "no rp.session.commit span: the commit span lands with task 2.3"
    database = run.kit.tenancy.database_of(run.tenants[-1])
    assert any(
        child_of(s, commits[-1]) and s.attributes.get("db.namespace") == database
        for s in run.named("update")
    ), "no update of the tenant's database below the last commit span"


@then("the read fails because the store is unavailable")
def _read_failed(run: Run) -> None:
    assert isinstance(run.error, StoreUnavailable), repr(run.error)


@then("the query of the store is marked as failed with the error's class")
def _query_failed(run: Run) -> None:
    failed = [s for s in run.named("query") if s.status.status_code is StatusCode.ERROR]
    assert failed, "no failed query span"
    assert all(s.attributes["error.type"].endswith("StoreUnavailable") for s in failed)


@then(parsers.parse('no trace attribute contains "{text}"'))
def _no_text(run: Run, text: str) -> None:
    seen = run.spans()
    assert seen, "no span was recorded"
    for span in seen:
        values = [span.attributes, *(event.attributes for event in span.events)]
        assert text not in str(values), f"{text} in a {span.name} span"


@then("the commit, a store call and the observer's work share one trace")
def _one_trace(run: Run) -> None:
    commits, observed = run.named("rp.session.commit"), run.named("rp.bus.observe")
    assert commits, "no rp.session.commit span: the commit span lands with task 2.3"
    assert observed, "no rp.bus.observe span"
    trace_id = commits[-1].context.trace_id
    assert observed[-1].context.trace_id == trace_id, "the observer is in another trace"
    assert any(s.context.trace_id == trace_id for s in run.named("update")), "no store call"


@then("one relay round holds one database span for each tenant")
def _round_holds(run: Run) -> None:
    rounds = sorted(run.named("rp.relay.round"), key=lambda s: s.start_time)
    assert rounds, "no relay round span"
    run.round_databases = [s for s in run.named("rp.relay.database") if child_of(s, rounds[-1])]
    named = [s.attributes["rp.tenant.id"] for s in run.round_databases]
    for tenant in run.tenants:
        assert named.count(tenant) == 1, f"{tenant} in {named}"


@then("each database span names its tenant")
def _round_names(run: Run) -> None:
    assert all("rp.tenant.id" in s.attributes for s in run.round_databases)


# -- Logs: a service that starts again over what an earlier one left -----------------------------


def restarted(run: Run, **wiring) -> None:
    """Stop the first service; a second one over the same stores is built, not yet started."""
    run.run(run.stack.aclose())
    run.stack = AsyncExitStack()
    run.toy = ToyService(run.store, **wiring)


@given(
    parsers.parse(
        'a library service with a tenant, and an orphan database "{name}" on the store "{store}"'
    )
)
def _orphan(run: Run, name: str, store: str) -> None:
    run.start()
    run.tenant()
    elsewhere = FakeStore()
    run.run(elsewhere.create_dataset(name))
    restarted(run, stores={store: elsewhere})


@when("the service starts and sweeps")
def _sweep(run: Run, caplog) -> None:
    caplog.set_level(logging.INFO)
    run.start()


@then(parsers.parse('one info record says "{message}"'))
def _info(run: Run, caplog, message: str) -> None:
    [record] = records_of(caplog, "drop-orphan-database")
    assert (record.levelno, record.getMessage()) == (logging.INFO, message)


@then(
    parsers.parse(
        'that record names the step, the database "{name}" and the store "{store}" as attributes'
    )
)
def _info_attributes(run: Run, caplog, name: str, store: str) -> None:
    [record] = records_of(caplog, "drop-orphan-database")
    assert attributes(record) == {
        "rp.step": "drop-orphan-database",
        "db.namespace": name,
        "rp.store.name": store,
    }


@given("a library service with a tenant whose migration request fails")
def _failing_tenant(run: Run) -> None:
    run.start()
    tenant = run.tenant()
    database = run.kit.tenancy.database_of(tenant)
    graph = run.kit.tenancy.stamps_graph
    run.run(run.store.update(database, f"DELETE WHERE {{ GRAPH <{graph}> {{ <{RP}> ?p ?o }} }}"))
    run.run(
        run.store.update(
            database,
            f'INSERT DATA {{ GRAPH <{graph}> {{ <{RP}> <{v.DATA_SCHEMA_VERSION}> "1" }} }}',
        )
    )
    restarted(run)
    run.store.refused.add(database)
    run.failing = tenant


@when("the service starts and migrates the tenants")
def _migrate(run: Run, caplog) -> None:
    caplog.set_level(logging.ERROR)
    run.start()


@then("one error record names the tenant, the schema and the migration as attributes")
def _error_attributes(run: Run, caplog) -> None:
    [record] = records_of(caplog, "migrate-tenant")
    assert record.levelno == logging.ERROR
    logged = attributes(record)
    assert logged["rp.tenant.id"] == run.failing
    assert logged["rp.schema.id"] == RP
    assert logged["rp.migration.name"].startswith("1__2")


@then("that record carries the failure")
def _error_carries(run: Run, caplog) -> None:
    [record] = records_of(caplog, "migrate-tenant")
    assert record.exc_info is not None
    assert "down" in str(record.exc_info[1])


# -- Logs: events received from another deployment -----------------------------------------------


def envelope_of(run: Run, tenant: str) -> EventEnvelope:
    return EventEnvelope(
        tenant=tenant,
        origin="lib",
        activity_class=run.kit.view.get_uri("Replace", expand=True),
        context="https://example.org/context",
    )


@given("a library service that receives events")
def _receiver(run: Run) -> None:
    run.toy = ToyService(run.store, deployment="cat")
    run.start()
    run.tenant()
    run.kit.bus = bootstrap(mapper=run.kit.mapper)


@given(parsers.parse("a library service that receives events, with a message limit of {limit:d}"))
def _receiver_with_limit(run: Run, limit: int) -> None:
    run.limit = limit
    _receiver(run)


@given("a replacement of a book that Ada made")
def _replacement(run: Run) -> None:
    seen: list[Activity] = []

    async def keep(activity: Activity, work: Work) -> None:
        seen.append(activity)

    run.kit.bus = bootstrap(observers={Replace: [keep]}, mapper=run.kit.mapper)

    async def replace() -> None:
        made = await run.call(
            "POST", f"/libraries/{run.tenants[-1].rsplit('/', 1)[-1]}/books", json=DUNE_BODY
        )
        assert made.status_code == 201, made.text
        put = await run.call(
            "PUT",
            made.headers["location"],
            json=DUNE_BODY,
            headers={"If-Match": made.headers["etag"]},
        )
        assert put.status_code == 200, put.text

    run.run(replace())
    [run.replacement] = [a for a in seen if isinstance(a, Replace)]


@given("an observer that answers each replacement with a command that sends itself again")
def _runaway(run: Run) -> None:
    async def handle(cmd: Replace, work: Work) -> None:
        await work.send(command(Replace))

    async def again(activity: Replace, work: Work) -> None:
        await bus.handle(command(Replace), SimpleNamespace(session=work.session))

    bus = bootstrap(
        commands={Replace: handle},
        observers={Replace: [again]},
        limits=LimitSettings(max_messages=run.limit),
        mapper=run.kit.mapper,
    )
    run.kit.bus = bus


@when(parsers.parse('it receives an event whose body is invalid and contains "{text}"'))
def _receive_invalid(run: Run, caplog, text: str) -> None:
    caplog.set_level(logging.DEBUG, KIT_LOGGER)
    body = f'{{"id": "urn:a:x", "started_at_time": "{text}"}}'.encode()
    run.run(run.kit.receive(envelope_of(run, run.tenants[-1]), body))


@when("the service receives that replacement")
def _receive_replacement(run: Run, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    body = run.replacement.model_dump_json().encode()
    run.run(run.kit.receive(envelope_of(run, run.tenants[-1]), body))


@then("one warning record carries the kind of failure and the field at fault")
def _warning(run: Run, caplog) -> None:
    [record] = [r for r in caplog.records if r.levelno > logging.DEBUG]
    assert record.levelno == logging.WARNING
    logged = attributes(record)
    assert logged["error.type"].endswith("ValidationError")
    assert "started_at_time" in str(logged["rp.error.detail"])


@then(parsers.parse('"{text}" appears nowhere in that record'))
def _nowhere(run: Run, caplog, text: str) -> None:
    [record] = [r for r in caplog.records if r.levelno > logging.DEBUG]
    assert record.exc_info is None
    assert text not in f"{record.getMessage()}{attributes(record)}{caplog.text}"


@then(parsers.parse("exactly one error record reports it, with the limit {limit:d}"))
def _limit(run: Run, caplog, limit: int) -> None:
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert [r.name for r in errors] == [KIT_LOGGER]
    assert attributes(errors[0])["rp.message.limit"] == limit

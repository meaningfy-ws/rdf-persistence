"""Steps of ``messages.feature``: the toy library with its bus over the fakes (message-bus 4.2).

Scenario to requirement of ``rp-messages``: the first three scenarios are "Every commit records one
activity", the next two "Activity records are kept", the next three "One message per commit reaches
observers", the next two "A command goes to the nearest handler", the next one "The toolkit fills the
provenance", the next three "A command's record carries only its own statements" and the last one
"Messages raised while handling stay bounded".

The world is built when the first step needs the session, so a scenario names its observers and its
bus limit before it stores a book.
"""

import asyncio
import logging
from contextlib import AsyncExitStack

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from rdflib import RDF, Graph, Literal, URIRef

from rdf_persistence import bootstrap, generated_models
from rdf_persistence.access.services.access import AccessRules, load_role_definitions
from rdf_persistence.core.domain.exceptions import Conflict, InvalidBody, MessageLimitExceeded
from rdf_persistence.core.domain.generated.rp_access import Action, RoleDefinition, RoleLevel
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.core.domain.generated.rp_files import DeleteFile
from rdf_persistence.core.domain.generated.rp_provenance import Activity
from rdf_persistence.core.domain.generated.rp_workflow import Transition
from rdf_persistence.iris.services.iris import DEFAULT_IRIS
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.mapper import UnitOfWork
from rdf_persistence.provenance.services.provenance import Served
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.messagebus import Work, command
from rdf_persistence.services.workflows import Workflows, load_workflow, state_iri
from rdf_persistence.services.write_guards import WriteGuards
from rdf_persistence.testkit import FakeStore, RecordingObserver, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.fixtures.library.generated.books import Book
from tests.logs import attributes, records_of
from tests.toy import (
    ADA,
    BOB,
    MODULES,
    REVIEW_WORKFLOW,
    ROLES,
    TENANT,
    TOY_SCHEMA,
    ApproveBook,
    ShelveBooks,
    book_iri,
    caller,
    dune,
    held,
    role,
    toy_mapper,
    toy_mapper_limited,
)
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, principal_of

scenarios("messages.feature")

VIEW = load_schema(TOY_SCHEMA)
REVIEW = load_workflow(REVIEW_WORKFLOW)
IN_REVIEW = state_iri(REVIEW, "in_review")
PROVENANCE = URIRef(DEFAULT_IRIS.provenance(TENANT))
B1, B2, B3, B4 = (book_iri(n) for n in (1, 2, 3, 4))
COMMAND_ID = "urn:uuid:5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c001"
APPROVE_BOOK = URIRef("https://example.org/ns/library#ApproveBook")
ALL_QUADS = "SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } }"


def relabelling():
    """A ``ShelveBooks`` handler: relabel the first two books in one commit of the command."""

    async def shelve(cmd: Activity, work: Work) -> None:
        unit = work.unit_of_work()
        for iri in (B1, B2):
            unit.add((await unit.get(Book, iri)).model_copy(update={"label": "Shelved"}))
        await unit.commit()

    return shelve


class Failing:
    """An observer that always raises."""

    async def __call__(self, activity: Activity, work: Work) -> None:
        raise RuntimeError("this observer fails")


class Run:
    """One scenario: a fake store, a session with a bus, and what the steps have seen."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.stack = AsyncExitStack()
        self.store = FakeStore()
        self.commands: dict = {}
        self.observers: dict[type[Activity], list] = {}
        self.limit = 100
        self.built = False
        self.error: BaseException | None = None
        self.answer: object = None
        self.before: frozenset = frozenset()
        self.held_versions: dict[str, str] = {}
        self.served: Served | None = None
        # the HTTP scenario
        self.toy = ToyService(self.store)
        self.book_url = ""
        self.book_iri = ""

    def run(self, work):
        return self.loop.run_until_complete(work)

    def attempt(self, work) -> None:
        """Run ``work`` and keep its error, if any, for the Then steps."""
        try:
            self.answer = self.run(work)
        except Exception as error:  # noqa: BLE001 -- any failure is the outcome the Then steps assert on
            self.error = error

    def close(self) -> None:
        self.run(self.stack.aclose())
        self.loop.close()

    # -- the world ---------------------------------------------------------------------------------

    def world(self) -> None:
        if not self.built:
            self.run(self._open())
            self.built = True

    async def _open(self) -> None:
        rules = AccessRules(
            [
                *load_role_definitions(ROLES),
                RoleDefinition(role="reviewer", level=RoleLevel.TENANT, actions=[Action.ANNOTATE]),
            ]
        )
        self.bus = bootstrap(
            commands=self.commands,
            observers=self.observers,
            limits=LimitSettings(max_messages=self.limit),
            mapper=toy_mapper(),
        )
        listings = Listings(VIEW)
        guards = WriteGuards(
            toy_mapper(), generated_models(*MODULES), listings, Workflows([REVIEW], VIEW, rules)
        )
        self.session = await self.stack.enter_async_context(
            fake_session(
                self.store,
                tenant_iri=TENANT,
                principal=Principal(id=ADA),
                listings=listings,
                guards=guards,
                on_commit=self.bus.publish,
            )
        )
        self.other = await self.stack.enter_async_context(
            fake_session(self.store, tenant_iri=TENANT, principal=Principal(id=BOB))
        )
        self.collaboration = Collaboration(
            self.session,
            view=VIEW,
            rules=rules,
            iris=DEFAULT_IRIS,
            mapper=toy_mapper(),
            models=generated_models(*MODULES),
            listings=listings,
            workflows=Workflows([REVIEW], VIEW, rules),
            caller=caller(principal=ADA),
            access=held(role("librarian"), role("reviewer")),
        )

    def store_books(self, *iris: str) -> None:
        self.world()
        for iri in iris:
            self.run(self.session.add_graph(iri, toy_mapper().to_triples(dune(iri, chapters=1))))

    def version_of(self, iri: str) -> str:
        return self.run(self.session.get_graph(iri))[2]

    def approval(self, **slots) -> ApproveBook:
        return command(
            ApproveBook,
            used_resource=B1,
            to_state="in_review",
            expected_version=self.version_of(B1),
            **slots,
        )

    # -- what the store holds ----------------------------------------------------------------------

    def quads(self) -> frozenset:
        rows = self.run(self.store.query(FAKE_DATABASE, ALL_QUADS))
        return frozenset(tuple(map(str, row)) for row in rows)  # type: ignore[union-attr]

    def records(self, database: str = FAKE_DATABASE, graph: URIRef = PROVENANCE):
        """The recorded activities as ``(activity, its type IRIs)``, read from the provenance graph."""
        text = f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}"
        stored = self.run(self.store.query(database, text)).graph or Graph()
        return [
            (
                toy_mapper().from_graph(Activity, str(subject), stored, graph),
                set(stored.objects(subject, RDF.type)),
            )
            for subject in set(stored.subjects(RDF.type, v.ACTIVITY))
        ]

    def of_kind(self, kind: URIRef):
        return [a for a, types in self.records() if kind in types]

    def generating(self, iri: str) -> Activity:
        [found] = [a for a, _ in self.records() if iri in [g.entity for g in a.generations or []]]
        return found


@pytest.fixture
def run():
    scenario = Run()
    yield scenario
    scenario.close()


# -- Given ---------------------------------------------------------------------------------------


@given("the library holds a book")
def _a_book(run: Run) -> None:
    run.store_books(B1)


@given("the library holds two books")
def _two_books(run: Run) -> None:
    run.store_books(B1, B2)


@given("the librarian holds an old version of the book")
def _old_version(run: Run) -> None:
    run.held_versions["old"] = run.version_of(B1)
    run.run(
        run.session.replace_graph(B1, toy_mapper().to_triples(dune(B1)), run.held_versions["old"])
    )
    run.before = run.quads()


@given("an observer of transitions")
def _transition_observer(run: Run) -> None:
    run.observers.setdefault(Transition, []).append(RecordingObserver())


@given("an observer of every activity")
def _activity_observer(run: Run) -> None:
    run.observers.setdefault(Activity, []).append(RecordingObserver())


@given("two observers of every activity, the first of which fails")
def _failing_then_recording(run: Run) -> None:
    run.observers[Activity] = [Failing(), RecordingObserver()]


@given(parsers.parse("a bus that handles at most {limit:d} commands in one call"))
def _limit(run: Run, limit: int) -> None:
    run.limit = limit
    run.commands[ShelveBooks] = relabelling()


@given("an observer that answers every shelving with another shelving")
def _shelving_loop(run: Run) -> None:
    async def again(activity: Activity, work: Work) -> None:
        await work.send(command(ShelveBooks))

    run.observers.setdefault(ShelveBooks, []).append(again)


@given("a shelving command was recorded")
def _recorded_shelving(run: Run) -> None:
    run.store_books(B1)
    run.run(_serve(run, B1, ShelveBooks(id=COMMAND_ID)))
    run.before = run.quads()


@given("a shelving record that also states a title for that book")
def _record_with_a_title(run: Run) -> None:
    run.before = run.quads()


@given("a shelving record whose change was refused as a conflict")
def _spent_record(run: Run) -> None:
    run.store_books(B1)
    stale = run.version_of(B1)
    run.run(run.session.replace_graph(B1, toy_mapper().to_triples(dune(B1)), stale))
    run.served = toy_mapper().served(ShelveBooks(id=COMMAND_ID))
    with pytest.raises(Conflict):
        run.run(_serve(run, B1, run.served, version=stale))


@given("a change that adds four books in batches of two")
def _four_books(run: Run) -> None:
    run.world()
    run.unit = UnitOfWork(run.session, toy_mapper_limited(2))
    for iri in (B1, B2, B3, B4):
        run.unit.add(dune(iri, chapters=1))


async def _serve(run: Run, iri: str, served, *, version: str | None = None) -> None:
    """Replace book ``iri`` in a transaction that serves ``served`` (a command or its record)."""
    record = toy_mapper().served(served) if isinstance(served, Activity) else served
    current = version or (await run.session.get_graph(iri))[2]
    async with run.session.transaction(served=record) as transaction:
        await transaction.replace_graph(iri, toy_mapper().to_triples(dune(iri)), current)


@given("Ada's library holds a book")
def _http_book(run: Run) -> None:
    async def create() -> None:
        async with run.toy.app.router.lifespan_context(run.toy.app):
            made = await _call(run, "POST", "/libraries", json=TENANT_BODY)
        run.tenant_path = made.headers["location"]
        book = await _call(run, "POST", f"{run.tenant_path}/books", json=DUNE_BODY)
        assert book.status_code == 201, book.text
        run.book_url = book.headers["location"]
        shown = await _call(run, "GET", run.book_url)
        run.book_iri = shown.json()["id"]
        run.held_versions["etag"] = shown.headers["etag"]

    run.run(create())


async def _call(run: Run, method: str, url: str, **kwargs) -> httpx.Response:
    async with run.toy.client() as http:
        headers = {**run.toy.bearer("ada"), **kwargs.pop("headers", {})}
        return await http.request(method, url, headers=headers, **kwargs)


# -- When ----------------------------------------------------------------------------------------


@when("Ada replaces the book through the service")
def _http_replace(run: Run) -> None:
    changed = {**DUNE_BODY, "label": "Dune Messiah"}
    headers = {"If-Match": run.held_versions["etag"]}
    response = run.run(_call(run, "PUT", run.book_url, json=changed, headers=headers))
    assert response.status_code == 200, response.text
    run.held_versions["new"] = response.headers["etag"]


@when("the librarian replaces the book with that old version")
def _replace_stale(run: Run) -> None:
    run.attempt(
        run.session.replace_graph(B1, toy_mapper().to_triples(dune(B1)), run.held_versions["old"])
    )


@when("one change adds a second book and removes the first, serving no command")
def _mixed(run: Run) -> None:
    first = run.version_of(B1)

    async def change() -> None:
        async with run.session.transaction() as transaction:
            await transaction.add_graph(B2, toy_mapper().to_triples(dune(B2, chapters=1)))
            await transaction.remove(B1, first)

    run.run(change())


@when("the book is removed")
def _remove(run: Run) -> None:
    run.run(run.session.remove(B1, run.version_of(B1)))


@when("a second change serves a command with the same identity")
def _same_identity(run: Run) -> None:
    run.attempt(_serve(run, B1, ShelveBooks(id=COMMAND_ID)))


@when("the librarian approves the book")
def _approve(run: Run) -> None:
    run.attempt(run.bus.handle(run.approval(), run.collaboration))


@when("another writer replaces the book before the librarian's change is confirmed")
def _false_conflict(run: Run) -> None:
    held_version = run.version_of(B1)

    async def overwrite() -> None:
        run.store.after_update = None
        current = (await run.other.get_graph(B1))[2]
        await run.other.replace_graph(B1, toy_mapper().to_triples(dune(B1)), current)

    run.store.after_update = overwrite
    run.attempt(run.session.replace_graph(B1, toy_mapper().to_triples(dune(B1)), held_version))


@when("a command to delete a file is handled")
def _delete_file(run: Run) -> None:
    run.world()
    run.attempt(run.bus.handle(command(DeleteFile, used_resource=B1), run.collaboration))


@when("the librarian approves the book naming Bob as the agent")
def _forged(run: Run) -> None:
    run.before = run.quads()
    run.attempt(run.bus.handle(run.approval(was_associated_with=[BOB]), run.collaboration))


@when("a change serves that record")
def _serve_record(run: Run) -> None:
    plain = toy_mapper().served(ShelveBooks(id=COMMAND_ID))
    title = (URIRef(B1), URIRef("http://purl.org/dc/terms/title"), Literal("hijacked"))

    async def commit() -> None:
        # the record is refused where it is built, before any commit can use it
        record = Served(plain.activity, [*plain.triples, title], plain.types)
        await run.session.add_graph(B2, toy_mapper().to_triples(dune(B2)), served=record)

    run.attempt(commit())


@when("a second change serves the same record")
def _serve_again(run: Run) -> None:
    run.attempt(_serve(run, B1, run.served))


@when("the change commits")
def _commit_batches(run: Run) -> None:
    run.run(run.unit.commit(batches=True))


@when("a shelving command is handled")
def _handle_shelving(run: Run) -> None:
    run.attempt(run.bus.handle(command(ShelveBooks), run.collaboration))


# -- Then: recording -----------------------------------------------------------------------------


def _replacement(run: Run):
    database = run.toy.kit.tenancy.database_of(
        run.toy.kit.tenant_iri(run.tenant_path.rsplit("/", 1)[-1])
    )
    tenant = run.toy.kit.tenant_iri(run.tenant_path.rsplit("/", 1)[-1])
    found = run.records(database, URIRef(DEFAULT_IRIS.provenance(tenant)))
    return [(a, t) for a, t in found if v.REPLACE in t]


@then("one replacement is recorded")
def _one_replacement(run: Run) -> None:
    assert len(_replacement(run)) == 1, f"replacements: {_replacement(run)}"


@then("the replacement is by Ada")
def _by_ada(run: Run) -> None:
    [(replace, _)] = _replacement(run)
    assert replace.was_associated_with == [principal_of("ada")], "the caller"


@then("the replacement generated the book")
def _generated(run: Run) -> None:
    [(replace, _)] = _replacement(run)
    assert [g.entity for g in replace.generations] == [run.book_iri], (
        "the replace generated the book"
    )


@then("the replacement invalidated the book")
def _invalidated(run: Run) -> None:
    [(replace, _)] = _replacement(run)
    assert [i.entity for i in replace.invalidations] == [run.book_iri], (
        "the replace invalidated the book"
    )


@then("the generated version is not the invalidated one")
def _versions_differ(run: Run) -> None:
    [(replace, _)] = _replacement(run)
    old, new = (run.held_versions[k].strip('"') for k in ("etag", "new"))  # an ETag is quoted
    assert replace.invalidations[0].entity_version == old, "the old version is invalidated"
    assert replace.generations[0].entity_version == new, "the new version is generated"


@then("the change is refused as a conflict")
def _conflict(run: Run) -> None:
    assert isinstance(run.error, Conflict), f"the error is {run.error!r}"


@then("the records are as they were")
def _unchanged(run: Run) -> None:
    assert run.quads() == run.before, "the store is unchanged"


@then("one plain activity is recorded for it")
def _plain(run: Run) -> None:
    mixed = run.generating(B2).id
    assert [t for a, t in run.records() if a.id == mixed] == [{v.ACTIVITY}], "prov:Activity only"


@then("the activity generated the second book")
def _gen_second(run: Run) -> None:
    assert run.generating(B2), "the second book was generated"


@then("the activity invalidated the first book")
def _inv_first(run: Run) -> None:
    assert [i.entity for i in run.generating(B2).invalidations] == [B1], (
        "the first book was invalidated"
    )


# -- Then: keeping -------------------------------------------------------------------------------


@then("the records hold the addition of the book")
def _holds_add(run: Run) -> None:
    assert [[g.entity for g in a.generations] for a in run.of_kind(v.ADD)] == [[B1]], (
        "the Add holds the first book"
    )


@then("the records hold a removal naming the book")
def _holds_remove(run: Run) -> None:
    assert [[i.entity for i in a.invalidations] for a in run.of_kind(v.REMOVE)] == [[B1]], (
        "the Remove holds the first book"
    )


@then("the change is refused as a conflict naming that identity")
def _conflict_naming(run: Run) -> None:
    assert isinstance(run.error, Conflict), repr(run.error)
    assert COMMAND_ID in str(run.error), repr(run.error)


# -- Then: observing -----------------------------------------------------------------------------


def _first_observer(run: Run, cls: type[Activity]) -> RecordingObserver:
    return next(o for o in run.observers[cls] if isinstance(o, RecordingObserver))


@then("the observer receives one message")
def _one_message(run: Run) -> None:
    assert len(_first_observer(run, Transition).activities) == 1, "the observer got one message"


@then("the message is the approval")
def _is_approval(run: Run) -> None:
    [seen] = _first_observer(run, Transition).activities
    assert isinstance(seen, ApproveBook), "the observer saw an approval"


@then("the message carries the generation of the book")
def _carries_generation(run: Run) -> None:
    [seen] = _first_observer(run, Transition).activities
    assert [g.entity for g in seen.generations] == [B1], (
        "the approval carries the book it generated"
    )


@then("the failure is logged")
def _failure_logged(run: Run, caplog: pytest.LogCaptureFixture) -> None:
    assert any(
        r.levelno >= logging.ERROR
        and "rp.observer.name" in attributes(r)
        and "fails" in str(r.exc_info)
        for r in records_of(caplog, "bus-observer-failed")
    ), "the failure was logged at error level, naming the observer, with its exception"


@then("the second observer still receives the approval")
def _second_ran(run: Run) -> None:
    assert [type(a) for a in run.observers[Activity][1].of(ApproveBook)] == [ApproveBook], (
        "the second observer still ran"
    )


@then("the librarian sees a conflict")
def _sees_conflict(run: Run) -> None:
    assert isinstance(run.error, Conflict), f"the error is {run.error!r}"


@then("the librarian's replacement is recorded")
def _replacement_recorded(run: Run) -> None:
    assert len(run.of_kind(v.REPLACE)) == 2, "the other writer's and the librarian's"


@then("the observer receives no replacement")
def _no_replacement(run: Run) -> None:
    from rdf_persistence.core.domain.generated.rp_provenance import Replace

    assert _first_observer(run, Activity).of(Replace) == [], "no replacement was sent"


# -- Then: handling ------------------------------------------------------------------------------


@then("the book is in review")
def _in_review(run: Run) -> None:
    status = run.run(run.session.root_values(B1, [v.WORKFLOW_STATUS]))[v.WORKFLOW_STATUS]
    assert [str(s) for s in status] == [IN_REVIEW], "the book is in review"


@then("the stored activity is an approval")
def _stored_approval(run: Run) -> None:
    assert len(run.of_kind(APPROVE_BOOK)) == 1, "one approval was stored"


@then("the command is refused with an error naming the file deletion")
def _refused_by_name(run: Run) -> None:
    assert isinstance(run.error, LookupError), repr(run.error)
    assert "DeleteFile" in str(run.error), repr(run.error)


# -- Then: provenance ----------------------------------------------------------------------------


@then("the command is refused as invalid")
def _invalid(run: Run) -> None:
    assert isinstance(run.error, InvalidBody), f"the error is {run.error!r}"


@then("nothing is written")
def _nothing_written(run: Run) -> None:
    assert run.quads() == run.before, "nothing was written"


@then("the change is refused")
def _refused(run: Run) -> None:
    assert isinstance(run.error, ValueError), f"the error is {run.error!r}"


@then("the second change is refused")
def _second_refused(run: Run) -> None:
    assert isinstance(run.error, RuntimeError), f"the error is {run.error!r}"


@then("two activities are recorded, one per batch")
def _two_batches(run: Run) -> None:
    assert len(run.records()) == 2, "two batches were recorded"


# -- Then: bounds --------------------------------------------------------------------------------


@then(parsers.parse("the call stops with an error naming the limit of {limit:d}"))
def _limit_error(run: Run, limit: int) -> None:
    assert isinstance(run.error, MessageLimitExceeded), repr(run.error)
    assert str(limit) in str(run.error), repr(run.error)

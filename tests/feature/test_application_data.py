"""Steps of ``application_data.feature``: application data beside the tenants, on the fakes (app-level-data 5.1)."""

import asyncio
from collections.abc import Awaitable
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from rdf_persistence import (
    Action,
    Conflict,
    Forbidden,
    InvalidIri,
    UnitOfWork,
    load_role_definitions,
)
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantAccess
from rdf_persistence.domain.iris import application_database_name
from rdf_persistence.services.access import _access_mapper
from rdf_persistence.services.sweep import sweep
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.books import Book
from tests.fixtures.library.generated.templates import Template
from tests.toy import ADA, ROLES, SETTINGS, dune, library_slots, template, toy_mapper
from tests.toy_service import ToyService, principal_of

scenarios("application_data.feature")

APP_DATABASE = application_database_name(SETTINGS.prefix)
CLASSES = {"Book": Book, "Template": Template}


def run_async[T](work: Awaitable[T]) -> T:
    return asyncio.run(work)  # type: ignore[arg-type]


class Run:
    """One toy service over the fakes, a tenant of it, and what the scenario has done so far."""

    def __init__(self) -> None:
        self.toy = ToyService()
        self.kit = self.toy.kit
        self.store: FakeStore = self.toy.store  # type: ignore[assignment]
        self.principal = principal_of("eve")
        self.tenant = ""
        self.application = str(self.kit.iris.application)
        self.template_iri = ""
        self.updates_before: list[Any] = []
        self.listed: list[str] = []
        self.read: Template | None = None
        self.outcomes: list[BaseException | None] = []
        self.refusal: BaseException | None = None
        self.access: Any = None
        self.databases_before: list[str] = []
        self.created_by_start = 0
        self.tenancy_without_application: Tenancy | None = None
        self.started: bool | None = None

    def sent_updates(self) -> list[Any]:
        return list(self.store.sent("update"))

    def add_template(self) -> None:
        self.template_iri = self.kit.application_iri(Template)

        async def add() -> None:
            async with self.kit.application_session(self.principal) as session:
                work = UnitOfWork(session, toy_mapper())
                work.add(template(self.template_iri))
                await work.commit()

        run_async(add())

    def read_template(self) -> Template:
        async def read() -> Template:
            async with self.kit.application_session(self.principal) as session:
                return await UnitOfWork(session, toy_mapper()).get(Template, self.template_iri)

        return run_async(read())


@pytest.fixture
def run() -> Run:
    return Run()


@given("the library service has a tenant and an application database")
def _service(run: Run) -> None:
    async def start() -> None:
        await run.kit.tenancy.ensure_system_database()
        await run.kit.tenancy.ensure_application_database()
        record = await run.kit.tenancy.create("Ghent", library_slots(), Principal(id=ADA))
        run.tenant = record.id

    run_async(start())
    assert APP_DATABASE in run_async(run.store.list_datasets())


# -- an application aggregate is not in any tenant ----------------------------------------------


@given("an application aggregate")
def _an_aggregate(run: Run) -> None:
    run.add_template()


@when(
    "the tenant's aggregates are listed and the application's aggregate is read through an application session"
)
def _list_and_read(run: Run) -> None:
    async def list_tenant() -> list[str]:
        async with run.kit.session(run.tenant, run.principal) as session:
            return await session.find(Book)  # a tenant lists tenant classes only

    run.listed = run_async(list_tenant())
    run.read = run.read_template()


@then("the listing does not include it")
def _not_listed(run: Run) -> None:
    assert run.template_iri not in run.listed


@then("the read returns it")
def _read_returns(run: Run) -> None:
    assert run.read is not None
    assert run.read.id == run.template_iri


# -- application writes are versioned -----------------------------------------------------------


@given("an application aggregate at version v1")
def _at_v1(run: Run) -> None:
    run.add_template()


@when("two application sessions replace it at v1")
def _two_replace(run: Run) -> None:
    async def replace() -> list[BaseException | None]:
        results: list[BaseException | None] = []
        async with (
            run.kit.application_session(run.principal) as first,
            run.kit.application_session(run.principal) as second,
        ):
            one, other = UnitOfWork(first, toy_mapper()), UnitOfWork(second, toy_mapper())
            mine, theirs = (
                await one.get(Template, run.template_iri),
                await other.get(Template, run.template_iri),
            )
            mine.label, theirs.label = "First", "Second"
            one.add(mine)
            other.add(theirs)
            for work in (one, other):
                try:
                    await work.commit()
                    results.append(None)
                except Conflict as error:
                    results.append(error)
        return results

    run.outcomes = run_async(replace())


@then("the first succeeds")
def _first_succeeds(run: Run) -> None:
    assert run.outcomes[0] is None


@then("the second is refused as a conflict")
def _second_conflicts(run: Run) -> None:
    assert isinstance(run.outcomes[1], Conflict)


# -- a class in the wrong space -----------------------------------------------------------------


@given(
    parsers.parse(
        '"{tenant_class}" is a tenant class and "{application_class}" an application class'
    )
)
def _spaces(run: Run, tenant_class: str, application_class: str) -> None:
    served = {cls.__name__ for cls in (Template,)}
    assert application_class in served
    assert tenant_class not in served
    with pytest.raises(InvalidIri):
        run.kit.application_iri(CLASSES[tenant_class])


@when(parsers.parse('a "{name}" is committed through {session}'))
def _commit_wrong(run: Run, name: str, session: str) -> None:
    through_application = session == "an application session"
    run.updates_before = run.sent_updates()

    async def commit() -> None:
        if through_application:
            iri = str(run.kit.iris.mint_aggregate(run.application, name, "books"))
            opened = run.kit.application_session(run.principal)
        else:
            iri = str(run.kit.iris.mint_aggregate(run.tenant, name, "templates"))
            opened = run.kit.session(run.tenant, run.principal)
        async with opened as opened_session:
            work = UnitOfWork(opened_session, toy_mapper())
            work.add(dune(iri) if name == "Book" else template(iri))
            await work.commit()

    try:
        run_async(commit())
    except InvalidIri as error:
        run.refusal = error


@then("the session raises InvalidIri")
def _invalid_iri(run: Run) -> None:
    assert isinstance(run.refusal, InvalidIri)


@then("nothing is written")
def _nothing_written(run: Run) -> None:
    assert run.sent_updates() == run.updates_before


# -- the sweep leaves the application database alone --------------------------------------------


@given("an application database with aggregates and no access record naming it")
def _app_with_aggregates(run: Run) -> None:
    run.add_template()
    run.databases_before = sorted(run_async(run.store.list_datasets()))
    run.read = run.read_template()


@when("the start-up sweep runs")
def _sweep(run: Run) -> None:
    run_async(sweep(run.kit.tenancy, run.store, run.toy.files, run.toy.settings))


@then("the application database is unchanged")
def _database_unchanged(run: Run) -> None:
    assert APP_DATABASE in run_async(run.store.list_datasets())


@then("its aggregates are unchanged")
def _aggregates_unchanged(run: Run) -> None:
    assert run.read_template() == run.read


# -- a schema without application classes -------------------------------------------------------


@given(parsers.parse('a schema with no class annotated "{annotation}"'))
def _no_application_class(run: Run, annotation: str) -> None:
    assert annotation == "database: application"
    run.store = FakeStore()
    run.tenancy_without_application = Tenancy(
        run.store,
        FakeFileStore(),
        SETTINGS,
        mapper=_access_mapper(),
        root_class=TenantAccess,
        access_class=TenantAccess,
    )


@when("the service starts")
def _starts(run: Run) -> None:
    assert run.tenancy_without_application is not None
    run.started = run_async(run.tenancy_without_application.ensure_application_database())


@then("no application database is created")
def _none_created(run: Run) -> None:
    assert run.started is False
    assert run.store.sent("create_dataset") == []


# -- application data is decided by global roles ------------------------------------------------


@given(
    parsers.parse(
        'role definitions where the global role "{role}" permits "{first}" and "{second}" at level "{level}"'
    )
)
def _role_definitions(run: Run, role: str, first: str, second: str, level: str) -> None:
    defined = {d.role: d for d in load_role_definitions(ROLES)}[role]
    assert (defined.level, defined.actions) == (level, [first, second])


@when(parsers.parse('a caller whose token carries "{role}" modifies an application aggregate'))
def _editor_modifies(run: Run, role: str) -> None:
    header = run.toy.bearer("eve", role)["Authorization"]
    run.access = run_async(run.kit.require_application(header, Action.MODIFY))


@then("the change is allowed")
def _allowed(run: Run) -> None:
    assert run.access.checked_target == run.application


@given(parsers.parse('a caller with the "{role}" role on a tenant and no global role'))
def _tenant_owner(run: Run, role: str) -> None:
    assert role == "owner"  # the tenant's creator, who holds the toy's creator role "librarian"
    assert SETTINGS.creator_role == "librarian"
    run.principal = principal_of("ada")


@when("it modifies an application aggregate")
def _owner_modifies(run: Run) -> None:
    run.updates_before = run.sent_updates()
    header = run.toy.bearer("ada")["Authorization"]
    try:
        run_async(run.kit.require_application(header, Action.MODIFY))
    except Forbidden as error:
        run.refusal = error


@then("the check answers Forbidden")
def _forbidden(run: Run) -> None:
    assert isinstance(run.refusal, Forbidden)

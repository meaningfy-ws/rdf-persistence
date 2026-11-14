"""The two sessions and the application database (app-level-data PD-6, PD-7, PD-8; TC-29 to TC-41).

The world is the sweep tests': one tenant ``T`` of the toy library over the fakes. ``A`` is the
application IRI, ``Tpl`` a ``Template`` (an application class), ``B`` a ``Book`` (a tenant class).
"""

from types import SimpleNamespace

import pytest
from rdflib import RDF, Dataset, Graph, Literal, URIRef
from rdflib.compare import isomorphic

from rdf_persistence import Conflict, InvalidIri, NotFound
from rdf_persistence.domain.exceptions import DatabaseGone
from rdf_persistence.domain.generated.rp_access import Grant
from rdf_persistence.domain.generated.rp_annotations import Tracked
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantAccess, TenantState
from rdf_persistence.domain.generated.service.rp_service import GrantSet
from rdf_persistence.domain.iris import Iris, application_database_name, graph_iri
from rdf_persistence.domain.media import N_QUADS
from rdf_persistence.services.access import _access_mapper
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import open_session, payload_triples
from rdf_persistence.services.sweep import sweep
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.books import Book
from tests.fixtures.library.generated.templates import Template
from tests.toy import ADA, SETTINGS, access, dune, library, template, toy_mapper
from tests.unit.services.test_tenant_sweep import CREATOR, make_world

APP_DATABASE = application_database_name(SETTINGS.prefix)
EXPECTED_REFUSAL_TENANT = "is an application aggregate and does not belong in a tenant database"
EXPECTED_REFUSAL_APPLICATION = "is not an application aggregate"
TITLE = URIRef("http://purl.org/dc/terms/title")


@pytest.fixture
async def world() -> SimpleNamespace:
    """The toy tenant ``T`` over the fakes, with the application database created."""
    made = await make_world(Iris(SETTINGS), SETTINGS)
    made.app_iri = str(made.iris.application)
    made.created = await made.tenancy.ensure_application_database()
    made.app = lambda: made.tenancy.application_session(CREATOR)
    made.tenant_session = lambda: made.tenancy.tenant_session(made.tenant, CREATOR)
    made.tpl_iri = lambda: str(made.iris.mint_aggregate(made.app_iri, "Template", "templates"))
    made.tenant_tpl_iri = lambda: str(
        made.iris.mint_aggregate(made.tenant, "Template", "templates")
    )
    made.book_at = lambda owner: str(made.iris.mint_aggregate(owner, "Book", "books"))
    return made


async def holds(store: FakeStore, database: str, graph: URIRef) -> bool:
    asked = await store.query(database, f"ASK {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}")
    return bool(asked.askAnswer)


async def graphs_of(store: FakeStore, database: str) -> dict[URIRef, Graph]:
    """Every named graph of ``database``, by name."""
    data = Dataset()
    data.parse(data=(await store.export_quads(database)).decode(), format=N_QUADS)
    return {URIRef(g.identifier): Graph().__iadd__(g) for g in data.graphs() if len(g)}


def same_content(read: Template, sent: Template) -> bool:
    """Equal but for the tracking the session adds."""
    kept = {"id", "label", "description"}
    return read.model_dump(include=kept) == sent.model_dump(include=kept)


def triples_typed(obj) -> list:
    return list(toy_mapper().to_triples(obj))


async def add_tpl(world: SimpleNamespace) -> str:
    iri = world.tpl_iri()
    async with world.app() as session:
        work = UnitOfWork(session, toy_mapper())
        work.add(template(iri))
        await work.commit()
    return iri


# -- TC-29, TC-30: the application session stores and reads application aggregates --------------


async def test_an_application_aggregate_is_stored_in_the_application_database_only(world):
    assert world.created is True, "the fixture created the application database"
    iri = await add_tpl(world)
    async with world.app() as session:
        read = await UnitOfWork(session, toy_mapper()).get(Template, iri)
        found = await session.find(Template)
    listings = Listings(toy_mapper().view)
    async with open_session(
        world.store,
        database=world.database,
        tenant_iri=world.tenant,
        principal=CREATOR,
        iris=world.iris,
        listings=listings,
    ) as tenant:
        books = await tenant.find(Book)
    assert same_content(read, template(iri)), "another application session reads it back equal"
    assert found == [iri], "find answers its IRI"
    assert iri not in books, "the listing of the tenant's books does not hold it"
    held_in = [
        name
        for name in await world.store.list_datasets()
        if await holds(world.store, name, graph_iri(iri))
    ]
    assert held_in == [APP_DATABASE], "the graph is in the application database only"


async def test_two_units_of_work_on_one_application_aggregate_conflict(world):
    iri = await add_tpl(world)
    async with world.app() as first, world.app() as second:
        one, other = UnitOfWork(first, toy_mapper()), UnitOfWork(second, toy_mapper())
        mine, theirs = await one.get(Template, iri), await other.get(Template, iri)
        mine.label, theirs.label = "First", "Second"
        one.add(mine)
        other.add(theirs)
        await one.commit()
        with pytest.raises(Conflict):
            await other.commit()
    async with world.app() as session:
        stored = await UnitOfWork(session, toy_mapper()).get(Template, iri)
    assert stored.label == "First", "the stored label is the first commit's"


# -- TC-31, TC-32, TC-33: what each session refuses -----------------------------------------------


def _b_at_application(w):
    iri = w.book_at(w.app_iri)
    return iri, dune(iri)


def _tenant_root_at_application(w):
    return w.app_iri, library(iri=w.app_iri)


def _access_at_application(w):
    iri = str(w.iris.access(w.app_iri))
    return iri, access().model_copy(update={"id": iri})


def _tpl_at_tenant(w):
    iri = w.tenant_tpl_iri()
    return iri, template(iri)


# (the session, what it is given, the words of the refusal)
REFUSED = [
    pytest.param("app", _b_at_application, EXPECTED_REFUSAL_APPLICATION, id="B-at-A"),
    pytest.param(
        "app", _tenant_root_at_application, EXPECTED_REFUSAL_APPLICATION, id="tenant-root-at-A"
    ),
    pytest.param("app", _access_at_application, EXPECTED_REFUSAL_APPLICATION, id="access-at-A"),
    pytest.param("tenant", _tpl_at_tenant, EXPECTED_REFUSAL_TENANT, id="Tpl-at-T"),
]
ACCEPTED = [
    pytest.param("app", lambda w: (w.tpl_iri(), None), id="Tpl-at-A"),
    pytest.param("tenant", lambda w: (w.book_at(w.tenant), None), id="B-at-T"),
]


def _object_of(world, make):
    iri, obj = make(world)
    if obj is None:
        obj = template(iri) if iri.startswith(world.app_iri) else dune(iri)
    return iri, obj


@pytest.mark.parametrize("through", ["commit", "add_graph"])
@pytest.mark.parametrize(("kind", "make", "words"), REFUSED)
async def test_a_class_of_the_other_space_is_refused_and_nothing_is_sent(
    world, through, kind, make, words
):
    iri, obj = _object_of(world, make)
    sent = list(world.store.sent("update"))
    with pytest.raises(InvalidIri, match=words):
        async with world.app() if kind == "app" else world.tenant_session() as session:
            if through == "commit":
                work = UnitOfWork(session, toy_mapper())
                work.add(obj)
                await work.commit()
            else:
                await session.add_graph(iri, triples_typed(obj))
    assert world.store.sent("update") == sent, "no update was sent"


async def test_a_root_with_no_type_is_refused_by_the_application_session(world):
    iri = world.tpl_iri()
    sent = list(world.store.sent("update"))
    with pytest.raises(InvalidIri, match=EXPECTED_REFUSAL_APPLICATION):
        async with world.app() as session:
            await session.add_graph(iri, [(URIRef(iri), TITLE, Literal("untyped"))])
    assert world.store.sent("update") == sent, "no update was sent"


@pytest.mark.parametrize("other", [Book, "tenant root"])
async def test_a_root_typed_with_an_application_and_a_tenant_class_is_refused(world, other):
    """D-6 c: a class of another database beside an application class is not an application aggregate."""
    iri = world.tpl_iri()
    stray = dune(iri) if other is Book else library(iri=iri)
    foreign = [t for t in triples_typed(stray) if t[1] == RDF.type]
    sent = list(world.store.sent("update"))
    with pytest.raises(InvalidIri, match=EXPECTED_REFUSAL_APPLICATION):
        async with world.app() as session:
            await session.add_graph(iri, [*triples_typed(template(iri)), *foreign])
    assert world.store.sent("update") == sent, "no update was sent"


@pytest.mark.parametrize("where", ["application", "access"])
async def test_an_application_class_at_the_application_or_its_access_record_is_refused(
    world, where
):
    """D-6 a: the application has no root object and no access record, whatever the root's type."""
    iri = world.app_iri if where == "application" else str(world.iris.access(world.app_iri))
    sent = list(world.store.sent("update"))
    with pytest.raises(InvalidIri, match="not an aggregate IRI"):
        async with world.app() as session:
            await session.add_graph(iri, triples_typed(template(iri)))
    assert world.store.sent("update") == sent, "no update was sent"


@pytest.mark.parametrize("through", ["commit", "add_graph"])
@pytest.mark.parametrize(("kind", "make"), ACCEPTED)
async def test_a_class_of_its_own_space_is_accepted(world, through, kind, make):
    iri, obj = _object_of(world, make)
    async with world.app() if kind == "app" else world.tenant_session() as session:
        if through == "commit":
            work = UnitOfWork(session, toy_mapper())
            work.add(obj)
            await work.commit()
        else:
            await session.add_graph(iri, triples_typed(obj))
        stored, _, _ = await session.get_graph(iri)
    assert len(stored), "the aggregate is stored"


@pytest.mark.parametrize(
    ("kind", "make", "message"),
    [
        pytest.param("app", _tpl_at_tenant, "not an aggregate IRI", id="Tpl-at-T-app-session"),
        pytest.param(
            "tenant",
            _b_at_application,
            "not an aggregate IRI",
            id="B-at-A-tenant-session",
        ),
    ],
)
async def test_an_iri_of_the_other_space_is_refused_by_the_iri_check(world, kind, make, message):
    iri, obj = make(world)
    sent = list(world.store.sent("update"))
    with pytest.raises(InvalidIri, match=message):
        async with world.app() if kind == "app" else world.tenant_session() as session:
            await session.add_graph(iri, triples_typed(obj))
    assert world.store.sent("update") == sent, "no update was sent"


async def test_a_replacement_typed_as_a_tenant_class_is_refused(world):
    iri = await add_tpl(world)
    async with world.app() as session:
        before, _, version = await session.get_graph(iri)
        with pytest.raises(InvalidIri, match=EXPECTED_REFUSAL_APPLICATION):
            await session.replace_graph(iri, triples_typed(dune(iri)), version)
        after, _, _ = await session.get_graph(iri)
    assert isomorphic(before, after), "the stored graph is unchanged"


# -- TC-46 at the tenancy: the IRI of a new application aggregate (D-6 g) ----------------------------


def test_the_tenancy_mints_an_application_aggregate_iri_for_an_application_class(world):
    iri = world.tenancy.application_iri(Template)
    assert world.iris.is_aggregate(world.app_iri, iri), "A accepts it as its aggregate"
    assert world.tenancy.application_iri(Template) != iri, "each call mints a new one"


def test_the_tenancy_refuses_an_application_iri_for_a_tenant_class(world):
    with pytest.raises(InvalidIri, match="Book is not an application class"):
        world.tenancy.application_iri(Book)


# -- TC-34: loaded graphs ----------------------------------------------------------------------


async def test_a_graph_loaded_for_an_application_aggregate_is_listed(world):
    iri = await add_tpl(world)
    async with world.app() as session:
        _, _, version = await session.get_graph(iri)
        loaded = await session.load_graph(
            iri, b'<https://ex.org/s> <http://purl.org/dc/terms/title> "t" .', rdf_format="turtle"
        )
        await session.replace_graph(iri, triples_typed(template(iri)), version, [loaded])
        listed = await session.loaded_graphs(iri)
    assert str(loaded).startswith(iri + "/"), "the loaded graph's IRI is under the aggregate's"
    assert listed == [loaded], "the loaded graph is listed"


# -- TC-35: the system database is untouched ---------------------------------------------------


async def test_the_system_database_is_unchanged_by_application_work(world):
    before = await graphs_of(world.store, world.tenancy.system_database)
    iri = await add_tpl(world)
    async with world.app() as session:
        _, _, version = await session.get_graph(iri)
        await session.replace_graph(iri, triples_typed(template(iri)), version)
        await session.load_graph(
            iri, b'<https://ex.org/s> <http://purl.org/dc/terms/title> "t" .', rdf_format="turtle"
        )
        with pytest.raises(InvalidIri):
            await session.add_graph(world.book_at(world.app_iri), triples_typed(dune(iri)))
    after = await graphs_of(world.store, world.tenancy.system_database)
    assert before.keys() == after.keys(), "the same graphs are there"
    assert all(isomorphic(before[name], after[name]) for name in before), "each is as it was"


# -- TC-36, TC-37: the application database ------------------------------------------------------


async def test_the_application_database_is_created_once(world):
    again = await world.tenancy.ensure_application_database()
    names = [n for n in await world.store.list_datasets() if n == APP_DATABASE]
    assert (world.created, again) == (True, False), "True the first time, False the second"
    assert names == [APP_DATABASE], "there is one application database"


async def test_an_application_session_on_a_database_never_created_fails_at_its_first_commit():
    made = await make_world(Iris(SETTINGS), SETTINGS)  # no ensure_application_database
    iri = str(made.iris.mint_aggregate(str(made.iris.application), "Template", "templates"))
    with pytest.raises(DatabaseGone):
        async with made.tenancy.application_session(CREATOR) as session:
            work = UnitOfWork(session, toy_mapper())
            work.add(template(iri))
            await work.commit()


async def test_a_conflict_on_create_is_suppressed_and_answers_false():
    store, files = FakeStore(), FakeFileStore()
    tenancy = Tenancy(
        store,
        files,
        SETTINGS,
        mapper=toy_mapper(),
        root_class=type(library()),
        access_class=type(access()),
    )
    store.on("create_dataset", Conflict("another worker created it"))
    assert await tenancy.ensure_application_database() is False, "another worker created it"


def _without_application() -> tuple[FakeStore, Tenancy]:
    store = FakeStore()
    tenancy = Tenancy(
        store,
        FakeFileStore(),
        SETTINGS,
        mapper=_access_mapper(),
        root_class=TenantAccess,
        access_class=TenantAccess,
    )
    return store, tenancy


async def test_a_schema_with_no_application_class_creates_no_database():
    store, tenancy = _without_application()
    assert await tenancy.ensure_application_database() is False, "nothing was created"
    assert [store.sent(op) for op in ("list_datasets", "create_dataset")] == [[], []], (
        "the store was not called"
    )


def test_a_schema_with_no_application_class_has_no_application_session():
    _, tenancy = _without_application()
    with pytest.raises(LookupError, match="no application class"):
        tenancy.application_session(Principal(id=ADA))  # at the call, not on entering


# -- TC-38: the start-up sweep keeps the application database ------------------------------------


async def test_the_start_up_sweep_leaves_the_application_database_alone(world):
    """Regression guard (TC-38): passes on the code before this change too; it keeps the sweep honest."""
    iri = await add_tpl(world)
    await sweep(world.tenancy, world.store, world.files, SETTINGS)
    async with world.app() as session:
        read = await UnitOfWork(session, toy_mapper()).get(Template, iri)
    assert APP_DATABASE in await world.store.list_datasets(), "the database is still listed"
    assert same_content(read, template(iri)), "the template is readable"


# -- TC-39, TC-40, TC-41: what the tenant session still accepts ------------------------------------


async def test_a_schema_with_no_application_class_refuses_nothing():
    """Regression guard (TC-39): passes on the code before this change too."""
    store, tenancy = _without_application()
    tenant = str(tenancy._iris.mint_tenant())
    name = tenancy._iris.resource_name(tenant)
    await store.create_dataset(name)
    record = TenantAccess(
        id=str(tenancy._iris.access(tenant)),
        label="Access",
        description="Who may do what.",
        state=TenantState.ACTIVE,
        database_name=name,
    )
    async with tenancy.tenant_session(tenant, CREATOR) as session:
        work = UnitOfWork(session, _access_mapper())
        work.add(record)
        await work.commit()
        stored, _, _ = await session.get_graph(record.id)
    assert len(stored), "the root is stored"


async def test_the_sessions_tenancy_opens_for_itself_refuse_nothing(world):
    """Regression guard (TC-40): passes on the code before this change too."""
    created = await world.tenancy.create("Antwerp", {}, CREATOR)
    record, version = await world.tenancy.get(created.id)
    grants = GrantSet(grants=[Grant(assignee=ADA, target=created.id, role="librarian")])
    await world.tenancy.set_grants(created.id, grants, version, CREATOR)
    after, _ = await world.tenancy.get(created.id)
    assert after.grants == grants.grants, "create and set_grants both succeeded"
    assert record.state == TenantState.ACTIVE, "the tenant was created active"


@pytest.fixture
async def stray(world) -> str:
    """A ``Tpl`` graph put straight into the tenant's database, as if its class moved to the application later."""
    iri = world.tenant_tpl_iri()
    graph = graph_iri(iri)
    stored = Graph()
    for triple in payload_triples(graph, "v1", Tracked(creator=ADA), triples_typed(template(iri))):
        stored.add(triple)
    await world.store.put_graph(world.database, graph, stored)
    return iri


async def test_the_tenant_session_reads_and_removes_a_stray_application_graph(world, stray):
    async with world.tenant_session() as session:
        _, _, version = await session.get_graph(stray)
        await session.remove(stray, version)
        with pytest.raises(NotFound):
            await session.get_graph(stray)


async def test_the_tenant_session_refuses_to_replace_a_stray_application_graph(world, stray):
    async with world.tenant_session() as session:
        _, _, version = await session.get_graph(stray)
        with pytest.raises(InvalidIri, match=EXPECTED_REFUSAL_TENANT):
            await session.replace_graph(stray, triples_typed(template(stray)), version)

"""The runner that applies the pending migrations of each database (schema-migrations PD-7, PD-9 to PD-11): TC-23 to TC-36, TC-54.

A tenant ``T`` holds a toy book whose ISBN is stored under an old, made-up predicate; the migration
``1__2`` moves it to the predicate of the current toy ``Book``. Chains are files in ``tmp_path``; the
store is the fake, which applies a request atomically.
"""

import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
import yaml
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS

from rdf_persistence.domain.exceptions import (
    Conflict,
    MigrationFailed,
    StoredDataInvalid,
    StoreUnavailable,
    TenantBehind,
)
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.service.rp_service import Migration, MigrationStep
from rdf_persistence.domain.iris import Iris, graph_iri, skolem_iri, stamps_graph_iri
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.iri_policy_guard import guard_iri_policy
from rdf_persistence.services.migration_runner import (
    migrate_database,
    migrate_shared,
    migrate_tenants,
    stamp_if_none,
    stamps,
)
from rdf_persistence.services.migrations import Chain, load_chain, migration_request
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import LABEL
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.books import Book
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, SETTINGS, TOY_SCHEMA, dune, library_slots, toy_mapper
from tests.unit.services.conftest import GENERATED
from tests.unit.services.test_tenant_sweep import HOUR, make_world

LIB = "https://example.org/ns/library"
RP = "https://meaningfy.ws/ns/rdf-persistence"
STAMPS = stamps_graph_iri(SETTINGS.base)
ISBN = URIRef("http://purl.org/ontology/bibo/isbn")
OLD_ISBN = URIRef("https://example.org/ns/library#oldIsbn")
MID_ISBN = URIRef("https://example.org/ns/library#midIsbn")
CREATOR = Principal(id=ADA)
ALL = "SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } }"


# -- chains ---------------------------------------------------------------------------------------


def rename(old: URIRef, new: URIRef) -> MigrationStep:
    return MigrationStep(
        title=f"rename {old}",
        where_pattern=f"?s <{old}> ?o .",
        delete_pattern=f"?s <{old}> ?o .",
        insert_pattern=f"?s <{new}> ?o .",
    )


def migration(schema: str, old: str, new: str, *steps: MigrationStep) -> Migration:
    return Migration(schema_id=schema, from_version=old, to_version=new, steps=list(steps) or None)


def chain_of(folder: Path, schema: str, *migrations: Migration, current: str) -> Chain:
    """The chain of the migration files written to ``folder``, ending at ``current``."""
    folder.mkdir(parents=True, exist_ok=True)
    for one in migrations:
        name = f"{one.from_version}__{one.to_version}.yaml"
        (folder / name).write_text(yaml.safe_dump(one.model_dump(exclude_none=True)), "utf-8")
    return load_chain(folder, schema, current)


@pytest.fixture
def lib_chain(tmp_path) -> Chain:
    """``[1, 2]``: version 2 moves the ISBN from its old predicate to the book's."""
    step = migration(LIB, "1", "2", rename(OLD_ISBN, ISBN))
    return chain_of(tmp_path / "lib", LIB, step, current="2")


@pytest.fixture
def three(tmp_path) -> Chain:
    """``[1, 2, 3]``: the ISBN goes old, then middle, then the book's predicate."""
    steps = (
        migration(LIB, "1", "2", rename(OLD_ISBN, MID_ISBN)),
        migration(LIB, "2", "3", rename(MID_ISBN, ISBN)),
    )
    return chain_of(tmp_path / "three", LIB, *steps, current="3")


# -- the world ------------------------------------------------------------------------------------


def book_of(tenant: str) -> str:
    return f"{tenant}/books/{UUID(int=1)}"


async def put_stamp(store, database: str, schema: str, version: str) -> None:
    await store.update(
        database,
        f'INSERT DATA {{ GRAPH <{STAMPS}> {{ <{schema}> <{v.DATA_SCHEMA_VERSION}> "{version}" }} }}',
    )


async def held(store, database: str) -> dict[str, str]:
    rows = await store.query(
        database, f"SELECT ?s ?v WHERE {{ GRAPH <{STAMPS}> {{ ?s <{v.DATA_SCHEMA_VERSION}> ?v }} }}"
    )
    return {str(row.s): str(row.v) for row in rows}  # type: ignore[union-attr]


async def quads(store, database: str) -> frozenset[tuple]:
    return frozenset(tuple(map(str, row)) for row in await store.query(database, ALL))


async def old_book(world: SimpleNamespace, tenant: str) -> str:
    """Store a book of ``tenant`` whose ISBN "A3" sits under the old predicate."""
    iri = book_of(tenant)
    triples = [
        (s, OLD_ISBN if p == ISBN else p, o)
        for s, p, o in toy_mapper().to_triples(dune(iri, isbn="A3"))
    ]
    async with world.tenancy.tenant_session(tenant, CREATOR) as session:
        await session.add_graph(iri, triples)
    return iri


async def read(world: SimpleNamespace, tenant: str) -> tuple[Graph, URIRef, str]:
    async with world.tenancy.tenant_session(tenant, CREATOR) as session:
        return await session.get_graph(book_of(tenant))


async def second_tenant(world: SimpleNamespace) -> SimpleNamespace:
    summary = await world.tenancy.create("Bruges", library_slots(), CREATOR)
    return SimpleNamespace(id=summary.id, database=world.tenancy.database_of(summary.id))


@pytest.fixture
async def world() -> SimpleNamespace:
    """The sweep test's tenant ``T`` over the fakes, stamped ``1`` for the consumer's schema, with an old-shaped book."""
    made = await make_world(Iris(SETTINGS), SETTINGS)
    await put_stamp(made.store, made.database, LIB, "1")
    made.book = await old_book(made, made.tenant)
    return made


# -- TC-23: stamping --------------------------------------------------------------------------------


async def test_a_database_with_no_stamp_is_stamped_with_the_first_version_then_migrated(
    world, lib_chain
):
    unstamped = await second_tenant(world)
    await old_book(world, unstamped.id)
    await migrate_database(world.store, unstamped.database, [(LIB, lib_chain)], STAMPS)
    assert await held(world.store, unstamped.database) == {LIB: "2"}, "stamped, then moved to 2"
    first, second = world.store.sent("update")[-2:]
    assert "NOT EXISTS" in first and '"1"' in first, (
        "the first write stamps the first version, conditionally"
    )
    assert '"2"' in second, "then the migration moves it"


async def test_a_new_system_database_holds_both_stamps_current_and_the_runner_sends_it_nothing(
    store_and_files, tmp_path, lib_chain
):
    store, files = store_and_files
    tenancy = Tenancy(
        store, files, SETTINGS, mapper=toy_mapper(), root_class=Library,
        access_class=LibraryAccess, stamps=((RP, "1"), (LIB, "2")),
    )  # fmt: skip
    assert await tenancy.ensure_system_database() is True, "this call created it"
    await guard_iri_policy(store, tenancy, SETTINGS)
    system = tenancy.system_database
    assert await held(store, system) == {RP: "1", LIB: "2"}, (
        "both stamps, current, beside the policy record"
    )
    chains = [(RP, chain_of(tmp_path / "rp", RP, current="1")), (LIB, lib_chain)]
    sent = len(store.sent("update"))
    await migrate_shared(tenancy, store, chains)
    assert len(store.sent("update")) == sent, "nothing is pending, so nothing is sent"


async def test_an_existing_system_database_is_not_stamped(store_and_files):
    store, files = store_and_files
    plain = Tenancy(
        store, files, SETTINGS, mapper=toy_mapper(), root_class=Library, access_class=LibraryAccess
    )
    await plain.ensure_system_database()
    stamping = Tenancy(
        store, files, SETTINGS, mapper=toy_mapper(), root_class=Library,
        access_class=LibraryAccess, stamps=((LIB, "2"),),
    )  # fmt: skip
    assert await stamping.ensure_system_database() is False, "it was there"
    assert await held(store, stamping.system_database) == {}, (
        "what the call did not create it does not stamp"
    )


@pytest.fixture
def store_and_files():
    return FakeStore(), FakeFileStore()


async def test_two_writers_stamping_at_once_leave_one_stamp(world):
    database = world.tenancy.database_of((await second_tenant(world)).id)
    await asyncio.gather(
        stamp_if_none(world.store, database, STAMPS, LIB, "1"),
        stamp_if_none(world.store, database, STAMPS, LIB, "2"),
    )
    assert await held(world.store, database) == {LIB: "1"}, "the first writer wins, one stamp"


async def test_the_stamps_are_read_per_schema(world):
    await put_stamp(world.store, world.database, RP, "7")
    assert await stamps(world.store, world.database, STAMPS) == {LIB: "1", RP: "7"}, "id to version"


async def test_two_stamps_of_one_schema_are_refused_naming_both(world):
    await put_stamp(world.store, world.database, LIB, "2")
    with pytest.raises(StoredDataInvalid) as refused:
        await stamps(world.store, world.database, STAMPS)
    assert LIB in str(refused.value), "the schema is named"
    assert '"1"' in str(refused.value), "the first version is named"
    assert '"2"' in str(refused.value), "the second version is named"


# -- TC-24 to TC-26: what a migration does to the data -----------------------------------------------


async def test_the_value_moves_to_the_new_predicate_and_the_book_still_validates(world, lib_chain):
    await migrate_database(world.store, world.database, [(LIB, lib_chain)], STAMPS)
    graph, name, _ = await read(world, world.tenant)
    subject = URIRef(world.book)
    assert list(graph.objects(subject, ISBN)) == [Literal("A3")], (
        "the value is under the new predicate"
    )
    assert list(graph.objects(subject, OLD_ISBN)) == [], "none is left under the old one"
    decoded = toy_mapper().from_graph(Book, world.book, graph, name)
    assert decoded.isbn == "A3", "the toy mapper decodes it"
    await Documents(load_schema(TOY_SCHEMA), GENERATED).validate(toy_mapper().to_graph(decoded))
    assert await held(world.store, world.database) == {LIB: "2"}, "the stamp is 2"


async def test_a_second_run_sends_the_store_no_update(world, lib_chain):
    await migrate_database(world.store, world.database, [(LIB, lib_chain)], STAMPS)
    sent = len(world.store.sent("update"))
    await migrate_database(world.store, world.database, [(LIB, lib_chain)], STAMPS)
    assert len(world.store.sent("update")) == sent, "the stamp says nothing is pending"


async def test_the_same_request_sent_twice_leaves_the_data_of_the_first(world, lib_chain):
    request = migration_request(lib_chain[1][0], STAMPS)
    await world.store.update(world.database, request)
    once = await quads(world.store, world.database)
    await world.store.update(world.database, request)
    assert await quads(world.store, world.database) == once, "the second send matches nothing"


async def test_the_token_changes_the_modified_date_stays_and_an_old_token_conflicts(
    world, lib_chain
):
    before, _, token = await read(world, world.tenant)
    await migrate_database(world.store, world.database, [(LIB, lib_chain)], STAMPS)
    after, _, new_token = await read(world, world.tenant)
    subject = URIRef(world.book)
    assert new_token != token, "the version token is new"
    assert list(after.objects(subject, DCTERMS.modified)) == list(
        before.objects(subject, DCTERMS.modified)
    ), "a migration is not an edit"
    async with world.tenancy.tenant_session(world.tenant, CREATOR) as session:
        with pytest.raises(Conflict):
            await session.replace_graph(world.book, list(after), token)


async def test_a_migration_with_no_steps_leaves_every_token(world, tmp_path):
    chain = chain_of(tmp_path / "plain", LIB, migration(LIB, "1", "2"), current="2")
    _, _, token = await read(world, world.tenant)
    await migrate_database(world.store, world.database, [(LIB, chain)], STAMPS)
    assert (await read(world, world.tenant))[2] == token, "no step, no rotation"


# -- TC-27: what a migration leaves alone ------------------------------------------------------------


async def test_a_migration_leaves_loaded_graphs_and_the_registry_and_migrates_owned_parts(
    lib_chain,
):
    made = await make_world(Iris(SETTINGS), SETTINGS)
    await put_stamp(made.store, made.database, LIB, "1")
    iri = f"{made.tenant}/books/{UUID(int=5)}"
    loaded = await made.load(iri, 3 * HOUR)
    await made.commit(iri, [loaded])
    part = skolem_iri(str(graph_iri(iri)))
    await made.store.update(
        made.database,
        f'INSERT DATA {{ GRAPH <{loaded}> {{ <urn:x> <{OLD_ISBN}> "Z" }} '
        f'GRAPH <{graph_iri(iri)}> {{ <{part}> <{OLD_ISBN}> "P" }} }}',
    )
    registry = made.iris.registry(made.tenant)
    before_loaded = await quads_of(made, loaded)
    before_registry = await quads_of(made, registry)
    await migrate_database(made.store, made.database, [(LIB, lib_chain)], STAMPS)
    assert await quads_of(made, loaded) == before_loaded, "the loaded graph is untouched"
    assert await quads_of(made, registry) == before_registry, "the registry entries are equal"
    owned = {(s, p, o) for _, s, p, o in await quads_of(made, graph_iri(iri))}
    assert (str(part), str(ISBN), "P") in owned, "the part moved to the new predicate"
    assert (str(part), str(OLD_ISBN), "P") not in owned, "and left the old one"
    report = await made.sweep()
    assert report.loaded_graphs == [], "a live sweep finds no orphan"
    assert await held(made.store, made.database) == {LIB: "2"}, "the stamps stay"


async def quads_of(world: SimpleNamespace, graph) -> frozenset[tuple]:
    rows = await world.store.query(
        world.database,
        f"SELECT ?g ?s ?p ?o WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} BIND(<{graph}> AS ?g) }}",
    )
    return frozenset(tuple(map(str, row)) for row in rows)


# -- TC-28, TC-29, TC-31, TC-33: a failure ------------------------------------------------------------


async def test_a_failing_second_migration_leaves_the_database_at_the_first_and_names_the_second(
    world, three
):
    world.store.on("update", StoreUnavailable("down"), after=1)
    with pytest.raises(MigrationFailed) as failed:
        await migrate_database(world.store, world.database, [(LIB, three)], STAMPS)
    assert await held(world.store, world.database) == {LIB: "2"}, "1__2 stays applied"
    assert "2__3" in str(failed.value), "the failed migration is named"
    assert world.database in str(failed.value), "the database is named"
    assert LIB in str(failed.value), "the schema is named"
    assert "down" in str(failed.value), "the cause is named"


async def test_a_failing_tenant_is_set_aside_and_the_next_one_runs(world, lib_chain, caplog):
    other = await second_tenant(world)
    await put_stamp(world.store, other.database, LIB, "1")
    await old_book(world, other.id)
    failing, healthy = sorted([world.tenant, other.id])
    databases = {world.tenant: world.database, other.id: other.database}
    before = await quads(world.store, databases[failing])
    world.store.on("update", StoreUnavailable("down"))
    with caplog.at_level(logging.ERROR):
        aside = await migrate_tenants(world.tenancy, world.store, [(LIB, lib_chain)])
    assert aside == {failing}, "the failed tenant is the returned set"
    assert world.tenancy.behind == {failing}, "and the tenancy's"
    assert await quads(world.store, databases[failing]) == before, (
        "its data and stamp are as before"
    )
    assert await held(world.store, databases[healthy]) == {LIB: "2"}, "the other tenant is at 2"
    record = next(r for r in caplog.records if getattr(r, "step", "") == "migrate-tenant")
    assert record.tenant == failing, "the log names the tenant"  # type: ignore[attr-defined]
    assert "1__2" in record.migration, "the log names the migration"  # type: ignore[attr-defined]
    assert "down" in record.cause, "the log gives the cause"  # type: ignore[attr-defined]
    assert record.levelno == logging.ERROR, "at error"
    assert await migrate_tenants(world.tenancy, world.store, [(LIB, lib_chain)]) == set(), (
        "a run that succeeds sets nothing aside"
    )
    assert world.tenancy.behind == set(), "and empties the set"


async def test_each_applied_migration_is_logged_at_info(world, lib_chain, caplog):
    with caplog.at_level(logging.INFO):
        await migrate_database(world.store, world.database, [(LIB, lib_chain)], STAMPS)
    record = next(r for r in caplog.records if getattr(r, "step", "") == "migrate")
    assert record.database == world.database, "the log names the database"  # type: ignore[attr-defined]
    assert "1__2" in record.migration, "and the migration"  # type: ignore[attr-defined]


async def test_a_stamp_that_stays_at_the_old_version_is_a_failure(world, lib_chain):
    async def put_back() -> None:
        world.store.after_update = None
        await world.store.update(
            world.database,
            f'DELETE {{ GRAPH <{STAMPS}> {{ ?s ?p ?o }} }} INSERT {{ GRAPH <{STAMPS}> {{ ?s ?p "1" }} }} '
            f"WHERE {{ GRAPH <{STAMPS}> {{ ?s ?p ?o }} }}",
        )

    world.store.after_update = put_back
    with pytest.raises(MigrationFailed, match="1__2"):
        await migrate_database(world.store, world.database, [(LIB, lib_chain)], STAMPS)


async def test_a_stamp_that_cannot_be_read_back_is_a_failure(world, lib_chain):
    async def lose() -> None:
        world.store.after_update = None
        await world.store.drop_dataset(world.database)

    world.store.after_update = lose
    with pytest.raises(MigrationFailed, match="1__2"):
        await migrate_database(world.store, world.database, [(LIB, lib_chain)], STAMPS)


async def put_two_stamps(world) -> None:
    await put_stamp(world.store, world.database, LIB, "2")


async def put_unknown_stamp(world) -> None:
    await world.store.update(
        world.database,
        f"DELETE WHERE {{ GRAPH <{STAMPS}> {{ ?s ?p ?o }} }}",
    )
    await put_stamp(world.store, world.database, LIB, "9")


@pytest.mark.parametrize("break_stamp", [put_two_stamps, put_unknown_stamp], ids=["two", "unknown"])
async def test_a_stamp_the_chain_cannot_use_sets_the_tenant_aside_and_sends_it_nothing(
    world, lib_chain, break_stamp
):
    await break_stamp(world)
    sent = len(world.store.sent("update"))
    assert await migrate_tenants(world.tenancy, world.store, [(LIB, lib_chain)]) == {
        world.tenant
    }, "the tenant is set aside"
    assert len(world.store.sent("update")) == sent, "nothing was sent to it"


async def test_the_data_of_a_database_set_aside_for_an_unknown_stamp_stays(world, lib_chain):
    await put_unknown_stamp(world)
    before = await quads(world.store, world.database)
    await migrate_tenants(world.tenancy, world.store, [(LIB, lib_chain)])
    assert await quads(world.store, world.database) == before, "nothing changed"


async def test_a_tenant_being_deleted_is_skipped_and_one_whose_database_is_gone_is_set_aside(
    world, lib_chain
):
    deleting = await second_tenant(world)
    gone = await second_tenant(world)
    _, version = await world.tenancy.get(deleting.id)
    world.store.on("drop_dataset", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await world.tenancy.delete(deleting.id, version)  # marks it deleting, then fails to drop
    await world.store.drop_dataset(gone.database)
    sent = len(world.store.sent("update"))
    aside = await migrate_tenants(world.tenancy, world.store, [(LIB, lib_chain)])
    assert aside == {gone.id}, (
        "the tenant whose database is gone is set aside, the deleting one skipped"
    )
    assert len(world.store.sent("update")) == sent + 1, "only the tenant T was sent a request"


# -- TC-32: another instance ---------------------------------------------------------------------------


async def test_a_migration_another_instance_applied_between_is_not_a_failure(world, three):
    other_instance = migration_request(three[1][1], STAMPS)

    async def other_applies_the_next() -> None:
        world.store.after_update = None
        await world.store.update(world.database, other_instance)

    world.store.after_update = other_applies_the_next
    sent = len(world.store.sent("update"))
    await migrate_database(world.store, world.database, [(LIB, three)], STAMPS)
    assert await held(world.store, world.database) == {LIB: "3"}, "the read-back is 3"
    assert len(world.store.sent("update")) == sent + 2, (
        "the runner's request and the other's, no more"
    )
    graph, _, _ = await read(world, world.tenant)
    assert list(graph.objects(URIRef(world.book), ISBN)) == [Literal("A3")], "migrated once"


# -- TC-30, TC-30a, TC-54: the shared databases --------------------------------------------------------


@pytest.fixture
def rp_chain(tmp_path) -> Chain:
    """The toolkit's chain ``[1, 2]``: version 2 renames the label predicate of the records."""
    label = v.predicate(LABEL)
    step = migration(RP, "1", "2", rename(OLD_ISBN, label))
    return chain_of(tmp_path / "rp", RP, step, current="2")


async def test_a_failing_system_database_stops_the_shared_migration(world, rp_chain, caplog):
    await put_stamp(world.store, world.tenancy.system_database, RP, "1")
    world.store.on("update", StoreUnavailable("down"))
    with caplog.at_level(logging.ERROR), pytest.raises(MigrationFailed):
        await migrate_shared(world.tenancy, world.store, [(RP, rp_chain)])
    record = next(r for r in caplog.records if getattr(r, "step", "") == "migrate-shared")
    assert record.levelno == logging.ERROR, "logged at error"


async def test_the_access_records_decode_only_after_the_system_database_is_migrated(
    world, rp_chain
):
    system = world.tenancy.system_database
    label = v.predicate(LABEL)
    await world.store.update(
        system,
        f"DELETE {{ GRAPH ?g {{ ?s <{label}> ?o }} }} INSERT {{ GRAPH ?g {{ ?s <{OLD_ISBN}> ?o }} }} "
        f"WHERE {{ GRAPH ?g {{ ?s <{label}> ?o . ?s <{v.STATE}> ?state }} }}",
    )
    await put_stamp(world.store, system, RP, "1")
    with pytest.raises(StoredDataInvalid):
        await world.tenancy.tenants()
    await migrate_shared(world.tenancy, world.store, [(RP, rp_chain)])
    assert [t.id for t in await world.tenancy.tenants()] == [world.tenant], "the records decode"


async def test_the_application_database_is_migrated_and_a_new_one_is_stamped_current(
    lib_chain,
):
    made = await make_world(Iris(SETTINGS), SETTINGS, stamps=((LIB, "2"),))
    assert await made.tenancy.ensure_application_database() is True, "this call created it"
    app = made.tenancy.application_database
    assert await held(made.store, app) == {LIB: "2"}, (
        "a new application database is stamped current"
    )
    await made.store.update(app, f"DELETE WHERE {{ GRAPH <{STAMPS}> {{ ?s ?p ?o }} }}")
    await put_stamp(made.store, app, LIB, "1")
    await migrate_shared(made.tenancy, made.store, [(LIB, lib_chain)])
    assert await held(made.store, app) == {LIB: "2"}, "migrated to 2"


async def test_a_failing_application_database_stops_the_shared_migration(lib_chain):
    made = await make_world(Iris(SETTINGS), SETTINGS)
    await made.tenancy.ensure_application_database()
    app = made.tenancy.application_database
    await put_stamp(made.store, app, LIB, "1")
    await put_stamp(made.store, made.tenancy.system_database, LIB, "2")
    made.store.on("update", StoreUnavailable("down"))
    with pytest.raises(MigrationFailed, match=app):
        await migrate_shared(made.tenancy, made.store, [(LIB, lib_chain)])


async def test_the_application_database_is_left_alone_when_it_does_not_exist(world, lib_chain):
    await put_stamp(world.store, world.tenancy.system_database, LIB, "2")
    await migrate_shared(world.tenancy, world.store, [(LIB, lib_chain)])
    assert world.tenancy.application_database not in await world.store.list_datasets(), (
        "the runner does not create it"
    )


# -- TC-35, TC-36 --------------------------------------------------------------------------------------


async def test_a_tenant_set_aside_has_no_session_and_another_has(world, lib_chain):
    other = await second_tenant(world)
    world.tenancy.behind.add(world.tenant)
    with pytest.raises(TenantBehind, match=world.tenant):
        world.tenancy.tenant_session(world.tenant, CREATOR)
    async with world.tenancy.tenant_session(other.id, CREATOR) as session:
        assert session is not None, "the other tenant is served"


async def test_the_toolkits_chain_runs_first_in_every_database(world, lib_chain, rp_chain):
    other = await second_tenant(world)
    for database in (world.database, other.database):
        await put_stamp(world.store, database, RP, "1")
    await put_stamp(world.store, other.database, LIB, "1")
    sent = len(world.store.sent("update"))
    await migrate_tenants(world.tenancy, world.store, [(RP, rp_chain), (LIB, lib_chain)])
    order = ["rp" if f"<{RP}>" in text else "lib" for text in world.store.sent("update")[sent:]]
    assert order == ["rp", "lib", "rp", "lib"], "in each database the toolkit's request is first"


async def test_a_stamp_unknown_to_the_chain_after_a_request_names_the_stamp(world, three):
    """schema-migrations PD-23: the read-back must be ``to`` or later; an unknown version is a failure."""

    async def to_nine() -> None:
        world.store.after_update = None
        await world.store.update(
            world.database,
            f"DELETE WHERE {{ GRAPH <{STAMPS}> {{ <{LIB}> <{v.DATA_SCHEMA_VERSION}> ?o }} }}; "
            f'INSERT DATA {{ GRAPH <{STAMPS}> {{ <{LIB}> <{v.DATA_SCHEMA_VERSION}> "9" }} }}',
        )

    world.store.after_update = to_nine
    with pytest.raises(MigrationFailed) as failed:
        await migrate_database(world.store, world.database, [(LIB, three)], STAMPS)
    assert '"9"' in failed.value.cause, "the stamp read back is named"
    assert "not one of the chain" in failed.value.cause, "and said to be unknown"

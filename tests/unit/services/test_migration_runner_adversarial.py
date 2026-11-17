"""Adversarial tests of the migration runner and the stamps (schema-migrations PD-2, PD-7, PD-9 to PD-11, RISK-2, RISK-3).

Each test attacks one claim: write order and atomicity (a failure at every numbered store call), other
instances (the fake's ``after_update`` hook acts as one), odd stamps, tenants set aside, creation and the
shared databases. A test that fails shows a defect; none is weakened to pass. Helpers come from
``test_migration_runner``.
"""

import asyncio
import io
import logging
from collections.abc import Awaitable, Callable
from types import SimpleNamespace

import pytest
from rdflib import URIRef

from rdf_persistence.domain.exceptions import (
    Conflict,
    MigrationFailed,
    StoredDataInvalid,
    StoreUnavailable,
    TenantBehind,
)
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.iris import Iris
from rdf_persistence.services.migration_runner import (
    migrate_database,
    migrate_shared,
    migrate_tenants,
)
from rdf_persistence.services.migrations import Chain, migration_request
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import LABEL
from rdf_persistence.services.sweep import sweep
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.services.tenant_dump import dump
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import SETTINGS, TOY_SCHEMA, toy_mapper
from tests.unit.services.test_migration_runner import (
    CREATOR,
    ISBN,
    LIB,
    MID_ISBN,
    OLD_ISBN,
    RP,
    STAMPS,
    chain_of,
    held,
    migration,
    old_book,
    put_stamp,
    quads,
    rename,
    second_tenant,
)
from tests.unit.services.test_tenant_sweep import make_world

RP_OLD = URIRef("urn:rp:old")
RP_NEW = URIRef("urn:rp:new")
STAMP = v.DATA_SCHEMA_VERSION
DOWN = StoreUnavailable("down")
SCHEMA_STORE_CALLS = {"query": 6, "update": 4}  # of the clean run in ``test_a_failure_at_each...``


# -- helpers --------------------------------------------------------------------------------------


@pytest.fixture
async def world() -> SimpleNamespace:
    """Tenant ``T`` stamped ``1`` for the consumer's schema, holding a book whose ISBN is under the old predicate."""
    made = await make_world(Iris(SETTINGS), SETTINGS)
    await put_stamp(made.store, made.database, LIB, "1")
    made.book = await old_book(made, made.tenant)
    return made


@pytest.fixture
def lib_chain(tmp_path) -> Chain:
    return chain_of(
        tmp_path / "lib", LIB, migration(LIB, "1", "2", rename(OLD_ISBN, ISBN)), current="2"
    )


@pytest.fixture
def three(tmp_path) -> Chain:
    steps = (
        migration(LIB, "1", "2", rename(OLD_ISBN, MID_ISBN)),
        migration(LIB, "2", "3", rename(MID_ISBN, ISBN)),
    )
    return chain_of(tmp_path / "three", LIB, *steps, current="3")


@pytest.fixture
def rp_one(tmp_path) -> Chain:
    """The toolkit's chain ``[1, 2]``, whose step renames a predicate the tests own."""
    step = migration(RP, "1", "2", rename(RP_OLD, RP_NEW))
    return chain_of(tmp_path / "rp", RP, step, current="2")


async def count(store, database: str, predicate: URIRef) -> int:
    text = f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH ?g {{ ?s <{predicate}> ?o }} }}"
    return int(next(iter(await store.query(database, text))).n)  # type: ignore[union-attr]


async def set_stamp(store, database: str, schema: str, version_text: str) -> None:
    """Replace the stamp of ``schema`` with ``version_text``, written as SPARQL (``"2"``, ``<urn:x>``, ...)."""
    stamps_graph = f"<{STAMPS}>"
    await store.update(
        database,
        f"DELETE WHERE {{ GRAPH {stamps_graph} {{ <{schema}> <{STAMP}> ?o }} }}; "
        f"INSERT DATA {{ GRAPH {stamps_graph} {{ <{schema}> <{STAMP}> {version_text} }} }}",
    )


def another_instance(
    store, act_after: Callable[[int], Callable[[], Awaitable[None]] | None]
) -> None:
    """After the n-th update the store applies, run ``act_after(n)`` (if any) as another instance would."""
    seen = 0

    async def hook() -> None:
        nonlocal seen
        seen += 1
        act = act_after(seen)
        if act is not None:
            store.after_update = None  # its own update must not recurse
            try:
                await act()
            finally:
                store.after_update = hook

    store.after_update = hook


# -- 1. order and atomicity -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("operation", "call"),
    [(op, n) for op, total in SCHEMA_STORE_CALLS.items() for n in range(total)],
)
async def test_a_failure_at_each_store_call_leaves_a_database_a_second_run_completes(
    world, three, rp_one, operation, call
):
    await world.store.update(
        world.database, f'INSERT DATA {{ GRAPH <{world.tenant}/g> {{ <urn:s> <{RP_OLD}> "x" }} }}'
    )
    chains = [(RP, rp_one), (LIB, three)]  # RP has no stamp: stamped, then moved; LIB 1 to 3
    world.store.on(operation, DOWN, after=call)
    with pytest.raises(MigrationFailed):
        await migrate_database(world.store, world.database, chains, STAMPS)
    await migrate_database(world.store, world.database, chains, STAMPS)
    assert await held(world.store, world.database) == {RP: "2", LIB: "3"}, "both stamps are right"
    assert await count(world.store, world.database, ISBN) == 1, (
        "the ISBN is under its predicate once"
    )
    assert await count(world.store, world.database, MID_ISBN) == 0, "none is left in the middle"
    assert await count(world.store, world.database, OLD_ISBN) == 0, "none is left in the old one"
    assert await count(world.store, world.database, RP_NEW) == 1, "the toolkit step ran once"
    assert await count(world.store, world.database, RP_OLD) == 0, "and left nothing behind"


async def test_a_clean_run_makes_the_store_calls_the_matrix_above_counts(world, three, rp_one):
    queries, updates = len(world.store.sent("query")), len(world.store.sent("update"))
    await migrate_database(world.store, world.database, [(RP, rp_one), (LIB, three)], STAMPS)
    assert len(world.store.sent("query")) - queries == SCHEMA_STORE_CALLS["query"], "queries"
    assert len(world.store.sent("update")) - updates == SCHEMA_STORE_CALLS["update"], "updates"


async def test_a_failed_read_back_sets_the_tenant_aside_and_the_next_start_serves_it(
    world, lib_chain
):
    def lose_the_next_query() -> Callable[[], Awaitable[None]]:
        async def act() -> None:
            world.store.on("query", DOWN)

        return act

    another_instance(world.store, lambda n: lose_the_next_query() if n == 1 else None)
    aside = await migrate_tenants(world.tenancy, world.store, [(LIB, lib_chain)])
    assert aside == {world.tenant}, "the request went through but the read-back failed"
    assert await held(world.store, world.database) == {LIB: "2"}, "the data is migrated"
    sent = len(world.store.sent("update"))
    assert await migrate_tenants(world.tenancy, world.store, [(LIB, lib_chain)]) == set(), (
        "the next start finds it current"
    )
    assert len(world.store.sent("update")) == sent, "and sends nothing"
    assert world.tenancy.behind == set(), "and serves it"


# -- 2. other instances ---------------------------------------------------------------------------


async def test_another_instance_sending_the_same_request_after_ours_changes_nothing(
    world, lib_chain
):
    twin = migration_request(lib_chain[1][0], STAMPS)

    async def send_twin() -> None:
        await world.store.update(world.database, twin)

    another_instance(world.store, lambda n: send_twin if n == 1 else None)
    await migrate_database(world.store, world.database, [(LIB, lib_chain)], STAMPS)
    assert await held(world.store, world.database) == {LIB: "2"}, "the stamp is 2"
    assert await count(world.store, world.database, ISBN) == 1, "migrated once"


async def test_another_instance_applying_every_remaining_migration_ends_the_run_at_the_last(
    world, three
):
    rest = [migration_request(step, STAMPS) for step in three[1][1:]]

    async def finish() -> None:
        for request in rest:
            await world.store.update(world.database, request)

    another_instance(world.store, lambda n: finish if n == 1 else None)
    await migrate_database(world.store, world.database, [(LIB, three)], STAMPS)
    assert await held(world.store, world.database) == {LIB: "3"}, "at the last version"
    assert await count(world.store, world.database, ISBN) == 1, "migrated once"


async def test_another_instance_finishing_the_consumer_chain_while_this_one_is_on_the_toolkits(
    world, three, rp_one
):
    await put_stamp(world.store, world.database, RP, "1")
    requests = [migration_request(step, STAMPS) for step in three[1]]

    async def finish_consumer() -> None:
        for request in requests:
            await world.store.update(world.database, request)

    another_instance(world.store, lambda n: finish_consumer if n == 1 else None)
    sent = len(world.store.sent("update"))
    await migrate_database(world.store, world.database, [(RP, rp_one), (LIB, three)], STAMPS)
    assert await held(world.store, world.database) == {RP: "2", LIB: "3"}, "both are current"
    assert len(world.store.sent("update")) - sent == 1 + len(requests), "ours, then the other's"
    assert await count(world.store, world.database, ISBN) == 1, "migrated once"


class RacingStore(FakeStore):
    """A fake store that lets another writer act just before the first update it receives."""

    def __init__(self) -> None:
        super().__init__()
        self.before_first: Callable[[], Awaitable[None]] | None = None

    async def update(self, dataset: str, sparql: str) -> None:
        act, self.before_first = self.before_first, None
        if act is not None:
            await act()
        await super().update(dataset, sparql)


async def test_a_stamp_another_writer_set_first_with_another_version_is_the_one_migrated_from(
    three,
):
    store = RacingStore()
    await store.create_dataset("db")
    await store.update("db", f'INSERT DATA {{ GRAPH <urn:g> {{ <urn:s> <{MID_ISBN}> "A3" }} }}')

    async def other_stamps_two() -> None:
        await put_stamp(store, "db", LIB, "2")

    store.before_first = other_stamps_two
    await migrate_database(store, "db", [(LIB, three)], STAMPS)
    assert await held(store, "db") == {LIB: "3"}, "the loser follows the first writer's stamp"
    assert await count(store, "db", ISBN) == 1, "the 2 to 3 step ran, once"
    assert await count(store, "db", MID_ISBN) == 0, "and nothing is left in the middle"


async def test_a_stamp_moved_backwards_after_the_last_request_is_a_failure(world, three):
    async def back_to_one() -> None:
        await set_stamp(world.store, world.database, LIB, '"1"')

    another_instance(world.store, lambda n: back_to_one if n == 2 else None)
    with pytest.raises(MigrationFailed):  # PD-7: the read-back must be ``to`` or later
        await migrate_database(world.store, world.database, [(LIB, three)], STAMPS)


async def test_a_stamp_moved_to_an_unknown_version_between_requests_is_a_failure(world, three):
    async def to_nine() -> None:
        await set_stamp(world.store, world.database, LIB, '"9"')

    another_instance(world.store, lambda n: to_nine if n == 1 else None)
    with pytest.raises(MigrationFailed, match="9"):
        await migrate_database(world.store, world.database, [(LIB, three)], STAMPS)


async def test_a_hostile_writer_moving_the_stamp_back_after_every_second_request_cannot_loop_the_runner(
    world, three
):
    async def back_to_one() -> None:
        await set_stamp(world.store, world.database, LIB, '"1"')

    budget = 40  # the hostile writer stops after this many updates, so the test ends either way
    another_instance(world.store, lambda n: back_to_one if n % 2 == 0 and n < budget else None)
    failure = None
    try:
        await migrate_database(world.store, world.database, [(LIB, three)], STAMPS)
    except MigrationFailed as error:
        failure = error
    assert len(world.store.sent("update")) < budget, "the runner gave up before the writer did"
    assert failure is not None, "and it gave up with a failure"


# -- 3. stamps ------------------------------------------------------------------------------------


# equivalence class: surrounding whitespace (leading space; trailing space and newline are the same)
@pytest.mark.parametrize(
    "stamp_text",
    ["<urn:v:1>", '""', '" 1"', '"01"'],
    ids=["iri", "empty", "leading-space", "zero-padded"],
)
async def test_a_stamp_that_is_not_exactly_a_version_sets_the_tenant_aside_and_sends_nothing(
    world, lib_chain, stamp_text
):
    await set_stamp(world.store, world.database, LIB, stamp_text)
    before, sent = await quads(world.store, world.database), len(world.store.sent("update"))
    assert await migrate_tenants(world.tenancy, world.store, [(LIB, lib_chain)]) == {
        world.tenant
    }, "set aside"
    assert len(world.store.sent("update")) == sent, "nothing was sent"
    assert await quads(world.store, world.database) == before, "the data is as it was"


@pytest.mark.parametrize(
    "stamp_text",
    ['"1"^^<http://www.w3.org/2001/XMLSchema#integer>', '"1"@en'],
    ids=["typed", "language-tagged"],
)
async def test_a_stamp_that_is_not_a_plain_string_is_not_read_as_a_version(
    world, lib_chain, stamp_text
):
    await set_stamp(world.store, world.database, LIB, stamp_text)
    aside = await migrate_tenants(world.tenancy, world.store, [(LIB, lib_chain)])
    assert aside == {world.tenant}, "PD-2: a stamp is the plain string of the version"


async def test_versions_that_differ_only_by_case_are_different_versions(world, tmp_path):
    letters = chain_of(
        tmp_path / "letters", LIB, migration(LIB, "a", "b", rename(OLD_ISBN, ISBN)), current="b"
    )
    await set_stamp(world.store, world.database, LIB, '"A"')
    assert await migrate_tenants(world.tenancy, world.store, [(LIB, letters)]) == {world.tenant}, (
        "a version differing only by case is migrated"
    )


async def test_a_stamp_of_a_schema_the_chains_do_not_know_is_left_alone(world, lib_chain):
    await put_stamp(world.store, world.database, "https://example.org/ns/other", "x7")
    await migrate_database(world.store, world.database, [(LIB, lib_chain)], STAMPS)
    assert await held(world.store, world.database) == {
        LIB: "2",
        "https://example.org/ns/other": "x7",
    }, "the third schema's stamp is as it was"


async def test_a_schema_id_that_is_a_prefix_of_another_does_not_share_its_stamp(world, lib_chain):
    longer = f"{LIB}/more"
    await put_stamp(world.store, world.database, longer, "9")
    await migrate_database(world.store, world.database, [(LIB, lib_chain)], STAMPS)
    assert await held(world.store, world.database) == {LIB: "2", longer: "9"}, "two stamps"


async def test_a_stamp_in_a_graph_that_is_not_the_stamps_graph_is_ignored(world, lib_chain):
    other = await second_tenant(world)
    await old_book(world, other.id)
    await world.store.update(
        other.database, f'INSERT DATA {{ GRAPH <urn:elsewhere> {{ <{LIB}> <{STAMP}> "2" }} }}'
    )
    await migrate_database(world.store, other.database, [(LIB, lib_chain)], STAMPS)
    assert await held(world.store, other.database) == {LIB: "2"}, "stamped 1 in its graph, moved"
    assert await count(world.store, other.database, ISBN) == 1, "the data was migrated"


async def test_a_database_holding_the_stamp_of_one_schema_gets_the_other_stamped_first(
    world, lib_chain, rp_one
):
    await world.store.update(
        world.database, f"DELETE WHERE {{ GRAPH ?g {{ <{LIB}> <{STAMP}> ?o }} }}"
    )
    await put_stamp(world.store, world.database, RP, "1")
    await migrate_database(world.store, world.database, [(RP, rp_one), (LIB, lib_chain)], STAMPS)
    assert await held(world.store, world.database) == {RP: "2", LIB: "2"}, "each from its own"
    assert await count(world.store, world.database, ISBN) == 1, "the consumer's data migrated"


# -- 4. tenants -----------------------------------------------------------------------------------


async def test_one_failing_tenant_among_three_is_set_aside_and_the_others_run_in_iri_order(
    world, lib_chain
):
    others = [await second_tenant(world), await second_tenant(world)]
    for other in others:
        await put_stamp(world.store, other.database, LIB, "1")
    order = [t.id for t in await world.tenancy.tenants()]
    assert order == sorted(order), "tenants come in IRI order"
    world.store.on("update", DOWN, after=1)  # the second tenant's request
    assert await migrate_tenants(world.tenancy, world.store, [(LIB, lib_chain)]) == {order[1]}, (
        "the second is set aside"
    )
    for tenant in (order[0], order[2]):
        assert await held(world.store, world.tenancy.database_of(tenant)) == {LIB: "2"}, tenant
    assert await held(world.store, world.tenancy.database_of(order[1])) == {LIB: "1"}, "kept at 1"


async def test_a_tenant_set_aside_and_deleted_before_the_next_run_leaves_nothing_behind(
    world, lib_chain
):
    other = await second_tenant(world)
    await put_stamp(world.store, other.database, LIB, "1")
    world.store.on("update", DOWN)
    aside = await migrate_tenants(world.tenancy, world.store, [(LIB, lib_chain)])
    (failed,) = aside
    _, version = await world.tenancy.get(failed)
    await world.tenancy.delete(failed, version)
    assert await migrate_tenants(world.tenancy, world.store, [(LIB, lib_chain)]) == set(), (
        "the deleted tenant is not in the next run"
    )
    assert world.tenancy.behind == set(), "and not in the set"


async def test_a_tenant_in_behind_is_still_listed_read_dumped_and_swept_and_a_new_one_is_served(
    world,
):
    world.tenancy.set_aside([world.tenant])
    assert world.tenant in [t.id for t in await world.tenancy.tenants()], "listed"
    record, _ = await world.tenancy.get(world.tenant)
    assert record.database_name == world.database, "read"
    out = io.BytesIO()
    view = load_schema(TOY_SCHEMA)
    await dump(world.tenancy, world.store, world.files, world.iris, view, world.tenant, out)
    assert out.getvalue(), "dumped"
    report = await world.sweep()
    assert report.tenant == world.tenant, "the live sweep ran on the tenant set aside"
    created = await world.tenancy.create("Bruges", {"city": "Bruges"}, CREATOR)
    async with world.tenancy.tenant_session(created.id, CREATOR) as session:
        assert session is not None, "a new tenant is served beside the one set aside"
    with pytest.raises(TenantBehind):
        world.tenancy.tenant_session(world.tenant, CREATOR)


async def test_the_start_up_sweep_keeps_the_database_of_a_tenant_set_aside(world):
    world.tenancy.set_aside([world.tenant])
    await sweep(world.tenancy, world.store, world.files, SETTINGS)
    assert world.database in await world.store.list_datasets(), "its database is not an orphan"


async def test_an_access_record_that_does_not_decode_stops_the_run_and_sends_no_tenant_anything(
    world, lib_chain
):
    label = v.predicate(LABEL)
    await world.store.update(
        world.tenancy.system_database,
        f"DELETE {{ GRAPH ?g {{ ?s <{label}> ?o }} }} INSERT {{ GRAPH ?g {{ ?s <{OLD_ISBN}> ?o }} }} "
        f"WHERE {{ GRAPH ?g {{ ?s <{label}> ?o . ?s <{v.STATE}> ?state }} }}",
    )
    sent = len(world.store.sent("update"))
    with pytest.raises(StoredDataInvalid):
        await migrate_tenants(world.tenancy, world.store, [(LIB, lib_chain)])
    assert len(world.store.sent("update")) == sent, "no tenant was touched"


# -- 5. creation ----------------------------------------------------------------------------------


@pytest.mark.parametrize("failing_stamp", [0, 1], ids=["first-stamp", "second-stamp"])
async def test_a_create_whose_stamp_write_fails_drops_the_database_it_made(
    failing_stamp,
):
    made = await make_world(Iris(SETTINGS), SETTINGS, stamps=((RP, "1"), (LIB, "2")))
    before = sorted(await made.store.list_datasets())
    made.store.on("update", DOWN, after=failing_stamp)
    with pytest.raises(StoreUnavailable):
        await made.tenancy.create("Bruges", {"city": "Bruges"}, CREATOR)
    assert sorted(await made.store.list_datasets()) == before, "the create dropped its database"
    await sweep(made.tenancy, made.store, made.files, SETTINGS)
    assert sorted(await made.store.list_datasets()) == before, "and the sweep has nothing to do"
    assert [t.id for t in await made.tenancy.tenants()] == [made.tenant], "no half tenant"


async def test_two_creates_at_once_make_two_stamped_tenants():
    made = await make_world(Iris(SETTINGS), SETTINGS, stamps=((RP, "1"), (LIB, "2")))
    first, second = await asyncio.gather(
        made.tenancy.create("Bruges", {"city": "Bruges"}, CREATOR),
        made.tenancy.create("Namur", {"city": "Namur"}, CREATOR),
    )
    assert first.id != second.id, "two tenants"
    for tenant in (first.id, second.id):
        database = made.tenancy.database_of(tenant)
        assert await held(made.store, database) == {RP: "1", LIB: "2"}, "stamped current"


async def test_a_worker_that_loses_the_race_to_create_the_system_database_does_not_stamp():
    store, files = FakeStore(), FakeFileStore()
    tenancy = Tenancy(
        store, files, SETTINGS, mapper=toy_mapper(), root_class=Library,
        access_class=LibraryAccess, stamps=((LIB, "2"),),
    )  # fmt: skip
    store.on("create_dataset", Conflict("another worker created it"))
    assert await tenancy.ensure_system_database() is False, "it was not this call's"
    assert store.sent("update") == [], "nothing was stamped over the other worker's"


async def test_an_application_database_found_unstamped_is_not_stamped_current_and_runs_from_one(
    lib_chain,
):
    made = await make_world(Iris(SETTINGS), SETTINGS, stamps=((LIB, "2"),))
    app = made.tenancy.application_database
    await made.store.create_dataset(app)
    await made.store.update(app, f'INSERT DATA {{ GRAPH <urn:g> {{ <urn:s> <{OLD_ISBN}> "A3" }} }}')
    assert await made.tenancy.ensure_application_database() is False, "it was there"
    assert await held(made.store, app) == {}, "found unstamped means first version, not current"
    await migrate_shared(made.tenancy, made.store, [(LIB, lib_chain)])
    assert await count(made.store, app, ISBN) == 1, "so its data was migrated"
    assert await held(made.store, app) == {LIB: "2"}, "and stamped 2 by the runner"


async def test_a_tenancy_built_without_stamps_writes_none():
    made = await make_world(Iris(SETTINGS), SETTINGS)
    assert await held(made.store, made.database) == {}, "the tenant holds no stamp"
    assert await held(made.store, made.tenancy.system_database) == {}, (
        "nor does the system database"
    )
    assert not any("schema-stamps" in text for text in made.store.sent("update")), "none was sent"


# -- 6. the shared databases ----------------------------------------------------------------------


async def test_a_failing_system_database_leaves_the_application_database_untouched(lib_chain):
    made = await make_world(Iris(SETTINGS), SETTINGS)
    await made.tenancy.ensure_application_database()
    app = made.tenancy.application_database
    await put_stamp(made.store, app, LIB, "1")
    await made.store.update(app, f'INSERT DATA {{ GRAPH <urn:g> {{ <urn:s> <{OLD_ISBN}> "A3" }} }}')
    await put_stamp(made.store, made.tenancy.system_database, LIB, "1")
    before = await quads(made.store, app)
    made.store.on("update", DOWN)
    with pytest.raises(MigrationFailed):
        await migrate_shared(made.tenancy, made.store, [(LIB, lib_chain)])
    assert await quads(made.store, app) == before, "the application database was not reached"


async def test_a_shared_failure_is_logged_with_its_database_migration_and_cause(
    world, lib_chain, caplog
):
    system = world.tenancy.system_database
    await put_stamp(world.store, system, LIB, "1")
    world.store.on("update", DOWN)
    with caplog.at_level(logging.ERROR), pytest.raises(MigrationFailed):
        await migrate_shared(world.tenancy, world.store, [(LIB, lib_chain)])
    record = next(r for r in caplog.records if getattr(r, "step", "") == "migrate-shared")
    assert record.database == system, "the database"  # type: ignore[attr-defined]
    assert "1__2" in record.migration, "the migration"  # type: ignore[attr-defined]
    assert "down" in record.cause, "the cause"  # type: ignore[attr-defined]

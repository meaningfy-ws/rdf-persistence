"""Stage 2 of mwb2-adoption-fixes, attacked: consumer validators on tenant writes (PD-7) at their edges."""

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from rdf_persistence.domain.exceptions import Conflict, InvalidBody, NotFound
from rdf_persistence.domain.generated.rp_access import Grant
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.service.rp_service import GrantSet
from rdf_persistence.domain.iris import tenant_resource_name
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import open_session
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, BOB, SETTINGS, library_slots, toy_mapper

CREATOR = Principal(id=ADA)
BEN = Principal(id=BOB)


class MovableStore(FakeStore):
    """A FakeStore that can run a coroutine just before the next update of one dataset: another writer."""

    def __init__(self) -> None:
        super().__init__()
        self._before: tuple[str, Callable[[], Awaitable[None]]] | None = None

    def before_update_of(self, dataset: str, action: Callable[[], Awaitable[None]]) -> None:
        self._before = (dataset, action)

    async def update(self, dataset: str, sparql: str) -> None:
        if self._before and self._before[0] == dataset:
            _, action = self._before
            self._before = None
            await action()
        await super().update(dataset, sparql)


@pytest.fixture
def store() -> MovableStore:
    return MovableStore()


@pytest.fixture
def files() -> FakeFileStore:
    return FakeFileStore()


def _tenancy(store, files, **validators) -> Tenancy:
    return Tenancy(
        store,
        files,
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        **validators,
    )


async def _made(store, files, label="A", **validators) -> tuple[Tenancy, str]:
    """A tenancy with ``validators`` and a tenant made through a validator-free one."""
    plain = _tenancy(store, files)
    await plain.ensure_system_database()
    summary = await plain.create(label, library_slots(), CREATOR)
    return _tenancy(store, files, **validators), summary.id


async def _root(store, tenant: str) -> Library:
    async with open_session(
        store,
        database=tenant_resource_name(SETTINGS.prefix, tenant),
        tenant_iri=tenant,
        principal=CREATOR,
    ) as session:
        return await UnitOfWork(session, toy_mapper()).get(Library, tenant)


async def _root_version(store, tenant: str) -> str:
    async with open_session(
        store,
        database=tenant_resource_name(SETTINGS.prefix, tenant),
        tenant_iri=tenant,
        principal=CREATOR,
    ) as session:
        return (await session.get_graph(tenant))[2]


def _ada(tenant: str) -> Grant:
    return Grant(assignee=ADA, target=tenant, role="librarian")


def _bob(tenant: str) -> Grant:
    return Grant(assignee=BOB, target=tenant, role="librarian")


def _refuse(old, new, who) -> None:
    raise InvalidBody("no")


# -- mutation: does a validator's change of its arguments leak into the write? --


async def test_a_passing_root_validator_that_relabels_the_new_root_on_create_cannot_split_the_tenants_label(
    store, files
):
    def relabel(old, new, who):
        new.label = "Sneaky"

    plain = _tenancy(store, files, root_validators=[relabel])
    await plain.ensure_system_database()
    summary = await plain.create("Ghent", library_slots(), CREATOR)
    record, _ = await plain.get(summary.id)
    root = await _root(store, summary.id)
    assert (record.label, root.label) == ("Ghent", "Ghent"), "a tenant has one label (PD-3)"


async def test_a_passing_root_validator_that_changes_the_id_on_create_cannot_move_the_root(
    store, files
):
    def move(old, new, who):
        new.id = "https://example.org/elsewhere"

    plain = _tenancy(store, files, root_validators=[move])
    await plain.ensure_system_database()
    summary = await plain.create("Ghent", library_slots(), CREATOR)
    assert (await _root(store, summary.id)).id == summary.id, "the root keeps the minted id"
    databases = [d for d in await store.list_datasets() if d.startswith("lib-t-")]
    assert databases == [tenant_resource_name(SETTINGS.prefix, summary.id)], (
        "one database, no orphan"
    )


async def test_a_validator_that_mutates_the_new_grants_leaks_into_the_stored_record(store, files):
    def add_bob(old, new, who):
        new.grants = [*(new.grants or []), _bob(tenant_slot[0])]

    tenant_slot = [""]
    made, tenant = await _made(store, files, grant_validators=[add_bob])
    tenant_slot[0] = tenant
    _, version = await made.get(tenant)
    await made.set_grants(tenant, GrantSet(grants=[_ada(tenant)]), version, CREATOR)
    record, _ = await made.get(tenant)
    assert [g.assignee for g in record.grants or []] == [ADA], (
        "a passing validator changes nothing about the write"
    )


async def test_a_validator_that_mutates_a_grant_of_old_does_not_leak_into_the_record(store, files):
    def demote(old, new, who):
        for grant in old.grants or []:
            grant.role = "reader"

    made, tenant = await _made(store, files, grant_validators=[demote])
    _, version = await made.get(tenant)
    await made.set_grants(tenant, GrantSet(grants=[_bob(tenant)]), version, CREATOR)
    record, _ = await made.get(tenant)
    assert [(g.assignee, g.role) for g in record.grants or []] == [(BOB, "librarian")], (
        "the record holds the body, not what the validator did to old"
    )


async def test_a_validator_that_mutates_old_grants_and_then_refuses_leaves_the_stored_record(
    store, files
):
    def vandal(old, new, who):
        for grant in old.grants or []:
            grant.role = "reader"
        old.grants = []
        raise InvalidBody("no")

    made, tenant = await _made(store, files, grant_validators=[vandal])
    before, version = await made.get(tenant)
    with pytest.raises(InvalidBody):
        await made.set_grants(tenant, GrantSet(), version, CREATOR)
    after, after_version = await made.get(tenant)
    assert (after.grants, after_version) == (before.grants, version), "the refusal left no trace"


async def test_a_validator_that_mutates_old_on_rename_does_not_leak_into_the_stored_root(
    store, files
):
    def vandal(old, new, who):
        old.city = "Mutated"

    made, tenant = await _made(store, files, root_validators=[vandal])
    _, version = await made.get(tenant)
    await made.rename(tenant, "B", version, BEN)
    assert (await _root(store, tenant)).city == "Ghent", "old is a copy"


async def test_a_validator_that_mutates_new_on_rename_and_refuses_leaves_root_and_record_and_versions(
    store, files
):
    def vandal(old, new, who):
        new.label = "Mutated"
        new.city = "Mutated"
        raise InvalidBody("no")

    made, tenant = await _made(store, files, root_validators=[vandal])
    record, version = await made.get(tenant)
    root_version = await _root_version(store, tenant)
    with pytest.raises(InvalidBody):
        await made.rename(tenant, "B", version, BEN)
    root = await _root(store, tenant)
    assert (root.label, root.city) == ("A", "Ghent"), "the root keeps its slots"
    assert await _root_version(store, tenant) == root_version, "the root keeps its version"
    after, after_version = await made.get(tenant)
    assert (after.label, after.description, after_version) == (
        record.label,
        record.description,
        version,
    ), "the record keeps its label, description and version"


async def test_a_passing_root_validator_that_changes_the_label_on_rename_cannot_split_the_label(
    store, files
):
    def relabel(old, new, who):
        new.label = "Sneaky"

    made, tenant = await _made(store, files, root_validators=[relabel])
    _, version = await made.get(tenant)
    await made.rename(tenant, "B", version, BEN)
    record, _ = await made.get(tenant)
    assert (record.label, (await _root(store, tenant)).label) == ("B", "B"), "one label (PD-3)"


async def test_a_root_validator_that_mutates_the_decoded_body_on_a_root_put_changes_nothing_stored(
    store, files
):
    def vandal(old, new, who):
        new.city = "Mutated"
        old.city = "Mutated"

    made, tenant = await _made(store, files, root_validators=[vandal])
    root = await _root(store, tenant)
    triples = toy_mapper().to_triples(root)
    await made.vet_root(tenant, triples, BEN)
    assert (await _root(store, tenant)).city == "Ghent", "vet_root writes nothing"


# -- failures leave no trace --


async def test_a_validator_bug_on_rename_leaves_root_and_record(store, files):
    def broken(old, new, who):
        raise RuntimeError("bug")

    made, tenant = await _made(store, files, root_validators=[broken])
    _, version = await made.get(tenant)
    with pytest.raises(RuntimeError):
        await made.rename(tenant, "B", version, BEN)
    assert ((await made.get(tenant))[0].label, (await _root(store, tenant)).label) == ("A", "A")
    assert (await made.get(tenant))[1] == version, "the record keeps its version"


async def test_a_validator_bug_on_create_leaves_no_database_bucket_or_record(store, files):
    def broken(old, new, who):
        raise RuntimeError("bug")

    plain = _tenancy(store, files, root_validators=[broken])
    await plain.ensure_system_database()
    with pytest.raises(RuntimeError):
        await plain.create("Ghent", library_slots(), CREATOR)
    assert [d for d in await store.list_datasets() if d.startswith("lib-t-")] == [], "no database"
    assert files.sent("create_bucket") == [], "no bucket"
    assert await plain.tenants() == [], "no record"


async def test_a_second_root_validator_refusing_on_create_still_leaves_nothing(store, files):
    plain = _tenancy(store, files, root_validators=[lambda *_: None, _refuse])
    await plain.ensure_system_database()
    with pytest.raises(InvalidBody):
        await plain.create("Ghent", library_slots(), CREATOR)
    assert files.sent("create_bucket") == [], "no bucket"
    assert await plain.tenants() == [], "no record"


async def test_a_stale_rename_is_a_conflict_and_no_root_validator_runs(store, files):
    calls: list[str] = []
    made, tenant = await _made(store, files, root_validators=[lambda *_: calls.append("ran")])
    _, version = await made.get(tenant)
    with pytest.raises(Conflict):
        await made.rename(tenant, "B", version + "x", BEN)
    assert calls == [], "the version check comes first, as before"


# -- ordering: a validator passes, the conditional write loses --


async def test_a_grant_validator_that_passes_before_a_lost_write_leaves_only_the_winners_grants(
    store, files
):
    calls: list[GrantSet] = []
    made, tenant = await _made(store, files, grant_validators=[lambda o, n, w: calls.append(n)])
    _, version = await made.get(tenant)
    winner = GrantSet(grants=[_ada(tenant)])
    loser = GrantSet(grants=[_bob(tenant)])
    database = tenant_resource_name(SETTINGS.prefix, tenant)
    system = made.system_database

    async def other_writer() -> None:
        await made.set_grants(tenant, winner, version, CREATOR)

    store.before_update_of(system, other_writer)
    with pytest.raises(Conflict):
        await made.set_grants(tenant, loser, version, CREATOR)
    record, _ = await made.get(tenant)
    assert [g.assignee for g in record.grants or []] == [ADA], "the loser's grants did not land"
    assert len(calls) == 2, "the validator ran for both writers"
    assert database in await store.list_datasets(), "the tenant is untouched"


async def test_a_rename_that_loses_the_record_race_after_the_validator_passed_reports_a_conflict(
    store, files
):
    made, tenant = await _made(store, files, root_validators=[lambda *_: None])
    _, version = await made.get(tenant)

    async def other_writer() -> None:
        await made.set_grants(tenant, GrantSet(grants=[_ada(tenant)]), version, CREATOR)

    store.before_update_of(made.system_database, other_writer)
    with pytest.raises(Conflict):
        await made.rename(tenant, "B", version, BEN)
    record, _ = await made.get(tenant)
    assert record.label == "A", "the record keeps its label"


async def test_two_renames_at_one_version_that_both_pass_the_validator_land_once(store, files):
    made, tenant = await _made(store, files, root_validators=[lambda *_: None])
    _, version = await made.get(tenant)
    results = await asyncio.gather(
        made.rename(tenant, "B", version, BEN),
        made.rename(tenant, "C", version, BEN),
        return_exceptions=True,
    )
    assert sum(isinstance(r, Conflict) for r in results) == 1, f"exactly one loses: {results}"
    record, _ = await made.get(tenant)
    assert (await _root(store, tenant)).label == record.label, "root and record agree"


# -- the extra read of the stored root on a root PUT --


async def test_vet_root_gives_the_validator_the_root_of_the_tenant_written_not_another(
    store, files
):
    seen: list[str] = []
    plain = _tenancy(store, files)
    await plain.ensure_system_database()
    first = await plain.create("A", library_slots("Ghent"), CREATOR)
    second = await plain.create("B", library_slots("Bruges"), CREATOR)
    made = _tenancy(store, files, root_validators=[lambda old, new, who: seen.append(old.city)])
    root = await _root(store, second.id)
    await made.vet_root(second.id, toy_mapper().to_triples(root), CREATOR)
    assert (seen, first.id != second.id) == (["Bruges"], True), "the stored root of the second"


async def test_vet_root_of_an_unknown_tenant_is_not_found_with_validators(store, files):
    made, tenant = await _made(store, files, root_validators=[lambda *_: None])
    root = await _root(store, tenant)
    with pytest.raises(NotFound):
        await made.vet_root(tenant + "x", toy_mapper().to_triples(root), CREATOR)


async def test_vet_root_with_the_tenant_database_gone_does_not_read_when_no_validators_given(
    store, files
):
    made, tenant = await _made(store, files)
    root = await _root(store, tenant)
    triples = list(toy_mapper().to_triples(root))
    reads = len(store.sent("query"))
    await made.vet_root(tenant, triples, CREATOR)
    # the record read is the only query: the default path adds no read of the root
    assert len(store.sent("query")) - reads == 1, "one read, of the record, as before"


# -- async validators, empty sequences, later changes --


async def test_an_async_grant_validator_is_refused_at_construction(store, files):
    async def refuse(old, new, who):
        raise InvalidBody("no")

    with pytest.raises(TypeError, match="not async"):
        _tenancy(store, files, grant_validators=[refuse])


async def test_an_async_root_validator_is_refused_at_construction(store, files):
    async def refuse(old, new, who):
        raise InvalidBody("no")

    with pytest.raises(TypeError, match="not async"):
        _tenancy(store, files, root_validators=[refuse])


async def test_empty_validator_sequences_leave_every_write_working(store, files):
    made, tenant = await _made(store, files, grant_validators=[], root_validators=())
    _, version = await made.get(tenant)
    version = await made.set_grants(tenant, GrantSet(), version, CREATOR)
    await made.rename(tenant, "B", version, CREATOR)
    assert (await made.get(tenant))[0].label == "B", "the writes landed"


async def test_a_validator_added_to_the_callers_list_after_construction_is_ignored(store, files):
    validators: list = []
    made, tenant = await _made(store, files, grant_validators=validators)
    validators.append(_refuse)
    _, version = await made.get(tenant)
    await made.set_grants(tenant, GrantSet(), version, CREATOR)


async def test_a_generator_of_validators_runs_on_every_write_not_just_the_first(store, files):
    calls: list[str] = []
    made, tenant = await _made(
        store, files, grant_validators=(v for v in [lambda *_: calls.append("ran")])
    )
    _, version = await made.get(tenant)
    version = await made.set_grants(tenant, GrantSet(), version, CREATOR)
    await made.set_grants(tenant, GrantSet(), version, CREATOR)
    assert calls == ["ran", "ran"], "one validator, two writes"


async def test_a_root_validator_is_not_run_by_set_grants_and_a_grant_validator_not_by_rename(
    store, files
):
    calls: list[str] = []
    made, tenant = await _made(
        store,
        files,
        grant_validators=[lambda *_: calls.append("grant")],
        root_validators=[lambda *_: calls.append("root")],
    )
    _, version = await made.get(tenant)
    await made.set_grants(tenant, GrantSet(), version, CREATOR)
    assert calls == ["grant"], "only the grant validator ran on set_grants"
    calls.clear()
    _, version = await made.get(tenant)
    await made.rename(tenant, "B", version, CREATOR)
    assert calls == ["root"], "only the root validator ran on rename"

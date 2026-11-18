"""The service runs the migrations (schema-migrations 2.3): TC-34 (stamps), TC-38, TC-39, TC-39a and the lifespan order of PD-9."""

from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI

from rdf_persistence.core.domain.exceptions import InvalidMigration
from rdf_persistence.entrypoints.service import install_service
from rdf_persistence.migrations.services.generated.rp_migrations_services import Migration
from rdf_persistence.migrations.services.migrations import stamps, versions
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.schema.services.vocabulary import metamodel
from rdf_persistence.testkit import FakeStore
from tests.fixtures.library import generated
from tests.toy import REVIEW_WORKFLOW, TOY_SCHEMA
from tests.toy_service import TENANT_BODY, ToyService

LIB = "https://example.org/ns/library"
RP = "https://meaningfy.ws/ns/rdf-persistence"


def write_step(folder: Path, schema: str, old: str, new: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    step = Migration(schema_id=schema, from_version=old, to_version=new)
    (folder / f"{old}__{new}.yaml").write_text(
        yaml.safe_dump(step.model_dump(exclude_none=True)), "utf-8"
    )


class LoggedStore(FakeStore):
    """A fake store that remembers each call with the database it was for, in the order sent."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, str]] = []
        self.texts: list[
            str
        ] = []  # the SPARQL of each call, at the index of the call ("" for a drop)

    async def query(self, dataset, sparql):
        self.calls.append(("query", dataset))
        self.texts.append(sparql)
        return await super().query(dataset, sparql)

    async def update(self, dataset, sparql):
        self.calls.append(("update", dataset))
        self.texts.append(sparql)
        await super().update(dataset, sparql)

    async def drop_dataset(self, name):
        self.calls.append(("drop_dataset", name))
        self.texts.append("")
        await super().drop_dataset(name)

    def first(self, kind: str, database: str, mentioning: str) -> int:
        """The index of the first call of ``kind`` on ``database`` whose SPARQL mentions ``mentioning``."""
        return next(
            i
            for i, call in enumerate(self.calls)
            if call == (kind, database) and mentioning in self.texts[i]
        )


async def a_tenant(toy: ToyService) -> str:
    """Start ``toy``, create a tenant through its API, and answer the tenant's id."""
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        created = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
    assert created.status_code == 201, created.text
    return created.headers["location"].rsplit("/", 1)[-1]


async def restamp(toy: ToyService, tenant: str, version: str) -> None:
    """Replace the library stamp of ``tenant`` with ``version``, as another release would have left it."""
    graph, database = (
        toy.kit.tenancy.stamps_graph,
        toy.kit.tenancy.database_of(toy.kit.tenant_iri(tenant)),
    )
    await toy.store.update(database, f"DELETE WHERE {{ GRAPH <{graph}> {{ <{LIB}> ?p ?o }} }}")
    await toy.store.update(
        database,
        f'INSERT DATA {{ GRAPH <{graph}> {{ <{LIB}> <{v.DATA_SCHEMA_VERSION}> "{version}" }} }}',
    )


# --- the kit loads the two chains (PD-9, PD-10, PD-13) ------------------------------------------


def test_the_kit_holds_the_toolkits_chain_first_and_the_consumers_second() -> None:
    kit = ToyService().kit
    assert [schema for schema, _ in kit.chains] == [str(metamodel().schema.id), LIB], (
        "toolkit first"
    )
    assert [versions(chain) for _, chain in kit.chains] == [("1", "2"), ("1",)], (
        "each at its current version"
    )


async def test_a_tenant_created_through_the_service_holds_both_stamps_current() -> None:
    toy = ToyService()
    tenant = await a_tenant(toy)
    database = toy.kit.tenancy.database_of(toy.kit.tenant_iri(tenant))
    held = await stamps(toy.store, database, toy.kit.tenancy.stamps_graph)
    assert held == {RP: "2", LIB: "1"}, "TC-34: both schemas at the versions the service runs"


# --- a bad chain stops the service (TC-38) -------------------------------------------------------


def test_a_consumer_chain_that_forks_stops_the_service(tmp_path) -> None:
    write_step(tmp_path, LIB, "1", "2")
    write_step(tmp_path, LIB, "1", "3")
    with pytest.raises(InvalidMigration) as refused:
        ToyService(migrations=tmp_path)
    assert "1__2" in str(refused.value), "the first forking file is named"
    assert "1__3" in str(refused.value), "the second forking file is named"


# --- the folder is required (TC-39) --------------------------------------------------------------


def test_install_service_without_migrations_is_a_type_error() -> None:
    toy = ToyService()
    wiring = {
        "schema": TOY_SCHEMA,
        "generated": generated,
        "store": toy.store,
        "files": toy.files,
        "identity": toy.kit.identity,
        "verifier": toy.kit.verifier,
        "rules": toy.kit.rules,
        "settings": toy.settings,
        "workflows": [REVIEW_WORKFLOW],
    }
    with pytest.raises(TypeError, match="migrations"):
        install_service(FastAPI(), **wiring)


# --- start-up (PD-9, PD-11) ----------------------------------------------------------------------


async def test_a_tenant_set_aside_is_freed_by_a_later_start_that_succeeds() -> None:
    store = FakeStore()
    tenant = await a_tenant(ToyService(store))
    toy = ToyService(store)
    await restamp(toy, tenant, "9")
    async with toy.app.router.lifespan_context(toy.app):
        assert toy.kit.tenancy.behind == {toy.kit.tenant_iri(tenant)}, (
            "a stamp the chain does not know sets it aside"
        )
    await restamp(toy, tenant, "1")
    async with toy.app.router.lifespan_context(toy.app):
        assert toy.kit.tenancy.behind == set(), "TC-39a: the second start empties the set"


async def test_start_up_migrates_the_system_database_then_sweeps_then_migrates_the_tenants() -> (
    None
):
    store = LoggedStore()
    tenant = await a_tenant(ToyService(store))
    orphan = "lib-t-" + "a" * 32  # the sweep drops it: its drop marks where the sweep ran
    await store.create_dataset(orphan)
    store.calls.clear()
    toy = ToyService(store)
    application = toy.kit.tenancy.application_database
    database = toy.kit.tenancy.database_of(toy.kit.tenant_iri(tenant))
    async with toy.app.router.lifespan_context(toy.app):
        pass
    calls = store.calls
    last_application = max(i for i, call in enumerate(calls) if call == ("query", application))
    sweep = calls.index(("drop_dataset", orphan))
    first_tenant = min(i for i, call in enumerate(calls) if call == ("query", database))
    assert last_application < sweep, "the shared databases are migrated before the sweep"
    assert sweep < first_tenant, "the tenants are migrated after the sweep"


async def test_the_iri_policy_is_recorded_before_the_first_stamp_of_the_system_database_is_read() -> (
    None
):
    store = LoggedStore()
    toy = ToyService(store)
    system = toy.kit.tenancy.system_database
    async with toy.app.router.lifespan_context(toy.app):
        pass
    policy = store.first("update", system, "iri-policy")
    first_stamp_read = store.first("query", system, "schema-stamps")
    assert policy < first_stamp_read, "the policy record is written first, then the stamps are read"

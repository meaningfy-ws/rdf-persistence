"""Adversarial tests of a dump and a restore across schema versions (schema-migrations PD-15, PD-24 item 1, PD-7, PD-11).

A restore takes a client's archive: its manifest and its ``graphs.nq`` are both hostile input. Each test builds the
archive from a real dump with the helpers of ``test_tenant_dump`` and attacks one seam: the manifest against the
stamp, the shape of a stamp, a chain that fails half way, a dump from a service ahead of or behind this one.
"""
# ruff: noqa: F811  (fixtures imported from the tests they extend are named again as test arguments)

import copy
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from rdflib import XSD, URIRef
from rdflib.namespace import SKOS

from rdf_persistence.domain.exceptions import StoredDataInvalid
from rdf_persistence.domain.generated.service.rp_service import MigrationStep, TenantDump
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.iris import stamps_graph_iri
from rdf_persistence.services.migration_runner import migrate_database
from rdf_persistence.services.migrations import SchemaChain
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.services.tenant_dump import dump
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import SETTINGS, toy_mapper
from tests.unit.services.migration_helpers import chain_of, migration, rename
from tests.unit.services.test_tenant_dump import (  # noqa: F401  (the fixtures)
    BOOK_DESCRIPTION,
    CITY,
    LIBRARY_SCHEMA,
    MANIFEST,
    OLD_CITY,
    OLD_DESCRIPTION,
    OWNER,
    RESTORER,
    STAMPS,
    TOOLKIT_SCHEMA,
    TOOLKIT_VERSION,
    VIEW,
    aged,
    chains,
    dumped,
    edited,
    iris_of,
    manifest_of,
    moved,
    populated,
    read_book,
    refused,
    restored,
    stamp_line,
    stamped,
    stamps_held,
    token_of,
    with_stamps,
)
from tests.unit.services.test_tenant_sweep import make_world

STAMPS_GRAPH = stamps_graph_iri(SETTINGS.base)
STAMP = str(v.DATA_SCHEMA_VERSION)
NEXT_TOOLKIT_VERSION = str(
    int(TOOLKIT_VERSION) + 1
)  # what a toolkit migration of these tests moves to


def at_version(version: str):
    """The service's schema view saying it is at ``version``."""
    other = copy.deepcopy(VIEW)
    other.schema.version = version
    return other


def chain_pair(tmp_path: Path, *library, toolkit=(), last: str) -> list[SchemaChain]:
    """The toolkit's chain (``toolkit`` migrations, ending at the toolkit's version, or the next one) and the library's, ending at ``last``."""
    toolkit_last = NEXT_TOOLKIT_VERSION if toolkit else TOOLKIT_VERSION
    return [
        (TOOLKIT_SCHEMA, chain_of(tmp_path / "rp", TOOLKIT_SCHEMA, *toolkit, current=toolkit_last)),
        (LIBRARY_SCHEMA, chain_of(tmp_path / "lib", LIBRARY_SCHEMA, *library, current=last)),
    ]


def running_at(world: SimpleNamespace, toolkit: str, library: str) -> Tenancy:
    """A tenancy over ``world``'s stores whose configured stamps are the given versions."""
    return Tenancy(
        world.store, world.files, SETTINGS, mapper=toy_mapper(), root_class=Library,
        access_class=LibraryAccess, iris=world.iris,
        stamps=((TOOLKIT_SCHEMA, toolkit), (LIBRARY_SCHEMA, library)),
    )  # fmt: skip


def failing_step(old: URIRef, new: URIRef) -> MigrationStep:
    return MigrationStep(
        title="a pattern rdflib cannot run",
        where_pattern=f'?s <{old}> ?o . FILTER(REGEX(?o, "["))',
        delete_pattern=f"?s <{old}> ?o .",
        insert_pattern=f"?s <{new}> ?o .",
    )


async def content_of(world: SimpleNamespace, tenant: str) -> list[str]:
    """What the tenant's database holds, the tenant's id and the version tokens left out, in a fixed order."""
    database = (await world.tenancy.get(tenant))[0].database_name
    tenant_id = world.iris.tenant_id_of(tenant)
    text = (await world.store.export_quads(database)).decode()
    return sorted(
        line.replace(tenant_id, "TID") for line in text.splitlines() if str(v.VERSION) not in line
    )


# -- 1. the manifest against the stamp ------------------------------------------------------------------------


def with_manifest_version(data: bytes, version: str | None) -> bytes:
    def change(payload: bytes) -> bytes:
        found = TenantDump.model_validate_json(payload)
        return found.model_copy(update={"schema_version": version}).model_dump_json().encode()

    return edited(data, MANIFEST, change)


async def test_a_manifest_ahead_of_the_stamp_is_refused_so_no_migration_can_be_skipped(
    aged, chains
):
    """Manifest ``2``, stamp ``1`` (PD-25.9): the version the check accepts is not the one the data follows."""
    data = with_manifest_version(await dumped(aged, view=at_version("2")), "2")
    reason = await refused(aged, data, tenancy=aged.running, view=at_version("2"), chains=chains)
    assert "'2'" in reason, "the reason names both versions"
    assert "'1'" in reason, "the reason names both versions"


async def test_a_manifest_behind_the_stamp_is_refused_so_no_migration_can_run_twice(
    stamped, chains
):
    """Manifest ``1``, stamp ``2`` (PD-25.9)."""
    view = at_version("2")
    data = with_manifest_version(await dumped(stamped, view=view), "1")
    reason = await refused(stamped, data, view=view, chains=chains)
    assert "'2'" in reason, "the reason names both versions"
    assert "'1'" in reason, "the reason names both versions"


async def test_a_manifest_with_no_version_over_a_stamped_dump_is_refused(aged, chains):
    data = with_manifest_version(await dumped(aged, view=at_version("2")), None)
    await refused(aged, data, tenancy=aged.running, view=at_version("2"), chains=chains)


# -- 2. a stamp that is not a plain statement of a version ------------------------------------------------------

BOGUS_STAMPS = {
    "two stamps for the schema": [
        stamp_line(TOOLKIT_SCHEMA, TOOLKIT_VERSION),
        stamp_line(LIBRARY_SCHEMA, "1"),
        stamp_line(LIBRARY_SCHEMA, "2"),
    ],
    "the version an IRI": [
        stamp_line(TOOLKIT_SCHEMA, TOOLKIT_VERSION),
        f"<{LIBRARY_SCHEMA}> <{STAMP}> <urn:version:1> <{STAMPS_GRAPH}> .\n",
    ],
    "the version typed": [
        stamp_line(TOOLKIT_SCHEMA, TOOLKIT_VERSION),
        f'<{LIBRARY_SCHEMA}> <{STAMP}> "1"^^<{XSD.integer}> <{STAMPS_GRAPH}> .\n',
    ],
    "the version language-tagged": [
        stamp_line(TOOLKIT_SCHEMA, TOOLKIT_VERSION),
        f'<{LIBRARY_SCHEMA}> <{STAMP}> "1"@en <{STAMPS_GRAPH}> .\n',
    ],
    "an empty version": [
        stamp_line(TOOLKIT_SCHEMA, TOOLKIT_VERSION),
        stamp_line(LIBRARY_SCHEMA, ""),
    ],
    "a version with a space": [
        stamp_line(TOOLKIT_SCHEMA, TOOLKIT_VERSION),
        stamp_line(LIBRARY_SCHEMA, "1 "),
    ],
    "a stamp of the tenant itself": [
        stamp_line(TOOLKIT_SCHEMA, TOOLKIT_VERSION),
        stamp_line(LIBRARY_SCHEMA, "1"),
        f'<https://example.org/library/libraries/abc> <{STAMP}> "1" <{STAMPS_GRAPH}> .\n',
    ],
    "a statement that is not a stamp": [
        stamp_line(TOOLKIT_SCHEMA, TOOLKIT_VERSION),
        stamp_line(LIBRARY_SCHEMA, "1"),
        stamp_line(LIBRARY_SCHEMA, "1", predicate="urn:other"),
    ],
    "the stamp in a graph that looks like the stamps graph": [
        stamp_line(TOOLKIT_SCHEMA, TOOLKIT_VERSION),
        f'<{LIBRARY_SCHEMA}> <{STAMP}> "1" <{STAMPS_GRAPH}/extra> .\n',
    ],
}


@pytest.mark.parametrize("lines", BOGUS_STAMPS.values(), ids=BOGUS_STAMPS.keys())
async def test_a_hostile_stamps_graph_is_refused_before_anything_is_created(aged, chains, lines):
    data = with_stamps(await dumped(aged, view=at_version("2")), *lines)
    await refused(aged, data, tenancy=aged.running, view=at_version("2"), chains=chains)


@pytest.mark.parametrize(
    "held",
    [f'"2"^^<{XSD.integer}>', '"2"@en'],
    ids=["typed", "language-tagged"],
)
async def test_a_stamp_at_the_running_version_that_is_not_a_plain_literal_is_refused_with_a_chain(
    stamped, chains, held
):
    """Kept, it is a stamp no later migration of the restored tenant can move (its ``from`` guard is a plain literal)."""
    view = at_version("2")
    line = f"<{LIBRARY_SCHEMA}> <{STAMP}> {held} <{STAMPS_GRAPH}> .\n"
    data = with_stamps(
        await dumped(stamped, view=view), stamp_line(TOOLKIT_SCHEMA, TOOLKIT_VERSION), line
    )
    await refused(stamped, data, view=view, chains=chains)


async def test_a_tenant_with_no_stamp_dumps_no_version_and_that_dump_is_refused_by_a_restore(
    chains,
):
    unstamped = await populated(await make_world(iris_of(SETTINGS), SETTINGS, stamps=()))
    assert await stamps_held(unstamped, unstamped.tenant) == {}, "the tenant holds no stamp"
    data = await dumped(unstamped, view=at_version("2"))
    assert manifest_of(data).schema_version is None, "no stamp, no version (PD-10, PD-25.7)"
    await refused(unstamped, data, view=at_version("2"), chains=chains)


# -- 3. the chain does not reach, or fails half way --------------------------------------------------------------


async def test_a_dump_older_than_the_first_version_of_the_chain_is_refused(aged, tmp_path):
    short = chain_pair(tmp_path, migration(LIBRARY_SCHEMA, "2", "3"), last="3")
    data = await dumped(aged, view=at_version("3"))
    reason = await refused(aged, data, tenancy=aged.running, view=at_version("3"), chains=short)
    assert "'2', '3'" in reason, "the reason names the versions the service has"


async def test_a_dump_ahead_of_the_service_is_refused_and_creates_nothing(stamped, tmp_path):
    behind = chain_pair(tmp_path, last="1")
    data = await dumped(stamped, view=at_version("2"))
    assert manifest_of(data).schema_version == "2", "the dump is of a tenant at version 2"
    reason = await refused(stamped, data, view=at_version("1"), chains=behind)
    assert "'1'" in reason, "the reason names the version this service has"


async def test_a_chain_whose_second_migration_fails_creates_nothing_and_the_same_archive_restores_once_fixed(
    aged, tmp_path
):
    first = migration(
        LIBRARY_SCHEMA, "1", "2", rename(OLD_DESCRIPTION, BOOK_DESCRIPTION), rename(OLD_CITY, CITY)
    )
    broken = chain_pair(
        tmp_path / "broken", first,
        migration(LIBRARY_SCHEMA, "2", "3", failing_step(CITY, CITY)), last="3",
    )  # fmt: skip
    fixed = chain_pair(tmp_path / "fixed", first, migration(LIBRARY_SCHEMA, "2", "3"), last="3")
    data = await dumped(aged, view=at_version("3"))
    reason = await refused(
        aged,
        data,
        tenancy=running_at(aged, TOOLKIT_VERSION, "3"),
        view=at_version("3"),
        chains=broken,
    )
    assert f"2__3 of {LIBRARY_SCHEMA}" in reason, "the reason names the migration that failed"
    summary = await restored(
        aged,
        data,
        tenancy=running_at(aged, TOOLKIT_VERSION, "3"),
        view=at_version("3"),
        chains=fixed,
    )
    book = await read_book(aged, summary.id, moved(aged, aged.book, summary.id))
    assert book.description == "A planet.", "the archive was not half migrated by the failed try"


async def test_a_step_that_leaves_the_root_undecodable_is_refused_before_anything_is_created(
    aged, tmp_path
):
    ruin = MigrationStep(
        title="drop every label, the root's included",
        where_pattern=f"?s <{SKOS.prefLabel}> ?o .",
        delete_pattern=f"?s <{SKOS.prefLabel}> ?o .",
    )
    chain = chain_pair(tmp_path, migration(LIBRARY_SCHEMA, "1", "2", ruin), last="2")
    data = await dumped(aged, view=at_version("2"))
    await refused(aged, data, tenancy=aged.running, view=at_version("2"), chains=chain)


async def test_the_toolkits_chain_runs_before_the_libraries_and_both_move_the_data(aged, tmp_path):
    toolkit = [
        migration(
            TOOLKIT_SCHEMA,
            TOOLKIT_VERSION,
            NEXT_TOOLKIT_VERSION,
            rename(OLD_DESCRIPTION, BOOK_DESCRIPTION),
        )
    ]
    library = migration(LIBRARY_SCHEMA, "1", "2", rename(OLD_CITY, CITY))
    both = chain_pair(tmp_path, library, toolkit=toolkit, last="2")
    data = await dumped(aged, view=at_version("2"))
    summary = await restored(
        aged,
        data,
        tenancy=running_at(aged, NEXT_TOOLKIT_VERSION, "2"),
        view=at_version("2"),
        chains=both,
    )
    assert await stamps_held(aged, summary.id) == {
        TOOLKIT_SCHEMA: NEXT_TOOLKIT_VERSION,
        LIBRARY_SCHEMA: "2",
    }, "both stamps moved"
    book = await read_book(aged, summary.id, moved(aged, aged.book, summary.id))
    assert book.description == "A planet.", "the toolkit's migration moved the description"
    assert summary.label == "Ghent", "the library's migration moved the root's city"


# -- 4. round trips --------------------------------------------------------------------------------------------------


async def test_a_dump_before_and_a_dump_after_the_upgrade_restore_to_the_same_data(aged, chains):
    view = at_version("2")
    before = await dumped(aged, view=view)
    assert manifest_of(before).schema_version == "1", "the first dump follows version 1"
    await migrate_database(aged.store, aged.database, chains, stamps_graph_iri(SETTINGS.base))
    after = await dumped(aged, view=view)
    assert manifest_of(after).schema_version == "2", "the tenant was upgraded in place"
    old = await restored(aged, before, tenancy=aged.running, view=view, chains=chains)
    new = await restored(aged, after, tenancy=aged.running, view=view, chains=chains)
    assert await stamps_held(aged, old.id) == await stamps_held(aged, new.id) == dict(STAMPS), (
        "both new tenants are at version 2"
    )
    assert await content_of(aged, old.id) == await content_of(aged, new.id), (
        "the migrated dump and the dump of the migrated tenant hold the same data"
    )


# -- 5. what a dump says about the tenant ---------------------------------------------------------------------------


async def test_a_tenant_set_aside_dumps_its_own_older_version_and_restores_into_a_fixed_service(
    aged, chains
):
    aged.tenancy.set_aside([aged.tenant])
    data = await dumped(aged, view=at_version("2"))
    assert manifest_of(data).schema_version == "1", "the tenant's own version, not the running one"
    summary = await restored(aged, data, tenancy=aged.running, view=at_version("2"), chains=chains)
    book = await read_book(aged, summary.id, moved(aged, aged.book, summary.id))
    assert book.description == "A planet.", "the fixed service migrated it"


async def test_a_tenant_with_two_stamps_is_not_dumped_and_nothing_is_written(aged):
    graph = stamps_graph_iri(SETTINGS.base)
    await aged.store.update(
        aged.database,
        f'INSERT DATA {{ GRAPH <{graph}> {{ <{LIBRARY_SCHEMA}> <{STAMP}> "2" }} }}',
    )
    out = io.BytesIO()
    with pytest.raises(StoredDataInvalid):
        await dump(
            aged.tenancy, aged.store, aged.files, aged.iris, at_version("2"), aged.tenant, out
        )
    assert out.getvalue() == b"", "no byte of an archive was written"

"""The migration request against a real Fuseki (schema-migrations 3.3): TC-40 to TC-42, RISK-4.

The runner sends one update request of several operations per migration and database and relies on the
store applying it atomically, and on the stamp guard to make a second sender's request a no-op. The unit
tests prove this on the fake; these prove it on Fuseki. A tenant's data is written straight into a fresh
dataset: a book graph per aggregate (with an owned part under a skolem IRI), a loaded graph, the registry.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import DCTERMS, XSD

from rdf_persistence.adapters.fuseki import FusekiStore
from rdf_persistence.domain.exceptions import PersistenceError
from rdf_persistence.domain.generated.rp_core import RegistryKind
from rdf_persistence.domain.generated.service.rp_service import MigrationStep
from rdf_persistence.domain.layout import graph_iri, skolem_iri
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.iris import DEFAULT_IRIS
from rdf_persistence.services.migration_runner import migrate_database
from rdf_persistence.services.migrations import Chain, migration_request, stamp_if_none, stamps
from tests.unit.services.test_migration_runner import (
    ISBN,
    LIB,
    MID_ISBN,
    OLD_ISBN,
    STAMPS,
    chain_of,
    migration,
    rename,
)

TENANT = "https://example.org/tenant/t1"
BOOKS = tuple(URIRef(f"{TENANT}/books/{n}") for n in (1, 2))
LOADED = URIRef(f"{TENANT}/loaded/1")
REGISTRY = DEFAULT_IRIS.registry(TENANT)
COUNTER = URIRef("https://example.org/ns/library#counter")
MODIFIED = Literal("2026-01-01T00:00:00Z", datatype=XSD.dateTime)
SAME_TOKEN = Literal("one-token-for-all")
ALL = "SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } }"
TOKENS = "SELECT ?g ?t WHERE { GRAPH ?g { ?g $p_version ?t } }"
REPETITIONS = 5
SOMEWHERE = URIRef("http://example.org/g")
MISSING = "<http://example.org/missing>"

SEED = (
    "INSERT DATA { "
    "GRAPH $stamps { $lib $p_stamp $one } "
    "GRAPH $g1 { $b1 $old 'A3' . $b1 $modified $when . $part $old 'P' . $g1 $p_version $token } "
    "GRAPH $g2 { $b2 $old 'B4' . $b2 $modified $when . $g2 $p_version $token } "
    "GRAPH $loaded { $x $old 'Z' } "
    "GRAPH $registry { $loaded $p_kind $loaded_kind . $loaded $old 'R' } }"
)
INSERT_ONE = "INSERT DATA { GRAPH $graph { $s $p $o } }"
COUNT_UP = MigrationStep(
    title="count the applications",
    where_pattern=f"?s <{COUNTER}> ?n . BIND (?n + 1 AS ?m)",
    delete_pattern=f"?s <{COUNTER}> ?n .",
    insert_pattern=f"?s <{COUNTER}> ?m .",
)


@pytest.fixture
async def database(store: FusekiStore) -> AsyncIterator[str]:
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


async def seed(store: FusekiStore, database: str, counter: bool = False) -> SimpleNamespace:
    """Two book graphs with one token, a part in the first, a loaded graph and its registry entry; stamp 1."""
    g1, g2 = graph_iri(str(BOOKS[0])), graph_iri(str(BOOKS[1]))
    part = skolem_iri(str(g1))
    text = fill(
        SEED,
        stamps=term(STAMPS), lib=term(URIRef(LIB)), p_stamp=term(v.DATA_SCHEMA_VERSION),
        one=term(Literal("1")), g1=term(g1), g2=term(g2), b1=term(BOOKS[0]), b2=term(BOOKS[1]),
        old=term(OLD_ISBN), modified=term(DCTERMS.modified), when=term(MODIFIED), part=term(part),
        p_version=term(v.VERSION), token=term(SAME_TOKEN), loaded=term(LOADED), x=term(URIRef("urn:x")),
        registry=term(REGISTRY), p_kind=term(v.REGISTRY_KIND),
        loaded_kind=term(v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]),
    )  # fmt: skip
    await store.update(database, text)
    if counter:
        await store.update(database, add_one(g1, BOOKS[0], Literal(0)))
    return SimpleNamespace(g1=g1, g2=g2, part=part)


def add_one(graph: URIRef, subject: URIRef, obj: Literal) -> str:
    return fill(INSERT_ONE, graph=term(graph), s=term(subject), p=term(COUNTER), o=term(obj))


async def quads(store: FusekiStore, database: str) -> frozenset[tuple]:
    return frozenset(tuple(map(str, row)) for row in await store.query(database, ALL))


async def in_graph(store: FusekiStore, database: str, graph: URIRef) -> frozenset[tuple]:
    return frozenset(row for row in await quads(store, database) if row[0] == str(graph))


async def tokens(store: FusekiStore, database: str) -> dict[str, str]:
    rows = await store.query(database, fill(TOKENS, p_version=term(v.VERSION)))
    return {str(row.g): str(row.t) for row in rows}  # type: ignore[union-attr]


async def values(
    store: FusekiStore, database: str, subject: URIRef, predicate: URIRef
) -> list[str]:
    found = await quads(store, database)
    return sorted(row[3] for row in found if row[1] == str(subject) and row[2] == str(predicate))


def one_step_chain(folder: Path) -> Chain:
    step = migration(LIB, "1", "2", rename(OLD_ISBN, ISBN))
    return chain_of(folder / "one", LIB, step, current="2")


def counting_chain(folder: Path) -> Chain:
    """``[1, 2, 3]``: each migration adds one to a counter and renames, so a migration applied twice shows."""
    steps = (
        migration(LIB, "1", "2", COUNT_UP, rename(OLD_ISBN, MID_ISBN)),
        migration(LIB, "2", "3", COUNT_UP, rename(MID_ISBN, ISBN)),
    )
    return chain_of(folder / "count", LIB, *steps, current="3")


# -- TC-40: the store applies the request atomically (RISK-4) ---------------------------------------

FIRST = add_one(SOMEWHERE, BOOKS[0], Literal("one"))
SECOND = fill(
    INSERT_ONE,
    graph=term(STAMPS),
    s=term(URIRef(LIB)),
    p=term(v.DATA_SCHEMA_VERSION),
    o=term(Literal("2")),
)
# Both parse; Fuseki answers 500 only when it runs them (a graph that does not exist, an unreachable URL).
FAILS_WHEN_RUN = [
    "LOAD <http://127.0.0.1:1/unreachable.ttl> INTO GRAPH <http://example.org/g>",
    f"ADD GRAPH {MISSING} TO GRAPH <http://example.org/g>",
]


@pytest.mark.parametrize("last", FAILS_WHEN_RUN)
async def test_a_request_whose_last_operation_fails_when_run_changes_nothing(store, database, last):
    with pytest.raises(PersistenceError):
        await store.update(database, ";\n".join([FIRST, SECOND, last]))
    assert await quads(store, database) == frozenset(), (
        "neither the data of the first operation nor the stamp of the second is there"
    )


async def test_the_first_two_operations_alone_do_change_the_data(store, database):
    await store.update(database, ";\n".join([FIRST, SECOND]))
    assert len(await quads(store, database)) == 2, "the control: the data and the stamp are written"


# -- TC-41: TC-24, TC-26 and TC-27 on Fuseki ---------------------------------------------------------


@pytest.fixture
async def migrated(store, database, tmp_path) -> SimpleNamespace:
    """A seeded database, before and after the runner moved it from 1 to 2."""
    made = await seed(store, database)
    made.before = await quads(store, database)
    made.tokens_before = await tokens(store, database)
    await migrate_database(store, database, [(LIB, one_step_chain(tmp_path))], STAMPS)
    return made


async def test_the_value_moves_to_the_new_predicate(store, database, migrated):
    assert await values(store, database, BOOKS[0], ISBN) == ["A3"], "the new predicate holds it"
    assert await values(store, database, BOOKS[0], OLD_ISBN) == [], "the old one holds nothing"


async def test_the_stamp_moves_to_the_new_version(store, database, migrated):
    assert await stamps(store, database, STAMPS) == {LIB: "2"}, "the stamp is 2"


async def test_the_token_of_each_graph_is_renewed_and_differs_from_the_other(
    store, database, migrated
):
    after = await tokens(store, database)
    assert set(after) == {str(migrated.g1), str(migrated.g2)}, "both book graphs keep a token"
    assert str(SAME_TOKEN) not in after.values(), "the token is renewed in each graph"
    assert after[str(migrated.g1)] != after[str(migrated.g2)], "STRUUID() gives one per row"


async def test_the_modified_date_stays(store, database, migrated):
    assert await values(store, database, BOOKS[0], DCTERMS.modified) == [str(MODIFIED)], (
        "a migration is not an edit"
    )


async def test_the_loaded_graph_and_the_registry_graph_are_untouched(store, database, migrated):
    for graph in (LOADED, REGISTRY):
        before = frozenset(row for row in migrated.before if row[0] == str(graph))
        assert await in_graph(store, database, graph) == before, f"{graph} is as it was"


async def test_an_owned_part_is_migrated_with_its_aggregate(store, database, migrated):
    assert await values(store, database, migrated.part, ISBN) == ["P"], "the part has the new one"
    assert await values(store, database, migrated.part, OLD_ISBN) == [], "and not the old one"


async def test_a_second_run_changes_nothing(store, database, migrated, tmp_path):
    once = await quads(store, database)
    await migrate_database(store, database, [(LIB, one_step_chain(tmp_path))], STAMPS)
    assert await quads(store, database) == once, (
        "tokens, data and stamp are as the first run left them"
    )


async def test_the_same_request_sent_again_changes_nothing(store, database, migrated, tmp_path):
    request = migration_request(one_step_chain(tmp_path)[1][0], STAMPS)
    once = await quads(store, database)
    await store.update(database, request)
    assert await quads(store, database) == once, "the stamp guard matches nothing the second time"


# -- TC-42: two instances at once --------------------------------------------------------------------


@pytest.mark.parametrize("round_", range(REPETITIONS))
async def test_two_runners_at_once_migrate_a_database_exactly_once(
    store, database, tmp_path, round_
):
    made = await seed(store, database, counter=True)
    chain = counting_chain(tmp_path)
    await asyncio.gather(
        migrate_database(store, database, [(LIB, chain)], STAMPS),
        migrate_database(store, database, [(LIB, chain)], STAMPS),
    )
    assert await stamps(store, database, STAMPS) == {LIB: "3"}, "the stamp is 3"
    assert await values(store, database, BOOKS[0], COUNTER) == ["2"], (
        "two migrations, each applied once: a second application would count more"
    )
    assert await values(store, database, BOOKS[0], ISBN) == ["A3"], (
        "the value is under the last predicate"
    )
    assert await values(store, database, BOOKS[0], MID_ISBN) == [], "none is left on the middle one"
    assert await values(store, database, made.part, ISBN) == ["P"], "the owned part followed"


async def test_two_conditional_first_stamps_at_once_leave_one_stamp(store, database):
    await asyncio.gather(
        stamp_if_none(store, database, STAMPS, LIB, "1"),
        stamp_if_none(store, database, STAMPS, LIB, "2"),
    )
    assert len(await stamps(store, database, STAMPS)) == 1, "one schema, one stamp"
    rows = await in_graph(store, database, STAMPS)
    assert len(rows) == 1, "one statement in the stamps graph, not two"

"""What the migration tests share: the library schema's ids, the ISBN predicates, the builders of a chain,
and the worlds the runner and the in-memory migration tests build.

Not collected as tests; the migration, dump, unit and integration tests import from here.
"""

from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import yaml
from rdflib import Dataset, Graph, Literal, URIRef

from rdf_persistence.access.domain.generated.rp_access import Grant
from rdf_persistence.access.domain.generated.rp_tenancy import TenantAccess, TenantState
from rdf_persistence.access.services.access import _access_mapper
from rdf_persistence.core.domain.generated.rp_core import RegistryKind
from rdf_persistence.iris.domain.layout import graph_iri, stamps_graph_iri
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.migrations.services.generated.rp_migrations_services import (
    Migration,
    MigrationStep,
)
from rdf_persistence.migrations.services.migrations import Chain, load_chain
from rdf_persistence.schema.services import vocabulary as v
from tests.tenancy_world import CREATOR
from tests.toy import DATABASE, SETTINGS, TENANT, dune, library_slots, toy_mapper

LIB = "https://example.org/ns/library"
RP = "https://meaningfy.ws/ns/rdf-persistence"
ISBN = URIRef("http://purl.org/ontology/bibo/isbn")
OLD_ISBN = URIRef("https://example.org/ns/library#oldIsbn")
MID_ISBN = URIRef("https://example.org/ns/library#midIsbn")
STAMPS = stamps_graph_iri(SETTINGS.base)
ALL = "SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } }"
BOOK = URIRef("https://example.org/library/libraries/t/books/b")
LOADED = URIRef("https://example.org/library/libraries/t/loaded/l")
REGISTRY = URIRef("https://example.org/library/libraries/t/registry")
TOKEN = Literal("token-1")
STAMP = URIRef(str(v.DATA_SCHEMA_VERSION))
OTHER_TENANT = "https://example.org/libraries/0b2e44d1"
BOOK_GRAPH = f"{TENANT}/books/b1"  # an aggregate's graph: a grant on it is an aggregate-level grant
RECORD = Iris(SETTINGS).access(TENANT)
OTHER_RECORD = Iris(SETTINGS).access(OTHER_TENANT)
ACCESS_TOKEN = Literal("access-token-1")

# (assignee, target, role): a grant as the tests state it
Held = set[tuple[str, str, str | None]]


def the_record(iri: URIRef, tenant: str, held: Held) -> Graph:
    """The access record of ``tenant`` holding ``held`` as grants, as the mapper writes it, with a version token."""
    record = TenantAccess(
        id=str(iri), label="Library", state=TenantState.ACTIVE, database_name=DATABASE,
        grants=[Grant(assignee=a, target=t, role=r) for a, t, r in sorted(held)],
    )  # fmt: skip
    graph = _access_mapper().to_graph(record)
    graph.add((graph_iri(str(iri)), v.VERSION, ACCESS_TOKEN))
    return graph


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


async def second_tenant(world: SimpleNamespace) -> SimpleNamespace:
    summary = await world.tenancy.create("Bruges", library_slots(), CREATOR)
    return SimpleNamespace(id=summary.id, database=world.tenancy.database_of(summary.id))


def stamp(schema: str, version: str) -> tuple[URIRef, URIRef, Literal]:
    return URIRef(schema), STAMP, Literal(version)


def dataset(
    *stamps: tuple[URIRef, URIRef, Literal], isbn: URIRef = OLD_ISBN, kind: type[Dataset] = Dataset
) -> Dataset:
    """A dump of class ``kind`` with the given stamps, a book whose ISBN is under ``isbn``, a loaded graph and its registry."""
    data = kind()
    for statement in stamps:
        data.graph(STAMPS).add(statement)
    data.graph(BOOK).add((BOOK, v.VERSION, TOKEN))
    data.graph(BOOK).add((BOOK, isbn, Literal("A3")))
    data.graph(LOADED).add((BOOK, OLD_ISBN, Literal("loaded")))
    data.graph(REGISTRY).add(
        (LOADED, v.REGISTRY_KIND, v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH])
    )
    data.graph(REGISTRY).add((REGISTRY, OLD_ISBN, Literal("registry")))
    return data

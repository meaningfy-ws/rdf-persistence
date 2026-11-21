"""What the relay's tests share: the constants, the commit helpers and the readers of the world.

The ``world`` fixture is in ``tests/unit/events/conftest.py``; these helpers take it as an argument.
"""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

from rdf_persistence.events.services.events import context_link
from rdf_persistence.schema.services.schema import load_schema
from tests.tenancy_world import CREATOR
from tests.toy import TOY_SCHEMA, dune, toy_mapper

DEPLOYMENT = "deployment-a"
CONTEXT = context_link("https://lib.example")
LOGGER = "rdf_persistence.events.services.relay"
VIEW = load_schema(TOY_SCHEMA)
NOW = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)
LONG_AGO = '"2001-01-01T00:00:00Z"^^<http://www.w3.org/2001/XMLSchema#dateTime>'


class RecordingOffer:
    def __init__(self) -> None:
        self.offered: list[tuple[str, str]] = []

    def offer(self, tenant: str, activity) -> None:
        self.offered.append((tenant, activity.id))


def book(world: SimpleNamespace, tenant: str) -> str:
    return str(world.iris.mint_aggregate(tenant, "Book", "books"))


def triples(iri: str) -> list:
    return list(toy_mapper().to_triples(dune(iri)))


def commit(world: SimpleNamespace, tenant: str):
    return world.tenancy.tenant_session(tenant, CREATOR)


async def add_replace_remove(world: SimpleNamespace, tenant: str) -> str:
    iri = book(world, tenant)
    async with commit(world, tenant) as session:
        version = await session.add_graph(iri, triples(iri))
        version = await session.replace_graph(iri, triples(iri), version)
        await session.remove(iri, version)
    return iri


async def add_one(world: SimpleNamespace, tenant: str) -> str:
    iri = book(world, tenant)
    async with commit(world, tenant) as session:
        await session.add_graph(iri, triples(iri))
    return iri


async def pending(world: SimpleNamespace, tenant: str, application: bool = False) -> list[str]:
    opened = (
        world.tenancy.application_session(world.tenancy.toolkit)
        if application
        else world.tenancy.tenant_session(tenant, world.tenancy.toolkit)
    )
    async with opened as session:
        return [iri for iri, _ in await session.pending_activities()]


def sent(world: SimpleNamespace, tenant: str | None = None) -> list[tuple[str, str, str]]:
    """(tenant, class IRI, activity id) of every message, in publication order."""
    return [
        (e.tenant, e.activity_class, json.loads(body)["id"])
        for e, body in world.broker.messages
        if tenant in (None, e.tenant)
    ]


def classes(world: SimpleNamespace, tenant: str) -> list[str]:
    return [c for _, c, _ in sent(world, tenant)]


async def insert_in_provenance(world: SimpleNamespace, tenant: str, body: str) -> None:
    graph = world.iris.provenance(tenant)
    await world.store.update(
        world.tenancy.database_of(tenant), f"INSERT DATA {{ GRAPH <{graph}> {{ {body} }} }}"
    )

"""What the message-bus tests share: the recorder and fakes of the dispatch tests, and the bus wired end to end.

Not collected as tests; the bus, its wiring and its attacks import from here.
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace

from rdflib import RDF, Graph, URIRef

from rdf_persistence import bootstrap, generated_models
from rdf_persistence.access.domain.generated.rp_access import Action, RoleDefinition, RoleLevel
from rdf_persistence.access.services.access import AccessRules, load_role_definitions
from rdf_persistence.collaboration.services.collaboration import Collaboration
from rdf_persistence.collaboration.services.workflows import Workflows, load_workflow, state_iri
from rdf_persistence.collaboration.services.write_guards import WriteGuards
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.iris.services.iris import DEFAULT_IRIS
from rdf_persistence.messaging.services.messagebus import MessageBus, Work
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity, Replace
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.fixtures.library.domain.generated.books import Book
from tests.toy import (
    ADA,
    MODULES,
    REVIEW_WORKFLOW,
    ROLES,
    TENANT,
    TOY_SCHEMA,
    book_iri,
    caller,
    dune,
    held,
    role,
    toy_mapper,
)
from tests.unit.activity_helpers import stored_graph

B1, B2, B3 = book_iri(1), book_iri(2), book_iri(3)
VIEW = load_schema(TOY_SCHEMA)
REVIEW = load_workflow(REVIEW_WORKFLOW)
DRAFT, IN_REVIEW = (state_iri(REVIEW, s) for s in ("draft", "in_review"))
PROVENANCE = URIRef(DEFAULT_IRIS.provenance(TENANT))


class ShelvedReplace(Replace):
    """A consumer's subclass of a standard activity."""


def fakes() -> tuple[SimpleNamespace, SimpleNamespace]:
    """A session and a collaboration that holds it."""
    session = SimpleNamespace(name="session")
    return session, SimpleNamespace(name="collaboration", session=session)


class Recorder:
    """Records what the handlers and observers were called with, in order."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Activity, Work]] = []

    def names(self) -> list[str]:
        return [name for name, _, _ in self.calls]

    def handler(self, name: str, result: object = None):
        async def handle(cmd: Activity, work: Work) -> object:
            self.calls.append((name, cmd, work))
            return result

        handle.__qualname__ = name
        return handle

    def observer(self, name: str):
        async def observe(activity: Activity, work: Work) -> None:
            self.calls.append((name, activity, work))

        observe.__qualname__ = name
        return observe


@dataclass
class World:
    """One caller's session on a fake store, with a collaboration and a bus wired to publish."""

    store: FakeStore
    session: object
    collaboration: Collaboration
    bus: MessageBus


@asynccontextmanager
async def world(
    *,
    commands=None,
    observers: dict[type[Activity], Sequence] | None = None,
    mapper=True,
    **dependencies,
) -> AsyncIterator[World]:
    rules = AccessRules(
        [
            *load_role_definitions(ROLES),
            RoleDefinition(role="reviewer", level=RoleLevel.TENANT, actions=[Action.ANNOTATE]),
        ]
    )
    bus = bootstrap(
        commands=commands,
        observers=observers,
        mapper=toy_mapper() if mapper else None,
        **dependencies,
    )
    store = FakeStore()
    listings = Listings(VIEW)
    guards = WriteGuards(
        toy_mapper(), generated_models(*MODULES), listings, Workflows([REVIEW], VIEW, rules)
    )
    async with fake_session(
        store,
        tenant_iri=TENANT,
        principal=Principal(id=ADA),
        listings=listings,
        guards=guards,
        on_commit=bus.publish,
    ) as session:
        collaboration = Collaboration(
            session,
            view=VIEW,
            rules=rules,
            iris=DEFAULT_IRIS,
            mapper=toy_mapper(),
            models=generated_models(*MODULES),
            listings=listings,
            workflows=Workflows([REVIEW], VIEW, rules),
            caller=caller(principal=ADA),
            access=held(role("librarian"), role("reviewer")),
        )
        for iri in (B1, B2):
            await session.add_graph(iri, toy_mapper().to_triples(dune(iri, chapters=1)))
        yield World(store, session, collaboration, bus)


async def version_of(world: World, iri: str = B1) -> str:
    return (await world.session.get_graph(iri))[2]


async def provenance(world: World) -> Graph:
    return await stored_graph(world.store, PROVENANCE, FAKE_DATABASE)


def types_of(graph: Graph, iri: str) -> set[URIRef]:
    return {t for t in graph.objects(URIRef(iri), RDF.type) if isinstance(t, URIRef)}


def shelving(*, twice: bool = False, new_book: str | None = None):
    """A ``ShelveBooks`` handler that relabels two books through ``work.unit_of_work()``."""

    async def shelve(cmd: Activity, work: Work) -> None:
        unit = work.unit_of_work()
        for iri in (B1, B2):
            book = await unit.get(Book, iri)
            unit.add(book.model_copy(update={"label": "Shelved"}))
        await unit.commit()
        if twice:
            again = work.unit_of_work()
            book = await again.get(Book, B1)
            again.add(book.model_copy(update={"label": "Again"}))
            await again.commit()

    return shelve

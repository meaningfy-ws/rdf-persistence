"""A commit places its activity under the IRI policy on a real Fuseki (activity-iri-policy PD-5, RISK-1).

The policy ``P`` is the activity template ``{tenant}/activity/{id}``. A served command keeps its
``urn:uuid:`` id in the command; the commit records, asks about and relays the placed IRI
``<tenant>/activity/<uuid>``.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from rdflib import XSD, Graph, Literal, URIRef

from rdf_persistence.core.domain.exceptions import Conflict
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.core.domain.sparql import fill, term
from rdf_persistence.iris.services.generated.rp_iris_services import IriPolicy
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.persistence.services.session import Session, open_session
from rdf_persistence.provenance.services.provenance import Served
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.testkit import assert_isomorphic
from tests.toy import ADA, TENANT, ShelveBooks, book_iri, dune, toy_mapper
from tests.toy_service import ToyService

POLICY = IriPolicy(activity_template="{tenant}/activity/{id}")
FIRST = "5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c101"
SECOND = "5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c102"
NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
WEEK = timedelta(days=7)
EVERYTHING = "CONSTRUCT { ?s ?p ?o } WHERE { GRAPH ?g { ?s ?p ?o } }"
RELAY = (
    "DELETE WHERE { GRAPH $provenance { $activity $pending ?o } };"
    " INSERT DATA { GRAPH $provenance { $activity $relayed $at } }"
)


@pytest.fixture
async def database(store) -> AsyncIterator[str]:
    """A fresh dataset for the test, dropped after it."""
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


@pytest.fixture
def iris() -> Iris:
    """The kit's ``Iris`` of the toy service under ``P``."""
    return ToyService(iri_policy=POLICY).kit.iris


@pytest.fixture
async def session(store, database, iris) -> AsyncIterator[Session]:
    async with open_session(
        store, database=database, tenant_iri=TENANT, principal=Principal(id=ADA), iris=iris
    ) as opened:
        yield opened


def placed(command_uuid: str) -> str:
    return f"{TENANT}/activity/{command_uuid}"


def serving(command_uuid: str) -> Served:
    """The command a handler would serve: its own id is the provisional ``urn:uuid:`` one."""
    return toy_mapper().served(ShelveBooks(id=f"urn:uuid:{command_uuid}", shelf_note="top shelf"))


async def add_book(session: Session, n: int, command_uuid: str) -> None:
    root = book_iri(n)
    async with session.transaction(served=serving(command_uuid)) as transaction:
        await transaction.add_graph(root, list(toy_mapper().to_triples(dune(root))))


async def database_graph(store, database: str) -> Graph:
    """Every triple of every graph of the database."""
    return (await store.query(database, EVERYTHING)).graph


async def relay(store, database: str, iri: str, at: str, iris: Iris) -> None:
    """Replace the pending mark of the activity ``iri`` by ``relayedAt`` at ``at`` (a UTC instant)."""
    await store.update(
        database,
        fill(
            RELAY,
            provenance=term(iris.provenance(TENANT)),
            activity=term(URIRef(iri)),
            pending=term(v.PENDING_SINCE),
            relayed=term(v.RELAYED_AT),
            at=term(Literal(at, datatype=XSD.dateTime)),
        ),
    )


async def test_a_served_commit_records_its_activity_at_the_placed_iri(session):  # IT-A1
    await add_book(session, 1, FIRST)
    assert await session.is_recorded(placed(FIRST)), "the placed IRI is recorded"
    assert not await session.is_recorded(f"urn:uuid:{FIRST}"), "the provisional IRI is not"


async def test_a_second_commit_of_a_command_with_the_same_uuid_is_refused_and_writes_nothing(
    store, database, session
):  # IT-A2
    await add_book(session, 1, FIRST)
    before = await database_graph(store, database)
    with pytest.raises(Conflict, match=placed(FIRST)):
        await add_book(session, 2, FIRST)
    assert_isomorphic(await database_graph(store, database), before)


async def test_relayed_since_the_placed_iri_returns_the_later_activity(
    store, database, session, iris
):  # IT-A3
    await add_book(session, 1, FIRST)
    await add_book(session, 2, SECOND)
    await relay(store, database, placed(FIRST), "2026-11-15T10:00:00Z", iris)
    await relay(store, database, placed(SECOND), "2026-11-15T10:00:01Z", iris)
    found = await session.relayed_since(placed(FIRST), WEEK, NOW)
    assert found is not None, "the first activity is known and relayed"
    assert [iri for iri, _ in found] == [placed(SECOND)], "the later activity, not the first"

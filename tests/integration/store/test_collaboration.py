"""Collaboration against a real Fuseki: the reverse references of a resource (IT-01, IT-02)."""

import uuid
from collections.abc import AsyncIterator, Callable

import pytest

from rdf_persistence import Action, CallerAccess, VerifiedCaller
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.service.rp_service import ReferrerList
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.session import Session, open_session
from tests.fixtures.library.generated.books import Book
from tests.toy import (
    ADA,
    BOB,
    ROLES,
    TENANT,
    TOY_SCHEMA,
    ban,
    book_iri,
    caller,
    dune,
    graph_of,
    held,
    role,
    shelf_iri,
    toy_mapper,
)

B1, B2, B3 = (book_iri(n) for n in (1, 2, 3))
S1, S2 = shelf_iri(1), shelf_iri(2)


@pytest.fixture
async def database(store) -> AsyncIterator[str]:
    """A fresh dataset for the test, dropped after it."""
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


@pytest.fixture
async def session(store, database) -> AsyncIterator[Session]:
    async with open_session(
        store, database=database, tenant_iri=TENANT, principal=Principal(id=ADA)
    ) as opened:
        yield opened


@pytest.fixture
def collaboration(session: Session) -> Callable[[VerifiedCaller, CallerAccess], Collaboration]:
    """Builds a ``Collaboration`` over the Fuseki session for a caller and its access."""
    view = load_schema(TOY_SCHEMA)
    rules = AccessRules(load_role_definitions(ROLES))

    def build(who: VerifiedCaller, access: CallerAccess) -> Collaboration:
        return Collaboration(
            session, view=view, rules=rules, iris=DEFAULT_IRIS, caller=who, access=access
        )

    return build


async def put_book(session: Session, iri: str, **slots: str) -> Book:
    book = dune(iri, chapters=1).model_copy(update=slots)
    await session.add_graph(iri, toy_mapper().to_triples(book))
    return book


def refs(found: ReferrerList) -> list[tuple[str, str, str]]:
    return [(r.referrer, r.referrer_class, r.referrer_slot) for r in found.referrers or []]


async def test_a_resource_lists_the_aggregates_that_point_at_it(session, collaboration):
    await put_book(session, B1, shelf=S1)
    await put_book(session, B2, shelf=S1)
    await put_book(session, B3, shelf=S2)
    found = await collaboration(caller(principal=ADA), held(role("librarian"))).referrers(S1)
    assert refs(found) == [(B1, "Book", "shelf"), (B2, "Book", "shelf")], "b3 is on s2"
    assert found.hidden_count == 0, "ada may read both"


async def test_a_referrer_the_caller_may_not_read_is_counted_and_not_named(session, collaboration):
    await put_book(session, B1, shelf=S1)
    await put_book(session, B2, shelf=S1)
    access = held(role("reader", who=BOB), bans=[ban(Action.READ, graph_of(B2), BOB)])
    found = await collaboration(caller(principal=BOB), access).referrers(S1)
    assert refs(found) == [(B1, "Book", "shelf")], "bob may read only b1"
    assert found.hidden_count == 1, "b2 is counted"
    assert B2 not in found.model_dump_json(), "and never named"


async def test_a_slot_narrows_the_referrers(session, collaboration):
    await put_book(session, B1)
    await put_book(session, B3, sequel_of=B1)
    b2 = dune(B2, chapters=1)
    b2.chapters[0].notes[0].about = B1
    await session.add_graph(B2, toy_mapper().to_triples(b2))
    found = await collaboration(caller(principal=ADA), held(role("librarian"))).referrers(
        B1, slot="sequel_of"
    )
    assert refs(found) == [(B3, "Book", "sequel_of")], "the note's about is left out"

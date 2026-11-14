"""Unique keys across aggregates against a real Fuseki (cross-aggregate-unique-keys 1.4: IT-01, IT-02, IT-04).

A, B are stored books of the toy tenant; "another session" is a second session on the same dataset.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
from rdflib import RDF, Literal, URIRef
from rdflib.namespace import XSD

from rdf_persistence.adapters.fuseki import FusekiStore
from rdf_persistence.domain.exceptions import Conflict, KeyConflict, NotFound
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import aggregate_keys
from rdf_persistence.services.session import Session
from tests.integration.store.test_session import ADA, BEN, TENANT, Ticker
from tests.integration.store.test_session import book as book_iri
from tests.toy import TOY_SCHEMA

A, B = book_iri(1), book_iri(2)
BIBO = "http://purl.org/ontology/bibo/"
BOOK, ISBN = URIRef(BIBO + "Book"), URIRef(BIBO + "isbn")
KEYS = aggregate_keys(load_schema(TOY_SCHEMA))
ROUNDS = 20
WITH_ISBN = "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?root $isbn $value } }"
HAS_ISBN = "ASK { GRAPH ?g { $root $isbn $value } }"


def book(iri: str, isbn: str | Literal) -> list:
    root = URIRef(iri)
    return [
        (root, RDF.type, BOOK),
        (root, ISBN, isbn if isinstance(isbn, Literal) else Literal(isbn)),
    ]


def session_of(store: FusekiStore, database: str, principal: Principal = ADA) -> Session:
    return Session(
        store,
        database=database,
        tenant_iri=TENANT,
        principal=principal,
        clock=Ticker(),
        keys=KEYS,
    )


async def graphs_holding(store: FusekiStore, database: str, isbn: str) -> int:
    answer = await store.query(
        database, fill(WITH_ISBN, isbn=term(ISBN), value=term(Literal(isbn)))
    )
    return len(list(answer))


async def holds_isbn(store: FusekiStore, database: str, root: str, isbn: str) -> bool:
    text = fill(HAS_ISBN, root=term(URIRef(root)), isbn=term(ISBN), value=term(Literal(isbn)))
    return bool((await store.query(database, text)).askAnswer)


async def stored(session: Session, root: str) -> bool:
    try:
        await session.get_graph(root)
    except NotFound:
        return False
    return True


@pytest.fixture
async def store(fuseki) -> AsyncIterator[FusekiStore]:
    async with FusekiStore(fuseki.url, fuseki.user, fuseki.password) as client:
        yield client


@pytest.fixture
async def database(store: FusekiStore) -> AsyncIterator[str]:
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


@pytest.fixture
async def session(store, database) -> Session:
    return session_of(store, database)


async def test_it01_of_two_concurrent_adds_of_one_isbn_exactly_one_is_stored(store, database):
    for n in range(ROUNDS):
        isbn = f"isbn-{n}"
        first, second = book_iri(100 + 2 * n), book_iri(101 + 2 * n)
        mine, theirs = session_of(store, database), session_of(store, database, BEN)

        outcomes = await asyncio.gather(
            mine.add_graph(first, book(first, isbn)),
            theirs.add_graph(second, book(second, isbn)),
            return_exceptions=True,
        )

        refused = [
            (root, o)
            for root, o in zip((first, second), outcomes, strict=True)
            if isinstance(o, BaseException)
        ]
        assert len(refused) == 1, f"round {n}: exactly one add is refused, got {outcomes}"
        loser, error = refused[0]
        assert type(error) is KeyConflict, f"round {n}: a key clash, not {error!r}"
        assert error.iris == (loser,), f"round {n}: the refused add names its own root"
        assert await graphs_holding(store, database, isbn) == 1, f"round {n}: one book per ISBN"


async def test_it02_a_replace_taking_another_key_is_refused_and_changes_nothing(
    store, database, session
):  # TC-12
    await session.add_graph(A, book(A, "1"))
    version_b = await session.add_graph(B, book(B, "2"))
    version_a = (await session.get_graph(A))[2]
    with pytest.raises(KeyConflict) as refused:
        await session.replace_graph(B, book(B, "1"), version_b)
    assert refused.value.iris == (B,), "B's claim clashed"
    assert (await session.get_graph(A))[2] == version_a, "A keeps its version"
    assert (await session.get_graph(B))[2] == version_b, "B keeps its version"
    assert await holds_isbn(store, database, B, "2"), "B keeps its triples"
    assert not await holds_isbn(store, database, B, "1"), "B took nothing"


async def test_it02_one_transaction_removes_the_holder_and_adds_the_key(session):  # TC-14
    version = await session.add_graph(A, book(A, "1"))
    async with session.transaction() as t:
        await t.remove(A, version)
        await t.add_graph(B, book(B, "1"))
    assert await stored(session, B), "B was stored"
    assert not await stored(session, A), "A was removed"


@pytest.mark.parametrize(
    ("stored_value", "claimed_value"),
    [
        (Literal("1", datatype=XSD.string), Literal("1")),
        (Literal("2"), Literal("2", datatype=XSD.string)),
    ],
    ids=["typed-stored-plain-claimed", "plain-stored-typed-claimed"],
)
async def test_an_xsd_string_and_a_plain_literal_are_one_value(
    session, stored_value, claimed_value
):
    """PD-5's premise: Fuseki holds the two as one term, so each blocks the other (TC-26)."""
    holder, claimant = book_iri(7), book_iri(8)
    await session.add_graph(holder, book(holder, stored_value))
    with pytest.raises(KeyConflict) as refused:
        await session.add_graph(claimant, book(claimant, claimed_value))
    assert refused.value.iris == (claimant,), "the second root's claim clashed"


async def test_it04_a_stale_replace_that_also_clashes_is_a_plain_conflict(store, database, session):
    other = session_of(store, database, BEN)  # TC-18
    version_a = await session.add_graph(A, book(A, "1"))
    await session.add_graph(B, book(B, "2"))
    await other.replace_graph(A, book(A, "1"), version_a)
    with pytest.raises(Conflict) as refused:
        await session.replace_graph(A, book(A, "2"), version_a)
    assert type(refused.value) is Conflict, "the version comes first, not a KeyConflict"
    assert refused.value.iris == (A,), "A is the root that changed"

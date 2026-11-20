"""Unique keys across aggregates against a real Fuseki.

cross-aggregate-unique-keys 1.4: IT-01, IT-02, IT-04, IT-05. unique-key-nulls-equal 1.6: IT-NE-1
(concurrent adds of one title with no subtitle), IT-NE-2 (the report names the shared absence).

A, B are stored books of the toy tenant; "another session" is a second session on the same dataset.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
from rdflib import RDF, BNode, Literal, URIRef
from rdflib.namespace import XSD

from rdf_persistence.core.domain.exceptions import Conflict, KeyConflict, NotFound
from rdf_persistence.core.domain.generated.rp_core import AggregateKey, KeyDuplicate
from rdf_persistence.core.domain.sparql import fill, term
from rdf_persistence.persistence.adapters.fuseki import FusekiStore
from rdf_persistence.persistence.services.session import Session
from tests.integration.store.sessions import (
    BEN,
    BOOK,
    ISBN,
    TITLE,
    session_of,
)
from tests.integration.store.sessions import book as book_iri
from tests.integration.store.sessions import keyed_book as book

A, B = book_iri(1), book_iri(2)
ROUNDS = 20
WITH_ISBN = "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?root $isbn $value } }"
HAS_ISBN = "ASK { GRAPH ?g { $root $isbn $value } }"


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
async def store(fuseki, toolkit) -> AsyncIterator[FusekiStore]:
    async with FusekiStore(fuseki.url, fuseki.user, fuseki.password, http=toolkit.http) as client:
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


async def test_it05_the_report_names_the_roots_that_share_a_key_value(store, database, session):
    alone = book_iri(3)  # TC-40
    unkeyed = session_of(store, database, keys=())
    for iri, isbn in ((A, "1"), (B, "1"), (alone, "2")):
        await unkeyed.add_graph(iri, book(iri, isbn))
    every_quad = "SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } }"
    before = len(list(await store.query(database, every_quad)))
    assert await session.key_duplicates() == [
        KeyDuplicate(key_name="isbn_key", root_class=str(BOOK), key_values=["1"], key_roots=[A, B])
    ], "one group: ISBN 1, roots A and B sorted; C is alone"
    after = len(list(await store.query(database, every_quad)))
    assert after == before, "the report changed nothing in the store"


# --- a key that counts an absence as a value (unique-key-nulls-equal 1.6: IT-NE-1, IT-NE-2) -------

ALTERNATIVE = URIRef("http://purl.org/dc/terms/alternative")
TITLE_SUBTITLE = AggregateKey(
    key_name="title_subtitle",
    root_class=str(BOOK),
    key_predicates=[str(TITLE), str(ALTERNATIVE)],
    key_counts_absent=True,
)
MARKER_TEXT = "https://meaningfy.ws/ns/rdf-persistence#absentKeyValue"
WITH_TITLE = "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?root a $book ; $title $value } }"


async def books_titled(store: FusekiStore, database: str, title: str) -> int:
    text = fill(WITH_TITLE, book=term(BOOK), title=term(TITLE), value=term(Literal(title)))
    return len(list(await store.query(database, text)))


def dune(iri: str, title: str = "Dune", *, with_part: bool = False) -> list:
    """A book with a title and no ``dcterms:alternative``; optionally with a part that has a title."""
    root = URIRef(iri)
    triples = [(root, RDF.type, BOOK), (root, TITLE, Literal(title))]
    if with_part:
        triples.append((BNode(), TITLE, Literal("Chapter")))
    return triples


async def test_it_ne_1_of_two_concurrent_adds_of_dune_without_subtitle_exactly_one_is_stored(
    store, database
):
    """Scenario: concurrent creates with the slot absent (RISK-1)."""
    keys = (TITLE_SUBTITLE,)
    for n in range(ROUNDS):
        title = f"Dune {n}"  # a fresh title each round: the key is one title with no subtitle
        first, second = book_iri(300 + 2 * n), book_iri(301 + 2 * n)
        mine = session_of(store, database, keys=keys)
        theirs = session_of(store, database, BEN, keys=keys)

        outcomes = await asyncio.gather(
            mine.add_graph(first, dune(first, title)),
            theirs.add_graph(second, dune(second, title)),
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
        assert error.keys == ("title_subtitle",), f"round {n}: the key that clashed"
        assert await books_titled(store, database, title) == 1, f"round {n}: one {title} / none"


async def test_it_ne_2_the_report_names_the_absence_two_dunes_share(store, database):
    """Scenario: duplicates that share an absence (PD-3, PD-5, D-5), on Fuseki."""
    first, second = book_iri(310), book_iri(311)
    unkeyed = session_of(store, database, keys=())
    await unkeyed.add_graph(first, dune(first, with_part=True))
    await unkeyed.add_graph(second, dune(second))
    keyed = session_of(store, database, keys=(TITLE_SUBTITLE,))

    report = await keyed.key_duplicates()

    assert report == [
        KeyDuplicate(
            key_name="title_subtitle",
            root_class=str(BOOK),
            key_values=["Dune", MARKER_TEXT],
            key_roots=[first, second],
        )
    ], "one group: Dune with the marker for the absent subtitle, both roots"

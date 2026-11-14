"""Unique keys across aggregates, enforced by the session (cross-aggregate-unique-keys 1.2).

The toy ``Book`` declares ``isbn_key`` over ``bibo:isbn``. A, B, C, D, E are books of the toy tenant
``T``; ``U`` is another tenant on the same fake store. "Another session" is a second session on the
same fake store.
"""

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from uuid import UUID

import pytest
from rdflib import RDF, BNode, Literal, URIRef
from rdflib.namespace import XSD
from rdflib.plugins.sparql import prepareQuery, prepareUpdate

from rdf_persistence.domain.exceptions import Conflict, InvalidBody, KeyConflict
from rdf_persistence.domain.generated.rp_core import AggregateKey, KeyDuplicate, Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import aggregate_keys
from rdf_persistence.services.session import Session, new_marker, request_text
from rdf_persistence.services.unique_keys import (
    claims_of,
    diagnosis,
    duplicates_query,
    guard,
    held,
    same_value,
)
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import TENANT, TOY_SCHEMA, book_iri, dune, graph_of, toy_mapper

A, B, C, D, E = (book_iri(n) for n in (1, 2, 3, 4, 5))
OTHER_TENANT = "https://example.org/libraries/other"
BIBO = "http://purl.org/ontology/bibo/"
BOOK, ISBN = URIRef(BIBO + "Book"), URIRef(BIBO + "isbn")
TITLE = URIRef("http://purl.org/dc/terms/title")
KEYS = aggregate_keys(load_schema(TOY_SCHEMA))
LONG_ISBN = "9780441172719"
HOSTILE = "'\"} ; DROP ALL ; #"
ENTRY = "ASK { GRAPH $registry { $graph ?p ?o } }"
HAS_ISBN = "ASK { GRAPH $graph { $root $isbn $value } }"


def book(iri: str, *isbns: str | Literal, title: str | None = None) -> list:
    """The triples of a book root holding ``isbns``; none gives a book without ISBN."""
    root = URIRef(iri)
    return [
        (root, RDF.type, BOOK),
        *((root, ISBN, i if isinstance(i, Literal) else Literal(i)) for i in isbns),
        *(((root, TITLE, Literal(title)),) if title else ()),
    ]


def opened(
    store: FakeStore, who: str = "ada", *, tenant: str = TENANT, keys=KEYS
) -> AbstractAsyncContextManager[Session]:
    return fake_session(
        store,
        tenant_iri=tenant,
        principal=Principal(id=f"https://example.org/people/{who}"),
        clock=lambda: datetime(2026, 11, 14, tzinfo=UTC),
        keys=keys,
    )


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


@pytest.fixture
async def session(store) -> AsyncIterator[Session]:
    async with opened(store) as s:
        yield s


@pytest.fixture
async def other(store) -> AsyncIterator[Session]:
    async with opened(store, "ben") as s:
        yield s


async def stored(session: Session, iri: str) -> bool:
    try:
        await session.get_graph(iri)
    except Exception:
        return False
    return True


async def has_entry(store: FakeStore, iri: str) -> bool:
    text = fill(
        ENTRY, registry=term(DEFAULT_IRIS.registry(TENANT)), graph=term(URIRef(graph_of(iri)))
    )
    return bool((await store.query(FAKE_DATABASE, text)).askAnswer)


async def holds_isbn(store: FakeStore, iri: str, value: str) -> bool:
    text = fill(
        HAS_ISBN,
        graph=term(URIRef(graph_of(iri))),
        root=term(URIRef(iri)),
        isbn=term(ISBN),
        value=term(Literal(value)),
    )
    return bool((await store.query(FAKE_DATABASE, text)).askAnswer)


async def test_tc10_a_second_add_of_one_key_value_is_a_key_conflict(store, session):
    await session.add_graph(A, book(A, "1"))
    with pytest.raises(KeyConflict) as refused:
        await session.add_graph(B, book(B, "1"))
    assert refused.value.iris == (B,), "the roots of the commit whose key clashed"
    assert refused.value.keys == ("isbn_key",), "the name of the key"
    assert not await stored(session, B), "B has no graph"
    assert not await has_entry(store, B), "B has no registry entry"


async def test_tc10_the_message_names_roots_and_keys_in_words(session):
    await session.add_graph(A, book(A, LONG_ISBN))
    with pytest.raises(KeyConflict) as refused:
        await session.add_graph(B, book(B, LONG_ISBN))
    text = str(refused.value)
    assert B in text and "isbn_key" in text, "it names the root and the key"
    assert LONG_ISBN not in text, "it gives no key value"
    assert A not in text, "it gives no holder"
    assert graph_of(B) not in text and "urn:uuid" not in text, "it gives no graph or token"


async def test_a_key_conflict_is_a_conflict(session):
    await session.add_graph(A, book(A, "1"))
    with pytest.raises(Conflict):
        await session.add_graph(B, book(B, "1"))


async def test_tc11_a_replace_keeps_its_own_key_or_changes_it(session):
    version = await session.add_graph(A, book(A, "1"))
    version = await session.replace_graph(A, book(A, "1", title="again"), version)
    await session.replace_graph(A, book(A, "2"), version)
    assert (await session.get_graph(A))[0].value(URIRef(A), ISBN) == Literal("2")


async def test_tc12_a_replace_taking_another_key_is_refused_and_changes_nothing(store, session):
    await session.add_graph(A, book(A, "1"))
    version_b = await session.add_graph(B, book(B, "2"))
    version_a = (await session.get_graph(A))[2]
    with pytest.raises(KeyConflict) as refused:
        await session.replace_graph(B, book(B, "1"), version_b)
    assert refused.value.iris == (B,), "B's claim clashed"
    assert (await session.get_graph(A))[2] == version_a, "A keeps its version"
    assert (await session.get_graph(B))[2] == version_b, "B keeps its version"
    assert await holds_isbn(store, B, "2"), "B keeps its triples"
    assert not await holds_isbn(store, B, "1"), "B took nothing"


async def test_tc13_a_removed_aggregate_frees_its_key(session):
    version = await session.add_graph(A, book(A, "1"))
    await session.remove(A, version)
    await session.add_graph(B, book(B, "1"))
    assert await stored(session, B), "B holds the value A freed"


async def test_tc14_one_transaction_removes_the_holder_and_adds_the_key(session):
    version = await session.add_graph(A, book(A, "1"))
    async with session.transaction() as t:
        await t.remove(A, version)
        await t.add_graph(B, book(B, "1"))
    assert await stored(session, B), "B was stored"
    assert not await stored(session, A), "A was removed"


async def test_tc15_one_transaction_swaps_two_keys(session):
    version_a = await session.add_graph(A, book(A, "1"))
    version_b = await session.add_graph(B, book(B, "2"))
    async with session.transaction() as t:
        await t.replace_graph(A, book(A, "2"), version_a)
        await t.replace_graph(B, book(B, "1"), version_b)
    assert (await session.get_graph(A))[0].value(URIRef(A), ISBN) == Literal("2"), "A holds 2"
    assert (await session.get_graph(B))[0].value(URIRef(B), ISBN) == Literal("1"), "B holds 1"


async def test_tc16_two_changes_of_one_key_in_one_transaction_send_nothing(store, session):
    sent = len(store.sent("update"))
    with pytest.raises(KeyConflict) as refused:
        async with session.transaction() as t:
            await t.add_graph(C, book(C, "3"))
            await t.add_graph(D, book(D, "3"))
    assert refused.value.iris == (C, D), "both roots, sorted"
    assert refused.value.keys == ("isbn_key",), "the key"
    assert len(store.sent("update")) == sent, "the store received no update"
    assert not await stored(session, C), "C was not stored"


async def test_tc17_books_without_isbn_never_clash(session):
    await session.add_graph(A, book(A))
    await session.add_graph(B, book(B))
    assert await stored(session, A) and await stored(session, B), "both stored"


async def test_tc18_a_stale_replace_that_also_clashes_is_a_plain_conflict(session, other):
    version_a = await session.add_graph(A, book(A, "1"))
    await session.add_graph(B, book(B, "2"))
    await other.replace_graph(A, book(A, "1", title="theirs"), version_a)
    with pytest.raises(Conflict) as refused:
        await session.replace_graph(A, book(A, "2"), version_a)
    assert type(refused.value) is Conflict, "the version comes first, not a KeyConflict"
    assert refused.value.iris == (A,), "A is the root that changed"


async def test_tc19_a_loaded_graph_holding_the_value_is_no_holder(session):
    ttl = f'<https://example.org/x> a <{BOOK}> ; <{ISBN}> "9" .'
    loaded = await session.load_graph(A, ttl.encode(), rdf_format=RdfFormat.TURTLE)
    await session.add_graph(A, book(A, "8"), [loaded])
    await session.add_graph(B, book(B, "9"))
    assert await stored(session, B), "B was stored"


async def test_tc20_the_same_value_in_another_tenant_is_stored(store, session):
    other_book = f"{OTHER_TENANT}/books/{UUID(int=1)}"
    await session.add_graph(A, book(A, "1"))
    async with opened(store, tenant=OTHER_TENANT) as elsewhere:
        await elsewhere.add_graph(other_book, book(other_book, "1"))
        assert await stored(elsewhere, other_book), "stored in U"


async def test_tc21_another_type_is_another_scope(store):
    lib = "https://example.org/ns/lib#"
    title_key = AggregateKey(
        key_name="title_key", root_class=lib + "Book2", key_predicates=[str(TITLE)]
    )
    async with opened(store, keys=[title_key]) as keyed:
        await keyed.add_graph(
            A, [(URIRef(A), RDF.type, URIRef(lib + "Book2")), (URIRef(A), TITLE, Literal("X"))]
        )
        await keyed.add_graph(
            B, [(URIRef(B), RDF.type, URIRef(lib + "Magazine")), (URIRef(B), TITLE, Literal("X"))]
        )
        assert await stored(keyed, B), "a Magazine is its own scope"


async def test_tc22_two_values_of_one_key_slot_are_an_invalid_body(store, session):
    sent = len(store.sent("update"))
    with pytest.raises(InvalidBody):
        await session.add_graph(B, book(B, "1", "2"))
    assert len(store.sent("update")) == sent, "nothing was sent"


async def test_tc23_a_session_without_keys_enforces_none(store):
    async with opened(store, keys=()) as unkeyed:
        await unkeyed.add_graph(A, book(A, "1"))
        await unkeyed.add_graph(B, book(B, "1"))
        assert await stored(unkeyed, B), "both stored"


def test_tc24_a_hostile_value_appears_only_as_an_escaped_literal():
    claim = claims_of(KEYS, B, book(B, HOSTILE))[0]
    registry = DEFAULT_IRIS.registry(TENANT)
    excluded = [URIRef(A)]
    rendered = str(term(Literal(HOSTILE)))
    texts = {
        "guard": guard(claim, registry, excluded),
        "diagnosis": diagnosis([claim], registry, excluded),
    }
    for name, text in texts.items():
        assert text.count(HOSTILE) == 0, f"{name}: the raw value is nowhere in the text"
        assert rendered in text, f"{name}: the value is its escaped literal"
    prepareUpdate(
        request_text(registry, new_marker(datetime(2026, 11, 14, tzinfo=UTC)), [texts["guard"]], [])
    )
    prepareQuery(texts["diagnosis"])


async def test_tc24_a_hostile_value_is_compared_as_a_value(session):
    await session.add_graph(A, book(A, HOSTILE))
    with pytest.raises(KeyConflict):
        await session.add_graph(B, book(B, HOSTILE))
    assert await stored(session, A), "A is still there"


async def test_tc25_a_holder_removed_before_the_diagnosis_is_a_lost_race(store, session, other):
    version_a = await session.add_graph(A, book(A, "1"))

    async def remove_holder() -> None:
        store.after_update = None
        await other.remove(A, version_a)

    store.after_update = remove_holder
    with pytest.raises(Conflict) as refused:
        await session.add_graph(B, book(B, "1"))
    assert type(refused.value) is Conflict, "not a KeyConflict: nobody holds the value now"
    assert refused.value.iris == (), "no culprit to name"


async def test_tc26_a_string_literal_is_the_plain_literal(session):
    await session.add_graph(A, book(A, "1"))
    with pytest.raises(KeyConflict) as refused:
        await session.add_graph(B, book(B, Literal("1", datatype=XSD.string)))
    assert refused.value.iris == (B,), 'xsd:string "1" is "1"'


async def test_tc26_a_stored_string_literal_blocks_the_plain_literal(session):
    await session.add_graph(A, book(A, Literal("1", datatype=XSD.string)))
    with pytest.raises(KeyConflict) as refused:
        await session.add_graph(B, book(B, "1"))
    assert refused.value.iris == (B,), 'the stored xsd:string "1" is "1"'


async def test_tc26_the_normalisation_holds_inside_one_transaction(session):
    with pytest.raises(KeyConflict) as refused:
        async with session.transaction() as t:
            await t.add_graph(C, book(C, "3"))
            await t.add_graph(D, book(D, Literal("3", datatype=XSD.string)))
    assert refused.value.iris == (C, D), "both roots"


async def test_a_blank_node_is_no_key_value(session):
    await session.add_graph(A, book(A, BNode("x")))
    await session.add_graph(B, book(B, BNode("y")))
    assert await stored(session, B), "a blank node claims nothing, so it never clashes"


async def test_a_language_tag_makes_another_value(session):
    await session.add_graph(A, book(A, Literal("Dune", lang="en")))
    await session.add_graph(B, book(B, "Dune"))
    assert await stored(session, B), '"Dune"@en is not "Dune"'


def test_same_value_names_the_claims_another_claim_repeats():
    one, two, three = (
        claims_of(KEYS, iri, book(iri, isbn))[0] for iri, isbn in ((C, "3"), (D, "3"), (E, "4"))
    )
    assert same_value([one, two, three]) == [one, two], "E is alone"
    assert same_value([one, three]) == [], "no repeat"


async def test_held_reads_the_claims_a_diagnosis_found(store, session):
    await session.add_graph(A, book(A, "1"))
    one, two = (claims_of(KEYS, iri, book(iri, isbn))[0] for iri, isbn in ((B, "1"), (C, "2")))
    text = diagnosis([one, two], DEFAULT_IRIS.registry(TENANT), [])
    assert held([one, two], await store.query(FAKE_DATABASE, text)) == [one], (
        "only B's value is held"
    )


async def test_tc27_a_key_conflict_of_a_later_batch_keeps_its_type_and_says_how_far_it_got(session):
    unit = UnitOfWork(session, toy_mapper(), max_roots=2)
    for iri, isbn in ((C, "5"), (D, "6"), (E, "5")):
        unit.add(dune(iri, chapters=0).model_copy(update={"isbn": isbn}))
    with pytest.raises(KeyConflict) as refused:
        await unit.commit(batches=True)
    assert refused.value.iris == (E,), "the root of the second batch"
    assert refused.value.keys == ("isbn_key",), "the key"
    assert "1 of 2 batches committed" in str(refused.value), "the message says how far it got"
    assert await stored(session, C), "the first batch is stored"


async def seeded(store: FakeStore) -> None:
    """A and B hold the ISBN "1", C holds "2", written by a session that enforces no key."""
    async with opened(store, keys=()) as unkeyed:
        await unkeyed.add_graph(A, book(A, "1"))
        await unkeyed.add_graph(B, book(B, "1"))
        await unkeyed.add_graph(C, book(C, "2"))


async def test_tc40_the_report_names_the_roots_that_share_a_key_value(store, session):
    await seeded(store)
    sent = len(store.sent("update"))
    assert await session.key_duplicates() == [
        KeyDuplicate(key_name="isbn_key", root_class=str(BOOK), key_values=["1"], key_roots=[A, B])
    ], "one group: ISBN 1, roots A and B sorted; C is alone"
    assert len(store.sent("update")) == sent, "the report changed nothing in the store"


async def test_tc41_no_duplicates_is_an_empty_report(session):
    await session.add_graph(A, book(A, "1"))
    await session.add_graph(B, book(B, "2"))
    await session.add_graph(C, book(C))
    assert await session.key_duplicates() == [], "distinct ISBNs, and no ISBN claims nothing"


async def test_tc41_a_session_without_keys_reports_nothing_and_asks_nothing(store):
    await seeded(store)
    async with opened(store, keys=()) as unkeyed:
        queries = len(store.sent("query"))
        assert await unkeyed.key_duplicates() == [], "no key, no report"
        assert len(store.sent("query")) == queries, "the store was not asked"


async def test_tc42_a_replace_keeping_a_duplicate_is_refused_until_it_changes_the_value(
    store, session
):
    await seeded(store)
    version_a = (await session.get_graph(A))[2]
    with pytest.raises(KeyConflict):
        await session.replace_graph(A, book(A, "1", title="again"), version_a)
    await session.replace_graph(A, book(A, "4"), version_a)
    assert await session.key_duplicates() == [], "A left the value, so B holds it alone"


async def test_the_report_counts_aggregates_of_this_tenant_and_type_only(store, session):
    other_book = f"{OTHER_TENANT}/books/{UUID(int=1)}"
    ttl = f'<https://example.org/x> a <{BOOK}> ; <{ISBN}> "1" .'
    await session.add_graph(A, book(A, "1"))
    loaded = await session.load_graph(B, ttl.encode(), rdf_format=RdfFormat.TURTLE)
    await session.add_graph(B, book(B, "2"), [loaded])
    async with opened(store, tenant=OTHER_TENANT) as elsewhere:
        await elsewhere.add_graph(other_book, book(other_book, "1"))
    assert await session.key_duplicates() == [], "a loaded graph and another tenant are no holders"


async def test_the_report_is_ordered_by_key_then_values_with_composite_keys(store):
    both = AggregateKey(
        key_name="a_title_isbn_key", root_class=str(BOOK), key_predicates=[str(TITLE), str(ISBN)]
    )
    async with opened(store, keys=(*KEYS, both)) as keyed:
        async with opened(store, keys=()) as unkeyed:
            for iri, isbn, title in ((A, "9", "t"), (B, "9", "t"), (C, "5", "t"), (D, "5", "t")):
                await unkeyed.add_graph(iri, book(iri, isbn, title=title))
        assert [(d.key_name, d.key_values, d.key_roots) for d in await keyed.key_duplicates()] == [
            ("a_title_isbn_key", ["t", "5"], [C, D]),
            ("a_title_isbn_key", ["t", "9"], [A, B]),
            ("isbn_key", ["5"], [C, D]),
            ("isbn_key", ["9"], [A, B]),
        ], "by key name, then by the values in key order; the values are lexical forms"


def test_the_report_query_parses_and_names_the_registry_and_the_class():
    registry = DEFAULT_IRIS.registry(TENANT)
    text = duplicates_query(KEYS[0], registry)
    prepareQuery(text)
    assert "HAVING" in text and "GROUP BY" in text, (
        "a group per value, kept when two roots share it"
    )
    assert str(registry) in text and str(BOOK) in text, "it names the registry and the key's class"

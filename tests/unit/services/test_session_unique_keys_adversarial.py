"""Adversarial tests of the unique keys across aggregates (cross-aggregate-unique-keys 1.2).

They try to break what ``test_session_unique_keys.py`` (TC-10..TC-27) holds: composite keys, odd
values, parts of other aggregates, transactions that swap, remove or refuse, the state after a
refusal, and a large commit. A, B, C, D, E are books of the toy tenant; keys are built by hand as
``AggregateKey`` models.
"""

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from uuid import UUID

import pytest
from rdflib import RDF, Literal, URIRef
from rdflib.namespace import XSD

from rdf_persistence.domain.exceptions import (
    Conflict,
    InvalidBody,
    InvalidIri,
    KeyConflict,
    NotFound,
)
from rdf_persistence.domain.generated.rp_core import AggregateKey, Principal
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import aggregate_keys
from rdf_persistence.services.session import Session
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import TENANT, TOY_SCHEMA, book_iri

A, B, C, D, E = (book_iri(n) for n in (1, 2, 3, 4, 5))
OTHER_TENANT = "https://example.org/libraries/other"
BIBO = "http://purl.org/ontology/bibo/"
BOOK, MAGAZINE = URIRef(BIBO + "Book"), URIRef(BIBO + "Magazine")
ISBN = URIRef(BIBO + "isbn")
TITLE = URIRef("http://purl.org/dc/terms/title")
SUBJECT = URIRef("http://purl.org/dc/terms/subject")
ISBN_KEY = aggregate_keys(load_schema(TOY_SCHEMA))
COUNT_QUADS = "SELECT (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } }"


def key(name: str, root_class: URIRef, *predicates: URIRef) -> AggregateKey:
    return AggregateKey(
        key_name=name, root_class=str(root_class), key_predicates=[str(p) for p in predicates]
    )


def root(iri: str, *pairs: tuple[URIRef, object], types: tuple[URIRef, ...] = (BOOK,)) -> list:
    """The triples of a root of ``types`` holding the (predicate, object) ``pairs``."""
    subject = URIRef(iri)
    return [*((subject, RDF.type, t) for t in types), *((subject, p, o) for p, o in pairs)]


def isbn_book(iri: str, value: object) -> list:
    return root(iri, (ISBN, value if not isinstance(value, str) else Literal(value)))


def opened(
    store: FakeStore, keys, who: str = "ada", tenant: str = TENANT
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
    async with opened(store, ISBN_KEY) as s:
        yield s


@pytest.fixture
async def other(store) -> AsyncIterator[Session]:
    async with opened(store, ISBN_KEY, "ben") as s:
        yield s


async def stored(session: Session, iri: str) -> bool:
    try:
        await session.get_graph(iri)
    except NotFound:
        return False
    return True


async def quads(store: FakeStore) -> int:
    return int(next(iter(await store.query(FAKE_DATABASE, COUNT_QUADS)))[0])


# --- composite keys -----------------------------------------------------------------------------


async def test_a_composite_key_clashes_only_when_every_slot_is_equal(store):
    composite = key("isbn_title_key", BOOK, ISBN, TITLE)
    async with opened(store, [composite]) as s:
        await s.add_graph(A, root(A, (ISBN, Literal("1")), (TITLE, Literal("t"))))
        await s.add_graph(B, root(B, (ISBN, Literal("1")), (TITLE, Literal("u"))))
        await s.add_graph(C, root(C, (ISBN, Literal("2")), (TITLE, Literal("t"))))
        with pytest.raises(KeyConflict) as refused:
            await s.add_graph(D, root(D, (ISBN, Literal("1")), (TITLE, Literal("t"))))
        assert refused.value.iris == (D,), "only the full match clashes"
        assert refused.value.keys == ("isbn_title_key",), "the composite key"


async def test_a_composite_key_does_not_confuse_its_slots(store):
    composite = key("isbn_title_key", BOOK, ISBN, TITLE)
    async with opened(store, [composite]) as s:
        await s.add_graph(A, root(A, (ISBN, Literal("x")), (TITLE, Literal("y"))))
        await s.add_graph(B, root(B, (ISBN, Literal("y")), (TITLE, Literal("x"))))
        assert await stored(s, B), "swapped slot values are other values"


@pytest.mark.parametrize(
    "predicates", [(ISBN, TITLE), (TITLE, ISBN)], ids=["isbn-first", "title-first"]
)
async def test_a_composite_key_with_an_absent_slot_claims_nothing(store, predicates):
    composite = key("pair_key", BOOK, *predicates)
    async with opened(store, [composite]) as s:
        await s.add_graph(A, root(A, (ISBN, Literal("1"))))
        await s.add_graph(B, root(B, (ISBN, Literal("1"))))
        await s.add_graph(C, root(C, (TITLE, Literal("t"))))
        await s.add_graph(D, root(D, (TITLE, Literal("t"))))
        assert await stored(s, D), "a root missing a slot never clashes"


async def test_a_key_without_predicates_enforces_nothing(store):
    async with opened(store, [key("empty_key", BOOK)]) as s:
        await s.add_graph(A, root(A))
        await s.add_graph(B, root(B))
        assert await stored(s, B), "no slot, no claim"


# --- values -------------------------------------------------------------------------------------

SAME_TEXT = "7"
VALUES = {
    "empty": Literal(""),
    "long": Literal("x" * 100_000),
    "quotes": Literal("a\"b'c\"\"\"d'''e"),
    "backslash": Literal("a\\b\\\\c\\"),
    "newline": Literal("a\nb\r\nc\t"),
    "dollar-name": Literal("$registry $values $excluded $p_kind"),
    "dollar-index": Literal("$index $claim"),
    "variable": Literal("?key_root ?claim ?key_graph"),
    "braces": Literal("} } FILTER NOT EXISTS { GRAPH ?g { ?s ?p ?o"),
    "unicode": Literal("日本語 é ñ 😀"),
    "integer": Literal(7),
    "date": Literal("2026-01-01", datatype=XSD.date),
    "lang": Literal("Dune", lang="en"),
}


@pytest.mark.parametrize("value", VALUES.values(), ids=VALUES.keys())
async def test_every_value_clashes_with_itself_and_with_no_other(session, value):
    await session.add_graph(A, isbn_book(A, value))
    with pytest.raises(KeyConflict) as refused:
        await session.add_graph(B, isbn_book(B, value))
    assert refused.value.iris == (B,), "the same term clashes"
    for iri, near in ((C, Literal(str(value) + "!")), (D, Literal(str(value)[:-1] or "other"))):
        await session.add_graph(iri, isbn_book(iri, near))
        assert await stored(session, iri), "a near value is another value"


@pytest.mark.parametrize("value", VALUES.values(), ids=VALUES.keys())
async def test_the_message_of_a_refusal_never_holds_the_value(session, value):
    await session.add_graph(A, isbn_book(A, value))
    with pytest.raises(KeyConflict) as refused:
        await session.add_graph(B, isbn_book(B, value))
    text = str(refused.value)
    assert str(value) not in text or not str(value), "no key value in the message"
    assert A not in text, "no holder in the message"


async def test_an_iri_value_is_not_the_literal_of_the_same_text(store):
    async with opened(store, [key("subject_key", BOOK, SUBJECT)]) as s:
        target = "https://example.org/topics/sf"
        await s.add_graph(A, root(A, (SUBJECT, URIRef(target))))
        await s.add_graph(B, root(B, (SUBJECT, Literal(target))))
        assert await stored(s, B), "an IRI and a literal of its text are two terms"
        with pytest.raises(KeyConflict):
            await s.add_graph(C, root(C, (SUBJECT, URIRef(target))))


@pytest.mark.parametrize(
    "first,second",
    [
        (Literal(1), Literal("1")),
        (Literal("2026-01-01", datatype=XSD.date), Literal("2026-01-01")),
        (Literal("Dune", lang="en"), Literal("Dune", lang="fr")),
        (Literal("1", datatype=XSD.integer), Literal("1", datatype=XSD.decimal)),
    ],
    ids=["integer-vs-plain", "date-vs-plain", "lang-vs-lang", "integer-vs-decimal"],
)
async def test_terms_of_another_datatype_or_language_are_other_values(session, first, second):
    await session.add_graph(A, isbn_book(A, first))
    await session.add_graph(B, isbn_book(B, second))
    assert await stored(session, B), "the two terms differ"


# --- which subjects and types claim -------------------------------------------------------------


async def test_a_part_holding_the_key_predicate_is_no_holder_and_claims_nothing(session):
    part_a, part_c = f"{A}/chapters/1", f"{C}/chapters/1"
    await session.add_graph(A, [*isbn_book(A, "7"), *root(part_a, (ISBN, Literal("9")))])
    await session.add_graph(B, isbn_book(B, "9"))
    await session.add_graph(C, [*root(C), *root(part_c, (ISBN, Literal("9")))])
    assert await stored(session, B) and await stored(session, C), "parts claim and hold nothing"
    with pytest.raises(KeyConflict):
        await session.add_graph(D, isbn_book(D, "7"))


async def test_a_root_with_two_types_claims_every_key_of_its_types(store):
    keys = [key("book_key", BOOK, ISBN), key("magazine_key", MAGAZINE, ISBN)]
    async with opened(store, keys) as s:
        await s.add_graph(A, root(A, (ISBN, Literal("1")), types=(BOOK, MAGAZINE)))
        with pytest.raises(KeyConflict) as refused:
            await s.add_graph(B, root(B, (ISBN, Literal("1")), types=(MAGAZINE,)))
        assert refused.value.keys == ("magazine_key",), "only the key of the shared type"
        with pytest.raises(KeyConflict) as both:
            await s.add_graph(C, root(C, (ISBN, Literal("1")), types=(MAGAZINE, BOOK)))
        assert both.value.keys == ("book_key", "magazine_key"), "both keys, sorted"


async def test_a_root_with_two_keys_clashes_on_the_one_it_shares(store):
    keys = [key("title_key", BOOK, TITLE), key("isbn_key", BOOK, ISBN)]
    async with opened(store, keys) as s:
        await s.add_graph(A, root(A, (ISBN, Literal("1")), (TITLE, Literal("t"))))
        with pytest.raises(KeyConflict) as refused:
            await s.add_graph(B, root(B, (ISBN, Literal("2")), (TITLE, Literal("t"))))
        assert refused.value.keys == ("title_key",), "only the key that clashed"


async def test_a_key_of_a_class_no_root_has_enforces_nothing(store):
    ghost = key("ghost_key", URIRef(BIBO + "Ghost"), ISBN)
    async with opened(store, [*ISBN_KEY, ghost]) as s:
        await s.add_graph(A, isbn_book(A, "1"))
        assert await stored(s, A), "the book is stored"


async def test_a_key_given_twice_does_not_clash_a_root_with_itself(store):
    async with opened(store, [*ISBN_KEY, *ISBN_KEY]) as s:
        await s.add_graph(A, isbn_book(A, "1"))
        assert await stored(s, A), "one root, one value"


# --- transactions -------------------------------------------------------------------------------


async def test_a_chain_of_three_rotates_its_values(session):
    versions = {
        n: await session.add_graph(n, isbn_book(n, str(i))) for i, n in enumerate((A, B, C), 1)
    }
    async with session.transaction() as t:
        await t.replace_graph(A, isbn_book(A, "2"), versions[A])
        await t.replace_graph(B, isbn_book(B, "3"), versions[B])
        await t.replace_graph(C, isbn_book(C, "1"), versions[C])
    held = {n: (await session.get_graph(n))[0].value(URIRef(n), ISBN) for n in (A, B, C)}
    assert held == {A: Literal("2"), B: Literal("3"), C: Literal("1")}, "the values rotated"


async def test_a_chain_shifting_into_a_new_value_and_a_fresh_add_is_stored(session):
    versions = {
        n: await session.add_graph(n, isbn_book(n, str(i))) for i, n in enumerate((A, B), 1)
    }
    async with session.transaction() as t:
        await t.replace_graph(A, isbn_book(A, "2"), versions[A])
        await t.replace_graph(B, isbn_book(B, "3"), versions[B])
        await t.add_graph(C, isbn_book(C, "1"))
    assert await stored(session, C), "C took the value A left"


async def test_a_removed_holder_frees_its_value_to_a_replace(session):
    version_a = await session.add_graph(A, isbn_book(A, "1"))
    version_b = await session.add_graph(B, isbn_book(B, "2"))
    async with session.transaction() as t:
        await t.remove(A, version_a)
        await t.replace_graph(B, isbn_book(B, "1"), version_b)
    assert (await session.get_graph(B))[0].value(URIRef(B), ISBN) == Literal("1"), "B holds 1"


async def test_an_untouched_holder_still_blocks_a_replace_next_to_other_changes(session):
    await session.add_graph(A, isbn_book(A, "1"))
    version_b = await session.add_graph(B, isbn_book(B, "2"))
    version_c = await session.add_graph(C, isbn_book(C, "3"))
    with pytest.raises(KeyConflict) as refused:
        async with session.transaction() as t:
            await t.remove(C, version_c)
            await t.replace_graph(B, isbn_book(B, "1"), version_b)
    assert refused.value.iris == (B,), "A was not part of the transaction, so it still holds 1"
    assert await stored(session, C), "the remove of C is undone with the rest"


async def test_a_stale_remove_of_the_holder_is_a_plain_conflict_and_writes_nothing(
    store, session, other
):
    version_a = await session.add_graph(A, isbn_book(A, "1"))
    await other.replace_graph(A, isbn_book(A, "1"), version_a)
    before = await quads(store)
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.remove(A, version_a)
            await t.add_graph(B, isbn_book(B, "1"))
    assert type(refused.value) is Conflict, "a stale version is not a key clash"
    assert refused.value.iris == (A,), "A is the root that changed"
    assert not await stored(session, B), "B was not stored"
    assert await quads(store) == before, "the store holds what it held"


async def test_adding_over_an_existing_root_is_a_plain_conflict_not_a_clash_with_itself(session):
    await session.add_graph(A, isbn_book(A, "1"))
    with pytest.raises(Conflict) as refused:
        await session.add_graph(A, isbn_book(A, "1"))
    assert type(refused.value) is Conflict, "A cannot clash with its own stored key"


async def test_a_change_refused_before_the_request_leaves_no_claim_behind(session):
    async with session.transaction() as t:
        with pytest.raises(InvalidBody):
            await t.add_graph(B, [*isbn_book(B, "1"), (URIRef(B), ISBN, Literal("2"))])
        with pytest.raises(ValueError):
            await t.add_graph(A, isbn_book(A, "3"))
            await t.add_graph(A, isbn_book(A, "4"))
        await t.add_graph(C, isbn_book(C, "1"))
        await t.add_graph(D, isbn_book(D, "4"))
        await t.add_graph(B, isbn_book(B, "5"))
    assert all([await stored(session, n) for n in (A, B, C, D)]), "every valid change committed"


async def test_a_missing_root_and_a_foreign_iri_leave_no_claim_behind(session):
    foreign = f"{OTHER_TENANT}/books/{UUID(int=9)}"
    async with session.transaction() as t:
        with pytest.raises(NotFound):
            await t.replace_graph(A, isbn_book(A, "1"), "no-such-version")
        with pytest.raises(InvalidIri):
            await t.add_graph(foreign, isbn_book(foreign, "1"))
        await t.add_graph(B, isbn_book(B, "1"))
    assert await stored(session, B), "B took the value the refused changes did not claim"


async def test_an_exception_ending_the_block_commits_and_claims_nothing(store, session):
    before = await quads(store)
    with pytest.raises(RuntimeError):
        async with session.transaction() as t:
            await t.add_graph(A, isbn_book(A, "1"))
            raise RuntimeError("boom")
    assert await quads(store) == before, "nothing was written"
    await session.add_graph(B, isbn_book(B, "1"))
    assert await stored(session, B), "the value is free"


# --- state after a refusal ----------------------------------------------------------------------


async def test_a_refused_commit_writes_nothing_and_the_session_works_after(store, session):
    await session.add_graph(A, isbn_book(A, "1"))
    before = await quads(store)
    with pytest.raises(KeyConflict):
        async with session.transaction() as t:
            await t.add_graph(C, isbn_book(C, "3"))
            await t.add_graph(B, isbn_book(B, "1"))
    assert await quads(store) == before, "no graph, no entry, no marker"
    await session.add_graph(B, isbn_book(B, "2"))
    await session.add_graph(C, isbn_book(C, "3"))
    assert await stored(session, B) and await stored(session, C), "the same session goes on"


async def test_a_clash_inside_the_commit_writes_nothing_and_the_session_works_after(store, session):
    before = await quads(store)
    with pytest.raises(KeyConflict):
        async with session.transaction() as t:
            await t.add_graph(A, isbn_book(A, "1"))
            await t.add_graph(B, isbn_book(B, "1"))
    assert await quads(store) == before, "nothing was written"
    await session.add_graph(A, isbn_book(A, "1"))
    assert await stored(session, A), "A was never stored, so it can be"


# --- races --------------------------------------------------------------------------------------


async def test_a_writer_racing_for_the_value_after_a_commit_is_refused(store, session, other):
    async def take() -> None:
        store.after_update = None
        with pytest.raises(KeyConflict):
            await other.add_graph(C, isbn_book(C, "1"))

    store.after_update = take
    await session.add_graph(A, isbn_book(A, "1"))
    assert await stored(session, A), "the first commit stands"
    assert not await stored(session, C), "the racer wrote nothing"


async def test_a_holder_arriving_after_the_refusal_is_still_one_key_conflict(store, session, other):
    version_a = await session.add_graph(A, isbn_book(A, "1"))

    async def swap_holders() -> None:
        store.after_update = None
        await other.remove(A, version_a)
        await other.add_graph(D, isbn_book(D, "1"))

    store.after_update = swap_holders
    with pytest.raises(KeyConflict) as refused:
        await session.add_graph(B, isbn_book(B, "1"))
    assert refused.value.iris == (B,), "a diagnosis of the state at the read (PD-15 d)"
    assert str(D) not in str(refused.value), "the new holder is not named"


# --- the exception ------------------------------------------------------------------------------


async def test_a_key_conflict_carries_sorted_tuples_of_str(session):
    with pytest.raises(KeyConflict) as refused:
        async with session.transaction() as t:
            await t.add_graph(E, isbn_book(E, "1"))
            await t.add_graph(C, isbn_book(C, "1"))
            await t.add_graph(D, isbn_book(D, "1"))
    error = refused.value
    assert isinstance(error, Conflict), "it is a Conflict"
    assert error.iris == (C, D, E), "roots sorted, whatever the order of the changes"
    assert isinstance(error.iris, tuple) and all(type(i) is str for i in error.iris), "str tuple"
    assert isinstance(error.keys, tuple) and all(type(k) is str for k in error.keys), "str tuple"
    assert "urn:uuid" not in str(error), "no version token"


# --- limits -------------------------------------------------------------------------------------


@pytest.mark.slow
async def test_three_hundred_claims_commit_in_one_request(store, session):
    sent = len(store.sent("update"))
    async with session.transaction() as t:
        for n in range(1, 301):
            await t.add_graph(book_iri(n), isbn_book(book_iri(n), f"isbn-{n}"))
    assert len(store.sent("update")) == sent + 1, "one update for all 300"
    assert await stored(session, book_iri(300)), "the last one is stored"


async def test_three_hundred_claims_with_one_repeat_send_nothing(store, session):
    sent = len(store.sent("update"))
    with pytest.raises(KeyConflict) as refused:
        async with session.transaction() as t:
            for n in range(1, 301):
                await t.add_graph(book_iri(n), isbn_book(book_iri(n), f"isbn-{n % 299}"))
    assert len(store.sent("update")) == sent, "the repeat is found before sending"
    assert len(refused.value.iris) == 2, "the two roots that repeat, no more"

"""A removal of a root of a refusing class is refused while another aggregate refers to it
(delete-refuses-referenced PD-3, PD-4, PD-5, PD-7, PD-9; TC-3, TC-4, TC-5).

The session knows no schema: ``StubRefusal`` stands for the schema side. ``A`` are authors (the
toy's refusing class), ``B`` books that refer to them with ``lib:writtenBy``, ``S`` is a root of a
class that is not refusing. The fake store applies a request atomically, as Fuseki does.
"""

import re
from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from uuid import UUID

import pytest
from rdflib import RDF, URIRef

from rdf_persistence import InUse
from rdf_persistence.core.domain.exceptions import Conflict, NotFound
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.persistence.services.mapper import UnitOfWork
from rdf_persistence.persistence.services.session import (
    ReferrerRow,
    Session,
    open_session,
)
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.fixtures.library.domain.generated.books import Author, Book
from tests.toy import TENANT, book_iri, dune, toy_mapper_limited

LIB = "https://example.org/ns/library#"
AUTHOR_CLASS, SHELF_CLASS = URIRef(LIB + "Author"), URIRef(LIB + "Shelf")
BOOK_CLASS = URIRef("http://purl.org/ontology/bibo/Book")
WRITTEN_BY, SEQUEL_OF = URIRef(LIB + "writtenBy"), URIRef(LIB + "sequelOf")
A1, A2 = (f"{TENANT}/authors/{UUID(int=n)}" for n in (1, 2))
B1, B2, B3 = (book_iri(n) for n in (1, 2, 3))
NOW = datetime(2026, 11, 20, tzinfo=UTC)


class StubRefusal:
    """The schema side of a removal refusal: what the session asks, kept for the tests to read."""

    def __init__(self, refusing: frozenset[URIRef] = frozenset({AUTHOR_CLASS})) -> None:
        self.refusing = refusing
        self.asked: list[tuple[tuple[str, ...], list[ReferrerRow], object]] = []

    async def in_use(self, roots: Sequence[str], rows: Sequence[ReferrerRow], readable) -> InUse:
        self.asked.append((tuple(roots), list(rows), readable))
        named = tuple((row[0], "Book", "written_by") for row in rows)
        return InUse("in use", iris=tuple(roots), referrers=named)


def opened(
    store: FakeStore, removals: StubRefusal | None, who: str = "ada"
) -> AbstractAsyncContextManager[Session]:
    return open_session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=TENANT,
        principal=Principal(id=f"https://example.org/people/{who}"),
        clock=lambda: NOW,
        removals=removals,
    )


def author(iri: str, *more: URIRef) -> list:
    return [(URIRef(iri), RDF.type, c) for c in (AUTHOR_CLASS, *more)]


def book(iri: str, **links: str) -> list:
    names = {"by": WRITTEN_BY, "sequel": SEQUEL_OF}
    return [(URIRef(iri), RDF.type, BOOK_CLASS)] + [
        (URIRef(iri), names[name], URIRef(target)) for name, target in links.items()
    ]


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


@pytest.fixture
def refusal() -> StubRefusal:
    return StubRefusal()


@pytest.fixture
async def session(store, refusal) -> AsyncIterator[Session]:
    async with opened(store, refusal) as s:
        yield s


@pytest.fixture
async def other(store, refusal) -> AsyncIterator[Session]:
    async with opened(store, refusal, "ben") as s:
        yield s


async def stored(session: Session, iri: str) -> bool:
    try:
        await session.get_graph(iri)
    except NotFound:
        return False
    return True


# --- TC-3: the guard ----------------------------------------------------------------------------


async def test_e1_a_referenced_author_is_refused_and_stays(session, refusal):
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(B1, book(B1, by=A1))
    with pytest.raises(InUse) as refused:
        await session.remove(A1, version)
    assert refused.value.iris == (A1,)
    assert refused.value.referrers == ((B1, "Book", "written_by"),)
    assert await stored(session, A1), "nothing was deleted"
    assert refusal.asked[0][0] == (A1,)
    assert [row[0] for row in refusal.asked[0][1]] == [B1], "the rows are the referrer's"


async def test_e3_an_author_nobody_refers_to_is_removed(session):
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(B1, book(B1, by=A2))  # refers to another author
    await session.remove(A1, version)
    assert not await stored(session, A1)


async def test_e4_a_referenced_book_is_removed_as_before(session):
    version = await session.add_graph(B2, book(B2))
    await session.add_graph(B1, book(B1, sequel=B2))
    await session.remove(B2, version)
    assert not await stored(session, B2), "Book is not a refusing class"


async def test_a_root_typed_with_two_classes_one_refusing_is_refused(session):
    version = await session.add_graph(A1, author(A1, SHELF_CLASS))
    await session.add_graph(B1, book(B1, by=A1))
    with pytest.raises(InUse):
        await session.remove(A1, version)
    assert await stored(session, A1)


async def test_matrix_14_a_part_referring_to_its_own_root_is_no_referrer(session, refusal):
    part = URIRef(f"{A1}/parts/1")
    version = await session.add_graph(A1, [*author(A1), (part, WRITTEN_BY, URIRef(A1))])
    await session.remove(A1, version)
    assert not await stored(session, A1)
    assert refusal.asked == [], "no diagnosis: the request applied"


async def test_a_referrer_removed_by_the_same_transaction_does_not_count(session):
    version_a = await session.add_graph(A1, author(A1))
    version_b = await session.add_graph(B1, book(B1, by=A1))
    async with session.transaction() as t:
        await t.remove(A1, version_a)
        await t.remove(B1, version_b)
    assert not await stored(session, A1)
    assert not await stored(session, B1)


async def test_two_refused_roots_are_named_together_and_the_first_one_gives_the_rows(
    session, refusal
):
    version_1 = await session.add_graph(A1, author(A1))
    version_2 = await session.add_graph(A2, author(A2))
    await session.add_graph(B1, book(B1, by=A2))
    await session.add_graph(B2, book(B2, by=A1))
    with pytest.raises(InUse) as refused:
        async with session.transaction() as t:
            await t.remove(A2, version_2)
            await t.remove(A1, version_1)
    assert refused.value.iris == (A1, A2)
    assert refused.value.referrers == ((B2, "Book", "written_by"),), "the rows of A1, sorted first"


async def test_the_readable_callable_reaches_the_schema_side(session, refusal):
    async def readable(iri: str, rows: Sequence[ReferrerRow]) -> set[str]:
        return {row[0] for row in rows}

    version = await session.add_graph(A1, author(A1))
    await session.add_graph(B1, book(B1, by=A1))
    with pytest.raises(InUse):
        await session.remove(A1, version, readable=readable)
    assert refusal.asked[0][2] is readable
    with pytest.raises(InUse):
        async with session.transaction(readable=readable) as t:
            await t.remove(A1, version)
    assert refusal.asked[1][2] is readable
    with pytest.raises(InUse):
        await session.remove(A1, version)
    assert refusal.asked[2][2] is None, "none is the session's full reach"


# --- TC-4: the same commit, the diagnosis, the batches ------------------------------------------


async def test_e10_an_add_naming_a_removed_author_is_refused_before_anything_is_sent(
    session, store
):
    version = await session.add_graph(A1, author(A1))
    sent = len(store.sent("update"))
    with pytest.raises(InUse) as refused:
        async with session.transaction() as t:
            await t.add_graph(B3, book(B3, by=A1))
            await t.remove(A1, version)
    assert refused.value.iris == (A1,)
    assert refused.value.referrers == ((B3, "Book", "written_by"),)
    assert len(store.sent("update")) == sent, "nothing was sent"
    assert await stored(session, A1)
    assert not await stored(session, B3)


async def test_an_add_naming_another_author_is_no_refusal(session):
    version = await session.add_graph(A1, author(A1))
    async with session.transaction() as t:
        await t.add_graph(B3, book(B3, by=A2))
        await t.remove(A1, version)
    assert not await stored(session, A1)
    assert await stored(session, B3)


async def test_an_add_naming_a_removed_root_of_a_class_that_is_not_refusing_is_stored(session):
    version = await session.add_graph(B2, book(B2))
    async with session.transaction() as t:
        await t.add_graph(B3, book(B3, sequel=B2))
        await t.remove(B2, version)
    assert await stored(session, B3)


async def test_matrix_2_a_stale_version_wins_over_a_referrer(session):
    await session.add_graph(A1, author(A1))
    await session.add_graph(B1, book(B1, by=A1))
    with pytest.raises(Conflict) as refused:
        await session.remove(A1, "stale")
    assert not isinstance(refused.value, InUse)
    assert "changed by someone else" in str(refused.value)


async def test_matrix_3_a_referrer_gone_between_the_refusal_and_the_diagnosis_is_a_lost_race(
    store, session, other
):
    version_a = await session.add_graph(A1, author(A1))
    version_b = await session.add_graph(B1, book(B1, by=A1))

    async def referrer_goes() -> None:
        store.after_update = None
        await other.remove(B1, version_b)

    store.after_update = referrer_goes
    with pytest.raises(Conflict, match="lost a race") as refused:
        await session.remove(A1, version_a)
    assert not isinstance(refused.value, InUse)
    await session.remove(A1, version_a)  # the retry succeeds
    assert not await stored(session, A1)


async def test_matrix_6_replacing_the_referrer_without_the_link_does_not_free_the_author(session):
    version_a = await session.add_graph(A1, author(A1))
    version_b = await session.add_graph(B1, book(B1, by=A1))
    with pytest.raises(InUse):
        async with session.transaction() as t:
            await t.replace_graph(B1, book(B1), version_b)
            await t.remove(A1, version_a)
    assert await stored(session, A1)
    await session.replace_graph(B1, book(B1), version_b)  # in two commits it works
    await session.remove(A1, version_a)
    assert not await stored(session, A1)


async def test_matrix_13_a_batch_that_removes_the_author_before_its_referrer_is_refused(
    store, refusal
):
    async with opened(store, refusal) as session:
        seed = UnitOfWork(session, toy_mapper_limited(1))
        seed.add(Author(id=A1, label="Frank"))
        seed.add(dune(B1, written_by=A1))
        seed.add(dune(B2))
        await seed.commit(batches=True)
        work = UnitOfWork(session, toy_mapper_limited(1))
        for cls, iri in ((Book, B2), (Author, A1), (Book, B1)):
            work.remove(await work.get(cls, iri))
        with pytest.raises(InUse, match="1 of 3 batches committed"):
            await work.commit(batches=True)
        assert not await stored(session, B2), "the batch before it stays committed"
        assert await stored(session, A1)
        assert await stored(session, B1)


# --- TC-5: G-3, no refusal configured, no guard -------------------------------------------------


async def remove_author(store: FakeStore, removals: StubRefusal | None) -> str:
    """The request that removes an author nobody refers to, from a session with ``removals``."""
    async with opened(store, removals) as session:
        version = await session.add_graph(A1, author(A1))
        await session.remove(A1, version)
    return store.sent("update")[-1]


def same_but_ids(text: str) -> str:
    """The request text with its minted ids (markers, versions, activity) made equal."""
    return re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "ID", text)


async def fresh_request(removals: StubRefusal | None) -> str:
    fresh = FakeStore()
    await fresh.create_dataset(FAKE_DATABASE)
    return await remove_author(fresh, removals)


@pytest.mark.parametrize("removals", [None, StubRefusal(frozenset())], ids=["none", "empty"])
async def test_tc5_a_session_that_refuses_nothing_sends_the_request_as_before(removals):
    request = same_but_ids(await fresh_request(removals))
    assert "?referrer" not in request, "no guard"
    assert request == same_but_ids(await fresh_request(None)), "the same text for both"


async def test_tc5_a_session_with_a_refusing_class_adds_one_guard_per_removed_root(refusal):
    plain = same_but_ids(await fresh_request(None))
    request = same_but_ids(await fresh_request(refusal))
    assert "?referrer0" in request
    assert request.count("FILTER NOT EXISTS") == plain.count("FILTER NOT EXISTS") + 1


async def test_tc5_a_session_without_removals_deletes_a_referenced_author(store):
    async with opened(store, None) as session:
        version = await session.add_graph(A1, author(A1))
        await session.add_graph(B1, book(B1, by=A1))
        await session.remove(A1, version)
        assert not await stored(session, A1)

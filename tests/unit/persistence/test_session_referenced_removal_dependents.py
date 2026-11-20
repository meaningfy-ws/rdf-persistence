"""A dependent record never blocks the removal of what it refers to (delete-refuses-referenced PD-3,
PD-5; E9, D-9).

The session's ``dependents`` are ``(record class, predicate)`` pairs: a link of such a pair is no
referrer, in the store guard and in the check of the same commit alike. ``StubRefusal`` stands for
the schema side; ``A`` are authors (refusing), ``B`` books, ``C`` comments (the dependent class).
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from uuid import UUID

import pytest
from rdflib import RDF, URIRef

from rdf_persistence import InUse
from rdf_persistence.core.domain.exceptions import Conflict, NotFound
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.persistence.services.session import (
    Dependents,
    ReferrerRow,
    Session,
    open_session,
)
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import TENANT, book_iri

LIB = "https://example.org/ns/library#"
AUTHOR_CLASS = URIRef(LIB + "Author")
BOOK_CLASS = URIRef("http://purl.org/ontology/bibo/Book")
WRITTEN_BY = URIRef(LIB + "writtenBy")
COMMENT_PAIR: Dependents = ((v.ANNOTATION, v.HAS_TARGET),)
A1 = f"{TENANT}/authors/{UUID(int=1)}"
B1 = book_iri(1)
C1 = f"{TENANT}/comments/{UUID(int=1)}"
NOW = datetime(2026, 11, 20, tzinfo=UTC)


class StubRefusal:
    """The schema side of a removal refusal: the refusing class, and an ``InUse`` naming the rows."""

    refusing = frozenset({AUTHOR_CLASS})

    async def in_use(self, roots: Sequence[str], rows: Sequence[ReferrerRow], readable) -> InUse:
        named = tuple((row[0], "Book", "written_by") for row in rows)
        return InUse("in use", iris=tuple(roots), referrers=named)


def opened(
    store: FakeStore, dependents: Dependents = COMMENT_PAIR
) -> AbstractAsyncContextManager[Session]:
    return open_session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=TENANT,
        principal=Principal(id="https://example.org/people/ada"),
        clock=lambda: NOW,
        removals=StubRefusal(),
        dependents=dependents,
    )


def author(iri: str) -> list:
    return [(URIRef(iri), RDF.type, AUTHOR_CLASS)]


def root(iri: str, cls: URIRef, *links: tuple[URIRef, str]) -> list:
    return [(URIRef(iri), RDF.type, cls), *((URIRef(iri), p, URIRef(o)) for p, o in links)]


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


@pytest.fixture
async def session(store) -> AsyncIterator[Session]:
    async with opened(store) as s:
        yield s


async def stored(session: Session, iri: str) -> bool:
    try:
        await session.get_graph(iri)
    except NotFound:
        return False
    return True


async def test_e9_a_comment_whose_only_link_is_its_target_does_not_block(session):
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(C1, root(C1, v.ANNOTATION, (v.HAS_TARGET, A1)))
    await session.remove(A1, version)
    assert not await stored(session, A1), "the author is removed"


async def test_a_comment_with_another_link_to_the_author_blocks(session):
    """probe of E9: only the pair is dropped; another link of the comment is a referrer."""
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(C1, root(C1, v.ANNOTATION, (v.HAS_TARGET, B1), (WRITTEN_BY, A1)))
    with pytest.raises(InUse) as refused:
        await session.remove(A1, version)
    assert refused.value.referrers[0][0] == C1, "the comment is named"


async def test_the_dependent_pair_is_only_for_the_comment_class(session):
    """probe of E9: a book with a ``has_target`` link to the author is no dependent; it blocks."""
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(B1, root(B1, BOOK_CLASS, (v.HAS_TARGET, A1)))
    with pytest.raises(InUse):
        await session.remove(A1, version)
    assert await stored(session, A1), "nothing was deleted"


async def test_a_comment_added_for_the_removed_author_in_the_same_commit_is_no_refusal(
    session, store
):
    """found D-T-1 (D-9): PD-5 skips the dependents pairs as the guard does.

    The commit is sent, not refused unsent. What follows is the commit's own cascade, which drops the
    comment it adds with its target (a ``Conflict``; see the report of the fix); never ``InUse``.
    """
    version = await session.add_graph(A1, author(A1))
    sent = len(store.sent("update"))
    try:
        async with session.transaction() as t:
            await t.add_graph(C1, root(C1, v.ANNOTATION, (v.HAS_TARGET, A1)))
            await t.remove(A1, version)
    except Conflict as refused:
        assert not isinstance(refused, InUse), "a dependent comment is no referrer"
    assert len(store.sent("update")) > sent, "the commit was sent"
    assert not await stored(session, A1), "the author is removed"

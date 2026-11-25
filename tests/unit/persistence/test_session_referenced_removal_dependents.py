"""A dependent record never blocks the removal of what it refers to (delete-refuses-referenced PD-3,
PD-5; E9, D-9).

The session's ``dependents`` are ``(record class, predicate)`` pairs: a link of such a pair is no
referrer, in the store guard and in the check of the same commit alike. ``StubRefusal`` stands for
the schema side; ``A`` are authors (refusing), ``B`` books, ``C`` comments (the dependent class).
"""

from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from rdflib import RDF, URIRef

from rdf_persistence import InUse
from rdf_persistence.core.domain.exceptions import Conflict
from rdf_persistence.persistence.services.referrers import Dependents
from rdf_persistence.persistence.services.session import Session
from rdf_persistence.schema.services import vocabulary as v
from tests.toy import BOOK_CLASS, TENANT, WRITTEN_BY, author_iri, book_iri
from tests.unit.persistence.referrer_helpers import StubRefusal, author, opened, stored

LIB = "https://example.org/ns/library#"
NOTE_CLASS = URIRef(LIB + "Note")
COMMENT_PAIR: Dependents = ((v.ANNOTATION, v.HAS_TARGET),)
A1 = author_iri(1)
B1 = book_iri(1)
C1 = f"{TENANT}/comments/{UUID(int=1)}"


def root(iri: str, cls: URIRef, *links: tuple[URIRef, str]) -> list:
    return [(URIRef(iri), RDF.type, cls), *((URIRef(iri), p, URIRef(o)) for p, o in links)]


@pytest.fixture
async def session(store) -> AsyncIterator[Session]:
    async with opened(store, StubRefusal(), dependents=COMMENT_PAIR) as s:
        yield s


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


@pytest.mark.parametrize("remove_first", [False, True], ids=["add-then-remove", "remove-then-add"])
@pytest.mark.parametrize("dependents_only", [False, True], ids=["refusing", "no-refusal"])
async def test_a_comment_added_for_the_author_the_same_commit_removes_is_refused_unsent(
    store, remove_first, dependents_only
):
    """#226 (D-T-1): the commit's cascade would drop the comment it adds, so the commit is refused
    before it is sent, naming both roots; a dependent comment is no referrer, so never ``InUse``.
    It holds with or without a removal refusal."""
    removals = None if dependents_only else StubRefusal()
    async with opened(store, removals, dependents=COMMENT_PAIR) as session:
        version = await session.add_graph(A1, author(A1))
        sent = len(store.sent("update"))
        with pytest.raises(Conflict) as refused:
            async with session.transaction() as t:
                if remove_first:
                    await t.remove(A1, version)
                await t.add_graph(C1, root(C1, v.ANNOTATION, (v.HAS_TARGET, A1)))
                if not remove_first:
                    await t.remove(A1, version)
        assert not isinstance(refused.value, InUse), "a dependent comment is no referrer"
        assert refused.value.iris == (A1, C1), "both roots are named"
        assert "the same commit removes" in str(refused.value), "the reason is the commit's own"
        assert len(store.sent("update")) == sent, "nothing was sent"
        assert await stored(session, A1), "the author is kept"
        assert not await stored(session, C1), "the comment is not stored"


async def test_a_comment_replaced_to_target_the_author_the_same_commit_removes_is_refused(
    session, store
):
    """#226: a replace that makes a stored comment depend on the removed root is refused alike."""
    version = await session.add_graph(A1, author(A1))
    c_version = await session.add_graph(C1, root(C1, v.ANNOTATION, (v.HAS_TARGET, B1)))
    sent = len(store.sent("update"))
    with pytest.raises(Conflict, match="the same commit removes"):
        async with session.transaction() as t:
            await t.replace_graph(C1, root(C1, v.ANNOTATION, (v.HAS_TARGET, A1)), c_version)
            await t.remove(A1, version)
    assert len(store.sent("update")) == sent, "nothing was sent"
    assert await stored(session, A1), "the author is kept"


async def test_a_comment_on_another_root_is_added_beside_the_removal(session):
    """probe of #226: only a dependent of the removed root is refused."""
    a2 = author_iri(2)
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(a2, author(a2))
    async with session.transaction() as t:
        await t.add_graph(C1, root(C1, v.ANNOTATION, (v.HAS_TARGET, a2)))
        await t.remove(A1, version)
    assert await stored(session, C1), "the comment on the other author is stored"
    assert not await stored(session, A1), "the author is removed"


def comment_and_book(iri: str, target: str) -> list:
    """A root typed both as the dependent class and as a note, linking by the dependent predicate.

    The note class sorts after the comment class, so the one class a commit names for a root is the
    dependent one: the shape the single-class check wrongly dropped.
    """
    return [*root(iri, v.ANNOTATION, (v.HAS_TARGET, target)), (URIRef(iri), RDF.type, NOTE_CLASS)]


async def test_a_root_typed_also_as_a_note_blocks_a_stored_removal(session):
    """follow-on of D-9: the guard keeps the solution of the type that is no dependent."""
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(C1, comment_and_book(C1, A1))
    with pytest.raises(InUse) as refused:
        await session.remove(A1, version)
    assert refused.value.referrers[0][0] == C1, "the root is named"
    assert await stored(session, A1), "nothing was deleted"


async def test_a_root_typed_also_as_a_note_added_in_the_same_commit_blocks_unsent(session, store):
    """the check of the commit agrees with the guard: one type of the root is no dependent."""
    version = await session.add_graph(A1, author(A1))
    sent = len(store.sent("update"))
    with pytest.raises(InUse):
        async with session.transaction() as t:
            await t.add_graph(C1, comment_and_book(C1, A1))
            await t.remove(A1, version)
    assert len(store.sent("update")) == sent, "nothing was sent"
    assert await stored(session, A1), "the author is kept"

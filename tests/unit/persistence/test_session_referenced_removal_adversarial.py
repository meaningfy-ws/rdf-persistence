"""Adversarial probes of the removal guard of a refusing root (delete-refuses-referenced task 2.2).

Each docstring names the PD, error-matrix row or example it probes. The session knows no schema:
``Refusal`` stands for the schema side, as in ``test_session_referenced_removal.py``. True
concurrency is not expressible on the fake store (one request at a time); integration IT-1..IT-3
cover it. ``A`` are authors (refusing), ``B`` books, ``S`` shelves (not refusing).
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from uuid import UUID

import pytest
from rdflib import RDF, Dataset, Graph, Literal, URIRef

from rdf_persistence import InUse
from rdf_persistence.core.domain.exceptions import BadQuery, Conflict, InvalidIri, NotFound
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.persistence.services.mapper import UnitOfWork
from rdf_persistence.persistence.services.session import (
    Dependents,
    ReferrerRow,
    Session,
    open_session,
)
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.fixtures.library.domain.generated.books import Author, Book
from tests.toy import TENANT, book_iri, dune, shelf_iri, toy_mapper_limited

LIB = "https://example.org/ns/library#"
AUTHOR_CLASS, SHELF_CLASS = URIRef(LIB + "Author"), URIRef(LIB + "Shelf")
SUB_AUTHOR, MIXIN, AUDIT = (URIRef(LIB + n) for n in ("SubAuthor", "Describable", "Audit"))
BOOK_CLASS = URIRef("http://purl.org/ontology/bibo/Book")
WRITTEN_BY, SEQUEL_OF = URIRef(LIB + "writtenBy"), URIRef(LIB + "sequelOf")
COMMENT_PAIR: Dependents = ((v.ANNOTATION, v.HAS_TARGET),)
NOW = datetime(2026, 11, 20, tzinfo=UTC)


def author_iri(n: int) -> str:
    return f"{TENANT}/authors/{UUID(int=n)}"


A1, A2, A3 = (author_iri(n) for n in (1, 2, 3))
B1, B2, B3 = (book_iri(n) for n in (1, 2, 3))
S1 = shelf_iri(1)
C1 = f"{TENANT}/comments/{UUID(int=1)}"
AUD1 = f"{TENANT}/audits/{UUID(int=1)}"


class Refusal:
    """The schema side: what the session asks, kept; ``call_readable`` makes it ask the callable."""

    def __init__(
        self,
        refusing: frozenset[URIRef] = frozenset({AUTHOR_CLASS}),
        call_readable: bool = False,
    ) -> None:
        self.refusing = refusing
        self.call_readable = call_readable
        self.asked: list[tuple[tuple[str, ...], list[ReferrerRow]]] = []

    async def in_use(self, roots: Sequence[str], rows: Sequence[ReferrerRow], readable) -> InUse:
        self.asked.append((tuple(roots), list(rows)))
        if self.call_readable and readable is not None:
            await readable(roots[0], rows)
        named = tuple((row[0], "Book", "written_by") for row in rows)
        return InUse("in use", iris=tuple(roots), referrers=named)


def opened(
    store: FakeStore, removals: Refusal | None, dependents: Dependents = ()
) -> AbstractAsyncContextManager[Session]:
    return open_session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=TENANT,
        principal=Principal(id="https://example.org/people/ada"),
        clock=lambda: NOW,
        removals=removals,
        dependents=dependents,
    )


def root(iri: str, cls: URIRef, *links: tuple[URIRef, str]) -> list:
    return [(URIRef(iri), RDF.type, cls), *((URIRef(iri), p, URIRef(o)) for p, o in links)]


def author(iri: str, *more: URIRef) -> list:
    return [(URIRef(iri), RDF.type, c) for c in (AUTHOR_CLASS, *more)]


def book(iri: str, **links: str) -> list:
    names = {"by": WRITTEN_BY, "sequel": SEQUEL_OF}
    return root(iri, BOOK_CLASS, *((names[k], t) for k, t in links.items()))


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


@pytest.fixture
def refusal() -> Refusal:
    return Refusal()


@pytest.fixture
async def session(store, refusal) -> AsyncIterator[Session]:
    async with opened(store, refusal, COMMENT_PAIR) as s:
        yield s


@pytest.fixture
async def other(store, refusal) -> AsyncIterator[Session]:
    async with opened(store, refusal, COMMENT_PAIR) as s:
        yield s


async def stored(session: Session, iri: str) -> bool:
    try:
        await session.get_graph(iri)
    except NotFound:
        return False
    return True


def graph_of_triples(triples: list) -> Graph:
    graph = Graph()
    for triple in triples:
        graph.add(triple)
    return graph


async def quads(store: FakeStore) -> set:
    data = Dataset()
    data.parse(data=await store.export_quads(FAKE_DATABASE), format="nquads")
    return {(s, p, o, g) for s, p, o, g in data.quads()}


# --- matrix 2, 3, 6 -------------------------------------------------------------------------------


async def test_matrix_2_one_stale_root_among_two_is_a_conflict_though_the_other_is_referenced(
    session,
):
    """probe of matrix row 2 (PD-4): a stale version of one root wins over a referrer of another."""
    version_1 = await session.add_graph(A1, author(A1))
    await session.add_graph(A2, author(A2))
    await session.add_graph(B1, book(B1, by=A1))
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.remove(A1, version_1)
            await t.remove(A2, "stale")
    assert not isinstance(refused.value, InUse)
    assert await stored(session, A1)
    assert await stored(session, A2)


async def test_matrix_3_a_new_referrer_at_diagnosis_is_named_not_the_old_one(store, session, other):
    """probe of matrix row 3 (PD-4): the diagnosis reads the referrers of now, not of the refusal."""
    version_a = await session.add_graph(A1, author(A1))
    version_b = await session.add_graph(B1, book(B1, by=A1))

    async def swap() -> None:
        store.after_update = None
        await other.remove(B1, version_b)
        await other.add_graph(B2, book(B2, by=A1))

    store.after_update = swap
    with pytest.raises(InUse) as refused:
        await session.remove(A1, version_a)
    assert refused.value.referrers == ((B2, "Book", "written_by"),)
    assert await stored(session, A1)


async def test_matrix_6_replacing_the_referrer_to_add_the_link_is_refused_before_sending(
    session, store
):
    """probe of matrix row 6 / PD-5: a replace that adds a link to the removed root is refused unsent."""
    version_a = await session.add_graph(A1, author(A1))
    version_b = await session.add_graph(B1, book(B1))
    sent = len(store.sent("update"))
    with pytest.raises(InUse) as refused:
        async with session.transaction() as t:
            await t.replace_graph(B1, book(B1, by=A1), version_b)
            await t.remove(A1, version_a)
    assert refused.value.referrers == ((B1, "Book", "written_by"),)
    assert len(store.sent("update")) == sent
    assert await stored(session, A1)


async def test_matrix_6_replacing_the_referrer_to_point_at_another_author_still_refuses(session):
    """probe of matrix row 6: the stored link guards, whatever the replace writes instead."""
    version_a = await session.add_graph(A1, author(A1))
    await session.add_graph(A2, author(A2))
    version_b = await session.add_graph(B1, book(B1, by=A1))
    with pytest.raises(InUse):
        async with session.transaction() as t:
            await t.replace_graph(B1, book(B1, by=A2), version_b)
            await t.remove(A1, version_a)
    assert await stored(session, A1)


async def test_a_refused_removal_changes_nothing_in_the_store(session, store):
    """probe of G-2 / PD-3: a refused removal leaves every quad as it was (no marker, no activity)."""
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(B1, book(B1, by=A1))
    before = await quads(store)
    with pytest.raises(InUse):
        await session.remove(A1, version)
    assert await quads(store) == before


async def test_removing_a_root_that_does_not_exist_is_not_found_not_in_use(session):
    """probe of matrix row 2 order: a missing aggregate is NotFound before any guard."""
    with pytest.raises(NotFound):
        await session.remove(A1, "any")


# --- what is a referrer (PD-3, matrix 14, E9) -----------------------------------------------------


async def test_a_toolkit_written_root_of_another_class_is_a_referrer(session):
    """probe of OPEN-3 / PD-3: a referrer of any class (as an rp_writes: service root) blocks."""
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(AUD1, root(AUD1, AUDIT, (WRITTEN_BY, A1)))
    with pytest.raises(InUse) as refused:
        await session.remove(A1, version)
    assert refused.value.referrers[0][0] == AUD1
    assert await stored(session, A1)


async def test_e9_a_comment_whose_only_link_is_its_target_does_not_block(session):
    """probe of E9 / PD-3: the dependent pair (comment, has_target) is dropped from the guard."""
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(C1, root(C1, v.ANNOTATION, (v.HAS_TARGET, A1)))
    await session.remove(A1, version)
    assert not await stored(session, A1)


async def test_a_comment_with_another_link_to_the_author_blocks(session):
    """probe of matrix 9 / PD-3: only the pair is dropped; a comment's other link is a referrer."""
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(C1, root(C1, v.ANNOTATION, (v.HAS_TARGET, B1), (WRITTEN_BY, A1)))
    with pytest.raises(InUse) as refused:
        await session.remove(A1, version)
    assert refused.value.referrers[0][0] == C1


async def test_the_dependent_pair_is_only_for_the_comment_class(session):
    """probe of PD-3: a book with a has_target link to the author is no dependent; it blocks."""
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(B1, root(B1, BOOK_CLASS, (v.HAS_TARGET, A1)))
    with pytest.raises(InUse):
        await session.remove(A1, version)


async def test_a_session_without_dependents_counts_the_comment_target(store, refusal):
    """probe of PD-3: the pairs are the session's; with none a comment's target blocks."""
    async with opened(store, refusal, ()) as session:
        version = await session.add_graph(A1, author(A1))
        await session.add_graph(C1, root(C1, v.ANNOTATION, (v.HAS_TARGET, A1)))
        with pytest.raises(InUse):
            await session.remove(A1, version)


async def test_two_refusing_roots_that_refer_to_each_other_are_removed_together(session):
    """probe of PD-3 (NOT IN removed): mutual referrers, both removed, do not block."""
    version_1 = await session.add_graph(A1, root(A1, AUTHOR_CLASS, (SEQUEL_OF, A2)))
    version_2 = await session.add_graph(A2, root(A2, AUTHOR_CLASS, (SEQUEL_OF, A1)))
    async with session.transaction() as t:
        await t.remove(A1, version_1)
        await t.remove(A2, version_2)
    assert not await stored(session, A1)
    assert not await stored(session, A2)


async def test_one_of_two_mutually_referring_roots_alone_is_refused(session):
    """probe of PD-3: removing only A1 leaves A2's link, a referrer."""
    version_1 = await session.add_graph(A1, root(A1, AUTHOR_CLASS, (SEQUEL_OF, A2)))
    await session.add_graph(A2, root(A2, AUTHOR_CLASS, (SEQUEL_OF, A1)))
    with pytest.raises(InUse) as refused:
        await session.remove(A1, version_1)
    assert refused.value.referrers[0][0] == A2


async def test_a_root_linking_to_itself_is_no_referrer(session):
    """probe of matrix 14 / PD-3: a root-level self link sits in the removed graph."""
    version = await session.add_graph(A1, root(A1, AUTHOR_CLASS, (SEQUEL_OF, A1)))
    await session.remove(A1, version)
    assert not await stored(session, A1)


async def test_a_part_of_another_aggregate_referring_to_the_author_blocks(session):
    """probe of matrix 14 reversed: only the part of the removed root is exempt, a foreign part counts."""
    version = await session.add_graph(A1, author(A1))
    part = URIRef(f"{B1}/parts/1")
    await session.add_graph(B1, [*book(B1), (part, WRITTEN_BY, URIRef(A1))])
    with pytest.raises(InUse) as refused:
        await session.remove(A1, version)
    assert refused.value.referrers[0][0] == B1


async def test_a_graph_outside_the_registry_is_no_referrer(session, store):
    """probe of PD-3: a graph that is not a registered aggregate does not block."""
    version = await session.add_graph(A1, author(A1))
    stray = URIRef(f"{TENANT}/graphs/stray")
    await store.put_graph(FAKE_DATABASE, stray, graph_of_triples(book(B1, by=A1)))
    await session.remove(A1, version)
    assert not await stored(session, A1)


async def test_a_literal_or_a_longer_iri_is_no_reference_to_the_author(session):
    """probe of PD-3: a literal equal to the IRI, and an IRI that merely starts with it, are no links."""
    version = await session.add_graph(A1, author(A1))
    triples = [*book(B1, by=A1 + "0"), (URIRef(B1), URIRef(LIB + "note"), Literal(A1))]
    await session.add_graph(B1, triples)
    await session.remove(A1, version)
    assert not await stored(session, A1)


async def test_an_rdf_type_statement_naming_the_author_is_no_reference(session):
    """probe of PD-3: ``?p != rdf:type``; a node typed with the IRI of the root is no referrer."""
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(B1, [(URIRef(B1), RDF.type, URIRef(A1)), *book(B1)])
    await session.remove(A1, version)
    assert not await stored(session, A1)


# --- which roots are guarded (PD-2, PD-7, G-3) ----------------------------------------------------


async def test_a_root_typed_only_with_a_refusing_subclass_is_refused(store):
    """probe of PD-2: the schema lists every refusing class; a root typed only with a subclass blocks."""
    refusal = Refusal(frozenset({AUTHOR_CLASS, SUB_AUTHOR}))
    async with opened(store, refusal) as session:
        version = await session.add_graph(A1, root(A1, SUB_AUTHOR))
        await session.add_graph(B1, book(B1, by=A1))
        with pytest.raises(InUse):
            await session.remove(A1, version)


async def test_a_root_typed_only_with_a_mixin_that_is_not_refusing_is_removed(session):
    """probe of PD-2: a mixin's annotation is not inherited; the root is removed though referenced."""
    version = await session.add_graph(A1, root(A1, MIXIN))
    await session.add_graph(B1, book(B1, by=A1))
    await session.remove(A1, version)
    assert not await stored(session, A1)


async def test_a_referenced_root_of_a_class_that_is_not_refusing_asks_nothing(session, refusal):
    """probe of G-3: removing a referenced shelf, with other roots refusing, never consults removals."""
    version = await session.add_graph(S1, root(S1, SHELF_CLASS))
    await session.add_graph(B1, book(B1, sequel=S1))
    await session.remove(S1, version)
    assert not await stored(session, S1)
    assert refusal.asked == []


async def test_a_shelf_removed_with_a_referenced_author_in_one_commit_names_only_the_author(
    session,
):
    """probe of PD-4: the unguarded root is not named by the refusal."""
    version_a = await session.add_graph(A1, author(A1))
    version_s = await session.add_graph(S1, root(S1, SHELF_CLASS))
    await session.add_graph(B1, book(B1, by=A1, sequel=S1))
    with pytest.raises(InUse) as refused:
        async with session.transaction() as t:
            await t.remove(S1, version_s)
            await t.remove(A1, version_a)
    assert refused.value.iris == (A1,)
    assert await stored(session, S1), "all or nothing"


async def test_many_removed_roots_each_get_their_own_guard(session):
    """probe of PD-3 (variable suffixes): twelve guards in one request, only the tenth root referenced."""
    iris = [author_iri(n) for n in range(1, 13)]
    versions = {iri: await session.add_graph(iri, author(iri)) for iri in iris}
    await session.add_graph(B1, book(B1, by=iris[9]))
    with pytest.raises(InUse) as refused:
        async with session.transaction() as t:
            for iri in iris:
                await t.remove(iri, versions[iri])
    assert refused.value.iris == (iris[9],)
    assert all([await stored(session, iri) for iri in iris])


async def test_many_removed_roots_none_referenced_are_all_removed(session):
    """probe of PD-3: twelve guards that all hold let the request apply."""
    iris = [author_iri(n) for n in range(1, 13)]
    versions = {iri: await session.add_graph(iri, author(iri)) for iri in iris}
    async with session.transaction() as t:
        for iri in iris:
            await t.remove(iri, versions[iri])
    assert not any([await stored(session, iri) for iri in iris])


async def test_referrers_removed_in_the_same_commit_free_two_authors_each(session):
    """probe of PD-3 / PD-4: one referrer of both authors, removed with them, blocks neither."""
    version_1 = await session.add_graph(A1, author(A1))
    version_2 = await session.add_graph(A2, author(A2))
    version_b = await session.add_graph(
        B1, root(B1, BOOK_CLASS, (WRITTEN_BY, A1), (WRITTEN_BY, A2))
    )
    async with session.transaction() as t:
        await t.remove(A1, version_1)
        await t.remove(A2, version_2)
        await t.remove(B1, version_b)
    assert not any([await stored(session, i) for i in (A1, A2, B1)])


async def test_a_referrer_removed_with_a_different_author_does_not_free_this_one(session):
    """probe of PD-3: the removed set is per transaction, not per root; B2 still refers to A2."""
    version_1 = await session.add_graph(A1, author(A1))
    version_2 = await session.add_graph(A2, author(A2))
    version_b = await session.add_graph(B1, book(B1, by=A1))
    await session.add_graph(B2, book(B2, by=A2))
    with pytest.raises(InUse) as refused:
        async with session.transaction() as t:
            await t.remove(A1, version_1)
            await t.remove(B1, version_b)
            await t.remove(A2, version_2)
    assert refused.value.iris == (A2,)
    assert refused.value.referrers == ((B2, "Book", "written_by"),)


# --- same transaction (PD-5, E10) -----------------------------------------------------------------


async def test_a_part_added_in_the_commit_that_names_the_removed_author_is_refused(session, store):
    """probe of PD-5: a link made by a part of an added root counts, unsent."""
    version = await session.add_graph(A1, author(A1))
    sent = len(store.sent("update"))
    part = URIRef(f"{B3}/parts/1")
    with pytest.raises(InUse) as refused:
        async with session.transaction() as t:
            await t.add_graph(
                B3, [*book(B3), (part, RDF.type, BOOK_CLASS), (part, WRITTEN_BY, URIRef(A1))]
            )
            await t.remove(A1, version)
    assert refused.value.referrers[0][0] == B3
    assert len(store.sent("update")) == sent


async def test_a_literal_in_an_added_graph_equal_to_the_removed_iri_is_no_refusal(session):
    """probe of PD-5: only IRI objects are links."""
    version = await session.add_graph(A1, author(A1))
    async with session.transaction() as t:
        await t.add_graph(B3, [*book(B3), (URIRef(B3), URIRef(LIB + "note"), Literal(A1))])
        await t.remove(A1, version)
    assert not await stored(session, A1)
    assert await stored(session, B3)


async def test_a_comment_added_for_the_removed_author_in_the_same_commit_is_no_refusal(session):
    """found D-T-1: PD-5 ignores the dependent pairs the guard (E9) honours.

    A comment added with the removal of its target, whose only link is ``has_target``, is no referrer
    once stored (``test_e9_...``), yet ``_link_rows`` counts it and the commit raises InUse naming it.
    """
    version = await session.add_graph(A1, author(A1))
    async with session.transaction() as t:
        await t.add_graph(C1, root(C1, v.ANNOTATION, (v.HAS_TARGET, A1)))
        await t.remove(A1, version)
    assert not await stored(session, A1)


async def test_an_added_root_linking_to_its_own_removed_neighbour_in_the_same_batch_is_refused(
    session,
):
    """probe of PD-5: the added root B3 names A2, removed with A1; A1 itself stays unnamed."""
    version_1 = await session.add_graph(A1, author(A1))
    version_2 = await session.add_graph(A2, author(A2))
    with pytest.raises(InUse) as refused:
        async with session.transaction() as t:
            await t.add_graph(B3, book(B3, by=A2))
            await t.remove(A1, version_1)
            await t.remove(A2, version_2)
    assert refused.value.iris == (A2,)
    assert await stored(session, A1)


async def test_a_root_removed_and_added_again_in_one_transaction_is_not_lost(session):
    """probe of PD-3: a removed root re-added by the same commit (a replace in effect) stays stored."""
    version = await session.add_graph(A1, author(A1))
    await session.add_graph(B1, book(B1, by=A1))
    try:
        async with session.transaction() as t:
            await t.remove(A1, version)
            await t.add_graph(A1, author(A1))
    except (InUse, Conflict, ValueError, RuntimeError):
        pass  # a refusal is allowed; losing the root or the referrer is not
    assert await stored(session, A1)
    assert await stored(session, B1)


@pytest.mark.parametrize(
    "segment", ["au'thors", 'au"thors', "au%20thors", "au;DROP", "au#x", "au\\thors", "au{x}"]
)
async def test_an_iri_that_needs_escaping_never_breaks_the_guard(store, refusal, segment):
    """probe of PD-3 (no concatenation): such a root is refused as a bad IRI or guarded; the store lives."""
    iri = f"{TENANT}/{segment}/{UUID(int=9)}"
    async with opened(store, refusal) as session:
        await session.add_graph(A2, author(A2))
        try:
            version = await session.add_graph(iri, author(iri))
            await session.add_graph(B1, book(B1, by=iri))
        except (InvalidIri, ValueError, BadQuery):  # the policy may refuse the IRI, not the guard
            assert await stored(session, A2)
            return
        with pytest.raises(InUse):
            await session.remove(iri, version)
        assert await stored(session, iri)


# --- readable, failures, row 4 --------------------------------------------------------------------


async def test_readable_raising_propagates_and_nothing_is_deleted(store):
    """probe of PD-9: an error of the readable callable is not turned into InUse or a Conflict."""
    refusal = Refusal(call_readable=True)

    async def broken(iri: str, rows: Sequence[ReferrerRow]) -> set[str]:
        raise RuntimeError("the policy is down")

    async with opened(store, refusal) as session:
        version = await session.add_graph(A1, author(A1))
        await session.add_graph(B1, book(B1, by=A1))
        with pytest.raises(RuntimeError, match="policy is down"):
            await session.remove(A1, version, readable=broken)
        assert await stored(session, A1)
        with pytest.raises(InUse):
            await session.remove(A1, version)  # the session is still usable


async def test_readable_raising_before_sending_for_an_add_names_nothing_sent(store):
    """probe of PD-5 / PD-9: the same on the exact path, which sends nothing."""
    refusal = Refusal(call_readable=True)

    async def broken(iri: str, rows: Sequence[ReferrerRow]) -> set[str]:
        raise RuntimeError("the policy is down")

    async with opened(store, refusal) as session:
        version = await session.add_graph(A1, author(A1))
        sent = len(store.sent("update"))
        with pytest.raises(RuntimeError, match="policy is down"):
            async with session.transaction(readable=broken) as t:
                await t.add_graph(B3, book(B3, by=A1))
                await t.remove(A1, version)
        assert len(store.sent("update")) == sent
        assert await stored(session, A1)


async def test_matrix_4_a_referrer_committed_after_the_delete_applied_is_not_detected(store):
    """probe of matrix row 4 / RISK-1: a referrer added right after the request leaves a dangling link."""
    async with opened(store, Refusal()) as session, opened(store, Refusal()) as writer:
        version = await session.add_graph(A1, author(A1))

        async def late_referrer() -> None:
            store.after_update = None
            await writer.add_graph(B1, book(B1, by=A1))

        store.after_update = late_referrer
        await session.remove(A1, version)
        assert not await stored(session, A1)
        assert await stored(session, B1)


# --- matrix 13: batches and max_roots -------------------------------------------------------------


async def seeded(session: Session, max_roots: int) -> UnitOfWork:
    seed = UnitOfWork(session, toy_mapper_limited(max_roots))
    seed.add(Author(id=A1, label="Frank"))
    seed.add(dune(B1, written_by=A1))
    await seed.commit(batches=True)
    return UnitOfWork(session, toy_mapper_limited(max_roots))


async def test_matrix_13_author_and_referrer_in_the_same_batch_are_removed(store, refusal):
    """probe of matrix row 13: within max_roots the batch is one transaction and the referrer goes too."""
    async with opened(store, refusal) as session:
        work = await seeded(session, 2)
        for cls, iri in ((Author, A1), (Book, B1)):
            work.remove(await work.get(cls, iri))
        await work.commit(batches=True)
        assert not await stored(session, A1)
        assert not await stored(session, B1)


async def test_matrix_13_the_first_batch_refused_commits_nothing(store, refusal):
    """probe of matrix row 13: author in batch 1, its referrer in batch 2; the error counts 0 of 2."""
    async with opened(store, refusal) as session:
        work = await seeded(session, 1)
        for cls, iri in ((Author, A1), (Book, B1)):
            work.remove(await work.get(cls, iri))
        with pytest.raises(InUse, match="0 of 2 batches committed"):
            await work.commit(batches=True)
        assert await stored(session, A1)
        assert await stored(session, B1)


async def test_matrix_13_referrer_first_in_a_later_batch_order_works(store, refusal):
    """probe of matrix row 13: the documented remedy, referrers first, removes both."""
    async with opened(store, refusal) as session:
        work = await seeded(session, 1)
        for cls, iri in ((Book, B1), (Author, A1)):
            work.remove(await work.get(cls, iri))
        await work.commit(batches=True)
        assert not await stored(session, A1)
        assert not await stored(session, B1)


async def test_matrix_13_without_batches_more_roots_than_max_roots_is_refused_unsent(
    store, refusal
):
    """probe of matrix row 13 (max_roots boundary): one over the limit is a size error, no guard run."""
    async with opened(store, refusal) as session:
        work = await seeded(session, 1)
        for cls, iri in ((Book, B1), (Author, A1)):
            work.remove(await work.get(cls, iri))
        with pytest.raises(Exception, match="max_roots|roots") as refused:
            await work.commit()
        assert not isinstance(refused.value, InUse)
        assert await stored(session, A1)
        assert await stored(session, B1)

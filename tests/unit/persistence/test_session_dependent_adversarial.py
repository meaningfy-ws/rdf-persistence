"""Adversarial probes of the dependent write guard and the cascade delete (dependent-aggregates PD-3
to PD-11, D-1, D-3; A-2, A-5, A-6, A-7; RISK-3, RISK-8), on the fake store.

Each docstring says what it attacks and whether it is a probe (expected to pass) or a found defect.
A ``NotFound`` carries no ``iris``; its message must name the whole.
"""

import pytest
from rdflib import RDF, URIRef

from rdf_persistence.core.domain.exceptions import (
    CommitTooLarge,
    Conflict,
    Forbidden,
    InUse,
    NotFound,
    Refused,
)
from rdf_persistence.core.domain.generated.rp_core import DependenceLink
from rdf_persistence.provenance.domain.generated.rp_provenance import Remove
from tests.unit.activity_helpers import Hook
from tests.unit.persistence.dependent_helpers import (
    A1,
    A2,
    AUDIT,
    LIB,
    LINK,
    OF_AUDIT,
    R1,
    R2,
    R3,
    RESULT,
    audit,
    iri,
    is_stored,
    names,
    new_store,
    opened,
    result,
)
from tests.unit.persistence.referrer_helpers import StubRefusal

FINDING, NOTE, SUBRESULT = (URIRef(LIB + n) for n in ("Finding", "Note", "SubResult"))
OF_RESULT, OF_FINDING, NOTE_OF, CITES = (
    URIRef(LIB + n) for n in ("of_result", "of_finding", "note_of", "cites_finding")
)
LINK_F = DependenceLink(
    part_classes=[str(FINDING)], pointer=str(OF_RESULT), whole_classes=[str(RESULT)]
)
LINK_N = DependenceLink(
    part_classes=[str(NOTE)], pointer=str(OF_FINDING), whole_classes=[str(FINDING)]
)
LINK_SIDE = DependenceLink(  # a second link on the same whole class: a note of an audit
    part_classes=[str(NOTE)], pointer=str(NOTE_OF), whole_classes=[str(AUDIT)]
)
LINK_SUB = DependenceLink(
    part_classes=[str(RESULT), str(SUBRESULT)],
    pointer=str(OF_AUDIT),
    whole_classes=[str(AUDIT)],
)
CHAIN = (LINK, LINK_F, LINK_N)
F1, F2 = iri("findings", 1), iri("findings", 2)
N1, N2 = iri("notes", 1), iri("notes", 2)


def part(root: str, cls: URIRef, pointer: URIRef, whole: str) -> list:
    return [(URIRef(root), RDF.type, cls), (URIRef(root), pointer, URIRef(whole))]


def finding(root: str, whole: str) -> list:
    return part(root, FINDING, OF_RESULT, whole)


def note(root: str, whole: str) -> list:
    return part(root, NOTE, OF_FINDING, whole)


@pytest.fixture
async def store():
    return await new_store()


async def chain(session) -> dict[str, str]:
    """A1 <- R1 <- F1 <- N1 (a whole that is a part, three levels down); the versions by root."""
    versions = {A1: await session.add_graph(A1, audit(A1))}
    versions[R1] = await session.add_graph(R1, result(R1, A1))
    versions[F1] = await session.add_graph(F1, finding(F1, R1))
    versions[N1] = await session.add_graph(N1, note(N1, F1))
    return versions


# --- a whole with parts of two links --------------------------------------------------------------
async def test_a_whole_with_parts_of_two_links_loses_both_kinds(store):
    """Attacks PD-6 (links share the whole class); probe of PD-6."""
    async with opened(store, links=(LINK, LINK_SIDE)) as session:
        a1 = await session.add_graph(A1, audit(A1))
        await session.add_graph(R1, result(R1, A1))
        await session.add_graph(N1, part(N1, NOTE, NOTE_OF, A1))
        await session.remove(A1, a1)
        stored = [await is_stored(session, root) for root in (A1, R1, N1)]
        assert stored == [False] * 3, "the parts of both links went with the whole"


# --- the same root written and removed in one transaction -----------------------------------------
async def test_a_whole_added_and_removed_in_one_transaction_is_a_value_error(store):
    """Attacks PD-5 (a part's whole both added and removed); probe of PD-5."""
    async with opened(store) as session:
        updates = len(store.sent("update"))
        with pytest.raises(ValueError, match="already has a change"):
            async with session.transaction() as transaction:
                await transaction.add_graph(A1, audit(A1))
                await transaction.add_graph(R1, result(R1, A1))
                await transaction.remove(A1, "any")
        assert len(store.sent("update")) == updates, "nothing was sent"


async def test_a_part_added_before_its_whole_is_removed_is_a_conflict(store):
    """Attacks PD-5 step 2 with the remove collected first; probe of PD-5."""
    async with opened(store) as session:
        a1 = await session.add_graph(A1, audit(A1))
        updates = len(store.sent("update"))
        with pytest.raises(Conflict) as error:
            async with session.transaction() as transaction:
                await transaction.remove(A1, a1)
                await transaction.add_graph(R3, result(R3, A1))
        assert error.value.iris == (A1, R3), "the whole and the part are named"
        assert len(store.sent("update")) == updates, "nothing was sent"
        assert await is_stored(session, A1), "the whole stays"


# --- a part and its whole removed together, counted once ------------------------------------------
@pytest.mark.parametrize(("max_roots", "refused"), [(4, False), (3, True)], ids=["exact", "over"])
async def test_a_chain_is_counted_once_per_root_at_the_limit_across_levels(
    store, max_roots, refused
):
    """Attacks PD-6 (the count across three levels, with F1 and N1 also removed by the caller)."""
    async with opened(store, links=CHAIN, max_roots=10) as session:
        versions = await chain(session)
    async with opened(store, links=CHAIN, max_roots=max_roots) as session:

        async def delete() -> None:
            async with session.transaction() as transaction:
                await transaction.remove(A1, versions[A1])
                await transaction.remove(F1, versions[F1])
                await transaction.remove(N1, versions[N1])

        if refused:
            with pytest.raises(CommitTooLarge, match=str(max_roots)):
                await delete()
            assert await is_stored(session, N1), "nothing was written"
        else:
            await delete()
            stored = [await is_stored(session, root) for root in (A1, R1, F1, N1)]
            assert stored == [False] * 4, "the four roots went, none twice"


async def test_a_part_and_its_whole_removed_together_record_one_invalidation_each(store):
    """Attacks PD-9 and A-7 (a root both explicit and found); probe of PD-9."""
    hook = Hook()
    async with opened(store, on_commit=hook) as session:
        a1 = await session.add_graph(A1, audit(A1))
        r1 = await session.add_graph(R1, result(R1, A1))
        async with session.transaction() as transaction:
            await transaction.remove(R1, r1)
            await transaction.remove(A1, a1)
        activity = hook.calls[-1][0]
        assert isinstance(activity, Remove), "a Remove activity"
        entities = sorted(i.entity for i in activity.invalidations or [])
        assert entities == [A1, R1], "one invalidation per root, no duplicate"


# --- a whole that is itself a part ----------------------------------------------------------------
async def test_deleting_the_middle_of_a_chain_keeps_what_is_above_it(store):
    """Attacks PD-5/PD-6 (a whole three levels down); probe of PD-6."""
    async with opened(store, links=CHAIN) as session:
        versions = await chain(session)
        await session.remove(F1, versions[F1])
        stored = [await is_stored(session, root) for root in (A1, R1, F1, N1)]
        assert stored == [True, True, False, False], "F1 and its note went, A1 and R1 stay"


async def test_deleting_the_top_of_a_chain_removes_three_levels(store):
    """Attacks PD-6 (level-by-level discovery depth three); probe of PD-6."""
    async with opened(store, links=CHAIN) as session:
        versions = await chain(session)
        await session.remove(A1, versions[A1])
        stored = [await is_stored(session, root) for root in (A1, R1, F1, N1)]
        assert stored == [False] * 4, "every level went"


async def test_a_note_written_under_a_finding_while_the_top_is_deleted_is_a_conflict(store):
    """Attacks PD-7 at depth three (a late part of a cascaded part); probe of PD-7."""
    async with opened(store, links=CHAIN) as session, opened(store, "ben", links=CHAIN) as other:
        versions = await chain(session)

        async def write_note() -> None:
            await other.add_graph(N2, note(N2, F1))

        store.before_update = write_note
        with pytest.raises(Conflict) as error:
            await session.remove(A1, versions[A1])
        assert error.value.iris == (A1,), "the removed root is named"
        assert await is_stored(session, N2), "the late note was kept"
        assert await is_stored(session, F1), "and so was its finding: nothing was removed"


# --- a part class and its subclass ----------------------------------------------------------------
def sub_result(root: str, whole: str, *classes: URIRef) -> list:
    return [(URIRef(root), RDF.type, c) for c in classes] + [
        (URIRef(root), OF_AUDIT, URIRef(whole))
    ]


async def test_a_part_of_a_subclass_needs_its_whole_and_goes_with_it(store):
    """Attacks PD-1/PD-3 (a part typed with a subclass of the part class); probe of PD-3."""
    async with opened(store, links=(LINK_SUB,)) as session:
        with pytest.raises(NotFound) as error:
            await session.add_graph(R1, sub_result(R1, A1, SUBRESULT))
        assert names(error.value, A1), "a subclass part has no whole to stand on"
        a1 = await session.add_graph(A1, audit(A1))
        await session.add_graph(R1, sub_result(R1, A1, SUBRESULT))
        await session.remove(A1, a1)
        assert not await is_stored(session, R1), "the subclass part went with its whole"


async def test_a_part_typed_with_two_part_classes_counts_once_against_the_limit(store):
    """Attacks PD-6 (a part's two rdf:types give two discovery rows, one root); probe of PD-6."""
    async with opened(store, links=(LINK_SUB,), max_roots=2) as session:
        a1 = await session.add_graph(A1, audit(A1))
        await session.add_graph(R1, sub_result(R1, A1, RESULT, SUBRESULT))
        await session.remove(A1, a1)
        assert not await is_stored(session, R1), "two roots, at the limit of two"


async def test_double_typed_parts_cannot_hide_the_parts_past_the_row_limit(store):
    """Attacks PD-6 (``LIMIT max_roots + 1`` counts rows, a double-typed part makes two rows);
    found ADV-1: the query is cut at four rows, so only two parts are seen, the count stays at
    three and the delete is sent; the third part is caught later as a late part (a ``Conflict``
    naming the whole, on every retry) instead of ``CommitTooLarge``.

    Three parts of A1 with two types each are four roots over a limit of three, so the delete is
    ``CommitTooLarge``; a truncated read that sees two parts must not pass as three.
    """
    async with opened(store, links=(LINK_SUB,), max_roots=3) as session:
        a1 = await session.add_graph(A1, audit(A1))
        for root in (R1, R2, R3):
            await session.add_graph(root, sub_result(root, A1, RESULT, SUBRESULT))
        with pytest.raises(CommitTooLarge, match="3"):
            await session.remove(A1, a1)
        assert await is_stored(session, R3), "nothing was written"


# --- a sibling written while a part is deleted explicitly -----------------------------------------
async def test_a_sibling_added_while_a_part_is_deleted_does_not_block_it(store):
    """Attacks PD-7 (the guard is per removed root, not per whole); probe of PD-7."""
    async with opened(store) as session, opened(store, "ben") as other:
        await session.add_graph(A1, audit(A1))
        r1 = await session.add_graph(R1, result(R1, A1))

        async def add_sibling() -> None:
            await other.add_graph(R2, result(R2, A1))

        store.before_update = add_sibling
        await session.remove(R1, r1)
        assert not await is_stored(session, R1), "the part was removed"
        assert await is_stored(session, R2), "its sibling was written"
        assert await is_stored(session, A1), "the whole stays"


async def test_a_child_added_under_a_part_deleted_explicitly_is_a_conflict(store):
    """Attacks PD-7 (the explicit part is itself a removed root); probe of PD-7."""
    async with opened(store, links=CHAIN) as session, opened(store, "ben", links=CHAIN) as other:
        await session.add_graph(A1, audit(A1))
        r1 = await session.add_graph(R1, result(R1, A1))

        async def add_child() -> None:
            await other.add_graph(F2, finding(F2, R1))

        store.before_update = add_child
        with pytest.raises(Conflict) as error:
            await session.remove(R1, r1)
        assert error.value.iris == (R1,), "the removed part is named"
        assert await is_stored(session, R1), "nothing was removed"


# --- a pointer that tries to break out of the SPARQL text -----------------------------------------
INJECTED = (
    "https://elsewhere.example/a> } ; DROP ALL ; INSERT DATA { <https://x/y> <https://x/z> <https://x/w",
    A1 + "> } ; DROP ALL ; #",
    "https://elsewhere.example/a b",
    "https://elsewhere.example/\u0000",
)


@pytest.mark.parametrize("whole", INJECTED, ids=["foreign", "tenant prefix", "space", "nul"])
async def test_a_pointer_that_carries_sparql_is_refused_and_never_sent(store, whole):
    """Attacks PD-3 (a pointer value is put in a guard and an ASK); probe of PD-3."""
    async with opened(store) as session:
        await session.add_graph(A1, audit(A1))
        updates, queries = len(store.sent("update")), len(store.sent("query"))
        with pytest.raises(Exception) as error:  # which refusal is not the point
            await session.add_graph(R1, result(R1, whole))
        assert not isinstance(error.value, AssertionError), "a refusal, not a crash"
        assert len(store.sent("update")) == updates, "nothing was sent"
        assert not any("DROP ALL" in text for text in store.sent("query")[queries:]), (
            "the value never reached a query"
        )
        assert await is_stored(session, A1), "the store is intact"


# --- a cascaded part the caller may not read is never named (PD-10, RISK-3) -----------------------
class Pinning:
    """A write guard whose delete rule refuses the roots in ``pinned``, naming them as a rule would."""

    def __init__(self, pinned: frozenset[str]) -> None:
        self.pinned = pinned

    async def prepare(
        self, session, iri, triples, stored, allowed_state, *, context, allowed_assignees=None
    ):
        return triples

    async def prepare_remove(self, session, iri, if_version, *, context):
        if iri in self.pinned:
            raise Refused(f"{iri} is pinned", iris=(iri,))


def reading(*hidden: str):
    return lambda root: root not in hidden


@pytest.mark.parametrize(
    ("hidden", "named"),
    [pytest.param(R2, False, id="unreadable part"), pytest.param(None, True, id="readable part")],
)
async def test_a_delete_rule_refusing_a_part_names_it_only_when_readable(store, hidden, named):
    """Attacks PD-10/D-1/A-6 (a validator's refusal of a cascaded part); probe of PD-10 until
    task 2.6 rewrites the cascaded refusals: the part must not be named when unreadable."""
    may_read = reading(hidden) if hidden else reading()
    async with opened(store, guards=Pinning(frozenset({R2})), may_read=may_read) as session:
        a1 = await session.add_graph(A1, audit(A1))
        await session.add_graph(R2, result(R2, A1))
        with pytest.raises(Refused) as error:
            await session.remove(A1, a1)
        shown = names(error.value, R2) or R2 in error.value.iris
        assert shown is named, "the part is named exactly when the caller may read it"
        assert await is_stored(session, A1), "all or nothing: the whole stays"
        assert await is_stored(session, R2), "all or nothing: the part stays"


@pytest.mark.parametrize(
    ("hidden", "named"),
    [pytest.param(F1, False, id="unreadable part"), pytest.param(None, True, id="readable part")],
)
async def test_a_refusing_part_cited_from_outside_is_named_only_when_readable(store, hidden, named):
    """Attacks PD-8/PD-10 (``InUse`` for a cascaded part cited from outside); probe of PD-10 until
    task 2.6: the part must not be named when unreadable."""
    refusal = StubRefusal(refusing=frozenset({FINDING}))
    may_read = reading(hidden) if hidden else reading()
    async with opened(store, links=CHAIN, removals=refusal, may_read=may_read) as session:
        versions = await chain(session)
        await session.add_graph(A2, audit(A2))
        _, _, a2 = await session.get_graph(A2)
        await session.replace_graph(A2, [*audit(A2), (URIRef(A2), CITES, URIRef(F1))], a2)
        with pytest.raises(InUse) as error:
            await session.remove(A1, versions[A1])
        shown = names(error.value, F1) or F1 in error.value.iris
        assert shown is named, "the part is named exactly when the caller may read it"
        assert await is_stored(session, F1), "nothing was removed"


class Vanishing(Pinning):
    """A write guard that finds a cascaded part gone or barred when it prepares the removal."""

    def __init__(self, kind: type[Exception], gone: frozenset[str]) -> None:
        super().__init__(gone)
        self.kind = kind

    async def prepare_remove(self, session, iri, if_version, *, context):
        if iri in self.pinned:
            raise self.kind(f"no graph {iri}")


@pytest.mark.parametrize("kind", [NotFound, Forbidden])
async def test_a_part_gone_or_barred_before_collection_is_never_named_when_unreadable(store, kind):
    """Attacks PD-10 (a NotFound from the read of a part that vanished after discovery, or a
    Forbidden from a workflow guard, names the part's IRI)."""
    guards = Vanishing(kind, frozenset({R2}))
    async with opened(store, guards=guards, may_read=reading(R2)) as session:
        a1 = await session.add_graph(A1, audit(A1))
        await session.add_graph(R2, result(R2, A1))
        with pytest.raises(kind) as error:
            await session.remove(A1, a1)
        assert R2 not in str(error.value), "the unreadable part is not named"
        assert A1 in str(error.value), "the whole is named"


async def test_a_part_changed_meanwhile_is_never_named_when_unreadable(store):
    """Attacks PD-10 (the message of the version conflict, not only its ``iris``); probe of PD-10."""
    async with (
        opened(store, may_read=reading(R2)) as session,
        opened(store, "ben") as other,
    ):
        a1 = await session.add_graph(A1, audit(A1))
        r2 = await session.add_graph(R2, result(R2, A1))

        async def change_part() -> None:
            await other.replace_graph(R2, result(R2, A1), r2)

        store.before_update = change_part
        with pytest.raises(Conflict) as error:
            await session.remove(A1, a1)
        assert not names(error.value, R2), "the message does not name the part"
        assert R2 not in error.value.iris, "nor does iris"
        assert error.value.iris == (A1,), "the whole is named"


async def test_a_part_added_under_an_unreadable_cascaded_part_names_the_removed_root(store):
    """Attacks PD-10/PD-5 step 2 (a Conflict naming the whole of a cascaded unreadable part)."""
    async with opened(store, links=CHAIN, may_read=reading(R1)) as session:
        versions = await chain(session)
        with pytest.raises(Conflict) as error:
            async with session.transaction() as transaction:
                await transaction.add_graph(F2, finding(F2, R1))
                await transaction.remove(A1, versions[A1])
        assert not names(error.value, R1), "the unreadable part is not named"
        assert error.value.iris == (A1, F2), "the removed root and the caller's own add are"


# --- sessions and rows nothing else reaches -------------------------------------------------------
async def test_a_session_with_no_links_discovers_nothing(store):
    """Attacks PD-6 (a session with no links pays no discovery query); probe of PD-6."""
    async with opened(store, links=()) as session:
        a1 = await session.add_graph(A1, audit(A1))
        before = len(store.sent("query"))
        await session.remove(A1, a1)
        assert not any("VALUES ?whole" in q for q in store.sent("query")[before:]), "no discovery"


async def test_a_part_removed_with_a_validator_that_passes_goes_with_its_whole(store):
    """Attacks D-1 (the positive case: validators run per part and let it pass); probe of D-1."""
    async with opened(store, guards=Pinning(frozenset({R3}))) as session:
        a1 = await session.add_graph(A1, audit(A1))
        await session.add_graph(R2, result(R2, A1))
        await session.remove(A1, a1)
        assert not await is_stored(session, R2), "an unpinned part went"

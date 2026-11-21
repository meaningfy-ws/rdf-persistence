"""Nested collections: a cycle is refused, a racing one is a conflict (PD-4, PD-5, PD-7)."""

import pytest

from rdf_persistence import Conflict, InvalidBody
from rdf_persistence.testkit import fake_session
from tests.toy import TENANT, shelf, shelf_iri, toy_mapper
from tests.unit.collaboration.test_write_guards import guards, save, version_of

X, Y, Z = shelf_iri(1), shelf_iri(2), shelf_iri(3)


def nesting(iri: str, *members: str):
    """A shelf that nests the given shelves."""
    return shelf(iri, nests=True).model_copy(update={"has_part": list(members) or None})


async def replace_in(session, t, *shelves) -> None:
    """Collect, in the transaction ``t``, the replacement of each stored shelf by ``shelves``."""
    for each in shelves:
        triples = toy_mapper().to_triples(each)
        await t.replace_graph(str(each.id), triples, await version_of(session, str(each.id)))


async def replace(session, *shelves) -> None:
    async with session.transaction() as t:
        await replace_in(session, t, *shelves)


async def chain(session, length: int) -> None:
    """Store ``length`` nesting shelves, each one naming the one stored before it."""
    for n in range(1, length + 1):
        await save(session, nesting(shelf_iri(n), *([shelf_iri(n - 1)] if n > 1 else [])))


# (the length of the chain, the number of collections the refusal counts between the two ends).
CYCLES = [
    pytest.param(1, 0, id="a-shelf-naming-itself"),
    pytest.param(2, 0, id="a-two-cycle"),
    pytest.param(3, 1, id="a-three-cycle"),
]


@pytest.mark.parametrize(("length", "more"), CYCLES)
async def test_a_replace_that_closes_a_cycle_is_refused_and_nothing_is_stored(length, more):
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await chain(session, length)
        before = await version_of(session, X)
        text = f"saving {X} would make a cycle: {X} → {shelf_iri(length)} → \\({more} more\\) → {X}"
        with pytest.raises(InvalidBody, match=text):
            await replace(session, nesting(X, shelf_iri(length)))
        assert await version_of(session, X) == before, "the shelf is as stored"


async def test_the_refusal_of_a_cycle_names_no_shelf_between_the_two_ends():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await chain(session, 3)
        with pytest.raises(InvalidBody) as refused:
            await replace(session, nesting(X, Z))
        assert Y not in str(refused.value), "a shelf between may be hidden from the saver"


async def test_a_cycle_closed_by_two_replaces_of_one_transaction_is_refused_at_the_second():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, nesting(X))
        await save(session, nesting(Y))
        versions = [await version_of(session, i) for i in (X, Y)]
        with pytest.raises(InvalidBody, match=f"saving {Y} would make a cycle"):
            await replace(session, nesting(X, Y), nesting(Y, X))
        assert [await version_of(session, i) for i in (X, Y)] == versions, "nothing is stored"


async def test_two_saves_that_together_close_a_cycle_commit_one_and_conflict_the_other():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, nesting(X))
        await save(session, nesting(Y))
        with pytest.raises(Conflict) as refused:
            async with session.transaction() as first:
                await replace_in(session, first, nesting(X, Y))
                async with session.transaction() as second:  # collected after the first, commits first
                    await replace_in(session, second, nesting(Y, X))
        assert refused.value.iris == (Y,), "the conflict names the collection the other one saved"
        with pytest.raises(InvalidBody, match="would make a cycle"):
            await replace(session, nesting(X, Y))  # the retry reads Y as saved


async def test_a_leaf_turned_into_a_nesting_shelf_meanwhile_conflicts_the_save_that_added_it():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, shelf(Y))  # a leaf: nests is false
        await save(session, nesting(X))
        with pytest.raises(Conflict) as refused:
            async with session.transaction() as adding:
                await replace_in(session, adding, nesting(X, Y))
                await replace(session, nesting(Y, X))  # Y nests X, committed first
        assert refused.value.iris == (Y,), "the conflict names the leaf"


async def test_a_replace_that_adds_no_nested_shelf_adds_no_guard():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, nesting(Y))
        await save(session, nesting(X, Y), nesting(Z))
        added = []
        for saved in (nesting(X, Y).model_copy(update={"label": "Renamed"}), nesting(Z, Y)):
            async with session.transaction() as t:
                before = len(t._guards)
                await replace_in(session, t, saved)
                added.append(len(t._guards) - before)
        renamed, nested = added
        assert renamed == 1, "a rename is guarded by its own replace only"
        assert nested > renamed, "a nested shelf added is guarded by what the walk read"

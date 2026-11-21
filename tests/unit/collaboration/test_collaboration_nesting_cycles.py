"""Nested collections: a cycle is refused, a racing one is a conflict (PD-4, PD-5, PD-7)."""

import pytest

from rdf_persistence import Conflict, InvalidBody
from rdf_persistence.testkit import FakeStore, fake_session
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
                async with (
                    session.transaction() as second
                ):  # collected after the first, commits first
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


# -- the member class of a nested collection cannot change under its parent (review C-1, W-4) --------


def holding(iri: str, **slots):
    """A flat shelf of books (no members) with the given slots changed."""
    return shelf(iri).model_copy(update=slots)


async def test_the_member_class_of_a_nested_shelf_cannot_change_while_a_nesting_shelf_holds_it():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, holding(Y))
        await save(session, nesting(X, Y))
        before = await version_of(session, Y)
        text = f"the member class of {Y} cannot change while a nesting collection holds it"
        with pytest.raises(InvalidBody, match=text) as refused:
            await replace(session, holding(Y, member_class="Author"))
        assert X not in str(refused.value), "the holder may be hidden from the saver"
        assert await version_of(session, Y) == before, "the shelf is as stored"


async def test_the_member_class_of_a_shelf_nobody_nests_can_change():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, holding(Y))
        await replace(session, holding(Y, member_class="Author"))
        assert await version_of(session, Y), "the replace was accepted"


async def test_a_new_member_class_refuses_the_nested_shelves_the_stored_one_held():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, holding(Y))
        await save(session, nesting(X, Y))
        before = await version_of(session, X)
        with pytest.raises(InvalidBody, match=f"not stored aggregates of Author: .*{Y}"):
            await replace(session, nesting(X, Y).model_copy(update={"member_class": "Author"}))
        assert await version_of(session, X) == before, "the shelf is as stored"


async def test_the_member_class_of_a_shelf_cannot_change_once_a_collected_replace_nests_it():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, holding(Y))
        await save(session, nesting(X))
        versions = [await version_of(session, i) for i in (X, Y)]
        with pytest.raises(InvalidBody, match="cannot change while a nesting collection holds it"):
            await replace(session, nesting(X, Y), holding(Y, member_class="Author"))
        assert [await version_of(session, i) for i in (X, Y)] == versions, "nothing is stored"


async def test_a_replace_cannot_nest_a_shelf_whose_member_class_a_collected_replace_changed():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, holding(Y))
        await save(session, nesting(X))
        versions = [await version_of(session, i) for i in (X, Y)]
        with pytest.raises(InvalidBody, match=f"not stored aggregates of Book: .*{Y}"):
            await replace(session, holding(Y, member_class="Author"), nesting(X, Y))
        assert [await version_of(session, i) for i in (X, Y)] == versions, "nothing is stored"


async def test_the_member_class_changes_once_a_collected_replace_no_longer_nests_the_shelf():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, holding(Y))
        await save(session, nesting(X, Y))
        await replace(session, nesting(X), holding(Y, member_class="Author"))
        assert await version_of(session, Y), "the replace was accepted"


async def test_renaming_a_nesting_shelf_reads_no_more_for_more_nested_shelves():
    counts = []
    for nested in (1, 3):
        store = FakeStore()
        async with fake_session(store, tenant_iri=TENANT, guards=guards()) as session:
            subs = [shelf_iri(10 + n) for n in range(nested)]
            for sub in subs:
                await save(session, holding(sub))
            await save(session, nesting(X, *subs))
            before = len(store.sent("query"))
            await replace(session, nesting(X, *subs).model_copy(update={"label": "New"}))
            counts.append(len(store.sent("query")) - before)
    assert counts[0] == counts[1], "a stored nested shelf is not read again on each save"

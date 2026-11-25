"""Nested collections, attacked: the walk, the same-transaction overlay, races, corrupt stores (PD-2 to PD-9).

A test marked ``xfail(strict=True)`` pins a defect found by attack; its reason says which.
"""

import itertools
from contextlib import asynccontextmanager

import pytest

from rdf_persistence import Conflict, InvalidBody, StoredDataInvalid
from rdf_persistence.collaboration.services.write_guards import _walk_from
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.testkit import FakeStore, fake_session
from tests.toy import TENANT, book_iri, shelf_iri, toy_mapper
from tests.unit.collaboration.collaboration_data import (
    a_shelf,
    as_ada,
    as_bob_without,
    cascade_stored,
    chain,
    collections_put,
    guards,
    nesting,
    put_book,
    replace,
    replace_in,
    save,
    version_of,
)

# --- walk_from: the pure walk ----------------------------------------------------------------


def test_walk_from_follows_a_chain_a_hundred_thousand_deep_without_recursing():
    skeleton = {f"n{i}": [f"n{i + 1}"] for i in range(100_000)}
    skeleton["n100000"] = ["root"]
    reached, cycle = _walk_from("root", ["n0"], skeleton)
    assert cycle == ("n0", 100_000), "a cycle through every collection of the chain"


def test_walk_from_reaches_every_node_of_a_long_chain_that_does_not_come_back():
    skeleton = {f"n{i}": [f"n{i + 1}"] for i in range(50_000)}
    reached, cycle = _walk_from("root", ["n0"], skeleton)
    assert cycle is None
    assert len(reached) == 50_001, "the end of the chain is reached and not entered"


def test_walk_from_ends_on_a_cycle_that_does_not_pass_through_the_root():
    skeleton = {"a": ["b"], "b": ["a", "c"], "c": ["c"]}
    reached, cycle = _walk_from("root", ["a"], skeleton)
    assert cycle is None, "a loop elsewhere is not the saved collection's cycle"
    assert reached == {"a", "b", "c"}


def test_walk_from_enters_a_diamond_once_and_reports_the_cycle_through_it():
    skeleton = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": ["root"]}
    reached, cycle = _walk_from("root", ["a"], skeleton)
    assert cycle == ("a", 2), "a, then b or c, then d: two between a and the root, d counts"


def test_walk_from_reports_a_cycle_through_a_node_a_first_path_already_entered():
    # d is entered by the long way first; the cycle it closes must still be found
    skeleton = {"a": ["d", "x"], "x": ["d"], "d": ["root"]}
    reached, cycle = _walk_from("root", ["a"], skeleton)
    assert cycle is not None
    assert cycle[0] == "a"


def test_walk_from_names_the_new_member_a_cycle_enters_by_and_not_the_first_new_member():
    skeleton = {"a": ["x"], "b": ["y"], "y": ["root"]}
    reached, cycle = _walk_from("root", ["a", "b"], skeleton)
    assert cycle == ("b", 1), "the second new member closes it, through y"


def test_walk_from_finds_a_cycle_through_a_node_both_new_members_lead_to():
    skeleton = {"a": ["d"], "b": ["d"], "d": ["root"]}
    reached, cycle = _walk_from("root", ["b", "a"], skeleton)
    assert cycle is not None
    assert cycle[1] == 1


@pytest.mark.parametrize(
    ("skeleton", "reached"),
    [
        pytest.param({}, {"n"}, id="a-new-member-outside-the-skeleton-is-reached-not-entered"),
        pytest.param({"n": []}, {"n"}, id="a-member-without-members"),
        pytest.param({"n": ["n"]}, {"n"}, id="a-member-naming-itself"),
    ],
)
def test_walk_from_reaches_a_new_member_whatever_the_skeleton_says_of_it(skeleton, reached):
    walked, cycle = _walk_from("root", ["n"], skeleton)
    assert cycle is None
    assert walked == reached


def test_walk_from_a_root_naming_itself_is_a_cycle_with_nothing_between():
    assert _walk_from("root", ["root"], {})[1] == ("root", 0)


def test_walk_from_nothing_new_walks_nothing():
    reached, cycle = _walk_from("root", [], {"a": ["root"]})
    assert cycle is None
    assert reached == frozenset()


def test_walk_from_never_enters_the_root_so_its_stored_members_are_not_followed():
    skeleton = {"root": ["old"], "old": ["new"], "new": ["root"]}
    reached, cycle = _walk_from("root", ["new"], skeleton)
    assert cycle == ("new", 0), "root is met first, as new's member"
    assert "old" not in reached, "the root's stale stored edge is never followed"


@pytest.mark.xfail(
    strict=True,
    reason="the walk is depth first, so between counts the path it met first, not the shortest: "
    "the refusal says '(3 more)' where one collection stands between",
)
def test_walk_from_counts_the_shortest_way_back_when_there_are_two():
    skeleton = {"a": ["root", "b"], "b": ["c"], "c": ["d"], "d": ["root"]}
    assert _walk_from("root", ["a"], skeleton)[1] == ("a", 0)


# --- the guard: a save that closes a cycle ----------------------------------------------------

X, Y, Z, W = (shelf_iri(n) for n in (1, 2, 3, 4))


async def test_a_replace_that_drops_one_nested_shelf_and_adds_one_that_leads_back_is_refused():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, nesting(Y))
        await save(session, nesting(X, Y))
        await save(session, nesting(W, X))
        before = await version_of(session, X)
        with pytest.raises(InvalidBody, match="would make a cycle"):
            await replace(session, nesting(X, W))  # Y is dropped, W (which nests X) is added
        assert await version_of(session, X) == before


async def test_a_replace_that_drops_the_old_edge_and_adds_an_unrelated_shelf_is_accepted():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, nesting(Y))
        await save(session, nesting(Z, Y))
        await save(session, nesting(X, Y))
        await replace(session, nesting(X, Z))  # Z nests Y, which no longer is X's: no cycle
        assert await version_of(session, X)


async def test_an_add_of_a_shelf_over_a_deep_stored_tree_is_accepted():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await chain(session, 5)
        await save(
            session, nesting(shelf_iri(9), shelf_iri(5))
        )  # nobody names it: no cycle possible
        assert await cascade_stored(session, shelf_iri(9))


async def test_an_add_of_a_shelf_naming_itself_is_refused_as_not_stored():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        with pytest.raises(InvalidBody, match="not stored aggregates"):
            await save(session, nesting(X, X))


async def test_an_add_and_a_replace_naming_each_other_in_one_transaction_are_refused():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, nesting(Y))
        with pytest.raises(InvalidBody):
            async with session.transaction() as t:
                await t.add_graph(X, toy_mapper().to_triples(nesting(X, Y)))
                await replace_in(session, t, nesting(Y, X))
        assert not await cascade_stored(session, X), "nothing is stored"


@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
async def test_three_replaces_of_one_transaction_close_a_cycle_whatever_their_order(order):
    edges = [nesting(X, Y), nesting(Y, Z), nesting(Z, X)]
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, nesting(X), nesting(Y), nesting(Z))
        versions = [await version_of(session, i) for i in (X, Y, Z)]
        with pytest.raises(InvalidBody, match="would make a cycle"):
            await replace(session, *(edges[i] for i in order))
        assert [await version_of(session, i) for i in (X, Y, Z)] == versions


@pytest.mark.xfail(
    strict=True,
    reason="the overlay of context.collected ignores removes: a shelf removed earlier in the "
    "transaction still carries its edges in the walk, so a false cycle is refused (low: conservative)",
)
async def test_a_replace_after_a_remove_of_a_shelf_on_the_path_is_not_refused_for_the_removed_edge():
    """Y nests X and N nests Y; the transaction removes Y, then lets X name N: no cycle remains."""
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, nesting(X))
        await save(session, nesting(Y, X))
        await save(session, nesting(Z, Y))
        async with session.transaction() as t:
            await t.remove(Y, await version_of(session, Y))
            await replace_in(session, t, nesting(X, Z))
        assert not await cascade_stored(session, Y)


async def test_the_refusal_of_a_four_cycle_names_neither_shelf_between():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await chain(session, 4)
        with pytest.raises(InvalidBody) as refused:
            await replace(session, nesting(X, W))
        text = str(refused.value)
        assert Y not in text, "a shelf between may be hidden from the saver"
        assert Z not in text, "a shelf between may be hidden from the saver"
        assert "(2 more)" in text


async def test_a_leaf_named_by_a_shelf_cannot_later_be_turned_nesting_and_name_it_back():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, a_shelf(X))  # a leaf
        await save(session, nesting(Y, X))
        with pytest.raises(InvalidBody, match="would make a cycle"):
            await replace(session, nesting(X, Y))


@asynccontextmanager
async def raw_and_guarded():
    """Two sessions on one store: ``raw`` bypasses every guard, ``checked`` has them."""
    store = FakeStore()
    async with (
        fake_session(store, tenant_iri=TENANT) as raw,
        fake_session(store, tenant_iri=TENANT, guards=guards()) as checked,
    ):
        yield raw, checked


async def test_a_leaf_that_stores_a_shelf_and_is_turned_nesting_cannot_close_a_cycle_unchecked():
    async with raw_and_guarded() as (raw, checked):
        await collections_put(raw, nesting(Y, X))  # Y nests X
        await collections_put(
            raw, a_shelf(X, has_part=[Y])
        )  # X is a leaf that nonetheless names Y (corrupt)
        try:
            await replace(checked, nesting(X, Y))
        except InvalidBody:
            return
        pytest.fail("X -> Y -> X was stored")


# --- races ------------------------------------------------------------------------------------


async def test_a_graph_changed_between_two_saves_of_one_transaction_is_a_conflict_not_a_value_error():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, nesting(Y), nesting(X), nesting(Z))
        with pytest.raises(Conflict):
            async with session.transaction() as t:
                await replace_in(session, t, nesting(X, Y))  # relies on Y as read
                await replace(session, nesting(Y).model_copy(update={"label": "Other"}))
                await replace_in(session, t, nesting(Z, Y))  # reads Y changed


async def test_a_shelf_deleted_on_the_walked_path_before_commit_conflicts_the_save():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, nesting(Z))
        await save(session, nesting(Y, Z))
        await save(session, nesting(X))
        with pytest.raises(Conflict) as refused:
            async with session.transaction() as adding:
                await replace_in(session, adding, nesting(X, Y))  # walks Y, then Z
                async with session.transaction() as deleting:
                    await deleting.remove(Z, await version_of(session, Z))
        assert refused.value.iris == (Z,)


async def test_a_shelf_collected_earlier_and_changed_by_another_writer_conflicts_on_its_own_guard():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, nesting(X), nesting(Y), nesting(Z))
        with pytest.raises(Conflict) as refused:
            async with session.transaction() as t:
                await replace_in(session, t, nesting(Y, Z))  # Y collected: not relied on again
                await replace(session, nesting(Y).model_copy(update={"label": "Other"}))
                await replace_in(session, t, nesting(X, Y))
        assert refused.value.iris == (Y,)


async def test_a_shelf_reached_through_a_collected_one_is_still_guarded_against_a_racing_edge():
    """T1 collects Y naming W, then X naming Y; T2 commits W naming X first: X -> Y -> W -> X."""
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, nesting(X), nesting(Y), nesting(W))
        with pytest.raises(Conflict) as refused:
            async with session.transaction() as t:
                await replace_in(session, t, nesting(Y, W))
                await replace_in(session, t, nesting(X, Y))
                await replace(session, nesting(W, X))
        assert W in refused.value.iris
        with pytest.raises(InvalidBody, match="would make a cycle"):
            await replace(session, nesting(Y, W), nesting(X, Y))


# --- reads of a stored tree that bypassed the guard -------------------------------------------

L1, L2, L3 = (shelf_iri(n) for n in (11, 12, 13))
B1, B2 = (book_iri(n) for n in (21, 22))


def tree(iri: str, *parts: str):
    return a_shelf(iri, nests=True, has_part=list(parts) or None)


async def test_a_deep_read_of_a_stored_cycle_ends_and_lists_each_item_once(
    toy_session, collaboration
):
    for iri in (B1, B2):
        await put_book(toy_session, iri)
    await collections_put(toy_session, tree(L2, B2, L1))  # written without guards: L1 -> L2 -> L1
    await collections_put(toy_session, tree(L1, B1, L2))
    found = await as_ada(collaboration, toy_session).members(L1, deep=True)
    assert found.member_iris == sorted([B1, B2])
    assert found.hidden_count == 0, "neither shelf is counted, they are structure"


async def test_a_deep_read_of_a_shelf_naming_itself_ends(toy_session, collaboration):
    await put_book(toy_session, B1)
    await collections_put(toy_session, tree(L1, B1, L1))
    found = await as_ada(collaboration, toy_session).members(L1, deep=True)
    assert found.member_iris == [B1]


async def test_an_unreadable_sub_shelf_named_at_two_levels_is_counted_once(
    toy_session, collaboration
):
    await put_book(toy_session, B1)
    await collections_put(toy_session, tree(L2, B1))
    await collections_put(toy_session, tree(L3, L2))
    await collections_put(toy_session, tree(L1, L2, L3))
    found = await as_bob_without(collaboration, toy_session, L2).members(L1, deep=True)
    assert found.hidden_count == 1, "L2 is named by L1 and by L3, counted once"
    assert found.member_iris is None, "what L2 holds is neither listed nor counted"


async def test_an_item_unreadable_and_named_at_every_level_is_counted_once(
    toy_session, collaboration
):
    await put_book(toy_session, B1)
    await put_book(toy_session, B2)
    await collections_put(toy_session, tree(L3, B1, B2))
    await collections_put(toy_session, tree(L2, B1, L3))
    await collections_put(toy_session, tree(L1, B1, L2))
    found = await as_bob_without(collaboration, toy_session, B1).members(L1, deep=True)
    assert found.member_iris == [B2]
    assert found.hidden_count == 1


async def test_a_cascade_refuses_a_stored_shelf_naming_a_shelf_without_nests(
    toy_session, collaboration
):
    await collections_put(toy_session, a_shelf(L2))
    await collections_put(
        toy_session, a_shelf(L1, has_part=[L2])
    )  # a leaf that names a shelf: corrupt
    version = (await toy_session.get_graph(L1))[2]
    with pytest.raises(StoredDataInvalid):
        await as_ada(collaboration, toy_session).delete_cascade(L1, version)
    assert await cascade_stored(toy_session, L2)


@pytest.mark.xfail(
    strict=True,
    reason="_require_of_member_class checks the class of a nested member, not its member class: "
    "a stored nested shelf of authors is deleted by the cascade, while a deep read of the same "
    "tree is StoredDataInvalid (low: only reachable past the write guard)",
)
async def test_a_cascade_refuses_a_stored_nested_shelf_of_another_member_class(
    toy_session, collaboration
):
    """The nested shelf holds authors, the nesting one holds books (written past the guard)."""
    await collections_put(toy_session, a_shelf(L2, member_class="Author"))
    await collections_put(toy_session, tree(L1, L2))
    version = (await toy_session.get_graph(L1))[2]
    with pytest.raises(StoredDataInvalid):
        await as_ada(collaboration, toy_session).delete_cascade(L1, version)
    assert await cascade_stored(toy_session, L2), "nothing is deleted"


# --- a corrupt nesting graph in the skeleton --------------------------------------------------


async def test_a_corrupt_stored_shelf_does_not_block_a_save_nor_name_itself_in_the_refusal():
    async with raw_and_guarded() as (raw, checked):
        await save(checked, nesting(X), nesting(Z))
        corrupt = [
            t for t in toy_mapper().to_triples(nesting(Y)) if t[1] != v.predicate("member_class")
        ]
        await raw.add_graph(Y, corrupt)  # a nesting shelf without its member class
        try:
            await replace(checked, nesting(X, Z))
        except InvalidBody as refused:
            assert Y not in str(refused), "another shelf's corruption is not for this saver"


# --- the collection check reads its own root, in a fixed order (after the refactor to one value) ---


async def test_an_add_is_not_held_to_the_member_class_a_stored_holder_names_for_its_iri():
    """The held-member-class check is for a replace: an add has no stored class to drift from."""
    async with raw_and_guarded() as (raw, checked):
        await collections_put(raw, nesting(Y, X))  # Y names X, which is not stored yet (corrupt)
        await save(checked, a_shelf(X, member_class="Author"))
        assert await version_of(checked, X), "the add was accepted, not refused as a changed class"


async def test_the_member_class_of_a_shelf_nobody_holds_changes_while_another_shelf_is_held():
    """The holders are those of the saved shelf's own IRI, not of any shelf in the store."""
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, a_shelf(X), a_shelf(Y))
        await save(session, nesting(Z, Y))  # Y is held, X is not
        await replace(session, a_shelf(X, member_class="Author"))
        assert await version_of(session, X), "X was replaced: only Y is held"


async def test_a_held_member_class_is_refused_before_the_members_are_read():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, a_shelf(Y))
        await save(session, nesting(X, Y))
        with pytest.raises(InvalidBody, match="cannot change while a nesting collection holds it"):
            await replace(
                session, a_shelf(Y, member_class="Author", has_part=[B1])
            )  # B1 not stored


async def test_a_replace_keeping_one_nested_shelf_and_adding_one_that_leads_back_is_refused():
    """Only the saved shelf's own stored members are skipped: Z, stored under another, is new."""
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, nesting(Y))
        await save(session, nesting(X, Y))
        await save(session, nesting(Z, X))
        before = await version_of(session, X)
        with pytest.raises(InvalidBody, match=f"saving {X} would make a cycle: {X} → {Z} →"):
            await replace(session, nesting(X, Y, Z))
        assert await version_of(session, X) == before, "the shelf is as stored"


async def test_a_new_nested_shelf_of_another_member_class_is_refused_for_its_member_class():
    async with raw_and_guarded() as (raw, checked):
        await save(checked, nesting(X))
        await collections_put(raw, nesting(Y).model_copy(update={"member_class": "Author"}))
        with pytest.raises(InvalidBody, match=f"not stored aggregates of Book: .*{Y}"):
            await replace(checked, nesting(X, Y))

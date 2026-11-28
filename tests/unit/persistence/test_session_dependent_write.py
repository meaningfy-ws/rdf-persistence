"""A dependent part is written only while its whole exists, and never moves to another whole
(dependent-aggregates PD-3, PD-4, PD-11; G-2, A-3, A-5, A-7), on the fake store.

A result is the part, an audit its whole (``LINK``). A ``NotFound`` carries no ``iris``, so its
message must name the whole; a ``Conflict`` names its roots in ``iris``.
"""

import pytest

from rdf_persistence.core.domain.exceptions import Conflict, InvalidBody, NotFound
from tests.unit.persistence.dependent_helpers import (
    A1,
    A2,
    AUDIT,
    ELSEWHERE,
    O1,
    OF_AUDIT,
    OTHER,
    R1,
    SPECIAL,
    audit,
    is_stored,
    names,
    new_store,
    opened,
    result,
)


@pytest.fixture
async def store():
    return await new_store()


# --- the whole check: one table, a positive and a negative case per way a whole can be wrong ----
@pytest.mark.parametrize(
    ("seeded", "whole", "refused"),
    [
        pytest.param(AUDIT, A1, False, id="whole of the class passes"),
        pytest.param(SPECIAL, A1, False, id="whole of another whole class passes"),
        pytest.param(None, A1, True, id="whole absent"),
        pytest.param(OTHER, A1, True, id="whole of another class"),
        pytest.param(AUDIT, ELSEWHERE, True, id="pointer that is no aggregate of the tenant"),
    ],
)
async def test_a_part_is_added_only_while_its_whole_exists(store, seeded, whole, refused):
    async with opened(store) as session:
        if seeded is not None:
            await session.add_graph(A1, audit(A1, seeded))
        updates = len(store.sent("update"))
        if refused:
            with pytest.raises(NotFound) as error:
                await session.add_graph(R1, result(R1, whole))
            assert names(error.value, whole), "the NotFound names the whole"
            assert len(store.sent("update")) == updates, "nothing was sent"
            assert not await is_stored(session, R1), "nothing was written"
        else:
            await session.add_graph(R1, result(R1, whole))
            assert await is_stored(session, R1), "the part was written"


async def test_an_aggregate_with_no_link_is_written_without_a_pointer(store):
    async with opened(store) as session:
        await session.add_graph(O1, audit(O1, OTHER))
        assert await is_stored(session, O1), "a class that is no part needs no whole"


async def test_a_whole_removed_between_the_check_and_the_send_is_not_found(store):
    async with opened(store) as session, opened(store, "ben") as other:
        await session.add_graph(A1, audit(A1))
        _, _, version = await other.get_graph(A1)

        async def remove_whole() -> None:
            await other.remove(A1, version)

        store.before_update = remove_whole
        with pytest.raises(NotFound) as error:
            await session.add_graph(R1, result(R1, A1))
        assert names(error.value, A1), "the NotFound names the removed whole"
        assert not await is_stored(session, R1), "the part was not written"


# --- the whole in the same transaction (G-2, A-3) ----------------------------------------------
@pytest.mark.parametrize("whole_first", [True, False], ids=["whole first", "part first"])
async def test_a_whole_added_in_the_same_transaction_counts_in_either_order(store, whole_first):
    async with opened(store) as session:
        async with session.transaction() as transaction:
            if whole_first:
                await transaction.add_graph(A1, audit(A1))
            await transaction.add_graph(R1, result(R1, A1))
            if not whole_first:
                await transaction.add_graph(A1, audit(A1))
        assert await is_stored(session, A1), "the whole was written"
        assert await is_stored(session, R1), "the part was written"


@pytest.mark.parametrize("whole_first", [True, False], ids=["whole first", "part first"])
@pytest.mark.parametrize(
    ("replaced_to", "refused"),
    [(SPECIAL, False), (OTHER, True)],
    ids=["to a whole class", "outside the whole classes"],
)
async def test_a_whole_replaced_in_the_same_transaction_is_judged_by_its_new_class(
    store, whole_first, replaced_to, refused
):
    async with opened(store) as session:
        version = await session.add_graph(A1, audit(A1))
        updates = len(store.sent("update"))

        async def collect() -> None:
            async with session.transaction() as transaction:
                if whole_first:
                    await transaction.replace_graph(A1, audit(A1, replaced_to), version)
                await transaction.add_graph(R1, result(R1, A1))
                if not whole_first:
                    await transaction.replace_graph(A1, audit(A1, replaced_to), version)

        if not refused:
            await collect()
            assert await is_stored(session, R1), "the part was written"
            return
        with pytest.raises(NotFound) as error:
            await collect()
        assert names(error.value, A1), "the NotFound names the whole"
        assert len(store.sent("update")) == updates, "nothing was sent"


# --- the pointer itself (A-7) ------------------------------------------------------------------
@pytest.mark.parametrize(
    "wholes",
    [(), (A1, A2), (R1,)],
    ids=["no value", "two values", "its own IRI"],
)
async def test_a_part_with_no_or_two_pointers_or_its_own_iri_is_an_invalid_body(store, wholes):
    async with opened(store) as session:
        await session.add_graph(A1, audit(A1))
        await session.add_graph(A2, audit(A2))
        updates = len(store.sent("update"))
        with pytest.raises(InvalidBody):
            await session.add_graph(R1, result(R1, *wholes))
        assert len(store.sent("update")) == updates, "nothing was sent"


# --- the pointer never changes (PD-4) ----------------------------------------------------------
@pytest.mark.parametrize(
    ("whole", "refused"),
    [pytest.param(A1, False, id="same pointer"), pytest.param(A2, True, id="another audit")],
)
async def test_a_part_keeps_its_pointer_when_replaced(store, whole, refused):
    async with opened(store) as session:
        await session.add_graph(A1, audit(A1))
        await session.add_graph(A2, audit(A2))
        version = await session.add_graph(R1, result(R1, A1))
        updates = len(store.sent("update"))
        if not refused:
            await session.replace_graph(R1, result(R1, whole), version)
            return
        with pytest.raises(Conflict) as error:
            await session.replace_graph(R1, result(R1, whole), version)
        assert str(OF_AUDIT) in str(error.value), "the Conflict names the slot"
        assert error.value.iris == (R1,), "the Conflict names the part"
        assert len(store.sent("update")) == updates, "nothing was sent"

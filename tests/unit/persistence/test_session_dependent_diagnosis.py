"""The diagnosis of a refused commit names a gone whole or a late part, before anything else
(dependent-aggregates PD-3, PD-7, PD-11; A-5): gone whole, then late part, then the versions, then
the store's other causes. Each test asserts the exception type and what it names.
"""

import pytest

from rdf_persistence.core.domain.exceptions import Conflict, NotFound
from tests.unit.persistence.dependent_helpers import (
    A1,
    A2,
    O1,
    OTHER,
    R1,
    R2,
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


async def test_a_gone_whole_is_named_before_a_stale_replace(store):
    async with opened(store) as session, opened(store, "ben") as other:
        await session.add_graph(A1, audit(A1))
        old = await session.add_graph(O1, audit(O1, OTHER))
        _, _, a1_version = await other.get_graph(A1)

        async def overtake() -> None:
            await other.remove(A1, a1_version)
            await other.replace_graph(O1, audit(O1, OTHER), old)

        with pytest.raises(NotFound) as error:
            async with session.transaction() as transaction:
                await transaction.replace_graph(O1, audit(O1, OTHER), old)
                await transaction.add_graph(R1, result(R1, A1))
                store.before_update = overtake
        assert names(error.value, A1), "the NotFound names the whole, not the stale replace"
        assert not await is_stored(session, R1), "the part was not written"


async def test_a_whole_that_changed_class_is_not_found(store):
    async with opened(store) as session, opened(store, "ben") as other:
        await session.add_graph(A1, audit(A1))
        _, _, a1_version = await other.get_graph(A1)

        async def change_class() -> None:
            await other.replace_graph(A1, audit(A1, OTHER), a1_version)

        store.before_update = change_class
        with pytest.raises(NotFound) as error:
            await session.add_graph(R1, result(R1, A1))
        assert names(error.value, A1), "the NotFound names the whole of the wrong class"


async def test_a_part_added_after_the_delete_was_collected_is_a_conflict_naming_the_whole(store):
    async with opened(store) as session, opened(store, "ben") as other:
        version = await session.add_graph(A1, audit(A1))

        async def add_part() -> None:  # after the cascade read the parts of A1
            await other.add_graph(R2, result(R2, A1))

        store.before_update = add_part
        with pytest.raises(Conflict) as error:
            async with session.transaction() as transaction:
                await transaction.remove(A1, version)
        assert error.value.iris == (A1,), "the Conflict names the removed root"
        assert "lost a race" not in str(error.value), "it is no generic lost race"
        assert await is_stored(session, A1), "nothing was removed"


async def test_a_removal_with_no_part_written_since_goes_through(store):
    async with opened(store) as session:
        version = await session.add_graph(A1, audit(A1))
        await session.remove(A1, version)
        assert not await is_stored(session, A1), "the whole was removed"


async def test_a_gone_whole_is_named_before_a_late_part(store):
    async with opened(store) as session, opened(store, "ben") as other:
        await session.add_graph(A1, audit(A1))
        a2_version = await session.add_graph(A2, audit(A2))
        _, _, a1_version = await other.get_graph(A1)

        async def remove_whole_and_add_part() -> None:  # after the cascade read the parts of A2
            await other.remove(A1, a1_version)
            await other.add_graph(R2, result(R2, A2))

        with pytest.raises(NotFound) as error:
            async with session.transaction() as transaction:
                await transaction.add_graph(R1, result(R1, A1))
                await transaction.remove(A2, a2_version)
                store.before_update = remove_whole_and_add_part
        assert names(error.value, A1), "the gone whole comes first"


async def test_a_late_part_is_named_before_a_stale_replace(store):
    async with opened(store) as session, opened(store, "ben") as other:
        a1_version = await session.add_graph(A1, audit(A1))
        old = await session.add_graph(O1, audit(O1, OTHER))
        await other.replace_graph(O1, audit(O1, OTHER), old)

        async def add_part() -> None:  # after the cascade read the parts of A1
            await other.add_graph(R2, result(R2, A1))

        store.before_update = add_part
        with pytest.raises(Conflict) as error:
            async with session.transaction() as transaction:
                await transaction.replace_graph(O1, audit(O1, OTHER), old)
                await transaction.remove(A1, a1_version)
        assert error.value.iris == (A1,), "the late part comes before the stale replace"

"""FakeStore: the shared conformance suite, and the fake's own failure injection."""

import pytest

from rdf_persistence.domain.errors import StoreUnavailable
from rdf_persistence.testkit import FakeStore, no_network  # noqa: F401  (fixture)
from rdf_persistence.testkit.store_conformance import CASES, run_case


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__)
async def test_the_fake_store_conforms(case, no_network):  # noqa: F811
    await run_case(case, FakeStore())


async def test_an_injected_error_is_raised_once_then_the_call_works():
    store = FakeStore()
    store.on("create_dataset", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await store.create_dataset("d")
    await store.create_dataset("d")
    assert await store.list_datasets() == ["d"]


async def test_an_injected_error_can_repeat_and_is_per_operation():
    store = FakeStore()
    store.on("list_datasets", StoreUnavailable("down"), times=2)
    for _ in range(2):
        with pytest.raises(StoreUnavailable):
            await store.list_datasets()
    assert await store.list_datasets() == [], "third call works"
    await store.create_dataset("d")  # another operation was never affected


async def test_sent_records_each_call_payload_including_failed_ones():
    store = FakeStore()
    await store.create_dataset("d")
    store.on("update", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await store.update("d", "CLEAR ALL")
    await store.update("d", "CLEAR DEFAULT")
    assert store.sent("update") == ["CLEAR ALL", "CLEAR DEFAULT"]
    assert store.sent("query") == []

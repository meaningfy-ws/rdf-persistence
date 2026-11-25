"""FakeStore: the shared conformance suite, and the fake's own failure injection."""

import asyncio
import inspect

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD

from rdf_persistence.core.domain.exceptions import StoreUnavailable
from rdf_persistence.testkit import FakeStore, no_network  # noqa: F401  (fixture)
from rdf_persistence.testkit.store_conformance import CASES, run_case


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__)
async def test_the_fake_store_conforms(case, no_network):  # noqa: F811
    await run_case(case, FakeStore())


@pytest.mark.parametrize("entry", ["update", "put_graph", "import_quads"])
async def test_an_xsd_string_literal_enters_as_the_plain_literal(entry):
    store = FakeStore()
    await store.create_dataset("d")
    typed = Literal("1", datatype=XSD.string)
    triple = (URIRef("urn:s"), URIRef("urn:p"), typed)
    if entry == "update":
        await store.update(
            "d", f'INSERT DATA {{ GRAPH <urn:g> {{ <urn:s> <urn:p> "1"^^<{XSD.string}> }} }}'
        )
    elif entry == "put_graph":
        await store.put_graph("d", URIRef("urn:g"), Graph().add(triple))
    else:
        await store.import_quads("d", f'<urn:s> <urn:p> "1"^^<{XSD.string}> <urn:g> .\n'.encode())
    plain = await store.query("d", 'ASK { GRAPH <urn:g> { <urn:s> <urn:p> "1" } }')
    assert plain.askAnswer, "the plain literal matches"
    stored = await store.query("d", "SELECT ?o WHERE { GRAPH <urn:g> { <urn:s> <urn:p> ?o } }")
    assert [r.o.datatype for r in stored] == [None], "one term, the plain one"


async def test_an_injected_error_is_raised_once_then_the_call_works():
    store = FakeStore()
    store.on("create_dataset", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await store.create_dataset("d")
    await store.create_dataset("d")
    assert await store.list_datasets() == ["d"], "after the one injected error the call works"


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
    assert store.sent("update") == ["CLEAR ALL", "CLEAR DEFAULT"], (
        "every update is recorded, including the failed one"
    )
    assert store.sent("query") == [], "no query was recorded"


async def test_an_injected_error_can_wait_for_later_calls():
    store = FakeStore()
    store.on("create_dataset", StoreUnavailable("down"), after=1)
    await store.create_dataset("first")
    with pytest.raises(StoreUnavailable):
        await store.create_dataset("second")
    assert await store.list_datasets() == ["first"], "an injected error can wait for later calls"


@pytest.mark.parametrize("call", ["on", "sent"])
def test_a_misspelt_operation_is_refused_not_silently_ignored(call):
    store = FakeStore()
    args = (StoreUnavailable("down"),) if call == "on" else ()
    with pytest.raises(ValueError, match="create_datasets"):
        getattr(store, call)("create_datasets", *args)


def test_the_known_operations_are_exactly_the_async_methods_of_the_fake():
    methods = {
        name
        for name in dir(FakeStore)
        if not name.startswith("_") and inspect.iscoroutinefunction(getattr(FakeStore, name))
    }
    assert methods == FakeStore.OPERATIONS, "an operation was added or removed without the list"


# -- hold: the first ``until`` calls of an operation wait for each other (E3 to E8, E4b) -----------


def _insert(name: str) -> str:
    return f"INSERT DATA {{ GRAPH <urn:g> {{ <urn:{name}> <urn:p> 1 }} }}"


async def _store() -> FakeStore:
    store = FakeStore()
    await store.create_dataset("d")
    return store


async def _settle() -> None:
    """Let every task that can run, run: a few turns of the loop, no clock."""
    for _ in range(5):
        await asyncio.sleep(0)


async def test_e3_a_held_call_waits_for_the_until_th_and_both_apply_in_arrival_order():
    store = await _store()
    async with store.hold("update", until=2):
        first = asyncio.create_task(store.update("d", _insert("a")))
        await _settle()
        assert store.sent("update") == [], (
            "the first call has not applied before the second arrives"
        )
        assert not first.done(), "the first call is waiting"
        second = asyncio.create_task(store.update("d", _insert("b")))
        await asyncio.gather(first, second)
    assert store.sent("update") == [_insert("a"), _insert("b")], (
        "both applied, the until-th call last"
    )


async def test_e4_a_hold_that_never_fills_releases_its_waiter_and_fails_on_exit():
    store = await _store()
    with pytest.raises(AssertionError, match=r"hold\('update', until=2\) saw 1 call\(s\)"):
        async with store.hold("update", until=2, timeout=0.1):
            await store.update("d", _insert("a"))
            assert store.sent("update") == [_insert("a")], (
                "the lone call completed after the timeout"
            )


@pytest.mark.parametrize("leave", ["raises", "cancelled"])
async def test_e4b_a_hold_left_by_an_exception_releases_its_waiter_and_keeps_the_exception(leave):
    store = await _store()
    waiting: list[asyncio.Task] = []

    async def body() -> None:
        async with store.hold("update", until=2):
            waiting.append(asyncio.create_task(store.update("d", _insert("a"))))
            await _settle()
            assert not waiting[0].done(), "the call is waiting inside the block"
            if leave == "raises":
                raise KeyError("boom")
            await asyncio.Event().wait()

    outer = asyncio.create_task(body())
    if leave == "cancelled":
        await _settle()
        outer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await outer
    else:
        with pytest.raises(KeyError):
            await outer
    await asyncio.wait_for(waiting[0], 1)
    assert store.sent("update") == [_insert("a")], "the waiting call was released and completed"


@pytest.mark.parametrize(
    ("operation", "until"), [("updte", 2), ("update", 0), ("update", -1)], ids=str
)
async def test_e5_a_mistaken_hold_raises_before_any_call_waits(operation, until):
    store = await _store()
    with pytest.raises(ValueError):
        async with store.hold(operation, until=until):
            pytest.fail("the block must not be entered")
    await store.update("d", _insert("a"))
    assert store.sent("update") == [_insert("a")], "a call does not wait after the refused hold"


async def test_e6_a_second_hold_on_the_same_operation_is_refused_and_the_first_stays_usable():
    store = await _store()
    async with store.hold("update", until=1):
        with pytest.raises(RuntimeError):
            async with store.hold("update", until=1):
                pytest.fail("the block must not be entered")
        async with store.hold("query", until=1):
            await store.query("d", "ASK {}")  # another operation may be held at once
        await store.update("d", _insert("a"))
    async with store.hold("update", until=1):  # the operation is free again after the exit
        await store.update("d", _insert("b"))


async def test_e7_calls_after_the_until_th_do_not_wait():
    store = await _store()
    async with store.hold("update", until=2):
        tasks = [asyncio.create_task(store.update("d", _insert(n))) for n in "ab"]
        await asyncio.wait_for(asyncio.gather(*tasks), 1)
        await asyncio.wait_for(store.update("d", _insert("c")), 1)  # would hang if it waited
    assert store.sent("update") == [_insert(n) for n in "abc"], "the third call was not held"


async def test_e8_an_armed_fault_goes_to_the_first_call_released():
    store = await _store()
    store.on("update", StoreUnavailable("down"))
    async with store.hold("update", until=2):
        first = asyncio.create_task(store.update("d", _insert("a")))
        await _settle()
        second = asyncio.create_task(store.update("d", _insert("b")))
        results = await asyncio.gather(first, second, return_exceptions=True)
    assert isinstance(results[0], StoreUnavailable), "the first released call takes the fault"
    assert results[1] is None, "the second call works"
    assert store.sent("update") == [_insert("a"), _insert("b")], "payloads in release order"

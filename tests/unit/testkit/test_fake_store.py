"""FakeStore: the shared conformance suite, and the fake's own failure injection."""

import inspect

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD

from rdf_persistence.domain.exceptions import StoreUnavailable
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


async def test_an_injected_error_can_wait_for_later_calls():
    store = FakeStore()
    store.on("create_dataset", StoreUnavailable("down"), after=1)
    await store.create_dataset("first")
    with pytest.raises(StoreUnavailable):
        await store.create_dataset("second")
    assert await store.list_datasets() == ["first"]


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

"""The session's version guards over the FakeStore: a stale or missing aggregate changes nothing."""

import pytest
from rdflib import Literal, URIRef

from rdf_persistence.domain.exceptions import Conflict, NotFound
from rdf_persistence.testkit import FakeStore, fake_session
from tests.toy import TENANT, book_iri

TITLE = URIRef("http://purl.org/dc/terms/title")


def title(iri: str, text: str) -> list:
    return [(URIRef(iri), TITLE, Literal(text))]


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


async def test_a_stale_remove_is_a_conflict_and_keeps_the_aggregate(store):
    iri = book_iri(1)
    async with fake_session(store, tenant_iri=TENANT) as session:
        await session.add_graph(iri, title(iri, "Dune"))
        with pytest.raises(Conflict):
            await session.remove(iri, "a-stale-version")
        stored, _, _ = await session.get_graph(iri)
    assert (URIRef(iri), TITLE, Literal("Dune")) in stored, "the aggregate is still there"


async def test_a_stale_replace_keeps_the_stored_triples(store):
    iri = book_iri(2)
    async with fake_session(store, tenant_iri=TENANT) as session:
        await session.add_graph(iri, title(iri, "Dune"))
        with pytest.raises(Conflict):
            await session.replace_graph(iri, title(iri, "Changed"), "a-stale-version")
        stored, _, _ = await session.get_graph(iri)
    assert (URIRef(iri), TITLE, Literal("Dune")) in stored
    assert (URIRef(iri), TITLE, Literal("Changed")) not in stored


@pytest.mark.parametrize("call", ["replace_graph", "remove"])
async def test_replacing_or_removing_a_missing_aggregate_is_not_found_and_writes_nothing(
    store, call
):
    iri = book_iri(3)
    async with fake_session(store, tenant_iri=TENANT) as session:
        arguments = (iri, [], "v") if call == "replace_graph" else (iri, "v")
        with pytest.raises(NotFound):
            await getattr(session, call)(*arguments)
    assert store.sent("update") == [], "no update was sent"

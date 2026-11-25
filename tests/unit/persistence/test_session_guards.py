"""The session's version guards over the FakeStore: a stale or missing aggregate changes nothing."""

import pytest
from rdflib import RDF, Literal, URIRef

from rdf_persistence.core.domain.exceptions import Conflict, NotFound
from rdf_persistence.persistence.services.generated.rp_persistence_services import Condition
from rdf_persistence.testkit import FakeStore, fake_session
from tests.toy import TENANT, TITLE, book_iri


def title(iri: str, text: str) -> list:
    return [(URIRef(iri), TITLE, Literal(text))]


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.mark.parametrize(("text", "expected"), [("UN", True), ("zz", False)])
async def test_matches_reads_a_contains_condition_as_a_substring_in_any_case(store, text, expected):
    iri = book_iri(1)
    kind = URIRef("http://purl.org/ontology/bibo/Book")
    async with fake_session(store, tenant_iri=TENANT) as session:
        await session.add_graph(iri, [*title(iri, "Dune"), (URIRef(iri), RDF.type, kind)])
        condition = Condition(predicate=str(TITLE), value=text, contains=True)
        assert await session.matches(iri, str(kind), [condition]) is expected, (
            "a contains condition is a substring in any case, not an equality"
        )


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
    assert (URIRef(iri), TITLE, Literal("Dune")) in stored, (
        "the stale replace keeps the stored title"
    )
    assert (URIRef(iri), TITLE, Literal("Changed")) not in stored, (
        "the stale replace does not store the changed title"
    )


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

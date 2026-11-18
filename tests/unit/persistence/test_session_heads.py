"""Session.heads: the IRI, types and version of stored aggregates, in one query (PD-6, TC-32)."""

from rdf_persistence.testkit import FakeStore, fake_session
from tests.toy import TENANT, book_iri, dune, toy_mapper

BOOK_TYPE = "http://purl.org/ontology/bibo/Book"


async def test_heads_answers_the_stored_aggregates_and_none_for_the_others():  # TC-32
    async with fake_session(tenant_iri=TENANT) as session:
        version = await session.add_graph(book_iri(1), toy_mapper().to_triples(dune(book_iri(1))))
        heads = await session.heads([book_iri(1), book_iri(9)])
    assert [(h.head_iri, h.head_types, h.head_version) for h in heads] == [
        (book_iri(1), [BOOK_TYPE], version)
    ], "one head for the stored book, none for the IRI nothing is stored at"


async def test_heads_of_no_iri_sends_no_query():
    store = FakeStore()
    async with fake_session(store, tenant_iri=TENANT) as session:
        before = len(store.sent("query"))
        assert await session.heads([]) == [], "no IRI, no head"
        assert len(store.sent("query")) == before, "and no query sent"

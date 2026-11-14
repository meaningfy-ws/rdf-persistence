"""Session.graphs_with: the graph of each registered aggregate whose root has a statement (PD-28 item 5)."""

from rdflib import RDF, Literal, URIRef

from rdf_persistence.services import vocabulary as v
from tests.fixtures.library.generated.books import Genre
from tests.toy import book_iri, dune, shelf, shelf_iri, toy_mapper
from tests.unit.services.test_collaboration_collections import poetry

LIB = "https://example.org/ns/library#"
SHELF_CLASS = URIRef(f"{LIB}Shelf")
BOOK_CLASS = URIRef("http://purl.org/ontology/bibo/Book")
B1, S1, S2 = book_iri(1), shelf_iri(1), shelf_iri(2)


async def put(session, model) -> None:
    await session.add_graph(model.id, toy_mapper().to_triples(model))


async def test_each_aggregate_with_the_predicate_comes_back_as_its_own_graph(toy_session):
    await put(toy_session, shelf(S1).model_copy(update={"membership_rule": poetry()}))
    await put(
        toy_session, shelf(S2).model_copy(update={"membership_rule": poetry("genre", "fiction")})
    )
    await put(toy_session, dune(B1, chapters=1).model_copy(update={"genre": Genre.POETRY.value}))
    found = await toy_session.graphs_with(v.MEMBERSHIP_RULE)
    assert sorted(found) == [S1, S2], "the two shelves; the book has no rule"
    assert Literal("fiction") in set(found[S2].objects()), "s2's own triples"
    assert Literal("fiction") not in set(found[S1].objects()), "and none of s2's in s1's graph"


async def test_an_object_narrows_the_aggregates(toy_session):
    await put(toy_session, shelf(S1))
    await put(toy_session, dune(B1, chapters=1))
    shelves = await toy_session.graphs_with(RDF.type, SHELF_CLASS)
    books = await toy_session.graphs_with(RDF.type, BOOK_CLASS)
    assert sorted(shelves) == [S1], "only the aggregate typed as a shelf"
    assert sorted(books) == [B1], "only the aggregate typed as a book"


async def test_triples_about_another_subject_stay_in_the_graph_that_holds_them(toy_session):
    stray = toy_mapper().to_triples(shelf(S2))
    await toy_session.add_graph(S1, [*toy_mapper().to_triples(shelf(S1)), *stray])
    found = await toy_session.graphs_with(RDF.type, SHELF_CLASS)
    assert sorted(found) == [S1], "s2 is no root: it has no graph of its own"
    assert (URIRef(S2), RDF.type, SHELF_CLASS) in found[S1], "its triples stay in s1's graph"

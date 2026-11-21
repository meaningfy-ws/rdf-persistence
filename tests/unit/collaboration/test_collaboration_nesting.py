"""Nested collections: a shelf that nests other shelves (PD-1 to PD-3)."""

from rdf_persistence.iris.domain.layout import graph_iri
from tests.fixtures.library.domain.generated.books import Shelf
from tests.toy import shelf, shelf_iri, toy_mapper

S1 = shelf_iri(1)


def round_trip(model: Shelf) -> Shelf:
    mapper = toy_mapper()
    return mapper.from_graph(Shelf, model.id, mapper.to_graph(model), graph_iri(model.id))


def test_a_shelf_without_nests_does_not_nest():
    restored = round_trip(shelf(S1))
    assert restored.nests is None, "absent stays absent after the round trip"
    assert not restored.nests, "and absent means false: the shelf does not nest"

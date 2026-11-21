"""Nested collections: a shelf that nests other shelves (PD-1 to PD-3)."""

import pytest

from rdf_persistence import InvalidBody
from rdf_persistence.iris.domain.layout import graph_iri
from rdf_persistence.testkit import fake_session
from tests.fixtures.library.domain.generated.books import Shelf
from tests.toy import TENANT, book_iri, dune, shelf, shelf_iri, toy_mapper
from tests.unit.collaboration.collaboration_data import guards, save

S1 = shelf_iri(1)


def round_trip(model: Shelf) -> Shelf:
    mapper = toy_mapper()
    return mapper.from_graph(Shelf, model.id, mapper.to_graph(model), graph_iri(model.id))


def test_a_shelf_without_nests_does_not_nest():
    restored = round_trip(shelf(S1))
    assert restored.nests is None, "absent stays absent after the round trip"
    assert not restored.nests, "and absent means false: the shelf does not nest"


S2 = shelf_iri(2)
NESTS_NEEDS = "nests needs a member class that is not a collection"

# (the stored child shelf, the saved parent shelf, the refusal text or None when accepted).
# The toy has no subclass of a collection class, so "a subclass" is not a row here.
NESTING = [
    pytest.param({}, {"nests": True, "has_part": [S2]}, None, id="a-nested-leaf-is-accepted"),
    pytest.param(
        {"nests": True},
        {"nests": True, "has_part": [S2]},
        None,
        id="a-nested-nesting-shelf-is-accepted",
    ),
    pytest.param(
        {"member_class": "Author"},
        {"nests": True, "has_part": [S2]},
        f"not stored aggregates of Book: .*{S2}",
        id="a-nested-shelf-of-another-member-class-is-refused",
    ),
    pytest.param(
        {},
        {"has_part": [S2]},
        f"not stored aggregates of Book: .*{S2}",
        id="a-shelf-without-nests-naming-a-shelf-is-refused",
    ),
    pytest.param(
        {},
        {"nests": True, "member_class": "Shelf"},
        NESTS_NEEDS,
        id="nests-over-a-collection-class",
    ),
    pytest.param({}, {"has_part": [book_iri(1)]}, None, id="a-flat-shelf-of-books-is-unchanged"),
]


@pytest.mark.parametrize(("child", "parent", "refusal"), NESTING)
async def test_a_collection_nests_only_collections_of_its_own_class_and_member_class(
    child, parent, refusal
):
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, dune(book_iri(1)), shelf(S2).model_copy(update=child))
        saving = save(session, shelf(S1).model_copy(update=parent))
        if refusal is None:
            await saving
            return
        with pytest.raises(InvalidBody, match=refusal):
            await saving

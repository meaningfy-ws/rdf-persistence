"""``located``: where a referrer is served, as ``(rp_path, id)`` (D-6; E10, E11, E13)."""

import pytest

from rdf_persistence.collaboration.services.collaboration import Collaboration
from rdf_persistence.collaboration.services.referrer_naming import located
from rdf_persistence.iris.services.iris import DEFAULT_IRIS
from rdf_persistence.schema.services.schema import load_schema
from tests.toy import TOY_SCHEMA, book_iri, shelf_iri

VIEW = load_schema(TOY_SCHEMA)
BOOK = book_iri(1)
BOOK_ID = BOOK.rsplit("/", 1)[1]
FOREIGN = "https://elsewhere.org/books/1"

CASES = [
    pytest.param("Book", BOOK, ("books", BOOK_ID), id="a-served-class-and-an-aggregate-iri"),
    pytest.param("Shelf", shelf_iri(2), ("shelves", shelf_iri(2).rsplit("/", 1)[1]), id="another"),
    pytest.param("AggregateRoot", BOOK, None, id="E10-a-mixin"),
    pytest.param("Chapter", BOOK, None, id="E10-a-class-without-a-path"),
    pytest.param("LendingItem", BOOK, None, id="E10-an-abstract-root-without-a-path"),
    pytest.param(FOREIGN, BOOK, None, id="E10-a-class-the-schema-does-not-know"),
    pytest.param("Book", FOREIGN, None, id="E11-an-iri-that-is-not-an-aggregate-iri"),
]


@pytest.mark.parametrize(("class_name", "iri", "expected"), CASES)
def test_located_is_the_path_and_id_of_a_served_aggregate_or_none(class_name, iri, expected):
    assert located(VIEW, DEFAULT_IRIS, class_name, iri) == expected, f"{class_name} at {iri}"


def test_a_root_of_two_classes_locates_only_the_served_one():  # E13
    rows = {(BOOK, "Book", "shelf"), (BOOK, "AggregateRoot", "shelf")}

    listed = Collaboration._listed(
        rows, None, None, {BOOK}, lambda c, i: located(VIEW, DEFAULT_IRIS, c, i)
    )

    by_class = {r.referrer_class: (r.referrer_rp_path, r.referrer_id) for r in listed.referrers}
    assert by_class == {"Book": ("books", BOOK_ID), "AggregateRoot": (None, None)}, (
        "one row per class; the pair is on the served class's row alone"
    )


def test_a_row_of_an_unlocated_class_keeps_its_three_names():  # E10
    listed = Collaboration._listed(
        {(BOOK, "AggregateRoot", "shelf")}, None, None, {BOOK}, lambda c, i: None
    )

    (row,) = listed.referrers
    assert (row.referrer, row.referrer_class, row.referrer_slot) == (BOOK, "AggregateRoot", "shelf")
    assert (row.referrer_rp_path, row.referrer_id) == (None, None), "neither field is set"

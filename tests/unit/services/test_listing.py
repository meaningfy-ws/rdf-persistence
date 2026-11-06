"""What a listing asks for and how it is read: the query string, the slots it may name, the typed values (PD-15)."""

import pytest
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import XSD, Literal, URIRef

from rdf_persistence.domain.exceptions import BadQuery
from rdf_persistence.domain.generated.service.rp_service import Filter, ListRequest
from rdf_persistence.services.listing import (
    Listings,
    list_request,
    listable_slots,
    sort_keys,
    typed_value,
)
from rdf_persistence.services.schema import load_schema
from tests.toy import TOY_SCHEMA, dune, toy_mapper

SCHEMA_ORG = "http://schema.org/"


@pytest.fixture(scope="module")
def view() -> SchemaView:
    return load_schema(TOY_SCHEMA)


@pytest.fixture(scope="module")
def listings(view) -> Listings:
    return Listings(view)


def test_no_parameters_ask_for_the_first_fifty_by_iri():
    assert list_request([]) == ListRequest(limit=50, offset=0, sort=None, filters=None)


def test_limit_offset_sort_and_filters_are_read_from_the_query_string():
    request = list_request(
        [("limit", "2"), ("offset", "4"), ("sort", "-label"), ("genre", "fiction"), ("isbn", "1")]
    )
    assert (request.limit, request.offset, request.sort) == (2, 4, "-label"), "the page and the key"
    assert request.filters == [
        Filter(slot="genre", value="fiction"),
        Filter(slot="isbn", value="1"),
    ], "everything else is a filter, in the order sent"


@pytest.mark.parametrize(
    "params",
    [
        [("limit", "0")],
        [("limit", "201")],
        [("limit", "-1")],
        [("limit", "abc")],
        [("limit", "1.5")],
        [("limit", "1_0")],
        [("limit", "")],
        [("limit", "2"), ("limit", "3")],
        [("offset", "-1")],
        [("offset", "x")],
        [("offset", "")],
        [("offset", "1"), ("offset", "2")],
        [("sort", "label"), ("sort", "isbn")],
    ],
    ids=lambda p: "&".join(f"{k}={v}" for k, v in p),
)
def test_a_limit_offset_or_sort_that_is_not_one_valid_value_is_a_bad_query(params):
    with pytest.raises(BadQuery):
        list_request(params)


@pytest.mark.parametrize("params", [[("limit", "1")], [("limit", "200")], [("offset", "0")]])
def test_the_bounds_of_limit_and_offset_are_allowed(params):
    list_request(params)


def test_the_slots_a_listing_may_name_are_those_of_the_type_that_are_not_bookkeeping_or_owned(view):
    names = set(listable_slots(view, view.get_class("Book")))
    assert {"label", "description", "isbn", "authors", "published", "genre"} <= names
    assert not names & {"id", "chapters", "creator", "contributor", "created", "modified"}, (
        "the identifier, the owned parts and the bookkeeping cannot be filtered on"
    )


@pytest.mark.parametrize(
    ("slot", "text", "expected"),
    [
        ("isbn", "978-0", Literal("978-0")),
        ("isbn", '"} ; DROP ALL ; #', Literal('"} ; DROP ALL ; #')),
        ("published", "2020-01-31", Literal("2020-01-31", datatype=XSD.date)),
        ("number", "12", Literal(12)),
        ("genre", "fiction", URIRef(f"{SCHEMA_ORG}Fiction")),
        ("scan_of", "https://example.org/a/b", URIRef("https://example.org/a/b")),
    ],
)
def test_a_value_is_typed_by_the_range_of_its_slot(view, slot, text, expected):
    assert typed_value(view, view.get_slot(slot), text) == expected


@pytest.mark.parametrize(
    ("slot", "text"),
    [
        ("published", "yesterday"),
        ("published", "2020-13-01"),
        ("number", "twelve"),
        ("number", "1.5"),
        ("genre", "horror"),
        ("genre", "Fiction"),
        ("genre", f"{SCHEMA_ORG}Fiction"),
        ("scan_of", "not an iri"),
        ("scan_of", "relative/path"),
        *[("scan_of", f"urn:x:a{char}b") for char in '<>"{}|^\\`'],
    ],
)
def test_a_value_the_range_cannot_hold_is_a_bad_query(view, slot, text):
    with pytest.raises(BadQuery):
        typed_value(view, view.get_slot(slot), text)


def plan_of(listings, view, *params, hidden=()):
    return listings.plan(view.get_class("Book"), list_request(list(params)), hidden)


def test_the_plan_of_a_listing_carries_the_typed_filters_the_sort_and_the_page(listings, view):
    plan = plan_of(listings, view, ("genre", "poetry"), ("sort", "-published"), ("limit", "3"))
    assert [(c.predicate, c.value, c.reference) for c in plan.conditions or []] == [
        (f"{SCHEMA_ORG}genre", f"{SCHEMA_ORG}Poetry", True)
    ]
    assert plan.sort_by == "http://purl.org/dc/terms/issued", "the predicate of the slot"
    assert plan.descending, "a minus sign sorts downwards"
    assert (plan.limit, plan.offset) == (3, 0)


def test_without_a_sort_key_the_listing_is_by_iri_ascending(listings, view):
    plan = plan_of(listings, view)
    assert (plan.sort_by, plan.descending) == (None, False)


def test_the_identifier_sorts_by_iri_in_the_direction_asked(listings, view):
    plan = plan_of(listings, view, ("sort", "-id"))
    assert (plan.sort_by, plan.descending) == (None, True)


@pytest.mark.parametrize(
    "params",
    [
        [("colour", "red")],
        [("creator", "https://example.org/people/ada")],
        [("chapters", "x")],
        [("id", "https://example.org/x")],
        [("genre", "horror")],
        [("sort", "colour")],
        [("sort", "-creator")],
        [("sort", "chapters")],
        [("sort", "")],
        [("sort", "-")],
        [("sort", "--label")],
        [("authors", "a"), ("shade", "x")],
    ],
    ids=lambda p: "&".join(f"{k}={v}" for k, v in p),
)
def test_a_slot_the_type_does_not_offer_is_a_bad_query(listings, view, params):
    with pytest.raises(BadQuery):
        plan_of(listings, view, *params)


def test_a_slot_name_is_matched_exactly_not_as_a_pattern(listings, view):
    for name in ("Label", "label ", "la.el", "label}"):
        with pytest.raises(BadQuery):
            plan_of(listings, view, (name, "x"))


def test_a_literal_filter_keeps_its_datatype_in_the_plan(listings, view):
    plan = plan_of(listings, view, ("published", "2020-01-31"), ("isbn", "978"))
    assert [(c.value, c.datatype, c.reference) for c in plan.conditions or []] == [
        ("2020-01-31", str(XSD.date), False),
        ("978", None, False),
    ]


def test_the_graphs_hidden_from_the_caller_are_in_the_plan(listings, view):
    plan = plan_of(listings, view, hidden=["https://example.org/g"])
    assert plan.hidden_graphs == ["https://example.org/g"]


def test_the_mapper_and_the_listing_hold_a_value_as_the_same_term(view):
    """One rule makes the term of a value: what the mapper writes, a filter on it matches."""
    mapped = toy_mapper().to_graph(dune("https://example.org/library/books/1"))
    stored = {o for _, _, o in mapped}
    book = view.get_class("Book")
    slots = listable_slots(view, book)
    for name, text in [("genre", "fiction"), ("authors", "Herbert")]:
        assert typed_value(view, slots[name], text) in stored, f"a filter on {name} matches"


def test_the_sort_keys_are_the_identifier_and_the_listable_slots_up_and_down(view):
    keys = sort_keys(view, view.get_class("Book"))
    assert keys[0] == "id" and "-id" in keys, "the identifier orders by IRI"
    assert {"label", "published", "-label", "-published"} <= set(keys)
    assert not {"chapters", "-chapters", "created"} & set(keys), "no owned part, no bookkeeping"
    assert (
        len(keys) == len(set(keys)) == 2 * (len(listable_slots(view, view.get_class("Book"))) + 1)
    )

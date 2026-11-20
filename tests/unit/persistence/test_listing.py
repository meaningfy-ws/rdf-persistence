"""What a listing asks for and how it is read: the query string, the slots it may name, the typed values (PD-15)."""

import pytest
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import XSD, Literal, URIRef

from rdf_persistence.core.domain.exceptions import BadQuery
from rdf_persistence.persistence.services.generated.rp_persistence_services import (
    Filter,
    ListRequest,
)
from rdf_persistence.persistence.services.listing import (
    Listings,
    list_request,
    listable_slots,
    sort_keys,
    typed_value,
)
from rdf_persistence.schema.services.schema import load_schema
from tests.toy import TOY_SCHEMA, dune, toy_mapper

SCHEMA_ORG = "http://schema.org/"


@pytest.fixture(scope="module")
def view() -> SchemaView:
    return load_schema(TOY_SCHEMA)


@pytest.fixture(scope="module")
def listings(view) -> Listings:
    return Listings(view)


def test_no_parameters_ask_for_the_first_fifty_by_iri():
    assert list_request([]) == ListRequest(limit=50, offset=0, sort=None, filters=None), (
        "no parameters ask for the first fifty by IRI"
    )


def test_limit_offset_sort_and_filters_are_read_from_the_query_string():
    request = list_request(
        [("limit", "2"), ("offset", "4"), ("sort", "-label"), ("genre", "fiction"), ("isbn", "1")]
    )
    assert (request.limit, request.offset, request.sort) == (2, 4, "-label"), "the page and the key"
    assert request.filters == [
        Filter(slot="genre", value="fiction"),
        Filter(slot="isbn", value="1"),
    ], "everything else is a filter, in the order sent"


# TC-01: a name ending in "~" is a contains filter on the name without that last "~"
@pytest.mark.parametrize(
    ("param", "expected"),
    [
        (("label~", "dune"), Filter(slot="label", value="dune", contains=True)),
        (("label", "dune"), Filter(slot="label", value="dune", contains=False)),
        (("label~", "a=b"), Filter(slot="label", value="a=b", contains=True)),
        (("sort~", "x"), Filter(slot="sort", value="x", contains=True)),
        (("label~~", "x"), Filter(slot="label~", value="x", contains=True)),
    ],
    ids=[
        "contains",
        "equality",
        "value-with-equals",
        "reserved-name-after-strip",
        "only-last-tilde",
    ],
)
def test_a_name_ending_in_a_tilde_is_a_contains_filter(param, expected):
    assert list_request([param]).filters == [expected], (
        "the last ~ makes a contains filter; reserved names are compared before it is stripped"
    )


# equivalence class: a limit that is not digits (abc); 0 and 201 are the range's boundaries
@pytest.mark.parametrize(
    "params",
    [
        [("limit", "0")],
        [("limit", "201")],
        [("limit", "abc")],
        [("limit", "2"), ("limit", "3")],
        [("offset", "-1")],
        [("offset", "x")],
        [("offset", "")],
        [("offset", "1"), ("offset", "2")],
        [("offset", "9007199254740992")],
        [("offset", "9223372036854775758")],
        [("sort", "label"), ("sort", "isbn")],
    ],
    ids=lambda p: "&".join(f"{k}={v}" for k, v in p),
)
def test_a_limit_offset_or_sort_that_is_not_one_valid_value_is_a_bad_query(params):
    with pytest.raises(BadQuery):
        list_request(params)


@pytest.mark.parametrize(
    "params",
    [[("limit", "1")], [("limit", "200")], [("offset", "0")], [("offset", "9007199254740991")]],
)
def test_the_bounds_of_limit_and_offset_are_allowed(params):
    list_request(params)


def test_the_slots_a_listing_may_name_are_those_of_the_type_that_are_not_bookkeeping_or_owned(view):
    names = set(listable_slots(view, view.get_class("Book")))
    assert {"label", "description", "isbn", "authors", "published", "genre"} <= names, (
        "the nameable slots include the plain ones of the type"
    )
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
    assert typed_value(view, view.get_slot(slot), text) == expected, (
        "the value is typed by the range of its slot"
    )


# equivalence classes: an IRI with no scheme ("relative/path"), one with a character IRIs forbid ("<")
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
        ("scan_of", "relative/path"),
        ("scan_of", "urn:x:a<b"),
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
    ], "the plan carries the typed filter with its reference"
    assert plan.sort_by == "http://purl.org/dc/terms/issued", "the predicate of the slot"
    assert plan.descending, "a minus sign sorts downwards"
    assert plan.limit == 3, "the plan carries the page size"
    assert plan.offset == 0, "the plan carries the page offset"


def test_without_a_sort_key_the_listing_is_by_iri_ascending(listings, view):
    plan = plan_of(listings, view)
    assert plan.sort_by is None, "the plan sorts by the identifier"
    assert plan.descending is False, "the plan sorts ascending"


def test_the_identifier_sorts_by_iri_in_the_direction_asked(listings, view):
    plan = plan_of(listings, view, ("sort", "-id"))
    assert plan.sort_by is None, "the plan sorts by the identifier"
    assert plan.descending is True, "the plan sorts descending"


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


# TC-03: a contains filter on a slot that is no string slot, on no slot, or with no text
@pytest.mark.parametrize(
    "params",
    [
        [("published~", "19")],
        [("genre~", "fic")],
        [("shelf~", "x")],
        [("workflow_status~", "x")],
        [("nope~", "x")],
        [("~", "x")],
        [("label~~", "x")],
        [("label~", "")],
    ],
    ids=lambda p: "&".join(f"{k}={v}" for k, v in p),
)
def test_a_contains_filter_that_cannot_be_planned_is_a_bad_query(listings, view, params):
    with pytest.raises(BadQuery):
        plan_of(listings, view, *params)


def test_a_contains_filter_keeps_its_text_as_sent_in_the_plan(listings, view):
    plan = plan_of(listings, view, ("label~", "DUNE"), ("genre", "fiction"))
    assert [(c.value, c.contains, c.reference, c.datatype) for c in plan.conditions or []] == [
        ("DUNE", True, False, None),
        (f"{SCHEMA_ORG}Fiction", False, True, None),
    ], "the text is not typed or folded; the equality filter is unchanged"


def test_a_slot_name_is_matched_exactly_not_as_a_pattern(listings, view):
    for name in ("Label", "label ", "la.el", "label}"):
        with pytest.raises(BadQuery):
            plan_of(listings, view, (name, "x"))


def test_a_literal_filter_keeps_its_datatype_in_the_plan(listings, view):
    plan = plan_of(listings, view, ("published", "2020-01-31"), ("isbn", "978"))
    assert [(c.value, c.datatype, c.reference) for c in plan.conditions or []] == [
        ("2020-01-31", str(XSD.date), False),
        ("978", None, False),
    ], "the literal filters keep their datatypes"


def test_the_graphs_hidden_from_the_caller_are_in_the_plan(listings, view):
    plan = plan_of(listings, view, hidden=["https://example.org/g"])
    assert plan.hidden_graphs == ["https://example.org/g"], (
        "the plan carries the graphs hidden from the caller"
    )


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
    assert keys[0] == "id", "the identifier orders by IRI"
    assert "-id" in keys, "the identifier orders by IRI"
    assert {"label", "published", "-label", "-published"} <= set(keys), (
        "the sort keys include the listable slots in both directions"
    )
    assert not {"chapters", "-chapters", "created"} & set(keys), "no owned part, no bookkeeping"
    assert (
        len(keys) == len(set(keys)) == 2 * (len(listable_slots(view, view.get_class("Book"))) + 1)
    ), "the sort keys are unique and cover every listable slot both ways and the identifier"

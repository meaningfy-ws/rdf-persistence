"""The listing query over an in-memory store: the page, the total, the order, the filters, what is hidden (PD-15)."""

from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import RDF, XSD, Literal, URIRef
from rdflib.plugins.sparql import prepareQuery

from rdf_persistence.domain.iris import graph_iri
from rdf_persistence.services.listing import (
    Listings,
    items_of,
    list_request,
    listing_query,
    total_of,
)
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.session import Session
from rdf_persistence.testkit.fakes import FAKE_TENANT, FakeStore, fake_session
from tests.toy import TOY_SCHEMA

SCHEMA = "http://schema.org/"
BIBO = "http://purl.org/ontology/bibo/"
SKOS_LABEL = URIRef("http://www.w3.org/2004/02/skos/core#prefLabel")
ISSUED = URIRef("http://purl.org/dc/terms/issued")
GENRE = URIRef(f"{SCHEMA}genre")
AUTHOR = URIRef(f"{SCHEMA}author")
BOOK_CLASS = URIRef(f"{BIBO}Book")
HOSTILE = '"} ; DROP ALL ; #'


def book_iri(n: int) -> str:
    return f"{FAKE_TENANT}/books/{UUID(int=n)}"


def book(n: int, label: str, *, genre: str = "Fiction", issued: str | None = None, authors=()):
    triples = [
        (URIRef(book_iri(n)), RDF.type, BOOK_CLASS),
        (URIRef(book_iri(n)), SKOS_LABEL, Literal(label)),
        (URIRef(book_iri(n)), GENRE, URIRef(f"{SCHEMA}{genre}")),
        *((URIRef(book_iri(n)), AUTHOR, Literal(a)) for a in authors),
    ]
    if issued:
        triples.append((URIRef(book_iri(n)), ISSUED, Literal(issued, datatype=XSD.date)))
    return book_iri(n), triples


@pytest.fixture(scope="module")
def view() -> SchemaView:
    return load_schema(TOY_SCHEMA)


@pytest.fixture
async def shelf() -> AsyncIterator[Session]:
    """Five books; the sort keys differ from the IRI order."""
    async with fake_session(FakeStore()) as session:
        for n, label, kwargs in [
            (1, "Dune", {"authors": ["Herbert"], "issued": "1965-08-01"}),
            (2, "Emma", {"genre": "NonFiction", "authors": ["Austen"], "issued": "1815-12-23"}),
            (3, "Ulysses", {"authors": ["Joyce", "Herbert"], "issued": "1922-02-02"}),
            (4, "Candide", {"genre": "NonFiction"}),
            (5, "Beloved", {"authors": ["Morrison"], "issued": "1987-09-02"}),
        ]:
            iri, triples = book(n, label, **kwargs)
            await session.add_graph(iri, triples)
        yield session


async def listed(
    session: Session, view: SchemaView, *params: tuple[str, str]
) -> tuple[list[int], int]:
    plan = Listings(view).plan(view.get_class("Book"), list_request(list(params)))
    answer = await session.page(plan)
    numbers = [UUID(root.rsplit("/", 1)[1]).int for root, _ in items_of(answer, plan)]
    return numbers, total_of(answer, plan)


@pytest.mark.parametrize(
    ("params", "numbers", "total"),
    [
        ([], [1, 2, 3, 4, 5], 5),
        ([("limit", "2"), ("offset", "2")], [3, 4], 5),
        ([("limit", "2"), ("offset", "4")], [5], 5),
        ([("limit", "2"), ("offset", "9")], [], 5),
        ([("sort", "-id")], [5, 4, 3, 2, 1], 5),
        ([("sort", "label")], [5, 4, 1, 2, 3], 5),
        ([("sort", "-label")], [3, 2, 1, 4, 5], 5),
        ([("sort", "published")], [4, 2, 3, 1, 5], 5),
        ([("sort", "-published"), ("limit", "2")], [5, 1], 5),
        ([("sort", "authors")], [4, 2, 1, 3, 5], 5),
        ([("genre", "nonfiction")], [2, 4], 2),
        ([("genre", "fiction"), ("authors", "Herbert")], [1, 3], 2),
        ([("authors", "Herbert"), ("authors", "Joyce")], [3], 1),
        ([("published", "1922-02-02")], [3], 1),
        ([("label", "Dune"), ("genre", "nonfiction")], [], 0),
        ([("genre", "fiction"), ("limit", "1"), ("offset", "1"), ("sort", "-label")], [1], 3),
    ],
    ids=lambda v: (
        str(v)
        if not isinstance(v, list) or not v or not isinstance(v[0], tuple)
        else "&".join(f"{a}={b}" for a, b in v)
    ),
)
async def test_a_page_holds_the_aggregates_in_order_and_the_total_counts_the_whole_listing(
    shelf, view, params, numbers, total
):
    assert await listed(shelf, view, *params) == (numbers, total)


async def test_a_hostile_filter_value_matches_nothing_and_leaves_the_store_unchanged(shelf, view):
    before = await listed(shelf, view)
    assert await listed(shelf, view, ("label", HOSTILE)) == ([], 0), "it is a value, nothing else"
    assert await listed(shelf, view) == before, "and the store still holds every book"


async def test_a_hidden_graph_is_left_out_of_the_page_and_of_the_total(shelf, view):
    plan = Listings(view).plan(
        view.get_class("Book"), list_request([("limit", "2")]), [str(graph_iri(book_iri(1)))]
    )
    answer = await shelf.page(plan)
    assert [root for root, _ in items_of(answer, plan)] == [
        URIRef(book_iri(2)),
        URIRef(book_iri(3)),
    ]
    assert total_of(answer, plan) == 4, "the books the caller may not read are not counted either"


async def test_another_type_in_the_same_tenant_is_not_listed(shelf, view):
    scan = f"{FAKE_TENANT}/scans/{UUID(int=9)}"
    await shelf.add_graph(
        scan, [(URIRef(scan), RDF.type, URIRef("https://example.org/ns/library#Scan"))]
    )
    assert (await listed(shelf, view))[1] == 5


async def test_the_triples_of_a_page_are_split_by_aggregate_with_their_parts(shelf, view):
    iri = URIRef(book_iri(7))
    part = URIRef(f"{iri}/parts/{UUID(int=1)}")
    await shelf.add_graph(
        str(iri),
        [
            (iri, RDF.type, BOOK_CLASS),
            (iri, SKOS_LABEL, Literal("Zorro")),
            (iri, URIRef("https://example.org/ns/library#chapter"), part),
            (part, SKOS_LABEL, Literal("One")),
        ],
    )
    plan = Listings(view).plan(view.get_class("Book"), list_request([("label", "Zorro")]))
    items = items_of(await shelf.page(plan), plan)
    assert [root for root, _ in items] == [iri]
    assert (part, SKOS_LABEL, Literal("One")) in items[0][1], "the part travels with its book"


def test_the_query_is_one_construct_with_the_total_and_no_value_pasted_in(view):
    plan = Listings(view).plan(view.get_class("Book"), list_request([("label", HOSTILE)]), [])
    text = listing_query(URIRef(f"{FAKE_TENANT}/registry"), plan)
    assert text.lstrip().startswith("CONSTRUCT"), "one query for the page"
    prepareQuery(text)
    assert text.count('\\"} ; DROP ALL ; #') == text.count("DROP ALL") > 0, (
        "every use is an escaped literal"
    )

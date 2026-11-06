"""The listing query over an in-memory store: the page, the total, the order, the filters, what is hidden (PD-15)."""

from collections.abc import AsyncIterator, Iterable
from datetime import date
from uuid import UUID

import pytest
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import URIRef
from rdflib.plugins.sparql import prepareQuery

from rdf_persistence.domain.iris import graph_iri
from rdf_persistence.domain.sparql import Triple
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
from tests.fixtures.library.generated.books import Book, Genre
from tests.fixtures.library.generated.scans import Scan
from tests.toy import TOY_SCHEMA, dune, toy_mapper

CHAPTER = URIRef("https://example.org/ns/library#chapter")
HOSTILE = '"} ; DROP ALL ; #'


def book_iri(n: int) -> str:
    return f"{FAKE_TENANT}/books/{UUID(int=n)}"


def book(
    n: int,
    label: str,
    *,
    genre: Genre = Genre.FICTION,
    issued: date | None = None,
    authors: tuple[str, ...] = (),
) -> tuple[str, Iterable[Triple]]:
    """A book as the mapper writes it: its IRI and its triples."""
    iri = book_iri(n)
    model = Book(
        id=iri,
        label=label,
        description=f"{label}, a book.",
        genre=genre,
        published=issued,
        authors=list(authors) or None,
    )
    return iri, toy_mapper().to_triples(model)


@pytest.fixture(scope="module")
def view() -> SchemaView:
    return load_schema(TOY_SCHEMA)


@pytest.fixture
async def shelf() -> AsyncIterator[Session]:
    """Five books; the sort keys differ from the IRI order."""
    async with fake_session(FakeStore()) as session:
        for n, label, kwargs in [
            (1, "Dune", {"authors": ("Herbert",), "issued": date(1965, 8, 1)}),
            (
                2,
                "Emma",
                {"genre": Genre.NONFICTION, "authors": ("Austen",), "issued": date(1815, 12, 23)},
            ),
            (3, "Ulysses", {"authors": ("Joyce", "Herbert"), "issued": date(1922, 2, 2)}),
            (4, "Candide", {"genre": Genre.NONFICTION}),
            (5, "Beloved", {"authors": ("Morrison",), "issued": date(1987, 9, 2)}),
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
    stored = Scan(id=scan, label="Dune, scanned", description="A scanned copy.")
    await shelf.add_graph(scan, toy_mapper().to_triples(stored))
    assert (await listed(shelf, view))[1] == 5


async def test_the_triples_of_a_page_are_split_by_aggregate_with_their_parts(shelf, view):
    iri = book_iri(7)
    zorro = dune(iri, chapters=1).model_copy(update={"label": "Zorro"})
    triples = list(toy_mapper().to_triples(zorro))
    await shelf.add_graph(iri, triples)
    plan = Listings(view).plan(view.get_class("Book"), list_request([("label", "Zorro")]))
    items = items_of(await shelf.page(plan), plan)
    assert [root for root, _ in items] == [URIRef(iri)]
    chapter = next(o for s, p, o in triples if s == URIRef(iri) and p == CHAPTER)
    assert any(s == chapter for s, _, _ in items[0][1]), "the part travels with its book"


def test_the_query_is_one_construct_with_the_total_and_no_value_pasted_in(view):
    plan = Listings(view).plan(view.get_class("Book"), list_request([("label", HOSTILE)]), [])
    text = listing_query(URIRef(f"{FAKE_TENANT}/registry"), plan)
    assert text.lstrip().startswith("CONSTRUCT"), "one query for the page"
    prepareQuery(text)
    assert text.count('\\"} ; DROP ALL ; #') == text.count("DROP ALL") > 0, (
        "every use is an escaped literal"
    )

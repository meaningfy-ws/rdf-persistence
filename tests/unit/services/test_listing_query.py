"""The listing query over an in-memory store: the page, the total, the order, the filters, what is hidden (PD-15)."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import RDFS, Literal, URIRef
from rdflib.plugins.sparql import prepareQuery

from rdf_persistence import new_part
from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.domain.iris import DEFAULT_IRIS, Iris, graph_iri
from rdf_persistence.domain.sparql import Triple
from rdf_persistence.services.listing import (
    Listings,
    items_of,
    list_request,
    listing_query,
    total_of,
)
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import iri_types
from rdf_persistence.services.session import Session
from rdf_persistence.testkit.fakes import FAKE_DATABASE, FAKE_PRINCIPAL, FAKE_TENANT, FakeStore
from tests.fixtures.library.generated.books import Book, Chapter, Genre
from tests.fixtures.library.generated.scans import Scan
from tests.toy import TOY_SCHEMA, dune, toy_mapper

CHAPTER = URIRef("https://example.org/ns/library#chapter")
HOSTILE = '"} ; DROP ALL ; #'


@dataclass(frozen=True)
class Policy:
    """An IRI policy and the shape of the ids minted under it: UUIDs (default) or 13 digits (flat, PD-7)."""

    name: str
    tenant: str
    iris: Iris
    object_id: Callable[[int], str]
    number_of_id: Callable[[str], int]

    def aggregate_iri(self, cls_type: str, rp_path: str, n: int) -> str:
        return str(self.iris.aggregate(self.tenant, cls_type, rp_path, self.object_id(n)))

    def book_iri(self, n: int) -> str:
        return self.aggregate_iri("book", "books", n)

    def number(self, iri: str) -> int:
        return self.number_of_id(iri.rsplit("/", 1)[1])

    def chapter(self, root: str) -> Chapter:
        return new_part(Chapter, root, iris=self.iris, tenant=self.tenant, number=1)


def _flat() -> Policy:
    layout = "{base}{tenant_id}/{type}/{id}"
    settings = ServiceSettings(
        base="http://mwb.meaningfy.ws/",
        prefix="mwb",
        tenant_segment="projects",
        creator_role="owner",
        roles_claim="roles",
        iri_policy=IriPolicy(
            tenant_template="{base}project/{tenant_id}",
            aggregate_template=layout,
            part_template=layout,
            loaded_graph_template=layout,
            tenant_id=IdSpec(kind=IdKind.RANDOM, length=7),
            object_id=IdSpec(kind=IdKind.RANDOM, length=13),
        ),
    )
    iris = Iris(settings, *iri_types(load_schema(TOY_SCHEMA)))
    return Policy("flat", str(iris.tenant("p4x8k2m")), iris, lambda n: f"{n:013d}", int)


POLICIES = [
    Policy("default", FAKE_TENANT, DEFAULT_IRIS, lambda n: str(UUID(int=n)), lambda i: UUID(i).int),
    _flat(),
]


@pytest.fixture(params=POLICIES, ids=lambda policy: policy.name)
def policy(request) -> Policy:
    return request.param


def book(
    policy: Policy,
    n: int,
    label: str,
    *,
    genre: Genre = Genre.FICTION,
    issued: date | None = None,
    authors: tuple[str, ...] = (),
) -> tuple[str, Iterable[Triple]]:
    """A book as the mapper writes it: its IRI and its triples."""
    iri = policy.book_iri(n)
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


async def session_of(policy: Policy) -> Session:
    store = FakeStore()
    await store.create_dataset(FAKE_DATABASE)
    return Session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=policy.tenant,
        principal=FAKE_PRINCIPAL,
        clock=lambda: datetime(2026, 11, 8, tzinfo=UTC),
        iris=policy.iris,
    )


@pytest.fixture
async def shelf(policy) -> Session:
    """Five books; the sort keys differ from the IRI order."""
    session = await session_of(policy)
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
        iri, triples = book(policy, n, label, **kwargs)
        await session.add_graph(iri, triples)
    return session


async def listed(
    session: Session, view: SchemaView, policy: Policy, *params: tuple[str, str]
) -> tuple[list[int], int]:
    plan = Listings(view).plan(view.get_class("Book"), list_request(list(params)))
    answer = await session.page(plan)
    numbers = [policy.number(root) for root, _ in items_of(answer, plan)]
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
    shelf, view, policy, params, numbers, total
):
    assert await listed(shelf, view, policy, *params) == (numbers, total)


async def test_a_hostile_filter_value_matches_nothing_and_leaves_the_store_unchanged(
    shelf, view, policy
):
    before = await listed(shelf, view, policy)
    assert await listed(shelf, view, policy, ("label", HOSTILE)) == ([], 0), (
        "it is a value, nothing else"
    )
    assert await listed(shelf, view, policy) == before, "and the store still holds every book"


async def test_a_hidden_graph_is_left_out_of_the_page_and_of_the_total(shelf, view, policy):
    plan = Listings(view).plan(
        view.get_class("Book"),
        list_request([("limit", "2")]),
        [str(graph_iri(policy.book_iri(1)))],
    )
    answer = await shelf.page(plan)
    assert [root for root, _ in items_of(answer, plan)] == [
        URIRef(policy.book_iri(2)),
        URIRef(policy.book_iri(3)),
    ]
    assert total_of(answer, plan) == 4, "the books the caller may not read are not counted either"


async def test_another_type_in_the_same_tenant_is_not_listed(shelf, view, policy):
    scan = policy.aggregate_iri("scan", "scans", 9)
    stored = Scan(id=scan, label="Dune, scanned", description="A scanned copy.")
    await shelf.add_graph(scan, toy_mapper().to_triples(stored))
    assert (await listed(shelf, view, policy))[1] == 5


async def test_the_triples_of_a_page_are_split_by_aggregate_with_their_parts(shelf, view, policy):
    iri = policy.book_iri(7)
    zorro = dune(iri, chapters=1).model_copy(update={"label": "Zorro"})
    triples = list(toy_mapper().to_triples(zorro))
    await shelf.add_graph(iri, triples)
    plan = Listings(view).plan(view.get_class("Book"), list_request([("label", "Zorro")]))
    items = items_of(await shelf.page(plan), plan)
    assert [root for root, _ in items] == [URIRef(iri)]
    chapter = next(o for s, p, o in triples if s == URIRef(iri) and p == CHAPTER)
    assert any(s == chapter for s, _, _ in items[0][1]), "the part travels with its book"


async def test_a_listing_of_aggregates_with_flat_parts_gives_each_item_its_own_parts_only(
    shelf, view, policy
):
    """Parts beside their roots (flat) or under them (default): the graph that holds a subject owns it."""
    owned = {}
    for n in (7, 8):
        iri = policy.book_iri(n)
        model = Book(
            id=iri,
            label="Zorro",
            description="d",
            genre=Genre.FICTION,
            chapters=[policy.chapter(iri)],
        )
        owned[iri] = {o for _, p, o in toy_mapper().to_triples(model) if p == CHAPTER}
        await shelf.add_graph(iri, toy_mapper().to_triples(model))
    plan = Listings(view).plan(view.get_class("Book"), list_request([("label", "Zorro")]))
    items = items_of(await shelf.page(plan), plan)
    assert {str(root) for root, _ in items} == set(owned), "both books are listed"
    for root, triples in items:
        own_subjects = set(triples.subjects()) - {graph_iri(str(root))}
        assert own_subjects == {root, *owned[str(root)]}, "the item holds its own parts, no others"


async def test_a_subject_stored_in_two_listed_graphs_goes_to_one_item_only(view):
    """The query names one graph per subject in a dict: a subject shared by two aggregates lands in one item."""
    default = POLICIES[0]
    session = await session_of(default)
    shared = URIRef("https://example.org/shared")
    for n in (1, 2):
        iri, triples = book(default, n, "Zorro")
        await session.add_graph(iri, [*triples, (shared, RDFS.label, Literal("shared"))])
    plan = Listings(view).plan(view.get_class("Book"), list_request([("label", "Zorro")]))
    items = items_of(await session.page(plan), plan)
    assert len(items) == 2, "both books are listed"
    assert sum(shared in set(triples.subjects()) for _, triples in items) == 1


def test_the_query_is_one_construct_with_the_total_and_no_value_pasted_in(view):
    plan = Listings(view).plan(view.get_class("Book"), list_request([("label", HOSTILE)]), [])
    text = listing_query(URIRef(f"{FAKE_TENANT}/registry"), plan)
    assert text.lstrip().startswith("CONSTRUCT"), "one query for the page"
    prepareQuery(text)
    assert text.count('\\"} ; DROP ALL ; #') == text.count("DROP ALL") > 0, (
        "every use is an escaped literal"
    )

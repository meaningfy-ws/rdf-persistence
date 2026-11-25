"""The listing query over an in-memory store: the page, the total, the order, the filters, what is hidden (PD-15)."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import RDFS, BNode, Literal, URIRef
from rdflib.plugins.sparql import prepareQuery

from rdf_persistence import new_part
from rdf_persistence.core.domain.sparql import Triple
from rdf_persistence.iris.domain.layout import graph_iri
from rdf_persistence.iris.services.generated.rp_iris_services import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.iris.services.iris import DEFAULT_IRIS, Iris
from rdf_persistence.persistence.services.generated.rp_persistence_services import (
    Condition,
    ListPlan,
)
from rdf_persistence.persistence.services.listing import (
    Listings,
    condition_patterns,
    items_of,
    list_request,
    listing_query,
    total_of,
)
from rdf_persistence.persistence.services.session import Session
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import iri_types
from rdf_persistence.testkit.fakes import FAKE_DATABASE, FAKE_PRINCIPAL, FAKE_TENANT, FakeStore
from tests.fixtures.library.domain.generated.books import Author, Book, Chapter, Display, Genre
from tests.fixtures.library.domain.generated.scans import Scan
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
        base="https://example.org/",
        prefix="lib",
        tenant_segment="projects",
        creator_role="owner",
        roles_claim="roles",
        iri_policy=IriPolicy(
            tenant_template="{base}library/{tenant_id}",
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
        # TC-05: a contains filter; an aggregate with two matching values is listed once
        ([("label~", "DUNE")], [1], 1),
        ([("label~", "u")], [1, 3], 2),
        ([("authors~", "HER")], [1, 3], 2),
        ([("authors~", "E"), ("limit", "2")], [1, 2], 3),
        # book 3 holds two matching authors: a join would list it twice, and offset 3 would reach it
        ([("authors~", "e"), ("offset", "3")], [], 3),
        ([("label~", "u"), ("genre", "fiction")], [1, 3], 2),
        ([("label~", "u"), ("genre", "nonfiction")], [], 0),
        ([("authors~", "e"), ("authors~", "j")], [3], 1),
        # every label holds an "e" (Dune too), so the total is 5; by -label: 3, 2, 1, 4, 5
        ([("label~", "e"), ("sort", "-label"), ("limit", "2"), ("offset", "1")], [2, 1], 5),
        # DEC-4: absence; only Candide (4) holds no published date and no author
        ([("absent", "published")], [4], 1),
        ([("absent", "authors")], [4], 1),
        ([("absent", "published"), ("absent", "authors")], [4], 1),
        ([("absent", "published"), ("genre", "nonfiction")], [4], 1),
        ([("absent", "published"), ("genre", "fiction")], [], 0),
        ([("absent", "published"), ("label~", "can")], [4], 1),
        ([("absent", "authors"), ("authors", "Herbert")], [], 0),  # E12: nothing is both
        ([("absent", "description")], [], 0),
        ([("absent", "published"), ("sort", "-label"), ("limit", "1")], [4], 1),
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
    assert await listed(shelf, view, policy, *params) == (numbers, total), (
        "the page holds the aggregates in order and the total counts the whole listing"
    )


@pytest.mark.parametrize("policy", [POLICIES[0]], indirect=True, ids=["default"])
async def test_a_hostile_filter_value_matches_nothing_and_leaves_the_store_unchanged(
    shelf, view, policy
):
    before = await listed(shelf, view, policy)
    assert await listed(shelf, view, policy, ("label", HOSTILE)) == ([], 0), (
        "it is a value, nothing else"
    )
    assert await listed(shelf, view, policy) == before, "and the store still holds every book"


# TC-06: the texts that would break out of a literal, as the contains filter's text
@pytest.mark.parametrize("policy", [POLICIES[0]], indirect=True, ids=["default"])
@pytest.mark.parametrize(
    "text",
    [HOSTILE, '"', "\\", "}", "a\nb", "\\u0022"],
    ids=["break-out", "quote", "backslash", "brace", "newline", "unicode-escape"],
)
async def test_a_hostile_contains_text_matches_nothing_and_leaves_the_store_unchanged(
    shelf, view, policy, text
):
    before = await listed(shelf, view, policy)
    assert await listed(shelf, view, policy, ("label~", text)) == ([], 0), (
        "it is a text, nothing else"
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
    ], "the hidden graph is left out of the page"
    assert total_of(answer, plan) == 4, "the books the caller may not read are not counted either"


async def test_another_type_in_the_same_tenant_is_not_listed(shelf, view, policy):
    scan = policy.aggregate_iri("scan", "scans", 9)
    stored = Scan(id=scan, label="Dune, scanned", description="A scanned copy.")
    await shelf.add_graph(scan, toy_mapper().to_triples(stored))
    assert (await listed(shelf, view, policy))[1] == 5, "the total counts only the listed type"


async def test_the_triples_of_a_page_are_split_by_aggregate_with_their_parts(shelf, view, policy):
    iri = policy.book_iri(7)
    zorro = dune(iri, chapters=1).model_copy(update={"label": "Zorro"})
    triples = list(toy_mapper().to_triples(zorro))
    await shelf.add_graph(iri, triples)
    plan = Listings(view).plan(view.get_class("Book"), list_request([("label", "Zorro")]))
    items = items_of(await shelf.page(plan), plan)
    assert [root for root, _ in items] == [URIRef(iri)], "the page is split by aggregate"
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
    assert sum(shared in set(triples.subjects()) for _, triples in items) == 1, (
        "a subject stored in two listed graphs goes to one item only"
    )


async def test_an_aggregate_holding_only_a_blank_node_part_is_not_absent(shelf, view, policy):
    """D-9: a part without an identifier is a blank node, and it is a value."""
    iri = policy.book_iri(8)
    _, triples = book(policy, 8, "Holder")
    await shelf.add_graph(iri, [*triples, (URIRef(iri), CHAPTER, BNode())])
    plan = ListPlan(
        target=str(view.get_uri(view.get_class("Book"), expand=True)),
        conditions=[Condition(predicate=str(CHAPTER), value="", absent=True)],
        limit=50,
        offset=0,
    )
    answer = await shelf.page(plan)
    assert policy.book_iri(8) not in {str(root) for root, _ in items_of(answer, plan)}, (
        "the book holding a blank-node chapter is not matched by absence"
    )
    assert total_of(answer, plan) == 5, "the five books with no chapter are matched, not it"


def test_conditions_without_absence_render_as_before_and_an_absent_one_renders_a_not_exists(view):
    """E14: the equal and contains parts are untouched; absence adds one FILTER NOT EXISTS."""
    listings = Listings(view)
    book_class = view.get_class("Book")

    def patterns(*params: tuple[str, str]) -> str:
        plan = listings.plan(book_class, list_request(list(params)))
        return condition_patterns("root", plan.conditions or [])

    equal = patterns(("label", "Dune"))
    contains = patterns(("label~", "du"))
    assert "NOT EXISTS" not in equal + contains, "no absence, no NOT EXISTS"
    assert "FILTER EXISTS" in contains, "contains still renders FILTER EXISTS"
    published = patterns(("absent", "published"))
    assert published.count("FILTER NOT EXISTS") == 1, "one absent condition, one NOT EXISTS"
    assert patterns(("label", "Dune"), ("absent", "published")).startswith(equal), (
        "the equal patterns come first and are unchanged"
    )
    assert patterns(("label", "Dune"), ("label~", "du"), ("absent", "published")) == (
        f"{equal} {contains} {published}"
    ), "equal, then contains, then absent, each as it renders alone"


SKOS_LABEL = "http://www.w3.org/2004/02/skos/core#prefLabel"
PUBLISHED = "http://purl.org/dc/terms/issued"
# What condition_patterns and listing_query returned for path-less conditions before `via` (E14).
BEFORE_EQUAL = f'?root <{SKOS_LABEL}> "Dune" .'
BEFORE_CONTAINS = (
    f"FILTER EXISTS {{ ?root <{SKOS_LABEL}> ?root_c0 . "
    'FILTER (CONTAINS(LCASE(STR(?root_c0)), LCASE("du"))) }'
)
BEFORE_ABSENT = f"FILTER NOT EXISTS {{ ?root <{PUBLISHED}> ?root_a0 . }}"
_BEFORE_MATCHING = (
    "\n  GRAPH <https://example.org/t/registry> { ?graph "
    "<https://meaningfy.ws/ns/rdf-persistence#kind> "
    "<https://meaningfy.ws/ns/rdf-persistence#Aggregate> ; "
    "<https://meaningfy.ws/ns/rdf-persistence#ownedBy> ?root }\n"
    "  GRAPH ?graph { ?root a <http://purl.org/ontology/bibo/Book> . "
    f"{BEFORE_EQUAL} {BEFORE_CONTAINS} {BEFORE_ABSENT} }}\n"
    "  FILTER (?graph NOT IN (<https://example.org/t/a/graph>, <https://example.org/t/b/graph>))\n"
)
BEFORE_QUERY_WITH_HIDDEN = (
    "\nCONSTRUCT { ?s ?p ?o . ?s <https://meaningfy.ws/ns/rdf-persistence#listedIn> ?graph . "
    "<http://purl.org/ontology/bibo/Book> <https://meaningfy.ws/ns/rdf-persistence#total> ?total } "
    "WHERE {\n  { SELECT (COUNT(DISTINCT ?root) AS ?total) WHERE { "
    + _BEFORE_MATCHING
    + " } }\n  UNION\n  { { SELECT ?root ?graph WHERE { "
    + _BEFORE_MATCHING
    + " } ORDER BY ASC(?root) LIMIT 50 OFFSET 0 } GRAPH ?graph { ?s ?p ?o } }\n}\n"
)


def test_a_path_less_condition_set_renders_exactly_as_before_whatever_is_hidden(view):
    """E14: the strings captured before `via` existed; hidden graphs change nothing without a path."""
    listings = Listings(view)
    book_class = view.get_class("Book")
    hidden = ["https://example.org/t/a/graph", "https://example.org/t/b/graph"]

    def patterns(*params: tuple[str, str]) -> str:
        plan = listings.plan(book_class, list_request(list(params)))
        return condition_patterns("root", plan.conditions or [], hidden)

    assert patterns(("label", "Dune")) == BEFORE_EQUAL, "equal renders as before"
    assert patterns(("label~", "du")) == BEFORE_CONTAINS, "contains renders as before"
    assert patterns(("absent", "published")) == BEFORE_ABSENT, "absent renders as before"
    plan = listings.plan(
        book_class,
        list_request([("label", "Dune"), ("label~", "du"), ("absent", "published")]),
        hidden,
    )
    text = listing_query(URIRef("https://example.org/t/registry"), plan)
    assert text == BEFORE_QUERY_WITH_HIDDEN, "the whole query with hidden graphs is unchanged"


def _hop(subject: str, predicate: str, variable: str, hidden: str, inner: str) -> str:
    return (
        f"?{subject} <{predicate}> ?{variable} . "
        f'BIND (IRI(CONCAT(STR(?{variable}), "/graph")) AS ?{variable}_g) '
        f"FILTER (?{variable}_g NOT IN (<{hidden}>)) "
        f"GRAPH ?{variable}_g {{ {inner} }}"
    )


def test_a_path_condition_renders_nested_hops_in_a_filter_exists_with_hidden_on_every_hop():
    """D-2: FILTER EXISTS around the hops, `{variable}_p{n}_{j}` variables, NOT IN on each hop."""
    first, second, hidden = "http://x/first", "http://x/second", "http://x/h/graph"
    condition = Condition(predicate=SKOS_LABEL, value="herbert", contains=True, via=[first, second])
    inner = (
        f"FILTER EXISTS {{ ?root_p0_2 <{SKOS_LABEL}> ?root_p0_2_c0 . "
        'FILTER (CONTAINS(LCASE(STR(?root_p0_2_c0)), LCASE("herbert"))) }'
    )
    second_hop = _hop("root_p0_1", second, "root_p0_2", hidden, inner)
    first_hop = _hop("root", first, "root_p0_1", hidden, second_hop)
    assert condition_patterns("root", [condition], [hidden]) == (
        f"FILTER EXISTS {{ {first_hop} }}"
    ), "two nested hops, the last segment a contains on the last target"
    assert hidden not in condition_patterns("root", [condition]), "no hidden, no NOT IN"


def test_path_conditions_number_their_variables_apart_after_the_path_less_ones():
    one = Condition(predicate=SKOS_LABEL, value="a", via=["http://x/ref"])
    two = Condition(predicate=SKOS_LABEL, value="b", via=["http://x/ref"])
    plain = Condition(predicate=SKOS_LABEL, value="Dune")

    def exists(n: int, value: str) -> str:
        return (
            f"FILTER EXISTS {{ ?root <http://x/ref> ?root_p{n}_1 . "
            f'BIND (IRI(CONCAT(STR(?root_p{n}_1), "/graph")) AS ?root_p{n}_1_g) '
            f'GRAPH ?root_p{n}_1_g {{ ?root_p{n}_1 <{SKOS_LABEL}> "{value}" . }} }}'
        )

    assert condition_patterns("root", [one, plain, two]) == (
        f"{BEFORE_EQUAL} {exists(0, 'a')} {exists(1, 'b')}"
    ), "the path-less condition renders first; each path condition has its own p{n}"


def test_the_listing_query_passes_the_hidden_graphs_to_every_hop(view):
    hidden = "https://example.org/t/h/graph"
    plan = Listings(view).plan(view.get_class("Book"), list_request([("label", "Dune")]), [hidden])
    plan.conditions = [
        Condition(predicate=SKOS_LABEL, value="x", via=["http://x/ref"]),
    ]
    text = listing_query(URIRef("https://example.org/t/registry"), plan)
    prepareQuery(text)
    assert text.count(f"?root_p0_1_g NOT IN (<{hidden}>)") == 2, (
        "the page and the count both filter the hop"
    )


AUTHOR_LABEL = URIRef(SKOS_LABEL)
HERBERT, AUSTEN = "Frank Herbert", "Jane Austen"


def _linked_book(policy: Policy, n: int, label: str, **links: str) -> tuple[str, list[Triple]]:
    iri = policy.book_iri(n)
    model = Book(id=iri, label=label, description=f"{label}, a book.", **links)
    return iri, list(toy_mapper().to_triples(model))


@pytest.fixture
async def linked(policy) -> Session:
    """Two authors (1: Herbert, 2: Austen); books 1 to 4 (1 and 3 and 4 by Herbert, 3 follows 1, 4 follows 3); two displays."""
    session = await session_of(policy)
    for n, name in [(1, HERBERT), (2, AUSTEN)]:
        iri = policy.aggregate_iri("author", "authors", n)
        model = Author(id=iri, label=name, description=f"{name}.")
        await session.add_graph(iri, toy_mapper().to_triples(model))
    herbert, austen = (policy.aggregate_iri("author", "authors", n) for n in (1, 2))
    for n, label, links in [
        (1, "Dune", {"written_by": herbert}),
        (2, "Emma", {"written_by": austen}),
        (3, "Children of Dune", {"written_by": herbert, "sequel_of": policy.book_iri(1)}),
        (4, "God Emperor", {"written_by": herbert, "sequel_of": policy.book_iri(3)}),
    ]:
        iri, triples = _linked_book(policy, n, label, **links)
        await session.add_graph(iri, triples)
    for n, features in [(1, [1, 3]), (2, [1, 2])]:
        iri = policy.aggregate_iri("display", "displays", n)
        model = Display(
            id=iri,
            label=f"Display {n}",
            description="d",
            features=[policy.book_iri(m) for m in features],
        )
        await session.add_graph(iri, toy_mapper().to_triples(model))
    return session


async def listed_of(
    session: Session,
    view: SchemaView,
    policy: Policy,
    cls: str,
    *params: tuple[str, str],
    hidden: Iterable[str] = (),
) -> tuple[list[int], int]:
    plan = Listings(view).plan(view.get_class(cls), list_request(list(params)), hidden)
    answer = await session.page(plan)
    return [policy.number(root) for root, _ in items_of(answer, plan)], total_of(answer, plan)


@pytest.mark.parametrize(
    ("cls", "params", "numbers", "total"),
    [
        ("Book", [("written_by.label", HERBERT)], [1, 3, 4], 3),  # S1
        ("Book", [("written_by.label", AUSTEN)], [2], 1),
        ("Book", [("written_by.label", "Nobody")], [], 0),
        ("Book", [("written_by.label~", "HERB")], [1, 3, 4], 3),  # S6
        (
            "Book",
            [("written_by.label~", "e")],
            [1, 2, 3, 4],
            4,
        ),  # S6: Herbert and Austen both hold an e
        ("Book", [("written_by.label~", "e"), ("limit", "2"), ("offset", "3")], [4], 4),
        (
            "Book",
            [("written_by.label", HERBERT), ("label~", "dune")],
            [1, 3],
            2,
        ),  # with a root filter
        ("Book", [("written_by.label", HERBERT), ("sort", "-label")], [4, 1, 3], 3),
        ("Book", [("sequel_of.written_by.label", HERBERT)], [3, 4], 2),  # S3b: two hops
        ("Book", [("sequel_of.sequel_of.written_by.label", HERBERT)], [4], 1),  # S3b: three hops
        ("Book", [("sequel_of.label", "Dune")], [3], 1),
        ("Book", [("sequel_of.label~", "dune")], [3, 4], 2),
        ("Display", [("features.written_by.label", HERBERT)], [1, 2], 2),  # S2: listed once
        ("Display", [("features.written_by.label", AUSTEN)], [2], 1),
        # E13, DEC-4: the two conditions need not hold of the same book
        (
            "Display",
            [("features.written_by.label", HERBERT), ("features.written_by.label", AUSTEN)],
            [2],
            1,
        ),
        ("Display", [("features.label~", "dune"), ("limit", "1")], [1], 2),
    ],
    ids=lambda v: (
        "&".join(f"{a}={b}" for a, b in v)
        if isinstance(v, list) and v and isinstance(v[0], tuple)
        else str(v)
    ),
)
async def test_a_path_filter_lists_the_aggregates_whose_referenced_aggregates_match(
    linked, view, policy, cls, params, numbers, total
):
    assert await listed_of(linked, view, policy, cls, *params) == (numbers, total), (
        "the page and the total hold the aggregates that reach a matching aggregate, once each"
    )


async def test_a_path_filter_on_a_reference_equality_matches_the_iri(linked, view, policy):  # S3
    herbert = policy.aggregate_iri("author", "authors", 1)
    assert await listed_of(linked, view, policy, "Book", ("sequel_of.written_by", herbert)) == (
        [3, 4],
        2,
    ), "the sequels of the books by that author"
    assert await listed_of(linked, view, policy, "Display", ("features.written_by", herbert)) == (
        [1, 2],
        2,
    ), "a display featuring two books by the author is listed once"


async def test_a_reference_to_an_aggregate_that_is_gone_matches_nothing(linked, view, policy):
    iri, triples = _linked_book(
        policy, 6, "Orphan", written_by=policy.aggregate_iri("author", "authors", 99)
    )
    await linked.add_graph(iri, triples)  # S9: a dangling IRI, no <author>/graph
    numbers, total = await listed_of(linked, view, policy, "Book", ("written_by.label~", "a"))
    assert 6 not in numbers, "the orphan has no author graph to match"
    assert (numbers, total) == ([1, 2, 3, 4], 4), "the others are unchanged"


async def test_a_statement_about_the_target_in_another_graph_does_not_match(linked, view, policy):
    austen = policy.aggregate_iri("author", "authors", 2)
    iri, triples = _linked_book(policy, 7, "Forger", written_by=austen)
    forged = (URIRef(austen), AUTHOR_LABEL, Literal(HERBERT))
    await linked.add_graph(
        iri, [*triples, forged]
    )  # S10: Austen is called Herbert in the book's graph
    assert await listed_of(linked, view, policy, "Book", ("written_by.label", HERBERT)) == (
        [1, 3, 4],
        3,
    ), "only the author's own graph speaks for the author"


async def test_a_graph_hidden_from_the_caller_hides_the_hop_it_would_reach(linked, view, policy):
    herbert = policy.aggregate_iri("author", "authors", 1)
    hidden = [str(graph_iri(herbert))]
    assert await listed_of(
        linked, view, policy, "Book", ("written_by.label", HERBERT), hidden=hidden
    ) == ([], 0), "S4: the author's graph is hidden, so no book matches through it"
    assert await listed_of(
        linked, view, policy, "Book", ("written_by.label", AUSTEN), hidden=hidden
    ) == (
        [2],
        1,
    ), "the other authors still match"


def test_the_query_is_one_construct_with_the_total_and_no_value_pasted_in(view):
    plan = Listings(view).plan(view.get_class("Book"), list_request([("label", HOSTILE)]), [])
    text = listing_query(URIRef(f"{FAKE_TENANT}/registry"), plan)
    assert text.lstrip().startswith("CONSTRUCT"), "one query for the page"
    prepareQuery(text)
    assert text.count('\\"} ; DROP ALL ; #') == text.count("DROP ALL") > 0, (
        "every use is an escaped literal"
    )

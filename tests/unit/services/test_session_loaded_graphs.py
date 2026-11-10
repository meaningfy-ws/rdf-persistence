"""The session's commit with loaded graphs and blank nodes, over the in-memory FakeStore."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from rdflib import RDF, BNode, Graph, Literal, URIRef

from rdf_persistence.domain.exceptions import Conflict, InvalidIri
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.generated.service.rp_service import IriPolicy, ServiceSettings
from rdf_persistence.domain.iris import (
    DEFAULT_IRIS,
    Iris,
    graph_iri,
)
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import iri_types
from rdf_persistence.services.session import Session
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.fixtures.library.generated.books import Book
from tests.toy import TOY_SCHEMA

BOOK = URIRef("http://purl.org/ontology/bibo/Book")
FLAT = "{base}{tenant_id}/{type}/{id}"

TENANT = "https://example.org/libraries/6f1c0c1e"
ADA, BEN = "https://example.org/people/ada", "https://example.org/people/ben"
ROOT = f"{TENANT}/books/{UUID(int=1)}"
OTHER = f"{TENANT}/books/{UUID(int=2)}"
OTHER_LOADED = URIRef(f"{OTHER}/content/{UUID(int=12)}")
TITLE = URIRef("http://purl.org/dc/terms/title")
LOADED = [URIRef(f"{ROOT}/content/{UUID(int=10)}"), URIRef(f"{ROOT}/content/{UUID(int=11)}")]
LOADED_TTL = '<https://example.org/b> <http://purl.org/dc/terms/title> "Dune" .'
ENTRIES = "SELECT ?g WHERE { GRAPH $r { ?g $kind $loaded } }"


@pytest.fixture
async def store():
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


@pytest.fixture
async def session(store) -> AsyncIterator[Session]:
    async with fake_session(
        store,
        tenant_iri=TENANT,
        principal=Principal(id="https://example.org/people/ada"),
        clock=lambda: datetime(2026, 11, 5, tzinfo=UTC),
    ) as opened:
        yield opened


async def has_triples(store, graph: URIRef) -> bool:
    result = await store.query(FAKE_DATABASE, fill("ASK { GRAPH $g { ?s ?p ?o } }", g=term(graph)))
    return bool(result.askAnswer)


async def registered_loaded(store) -> set[URIRef]:
    text = fill(
        ENTRIES,
        r=term(DEFAULT_IRIS.registry(TENANT)),
        kind=term(v.REGISTRY_KIND),
        loaded=term(v.REGISTRY_KIND_IRIS["loaded_graph"]),
    )
    return {row.g for row in await store.query(FAKE_DATABASE, text)}


async def test_add_registers_every_loaded_graph_in_the_same_update(session, store):
    await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    assert await registered_loaded(store) == set(LOADED), "one entry per loaded graph"
    assert len(store.sent("update")) == 1, "graph and entries are one update"


async def test_replace_rewrites_the_loaded_graph_entries_to_the_given_ones(session, store):
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [], version, loaded_graphs=LOADED[:1])
    assert await registered_loaded(store) == set(LOADED[:1]), "the dropped graph is unregistered"


async def test_replace_with_an_empty_list_unregisters_them(session, store):
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [], version, loaded_graphs=[])
    assert await registered_loaded(store) == set(), "an explicit empty list drops them all"


async def test_replace_without_a_list_keeps_the_registered_loaded_graphs(session, store):
    for graph in LOADED:
        await store.put_graph(FAKE_DATABASE, graph, Graph().parse(data=LOADED_TTL, format="turtle"))
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [(URIRef(ROOT), TITLE, Literal("edited"))], version)
    assert await registered_loaded(store) == set(LOADED), "their entries stay"
    assert [g for g in LOADED if await has_triples(store, g)] == LOADED, "their triples stay"


async def test_replace_without_a_list_leaves_the_loaded_graphs_of_another_aggregate_alone(
    session, store
):
    await session.add_graph(OTHER, [], loaded_graphs=[OTHER_LOADED])
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [], version)
    assert await registered_loaded(store) == {*LOADED, OTHER_LOADED}


OUTSIDE_THE_CONTENT = [
    pytest.param(URIRef(f"{OTHER}/graph"), id="another aggregate's graph"),
    pytest.param(DEFAULT_IRIS.registry(TENANT), id="the registry graph"),
    pytest.param(OTHER_LOADED, id="another aggregate's loaded graph"),
    pytest.param(URIRef(f"{ROOT}/content"), id="the content segment without a graph"),
    pytest.param(
        URIRef(f"{ROOT}0/content/{UUID(int=10)}"), id="a sibling that shares the prefix text"
    ),
]


@pytest.mark.parametrize("bad", OUTSIDE_THE_CONTENT)
async def test_add_refuses_a_loaded_graph_outside_the_aggregate_before_any_request(
    session, store, bad
):
    with pytest.raises(ValueError, match="loaded graph"):
        await session.add_graph(ROOT, [], loaded_graphs=[LOADED[0], bad])
    assert (store.sent("query"), store.sent("update")) == ([], []), "the store was not touched"


@pytest.mark.parametrize("bad", OUTSIDE_THE_CONTENT)
async def test_replace_refuses_a_loaded_graph_outside_the_aggregate_before_any_request(
    session, store, bad
):
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    requests = (len(store.sent("query")), len(store.sent("update")))
    with pytest.raises(ValueError, match="loaded graph"):
        await session.replace_graph(ROOT, [], version, loaded_graphs=[bad])
    assert (len(store.sent("query")), len(store.sent("update"))) == requests, "nothing was sent"
    assert await registered_loaded(store) == set(LOADED), "and nothing changed"


async def test_removing_an_aggregate_cannot_empty_the_graph_of_another(session, store):
    victim = OTHER
    await session.add_graph(victim, [(URIRef(victim), TITLE, Literal("victim"))])
    with pytest.raises(ValueError, match="loaded graph"):
        await session.add_graph(ROOT, [], loaded_graphs=[graph_iri(victim)])
    stored, _, _ = await session.get_graph(victim)
    assert (URIRef(victim), TITLE, Literal("victim")) in stored, "the victim is intact"


async def test_remove_unregisters_the_loaded_graphs_with_the_aggregate(session, store):
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.remove(ROOT, version)
    assert await registered_loaded(store) == set(), "no entry survives the aggregate"


async def test_a_graph_with_blank_nodes_is_stored_once_with_skolem_iris(session):
    part = BNode("part")
    triples = [(URIRef(ROOT), TITLE, part), (part, TITLE, Literal("x"))]
    version = await session.add_graph(ROOT, triples)
    await session.replace_graph(ROOT, triples, version)  # the guard matches many rows here
    stored, _, _ = await session.get_graph(ROOT)
    plain = [t for t in stored if t[1] not in v.BOOKKEEPING_PREDICATES]
    assert len(plain) == 2, "two statements, none copied per matched row"
    assert not any(isinstance(n, BNode) for t in stored for n in t), "no blank node stored"
    skolem = next(o for s, _, o in plain if s == URIRef(ROOT))
    assert str(skolem).startswith(f"{ROOT}/graph/.well-known/genid/"), (
        "a skolem IRI under the graph"
    )


async def test_remove_drops_the_triples_of_the_loaded_graphs_it_owned(session, store):
    for graph in LOADED:
        await store.put_graph(FAKE_DATABASE, graph, Graph().parse(data=LOADED_TTL, format="turtle"))
    other = OTHER_LOADED
    await store.put_graph(FAKE_DATABASE, other, Graph().parse(data=LOADED_TTL, format="turtle"))
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.remove(ROOT, version)
    assert [g for g in (*LOADED, other) if await has_triples(store, g)] == [other], (
        "only the removed aggregate's loaded graphs are gone"
    )


async def test_replace_drops_the_triples_of_unlisted_loaded_graphs_and_keeps_listed_ones(
    session, store
):
    for graph in LOADED:
        await store.put_graph(FAKE_DATABASE, graph, Graph().parse(data=LOADED_TTL, format="turtle"))
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [], version, loaded_graphs=LOADED[:1])
    assert await has_triples(store, LOADED[0]), "the listed graph keeps its triples"
    assert not await has_triples(store, LOADED[1]), "the unlisted graph is emptied"


async def test_replace_with_an_empty_list_empties_all_of_them(session, store):
    for graph in LOADED:
        await store.put_graph(FAKE_DATABASE, graph, Graph().parse(data=LOADED_TTL, format="turtle"))
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [], version, loaded_graphs=[])
    assert [g for g in LOADED if await has_triples(store, g)] == [], "none is left"


async def test_a_stale_replace_leaves_the_loaded_graphs_alone(session, store):
    await store.put_graph(FAKE_DATABASE, LOADED[0], Graph().parse(data=LOADED_TTL, format="turtle"))
    await session.add_graph(ROOT, [], loaded_graphs=LOADED[:1])
    with pytest.raises(Conflict):
        await session.replace_graph(ROOT, [], "stale")
    assert await has_triples(store, LOADED[0]), "the guard protects the loaded graph too"


async def test_two_concurrent_adds_of_one_iri_give_one_success_and_one_conflict(store):
    gate = asyncio.Barrier(2)
    original = store.update

    async def held(dataset: str, sparql: str) -> None:
        await gate.wait()  # both have passed any pre-check by now
        await original(dataset, sparql)

    store.update = held
    async with (
        fake_session(store, tenant_iri=TENANT, principal=Principal(id=ADA)) as first,
        fake_session(store, tenant_iri=TENANT, principal=Principal(id=BEN)) as second,
    ):
        outcomes = await asyncio.gather(
            first.add_graph(ROOT, []), second.add_graph(ROOT, []), return_exceptions=True
        )
        stored, _, _ = await first.get_graph(ROOT)
    assert sorted(type(o).__name__ for o in outcomes) == ["Conflict", "str"], "one wins"
    assert len(list(stored.objects(None, v.VERSION))) == 1, "one version token was written"


NOT_MINTED = [
    pytest.param(f"{ROOT}/content/x", id="a path below an aggregate"),
    pytest.param(f"{TENANT}/books/1", id="not a UUID"),
    pytest.param(f"{TENANT}/books/{str(uuid4()).upper()}", id="not a canonical UUID"),
    pytest.param(f"{ROOT}/graph", id="an aggregate's graph IRI"),
]


@pytest.mark.parametrize("bad", NOT_MINTED)
@pytest.mark.parametrize("call", ["add_graph", "replace_graph", "loaded_graph"])
async def test_a_commit_refuses_an_aggregate_iri_that_was_not_minted_before_any_request(
    session, store, call, bad
):
    arguments = {"add_graph": (bad, []), "replace_graph": (bad, [], "v")}.get(
        call, (bad, LOADED[0])
    )
    with pytest.raises(InvalidIri, match="aggregate"):
        await getattr(session, call)(*arguments)
    assert (store.sent("query"), store.sent("update")) == ([], []), "the store was not touched"


async def test_an_aggregate_cannot_pose_as_a_loaded_graph_of_another_and_be_removed_with_it(
    session, store
):
    posing = f"{ROOT}/content/x"
    with pytest.raises(InvalidIri):
        await session.add_graph(posing, [(URIRef(posing), TITLE, Literal("victim"))])
    assert await registered_loaded(store) == set(), "nothing is registered under the root"


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(URIRef(f"{ROOT}/content/x"), id="not a UUID"),
        pytest.param(URIRef(f"{ROOT}/content/{uuid4().hex}"), id="a UUID without hyphens"),
        pytest.param(URIRef(f"{ROOT}/content/{uuid4()}/more"), id="a longer path"),
    ],
)
async def test_a_loaded_graph_must_be_exactly_the_minted_form(session, store, bad):
    with pytest.raises(InvalidIri, match="loaded graph"):
        await session.add_graph(ROOT, [], loaded_graphs=[bad])
    assert store.sent("update") == [], "nothing was sent"


# --- the tenant root's loaded graphs (tenant-root-loads, issue #73) ---------------------------

ROOT_TRIPLES = [(URIRef(TENANT), TITLE, Literal("Ghent"))]
AGGREGATE = URIRef("https://meaningfy.ws/ns/rdf-persistence#Aggregate")


async def _root_with(session, loaded: list[URIRef]) -> str:
    """The tenant root stored, then committed with ``loaded``; answers its version."""
    version = await session.add_graph(TENANT, ROOT_TRIPLES)
    return await session.replace_graph(TENANT, ROOT_TRIPLES, version, loaded_graphs=loaded)


async def _load(session, aggregate: str) -> URIRef:
    return await session.load_graph(aggregate, LOADED_TTL.encode(), rdf_format=RdfFormat.TURTLE)


async def test_tc01_a_root_load_comes_back_in_a_new_session(store):
    async with fake_session(store, tenant_iri=TENANT) as first:
        loaded = await _load(first, TENANT)
        await _root_with(first, [loaded])
    async with fake_session(store, tenant_iri=TENANT) as later:
        assert await later.loaded_graphs(TENANT) == [loaded]
        content = await later.loaded_graph(TENANT, str(loaded))
    assert set(content) == set(Graph().parse(data=LOADED_TTL, format="turtle"))


async def test_tc03_a_root_replace_with_an_empty_list_empties_its_load(session, store):
    loaded = await _load(session, TENANT)
    version = await _root_with(session, [loaded])
    await session.replace_graph(TENANT, ROOT_TRIPLES, version, loaded_graphs=[])
    assert await session.loaded_graphs(TENANT) == []
    assert not await has_triples(store, loaded)


async def test_tc04_removing_the_root_empties_its_loads_and_their_entries(session, store):
    loaded = await _load(session, TENANT)
    version = await _root_with(session, [loaded])
    await session.remove(TENANT, version)
    assert not await has_triples(store, loaded)
    assert await registered_loaded(store) == set()


async def _root_and_book(session) -> tuple[URIRef, URIRef, str, str]:
    """The root committed with one load and a book with another; answers both and both versions."""
    mine, theirs = await _load(session, TENANT), await _load(session, ROOT)
    root_version = await _root_with(session, [mine])
    book_version = await session.add_graph(ROOT, [], loaded_graphs=[theirs])
    return mine, theirs, root_version, book_version


async def test_tc05_a_root_replace_with_an_empty_list_leaves_a_books_loads(session, store):
    _, theirs, root_version, _ = await _root_and_book(session)
    await session.replace_graph(TENANT, ROOT_TRIPLES, root_version, loaded_graphs=[])
    assert await session.loaded_graphs(ROOT) == [theirs]
    assert await has_triples(store, theirs)


async def test_tc06_a_books_replace_and_remove_leave_the_roots_loads(session, store):
    mine, _, _, book_version = await _root_and_book(session)
    book_version = await session.replace_graph(ROOT, [], book_version, loaded_graphs=[])
    await session.remove(ROOT, book_version)
    assert await session.loaded_graphs(TENANT) == [mine]
    assert await has_triples(store, mine)


async def test_tc07_a_root_replace_without_a_list_keeps_both_sets(session, store):
    mine, theirs, root_version, _ = await _root_and_book(session)
    await session.replace_graph(TENANT, ROOT_TRIPLES, root_version)
    assert await session.loaded_graphs(TENANT) == [mine]
    assert await session.loaded_graphs(ROOT) == [theirs]


async def test_tc08_a_root_commit_cannot_claim_a_books_load_under_a_flat_policy(store):
    settings = ServiceSettings(
        base="http://mwb.meaningfy.ws/",
        prefix="mwb",
        tenant_segment="projects",
        creator_role="librarian",
        roles_claim="roles",
        iri_policy=IriPolicy(
            tenant_template="{base}project/{tenant_id}",
            aggregate_template=FLAT,
            part_template=FLAT,
            loaded_graph_template=FLAT,
        ),
    )
    iris = Iris(settings, *iri_types(load_schema(TOY_SCHEMA)))
    tenant = str(iris.mint_tenant())
    book = str(iris.mint_aggregate(tenant, "book", "books"))
    root_triples = [(URIRef(tenant), TITLE, Literal("Ghent"))]
    async with fake_session(store, tenant_iri=tenant, iris=iris) as session:
        theirs = await _load(session, book)
        await session.add_graph(book, [], loaded_graphs=[theirs])
        version = await session.add_graph(tenant, root_triples)
        before = len(store.sent("update"))
        with pytest.raises(InvalidIri, match="owned by another aggregate"):
            await session.replace_graph(tenant, root_triples, version, loaded_graphs=[theirs])
        assert len(store.sent("update")) == before, "nothing written"
        assert await session.loaded_graphs(book) == [theirs]


async def test_tc10_the_root_gets_no_aggregate_entry_and_joins_no_listing(store):
    listings = Listings(load_schema(TOY_SCHEMA))
    async with fake_session(store, tenant_iri=TENANT, listings=listings) as session:
        loaded = await _load(session, TENANT)
        await _root_with(session, [loaded])
        await session.add_graph(ROOT, [(URIRef(ROOT), RDF.type, BOOK)])
        assert await session.find(Book) == [ROOT]
    text = fill(
        "ASK { GRAPH $r { $meta ?p $aggregate } }",
        r=term(DEFAULT_IRIS.registry(TENANT)),
        meta=term(DEFAULT_IRIS.meta(TENANT)),
        aggregate=term(AGGREGATE),
    )
    assert not (await store.query(FAKE_DATABASE, text)).askAnswer

"""The ``Store`` conformance suite: one set of cases, run against the fake and against Fuseki.

Each case takes a store and the name of a fresh dataset. A divergence between the fake and Fuseki
is a bug in the fake. Run a case with ``run_case``, which creates the dataset and drops it (and
any ``<dataset>-*`` the case made) afterwards.
"""

import uuid
from collections.abc import Awaitable, Callable, Iterable
from typing import cast

import pytest
from rdflib import BNode, Dataset, Graph, Literal, URIRef
from rdflib.compare import graph_diff, isomorphic
from rdflib.query import ResultRow

from rdf_persistence.domain.exceptions import BadQuery, Conflict, DatabaseGone, NotFound
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services.store import Store

EX = "http://example.org/"
A, B, P, G, OTHER = (URIRef(f"{EX}{n}") for n in ("a", "b", "p", "g", "other"))
ASK_TRIPLE = "ASK { GRAPH $graph { $s $p $o } }"
INSERT = "INSERT DATA { GRAPH $graph { $s $p $o } }"
GUARDED_BUMP = """
DELETE { GRAPH $graph { $s $p ?old } }
INSERT { GRAPH $graph { $s $p $new } }
WHERE { GRAPH $graph { $s $p ?old . FILTER(?old = $expected) } }
"""

Case = Callable[[Store, str], Awaitable[None]]


def triple_text(template: str, obj: Literal | URIRef, graph: URIRef = G) -> str:
    """Fill a template that uses ``$graph``, ``$s``, ``$p`` and ``$o`` with the suite's terms."""
    return fill(template, graph=term(graph), s=term(A), p=term(P), o=term(obj))


async def _holds(store: Store, dataset: str, obj: Literal | URIRef, graph: URIRef = G) -> bool:
    return bool((await store.query(dataset, triple_text(ASK_TRIPLE, obj, graph))).askAnswer)


async def create_list_and_drop(store: Store, dataset: str) -> None:
    name = f"{dataset}-second"
    await store.create_dataset(name)
    assert name in await store.list_datasets(), "created"
    await store.drop_dataset(name)
    assert name not in await store.list_datasets(), "dropped"


async def create_existing_is_conflict(store: Store, dataset: str) -> None:
    with pytest.raises(Conflict):
        await store.create_dataset(dataset)


async def drop_missing_is_not_found(store: Store, dataset: str) -> None:
    with pytest.raises(NotFound):
        await store.drop_dataset(f"{dataset}-missing")


async def update_then_ask(store: Store, dataset: str) -> None:
    obj = Literal('a "quoted"\nvalue\\')
    assert not await _holds(store, dataset, obj), "absent before"
    await store.update(dataset, triple_text(INSERT, obj))
    assert await _holds(store, dataset, obj), "present after"


async def select_returns_rdflib_terms(store: Store, dataset: str) -> None:
    await store.update(dataset, triple_text(INSERT, Literal(7)))
    result = await store.query(dataset, "SELECT ?s ?o WHERE { GRAPH ?g { ?s ?p ?o } }")
    rows = [(row.s, row.o) for row in cast(Iterable[ResultRow], result)]
    assert rows == [(A, Literal(7))]


async def construct_returns_a_graph(store: Store, dataset: str) -> None:
    await store.update(dataset, triple_text(INSERT, B))
    result = await store.query(dataset, "CONSTRUCT { ?s ?p ?o } WHERE { GRAPH ?g { ?s ?p ?o } }")
    expected = Graph()
    expected.add((A, P, B))
    assert result.graph is not None, "a CONSTRUCT carries a graph"
    assert isomorphic(result.graph, expected), graph_diff(result.graph, expected)


async def put_graph_replaces_the_named_graph_and_only_it(store: Store, dataset: str) -> None:
    await store.update(dataset, triple_text(INSERT, Literal("old")))
    await store.update(dataset, triple_text(INSERT, Literal("elsewhere"), graph=OTHER))
    replacement = Graph()
    replacement.add((A, P, Literal("new")))
    await store.put_graph(dataset, G, replacement)
    assert await _holds(store, dataset, Literal("new")), "replacement present"
    assert not await _holds(store, dataset, Literal("old")), "old content gone"
    assert await _holds(store, dataset, Literal("elsewhere"), graph=OTHER), "other graph kept"


async def graph_iri_with_reserved_characters_is_one_graph(store: Store, dataset: str) -> None:
    graph_iri = URIRef(f"{EX}g?x=1&y=2#z")
    replacement = Graph()
    replacement.add((A, P, Literal("v")))
    await store.put_graph(dataset, graph_iri, replacement)
    assert await _holds(store, dataset, Literal("v"), graph=graph_iri)


async def datasets_are_isolated(store: Store, dataset: str) -> None:
    other = f"{dataset}-other"
    await store.create_dataset(other)
    await store.update(dataset, triple_text(INSERT, B))
    assert not await _holds(store, other, B), "the other dataset stays empty"


async def malformed_query_is_bad_query(store: Store, dataset: str) -> None:
    with pytest.raises(BadQuery):
        await store.query(dataset, "SELEKT nothing")


async def malformed_update_is_bad_query(store: Store, dataset: str) -> None:
    with pytest.raises(BadQuery):
        await store.update(dataset, "INSERT nothing")


async def guarded_update_that_matches_changes_the_data(store: Store, dataset: str) -> None:
    await store.update(dataset, triple_text(INSERT, Literal("1")))
    await store.update(dataset, _bump(expected="1", new="2"))
    assert await _holds(store, dataset, Literal("2")), "new token present"
    assert not await _holds(store, dataset, Literal("1")), "old token gone"


async def guarded_update_that_matches_nothing_changes_nothing(store: Store, dataset: str) -> None:
    await store.update(dataset, triple_text(INSERT, Literal("1")))
    await store.update(dataset, _bump(expected="9", new="2"))
    assert not await _holds(store, dataset, Literal("2")), "ASK reports the guard lost"
    assert await _holds(store, dataset, Literal("1")), "old token kept"


def _bump(expected: str, new: str) -> str:
    return fill(
        GUARDED_BUMP,
        graph=term(G),
        s=term(A),
        p=term(P),
        new=term(Literal(new)),
        expected=term(Literal(expected)),
    )


async def _dropped(store: Store, dataset: str) -> str:
    name = f"{dataset}-dropped"
    await store.create_dataset(name)
    await store.drop_dataset(name)
    return name


async def query_on_a_dropped_dataset_is_gone(store: Store, dataset: str) -> None:
    with pytest.raises(DatabaseGone):
        await store.query(await _dropped(store, dataset), "ASK {}")


async def update_on_a_dropped_dataset_is_gone(store: Store, dataset: str) -> None:
    with pytest.raises(DatabaseGone):
        await store.update(await _dropped(store, dataset), "CLEAR ALL")


async def put_graph_on_a_dropped_dataset_is_gone(store: Store, dataset: str) -> None:
    with pytest.raises(DatabaseGone):
        await store.put_graph(await _dropped(store, dataset), G, Graph())


def _two_graphs() -> Dataset:
    """Two named graphs: language-tagged and typed literals; a blank node subject of two triples."""
    data = Dataset()
    first, second = data.graph(G), data.graph(OTHER)
    first.add((A, P, Literal("bonjour", lang="fr")))
    first.add((A, P, Literal(7)))
    node = BNode()
    second.add((node, P, B))
    second.add((node, P, Literal("x")))
    return data


async def export_then_import_round_trips_every_named_graph(store: Store, dataset: str) -> None:
    source, copy = _two_graphs(), f"{dataset}-copy"
    for graph in source.graphs():
        await store.put_graph(dataset, cast(URIRef, graph.identifier), graph)
    await store.create_dataset(copy)
    await store.import_quads(copy, await store.export_quads(dataset))
    restored = Dataset()
    restored.parse(data=await store.export_quads(copy), format="nquads")
    for graph in source.graphs():
        assert isomorphic(restored.graph(graph.identifier), graph), graph.identifier
    assert len(restored.default_graph) == 0, "no default-graph triple"
    blank = {s for s in restored.graph(OTHER).subjects() if isinstance(s, BNode)}
    assert len(blank) == 1, "the blank node still links its two triples"


async def export_of_a_dropped_dataset_is_gone(store: Store, dataset: str) -> None:
    with pytest.raises(DatabaseGone):
        await store.export_quads(await _dropped(store, dataset))


async def import_into_a_dropped_dataset_is_gone(store: Store, dataset: str) -> None:
    with pytest.raises(DatabaseGone):
        await store.import_quads(await _dropped(store, dataset), b"")


CASES: tuple[Case, ...] = (
    create_list_and_drop,
    create_existing_is_conflict,
    drop_missing_is_not_found,
    update_then_ask,
    select_returns_rdflib_terms,
    construct_returns_a_graph,
    put_graph_replaces_the_named_graph_and_only_it,
    graph_iri_with_reserved_characters_is_one_graph,
    datasets_are_isolated,
    malformed_query_is_bad_query,
    malformed_update_is_bad_query,
    guarded_update_that_matches_changes_the_data,
    guarded_update_that_matches_nothing_changes_nothing,
    query_on_a_dropped_dataset_is_gone,
    update_on_a_dropped_dataset_is_gone,
    put_graph_on_a_dropped_dataset_is_gone,
    export_then_import_round_trips_every_named_graph,
    export_of_a_dropped_dataset_is_gone,
    import_into_a_dropped_dataset_is_gone,
)


async def run_case(case: Case, store: Store) -> None:
    """Run one case in a fresh dataset, then drop it and every ``<dataset>-*`` the case left."""
    dataset = f"conf-{uuid.uuid4().hex}"
    await store.create_dataset(dataset)
    try:
        await case(store, dataset)
    finally:
        for name in await store.list_datasets():
            if name.startswith(dataset):
                await store.drop_dataset(name)

"""The Store conformance suite against a real Fuseki; the same cases run on the fake."""

import pytest
from rdflib import Literal, URIRef

from rdf_persistence.core.domain.sparql import fill, term
from rdf_persistence.persistence.services.store import Store
from rdf_persistence.testkit.store_conformance import (
    ASK_TRIPLE,
    CASES,
    INSERT,
    OTHER,
    A,
    G,
    P,
    run_case,
    triple_text,
)

# The write goes to $graph; the guard reads $other, a graph the request does not write.
GUARD_READS_OTHER = """
INSERT { GRAPH $graph { $s $p $o } }
WHERE { GRAPH $other { $s $p ?seen } }
"""
GUARD_FINDS_NONE_IN_OTHER = """
INSERT { GRAPH $graph { $s $p $o } }
WHERE { FILTER NOT EXISTS { GRAPH $other { $s $p ?seen } } }
"""


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__)
async def test_fuseki_conforms(case, store):
    await run_case(case, store)


def guarded(template: str, obj: Literal) -> str:
    """A write of ``obj`` into ``G``, guarded by what ``OTHER`` holds."""
    return fill(template, graph=term(G), other=term(OTHER), s=term(A), p=term(P), o=term(obj))


async def written(store: Store, dataset: str, obj: Literal, graph: URIRef = G) -> bool:
    text = triple_text(ASK_TRIPLE, obj, graph)
    return bool((await store.query(dataset, text)).askAnswer)


async def a_guard_reads_a_graph_the_request_does_not_write(store: Store, dataset: str) -> None:
    """A request that writes one graph is guarded by what another graph holds when it is applied
    (dependent-aggregates RISK-1, A-13): the positive form (the whole exists), the negative one (no
    late part exists), each both ways."""
    first, second, free, late = (Literal(n) for n in ("first", "second", "free", "late"))
    await store.update(dataset, guarded(GUARD_READS_OTHER, first))
    assert not await written(store, dataset, first), "the other graph is empty: nothing written"
    await store.update(dataset, guarded(GUARD_FINDS_NONE_IN_OTHER, free))
    assert await written(store, dataset, free), "nothing in the other graph: written"
    await store.update(dataset, triple_text(INSERT, Literal("held"), OTHER))
    await store.update(dataset, guarded(GUARD_READS_OTHER, second))
    assert await written(store, dataset, second), "the other graph holds the pattern: written"
    await store.update(dataset, guarded(GUARD_FINDS_NONE_IN_OTHER, late))
    assert not await written(store, dataset, late), "a late triple in the other graph: not written"
    assert await written(store, dataset, Literal("held"), OTHER), "the guard's graph is untouched"


async def test_fuseki_a_guard_reads_a_graph_the_request_does_not_write(store):
    await run_case(a_guard_reads_a_graph_the_request_does_not_write, store)

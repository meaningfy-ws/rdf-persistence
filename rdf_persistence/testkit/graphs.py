"""Graph comparison for tests, in the library so that using it needs no generator (D-10).

``assert_isomorphic`` needs ``rdflib`` only; the round trip that ends with it lives in
``rdf_persistence_generation.testkit.roundtrip``, which imports it from here.
"""

from rdflib import Graph
from rdflib.compare import graph_diff, isomorphic


def assert_isomorphic(before: Graph, after: Graph) -> None:
    """Fail, with the triples only one side has, when the two graphs are not isomorphic.

    Raises:
        AssertionError: When the graphs differ.
    """
    assert isomorphic(before, after), (
        "the two graphs differ:\n"
        f"only before: {sorted(graph_diff(before, after)[1])}\n"
        f"only after: {sorted(graph_diff(before, after)[2])}"
    )

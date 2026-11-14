"""Adversarial tests of the stamps graph in a dump and its restore (schema-migrations PD-15, RISK-3)."""

import pytest
from rdflib import Dataset, Literal, URIRef

from rdf_persistence.domain.exceptions import InvalidBody
from rdf_persistence.domain.iris import Iris, stamps_graph_iri
from rdf_persistence.domain.tenant_move import check_graphs, rewrite
from rdf_persistence.services import vocabulary as v
from tests.toy import SETTINGS

BASE = SETTINGS.base
STAMPS_GRAPH = stamps_graph_iri(BASE)


def quad_in(graph: str) -> Dataset:
    data = Dataset()
    data.graph(URIRef(graph)).add((URIRef("urn:s"), v.DATA_SCHEMA_VERSION, Literal("1")))
    return data


def test_the_stamps_graph_itself_passes_the_graph_check():
    check_graphs(
        quad_in(str(STAMPS_GRAPH)), "https://example.org/library/libraries/abc", Iris(SETTINGS)
    )


@pytest.mark.parametrize(
    "lookalike",
    [
        f"{STAMPS_GRAPH}/extra",
        f"{STAMPS_GRAPH}2",
        f"{STAMPS_GRAPH}#x",
        f"{STAMPS_GRAPH.rsplit('/', 1)[0]}/schema-stamps-other",
        f"{BASE}libraries/other/schema-stamps",
        f"{BASE}toolkit/schema-stamp",
        f"{BASE}Toolkit/schema-stamps",
    ],
)
def test_a_graph_that_only_looks_like_the_stamps_graph_is_refused(lookalike):
    with pytest.raises(InvalidBody):
        check_graphs(
            quad_in(lookalike), "https://example.org/library/libraries/abc", Iris(SETTINGS)
        )


def test_a_schema_id_holding_the_source_tenants_id_is_not_rewritten_by_the_move():
    """Changed for PD-24.1: a restore now refuses a stamp of a foreign schema, so this attacks ``rewrite`` itself."""
    old_id, new_id = "k3f9a2", "z8y7x6"
    schema = URIRef(f"{BASE}schemas/{old_id}/library")  # under the base, the id a delimited token
    stamp = (schema, v.DATA_SCHEMA_VERSION, Literal("4"))
    data = Dataset()
    data.graph(URIRef(STAMPS_GRAPH)).add(stamp)
    moved = rewrite(data, BASE, old_id, new_id)
    assert set(moved.graph(URIRef(STAMPS_GRAPH))) == {stamp}, "the stamps graph is copied as it is"

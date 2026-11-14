"""Adversarial tests of the stamps graph in a dump and its restore (schema-migrations PD-15, RISK-3)."""

from types import SimpleNamespace

import pytest
from rdflib import Dataset, Literal, URIRef

from rdf_persistence.domain.exceptions import InvalidBody
from rdf_persistence.domain.iris import Iris, stamps_graph_iri
from rdf_persistence.domain.tenant_move import check_graphs
from rdf_persistence.services import vocabulary as v
from tests.toy import SETTINGS
from tests.unit.services.test_tenant_dump import (
    STAMPS,
    dumped,
    iris_of,
    populated,
    restored,
    stamps_held,
)
from tests.unit.services.test_tenant_sweep import make_world

BASE = SETTINGS.base
STAMPS_GRAPH = stamps_graph_iri(BASE)


@pytest.fixture
async def world() -> SimpleNamespace:
    return await populated(await make_world(iris_of(SETTINGS), SETTINGS, stamps=STAMPS))


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


async def test_a_schema_id_holding_the_source_tenants_id_is_not_rewritten_by_a_restore(world):
    token = world.iris.tenant_id_of(world.tenant)
    schema = f"{BASE}schemas/{token}/library"  # under the base, with the id as a delimited token
    await world.store.update(
        world.database,
        f'INSERT DATA {{ GRAPH <{STAMPS_GRAPH}> {{ <{schema}> <{v.DATA_SCHEMA_VERSION}> "4" }} }}',
    )
    before = await stamps_held(world, world.tenant)
    summary = await restored(world, await dumped(world))
    assert await stamps_held(world, summary.id) == before, "the restored tenant keeps its stamps"

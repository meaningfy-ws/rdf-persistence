"""The tenant root is found whatever string type the tenant IRI arrives in (issue #76, PD-12)."""

from datetime import UTC, datetime

import pytest
from rdflib import Literal, URIRef

from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE

TENANT = "https://example.org/libraries/6f1c0c1e"
TITLE = URIRef("http://purl.org/dc/terms/title")
ROOT_TRIPLES = [(URIRef(TENANT), TITLE, Literal("Ghent"))]
HAS_AGGREGATE_ENTRY = "ASK { GRAPH $r { ?g $kind $aggregate } }"


@pytest.fixture
async def store():
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


def opened(store, tenant):
    return fake_session(
        store,
        tenant_iri=tenant,
        principal=Principal(id="https://example.org/people/ada"),
        clock=lambda: datetime(2026, 11, 13, tzinfo=UTC),
    )


async def test_tc00a_a_uriref_tenant_stores_the_root_in_meta_without_an_aggregate_entry(store):
    async with opened(store, URIRef(TENANT)) as session:
        await session.add_graph(TENANT, ROOT_TRIPLES)
    in_meta = fill("ASK { GRAPH $g { ?s ?p ?o } }", g=term(DEFAULT_IRIS.meta(TENANT)))
    assert (await store.query(FAKE_DATABASE, in_meta)).askAnswer, "the root is in the meta graph"
    entry = fill(
        HAS_AGGREGATE_ENTRY,
        r=term(DEFAULT_IRIS.registry(TENANT)),
        kind=term(v.REGISTRY_KIND),
        aggregate=term(v.REGISTRY_KIND_IRIS["aggregate"]),
    )
    assert not (await store.query(FAKE_DATABASE, entry)).askAnswer, "no aggregate entry"


async def test_tc00b_a_str_tenant_reads_the_root_given_as_a_uriref(store):
    async with opened(store, URIRef(TENANT)) as writer:
        await writer.add_graph(TENANT, ROOT_TRIPLES)
    async with opened(store, TENANT) as reader:
        graph, graph_iri, _version = await reader.get_graph(URIRef(TENANT))
    assert graph_iri == DEFAULT_IRIS.meta(TENANT)
    assert (URIRef(TENANT), TITLE, Literal("Ghent")) in graph

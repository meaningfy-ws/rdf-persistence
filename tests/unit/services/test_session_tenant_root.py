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


# both ways a tenant IRI and a root IRI can arrive: as a str, or as a URIRef (which never equals a str)
PAIRINGS = [
    pytest.param(str, str, id="str-tenant-str-root"),
    pytest.param(str, URIRef, id="str-tenant-uriref-root"),
    pytest.param(URIRef, str, id="uriref-tenant-str-root"),
    pytest.param(URIRef, URIRef, id="uriref-tenant-uriref-root"),
]


@pytest.mark.parametrize(("tenant_type", "root_type"), PAIRINGS)
async def test_tc00a_the_root_is_stored_in_meta_without_an_aggregate_entry(
    store, tenant_type, root_type
):
    async with opened(store, tenant_type(TENANT)) as session:
        await session.add_graph(root_type(TENANT), ROOT_TRIPLES)
    in_meta = fill("ASK { GRAPH $g { ?s ?p ?o } }", g=term(DEFAULT_IRIS.meta(TENANT)))
    assert (await store.query(FAKE_DATABASE, in_meta)).askAnswer, "the root is in the meta graph"
    entry = fill(
        HAS_AGGREGATE_ENTRY,
        r=term(DEFAULT_IRIS.registry(TENANT)),
        kind=term(v.REGISTRY_KIND),
        aggregate=term(v.REGISTRY_KIND_IRIS["aggregate"]),
    )
    assert not (await store.query(FAKE_DATABASE, entry)).askAnswer, "no aggregate entry"


@pytest.mark.parametrize(("tenant_type", "root_type"), PAIRINGS)
async def test_tc00b_a_session_reads_the_root_whatever_the_types_of_tenant_and_root(
    store, tenant_type, root_type
):
    async with opened(store, URIRef(TENANT)) as writer:
        await writer.add_graph(TENANT, ROOT_TRIPLES)
    async with opened(store, tenant_type(TENANT)) as reader:
        graph, graph_iri, _version = await reader.get_graph(root_type(TENANT))
    assert graph_iri == DEFAULT_IRIS.meta(TENANT), "the root's graph is the meta graph"
    assert (URIRef(TENANT), TITLE, Literal("Ghent")) in graph, "with the root's triples"


@pytest.mark.parametrize(("tenant_type", "root_type"), PAIRINGS)
async def test_tc00c_a_transaction_replaces_the_root_whatever_the_types(
    store, tenant_type, root_type
):
    async with opened(store, tenant_type(TENANT)) as session:
        version = await session.add_graph(root_type(TENANT), ROOT_TRIPLES)
        async with session.transaction() as transaction:
            await transaction.replace_graph(
                root_type(TENANT), [(URIRef(TENANT), TITLE, Literal("Bruges"))], version
            )
        graph, _, _ = await session.get_graph(root_type(TENANT))
    assert (URIRef(TENANT), TITLE, Literal("Bruges")) in graph, "the root was replaced"

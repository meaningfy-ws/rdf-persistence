"""Tenancy against a real Fuseki and the parametrised file store: create then delete, a grant is ODRL."""

from rdflib import RDF, Literal, URIRef
from rdflib.namespace import Namespace

from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import access_iri, tenant_resource_name
from rdf_persistence.services.session import open_session
from tests.toy import ADA, library

ODRL = Namespace("http://www.w3.org/ns/odrl/2/")
RP = Namespace("https://meaningfy.ws/ns/rdf-persistence#")
CREATOR = Principal(id=ADA)


async def access_graph(store, settings, tenant: str):
    async with open_session(
        store, database=f"{settings.prefix}-system", tenant_iri=tenant, principal=CREATOR
    ) as session:
        graph, _ = await session.get_graph(str(access_iri(tenant)))
    return graph


async def test_create_then_delete_leaves_no_database_no_bucket_and_no_record(
    tenancy, store, files, settings
):
    summary = await tenancy.create("Ghent", library(), CREATOR)
    name = tenant_resource_name(settings.prefix, summary.id)
    assert name in await store.list_datasets(), "the database exists after create"
    assert await files.list_buckets(name) == [name], "the bucket exists after create"
    assert [t.id for t in await tenancy.tenants()] == [summary.id], "the record exists after create"
    _, version = await tenancy.get(summary.id)
    await tenancy.delete(summary.id, version)
    assert name not in await store.list_datasets(), "database"
    assert await files.list_buckets(name) == [], "bucket"
    assert await tenancy.tenants() == [], "access record"


async def test_a_grant_is_an_odrl_permission_of_the_creator_on_the_tenant(tenancy, store, settings):
    summary = await tenancy.create("Ghent", library(), CREATOR)
    graph = await access_graph(store, settings, summary.id)
    permissions = list(graph.subjects(RDF.type, ODRL.Permission))
    assert len(permissions) == 1, "one permission, the creator's"
    assert set(graph.predicate_objects(permissions[0])) == {
        (RDF.type, ODRL.Permission),
        (ODRL.assignee, URIRef(ADA)),
        (ODRL.target, URIRef(summary.id)),
        (RP.role, Literal("librarian")),
    }, "an odrl:Permission with the principal, the tenant and the role"


async def test_the_access_record_owns_the_grant(tenancy, store, settings):
    summary = await tenancy.create("Ghent", library(), CREATOR)
    graph = await access_graph(store, settings, summary.id)
    permission = next(graph.subjects(RDF.type, ODRL.Permission))
    assert (URIRef(access_iri(summary.id)), RP.grant, permission) in graph


ASK_CITY = "ASK { GRAPH ?g { ?s <http://schema.org/addressLocality> '%s' } }"


async def test_a_tenant_database_holds_only_its_own_root_object(tenancy, store, settings):
    ghent = await tenancy.create("Ghent", library(city="Ghent"), CREATOR)
    await tenancy.create("Bruges", library(city="Bruges"), CREATOR)
    name = tenant_resource_name(settings.prefix, ghent.id)
    held = [
        bool((await store.query(name, ASK_CITY % city)).askAnswer) for city in ("Ghent", "Bruges")
    ]
    assert held == [True, False], "Ghent's database has Ghent and not Bruges"

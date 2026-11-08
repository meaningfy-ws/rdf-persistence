"""The consumer's tenant end to end over the fakes (iri-policy task 5.1, PD-3a, PD-10, PD-12a).

Access record ``{base}{deployment}/project/{tenant_id}``; meta and registry graphs under templates of
their own. Nothing is read or written at the default ``{tenant}/access|meta|registry``.
"""

import re
from uuid import uuid4

from rdflib import URIRef

from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.domain.iris import Iris, system_database_name
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services.access import AccessRules, load_caller_access, load_role_definitions
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, BOB, ROLES, caller, library_slots, toy_mapper

BASE = "http://mwb.meaningfy.ws/"
CREATOR = Principal(id=ADA)
ACCESS = "{base}{deployment}/project/{tenant_id}"
META = "{base}{deployment}/meta/{tenant_id}"
REGISTRY = "{base}{deployment}/registry/{tenant_id}"
SETTINGS = ServiceSettings(
    base=BASE,
    prefix="mwb",
    tenant_segment="projects",
    creator_role="librarian",
    roles_claim="roles",
    deployment="k3f9a2x",
    iri_policy=IriPolicy(
        tenant_template="{base}project/{tenant_id}",
        access_template=ACCESS,
        meta_template=META,
        registry_template=REGISTRY,
        tenant_id=IdSpec(kind=IdKind.RANDOM, length=7),
    ),
)
SYSTEM = system_database_name(SETTINGS.prefix)
ASK = "ASK { GRAPH $g { ?s ?p ?o } }"


async def holds(store: FakeStore, database: str, graph: URIRef) -> bool:
    return bool((await store.query(database, fill(ASK, g=term(graph)))).askAnswer)


async def tenancy_of(store: FakeStore, iris: Iris) -> Tenancy:
    made = Tenancy(
        store,
        FakeFileStore(),
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        iris=iris,
    )
    await made.ensure_system_database()
    return made


async def test_the_consumers_tenant_is_created_read_listed_and_deleted_by_the_policy():
    store, iris = FakeStore(), Iris(SETTINGS)
    tenancy = await tenancy_of(store, iris)
    rules = AccessRules(load_role_definitions(ROLES), iris)

    summary = await tenancy.create("Ghent", library_slots(), CREATOR)

    assert re.fullmatch(rf"{BASE}project/[a-z0-9]{{7}}", summary.id), "the tenant IRI"
    tenant_id = summary.id.rsplit("/", 1)[-1]
    record, version = await tenancy.get(summary.id)
    assert record.id == f"{BASE}k3f9a2x/project/{tenant_id}", "the access record"
    assert record.database_name == f"mwb-t-{tenant_id}"
    page = await tenancy.visible_tenants(caller(), rules, limit=10, offset=0)
    assert [item.id for item in page.items] == [summary.id], "listed through tenant_of_access"
    assert await tenancy.tenants() == [summary]

    await tenancy.delete(summary.id, version)
    assert await tenancy.tenants() == []
    assert not await holds(store, SYSTEM, URIRef(f"{record.id}/graph")), "the record is gone"


async def test_a_callers_access_is_found_at_the_policys_access_iri():
    store, iris = FakeStore(), Iris(SETTINGS)
    tenancy = await tenancy_of(store, iris)
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)

    found = await load_caller_access(store, SYSTEM, summary.id, ADA, iris=iris)

    assert found.state == TenantState.ACTIVE
    assert [grant.assignee for grant in found.grants or []] == [ADA]
    assert (await load_caller_access(store, SYSTEM, summary.id, BOB, iris=iris)).grants is None


async def test_the_root_and_the_registry_sit_in_the_graphs_the_policy_names():
    store, iris = FakeStore(), Iris(SETTINGS)
    tenancy = await tenancy_of(store, iris)
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    database = iris.resource_name(summary.id)

    async with tenancy.tenant_session(summary.id, CREATOR) as session:
        graph, _, _ = await session.get_graph(summary.id)
    assert graph, "the root reads back"
    assert await holds(store, database, iris.meta(summary.id))
    assert not await holds(store, database, URIRef(f"{summary.id}/meta"))

    async with tenancy.tenant_session(summary.id, CREATOR) as session:
        await session.add_graph(str(iris.aggregate(summary.id, "", "books", str(uuid4()))), [])
    assert await holds(store, database, iris.registry(summary.id)), "the entry is in the registry"
    assert not await holds(store, database, URIRef(f"{summary.id}/registry"))

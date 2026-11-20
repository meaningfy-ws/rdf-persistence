"""A dump of a tenant at toolkit version 2 holding a reference collection is restored with its members (collection-has-part TC-10).

The shelf of the dump states its members with ``prov:hadMember``, as the toolkit's version 2 stored them. The restore
runs the toolkit's chain first; the restored tenant states ``dcterms:hasPart`` and the collection service lists them.
"""

from types import SimpleNamespace

import pytest
from rdflib import Literal, URIRef

from rdf_persistence import generated_models
from rdf_persistence.access.domain.generated.rp_tenancy import TenantState
from rdf_persistence.access.services.access import AccessRules, load_role_definitions
from rdf_persistence.access.services.generated.rp_access_services import CallerAccess, Grant
from rdf_persistence.collaboration.services.collaboration import Collaboration
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.tenancy.services.tenancy import Tenancy
from tests.fixtures.library.domain.generated.library import Library
from tests.fixtures.library.domain.generated.library_access import LibraryAccess
from tests.toy import (
    MODULES,
    ROLES,
    SETTINGS,
    TOY_SCHEMA,
    caller,
    dune,
    shelf,
    toy_mapper,
)
from tests.unit.tenancy.test_tenant_dump import (
    BOB,
    LIBRARY_SCHEMA,
    RESTORER,
    TOOLKIT_SCHEMA,
    TOY_CHAINS,
    VIEW,
    dumped,
    iris_of,
    make_world,
    manifest_of,
    moved,
    populated,
    restored,
    stamps_held,
)

HAD_MEMBER = URIRef("http://www.w3.org/ns/prov#hadMember")
HAS_PART = URIRef("http://purl.org/dc/terms/hasPart")
VERSION_TWO = "2"
RUNNING_TOOLKIT_VERSION = "3"


@pytest.fixture
async def world_at_toolkit_two() -> SimpleNamespace:
    """A tenant stamped toolkit ``2`` with a shelf of two books, the shelf stating its members with ``prov:hadMember``."""
    world = await populated(
        await make_world(
            iris_of(SETTINGS),
            SETTINGS,
            stamps=((TOOLKIT_SCHEMA, VERSION_TWO), (LIBRARY_SCHEMA, "1")),
        )
    )
    tenant, iris = world.tenant, world.iris
    world.b1, world.b2 = (str(iris.mint_aggregate(tenant, "book", "books")) for _ in range(2))
    world.shelf = str(iris.mint_aggregate(tenant, "shelf", "shelves"))
    async with world.session() as opened:
        for book in (world.b1, world.b2):
            await opened.add_graph(book, toy_mapper().to_triples(dune(book, chapters=1)))
        stored = [
            *toy_mapper().to_triples(shelf(world.shelf)),
            *[(URIRef(world.shelf), HAD_MEMBER, URIRef(b)) for b in (world.b1, world.b2)],
        ]
        await opened.add_graph(world.shelf, stored)
    world.running = Tenancy(
        world.store, world.files, SETTINGS, mapper=toy_mapper(), root_class=Library,
        access_class=LibraryAccess, iris=iris,
        stamps=((TOOLKIT_SCHEMA, RUNNING_TOOLKIT_VERSION), (LIBRARY_SCHEMA, "1")),
    )  # fmt: skip
    return world


async def test_a_dump_at_toolkit_version_two_is_restored_with_the_members_of_its_collection(
    world_at_toolkit_two,
):
    world = world_at_toolkit_two
    data = await dumped(world, view=VIEW)
    assert manifest_of(data).schema_version == "1", "the manifest carries the library's stamp"
    summary = await restored(world, data, tenancy=world.running, view=VIEW, chains=TOY_CHAINS)
    assert await stamps_held(world, summary.id) == {
        TOOLKIT_SCHEMA: RUNNING_TOOLKIT_VERSION,
        LIBRARY_SCHEMA: "1",
    }, "the restored tenant is at toolkit version 3"
    new_shelf = moved(world, world.shelf, summary.id)
    members = {URIRef(moved(world, b, summary.id)) for b in (world.b1, world.b2)}
    async with world.tenancy.tenant_session(summary.id, RESTORER) as opened:
        graph, _, _ = await opened.get_graph(new_shelf)
    stated = {o for _, p, o in graph if p == HAS_PART}
    assert stated == members, "the restored shelf states dcterms:hasPart for b1 and b2"
    assert not [t for t in graph if t[1] == HAD_MEMBER], "and no prov:hadMember"
    assert Literal("Book") in {o for _, _, o in graph}, "its member class is kept"
    async with world.tenancy.tenant_session(summary.id, RESTORER) as opened:
        found = await collaboration_over(opened, summary.id).members(new_shelf)
    assert found.member_iris == sorted(map(str, members)), "members(s1) lists b1 and b2"


def collaboration_over(session, tenant: str) -> Collaboration:
    """A ``Collaboration`` of a librarian over the restored tenant, built as ``ServiceKit.collaboration`` builds it."""
    view = load_schema(TOY_SCHEMA)
    access = CallerAccess(
        tenant=tenant,
        state=TenantState.ACTIVE,
        grants=[Grant(assignee=BOB, target=tenant, role="librarian")],
    )
    return Collaboration(
        session,
        view=view,
        rules=AccessRules(load_role_definitions(ROLES)),
        iris=iris_of(SETTINGS),
        mapper=toy_mapper(),
        models=generated_models(*MODULES),
        listings=Listings(view),
        caller=caller(principal=BOB),
        access=access,
    )

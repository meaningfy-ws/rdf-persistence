"""A session carries the read check its caller opened it with (aggregate-validators PD-4).

The session itself checks nothing with it: the reader of the collaboration layer does.
"""

from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.persistence.services.session import open_session
from rdf_persistence.testkit import FakeStore
from tests.tenancy_world import CREATOR, NOW, make_world
from tests.toy import SETTINGS

TENANT = "https://example.org/libraries/6f1c0c1e"


def may_read_nothing(iri: str) -> bool:
    return False


def open_with(**extra):
    return open_session(
        FakeStore(),
        database="db",
        tenant_iri=TENANT,
        principal=CREATOR,
        clock=lambda: NOW,
        **extra,
    )


async def test_a_session_opened_with_may_read_exposes_it():
    async with open_with(may_read=may_read_nothing) as session:
        assert session.may_read is may_read_nothing


async def test_a_session_opened_without_may_read_exposes_none():
    async with open_with() as session:
        assert session.may_read is None


async def test_a_tenant_session_opened_with_may_read_hands_it_to_the_session():
    world = await make_world(Iris(SETTINGS), SETTINGS)
    async with world.tenancy.tenant_session(
        world.tenant, CREATOR, may_read=may_read_nothing
    ) as session:
        assert session.may_read is may_read_nothing


async def test_a_tenant_session_opened_without_may_read_exposes_none():
    world = await make_world(Iris(SETTINGS), SETTINGS)
    async with world.tenancy.tenant_session(world.tenant, CREATOR) as session:
        assert session.may_read is None

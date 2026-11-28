"""A session carries the links of dependence and the root limit it was opened with (dependent-aggregates PD-2, PD-6).

Only the wiring: the session stores them and refuses links without a limit (A-8); the checks that
use them come with the write guard and the cascade.
"""

import pytest

from rdf_persistence.core.domain.generated.rp_core import DependenceLink
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.persistence.services.session import Session, open_session
from rdf_persistence.tenancy.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore, fake_session
from tests.fixtures.library.domain.generated.library import Library
from tests.fixtures.library.domain.generated.library_access import LibraryAccess
from tests.tenancy_world import CREATOR, NOW
from tests.toy import SETTINGS, library_slots, toy_mapper, toy_rules

TENANT = "https://example.org/libraries/6f1c0c1e"
LINK = DependenceLink(
    part_classes=["https://example.org/Audit"],
    pointer="https://example.org/ofAudit",
    whole_classes=["https://example.org/Report"],
)
MAX_ROOTS = 7


def open_with(**extra):
    return open_session(
        FakeStore(),
        database="db",
        tenant_iri=TENANT,
        principal=CREATOR,
        clock=lambda: NOW,
        **extra,
    )


async def make_tenancy(**extra) -> Tenancy:
    tenancy = Tenancy(
        FakeStore(),
        FakeFileStore(lambda: NOW),
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        rules=toy_rules(),
        iris=Iris(SETTINGS),
        **extra,
    )
    await tenancy.ensure_system_database()
    return tenancy


@pytest.mark.parametrize(
    ("given", "dependence", "max_roots"),
    [
        pytest.param({}, (), None, id="nothing given"),
        pytest.param({"max_roots": MAX_ROOTS}, (), MAX_ROOTS, id="a limit alone"),
        pytest.param(
            {"dependence": [LINK], "max_roots": MAX_ROOTS},
            (LINK,),
            MAX_ROOTS,
            id="links with a limit",
        ),
    ],
)
async def test_a_session_keeps_what_it_was_opened_with(given, dependence, max_roots):
    async with open_with(**given) as session:
        assert session.dependence == dependence, "the links, as a tuple"
        assert session.max_roots == max_roots, "the limit as given"


async def test_links_without_a_limit_are_refused_by_the_constructor():
    with pytest.raises(ValueError, match="max_roots"):
        Session(
            FakeStore(),
            database="db",
            tenant_iri=TENANT,
            principal=CREATOR,
            clock=lambda: NOW,
            dependence=[LINK],
        )


async def test_links_without_a_limit_are_refused_when_opening():
    with pytest.raises(ValueError, match="max_roots"):
        async with open_with(dependence=[LINK]):
            pytest.fail("a session must not open")


async def test_the_testkit_session_passes_both_on():
    async with fake_session(dependence=[LINK], max_roots=MAX_ROOTS) as session:
        assert session.dependence == (LINK,), "the links reach the session"
        assert session.max_roots == MAX_ROOTS, "the limit reaches the session"


async def test_the_testkit_session_refuses_links_without_a_limit():
    with pytest.raises(ValueError, match="max_roots"):
        async with fake_session(dependence=[LINK]):
            pytest.fail("a session must not open")


async def test_a_tenant_session_carries_what_the_tenancy_was_given():
    tenancy = await make_tenancy(dependence=[LINK], max_roots=MAX_ROOTS)
    tenant = (await tenancy.create("Ghent", library_slots(), CREATOR)).id
    async with tenancy.tenant_session(tenant, CREATOR) as session:
        assert session.dependence == (LINK,), "the tenancy's links"
        assert session.max_roots == MAX_ROOTS, "the tenancy's limit"


async def test_a_tenancy_refuses_links_without_a_limit_when_built():
    with pytest.raises(ValueError, match="max_roots"):
        await make_tenancy(dependence=[LINK])

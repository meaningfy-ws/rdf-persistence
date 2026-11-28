"""A session carries the links of dependence and the limits it was opened with (dependent-aggregates
PD-2, PD-6, D-9).

Only the wiring: the session stores the links and reads the root limit from the given or default
``LimitSettings``, so a cascade is always bounded (A-8); the checks that use them are tested apart.
"""

import pytest

from rdf_persistence.core.domain.generated.rp_core import DependenceLink
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.persistence.services.session import open_session
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
LIMITS = LimitSettings(max_roots=MAX_ROOTS)
DEFAULT_MAX_ROOTS = LimitSettings().max_roots


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
        pytest.param({}, (), DEFAULT_MAX_ROOTS, id="nothing given: the default limit"),
        pytest.param({"limits": LIMITS}, (), MAX_ROOTS, id="limits alone"),
        pytest.param(
            {"dependence": [LINK], "limits": LIMITS}, (LINK,), MAX_ROOTS, id="links with limits"
        ),
        pytest.param(
            {"dependence": [LINK]}, (LINK,), DEFAULT_MAX_ROOTS, id="links, the default limit"
        ),
    ],
)
async def test_a_session_keeps_what_it_was_opened_with(given, dependence, max_roots):
    async with open_with(**given) as session:
        assert session.dependence == dependence, "the links, as a tuple"
        assert session.max_roots == max_roots, "the limit of the given or default settings"


async def test_the_testkit_session_passes_both_on():
    async with fake_session(dependence=[LINK], limits=LIMITS) as session:
        assert session.dependence == (LINK,), "the links reach the session"
        assert session.max_roots == MAX_ROOTS, "the limits reach the session"


async def test_a_tenant_session_carries_what_the_tenancy_was_given():
    tenancy = await make_tenancy(dependence=[LINK], limits=LIMITS)
    tenant = (await tenancy.create("Ghent", library_slots(), CREATOR)).id
    async with tenancy.tenant_session(tenant, CREATOR) as session:
        assert session.dependence == (LINK,), "the tenancy's links"
        assert session.max_roots == MAX_ROOTS, "the tenancy's limits"


async def test_a_tenancy_without_limits_gives_its_sessions_the_default():
    tenancy = await make_tenancy(dependence=[LINK])
    tenant = (await tenancy.create("Ghent", library_slots(), CREATOR)).id
    async with tenancy.tenant_session(tenant, CREATOR) as session:
        assert session.max_roots == DEFAULT_MAX_ROOTS, "the default limit"

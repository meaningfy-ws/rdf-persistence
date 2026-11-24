"""The start-up report of grants (grant-roles D-5, DEC-5): T8 the warnings, T8b a failing read never stops start-up."""

import logging
from types import SimpleNamespace

import pytest

from rdf_persistence.access.domain.generated.rp_access import Grant, RoleLevel
from rdf_persistence.access.services.access import AccessRules, load_role_definitions
from rdf_persistence.access.services.generated.rp_access_services import GrantSet
from rdf_persistence.core.domain.exceptions import (
    PersistenceError,
    StoredDataInvalid,
    StoreUnavailable,
)
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.tenancy.services.grant_report import report_grants
from rdf_persistence.tenancy.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.domain.generated.library import Library
from tests.fixtures.library.domain.generated.library_access import LibraryAccess
from tests.logs import attributes, records_of
from tests.toy import ADA, BOB, ROLES, SETTINGS, library_slots, toy_mapper, toy_rules

CREATOR = Principal(id=ADA)
UNDEFINED = "grants name undefined roles"
UNADMINISTERED = "no grant administers the tenant"
STEP = "check-grants"
LIBRARIAN_ONLY = AccessRules(
    [d for d in load_role_definitions(ROLES) if d.role == "librarian" and d.level == RoleLevel.TENANT]
)


async def _tenancy_with_one_tenant() -> tuple[Tenancy, str]:
    """A tenancy with one tenant, holding only the creator's grant."""
    tenancy = Tenancy(
        FakeStore(),
        FakeFileStore(),
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        rules=toy_rules(),
    )
    await tenancy.ensure_system_database()
    tenant = (await tenancy.create("Ghent", library_slots(), CREATOR)).id
    return tenancy, tenant


def _role(role: str, assignee: str, tenant: str) -> Grant:
    return Grant(assignee=assignee, target=tenant, role=role)


def _reported(caplog: pytest.LogCaptureFixture, message: str) -> list[logging.LogRecord]:
    return [r for r in records_of(caplog, STEP) if r.getMessage() == message]


async def test_a_role_the_definitions_lack_is_reported_with_its_tenant_and_pair(caplog):
    tenancy, tenant = await _tenancy_with_one_tenant()
    _, version = await tenancy.get(tenant)
    await tenancy.set_grants(
        tenant,
        GrantSet(grants=[_role("librarian", ADA, tenant), _role("reader", BOB, tenant)]),
        version,
        CREATOR,
    )

    with caplog.at_level(logging.WARNING):
        await report_grants(tenancy, LIBRARIAN_ONLY)

    [record] = _reported(caplog, UNDEFINED)
    logged = attributes(record)
    assert record.levelno == logging.WARNING, "an undefined role is a warning"
    assert logged["rp.tenant.id"] == tenant, "the record names the tenant"
    assert logged["rp.grants.undefined_roles"] == ["tenant:reader"], "it names the level:role pair"
    assert _reported(caplog, UNADMINISTERED) == [], "the librarian still administers"


@pytest.mark.parametrize(
    ("grants", "warned"),
    [
        (None, False),
        ([], True),
        ([("reader", BOB)], True),
        ([("librarian", ADA)], False),
        ([("reader", BOB), ("librarian", ADA)], False),
    ],
    ids=["creator-only", "no-grants", "reader-only", "librarian", "reader-and-librarian"],
)
async def test_a_tenant_no_grant_administers_is_reported_and_one_that_is_administered_is_not(
    caplog, grants, warned
):
    tenancy, tenant = await _tenancy_with_one_tenant()
    if grants is not None:
        _, version = await tenancy.get(tenant)
        await tenancy.set_grants(
            tenant,
            GrantSet(grants=[_role(role, who, tenant) for role, who in grants]),
            version,
            CREATOR,
        )

    with caplog.at_level(logging.WARNING):
        await report_grants(tenancy, toy_rules())

    records = _reported(caplog, UNADMINISTERED)
    assert [attributes(r)["rp.tenant.id"] for r in records] == ([tenant] if warned else []), (
        "the warning names the tenant exactly when no grant administers it"
    )
    assert _reported(caplog, UNDEFINED) == [], "every role is defined"


async def test_a_clean_store_logs_nothing(caplog):
    tenancy, _ = await _tenancy_with_one_tenant()

    with caplog.at_level(logging.DEBUG):
        await report_grants(tenancy, toy_rules())

    assert records_of(caplog, STEP) == [], "nothing to report"


@pytest.mark.parametrize(
    "error",
    [StoreUnavailable("down"), StoredDataInvalid("one record does not decode")],
    ids=["store-down", "record-undecodable"],
)
async def test_a_failed_read_is_logged_at_error_and_never_raised(caplog, error):
    async def fail() -> list:
        raise error

    broken = SimpleNamespace(access_records=fail)

    with caplog.at_level(logging.WARNING):
        await report_grants(broken, toy_rules())  # type: ignore[arg-type]

    [record] = records_of(caplog, STEP)
    assert record.levelno == logging.ERROR, "the failure is an error"
    assert record.exc_info is not None, "with the exception attached"
    assert record.exc_info[1] is error, "and it is the one the store raised"
    assert isinstance(error, PersistenceError), "both failures are persistence errors"

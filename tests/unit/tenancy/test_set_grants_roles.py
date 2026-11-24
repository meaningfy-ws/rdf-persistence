"""``Tenancy.set_grants`` refuses what the grants route refuses, through one validation path (consumer-gap-fixes D-4)."""

import pytest

from rdf_persistence.access.domain.generated.rp_access import (
    Action,
    Grant,
    RoleDefinition,
    RoleLevel,
)
from rdf_persistence.access.services.access import AccessRules, load_role_definitions
from rdf_persistence.access.services.generated.rp_access_services import GrantSet
from rdf_persistence.core.domain.exceptions import (
    InvalidBody,
    InvalidGrant,
    NotFound,
    UnknownRole,
)
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.tenancy.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.domain.generated.library import Library
from tests.fixtures.library.domain.generated.library_access import LibraryAccess
from tests.toy import ADA, BOB, ROLES, SETTINGS, library_slots, toy_mapper, toy_rules
from tests.unit.api.iri_policy_helpers import BASE
from tests.unit.api.iri_policy_helpers import IRIS as FLAT_IRIS

CREATOR = Principal(id=ADA)
GHOST = RoleDefinition(role="ghost", level=RoleLevel.TENANT, actions=[Action.READ])


def _tenancy(store, files, rules: AccessRules | None = None, **options) -> Tenancy:
    return Tenancy(
        store,
        files,
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        rules=rules or toy_rules(),
        **options,
    )


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def files() -> FakeFileStore:
    return FakeFileStore()


async def _made(store, files, **options) -> tuple[Tenancy, str]:
    tenancy = _tenancy(store, files, **options)
    await tenancy.ensure_system_database()
    return tenancy, (await tenancy.create("Ghent", library_slots(), CREATOR)).id


def _grant(tenant: str, role: str, assignee: str = BOB) -> GrantSet:
    return GrantSet(grants=[Grant(assignee=assignee, target=tenant, role=role)])


# E4 an undefined role, E5 a role defined only at system level: refused, nothing written
@pytest.mark.parametrize("role", ["no-such-role", "admin"], ids=["undefined", "system-only"])
async def test_set_grants_refuses_a_role_that_cannot_be_granted_and_writes_nothing(
    store, files, role
):
    tenancy, tenant = await _made(store, files)
    _, version = await tenancy.get(tenant)

    with pytest.raises(UnknownRole):
        await tenancy.set_grants(tenant, _grant(tenant, role), version, CREATOR)

    record, after = await tenancy.get(tenant)
    assert after == version, "the record version is unchanged"
    assert [g.assignee for g in record.grants or []] == [ADA], "the stored grants are unchanged"


async def test_a_refused_role_never_reaches_the_grant_validators(store, files):
    called: list[int] = []

    def watch(old, new, who) -> None:
        called.append(1)
        raise InvalidBody("no")

    tenancy, tenant = await _made(store, files, grant_validators=[watch])
    _, version = await tenancy.get(tenant)

    with pytest.raises(UnknownRole):
        await tenancy.set_grants(tenant, _grant(tenant, "no-such-role"), version, CREATOR)

    assert called == [], "the roles are checked before the consumer's validators run"


# E6 a target foreign to the tenant
async def test_set_grants_refuses_a_foreign_target_as_invalid_grant(store, files):
    tenancy, tenant = await _made(store, files)
    _, version = await tenancy.get(tenant)
    foreign = GrantSet(
        grants=[Grant(assignee=BOB, target="https://elsewhere.example/t", role="reader")]
    )

    with pytest.raises(InvalidGrant):
        await tenancy.set_grants(tenant, foreign, version, CREATOR)

    assert (await tenancy.get(tenant))[1] == version, "the record version is unchanged"


# E7 a stored role that is no longer defined is dropped by the new set; E8 the new set keeps it
async def test_a_stored_role_that_is_no_longer_defined_can_be_dropped_but_not_kept(store, files):
    defined = AccessRules([*load_role_definitions(ROLES), GHOST])
    old, tenant = await _made(store, files, rules=defined)
    _, version = await old.get(tenant)
    version = await old.set_grants(
        tenant,
        GrantSet(grants=[Grant(assignee=ADA, target=tenant, role="ghost")]),
        version,
        CREATOR,
    )
    current = _tenancy(store, files)  # the roles file lost "ghost"

    with pytest.raises(UnknownRole, match="ghost"):
        await current.set_grants(
            tenant, _grant(tenant, "ghost", assignee=ADA), version, CREATOR
        )  # E8
    assert (await current.get(tenant))[1] == version, "the refused set wrote nothing"

    await current.set_grants(tenant, _grant(tenant, "librarian", assignee=ADA), version, CREATOR)
    record, _ = await current.get(tenant)
    assert [g.role for g in record.grants or []] == ["librarian"], "the new set replaced it (E7)"


# E15 the record is read first: a missing tenant is NotFound whatever the roles say
async def test_a_missing_tenant_is_not_found_before_the_roles_are_checked(store, files):
    tenancy, tenant = await _made(store, files)

    with pytest.raises(NotFound):
        await tenancy.set_grants(
            tenant + "-missing", _grant(tenant, "no-such-role"), "any-version", CREATOR
        )


# E19 the rules follow the tenancy's IRI policy: an aggregate graph of the custom policy is a valid target
async def test_set_grants_judges_targets_by_the_tenancys_iri_policy(store, files):
    tenancy, tenant = await _made(store, files, iris=FLAT_IRIS)
    tenant_id = FLAT_IRIS.tenant_id_of(tenant)
    graph = f"{BASE}{tenant_id}/book/{1:013d}/graph"
    assert FLAT_IRIS.is_aggregate_graph(tenant, graph), "the target is an aggregate graph (flat)"
    _, version = await tenancy.get(tenant)
    grants = GrantSet(grants=[Grant(assignee=BOB, target=graph, action=Action.READ)])

    await tenancy.set_grants(tenant, grants, version, CREATOR)

    record, _ = await tenancy.get(tenant)
    assert [g.target for g in record.grants or []] == [graph], "the grant on the aggregate is kept"

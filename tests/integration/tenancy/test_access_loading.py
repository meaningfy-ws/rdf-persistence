"""The one-query access load against a real Fuseki, for a tenant that `Tenancy` created."""

import pytest

from rdf_persistence import Grant, Principal, TenantState
from rdf_persistence.domain.exceptions import NotFound
from rdf_persistence.domain.iris import system_database_name
from rdf_persistence.services.access import load_caller_access
from tests.toy import ADA, library

BOB = "https://example.org/people/bob"


async def test_the_creator_loads_the_librarian_grant_on_an_active_tenant(tenancy, store, settings):
    summary = await tenancy.create("Ghent", library(), Principal(id=ADA))
    loaded = await load_caller_access(store, system_database_name(settings.prefix), summary.id, ADA)
    assert (loaded.tenant, loaded.state) == (summary.id, TenantState.ACTIVE), "tenant and state"
    assert loaded.grants == [Grant(assignee=ADA, target=summary.id, role="librarian")], "the grant"
    assert loaded.prohibitions is None, "no prohibitions"


async def test_another_principal_loads_the_state_and_no_rules(tenancy, store, settings):
    summary = await tenancy.create("Ghent", library(), Principal(id=ADA))
    loaded = await load_caller_access(store, system_database_name(settings.prefix), summary.id, BOB)
    assert (loaded.state, loaded.grants, loaded.prohibitions) == (
        TenantState.ACTIVE,
        None,
        None,
    ), "an outsider sees the state and nothing else"


async def test_a_tenant_that_was_never_created_is_not_found(tenancy, store, settings):
    with pytest.raises(NotFound):
        await load_caller_access(
            store,
            system_database_name(settings.prefix),
            "https://example.org/library/libraries/6f1c0c1e-0000-4000-8000-000000000000",
            ADA,
        )

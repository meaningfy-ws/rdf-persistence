"""The one-query access load against a real Fuseki, for a tenant that `Tenancy` created."""

from uuid import UUID

import pytest

from rdf_persistence import Action, Grant, Principal, TenantState
from rdf_persistence.domain.exceptions import NotFound
from rdf_persistence.domain.iris import access_iri, system_database_name
from rdf_persistence.services.access import load_caller_access
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import open_session
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, BOB, ban, direct, graph_of, library, toy_mapper


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


async def test_a_direct_grant_and_a_prohibition_of_the_caller_load_and_another_principals_do_not(
    tenancy, store, settings
):
    summary = await tenancy.create("Ghent", library(), Principal(id=ADA))
    database = system_database_name(settings.prefix)
    book_graph = graph_of(f"{summary.id}/books/{UUID(int=1)}")
    async with open_session(
        store, database=database, tenant_iri=summary.id, principal=Principal(id=ADA)
    ) as session:
        work = UnitOfWork(session, toy_mapper())
        record = await work.get(LibraryAccess, str(access_iri(summary.id)))
        record.grants = [
            *(record.grants or []),
            direct(Action.MODIFY, book_graph, ADA),
            direct(Action.READ, book_graph, BOB),
        ]
        record.prohibitions = [
            ban(Action.DELETE, book_graph),
            ban(Action.MODIFY, book_graph, BOB),
        ]
        work.add(record)
        await work.commit()
    loaded = await load_caller_access(store, database, summary.id, ADA)
    assert sorted(loaded.grants or [], key=repr) == sorted(
        [
            Grant(assignee=ADA, target=summary.id, role="librarian"),
            direct(Action.MODIFY, book_graph),
        ],
        key=repr,
    ), "ADA's role grant and direct grant, not BOB's"
    assert loaded.prohibitions == [ban(Action.DELETE, book_graph)], "ADA's prohibition only"

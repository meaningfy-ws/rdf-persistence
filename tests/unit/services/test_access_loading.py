"""Loading one caller's access to one tenant: one query, the caller's rules only (PD-9, PD-10)."""

import pytest

from rdf_persistence import Action, Grant, Principal, Prohibition, TenantState
from rdf_persistence.domain.exceptions import NotFound
from rdf_persistence.domain.iris import access_iri, system_database_name
from rdf_persistence.services.access import load_caller_access
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import open_session
from rdf_persistence.testkit import FakeStore
from tests.toy import ADA, SETTINGS, TENANT, access, book_iri, toy_mapper

BOB = "https://example.org/people/bob"
SYSTEM = system_database_name(SETTINGS.prefix)
BOOK_GRAPH = f"{book_iri(1)}/graph"


@pytest.fixture
async def store() -> FakeStore:
    made = FakeStore()
    await made.create_dataset(SYSTEM)
    return made


async def keep(store: FakeStore, record) -> None:
    async with open_session(
        store, database=SYSTEM, tenant_iri=TENANT, principal=Principal(id=ADA)
    ) as session:
        work = UnitOfWork(session, toy_mapper())
        work.add(record)
        await work.commit()


RULES = {
    "role": Grant(assignee=ADA, target=TENANT, role="reader"),
    "action": Grant(assignee=ADA, target=BOOK_GRAPH, action=Action.MODIFY),
    "another": Grant(assignee=BOB, target=TENANT, role="librarian"),
}
BAN = Prohibition(assignee=ADA, target=BOOK_GRAPH, action=Action.MODIFY)
BOBS_BAN = Prohibition(assignee=BOB, target=TENANT, action=Action.READ)


async def test_the_callers_grants_and_prohibitions_come_back_and_nobody_elses(store):
    await keep(
        store,
        access(
            grants=[RULES["role"], RULES["action"], RULES["another"]],
            prohibitions=[BAN, BOBS_BAN],
        ),
    )
    loaded = await load_caller_access(store, SYSTEM, TENANT, ADA)
    assert (loaded.tenant, loaded.state) == (TENANT, TenantState.ACTIVE), "the tenant and its state"
    assert sorted(loaded.grants or [], key=repr) == sorted(
        [RULES["role"], RULES["action"]], key=repr
    ), "a role grant and a direct grant, both of ADA"
    assert loaded.prohibitions == [BAN], "ADA's prohibition only"


async def test_a_caller_with_no_rules_still_gets_the_tenants_state(store):
    record = access(grants=[RULES["another"]])
    record.state = TenantState.DELETING
    await keep(store, record)
    loaded = await load_caller_access(store, SYSTEM, TENANT, ADA)
    assert loaded.state == TenantState.DELETING, "the state"
    assert (loaded.grants, loaded.prohibitions) == (None, None), "no rules"


async def test_a_tenant_without_an_access_record_is_not_found(store):
    with pytest.raises(NotFound):
        await load_caller_access(store, SYSTEM, TENANT, ADA)


async def test_the_load_is_one_query_against_the_access_graph_of_the_tenant(store):
    await keep(store, access(grants=[RULES["role"]], prohibitions=[BAN]))
    before = len(store.sent("query"))
    await load_caller_access(store, SYSTEM, TENANT, ADA)
    sent = store.sent("query")[before:]
    assert len(sent) == 1, "one query"
    assert str(access_iri(TENANT)) in sent[0], "it names the tenant's access record"


async def test_an_iri_that_would_break_the_query_is_refused_before_it_is_sent(store):
    with pytest.raises(ValueError, match="IRI"):
        await load_caller_access(store, SYSTEM, TENANT, "https://example.org/a> } DROP ALL {")
    assert store.sent("query") == [], "nothing was sent"

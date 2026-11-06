"""FakeIdentity: the behaviour of the identity port that the services rely on, and its failure injection."""

import inspect

import pytest

from rdf_persistence.domain.exceptions import IdentityUnavailable, NotFound
from rdf_persistence.domain.generated.service.rp_service import AccountSummary
from rdf_persistence.testkit import no_network  # noqa: F401  (fixture)
from rdf_persistence.testkit.fakes import FakeIdentity

ANN = AccountSummary(account_id="1", user_name="ann", email="ann@example.org", active=True)
BOT = AccountSummary(account_id="2", user_name="bot", active=True, global_roles=["admin"])


@pytest.fixture
def identity(no_network) -> FakeIdentity:  # noqa: F811
    return FakeIdentity([ANN, BOT])


async def test_an_account_is_found_by_its_exact_email(identity):
    assert (await identity.find_by_email("ann@example.org")).account_id == "1"


@pytest.mark.parametrize("email", ["ANN@example.org", "ann@example", "", "bot"])
async def test_no_account_answers_to_an_email_that_is_not_exact(identity, email):
    with pytest.raises(NotFound):
        await identity.find_by_email(email)


async def test_accounts_are_listed_in_the_order_they_were_added(identity):
    assert [a.user_name for a in await identity.list_accounts()] == ["ann", "bot"]


async def test_a_disabled_account_is_inactive_until_it_is_enabled(identity):
    await identity.disable("1")
    assert (await identity.find_by_email("ann@example.org")).active is False, "disabled"
    await identity.enable("1")
    assert (await identity.find_by_email("ann@example.org")).active is True, "enabled again"


async def test_disabling_twice_is_harmless(identity):
    await identity.disable("1")
    await identity.disable("1")
    assert [a.active for a in await identity.list_accounts()] == [False, True]


@pytest.mark.parametrize("operation", ["disable", "enable"])
async def test_disabling_or_enabling_an_unknown_account_is_not_found(identity, operation):
    with pytest.raises(NotFound):
        await getattr(identity, operation)("missing")


async def test_a_global_role_is_granted_once_and_removed(identity):
    await identity.grant_global_role("1", "admin")
    await identity.grant_global_role("1", "admin")
    assert (await identity.find_by_email("ann@example.org")).global_roles == ["admin"]
    await identity.remove_global_role("1", "admin")
    assert not (await identity.find_by_email("ann@example.org")).global_roles, "role removed"


async def test_removing_a_role_the_account_lacks_changes_nothing(identity):
    await identity.remove_global_role("1", "admin")
    assert [a.global_roles for a in await identity.list_accounts()] == [None, ["admin"]]


@pytest.mark.parametrize("operation", ["grant_global_role", "remove_global_role"])
async def test_a_role_change_on_an_unknown_account_is_not_found(identity, operation):
    with pytest.raises(NotFound):
        await getattr(identity, operation)("missing", "admin")


async def test_the_fake_keeps_its_own_copy_of_each_account(identity):
    (await identity.find_by_email("ann@example.org")).active = False
    assert ANN.active is True, "the caller's record was not touched"
    assert (await identity.find_by_email("ann@example.org")).active is True, "nor the fake's"


async def test_an_injected_error_is_raised_once_and_sent_records_the_failed_call(identity):
    identity.on("disable", IdentityUnavailable("down"))
    with pytest.raises(IdentityUnavailable):
        await identity.disable("1")
    await identity.disable("1")
    assert identity.sent("disable") == ["1", "1"]
    assert identity.sent("grant_global_role") == [], "other operations are untouched"


async def test_the_role_operations_record_the_account_and_the_role(identity):
    await identity.grant_global_role("1", "admin")
    assert identity.sent("grant_global_role") == ["1 admin"]


@pytest.mark.parametrize("call", ["on", "sent"])
def test_a_misspelt_operation_is_refused_not_silently_ignored(call):
    identity = FakeIdentity()
    args = (IdentityUnavailable("down"),) if call == "on" else ()
    with pytest.raises(ValueError, match="disabled"):
        getattr(identity, call)("disabled", *args)


def test_the_known_operations_are_exactly_the_async_methods_of_the_fake():
    methods = {
        name
        for name in dir(FakeIdentity)
        if not name.startswith("_") and inspect.iscoroutinefunction(getattr(FakeIdentity, name))
    }
    assert methods == FakeIdentity.OPERATIONS, "an operation was added or removed without the list"

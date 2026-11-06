"""The ``Identity`` conformance suite: one set of cases, run against the fake and against Zitadel.

Each case takes an identity and the id of an account that is new to the case, active and without
global roles; the project has the role ``ROLE`` and no ``UNKNOWN_ROLE``. A divergence between the
fake and Zitadel is a bug in the fake. Run a case with ``run_case``, which leaves the account as it
found it.
"""

from collections.abc import Awaitable, Callable

import pytest

from rdf_persistence.domain.exceptions import NotFound
from rdf_persistence.domain.generated.service.rp_service import AccountSummary
from rdf_persistence.services.identity import Identity

ROLE = "admin"
UNKNOWN_ROLE = "no-such-role"
UNKNOWN_ACCOUNT = "1"
NOT_AN_ID = ("", " ", "a b", "../x", "u1/grants")
UNKNOWN_EMAIL = "nobody@example.org"

Case = Callable[[Identity, str], Awaitable[None]]


async def _account(identity: Identity, account_id: str) -> AccountSummary:
    return next(a for a in await identity.list_accounts() if a.account_id == account_id)


async def a_granted_role_is_listed_and_granting_it_again_changes_nothing(
    identity: Identity, account_id: str
) -> None:
    await identity.grant_global_role(account_id, ROLE)
    await identity.grant_global_role(account_id, ROLE)
    assert (await _account(identity, account_id)).global_roles == [ROLE]


async def removing_the_last_role_leaves_none(identity: Identity, account_id: str) -> None:
    await identity.grant_global_role(account_id, ROLE)
    await identity.remove_global_role(account_id, ROLE)
    assert (await _account(identity, account_id)).global_roles is None


async def removing_a_role_the_account_lacks_changes_nothing(
    identity: Identity, account_id: str
) -> None:
    await identity.remove_global_role(account_id, ROLE)
    assert (await _account(identity, account_id)).global_roles is None


async def granting_a_role_the_project_lacks_is_not_found(
    identity: Identity, account_id: str
) -> None:
    with pytest.raises(NotFound):
        await identity.grant_global_role(account_id, UNKNOWN_ROLE)
    assert (await _account(identity, account_id)).global_roles is None


async def a_disabled_account_is_inactive_until_it_is_enabled(
    identity: Identity, account_id: str
) -> None:
    await identity.disable(account_id)
    await identity.disable(account_id)
    assert (await _account(identity, account_id)).active is False
    await identity.enable(account_id)
    await identity.enable(account_id)
    assert (await _account(identity, account_id)).active is True


async def an_account_that_does_not_exist_is_not_found_by_every_change(
    identity: Identity, account_id: str
) -> None:
    for missing in (UNKNOWN_ACCOUNT, *NOT_AN_ID):
        for change in (identity.disable, identity.enable):
            with pytest.raises(NotFound):
                await change(missing)
        for role_change in (identity.grant_global_role, identity.remove_global_role):
            with pytest.raises(NotFound):
                await role_change(missing, ROLE)


async def an_email_nobody_has_is_not_found(identity: Identity, account_id: str) -> None:
    with pytest.raises(NotFound):
        await identity.find_by_email(UNKNOWN_EMAIL)


CASES: tuple[Case, ...] = (
    a_granted_role_is_listed_and_granting_it_again_changes_nothing,
    removing_the_last_role_leaves_none,
    removing_a_role_the_account_lacks_changes_nothing,
    granting_a_role_the_project_lacks_is_not_found,
    a_disabled_account_is_inactive_until_it_is_enabled,
    an_account_that_does_not_exist_is_not_found_by_every_change,
    an_email_nobody_has_is_not_found,
)


async def run_case(case: Case, identity: Identity, account_id: str) -> None:
    """Run one case on the account, then take its role away and enable it again."""
    try:
        await case(identity, account_id)
    finally:
        await identity.remove_global_role(account_id, ROLE)
        await identity.enable(account_id)

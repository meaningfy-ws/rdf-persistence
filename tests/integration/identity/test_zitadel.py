"""ZitadelIdentity against a real Zitadel: service accounts are refused when disabled, and roles reach tokens."""

import uuid

import pytest

from rdf_persistence.adapters.jwks import JwksTokenVerifier
from rdf_persistence.adapters.zitadel import ZitadelIdentity, zitadel_roles_claim
from rdf_persistence.domain.exceptions import InvalidToken, NotFound
from rdf_persistence.testkit.exceptions import TokenRefusedError
from rdf_persistence.testkit.identity_conformance import CASES, run_case
from rdf_persistence.testkit.zitadel import ADMIN_ROLE, access_token, create_machine_user


@pytest.fixture
async def verifier(zitadel_project):
    """A verifier of the container's tokens; the container speaks http, so the https rule is opted out of."""
    async with JwksTokenVerifier(
        zitadel_project.server.url,
        zitadel_project.project_id,
        zitadel_roles_claim(zitadel_project.project_id),
        allow_insecure_issuer=True,
    ) as client:
        yield client


async def roles_in(verifier, project, account) -> set[str]:
    """The global roles of a fresh token of the account, as the toolkit's verifier reads them."""
    return set((await verifier.verify(access_token(project, account))).global_roles)


@pytest.fixture
async def identity(zitadel_project):
    async with ZitadelIdentity(
        zitadel_project.server.url,
        zitadel_project.server.admin_pat,
        zitadel_project.organisation_id,
        zitadel_project.project_id,
    ) as client:
        yield client


@pytest.fixture
def account(zitadel_project):
    """A service account of this test alone."""
    return create_machine_user(zitadel_project, f"bot-{uuid.uuid4().hex[:8]}")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__)
async def test_zitadel_conforms(case, identity, account):
    await run_case(case, identity, account.user_id)


async def test_a_live_token_is_verified_to_the_principal_of_its_account(
    verifier, zitadel_project, account
):
    caller = await verifier.verify(access_token(zitadel_project, account))
    assert caller.principal == f"{zitadel_project.server.url}/users/{account.user_id}"
    assert caller.global_roles == [], "an account without grants holds no role"


async def test_the_admin_principal_holds_the_admin_role_in_its_verified_token(
    verifier, zitadel_project
):
    admin = next(user for user in zitadel_project.machine_users if user.name == ADMIN_ROLE)
    caller = await verifier.verify(access_token(zitadel_project, admin))
    assert caller.global_roles == [ADMIN_ROLE]


async def test_a_token_for_another_audience_is_refused_by_the_live_issuers_keys(
    zitadel_project, account
):
    async with JwksTokenVerifier(
        zitadel_project.server.url, "another-project", "roles", allow_insecure_issuer=True
    ) as other:
        with pytest.raises(InvalidToken):
            await other.verify(access_token(zitadel_project, account))


async def test_a_disabled_service_account_is_refused_a_token_until_it_is_enabled(
    identity, zitadel_project, account
):
    await identity.disable(account.user_id)
    with pytest.raises(TokenRefusedError):
        access_token(zitadel_project, account)
    await identity.enable(account.user_id)
    assert access_token(zitadel_project, account), "a token again"


async def test_disabling_twice_is_harmless_and_shows_in_the_listing(identity, account):
    await identity.disable(account.user_id)
    await identity.disable(account.user_id)
    listed = {a.account_id: a for a in await identity.list_accounts()}
    assert listed[account.user_id].active is False
    assert listed[account.user_id].user_name == account.name


async def test_a_global_role_shows_in_a_fresh_token_until_it_is_removed(
    identity, verifier, zitadel_project, account
):
    assert ADMIN_ROLE not in await roles_in(verifier, zitadel_project, account), "none at first"
    await identity.grant_global_role(account.user_id, ADMIN_ROLE)
    await identity.grant_global_role(account.user_id, ADMIN_ROLE)
    assert ADMIN_ROLE in await roles_in(verifier, zitadel_project, account), "granted"
    listed = {a.account_id: a for a in await identity.list_accounts()}
    assert listed[account.user_id].global_roles == [ADMIN_ROLE]
    await identity.remove_global_role(account.user_id, ADMIN_ROLE)
    assert ADMIN_ROLE not in await roles_in(verifier, zitadel_project, account), "removed"


async def test_an_unknown_role_or_account_is_not_found(identity, account):
    with pytest.raises(NotFound):
        await identity.grant_global_role(account.user_id, "nosuch")
    with pytest.raises(NotFound):
        await identity.disable("1")


async def _found_once_indexed(identity, email, attempts=30):
    """Zitadel indexes a new user for search asynchronously, so a search right after a create can miss it."""
    import anyio

    for _ in range(attempts - 1):
        try:
            return await identity.find_by_email(email)
        except NotFound:
            await anyio.sleep(0.5)
    return await identity.find_by_email(email)


async def test_a_person_is_found_by_exact_email(identity, zitadel_project):
    import httpx

    email = f"ann-{uuid.uuid4().hex[:8]}@example.org"
    server = zitadel_project.server
    created = httpx.post(
        f"{server.url}/v2/users/human",
        headers={"Authorization": f"Bearer {server.admin_pat}"},
        json={
            "username": email,
            "profile": {"givenName": "Ann", "familyName": "A"},
            "email": {"email": email, "isVerified": True},
        },
    )
    created.raise_for_status()
    found = await _found_once_indexed(identity, email)
    assert (found.account_id, found.email, found.active) == (created.json()["userId"], email, True)
    with pytest.raises(NotFound):
        await identity.find_by_email(email.upper())

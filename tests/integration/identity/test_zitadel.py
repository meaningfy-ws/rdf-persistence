"""ZitadelIdentity against a real Zitadel: service accounts are refused when disabled, and roles reach tokens."""

import uuid

import jwt
import pytest

from rdf_persistence.adapters.zitadel import ZitadelIdentity
from rdf_persistence.domain.exceptions import NotFound
from rdf_persistence.testkit.zitadel import (
    ADMIN_ROLE,
    TokenRefusedError,
    access_token,
    create_machine_user,
    roles_claim,
)


def roles_in(project, token: str) -> set[str]:
    claims = jwt.decode(token, options={"verify_signature": False})
    return set(claims.get(roles_claim(project.project_id), ()))


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


async def test_a_service_account_gets_a_jwt_that_names_the_project(zitadel_project, account):
    claims = jwt.decode(access_token(zitadel_project, account), options={"verify_signature": False})
    assert claims["sub"] == account.user_id
    assert zitadel_project.project_id in claims["aud"], "the project audience"


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
    identity, zitadel_project, account
):
    assert ADMIN_ROLE not in roles_in(zitadel_project, access_token(zitadel_project, account)), (
        "none at first"
    )
    await identity.grant_global_role(account.user_id, ADMIN_ROLE)
    await identity.grant_global_role(account.user_id, ADMIN_ROLE)
    assert ADMIN_ROLE in roles_in(zitadel_project, access_token(zitadel_project, account)), (
        "granted"
    )
    listed = {a.account_id: a for a in await identity.list_accounts()}
    assert listed[account.user_id].global_roles == [ADMIN_ROLE]
    await identity.remove_global_role(account.user_id, ADMIN_ROLE)
    assert ADMIN_ROLE not in roles_in(zitadel_project, access_token(zitadel_project, account)), (
        "removed"
    )


async def test_an_unknown_role_or_account_is_not_found(identity, account):
    with pytest.raises(NotFound):
        await identity.grant_global_role(account.user_id, "nosuch")
    with pytest.raises(NotFound):
        await identity.disable("1")


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
    found = await identity.find_by_email(email)
    assert (found.account_id, found.email, found.active) == (created.json()["userId"], email, True)
    with pytest.raises(NotFound):
        await identity.find_by_email(email.upper())

"""Provision a test Zitadel and get JWT access tokens from it (PD-16).

Plain ``httpx`` and ``PyJWT``, so this needs neither Docker nor the extra ``testkit``. The
container fixtures call ``provision_project``; a test calls ``create_machine_user`` for a service
account of its own and ``access_token`` for the token of any machine user.
"""

import base64
import json
import time
from collections.abc import Callable, Iterable
from typing import NoReturn

import httpx
import jwt

from rdf_persistence.generation.generated.rp_generation import (
    MachineUser,
    ZitadelProject,
    ZitadelServer,
)

JWT_BEARER_GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer"
ADMIN_ROLE = "admin"
PROJECT_NAME = "rp-test"
ORG_HEADER = "x-zitadel-orgid"
ASSERTION_SECONDS = 60
TIMEOUT_SECONDS = 30


class ProvisioningError(RuntimeError):
    """The test Zitadel refused a provisioning call; the message holds the status, never a secret."""


class TokenRefusedError(RuntimeError):
    """Zitadel refused a token request (a disabled account, an unknown key, ...)."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"Zitadel refused the token request with {status_code}")
        self.status_code = status_code


def token_scopes(project_id: str) -> str:
    """The scopes that put the project audience and the roles claim into the token."""
    return " ".join(
        [
            "openid",
            f"urn:zitadel:iam:org:project:id:{project_id}:aud",
            "urn:zitadel:iam:org:projects:roles",
        ]
    )


def roles_claim(project_id: str) -> str:
    """The claim that holds the project's roles in a token (Zitadel names it after the project)."""
    return f"urn:zitadel:iam:org:project:{project_id}:roles"


def client_assertion(issuer: str, user: MachineUser, *, now: float) -> str:
    """The signed JWT a machine user presents in the JWT-profile grant."""
    issued = int(now)
    claims = {
        "iss": user.user_id,
        "sub": user.user_id,
        "aud": issuer,
        "iat": issued,
        "exp": issued + ASSERTION_SECONDS,
    }
    return jwt.encode(claims, user.private_key, algorithm="RS256", headers={"kid": user.key_id})


def access_token(
    project: ZitadelProject,
    user: MachineUser,
    *,
    transport: httpx.BaseTransport | None = None,
    now: Callable[[], float] = time.time,
) -> str:
    """Get a JWT access token for a machine user with the JWT-profile grant.

    Raises:
        TokenRefusedError: Zitadel refused the request.
    """
    issuer = project.server.url
    assertion = client_assertion(issuer, user, now=now())
    form = {
        "grant_type": JWT_BEARER_GRANT,
        "scope": token_scopes(project.project_id),
        "assertion": assertion,
    }
    with httpx.Client(base_url=issuer, transport=transport, timeout=TIMEOUT_SECONDS) as client:
        response = client.post("/oauth/v2/token", data=form)
    if not response.is_success:
        raise TokenRefusedError(response.status_code)
    return str(response.json()["access_token"])


def _fail(what: str, response: httpx.Response) -> NoReturn:
    raise ProvisioningError(f"Zitadel refused to {what} with {response.status_code}")


def _manage(
    server: ZitadelServer,
    organisation_id: str | None,
    method: str,
    path: str,
    body: object | None = None,
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {server.admin_pat}"}
    if organisation_id:
        headers[ORG_HEADER] = organisation_id
    with httpx.Client(base_url=server.url, headers=headers, timeout=TIMEOUT_SECONDS) as client:
        return client.request(method, path, json=body)


def _create_project(server: ZitadelServer, organisation_id: str) -> str:
    response = _manage(
        server, organisation_id, "POST", "/management/v1/projects", {"name": PROJECT_NAME}
    )
    if not response.is_success:
        _fail("create the project", response)
    project_id = str(response.json()["id"])
    role = {"roleKey": ADMIN_ROLE, "displayName": ADMIN_ROLE}
    response = _manage(
        server, organisation_id, "POST", f"/management/v1/projects/{project_id}/roles", role
    )
    if not response.is_success:
        _fail("create the admin role", response)
    return project_id


def create_machine_user(
    project: ZitadelProject, name: str, *, roles: Iterable[str] = ()
) -> MachineUser:
    """Create a machine user whose tokens are JWTs, with a key, and the given global roles.

    Args:
        project: The provisioned project.
        name: The user name; it must be new, so a test namespaces it.
        roles: Roles of the project to grant it.

    Raises:
        ProvisioningError: Zitadel refused a call.
    """
    server, org = project.server, project.organisation_id
    created = _manage(
        server,
        org,
        "POST",
        "/management/v1/users/machine",
        {"userName": name, "name": name, "accessTokenType": "ACCESS_TOKEN_TYPE_JWT"},
    )
    if not created.is_success:
        _fail(f"create the machine user {name}", created)
    user_id = str(created.json()["userId"])
    keyed = _manage(
        server, org, "POST", f"/management/v1/users/{user_id}/keys", {"type": "KEY_TYPE_JSON"}
    )
    if not keyed.is_success:
        _fail(f"create a key for {name}", keyed)
    key_file = json.loads(base64.b64decode(keyed.json()["keyDetails"]))
    role_keys = list(roles)
    if role_keys:
        grant = {"projectId": project.project_id, "roleKeys": role_keys}
        granted = _manage(server, org, "POST", f"/management/v1/users/{user_id}/grants", grant)
        if not granted.is_success:
            _fail(f"grant {name} its roles", granted)
    return MachineUser(
        name=name, user_id=user_id, key_id=str(key_file["keyId"]), private_key=str(key_file["key"])
    )


def provision_project(server: ZitadelServer, principals: Iterable[str]) -> ZitadelProject:
    """Create the project with the role ``admin``, and one machine user per principal.

    The principal named ``admin`` holds the ``admin`` role.

    Raises:
        ProvisioningError: Zitadel refused a call.
    """
    org = _manage(server, None, "GET", "/management/v1/orgs/me")
    if not org.is_success:
        _fail("read the organisation", org)
    organisation_id = str(org.json()["org"]["id"])
    bare = ZitadelProject(
        server=server,
        organisation_id=organisation_id,
        project_id=_create_project(server, organisation_id),
    )
    users = [
        create_machine_user(bare, name, roles=[ADMIN_ROLE] if name == ADMIN_ROLE else [])
        for name in principals
    ]
    return bare.model_copy(update={"machine_users": users})

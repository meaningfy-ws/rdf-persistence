"""Provision a test Zitadel and get JWT access tokens from it (PD-16).

Plain ``httpx`` and ``PyJWT``, so this needs neither Docker nor the extra ``testkit``. The
container fixtures call ``provision_project``; a test calls ``create_machine_user`` for a service
account of its own and ``access_token`` for the token of any machine user. Requests and answers are
the records of ``rdf_persistence.adapters.generated.rp_wire``.
"""

import base64
import binascii
import time
from collections.abc import Iterable
from http import HTTPMethod

import httpx
import jwt
from pydantic import BaseModel, ValidationError

from rdf_persistence.adapters._http import READ_TIMEOUT_SECONDS, json_body
from rdf_persistence.adapters.generated.rp_wire import (
    ZitadelAssertion,
    ZitadelCreated,
    ZitadelGrantRequest,
    ZitadelKeyAnswer,
    ZitadelKeyFile,
    ZitadelKeyRequest,
    ZitadelMachineUserAnswer,
    ZitadelMachineUserRequest,
    ZitadelOrganisationAnswer,
    ZitadelProjectRequest,
    ZitadelRoleRequest,
    ZitadelTokenAnswer,
    ZitadelTokenRequest,
)
from rdf_persistence.adapters.jwks import RS256
from rdf_persistence.adapters.zitadel import (
    MACHINE_USERS,
    MANAGEMENT,
    ORG_HEADER,
    OWN_ORGANISATION,
    PROJECTS,
    TOKEN_PATH,
    user_grant_path,
)
from rdf_persistence.generation.generated.rp_generation import (
    MachineUser,
    ZitadelProject,
    ZitadelServer,
)
from rdf_persistence.services.tokens import EpochClock
from rdf_persistence.testkit.exceptions import ProvisioningError, TokenRefusedError

ADMIN_ROLE = "admin"
PROJECT_NAME = "rp-test"
ASSERTION_SECONDS = 60


def token_scopes(project_id: str) -> str:
    """The scopes that put the project audience and the roles claim into the token."""
    return " ".join(
        [
            "openid",
            f"urn:zitadel:iam:org:project:id:{project_id}:aud",
            "urn:zitadel:iam:org:projects:roles",
        ]
    )


def client_assertion(issuer: str, user: MachineUser, *, now: float) -> str:
    """The signed JWT a machine user presents in the JWT-profile grant."""
    issued = int(now)
    claims = ZitadelAssertion(
        iss=user.user_id,
        sub=user.user_id,
        aud=issuer,
        iat=issued,
        exp=issued + ASSERTION_SECONDS,
    )
    return jwt.encode(
        claims.model_dump(), user.private_key, algorithm=RS256, headers={"kid": user.key_id}
    )


def _unreadable(what: str) -> ProvisioningError:
    return ProvisioningError(f"Zitadel answered unreadably when asked to {what}")


def _read[M: BaseModel](model: type[M], content: bytes, what: str) -> M:
    try:
        return model.model_validate_json(content)
    except ValidationError as error:
        raise _unreadable(what) from error


def access_token(
    project: ZitadelProject,
    user: MachineUser,
    *,
    transport: httpx.BaseTransport | None = None,
    now: EpochClock = time.time,
) -> str:
    """Get a JWT access token for a machine user with the JWT-profile grant.

    Raises:
        TokenRefusedError: Zitadel refused the request.
        ProvisioningError: Zitadel answered with something unreadable.
    """
    issuer = project.server.url
    form = ZitadelTokenRequest(
        scope=token_scopes(project.project_id),
        assertion=client_assertion(issuer, user, now=now()),
    )
    with httpx.Client(base_url=issuer, transport=transport, timeout=READ_TIMEOUT_SECONDS) as client:
        response = client.post(TOKEN_PATH, data=form.model_dump())
    if not response.is_success:
        raise TokenRefusedError(response.status_code)
    return _read(ZitadelTokenAnswer, response.content, "grant a token").access_token


def _manage(
    server: ZitadelServer,
    organisation_id: str | None,
    method: HTTPMethod,
    path: str,
    what: str,
    body: BaseModel | None = None,
) -> bytes:
    """Call the management API; the answer's content, or a ``ProvisioningError`` naming ``what`` and the status."""
    headers = {"Authorization": f"Bearer {server.admin_pat}"}
    if organisation_id:
        headers[ORG_HEADER] = organisation_id
    with httpx.Client(base_url=server.url, headers=headers, timeout=READ_TIMEOUT_SECONDS) as client:
        response = client.request(method, path, **json_body(body))
    if not response.is_success:
        raise ProvisioningError(f"Zitadel refused to {what} with {response.status_code}")
    return response.content


def _create_project(server: ZitadelServer, organisation_id: str) -> str:
    request = ZitadelProjectRequest(name=PROJECT_NAME)
    answer = _manage(
        server, organisation_id, HTTPMethod.POST, PROJECTS, "create the project", request
    )
    project_id = _read(ZitadelCreated, answer, "create the project").id
    role = ZitadelRoleRequest(roleKey=ADMIN_ROLE, displayName=ADMIN_ROLE)
    _manage(
        server,
        organisation_id,
        HTTPMethod.POST,
        f"{PROJECTS}/{project_id}/roles",
        "create the admin role",
        role,
    )
    return project_id


def _create_user(project: ZitadelProject, name: str) -> str:
    request = ZitadelMachineUserRequest(userName=name, name=name)
    what = f"create the machine user {name}"
    answer = _manage(
        project.server, project.organisation_id, HTTPMethod.POST, MACHINE_USERS, what, request
    )
    return _read(ZitadelMachineUserAnswer, answer, what).userId


def _create_key(project: ZitadelProject, user_id: str, name: str) -> ZitadelKeyFile:
    what = f"create a key for {name}"
    answer = _manage(
        project.server,
        project.organisation_id,
        HTTPMethod.POST,
        f"{MANAGEMENT}/users/{user_id}/keys",
        what,
        ZitadelKeyRequest(),
    )
    details = _read(ZitadelKeyAnswer, answer, what).keyDetails
    try:
        return _read(ZitadelKeyFile, base64.b64decode(details), what)
    except binascii.Error as error:
        raise _unreadable(what) from error


def _grant_roles(project: ZitadelProject, user_id: str, name: str, roles: list[str]) -> None:
    grant = ZitadelGrantRequest(projectId=project.project_id, roleKeys=roles)
    _manage(
        project.server,
        project.organisation_id,
        HTTPMethod.POST,
        user_grant_path(user_id),
        f"grant {name} its roles",
        grant,
    )


def create_machine_user(
    project: ZitadelProject, name: str, *, roles: Iterable[str] = ()
) -> MachineUser:
    """Create a machine user whose tokens are JWTs, with a key, and the given global roles.

    Args:
        project: The provisioned project.
        name: The user name; it must be new, so a test namespaces it.
        roles: Roles of the project to grant it.

    Raises:
        ProvisioningError: Zitadel refused a call or answered with something unreadable.
    """
    user_id = _create_user(project, name)
    key = _create_key(project, user_id, name)
    if role_keys := list(roles):
        _grant_roles(project, user_id, name, role_keys)
    return MachineUser(name=name, user_id=user_id, key_id=key.keyId, private_key=key.key)


def provision_project(server: ZitadelServer, principals: Iterable[str]) -> ZitadelProject:
    """Create the project with the role ``admin``, and one machine user per principal.

    The principal named ``admin`` holds the ``admin`` role.

    Raises:
        ProvisioningError: Zitadel refused a call or answered with something unreadable.
    """
    what = "read the organisation"
    answer = _manage(server, None, HTTPMethod.GET, OWN_ORGANISATION, what)
    organisation_id = _read(ZitadelOrganisationAnswer, answer, what).org.id
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

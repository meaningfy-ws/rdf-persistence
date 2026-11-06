"""The Zitadel implementation of the ``Identity`` port, over the v2 user API and the management API.

A global role is a role of the configured project, granted to the user (a user grant); the roles
claim of a token carries them (``access-control.adoc#identity``).
"""

import logging
from collections.abc import Callable, Sequence
from http import HTTPMethod, HTTPStatus
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ValidationError

from rdf_persistence.adapters._http import HttpAdapter, json_body
from rdf_persistence.adapters.generated.rp_wire import (
    BadRequestMeans,
    ZitadelEmailQuery,
    ZitadelGrantPage,
    ZitadelGrantRequest,
    ZitadelOrganisationQuery,
    ZitadelProjectQuery,
    ZitadelQuery,
    ZitadelSearch,
    ZitadelUser,
    ZitadelUserGrant,
    ZitadelUserPage,
    ZitadelUserQuery,
    ZitadelWindow,
)
from rdf_persistence.domain.exceptions import IdentityUnavailable, NotFound
from rdf_persistence.domain.generated.service.rp_service import AccountSummary

ORG_HEADER = "x-zitadel-orgid"
USERS = "/v2/users"
MANAGEMENT = "/management/v1"
USER_GRANT_SEARCH = f"{MANAGEMENT}/users/grants/_search"
PROJECTS = f"{MANAGEMENT}/projects"
MACHINE_USERS = f"{MANAGEMENT}/users/machine"
OWN_ORGANISATION = f"{MANAGEMENT}/orgs/me"
TOKEN_PATH = "/oauth/v2/token"
PAGE_SIZE = 100
ACTIVE_STATE = "USER_STATE_ACTIVE"
UNREADABLE = "Zitadel answered with something unreadable"

log = logging.getLogger(__name__)


def zitadel_roles_claim(project_id: str) -> str:
    """The claim that holds a project's roles in a token: Zitadel names it after the project."""
    return f"urn:zitadel:iam:org:project:{project_id}:roles"


def _summary(user: ZitadelUser, roles: list[str]) -> AccountSummary:
    email = user.human.email.email if user.human and user.human.email else None
    return AccountSummary(
        account_id=user.userId,
        user_name=user.username,
        email=email,
        active=user.state == ACTIVE_STATE,
        global_roles=roles or None,
    )


def _user_path(account_id: str, *rest: str) -> str:
    return "/".join([USERS, quote(account_id, safe=""), *rest])


def user_grant_path(user_id: str, *rest: str) -> str:
    """The management path of a user's grants, or of one grant."""
    return "/".join([MANAGEMENT, "users", quote(user_id, safe=""), "grants", *rest])


def _users_in(response: httpx.Response) -> list[ZitadelUser]:
    return _read(ZitadelUserPage, response).result or []


def _grants_in(response: httpx.Response) -> list[ZitadelUserGrant]:
    return _read(ZitadelGrantPage, response).result or []


def _read[M: BaseModel](model: type[M], response: httpx.Response) -> M:
    try:
        return model.model_validate_json(response.content)
    except ValidationError as error:
        raise IdentityUnavailable(UNREADABLE) from error


class ZitadelIdentity(HttpAdapter):
    """An ``Identity`` over a Zitadel instance, authenticated with a service token.

    Args:
        issuer: The base URL of the instance.
        service_token: A token of a machine user allowed to administer the organisation.
        organisation_id: The organisation whose accounts are administered.
        project_id: The project whose roles are the global roles.
    """

    service = "Zitadel"
    unavailable = IdentityUnavailable

    def __init__(
        self,
        issuer: str,
        service_token: str,
        organisation_id: str,
        project_id: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            base_url=issuer,
            headers={"Authorization": f"Bearer {service_token}", ORG_HEADER: organisation_id},
            transport=transport,
        )
        self._organisation_id = organisation_id
        self._project_id = project_id

    async def _send(
        self,
        method: HTTPMethod,
        path: str,
        body: BaseModel | None = None,
        *,
        bad_request: BadRequestMeans = BadRequestMeans.FAILURE,
    ) -> httpx.Response:
        """Send a request and map the failures; ``bad_request`` says what a 400 means to this call."""
        response = await self.request(method, path, **json_body(body))
        status = response.status_code
        if status == HTTPStatus.NOT_FOUND:
            raise NotFound(f"Zitadel answered 404 for {path}")
        if status == HTTPStatus.BAD_REQUEST and bad_request == BadRequestMeans.ALREADY_DONE:
            return response
        if status == HTTPStatus.BAD_REQUEST and bad_request == BadRequestMeans.MISSING_ROLE:
            raise NotFound("the project has no such role")
        if not response.is_success:
            log.debug("Zitadel answered %s: %s", status, response.text)
            raise IdentityUnavailable(f"Zitadel answered {status} for {path}")
        return response

    async def _search_all[T](
        self,
        path: str,
        queries: Sequence[ZitadelQuery],
        items_in: Callable[[httpx.Response], list[T]],
    ) -> list[T]:
        """Every item the search finds, page by page."""
        found: list[T] = []
        while True:
            window = ZitadelWindow(offset=len(found), limit=PAGE_SIZE)
            search = ZitadelSearch(query=window, queries=list(queries))
            page = items_in(await self._send(HTTPMethod.POST, path, search))
            found.extend(page)
            if len(page) < PAGE_SIZE:
                return found

    def _in_organisation(self, *more: ZitadelQuery) -> list[ZitadelQuery]:
        organisation = ZitadelOrganisationQuery(organizationId=self._organisation_id)
        return [ZitadelQuery(organizationIdQuery=organisation), *more]

    async def _grants(self, account_id: str | None = None) -> list[ZitadelUserGrant]:
        queries = [ZitadelQuery(projectIdQuery=ZitadelProjectQuery(projectId=self._project_id))]
        if account_id:
            queries.append(ZitadelQuery(userIdQuery=ZitadelUserQuery(userId=account_id)))
        return await self._search_all(USER_GRANT_SEARCH, queries, _grants_in)

    async def find_by_email(self, email: str) -> AccountSummary:
        by_email = ZitadelQuery(emailQuery=ZitadelEmailQuery(emailAddress=email))
        users = await self._search_all(USERS, self._in_organisation(by_email), _users_in)
        if not users:
            raise NotFound(f"no account with email {email}")
        grants = await self._grants(users[0].userId)
        return _summary(users[0], [role for grant in grants for role in grant.roleKeys or []])

    async def list_accounts(self) -> list[AccountSummary]:
        users = await self._search_all(USERS, self._in_organisation(), _users_in)
        roles: dict[str, list[str]] = {}
        for grant in await self._grants():
            roles.setdefault(grant.userId, []).extend(grant.roleKeys or [])
        return [_summary(user, roles.get(user.userId, [])) for user in users]

    async def disable(self, account_id: str) -> None:
        path = _user_path(account_id, "deactivate")
        await self._send(HTTPMethod.POST, path, bad_request=BadRequestMeans.ALREADY_DONE)

    async def enable(self, account_id: str) -> None:
        path = _user_path(account_id, "reactivate")
        await self._send(HTTPMethod.POST, path, bad_request=BadRequestMeans.ALREADY_DONE)

    async def _require_account(self, account_id: str) -> None:
        await self._send(HTTPMethod.GET, _user_path(account_id))

    async def grant_global_role(self, account_id: str, role: str) -> None:
        await self._require_account(account_id)
        held = await self._grants(account_id)
        if not held:
            body = ZitadelGrantRequest(projectId=self._project_id, roleKeys=[role])
            await self._send(
                HTTPMethod.POST,
                user_grant_path(account_id),
                body,
                bad_request=BadRequestMeans.MISSING_ROLE,
            )
            return
        roles = held[0].roleKeys or []
        if role not in roles:
            await self._send(
                HTTPMethod.PUT,
                user_grant_path(account_id, held[0].id),
                ZitadelGrantRequest(roleKeys=[*roles, role]),
                bad_request=BadRequestMeans.MISSING_ROLE,
            )

    async def remove_global_role(self, account_id: str, role: str) -> None:
        await self._require_account(account_id)
        held = await self._grants(account_id)
        roles = held[0].roleKeys or [] if held else []
        if role not in roles:
            return
        remaining = [r for r in roles if r != role]
        path = user_grant_path(account_id, held[0].id)
        if remaining:
            await self._send(HTTPMethod.PUT, path, ZitadelGrantRequest(roleKeys=remaining))
        else:
            await self._send(HTTPMethod.DELETE, path)

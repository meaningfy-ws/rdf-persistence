"""The Zitadel implementation of the ``Identity`` port, over the v2 user API and the management API.

A global role is a role of the configured project, granted to the user (a user grant); the roles
claim of a token carries them (``access-control.adoc#identity``).
"""

import logging
from collections.abc import Sequence
from http import HTTPMethod, HTTPStatus
from types import TracebackType
from typing import Self
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from rdf_persistence.domain.exceptions import IdentityUnavailable, NotFound
from rdf_persistence.domain.generated.service.rp_service import AccountSummary

USERS = "/v2/users"
USER_GRANT_SEARCH = "/management/v1/users/grants/_search"
ORG_HEADER = "x-zitadel-orgid"
PAGE_SIZE = 100
ACTIVE_STATE = "USER_STATE_ACTIVE"
EMAIL_EQUALS = "TEXT_QUERY_METHOD_EQUALS"
UNREADABLE = "Zitadel answered with something unreadable"

log = logging.getLogger(__name__)


class _Wire(BaseModel):
    """Zitadel's JSON: camelCase names, and fields this adapter does not read are ignored."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


class _EmailQuery(_Wire):
    email_address: str
    method: str = EMAIL_EQUALS


class _OrganisationQuery(_Wire):
    organization_id: str


class _ProjectQuery(_Wire):
    project_id: str


class _UserQuery(_Wire):
    user_id: str


class _Query(_Wire):
    email_query: _EmailQuery | None = None
    organization_id_query: _OrganisationQuery | None = None
    project_id_query: _ProjectQuery | None = None
    user_id_query: _UserQuery | None = None


class _Window(_Wire):
    offset: int
    limit: int


class _Search(_Wire):
    query: _Window
    queries: Sequence[_Query]


class _GrantRequest(_Wire):
    project_id: str | None = None
    role_keys: Sequence[str]


class _Email(_Wire):
    email: str


class _Human(_Wire):
    email: _Email | None = None


class _User(_Wire):
    user_id: str
    state: str
    username: str
    human: _Human | None = None


class _UserGrant(_Wire):
    id: str
    user_id: str
    role_keys: list[str] = []


class _Answer[T](_Wire):
    result: list[T] = []


class _UserAnswer(_Wire):
    user: _User


def _summary(user: _User, roles: list[str]) -> AccountSummary:
    email = user.human.email.email if user.human and user.human.email else None
    return AccountSummary(
        account_id=user.user_id,
        user_name=user.username,
        email=email,
        active=user.state == ACTIVE_STATE,
        global_roles=roles or None,
    )


def _user_path(account_id: str, *rest: str) -> str:
    return "/".join([USERS, quote(account_id, safe=""), *rest])


def _grant_path(account_id: str, *rest: str) -> str:
    return "/".join(["/management/v1/users", quote(account_id, safe=""), "grants", *rest])


class ZitadelIdentity:
    """An ``Identity`` over a Zitadel instance, authenticated with a service token.

    Args:
        issuer: The base URL of the instance.
        service_token: A token of a machine user allowed to administer the organisation.
        organisation_id: The organisation whose accounts are administered.
        project_id: The project whose roles are the global roles.
    """

    def __init__(
        self,
        issuer: str,
        service_token: str,
        organisation_id: str,
        project_id: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._organisation_id = organisation_id
        self._project_id = project_id
        self._client = httpx.AsyncClient(
            base_url=issuer,
            headers={"Authorization": f"Bearer {service_token}", ORG_HEADER: organisation_id},
            transport=transport,
        )

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _send(
        self,
        method: HTTPMethod,
        path: str,
        body: _Wire | None = None,
        *,
        tolerate_bad_request: bool = False,
        bad_request_is_missing_role: bool = False,
    ) -> httpx.Response:
        """Send a request and map the failures.

        Zitadel answers 400 to a state change that is already done, and to a grant of a role the
        project lacks; the two flags tell the call which of these a 400 means.
        """
        content = body.model_dump_json(by_alias=True, exclude_none=True) if body else "{}"
        try:
            response = await self._client.request(
                method, path, content=content, headers={"Content-Type": "application/json"}
            )
        except httpx.HTTPError as error:
            raise IdentityUnavailable(f"Zitadel is unreachable: {error}") from error
        status = response.status_code
        if status == HTTPStatus.NOT_FOUND:
            raise NotFound(f"Zitadel answered 404 for {path}")
        if status == HTTPStatus.BAD_REQUEST and tolerate_bad_request:
            return response
        if status == HTTPStatus.BAD_REQUEST and bad_request_is_missing_role:
            raise NotFound("the project has no such role")
        if not response.is_success:
            log.debug("Zitadel answered %s: %s", status, response.text)
            raise IdentityUnavailable(f"Zitadel answered {status} for {path}")
        return response

    async def _search_all[T](self, path: str, queries: Sequence[_Query], item: type[T]) -> list[T]:
        """Every item the search finds, page by page."""
        found: list[T] = []
        while True:
            window = _Window(offset=len(found), limit=PAGE_SIZE)
            response = await self._send(
                HTTPMethod.POST, path, _Search(query=window, queries=queries)
            )
            page = self._read(_Answer[item], response)  # type: ignore[valid-type]
            found.extend(page.result)
            if len(page.result) < PAGE_SIZE:
                return found

    @staticmethod
    def _read[M: BaseModel](model: type[M], response: httpx.Response) -> M:
        try:
            return model.model_validate_json(response.content)
        except ValidationError as error:
            raise IdentityUnavailable(UNREADABLE) from error

    def _in_organisation(self, *more: _Query) -> list[_Query]:
        organisation = _OrganisationQuery(organization_id=self._organisation_id)
        return [_Query(organization_id_query=organisation), *more]

    async def _grants(self, account_id: str | None = None) -> list[_UserGrant]:
        queries = [_Query(project_id_query=_ProjectQuery(project_id=self._project_id))]
        if account_id:
            queries.append(_Query(user_id_query=_UserQuery(user_id=account_id)))
        return await self._search_all(USER_GRANT_SEARCH, queries, _UserGrant)

    async def find_by_email(self, email: str) -> AccountSummary:
        by_email = _Query(email_query=_EmailQuery(email_address=email))
        users = await self._search_all(USERS, self._in_organisation(by_email), _User)
        if not users:
            raise NotFound(f"no account with email {email}")
        roles = [role for grant in await self._grants(users[0].user_id) for role in grant.role_keys]
        return _summary(users[0], roles)

    async def list_accounts(self) -> list[AccountSummary]:
        users = await self._search_all(USERS, self._in_organisation(), _User)
        roles: dict[str, list[str]] = {}
        for grant in await self._grants():
            roles.setdefault(grant.user_id, []).extend(grant.role_keys)
        return [_summary(user, roles.get(user.user_id, [])) for user in users]

    async def disable(self, account_id: str) -> None:
        await self._send(
            HTTPMethod.POST, _user_path(account_id, "deactivate"), tolerate_bad_request=True
        )

    async def enable(self, account_id: str) -> None:
        await self._send(
            HTTPMethod.POST, _user_path(account_id, "reactivate"), tolerate_bad_request=True
        )

    async def _require_account(self, account_id: str) -> None:
        await self._send(HTTPMethod.GET, _user_path(account_id))

    async def grant_global_role(self, account_id: str, role: str) -> None:
        await self._require_account(account_id)
        held = await self._grants(account_id)
        if not held:
            body = _GrantRequest(project_id=self._project_id, role_keys=[role])
            await self._send(
                HTTPMethod.POST, _grant_path(account_id), body, bad_request_is_missing_role=True
            )
        elif role not in held[0].role_keys:
            body = _GrantRequest(role_keys=[*held[0].role_keys, role])
            await self._send(
                HTTPMethod.PUT,
                _grant_path(account_id, held[0].id),
                body,
                bad_request_is_missing_role=True,
            )

    async def remove_global_role(self, account_id: str, role: str) -> None:
        await self._require_account(account_id)
        held = await self._grants(account_id)
        if not held or role not in held[0].role_keys:
            return
        remaining = [r for r in held[0].role_keys if r != role]
        path = _grant_path(account_id, held[0].id)
        if remaining:
            await self._send(HTTPMethod.PUT, path, _GrantRequest(role_keys=remaining))
        else:
            await self._send(HTTPMethod.DELETE, path)

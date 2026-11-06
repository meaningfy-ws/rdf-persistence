"""The two dependencies every route has: the verified caller, and the access check (PD-9).

The token is verified first, then the caller's grants in the tenant are loaded in one query and the
route's action is checked on its target. A refusal is raised before the route's own code runs.
"""

from typing import Annotated

from fastapi import Depends, Header

from rdf_persistence.domain.exceptions import InvalidToken
from rdf_persistence.domain.generated.rp_access import Action
from rdf_persistence.domain.generated.service.rp_service import CallerAccess, VerifiedCaller
from rdf_persistence.entrypoints.kit import ServiceKit
from rdf_persistence.services.access import load_caller_access

BEARER_SCHEME = "bearer"


class Gate:
    """Builds the dependencies of the routes of one service."""

    def __init__(self, kit: ServiceKit) -> None:
        self._kit = kit

    async def caller(self, authorization: Annotated[str | None, Header()] = None) -> VerifiedCaller:
        """The caller the request's bearer token identifies.

        Raises:
            InvalidToken: No bearer token, or one the verifier refuses.
        """
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != BEARER_SCHEME or not token.strip():
            raise InvalidToken("a bearer token is required")
        return await self._kit.verifier.verify(token.strip())

    async def check(
        self, caller: VerifiedCaller, tenant: str, target: str, action: Action
    ) -> CallerAccess:
        """The caller's access to ``tenant``, after checking that it may take ``action`` on ``target``.

        Raises:
            NotFound: The tenant or the target is not visible to the caller.
            Forbidden: The caller may see it but not take ``action``.
        """
        system = self._kit.system_database
        access = await load_caller_access(self._kit.store, system, tenant, caller.principal)
        self._kit.rules.require(caller, access, target, action)
        return access

    def tenant(self, action: Action):
        """A dependency: ``action`` on the tenant of the path."""

        async def permitted(
            t: str, caller: Annotated[VerifiedCaller, Depends(self.caller)]
        ) -> CallerAccess:
            tenant = self._kit.tenant_iri(t)
            return await self.check(caller, tenant, tenant, action)

        return permitted

    def aggregate(self, rp_path: str, action: Action):
        """A dependency: ``action`` on the aggregate of the path, below ``rp_path``."""

        async def permitted(
            t: str, aggregate_id: str, caller: Annotated[VerifiedCaller, Depends(self.caller)]
        ) -> CallerAccess:
            tenant = self._kit.tenant_iri(t)
            return await self.check(caller, tenant, f"{tenant}/{rp_path}/{aggregate_id}", action)

        return permitted

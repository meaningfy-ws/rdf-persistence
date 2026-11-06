"""The generic router: tenant routes, and aggregate routes for every type of the schema (PD-13, PD-14).

The routes are built when the service is installed, from the schema as it is then: a class added to the
model and a restart add its routes. Each route names the action it needs (PD-9); the access check runs
as a dependency, so a refused request never reaches the route's own code. Writes carry the version
of what they replace in ``If-Match`` (428 without, 409 when stale).

Task 5.4 adds the listing of an aggregate type (``GET /{tenant_segment}/{t}/{rp_path}``) and pages the
listing of tenants; the seams are ``add_aggregate_routes`` and ``TenantApi.listing``.
"""

import json
from collections.abc import Iterable
from typing import cast

from fastapi import APIRouter, Depends, Request, Response
from linkml_runtime.linkml_model.meta import ClassDefinition
from pydantic import BaseModel

from rdf_persistence.domain.exceptions import Forbidden, InvalidBody, NotFound
from rdf_persistence.domain.generated.rp_access import Action
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.generated.service.rp_service import (
    CallerAccess,
    GrantSet,
    LabelUpdate,
    Page,
    TenantCreate,
    TenantSummary,
    VerifiedCaller,
)
from rdf_persistence.domain.iris import mint_aggregate_iri
from rdf_persistence.domain.sparql import Triple
from rdf_persistence.entrypoints.auth import Gate
from rdf_persistence.entrypoints.kit import ServiceKit
from rdf_persistence.entrypoints.negotiation import (
    accepted_media_type,
    expected_version,
    request_media_type,
)
from rdf_persistence.entrypoints.responses import (
    ACCEPT,
    CONTEXT_ROUTE,
    document_response,
    model_response,
)
from rdf_persistence.services.documents import JSON, JSON_LD

IF_MATCH = "If-Match"
CONTENT_TYPE = "Content-Type"
CONTEXT_FILE_NAME = "context.jsonld"
NO_CONTENT = 204
CREATED = 201


def _last_segment(path_or_iri: str) -> str:
    return path_or_iri.rstrip("/").rsplit("/", 1)[-1]


async def read_model[M: BaseModel](request: Request, model: type[M]) -> M:
    """The JSON body of the request as a ``model``.

    Raises:
        UnsupportedMediaType: The body is not JSON.
        ValidationError: The body is not valid JSON, or does not fit the model (pydantic's).
    """
    request_media_type(request.headers.get(CONTENT_TYPE), (JSON,))
    return model.model_validate_json(await request.body())


class DocumentApi:
    """Reads, creates, replaces and removes the documents of one class of the schema (PD-14)."""

    def __init__(self, kit: ServiceKit, cls: ClassDefinition) -> None:
        self._kit = kit
        self._cls = cls

    async def read(
        self, request: Request, caller: VerifiedCaller, tenant: str, iri: str
    ) -> Response:
        media_type = accepted_media_type(request.headers.get(ACCEPT))
        async with self._kit.session(tenant, caller.principal) as session:
            stored, graph, version = await session.get_graph(iri)
        return await document_response(
            request, self._kit.documents, stored, graph, self._cls, media_type, version
        )

    async def _body(self, request: Request, iri: str, *, creating: bool) -> Iterable[Triple]:
        """The validated triples of the request's body, rooted at ``iri``."""
        media_type = request_media_type(request.headers.get(CONTENT_TYPE), (JSON, JSON_LD))
        documents = self._kit.documents
        graph = await documents.parse(
            await request.body(), media_type, self._cls, iri, creating=creating
        )
        await documents.validate(graph)
        # rdflib types a graph's terms as Node; a parsed body holds only URIs, literals and blank nodes
        return cast(Iterable[Triple], graph)

    async def create(
        self, request: Request, caller: VerifiedCaller, tenant: str, rp_path: str
    ) -> Response:
        media_type = accepted_media_type(request.headers.get(ACCEPT))
        iri = str(mint_aggregate_iri(tenant, rp_path))
        triples = await self._body(request, iri, creating=True)
        async with self._kit.session(tenant, caller.principal) as session:
            await session.add_graph(iri, triples)
            stored, graph, version = await session.get_graph(iri)
        return await document_response(
            request,
            self._kit.documents,
            stored,
            graph,
            self._cls,
            media_type,
            version,
            status=CREATED,
            location=f"{request.url.path.rstrip('/')}/{_last_segment(iri)}",
        )

    async def replace(
        self, request: Request, caller: VerifiedCaller, tenant: str, iri: str
    ) -> Response:
        media_type = accepted_media_type(request.headers.get(ACCEPT))
        expected = expected_version(request.headers.get(IF_MATCH))
        triples = await self._body(request, iri, creating=False)
        async with self._kit.session(tenant, caller.principal) as session:
            await session.replace_graph(iri, triples, expected)
            stored, graph, version = await session.get_graph(iri)
        return await document_response(
            request, self._kit.documents, stored, graph, self._cls, media_type, version
        )

    async def remove(
        self, request: Request, caller: VerifiedCaller, tenant: str, iri: str
    ) -> Response:
        expected = expected_version(request.headers.get(IF_MATCH))
        async with self._kit.session(tenant, caller.principal) as session:
            await session.remove(iri, expected)
        return Response(status_code=NO_CONTENT)


class TenantApi:
    """The tenant routes: create, list, delete, the grants and the label."""

    def __init__(self, kit: ServiceKit, gate: Gate) -> None:
        self._kit = kit
        self._gate = gate

    async def create(self, request: Request, caller: VerifiedCaller) -> Response:
        body = await read_model(request, TenantCreate)
        summary = await self._kit.tenancy.create(
            body.label, self._root(body), Principal(id=caller.principal)
        )
        location = f"{request.url.path.rstrip('/')}/{_last_segment(summary.id)}"
        return model_response(summary, status=CREATED, location=location)

    def _root(self, body: TenantCreate) -> BaseModel:
        """The tenant's root object: the slots of the body, the label defaulting to the tenant's."""
        if not isinstance(body.root, dict):
            raise InvalidBody("root must be an object holding the slots of the tenant's root")
        if "id" in body.root:
            raise InvalidBody("the service assigns the IRI of a new tenant")
        placeholder = {
            "id": self._kit.settings.base,
            "label": body.label,
        }  # replaced by the minted IRI
        return self._kit.tenant_root_model.model_validate({**placeholder, **body.root})

    async def listing(self, caller: VerifiedCaller) -> Response:
        """The tenants the caller may read, all of them in one page (task 5.4 pages it)."""
        visible = [t for t in await self._kit.tenancy.tenants() if await self._may_read(caller, t)]
        page = Page(items=visible, total=len(visible), limit=max(len(visible), 1), offset=0)
        return model_response(page)

    async def _may_read(self, caller: VerifiedCaller, tenant: TenantSummary) -> bool:
        try:
            await self._gate.check(caller, tenant.id, tenant.id, Action.READ)
        except (NotFound, Forbidden):
            return False
        return True

    async def delete(self, request: Request, access: CallerAccess) -> Response:
        expected = expected_version(request.headers.get(IF_MATCH))
        await self._kit.tenancy.delete(access.tenant, expected)
        return Response(status_code=NO_CONTENT)

    async def grants(self, access: CallerAccess) -> Response:
        record, version = await self._kit.tenancy.get(access.tenant)
        grants = GrantSet(grants=record.grants, prohibitions=record.prohibitions)
        return model_response(grants, version=version)

    async def set_grants(
        self, request: Request, caller: VerifiedCaller, access: CallerAccess
    ) -> Response:
        expected = expected_version(request.headers.get(IF_MATCH))
        grants = await read_model(request, GrantSet)
        self._kit.rules.validate_grants(grants, access.tenant)
        version = await self._kit.tenancy.set_grants(
            access.tenant, grants, expected, Principal(id=caller.principal)
        )
        return model_response(grants, version=version)

    async def set_label(
        self, request: Request, caller: VerifiedCaller, access: CallerAccess
    ) -> Response:
        expected = expected_version(request.headers.get(IF_MATCH))
        update = await read_model(request, LabelUpdate)
        version = await self._kit.tenancy.rename(
            access.tenant, update.label, expected, Principal(id=caller.principal)
        )
        summary = TenantSummary(id=access.tenant, label=update.label, state=TenantState.ACTIVE)
        return model_response(summary, version=version)


def add_tenant_routes(router: APIRouter, kit: ServiceKit, gate: Gate) -> None:
    """``/{tenant_segment}`` and below: the tenants, their root object, grants and label (PD-13)."""
    api = TenantApi(kit, gate)
    root = DocumentApi(kit, kit.documents.tenant_root)
    segment = kit.settings.tenant_segment
    collection, member = f"/{segment}", f"/{segment}/{{t}}"
    as_caller = Depends(gate.caller)
    may_read = Depends(gate.tenant(Action.READ))
    may_modify = Depends(gate.tenant(Action.MODIFY))
    may_delete = Depends(gate.tenant(Action.DELETE))
    may_administer = Depends(gate.tenant(Action.ADMINISTER))

    async def create(request: Request, caller: VerifiedCaller = as_caller) -> Response:
        return await api.create(request, caller)

    async def listing(caller: VerifiedCaller = as_caller) -> Response:
        return await api.listing(caller)

    async def read_root(
        request: Request, caller: VerifiedCaller = as_caller, access: CallerAccess = may_read
    ) -> Response:
        return await root.read(request, caller, access.tenant, access.tenant)

    async def replace_root(
        request: Request, caller: VerifiedCaller = as_caller, access: CallerAccess = may_modify
    ) -> Response:
        return await root.replace(request, caller, access.tenant, access.tenant)

    async def delete(request: Request, access: CallerAccess = may_delete) -> Response:
        return await api.delete(request, access)

    async def grants(access: CallerAccess = may_administer) -> Response:
        return await api.grants(access)

    async def set_grants(
        request: Request, caller: VerifiedCaller = as_caller, access: CallerAccess = may_administer
    ) -> Response:
        return await api.set_grants(request, caller, access)

    async def set_label(
        request: Request, caller: VerifiedCaller = as_caller, access: CallerAccess = may_modify
    ) -> Response:
        return await api.set_label(request, caller, access)

    routes = (
        (collection, "GET", listing),
        (collection, "POST", create),
        (member, "GET", read_root),
        (member, "PUT", replace_root),
        (member, "DELETE", delete),
        (f"{member}/grants", "GET", grants),
        (f"{member}/grants", "PUT", set_grants),
        (f"{member}/label", "PUT", set_label),
    )
    for path, method, endpoint in routes:
        router.add_api_route(path, endpoint, methods=[method], response_model=None)


def add_aggregate_routes(
    router: APIRouter, kit: ServiceKit, gate: Gate, rp_path: str, cls: ClassDefinition
) -> None:
    """``/{tenant_segment}/{t}/{rp_path}`` and ``…/{aggregate_id}`` for one aggregate type (PD-13)."""
    api = DocumentApi(kit, cls)
    collection = f"/{kit.settings.tenant_segment}/{{t}}/{rp_path}"
    member = f"{collection}/{{aggregate_id}}"
    as_caller = Depends(gate.caller)
    may_create = Depends(gate.tenant(Action.MODIFY))
    may_read = Depends(gate.aggregate(rp_path, Action.READ))
    may_modify = Depends(gate.aggregate(rp_path, Action.MODIFY))
    may_delete = Depends(gate.aggregate(rp_path, Action.DELETE))

    def iri(access: CallerAccess, aggregate_id: str) -> str:
        return f"{access.tenant}/{rp_path}/{aggregate_id}"

    async def create(
        request: Request, caller: VerifiedCaller = as_caller, access: CallerAccess = may_create
    ) -> Response:
        return await api.create(request, caller, access.tenant, rp_path)

    async def read(
        request: Request,
        aggregate_id: str,
        caller: VerifiedCaller = as_caller,
        access: CallerAccess = may_read,
    ) -> Response:
        return await api.read(request, caller, access.tenant, iri(access, aggregate_id))

    async def replace(
        request: Request,
        aggregate_id: str,
        caller: VerifiedCaller = as_caller,
        access: CallerAccess = may_modify,
    ) -> Response:
        return await api.replace(request, caller, access.tenant, iri(access, aggregate_id))

    async def remove(
        request: Request,
        aggregate_id: str,
        caller: VerifiedCaller = as_caller,
        access: CallerAccess = may_delete,
    ) -> Response:
        return await api.remove(request, caller, access.tenant, iri(access, aggregate_id))

    router.add_api_route(collection, create, methods=["POST"], response_model=None)
    router.add_api_route(member, read, methods=["GET"], response_model=None)
    router.add_api_route(member, replace, methods=["PUT"], response_model=None)
    router.add_api_route(member, remove, methods=["DELETE"], response_model=None)


def add_context_route(router: APIRouter, kit: ServiceKit) -> None:
    """``GET /context.jsonld``: the generated context, public, so the ``Link`` header leads somewhere."""

    async def context() -> Response:
        body = {"@context": kit.documents.context}
        return Response(json.dumps(body, ensure_ascii=False), media_type=JSON_LD)

    router.add_api_route(
        f"/{CONTEXT_FILE_NAME}", context, methods=["GET"], name=CONTEXT_ROUTE, response_model=None
    )


def build_router(kit: ServiceKit) -> APIRouter:
    """The router of the service: the context, the tenant routes, and the routes of each aggregate type."""
    router = APIRouter()
    gate = Gate(kit)
    add_context_route(router, kit)
    add_tenant_routes(router, kit, gate)
    for rp_path, cls in kit.documents.aggregates.items():
        add_aggregate_routes(router, kit, gate, rp_path, cls)
    return router

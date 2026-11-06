"""The generic router: tenant routes, and aggregate routes for every type of the schema (PD-13, PD-14).

The routes are built when the service is installed, from the schema as it is then: a class added to the
model and a restart add its routes. Each route names the action it needs (PD-9); the access check runs
as a dependency, so a refused request never reaches the route's own code. Writes carry the version
of what they replace in ``If-Match`` (428 without, 409 when stale).

A listing (``GET /{tenant_segment}/{t}/{rp_path}``) needs ``read`` on the tenant: a permission on one
aggregate alone lists nothing. It leaves out the aggregates a Prohibition of ``read`` hides from the
caller, before it counts and pages. It is JSON or JSON-LD, never Turtle (PD-15).
"""

import json
from collections.abc import Iterable
from typing import Any, cast

from fastapi import APIRouter, Depends, Request, Response
from linkml_runtime.linkml_model.meta import ClassDefinition
from pydantic import BaseModel
from rdflib import Graph, URIRef

from rdf_persistence.domain.exceptions import BadQuery, InvalidBody, PayloadTooLarge
from rdf_persistence.domain.generated.rp_access import Action
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.generated.service.rp_service import (
    Authorised,
    CallerAccess,
    GrantSet,
    LabelUpdate,
    Page,
    TenantCreate,
    TenantSummary,
    VerifiedCaller,
)
from rdf_persistence.domain.iris import graph_iri, mint_aggregate_iri
from rdf_persistence.domain.sparql import Triple
from rdf_persistence.entrypoints.auth import Gate
from rdf_persistence.entrypoints.kit import CONTEXT_FILE_NAME, ServiceKit
from rdf_persistence.entrypoints.negotiation import (
    accepted_listing_type,
    accepted_media_type,
    expected_version,
    request_media_type,
)
from rdf_persistence.entrypoints.openapi import AggregateOpenApi, TenantOpenApi
from rdf_persistence.entrypoints.responses import (
    ACCEPT,
    document_response,
    model_response,
    page_response,
)
from rdf_persistence.services.documents import JSON, JSON_LD
from rdf_persistence.services.listing import items_of, list_request, total_of

IF_MATCH = "If-Match"
CONTENT_TYPE = "Content-Type"
CONTENT_LENGTH = "Content-Length"
CONTEXT_ROUTE = "context"
NO_CONTENT = 204
CREATED = 201


def _last_segment(path_or_iri: str) -> str:
    return path_or_iri.rstrip("/").rsplit("/", 1)[-1]


async def limited_body(request: Request, limit: int) -> bytes:
    """The body of the request, if it is at most ``limit`` bytes.

    A ``Content-Length`` over the limit is refused before a byte is read, and a body without one
    (chunked) is refused as soon as it has outgrown the limit.

    Raises:
        PayloadTooLarge: The body is larger than ``limit``.
    """
    refusal = PayloadTooLarge(f"a body holds at most {limit} bytes")
    declared = request.headers.get(CONTENT_LENGTH, "")
    if declared.isdigit() and int(declared) > limit:
        raise refusal
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise refusal
        chunks.append(chunk)
    return b"".join(chunks)


async def read_model[M: BaseModel](request: Request, model: type[M], limit: int) -> M:
    """The JSON body of the request as a ``model``.

    Raises:
        UnsupportedMediaType: The body is not JSON.
        PayloadTooLarge: The body is larger than ``limit`` bytes.
        ValidationError: The body is not valid JSON, or does not fit the model (pydantic's).
    """
    request_media_type(request.headers.get(CONTENT_TYPE), (JSON,))
    return model.model_validate_json(await limited_body(request, limit))


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
            self._kit.context_url,
            self._kit.documents,
            stored,
            graph,
            self._cls,
            media_type,
            version,
        )

    async def listing(
        self, request: Request, caller: VerifiedCaller, access: CallerAccess
    ) -> Response:
        """One page of the documents of the class, filtered and sorted as the query string says."""
        media_type = accepted_listing_type(request.headers.get(ACCEPT))
        hidden = self._kit.rules.hidden_graphs(caller, access)
        plan = self._kit.listings.plan(
            self._cls, list_request(request.query_params.multi_items()), hidden
        )
        async with self._kit.session(access.tenant, caller.principal) as session:
            answer = await session.page(plan)
        items = [await self._item(*item, media_type) for item in items_of(answer, plan)]
        page = Page(items=items, total=total_of(answer, plan), limit=plan.limit, offset=plan.offset)
        return page_response(self._kit.context_url, page, media_type)

    async def _item(self, root: URIRef, graph: Graph, media_type: str) -> object:
        body = await self._kit.documents.render(graph, graph_iri(root), self._cls, media_type)
        return json.loads(body)

    async def _body(self, request: Request, iri: str, *, creating: bool) -> Iterable[Triple]:
        """The validated triples of the request's body, rooted at ``iri``."""
        media_type = request_media_type(request.headers.get(CONTENT_TYPE), (JSON, JSON_LD))
        documents = self._kit.documents
        body = await limited_body(request, self._kit.max_body_bytes)
        graph = await documents.parse(body, media_type, self._cls, iri, creating=creating)
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
            self._kit.context_url,
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
            self._kit.context_url,
            self._kit.documents,
            stored,
            graph,
            self._cls,
            media_type,
            version,
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

    def __init__(self, kit: ServiceKit) -> None:
        self._kit = kit

    async def create(self, request: Request, caller: VerifiedCaller) -> Response:
        body = await read_model(request, TenantCreate, self._kit.max_body_bytes)
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

    async def listing(self, request: Request, caller: VerifiedCaller) -> Response:
        """One page of the tenants the caller may read, ordered by IRI.

        Raises:
            BadQuery: The query has a filter or a sort key (tenants are paged only), or a bad
                ``limit`` or ``offset``.
        """
        paging = list_request(request.query_params.multi_items())
        if paging.filters or paging.sort:
            raise BadQuery("tenants are listed by IRI; only limit and offset are taken")
        assert paging.limit is not None and paging.offset is not None, "ListRequest defaults"
        page = await self._kit.tenancy.visible_tenants(
            caller, self._kit.rules, limit=paging.limit, offset=paging.offset
        )
        return model_response(page)

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
        grants = await read_model(request, GrantSet, self._kit.max_body_bytes)
        self._kit.rules.validate_grants(grants, access.tenant)
        version = await self._kit.tenancy.set_grants(
            access.tenant, grants, expected, Principal(id=caller.principal)
        )
        return model_response(grants, version=version)

    async def set_label(
        self, request: Request, caller: VerifiedCaller, access: CallerAccess
    ) -> Response:
        expected = expected_version(request.headers.get(IF_MATCH))
        update = await read_model(request, LabelUpdate, self._kit.max_body_bytes)
        version = await self._kit.tenancy.rename(
            access.tenant, update.label, expected, Principal(id=caller.principal)
        )
        summary = TenantSummary(id=access.tenant, label=update.label, state=TenantState.ACTIVE)
        return model_response(summary, version=version)


def _add(router: APIRouter, path: str, method: str, endpoint, docs: dict[str, Any]) -> None:
    router.add_api_route(path, endpoint, methods=[method], response_model=None, **docs)


def add_tenant_routes(router: APIRouter, kit: ServiceKit, gate: Gate) -> None:
    """``/{tenant_segment}`` and below: the tenants, their root object, grants and label (PD-13)."""
    api = TenantApi(kit)
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

    async def listing(request: Request, caller: VerifiedCaller = as_caller) -> Response:
        return await api.listing(request, caller)

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

    docs = TenantOpenApi(kit.documents.tenant_root)
    routes = (
        (collection, "GET", listing, docs.listing()),
        (collection, "POST", create, docs.create()),
        (member, "GET", read_root, docs.read_root()),
        (member, "PUT", replace_root, docs.replace_root()),
        (member, "DELETE", delete, docs.delete()),
        (f"{member}/grants", "GET", grants, docs.grants()),
        (f"{member}/grants", "PUT", set_grants, docs.set_grants()),
        (f"{member}/label", "PUT", set_label, docs.set_label()),
    )
    for path, method, endpoint, doc in routes:
        _add(router, path, method, endpoint, doc)


def add_aggregate_routes(
    router: APIRouter, kit: ServiceKit, gate: Gate, rp_path: str, cls: ClassDefinition
) -> None:
    """``/{tenant_segment}/{t}/{rp_path}`` and ``…/{aggregate_id}`` for one aggregate type (PD-13)."""
    api = DocumentApi(kit, cls)
    collection = f"/{kit.settings.tenant_segment}/{{t}}/{rp_path}"
    member = f"{collection}/{{aggregate_id}}"
    as_caller = Depends(gate.caller)
    may_create = Depends(gate.tenant(Action.MODIFY))
    may_list = Depends(gate.tenant(Action.READ))
    may_read = Depends(gate.aggregate(rp_path, Action.READ))
    may_modify = Depends(gate.aggregate(rp_path, Action.MODIFY))
    may_delete = Depends(gate.aggregate(rp_path, Action.DELETE))

    async def listing(
        request: Request, caller: VerifiedCaller = as_caller, access: CallerAccess = may_list
    ) -> Response:
        return await api.listing(request, caller, access)

    async def create(
        request: Request, caller: VerifiedCaller = as_caller, access: CallerAccess = may_create
    ) -> Response:
        return await api.create(request, caller, access.tenant, rp_path)

    async def read(
        request: Request,
        caller: VerifiedCaller = as_caller,
        checked: Authorised = may_read,
    ) -> Response:
        return await api.read(request, caller, checked.caller_access.tenant, checked.checked_target)

    async def replace(
        request: Request,
        caller: VerifiedCaller = as_caller,
        checked: Authorised = may_modify,
    ) -> Response:
        tenant = checked.caller_access.tenant
        return await api.replace(request, caller, tenant, checked.checked_target)

    async def remove(
        request: Request,
        caller: VerifiedCaller = as_caller,
        checked: Authorised = may_delete,
    ) -> Response:
        tenant = checked.caller_access.tenant
        return await api.remove(request, caller, tenant, checked.checked_target)

    docs = AggregateOpenApi(kit.view, cls, rp_path)
    _add(router, collection, "GET", listing, docs.listing())
    _add(router, collection, "POST", create, docs.create())
    _add(router, member, "GET", read, docs.read())
    _add(router, member, "PUT", replace, docs.replace())
    _add(router, member, "DELETE", remove, docs.remove())


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
    gate = kit.gate
    add_context_route(router, kit)
    add_tenant_routes(router, kit, gate)
    for rp_path, cls in kit.documents.aggregates.items():
        add_aggregate_routes(router, kit, gate, rp_path, cls)
    return router

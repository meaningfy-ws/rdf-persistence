"""The OpenAPI document of the service: what each route takes and answers, over the schema (PD-13, PD-24).

The router builds its routes from the schema, and so does this module build what the document says
about them: for each aggregate type the listing with a query parameter per filterable slot, the
request and response bodies, the version headers, and the problem responses the error matrix gives
the route. The bodies refer to component schemas that ``rp-generate`` wrote at generation time, over
the application's schema and the toolkit's own (``generation.components``); ``install_openapi`` reads
those files when the service is installed and adds the schemas to the document when it is first
built, so a running service needs no generator. The tenant routes read their bodies by hand, so
their bodies are declared here too.

The pieces are ``fastapi.openapi.models`` objects, the typed model of the OpenAPI specification;
only the last step, which hands a route to the router, turns them into the mappings FastAPI's
``add_api_route`` takes.
"""

import copy
from collections.abc import Callable, Iterable
from enum import Enum
from http import HTTPMethod, HTTPStatus

from fastapi import APIRouter, FastAPI
from fastapi.openapi.models import (
    Components,
    Header,
    HTTPBearer,
    MediaType,
    OpenAPI,
    Operation,
    Parameter,
    ParameterInType,
    Reference,
    RequestBody,
    Response,
    Schema,
)
from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import Field

from rdf_persistence.domain.generated.service.rp_service import (
    GrantSet,
    LabelUpdate,
    ListRequest,
    Page,
    Problem,
    ProblemKind,
    TenantCreate,
    TenantSummary,
)
from rdf_persistence.domain.media import JSON, JSON_LD, PROBLEM_JSON, TURTLE
from rdf_persistence.entrypoints import problems
from rdf_persistence.entrypoints.auth import BEARER_SCHEME
from rdf_persistence.entrypoints.kit import ServiceKit
from rdf_persistence.entrypoints.negotiation import (
    ALLOWED_ACTIONS,
    ETAG,
    IF_MATCH,
    LOCATION,
    RECORD_ETAG,
    allowed_actions_value,
)
from rdf_persistence.entrypoints.problems import WWW_AUTHENTICATE
from rdf_persistence.services.access import ACTIONS
from rdf_persistence.services.artifacts import COMPONENT_REFERENCES, PROPERTIES, REF
from rdf_persistence.services.components import TOOLKIT_FOLDER, JsonSchema, component_schemas
from rdf_persistence.services.listing import (
    DESCENDING,
    LIMIT,
    OFFSET,
    SORT,
    listable_slots,
    sort_keys,
)
from rdf_persistence.services.schema_structure import DESCRIPTION

BEARER_AUTH = "bearerAuth"
# The toolkit's own bodies, by the class of rp_service.yaml; every route that has one names it here.
TOOLKIT_BODIES = tuple(
    cls.__name__
    for cls in (Page, Problem, TenantCreate, TenantSummary, LabelUpdate, GrantSet, ListRequest)
)
DEFAULT = "default"
# What FastAPI is given beside the answers and the status of a route: the rest of its operation.
_OPERATION_PARTS = ("parameters", "requestBody", "security")

# The problems of each kind of route, in the order of the status codes (the error matrix).
_AUTHENTICATED = (problems.INVALID_TOKEN, problems.UNAVAILABLE)
_IN_A_TENANT = (problems.FORBIDDEN, problems.NOT_FOUND)
_READS = (*_AUTHENTICATED, *_IN_A_TENANT, problems.NOT_ACCEPTABLE)
_WRITES = (*_AUTHENTICATED, *_IN_A_TENANT, problems.CONFLICT)
_BODY = (problems.PAYLOAD_TOO_LARGE, problems.UNSUPPORTED_MEDIA_TYPE, problems.INVALID_BODY)


class RouteDocs(Operation):
    """What the document says about one route: its OpenAPI operation, and the status of its success answer."""

    status_code: HTTPStatus = Field(exclude=True)

    def add_to(
        self, router: APIRouter, path: str, method: HTTPMethod, endpoint: Callable[..., object]
    ) -> None:
        """Register ``endpoint`` on ``router`` at ``path``, documented as this says.

        The answers are declared whole, with a ``default``, which keeps FastAPI from adding its own
        422; the parameters, the request body and the security go in as the operation's extras.
        """
        documented = self.model_dump(by_alias=True, exclude_none=True, mode="json")
        router.add_api_route(
            path,
            endpoint,
            methods=[method],
            response_model=None,
            status_code=self.status_code,
            summary=self.summary,
            tags=list[str | Enum](self.tags or []),
            responses=documented["responses"],
            openapi_extra={k: v for k, v in documented.items() if k in _OPERATION_PARTS},
        )


def _ref(name: str, pointer: str = "") -> Schema:
    return Schema.model_validate({REF: f"{COMPONENT_REFERENCES}{name}{pointer}"})


def _media(schema: Schema, *types: str) -> dict[str, MediaType]:
    return {media_type: MediaType(schema=schema) for media_type in types}


def _document_media(schema: Schema, *, turtle: bool = True) -> dict[str, MediaType]:
    """The representations of a document: JSON by the schema, JSON-LD and Turtle by their own rules."""
    media = {**_media(schema, JSON), **_media(Schema(type="object"), JSON_LD)}
    return {**media, **_media(Schema(type="string"), TURTLE)} if turtle else media


def _problem(kind: ProblemKind) -> Response:
    headers: dict[str, Header | Reference] = {
        WWW_AUTHENTICATE: Header(schema=Schema(type="string"))
    }
    return Response(
        description=kind.title,
        content=_media(_ref(Problem.__name__), PROBLEM_JSON),
        headers=headers if kind == problems.INVALID_TOKEN else None,
    )


def _success(
    content: dict[str, MediaType] | None = None,
    *,
    versioned: bool = False,
    located: bool = False,
    description: str = "Success",
) -> Response:
    headers: dict[str, Header | Reference] = {
        **({ETAG: Header(schema=Schema(type="string"))} if versioned else {}),
        **({LOCATION: Header(schema=Schema(type="string", format="uri"))} if located else {}),
    }
    return Response(description=description, headers=headers or None, content=content)


def _with_allowed_actions(read: Response) -> Response:
    """``read`` with the ``Allowed-Actions`` header documented (PD-10)."""
    read.headers = {
        **(read.headers or {}),
        ALLOWED_ACTIONS: Header(
            description=f"what the caller may do here, comma separated, in the order {allowed_actions_value(ACTIONS)}",
            schema=Schema(type="string"),
        ),
    }
    return read


def _parameter(
    name: str, where: ParameterInType, schema: Schema, *, required: bool, description: str | None
) -> Parameter:
    # the field is called ``in``, a keyword, so the model takes it by its alias
    return Parameter.model_validate(
        {
            "name": name,
            "in": where,
            "required": required,
            DESCRIPTION: description,
            "schema": schema,
        }
    )


def _header(name: str, description: str) -> Parameter:
    return _parameter(
        name, ParameterInType.header, Schema(type="string"), required=True, description=description
    )


def _query(name: str, schema: Schema, description: str | None = None) -> Parameter:
    return _parameter(name, ParameterInType.query, schema, required=False, description=description)


EXPECTED_VERSION = _header(
    IF_MATCH, "The version of the object being replaced or removed, its ETag."
)
_PAGING = (
    _query(
        LIMIT, _ref(ListRequest.__name__, f"{PROPERTIES}{LIMIT}"), "The most items on the page."
    ),
    _query(
        OFFSET,
        _ref(ListRequest.__name__, f"{PROPERTIES}{OFFSET}"),
        "The position of the first item.",
    ),
)


def route_options(
    summary: str,
    tag: str,
    success: tuple[HTTPStatus, Response],
    kinds: Iterable[ProblemKind],
    *,
    parameters: Iterable[Parameter] = (),
    request: RequestBody | None = None,
) -> RouteDocs:
    """The documentation of one operation, to register its route with.

    ``success`` is the status of the answer and what it says; ``kinds`` are the problems the route
    can answer with (the error matrix), each with its fixed title and status.
    """
    status, response = success
    responses: dict[str, Response | object] = {str(status.value): response}
    responses.update(
        {str(kind.status): _problem(kind) for kind in sorted(kinds, key=lambda k: k.status)}
    )
    # Any other failure is a problem as well; declaring it keeps FastAPI from adding its own 422.
    responses[DEFAULT] = Response(
        description="Any other problem", content=_media(_ref(Problem.__name__), PROBLEM_JSON)
    )
    return RouteDocs(
        status_code=status,
        summary=summary,
        tags=[tag],
        responses=responses,
        parameters=list(parameters) or None,
        requestBody=request,
        security=[{BEARER_AUTH: []}],
    )


def _body(schema: Schema, *, documents: bool = False) -> RequestBody:
    """A required request body: plain JSON by the schema, and JSON-LD too for a document."""
    media = _document_media(schema, turtle=False) if documents else _media(schema, JSON)
    return RequestBody(required=True, content=media)


def _page_of(items: Schema) -> Schema:
    """A page whose items are of the given schema."""
    return Schema(
        allOf=[_ref(Page.__name__)], properties={"items": Schema(type="array", items=items)}
    )


class TenantOpenApi:
    """What the document says about each tenant route (PD-13); ``root`` is the tenant root's class."""

    TAG = "tenants"

    def __init__(self, root: ClassDefinition) -> None:
        self._root = _ref(root.name)

    def listing(self) -> RouteDocs:
        page = _success(_media(_page_of(_ref(TenantSummary.__name__)), JSON))
        kinds = (*_AUTHENTICATED, problems.BAD_QUERY)
        return route_options(
            "List the tenants the caller may read",
            self.TAG,
            (HTTPStatus.OK, page),
            kinds,
            parameters=_PAGING,
        )

    def create(self) -> RouteDocs:
        created = _success(_media(_ref(TenantSummary.__name__), JSON), located=True)
        return route_options(
            "Create a tenant",
            self.TAG,
            (HTTPStatus.CREATED, created),
            (*_AUTHENTICATED, *_BODY),
            request=_body(_ref(TenantCreate.__name__)),
        )

    def read_root(self) -> RouteDocs:
        read = _with_allowed_actions(_success(_document_media(self._root), versioned=True))
        read.headers = {
            **(read.headers or {}),
            RECORD_ETAG: Header(
                description="the access record's version; send it as `If-Match` to rename the tenant",
                schema=Schema(type="string"),
            ),
        }
        return route_options(
            "Read the root object of a tenant", self.TAG, (HTTPStatus.OK, read), _READS
        )

    def replace_root(self) -> RouteDocs:
        replaced = _success(_document_media(self._root), versioned=True)
        kinds = (*_WRITES, problems.NOT_ACCEPTABLE, *_BODY, problems.PRECONDITION_REQUIRED)
        return route_options(
            "Replace the root object of a tenant",
            self.TAG,
            (HTTPStatus.OK, replaced),
            kinds,
            parameters=[EXPECTED_VERSION],
            request=_body(self._root, documents=True),
        )

    def delete(self) -> RouteDocs:
        deleted = (HTTPStatus.NO_CONTENT, _success(description="Deleted"))
        kinds = (*_WRITES, problems.PRECONDITION_REQUIRED)
        return route_options(
            "Delete a tenant and everything in it",
            self.TAG,
            deleted,
            kinds,
            parameters=[EXPECTED_VERSION],
        )

    def grants(self) -> RouteDocs:
        read = _success(_media(_ref(GrantSet.__name__), JSON), versioned=True)
        return route_options(
            "Read the grants and prohibitions of a tenant",
            self.TAG,
            (HTTPStatus.OK, read),
            (*_AUTHENTICATED, *_IN_A_TENANT),
        )

    def set_grants(self) -> RouteDocs:
        replaced = _success(_media(_ref(GrantSet.__name__), JSON), versioned=True)
        return route_options(
            "Replace the grants and prohibitions of a tenant",
            self.TAG,
            (HTTPStatus.OK, replaced),
            (*_WRITES, *_BODY, problems.PRECONDITION_REQUIRED),
            parameters=[EXPECTED_VERSION],
            request=_body(_ref(GrantSet.__name__)),
        )

    def set_label(self) -> RouteDocs:
        renamed = _success(_media(_ref(TenantSummary.__name__), JSON), versioned=True)
        return route_options(
            "Rename a tenant",
            self.TAG,
            (HTTPStatus.OK, renamed),
            (*_WRITES, *_BODY, problems.PRECONDITION_REQUIRED),
            parameters=[EXPECTED_VERSION],
            request=_body(_ref(LabelUpdate.__name__)),
        )


def _filter(cls: ClassDefinition, rp_path: str, name: str, slot: SlotDefinition) -> Parameter:
    """A query parameter for a slot, typed by the slot's property in the component schema."""
    pointer = f"{PROPERTIES}{name}" + ("/items" if slot.multivalued else "")
    note = " May be repeated: all the values must be present." if slot.multivalued else ""
    return _query(
        name, _ref(cls.name, pointer), f"Only the {rp_path} whose {name} is this value.{note}"
    )


class AggregateOpenApi:
    """What the document says about the routes of one aggregate type, served at ``rp_path`` (PD-13)."""

    def __init__(self, view: SchemaView, cls: ClassDefinition, rp_path: str) -> None:
        self._view, self._cls, self._tag = view, cls, rp_path
        self._schema = _ref(cls.name)

    def _query_parameters(self) -> list[Parameter]:
        slots = listable_slots(self._view, self._cls)
        order = (
            f"The key to order by; a {DESCENDING} sign before it orders descending. "
            "By IRI if absent."
        )
        return [
            *(_filter(self._cls, self._tag, name, slot) for name, slot in sorted(slots.items())),
            *_PAGING,
            _query(SORT, Schema(type="string", enum=sort_keys(self._view, self._cls)), order),
        ]

    def listing(self) -> RouteDocs:
        page = _success(_document_media(_page_of(self._schema), turtle=False))
        return route_options(
            f"List the {self._tag}",
            self._tag,
            (HTTPStatus.OK, page),
            (*_READS, problems.BAD_QUERY),
            parameters=self._query_parameters(),
        )

    def create(self) -> RouteDocs:
        created = _success(_document_media(self._schema), versioned=True, located=True)
        return route_options(
            f"Create a {self._cls.name}",
            self._tag,
            (HTTPStatus.CREATED, created),
            (*_AUTHENTICATED, *_IN_A_TENANT, problems.NOT_ACCEPTABLE, *_BODY),
            request=_body(self._schema, documents=True),
        )

    def read(self) -> RouteDocs:
        read = _with_allowed_actions(_success(_document_media(self._schema), versioned=True))
        return route_options(f"Read a {self._cls.name}", self._tag, (HTTPStatus.OK, read), _READS)

    def replace(self) -> RouteDocs:
        replaced = _success(_document_media(self._schema), versioned=True)
        kinds = (*_WRITES, problems.NOT_ACCEPTABLE, *_BODY, problems.PRECONDITION_REQUIRED)
        return route_options(
            f"Replace a {self._cls.name}",
            self._tag,
            (HTTPStatus.OK, replaced),
            kinds,
            parameters=[EXPECTED_VERSION],
            request=_body(self._schema, documents=True),
        )

    def remove(self) -> RouteDocs:
        deleted = (HTTPStatus.NO_CONTENT, _success(description="Deleted"))
        return route_options(
            f"Delete a {self._cls.name}",
            self._tag,
            deleted,
            (*_WRITES, problems.PRECONDITION_REQUIRED),
            parameters=[EXPECTED_VERSION],
        )


def component_roots(kit: ServiceKit) -> list[str]:
    """The classes the routes mention: the aggregate types, the tenant root and the toolkit's bodies."""
    classes = [*kit.documents.aggregates.values(), kit.documents.tenant_root]
    return [*(cls.name for cls in classes), *TOOLKIT_BODIES]


def _target_in(raw: dict[str, JsonSchema], pointer: str) -> JsonSchema:
    """A copy of what ``#/components/schemas/<C>/properties/<p>[/items]`` points at, without its description."""
    name, *path = pointer.removeprefix(COMPONENT_REFERENCES).split("/")
    target = raw[name]
    for step in path:
        target = target[step]
    return {k: copy.deepcopy(v) for k, v in target.items() if k != DESCRIPTION}


def _inline_property_refs(document: OpenAPI, raw: dict[str, JsonSchema]) -> None:
    """Replace each parameter schema that points into a property by a copy of its target in ``raw`` (PD-4).

    openapi-typescript renders such a pointer as an indexed access on an optional property, which
    ``tsc --strict`` rejects. FastAPI's model keeps the path items of the routes as plain mappings
    (``paths`` is typed ``PathItem | Any``); a path item it did validate has no such parameters.
    """
    paths: list[object] = list((document.paths or {}).values())
    for path in (p for p in paths if isinstance(p, dict)):
        for method in HTTPMethod:
            for parameter in path.get(method.lower(), {}).get("parameters", []):
                pointer = parameter["schema"].get(REF, "")
                if PROPERTIES in pointer:
                    parameter["schema"] = _target_in(raw, pointer)


def install_openapi(app: FastAPI, kit: ServiceKit) -> None:
    """Make ``app`` publish the component schemas of the routes and the bearer scheme in its document.

    The schemas are those the generator wrote next to the application's context and in the toolkit's
    own package, read now so that a generated folder without them stops the service at start-up.

    Raises:
        OSError: The generated folder has no components file (it was generated by an older toolkit).
    """
    raw = component_schemas((TOOLKIT_FOLDER, kit.generated_folder), component_roots(kit))
    schemas = {name: Schema.model_validate(schema) for name, schema in raw.items()}
    build = app.openapi

    def openapi() -> dict[str, object]:
        if app.openapi_schema is None:
            document = OpenAPI.model_validate(build())
            components = document.components or Components()
            components.schemas = dict(sorted({**(components.schemas or {}), **schemas}.items()))
            components.securitySchemes = {BEARER_AUTH: HTTPBearer(scheme=BEARER_SCHEME)}
            document.components = components
            _inline_property_refs(document, raw)
            app.openapi_schema = document.model_dump(by_alias=True, exclude_none=True, mode="json")
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]

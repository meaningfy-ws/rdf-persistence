"""The OpenAPI document of the service: what each route takes and answers, over the schema (PD-13, PD-24).

The router builds its routes from the schema, and so does this module build what the document says
about them: for each aggregate type the listing with a query parameter per filterable slot, the
request and response bodies, the version headers, and the problem responses the error matrix gives
the route. The bodies refer to component schemas that ``gen-json-schema`` generates over the
application's schema and the toolkit's own (``services.components``); they are added to the document
when it is first built, so a service that never serves its document never needs the generators.
The tenant routes read their bodies by hand, so their bodies are declared here too.

The pieces are ``fastapi.openapi.models`` objects, the typed model of the OpenAPI specification;
only the final step turns them into the mappings FastAPI's ``add_api_route`` takes.
"""

from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.models import (
    Header,
    HTTPBearer,
    MediaType,
    Parameter,
    ParameterInType,
    Reference,
    RequestBody,
    Response,
    Schema,
)
from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.formatutils import underscore
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.domain.generated.service.rp_service import ProblemKind
from rdf_persistence.entrypoints import problems
from rdf_persistence.entrypoints.kit import ServiceKit
from rdf_persistence.entrypoints.problems import PROBLEM_MEDIA_TYPE, WWW_AUTHENTICATE
from rdf_persistence.services.components import (
    COMPONENTS,
    TOOLKIT_FOLDER,
    component_schemas,
)
from rdf_persistence.services.documents import JSON, JSON_LD, TURTLE
from rdf_persistence.services.listing import listable_slots

BEARER_AUTH = "bearerAuth"
IF_MATCH = "If-Match"
# The toolkit's own bodies, by the class of rp_service.yaml; every route that has one names it here.
PAGE, PROBLEM, TENANT_CREATE, TENANT_SUMMARY, LABEL_UPDATE, GRANT_SET, LIST_REQUEST = (
    "Page",
    "Problem",
    "TenantCreate",
    "TenantSummary",
    "LabelUpdate",
    "GrantSet",
    "ListRequest",
)
TOOLKIT_BODIES = (
    PAGE,
    PROBLEM,
    TENANT_CREATE,
    TENANT_SUMMARY,
    LABEL_UPDATE,
    GRANT_SET,
    LIST_REQUEST,
)
SORT, LIMIT, OFFSET = "sort", "limit", "offset"
DESCENDING = "-"
OK, CREATED, NO_CONTENT = 200, 201, 204
DEFAULT = "default"

# The problems of each kind of route, in the order of the status codes (the error matrix).
_AUTHENTICATED = (problems.INVALID_TOKEN, problems.UNAVAILABLE)
_IN_A_TENANT = (problems.FORBIDDEN, problems.NOT_FOUND)
_READS = (*_AUTHENTICATED, *_IN_A_TENANT, problems.NOT_ACCEPTABLE)
_WRITES = (*_AUTHENTICATED, *_IN_A_TENANT, problems.CONFLICT)
_BODY = (problems.PAYLOAD_TOO_LARGE, problems.UNSUPPORTED_MEDIA_TYPE, problems.INVALID_BODY)


def _ref(name: str, pointer: str = "") -> Schema:
    return Schema.model_validate({"$ref": f"{COMPONENTS}{name}{pointer}"})


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
        content=_media(_ref(PROBLEM), PROBLEM_MEDIA_TYPE),
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
        **({"ETag": Header(schema=Schema(type="string"))} if versioned else {}),
        **({"Location": Header(schema=Schema(type="string", format="uri"))} if located else {}),
    }
    return Response(description=description, headers=headers or None, content=content)


def _dumped(model: Any) -> Any:
    return model.model_dump(by_alias=True, exclude_none=True, mode="json")


def _parameter(
    name: str, where: ParameterInType, schema: Schema, *, required: bool, description: str | None
) -> Parameter:
    # the field is called ``in``, a keyword, so the model takes it by its alias
    return Parameter.model_validate(
        {
            "name": name,
            "in": where,
            "required": required,
            "description": description,
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
    _query(LIMIT, _ref(LIST_REQUEST, f"/properties/{LIMIT}"), "The most items on the page."),
    _query(OFFSET, _ref(LIST_REQUEST, f"/properties/{OFFSET}"), "The position of the first item."),
)


def route_options(
    summary: str,
    tag: str,
    success: tuple[int, Response],
    kinds: Iterable[ProblemKind],
    *,
    parameters: Iterable[Parameter] = (),
    request: RequestBody | None = None,
) -> dict[str, Any]:
    """The keyword arguments of ``add_api_route`` that document one operation.

    ``success`` is the status of the answer and what it says; ``kinds`` are the problems the route
    can answer with (the error matrix), each with its fixed title and status.
    """
    status, response = success
    responses: dict[int | str, Response] = {status: response}
    responses.update(
        {kind.status: _problem(kind) for kind in sorted(kinds, key=lambda k: k.status)}
    )
    # Any other failure is a problem as well; declaring it keeps FastAPI from adding its own 422.
    responses[DEFAULT] = Response(
        description="Any other problem", content=_media(_ref(PROBLEM), PROBLEM_MEDIA_TYPE)
    )
    extra: dict[str, Any] = {"security": [{BEARER_AUTH: []}]}
    if parameters := list(parameters):
        extra["parameters"] = [_dumped(p) for p in parameters]
    if request is not None:
        extra["requestBody"] = _dumped(request)
    return {
        "status_code": status,
        "summary": summary,
        "tags": [tag],
        "responses": {code: _dumped(r) for code, r in responses.items()},
        "openapi_extra": extra,
    }


def _body(schema: Schema, *, documents: bool = False) -> RequestBody:
    """A required request body: plain JSON by the schema, and JSON-LD too for a document."""
    media = _document_media(schema, turtle=False) if documents else _media(schema, JSON)
    return RequestBody(required=True, content=media)


def _page_of(items: Schema) -> Schema:
    """A page whose items are of the given schema."""
    return Schema(allOf=[_ref(PAGE)], properties={"items": Schema(type="array", items=items)})


class TenantOpenApi:
    """What the document says about each tenant route (PD-13); ``root`` is the tenant root's class."""

    TAG = "tenants"

    def __init__(self, root: ClassDefinition) -> None:
        self._root = _ref(root.name)

    def listing(self) -> dict[str, Any]:
        page = _success(_media(_page_of(_ref(TENANT_SUMMARY)), JSON))
        kinds = (*_AUTHENTICATED, problems.BAD_QUERY)
        return route_options(
            "List the tenants the caller may read", self.TAG, (OK, page), kinds, parameters=_PAGING
        )

    def create(self) -> dict[str, Any]:
        created = _success(_media(_ref(TENANT_SUMMARY), JSON), located=True)
        return route_options(
            "Create a tenant",
            self.TAG,
            (CREATED, created),
            (*_AUTHENTICATED, *_BODY),
            request=_body(_ref(TENANT_CREATE)),
        )

    def read_root(self) -> dict[str, Any]:
        read = _success(_document_media(self._root), versioned=True)
        return route_options("Read the root object of a tenant", self.TAG, (OK, read), _READS)

    def replace_root(self) -> dict[str, Any]:
        replaced = _success(_document_media(self._root), versioned=True)
        kinds = (*_WRITES, problems.NOT_ACCEPTABLE, *_BODY, problems.PRECONDITION_REQUIRED)
        return route_options(
            "Replace the root object of a tenant",
            self.TAG,
            (OK, replaced),
            kinds,
            parameters=[EXPECTED_VERSION],
            request=_body(self._root, documents=True),
        )

    def delete(self) -> dict[str, Any]:
        deleted = (NO_CONTENT, _success(description="Deleted"))
        kinds = (*_WRITES, problems.PRECONDITION_REQUIRED)
        return route_options(
            "Delete a tenant and everything in it",
            self.TAG,
            deleted,
            kinds,
            parameters=[EXPECTED_VERSION],
        )

    def grants(self) -> dict[str, Any]:
        read = _success(_media(_ref(GRANT_SET), JSON), versioned=True)
        return route_options(
            "Read the grants and prohibitions of a tenant",
            self.TAG,
            (OK, read),
            (*_AUTHENTICATED, *_IN_A_TENANT),
        )

    def set_grants(self) -> dict[str, Any]:
        replaced = _success(_media(_ref(GRANT_SET), JSON), versioned=True)
        return route_options(
            "Replace the grants and prohibitions of a tenant",
            self.TAG,
            (OK, replaced),
            (*_WRITES, *_BODY, problems.PRECONDITION_REQUIRED),
            parameters=[EXPECTED_VERSION],
            request=_body(_ref(GRANT_SET)),
        )

    def set_label(self) -> dict[str, Any]:
        renamed = _success(_media(_ref(TENANT_SUMMARY), JSON), versioned=True)
        return route_options(
            "Rename a tenant",
            self.TAG,
            (OK, renamed),
            (*_WRITES, *_BODY, problems.PRECONDITION_REQUIRED),
            parameters=[EXPECTED_VERSION],
            request=_body(_ref(LABEL_UPDATE)),
        )


def _filter(cls: ClassDefinition, rp_path: str, name: str, slot: SlotDefinition) -> Parameter:
    """A query parameter for a slot, typed by the slot's property in the component schema."""
    pointer = f"/properties/{name}" + ("/items" if slot.multivalued else "")
    note = " May be repeated: all the values must be present." if slot.multivalued else ""
    return _query(
        name, _ref(cls.name, pointer), f"Only the {rp_path} whose {name} is this value.{note}"
    )


class AggregateOpenApi:
    """What the document says about the routes of one aggregate type, served at ``rp_path`` (PD-13)."""

    def __init__(self, view: SchemaView, cls: ClassDefinition, rp_path: str) -> None:
        self._view, self._cls, self._tag = view, cls, rp_path
        self._schema = _ref(cls.name)

    def _sort_keys(self, names: Iterable[str]) -> list[str]:
        identifier = self._view.get_identifier_slot(self._cls.name)
        keys = [*([underscore(identifier.name)] if identifier else []), *sorted(names)]
        return [*keys, *(f"{DESCENDING}{key}" for key in keys)]

    def _query_parameters(self) -> list[Parameter]:
        slots = listable_slots(self._view, self._cls)
        order = "The key to order by; a minus sign before it orders descending. By IRI if absent."
        return [
            *(_filter(self._cls, self._tag, name, slot) for name, slot in sorted(slots.items())),
            *_PAGING,
            _query(SORT, Schema(type="string", enum=self._sort_keys(slots)), order),
        ]

    def listing(self) -> dict[str, Any]:
        page = _success(_document_media(_page_of(self._schema), turtle=False))
        return route_options(
            f"List the {self._tag}",
            self._tag,
            (OK, page),
            (*_READS, problems.BAD_QUERY),
            parameters=self._query_parameters(),
        )

    def create(self) -> dict[str, Any]:
        created = _success(_document_media(self._schema), versioned=True, located=True)
        return route_options(
            f"Create a {self._cls.name}",
            self._tag,
            (CREATED, created),
            (*_AUTHENTICATED, *_IN_A_TENANT, problems.NOT_ACCEPTABLE, *_BODY),
            request=_body(self._schema, documents=True),
        )

    def read(self) -> dict[str, Any]:
        read = _success(_document_media(self._schema), versioned=True)
        return route_options(f"Read a {self._cls.name}", self._tag, (OK, read), _READS)

    def replace(self) -> dict[str, Any]:
        replaced = _success(_document_media(self._schema), versioned=True)
        kinds = (*_WRITES, problems.NOT_ACCEPTABLE, *_BODY, problems.PRECONDITION_REQUIRED)
        return route_options(
            f"Replace a {self._cls.name}",
            self._tag,
            (OK, replaced),
            kinds,
            parameters=[EXPECTED_VERSION],
            request=_body(self._schema, documents=True),
        )

    def remove(self) -> dict[str, Any]:
        deleted = (NO_CONTENT, _success(description="Deleted"))
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


def install_openapi(app: FastAPI, kit: ServiceKit) -> None:
    """Make ``app`` publish the component schemas of the routes and the bearer scheme in its document.

    The schemas are those the generator wrote next to the application's context and in the toolkit's
    own package, read now so that a generated folder without them stops the service at start-up.

    Raises:
        OSError: The generated folder has no components file (it was generated by an older toolkit).
    """
    schemas = component_schemas((TOOLKIT_FOLDER, kit.generated_folder), component_roots(kit))
    build = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            document = build()
            components = document.setdefault("components", {})
            merged = [*components.get("schemas", {}).items(), *schemas.items()]
            components["schemas"] = dict(sorted(merged))
            components["securitySchemes"] = {BEARER_AUTH: _dumped(HTTPBearer(scheme="bearer"))}
        return app.openapi_schema or {}

    app.openapi = openapi  # type: ignore[method-assign]

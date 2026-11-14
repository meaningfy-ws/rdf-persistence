"""Scenario 'the document lists the routes' (rp-service-api): the OpenAPI document over the toy library (task 5.5)."""

import json
from http import HTTPStatus
from typing import Any

import pytest
from openapi_spec_validator import validate

from rdf_persistence.domain.media import JSON, JSON_LD, PROBLEM_JSON, TURTLE
from rdf_persistence.entrypoints.problems import CONFLICT as VERSION_CONFLICT
from rdf_persistence.entrypoints.problems import KEY_CONFLICT, KINDS
from rdf_persistence.services.listing import listable_slots
from rdf_persistence.services.schema_structure import is_internal
from tests.toy_service import ToyService

COMPONENT = "#/components/schemas/"
BOOKKEEPING = {
    "created",
    "modified",
    "creator",
    "contributor",
    "version",
    "graph",
    "kind",
    "owned_by",
}
TENANTS, TENANT = "/libraries", "/libraries/{t}"
SUCCESS = {200, 201, 204}

# (path, method, the statuses it answers with): the problem statuses are the error matrix's
READ = {200, 401, 403, 404, 406, 503}
LIST = {200, 400, 401, 403, 404, 406, 503}
CREATE = {201, 401, 403, 404, 406, 409, 413, 415, 422, 503}
REPLACE = {200, 401, 403, 404, 406, 409, 413, 415, 422, 428, 503}
DELETE = {204, 401, 403, 404, 409, 428, 503}


def aggregate_routes(rp_path: str, *, written: bool = True) -> list[tuple[str, str, set[int]]]:
    """The routes of a root; ``written=False`` for one the consumer writes through a session (PD-3)."""
    collection, member = f"{TENANT}/{rp_path}", f"{TENANT}/{rp_path}/{{aggregate_id}}"
    reads = [(collection, "get", LIST), (member, "get", READ)]
    writes = [(collection, "post", CREATE), (member, "put", REPLACE), (member, "delete", DELETE)]
    return reads + (writes if written else [])


ROUTES = [
    (TENANTS, "get", {200, 400, 401, 503}),
    (TENANTS, "post", {201, 401, 413, 415, 422, 503}),
    (TENANT, "get", READ),
    (TENANT, "put", REPLACE),
    (TENANT, "delete", DELETE),
    (f"{TENANT}/grants", "get", {200, 401, 403, 404, 503}),
    (f"{TENANT}/grants", "put", {200, 401, 403, 404, 409, 413, 415, 422, 428, 503}),
    (f"{TENANT}/label", "put", {200, 401, 403, 404, 409, 413, 415, 422, 428, 503}),
    *aggregate_routes("books"),
    *aggregate_routes("scans", written=False),
    *aggregate_routes("shelves"),
]
IDS = [f"{method.upper()} {path}" for path, method, _ in ROUTES]


@pytest.fixture(scope="module")
def toy() -> ToyService:
    return ToyService()


@pytest.fixture(scope="module")
def document(toy: ToyService) -> dict[str, Any]:
    return toy.app.openapi()


def operation(document: dict, path: str, method: str) -> dict:
    return document["paths"][path][method]


def statuses(op: dict) -> set[int]:
    return {int(status) for status in op["responses"] if status.isdigit()}


def schema_of(media: dict) -> dict:
    return media["schema"]


def test_the_document_is_openapi_3_1_and_valid(document) -> None:
    assert document["openapi"].startswith("3.1"), document["openapi"]
    validate(document)


@pytest.mark.parametrize(("path", "method", "expected"), ROUTES, ids=IDS)
def test_every_route_is_listed_with_its_success_and_problem_responses(
    document, path, method, expected
) -> None:
    assert statuses(operation(document, path, method)) == expected


def test_no_route_of_the_service_is_left_out_of_the_table(document) -> None:
    served = {
        (path, method)
        for path, operations in document["paths"].items()
        for method in operations
        if path != "/context.jsonld"
    }
    assert served == {(path, method) for path, method, _ in ROUTES}


def test_the_service_has_no_route_for_comments(document) -> None:
    """TC-48: the toolkit writes and reads them; a generic GET would leak their audience (PD-11)."""
    assert not [path for path in document["paths"] if "rp-comments" in path]


@pytest.mark.parametrize(("path", "method", "expected"), ROUTES, ids=IDS)
def test_a_problem_response_is_an_rfc_9457_problem_with_the_fixed_title(
    document, path, method, expected
) -> None:
    op = operation(document, path, method)
    # two kinds share 409: the description of a status names the titles of its kinds the route has
    for status in expected - SUCCESS:
        response = op["responses"][str(status)]
        assert schema_of(response["content"][PROBLEM_JSON]) == {"$ref": f"{COMPONENT}Problem"}, (
            f"{status} is a Problem"
        )
        titles = [k.title for k in KINDS if k.status == status]
        assert any(title in response["description"] for title in titles), (
            f"{status} carries the problem's title"
        )


@pytest.mark.parametrize(
    ("path", "method"), [(f"{TENANT}/books", "post"), (f"{TENANT}/books/{{aggregate_id}}", "put")]
)
def test_a_write_that_a_unique_key_can_refuse_lists_the_key_conflict(
    document, path, method
) -> None:  # TC-33
    description = operation(document, path, method)["responses"]["409"]["description"]
    assert KEY_CONFLICT.title in description, "the key conflict is listed"
    if method == "put":
        assert VERSION_CONFLICT.title in description, "beside the version conflict"


def test_fastapis_own_validation_error_is_not_published(document) -> None:
    assert "HTTPValidationError" not in document["components"]["schemas"]
    assert "ValidationError" not in document["components"]["schemas"]


@pytest.mark.parametrize("rp_path", ["books", "scans", "shelves"])
def test_a_listing_takes_a_parameter_per_slot_of_the_type_and_the_paging_ones(
    toy, document, rp_path
) -> None:
    cls = toy.kit.documents.aggregates[rp_path]
    op = operation(document, f"{TENANT}/{rp_path}", "get")
    queries = {p["name"] for p in op["parameters"] if p["in"] == "query"}
    assert queries == {*listable_slots(toy.kit.view, cls), "limit", "offset", "sort"}


def test_the_filters_of_a_book_are_typed_by_the_schema(document) -> None:
    op = operation(document, f"{TENANT}/books", "get")
    params = {p["name"]: p for p in op["parameters"] if p["in"] == "query"}
    assert params["genre"]["schema"] == {"$ref": f"{COMPONENT}Genre"}
    assert params["authors"]["schema"] == {"type": "string"}
    limit = params["limit"]["schema"]
    assert limit["type"] == "integer" and limit["maximum"] == 200
    assert properties(document, "ListRequest")["limit"]["maximum"] == 200, "the bounds of PD-15"
    assert "-label" in params["sort"]["schema"]["enum"], "descending is the name with a minus sign"
    assert not {"creator", "chapters", "id"} & set(params), (
        "bookkeeping, parts and the id are not filters"
    )


def test_no_parameter_points_into_a_property(document) -> None:
    pointing = [
        (path, p["name"])
        for path, methods in document["paths"].items()
        for op in methods.values()
        for p in op.get("parameters", [])
        if "/properties/" in json.dumps(p["schema"])
    ]
    assert pointing == []


def test_a_listing_answers_a_page_of_the_type(document) -> None:
    ok = operation(document, f"{TENANT}/books", "get")["responses"]["200"]["content"]
    page = schema_of(ok[JSON])
    assert page["allOf"] == [{"$ref": f"{COMPONENT}Page"}]
    assert page["properties"]["items"]["items"] == {"$ref": f"{COMPONENT}Book"}
    assert JSON_LD in ok, "and the same page as JSON-LD"
    assert TURTLE not in ok, "never Turtle"


def test_the_tenant_listing_answers_a_page_of_tenant_summaries(document) -> None:
    ok = operation(document, TENANTS, "get")["responses"]["200"]["content"][JSON]
    assert schema_of(ok)["properties"]["items"]["items"] == {"$ref": f"{COMPONENT}TenantSummary"}


def test_a_book_is_created_and_replaced_with_the_json_or_json_ld_body(document) -> None:
    for method, path in (("post", f"{TENANT}/books"), ("put", f"{TENANT}/books/{{aggregate_id}}")):
        body = operation(document, path, method)["requestBody"]
        assert body["required"], f"{method} needs a body"
        assert schema_of(body["content"][JSON]) == {"$ref": f"{COMPONENT}Book"}
        assert JSON_LD in body["content"]


def test_a_read_answers_every_representation_and_the_version(document) -> None:
    ok = operation(document, f"{TENANT}/books/{{aggregate_id}}", "get")["responses"]["200"]
    assert set(ok["content"]) == {JSON, JSON_LD, TURTLE}
    assert schema_of(ok["content"][JSON]) == {"$ref": f"{COMPONENT}Book"}
    assert "ETag" in ok["headers"]


@pytest.mark.parametrize("path", [TENANT, f"{TENANT}/books/{{aggregate_id}}"])
def test_a_read_documents_the_allowed_actions_header(document, path) -> None:
    ok = operation(document, path, "get")["responses"]["200"]
    description = ok["headers"]["Allowed-Actions"]["description"]
    assert "read, modify, delete, administer" in description, f"{path}: the order is documented"


def test_a_create_answers_the_location_and_the_version(document) -> None:
    created = operation(document, f"{TENANT}/books", "post")["responses"]["201"]
    assert {"Location", "ETag"} <= set(created["headers"])


@pytest.mark.parametrize(
    "path",
    [TENANT, f"{TENANT}/books/{{aggregate_id}}", f"{TENANT}/grants", f"{TENANT}/label"],
)
def test_an_update_carries_its_expected_version_in_if_match(document, path) -> None:
    op = operation(document, path, "put")
    headers = [p for p in op["parameters"] if p["in"] == "header" and p["name"] == "If-Match"]
    assert [h["required"] for h in headers] == [True]


def test_a_delete_carries_its_expected_version_in_if_match(document) -> None:
    op = operation(document, f"{TENANT}/books/{{aggregate_id}}", "delete")
    assert [p["required"] for p in op["parameters"] if p["name"] == "If-Match"] == [True]


@pytest.mark.parametrize(
    ("path", "method", "body"),
    [
        (TENANTS, "post", "TenantCreate"),
        (f"{TENANT}/label", "put", "LabelUpdate"),
        (f"{TENANT}/grants", "put", "GrantSet"),
        (TENANT, "put", "Library"),
    ],
)
def test_the_bodies_of_the_tenant_routes_are_declared(document, path, method, body) -> None:
    content = operation(document, path, method)["requestBody"]["content"]
    assert schema_of(content[JSON]) == {"$ref": f"{COMPONENT}{body}"}


def test_the_tenant_routes_answer_their_models(document) -> None:
    created = operation(document, TENANTS, "post")["responses"]["201"]["content"][JSON]
    grants = operation(document, f"{TENANT}/grants", "get")["responses"]["200"]["content"][JSON]
    root = operation(document, TENANT, "get")["responses"]["200"]["content"][JSON]
    assert schema_of(created) == {"$ref": f"{COMPONENT}TenantSummary"}
    assert schema_of(grants) == {"$ref": f"{COMPONENT}GrantSet"}
    assert schema_of(root) == {"$ref": f"{COMPONENT}Library"}


def test_every_route_but_the_context_asks_for_a_bearer_token(document) -> None:
    assert document["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"
    for path, method, _ in ROUTES:
        assert operation(document, path, method)["security"] == [{"bearerAuth": []}], path


# --- the component schemas ----------------------------------------------------------------------


def properties(document: dict, name: str) -> dict:
    return document["components"]["schemas"][name].get("properties", {})


def test_the_schemas_of_every_type_and_of_the_toolkit_bodies_are_components(document) -> None:
    schemas = set(document["components"]["schemas"])
    assert {
        "Book", "Scan", "Library", "Genre", "Chapter", "Note", "Page", "Problem", "TenantCreate",
        "TenantSummary", "LabelUpdate", "GrantSet", "ListRequest", "Filter",
    } <= schemas  # fmt: skip


def test_no_bookkeeping_slot_is_in_a_component_schema(document) -> None:
    leaked = {
        (name, prop)
        for name, schema in document["components"]["schemas"].items()
        for prop in schema.get("properties", {})
        if prop in BOOKKEEPING
    }
    assert not leaked


def test_no_internal_slot_is_in_a_component_schema(document, toy) -> None:
    internal = {s.name for s in toy.kit.view.class_induced_slots("Scan") if is_internal(s)}
    assert internal, "the toy's scan keeps a stored file, whose slots are internal"
    assert not internal & set(properties(document, "Scan"))


def test_the_iri_of_a_document_is_read_only(document) -> None:
    assert properties(document, "Book")["id"]["readOnly"] is True, "the service assigns it"


def test_the_components_reference_only_components_that_exist(document) -> None:
    text = json.dumps(document)
    refs = {part.split('"')[0] for part in text.split(COMPONENT)[1:]}
    names = set(document["components"]["schemas"])
    assert {r.split("/")[0] for r in refs} <= names


def test_the_document_is_the_same_each_time_it_is_built(document) -> None:
    again = ToyService().app.openapi()
    assert json.dumps(again) == json.dumps(document)


async def test_the_document_is_served_where_fastapi_serves_it(toy) -> None:
    async with toy.client() as http:
        served = await http.get("/openapi.json")
    assert served.status_code == 200
    assert served.json() == json.loads(json.dumps(toy.app.openapi()))


def test_every_status_the_document_names_has_a_problem_kind_or_is_a_success() -> None:
    kinds = {k.status for k in KINDS}
    named = set().union(*(s for _, _, s in ROUTES)) - SUCCESS
    assert named <= kinds, f"unknown problem statuses {named - kinds}"
    assert all(HTTPStatus(s) for s in named)


def test_an_application_class_has_no_path_and_no_component(document) -> None:
    """TC-12: ``Template`` lives in the application database, so the tenant routes leave it out."""
    assert not [path for path in document["paths"] if "templates" in path]
    assert "Template" not in document["components"]["schemas"]

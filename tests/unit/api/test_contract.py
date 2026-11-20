"""Scenario 'the service keeps to its document' (rp-service-api): the toy service against its own /openapi.json (PD-15)."""

from collections.abc import Iterator
from typing import Any

import pytest
import schemathesis
from fastapi import Response
from hypothesis import HealthCheck, given, settings
from schemathesis.checks import CheckFunction, not_a_server_error
from schemathesis.config import SchemathesisConfig
from schemathesis.core.failures import FailureGroup
from schemathesis.specs.openapi.checks import (
    content_type_conformance,
    response_schema_conformance,
    status_code_conformance,
)

from rdf_persistence.core.domain.media import JSON, PROBLEM_JSON
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService

CHECKS: list[CheckFunction] = [
    not_a_server_error,
    status_code_conformance,
    content_type_conformance,
    response_schema_conformance,
]
EXAMPLES = 25
TEAPOT = 418


class Ids:
    """The path ids the contract run fills in: a tenant and a book made through the service."""

    def __init__(self, tenant: str, aggregate: str) -> None:
        self.tenant, self.aggregate = tenant, aggregate

    @property
    def path_parameters(self) -> dict[str, str]:
        return {"t": self.tenant, "aggregate_id": self.aggregate}


def make_ids(schema: Any, headers: dict[str, str]) -> Ids:
    """Make the tenant and its book through the document's own operations; the ids are the last path segments."""
    made = (
        schema["/libraries"]["POST"].Case(body=TENANT_BODY, headers=headers, media_type=JSON).call()
    )
    assert made.status_code == 201, made.text  # say why, if the tenant was not made
    tenant = made.headers["location"][0].rsplit("/", 1)[-1]  # a response's headers hold lists
    book = (
        schema["/libraries/{t}/books"]["POST"]
        .Case(path_parameters={"t": tenant}, body=DUNE_BODY, headers=headers, media_type=JSON)
        .call()
    )
    assert book.status_code == 201, book.text
    return Ids(tenant, book.headers["location"][0].rsplit("/", 1)[-1])


def operations_of(toy: ToyService) -> list[str]:
    """The operations of the toy service's document, as ``METHOD path``: one contract case each."""
    schema = schemathesis.openapi.from_asgi("/openapi.json", toy.app)
    return [
        f"{found.ok().method.upper()} {found.ok().path}" for found in schema.get_all_operations()
    ]


ONE_EVENT = 1  # a stream is read to its first event: it lives for minutes, and the run must end


def run_contract(
    toy: ToyService,
    checks: list[CheckFunction] = CHECKS,
    path: str | None = None,
    method: str | None = None,
) -> int:
    """Run the ``checks`` on every operation of the document (or those of ``path``, or the one ``method`` ``path``) with ``EXAMPLES`` derandomised examples; answer the operation count."""
    config = SchemathesisConfig.from_dict({"max-stream-events": ONE_EVENT})
    schema = schemathesis.openapi.from_asgi("/openapi.json", toy.app, config=config)
    headers = toy.bearer("ada")
    ids = make_ids(schema, headers)
    operations = [
        found.ok()
        for found in schema.get_all_operations()
        if path in (None, found.ok().path) and method in (None, found.ok().method.upper())
    ]

    for operation in operations:

        @settings(
            max_examples=EXAMPLES,
            derandomize=True,
            deadline=None,
            database=None,
            suppress_health_check=list(HealthCheck),
        )
        @given(case=operation.as_strategy())
        def one_case(case: Any) -> None:
            generated = case.path_parameters or {}
            case.path_parameters = {
                name: ids.path_parameters.get(name, value) for name, value in generated.items()
            }
            response = case.call(headers=headers)
            case.validate_response(response, checks=checks, headers=headers)

        one_case()
    return len(operations)


@pytest.fixture
def toy() -> Iterator[ToyService]:
    yield ToyService()


OPERATIONS = operations_of(ToyService())
NOT_THE_SCHEMA = [check for check in CHECKS if check is not response_schema_conformance]


def case_of(operation: str) -> tuple[str, str]:
    method, path = operation.split(" ", 1)
    return method, path


@pytest.mark.slow
@pytest.mark.parametrize("operation", OPERATIONS)
def test_the_service_keeps_to_its_document(toy: ToyService, operation: str) -> None:
    """TC-63: no server error; every status and content type of the operation documented."""
    method, path = case_of(operation)
    assert run_contract(toy, NOT_THE_SCHEMA, path, method) == 1


@pytest.mark.slow
@pytest.mark.parametrize("operation", OPERATIONS)
def test_every_json_body_is_valid_against_its_schema(toy: ToyService, operation: str) -> None:
    """TC-63: every body the operation answers (a stream's first event included) is valid against its schema."""
    method, path = case_of(operation)
    assert run_contract(toy, [response_schema_conformance], path, method) == 1


def delete_conflict(toy: ToyService, rp_path: str) -> dict[str, Any]:
    """The documented 409 answer of ``DELETE /libraries/{t}/<rp_path>/{aggregate_id}``."""
    path = f"/libraries/{{t}}/{rp_path}/{{aggregate_id}}"
    return toy.app.openapi()["paths"][path]["delete"]["responses"]["409"]


def test_the_delete_of_a_refusing_class_documents_the_in_use_problem(toy: ToyService) -> None:
    """TC-10: ``DELETE /authors/{id}`` 409 is an ``InUseProblem``; a class that does not refuse keeps ``Problem``."""
    in_use = "#/components/schemas/InUseProblem"
    refusing = delete_conflict(toy, "authors")["content"][PROBLEM_JSON]["schema"]
    assert refusing == {"$ref": in_use}, "a refusing class answers 409 with the in-use problem"
    assert "In use" in delete_conflict(toy, "authors")["description"], "its title is named"
    plain = delete_conflict(toy, "books")["content"][PROBLEM_JSON]["schema"]
    assert plain == {"$ref": "#/components/schemas/Problem"}, "a book keeps today's 409"
    assert "InUseProblem" in toy.app.openapi()["components"]["schemas"], "the component exists"


@pytest.mark.slow
def test_the_context_route_answers_the_media_type_it_documents(toy: ToyService) -> None:
    """The context route is documented as JSON-LD, as it answers (found by TC-63's run)."""
    assert run_contract(toy, path="/context.jsonld") == 1, "the document lists the context route"


@pytest.mark.slow
def test_an_undocumented_status_fails_the_contract(toy: ToyService) -> None:
    """TC-64: a route that answers an undocumented 418 makes the contract run fail (the check is live)."""

    @toy.app.get("/teapot")
    def teapot() -> Response:
        return Response(status_code=TEAPOT)

    with pytest.raises(FailureGroup) as failed:
        run_contract(toy, path="/teapot")
    assert str(TEAPOT) in str(failed.value), "the failure names the undocumented status"

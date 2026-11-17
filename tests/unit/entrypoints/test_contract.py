"""Scenario 'the service keeps to its document' (rp-service-api): the toy service against its own /openapi.json (PD-15)."""

from collections.abc import Iterator
from typing import Any

import pytest
import schemathesis
from fastapi import Response
from hypothesis import HealthCheck, given, settings
from schemathesis.checks import CheckFunction, not_a_server_error
from schemathesis.core.failures import FailureGroup
from schemathesis.specs.openapi.checks import (
    content_type_conformance,
    response_schema_conformance,
    status_code_conformance,
)

from rdf_persistence.domain.media import JSON
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


def run_contract(toy: ToyService, only: str | None = None) -> int:
    """Run the four checks on every operation of the document (or those of the path ``only``) with ``EXAMPLES`` derandomised examples; answer the operation count."""
    schema = schemathesis.openapi.from_asgi("/openapi.json", toy.app)
    headers = toy.bearer("ada")
    ids = make_ids(schema, headers)
    operations = [
        found.ok() for found in schema.get_all_operations() if only in (None, found.ok().path)
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
            case.validate_response(response, checks=CHECKS, headers=headers)

        one_case()
    return len(operations)


@pytest.fixture
def toy() -> Iterator[ToyService]:
    yield ToyService()


@pytest.mark.slow
@pytest.mark.xfail(  # https://github.com/meaningfy-ws/rdf-persistence/issues/148
    strict=True,
    raises=FailureGroup,
    reason="#148: a plain JSON read carries `type`, which the object component schemas "
    "(additionalProperties: false) do not list; the fix is in the generator",
)
def test_the_service_keeps_to_its_document(toy: ToyService) -> None:
    """TC-63: no server error; every status and content type documented; every JSON body valid against its schema."""
    assert run_contract(toy) > 0, "the document lists no operation"


@pytest.mark.slow
def test_the_context_route_answers_the_media_type_it_documents(toy: ToyService) -> None:
    """The context route is documented as JSON-LD, as it answers (found by TC-63's run)."""
    assert run_contract(toy, only="/context.jsonld") == 1, "the document lists the context route"


@pytest.mark.slow
def test_an_undocumented_status_fails_the_contract(toy: ToyService) -> None:
    """TC-64: a route that answers an undocumented 418 makes the contract run fail (the check is live)."""

    @toy.app.get("/teapot")
    def teapot() -> Response:
        return Response(status_code=TEAPOT)

    with pytest.raises(FailureGroup) as failed:
        run_contract(toy, only="/teapot")
    assert str(TEAPOT) in str(failed.value), "the failure names the undocumented status"

"""Every toolkit error becomes an RFC 9457 problem response (task 5.1, PD-15, the error matrix)."""

import inspect

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from rdf_persistence import LabelUpdate, Problem, ProblemKind
from rdf_persistence.domain import exceptions
from rdf_persistence.domain.exceptions import PersistenceError
from rdf_persistence.entrypoints.problems import (
    KINDS,
    PROBLEM_MEDIA_TYPE,
    install_problem_handlers,
    kind_of,
)

BASE = "https://example.org/library/"
ERRORS = [
    cls
    for _, cls in inspect.getmembers(exceptions, inspect.isclass)
    if cls.__module__ == exceptions.__name__ and cls is not PersistenceError
]
# error, status, slug: the error matrix, one row per error class
ROWS = [
    (exceptions.InvalidToken, 401, "invalid-token"),
    (exceptions.Forbidden, 403, "forbidden"),
    (exceptions.NotFound, 404, "not-found"),
    (exceptions.DatabaseGone, 404, "not-found"),
    (exceptions.TenantGone, 404, "not-found"),
    (exceptions.Conflict, 409, "conflict"),
    (exceptions.PreconditionRequired, 428, "precondition-required"),
    (exceptions.InvalidBody, 422, "invalid-body"),
    (exceptions.InvalidGraph, 422, "invalid-body"),
    (exceptions.InvalidGrant, 422, "invalid-body"),
    (exceptions.UnknownRole, 422, "invalid-body"),
    (exceptions.InvalidIri, 422, "invalid-body"),
    (exceptions.NotAcceptable, 406, "not-acceptable"),
    (exceptions.UnsupportedMediaType, 415, "unsupported-media-type"),
    (exceptions.BadQuery, 400, "bad-query"),
    (exceptions.SparqlError, 400, "bad-query"),
    (exceptions.StoreUnavailable, 503, "unavailable"),
    (exceptions.IdentityUnavailable, 503, "unavailable"),
    (exceptions.InvalidRoleDefinition, 503, "unavailable"),
]
TITLES = {
    "invalid-token": "Invalid token",
    "forbidden": "Forbidden",
    "not-found": "Not found",
    "conflict": "Version conflict",
    "precondition-required": "Precondition required",
    "invalid-body": "Invalid body",
    "not-acceptable": "Not acceptable",
    "unsupported-media-type": "Unsupported media type",
    "bad-query": "Bad query",
    "unavailable": "Service unavailable",
}
SECRET = "http://fuseki.internal:3030/lib-t-0001 refused the connection"


def app_raising(error: Exception) -> FastAPI:
    app = FastAPI()
    install_problem_handlers(app, BASE)

    @app.get("/boom")
    async def boom() -> None:
        raise error

    return app


async def get(app: FastAPI, path: str = "/boom") -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.parametrize("error", ERRORS, ids=lambda cls: cls.__name__)
def test_every_error_class_of_the_toolkit_has_a_problem_kind(error: type[PersistenceError]) -> None:
    assert kind_of(error("x")) is not None, f"{error.__name__} would escape as a bare 500"


def test_the_table_has_a_row_for_every_error_class() -> None:
    assert {row[0] for row in ROWS} == set(ERRORS), "an error class has no row in this table"


@pytest.mark.parametrize(("error", "status", "slug"), ROWS, ids=[r[0].__name__ for r in ROWS])
async def test_an_error_answers_with_its_status_and_problem_type(
    error: type[PersistenceError], status: int, slug: str
) -> None:
    response = await get(app_raising(error("detail")))
    problem = Problem.model_validate(response.json())
    assert response.status_code == status, "status"
    assert (problem.type, problem.title, problem.status) == (
        f"{BASE}problems/{slug}",
        TITLES[slug],
        status,
    ), "type, title and status of the body"
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE, "media type"


def test_the_kinds_are_exactly_the_slugs_and_titles_of_pd_15() -> None:
    assert {k.slug: k.title for k in KINDS} == TITLES, "slugs and their fixed titles"
    assert all(isinstance(k, ProblemKind) for k in KINDS), "each kind is a generated ProblemKind"


@pytest.mark.parametrize("error", [exceptions.NotFound, exceptions.Forbidden, exceptions.Conflict])
async def test_a_refusal_hides_the_text_of_the_error(error: type[PersistenceError]) -> None:
    body = (await get(app_raising(error(SECRET)))).text
    assert "fuseki" not in body, "the detail would tell a caller what exists, or where the store is"


@pytest.mark.parametrize("error", [exceptions.StoreUnavailable, exceptions.IdentityUnavailable])
async def test_an_outage_hides_where_the_store_or_the_provider_is(
    error: type[PersistenceError],
) -> None:
    assert "fuseki" not in (await get(app_raising(error(SECRET)))).text, "no internal address"


async def test_a_rejected_body_says_why() -> None:
    response = await get(app_raising(exceptions.InvalidBody("label: Field required")))
    assert Problem.model_validate(response.json()).detail == "label: Field required", (
        "a 422 carries the messages the caller needs to fix the body"
    )


async def test_an_invalid_token_asks_for_a_bearer_token() -> None:
    response = await get(app_raising(exceptions.InvalidToken("expired")))
    assert response.headers["www-authenticate"] == "Bearer", "RFC 6750: a 401 names its scheme"


async def test_a_pydantic_validation_error_is_an_invalid_body_naming_the_field() -> None:
    try:
        LabelUpdate(label="")
    except ValidationError as error:
        response = await get(app_raising(error))
    problem = Problem.model_validate(response.json())
    assert (response.status_code, problem.type) == (422, f"{BASE}problems/invalid-body"), "status"
    assert "label" in (problem.detail or ""), "the field is named"


async def test_an_unknown_path_is_a_not_found_problem() -> None:
    response = await get(app_raising(exceptions.NotFound("x")), "/nowhere")
    assert response.status_code == 404, "status"
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE, (
        "even a missing route answers a problem"
    )


async def test_an_unmapped_failure_is_left_to_the_server_error_page() -> None:
    response = await get(app_raising(RuntimeError("bug")))
    assert response.status_code == 500, "a bug is not turned into one of the toolkit's problems"

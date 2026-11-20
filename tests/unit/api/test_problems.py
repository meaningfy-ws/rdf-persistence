"""Every toolkit error becomes an RFC 9457 problem response (task 5.1, PD-15, the error matrix)."""

import inspect
import logging

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError

from rdf_persistence import LabelUpdate, Problem, ProblemKind, Referrer
from rdf_persistence.api.entrypoints.generated.rp_api_entrypoints import InUseProblem, ProblemSlug
from rdf_persistence.api.entrypoints.problems import (
    KINDS,
    install_problem_handlers,
    kind_of,
)
from rdf_persistence.core.domain import exceptions
from rdf_persistence.core.domain.exceptions import PersistenceError
from rdf_persistence.core.domain.media import PROBLEM_JSON
from rdf_persistence.persistence.services.decoding import error_text
from tests.logs import attributes
from tests.toy_service import assert_problem

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
    (exceptions.KeyConflict, 409, "key-conflict"),
    (exceptions.InUse, 409, "in-use"),
    (exceptions.PreconditionRequired, 428, "precondition-required"),
    (exceptions.InvalidBody, 422, "invalid-body"),
    (exceptions.InvalidGraph, 422, "invalid-body"),
    (exceptions.InvalidGrant, 422, "invalid-body"),
    (exceptions.UnknownRole, 422, "invalid-body"),
    (exceptions.InvalidIri, 422, "invalid-body"),
    (exceptions.NotAcceptable, 406, "not-acceptable"),
    (exceptions.UnsupportedMediaType, 415, "unsupported-media-type"),
    (exceptions.BadQuery, 400, "bad-query"),
    (exceptions.SparqlError, 500, "internal-error"),
    (exceptions.StoredDataInvalid, 500, "internal-error"),
    (exceptions.MessageLimitExceeded, 500, "internal-error"),
    (exceptions.IriPolicyChanged, 503, "unavailable"),
    (exceptions.PayloadTooLarge, 413, "payload-too-large"),
    (exceptions.CommitTooLarge, 413, "payload-too-large"),
    (exceptions.StoreUnavailable, 503, "unavailable"),
    (exceptions.IdentityUnavailable, 503, "unavailable"),
    (exceptions.InvalidRoleDefinition, 503, "unavailable"),
    (exceptions.InvalidWorkflow, 503, "unavailable"),
    (exceptions.InvalidMigration, 503, "unavailable"),
    (exceptions.MigrationFailed, 503, "unavailable"),
    (exceptions.TenantBehind, 503, "tenant-behind"),
    (exceptions.StoreNotWired, 500, "internal-error"),
]
TITLES = {
    "invalid-token": "Invalid token",
    "forbidden": "Forbidden",
    "not-found": "Not found",
    "conflict": "Version conflict",
    "key-conflict": "Key conflict",
    "in-use": "In use",
    "precondition-required": "Precondition required",
    "invalid-body": "Invalid body",
    "not-acceptable": "Not acceptable",
    "unsupported-media-type": "Unsupported media type",
    "bad-query": "Bad query",
    "unavailable": "Service unavailable",
    "tenant-behind": "Tenant behind its schema",
    "payload-too-large": "Payload too large",
    "method-not-allowed": "Method not allowed",
    "internal-error": "Internal error",
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
    problem = (InUseProblem if slug == "in-use" else Problem).model_validate(response.json())
    assert response.status_code == status, "status"
    assert (problem.type, problem.title, problem.status) == (
        f"{BASE}problems/{slug}",
        TITLES[slug],
        status,
    ), "type, title and status of the body"
    assert response.headers["content-type"] == PROBLEM_JSON, "media type"


def test_the_kinds_are_exactly_the_slugs_and_titles_of_pd_15() -> None:
    assert {k.slug: k.title for k in KINDS} == TITLES, "slugs and their fixed titles"
    assert all(isinstance(k, ProblemKind) for k in KINDS), "each kind is a generated ProblemKind"
    assert [k.slug.replace("-", "_") for k in KINDS] == [s.value for s in ProblemSlug], (
        "one kind for each generated slug, in the order of the enum"
    )


def test_a_key_conflict_has_its_own_kind_and_a_version_conflict_keeps_its_own() -> None:  # TC-30
    key = kind_of(exceptions.KeyConflict("x", iris=("i",), keys=("k",)))
    assert key is not None, "the key conflict was raised"
    assert (key.slug, key.title, key.status) == ("key-conflict", "Key conflict", 409), "own kind"
    version = kind_of(exceptions.Conflict("x"))
    assert version is not None, "the version conflict was raised"
    assert (version.slug, version.title) == ("conflict", "Version conflict"), "unchanged"


@pytest.mark.parametrize(
    "error",
    [exceptions.NotFound, exceptions.Forbidden, exceptions.Conflict, exceptions.KeyConflict],
)
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
    problem = assert_problem(response, 422, "invalid-body")  # the base is checked by the table test
    assert problem.detail == "label: Field required", (
        "a 422 carries the messages the caller needs to fix the body"
    )


async def test_an_in_use_refusal_names_the_referrers_as_members_and_has_no_detail() -> (
    None
):  # TC-9, PD-11
    error = exceptions.InUse(
        "http://lib/books/b1 refers to it",
        iris=("http://lib/authors/a1",),
        referrers=(
            ("http://lib/books/b2", "Book", "written_by"),
            ("http://lib/books/b1", "Book", "written_by"),
        ),
        more_count=2,
        hidden_count=3,
        filtered=True,  # D-10: only a judged refusal names its referrers
    )
    response = await get(app_raising(error))
    problem = InUseProblem.model_validate(response.json())
    assert response.status_code == 409, "status"
    assert problem.type == f"{BASE}problems/in-use", "the in-use type under the base"
    assert (problem.title, problem.status) == ("In use", 409), "its fixed title and status"
    assert problem.detail is None, "a 409 carries no text, the members say what refers"
    assert "refers to it" not in response.text, "the text of the error does not leak"
    assert problem.referrers == [
        Referrer(referrer="http://lib/books/b1", referrer_class="Book", referrer_slot="written_by"),
        Referrer(referrer="http://lib/books/b2", referrer_class="Book", referrer_slot="written_by"),
    ], "the referrers, as generated models, in the order of the error"
    assert (problem.more_count, problem.hidden_count) == (2, 3), "the counts"
    assert response.headers["content-type"] == PROBLEM_JSON, "media type"


async def test_an_in_use_refusal_with_only_hidden_referrers_has_an_empty_list_and_the_count() -> (
    None
):  # E2
    response = await get(app_raising(exceptions.InUse("x", iris=("i",), hidden_count=1)))
    problem = InUseProblem.model_validate(response.json())
    assert (problem.referrers, problem.more_count, problem.hidden_count) == ([], 0, 1), (
        "no name is given, only that one referrer exists"
    )
    assert problem.detail is None, "no detail"


async def test_an_unfiltered_in_use_refusal_names_nobody_and_hides_every_referrer() -> None:  # D-10
    error = exceptions.InUse(
        "x",
        iris=("http://lib/authors/a1",),
        referrers=(
            ("http://lib/books/b1", "Book", "written_by"),
            ("http://lib/books/b2", "Book", "written_by"),
            ("http://lib/books/b2", "Book", "sequel_of"),
        ),
        more_count=2,
        hidden_count=3,
    )
    assert error.filtered is False, "the error was raised without a readable callable"
    response = await get(app_raising(error))
    problem = InUseProblem.model_validate(response.json())
    assert response.status_code == 409, "still the in-use refusal"
    assert (problem.referrers, problem.more_count) == ([], 0), "nothing is named or left over"
    assert problem.hidden_count == 2 + 2 + 3, "every referrer aggregate: named, more and hidden"
    assert "http://lib/books" not in response.text, "no referrer IRI is in the response"


async def test_a_filtered_in_use_refusal_is_answered_as_it_was_judged() -> None:  # D-10
    error = exceptions.InUse(
        "x",
        iris=("i",),
        referrers=(("http://lib/books/b1", "Book", "written_by"),),
        more_count=1,
        hidden_count=1,
        filtered=True,
    )
    problem = InUseProblem.model_validate((await get(app_raising(error))).json())
    assert [r.referrer for r in problem.referrers or []] == ["http://lib/books/b1"], "named"
    assert (problem.more_count, problem.hidden_count) == (1, 1), "the counts as given"


async def test_a_version_conflict_is_not_an_in_use_problem() -> None:  # TC-9
    body = (await get(app_raising(exceptions.Conflict("stale")))).json()
    assert not {"referrers", "more_count", "hidden_count"} & set(body), "no members on a conflict"


async def test_an_invalid_token_asks_for_a_bearer_token() -> None:
    response = await get(app_raising(exceptions.InvalidToken("expired")))
    assert response.headers["www-authenticate"] == "Bearer", "RFC 6750: a 401 names its scheme"


async def test_a_pydantic_validation_error_is_an_invalid_body_naming_the_field() -> None:
    try:
        LabelUpdate(label="")
    except ValidationError as error:
        response = await get(app_raising(error))
    problem = assert_problem(response, 422, "invalid-body")
    assert "label" in (problem.detail or ""), "the field is named"


async def test_an_unknown_path_is_a_not_found_problem() -> None:
    response = await get(app_raising(exceptions.NotFound("x")), "/nowhere")
    assert response.status_code == 404, "status"
    assert response.headers["content-type"] == PROBLEM_JSON, (
        "even a missing route answers a problem"
    )


async def test_an_unmapped_failure_is_an_internal_error_problem_without_its_text() -> None:
    response = await get(app_raising(RuntimeError("fuseki bug")))
    problem = Problem.model_validate(response.json())
    assert response.status_code == 500, "an unmapped failure is a server error"
    assert problem.type == f"{BASE}problems/internal-error", (
        "an unmapped failure is the internal-error kind"
    )
    assert "fuseki" not in response.text, "a fault of the service tells the caller nothing of it"


# One class: both are the internal-error 500 of one handler (test_router_hardening covers both by routes).
@pytest.mark.parametrize("error", [exceptions.SparqlError])
async def test_a_fault_of_the_service_hides_its_text(error: type[PersistenceError]) -> None:
    assert "fuseki" not in (await get(app_raising(error(SECRET)))).text, "no detail"


async def test_a_method_the_route_lacks_is_a_problem_that_keeps_the_allow_header() -> None:
    transport = httpx.ASGITransport(app=app_raising(RuntimeError("x")))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/boom")
    problem = Problem.model_validate(response.json())
    assert response.status_code == 405, "a missing method is refused with 405"
    assert problem.type == f"{BASE}problems/method-not-allowed", (
        "the problem has the method-not-allowed kind"
    )
    assert problem.title == TITLES["method-not-allowed"], "the problem has the kind's title"
    assert response.headers["allow"] == "GET", "the header the standard asks for"


async def test_an_http_exception_is_a_problem_with_a_title_from_its_status() -> None:
    response = await get(app_raising(HTTPException(status_code=418, detail="fuseki")))
    problem = Problem.model_validate(response.json())
    assert response.status_code == 418, "the exception's own status is kept"
    assert problem.type == f"{BASE}problems/im-a-teapot", "the kind is named after the status"
    assert "fuseki" not in response.text, "its text is not for the caller"


LOGGER = "rdf_persistence.api.entrypoints.problems"


@pytest.mark.parametrize(
    "error", [exceptions.MessageLimitExceeded(5), exceptions.StoredDataInvalid(SECRET)], ids=type
)
async def test_a_mapped_500_is_logged_once_at_error_with_its_type(error, caplog) -> None:  # TC-33
    caplog.set_level(logging.DEBUG, LOGGER)
    response = await get(app_raising(error))
    [record] = [r for r in caplog.records if r.name == LOGGER]
    assert response.status_code == 500, "a mapped fault of the service is a 500 problem"
    assert record.levelno == logging.ERROR, "logged at error"
    assert record.getMessage() == "internal error answered", "a constant message"
    assert record.exc_info, "the error travels with it"
    assert record.exc_info[1] is error, "the very error"
    assert attributes(record) == {
        "rp.step": "answer-internal-error",
        "error.type": f"{type(error).__module__}.{type(error).__qualname__}",
    }, "the step and the fully qualified class name, nothing else"  # TC-13c


class Stored(BaseModel):
    count: int


async def test_a_500_from_stored_data_the_schema_refuses_logs_no_traceback_and_no_value(
    caplog,
) -> None:  # TC-13c, D-11
    marker = "secret-tenant-text"
    with pytest.raises(ValidationError) as refusal:
        Stored(count=marker)  # type: ignore[arg-type]
    cause = refusal.value
    error = exceptions.StoredDataInvalid("the collection is invalid")
    error.__cause__ = cause
    assert marker in str(cause), "the validation error does quote the stored value"
    caplog.set_level(logging.DEBUG, LOGGER)

    response = await get(app_raising(error))

    [record] = [r for r in caplog.records if r.name == LOGGER]
    assert response.status_code == 500, "still a 500 problem"
    assert not record.exc_info, "no traceback: its chain quotes the stored values"
    assert not record.exc_text, "and no rendered one"
    assert attributes(record) == {
        "rp.step": "answer-internal-error",
        "error.type": "rdf_persistence.core.domain.exceptions.StoredDataInvalid",
        "rp.error.detail": error_text(cause),
    }, "the type and the fault named without the value"
    assert marker not in "".join(
        [record.getMessage(), *map(str, attributes(record).values()), response.text]
    ), "the marker is in no message, attribute or answer"


async def test_an_unmapped_failure_is_left_to_the_server_to_log(caplog) -> None:  # TC-33b
    caplog.set_level(logging.DEBUG, LOGGER)
    response = await get(app_raising(RuntimeError("fuseki bug")))
    assert response.status_code == 500, "a 500 problem"
    assert not [r for r in caplog.records if r.name == LOGGER], (
        "Starlette re-raises and the server logs: no second log here"
    )


async def test_a_not_found_is_answered_without_an_error_record(caplog) -> None:  # TC-34
    caplog.set_level(logging.DEBUG)
    response = await get(app_raising(exceptions.NotFound("no such book")))
    assert response.status_code == 404, "a refusal"
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR], "not a fault of ours"

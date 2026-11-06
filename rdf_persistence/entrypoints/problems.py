"""Problem responses (RFC 9457): every toolkit error becomes one, with a fixed type and title (PD-15).

The type of a problem is ``{base}problems/{slug}``. The text of an error reaches the caller only for
the statuses that say what to fix in the request (400, 406, 415, 422, 428); a refusal (401, 403,
404, 409) or an outage (5xx) carries none, so an answer never tells an outsider what exists or where
the store is.
"""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from rdf_persistence.domain import exceptions as errors
from rdf_persistence.domain.exceptions import PersistenceError
from rdf_persistence.domain.generated.service.rp_service import Problem, ProblemKind

PROBLEM_MEDIA_TYPE = "application/problem+json"
WWW_AUTHENTICATE = "WWW-Authenticate"
BEARER = "Bearer"
PROBLEMS_PATH = "problems/"


def _kind(slug: str, title: str, status: HTTPStatus) -> ProblemKind:
    return ProblemKind(slug=slug, title=title, status=status.value)


INVALID_TOKEN = _kind("invalid-token", "Invalid token", HTTPStatus.UNAUTHORIZED)
FORBIDDEN = _kind("forbidden", "Forbidden", HTTPStatus.FORBIDDEN)
NOT_FOUND = _kind("not-found", "Not found", HTTPStatus.NOT_FOUND)
CONFLICT = _kind("conflict", "Version conflict", HTTPStatus.CONFLICT)
PRECONDITION_REQUIRED = _kind(
    "precondition-required", "Precondition required", HTTPStatus.PRECONDITION_REQUIRED
)
INVALID_BODY = _kind("invalid-body", "Invalid body", HTTPStatus.UNPROCESSABLE_ENTITY)
NOT_ACCEPTABLE = _kind("not-acceptable", "Not acceptable", HTTPStatus.NOT_ACCEPTABLE)
UNSUPPORTED_MEDIA_TYPE = _kind(
    "unsupported-media-type", "Unsupported media type", HTTPStatus.UNSUPPORTED_MEDIA_TYPE
)
BAD_QUERY = _kind("bad-query", "Bad query", HTTPStatus.BAD_REQUEST)
UNAVAILABLE = _kind("unavailable", "Service unavailable", HTTPStatus.SERVICE_UNAVAILABLE)

KINDS = (
    INVALID_TOKEN,
    FORBIDDEN,
    NOT_FOUND,
    CONFLICT,
    PRECONDITION_REQUIRED,
    INVALID_BODY,
    NOT_ACCEPTABLE,
    UNSUPPORTED_MEDIA_TYPE,
    BAD_QUERY,
    UNAVAILABLE,
)
# The error matrix: each error class of the toolkit and the problem it becomes. The base class has
# no row, so an error added without one stays a 500 until it gets its own (a test lists the gaps).
ERROR_KINDS: tuple[tuple[type[PersistenceError], ProblemKind], ...] = (
    (errors.InvalidToken, INVALID_TOKEN),
    (errors.Forbidden, FORBIDDEN),
    (errors.NotFound, NOT_FOUND),
    (errors.DatabaseGone, NOT_FOUND),
    (errors.TenantGone, NOT_FOUND),
    (errors.Conflict, CONFLICT),
    (errors.PreconditionRequired, PRECONDITION_REQUIRED),
    (errors.InvalidBody, INVALID_BODY),
    (errors.InvalidGraph, INVALID_BODY),
    (errors.InvalidGrant, INVALID_BODY),
    (errors.UnknownRole, INVALID_BODY),
    (errors.InvalidIri, INVALID_BODY),
    (errors.NotAcceptable, NOT_ACCEPTABLE),
    (errors.UnsupportedMediaType, UNSUPPORTED_MEDIA_TYPE),
    (errors.BadQuery, BAD_QUERY),
    (errors.SparqlError, BAD_QUERY),
    (errors.StoreUnavailable, UNAVAILABLE),
    (errors.IdentityUnavailable, UNAVAILABLE),
    (
        errors.InvalidRoleDefinition,
        UNAVAILABLE,
    ),  # raised at start-up; a service that kept going would be unusable
)
# What the caller may read of the error: only where the text tells it what to fix.
_EXPLAINED = frozenset(
    {
        HTTPStatus.BAD_REQUEST,
        HTTPStatus.NOT_ACCEPTABLE,
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        HTTPStatus.UNPROCESSABLE_ENTITY,
        HTTPStatus.PRECONDITION_REQUIRED,
    }
)


def kind_of(error: BaseException) -> ProblemKind | None:
    """The problem kind of ``error``, found through its class and then its ancestors; None if unmapped."""
    for cls in type(error).__mro__:
        for mapped, kind in ERROR_KINDS:
            if cls is mapped:
                return kind
    return None


def problem_for(base: str, kind: ProblemKind, detail: str | None = None) -> Problem:
    """The problem of ``kind``; ``detail`` is kept only for the statuses that explain what to fix."""
    explained = HTTPStatus(kind.status) in _EXPLAINED
    return Problem(
        type=f"{base}{PROBLEMS_PATH}{kind.slug}",
        title=kind.title,
        status=kind.status,
        detail=detail if explained and detail else None,
    )


def problem_response(problem: Problem) -> Response:
    """The answer for ``problem``: its status, RFC 9457 media type, and ``WWW-Authenticate`` on a 401."""
    headers = {WWW_AUTHENTICATE: BEARER} if problem.status == HTTPStatus.UNAUTHORIZED else None
    return JSONResponse(
        problem.model_dump(exclude_none=True),
        status_code=problem.status,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


def validation_detail(error: ValidationError) -> str:
    """What failed in a validation, one ``field: message`` per error."""
    return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())


def install_problem_handlers(app: FastAPI, base: str) -> None:
    """Make ``app`` answer every mapped toolkit error, every validation error and every unknown path as a problem."""

    async def toolkit_error(_: Request, error: Exception) -> Response:
        kind = kind_of(error)
        assert kind is not None, "a handler is registered only for mapped errors"
        return problem_response(problem_for(base, kind, str(error)))

    async def invalid_body(_: Request, error: Exception) -> Response:
        assert isinstance(error, ValidationError)
        return problem_response(problem_for(base, INVALID_BODY, validation_detail(error)))

    async def http_error(request: Request, error: Exception) -> Response:
        assert isinstance(error, HTTPException)
        if error.status_code != HTTPStatus.NOT_FOUND:
            return await http_exception_handler(request, error)
        return problem_response(problem_for(base, NOT_FOUND))

    for cls, _ in ERROR_KINDS:
        app.add_exception_handler(cls, toolkit_error)
    app.add_exception_handler(ValidationError, invalid_body)
    app.add_exception_handler(HTTPException, http_error)

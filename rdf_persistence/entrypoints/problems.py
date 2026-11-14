"""Problem responses (RFC 9457): every toolkit error becomes one, with a fixed type and title (PD-15).

The type of a problem is ``{base}problems/{slug}``. The text of an error reaches the caller only for
the statuses that say what to fix in the request (400, 406, 413, 415, 422, 428); a refusal (401, 403,
404, 409), an outage or a fault of the service (5xx) carries none, so an answer never tells an
outsider what exists or where the store is. Errors of the framework (an unknown path, a method the
route lacks) and of the consumer's own routes are problems too.
"""

import re
from collections.abc import Mapping
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from rdf_persistence.domain import exceptions as errors
from rdf_persistence.domain.exceptions import PersistenceError
from rdf_persistence.domain.generated.service.rp_service import Problem, ProblemKind, ProblemSlug
from rdf_persistence.domain.media import PROBLEM_JSON
from rdf_persistence.entrypoints.auth import BEARER_SCHEME

WWW_AUTHENTICATE = "WWW-Authenticate"
BEARER = BEARER_SCHEME.capitalize()
PROBLEMS_PATH = "problems/"

# The fixed title and status of each kind of problem; the slugs are those of the generated ``ProblemSlug``.
_ROWS = {
    ProblemSlug.INVALID_TOKEN: ("Invalid token", HTTPStatus.UNAUTHORIZED),
    ProblemSlug.FORBIDDEN: ("Forbidden", HTTPStatus.FORBIDDEN),
    ProblemSlug.NOT_FOUND: ("Not found", HTTPStatus.NOT_FOUND),
    ProblemSlug.CONFLICT: ("Version conflict", HTTPStatus.CONFLICT),
    ProblemSlug.KEY_CONFLICT: ("Key conflict", HTTPStatus.CONFLICT),
    ProblemSlug.PRECONDITION_REQUIRED: ("Precondition required", HTTPStatus.PRECONDITION_REQUIRED),
    ProblemSlug.INVALID_BODY: ("Invalid body", HTTPStatus.UNPROCESSABLE_ENTITY),
    ProblemSlug.NOT_ACCEPTABLE: ("Not acceptable", HTTPStatus.NOT_ACCEPTABLE),
    ProblemSlug.UNSUPPORTED_MEDIA_TYPE: (
        "Unsupported media type",
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
    ),
    ProblemSlug.BAD_QUERY: ("Bad query", HTTPStatus.BAD_REQUEST),
    ProblemSlug.UNAVAILABLE: ("Service unavailable", HTTPStatus.SERVICE_UNAVAILABLE),
    ProblemSlug.PAYLOAD_TOO_LARGE: ("Payload too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE),
    ProblemSlug.METHOD_NOT_ALLOWED: ("Method not allowed", HTTPStatus.METHOD_NOT_ALLOWED),
    ProblemSlug.INTERNAL_ERROR: ("Internal error", HTTPStatus.INTERNAL_SERVER_ERROR),
}


def _kind(slug: ProblemSlug) -> ProblemKind:
    title, status = _ROWS[slug]
    return ProblemKind(slug=slug.value.replace("_", "-"), title=title, status=status.value)


INVALID_TOKEN = _kind(ProblemSlug.INVALID_TOKEN)
FORBIDDEN = _kind(ProblemSlug.FORBIDDEN)
NOT_FOUND = _kind(ProblemSlug.NOT_FOUND)
CONFLICT = _kind(ProblemSlug.CONFLICT)
KEY_CONFLICT = _kind(ProblemSlug.KEY_CONFLICT)
PRECONDITION_REQUIRED = _kind(ProblemSlug.PRECONDITION_REQUIRED)
INVALID_BODY = _kind(ProblemSlug.INVALID_BODY)
NOT_ACCEPTABLE = _kind(ProblemSlug.NOT_ACCEPTABLE)
UNSUPPORTED_MEDIA_TYPE = _kind(ProblemSlug.UNSUPPORTED_MEDIA_TYPE)
BAD_QUERY = _kind(ProblemSlug.BAD_QUERY)
UNAVAILABLE = _kind(ProblemSlug.UNAVAILABLE)
PAYLOAD_TOO_LARGE = _kind(ProblemSlug.PAYLOAD_TOO_LARGE)
METHOD_NOT_ALLOWED = _kind(ProblemSlug.METHOD_NOT_ALLOWED)
INTERNAL_ERROR = _kind(ProblemSlug.INTERNAL_ERROR)

KINDS = tuple(_kind(slug) for slug in ProblemSlug)
# The error matrix: each error class of the toolkit and the problem it becomes. The base class has
# no row, so an error added without one stays a 500 until it gets its own (a test lists the gaps).
ERROR_KINDS: tuple[tuple[type[PersistenceError], ProblemKind], ...] = (
    (errors.InvalidToken, INVALID_TOKEN),
    (errors.Forbidden, FORBIDDEN),
    (errors.NotFound, NOT_FOUND),
    (errors.DatabaseGone, NOT_FOUND),
    (errors.TenantGone, NOT_FOUND),
    (errors.Conflict, CONFLICT),
    (errors.KeyConflict, KEY_CONFLICT),  # found through the class first, so it wins over its base
    (errors.PreconditionRequired, PRECONDITION_REQUIRED),
    (errors.InvalidBody, INVALID_BODY),
    (errors.InvalidGraph, INVALID_BODY),
    (errors.InvalidGrant, INVALID_BODY),
    (errors.UnknownRole, INVALID_BODY),
    (errors.InvalidIri, INVALID_BODY),
    (errors.NotAcceptable, NOT_ACCEPTABLE),
    (errors.UnsupportedMediaType, UNSUPPORTED_MEDIA_TYPE),
    (errors.BadQuery, BAD_QUERY),
    # caller input that SPARQL cannot carry is refused earlier (BadQuery, InvalidBody); one that gets here is ours
    (errors.SparqlError, INTERNAL_ERROR),
    (errors.StoredDataInvalid, INTERNAL_ERROR),
    (
        errors.IriPolicyChanged,
        UNAVAILABLE,
    ),  # raised at start-up; a service that kept going would mint IRIs by the wrong policy
    (errors.PayloadTooLarge, PAYLOAD_TOO_LARGE),
    (
        errors.CommitTooLarge,
        PAYLOAD_TOO_LARGE,
    ),  # a request asked for more roots than one commit takes
    (errors.StoreUnavailable, UNAVAILABLE),
    (errors.IdentityUnavailable, UNAVAILABLE),
    (
        errors.InvalidRoleDefinition,
        UNAVAILABLE,
    ),  # raised at start-up; a service that kept going would be unusable
    (errors.InvalidWorkflow, UNAVAILABLE),  # raised at start-up, for the same reason
)
# The statuses the framework raises on its own, which have a kind of their own.
_OF_THE_FRAMEWORK = {
    HTTPStatus.NOT_FOUND.value: NOT_FOUND,
    HTTPStatus.METHOD_NOT_ALLOWED.value: METHOD_NOT_ALLOWED,
}
# What the caller may read of the error: only where the text tells it what to fix.
_EXPLAINED = frozenset(
    {
        HTTPStatus.BAD_REQUEST,
        HTTPStatus.NOT_ACCEPTABLE,
        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
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


def problem_response(problem: Problem, headers: Mapping[str, str] | None = None) -> Response:
    """The answer for ``problem``: its status, RFC 9457 media type, and ``WWW-Authenticate`` on a 401.

    ``headers`` are those the framework asked for with the error, such as ``Allow`` on a 405.
    """
    headers = dict(headers or {})
    if problem.status == HTTPStatus.UNAUTHORIZED:
        headers[WWW_AUTHENTICATE] = BEARER
    return JSONResponse(
        problem.model_dump(exclude_none=True),
        status_code=problem.status,
        media_type=PROBLEM_JSON,
        headers=headers or None,
    )


def status_kind(status: int) -> ProblemKind:
    """The problem kind of an HTTP status the toolkit has no kind for: its slug and title are the status phrase."""
    if status in _OF_THE_FRAMEWORK:
        return _OF_THE_FRAMEWORK[status]
    try:
        phrase = HTTPStatus(status).phrase
    except ValueError:
        return INTERNAL_ERROR
    return ProblemKind(
        slug=re.sub(r"[^a-z]+", "-", phrase.lower().replace("'", "")).strip("-"),
        title=phrase,
        status=status,
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

    async def http_error(_: Request, error: Exception) -> Response:
        assert isinstance(error, HTTPException)
        problem = problem_for(base, status_kind(error.status_code))
        return problem_response(problem, error.headers)

    async def server_error(_: Request, __: Exception) -> Response:
        return problem_response(problem_for(base, INTERNAL_ERROR))

    for cls, _ in ERROR_KINDS:
        app.add_exception_handler(cls, toolkit_error)
    app.add_exception_handler(ValidationError, invalid_body)
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(Exception, server_error)

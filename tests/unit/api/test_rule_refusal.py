"""A write rule refuses with a consumer problem (consumer-write-rules PD-5 to PD-7, PD-9a; TC-5, TC-6)."""

import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from rdf_persistence import Problem, RuleRefusal
from tests.fixtures.library.services.generated.library_problems import HeldKeyProblem
from tests.scene import PROBLEMS, Scene, problem_of
from tests.toy_service import DUNE_BODY, ToyService, fixed_refusal

PROBLEM_LOG = "rdf_persistence.api.entrypoints.problems"
MESSAGE = "rule refusal answered as internal error"


class Sibling(HeldKeyProblem):
    """A subclass of a registered class: not itself registered."""


class Unregistered(Problem):
    """A problem class the service was not given."""

    extra: str


def refusing(problem: object):
    """A rule that refuses a book with isbn ``x`` with ``problem`` (the scene's own book has none)."""

    def rule(old: Any, new: Any, who: Any, reader: Any) -> None:
        if new.isbn == "x":
            raise RuleRefusal(problem)

    return rule


def held(**changes: Any) -> HeldKeyProblem:
    fields: dict[str, Any] = {
        "type": f"{PROBLEMS}key-held",
        "title": "Key held",
        "status": 409,
        "detail": "isbn x is held",
        "holder": "urn:holder",
    }
    return HeldKeyProblem(**{**fields, **changes})


@asynccontextmanager
async def scene_with(
    rule: Any, refusal_problems: Sequence[type[BaseModel]] = (HeldKeyProblem,)
) -> AsyncIterator[Scene]:
    toy = ToyService(aggregate_validators={"Book": [rule]}, refusal_problems=refusal_problems)
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        yield await Scene.set_up(toy, http)


async def create(scene: Scene, **body: Any) -> httpx.Response:
    return await scene.http.post(
        f"{scene.tenant}/books", json={**DUNE_BODY, **body}, headers=scene.headers("ada")
    )


async def listed(scene: Scene) -> list[str]:
    page = await scene.http.get(f"{scene.tenant}/books", headers=scene.headers("ada"))
    return [item["id"] for item in page.json()["items"]]


def internal_error_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == PROBLEM_LOG and r.levelno >= logging.ERROR]


@pytest.mark.parametrize(
    ("isbn", "status", "detail"),
    [("held", 409, "isbn held is held"), ("malformed", 422, "isbn malformed is malformed")],
)
async def test_a_registered_refusal_is_answered_as_the_rule_built_it(  # TC-5
    isbn: str, status: int, detail: str, caplog: pytest.LogCaptureFixture
):
    async with scene_with(fixed_refusal) as scene:
        with caplog.at_level(logging.DEBUG):
            before = await listed(scene)
            response = await create(scene, isbn=isbn)
        body = response.json()
        assert response.status_code == status, response.text
        assert response.headers["content-type"].startswith("application/problem+json")
        assert body["type"].endswith("key-held"), "the rule's own type"
        assert body["detail"] == detail, "the rule's own text"
        assert body["holder"], "the extra field is kept"
        assert await listed(scene) == before, "nothing was written"
        assert internal_error_records(caplog) == [], "a registered refusal is no internal error"


async def test_a_book_the_rule_accepts_is_created():  # TC-5, negative
    async with scene_with(fixed_refusal) as scene:
        assert (await create(scene, isbn="free")).status_code == 201


async def test_a_replace_refused_is_answered_as_the_rule_built_it():  # TC-5
    async with scene_with(fixed_refusal) as scene:
        made = await create(scene, isbn="free")
        response = await scene.http.put(
            made.headers["location"],
            json={**DUNE_BODY, "isbn": "held"},
            headers=scene.headers("ada", **{"If-Match": made.headers["etag"]}),
        )
        assert response.status_code == 409, response.text
        assert response.json()["holder"], "the extra field is kept"


@pytest.mark.parametrize(
    ("problem", "registered", "why"),
    [
        (
            Unregistered(type="t", title="x", status=409, extra="e"),
            (HeldKeyProblem,),
            "unregistered",
        ),
        (Unregistered(type="t", title="x", status=409, extra="e"), (), "unregistered"),
        (
            Sibling(type="t", title="x", status=409, holder="urn:h"),
            (HeldKeyProblem,),
            "unregistered",
        ),
        ("a string, not a problem", (HeldKeyProblem,), "unregistered"),
        (held(status=400), (HeldKeyProblem,), "status 400"),
        (held(status=500), (HeldKeyProblem,), "status 500"),
    ],
    ids=["other-class", "none-registered", "subclass", "not-a-problem", "status-400", "status-500"],
)
async def test_any_other_refusal_is_a_500_internal_error_logged_once_without_a_traceback(  # TC-6
    problem: object,
    registered: tuple[type[BaseModel], ...],
    why: str,
    caplog: pytest.LogCaptureFixture,
):
    async with scene_with(refusing(problem), registered) as scene:
        with caplog.at_level(logging.DEBUG):
            before = await listed(scene)
            response = await create(scene, isbn="x")
        assert response.status_code == 500, response.text
        assert problem_of(response).type == f"{PROBLEMS}internal-error"
        assert not {"holder", "extra"} & response.json().keys(), "no field of the rule's problem"
        assert await listed(scene) == before, "nothing was written"
        records = internal_error_records(caplog)
        assert len(records) == 1, f"exactly one error record: {[r.getMessage() for r in records]}"
        assert records[0].getMessage() == MESSAGE, "the constant message"
        assert records[0].exc_info is None, "no traceback"
        assert why in str(records[0].__dict__), "the record says why"


@pytest.mark.parametrize("registered", [(), (HeldKeyProblem,)])
async def test_a_rule_that_does_not_refuse_leaves_no_error_record(
    registered: tuple[type[BaseModel], ...], caplog: pytest.LogCaptureFixture
):  # TC-6, no refusal_problems
    async with scene_with(fixed_refusal, registered) as scene:
        with caplog.at_level(logging.DEBUG):
            assert (await create(scene, isbn="free")).status_code == 201
        assert internal_error_records(caplog) == [], "nothing logged"


class NotAProblem(BaseModel):
    title: str


@pytest.mark.parametrize("bad", [NotAProblem, dict])
def test_a_registered_class_that_is_not_a_problem_stops_the_start_up(bad: type):  # TC-6
    with pytest.raises(TypeError, match=bad.__name__):
        ToyService(refusal_problems=[bad])

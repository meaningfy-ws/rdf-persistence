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
from tests.toy_service import DUNE_BODY, FIXED_HOLDER, HELD, ToyService, fixed_refusal

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


def built(status: Any) -> HeldKeyProblem:
    """A registered problem whose ``status`` skips validation, as a rule that assigns it later would."""
    return HeldKeyProblem.model_construct(
        type=f"{PROBLEMS}key-held", title="Key held", detail="d", holder="urn:h", status=status
    )


class Shape:
    """An object that is no problem, carrying a registered-looking status."""

    status = 409
    title = "Key held"
    detail = "d"
    holder = "urn:h"


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
        assert body["type"] == HELD, "the rule's own type"
        assert body["title"] == "Key held", "the rule's own title"
        assert body["status"] == status, "the rule's own status"
        assert body["detail"] == detail, "the rule's own text"
        assert body["holder"] == FIXED_HOLDER, "the extra field is kept"
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
        body = response.json()
        assert response.status_code == 409, response.text
        assert body["type"] == HELD, "the rule's own type"
        assert body["title"] == "Key held", "the rule's own title"
        assert body["status"] == 409, "the rule's own status"
        assert body["detail"] == "isbn held is held", "the rule's own text"
        assert body["holder"] == FIXED_HOLDER, "the extra field is kept"


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
        (
            Problem(type="t", title="x", status=409),
            (HeldKeyProblem,),
            "unregistered",
        ),  # probe of PD-6: the base class of a registered one is not registered
        ("a string, not a problem", (HeldKeyProblem,), "unregistered"),
        (Shape(), (HeldKeyProblem,), "unregistered"),  # probe of PD-6: an object shaped like one
        (held(status=400), (HeldKeyProblem,), "status 400"),
        (held(status=403), (HeldKeyProblem,), "status 403"),
        (held(status=500), (HeldKeyProblem,), "status 500"),
        (built("409"), (HeldKeyProblem,), "status"),  # probe of PD-6: a status that is no int
    ],
    ids=[
        "other-class",
        "none-registered",
        "subclass",
        "base-class",
        "not-a-problem",
        "problem-shaped-object",
        "status-400",
        "status-403",
        "status-500",
        "status-not-an-int",
    ],
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


@pytest.mark.parametrize(
    ("problem", "registered", "answered"),
    [
        (held(), (HeldKeyProblem, HeldKeyProblem), 409),
        (Sibling(type="t", title="x", status=409, holder="urn:h"), (Sibling,), 409),
        (Sibling(type="t", title="x", status=409, holder="urn:h"), (HeldKeyProblem, Sibling), 409),
        (Problem(type="t", title="x", status=409), (Problem,), 409),
    ],
    ids=["registered-twice", "the-subclass-itself", "base-and-subclass", "the-base-itself"],
)
async def test_a_class_registered_by_exact_match_is_answered_as_built(
    problem: Problem, registered: tuple[type[BaseModel], ...], answered: int
):  # probe of PD-6 exact class and PD-7, the positive side of the table above
    async with scene_with(refusing(problem), registered) as scene:
        response = await create(scene, isbn="x")
        assert response.status_code == answered, response.text


async def test_a_refusal_answer_leaves_out_none_fields_and_keeps_the_extra_one():
    # probe of PD-6 "problem_response"
    async with scene_with(refusing(held(detail=None, instance=None))) as scene:
        response = await create(scene, isbn="x")
        assert response.status_code == 409, response.text
        assert "detail" not in response.json(), "None detail left out"
        assert "instance" not in response.json(), "None instance left out"
        assert response.json()["holder"] == "urn:holder", "extra field kept"


async def test_a_refused_replace_keeps_the_stored_aggregate():
    # probe of the error matrix "nothing written", on a replace
    async with scene_with(fixed_refusal) as scene:
        made = await create(scene, isbn="free")
        before = await scene.http.get(made.headers["location"], headers=scene.headers("ada"))
        refused = await scene.http.put(
            made.headers["location"],
            json={**before.json(), "isbn": "malformed"},
            headers=scene.headers("ada", **{"If-Match": made.headers["etag"]}),
        )
        assert refused.status_code == 422, refused.text
        after = await scene.http.get(made.headers["location"], headers=scene.headers("ada"))
        assert after.json() == before.json(), "the stored aggregate is as it was"
        assert after.headers["etag"] == made.headers["etag"], "no new version"


async def test_a_delete_rule_raising_rule_refusal_is_a_500_naming_no_problem():
    # probe of the error matrix "a delete rule raises RuleRefusal"
    def deleting(old: Any, who: Any, reader: Any) -> None:
        raise RuleRefusal(held())

    toy = ToyService(delete_validators={"Book": [deleting]}, refusal_problems=[HeldKeyProblem])
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        scene = await Scene.set_up(toy, http)
        made = await http.post(
            f"{scene.tenant}/books", json=DUNE_BODY, headers=scene.headers("ada")
        )
        response = await http.delete(
            made.headers["location"],
            headers=scene.headers("ada", **{"If-Match": made.headers["etag"]}),
        )
        assert response.status_code == 500, response.text
        assert "holder" not in response.json(), "the rule's problem is not sent"
        assert problem_of(response).type == f"{PROBLEMS}internal-error", "the fallback problem"


@pytest.mark.parametrize(
    ("problem", "text"),
    [
        (HeldKeyProblem.model_construct(detail="d", title="t"), "d"),
        (HeldKeyProblem.model_construct(detail=None, title="t"), "t"),
        (HeldKeyProblem.model_construct(detail=None, title=None), "HeldKeyProblem"),
    ],
    ids=["detail", "title", "class-name"],
)
def test_the_text_of_a_refusal_is_detail_then_title_then_the_class_name(problem: object, text: str):
    # probe of PD-5
    assert str(RuleRefusal(problem)) == text, "the text follows PD-5"


def test_the_kit_keeps_a_tuple_of_the_classes_given_in_order():
    # probe of PD-7
    toy = ToyService(refusal_problems=[Sibling, HeldKeyProblem])
    assert toy.kit.refusal_problems == (Sibling, HeldKeyProblem), "a tuple in the given order"
    assert ToyService().kit.refusal_problems == (), "none by default"


class NotAProblem(BaseModel):
    title: str


@pytest.mark.parametrize("bad", [NotAProblem, dict])
def test_a_registered_class_that_is_not_a_problem_stops_the_start_up(bad: type):  # TC-6
    with pytest.raises(TypeError, match=bad.__name__):
        ToyService(refusal_problems=[bad])

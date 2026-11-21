"""SPIKE-1 (DEC-4, S-6): the generic routes serve a root that is an ``Activity`` (PD-34)."""

from datetime import UTC, datetime

import httpx

from tests.fixtures.library.domain.generated.books_activities import Review
from tests.scene import Scene
from tests.toy_service import body_of

STARTED = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)


def a_review_body() -> dict:
    """A review as a client describes it: the service mints the id."""
    review = Review.model_construct(
        label="A review", description="A review of Dune.", started_at_time=STARTED
    )
    return body_of(review)


async def test_s6_a_review_is_posted_with_its_start_time_and_read_back(
    scene: Scene, client: httpx.AsyncClient
) -> None:
    made = await client.post(
        f"{scene.tenant}/reviews", json=a_review_body(), headers=scene.headers("ada")
    )
    assert made.status_code == 201, made.text
    read = await client.get(made.headers["location"], headers=scene.headers("ada"))
    assert read.status_code == 200, read.text
    assert read.json()["started_at_time"].startswith("2026-11-20T09:00:00"), (
        "the start time the client sent is served back"
    )

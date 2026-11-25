"""Steps of ``testkit_faults.feature``: an aimed fault and a held write, over the toy service (consumer-test-gaps 1.1).

Both scenarios belong to the requirements of ``rp-testkit`` named in the feature's ``# spec:`` lines. The
toy service's client skips the app's lifespan, so each scenario enters it itself: only then the relay
runs, and only then is there something for ``kit.relay.paused()`` to keep out. Nothing sleeps.
"""

import asyncio
import contextlib
from contextlib import AsyncExitStack
from functools import partial

import httpx
import pytest
from pytest_bdd import given, scenarios, then, when

from rdf_persistence.core.domain.exceptions import StoreUnavailable
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.testkit import wait_until_async
from tests.scene import Scene
from tests.toy_service import ADA, DUNE_BODY, ToyService, assert_problem

scenarios("testkit_faults.feature")

RUNS = 20  # RISK-5: one pass could be right by luck
RELAY_TIMEOUT = 5.0  # seconds the woken relay has to mark the activities after the block


class Faults:
    """One scenario: the toy service with its lifespan entered, a tenant with a book, and what the steps saw."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.stack = AsyncExitStack()
        self.scene: Scene
        self.answers: list[httpx.Response] = []
        self.unrelayed: list[str] = []

    def run(self, work):
        return self.loop.run_until_complete(work)

    def close(self) -> None:
        self.run(self.stack.aclose())
        self.loop.close()

    @property
    def kit(self):
        return self.scene.service.kit

    async def open(self) -> None:
        service = ToyService()
        await self.stack.enter_async_context(service.app.router.lifespan_context(service.app))
        http = await self.stack.enter_async_context(service.client())
        self.scene = await Scene.set_up(service, http)

    async def pending(self) -> set[str]:
        """The activities of the tenant that wait to be relayed."""
        tenancy = self.kit.tenancy
        async with tenancy.tenant_session(self.scene.tenant_iri, tenancy.toolkit) as session:
            return {iri for iri, _ in await session.pending_activities()}

    async def relayed(self, activity: str) -> bool:
        """Whether the activity carries a ``relayed_at``."""
        tenant = self.scene.tenant_iri
        graph = self.kit.iris.provenance(tenant)
        answer = await self.scene.service.store.query(
            self.kit.tenancy.database_of(tenant),
            f"ASK {{ GRAPH <{graph}> {{ <{activity}> <{v.RELAYED_AT}> ?at }} }}",
        )
        return bool(answer.askAnswer)

    async def all_relayed(self, activities: set[str]) -> bool:
        return all([await self.relayed(a) for a in activities])

    async def post_book(self, label: str) -> httpx.Response:
        scene = self.scene
        return await scene.http.post(
            f"{scene.tenant}/books", json={**DUNE_BODY, "label": label}, headers=scene.headers(ADA)
        )

    async def aim_a_fault(self) -> None:
        store = self.scene.service.store
        for run in range(RUNS):
            async with self.kit.relay.paused():
                before = await self.pending()
                committed = await self.post_book(f"Commit {run}")
                assert committed.status_code == 201, committed.text
                activities = (await self.pending()) - before
                assert activities, f"run {run}: the commit's activity is still pending"
                store.on("update", StoreUnavailable("down"))
                self.answers.append(await self.post_book(f"Fault {run}"))
            # the woken relay runs the round the block kept out; wait for it, never run it by hand
            with contextlib.suppress(TimeoutError):  # a relay that never runs shows in `unrelayed`
                await wait_until_async(
                    partial(self.all_relayed, activities),
                    f"run {run}: the relay marks every activity",
                    timeout=RELAY_TIMEOUT,
                )
            self.unrelayed += [a for a in activities if not await self.relayed(a)]

    async def replace_twice(self) -> None:
        scene = self.scene
        store = scene.service.store

        def put(label: str):
            return scene.http.put(
                scene.book,
                json={**DUNE_BODY, "label": label},
                headers=scene.headers(ADA, **{"If-Match": scene.book_etag}),
            )

        async with self.kit.relay.paused(), store.hold("update", until=2):
            self.answers = list(await asyncio.gather(put("Dune A"), put("Dune B")))


@pytest.fixture
def faults():
    made = Faults()
    yield made
    made.close()


@given("a service over the fake store with its relay running")
def _service(faults):
    faults.run(faults.open())


@when(
    "inside a paused relay a commit leaves an activity pending, the store is told to fail and a book is posted, twenty times"
)
def _aimed(faults):
    faults.run(faults.aim_a_fault())


@then(
    "every post is answered 503 unavailable and, after the block, each pending activity is relayed"
)
def _answered_503(faults):
    assert len(faults.answers) == RUNS, "every run posted"
    for answer in faults.answers:
        assert_problem(answer, 503, "unavailable")
    assert faults.unrelayed == [], "every activity pending in the block was relayed after it"


@when(
    "two requests replace the same book at the same version at once, the relay paused and the store's update held"
)
def _two_writers(faults):
    faults.run(faults.replace_twice())


@then("one is answered 200 and the other 409 conflict, and the stored book is the winner's")
def _one_wins(faults):
    won, lost = sorted(faults.answers, key=lambda a: a.status_code)
    assert (won.status_code, lost.status_code) == (200, 409), "one commits, the other conflicts"
    assert_problem(lost, 409, "conflict")

    async def stored():
        scene = faults.scene
        return await scene.http.get(scene.book, headers=scene.headers(ADA))

    kept = faults.run(stored())
    assert kept.headers["etag"] == won.headers["etag"], "the stored version is the winner's"
    assert kept.json()["label"] == won.json()["label"], "the stored book is the winner's"

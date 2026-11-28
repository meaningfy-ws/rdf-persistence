"""Steps of ``dependent_aggregates.feature`` (dependent-aggregates 2.9).

Scenario to requirement: 1, 2, 4 to 9 are of ``rp-aggregate-store`` and run on a session over the fake
store (an audit, its results, a result's finding); 3 is of ``rp-service-api`` and runs through the real
delete route on the toy service, where Bob's rights are checked. A "held" step parks one request at its
update (``PausingStore``) so another writer acts in that window. Nothing sleeps.
"""

import asyncio
from contextlib import AsyncExitStack

import httpx
import pytest
from pytest_bdd import given, parsers, scenario, scenarios, then, when
from rdflib import RDF, URIRef

from rdf_persistence import GrantSet
from rdf_persistence.access.domain.generated.rp_access import Action, Grant
from rdf_persistence.core.domain.exceptions import (
    CommitTooLarge,
    Conflict,
    InUse,
    NotFound,
    PersistenceError,
)
from rdf_persistence.core.domain.generated.rp_core import DependenceLink
from rdf_persistence.files.domain.generated.rp_files import RdfFormat
from rdf_persistence.iris.domain.layout import graph_iri
from rdf_persistence.provenance.domain.generated.rp_provenance import Remove
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.events_follow import reshape_grants
from tests.integration.store.pausing_store import PausingStore
from tests.scene import Scene
from tests.toy_service import ToyService, principal_of
from tests.unit.activity_helpers import Hook
from tests.unit.persistence.dependent_helpers import (
    A1,
    A2,
    LIB,
    LINK,
    OF_AUDIT,
    R1,
    R2,
    R3,
    RESULT,
    audit,
    iri,
    is_stored,
    names,
    new_store,
    opened,
    result,
)
from tests.unit.persistence.referrer_helpers import StubRefusal

FINDING, OF_RESULT, CITES = (
    URIRef(LIB + name) for name in ("Finding", "of_result", "cites_finding")
)
LINK_F = DependenceLink(
    part_classes=[str(FINDING)], pointer=str(OF_RESULT), whole_classes=[str(RESULT)]
)
LINKS = (LINK, LINK_F)
F1 = iri("findings", 1)
ROOTS = {"A1": A1, "A2": A2, "R1": R1, "R2": R2, "R3": R3, "F1": F1}
REPORT = b"<https://example.org/a> <https://example.org/b> <https://example.org/c> ."
BODY = {"label": "Item", "description": "An item."}


def finding(root: str, whole: str) -> list:
    return [(URIRef(root), RDF.type, FINDING), (URIRef(root), OF_RESULT, URIRef(whole))]


class Http:
    """Ada's library on the toy service, for the one scenario that needs access checks."""

    def __init__(self, scene: Scene) -> None:
        self.scene = scene
        self.audit = self.result = ""

    def url(self, root: str, collection: str) -> str:
        return f"{self.scene.tenant}/{collection}/{root.rsplit('/', 1)[1]}"

    async def created(self, collection: str, **slots: str) -> str:
        made = await self.scene.http.post(
            f"{self.scene.tenant}/{collection}",
            json={**BODY, **slots},
            headers=self.scene.headers("ada"),
        )
        assert made.status_code == 201, made.text
        return made.json()["id"]

    async def delete(self, who: str) -> httpx.Response:
        url, http = self.url(self.audit, "audits"), self.scene.http
        etag = (await http.get(url, headers=self.scene.headers("ada"))).headers["etag"]
        return await http.delete(url, headers=self.scene.headers(who, **{"If-Match": etag}))

    async def result_exists(self) -> bool:
        url = self.url(self.result, "audit-results")
        return (
            await self.scene.http.get(url, headers=self.scene.headers("ada"))
        ).status_code == 200

    async def let_bob_delete_the_audit(self) -> None:
        target = str(graph_iri(self.audit))
        bob = Grant(assignee=principal_of("bob"), target=target, action=Action.DELETE)
        await reshape_grants(self.scene, lambda held: GrantSet(grants=[*(held.grants or []), bob]))


class Run:
    """One scenario: a store (or the toy service), the sessions it opens, and what the steps saw."""

    def __init__(self, backend: str) -> None:
        self.loop = asyncio.new_event_loop()
        self.stack = AsyncExitStack()
        self.hook = Hook()
        self.removals: StubRefusal | None = None
        self.max_roots = 10
        self.errors: dict[str, PersistenceError | None] = {}
        self.pause: PausingStore | None = None
        self.task: asyncio.Task | None = None
        self.loaded: URIRef | None = None
        self.audit_version = ""
        self.response: httpx.Response | None = None
        self.http: Http | None = None
        self.store = self.run(new_store())
        if backend == "http":
            self.http = self.run(self.start_http())

    def run(self, work):
        return self.loop.run_until_complete(work)

    async def start_http(self) -> Http:
        toy = ToyService()
        await self.stack.enter_async_context(toy.app.router.lifespan_context(toy.app))
        client = await self.stack.enter_async_context(toy.client())
        return Http(await Scene.set_up(toy, client))

    def close(self) -> None:
        if self.task is not None and not self.task.done():
            self.task.cancel()
        self.run(self.stack.aclose())
        self.loop.close()

    def session(self, who: str = "ada", store=None):
        return opened(
            store or self.store,
            who,
            links=LINKS,
            max_roots=self.max_roots,
            on_commit=self.hook,
            removals=self.removals,
        )

    async def write(self, root: str, triples: list, who: str = "worker", store=None) -> str:
        async with self.session(who, store) as session:
            return await session.add_graph(root, triples)

    async def version(self, root: str) -> str:
        async with self.session() as session:
            return (await session.get_graph(root))[2]

    async def delete(self, root: str, store=None) -> None:
        async with self.session("ada", store) as session:
            await session.remove(root, (await session.get_graph(root))[2])

    async def stored(self, root: str) -> bool:
        async with self.session() as session:
            return await is_stored(session, root)

    async def attempt(self, who: str, work) -> None:
        """Run ``work``; keep the refusal it ended with (or ``None``) under ``who``."""
        try:
            await work
        except PersistenceError as refusal:
            self.errors[who] = refusal
        else:
            self.errors[who] = None

    async def asked(self, sparql: str) -> bool:
        return bool((await self.store.query(FAKE_DATABASE, sparql)).askAnswer)

    def hold(self, who: str, work_on) -> None:
        """Start ``work_on(pausing_store)`` and return once it waits at its update."""
        self.pause = PausingStore(self.store)
        self.task = self.loop.create_task(self.attempt(who, work_on(self.pause)))
        self.run(self.pause.paused(self.task))

    def release(self) -> None:
        assert self.pause is not None, "a request is held"
        assert self.task is not None, "its task is running"
        self.pause.release()
        self.run(self.task)


@pytest.fixture
def backend() -> str:
    return "session"


@pytest.fixture
def lib(backend: str):
    made = Run(backend)
    yield made
    made.close()


@pytest.mark.parametrize("backend", ["http"])
@scenario(
    "dependent_aggregates.feature", "Deleting an audit needs only the right to delete the audit"
)
def test_deleting_an_audit_needs_only_the_right_to_delete_the_audit(backend):
    """Runs on the toy service: the right to delete is checked by the route."""
    assert backend == "http", "this scenario runs through the route"


scenarios("dependent_aggregates.feature")


# --- background and the shared givens ---------------------------------------------------------
@given('Ada has a library with an audit "A1"')
def _library(lib):
    if lib.http is not None:
        lib.http.audit = lib.run(lib.http.created("audits"))
    else:
        lib.run(lib.write(A1, audit(A1), "ada"))


@given('the audit "A1" has a result "R1"')
def _one_result(lib):
    if lib.http is not None:
        lib.http.result = lib.run(lib.http.created("audit-results", of_audit=lib.http.audit))
    else:
        lib.run(lib.write(R1, result(R1, A1)))


@given('the audit "A1" has results "R1" and "R2"')
def _two_results(lib):
    for root in (R1, R2):
        lib.run(lib.write(root, result(root, A1)))


@given('the audit "A1" has results "R1", "R2" and "R3"')
def _three_results(lib):
    for root in (R1, R2, R3):
        lib.run(lib.write(root, result(root, A1)))


@given('the audit "A1" has a result "R1" with a finding "F1"')
def _result_and_finding(lib):
    lib.run(lib.write(R1, result(R1, A1)))
    lib.run(lib.write(F1, finding(F1, R1)))


@given('Ada has an audit "A2"')
def _second_audit(lib):
    lib.run(lib.write(A2, audit(A2), "ada"))


# --- 1: a result after the audit's deletion ---------------------------------------------------
@given('Ada has deleted the audit "A1"')
def _deleted(lib):
    lib.run(lib.delete(A1))


@when('a worker writes a result for the audit "A1"')
def _worker_writes(lib):
    lib.run(lib.attempt("worker", lib.write(R1, result(R1, A1))))


@then('the worker is told the audit "A1" is not found')
def _worker_not_found(lib):
    refusal = lib.errors["worker"]
    assert isinstance(refusal, NotFound), f"the worker is told not found, not {refusal!r}"
    assert names(refusal, A1), "the answer names the audit"


@then('no result of the audit "A1" is stored')
def _no_result_of_a1(lib):
    pointing = f"ASK {{ GRAPH ?g {{ ?r <{OF_AUDIT}> <{A1}> }} }}"
    assert not lib.run(lib.asked(pointing)), "no stored graph points to the audit"


# --- 2: the cascade and its change ------------------------------------------------------------
@given('the result "R1" has a finding "F1" and a loaded report file')
def _finding_and_file(lib):
    async def go():
        await lib.write(F1, finding(F1, R1))
        async with lib.session("ada") as session:
            version = (await session.get_graph(R1))[2]
            lib.loaded = await session.load_graph(R1, REPORT, rdf_format=RdfFormat.TURTLE)
            await session.replace_graph(R1, result(R1, A1), version, [lib.loaded])

    lib.run(go())


@when(parsers.parse('{who} deletes the audit "A1"'))
def _deletes(lib, who):
    if lib.http is not None:
        lib.response = lib.run(lib.http.delete(who.lower()))
    else:
        lib.run(lib.attempt(who.lower(), lib.delete(A1)))


@then('the audit "A1", the results "R1" and "R2", the finding "F1" and the report file are gone')
def _all_gone(lib):
    stored = [lib.run(lib.stored(root)) for root in (A1, R1, R2, F1)]
    assert stored == [False] * 4, "the audit, both results and the finding are gone"
    held = f"ASK {{ GRAPH <{lib.loaded}> {{ ?s ?p ?o }} }}"
    assert not lib.run(lib.asked(held)), "the loaded report file went with its result"


@then("one change is recorded with a deletion for each of the four")
def _one_change(lib):
    removed = [a for a, _ in lib.hook.calls if isinstance(a, Remove)]
    assert len(removed) == 1, "one change recorded the deletion"
    entities = sorted(i.entity for i in removed[0].invalidations or [])
    assert entities == sorted([A1, R1, R2, F1]), "it holds a deletion for each of the four"


# --- 3: the right to delete the audit is enough -----------------------------------------------
@given('Bob may delete the audit "A1" and holds no right on its results')
def _bob(lib):
    lib.run(lib.http.let_bob_delete_the_audit())


@then("the deletion succeeds")
def _succeeds(lib):
    assert lib.response is not None, "the route answered"
    assert lib.response.status_code == 204, "the route answers 204"


@then('the result "R1" is gone')
def _result_gone(lib):
    assert not lib.run(lib.http.result_exists()), "the result went with its audit"


# --- 4: above the limit of one change ---------------------------------------------------------
@given("one change may hold at most 3 aggregates")
def _limit(lib):
    lib.max_roots = 3


@then("Ada is told the change is too large, with the limit 3")
def _too_large(lib):
    refusal = lib.errors["ada"]
    assert isinstance(refusal, CommitTooLarge), f"Ada is told too large, not {refusal!r}"
    assert "3" in str(refusal), "the answer gives the limit"


@then('the audit "A1" and its three results remain')
def _four_remain(lib):
    stored = [lib.run(lib.stored(root)) for root in (A1, R1, R2, R3)]
    assert stored == [True] * 4, "nothing was deleted"


# --- 5: a finding another audit cites ---------------------------------------------------------
@given("findings may not be deleted while referred to")
def _refusing(lib):
    lib.removals = StubRefusal(refusing=frozenset({FINDING}))


@given('the audit "A2" cites the finding "F1"')
def _cites(lib):
    lib.run(lib.write(A2, [*audit(A2), (URIRef(A2), CITES, URIRef(F1))], "ada"))


@then('Ada is told the deletion is refused because the finding is in use by the audit "A2"')
def _in_use(lib):
    refusal = lib.errors["ada"]
    assert isinstance(refusal, InUse), f"Ada is told in use, not {refusal!r}"
    assert refusal.iris == (F1,), "the refused part is the finding"
    assert [row[0] for row in refusal.referrers] == [A2], "the audit A2 is its referrer"


@then('the audit "A1", the result "R1" and the finding "F1" remain')
def _three_remain(lib):
    stored = [lib.run(lib.stored(root)) for root in (A1, R1, F1)]
    assert stored == [True] * 3, "all or nothing: all three remain"


# --- 6: the pointer is fixed ------------------------------------------------------------------
@when('Ada replaces the result "R1" so that it belongs to the audit "A2"')
def _move(lib):
    async def go():
        async with lib.session("ada") as session:
            version = (await session.get_graph(R1))[2]
            await session.replace_graph(R1, result(R1, A2), version)

    lib.run(lib.attempt("ada", go()))


@then("Ada is told of a conflict on the result's audit")
def _pointer_conflict(lib):
    refusal = lib.errors["ada"]
    assert isinstance(refusal, Conflict), f"Ada is told of a conflict, not {refusal!r}"
    assert str(OF_AUDIT) in str(refusal), "the conflict names the audit slot"
    assert refusal.iris == (R1,), "the conflict names the result"


@then('the result "R1" still belongs to the audit "A1"')
def _still_a1(lib):
    async def go():
        async with lib.session("ada") as session:
            return (await session.get_graph(R1))[0]

    graph = lib.run(go())
    assert list(graph.objects(URIRef(R1), OF_AUDIT)) == [URIRef(A1)], "R1 points to A1 alone"


# --- 7: two workers at the same time ----------------------------------------------------------
@when('two workers each write a result for the audit "A1" at the same time')
def _two_workers(lib):
    async def go():
        lib.audit_version = await lib.version(A1)
        await asyncio.gather(
            lib.attempt("first", lib.write(R1, result(R1, A1), "worker-1")),
            lib.attempt("second", lib.write(R2, result(R2, A1), "worker-2")),
        )

    lib.run(go())


@then("both results are stored")
def _both(lib):
    assert lib.errors == {"first": None, "second": None}, "neither worker was refused"
    stored = [lib.run(lib.stored(root)) for root in (R1, R2)]
    assert stored == [True, True], "both results are stored"


@then('the audit "A1" has not changed')
def _audit_unchanged(lib):
    assert lib.run(lib.version(A1)) == lib.audit_version, "the audit kept its version"


# --- 8: a result written after the deletion looked for results --------------------------------
@given('Ada\'s deletion of the audit "A1" has looked for its results and is held before it is sent')
def _held_deletion(lib):
    lib.hold("ada", lambda held: lib.delete(A1, held))


@when('a worker writes a result "R3" for the audit "A1"')
def _worker_r3(lib):
    lib.run(lib.attempt("worker", lib.write(R3, result(R3, A1))))


@when("Ada's deletion is sent")
def _send_deletion(lib):
    lib.release()


@then('Ada is told of a conflict on the audit "A1"')
def _audit_conflict(lib):
    refusal = lib.errors["ada"]
    assert isinstance(refusal, Conflict), f"Ada is told of a conflict, not {refusal!r}"
    assert A1 in refusal.iris, "the conflict names the audit"


@then('the audit "A1" and the result "R3" remain')
def _a1_r3_remain(lib):
    assert lib.errors["worker"] is None, "the worker's result was accepted"
    stored = [lib.run(lib.stored(root)) for root in (A1, R3)]
    assert stored == [True, True], "the deletion was not applied"


# --- 9: a result checked before the audit was deleted -----------------------------------------
@given(
    'a worker\'s result "R3" for the audit "A1" has found the audit and is held before it is sent'
)
def _held_result(lib):
    lib.hold("worker", lambda held: lib.write(R3, result(R3, A1), store=held))


@when("the worker's result is sent")
def _send_result(lib):
    lib.release()


@then('no result "R3" is stored')
def _no_r3(lib):
    assert lib.errors["ada"] is None, "Ada's deletion went through"
    assert not lib.run(lib.stored(R3)), "the late result is not stored"

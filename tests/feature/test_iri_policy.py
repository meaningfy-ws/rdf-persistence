"""Steps of ``iri_policy.feature``: the toy library served end to end with the fakes (iri-policy 3.4)."""

import asyncio
import re

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from rdflib import RDF, Graph, URIRef

from rdf_persistence import Action, GrantSet
from rdf_persistence.access.domain.generated.rp_access import Grant
from rdf_persistence.core.domain.exceptions import IriPolicyChanged
from rdf_persistence.core.domain.media import JSON
from rdf_persistence.iris.services.generated.rp_iris_services import IriPolicy
from rdf_persistence.iris.services.iris import draw_id
from rdf_persistence.schema.services import vocabulary as v
from tests.toy_service import DUNE_BODY, EXAMPLE_POLICY, TENANT_BODY, ToyService, principal_of

scenarios("iri_policy.feature")

BASE = "https://example.org/library/"
ID = r"[a-z0-9]"


class Run:
    """One service and what the scenario has seen of it so far."""

    def __init__(self) -> None:
        self.toy = ToyService(iri_policy=EXAMPLE_POLICY)
        asyncio.run(self.toy.kit.tenancy.ensure_system_database())
        self.headers = self.toy.bearer("ada")
        self.last: httpx.Response | None = None
        self.tenant: httpx.Response | None = None
        self.book: httpx.Response | None = None
        self.comment = ""
        self.updates = 0
        self.draws = Counting()
        self.refused: IriPolicyChanged | None = None

    def call(self, method: str, url: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            async with self.toy.client() as http:
                return await http.request(method, url, headers=self.headers, **kwargs)

        self.last = asyncio.run(send())
        return self.last

    @property
    def book_path(self) -> str:
        assert self.book is not None, "the book was created"
        return self.book.headers["location"]


@pytest.fixture
def run() -> Run:
    return Run()


@given("the library service runs under the example policy")
def _service(run: Run) -> None:
    assert run.toy.kit.iris.settings.iri_policy == EXAMPLE_POLICY, (
        "the service runs under the example policy"
    )


@when("Ada creates a library")
def _create_library(run: Run) -> None:
    run.tenant = run.call("POST", "/libraries", json=TENANT_BODY)
    assert run.tenant.status_code == 201, run.tenant.text


@then(parsers.parse('the library IRI is under "{segment}" and ends in a 7-character id'))
def _library_iri(run: Run, segment: str) -> None:
    assert run.tenant is not None, "the library was created"
    assert re.fullmatch(f"{re.escape(BASE)}{segment}{ID}{{7}}", run.tenant.json()["id"]), (
        "the library IRI is the library path and a short id"
    )


@then("its Location path ends in that id")
def _library_location(run: Run) -> None:
    assert run.tenant is not None, "the library was created"
    assert run.tenant.headers["location"] == "/libraries/" + run.tenant.json()["id"][-7:], (
        "the library's location is its short id"
    )


@when("Ada adds a book with a chapter to it")
def _add_book(run: Run) -> None:
    assert run.tenant is not None, "the library was created"
    run.book = run.call("POST", f"{run.tenant.headers['location']}/books", json=DUNE_BODY)
    assert run.book.status_code == 201, run.book.text


def _tenant_id(run: Run) -> str:
    assert run.tenant is not None, "the library was created"
    return run.tenant.json()["id"][-7:]


@then(parsers.parse('the book IRI is flat beside the library id under "{kind}"'))
def _book_iri(run: Run, kind: str) -> None:
    assert run.book is not None, "the book was created"
    assert re.fullmatch(
        f"{re.escape(BASE)}{_tenant_id(run)}/{kind}/{ID}{{13}}", run.book.json()["id"]
    ), "the book IRI has the flat shape of the policy"


@then(parsers.parse('the chapter IRI is flat beside the library id under "{kind}"'))
def _chapter_iri(run: Run, kind: str) -> None:
    assert run.book is not None, "the book was created"
    chapter = run.book.json()["chapters"][0]["id"]
    assert re.fullmatch(f"{re.escape(BASE)}{_tenant_id(run)}/{kind}/{ID}{{13}}", chapter), (
        "the chapter IRI has the flat shape of the policy"
    )


@then("the book Location path ends in the book id")
def _book_location(run: Run) -> None:
    assert run.book is not None, "the book was created"
    assert run.book_path == f"/libraries/{_tenant_id(run)}/books/{run.book.json()['id'][-13:]}", (
        "the book's location is the library and its short id"
    )


@then("reading the book answers its IRI and its chapter")
def _read_book(run: Run) -> None:
    assert run.book is not None, "the book was created"
    body = run.call("GET", run.book_path).json()
    assert body["id"] == run.book.json()["id"], "the book read back has the same IRI"
    assert [c["id"] for c in body["chapters"]] == [c["id"] for c in run.book.json()["chapters"]], (
        "the book read back has the same chapters"
    )


@then("listing the books answers the book")
def _list_books(run: Run) -> None:
    assert run.book is not None, "the book was created"
    listing = run.call("GET", run.book_path.rsplit("/", 1)[0]).json()
    assert [item["id"] for item in listing["items"]] == [run.book.json()["id"]], (
        "the listing holds the created book"
    )


@when("Ada replaces the book with a new label")
def _replace_book(run: Run) -> None:
    current = run.call("GET", run.book_path)
    body = {**current.json(), "label": "Dune Messiah"}
    run.headers = {**run.headers, "If-Match": current.headers["etag"], "Content-Type": JSON}
    replaced = run.call("PUT", run.book_path, json=body)
    assert replaced.status_code == 200, replaced.text
    run.headers = {k: v for k, v in run.headers.items() if k not in ("If-Match", "Content-Type")}


@then("reading the book answers the new label")
def _read_new_label(run: Run) -> None:
    assert run.call("GET", run.book_path).json()["label"] == "Dune Messiah", (
        "the new label is read back"
    )


@when("Ada deletes the book")
def _delete_book(run: Run) -> None:
    etag = run.call("GET", run.book_path).headers["etag"]
    run.headers = {**run.headers, "If-Match": etag}
    assert run.call("DELETE", run.book_path).status_code == 204, (
        "the delete is answered with no content"
    )
    run.headers = {k: v for k, v in run.headers.items() if k != "If-Match"}


@then("reading the book answers 404")
def _book_gone(run: Run) -> None:
    assert run.call("GET", run.book_path).status_code == 404, "the deleted book is gone"


@when(parsers.parse('Ada reads "{path}"'))
def _read(run: Run, path: str) -> None:
    run.call("GET", path)


@then(parsers.parse("the answer is {status:d}"))
def _answer(run: Run, status: int) -> None:
    assert run.last is not None, "a call was answered"
    assert run.last.status_code == status, "the answer has the expected status"


# -- activities under the IRI policy (activity-iri-policy 1.7) ------------------------------------

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


class Counting:
    """An id source that draws like the default and counts its draws."""

    def __init__(self) -> None:
        self.drawn = 0

    def __call__(self, *args, **kwargs) -> str:
        self.drawn += 1
        return draw_id(*args, **kwargs)


def _under(template: str) -> IriPolicy:
    return EXAMPLE_POLICY.model_copy(update={"activity_template": template})


def _with_collaboration(run: Run, work) -> object:
    """Run ``work(collaboration)`` as Ada on the library of the scenario."""
    assert run.tenant is not None, "the library was created"

    async def go() -> object:
        authorised = await run.toy.kit.require(
            run.headers["Authorization"],
            run.tenant.headers["location"].rsplit("/", 1)[1],
            Action.READ,
        )
        async with run.toy.kit.collaboration(authorised) as collaboration:
            return await work(collaboration)

    return asyncio.run(go())


def _provenance(run: Run) -> Graph:
    """The provenance graph of the library of the scenario."""
    assert run.tenant is not None, "the library was created"
    tenant = run.tenant.json()["id"]
    text = f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{run.toy.kit.iris.provenance(tenant)}> {{ ?s ?p ?o }} }}"
    found = asyncio.run(run.toy.store.query(run.toy.kit.tenancy.database_of(tenant), text))
    return found.graph or Graph()


def _generating(graph: Graph, entity: str, kind: URIRef | None = None) -> str:
    """The IRI of the one activity (of type ``kind``, if given) that generated ``entity``."""
    found = {
        str(activity)
        for activity in graph.subjects(RDF.type, v.ACTIVITY)
        if (kind is None or (activity, RDF.type, kind) in graph)
        and URIRef(entity)
        in {graph.value(part, v.ENTITY) for part in graph.objects(activity, v.HAS_GENERATION)}
    }
    assert len(found) == 1, f"one activity generated {entity}: {sorted(found)}"
    return found.pop()


def _move(run: Run) -> str:
    """The IRI of the move's activity, read from the provenance graph."""
    assert run.book is not None, "the book was created"
    return _generating(_provenance(run), run.book.json()["id"], v.TRANSITION)


@given("Ada has a library with a book")
def _library_with_a_book(run: Run) -> None:
    _create_library(run)
    _add_book(run)


@given(
    parsers.parse(
        'the library service runs under the example policy with activity template "{template}"'
    )
)
def _service_with_activity_template(run: Run, template: str) -> None:
    run.toy = ToyService(iri_policy=_under(template))
    asyncio.run(run.toy.kit.tenancy.ensure_system_database())
    run.headers = run.toy.bearer("ada")
    assert run.toy.kit.iris.settings.iri_policy.activity_template == template, (
        "the service runs under the activity template"
    )


@when("Ada moves the book to its next state with a comment")
def _move_the_book(run: Run) -> None:
    version = run.call("GET", run.book_path).headers["etag"].strip('"')
    assert run.book is not None, "the book was created"
    _with_collaboration(
        run,
        lambda c: c.transition(
            run.book.json()["id"], "in_review", if_version=version, comment="Ready for review"
        ),
    )


def _allow_annotating(run: Run) -> None:
    """Grant Ada the action ``annotate`` on the library, beside the grants it has."""
    assert run.tenant is not None, "the library was created"
    grants_path = f"{run.tenant.headers['location']}/grants"
    current = run.call("GET", grants_path)
    body = GrantSet.model_validate(current.json())
    added = Grant(
        assignee=principal_of("ada"), target=run.tenant.json()["id"], action=Action.ANNOTATE
    )
    kept = run.headers
    run.headers = {**kept, "If-Match": current.headers["etag"], "Content-Type": JSON}
    granted = run.call(
        "PUT",
        grants_path,
        content=GrantSet(grants=[*(body.grants or []), added]).model_dump_json(exclude_none=True),
    )
    run.headers = kept
    assert granted.status_code == 200, granted.text


@when("Ada posts a comment on the book")
def _post_a_comment(run: Run) -> None:
    assert run.book is not None, "the book was created"
    _allow_annotating(run)
    run.comment = _with_collaboration(
        run, lambda c: c.comment(run.book.json()["id"], "A remark on the book")
    )


@then('the move\'s activity IRI is "urn:uuid:" followed by a UUID')
def _move_is_a_urn(run: Run) -> None:
    assert re.fullmatch(f"urn:uuid:{UUID}", _move(run)), "the move's activity IRI is a urn:uuid"


@then("the book's transitions name that activity")
@then("the book's transitions name the move's activity")
def _transitions_name_the_move(run: Run) -> None:
    assert run.book is not None, "the book was created"
    moves = _with_collaboration(run, lambda c: c.transitions(run.book.json()["id"]))
    assert [m.id for m in moves] == [_move(run)], "the one move listed is the recorded activity"


@then('each of the three activity IRIs is the library IRI, "/activity/" and a UUID')
def _three_placed(run: Run) -> None:
    assert run.tenant is not None, "the library was created"
    assert run.book is not None, "the book was created"
    graph = _provenance(run)
    activities = {
        "move": _move(run),
        "comment": _generating(graph, run.comment),
        "replace": _generating(graph, run.book.json()["id"], v.REPLACE),
    }
    assert len(set(activities.values())) == 3, f"three distinct activities: {activities}"
    for name, iri in activities.items():
        assert re.fullmatch(f"{re.escape(run.tenant.json()['id'])}/activity/{UUID}", iri), (
            f"the {name}'s activity IRI is under its tenant: {iri}"
        )


@then("the comment's thread names the comment's activity")
def _thread_names_the_comment(run: Run) -> None:
    assert run.book is not None, "the book was created"
    thread = _with_collaboration(run, lambda c: c.thread(run.book.json()["id"]))
    assert run.comment in [c.id for c in thread], "the thread holds the comment"
    activity = _generating(_provenance(run), run.comment)
    assert re.fullmatch(f".*/activity/{UUID}", activity), (
        "the comment's recorded activity is the one placed under the tenant"
    )


@then('the library\'s provenance holds the three activities and no "urn:uuid:" IRI')
def _provenance_is_placed(run: Run) -> None:
    assert run.book is not None, "the book was created"
    graph = _provenance(run)
    held = {str(a) for a in graph.subjects(RDF.type, v.ACTIVITY)}
    named = {
        _move(run),
        _generating(graph, run.comment),
        _generating(graph, run.book.json()["id"], v.REPLACE),
    }
    assert named <= held, "the provenance holds the three activities"
    assert not [str(t) for triple in graph for t in triple if str(t).startswith("urn:uuid:")], (
        "no urn:uuid: IRI in the provenance graph"
    )


@given("the library service has started once with no activity template")
def _started_once(run: Run) -> None:
    async def start() -> None:
        async with run.toy.app.router.lifespan_context(run.toy.app):
            pass

    asyncio.run(start())
    assert run.toy.kit.iris.effective_policy.activity_template == IriPolicy().activity_template, (
        "no activity template: the default one"
    )
    run.updates = len(run.toy.store.sent("update"))
    assert run.updates > 0, "the first start recorded its policy"


@when(parsers.parse('it is restarted with activity template "{template}"'))
def _restart(run: Run, template: str) -> None:
    run.draws = Counting()
    again = ToyService(
        run.toy.store, run.toy.files, iri_policy=_under(template), id_source=run.draws
    )

    async def start() -> None:
        async with again.app.router.lifespan_context(again.app):
            pass

    try:
        asyncio.run(start())
    except IriPolicyChanged as error:
        run.refused = error


@then(parsers.parse('start-up fails naming "{field}"'))
def _start_up_fails(run: Run, field: str) -> None:
    assert isinstance(getattr(run, "refused", None), IriPolicyChanged), "the restart was refused"
    assert field in str(run.refused), "the refusal names the field"


@then("no IRI has been minted")
def _nothing_minted(run: Run) -> None:
    assert run.draws.drawn == 0, "no id was drawn"
    assert len(run.toy.store.sent("update")) == run.updates, "nothing was written by the restart"

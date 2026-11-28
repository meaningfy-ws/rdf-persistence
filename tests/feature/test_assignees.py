"""Steps of ``assignees.feature``: the assignees of a book, set through the toolkit and read through the service (rp-workflow)."""

import asyncio
from pathlib import Path

import httpx
import pytest
import yaml
from pytest_bdd import given, parsers, scenarios, then, when

from rdf_persistence import GrantSet
from rdf_persistence.access.domain.generated.rp_access import Action, Grant
from rdf_persistence.collaboration.domain.generated.rp_workflow import Assignment
from rdf_persistence.collaboration.services.workflows import load_workflow
from rdf_persistence.core.domain.media import JSON
from tests.toy import REVIEW_WORKFLOW, graph_of
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, principal_of

scenarios("assignees.feature")

ADA = "ada"


class Run:
    """One service whose review workflow is assignable, and what the scenario has seen of it so far."""

    def __init__(self, folder: Path) -> None:
        assignable = load_workflow(REVIEW_WORKFLOW).model_copy(update={"assignable": True})
        workflow_file = folder / "assignable.workflow.yaml"
        workflow_file.write_text(
            yaml.safe_dump(assignable.model_dump(mode="json", exclude_none=True)), encoding="utf-8"
        )
        self.toy = ToyService(workflows=[workflow_file])
        asyncio.run(self.toy.kit.tenancy.ensure_system_database())
        self.headers = self.toy.bearer(ADA)
        self.tenant_path = ""
        self.tenant_iri = ""
        self.books: dict[str, dict[str, str]] = {}  # name -> iri and version
        self.answer: httpx.Response | None = None

    def person(self, name: str) -> str:
        return principal_of(name.lower())


@pytest.fixture
def run(tmp_path: Path) -> Run:
    return Run(tmp_path)


@given(parsers.parse("Ada's library holds the books {names}"))
def _library_with_books(run: Run, names: str) -> None:
    labels = [n.strip() for n in names.replace(" and ", ", ").split(",")]

    async def create() -> None:
        async with run.toy.client() as http:
            tenant = await http.post("/libraries", json=TENANT_BODY, headers=run.headers)
            assert tenant.status_code == 201, tenant.text
            run.tenant_path, run.tenant_iri = tenant.headers["location"], tenant.json()["id"]
            for label in labels:
                book = await http.post(
                    f"{run.tenant_path}/books",
                    json={**DUNE_BODY, "label": label},
                    headers=run.headers,
                )
                assert book.status_code == 201, book.text
                run.books[label] = {
                    "iri": book.json()["id"],
                    "version": book.headers["etag"].strip('"'),
                }

    asyncio.run(create())


@given("Pia and Pol may read the library")
def _readers(run: Run) -> None:
    async def grant() -> None:
        async with run.toy.client() as http:
            held = await http.get(f"{run.tenant_path}/grants", headers=run.headers)
            body = GrantSet.model_validate(held.json())
            readers = [
                Grant(assignee=run.person(who), target=run.tenant_iri, role="reader")
                for who in ("Pia", "Pol")
            ]
            put = await http.put(
                f"{run.tenant_path}/grants",
                content=GrantSet(grants=[*(body.grants or []), *readers]).model_dump_json(
                    exclude_none=True
                ),
                headers={**run.headers, "If-Match": held.headers["etag"], "Content-Type": JSON},
            )
            assert put.status_code == 200, put.text

    asyncio.run(grant())


@given(parsers.parse("Ada assigns {book} to {people}"))
def _assign(run: Run, book: str, people: str) -> None:
    names = [n.strip() for n in people.replace(" and ", ", ").split(",")]
    tenant_id = run.tenant_path.rsplit("/", 1)[1]

    async def assign() -> None:
        authorised = await run.toy.kit.require(
            run.headers["Authorization"], tenant_id, Action.MODIFY
        )
        async with run.toy.kit.collaboration(authorised) as collaboration:
            await collaboration.assign(
                run.books[book]["iri"],
                [run.person(n) for n in names],
                if_version=run.books[book]["version"],
            )

    asyncio.run(assign())


@given(parsers.parse("Pia holds {grant} on {book}"))
def _own_grant(run: Run, grant: str, book: str) -> None:
    if grant == "no grant":
        return

    async def put() -> None:
        async with run.toy.client() as http:
            held = await http.get(f"{run.tenant_path}/grants", headers=run.headers)
            body = GrantSet.model_validate(held.json())
            own = Grant(
                assignee=run.person("Pia"),
                target=graph_of(run.books[book]["iri"]),
                action=Action.READ,
            )
            sent = await http.put(
                f"{run.tenant_path}/grants",
                content=GrantSet(grants=[*(body.grants or []), own]).model_dump_json(
                    exclude_none=True
                ),
                headers={**run.headers, "If-Match": held.headers["etag"], "Content-Type": JSON},
            )
            assert sent.status_code == 200, sent.text

    asyncio.run(put())


@when("Ada replaces the grants without Pia's reading of the library")
def _replace_without_pia(run: Run) -> None:
    async def put() -> httpx.Response:
        async with run.toy.client() as http:
            held = await http.get(f"{run.tenant_path}/grants", headers=run.headers)
            body = GrantSet.model_validate(held.json())
            kept = [
                g
                for g in body.grants or []
                if not (g.assignee == run.person("Pia") and g.target == run.tenant_iri)
            ]
            return await http.put(
                f"{run.tenant_path}/grants",
                content=GrantSet(grants=kept).model_dump_json(exclude_none=True),
                headers={**run.headers, "If-Match": held.headers["etag"], "Content-Type": JSON},
            )

    run.answer = asyncio.run(put())
    assert run.answer.status_code == 200, run.answer.text


@when(parsers.parse("Ada lists the books assigned to {person}"))
def _list_assigned(run: Run, person: str) -> None:
    async def send() -> httpx.Response:
        async with run.toy.client() as http:
            return await http.get(
                f"{run.tenant_path}/books",
                params={"assigned_to": run.person(person)},
                headers={**run.headers, "Accept": JSON},
            )

    run.answer = asyncio.run(send())


@then(parsers.parse("the listing holds {books}"))
def _holds(run: Run, books: str) -> None:
    assert run.answer is not None, "the books were listed"
    assert run.answer.status_code == 200, run.answer.text
    wanted = set() if books == "none" else {run.books[n.strip()]["iri"] for n in books.split(",")}
    assert {item["id"] for item in run.answer.json()["items"]} == wanted, (
        "the listing holds the books the person is one of the assignees of"
    )


@then(parsers.parse("{book} is assigned to {people}"))
def _is_assigned(run: Run, book: str, people: str) -> None:
    async def read() -> httpx.Response:
        async with run.toy.client() as http:
            return await http.get(
                f"{run.tenant_path}/books", headers={**run.headers, "Accept": JSON}
            )

    listing = asyncio.run(read())
    assert listing.status_code == 200, listing.text
    item = next(i for i in listing.json()["items"] if i["id"] == run.books[book]["iri"])
    wanted = {run.person(n.strip()) for n in people.split(",")}
    assert set(item.get("assigned_to") or []) == wanted, "the service shows these assignees"


@then(parsers.parse("its last assignment, by Ada, released {released}"))
def _last_assignment(run: Run, released: str) -> None:
    book = next(iter(run.books.values()))["iri"]
    tenant_id = run.tenant_path.rsplit("/", 1)[1]

    async def history() -> list[Assignment]:
        authorised = await run.toy.kit.require(run.headers["Authorization"], tenant_id, Action.READ)
        async with run.toy.kit.collaboration(authorised) as collaboration:
            return await collaboration.assignments(book)

    last = asyncio.run(history())[-1]
    wanted = set() if released == "no one" else {run.person(released)}
    assert set(last.released_principals or []) == wanted, "the last assignment released these"
    assert last.was_associated_with == [run.person(ADA)], "Ada is its agent"


@then(parsers.parse("its total is {total:d}"))
def _total(run: Run, total: int) -> None:
    assert run.answer is not None, "the books were listed"
    assert run.answer.json()["total"] == total, "the total counts the same books"
